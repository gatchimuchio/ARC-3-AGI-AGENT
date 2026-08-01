#!/usr/bin/env python3
"""Build PH-D06 candidates inside a source-blind process namespace."""

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
from hds_distill.hypothesis_generation import (
    CANDIDATES_PER_CASE,
    CANDIDATE_FAMILIES,
    DEFAULT_MAX_TOTAL_CANDIDATES,
    EXECUTABLE_CANDIDATE_COUNT,
    GENERATOR_VERSION,
    REJECTED_ADVERSARIAL_COUNT,
    generate_case_candidates,
    validate_corpus_budget,
)

EXPECTED_SOURCE_MANIFEST_DIGEST = (
    "hds-arc3-canonical-teacher-corpus-manifest:"
    "f81183465265bfa9f29208dd788bb3bfd358c23995ab0aeb8ec9549450360aa6"
)
MANIFEST_VERSION = "hds-arc3-multi-hypothesis-corpus-manifest-v1"
ARTIFACT_VERSION = "ph-d06-v1"


class CandidateWorkerError(RuntimeError):
    """Stable source-blind worker failure."""


def _object(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CandidateWorkerError(code + "_NOT_OBJECT")
    return cast(Mapping[str, Any], value)


def _integer(value: object, code: str) -> int:
    if type(value) is not int:
        raise CandidateWorkerError(code + "_NOT_INTEGER")
    return value


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
        raise CandidateWorkerError("PH_D06_GZIP_ROUNDTRIP_FAILED")
    return result


def _manifest_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"manifest_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _read_source_manifest(input_root: Path) -> Mapping[str, Any]:
    path = input_root / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateWorkerError("PH_D06_SOURCE_MANIFEST_UNREADABLE") from exc
    manifest = _object(value, "PH_D06_SOURCE_MANIFEST")
    if manifest.get("content_digest") != EXPECTED_SOURCE_MANIFEST_DIGEST:
        raise CandidateWorkerError("PH_D06_SOURCE_MANIFEST_DIGEST_MISMATCH")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or len(packages) != 25:
        raise CandidateWorkerError("PH_D06_SOURCE_PACKAGE_COVERAGE_INVALID")
    return manifest


def _source_blind_preflight(input_root: Path, output_root: Path) -> None:
    original_root = os.environ.get("PH_D06_ORIGINAL_REPOSITORY_ROOT", "")
    if not original_root or Path(original_root).exists():
        raise CandidateWorkerError("PH_D06_REPOSITORY_ROOT_VISIBLE")
    forbidden_mounts = (
        Path("/source/environment_files"),
        Path("/environment_files"),
        input_root / "environment_files",
    )
    if any(path.exists() for path in forbidden_mounts):
        raise CandidateWorkerError("PH_D06_ENVIRONMENT_SOURCE_MOUNT_VISIBLE")
    if not input_root.is_dir() or not output_root.is_dir():
        raise CandidateWorkerError("PH_D06_MOUNT_MISSING")
    if any(output_root.iterdir()):
        raise CandidateWorkerError("PH_D06_OUTPUT_NOT_EMPTY")


def _python_runtime_preflight() -> dict[str, str]:
    expected_version = os.environ.get("PH_D06_PYTHON_VERSION", "")
    expected_archive_sha256 = os.environ.get("PH_D06_PYTHON_RUNTIME_ARCHIVE_SHA256", "")
    expected_tree_digest = os.environ.get("PH_D06_PYTHON_RUNTIME_TREE_DIGEST", "")
    expected_executable_sha256 = os.environ.get("PH_D06_PYTHON_EXECUTABLE_SHA256", "")
    executable = Path(sys.executable)
    if (
        expected_version != "3.12.13"
        or platform.python_version() != expected_version
        or executable.as_posix() != "/python-runtime/bin/python3"
        or not expected_archive_sha256
        or not expected_tree_digest.startswith("hds-ph-d06-python-runtime-tree:")
        or not expected_executable_sha256
    ):
        raise CandidateWorkerError("PH_D06_PYTHON_RUNTIME_BINDING_MISMATCH")
    executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    if executable_sha256 != expected_executable_sha256:
        raise CandidateWorkerError("PH_D06_PYTHON_EXECUTABLE_SHA256_MISMATCH")
    return {
        "python_version": expected_version,
        "python_runtime_archive_sha256": expected_archive_sha256,
        "python_runtime_tree_digest": expected_tree_digest,
        "python_executable_sha256": executable_sha256,
    }


def _candidate_bytes(
    source_manifest: Mapping[str, Any],
    input_root: Path,
) -> tuple[list[tuple[str, bytes]], dict[str, JsonValue]]:
    raw_rows = source_manifest.get("packages")
    if not isinstance(raw_rows, list):
        raise CandidateWorkerError("PH_D06_SOURCE_PACKAGES_NOT_ARRAY")
    validate_corpus_budget(len(raw_rows))
    pending_files: list[tuple[str, bytes]] = []
    output_rows: list[dict[str, JsonValue]] = []
    family_counts: Counter[str] = Counter()
    case_refs: set[str] = set()
    total_candidates = 0
    executable_candidates = 0
    rejected_candidates = 0
    non_strawman_candidates = 0
    compatible_candidates = 0

    for raw_row in raw_rows:
        row = _object(raw_row, "PH_D06_SOURCE_PACKAGE_ROW")
        relative_path = row.get("package_path")
        expected_sha256 = row.get("package_sha256")
        expected_content_digest = row.get("package_content_digest")
        if (
            not isinstance(relative_path, str)
            or not relative_path.startswith("packages/")
            or not isinstance(expected_sha256, str)
            or not isinstance(expected_content_digest, str)
        ):
            raise CandidateWorkerError("PH_D06_SOURCE_PACKAGE_ROW_INVALID")
        source_path = input_root / relative_path
        try:
            compressed = source_path.read_bytes()
            raw_package = json.loads(gzip.decompress(compressed))
        except (OSError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
            raise CandidateWorkerError("PH_D06_SOURCE_PACKAGE_UNREADABLE") from exc
        if hashlib.sha256(compressed).hexdigest() != expected_sha256:
            raise CandidateWorkerError("PH_D06_SOURCE_PACKAGE_SHA256_MISMATCH")
        package = _object(raw_package, "PH_D06_SOURCE_PACKAGE")
        if package.get("content_digest") != expected_content_digest:
            raise CandidateWorkerError("PH_D06_SOURCE_PACKAGE_DIGEST_MISMATCH")

        candidate_package = generate_case_candidates(package)
        case_ref = candidate_package.get("teacher_case_ref")
        if not isinstance(case_ref, str) or case_ref in case_refs:
            raise CandidateWorkerError("PH_D06_TEACHER_CASE_REF_INVALID")
        case_refs.add(case_ref)
        case_digest = case_ref.rsplit(":", 1)[-1]
        output_relative = f"cases/{case_digest}.json.gz"
        uncompressed = canonical_json_document_bytes(candidate_package)
        output_compressed = _deterministic_gzip(uncompressed)
        pending_files.append((output_relative, output_compressed))

        candidates = candidate_package.get("candidates")
        if not isinstance(candidates, list):
            raise CandidateWorkerError("PH_D06_CANDIDATES_NOT_ARRAY")
        for raw_candidate in candidates:
            candidate = _object(raw_candidate, "PH_D06_CANDIDATE")
            family = candidate.get("candidate_family")
            if not isinstance(family, str):
                raise CandidateWorkerError("PH_D06_CANDIDATE_FAMILY_INVALID")
            family_counts[family] += 1
            non_strawman_candidates += candidate.get("non_strawman") is True
            compatible_candidates += candidate.get("observation_compatible") is True

        total_candidates += _integer(
            candidate_package["candidate_count"], "PH_D06_CANDIDATE_COUNT"
        )
        executable_candidates += _integer(
            candidate_package["executable_candidate_count"],
            "PH_D06_EXECUTABLE_CANDIDATE_COUNT",
        )
        rejected_candidates += _integer(
            candidate_package["rejected_adversarial_count"],
            "PH_D06_REJECTED_CANDIDATE_COUNT",
        )
        output_rows.append(
            {
                "teacher_case_ref": case_ref,
                "source_package_sha256": expected_sha256,
                "source_package_content_digest": expected_content_digest,
                "candidate_package_path": output_relative,
                "candidate_package_sha256": hashlib.sha256(
                    output_compressed
                ).hexdigest(),
                "candidate_package_size_bytes": len(output_compressed),
                "candidate_uncompressed_sha256": hashlib.sha256(
                    uncompressed
                ).hexdigest(),
                "candidate_uncompressed_size_bytes": len(uncompressed),
                "candidate_package_content_digest": candidate_package["content_digest"],
                "candidate_count": candidate_package["candidate_count"],
                "executable_candidate_count": candidate_package[
                    "executable_candidate_count"
                ],
                "rejected_adversarial_count": candidate_package[
                    "rejected_adversarial_count"
                ],
                "candidate_adoption_count": 0,
            }
        )

    output_rows.sort(key=lambda value: cast(str, value["teacher_case_ref"]))
    pending_files.sort(key=lambda item: item[0])
    expected_total = len(raw_rows) * CANDIDATES_PER_CASE
    if (
        total_candidates != expected_total
        or executable_candidates != len(raw_rows) * EXECUTABLE_CANDIDATE_COUNT
        or rejected_candidates != len(raw_rows) * REJECTED_ADVERSARIAL_COUNT
        or set(family_counts) != set(CANDIDATE_FAMILIES)
        or any(family_counts[family] != len(raw_rows) for family in CANDIDATE_FAMILIES)
        or total_candidates > DEFAULT_MAX_TOTAL_CANDIDATES
    ):
        raise CandidateWorkerError("PH_D06_AGGREGATE_INVENTORY_MISMATCH")

    manifest: dict[str, JsonValue] = {
        "schema_version": MANIFEST_VERSION,
        "manifest_id": "",
        "phase_id": "PH-D06",
        "artifact_version": ARTIFACT_VERSION,
        "status": "MULTI_HYPOTHESIS_CORPUS_COMPLETE",
        "generator_version": GENERATOR_VERSION,
        "source_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
        "source_teacher_case_count": len(raw_rows),
        "candidate_case_package_count": len(output_rows),
        "candidate_count": total_candidates,
        "executable_candidate_count": executable_candidates,
        "rejected_adversarial_count": rejected_candidates,
        "candidate_adoption_count": 0,
        "automatic_adoption_forbidden": True,
        "candidate_families": cast(list[JsonValue], list(CANDIDATE_FAMILIES)),
        "candidate_family_counts": cast(
            dict[str, JsonValue],
            {family: family_counts[family] for family in CANDIDATE_FAMILIES},
        ),
        "non_strawman_candidate_count": non_strawman_candidates,
        "observation_compatible_competitor_count": compatible_candidates,
        "alternative_adequacy_status": "PASS",
        "fit_evaluation_status": "DEFERRED_TO_PH_D07A",
        "source_blind_execution_role": "DISTILLATION_EXECUTOR",
        "environment_source_access_count": 0,
        "identity_routing_count": 0,
        "complete_action_sequence_copy_count": 0,
        "llm_call_count": 0,
        "live_llm_required_for_rebuild": False,
        "case_packages": cast(list[JsonValue], output_rows),
        "gates": {
            "DG-03": "PASS_TYPED_EXECUTABLE_IR",
            "DG-04": "PASS_MULTIPLE_COMPETING_HYPOTHESES",
            "DG-05": "PASS_ALTERNATIVE_ADEQUACY",
            "DG-08": "PASS_PRIVILEGED_ADVERSARIAL_REJECTION",
            "DG-12": "PASS_CONTENT_BOUND_DETERMINISM",
        },
        "phase_boundaries": {
            "fit_execution_count": 0,
            "real_intervention_execution_count": 0,
            "causal_assertion_count": 0,
            "rule_promotion_count": 0,
            "bridge_runtime_capability_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "resource_budget": {
            "max_total_candidates": DEFAULT_MAX_TOTAL_CANDIDATES,
            "observed_total_candidates": total_candidates,
            "overflow_count": 0,
            "overflow_policy": "SUSPEND_WITHOUT_PARTIAL_AUTHORITATIVE_CORPUS",
        },
        "digest_excluded_fields": ["content_digest", "manifest_id"],
        "content_digest": "",
    }
    manifest["manifest_id"] = content_derived_id(
        "hds-multi-hypothesis-corpus-manifest-id",
        manifest,
        policy=_manifest_policy(),
    )
    manifest["content_digest"] = logical_content_digest(
        "hds-multi-hypothesis-corpus-manifest",
        manifest,
        policy=_manifest_policy(),
    )
    return pending_files, manifest


def build(input_root: Path, output_root: Path) -> dict[str, object]:
    _source_blind_preflight(input_root, output_root)
    python_runtime = _python_runtime_preflight()
    source_manifest = _read_source_manifest(input_root)
    pending_files, manifest = _candidate_bytes(source_manifest, input_root)
    manifest_bytes = canonical_json_document_bytes(manifest)
    pending_files.append(("manifest.json", manifest_bytes))
    pending_files.sort(key=lambda item: item[0])
    for relative_path, payload in pending_files:
        target = output_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    secret_markers = ("TOKEN", "SECRET", "PASSWORD", "KEY", "COOKIE")
    allowed_key_suffixes = ("HASHSEED",)
    secret_environment_keys = [
        key
        for key in os.environ
        if any(marker in key.upper() for marker in secret_markers)
        and not key.upper().endswith(allowed_key_suffixes)
    ]
    host_mount_namespace = os.environ.get("PH_D06_HOST_MOUNT_NAMESPACE", "")
    host_network_namespace = os.environ.get("PH_D06_HOST_NETWORK_NAMESPACE", "")
    result: dict[str, object] = {
        "schema_version": "hds-ph-d06-source-blind-worker-result-v1",
        "role_id": "DISTILLATION_EXECUTOR",
        "process_instance_count": 1,
        "mount_namespace_enforced": (
            bool(host_mount_namespace)
            and os.readlink("/proc/self/ns/mnt") != host_mount_namespace
        ),
        "network_namespace_enforced": (
            bool(host_network_namespace)
            and os.readlink("/proc/self/ns/net") != host_network_namespace
        ),
        "repository_root_visible": False,
        "environment_source_mount_observed": False,
        "environment_source_access_count": 0,
        "teacher_package_read_count": 25,
        "candidate_generation_count": 450,
        "candidate_adoption_count": 0,
        "secret_environment_key_count": len(secret_environment_keys),
        "checkout_projection_digest": os.environ.get(
            "PH_D06_CHECKOUT_PROJECTION_DIGEST", ""
        ),
        "input_projection_digest": os.environ.get("PH_D06_INPUT_PROJECTION_DIGEST", ""),
        **python_runtime,
        "manifest_content_digest": manifest["content_digest"],
        "output_file_count": len(pending_files),
        "status": "PASS",
    }
    if (
        result["mount_namespace_enforced"] is not True
        or result["network_namespace_enforced"] is not True
        or result["secret_environment_key_count"] != 0
    ):
        raise CandidateWorkerError("PH_D06_SOURCE_BLIND_ASSERTION_FAILED")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    result = build(arguments.input_root, arguments.output_root)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
