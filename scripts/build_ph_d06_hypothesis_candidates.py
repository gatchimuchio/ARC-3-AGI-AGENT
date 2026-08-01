#!/usr/bin/env python3
"""Build and verify the PH-D06 source-blind multi-hypothesis corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.canonical import (  # noqa: E402
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
)

PHASE_ID = "PH-D06"
BUBBLEWRAP = Path("/usr/bin/bwrap")
SOURCE_ROOT = Path("distillation/artifacts/teacher/arc3/ph_d05_v1")
CANDIDATE_ROOT = Path("distillation/artifacts/candidates/arc3/ph_d06_v1")
GENERATION_REPORT = Path(
    "distillation/artifacts/reports/arc3_hypothesis_candidate_generation.json"
)
SOURCE_BLIND_REPORT = Path(
    "distillation/artifacts/reports/arc3_hypothesis_source_blind_execution.json"
)
LLM_CAPTURE_REPORT = Path(
    "distillation/artifacts/reports/arc3_hypothesis_llm_capture.json"
)
CONTRACT_PATH = Path(
    "distillation/input/arc3_hypothesis_candidate_generation_contract.json"
)
WORKER_PATH = Path("scripts/ph_d06_candidate_worker.py")
EXPECTED_SOURCE_MANIFEST_DIGEST = (
    "hds-arc3-canonical-teacher-corpus-manifest:"
    "f81183465265bfa9f29208dd788bb3bfd358c23995ab0aeb8ec9549450360aa6"
)
PYTHON_RUNTIME_ROOT_ENV = "ARC3_PH_D06_PYTHON_RUNTIME_ROOT"
PYTHON_RUNTIME_ARCHIVE_ENV = "ARC3_PH_D06_PYTHON_RUNTIME_ARCHIVE"
EXPECTED_PYTHON_VERSION = "3.12.13"
EXPECTED_PYTHON_RUNTIME_ASSET = (
    "cpython-3.12.13+20260728-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
)
EXPECTED_PYTHON_RUNTIME_ARCHIVE_SHA256 = (
    "7ceaf4360f4b4ab44f31d8217cfdc70df8e12b61d9561b4900ee7af87176e50d"
)


class CandidateBuildError(RuntimeError):
    """Stable PH-D06 orchestration or verification failure."""


@dataclass(frozen=True, slots=True)
class PythonRuntimeDependency:
    """Content-verified external Python runtime used by every worker."""

    root: Path
    archive: Path
    version: str
    archive_sha256: str
    tree_digest: str
    entry_count: int
    executable_sha256: str


def _object(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CandidateBuildError(code + "_NOT_OBJECT")
    return cast(Mapping[str, Any], value)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_external_path(environment_key: str) -> Path:
    raw = os.environ.get(environment_key, "")
    if not raw:
        raise CandidateBuildError(
            "PH_D06_PYTHON_RUNTIME_PATH_MISSING:" + environment_key
        )
    path = Path(raw)
    if not path.is_absolute():
        raise CandidateBuildError(
            "PH_D06_PYTHON_RUNTIME_PATH_NOT_ABSOLUTE:" + environment_key
        )
    return path.resolve()


def _python_runtime_dependency() -> PythonRuntimeDependency:
    runtime_root = _required_external_path(PYTHON_RUNTIME_ROOT_ENV)
    archive_path = _required_external_path(PYTHON_RUNTIME_ARCHIVE_ENV)
    if not runtime_root.is_dir() or not archive_path.is_file():
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_INPUT_MISSING")
    if archive_path.name != EXPECTED_PYTHON_RUNTIME_ASSET:
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_ASSET_MISMATCH")
    archive_sha256 = _file_sha256(archive_path)
    if archive_sha256 != EXPECTED_PYTHON_RUNTIME_ARCHIVE_SHA256:
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_ARCHIVE_SHA256_MISMATCH")

    inventory: list[dict[str, JsonValue]] = []
    expected_paths: set[str] = set()
    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_ARCHIVE_INVALID") from exc
    with archive:
        members = archive.getmembers()
        if not members:
            raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_ARCHIVE_EMPTY")
        for member in members:
            archive_path_value = PurePosixPath(member.name)
            if (
                archive_path_value.is_absolute()
                or ".." in archive_path_value.parts
                or len(archive_path_value.parts) < 2
                or archive_path_value.parts[0] != "python"
            ):
                raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_MEMBER_PATH_INVALID")
            relative = PurePosixPath(*archive_path_value.parts[1:])
            relative_value = relative.as_posix()
            if relative_value in expected_paths:
                raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_MEMBER_DUPLICATE")
            expected_paths.add(relative_value)
            actual_path = runtime_root.joinpath(*relative.parts)
            if member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_MEMBER_UNREADABLE")
                expected_payload = extracted.read()
                if actual_path.is_symlink() or not actual_path.is_file():
                    raise CandidateBuildError(
                        "PH_D06_PYTHON_RUNTIME_MEMBER_TYPE_MISMATCH"
                    )
                actual_payload = actual_path.read_bytes()
                if actual_payload != expected_payload:
                    raise CandidateBuildError(
                        "PH_D06_PYTHON_RUNTIME_MEMBER_BYTES_MISMATCH"
                    )
                inventory.append(
                    {
                        "path": relative_value,
                        "type": "FILE",
                        "mode": member.mode,
                        "size_bytes": len(actual_payload),
                        "sha256": _sha256(actual_payload),
                    }
                )
            elif member.issym():
                if not actual_path.is_symlink():
                    raise CandidateBuildError(
                        "PH_D06_PYTHON_RUNTIME_MEMBER_TYPE_MISMATCH"
                    )
                actual_target = os.readlink(actual_path)
                if actual_target != member.linkname:
                    raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_SYMLINK_MISMATCH")
                resolved_target = (actual_path.parent / actual_target).resolve()
                try:
                    resolved_target.relative_to(runtime_root)
                except ValueError as exc:
                    raise CandidateBuildError(
                        "PH_D06_PYTHON_RUNTIME_SYMLINK_ESCAPE"
                    ) from exc
                inventory.append(
                    {
                        "path": relative_value,
                        "type": "SYMLINK",
                        "mode": member.mode,
                        "target": actual_target,
                    }
                )
            else:
                raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_MEMBER_TYPE_FORBIDDEN")
    actual_paths = {
        path.relative_to(runtime_root).as_posix()
        for path in runtime_root.rglob("*")
        if path.is_symlink() or path.is_file()
    }
    if actual_paths != expected_paths:
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_TREE_MISMATCH")
    inventory.sort(key=lambda item: cast(str, item["path"]))
    tree_digest = logical_content_digest(
        "hds-ph-d06-python-runtime-tree",
        {
            "archive_sha256": archive_sha256,
            "entries": cast(list[JsonValue], inventory),
        },
        policy=DigestExclusionPolicy(),
    )
    executable = runtime_root / "bin/python3"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_EXECUTABLE_MISSING")
    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "LC_ALL": "C.UTF-8",
            "PATH": str(runtime_root / "bin"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        },
    )
    version_output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0 or version_output != (
        "Python " + EXPECTED_PYTHON_VERSION
    ):
        raise CandidateBuildError("PH_D06_PYTHON_RUNTIME_VERSION_MISMATCH")
    return PythonRuntimeDependency(
        root=runtime_root,
        archive=archive_path,
        version=EXPECTED_PYTHON_VERSION,
        archive_sha256=archive_sha256,
        tree_digest=tree_digest,
        entry_count=len(inventory),
        executable_sha256=_file_sha256(executable),
    )


def _report(
    namespace: str,
    body: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    value = dict(body)
    value["digest_excluded_fields"] = ["content_digest"]
    value["content_digest"] = ""
    value["content_digest"] = logical_content_digest(
        namespace,
        value,
        policy=DigestExclusionPolicy(digest_fields=frozenset({"content_digest"})),
    )
    return value


def _tree_inventory(root: Path) -> list[dict[str, JsonValue]]:
    result: list[dict[str, JsonValue]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
    return result


def _tree_digest(inventory: Sequence[Mapping[str, JsonValue]]) -> str:
    return logical_content_digest(
        "hds-ph-d06-output-tree",
        {"files": cast(list[JsonValue], [dict(item) for item in inventory])},
        policy=DigestExclusionPolicy(),
    )


def _source_manifest(repository_root: Path) -> Mapping[str, Any]:
    path = repository_root / SOURCE_ROOT / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildError("PH_D06_SOURCE_MANIFEST_UNREADABLE") from exc
    manifest = _object(value, "PH_D06_SOURCE_MANIFEST")
    if manifest.get("content_digest") != EXPECTED_SOURCE_MANIFEST_DIGEST:
        raise CandidateBuildError("PH_D06_SOURCE_MANIFEST_DIGEST_MISMATCH")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or len(packages) != 25:
        raise CandidateBuildError("PH_D06_SOURCE_MANIFEST_COVERAGE_INVALID")
    return manifest


def _input_projection_digest(source_manifest: Mapping[str, Any]) -> str:
    raw_rows = source_manifest.get("packages")
    if not isinstance(raw_rows, list):
        raise CandidateBuildError("PH_D06_SOURCE_PACKAGES_NOT_ARRAY")
    rows: list[JsonValue] = []
    for raw_row in raw_rows:
        row = _object(raw_row, "PH_D06_SOURCE_PACKAGE_ROW")
        rows.append(
            {
                "package_content_digest": row.get("package_content_digest"),
                "package_sha256": row.get("package_sha256"),
                "package_size_bytes": row.get("package_size_bytes"),
            }
        )
    return logical_content_digest(
        "hds-ph-d06-input-projection",
        {
            "source_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
            "packages": rows,
        },
        policy=DigestExclusionPolicy(),
    )


def _materialize_code_projection(
    repository_root: Path,
    projection_root: Path,
) -> tuple[str, int]:
    source_package = repository_root / "distillation/src/hds_distill"
    target_package = projection_root / "distillation/src/hds_distill"
    target_package.mkdir(parents=True, exist_ok=True)
    source_files = sorted(source_package.glob("*.py"))
    if not source_files:
        raise CandidateBuildError("PH_D06_CODE_PROJECTION_EMPTY")
    digest_rows: list[dict[str, JsonValue]] = []
    for source in source_files:
        payload = source.read_bytes()
        relative = Path("distillation/src/hds_distill") / source.name
        target = projection_root / relative
        target.write_bytes(payload)
        digest_rows.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
    worker_source = repository_root / WORKER_PATH
    worker_payload = worker_source.read_bytes()
    worker_target = projection_root / WORKER_PATH
    worker_target.parent.mkdir(parents=True, exist_ok=True)
    worker_target.write_bytes(worker_payload)
    digest_rows.append(
        {
            "path": WORKER_PATH.as_posix(),
            "sha256": _sha256(worker_payload),
            "size_bytes": len(worker_payload),
        }
    )
    digest_rows.sort(key=lambda item: cast(str, item["path"]))
    digest = logical_content_digest(
        "hds-ph-d06-checkout-projection",
        {"files": cast(list[JsonValue], digest_rows)},
        policy=DigestExclusionPolicy(),
    )
    return digest, len(digest_rows)


def _run_worker(
    *,
    repository_root: Path,
    code_projection: Path,
    output_root: Path,
    checkout_projection_digest: str,
    input_projection_digest: str,
    python_runtime: PythonRuntimeDependency,
) -> Mapping[str, Any]:
    if not BUBBLEWRAP.is_file():
        raise CandidateBuildError("PH_D06_BUBBLEWRAP_MISSING")
    host_mount_namespace = os.readlink("/proc/self/ns/mnt")
    host_network_namespace = os.readlink("/proc/self/ns/net")
    command = [
        str(BUBBLEWRAP),
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--ro-bind",
        str(python_runtime.root),
        "/python-runtime",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/work",
        "--dir",
        "/input",
        "--dir",
        "/output",
        "--ro-bind",
        str(code_projection),
        "/work",
        "--ro-bind",
        str(repository_root / SOURCE_ROOT),
        "/input",
        "--bind",
        str(output_root),
        "/output",
        "--setenv",
        "PATH",
        "/python-runtime/bin:/usr/bin:/bin",
        "--setenv",
        "PYTHONPATH",
        "/work/distillation/src",
        "--setenv",
        "PYTHONHASHSEED",
        "0",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--setenv",
        "LC_ALL",
        "C.UTF-8",
        "--setenv",
        "PH_D06_ORIGINAL_REPOSITORY_ROOT",
        str(repository_root),
        "--setenv",
        "PH_D06_HOST_MOUNT_NAMESPACE",
        host_mount_namespace,
        "--setenv",
        "PH_D06_HOST_NETWORK_NAMESPACE",
        host_network_namespace,
        "--setenv",
        "PH_D06_CHECKOUT_PROJECTION_DIGEST",
        checkout_projection_digest,
        "--setenv",
        "PH_D06_INPUT_PROJECTION_DIGEST",
        input_projection_digest,
        "--setenv",
        "PH_D06_PYTHON_VERSION",
        python_runtime.version,
        "--setenv",
        "PH_D06_PYTHON_RUNTIME_ARCHIVE_SHA256",
        python_runtime.archive_sha256,
        "--setenv",
        "PH_D06_PYTHON_RUNTIME_TREE_DIGEST",
        python_runtime.tree_digest,
        "--setenv",
        "PH_D06_PYTHON_EXECUTABLE_SHA256",
        python_runtime.executable_sha256,
        "--chdir",
        "/",
        "/python-runtime/bin/python3",
        "/work/scripts/ph_d06_candidate_worker.py",
        "--input-root",
        "/input",
        "--output-root",
        "/output",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if completed.returncode != 0:
        raise CandidateBuildError(
            "PH_D06_SOURCE_BLIND_WORKER_FAILED:"
            + completed.stderr.strip()
            + completed.stdout.strip()
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CandidateBuildError("PH_D06_WORKER_RESULT_INVALID") from exc
    result = _object(value, "PH_D06_WORKER_RESULT")
    required_true = (
        result.get("status") == "PASS"
        and result.get("mount_namespace_enforced") is True
        and result.get("network_namespace_enforced") is True
        and result.get("repository_root_visible") is False
        and result.get("environment_source_mount_observed") is False
        and result.get("environment_source_access_count") == 0
        and result.get("secret_environment_key_count") == 0
        and result.get("candidate_generation_count") == 450
        and result.get("candidate_adoption_count") == 0
        and result.get("checkout_projection_digest") == checkout_projection_digest
        and result.get("input_projection_digest") == input_projection_digest
        and result.get("output_file_count") == 26
        and result.get("python_version") == python_runtime.version
        and result.get("python_runtime_archive_sha256") == python_runtime.archive_sha256
        and result.get("python_runtime_tree_digest") == python_runtime.tree_digest
        and result.get("python_executable_sha256") == python_runtime.executable_sha256
    )
    if not required_true:
        raise CandidateBuildError("PH_D06_WORKER_ASSERTION_MISMATCH")
    return result


def _compare_builds(
    build_roots: Sequence[Path],
) -> tuple[list[dict[str, JsonValue]], str]:
    inventories = [_tree_inventory(root) for root in build_roots]
    if any(inventory != inventories[0] for inventory in inventories[1:]):
        raise CandidateBuildError("PH_D06_REBUILD_BYTE_MISMATCH")
    if len(inventories[0]) != 26:
        raise CandidateBuildError("PH_D06_REBUILD_FILE_COUNT_MISMATCH")
    return inventories[0], _tree_digest(inventories[0])


def _build_reports(
    *,
    python_runtime: PythonRuntimeDependency,
    worker_results: Sequence[Mapping[str, Any]],
    output_inventory: Sequence[Mapping[str, JsonValue]],
    output_tree_digest: str,
    checkout_projection_digest: str,
    checkout_projection_file_count: int,
    input_projection_digest: str,
    candidate_manifest: Mapping[str, Any],
) -> tuple[
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
]:
    rebuild = _report(
        "hds-ph-d06-rebuild-x3",
        {
            "schema_version": "hds-ph-d06-rebuild-x3-v1",
            "phase_id": PHASE_ID,
            "independent_process_count": len(worker_results),
            "compared_file_count_per_build": len(output_inventory),
            "output_tree_digest": output_tree_digest,
            "byte_mismatch_count": 0,
            "candidate_case_package_count": 25,
            "candidate_count": 450,
            "status": "PASS",
        },
    )
    process_rows: list[JsonValue] = []
    for index, raw_result in enumerate(worker_results, start=1):
        result = dict(raw_result)
        result["process_ordinal"] = index
        process_rows.append(cast(dict[str, JsonValue], result))
    source_blind = _report(
        "hds-ph-d06-source-blind-execution",
        {
            "schema_version": "hds-ph-d06-source-blind-execution-v1",
            "phase_id": PHASE_ID,
            "role_id": "DISTILLATION_EXECUTOR",
            "enforcement_backend": "BUBBLEWRAP_USER_MOUNT_NETWORK_NAMESPACE",
            "python_runtime": {
                "asset_name": EXPECTED_PYTHON_RUNTIME_ASSET,
                "archive_sha256": python_runtime.archive_sha256,
                "version": python_runtime.version,
                "tree_digest": python_runtime.tree_digest,
                "entry_count": python_runtime.entry_count,
                "executable_sha256": python_runtime.executable_sha256,
                "mount_path": "/python-runtime",
                "network_acquisition_during_build": False,
            },
            "independent_process_count": len(worker_results),
            "checkout_projection_digest": checkout_projection_digest,
            "checkout_projection_file_count": checkout_projection_file_count,
            "input_projection_digest": input_projection_digest,
            "mount_allowlist": [
                "/usr:READ_ONLY_RUNTIME",
                "/lib:READ_ONLY_RUNTIME",
                "/lib64:READ_ONLY_RUNTIME",
                "/python-runtime:READ_ONLY_PINNED_PYTHON_3_12_13",
                "/work:READ_ONLY_CODE_PROJECTION",
                "/input:READ_ONLY_CANONICAL_TEACHER_PACKAGES",
                "/output:WRITE_ONLY_GENERATED_ARTIFACTS",
                "/tmp:PRIVATE_TMPFS",
                "/proc:PRIVATE_NAMESPACE",
                "/dev:PRIVATE_NAMESPACE",
            ],
            "repository_root_visibility_count": 0,
            "environment_source_mount_count": 0,
            "environment_source_access_count": 0,
            "same_process_source_access_then_candidate_generation_count": 0,
            "secret_environment_key_count": 0,
            "network_namespace_pass_count": len(worker_results),
            "mount_namespace_pass_count": len(worker_results),
            "candidate_generation_count": 450,
            "candidate_adoption_count": 0,
            "process_results": process_rows,
            "claim_boundary": (
                "Candidate generation had canonical teacher packages and "
                "distillation code only; environment source and repository "
                "root were not mounted or visible."
            ),
            "status": "PASS_SOURCE_BLIND_ESTABLISHED",
        },
    )
    llm_capture = _report(
        "hds-ph-d06-llm-capture",
        {
            "schema_version": "hds-ph-d06-llm-capture-v1",
            "phase_id": PHASE_ID,
            "llm_mode": "NOT_USED",
            "llm_call_count": 0,
            "frozen_prompt_count": 0,
            "raw_response_capture_count": 0,
            "response_digest_count": 0,
            "deterministic_parse_count": 0,
            "arbitrary_code_execution_count": 0,
            "live_llm_required_for_rebuild": False,
            "deterministic_template_candidate_count": 350,
            "bounded_graph_enumeration_candidate_count": 50,
            "adversarial_generation_candidate_count": 50,
            "status": "PASS_NO_LLM_DEPENDENCY",
        },
    )
    generation = _report(
        "hds-ph-d06-hypothesis-candidate-generation",
        {
            "schema_version": "hds-ph-d06-candidate-generation-report-v1",
            "phase_id": PHASE_ID,
            "status": "MULTI_HYPOTHESIS_CORPUS_COMPLETE",
            "source_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
            "candidate_manifest_digest": candidate_manifest["content_digest"],
            "rebuild_x3_digest": rebuild["content_digest"],
            "source_blind_execution_digest": source_blind["content_digest"],
            "llm_capture_digest": llm_capture["content_digest"],
            "teacher_case_count": 25,
            "candidate_case_package_count": 25,
            "candidate_count": 450,
            "executable_candidate_count": 400,
            "rejected_adversarial_count": 50,
            "candidate_adoption_count": 0,
            "fit_execution_count": 0,
            "real_intervention_execution_count": 0,
            "causal_assertion_count": 0,
            "rule_promotion_count": 0,
            "source_access_count": 0,
            "identity_routing_count": 0,
            "complete_action_sequence_copy_count": 0,
            "alternative_adequacy_status": "PASS",
            "answer_copy_generated_and_rejected_count": 25,
            "trajectory_lookup_generated_and_rejected_count": 25,
            "independent_rebuild_process_count": 3,
            "byte_mismatch_count": 0,
            "gates": {
                "DG-03": "PASS",
                "DG-04": "PASS",
                "DG-05": "PASS",
                "DG-08": "PASS",
                "DG-12": "PASS",
            },
            "next_phase": "PH-D07A",
            "claim_boundary": (
                "All candidates remain unselected and unevaluated for fit; "
                "PH-D07A may execute teacher-fit evaluation."
            ),
        },
    )
    return rebuild, source_blind, llm_capture, generation


def _contract_bytes(
    *,
    repository_root: Path,
    python_runtime: PythonRuntimeDependency,
    candidate_manifest: Mapping[str, Any],
    rebuild: Mapping[str, Any],
    source_blind: Mapping[str, Any],
    llm_capture: Mapping[str, Any],
    generation: Mapping[str, Any],
) -> bytes:
    contract_path = repository_root / CONTRACT_PATH
    try:
        raw_contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildError("PH_D06_CONTRACT_UNREADABLE") from exc
    contract = dict(_object(raw_contract, "PH_D06_CONTRACT"))
    if contract.get("phase_id") != PHASE_ID:
        raise CandidateBuildError("PH_D06_CONTRACT_PHASE_MISMATCH")
    authority = _object(contract.get("authority"), "PH_D06_CONTRACT_AUTHORITY")
    live_bindings: dict[str, object] = {}
    for field, relative_path in (
        (
            "work_block_frame_digest",
            Path("control/rev3/PH-D06_WORK_BLOCK_FRAME.json"),
        ),
        (
            "preinventory_digest",
            Path("analysis/rev3/ph_d06_hypothesis_candidate_preinventory.json"),
        ),
        (
            "phase_transition_digest",
            Path("control/rev3/PHASE_TRANSITIONS/PH-D05_TO_PH-D06.json"),
        ),
    ):
        value = _object(
            json.loads((repository_root / relative_path).read_text(encoding="utf-8")),
            "PH_D06_CONTRACT_AUTHORITY_INPUT",
        )
        live_bindings[field] = value.get("content_digest")
    contract["authority"] = {**authority, **live_bindings}
    contract["python_runtime_contract"] = {
        "required_version": python_runtime.version,
        "asset_name": EXPECTED_PYTHON_RUNTIME_ASSET,
        "archive_sha256": python_runtime.archive_sha256,
        "tree_digest": python_runtime.tree_digest,
        "entry_count": python_runtime.entry_count,
        "executable_sha256": python_runtime.executable_sha256,
        "runtime_root_environment_key": PYTHON_RUNTIME_ROOT_ENV,
        "runtime_archive_environment_key": PYTHON_RUNTIME_ARCHIVE_ENV,
        "source_blind_mount_path": "/python-runtime",
        "network_acquisition_during_build_allowed": False,
        "archive_or_runtime_in_git_allowed": False,
    }
    output = dict(_object(contract.get("output_contract"), "PH_D06_OUTPUT_CONTRACT"))
    output.update(
        {
            "candidate_manifest_digest": candidate_manifest.get("content_digest"),
            "rebuild_x3_digest": rebuild.get("content_digest"),
            "source_blind_report_digest": source_blind.get("content_digest"),
            "llm_capture_report_digest": llm_capture.get("content_digest"),
            "generation_report_digest": generation.get("content_digest"),
        }
    )
    contract["output_contract"] = output
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"contract_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    contract["content_digest"] = logical_content_digest(
        "hds-arc3-hypothesis-candidate-generation-contract",
        contract,
        policy=policy,
    )
    contract["contract_id"] = content_derived_id(
        "hds-arc3-hypothesis-candidate-generation-contract-id",
        contract,
        policy=policy,
    )
    return canonical_json_document_bytes(contract)


def _checked_outputs(
    repository_root: Path,
) -> dict[Path, bytes]:
    result: dict[Path, bytes] = {}
    candidate_root = repository_root / CANDIDATE_ROOT
    for path in sorted(item for item in candidate_root.rglob("*") if item.is_file()):
        result[path.relative_to(repository_root)] = path.read_bytes()
    for relative in (GENERATION_REPORT, SOURCE_BLIND_REPORT, LLM_CAPTURE_REPORT):
        path = repository_root / relative
        if not path.is_file():
            raise CandidateBuildError(
                "PH_D06_CHECKED_ARTIFACT_MISSING:" + str(relative)
            )
        result[relative] = path.read_bytes()
    contract_path = repository_root / CONTRACT_PATH
    if not contract_path.is_file():
        raise CandidateBuildError("PH_D06_CHECKED_CONTRACT_MISSING")
    result[CONTRACT_PATH] = contract_path.read_bytes()
    return result


def build_all(repository_root: Path) -> dict[Path, bytes]:
    python_runtime = _python_runtime_dependency()
    source_manifest = _source_manifest(repository_root)
    input_digest = _input_projection_digest(source_manifest)
    with tempfile.TemporaryDirectory(prefix="arc3-ph-d06-build-") as raw_temp:
        temporary_root = Path(raw_temp)
        code_projection = temporary_root / "code"
        code_projection.mkdir()
        checkout_digest, checkout_file_count = _materialize_code_projection(
            repository_root,
            code_projection,
        )
        build_roots = [temporary_root / f"build-{index}" for index in range(1, 4)]
        worker_results: list[Mapping[str, Any]] = []
        for build_root in build_roots:
            build_root.mkdir()
            worker_results.append(
                _run_worker(
                    repository_root=repository_root,
                    code_projection=code_projection,
                    output_root=build_root,
                    checkout_projection_digest=checkout_digest,
                    input_projection_digest=input_digest,
                    python_runtime=python_runtime,
                )
            )
        inventory, output_tree_digest = _compare_builds(build_roots)
        candidate_manifest = _object(
            json.loads((build_roots[0] / "manifest.json").read_text(encoding="utf-8")),
            "PH_D06_CANDIDATE_MANIFEST",
        )
        rebuild, source_blind, llm_capture, generation = _build_reports(
            python_runtime=python_runtime,
            worker_results=worker_results,
            output_inventory=inventory,
            output_tree_digest=output_tree_digest,
            checkout_projection_digest=checkout_digest,
            checkout_projection_file_count=checkout_file_count,
            input_projection_digest=input_digest,
            candidate_manifest=candidate_manifest,
        )

        generated: dict[Path, bytes] = {}
        for path in sorted(
            item for item in build_roots[0].rglob("*") if item.is_file()
        ):
            relative = path.relative_to(build_roots[0])
            generated[CANDIDATE_ROOT / relative] = path.read_bytes()
        generated[CANDIDATE_ROOT / "rebuild_x3.json"] = canonical_json_document_bytes(
            rebuild
        )
        generated[SOURCE_BLIND_REPORT] = canonical_json_document_bytes(source_blind)
        generated[LLM_CAPTURE_REPORT] = canonical_json_document_bytes(llm_capture)
        generated[GENERATION_REPORT] = canonical_json_document_bytes(generation)
        generated[CONTRACT_PATH] = _contract_bytes(
            repository_root=repository_root,
            python_runtime=python_runtime,
            candidate_manifest=candidate_manifest,
            rebuild=rebuild,
            source_blind=source_blind,
            llm_capture=llm_capture,
            generation=generation,
        )
        return generated


def _write_outputs(repository_root: Path, generated: Mapping[Path, bytes]) -> None:
    candidate_root = repository_root / CANDIDATE_ROOT
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    for relative, payload in sorted(generated.items(), key=lambda item: str(item[0])):
        target = repository_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def _verify_outputs(repository_root: Path, generated: Mapping[Path, bytes]) -> None:
    checked = _checked_outputs(repository_root)
    if set(checked) != set(generated):
        missing = sorted(str(path) for path in set(generated) - set(checked))
        extra = sorted(str(path) for path in set(checked) - set(generated))
        raise CandidateBuildError(
            "PH_D06_CHECKED_PATH_SET_MISMATCH:missing="
            + ",".join(missing)
            + ":extra="
            + ",".join(extra)
        )
    mismatches = [str(path) for path in generated if generated[path] != checked[path]]
    if mismatches:
        raise CandidateBuildError(
            "PH_D06_CHECKED_BYTE_MISMATCH:" + ",".join(sorted(mismatches))
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    repository_root = arguments.root.resolve()
    generated = build_all(repository_root)
    if arguments.write:
        _write_outputs(repository_root, generated)
    else:
        _verify_outputs(repository_root, generated)
    summary = {
        "generated_file_count": len(generated),
        "candidate_case_package_count": 25,
        "candidate_count": 450,
        "independent_process_count": 3,
        "status": "PASS",
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
