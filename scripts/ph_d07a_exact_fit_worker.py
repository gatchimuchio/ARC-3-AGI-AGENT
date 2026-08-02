#!/usr/bin/env python3
"""Build PH-D07A fit evidence inside an isolated comparator process."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import struct
import sys
import zlib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from hds_distill.canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
)
from hds_distill.exact_fit import EVALUATOR_VERSION, FIT_AXES, evaluate_case
from hds_distill.hypothesis_generation import teacher_case_ref

EXPECTED_TEACHER_MANIFEST_DIGEST = (
    "hds-arc3-canonical-teacher-corpus-manifest:"
    "f81183465265bfa9f29208dd788bb3bfd358c23995ab0aeb8ec9549450360aa6"
)
EXPECTED_CANDIDATE_MANIFEST_DIGEST = (
    "hds-multi-hypothesis-corpus-manifest:"
    "82c5f9c26c85686f1f40c53cd7c926995a1371811efb85f359962afefb69169d"
)
MANIFEST_VERSION = "hds-arc3-extensional-fit-manifest-v1"
ARTIFACT_VERSION = "ph-d07a-v1"


class FitWorkerError(RuntimeError):
    """Stable isolated comparator failure."""


def _object(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FitWorkerError(code + "_NOT_OBJECT")
    return cast(Mapping[str, Any], value)


def _integer(value: object, code: str) -> int:
    if type(value) is not int:
        raise FitWorkerError(code + "_NOT_INTEGER")
    return value


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _deterministic_gzip(payload: bytes) -> bytes:
    compressor = zlib.compressobj(
        level=6,
        method=zlib.DEFLATED,
        wbits=-zlib.MAX_WBITS,
        memLevel=8,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    compressed = compressor.compress(payload) + compressor.flush()
    result = (
        bytes.fromhex("1f8b08000000000000ff")
        + compressed
        + struct.pack(
            "<II",
            zlib.crc32(payload) & 0xFFFFFFFF,
            len(payload) & 0xFFFFFFFF,
        )
    )
    if gzip.decompress(result) != payload:
        raise FitWorkerError("PH_D07A_GZIP_ROUNDTRIP_FAILED")
    return result


def _manifest_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"manifest_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _read_manifest(
    root: Path,
    *,
    expected_digest: str,
    code: str,
) -> Mapping[str, Any]:
    try:
        value = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FitWorkerError(code + "_MANIFEST_UNREADABLE") from exc
    manifest = _object(value, code + "_MANIFEST")
    if manifest.get("content_digest") != expected_digest:
        raise FitWorkerError(code + "_MANIFEST_DIGEST_MISMATCH")
    return manifest


def _preflight(teacher_root: Path, candidate_root: Path, output_root: Path) -> None:
    original_root = os.environ.get("PH_D07A_ORIGINAL_REPOSITORY_ROOT", "")
    if not original_root or Path(original_root).exists():
        raise FitWorkerError("PH_D07A_REPOSITORY_ROOT_VISIBLE")
    forbidden_mounts = (
        Path("/source"),
        Path("/environment_files"),
        teacher_root / "environment_files",
        candidate_root / "environment_files",
    )
    if any(path.exists() for path in forbidden_mounts):
        raise FitWorkerError("PH_D07A_ENVIRONMENT_SOURCE_MOUNT_VISIBLE")
    if (
        not teacher_root.is_dir()
        or not candidate_root.is_dir()
        or not output_root.is_dir()
    ):
        raise FitWorkerError("PH_D07A_MOUNT_MISSING")
    if any(output_root.iterdir()):
        raise FitWorkerError("PH_D07A_OUTPUT_NOT_EMPTY")


def _runtime_preflight() -> dict[str, str]:
    expected_version = os.environ.get("PH_D07A_PYTHON_VERSION", "")
    archive_sha256 = os.environ.get("PH_D07A_RUNTIME_ARCHIVE_SHA256", "")
    tree_digest = os.environ.get("PH_D07A_RUNTIME_TREE_DIGEST", "")
    executable_sha256 = os.environ.get("PH_D07A_PYTHON_EXECUTABLE_SHA256", "")
    executable = Path(sys.executable)
    if (
        expected_version != "3.12.13"
        or platform.python_version() != expected_version
        or executable.as_posix() != "/python-runtime/bin/python3"
        or not archive_sha256
        or not tree_digest.startswith("hds-ph-d06-python-runtime-tree:")
        or not executable_sha256
    ):
        raise FitWorkerError("PH_D07A_PYTHON_RUNTIME_BINDING_MISMATCH")
    actual_executable_sha256 = _sha256(executable.read_bytes())
    if actual_executable_sha256 != executable_sha256:
        raise FitWorkerError("PH_D07A_PYTHON_EXECUTABLE_SHA256_MISMATCH")
    return {
        "python_version": expected_version,
        "python_runtime_archive_sha256": archive_sha256,
        "python_runtime_tree_digest": tree_digest,
        "python_executable_sha256": actual_executable_sha256,
    }


def _read_package(
    root: Path,
    row: Mapping[str, Any],
    *,
    path_field: str,
    sha_field: str,
    digest_field: str,
    code: str,
) -> Mapping[str, Any]:
    relative = row.get(path_field)
    expected_sha = row.get(sha_field)
    expected_digest = row.get(digest_field)
    if (
        not isinstance(relative, str)
        or not relative.endswith(".json.gz")
        or not isinstance(expected_sha, str)
        or not isinstance(expected_digest, str)
    ):
        raise FitWorkerError(code + "_ROW_INVALID")
    path = root / relative
    try:
        compressed = path.read_bytes()
        value = json.loads(gzip.decompress(compressed))
    except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
        raise FitWorkerError(code + "_UNREADABLE") from exc
    if _sha256(compressed) != expected_sha:
        raise FitWorkerError(code + "_SHA256_MISMATCH")
    package = _object(value, code)
    if package.get("content_digest") != expected_digest:
        raise FitWorkerError(code + "_CONTENT_DIGEST_MISMATCH")
    return package


def _teacher_rows(
    manifest: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = manifest.get("packages")
    if not isinstance(rows, list) or len(rows) != 25:
        raise FitWorkerError("PH_D07A_TEACHER_COVERAGE_INVALID")
    by_digest: dict[str, Mapping[str, Any]] = {}
    for raw_row in rows:
        row = _object(raw_row, "PH_D07A_TEACHER_ROW")
        digest = row.get("package_content_digest")
        if not isinstance(digest, str) or not digest.startswith(
            "hds-arc3-teacher-trajectory-package:"
        ):
            raise FitWorkerError("PH_D07A_TEACHER_ROW_DIGEST_INVALID")
        if digest in by_digest:
            raise FitWorkerError("PH_D07A_TEACHER_PACKAGE_DUPLICATE")
        by_digest[digest] = row
    return by_digest


def _teacher_for_candidate(
    teacher_rows: Mapping[str, Mapping[str, Any]],
    teacher_root: Path,
    candidate_row: Mapping[str, Any],
) -> Mapping[str, Any]:
    source_digest = candidate_row.get("source_package_content_digest")
    source_sha256 = candidate_row.get("source_package_sha256")
    if not isinstance(source_digest, str) or not isinstance(
        source_sha256, str
    ):
        raise FitWorkerError("PH_D07A_CANDIDATE_SOURCE_BINDING_INVALID")
    teacher_row = teacher_rows.get(source_digest)
    if teacher_row is None:
        raise FitWorkerError("PH_D07A_TEACHER_SOURCE_DIGEST_UNBOUND")
    if teacher_row.get("package_sha256") != source_sha256:
        raise FitWorkerError("PH_D07A_TEACHER_SOURCE_SHA256_MISMATCH")
    return _read_package(
        teacher_root,
        teacher_row,
        path_field="package_path",
        sha_field="package_sha256",
        digest_field="package_content_digest",
        code="PH_D07A_TEACHER_PACKAGE",
    )


def _fit_bytes(
    teacher_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    teacher_root: Path,
    candidate_root: Path,
) -> tuple[list[tuple[str, bytes]], dict[str, JsonValue]]:
    if (
        candidate_manifest.get("status") != "MULTI_HYPOTHESIS_CORPUS_COMPLETE"
        or candidate_manifest.get("candidate_count") != 450
        or candidate_manifest.get("executable_candidate_count") != 400
        or candidate_manifest.get("rejected_adversarial_count") != 50
        or candidate_manifest.get("candidate_adoption_count") != 0
    ):
        raise FitWorkerError("PH_D07A_CANDIDATE_MANIFEST_BOUNDARY_MISMATCH")
    raw_rows = candidate_manifest.get("case_packages")
    if not isinstance(raw_rows, list) or len(raw_rows) != 25:
        raise FitWorkerError("PH_D07A_CANDIDATE_COVERAGE_INVALID")
    teacher_rows = _teacher_rows(teacher_manifest)
    consumed_teacher_digests: set[str] = set()

    pending: list[tuple[str, bytes]] = []
    output_rows: list[dict[str, JsonValue]] = []
    status_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    axis_counts: Counter[str] = Counter()
    family_status_counts: dict[str, Counter[str]] = {}
    teacher_steps = 0
    candidate_steps = 0
    fit_result_count = 0
    exact_fit_count = 0
    eligible_count = 0
    rejected_count = 0

    for raw_row in raw_rows:
        row = _object(raw_row, "PH_D07A_CANDIDATE_ROW")
        candidate_package = _read_package(
            candidate_root,
            row,
            path_field="candidate_package_path",
            sha_field="candidate_package_sha256",
            digest_field="candidate_package_content_digest",
            code="PH_D07A_CANDIDATE_PACKAGE",
        )
        teacher_package = _teacher_for_candidate(
            teacher_rows,
            teacher_root,
            row,
        )
        case_ref = candidate_package.get("teacher_case_ref")
        if (
            not isinstance(case_ref, str)
            or row.get("teacher_case_ref") != case_ref
            or teacher_case_ref(teacher_package) != case_ref
        ):
            raise FitWorkerError("PH_D07A_CASE_BINDING_MISMATCH")
        source_digest = row.get("source_package_content_digest")
        if not isinstance(source_digest, str):
            raise FitWorkerError("PH_D07A_CANDIDATE_SOURCE_DIGEST_INVALID")
        if source_digest in consumed_teacher_digests:
            raise FitWorkerError("PH_D07A_TEACHER_CASE_DUPLICATE")
        consumed_teacher_digests.add(source_digest)
        fit_case = evaluate_case(candidate_package, teacher_package)
        case_digest = case_ref.rsplit(":", 1)[-1]
        relative = f"cases/{case_digest}.json.gz"
        uncompressed = canonical_json_document_bytes(fit_case)
        compressed = _deterministic_gzip(uncompressed)
        pending.append((relative, compressed))

        raw_results = fit_case.get("fit_results")
        if not isinstance(raw_results, list) or len(raw_results) != 18:
            raise FitWorkerError("PH_D07A_FIT_RESULT_COVERAGE_INVALID")
        for raw_result in raw_results:
            fit_result = _object(raw_result, "PH_D07A_FIT_RESULT")
            status = str(fit_result.get("fit_status"))
            support = str(fit_result.get("mechanism_support_state"))
            family = str(fit_result.get("candidate_family"))
            status_counts[status] += 1
            support_counts[support] += 1
            family_status_counts.setdefault(family, Counter())[status] += 1
            axis = fit_result.get("comparison_axis")
            if isinstance(axis, str):
                axis_counts[axis] += 1
            exact_fit_count += fit_result.get("exact_fit") is True
            eligible_count += (
                fit_result.get("evaluation_eligibility")
                == "ELIGIBLE_EXECUTABLE_IR"
            )
            rejected_count += (
                fit_result.get("evaluation_eligibility")
                == "NOT_ELIGIBLE_DG_08"
            )
        fit_result_count += len(raw_results)
        teacher_steps += _integer(
            fit_case.get("teacher_step_count"),
            "PH_D07A_TEACHER_STEP_COUNT",
        )
        candidate_steps += _integer(
            fit_case.get("candidate_step_evaluation_count"),
            "PH_D07A_CANDIDATE_STEP_COUNT",
        )
        output_rows.append(
            {
                "teacher_case_ref": case_ref,
                "teacher_package_content_digest": fit_case[
                    "teacher_package_content_digest"
                ],
                "candidate_package_content_digest": fit_case[
                    "candidate_package_content_digest"
                ],
                "fit_case_content_digest": fit_case["content_digest"],
                "fit_case_path": relative,
                "fit_case_sha256": _sha256(compressed),
                "fit_case_size_bytes": len(compressed),
                "fit_case_uncompressed_sha256": _sha256(uncompressed),
                "fit_case_uncompressed_size_bytes": len(uncompressed),
                "teacher_step_count": fit_case["teacher_step_count"],
                "candidate_step_evaluation_count": fit_case[
                    "candidate_step_evaluation_count"
                ],
                "fit_status_counts": fit_case["fit_status_counts"],
            }
        )

    pending.sort(key=lambda item: item[0])
    output_rows.sort(key=lambda item: cast(str, item["teacher_case_ref"]))
    if (
        len(teacher_rows) != 25
        or len(consumed_teacher_digests) != 25
        or fit_result_count != 450
        or eligible_count != 400
        or rejected_count != 50
        or teacher_steps != 11574
        or candidate_steps != 185184
        or set(axis_counts) != set(FIT_AXES)
    ):
        raise FitWorkerError("PH_D07A_AGGREGATE_ACCOUNTING_MISMATCH")

    family_counts_json: dict[str, JsonValue] = {
        family: cast(dict[str, JsonValue], dict(sorted(counts.items())))
        for family, counts in sorted(family_status_counts.items())
    }
    manifest: dict[str, JsonValue] = {
        "schema_version": MANIFEST_VERSION,
        "manifest_id": "",
        "phase_id": "PH-D07A",
        "artifact_version": ARTIFACT_VERSION,
        "status": "EXTENSIONAL_FIT_ACCOUNTED",
        "evaluator_version": EVALUATOR_VERSION,
        "teacher_manifest_digest": EXPECTED_TEACHER_MANIFEST_DIGEST,
        "candidate_manifest_digest": EXPECTED_CANDIDATE_MANIFEST_DIGEST,
        "primary_source_manifest_digest_before": EXPECTED_TEACHER_MANIFEST_DIGEST,
        "primary_source_manifest_digest_after": EXPECTED_TEACHER_MANIFEST_DIGEST,
        "primary_source_manifest_mutation_count": 0,
        "teacher_case_count": 25,
        "teacher_step_count": teacher_steps,
        "fit_case_package_count": len(output_rows),
        "candidate_count": fit_result_count,
        "eligible_fit_evaluation_count": eligible_count,
        "rejected_ineligible_candidate_count": rejected_count,
        "candidate_step_evaluation_count": candidate_steps,
        "exact_fit_candidate_count": exact_fit_count,
        "fit_status_counts": cast(
            dict[str, JsonValue],
            dict(sorted(status_counts.items())),
        ),
        "mechanism_support_state_counts": cast(
            dict[str, JsonValue],
            dict(sorted(support_counts.items())),
        ),
        "axis_candidate_counts": cast(
            dict[str, JsonValue],
            {axis: axis_counts[axis] for axis in FIT_AXES},
        ),
        "candidate_family_fit_status_counts": family_counts_json,
        "case_packages": cast(list[JsonValue], output_rows),
        "gates": {
            "DG-07": "PASS_EXTENSIONAL_FIT_ACCOUNTED",
            "DG-08": "PASS_PRIVILEGE_REJECTION_PRESERVED",
            "DG-09": "PASS_FIT_CAUSAL_SEPARATION",
        },
        "phase_boundaries": {
            "candidate_adoption_count": 0,
            "candidate_selection_count": 0,
            "causal_support_count": 0,
            "real_intervention_execution_count": 0,
            "rule_promotion_count": 0,
            "bridge_runtime_capability_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "claim_boundary": (
            "Exact fit is trajectory-local observational compatibility only. "
            "It establishes neither unique mechanism nor causal support."
        ),
        "digest_excluded_fields": ["manifest_id", "content_digest"],
        "content_digest": "",
    }
    policy = _manifest_policy()
    manifest["manifest_id"] = content_derived_id(
        "hds-arc3-extensional-fit-manifest-id",
        manifest,
        policy=policy,
    )
    manifest["content_digest"] = logical_content_digest(
        "hds-arc3-extensional-fit-manifest",
        manifest,
        policy=policy,
    )
    return pending, manifest


def _write_outputs(
    output_root: Path,
    pending: list[tuple[str, bytes]],
    manifest: Mapping[str, JsonValue],
) -> None:
    for relative, payload in pending:
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (output_root / "manifest.json").write_bytes(
        canonical_json_document_bytes(manifest)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    teacher_root = arguments.teacher_root.resolve()
    candidate_root = arguments.candidate_root.resolve()
    output_root = arguments.output_root.resolve()
    _preflight(teacher_root, candidate_root, output_root)
    runtime = _runtime_preflight()
    teacher_manifest = _read_manifest(
        teacher_root,
        expected_digest=EXPECTED_TEACHER_MANIFEST_DIGEST,
        code="PH_D07A_TEACHER",
    )
    candidate_manifest = _read_manifest(
        candidate_root,
        expected_digest=EXPECTED_CANDIDATE_MANIFEST_DIGEST,
        code="PH_D07A_CANDIDATE",
    )
    pending, manifest = _fit_bytes(
        teacher_manifest,
        candidate_manifest,
        teacher_root,
        candidate_root,
    )
    _write_outputs(output_root, pending, manifest)

    host_mount = os.environ.get("PH_D07A_HOST_MOUNT_NAMESPACE", "")
    host_network = os.environ.get("PH_D07A_HOST_NETWORK_NAMESPACE", "")
    current_mount = os.readlink("/proc/self/ns/mnt")
    current_network = os.readlink("/proc/self/ns/net")
    secret_markers = ("TOKEN", "SECRET", "PASSWORD", "COOKIE", "CREDENTIAL")
    secret_count = sum(
        any(marker in key.upper() for marker in secret_markers)
        for key in os.environ
    )
    if (
        not host_mount
        or not host_network
        or current_mount == host_mount
        or current_network == host_network
        or secret_count != 0
    ):
        raise FitWorkerError("PH_D07A_NAMESPACE_OR_SECRET_BOUNDARY_MISMATCH")
    summary = {
        "status": "PASS",
        "mount_namespace_enforced": True,
        "network_namespace_enforced": True,
        "repository_root_visible": False,
        "environment_source_mount_observed": False,
        "environment_source_access_count": 0,
        "secret_environment_key_count": 0,
        "teacher_package_read_count": 25,
        "candidate_package_read_count": 25,
        "fit_case_package_count": 25,
        "candidate_accounting_count": 450,
        "eligible_fit_evaluation_count": 400,
        "candidate_step_evaluation_count": 185184,
        "primary_source_write_count": 0,
        "candidate_source_write_count": 0,
        "candidate_selection_count": 0,
        "causal_support_count": 0,
        "real_intervention_execution_count": 0,
        "rule_promotion_count": 0,
        "output_file_count": 26,
        "output_manifest_digest": manifest["content_digest"],
        "checkout_projection_digest": os.environ.get(
            "PH_D07A_CHECKOUT_PROJECTION_DIGEST",
            "",
        ),
        "input_projection_digest": os.environ.get(
            "PH_D07A_INPUT_PROJECTION_DIGEST",
            "",
        ),
        **runtime,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
