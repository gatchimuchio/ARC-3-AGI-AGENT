#!/usr/bin/env python3
"""Build the synthetic PH-D02A canonical conformance vectors.

The builder reads only the checked canonicalization contract and synthetic
constants in this file. It never reads teacher/source payloads, executes an
environment, accesses a network, or grants a phase/Owner approval.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.canonical import (  # noqa: E402
    CanonicalTensor,
    DigestExclusionPolicy,
    bind_trajectory_digests,
    build_canonical_npz,
    build_canonical_zip,
    canonical_json_document_bytes,
    canonical_jsonl_bytes,
    canonical_npz_digests,
    canonical_npz_logical_value,
    content_derived_id,
    logical_content_digest,
    logical_digest_body,
    physical_package_digest,
    verify_canonical_json_document_bytes,
)

CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "input"
    / "canonicalization_contract.json"
)
DEFAULT_OUTPUT_ROOT = (
    REPOSITORY_ROOT / "distillation" / "artifacts" / "test_vectors"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"artifact_id"}),
        digest_fields=frozenset({"content_digest"}),
        timestamp_fields=frozenset({"created_at"}),
        physical_metadata_fields=frozenset({"local_path"}),
    )


def _logical_fixture() -> dict[str, object]:
    return {
        "artifact_id": "VARIED_EXCLUDED",
        "confidence_ppm": 875_000,
        "content_digest": "VARIED_EXCLUDED",
        "created_at": "VARIED_EXCLUDED",
        "local_path": "VARIED_EXCLUDED",
        "ordered": ["second", "first"],
        "provenance": {
            "source_digest": "source-sha256:bound",
            "source_id": "source-stays-bound",
        },
        "tags": {"zeta", "alpha", "e\u0301"},
        "title": "Cafe\u0301",
        "unordered": [
            {"name": "beta", "rank": 2},
            {"name": "alpha", "rank": 1},
            {"name": "cafe\u0301", "rank": 3},
        ],
    }


def _jsonl_fixture() -> list[dict[str, object]]:
    return [
        {
            "confidence_ppm": 500_000,
            "payload": {"kind": "z-last"},
            "record_id": "record-z",
        },
        {
            "confidence_ppm": 1_000_000,
            "payload": {"kind": "first"},
            "record_id": "record-a",
        },
        {
            "confidence_ppm": 750_000,
            "payload": {"kind": "Cafe\u0301"},
            "record_id": "record-e\u0301",
        },
    ]


def _tensors() -> dict[str, CanonicalTensor]:
    return {
        "pixels": CanonicalTensor.from_values(
            dtype="|u1",
            shape=(2, 3),
            values=(0, 1, 2, 3, 4, 255),
        ),
        "scores": CanonicalTensor.from_values(
            dtype="<f4",
            shape=(2,),
            values=(0.0, 1.5),
        ),
        "valid": CanonicalTensor.from_values(
            dtype="|b1",
            shape=(3,),
            values=(True, False, True),
        ),
    }


def _contract_record(contract_payload: bytes) -> dict[str, Any]:
    value = verify_canonical_json_document_bytes(contract_payload)
    if not isinstance(value, dict):
        raise TypeError("D02A_CONTRACT_OBJECT_REQUIRED")
    claimed = value.get("content_digest")
    computed = logical_content_digest(
        "hds-canonicalization-contract",
        value,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    if claimed != computed:
        raise ValueError("D02A_CONTRACT_CONTENT_DIGEST_MISMATCH")
    return value


def build_vector_artifacts(
    contract_payload: bytes,
) -> dict[str, bytes]:
    """Return all canonical vector bytes keyed by repository filename."""

    contract = _contract_record(contract_payload)
    logical_fixture = _logical_fixture()
    body = logical_digest_body(
        logical_fixture,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    json_payload = canonical_json_document_bytes(body)
    jsonl_payload = canonical_jsonl_bytes(reversed(_jsonl_fixture()))
    zip_members = {
        "z-last.bin": b"\x00\x01",
        "records.jsonl": jsonl_payload,
        "unicode/cafe\u0301.txt": "Cafe\u0301\n".encode(),
        "manifest.json": json_payload,
    }
    zip_payload = build_canonical_zip(zip_members)
    tensors = _tensors()
    npz_payload = build_canonical_npz(tensors)
    npz_digests = canonical_npz_digests(tensors)
    trajectory = bind_trajectory_digests(
        raw_payload=b'{"raw_action":"ACTION1","frame":[1,2]}',
        canonical_record={
            "trajectory_id": "excluded",
            "created_at": "excluded",
            "steps": [
                {"action": "ACTION1", "effect": "CHANGED"},
            ],
        },
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"trajectory_id"}),
            timestamp_fields=frozenset({"created_at"}),
        ),
    )
    output_records: dict[str, Any] = {
        "canonical_json": {
            "path": (
                "distillation/artifacts/test_vectors/"
                "canonical_json_v1.json"
            ),
            "sha256": _sha256(json_payload),
            "size_bytes": len(json_payload),
        },
        "canonical_jsonl": {
            "path": (
                "distillation/artifacts/test_vectors/"
                "canonical_jsonl_v1.jsonl"
            ),
            "record_count": 3,
            "sha256": _sha256(jsonl_payload),
            "size_bytes": len(jsonl_payload),
        },
        "canonical_npz": {
            "logical_content_digest": (
                npz_digests.logical_content_digest
            ),
            "logical_value": canonical_npz_logical_value(tensors),
            "path": (
                "distillation/artifacts/test_vectors/"
                "canonical_npz_v1.npz"
            ),
            "physical_package_digest": (
                npz_digests.physical_package_digest
            ),
            "sha256": _sha256(npz_payload),
            "size_bytes": len(npz_payload),
        },
        "canonical_zip": {
            "members": [
                {
                    "name": name,
                    "sha256": _sha256(payload),
                    "size_bytes": len(payload),
                }
                for name, payload in sorted(
                    {
                        "z-last.bin": b"\x00\x01",
                        "records.jsonl": jsonl_payload,
                        "unicode/café.txt": "Café\n".encode(),
                        "manifest.json": json_payload,
                    }.items(),
                    key=lambda item: item[0].encode("utf-8"),
                )
            ],
            "path": (
                "distillation/artifacts/test_vectors/"
                "canonical_zip_v1.zip"
            ),
            "physical_package_digest": physical_package_digest(
                "hds-test-zip-physical",
                zip_payload,
            ),
            "sha256": _sha256(zip_payload),
            "size_bytes": len(zip_payload),
        },
        "content_derived_id": content_derived_id(
            "hds-test-id",
            logical_fixture,
            policy=_policy(),
            unordered_paths=("/unordered",),
        ),
        "logical_content_digest": logical_content_digest(
            "hds-test-logical",
            logical_fixture,
            policy=_policy(),
            unordered_paths=("/unordered",),
        ),
        "trajectory_digests": trajectory.as_json(),
    }
    manifest: dict[str, object] = {
        "schema_version": "hds-canonical-test-vectors-v1",
        "phase_id": "PH-D02A",
        "vector_set_id": "HDS-PH-D02A-CANONICAL-TEST-VECTORS-V1",
        "contract": {
            "path": "distillation/input/canonicalization_contract.json",
            "sha256": _sha256(contract_payload),
            "content_digest": contract["content_digest"],
        },
        "gates": ["DG-06", "DG-07"],
        "input_semantics": {
            "digest_exclusion_policy": {
                "id_fields": ["artifact_id"],
                "digest_fields": ["content_digest"],
                "timestamp_fields": ["created_at"],
                "physical_metadata_fields": ["local_path"],
            },
            "logical_fixture": {
                "artifact_id": "VARIED_EXCLUDED",
                "confidence_ppm": 875_000,
                "content_digest": "VARIED_EXCLUDED",
                "created_at": "VARIED_EXCLUDED",
                "local_path": "VARIED_EXCLUDED",
                "ordered": ["second", "first"],
                "provenance": {
                    "source_digest": "source-sha256:bound",
                    "source_id": "source-stays-bound",
                },
                "tags": {
                    "input_type": "PYTHON_SET",
                    "members": ["zeta", "alpha", "e\\u0301"],
                },
                "title": "NFD_INPUT_NORMALIZED_TO_NFC",
                "unordered": [
                    {"name": "beta", "rank": 2},
                    {"name": "alpha", "rank": 1},
                    {"name": "cafe\\u0301", "rank": 3},
                ],
            },
            "jsonl_fixture": {
                "input_order": ["record-z", "record-a", "record-e\\u0301"],
                "output_order": ["record-a", "record-z", "record-é"],
                "record_id_field": "record_id",
            },
            "trajectory_digest_exclusion_policy": {
                "id_fields": ["trajectory_id"],
                "digest_fields": [],
                "timestamp_fields": ["created_at"],
                "physical_metadata_fields": [],
            },
            "unordered_paths": ["/unordered"],
        },
        "outputs": output_records,
        "independent_rebuild_contract": {
            "count": 3,
            "expected": "BYTE_IDENTICAL",
            "vary": [
                "cwd",
                "excluded_self_metadata",
                "mapping_order",
                "unordered_order",
                "jsonl_record_order",
                "tensor_order",
                "zip_member_order",
                "PYTHONHASHSEED",
            ],
        },
        "digest_excluded_fields": [
            "content_digest",
            "vector_set_id",
        ],
    }
    manifest["content_digest"] = logical_content_digest(
        "hds-canonical-test-vectors",
        manifest,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"vector_set_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    return {
        "canonical_json_v1.json": json_payload,
        "canonical_jsonl_v1.jsonl": jsonl_payload,
        "canonical_npz_v1.npz": npz_payload,
        "canonical_zip_v1.zip": zip_payload,
        "canonical_test_vectors.json": canonical_json_document_bytes(
            manifest
        ),
    }


def write_vector_artifacts(
    artifacts: Mapping[str, bytes],
    output_root: Path,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for name, payload in sorted(artifacts.items()):
        (output_root / name).write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=CONTRACT_PATH,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    arguments = parser.parse_args()
    artifacts = build_vector_artifacts(arguments.contract.read_bytes())
    write_vector_artifacts(artifacts, arguments.output_root)
    for name, payload in sorted(artifacts.items()):
        print(f"{name} {len(payload)} {_sha256(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
