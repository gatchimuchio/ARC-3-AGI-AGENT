#!/usr/bin/env python3
"""Build and verify PH-D07A extensional fit evidence in three processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from build_ph_d06_hypothesis_candidates import (  # noqa: E402
    BUBBLEWRAP,
    EXPECTED_PYTHON_RUNTIME_ASSET,
    PythonRuntimeDependency,
    _python_runtime_dependency,
)

from hds_distill.canonical import (  # noqa: E402
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
)

PHASE_ID = "PH-D07A"
TEACHER_ROOT = Path("distillation/artifacts/teacher/arc3/ph_d05_v1")
CANDIDATE_ROOT = Path("distillation/artifacts/candidates/arc3/ph_d06_v1")
FIT_ROOT = Path("distillation/artifacts/fit/arc3/ph_d07a_v1")
FIT_REPORT = Path(
    "distillation/artifacts/reports/arc3_extensional_exact_fit.json"
)
ISOLATION_REPORT = Path(
    "distillation/artifacts/reports/arc3_extensional_fit_isolation.json"
)
CONTRACT_PATH = Path("distillation/input/arc3_extensional_exact_fit_contract.json")
WORKER_PATH = Path("scripts/ph_d07a_exact_fit_worker.py")
FRAME_PATH = Path("control/rev3/PH-D07A_WORK_BLOCK_FRAME.json")
TRANSITION_PATH = Path("control/rev3/PHASE_TRANSITIONS/PH-D06_TO_PH-D07A.json")
PREINVENTORY_PATH = Path("analysis/rev3/ph_d07a_exact_fit_preinventory.json")
EXPECTED_TEACHER_MANIFEST_DIGEST = (
    "hds-arc3-canonical-teacher-corpus-manifest:"
    "f81183465265bfa9f29208dd788bb3bfd358c23995ab0aeb8ec9549450360aa6"
)
EXPECTED_CANDIDATE_MANIFEST_DIGEST = (
    "hds-multi-hypothesis-corpus-manifest:"
    "82c5f9c26c85686f1f40c53cd7c926995a1371811efb85f359962afefb69169d"
)


class FitBuildError(RuntimeError):
    """Stable PH-D07A build or verification failure."""


def _object(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FitBuildError(code + "_NOT_OBJECT")
    return cast(Mapping[str, Any], value)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_object(path: Path, code: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FitBuildError(code + "_UNREADABLE") from exc
    return _object(value, code)


def _manifest(
    repository_root: Path,
    relative_root: Path,
    expected_digest: str,
    code: str,
) -> Mapping[str, Any]:
    value = _load_object(repository_root / relative_root / "manifest.json", code)
    if value.get("content_digest") != expected_digest:
        raise FitBuildError(code + "_DIGEST_MISMATCH")
    return value


def _report(namespace: str, body: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
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
    rows: list[dict[str, JsonValue]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
    return rows


def _tree_digest(inventory: Sequence[Mapping[str, JsonValue]]) -> str:
    return logical_content_digest(
        "hds-ph-d07a-output-tree",
        {"files": cast(list[JsonValue], [dict(item) for item in inventory])},
        policy=DigestExclusionPolicy(),
    )


def _input_projection_digest(
    teacher_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
) -> str:
    teacher_rows = teacher_manifest.get("packages")
    candidate_rows = candidate_manifest.get("case_packages")
    if not isinstance(teacher_rows, list) or not isinstance(candidate_rows, list):
        raise FitBuildError("PH_D07A_INPUT_PROJECTION_ROWS_INVALID")
    return logical_content_digest(
        "hds-ph-d07a-input-projection",
        {
            "teacher_manifest_digest": EXPECTED_TEACHER_MANIFEST_DIGEST,
            "candidate_manifest_digest": EXPECTED_CANDIDATE_MANIFEST_DIGEST,
            "teacher_packages": [
                {
                    "content_digest": row.get("package_content_digest"),
                    "sha256": row.get("package_sha256"),
                    "size_bytes": row.get("package_size_bytes"),
                }
                for row in teacher_rows
                if isinstance(row, dict)
            ],
            "candidate_packages": [
                {
                    "content_digest": row.get("candidate_package_content_digest"),
                    "sha256": row.get("candidate_package_sha256"),
                    "size_bytes": row.get("candidate_package_size_bytes"),
                }
                for row in candidate_rows
                if isinstance(row, dict)
            ],
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
    rows: list[dict[str, JsonValue]] = []
    for source in sorted(source_package.glob("*.py")):
        payload = source.read_bytes()
        relative = Path("distillation/src/hds_distill") / source.name
        target = projection_root / relative
        target.write_bytes(payload)
        rows.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(payload),
                "size_bytes": len(payload),
            }
        )
    worker_payload = (repository_root / WORKER_PATH).read_bytes()
    worker_target = projection_root / WORKER_PATH
    worker_target.parent.mkdir(parents=True, exist_ok=True)
    worker_target.write_bytes(worker_payload)
    rows.append(
        {
            "path": WORKER_PATH.as_posix(),
            "sha256": _sha256(worker_payload),
            "size_bytes": len(worker_payload),
        }
    )
    rows.sort(key=lambda item: cast(str, item["path"]))
    return (
        logical_content_digest(
            "hds-ph-d07a-checkout-projection",
            {"files": cast(list[JsonValue], rows)},
            policy=DigestExclusionPolicy(),
        ),
        len(rows),
    )


def _run_worker(
    *,
    repository_root: Path,
    code_projection: Path,
    output_root: Path,
    checkout_projection_digest: str,
    input_projection_digest: str,
    runtime: PythonRuntimeDependency,
) -> Mapping[str, Any]:
    if not BUBBLEWRAP.is_file():
        raise FitBuildError("PH_D07A_BUBBLEWRAP_MISSING")
    host_mount = os.readlink("/proc/self/ns/mnt")
    host_network = os.readlink("/proc/self/ns/net")
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
        str(runtime.root),
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
        "/teacher",
        "--dir",
        "/candidates",
        "--dir",
        "/output",
        "--ro-bind",
        str(code_projection),
        "/work",
        "--ro-bind",
        str(repository_root / TEACHER_ROOT),
        "/teacher",
        "--ro-bind",
        str(repository_root / CANDIDATE_ROOT),
        "/candidates",
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
        "PH_D07A_ORIGINAL_REPOSITORY_ROOT",
        str(repository_root),
        "--setenv",
        "PH_D07A_HOST_MOUNT_NAMESPACE",
        host_mount,
        "--setenv",
        "PH_D07A_HOST_NETWORK_NAMESPACE",
        host_network,
        "--setenv",
        "PH_D07A_CHECKOUT_PROJECTION_DIGEST",
        checkout_projection_digest,
        "--setenv",
        "PH_D07A_INPUT_PROJECTION_DIGEST",
        input_projection_digest,
        "--setenv",
        "PH_D07A_PYTHON_VERSION",
        runtime.version,
        "--setenv",
        "PH_D07A_RUNTIME_ARCHIVE_SHA256",
        runtime.archive_sha256,
        "--setenv",
        "PH_D07A_RUNTIME_TREE_DIGEST",
        runtime.tree_digest,
        "--setenv",
        "PH_D07A_PYTHON_EXECUTABLE_SHA256",
        runtime.executable_sha256,
        "--chdir",
        "/",
        "/python-runtime/bin/python3",
        "/work/scripts/ph_d07a_exact_fit_worker.py",
        "--teacher-root",
        "/teacher",
        "--candidate-root",
        "/candidates",
        "--output-root",
        "/output",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if completed.returncode != 0:
        raise FitBuildError(
            "PH_D07A_COMPARATOR_FAILED:"
            + completed.stderr.strip()
            + completed.stdout.strip()
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise FitBuildError("PH_D07A_COMPARATOR_RESULT_INVALID") from exc
    result = _object(value, "PH_D07A_COMPARATOR_RESULT")
    if not (
        result.get("status") == "PASS"
        and result.get("mount_namespace_enforced") is True
        and result.get("network_namespace_enforced") is True
        and result.get("repository_root_visible") is False
        and result.get("environment_source_mount_observed") is False
        and result.get("environment_source_access_count") == 0
        and result.get("secret_environment_key_count") == 0
        and result.get("candidate_accounting_count") == 450
        and result.get("eligible_fit_evaluation_count") == 400
        and result.get("candidate_step_evaluation_count") == 185184
        and result.get("candidate_selection_count") == 0
        and result.get("causal_support_count") == 0
        and result.get("real_intervention_execution_count") == 0
        and result.get("rule_promotion_count") == 0
        and result.get("output_file_count") == 26
        and result.get("checkout_projection_digest")
        == checkout_projection_digest
        and result.get("input_projection_digest") == input_projection_digest
        and result.get("python_version") == runtime.version
        and result.get("python_runtime_archive_sha256") == runtime.archive_sha256
        and result.get("python_runtime_tree_digest") == runtime.tree_digest
        and result.get("python_executable_sha256") == runtime.executable_sha256
    ):
        raise FitBuildError("PH_D07A_COMPARATOR_ASSERTION_MISMATCH")
    return result


def _compare_builds(
    roots: Sequence[Path],
) -> tuple[list[dict[str, JsonValue]], str]:
    inventories = [_tree_inventory(root) for root in roots]
    if any(item != inventories[0] for item in inventories[1:]):
        raise FitBuildError("PH_D07A_COMPARATOR_BYTE_MISMATCH")
    if len(inventories[0]) != 26:
        raise FitBuildError("PH_D07A_COMPARATOR_FILE_COUNT_MISMATCH")
    return inventories[0], _tree_digest(inventories[0])


def _build_reports(
    *,
    runtime: PythonRuntimeDependency,
    worker_results: Sequence[Mapping[str, Any]],
    output_inventory: Sequence[Mapping[str, JsonValue]],
    output_tree_digest: str,
    checkout_projection_digest: str,
    checkout_projection_file_count: int,
    input_projection_digest: str,
    fit_manifest: Mapping[str, Any],
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]]:
    rebuild = _report(
        "hds-ph-d07a-comparator-rebuild-x3",
        {
            "schema_version": "hds-ph-d07a-comparator-rebuild-x3-v1",
            "phase_id": PHASE_ID,
            "independent_process_count": len(worker_results),
            "comparator_execution_mode": "SEQUENTIAL_INDEPENDENT_PROCESSES",
            "maximum_concurrent_process_count": 1,
            "compared_file_count_per_build": len(output_inventory),
            "output_tree_digest": output_tree_digest,
            "byte_mismatch_count": 0,
            "fit_case_package_count": 25,
            "candidate_accounting_count": 450,
            "candidate_step_evaluation_count": 185184,
            "status": "PASS",
        },
    )
    process_rows: list[JsonValue] = []
    for ordinal, raw in enumerate(worker_results, start=1):
        row = dict(raw)
        row["process_ordinal"] = ordinal
        process_rows.append(cast(dict[str, JsonValue], row))
    isolation = _report(
        "hds-ph-d07a-fit-isolation",
        {
            "schema_version": "hds-ph-d07a-fit-isolation-v1",
            "phase_id": PHASE_ID,
            "role_id": "DISTILLATION_COMPARATOR",
            "enforcement_backend": "BUBBLEWRAP_USER_MOUNT_NETWORK_NAMESPACE",
            "python_runtime": {
                "asset_name": EXPECTED_PYTHON_RUNTIME_ASSET,
                "archive_sha256": runtime.archive_sha256,
                "version": runtime.version,
                "tree_digest": runtime.tree_digest,
                "entry_count": runtime.entry_count,
                "executable_sha256": runtime.executable_sha256,
                "mount_path": "/python-runtime",
                "network_acquisition_during_build": False,
            },
            "independent_process_count": len(worker_results),
            "comparator_execution_mode": "SEQUENTIAL_INDEPENDENT_PROCESSES",
            "maximum_concurrent_process_count": 1,
            "checkout_projection_digest": checkout_projection_digest,
            "checkout_projection_file_count": checkout_projection_file_count,
            "input_projection_digest": input_projection_digest,
            "repository_root_visibility_count": 0,
            "environment_source_mount_count": 0,
            "environment_source_access_count": 0,
            "secret_environment_key_count": 0,
            "primary_source_write_count": 0,
            "candidate_source_write_count": 0,
            "network_namespace_pass_count": len(worker_results),
            "mount_namespace_pass_count": len(worker_results),
            "process_results": process_rows,
            "status": "PASS_ISOLATED_COMPARATOR_X3",
        },
    )
    fit_report = _report(
        "hds-ph-d07a-extensional-exact-fit",
        {
            "schema_version": "hds-ph-d07a-extensional-exact-fit-report-v1",
            "phase_id": PHASE_ID,
            "status": "EXTENSIONAL_FIT_ACCOUNTED",
            "teacher_manifest_digest": EXPECTED_TEACHER_MANIFEST_DIGEST,
            "candidate_manifest_digest": EXPECTED_CANDIDATE_MANIFEST_DIGEST,
            "fit_manifest_digest": fit_manifest["content_digest"],
            "rebuild_x3_digest": rebuild["content_digest"],
            "isolation_report_digest": isolation["content_digest"],
            "teacher_case_count": fit_manifest["teacher_case_count"],
            "teacher_step_count": fit_manifest["teacher_step_count"],
            "candidate_accounting_count": fit_manifest["candidate_count"],
            "eligible_fit_evaluation_count": fit_manifest[
                "eligible_fit_evaluation_count"
            ],
            "rejected_ineligible_candidate_count": fit_manifest[
                "rejected_ineligible_candidate_count"
            ],
            "candidate_step_evaluation_count": fit_manifest[
                "candidate_step_evaluation_count"
            ],
            "exact_fit_candidate_count": fit_manifest[
                "exact_fit_candidate_count"
            ],
            "fit_status_counts": fit_manifest["fit_status_counts"],
            "mechanism_support_state_counts": fit_manifest[
                "mechanism_support_state_counts"
            ],
            "axis_candidate_counts": fit_manifest["axis_candidate_counts"],
            "primary_source_manifest_mutation_count": 0,
            "candidate_selection_count": 0,
            "candidate_adoption_count": 0,
            "causal_support_count": 0,
            "real_intervention_execution_count": 0,
            "rule_promotion_count": 0,
            "gates": {
                "DG-07": "PASS",
                "DG-08": "PASS",
                "DG-09": "PASS",
            },
            "next_phase": "PH-D07B",
            "claim_boundary": (
                "LOCAL_EXACT_FIT is trajectory-local observational evidence "
                "only; causal support remains zero until PH-D07B."
            ),
        },
    )
    return rebuild, isolation, fit_report


def _contract_bytes(
    *,
    repository_root: Path,
    runtime: PythonRuntimeDependency,
    fit_manifest: Mapping[str, Any],
    rebuild: Mapping[str, Any],
    isolation: Mapping[str, Any],
    fit_report: Mapping[str, Any],
) -> bytes:
    contract = dict(
        _load_object(repository_root / CONTRACT_PATH, "PH_D07A_CONTRACT")
    )
    if contract.get("phase_id") != PHASE_ID:
        raise FitBuildError("PH_D07A_CONTRACT_PHASE_MISMATCH")
    authority = dict(
        _object(contract.get("authority"), "PH_D07A_CONTRACT_AUTHORITY")
    )
    for field, relative in (
        ("work_block_frame_digest", FRAME_PATH),
        ("phase_transition_digest", TRANSITION_PATH),
        ("preinventory_digest", PREINVENTORY_PATH),
    ):
        authority[field] = _load_object(
            repository_root / relative,
            "PH_D07A_AUTHORITY_BINDING",
        ).get("content_digest")
    contract["authority"] = authority
    contract["python_runtime_contract"] = {
        "required_version": runtime.version,
        "asset_name": EXPECTED_PYTHON_RUNTIME_ASSET,
        "archive_sha256": runtime.archive_sha256,
        "tree_digest": runtime.tree_digest,
        "entry_count": runtime.entry_count,
        "executable_sha256": runtime.executable_sha256,
        "runtime_root_environment_key": "ARC3_PH_D06_PYTHON_RUNTIME_ROOT",
        "runtime_archive_environment_key": "ARC3_PH_D06_PYTHON_RUNTIME_ARCHIVE",
        "comparator_mount_path": "/python-runtime",
        "network_acquisition_during_build_allowed": False,
        "archive_or_runtime_in_git_allowed": False,
    }
    output = dict(
        _object(contract.get("output_contract"), "PH_D07A_OUTPUT_CONTRACT")
    )
    output.update(
        {
            "fit_manifest_digest": fit_manifest["content_digest"],
            "rebuild_x3_digest": rebuild["content_digest"],
            "isolation_report_digest": isolation["content_digest"],
            "fit_report_digest": fit_report["content_digest"],
        }
    )
    contract["output_contract"] = output
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"contract_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    contract["content_digest"] = logical_content_digest(
        "hds-arc3-extensional-exact-fit-contract",
        contract,
        policy=policy,
    )
    contract["contract_id"] = content_derived_id(
        "hds-arc3-extensional-exact-fit-contract-id",
        contract,
        policy=policy,
    )
    return canonical_json_document_bytes(contract)


def build_all(repository_root: Path) -> dict[Path, bytes]:
    runtime = _python_runtime_dependency()
    teacher_manifest = _manifest(
        repository_root,
        TEACHER_ROOT,
        EXPECTED_TEACHER_MANIFEST_DIGEST,
        "PH_D07A_TEACHER_MANIFEST",
    )
    candidate_manifest = _manifest(
        repository_root,
        CANDIDATE_ROOT,
        EXPECTED_CANDIDATE_MANIFEST_DIGEST,
        "PH_D07A_CANDIDATE_MANIFEST",
    )
    input_digest = _input_projection_digest(teacher_manifest, candidate_manifest)
    with tempfile.TemporaryDirectory(prefix="arc3-ph-d07a-build-") as raw_temp:
        temporary_root = Path(raw_temp)
        code_projection = temporary_root / "code"
        code_projection.mkdir()
        checkout_digest, checkout_count = _materialize_code_projection(
            repository_root,
            code_projection,
        )
        roots = [temporary_root / f"build-{index}" for index in range(1, 4)]
        for root in roots:
            root.mkdir()

        def run_worker(root: Path) -> Mapping[str, Any]:
            return _run_worker(
                repository_root=repository_root,
                code_projection=code_projection,
                output_root=root,
                checkout_projection_digest=checkout_digest,
                input_projection_digest=input_digest,
                runtime=runtime,
            )

        # Each comparator is still a fresh, isolated process.  Run them one at
        # a time so the evidence build remains safe on the pinned 2.8 GiB WSL
        # execution envelope; concurrency is not an independence requirement.
        with ThreadPoolExecutor(max_workers=1) as executor:
            worker_results = list(executor.map(run_worker, roots))
        inventory, tree_digest = _compare_builds(roots)
        fit_manifest = _load_object(
            roots[0] / "manifest.json",
            "PH_D07A_FIT_MANIFEST",
        )
        rebuild, isolation, fit_report = _build_reports(
            runtime=runtime,
            worker_results=worker_results,
            output_inventory=inventory,
            output_tree_digest=tree_digest,
            checkout_projection_digest=checkout_digest,
            checkout_projection_file_count=checkout_count,
            input_projection_digest=input_digest,
            fit_manifest=fit_manifest,
        )
        generated: dict[Path, bytes] = {}
        for path in sorted(item for item in roots[0].rglob("*") if item.is_file()):
            generated[FIT_ROOT / path.relative_to(roots[0])] = path.read_bytes()
        generated[FIT_ROOT / "rebuild_x3.json"] = canonical_json_document_bytes(
            rebuild
        )
        generated[ISOLATION_REPORT] = canonical_json_document_bytes(isolation)
        generated[FIT_REPORT] = canonical_json_document_bytes(fit_report)
        generated[CONTRACT_PATH] = _contract_bytes(
            repository_root=repository_root,
            runtime=runtime,
            fit_manifest=fit_manifest,
            rebuild=rebuild,
            isolation=isolation,
            fit_report=fit_report,
        )
        return generated


def _checked_outputs(repository_root: Path) -> dict[Path, bytes]:
    checked: dict[Path, bytes] = {}
    fit_root = repository_root / FIT_ROOT
    if not fit_root.is_dir():
        raise FitBuildError("PH_D07A_CHECKED_FIT_ROOT_MISSING")
    for path in sorted(item for item in fit_root.rglob("*") if item.is_file()):
        checked[path.relative_to(repository_root)] = path.read_bytes()
    for relative in (ISOLATION_REPORT, FIT_REPORT, CONTRACT_PATH):
        path = repository_root / relative
        if not path.is_file():
            raise FitBuildError("PH_D07A_CHECKED_ARTIFACT_MISSING:" + str(relative))
        checked[relative] = path.read_bytes()
    return checked


def _write_outputs(repository_root: Path, generated: Mapping[Path, bytes]) -> None:
    fit_root = repository_root / FIT_ROOT
    if fit_root.exists():
        shutil.rmtree(fit_root)
    for relative, payload in sorted(generated.items(), key=lambda item: str(item[0])):
        target = repository_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def _verify_outputs(repository_root: Path, generated: Mapping[Path, bytes]) -> None:
    checked = _checked_outputs(repository_root)
    if set(checked) != set(generated):
        missing = sorted(str(path) for path in set(generated) - set(checked))
        extra = sorted(str(path) for path in set(checked) - set(generated))
        raise FitBuildError(
            "PH_D07A_CHECKED_PATH_SET_MISMATCH:missing="
            + ",".join(missing)
            + ":extra="
            + ",".join(extra)
        )
    mismatches = [str(path) for path in generated if generated[path] != checked[path]]
    if mismatches:
        raise FitBuildError(
            "PH_D07A_CHECKED_BYTE_MISMATCH:" + ",".join(sorted(mismatches))
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
    print(
        json.dumps(
            {
                "generated_file_count": len(generated),
                "fit_case_package_count": 25,
                "candidate_accounting_count": 450,
                "candidate_step_evaluation_count": 185184,
                "independent_process_count": 3,
                "comparator_execution_mode": (
                    "SEQUENTIAL_INDEPENDENT_PROCESSES"
                ),
                "status": "PASS",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
