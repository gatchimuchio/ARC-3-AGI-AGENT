#!/usr/bin/env python3
"""Validate installed rev3 governance without external schema packages."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zipfile import ZipFile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = Path("control/rev3/REV3_CURRENT_SELECTOR.json")
SELECTOR_SCHEMA_PATH = Path(
    "docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V15.json"
)
DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "REV3_DOC_FIX_TO_PH-R-1_20260731.json"
)
DECISION_SCHEMA_PATH = Path(
    "docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V1.json"
)
APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "REV3_DOC_FIX_TO_PH-R-1_20260731.json"
)
APPROVAL_SCHEMA_PATH = Path(
    "docs/strategy/contracts/APPROVAL_RECORD_SCHEMA_V1.json"
)
FRAME_PATH = Path("control/rev3/PH-R-1_WORK_BLOCK_FRAME.json")
AUTHORITY_MANIFEST_PATH = Path(
    "docs/strategy/REV3_CURRENT_AUTHORITY_MANIFEST.json"
)
CORRECTION_ATTESTATION_PATH = Path(
    "control/rev3/REV3_DOC_FIX_EVIDENCE_ATTESTATION.json"
)
GOVERNANCE_CONTRACT_PATH = Path(
    "docs/strategy/contracts/REV3_GOVERNANCE_CONTRACT_V1.json"
)
BUILD_READY_PROFILE_PATH = Path(
    "docs/strategy/contracts/AGI_BUILD_READY_PROFILE_V1.json"
)
STANDING_AUTHORIZATION_SCHEMA_PATH = Path(
    "docs/strategy/contracts/OWNER_STANDING_AUTHORIZATION_SCHEMA_V1.json"
)
STANDING_AUTHORIZATION_PATH = Path(
    "control/rev3/OWNER_STANDING_AUTHORIZATIONS/"
    "CONTINUOUS_INTERNAL_DEVELOPMENT_20260731.json"
)
DECISION_V2_SCHEMA_PATH = Path(
    "docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V2.json"
)
PH_R00_ENTRY_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-R-1_TO_PH-R00_20260731.json"
)
PH_R00_ENTRY_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-R-1_TO_PH-R00_20260731.json"
)
PH_R00_FRAME_PATH = Path("control/rev3/PH-R00_WORK_BLOCK_FRAME.json")
PH_R00_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-R-1_TO_PH-R00.json"
)
PH_R00_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-R00_EVIDENCE_ATTESTATION.json"
)
PH_D00A_ENTRY_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-R00_TO_PH-D00A_20260731.json"
)
PH_D00A_ENTRY_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-R00_TO_PH-D00A_20260731.json"
)
PH_D00A_FRAME_PATH = Path("control/rev3/PH-D00A_WORK_BLOCK_FRAME.json")
PH_D00A_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-R00_TO_PH-D00A.json"
)
PH_D00A_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D00A_TO_PH-D00B_20260731.json"
)
PH_D00A_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D00A_TO_PH-D00B_20260731.json"
)
PH_D00A_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D00A_EVIDENCE_ATTESTATION.json"
)
PH_D00A_PHASE_STATE_PATH = Path("control/rev3/D00A_PHASE_STATE.json")
PH_D00B_FRAME_PATH = Path("control/rev3/PH-D00B_WORK_BLOCK_FRAME.json")
PH_D00B_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D00A_TO_PH-D00B.json"
)
PH_D00B_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D00B_TO_PH-D01A_20260731.json"
)
PH_D00B_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D00B_TO_PH-D01A_20260731.json"
)
PH_D00B_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D00B_EVIDENCE_ATTESTATION.json"
)
PH_D00B_PHASE_STATE_PATH = Path("control/rev3/D00B_PHASE_STATE.json")
PH_D01A_FRAME_PATH = Path("control/rev3/PH-D01A_WORK_BLOCK_FRAME.json")
PH_D01A_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D00B_TO_PH-D01A.json"
)
PH_D01A_SOURCE_INVENTORY_PATH = Path(
    "distillation/artifacts/reports/source_inventory.json"
)
PH_D01A_PROVENANCE_REPORT_PATH = Path(
    "distillation/artifacts/reports/primary_source_provenance.json"
)
PH_D01A_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D01A_TO_PH-D01B_20260731.json"
)
PH_D01A_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D01A_TO_PH-D01B_20260731.json"
)
PH_D01A_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D01A_EVIDENCE_ATTESTATION.json"
)
PH_D01A_PHASE_STATE_PATH = Path("control/rev3/D01A_PHASE_STATE.json")
PH_D01B_FRAME_PATH = Path("control/rev3/PH-D01B_WORK_BLOCK_FRAME.json")
PH_D01B_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D01A_TO_PH-D01B.json"
)
PH_D01B_MANIFEST_PLAN_PATH = Path(
    "distillation/input/manifest_freeze_plan.json"
)
PH_D01B_SOURCE_BLIND_PLAN_PATH = Path(
    "distillation/input/source_blind_execution_plan.json"
)
PH_D01B_SOURCE_BLIND_RECORD_PATH = Path(
    "distillation/artifacts/reports/source_blind_execution.json"
)
PH_D01B_ISOLATION_REPORT_PATH = Path(
    "distillation/artifacts/reports/environment_isolation.json"
)
PH_D01B_FREEZE_REPORT_PATH = Path(
    "distillation/artifacts/reports/source_manifest_freeze.json"
)
PH_D01B_ENVIRONMENT_MANIFEST_PATH = Path(
    "distillation/manifests/environment/arc3-replay.json"
)
PH_D01B_RUN_MANIFEST_PATH = Path(
    "distillation/manifests/run/ph-d01b-freeze.json"
)
PH_D01B_DOWNSTREAM_INVALIDATION_PATH = Path(
    "distillation/artifacts/reports/ph_d01b_downstream_invalidation.json"
)
PH_D01B_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D01B_TO_PH-D02A_20260731.json"
)
PH_D01B_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D01B_TO_PH-D02A_20260731.json"
)
PH_D01B_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D01B_EVIDENCE_ATTESTATION.json"
)
PH_D01B_PHASE_STATE_PATH = Path("control/rev3/D01B_PHASE_STATE.json")
PH_D02A_FRAME_PATH = Path("control/rev3/PH-D02A_WORK_BLOCK_FRAME.json")
PH_D02A_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D01B_TO_PH-D02A.json"
)
PH_D02A_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d02a_canonical_preinventory.json"
)
PH_D02A_CONTRACT_PATH = Path(
    "distillation/input/canonicalization_contract.json"
)
PH_D02A_VECTOR_MANIFEST_PATH = Path(
    "distillation/artifacts/test_vectors/canonical_test_vectors.json"
)
PH_D02A_CONFORMANCE_PATH = Path(
    "distillation/artifacts/reports/canonicalization_conformance.json"
)
PH_D02A_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D02A_TO_PH-D02B_20260731.json"
)
PH_D02A_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D02A_TO_PH-D02B_20260731.json"
)
PH_D02A_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D02A_EVIDENCE_ATTESTATION.json"
)
PH_D02A_PHASE_STATE_PATH = Path("control/rev3/D02A_PHASE_STATE.json")
PH_D02B_FRAME_PATH = Path("control/rev3/PH-D02B_WORK_BLOCK_FRAME.json")
PH_D02B_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D02A_TO_PH-D02B.json"
)
PH_D02B_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d02b_schema_bundle_preinventory.json"
)
PH_D02B_DOCUMENT_CONTRACT_PATH = Path(
    "docs/strategy/contracts/HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json"
)
PH_D02B_CONTRACT_PATH = Path(
    "distillation/input/post_audit_schema_bundle_contract.json"
)
PH_D02B_SNAPSHOT_MANIFEST_PATH = Path(
    "distillation/input/historical_pre_audit/PH-D02B/"
    "SNAPSHOT_MANIFEST.json"
)
PH_D02B_EXAMPLES_PATH = Path(
    "distillation/artifacts/test_vectors/"
    "post_audit_schema_bundle_examples.json"
)
PH_D02B_INVALID_CASES_PATH = Path(
    "distillation/artifacts/test_vectors/"
    "post_audit_schema_bundle_invalid_cases.json"
)
PH_D02B_CONFORMANCE_PATH = Path(
    "distillation/artifacts/reports/"
    "post_audit_schema_bundle_conformance.json"
)
PH_D02B_SCHEMA_ROOT = Path("distillation/schema_sets/ph_d02b_v1")
PH_D02B_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D02B_TO_PH-D02C_20260731.json"
)
PH_D02B_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D02B_TO_PH-D02C_20260731.json"
)
PH_D02B_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D02B_EVIDENCE_ATTESTATION.json"
)
PH_D02B_PHASE_STATE_PATH = Path("control/rev3/D02B_PHASE_STATE.json")
PH_D02C_FRAME_PATH = Path("control/rev3/PH-D02C_WORK_BLOCK_FRAME.json")
PH_D02C_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D02B_TO_PH-D02C.json"
)
PH_D02C_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d02c_post_audit_ir_preinventory.json"
)
PH_D02C_DOCUMENT_CONTRACT_PATH = Path(
    "docs/strategy/contracts/POST_AUDIT_CAUSAL_IR_CONTRACT_V1.json"
)
PH_D02C_SCHEMA_CONTRACT_PATH = Path(
    "distillation/input/post_audit_causal_ir_schema_contract.json"
)
PH_D02C_CAUSAL_IR_CONTRACT_PATH = Path(
    "distillation/input/causal_ir_contract.json"
)
PH_D02C_SNAPSHOT_MANIFEST_PATH = Path(
    "distillation/input/historical_pre_audit/PH-D02C/"
    "SNAPSHOT_MANIFEST.json"
)
PH_D02C_VALID_VECTORS_PATH = Path(
    "distillation/artifacts/test_vectors/causal_ir/"
    "valid_ir_vectors.json"
)
PH_D02C_INVALID_VECTORS_PATH = Path(
    "distillation/artifacts/test_vectors/causal_ir/"
    "invalid_ir_vectors.json"
)
PH_D02C_CONFORMANCE_PATH = Path(
    "distillation/artifacts/reports/causal_ir_conformance.json"
)
PH_D02C_SCHEMA_ROOT = Path("distillation/schema_sets/ph_d02c_v1")
PH_D02C_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D02C_TO_PH-D03A_20260731.json"
)
PH_D02C_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D02C_TO_PH-D03A_20260731.json"
)
PH_D02C_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D02C_EVIDENCE_ATTESTATION.json"
)
PH_D02C_PHASE_STATE_PATH = Path("control/rev3/D02C_PHASE_STATE.json")
PH_D03A_FRAME_PATH = Path("control/rev3/PH-D03A_WORK_BLOCK_FRAME.json")
PH_D03A_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D02C_TO_PH-D03A.json"
)
PH_D03A_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d03a_post_audit_golden_preinventory.json"
)
PH_D03A_SNAPSHOT_MANIFEST_PATH = Path(
    "distillation/input/historical_pre_audit/PH-D03A/"
    "SNAPSHOT_MANIFEST.json"
)
PH_D03A_CONTRACT_PATH = Path(
    "distillation/input/golden_conformance_contract.json"
)
PH_D03A_CANDIDATE_SET_PATH = Path(
    "distillation/artifacts/golden/candidate_cases.json"
)
PH_D03A_COVERAGE_PATH = Path(
    "distillation/artifacts/reports/golden_gate_coverage.json"
)
PH_D03A_REVIEW_REQUEST_PATH = Path(
    "distillation/artifacts/golden/owner_review_request.json"
)
PH_D03A_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D03A_TO_PH-D03B_20260731.json"
)
PH_D03A_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D03A_TO_PH-D03B_20260731.json"
)
PH_D03A_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D03A_EVIDENCE_ATTESTATION.json"
)
PH_D03A_PHASE_STATE_PATH = Path("control/rev3/D03A_CANDIDATE_STATE.json")
PH_D03A_TARGET_BUNDLE_PATH = Path(
    "control/rev3/PH-D03A_OWNER_REVIEW_PACKAGE/"
    "exact_target_bundle.json"
)
PH_D03B_FRAME_PATH = Path("control/rev3/PH-D03B_WORK_BLOCK_FRAME.json")
PH_D03B_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D03A_TO_PH-D03B.json"
)
PH_D03B_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d03b_sealed_audit_preinventory.json"
)
PH_D03B_CONTRACT_PATH = Path(
    "distillation/input/sealed_audit_contract.json"
)
PH_D03B_COMMITMENTS_PATH = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/"
    "expected_commitments.json"
)
PH_D03B_MANIFEST_PATH = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/manifest.json"
)
PH_D03B_RUNNER_CONTRACT_PATH = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/"
    "runner_contract.json"
)
PH_D03B_FREEZE_REPORT_PATH = Path(
    "distillation/artifacts/reports/sealed_audit_freeze.json"
)
PH_D03B_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D03B_TO_PH-D05_20260731.json"
)
PH_D03B_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D03B_TO_PH-D05_20260731.json"
)
PH_D03B_EVIDENCE_ATTESTATION_PATH = Path(
    "control/rev3/PH-D03B_EVIDENCE_ATTESTATION.json"
)
PH_D03B_PHASE_STATE_PATH = Path("control/rev3/D03B_PHASE_STATE.json")
PH_D05_FRAME_PATH = Path("control/rev3/PH-D05_WORK_BLOCK_FRAME.json")
PH_D05_TRANSITION_PATH = Path(
    "control/rev3/PHASE_TRANSITIONS/PH-D03B_TO_PH-D05.json"
)
PH_D05_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d05_teacher_trajectory_preinventory.json"
)
PH_D05_CONTRACT_PATH = Path(
    "distillation/input/arc3_teacher_trajectory_normalization_contract.json"
)
PH_D05_ACQUISITION_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_teacher_recording_acquisition.json"
)
PH_D05_REPLAY_X3_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_teacher_replay_x3.json"
)
PH_D05_NORMALIZATION_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_teacher_trajectory_normalization.json"
)
PH_D05_ARTIFACT_ROOT = Path(
    "distillation/artifacts/teacher/arc3/ph_d05_v1"
)
PH_D05_MANIFEST_PATH = PH_D05_ARTIFACT_ROOT / "manifest.json"
PH_D05_REBUILD_X3_PATH = PH_D05_ARTIFACT_ROOT / "rebuild_x3.json"
PH_D05_RESULT_DECISION_PATH = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/PH-D05_TO_PH-D06_20260801.json"
)
PH_D05_RESULT_APPROVAL_PATH = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/PH-D05_TO_PH-D06_20260801.json"
)
PH_D05_EVIDENCE_ATTESTATION_PATH = Path("control/rev3/PH-D05_EVIDENCE_ATTESTATION.json")
PH_D05_PHASE_STATE_PATH = Path("control/rev3/D05_PHASE_STATE.json")
PH_D06_FRAME_PATH = Path("control/rev3/PH-D06_WORK_BLOCK_FRAME.json")
PH_D06_TRANSITION_PATH = Path("control/rev3/PHASE_TRANSITIONS/PH-D05_TO_PH-D06.json")
PH_D06_PREINVENTORY_PATH = Path(
    "analysis/rev3/ph_d06_hypothesis_candidate_preinventory.json"
)
PH_D06_CONTRACT_PATH = Path(
    "distillation/input/arc3_hypothesis_candidate_generation_contract.json"
)
PH_D06_ARTIFACT_ROOT = Path("distillation/artifacts/candidates/arc3/ph_d06_v1")
PH_D06_MANIFEST_PATH = PH_D06_ARTIFACT_ROOT / "manifest.json"
PH_D06_REBUILD_X3_PATH = PH_D06_ARTIFACT_ROOT / "rebuild_x3.json"
PH_D06_GENERATION_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_hypothesis_candidate_generation.json"
)
PH_D06_SOURCE_BLIND_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_hypothesis_source_blind_execution.json"
)
PH_D06_LLM_CAPTURE_REPORT_PATH = Path(
    "distillation/artifacts/reports/arc3_hypothesis_llm_capture.json"
)
PH_R00_PHASE_STATE_PATH = Path("control/rev3/R00_PHASE_STATE.json")
PH_R00_ASSET_CLASSIFICATION_PATH = Path(
    "docs/strategy/ASSET_CLASSIFICATION_REV3.json"
)
PH_R00_BASELINE_PATH = Path(
    "analysis/rev3/pre_distillation_infrastructure_baseline.json"
)
CORRECTION_PACKAGE_PATH = Path(
    "artifacts/rev3/"
    "arc3_hds_distillation_first_strategy_rev3_corrected.zip"
)
CORRECTION_PACKAGE_SHA256 = (
    "f136e975c7b065db6ca550ff76b182ab50f15ccf6cc029b259852ed0b997489c"
)


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_object(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nfc_json(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc_json(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("object key must be a string")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                raise ValueError("NFC key collision")
            normalized[key] = _nfc_json(raw_value)
        return normalized
    return value


def _strict_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _canonical_document_failures(
    root: Path,
    relative_path: Path,
    location: str,
) -> list[str]:
    payload = (root / relative_path).read_bytes()
    try:
        decoded = payload.decode("utf-8", errors="strict")
        parsed = json.loads(
            decoded,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("non-finite JSON token: " + value)
            ),
        )
        rebuilt = (
            canonical_json(_nfc_json(parsed)).encode("utf-8") + b"\n"
        )
    except (UnicodeDecodeError, TypeError, ValueError):
        return [f"{location}:CANONICAL_DOCUMENT_INVALID"]
    if payload != rebuilt:
        return [f"{location}:CANONICAL_DOCUMENT_BYTES_MISMATCH"]
    return []


def _domain_content_digest_failures(
    value: Mapping[str, Any],
    namespace: str,
    field: str,
    location: str,
) -> list[str]:
    excluded = value.get("digest_excluded_fields")
    if not isinstance(excluded, list):
        return [f"{location}:DIGEST_EXCLUSIONS_MISSING"]
    body = dict(value)
    for item in excluded:
        if not isinstance(item, str) or item not in body:
            return [f"{location}:DIGEST_EXCLUSION_INVALID"]
        body.pop(item)
    try:
        payload = canonical_json(_nfc_json(body)).encode("utf-8")
        expected = namespace + ":" + hashlib.sha256(
            b"HDS-LOGICAL-CONTENT-V1\0"
            + namespace.encode("ascii")
            + b"\0"
            + payload
        ).hexdigest()
    except (TypeError, UnicodeEncodeError, ValueError):
        return [f"{location}:CONTENT_DIGEST_INPUT_INVALID"]
    if value.get(field) != expected:
        return [f"{location}:CONTENT_DIGEST_MISMATCH"]
    return []


def _load_object(root: Path, relative_path: Path) -> dict[str, Any]:
    value = json.loads(
        (root / relative_path).read_text(encoding="utf-8")
    )
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {relative_path}")
    return value


def _contains_json_key(value: object, forbidden: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in forbidden or _contains_json_key(child, forbidden)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_json_key(child, forbidden) for child in value)
    return False


def _matches_type(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, int | float)
            and not isinstance(value, bool)
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _schema_failures(
    value: object,
    schema: Mapping[str, Any],
    location: str = "$",
) -> list[str]:
    failures: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        accepted = _matches_type(value, expected_type)
    elif isinstance(expected_type, list):
        accepted = all(isinstance(item, str) for item in expected_type) and (
            any(_matches_type(value, item) for item in expected_type)
        )
    else:
        accepted = True
    if not accepted:
        return [f"{location}:TYPE_MISMATCH"]

    if "const" in schema and value != schema["const"]:
        failures.append(f"{location}:CONST_MISMATCH")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        failures.append(f"{location}:ENUM_MISMATCH")

    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            failures.append(f"{location}:MIN_LENGTH")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            failures.append(f"{location}:PATTERN_MISMATCH")

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if (
            isinstance(minimum_items, int)
            and len(value) < minimum_items
        ):
            failures.append(f"{location}:MIN_ITEMS")
        if schema.get("uniqueItems") is True:
            encoded = [canonical_json(item) for item in value]
            if len(encoded) != len(set(encoded)):
                failures.append(f"{location}:DUPLICATE_ITEMS")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                failures.extend(
                    _schema_failures(
                        item,
                        item_schema,
                        f"{location}[{index}]",
                    )
                )

    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    failures.append(f"{location}.{key}:MISSING")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            failures.extend(
                f"{location}.{key}:ADDITIONAL_PROPERTY"
                for key in extras
            )
        for key, item in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, dict):
                failures.extend(
                    _schema_failures(
                        item,
                        child_schema,
                        f"{location}.{key}",
                    )
                )
    return failures


def _content_digest_failures(
    value: Mapping[str, Any],
    prefix: str,
    field: str,
    location: str,
) -> list[str]:
    excluded = value.get("digest_excluded_fields")
    if not isinstance(excluded, list):
        return [f"{location}:DIGEST_EXCLUSIONS_MISSING"]
    body = dict(value)
    for item in excluded:
        if not isinstance(item, str) or item not in body:
            return [f"{location}:DIGEST_EXCLUSION_INVALID"]
        body.pop(item)
    expected = prefix + digest_object(body)
    if value.get(field) != expected:
        return [f"{location}:CONTENT_DIGEST_MISMATCH"]
    return []


def _git_object_exists(root: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", commit + "^{commit}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _git_tree(root: Path, commit: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", commit + "^{tree}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_blob(
    root: Path,
    commit: str,
    relative_path: str,
) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def validate_repository(root: Path) -> dict[str, object]:
    failures: list[str] = []
    selector = _load_object(root, SELECTOR_PATH)
    selector_schema = _load_object(root, SELECTOR_SCHEMA_PATH)
    failures.extend(
        _schema_failures(selector, selector_schema, "selector")
    )

    decision = _load_object(root, DECISION_PATH)
    decision_schema = _load_object(root, DECISION_SCHEMA_PATH)
    failures.extend(
        _schema_failures(decision, decision_schema, "decision")
    )
    failures.extend(
        _content_digest_failures(
            decision,
            "sha256:",
            "owner_decision_content_digest",
            "decision",
        )
    )

    approval = _load_object(root, APPROVAL_PATH)
    approval_schema = _load_object(root, APPROVAL_SCHEMA_PATH)
    failures.extend(
        _schema_failures(approval, approval_schema, "approval")
    )
    failures.extend(
        _content_digest_failures(
            approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "approval",
        )
    )
    if (
        approval.get("owner_decision_capture_digest")
        != decision.get("owner_decision_content_digest")
    ):
        failures.append("approval:DECISION_DIGEST_MISMATCH")

    attestation = _load_object(root, CORRECTION_ATTESTATION_PATH)
    target_commit = decision.get("target_evidence_commit")
    target_digest = decision.get("target_artifact_digest")
    if not isinstance(target_commit, str) or not _git_object_exists(
        root, target_commit
    ):
        failures.append("decision:TARGET_EVIDENCE_COMMIT_MISSING")
    if attestation.get("evidence", {}).get("commit") != target_commit:
        failures.append("decision:ATTESTATION_COMMIT_MISMATCH")
    if attestation.get("evidence", {}).get(
        "payload_digest"
    ) != target_digest:
        failures.append("decision:ATTESTATION_PAYLOAD_MISMATCH")

    frame = _load_object(root, FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            frame,
            "rev3-work-block-frame:",
            "content_digest",
            "frame",
        )
    )

    manifest = _load_object(root, AUTHORITY_MANIFEST_PATH)
    failures.extend(
        _content_digest_failures(
            manifest,
            "rev3-current-authority-manifest:",
            "content_digest",
            "authority_manifest",
        )
    )
    if (
        manifest.get("schema_version") != "arc3-rev3-current-authority-manifest-v13"
        or manifest.get("active_phase") != selector.get("active_phase")
        or manifest.get("current_work_class") != selector.get("current_work_class")
        or manifest.get("ph_d02c_status") != selector.get("ph_d02c_status")
        or manifest.get("ph_d03a_status") != selector.get("ph_d03a_status")
        or manifest.get("ph_d03b_status") != selector.get("ph_d03b_status")
        or manifest.get("ph_d05_status") != selector.get("ph_d05_status")
        or manifest.get("ph_d06_status") != selector.get("ph_d06_status")
        or manifest.get("source_binding")
        != {
            "commit": "e97f725dafca65c50963c367df58e875e81cb999",
            "tree": "7eb4cbd84edbc17e2bcebdfc1baac176721aa1eb",
        }
        or manifest.get("phase_entry_approval")
        != {
            "approval_artifact_digest": (
                "owner-approval-record:"
                "a2dae0790796b2b9169f8c88e91f704f59226ef8b98ff3342296c09a448a5376"
            ),
            "decision_capture_digest": (
                "sha256:"
                "fa327550ff6c9c0aa81c24589bfa16334ac4d591db6223c48af8ba2f8c5f098b"
            ),
            "from_phase": "PH-D05",
            "target_artifact_digest": (
                "sha256:"
                "eb17f67a8a637528a77f0d4fab5a85e6742d7d707adad8e6a66562fc78540a85"
            ),
            "target_evidence_commit": ("ab634857aafb952c09917791b6b10d6be8f1efd7"),
            "to_phase": "PH-D06",
        }
        or manifest.get("current_work_block")
        != {
            "content_digest": (
                "rev3-work-block-frame:"
                "a0fb8f813a90b6a775c12d8778cc5a6d0d60939c18c61359ccb1641f755fe4e1"
            ),
            "entry_transition_digest": (
                "rev3-phase-transition:"
                "916b7d737e5814c13ad8e11866eacefe0a98cba5583f956fca2878658f956edd"
            ),
            "path": "control/rev3/PH-D06_WORK_BLOCK_FRAME.json",
        }
    ):
        failures.append("authority_manifest:CURRENT_SELECTOR_MISMATCH")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        failures.append("authority_manifest:ENTRIES_MISSING")
    else:
        if manifest.get("entry_count") != len(entries):
            failures.append("authority_manifest:ENTRY_COUNT_MISMATCH")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                failures.append(
                    f"authority_manifest.entries[{index}]:TYPE_MISMATCH"
                )
                continue
            path = entry.get("path")
            expected_sha = entry.get("sha256")
            if not isinstance(path, str) or not isinstance(
                expected_sha, str
            ):
                failures.append(
                    f"authority_manifest.entries[{index}]:INVALID"
                )
                continue
            artifact = root / path
            if not artifact.is_file():
                failures.append(
                    f"authority_manifest.entries[{index}]:MISSING"
                )
                continue
            actual_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                failures.append(
                    f"authority_manifest.entries[{index}]:SHA256_MISMATCH"
                )

    standing = _load_object(root, STANDING_AUTHORIZATION_PATH)
    standing_schema = _load_object(
        root, STANDING_AUTHORIZATION_SCHEMA_PATH
    )
    failures.extend(
        _schema_failures(standing, standing_schema, "standing")
    )
    failures.extend(
        _content_digest_failures(
            standing,
            "sha256:",
            "standing_authorization_content_digest",
            "standing",
        )
    )

    entry_decision = _load_object(root, PH_R00_ENTRY_DECISION_PATH)
    decision_v2_schema = _load_object(root, DECISION_V2_SCHEMA_PATH)
    failures.extend(
        _schema_failures(
            entry_decision,
            decision_v2_schema,
            "ph_r00_entry_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            entry_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_r00_entry_decision",
        )
    )
    if (
        entry_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_r00_entry_decision:STANDING_AUTHORIZATION_MISMATCH"
        )

    entry_approval = _load_object(root, PH_R00_ENTRY_APPROVAL_PATH)
    failures.extend(
        _schema_failures(
            entry_approval,
            approval_schema,
            "ph_r00_entry_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            entry_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_r00_entry_approval",
        )
    )
    if (
        entry_approval.get("owner_decision_capture_digest")
        != entry_decision.get("owner_decision_content_digest")
    ):
        failures.append(
            "ph_r00_entry_approval:DECISION_DIGEST_MISMATCH"
        )

    ph_r00_attestation = _load_object(
        root, PH_R00_EVIDENCE_ATTESTATION_PATH
    )
    attestation_schema = _load_object(
        root,
        Path(
            "docs/strategy/contracts/"
            "EVIDENCE_COMMIT_ATTESTATION_SCHEMA_V1.json"
        ),
    )
    failures.extend(
        _schema_failures(
            ph_r00_attestation,
            attestation_schema,
            "ph_r00_evidence_attestation",
        )
    )
    if ph_r00_attestation.get("phase_id") != "PH-R00":
        failures.append("ph_r00_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_r00_attestation.get(commit_field)
        expected_tree = ph_r00_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_r00_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )

    ph_d00a_entry_decision = _load_object(
        root, PH_D00A_ENTRY_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00a_entry_decision,
            decision_v2_schema,
            "ph_d00a_entry_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00a_entry_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d00a_entry_decision",
        )
    )
    if (
        ph_d00a_entry_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_d00a_entry_decision:STANDING_AUTHORIZATION_MISMATCH"
        )
    if (
        ph_d00a_entry_decision.get("target_evidence_commit")
        != ph_r00_attestation.get("evidence_commit")
        or ph_d00a_entry_decision.get("target_artifact_digest")
        != ph_r00_attestation.get("evidence_payload_digest")
    ):
        failures.append(
            "ph_d00a_entry_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d00a_entry_approval = _load_object(
        root, PH_D00A_ENTRY_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00a_entry_approval,
            approval_schema,
            "ph_d00a_entry_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00a_entry_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d00a_entry_approval",
        )
    )
    if (
        ph_d00a_entry_approval.get("owner_decision_capture_digest")
        != ph_d00a_entry_decision.get(
            "owner_decision_content_digest"
        )
    ):
        failures.append(
            "ph_d00a_entry_approval:DECISION_DIGEST_MISMATCH"
        )

    ph_d00a_attestation = _load_object(
        root, PH_D00A_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00a_attestation,
            attestation_schema,
            "ph_d00a_evidence_attestation",
        )
    )
    if ph_d00a_attestation.get("phase_id") != "PH-D00A":
        failures.append("ph_d00a_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d00a_attestation.get(commit_field)
        expected_tree = ph_d00a_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d00a_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d00a_phase_state = root / PH_D00A_PHASE_STATE_PATH
    if hashlib.sha256(ph_d00a_phase_state.read_bytes()).hexdigest() != (
        ph_d00a_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d00a_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )

    ph_d00a_result_decision = _load_object(
        root, PH_D00A_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00a_result_decision,
            decision_v2_schema,
            "ph_d00a_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00a_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d00a_result_decision",
        )
    )
    if (
        ph_d00a_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_d00a_result_decision:STANDING_AUTHORIZATION_MISMATCH"
        )
    if (
        ph_d00a_result_decision.get("target_evidence_commit")
        != ph_d00a_attestation.get("evidence_commit")
        or ph_d00a_result_decision.get("target_artifact_digest")
        != ph_d00a_attestation.get("evidence_payload_digest")
    ):
        failures.append(
            "ph_d00a_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d00a_result_approval = _load_object(
        root, PH_D00A_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00a_result_approval,
            approval_schema,
            "ph_d00a_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00a_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d00a_result_approval",
        )
    )
    if (
        ph_d00a_result_approval.get("owner_decision_capture_digest")
        != ph_d00a_result_decision.get(
            "owner_decision_content_digest"
        )
    ):
        failures.append(
            "ph_d00a_result_approval:DECISION_DIGEST_MISMATCH"
        )

    ph_d00b_attestation = _load_object(
        root, PH_D00B_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00b_attestation,
            attestation_schema,
            "ph_d00b_evidence_attestation",
        )
    )
    if ph_d00b_attestation.get("phase_id") != "PH-D00B":
        failures.append("ph_d00b_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d00b_attestation.get(commit_field)
        expected_tree = ph_d00b_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d00b_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d00b_phase_state = root / PH_D00B_PHASE_STATE_PATH
    if hashlib.sha256(ph_d00b_phase_state.read_bytes()).hexdigest() != (
        ph_d00b_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d00b_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )

    ph_d00b_result_decision = _load_object(
        root, PH_D00B_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00b_result_decision,
            decision_v2_schema,
            "ph_d00b_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00b_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d00b_result_decision",
        )
    )
    if (
        ph_d00b_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_d00b_result_decision:STANDING_AUTHORIZATION_MISMATCH"
        )
    if (
        ph_d00b_result_decision.get("target_evidence_commit")
        != ph_d00b_attestation.get("evidence_commit")
        or ph_d00b_result_decision.get("target_artifact_digest")
        != ph_d00b_attestation.get("evidence_payload_digest")
    ):
        failures.append(
            "ph_d00b_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d00b_result_approval = _load_object(
        root, PH_D00B_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d00b_result_approval,
            approval_schema,
            "ph_d00b_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d00b_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d00b_result_approval",
        )
    )
    if (
        ph_d00b_result_approval.get("owner_decision_capture_digest")
        != ph_d00b_result_decision.get(
            "owner_decision_content_digest"
        )
    ):
        failures.append(
            "ph_d00b_result_approval:DECISION_DIGEST_MISMATCH"
        )

    ph_d01a_attestation = _load_object(
        root, PH_D01A_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01a_attestation,
            attestation_schema,
            "ph_d01a_evidence_attestation",
        )
    )
    if ph_d01a_attestation.get("phase_id") != "PH-D01A":
        failures.append("ph_d01a_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d01a_attestation.get(commit_field)
        expected_tree = ph_d01a_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d01a_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d01a_phase_state = root / PH_D01A_PHASE_STATE_PATH
    if hashlib.sha256(ph_d01a_phase_state.read_bytes()).hexdigest() != (
        ph_d01a_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d01a_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )

    ph_d01a_result_decision = _load_object(
        root, PH_D01A_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01a_result_decision,
            decision_v2_schema,
            "ph_d01a_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d01a_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d01a_result_decision",
        )
    )
    if (
        ph_d01a_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_d01a_result_decision:STANDING_AUTHORIZATION_MISMATCH"
        )
    if (
        ph_d01a_result_decision.get("target_evidence_commit")
        != ph_d01a_attestation.get("evidence_commit")
        or ph_d01a_result_decision.get("target_artifact_digest")
        != ph_d01a_attestation.get("evidence_payload_digest")
    ):
        failures.append(
            "ph_d01a_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d01a_result_approval = _load_object(
        root, PH_D01A_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01a_result_approval,
            approval_schema,
            "ph_d01a_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d01a_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d01a_result_approval",
        )
    )
    if (
        ph_d01a_result_approval.get("owner_decision_capture_digest")
        != ph_d01a_result_decision.get(
            "owner_decision_content_digest"
        )
    ):
        failures.append(
            "ph_d01a_result_approval:DECISION_DIGEST_MISMATCH"
        )

    ph_d01b_attestation = _load_object(
        root, PH_D01B_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01b_attestation,
            attestation_schema,
            "ph_d01b_evidence_attestation",
        )
    )
    if ph_d01b_attestation.get("phase_id") != "PH-D01B":
        failures.append("ph_d01b_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d01b_attestation.get(commit_field)
        expected_tree = ph_d01b_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d01b_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d01b_phase_state_path = root / PH_D01B_PHASE_STATE_PATH
    if (
        hashlib.sha256(ph_d01b_phase_state_path.read_bytes()).hexdigest()
        != ph_d01b_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d01b_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )
    ph_d01b_phase_state = _load_object(root, PH_D01B_PHASE_STATE_PATH)
    if (
        ph_d01b_phase_state.get("phase_id") != "PH-D01B"
        or ph_d01b_phase_state.get("status") != "CODEX_SELF_AUDIT_PASS"
        or ph_d01b_phase_state.get("failed_requirement_ids") != []
        or ph_d01b_phase_state.get("evidence_payload_digest")
        != ph_d01b_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d01b_phase_state:RESULT_BINDING_MISMATCH")

    ph_d01b_result_decision = _load_object(
        root, PH_D01B_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01b_result_decision,
            decision_v2_schema,
            "ph_d01b_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d01b_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d01b_result_decision",
        )
    )
    if (
        ph_d01b_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
    ):
        failures.append(
            "ph_d01b_result_decision:STANDING_AUTHORIZATION_MISMATCH"
        )
    if (
        ph_d01b_result_decision.get("target_evidence_commit")
        != ph_d01b_attestation.get("evidence_commit")
        or ph_d01b_result_decision.get("target_artifact_digest")
        != ph_d01b_attestation.get("evidence_payload_digest")
        or ph_d01b_result_decision.get("gate_status") != "PASS"
    ):
        failures.append(
            "ph_d01b_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d01b_result_approval = _load_object(
        root, PH_D01B_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d01b_result_approval,
            approval_schema,
            "ph_d01b_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d01b_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d01b_result_approval",
        )
    )
    if (
        ph_d01b_result_approval.get("owner_decision_capture_digest")
        != ph_d01b_result_decision.get("owner_decision_content_digest")
        or ph_d01b_result_approval.get("target_evidence_commit")
        != ph_d01b_attestation.get("evidence_commit")
        or ph_d01b_result_approval.get("target_artifact_digest")
        != ph_d01b_attestation.get("evidence_payload_digest")
        or ph_d01b_result_approval.get("next_phase_id") != "PH-D02A"
        or ph_d01b_result_approval.get("next_phase_authorized") is not True
    ):
        failures.append(
            "ph_d01b_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    ph_d02a_attestation = _load_object(
        root, PH_D02A_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02a_attestation,
            attestation_schema,
            "ph_d02a_evidence_attestation",
        )
    )
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d02a_attestation.get(commit_field)
        expected_tree = ph_d02a_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d02a_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d02a_phase_state_path = root / PH_D02A_PHASE_STATE_PATH
    if (
        hashlib.sha256(ph_d02a_phase_state_path.read_bytes()).hexdigest()
        != ph_d02a_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d02a_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )
    ph_d02a_phase_state = _load_object(root, PH_D02A_PHASE_STATE_PATH)
    if (
        ph_d02a_phase_state.get("phase_id") != "PH-D02A"
        or ph_d02a_phase_state.get("status") != "CODEX_SELF_AUDIT_PASS"
        or ph_d02a_phase_state.get("failed_requirement_ids") != []
        or ph_d02a_phase_state.get("evidence_payload_digest")
        != ph_d02a_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02a_phase_state:RESULT_BINDING_MISMATCH")

    ph_d02a_result_decision = _load_object(
        root, PH_D02A_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02a_result_decision,
            decision_v2_schema,
            "ph_d02a_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02a_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d02a_result_decision",
        )
    )
    if (
        ph_d02a_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d02a_result_decision.get("target_evidence_commit")
        != ph_d02a_attestation.get("evidence_commit")
        or ph_d02a_result_decision.get("target_artifact_digest")
        != ph_d02a_attestation.get("evidence_payload_digest")
        or ph_d02a_result_decision.get("gate_status") != "PASS"
    ):
        failures.append(
            "ph_d02a_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d02a_result_approval = _load_object(
        root, PH_D02A_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02a_result_approval,
            approval_schema,
            "ph_d02a_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02a_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d02a_result_approval",
        )
    )
    if (
        ph_d02a_result_approval.get("owner_decision_capture_digest")
        != ph_d02a_result_decision.get("owner_decision_content_digest")
        or ph_d02a_result_approval.get("target_evidence_commit")
        != ph_d02a_attestation.get("evidence_commit")
        or ph_d02a_result_approval.get("target_artifact_digest")
        != ph_d02a_attestation.get("evidence_payload_digest")
        or ph_d02a_result_approval.get("next_phase_id") != "PH-D02B"
        or ph_d02a_result_approval.get("next_phase_authorized") is not True
    ):
        failures.append(
            "ph_d02a_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    ph_d02b_attestation = _load_object(
        root, PH_D02B_EVIDENCE_ATTESTATION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02b_attestation,
            attestation_schema,
            "ph_d02b_evidence_attestation",
        )
    )
    if ph_d02b_attestation.get("phase_id") != "PH-D02B":
        failures.append("ph_d02b_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d02b_attestation.get(commit_field)
        expected_tree = ph_d02b_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d02b_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d02b_phase_state_path = root / PH_D02B_PHASE_STATE_PATH
    if (
        hashlib.sha256(ph_d02b_phase_state_path.read_bytes()).hexdigest()
        != ph_d02b_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d02b_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )
    ph_d02b_phase_state = _load_object(root, PH_D02B_PHASE_STATE_PATH)
    if (
        ph_d02b_phase_state.get("phase_id") != "PH-D02B"
        or ph_d02b_phase_state.get("status") != "CODEX_SELF_AUDIT_PASS"
        or ph_d02b_phase_state.get("failed_requirement_ids") != []
        or ph_d02b_phase_state.get("evidence_payload_digest")
        != ph_d02b_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02b_phase_state:RESULT_BINDING_MISMATCH")

    ph_d02b_result_decision = _load_object(
        root, PH_D02B_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02b_result_decision,
            decision_v2_schema,
            "ph_d02b_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02b_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d02b_result_decision",
        )
    )
    if (
        ph_d02b_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d02b_result_decision.get("target_evidence_commit")
        != ph_d02b_attestation.get("evidence_commit")
        or ph_d02b_result_decision.get("target_artifact_digest")
        != ph_d02b_attestation.get("evidence_payload_digest")
        or ph_d02b_result_decision.get("gate_status") != "PASS"
    ):
        failures.append(
            "ph_d02b_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d02b_result_approval = _load_object(
        root, PH_D02B_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02b_result_approval,
            approval_schema,
            "ph_d02b_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02b_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d02b_result_approval",
        )
    )
    if (
        ph_d02b_result_approval.get("owner_decision_capture_digest")
        != ph_d02b_result_decision.get("owner_decision_content_digest")
        or ph_d02b_result_approval.get("target_evidence_commit")
        != ph_d02b_attestation.get("evidence_commit")
        or ph_d02b_result_approval.get("target_artifact_digest")
        != ph_d02b_attestation.get("evidence_payload_digest")
        or ph_d02b_result_approval.get("next_phase_id") != "PH-D02C"
        or ph_d02b_result_approval.get("next_phase_authorized") is not True
    ):
        failures.append(
            "ph_d02b_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    ph_d02c_attestation = _load_object(
        root, PH_D02C_EVIDENCE_ATTESTATION_PATH
    )
    if (
        ph_d02c_attestation.get("phase_id") != "PH-D02C"
        or ph_d02c_attestation.get("self_reference_avoided") is not True
        or ph_d02c_attestation.get("owner_approval") != "NOT_ESTABLISHED"
    ):
        failures.append("ph_d02c_evidence_attestation:BOUNDARY_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d02c_attestation.get(commit_field)
        expected_tree = ph_d02c_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (
            expected_tree
        ):
            failures.append(
                "ph_d02c_evidence_attestation:"
                + commit_field.upper()
                + "_TREE_MISMATCH"
            )
    ph_d02c_phase_state_path = root / PH_D02C_PHASE_STATE_PATH
    if (
        hashlib.sha256(ph_d02c_phase_state_path.read_bytes()).hexdigest()
        != ph_d02c_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_d02c_evidence_attestation:"
            "PHASE_STATE_SHA256_MISMATCH"
        )
    ph_d02c_phase_state = _load_object(root, PH_D02C_PHASE_STATE_PATH)
    if (
        ph_d02c_phase_state.get("phase_id") != "PH-D02C"
        or ph_d02c_phase_state.get("status") != "CODEX_SELF_AUDIT_PASS"
        or ph_d02c_phase_state.get("failed_requirement_ids") != []
        or ph_d02c_phase_state.get("evidence_payload_digest")
        != ph_d02c_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02c_phase_state:RESULT_BINDING_MISMATCH")

    ph_d02c_result_decision = _load_object(
        root, PH_D02C_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02c_result_decision,
            decision_v2_schema,
            "ph_d02c_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02c_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d02c_result_decision",
        )
    )
    if (
        ph_d02c_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d02c_result_decision.get("target_evidence_commit")
        != ph_d02c_attestation.get("evidence_commit")
        or ph_d02c_result_decision.get("target_artifact_digest")
        != ph_d02c_attestation.get("evidence_payload_digest")
        or ph_d02c_result_decision.get("gate_status") != "PASS"
    ):
        failures.append(
            "ph_d02c_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d02c_result_approval = _load_object(
        root, PH_D02C_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d02c_result_approval,
            approval_schema,
            "ph_d02c_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d02c_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d02c_result_approval",
        )
    )
    if (
        ph_d02c_result_approval.get("owner_decision_capture_digest")
        != ph_d02c_result_decision.get("owner_decision_content_digest")
        or ph_d02c_result_approval.get("target_evidence_commit")
        != ph_d02c_attestation.get("evidence_commit")
        or ph_d02c_result_approval.get("target_artifact_digest")
        != ph_d02c_attestation.get("evidence_payload_digest")
        or ph_d02c_result_approval.get("next_phase_id") != "PH-D03A"
        or ph_d02c_result_approval.get("next_phase_authorized")
        is not True
    ):
        failures.append(
            "ph_d02c_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    ph_d03a_attestation = _load_object(
        root, PH_D03A_EVIDENCE_ATTESTATION_PATH
    )
    attestation_properties = attestation_schema.get("properties")
    ph_d03a_attestation_core = (
        {
            key: value
            for key, value in ph_d03a_attestation.items()
            if key in attestation_properties
        }
        if isinstance(attestation_properties, dict)
        else {}
    )
    failures.extend(
        _schema_failures(
            ph_d03a_attestation_core,
            attestation_schema,
            "ph_d03a_attestation",
        )
    )
    ph_d03a_phase_state = _load_object(root, PH_D03A_PHASE_STATE_PATH)
    ph_d03a_target_bundle = _load_object(
        root, PH_D03A_TARGET_BUNDLE_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d03a_target_bundle,
            "ph-d03a-exact-target-bundle:",
            "content_digest",
            "ph_d03a_target_bundle",
        )
    )
    if (
        ph_d03a_attestation.get("phase_id") != "PH-D03A"
        or ph_d03a_attestation.get("implementation_commit")
        != ph_d03a_phase_state.get("implementation_commit")
        or ph_d03a_attestation.get("implementation_tree")
        != ph_d03a_phase_state.get("implementation_tree")
        or ph_d03a_attestation.get("evidence_payload_digest")
        != ph_d03a_phase_state.get("evidence_payload_digest")
        or ph_d03a_attestation.get("phase_state_sha256")
        != hashlib.sha256(
            (root / PH_D03A_PHASE_STATE_PATH).read_bytes()
        ).hexdigest()
        or ph_d03a_attestation.get("exact_target_bundle_digest")
        != ph_d03a_target_bundle.get("content_digest")
        or ph_d03a_attestation.get("exact_target_count") != 16
        or ph_d03a_target_bundle.get("target_count") != 16
        or not _git_object_exists(
            root,
            str(ph_d03a_attestation.get("implementation_commit")),
        )
        or not _git_object_exists(
            root,
            str(ph_d03a_attestation.get("evidence_commit")),
        )
    ):
        failures.append("ph_d03a_attestation:TARGET_BINDING_MISMATCH")

    ph_d03a_result_decision = _load_object(
        root, PH_D03A_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d03a_result_decision,
            decision_v2_schema,
            "ph_d03a_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d03a_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d03a_result_decision",
        )
    )
    if (
        ph_d03a_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d03a_result_decision.get("target_evidence_commit")
        != ph_d03a_attestation.get("evidence_commit")
        or ph_d03a_result_decision.get("target_artifact_digest")
        != ph_d03a_attestation.get("evidence_payload_digest")
        or ph_d03a_result_decision.get("gate_result_digest")
        != ph_d03a_target_bundle.get("content_digest")
        or ph_d03a_result_decision.get("gate_status") != "PASS"
        or ph_d03a_result_decision.get("allowed_transition")
        != "PH-D03A_TO_PH-D03B"
        or ph_d03a_result_decision.get("decision")
        != (
            "APPROVE_ALL_SIXTEEN_PROVISIONAL_EXPECTATIONS_"
            "AND_AUTHORIZE_NEXT_PHASE_ENTRY"
        )
    ):
        failures.append(
            "ph_d03a_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d03a_result_approval = _load_object(
        root, PH_D03A_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d03a_result_approval,
            approval_schema,
            "ph_d03a_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d03a_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d03a_result_approval",
        )
    )
    if (
        ph_d03a_result_approval.get("owner_decision_capture_digest")
        != ph_d03a_result_decision.get("owner_decision_content_digest")
        or ph_d03a_result_approval.get("target_evidence_commit")
        != ph_d03a_attestation.get("evidence_commit")
        or ph_d03a_result_approval.get("target_artifact_digest")
        != ph_d03a_attestation.get("evidence_payload_digest")
        or ph_d03a_result_approval.get("approved_transition")
        != "PH-D03A_TO_PH-D03B"
        or ph_d03a_result_approval.get("next_phase_id") != "PH-D03B"
        or ph_d03a_result_approval.get("next_phase_authorized")
        is not True
    ):
        failures.append(
            "ph_d03a_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    if selector.get("active_phase") != "PH-D06":
        failures.append("selector:ACTIVE_PHASE_MISMATCH")
    if selector.get("ph_r00_owner_authorization") != "ESTABLISHED":
        failures.append("selector:PH_R00_AUTHORIZATION_MISSING")
    if selector.get("ph_r00_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_R00_STATUS_MISMATCH")
    if selector.get("ph_d00a_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D00A_STATUS_MISMATCH")
    if selector.get("ph_d00b_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D00B_STATUS_MISMATCH")
    if selector.get("ph_d01a_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D01A_STATUS_MISMATCH")
    if selector.get("ph_d01b_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D01B_STATUS_MISMATCH")
    if selector.get("ph_d02a_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D02A_STATUS_MISMATCH")
    if selector.get("ph_d02b_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D02B_STATUS_MISMATCH")
    if selector.get("ph_d02c_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D02C_STATUS_MISMATCH")
    if selector.get("ph_d03a_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D03A_STATUS_MISMATCH")
    if selector.get("ph_d03b_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D03B_STATUS_MISMATCH")
    if selector.get("ph_d05_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D05_STATUS_MISMATCH")
    if selector.get("ph_d06_status") != "IN_PROGRESS":
        failures.append("selector:PH_D06_STATUS_MISMATCH")
    if selector.get("runtime_activation_status") != "SUSPEND":
        failures.append("selector:RUNTIME_ACTIVATION_ESCALATED")
    selector_entry_approval = selector.get("phase_entry_approval")
    if not isinstance(selector_entry_approval, dict):
        failures.append("selector:PH_D06_ENTRY_APPROVAL_MISSING")
    elif selector_entry_approval.get("approval_artifact_digest") != (
        "owner-approval-record:"
        "a2dae0790796b2b9169f8c88e91f704f59226ef8b98ff3342296c09a448a5376"
    ):
        failures.append("selector:PH_D06_ENTRY_APPROVAL_MISMATCH")
    selector_standing = selector.get("standing_authorization")
    if not isinstance(selector_standing, dict):
        failures.append("selector:STANDING_AUTHORIZATION_MISSING")
    elif selector_standing.get("content_digest") != standing.get(
        "standing_authorization_content_digest"
    ):
        failures.append("selector:STANDING_AUTHORIZATION_MISMATCH")

    ph_r00_frame = _load_object(root, PH_R00_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_r00_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_r00_frame",
        )
    )
    if ph_r00_frame.get("phase_id") != "PH-R00":
        failures.append("ph_r00_frame:PHASE_MISMATCH")
    frame_budget = ph_r00_frame.get("resource_budget")
    if not isinstance(frame_budget, dict):
        failures.append("ph_r00_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field in (
            "network_submission_count",
            "locked_final_access_count",
            "official_access_count",
            "kaggle_mutation_count",
            "maximum_new_runtime_capabilities",
            "teacher_source_read_count",
        ):
            if frame_budget.get(field) != 0:
                failures.append(f"ph_r00_frame:{field}:NONZERO")

    transition = _load_object(root, PH_R00_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_r00_transition",
        )
    )
    if (
        transition.get("from_phase_id"),
        transition.get("to_phase_id"),
        transition.get("decision"),
    ) != ("PH-R-1", "PH-R00", "ENTRY_AUTHORIZED"):
        failures.append("ph_r00_transition:SEQUENCE_MISMATCH")
    if transition.get("authorization_digest") != entry_approval.get(
        "approval_artifact_digest"
    ):
        failures.append("ph_r00_transition:APPROVAL_MISMATCH")
    if transition.get("external_irreversible_action_authorized") is not False:
        failures.append("ph_r00_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d00a_frame = _load_object(root, PH_D00A_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d00a_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d00a_frame",
        )
    )
    if ph_d00a_frame.get("phase_id") != "PH-D00A":
        failures.append("ph_d00a_frame:PHASE_MISMATCH")
    ph_d00a_budget = ph_d00a_frame.get("resource_budget")
    if not isinstance(ph_d00a_budget, dict):
        failures.append("ph_d00a_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field in (
            "network_submission_count",
            "locked_final_access_count",
            "official_access_count",
            "kaggle_mutation_count",
            "maximum_new_runtime_capabilities",
            "arc_task_payload_read_count",
            "teacher_trajectory_read_count",
            "hds_hypothesis_generation_count",
            "rule_promotion_count",
        ):
            if ph_d00a_budget.get(field) != 0:
                failures.append(f"ph_d00a_frame:{field}:NONZERO")

    ph_d00a_transition = _load_object(root, PH_D00A_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d00a_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d00a_transition",
        )
    )
    if (
        ph_d00a_transition.get("from_phase_id"),
        ph_d00a_transition.get("to_phase_id"),
        ph_d00a_transition.get("decision"),
    ) != ("PH-R00", "PH-D00A", "ENTRY_AUTHORIZED"):
        failures.append("ph_d00a_transition:SEQUENCE_MISMATCH")
    if ph_d00a_transition.get(
        "authorization_digest"
    ) != ph_d00a_entry_approval.get("approval_artifact_digest"):
        failures.append("ph_d00a_transition:APPROVAL_MISMATCH")
    if (
        ph_d00a_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d00a_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d00b_frame = _load_object(root, PH_D00B_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d00b_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d00b_frame",
        )
    )
    if ph_d00b_frame.get("phase_id") != "PH-D00B":
        failures.append("ph_d00b_frame:PHASE_MISMATCH")
    ph_d00b_budget = ph_d00b_frame.get("resource_budget")
    if not isinstance(ph_d00b_budget, dict):
        failures.append("ph_d00b_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field in (
            "network_submission_count",
            "locked_final_access_count",
            "official_access_count",
            "kaggle_mutation_count",
            "arc_task_payload_read_count",
            "teacher_trajectory_read_count",
            "hds_hypothesis_generation_count",
            "distillation_execution_count",
            "bridge_runtime_capability_count",
            "audited_source_execution_count",
            "rule_promotion_count",
        ):
            if ph_d00b_budget.get(field) != 0:
                failures.append(f"ph_d00b_frame:{field}:NONZERO")

    ph_d00b_transition = _load_object(root, PH_D00B_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d00b_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d00b_transition",
        )
    )
    if (
        ph_d00b_transition.get("from_phase_id"),
        ph_d00b_transition.get("to_phase_id"),
        ph_d00b_transition.get("decision"),
    ) != ("PH-D00A", "PH-D00B", "ENTRY_AUTHORIZED"):
        failures.append("ph_d00b_transition:SEQUENCE_MISMATCH")
    if ph_d00b_transition.get(
        "authorization_digest"
    ) != ph_d00a_result_approval.get("approval_artifact_digest"):
        failures.append("ph_d00b_transition:APPROVAL_MISMATCH")
    if (
        ph_d00b_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d00b_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d01a_frame = _load_object(root, PH_D01A_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d01a_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d01a_frame",
        )
    )
    if ph_d01a_frame.get("phase_id") != "PH-D01A":
        failures.append("ph_d01a_frame:PHASE_MISMATCH")
    ph_d01a_budget = ph_d01a_frame.get("resource_budget")
    if not isinstance(ph_d01a_budget, dict):
        failures.append("ph_d01a_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field, value in ph_d01a_budget.items():
            if not isinstance(field, str) or value != 0:
                failures.append(f"ph_d01a_frame:{field}:NONZERO")

    ph_d01a_transition = _load_object(root, PH_D01A_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d01a_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d01a_transition",
        )
    )
    if (
        ph_d01a_transition.get("from_phase_id"),
        ph_d01a_transition.get("to_phase_id"),
        ph_d01a_transition.get("decision"),
    ) != ("PH-D00B", "PH-D01A", "ENTRY_AUTHORIZED"):
        failures.append("ph_d01a_transition:SEQUENCE_MISMATCH")
    if ph_d01a_transition.get(
        "authorization_digest"
    ) != ph_d00b_result_approval.get("approval_artifact_digest"):
        failures.append("ph_d01a_transition:APPROVAL_MISMATCH")
    if (
        ph_d01a_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d01a_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d01b_frame = _load_object(root, PH_D01B_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d01b_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d01b_frame",
        )
    )
    if ph_d01b_frame.get("phase_id") != "PH-D01B":
        failures.append("ph_d01b_frame:PHASE_MISMATCH")
    ph_d01b_budget = ph_d01b_frame.get("resource_budget")
    if not isinstance(ph_d01b_budget, dict):
        failures.append("ph_d01b_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field in (
            "remote_recording_content_hash_count",
            "source_payload_semantic_parse_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "hds_hypothesis_generation_count",
            "distillation_execution_count",
            "bridge_runtime_capability_count",
            "rule_promotion_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d01b_budget.get(field) != 0:
                failures.append(f"ph_d01b_frame:{field}:NONZERO")
        if ph_d01b_budget.get(
            "local_source_blind_probe_process_count"
        ) != 3:
            failures.append(
                "ph_d01b_frame:SOURCE_BLIND_PROCESS_COUNT_MISMATCH"
            )
        if ph_d01b_budget.get("external_network_use") != "NONE":
            failures.append("ph_d01b_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d01b_transition = _load_object(root, PH_D01B_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d01b_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d01b_transition",
        )
    )
    if (
        ph_d01b_transition.get("from_phase_id"),
        ph_d01b_transition.get("to_phase_id"),
        ph_d01b_transition.get("decision"),
    ) != ("PH-D01A", "PH-D01B", "ENTRY_AUTHORIZED"):
        failures.append("ph_d01b_transition:SEQUENCE_MISMATCH")
    if (
        ph_d01b_transition.get("authorization_digest")
        != ph_d01a_result_approval.get("approval_artifact_digest")
        or ph_d01b_transition.get("from_phase_evidence_commit")
        != ph_d01a_attestation.get("evidence_commit")
        or ph_d01b_transition.get("from_phase_evidence_payload_digest")
        != ph_d01a_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d01b_transition:EVIDENCE_BINDING_MISMATCH")
    if (
        ph_d01b_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d01b_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d02a_frame = _load_object(root, PH_D02A_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02a_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d02a_frame",
        )
    )
    if (
        ph_d02a_frame.get("phase_id") != "PH-D02A"
        or ph_d02a_frame.get("base_commit")
        != "4dbf17513fdf2027527f9f5ea64f16a99fc52326"
        or ph_d02a_frame.get("base_tree")
        != "fe3c806ab55a7adfa80e5f8f8c0e9a488317af0d"
    ):
        failures.append("ph_d02a_frame:PHASE_OR_BASE_MISMATCH")
    ph_d02a_budget = ph_d02a_frame.get("resource_budget")
    if not isinstance(ph_d02a_budget, dict):
        failures.append("ph_d02a_frame:RESOURCE_BUDGET_MISSING")
    else:
        for field in (
            "source_payload_read_count",
            "source_payload_semantic_parse_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "real_trajectory_normalization_count",
            "ph_d02b_schema_count",
            "hds_hypothesis_generation_count",
            "distillation_execution_count",
            "bridge_runtime_capability_count",
            "rule_promotion_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d02a_budget.get(field) != 0:
                failures.append(f"ph_d02a_frame:{field}:NONZERO")
        if ph_d02a_budget.get(
            "canonical_test_vector_rebuild_process_count"
        ) != 3:
            failures.append(
                "ph_d02a_frame:VECTOR_REBUILD_COUNT_MISMATCH"
            )
        if ph_d02a_budget.get("external_network_use") != "NONE":
            failures.append("ph_d02a_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d02a_transition = _load_object(root, PH_D02A_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02a_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d02a_transition",
        )
    )
    if (
        ph_d02a_transition.get("from_phase_id"),
        ph_d02a_transition.get("to_phase_id"),
        ph_d02a_transition.get("decision"),
    ) != ("PH-D01B", "PH-D02A", "ENTRY_AUTHORIZED"):
        failures.append("ph_d02a_transition:SEQUENCE_MISMATCH")
    if (
        ph_d02a_transition.get("authorization_digest")
        != ph_d01b_result_approval.get("approval_artifact_digest")
        or ph_d02a_transition.get("from_phase_state_sha256")
        != ph_d01b_attestation.get("phase_state_sha256")
        or ph_d02a_transition.get("from_phase_evidence_commit")
        != ph_d01b_attestation.get("evidence_commit")
        or ph_d02a_transition.get("from_phase_evidence_tree")
        != ph_d01b_attestation.get("evidence_tree")
        or ph_d02a_transition.get(
            "from_phase_evidence_payload_digest"
        )
        != ph_d01b_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02a_transition:EVIDENCE_BINDING_MISMATCH")
    if (
        ph_d02a_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d02a_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d02a_preinventory = _load_object(
        root, PH_D02A_PREINVENTORY_PATH
    )
    preinventory_body = dict(ph_d02a_preinventory)
    preinventory_body.pop("content_digest", None)
    if ph_d02a_preinventory.get("content_digest") != (
        "rev3-ph-d02a-canonical-preinventory:"
        + digest_object(preinventory_body)
    ):
        failures.append("ph_d02a_preinventory:CONTENT_DIGEST_MISMATCH")
    if (
        ph_d02a_preinventory.get("phase_id") != "PH-D02A"
        or ph_d02a_preinventory.get("base_commit")
        != ph_d02a_frame.get("base_commit")
        or ph_d02a_preinventory.get("base_tree")
        != ph_d02a_frame.get("base_tree")
        or ph_d02a_preinventory.get("preexisting_dirty_state", {}).get(
            "path_scope"
        )
        != "analysis/autonomous_completion/**"
        or ph_d02a_preinventory.get("preexisting_dirty_state", {}).get(
            "mutation"
        )
        != "NONE"
    ):
        failures.append("ph_d02a_preinventory:BOUNDARY_MISMATCH")

    ph_d02a_contract = _load_object(root, PH_D02A_CONTRACT_PATH)
    failures.extend(
        _domain_content_digest_failures(
            ph_d02a_contract,
            "hds-canonicalization-contract",
            "content_digest",
            "ph_d02a_contract",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02A_CONTRACT_PATH,
            "ph_d02a_contract",
        )
    )
    contract_authority = ph_d02a_contract.get("authority")
    if not isinstance(contract_authority, dict) or (
        ph_d02a_contract.get("phase_id") != "PH-D02A"
        or ph_d02a_contract.get("gates") != ["DG-06", "DG-07"]
        or contract_authority.get("input_phase_state_sha256")
        != ph_d01b_attestation.get("phase_state_sha256")
        or contract_authority.get("input_evidence_commit")
        != ph_d01b_attestation.get("evidence_commit")
        or contract_authority.get("input_evidence_tree")
        != ph_d01b_attestation.get("evidence_tree")
        or contract_authority.get("input_evidence_payload_digest")
        != ph_d01b_attestation.get("evidence_payload_digest")
        or contract_authority.get("input_owner_approval_digest")
        != ph_d01b_result_approval.get("approval_artifact_digest")
        or contract_authority.get("entry_transition_digest")
        != ph_d02a_transition.get("content_digest")
        or contract_authority.get("work_block_frame_digest")
        != ph_d02a_frame.get("content_digest")
    ):
        failures.append("ph_d02a_contract:AUTHORITY_BINDING_MISMATCH")
    canonical_json_contract = ph_d02a_contract.get("canonical_json")
    canonical_jsonl_contract = ph_d02a_contract.get("canonical_jsonl")
    if not isinstance(canonical_json_contract, dict) or (
        canonical_json_contract.get(
            "document_serialization_trailing_lf"
        )
        is not True
    ):
        failures.append("ph_d02a_contract:JSON_DOCUMENT_LF_MISSING")
    if not isinstance(canonical_jsonl_contract, dict) or (
        canonical_jsonl_contract.get("record_order")
        != "UTF8_LEXICOGRAPHIC_BY_NFC_RECORD_ID"
        or canonical_jsonl_contract.get("final_lf")
        != "REQUIRED_FOR_NONEMPTY_FILE"
    ):
        failures.append("ph_d02a_contract:JSONL_CONTRACT_MISMATCH")

    ph_d02a_vectors = _load_object(
        root, PH_D02A_VECTOR_MANIFEST_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02a_vectors,
            "hds-canonical-test-vectors",
            "content_digest",
            "ph_d02a_vectors",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02A_VECTOR_MANIFEST_PATH,
            "ph_d02a_vectors",
        )
    )
    vector_contract = ph_d02a_vectors.get("contract")
    rebuild_contract = ph_d02a_vectors.get(
        "independent_rebuild_contract"
    )
    if not isinstance(vector_contract, dict) or (
        vector_contract.get("content_digest")
        != ph_d02a_contract.get("content_digest")
        or vector_contract.get("path")
        != PH_D02A_CONTRACT_PATH.as_posix()
        or ph_d02a_vectors.get("gates") != ["DG-06", "DG-07"]
    ):
        failures.append("ph_d02a_vectors:CONTRACT_BINDING_MISMATCH")
    if not isinstance(rebuild_contract, dict) or (
        rebuild_contract.get("count") != 3
        or rebuild_contract.get("expected") != "BYTE_IDENTICAL"
    ):
        failures.append("ph_d02a_vectors:REBUILD_CONTRACT_MISMATCH")
    vector_outputs = ph_d02a_vectors.get("outputs")
    expected_vector_paths = {
        "canonical_json": Path(
            "distillation/artifacts/test_vectors/canonical_json_v1.json"
        ),
        "canonical_jsonl": Path(
            "distillation/artifacts/test_vectors/canonical_jsonl_v1.jsonl"
        ),
        "canonical_npz": Path(
            "distillation/artifacts/test_vectors/canonical_npz_v1.npz"
        ),
        "canonical_zip": Path(
            "distillation/artifacts/test_vectors/canonical_zip_v1.zip"
        ),
    }
    if not isinstance(vector_outputs, dict):
        failures.append("ph_d02a_vectors:OUTPUTS_MISSING")
    else:
        for output_name, expected_path in expected_vector_paths.items():
            output = vector_outputs.get(output_name)
            if not isinstance(output, dict) or output.get(
                "path"
            ) != expected_path.as_posix():
                failures.append(
                    f"ph_d02a_vectors:{output_name}:PATH_MISMATCH"
                )
                continue
            output_path = root / expected_path
            if (
                not output_path.is_file()
                or hashlib.sha256(output_path.read_bytes()).hexdigest()
                != output.get("sha256")
                or output_path.stat().st_size != output.get("size_bytes")
            ):
                failures.append(
                    f"ph_d02a_vectors:{output_name}:BYTES_MISMATCH"
                )

    ph_d02a_conformance = _load_object(
        root, PH_D02A_CONFORMANCE_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02a_conformance,
            "hds-canonicalization-conformance",
            "content_digest",
            "ph_d02a_conformance",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02A_CONFORMANCE_PATH,
            "ph_d02a_conformance",
        )
    )
    report_authority = ph_d02a_conformance.get("authority")
    determinism = ph_d02a_conformance.get("determinism")
    report_contract = ph_d02a_conformance.get("contract")
    report_vectors = ph_d02a_conformance.get("test_vectors")
    if not isinstance(report_authority, dict) or (
        report_authority.get("input_phase_state_sha256")
        != ph_d01b_attestation.get("phase_state_sha256")
        or report_authority.get("owner_authorization_digest")
        != ph_d01b_result_approval.get("approval_artifact_digest")
        or report_authority.get("phase_transition_digest")
        != ph_d02a_transition.get("content_digest")
        or report_authority.get("preinventory_digest")
        != ph_d02a_preinventory.get("content_digest")
        or report_authority.get("work_block_frame_digest")
        != ph_d02a_frame.get("content_digest")
    ):
        failures.append("ph_d02a_conformance:AUTHORITY_MISMATCH")
    if not isinstance(report_contract, dict) or (
        report_contract.get("content_digest")
        != ph_d02a_contract.get("content_digest")
    ):
        failures.append("ph_d02a_conformance:CONTRACT_MISMATCH")
    if not isinstance(report_vectors, dict) or (
        report_vectors.get("manifest", {}).get("content_digest")
        != ph_d02a_vectors.get("content_digest")
    ):
        failures.append("ph_d02a_conformance:VECTOR_BINDING_MISMATCH")
    if not isinstance(determinism, dict) or (
        determinism.get("independent_process_rebuild_count") != 3
        or determinism.get("byte_identical") is not True
        or determinism.get("canonical_json_match") is not True
        or determinism.get("canonical_jsonl_match") is not True
        or determinism.get("canonical_npz_match") is not True
        or determinism.get("canonical_zip_match") is not True
    ):
        failures.append("ph_d02a_conformance:DETERMINISM_MISMATCH")
    if (
        ph_d02a_conformance.get("phase_id") != "PH-D02A"
        or ph_d02a_conformance.get("status")
        != "CODEX_IMPLEMENTATION_VALIDATED"
        or ph_d02a_conformance.get("active_failure_count") != 0
        or ph_d02a_conformance.get("gates")
        != {"DG-06": "PASS", "DG-07": "PASS"}
    ):
        failures.append("ph_d02a_conformance:GATE_MISMATCH")

    ph_d02b_frame = _load_object(root, PH_D02B_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02b_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d02b_frame",
        )
    )
    if (
        ph_d02b_frame.get("phase_id") != "PH-D02B"
        or ph_d02b_frame.get("base_commit")
        != "32b141ef50224e74d6ed95e9198377a2860328e3"
        or ph_d02b_frame.get("base_tree")
        != "8f794710bcbde10a22b6a1fc91364cbb1005f0f7"
    ):
        failures.append("ph_d02b_frame:PHASE_OR_BASE_MISMATCH")
    ph_d02b_budget = ph_d02b_frame.get("resource_budget")
    if not isinstance(ph_d02b_budget, dict):
        failures.append("ph_d02b_frame:RESOURCE_BUDGET_MISSING")
    else:
        if (
            ph_d02b_budget.get("hds_rev2_schema_count"),
            ph_d02b_budget.get("structure_bundle_schema_count"),
            ph_d02b_budget.get("total_schema_count"),
            ph_d02b_budget.get("synthetic_valid_example_count"),
            ph_d02b_budget.get("schema_artifact_rebuild_process_count"),
        ) != (38, 7, 45, 45, 3):
            failures.append("ph_d02b_frame:SCHEMA_BUDGET_MISMATCH")
        for field in (
            "source_payload_read_count",
            "source_payload_semantic_parse_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "real_trajectory_normalization_count",
            "ph_d02c_execution_count",
            "hds_hypothesis_generation_count",
            "distillation_execution_count",
            "bridge_runtime_capability_count",
            "rule_promotion_count",
            "owner_approval_generated_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d02b_budget.get(field) != 0:
                failures.append(f"ph_d02b_frame:{field}:NONZERO")
        if ph_d02b_budget.get("external_network_use") != "NONE":
            failures.append("ph_d02b_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d02b_transition = _load_object(root, PH_D02B_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02b_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d02b_transition",
        )
    )
    if (
        ph_d02b_transition.get("from_phase_id"),
        ph_d02b_transition.get("to_phase_id"),
        ph_d02b_transition.get("decision"),
    ) != ("PH-D02A", "PH-D02B", "ENTRY_AUTHORIZED"):
        failures.append("ph_d02b_transition:SEQUENCE_MISMATCH")
    if (
        ph_d02b_transition.get("authorization_digest")
        != ph_d02a_result_approval.get("approval_artifact_digest")
        or ph_d02b_transition.get("from_phase_state_sha256")
        != ph_d02a_attestation.get("phase_state_sha256")
        or ph_d02b_transition.get("from_phase_evidence_commit")
        != ph_d02a_attestation.get("evidence_commit")
        or ph_d02b_transition.get("from_phase_evidence_tree")
        != ph_d02a_attestation.get("evidence_tree")
        or ph_d02b_transition.get(
            "from_phase_evidence_payload_digest"
        )
        != ph_d02a_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02b_transition:EVIDENCE_BINDING_MISMATCH")
    if (
        ph_d02b_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d02b_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d02b_preinventory = _load_object(
        root, PH_D02B_PREINVENTORY_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d02b_preinventory,
            "rev3-ph-d02b-schema-bundle-preinventory:",
            "content_digest",
            "ph_d02b_preinventory",
        )
    )
    if (
        ph_d02b_preinventory.get("phase_id") != "PH-D02B"
        or ph_d02b_preinventory.get("base_commit")
        != ph_d02b_frame.get("base_commit")
        or ph_d02b_preinventory.get("base_tree")
        != ph_d02b_frame.get("base_tree")
        or ph_d02b_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("path_scope")
        != "analysis/autonomous_completion/**"
        or ph_d02b_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("mutation")
        != "NONE"
    ):
        failures.append("ph_d02b_preinventory:BOUNDARY_MISMATCH")

    ph_d02b_snapshot = _load_object(
        root, PH_D02B_SNAPSHOT_MANIFEST_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d02b_snapshot,
            "hds-d02b-pre-audit-snapshot:",
            "content_digest",
            "ph_d02b_snapshot",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02B_SNAPSHOT_MANIFEST_PATH,
            "ph_d02b_snapshot",
        )
    )
    snapshot_artifacts = ph_d02b_snapshot.get("artifacts")
    snapshot_root = PH_D02B_SNAPSHOT_MANIFEST_PATH.parent
    if (
        ph_d02b_snapshot.get("artifact_count") != 41
        or ph_d02b_snapshot.get("source_commit")
        != "108c5462c2c73bdd95953e9e9b0cbbce68ac5d02"
        or not isinstance(snapshot_artifacts, list)
        or len(snapshot_artifacts) != 41
    ):
        failures.append("ph_d02b_snapshot:INVENTORY_MISMATCH")
    elif any(
        not isinstance(item, dict)
        or not isinstance(item.get("path"), str)
        or not (root / snapshot_root / item["path"]).is_file()
        or hashlib.sha256(
            (root / snapshot_root / item["path"]).read_bytes()
        ).hexdigest()
        != item.get("sha256")
        for item in snapshot_artifacts
    ):
        failures.append("ph_d02b_snapshot:ARTIFACT_BYTES_MISMATCH")

    ph_d02b_document_contract = _load_object(
        root, PH_D02B_DOCUMENT_CONTRACT_PATH
    )
    document_inventory = ph_d02b_document_contract.get(
        "schema_inventory"
    )
    document_mapping = ph_d02b_document_contract.get(
        "hds_rev2_schema_mapping"
    )
    document_files = ph_d02b_document_contract.get(
        "required_file_inventory"
    )
    if (
        not isinstance(document_inventory, dict)
        or not isinstance(document_mapping, dict)
        or not isinstance(document_files, list)
        or document_inventory.get("hds_rev2_schema_count") != 38
        or document_inventory.get("bundle_schema_count") != 7
        or document_inventory.get("total_schema_count") != 45
        or len(document_files) != 34
    ):
        failures.append("ph_d02b_document_contract:INVENTORY_MISMATCH")
        document_hds_names: list[object] = []
        document_bundle_names: list[object] = []
    else:
        document_hds_names = list(
            document_inventory.get("hds_rev2_schema_names", [])
        )
        document_bundle_names = list(
            document_inventory.get("bundle_schema_names", [])
        )
        mapped_names = [
            name
            for bundle_name in document_bundle_names
            for name in document_mapping.get(bundle_name, [])
        ]
        if (
            len(document_hds_names) != 38
            or len(set(document_hds_names)) != 38
            or len(document_bundle_names) != 7
            or set(document_mapping) != set(document_bundle_names)
            or len(mapped_names) != 38
            or len(set(mapped_names)) != 38
            or set(mapped_names) != set(document_hds_names)
        ):
            failures.append(
                "ph_d02b_document_contract:ONE_TO_ONE_MAPPING_MISMATCH"
            )

    ph_d02b_contract = _load_object(root, PH_D02B_CONTRACT_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02b_contract,
            "hds-post-audit-schema-bundle-contract:",
            "content_digest",
            "ph_d02b_contract",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02B_CONTRACT_PATH,
            "ph_d02b_contract",
        )
    )
    hds_entries = ph_d02b_contract.get("hds_rev2_schema_entries")
    bundle_entries = ph_d02b_contract.get("bundle_schema_entries")
    one_to_one = ph_d02b_contract.get(
        "hds_rev2_one_to_one_mapping"
    )
    contract_files = ph_d02b_contract.get(
        "required_bundle_file_inventory"
    )
    if (
        ph_d02b_contract.get("phase_id") != "PH-D02B"
        or ph_d02b_contract.get("base_hds_schema_count") != 38
        or ph_d02b_contract.get("bundle_schema_count") != 7
        or ph_d02b_contract.get("total_schema_count") != 45
        or not isinstance(hds_entries, list)
        or not isinstance(bundle_entries, list)
        or not isinstance(one_to_one, dict)
        or not isinstance(contract_files, list)
        or len(hds_entries) != 38
        or len(bundle_entries) != 7
        or len(one_to_one) != 38
        or len(contract_files) != 34
        or contract_files != document_files
    ):
        failures.append("ph_d02b_contract:INVENTORY_MISMATCH")
    else:
        contract_hds_names = [entry.get("name") for entry in hds_entries]
        contract_bundle_names = [
            entry.get("name") for entry in bundle_entries
        ]
        if (
            contract_hds_names != document_hds_names
            or contract_bundle_names != document_bundle_names
            or set(one_to_one) != set(document_hds_names)
        ):
            failures.append("ph_d02b_contract:NAME_MAPPING_MISMATCH")
        schema_entries = [*hds_entries, *bundle_entries]
        expected_schema_files = {
            entry.get("filename") for entry in schema_entries
        }
        actual_schema_files = {
            path.name
            for path in (root / PH_D02B_SCHEMA_ROOT).glob(
                "*.schema.json"
            )
        }
        if (
            None in expected_schema_files
            or len(expected_schema_files) != 45
            or actual_schema_files != expected_schema_files
        ):
            failures.append("ph_d02b_contract:SCHEMA_FILES_MISMATCH")
        else:
            for entry in schema_entries:
                schema_path = root / str(entry["schema_path"])
                if (
                    not schema_path.is_file()
                    or hashlib.sha256(schema_path.read_bytes()).hexdigest()
                    != entry.get("schema_sha256")
                ):
                    failures.append(
                        "ph_d02b_contract:SCHEMA_BYTES_MISMATCH:"
                        + str(entry.get("name"))
                    )

    ph_d02b_examples = _load_object(root, PH_D02B_EXAMPLES_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02b_examples,
            "hds-post-audit-valid-schema-examples:",
            "content_digest",
            "ph_d02b_examples",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02B_EXAMPLES_PATH,
            "ph_d02b_examples",
        )
    )
    examples = ph_d02b_examples.get("examples")
    if (
        ph_d02b_examples.get("phase_id") != "PH-D02B"
        or ph_d02b_examples.get("synthetic_fixture_only") is not True
        or ph_d02b_examples.get("owner_approval_generated") is not False
        or ph_d02b_examples.get("example_count") != 45
        or not isinstance(examples, list)
        or len(examples) != 45
    ):
        failures.append("ph_d02b_examples:INVENTORY_MISMATCH")

    ph_d02b_invalid = _load_object(root, PH_D02B_INVALID_CASES_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02b_invalid,
            "hds-post-audit-invalid-schema-cases:",
            "content_digest",
            "ph_d02b_invalid",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02B_INVALID_CASES_PATH,
            "ph_d02b_invalid",
        )
    )
    invalid_cases = ph_d02b_invalid.get("cases")
    if (
        ph_d02b_invalid.get("phase_id") != "PH-D02B"
        or ph_d02b_invalid.get("case_count") != 9
        or not isinstance(invalid_cases, list)
        or len(invalid_cases) != 9
    ):
        failures.append("ph_d02b_invalid:INVENTORY_MISMATCH")

    ph_d02b_conformance = _load_object(
        root, PH_D02B_CONFORMANCE_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d02b_conformance,
            "hds-post-audit-schema-conformance:",
            "content_digest",
            "ph_d02b_conformance",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02B_CONFORMANCE_PATH,
            "ph_d02b_conformance",
        )
    )
    if (
        ph_d02b_conformance.get("phase_id") != "PH-D02B"
        or ph_d02b_conformance.get("result")
        != "PH_D02B_SCHEMA_SET_PASS"
        or ph_d02b_conformance.get("base_hds_schema_count") != 38
        or ph_d02b_conformance.get("bundle_schema_count") != 7
        or ph_d02b_conformance.get("total_schema_count") != 45
        or ph_d02b_conformance.get("positive_record_count") != 45
        or ph_d02b_conformance.get("invalid_case_count") != 9
        or ph_d02b_conformance.get("required_bundle_file_count") != 34
        or ph_d02b_conformance.get("cross_file_reference_integrity")
        != "PASS"
        or ph_d02b_conformance.get("partial_bundle_rejection") != "PASS"
        or ph_d02b_conformance.get("unknown_file_rejection") != "PASS"
        or ph_d02b_conformance.get("dependency_lock_rejection") != "PASS"
        or ph_d02b_conformance.get("owner_approval_generated_count") != 0
        or ph_d02b_conformance.get("ph_d02c_execution_count") != 0
        or ph_d02b_conformance.get("rule_promotion_count") != 0
    ):
        failures.append("ph_d02b_conformance:GATE_MISMATCH")

    ph_d02c_frame = _load_object(root, PH_D02C_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02c_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d02c_frame",
        )
    )
    if (
        ph_d02c_frame.get("phase_id") != "PH-D02C"
        or ph_d02c_frame.get("base_commit")
        != "9c9cf5a9790fae341ad1be45506c88e7a7f34b58"
        or ph_d02c_frame.get("base_tree")
        != "e2b19714dd86bd2193a9531fdb65ece4bec0417c"
    ):
        failures.append("ph_d02c_frame:PHASE_OR_BASE_MISMATCH")
    ph_d02c_budget = ph_d02c_frame.get("resource_budget")
    if not isinstance(ph_d02c_budget, dict):
        failures.append("ph_d02c_frame:RESOURCE_BUDGET_MISSING")
    else:
        if (
            ph_d02c_budget.get("required_common_type_count"),
            ph_d02c_budget.get("required_arc2_opcode_count"),
            ph_d02c_budget.get("required_arc3_opcode_count"),
            ph_d02c_budget.get("required_total_domain_opcode_count"),
            ph_d02c_budget.get("changed_schema_count"),
            ph_d02c_budget.get("derived_schema_set_total_count"),
            ph_d02c_budget.get("independent_process_rebuild_count"),
        ) != (18, 33, 18, 51, 2, 45, 3):
            failures.append("ph_d02c_frame:IR_BUDGET_MISMATCH")
        for field in (
            "source_payload_read_count",
            "source_payload_semantic_parse_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "real_trajectory_normalization_count",
            "real_intervention_execution_count",
            "hds_hypothesis_generation_count",
            "rule_promotion_count",
            "owner_approval_generated_count",
            "bridge_runtime_capability_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d02c_budget.get(field) != 0:
                failures.append(f"ph_d02c_frame:{field}:NONZERO")
        if ph_d02c_budget.get("external_network_use") != "NONE":
            failures.append("ph_d02c_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d02c_transition = _load_object(root, PH_D02C_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d02c_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d02c_transition",
        )
    )
    if (
        ph_d02c_transition.get("from_phase_id"),
        ph_d02c_transition.get("to_phase_id"),
        ph_d02c_transition.get("decision"),
    ) != ("PH-D02B", "PH-D02C", "ENTRY_AUTHORIZED"):
        failures.append("ph_d02c_transition:SEQUENCE_MISMATCH")
    if (
        ph_d02c_transition.get("authorization_digest")
        != ph_d02b_result_approval.get("approval_artifact_digest")
        or ph_d02c_transition.get("from_phase_state_sha256")
        != ph_d02b_attestation.get("phase_state_sha256")
        or ph_d02c_transition.get("from_phase_evidence_commit")
        != ph_d02b_attestation.get("evidence_commit")
        or ph_d02c_transition.get("from_phase_evidence_tree")
        != ph_d02b_attestation.get("evidence_tree")
        or ph_d02c_transition.get(
            "from_phase_evidence_payload_digest"
        )
        != ph_d02b_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d02c_transition:EVIDENCE_BINDING_MISMATCH")
    if (
        ph_d02c_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d02c_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d02c_preinventory = _load_object(
        root, PH_D02C_PREINVENTORY_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d02c_preinventory,
            "rev3-ph-d02c-post-audit-ir-preinventory:",
            "content_digest",
            "ph_d02c_preinventory",
        )
    )
    if (
        ph_d02c_preinventory.get("phase_id") != "PH-D02C"
        or ph_d02c_preinventory.get("base_commit")
        != ph_d02c_frame.get("base_commit")
        or ph_d02c_preinventory.get("base_tree")
        != ph_d02c_frame.get("base_tree")
        or ph_d02c_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("path_scope")
        != "analysis/autonomous_completion/**"
        or ph_d02c_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("mutation")
        != "NONE"
    ):
        failures.append("ph_d02c_preinventory:BOUNDARY_MISMATCH")

    ph_d02c_document_contract = _load_object(
        root, PH_D02C_DOCUMENT_CONTRACT_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d02c_document_contract,
            "rev3-post-audit-causal-ir-contract:",
            "content_digest",
            "ph_d02c_document_contract",
        )
    )
    if (
        ph_d02c_document_contract.get("phase_owner") != "PH-D02C"
        or ph_d02c_document_contract.get(
            "schema_migration", {}
        ).get("derived_schema_count")
        != 45
        or ph_d02c_document_contract.get(
            "schema_migration", {}
        ).get("changed_schema_count")
        != 2
        or ph_d02c_document_contract.get(
            "type_and_opcode_inventory", {}
        ).get("total_domain_opcode_count")
        != 51
    ):
        failures.append("ph_d02c_document_contract:INVENTORY_MISMATCH")
    document_authority = ph_d02c_document_contract.get(
        "authority_binding"
    )
    if not isinstance(document_authority, dict) or (
        document_authority.get(
            "ph_d02b_schema_bundle_contract_digest"
        )
        != ph_d02b_contract.get("content_digest")
        or document_authority.get("ph_d02b_phase_state_sha256")
        != ph_d02b_attestation.get("phase_state_sha256")
        or document_authority.get(
            "ph_d02b_evidence_payload_digest"
        )
        != ph_d02b_attestation.get("evidence_payload_digest")
        or document_authority.get("ph_d02c_entry_approval_digest")
        != ph_d02b_result_approval.get("approval_artifact_digest")
        or document_authority.get(
            "ph_d02c_work_block_frame_digest"
        )
        != ph_d02c_frame.get("content_digest")
    ):
        failures.append(
            "ph_d02c_document_contract:AUTHORITY_BINDING_MISMATCH"
        )

    ph_d02c_snapshot = _load_object(
        root, PH_D02C_SNAPSHOT_MANIFEST_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_snapshot,
            "hds-ph-d02c-historical-snapshot",
            "content_digest",
            "ph_d02c_snapshot",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02C_SNAPSHOT_MANIFEST_PATH,
            "ph_d02c_snapshot",
        )
    )
    snapshot_items = ph_d02c_snapshot.get("artifacts")
    if (
        ph_d02c_snapshot.get("phase_id") != "PH-D02C"
        or ph_d02c_snapshot.get("source_commit")
        != "9c9cf5a9790fae341ad1be45506c88e7a7f34b58"
        or ph_d02c_snapshot.get("artifact_count") != 12
        or ph_d02c_snapshot.get("eligible_for_current_activation")
        is not False
        or not isinstance(snapshot_items, list)
        or len(snapshot_items) != 12
    ):
        failures.append("ph_d02c_snapshot:INVENTORY_MISMATCH")
    else:
        for item in snapshot_items:
            if not isinstance(item, dict):
                failures.append("ph_d02c_snapshot:ITEM_INVALID")
                continue
            source_path = item.get("source_path")
            destination_path = item.get("destination_path")
            expected_sha = item.get("sha256")
            destination = (
                root / destination_path
                if isinstance(destination_path, str)
                else None
            )
            source_bytes = (
                _git_blob(
                    root,
                    "9c9cf5a9790fae341ad1be45506c88e7a7f34b58",
                    source_path,
                )
                if isinstance(source_path, str)
                else None
            )
            if (
                destination is None
                or not destination.is_file()
                or source_bytes is None
                or hashlib.sha256(destination.read_bytes()).hexdigest()
                != expected_sha
                or hashlib.sha256(source_bytes).hexdigest() != expected_sha
            ):
                failures.append(
                    "ph_d02c_snapshot:ARTIFACT_BYTES_MISMATCH:"
                    + str(source_path)
                )

    ph_d02c_schema_contract = _load_object(
        root, PH_D02C_SCHEMA_CONTRACT_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_schema_contract,
            "hds-post-audit-causal-ir-schema-contract",
            "content_digest",
            "ph_d02c_schema_contract",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02C_SCHEMA_CONTRACT_PATH,
            "ph_d02c_schema_contract",
        )
    )
    ph_d02c_schema_entries = ph_d02c_schema_contract.get(
        "schema_entries"
    )
    schema_authority = ph_d02c_schema_contract.get("authority")
    if (
        ph_d02c_schema_contract.get("phase_id") != "PH-D02C"
        or ph_d02c_schema_contract.get("base_schema_count") != 45
        or ph_d02c_schema_contract.get("derived_schema_count") != 45
        or ph_d02c_schema_contract.get("unchanged_schema_count") != 43
        or ph_d02c_schema_contract.get("changed_schema_count") != 2
        or ph_d02c_schema_contract.get("changed_schema_names")
        != ["HypothesisIR", "OperatorRegistry"]
        or not isinstance(ph_d02c_schema_entries, list)
        or len(ph_d02c_schema_entries) != 45
    ):
        failures.append("ph_d02c_schema_contract:INVENTORY_MISMATCH")
    else:
        actual_schema_files = {
            path.name
            for path in (root / PH_D02C_SCHEMA_ROOT).glob(
                "*.schema.json"
            )
        }
        expected_schema_files = {
            item.get("filename")
            for item in ph_d02c_schema_entries
            if isinstance(item, dict)
        }
        if (
            len(actual_schema_files) != 45
            or actual_schema_files != expected_schema_files
        ):
            failures.append(
                "ph_d02c_schema_contract:SCHEMA_FILES_MISMATCH"
            )
        for item in ph_d02c_schema_entries:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename")
            ph_d02c_schema_path = (
                root / PH_D02C_SCHEMA_ROOT / filename
                if isinstance(filename, str)
                else None
            )
            if (
                ph_d02c_schema_path is None
                or not ph_d02c_schema_path.is_file()
                or hashlib.sha256(
                    ph_d02c_schema_path.read_bytes()
                ).hexdigest()
                != item.get("derived_schema_sha256")
            ):
                failures.append(
                    "ph_d02c_schema_contract:SCHEMA_BYTES_MISMATCH:"
                    + str(item.get("name"))
                )
    if not isinstance(schema_authority, dict) or (
        schema_authority.get("ph_d02b_contract_digest")
        != ph_d02b_contract.get("content_digest")
        or schema_authority.get("ph_d02b_phase_state_sha256")
        != ph_d02b_attestation.get("phase_state_sha256")
        or schema_authority.get("ph_d02b_evidence_payload_digest")
        != ph_d02b_attestation.get("evidence_payload_digest")
        or schema_authority.get("ph_d02c_entry_approval_digest")
        != ph_d02b_result_approval.get("approval_artifact_digest")
        or schema_authority.get("ph_d02c_work_block_frame_digest")
        != ph_d02c_frame.get("content_digest")
    ):
        failures.append(
            "ph_d02c_schema_contract:AUTHORITY_BINDING_MISMATCH"
        )

    ph_d02c_ir_contract = _load_object(
        root, PH_D02C_CAUSAL_IR_CONTRACT_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_ir_contract,
            "hds-causal-ir-contract",
            "content_digest",
            "ph_d02c_ir_contract",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02C_CAUSAL_IR_CONTRACT_PATH,
            "ph_d02c_ir_contract",
        )
    )
    ir_authority = ph_d02c_ir_contract.get("authority")
    if (
        ph_d02c_ir_contract.get("phase_id") != "PH-D02C"
        or len(ph_d02c_ir_contract.get("common_types", [])) != 18
        or len(ph_d02c_ir_contract.get("arc2_opcodes", [])) != 33
        or len(ph_d02c_ir_contract.get("arc3_opcodes", [])) != 18
        or ph_d02c_ir_contract.get("gates")
        != ["DG-03", "DG-08", "DG-09", "DG-12"]
    ):
        failures.append("ph_d02c_ir_contract:INVENTORY_MISMATCH")
    if not isinstance(ir_authority, dict) or (
        ir_authority.get("ph_d02b_schema_contract_digest")
        != ph_d02b_contract.get("content_digest")
        or ir_authority.get("ph_d02b_phase_state_sha256")
        != "sha256:" + str(ph_d02b_attestation.get("phase_state_sha256"))
        or ir_authority.get("ph_d02b_evidence_payload_digest")
        != ph_d02b_attestation.get("evidence_payload_digest")
        or ir_authority.get("ph_d02c_entry_approval_digest")
        != ph_d02b_result_approval.get("approval_artifact_digest")
        or ir_authority.get("schema_refinement_contract_digest")
        != ph_d02c_schema_contract.get("content_digest")
        or ir_authority.get("work_block_frame_digest")
        != ph_d02c_frame.get("content_digest")
    ):
        failures.append(
            "ph_d02c_ir_contract:AUTHORITY_BINDING_MISMATCH"
        )

    ph_d02c_valid_vectors = _load_object(
        root, PH_D02C_VALID_VECTORS_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_valid_vectors,
            "hds-valid-ir-vector-set",
            "content_digest",
            "ph_d02c_valid_vectors",
        )
    )
    ph_d02c_invalid_vectors = _load_object(
        root, PH_D02C_INVALID_VECTORS_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_invalid_vectors,
            "hds-invalid-ir-vector-set",
            "content_digest",
            "ph_d02c_invalid_vectors",
        )
    )
    if (
        ph_d02c_valid_vectors.get("vector_count") != 51
        or ph_d02c_valid_vectors.get("synthetic_fixture_only") is not True
        or ph_d02c_invalid_vectors.get("vector_count") != 15
        or ph_d02c_invalid_vectors.get("synthetic_fixture_only") is not True
    ):
        failures.append("ph_d02c_vectors:INVENTORY_MISMATCH")

    ph_d02c_conformance = _load_object(
        root, PH_D02C_CONFORMANCE_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d02c_conformance,
            "hds-causal-ir-conformance",
            "content_digest",
            "ph_d02c_conformance",
        )
    )
    failures.extend(
        _canonical_document_failures(
            root,
            PH_D02C_CONFORMANCE_PATH,
            "ph_d02c_conformance",
        )
    )
    expected_d02c_gates = {
        "DG-03": "PASS_TYPED_EXECUTABLE_IR_AND_STABLE_ERRORS",
        "DG-08": "PASS_PRIVILEGED_ROUTING_REJECTED",
        "DG-09": "PASS_PREDICTIVE_SCOPE_NO_CAUSAL_OVERCLAIM",
        "DG-12": "PASS_RESOURCE_OVERFLOW_SUSPENDS",
    }
    resource_suspension = ph_d02c_conformance.get(
        "resource_suspension"
    )
    synthetic_intervention = ph_d02c_conformance.get(
        "synthetic_intervention"
    )
    if (
        ph_d02c_conformance.get("phase_id") != "PH-D02C"
        or ph_d02c_conformance.get("synthetic_fixture_only") is not True
        or ph_d02c_conformance.get("owner_approval_generated") is not False
        or ph_d02c_conformance.get("valid_vector_count") != 51
        or ph_d02c_conformance.get("valid_vector_pass_count") != 51
        or ph_d02c_conformance.get("invalid_vector_count") != 15
        or ph_d02c_conformance.get("invalid_vector_pass_count") != 15
        or ph_d02c_conformance.get("gate_results") != expected_d02c_gates
        or not isinstance(resource_suspension, dict)
        or resource_suspension.get("status") != "SUSPEND_RESOURCE"
        or resource_suspension.get("assertion_state") != "SUSPEND"
        or resource_suspension.get("operation_state") != "HOLD"
        or resource_suspension.get("evidence_state") != "INCONCLUSIVE"
        or not isinstance(synthetic_intervention, dict)
        or synthetic_intervention.get("execution_scope") != "SYNTHETIC_ONLY"
        or synthetic_intervention.get("causal_claim") is not None
    ):
        failures.append("ph_d02c_conformance:GATE_MISMATCH")
    d02c_boundaries = ph_d02c_conformance.get("phase_boundaries")
    if not isinstance(d02c_boundaries, dict) or any(
        d02c_boundaries.get(field) not in (0, False)
        for field in (
            "candidate_generation_started",
            "causal_mechanism_assertion_count",
            "golden_freeze_started",
            "kaggle_mutation_count",
            "locked_final_access_count",
            "official_access_count",
            "real_intervention_execution_count",
            "real_trajectory_normalization_count",
            "rule_promotion_count",
            "sealed_corpus_started",
            "source_payload_read_count",
        )
    ):
        failures.append("ph_d02c_conformance:BOUNDARY_ESCALATED")

    ph_d03a_frame = _load_object(root, PH_D03A_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d03a_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d03a_frame",
        )
    )
    if (
        ph_d03a_frame.get("phase_id") != "PH-D03A"
        or ph_d03a_frame.get("base_commit")
        != "70722de7df8278c866de0734c97206c9952d731d"
        or ph_d03a_frame.get("base_tree")
        != "fd330c8fd8dd9cb66e16d12cbcde14452a28aa6f"
    ):
        failures.append("ph_d03a_frame:PHASE_OR_BASE_MISMATCH")
    ph_d03a_budget = ph_d03a_frame.get("resource_budget")
    if not isinstance(ph_d03a_budget, dict):
        failures.append("ph_d03a_frame:RESOURCE_BUDGET_MISSING")
    else:
        if (
            ph_d03a_budget.get("required_arc2_case_count"),
            ph_d03a_budget.get("required_arc3_case_count"),
            ph_d03a_budget.get("required_total_case_count"),
            ph_d03a_budget.get("required_gate_count"),
            ph_d03a_budget.get("required_checked_artifact_count"),
            ph_d03a_budget.get("independent_process_rebuild_count"),
        ) != (8, 8, 16, 16, 4, 3):
            failures.append("ph_d03a_frame:CANDIDATE_BUDGET_MISMATCH")
        for field in (
            "source_payload_read_count",
            "source_payload_semantic_parse_count",
            "teacher_trajectory_read_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "real_intervention_execution_count",
            "general_candidate_generation_count",
            "owner_approval_generated_count",
            "golden_expected_artifact_freeze_count",
            "sealed_corpus_artifact_count",
            "rule_promotion_count",
            "bridge_runtime_capability_count",
            "external_network_call_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d03a_budget.get(field) != 0:
                failures.append(f"ph_d03a_frame:{field}:NONZERO")
        if ph_d03a_budget.get("external_network_use") != "NONE":
            failures.append("ph_d03a_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d03a_transition = _load_object(root, PH_D03A_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d03a_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d03a_transition",
        )
    )
    if (
        ph_d03a_transition.get("from_phase_id"),
        ph_d03a_transition.get("to_phase_id"),
        ph_d03a_transition.get("decision"),
    ) != ("PH-D02C", "PH-D03A", "ENTRY_AUTHORIZED"):
        failures.append("ph_d03a_transition:SEQUENCE_MISMATCH")
    if (
        ph_d03a_transition.get("authorization_digest")
        != ph_d02c_result_approval.get("approval_artifact_digest")
        or ph_d03a_transition.get("from_phase_state_sha256")
        != ph_d02c_attestation.get("phase_state_sha256")
        or ph_d03a_transition.get("from_phase_evidence_commit")
        != ph_d02c_attestation.get("evidence_commit")
        or ph_d03a_transition.get("from_phase_evidence_tree")
        != ph_d02c_attestation.get("evidence_tree")
        or ph_d03a_transition.get(
            "from_phase_evidence_payload_digest"
        )
        != ph_d02c_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d03a_transition:EVIDENCE_BINDING_MISMATCH")
    if (
        ph_d03a_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d03a_transition:EXTERNAL_ACTION_AUTHORIZED")

    ph_d03a_preinventory = _load_object(
        root, PH_D03A_PREINVENTORY_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d03a_preinventory,
            "rev3-ph-d03a-post-audit-golden-preinventory:",
            "content_digest",
            "ph_d03a_preinventory",
        )
    )
    preinventory_authority = ph_d03a_preinventory.get("authority")
    if (
        ph_d03a_preinventory.get("phase_id") != "PH-D03A"
        or ph_d03a_preinventory.get("base_commit")
        != ph_d03a_frame.get("base_commit")
        or ph_d03a_preinventory.get("base_tree")
        != ph_d03a_frame.get("base_tree")
        or not isinstance(preinventory_authority, dict)
        or preinventory_authority.get("input_phase_state_sha256")
        != ph_d02c_attestation.get("phase_state_sha256")
        or preinventory_authority.get("input_evidence_payload_digest")
        != ph_d02c_attestation.get("evidence_payload_digest")
        or preinventory_authority.get("phase_entry_approval_digest")
        != ph_d02c_result_approval.get("approval_artifact_digest")
        or ph_d03a_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("aggregate_sha256")
        != "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    ):
        failures.append("ph_d03a_preinventory:BOUNDARY_MISMATCH")

    ph_d03a_snapshot = _load_object(
        root, PH_D03A_SNAPSHOT_MANIFEST_PATH
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d03a_snapshot,
            "hds-ph-d03a-historical-snapshot",
            "content_digest",
            "ph_d03a_snapshot",
        )
    )
    snapshot_entries = ph_d03a_snapshot.get("entries")
    snapshot_root = (
        root / "distillation/input/historical_pre_audit/PH-D03A"
    )
    if (
        ph_d03a_snapshot.get("phase_id") != "PH-D03A"
        or ph_d03a_snapshot.get("source_commit")
        != "70722de7df8278c866de0734c97206c9952d731d"
        or ph_d03a_snapshot.get("artifact_count") != 6
        or ph_d03a_snapshot.get("eligible_for_current_activation")
        is not False
        or not isinstance(snapshot_entries, list)
        or len(snapshot_entries) != 6
    ):
        failures.append("ph_d03a_snapshot:INVENTORY_MISMATCH")
    else:
        for item in snapshot_entries:
            if not isinstance(item, dict):
                failures.append("ph_d03a_snapshot:ITEM_INVALID")
                continue
            source_path = item.get("source_path")
            snapshot_path = item.get("snapshot_path")
            expected_sha = item.get("sha256")
            destination = (
                snapshot_root / snapshot_path
                if isinstance(snapshot_path, str)
                else None
            )
            source_bytes = (
                _git_blob(
                    root,
                    "70722de7df8278c866de0734c97206c9952d731d",
                    source_path,
                )
                if isinstance(source_path, str)
                else None
            )
            if (
                destination is None
                or not destination.is_file()
                or source_bytes is None
                or hashlib.sha256(destination.read_bytes()).hexdigest()
                != expected_sha
                or hashlib.sha256(source_bytes).hexdigest()
                != expected_sha
            ):
                failures.append(
                    "ph_d03a_snapshot:ARTIFACT_BYTES_MISMATCH:"
                    + str(source_path)
                )

    ph_d03a_contract = _load_object(root, PH_D03A_CONTRACT_PATH)
    ph_d03a_candidate = _load_object(root, PH_D03A_CANDIDATE_SET_PATH)
    ph_d03a_coverage = _load_object(root, PH_D03A_COVERAGE_PATH)
    ph_d03a_review = _load_object(root, PH_D03A_REVIEW_REQUEST_PATH)
    for value, path, namespace, location in (
        (
            ph_d03a_contract,
            PH_D03A_CONTRACT_PATH,
            "hds-golden-conformance-contract",
            "ph_d03a_contract",
        ),
        (
            ph_d03a_candidate,
            PH_D03A_CANDIDATE_SET_PATH,
            "hds-golden-candidate-set",
            "ph_d03a_candidate",
        ),
        (
            ph_d03a_coverage,
            PH_D03A_COVERAGE_PATH,
            "hds-golden-gate-coverage",
            "ph_d03a_coverage",
        ),
        (
            ph_d03a_review,
            PH_D03A_REVIEW_REQUEST_PATH,
            "hds-golden-owner-review-request",
            "ph_d03a_review",
        ),
    ):
        failures.extend(
            _domain_content_digest_failures(
                value,
                namespace,
                "content_digest",
                location,
            )
        )
        failures.extend(
            _canonical_document_failures(root, path, location)
        )
    golden_authority = ph_d03a_contract.get("authority")
    if (
        ph_d03a_contract.get("phase_id") != "PH-D03A"
        or ph_d03a_contract.get("candidate_state")
        != "PROPOSED_PENDING_OWNER_APPROVAL"
        or ph_d03a_contract.get("required_arc2_case_count") != 8
        or ph_d03a_contract.get("required_arc3_case_count") != 8
        or ph_d03a_contract.get("required_total_case_count") != 16
        or not isinstance(golden_authority, dict)
        or golden_authority.get("work_block_frame_digest")
        != ph_d03a_frame.get("content_digest")
        or golden_authority.get("preinventory_digest")
        != ph_d03a_preinventory.get("content_digest")
        or golden_authority.get("phase_transition_digest")
        != ph_d03a_transition.get("content_digest")
        or golden_authority.get("phase_entry_approval_digest")
        != ph_d02c_result_approval.get("approval_artifact_digest")
        or golden_authority.get("input_phase_state_sha256")
        != "sha256:" + str(ph_d02c_attestation.get("phase_state_sha256"))
        or golden_authority.get("input_evidence_payload_digest")
        != ph_d02c_attestation.get("evidence_payload_digest")
        or golden_authority.get("schema_contract_digest")
        != ph_d02c_schema_contract.get("content_digest")
        or golden_authority.get("causal_ir_contract_digest")
        != ph_d02c_ir_contract.get("content_digest")
    ):
        failures.append("ph_d03a_contract:AUTHORITY_OR_INVENTORY_MISMATCH")
    candidate_cases = ph_d03a_candidate.get("cases")
    if (
        ph_d03a_candidate.get("phase_id") != "PH-D03A"
        or ph_d03a_candidate.get("candidate_state")
        != "PROPOSED_PENDING_OWNER_APPROVAL"
        or ph_d03a_candidate.get("arc2_case_count") != 8
        or ph_d03a_candidate.get("arc3_case_count") != 8
        or ph_d03a_candidate.get("case_count") != 16
        or ph_d03a_candidate.get(
            "content_specific_owner_approval_count"
        )
        != 0
        or ph_d03a_candidate.get("golden_frozen_case_count") != 0
        or ph_d03a_candidate.get("sealed_case_count") != 0
        or not isinstance(candidate_cases, list)
        or len(candidate_cases) != 16
    ):
        failures.append("ph_d03a_candidate:INVENTORY_OR_BOUNDARY_MISMATCH")
    gate_entries = ph_d03a_coverage.get("gate_entries")
    if (
        ph_d03a_coverage.get("phase_id") != "PH-D03A"
        or ph_d03a_coverage.get("gate_count") != 16
        or ph_d03a_coverage.get("covered_gate_count") != 16
        or ph_d03a_coverage.get(
            "behaviorally_recomputed_gate_count"
        )
        != 16
        or ph_d03a_coverage.get(
            "declarative_gate_result_trusted"
        )
        is not False
        or ph_d03a_coverage.get("coverage_complete") is not True
        or ph_d03a_coverage.get("fail_result_count") != 0
        or not isinstance(gate_entries, list)
        or len(gate_entries) != 16
    ):
        failures.append("ph_d03a_coverage:GATE_MISMATCH")
    elif any(
        not isinstance(item, dict)
        or not isinstance(item.get("obligation_evidence"), dict)
        or item["obligation_evidence"].get("recomputed") is not True
        or item["obligation_evidence"].get(
            "declarative_gate_result_trusted"
        )
        is not False
        or len(item["obligation_evidence"].get("check_ids", [])) != 2
        for item in gate_entries
    ):
        failures.append("ph_d03a_coverage:OBLIGATION_EVIDENCE_MISMATCH")
    if (
        ph_d03a_review.get("phase_id") != "PH-D03A"
        or ph_d03a_review.get("target_count") != 16
        or ph_d03a_review.get("owner_decision_present") is not False
        or ph_d03a_review.get("owner_approval_generated") is not False
        or ph_d03a_review.get("golden_freeze_started") is not False
        or ph_d03a_review.get("sealed_corpus_started") is not False
        or ph_d03a_review.get(
            "automatic_expectation_update_allowed"
        )
        is not False
    ):
        failures.append("ph_d03a_review:AUTHORITY_BOUNDARY_MISMATCH")

    distillation_source = root / "distillation" / "src"
    source_text = str(distillation_source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    try:
        from hds_distill.golden_corpus import (
            build_phase_d03a_candidate_artifacts,
        )

        rebuilt_golden = build_phase_d03a_candidate_artifacts(root)
    except Exception as exc:  # fail closed and preserve stable report shape
        failures.append(
            "ph_d03a_rebuild:EXCEPTION:" + type(exc).__name__
        )
    else:
        if set(rebuilt_golden) != {
            PH_D03A_CONTRACT_PATH.as_posix(),
            PH_D03A_CANDIDATE_SET_PATH.as_posix(),
            PH_D03A_COVERAGE_PATH.as_posix(),
            PH_D03A_REVIEW_REQUEST_PATH.as_posix(),
        }:
            failures.append("ph_d03a_rebuild:INVENTORY_MISMATCH")
        for relative_path, payload in rebuilt_golden.items():
            if (root / relative_path).read_bytes() != payload:
                failures.append(
                    "ph_d03a_rebuild:BYTES_MISMATCH:" + relative_path
                )

    ph_d03b_frame = _load_object(root, PH_D03B_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d03b_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d03b_frame",
        )
    )
    if (
        ph_d03b_frame.get("phase_id") != "PH-D03B"
        or ph_d03b_frame.get("base_commit")
        != "4b4a89bc5cc25f166296a491baf8f12ed30babdf"
        or ph_d03b_frame.get("base_tree")
        != "15c41b03761b4e6bdc1ddfad235844815d52c447"
    ):
        failures.append("ph_d03b_frame:PHASE_OR_BASE_MISMATCH")
    ph_d03b_budget = ph_d03b_frame.get("resource_budget")
    if not isinstance(ph_d03b_budget, dict):
        failures.append("ph_d03b_frame:RESOURCE_BUDGET_MISSING")
    else:
        if (
            ph_d03b_budget.get("required_expected_commitment_count"),
            ph_d03b_budget.get("required_source_artifact_count"),
            ph_d03b_budget.get("required_checked_artifact_count"),
            ph_d03b_budget.get("independent_process_rebuild_count"),
            ph_d03b_budget.get("required_gate_count"),
            ph_d03b_budget.get("required_gate_ids"),
        ) != (16, 7, 5, 3, 2, ["DG-06", "DG-14"]):
            failures.append("ph_d03b_frame:SEALED_BUDGET_MISMATCH")
        for field in (
            "actual_sealed_corpus_execution_count",
            "expected_plaintext_stored_count",
            "runtime_dependency_addition_count",
            "source_payload_read_count",
            "source_payload_semantic_parse_count",
            "teacher_trajectory_read_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "real_intervention_execution_count",
            "general_candidate_generation_count",
            "rule_promotion_count",
            "bridge_runtime_capability_count",
            "llm_call_count",
            "external_network_call_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d03b_budget.get(field) != 0:
                failures.append(f"ph_d03b_frame:{field}:NONZERO")
        if ph_d03b_budget.get("external_network_use") != "NONE":
            failures.append("ph_d03b_frame:EXTERNAL_NETWORK_ENABLED")

    ph_d03b_transition = _load_object(root, PH_D03B_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d03b_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d03b_transition",
        )
    )
    if (
        ph_d03b_transition.get("from_phase_id"),
        ph_d03b_transition.get("to_phase_id"),
        ph_d03b_transition.get("decision"),
    ) != ("PH-D03A", "PH-D03B", "ENTRY_AUTHORIZED"):
        failures.append("ph_d03b_transition:SEQUENCE_MISMATCH")
    if (
        ph_d03b_transition.get("authorization_digest")
        != ph_d03a_result_approval.get("approval_artifact_digest")
        or ph_d03b_transition.get("decision_capture_digest")
        != ph_d03a_result_decision.get("owner_decision_content_digest")
        or ph_d03b_transition.get("from_phase_state_sha256")
        != ph_d03a_attestation.get("phase_state_sha256")
        or ph_d03b_transition.get("from_phase_evidence_commit")
        != ph_d03a_attestation.get("evidence_commit")
        or ph_d03b_transition.get("from_phase_evidence_tree")
        != ph_d03a_attestation.get("evidence_tree")
        or ph_d03b_transition.get(
            "from_phase_evidence_payload_digest"
        )
        != ph_d03a_attestation.get("evidence_payload_digest")
        or ph_d03b_transition.get(
            "from_phase_exact_target_bundle_digest"
        )
        != ph_d03a_target_bundle.get("content_digest")
        or ph_d03b_transition.get(
            "external_irreversible_action_authorized"
        )
        is not False
    ):
        failures.append("ph_d03b_transition:EVIDENCE_BINDING_MISMATCH")

    ph_d03b_preinventory = _load_object(
        root, PH_D03B_PREINVENTORY_PATH
    )
    failures.extend(
        _content_digest_failures(
            ph_d03b_preinventory,
            "rev3-ph-d03b-sealed-audit-preinventory:",
            "content_digest",
            "ph_d03b_preinventory",
        )
    )
    d03b_preinventory_authority = ph_d03b_preinventory.get("authority")
    d03b_implementation_plan = ph_d03b_preinventory.get(
        "implementation_plan"
    )
    if (
        ph_d03b_preinventory.get("phase_id") != "PH-D03B"
        or ph_d03b_preinventory.get("base_commit")
        != ph_d03b_frame.get("base_commit")
        or ph_d03b_preinventory.get("base_tree")
        != ph_d03b_frame.get("base_tree")
        or not isinstance(d03b_preinventory_authority, dict)
        or d03b_preinventory_authority.get("input_evidence_commit")
        != ph_d03a_attestation.get("evidence_commit")
        or d03b_preinventory_authority.get(
            "input_evidence_payload_digest"
        )
        != ph_d03a_attestation.get("evidence_payload_digest")
        or d03b_preinventory_authority.get("exact_target_bundle_digest")
        != ph_d03a_target_bundle.get("content_digest")
        or d03b_preinventory_authority.get(
            "phase_entry_decision_digest"
        )
        != ph_d03a_result_decision.get("owner_decision_content_digest")
        or d03b_preinventory_authority.get(
            "phase_entry_approval_digest"
        )
        != ph_d03a_result_approval.get("approval_artifact_digest")
        or not isinstance(d03b_implementation_plan, dict)
        or d03b_implementation_plan.get("checked_artifact_count") != 5
        or ph_d03b_preinventory.get(
            "preexisting_dirty_state", {}
        ).get("aggregate_sha256")
        != "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    ):
        failures.append("ph_d03b_preinventory:BOUNDARY_MISMATCH")

    ph_d03b_contract = _load_object(root, PH_D03B_CONTRACT_PATH)
    ph_d03b_commitments = _load_object(root, PH_D03B_COMMITMENTS_PATH)
    ph_d03b_manifest = _load_object(root, PH_D03B_MANIFEST_PATH)
    ph_d03b_runner = _load_object(root, PH_D03B_RUNNER_CONTRACT_PATH)
    ph_d03b_report = _load_object(root, PH_D03B_FREEZE_REPORT_PATH)
    for value, path, namespace, location in (
        (
            ph_d03b_contract,
            PH_D03B_CONTRACT_PATH,
            "hds-sealed-audit-contract",
            "ph_d03b_contract",
        ),
        (
            ph_d03b_commitments,
            PH_D03B_COMMITMENTS_PATH,
            "hds-sealed-expected-commitment-set",
            "ph_d03b_commitments",
        ),
        (
            ph_d03b_manifest,
            PH_D03B_MANIFEST_PATH,
            "hds-sealed-audit-manifest",
            "ph_d03b_manifest",
        ),
        (
            ph_d03b_runner,
            PH_D03B_RUNNER_CONTRACT_PATH,
            "hds-sealed-audit-runner-contract",
            "ph_d03b_runner",
        ),
        (
            ph_d03b_report,
            PH_D03B_FREEZE_REPORT_PATH,
            "hds-sealed-audit-freeze-report",
            "ph_d03b_report",
        ),
    ):
        failures.extend(
            _domain_content_digest_failures(
                value,
                namespace,
                "content_digest",
                location,
            )
        )
        failures.extend(
            _canonical_document_failures(root, path, location)
        )

    sealed_authority = ph_d03b_contract.get("authority")
    freeze_contract = ph_d03b_contract.get("freeze_contract")
    if (
        ph_d03b_contract.get("phase_id") != "PH-D03B"
        or ph_d03b_contract.get("corpus_version") != "ph-d03b-v1"
        or not isinstance(sealed_authority, dict)
        or sealed_authority.get("work_block_frame_digest")
        != ph_d03b_frame.get("content_digest")
        or sealed_authority.get("preinventory_digest")
        != ph_d03b_preinventory.get("content_digest")
        or sealed_authority.get("phase_transition_digest")
        != ph_d03b_transition.get("content_digest")
        or sealed_authority.get("input_evidence_commit")
        != ph_d03a_attestation.get("evidence_commit")
        or sealed_authority.get("input_evidence_payload_digest")
        != ph_d03a_attestation.get("evidence_payload_digest")
        or sealed_authority.get("exact_target_bundle_digest")
        != ph_d03a_target_bundle.get("content_digest")
        or sealed_authority.get(
            "content_specific_owner_decision_digest"
        )
        != ph_d03a_result_decision.get("owner_decision_content_digest")
        or sealed_authority.get(
            "content_specific_owner_approval_digest"
        )
        != ph_d03a_result_approval.get("approval_artifact_digest")
        or not isinstance(freeze_contract, dict)
        or freeze_contract.get("expected_commitment_count") != 16
        or freeze_contract.get("expected_plaintext_stored_count") != 0
        or freeze_contract.get(
            "automatic_expectation_update_allowed"
        )
        is not False
    ):
        failures.append("ph_d03b_contract:AUTHORITY_OR_BOUNDARY_MISMATCH")

    raw_commitments = ph_d03b_commitments.get("commitments")
    if (
        ph_d03b_commitments.get("phase_id") != "PH-D03B"
        or ph_d03b_commitments.get("commitment_count") != 16
        or ph_d03b_commitments.get("fixture_identifier_count") != 0
        or ph_d03b_commitments.get("expected_plaintext_stored_count") != 0
        or not isinstance(raw_commitments, list)
        or len(raw_commitments) != 16
        or len(set(str(item) for item in raw_commitments)) != 16
        or raw_commitments != sorted(raw_commitments)
        or _contains_json_key(
            ph_d03b_commitments,
            frozenset(
                {
                    "expected_artifact",
                    "expected_payload",
                    "fixture_id",
                    "provisional_expected_artifact",
                }
            ),
        )
    ):
        failures.append("ph_d03b_commitments:INVENTORY_OR_DISCLOSURE")

    source_artifacts = ph_d03b_manifest.get("source_artifacts")
    sealed_artifacts = ph_d03b_manifest.get("sealed_artifacts")
    if (
        ph_d03b_manifest.get("freeze_status")
        != "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
        or ph_d03b_manifest.get("version_state") != "FROZEN_UNCONSUMED"
        or ph_d03b_manifest.get("source_artifact_count") != 7
        or ph_d03b_manifest.get("expected_commitment_count") != 16
        or ph_d03b_manifest.get("expected_plaintext_stored_count") != 0
        or ph_d03b_manifest.get("actual_audit_consumption_count") != 0
        or ph_d03b_manifest.get("runner_output_contract")
        != "PASS_OR_FAIL_ONLY"
        or not isinstance(source_artifacts, list)
        or len(source_artifacts) != 7
        or not isinstance(sealed_artifacts, list)
        or len(sealed_artifacts) != 3
    ):
        failures.append("ph_d03b_manifest:INVENTORY_OR_BOUNDARY_MISMATCH")

    runner_output = ph_d03b_runner.get("output_contract")
    runner_consumption = ph_d03b_runner.get("consumption_contract")
    if (
        ph_d03b_runner.get("commitment_set_digest")
        != ph_d03b_commitments.get("content_digest")
        or not isinstance(runner_output, dict)
        or runner_output.get("allowed_stdout_bytes_hex")
        != ["4641494c0a", "504153530a"]
        or runner_output.get("allowed_values") != ["FAIL", "PASS"]
        or runner_output.get("additional_fields_allowed") is not False
        or runner_output.get("stderr_allowed") is not False
        or not isinstance(runner_consumption, dict)
        or runner_consumption.get("policy")
        != "CONSUME_ON_FIRST_AUDIT_ATTEMPT"
        or runner_consumption.get("atomic_reservation_required") is not True
        or runner_consumption.get("ledger_must_be_outside_repository")
        is not True
    ):
        failures.append("ph_d03b_runner:DISCLOSURE_OR_CONSUMPTION_MISMATCH")

    sealed_gate_entries = ph_d03b_report.get("gate_entries")
    if (
        ph_d03b_report.get("status") != "PASS"
        or ph_d03b_report.get("exit_state")
        != "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
        or ph_d03b_report.get("failed_requirement_count") != 0
        or ph_d03b_report.get("actual_sealed_corpus_execution_count") != 0
        or ph_d03b_report.get("manifest_digest")
        != ph_d03b_manifest.get("content_digest")
        or not isinstance(sealed_gate_entries, list)
        or [
            item.get("gate_id")
            for item in sealed_gate_entries
            if isinstance(item, dict)
        ]
        != ["DG-06", "DG-14"]
        or any(
            not isinstance(item, dict)
            or item.get("result") != "PASS"
            or item.get("behaviorally_recomputed") is not True
            for item in sealed_gate_entries
        )
    ):
        failures.append("ph_d03b_report:GATE_OR_BOUNDARY_MISMATCH")

    try:
        from hds_distill.sealed_audit import (
            build_phase_d03b_artifacts,
        )

        rebuilt_sealed = build_phase_d03b_artifacts(root)
    except Exception as exc:  # fail closed and preserve stable report shape
        failures.append(
            "ph_d03b_rebuild:EXCEPTION:" + type(exc).__name__
        )
    else:
        if set(rebuilt_sealed) != {
            PH_D03B_CONTRACT_PATH.as_posix(),
            PH_D03B_COMMITMENTS_PATH.as_posix(),
            PH_D03B_MANIFEST_PATH.as_posix(),
            PH_D03B_RUNNER_CONTRACT_PATH.as_posix(),
            PH_D03B_FREEZE_REPORT_PATH.as_posix(),
        }:
            failures.append("ph_d03b_rebuild:INVENTORY_MISMATCH")
        for relative_path, payload in rebuilt_sealed.items():
            if (root / relative_path).read_bytes() != payload:
                failures.append(
                    "ph_d03b_rebuild:BYTES_MISMATCH:" + relative_path
                )

    ph_d03b_attestation = _load_object(
        root, PH_D03B_EVIDENCE_ATTESTATION_PATH
    )
    ph_d03b_attestation_core = (
        {
            key: value
            for key, value in ph_d03b_attestation.items()
            if key in attestation_properties
        }
        if isinstance(attestation_properties, dict)
        else {}
    )
    failures.extend(
        _schema_failures(
            ph_d03b_attestation_core,
            attestation_schema,
            "ph_d03b_attestation",
        )
    )
    ph_d03b_phase_state = _load_object(root, PH_D03B_PHASE_STATE_PATH)
    if (
        ph_d03b_attestation.get("phase_id") != "PH-D03B"
        or ph_d03b_attestation.get("implementation_commit")
        != ph_d03b_phase_state.get("implementation_commit")
        or ph_d03b_attestation.get("implementation_tree")
        != ph_d03b_phase_state.get("implementation_tree")
        or ph_d03b_attestation.get("evidence_payload_digest")
        != ph_d03b_phase_state.get("evidence_payload_digest")
        or ph_d03b_attestation.get("phase_state_sha256")
        != hashlib.sha256(
            (root / PH_D03B_PHASE_STATE_PATH).read_bytes()
        ).hexdigest()
        or not _git_object_exists(
            root, str(ph_d03b_attestation.get("implementation_commit"))
        )
        or not _git_object_exists(
            root, str(ph_d03b_attestation.get("evidence_commit"))
        )
    ):
        failures.append("ph_d03b_attestation:EVIDENCE_BINDING_MISMATCH")

    ph_d03b_result_decision = _load_object(
        root, PH_D03B_RESULT_DECISION_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d03b_result_decision,
            decision_v2_schema,
            "ph_d03b_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d03b_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d03b_result_decision",
        )
    )
    if (
        ph_d03b_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d03b_result_decision.get("target_evidence_commit")
        != ph_d03b_attestation.get("evidence_commit")
        or ph_d03b_result_decision.get("target_artifact_digest")
        != ph_d03b_attestation.get("evidence_payload_digest")
        or ph_d03b_result_decision.get("gate_result_digest")
        != ph_d03b_report.get("content_digest")
        or ph_d03b_result_decision.get("gate_status") != "PASS"
        or ph_d03b_result_decision.get("allowed_transition")
        != "PH-D03B_TO_PH-D05"
    ):
        failures.append(
            "ph_d03b_result_decision:ATTESTATION_BINDING_MISMATCH"
        )

    ph_d03b_result_approval = _load_object(
        root, PH_D03B_RESULT_APPROVAL_PATH
    )
    failures.extend(
        _schema_failures(
            ph_d03b_result_approval,
            approval_schema,
            "ph_d03b_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d03b_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d03b_result_approval",
        )
    )
    if (
        ph_d03b_result_approval.get("owner_decision_capture_digest")
        != ph_d03b_result_decision.get("owner_decision_content_digest")
        or ph_d03b_result_approval.get("target_evidence_commit")
        != ph_d03b_attestation.get("evidence_commit")
        or ph_d03b_result_approval.get("target_artifact_digest")
        != ph_d03b_attestation.get("evidence_payload_digest")
        or ph_d03b_result_approval.get("approved_transition")
        != "PH-D03B_TO_PH-D05"
        or ph_d03b_result_approval.get("next_phase_id") != "PH-D05"
        or ph_d03b_result_approval.get("next_phase_authorized") is not True
    ):
        failures.append(
            "ph_d03b_result_approval:DECISION_OR_TARGET_MISMATCH"
        )

    ph_d05_frame = _load_object(root, PH_D05_FRAME_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d05_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d05_frame",
        )
    )
    ph_d05_budget = ph_d05_frame.get("resource_budget")
    if (
        ph_d05_frame.get("phase_id") != "PH-D05"
        or ph_d05_frame.get("base_commit")
        != "e97f725dafca65c50963c367df58e875e81cb999"
        or ph_d05_frame.get("base_tree")
        != "7eb4cbd84edbc17e2bcebdfc1baac176721aa1eb"
        or not isinstance(ph_d05_budget, dict)
        or (
            ph_d05_budget.get("required_raw_recording_count"),
            ph_d05_budget.get("required_game_count"),
            ph_d05_budget.get("required_level_count"),
            ph_d05_budget.get("required_source_recorded_action_count"),
            ph_d05_budget.get("required_canonical_success_prefix_action_count"),
            ph_d05_budget.get("independent_replay_process_count"),
            ph_d05_budget.get("required_gate_ids"),
        )
        != (
            25,
            25,
            183,
            11648,
            11574,
            3,
            ["DG-00", "DG-06", "DG-10", "DG-11", "DG-12"],
        )
    ):
        failures.append("ph_d05_frame:PHASE_BASE_OR_BUDGET_MISMATCH")
    if isinstance(ph_d05_budget, dict):
        for field in (
            "runtime_dependency_addition_count",
            "real_intervention_execution_count",
            "general_candidate_generation_count",
            "rule_promotion_count",
            "bridge_runtime_capability_count",
            "llm_call_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
        ):
            if ph_d05_budget.get(field) != 0:
                failures.append(f"ph_d05_frame:{field}:NONZERO")

    ph_d05_transition = _load_object(root, PH_D05_TRANSITION_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d05_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d05_transition",
        )
    )
    if (
        (
            ph_d05_transition.get("from_phase_id"),
            ph_d05_transition.get("to_phase_id"),
            ph_d05_transition.get("decision"),
        )
        != ("PH-D03B", "PH-D05", "ENTRY_AUTHORIZED")
        or ph_d05_transition.get("authorization_digest")
        != ph_d03b_result_approval.get("approval_artifact_digest")
        or ph_d05_transition.get("decision_capture_digest")
        != ph_d03b_result_decision.get("owner_decision_content_digest")
        or ph_d05_transition.get("from_phase_state_sha256")
        != ph_d03b_attestation.get("phase_state_sha256")
        or ph_d05_transition.get("from_phase_evidence_commit")
        != ph_d03b_attestation.get("evidence_commit")
        or ph_d05_transition.get("from_phase_evidence_tree")
        != ph_d03b_attestation.get("evidence_tree")
        or ph_d05_transition.get("from_phase_evidence_payload_digest")
        != ph_d03b_attestation.get("evidence_payload_digest")
        or ph_d05_transition.get("external_irreversible_action_authorized")
        is not False
    ):
        failures.append("ph_d05_transition:EVIDENCE_BINDING_MISMATCH")

    ph_d05_preinventory = _load_object(root, PH_D05_PREINVENTORY_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d05_preinventory,
            "rev3-ph-d05-teacher-trajectory-preinventory:",
            "content_digest",
            "ph_d05_preinventory",
        )
    )
    if (
        ph_d05_preinventory.get("phase_id") != "PH-D05"
        or ph_d05_preinventory.get("base_commit")
        != ph_d05_frame.get("base_commit")
        or ph_d05_preinventory.get("base_tree")
        != ph_d05_frame.get("base_tree")
        or ph_d05_preinventory.get("preexisting_dirty_state", {}).get(
            "aggregate_sha256"
        )
        != "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    ):
        failures.append("ph_d05_preinventory:BOUNDARY_MISMATCH")

    ph_d05_contract = _load_object(root, PH_D05_CONTRACT_PATH)
    ph_d05_acquisition = _load_object(root, PH_D05_ACQUISITION_REPORT_PATH)
    ph_d05_replay = _load_object(root, PH_D05_REPLAY_X3_REPORT_PATH)
    ph_d05_manifest = _load_object(root, PH_D05_MANIFEST_PATH)
    ph_d05_normalization = _load_object(
        root, PH_D05_NORMALIZATION_REPORT_PATH
    )
    ph_d05_rebuild = _load_object(root, PH_D05_REBUILD_X3_PATH)
    failures.extend(
        _domain_content_digest_failures(
            ph_d05_contract,
            "hds-arc3-teacher-trajectory-normalization-contract",
            "content_digest",
            "ph_d05_contract",
        )
    )
    failures.extend(
        _domain_content_digest_failures(
            ph_d05_manifest,
            "hds-arc3-canonical-teacher-corpus-manifest",
            "content_digest",
            "ph_d05_manifest",
        )
    )
    for value, namespace, location in (
        (
            ph_d05_acquisition,
            "hds-arc3-teacher-recording-acquisition:",
            "ph_d05_acquisition",
        ),
        (
            ph_d05_normalization,
            "hds-arc3-teacher-trajectory-normalization-report:",
            "ph_d05_normalization",
        ),
        (
            ph_d05_rebuild,
            "hds-arc3-canonical-trajectory-rebuild-x3:",
            "ph_d05_rebuild",
        ),
    ):
        failures.extend(
            _content_digest_failures(
                value,
                namespace,
                "content_digest",
                location,
            )
        )
    ph_d05_replay_body = dict(ph_d05_replay)
    ph_d05_replay_body.pop("content_digest", None)
    if ph_d05_replay.get("content_digest") != (
        "hds-arc3-replay-x3:" + digest_object(ph_d05_replay_body)
    ):
        failures.append("ph_d05_replay:CONTENT_DIGEST_MISMATCH")
    for path, location in (
        (PH_D05_CONTRACT_PATH, "ph_d05_contract"),
        (PH_D05_ACQUISITION_REPORT_PATH, "ph_d05_acquisition"),
        (PH_D05_REPLAY_X3_REPORT_PATH, "ph_d05_replay"),
        (PH_D05_NORMALIZATION_REPORT_PATH, "ph_d05_normalization"),
        (PH_D05_MANIFEST_PATH, "ph_d05_manifest"),
        (PH_D05_REBUILD_X3_PATH, "ph_d05_rebuild"),
    ):
        failures.extend(_canonical_document_failures(root, path, location))

    contract_authority = ph_d05_contract.get("authority")
    contract_source = ph_d05_contract.get("source_contract")
    contract_output = ph_d05_contract.get("output_contract")
    if (
        ph_d05_contract.get("phase_id") != "PH-D05"
        or not isinstance(contract_authority, dict)
        or contract_authority.get("work_block_frame_digest")
        != ph_d05_frame.get("content_digest")
        or contract_authority.get("preinventory_digest")
        != ph_d05_preinventory.get("content_digest")
        or contract_authority.get("phase_transition_digest")
        != ph_d05_transition.get("content_digest")
        or contract_authority.get("phase_entry_decision_digest")
        != ph_d03b_result_decision.get("owner_decision_content_digest")
        or contract_authority.get("phase_entry_approval_digest")
        != ph_d03b_result_approval.get("approval_artifact_digest")
        or not isinstance(contract_source, dict)
        or (
            contract_source.get("source_recording_count"),
            contract_source.get("game_count"),
            contract_source.get("level_count"),
            contract_source.get("recorded_action_count"),
            contract_source.get("canonical_success_prefix_action_count"),
        )
        != (25, 25, 183, 11648, 11574)
        or not isinstance(contract_output, dict)
        or contract_output.get("canonical_manifest_digest")
        != ph_d05_manifest.get("content_digest")
        or contract_output.get("normalization_report_digest")
        != ph_d05_normalization.get("content_digest")
        or contract_output.get("rebuild_x3_digest")
        != ph_d05_rebuild.get("content_digest")
    ):
        failures.append("ph_d05_contract:AUTHORITY_OR_OUTPUT_MISMATCH")

    replay_contracts = ph_d05_replay.get("per_game_replay_contracts")
    process_evidence = ph_d05_replay.get("process_evidence")
    if (
        ph_d05_replay.get("exit_claim")
        != "ARC3_STRICT_OFFLINE_REPLAY_X3_COMPLETE"
        or ph_d05_replay.get("independent_process_count") != 3
        or ph_d05_replay.get("game_count") != 25
        or ph_d05_replay.get("level_count") != 183
        or ph_d05_replay.get("action_count") != 11574
        or ph_d05_replay.get("canonical_replay_mismatch_count") != 0
        or ph_d05_replay.get(
            "action_availability_terminal_progress_mismatch_count"
        )
        != 0
        or not isinstance(replay_contracts, list)
        or len(replay_contracts) != 25
        or not isinstance(process_evidence, list)
        or len(process_evidence) != 3
        or ph_d05_replay.get("network_denial_pass_count") != 3
        or ph_d05_replay.get("secret_scrub_pass_count") != 3
        or ph_d05_replay.get("source_pre_post_identity_pass_count") != 3
        or ph_d05_replay.get("write_boundary_pass_count") != 3
    ):
        failures.append("ph_d05_replay:COVERAGE_OR_ISOLATION_MISMATCH")

    packages = ph_d05_manifest.get("packages")
    if (
        ph_d05_manifest.get("status")
        != "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE"
        or (
            ph_d05_manifest.get("game_count"),
            ph_d05_manifest.get("level_count"),
            ph_d05_manifest.get("recorded_action_count"),
            ph_d05_manifest.get("canonical_success_prefix_action_count"),
            ph_d05_manifest.get("canonical_replay_mismatch_count"),
        )
        != (25, 183, 11648, 11574, 0)
        or not isinstance(packages, list)
        or len(packages) != 25
        or any(
            ph_d05_manifest.get(field) != 0
            for field in (
                "hypothesis_generation_count",
                "causal_assertion_count",
                "real_intervention_execution_count",
                "rule_promotion_count",
                "bridge_runtime_capability_count",
                "official_access_count",
                "kaggle_mutation_count",
            )
        )
    ):
        failures.append("ph_d05_manifest:COVERAGE_OR_BOUNDARY_MISMATCH")
    if isinstance(packages, list):
        for item in packages:
            if not isinstance(item, dict):
                failures.append("ph_d05_manifest:PACKAGE_RECORD_INVALID")
                continue
            package_path = root / PH_D05_ARTIFACT_ROOT / str(
                item.get("package_path", "")
            )
            if not package_path.is_file():
                failures.append("ph_d05_manifest:PACKAGE_MISSING")
                continue
            payload = package_path.read_bytes()
            if (
                len(payload) != item.get("package_size_bytes")
                or hashlib.sha256(payload).hexdigest()
                != item.get("package_sha256")
            ):
                failures.append("ph_d05_manifest:PACKAGE_BYTES_MISMATCH")

    if (
        ph_d05_normalization.get("exit_claim")
        != "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE"
        or ph_d05_normalization.get("failed_requirement_ids") != []
        or ph_d05_normalization.get("gates")
        != {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-10": "PASS",
            "DG-11": "PASS",
            "DG-12": "PASS",
        }
        or ph_d05_normalization.get("canonical_manifest_digest")
        != ph_d05_manifest.get("content_digest")
    ):
        failures.append("ph_d05_normalization:GATE_OR_BINDING_MISMATCH")
    if (
        ph_d05_rebuild.get("exit_claim")
        != "ARC3_CANONICAL_TRAJECTORY_REBUILD_X3_COMPLETE"
        or ph_d05_rebuild.get("canonical_build_count") != 3
        or ph_d05_rebuild.get("package_count_per_build") != 25
        or ph_d05_rebuild.get("compared_file_count_per_build") != 27
        or ph_d05_rebuild.get("total_byte_mismatch_count") != 0
        or ph_d05_rebuild.get("failed_requirement_ids") != []
        or len(ph_d05_rebuild.get("file_bindings", [])) != 27
    ):
        failures.append("ph_d05_rebuild:DETERMINISM_MISMATCH")

    ph_d05_attestation = _load_object(root, PH_D05_EVIDENCE_ATTESTATION_PATH)
    failures.extend(
        _schema_failures(
            ph_d05_attestation,
            attestation_schema,
            "ph_d05_evidence_attestation",
        )
    )
    if ph_d05_attestation.get("phase_id") != "PH-D05":
        failures.append("ph_d05_evidence_attestation:PHASE_MISMATCH")
    for commit_field, tree_field in (
        ("implementation_commit", "implementation_tree"),
        ("evidence_commit", "evidence_tree"),
    ):
        commit = ph_d05_attestation.get(commit_field)
        expected_tree = ph_d05_attestation.get(tree_field)
        if not isinstance(commit, str) or _git_tree(root, commit) != (expected_tree):
            failures.append(
                "ph_d05_evidence_attestation:" + commit_field.upper() + "_TREE_MISMATCH"
            )
    ph_d05_phase_state_path = root / PH_D05_PHASE_STATE_PATH
    if hashlib.sha256(ph_d05_phase_state_path.read_bytes()).hexdigest() != (
        ph_d05_attestation.get("phase_state_sha256")
    ):
        failures.append("ph_d05_evidence_attestation:PHASE_STATE_SHA256_MISMATCH")
    ph_d05_phase_state = _load_object(root, PH_D05_PHASE_STATE_PATH)
    if (
        ph_d05_phase_state.get("phase_id") != "PH-D05"
        or ph_d05_phase_state.get("status") != "CODEX_SELF_AUDIT_PASS"
        or ph_d05_phase_state.get("failed_requirement_ids") != []
        or ph_d05_phase_state.get("implementation_commit")
        != ph_d05_attestation.get("implementation_commit")
        or ph_d05_phase_state.get("implementation_tree")
        != ph_d05_attestation.get("implementation_tree")
        or ph_d05_phase_state.get("evidence_payload_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
    ):
        failures.append("ph_d05_phase_state:RESULT_BINDING_MISMATCH")

    ph_d05_result_decision = _load_object(root, PH_D05_RESULT_DECISION_PATH)
    failures.extend(
        _schema_failures(
            ph_d05_result_decision,
            decision_v2_schema,
            "ph_d05_result_decision",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d05_result_decision,
            "sha256:",
            "owner_decision_content_digest",
            "ph_d05_result_decision",
        )
    )
    if (
        ph_d05_result_decision.get("standing_authorization_digest")
        != standing.get("standing_authorization_content_digest")
        or ph_d05_result_decision.get("target_evidence_commit")
        != ph_d05_attestation.get("evidence_commit")
        or ph_d05_result_decision.get("target_artifact_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
        or ph_d05_result_decision.get("gate_result_digest")
        != ph_d05_normalization.get("content_digest")
        or ph_d05_result_decision.get("gate_status") != "PASS"
        or ph_d05_result_decision.get("allowed_transition") != "PH-D05_TO_PH-D06"
        or ph_d05_result_decision.get("decision")
        != "APPROVE_PHASE_RESULT_AND_AUTHORIZE_NEXT_PHASE_ENTRY"
    ):
        failures.append("ph_d05_result_decision:BINDING_MISMATCH")

    ph_d05_result_approval = _load_object(root, PH_D05_RESULT_APPROVAL_PATH)
    failures.extend(
        _schema_failures(
            ph_d05_result_approval,
            approval_schema,
            "ph_d05_result_approval",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d05_result_approval,
            "owner-approval-record:",
            "approval_artifact_digest",
            "ph_d05_result_approval",
        )
    )
    if (
        ph_d05_result_approval.get("owner_decision_capture_digest")
        != ph_d05_result_decision.get("owner_decision_content_digest")
        or ph_d05_result_approval.get("target_evidence_commit")
        != ph_d05_attestation.get("evidence_commit")
        or ph_d05_result_approval.get("target_artifact_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
        or ph_d05_result_approval.get("approved_transition") != "PH-D05_TO_PH-D06"
        or ph_d05_result_approval.get("next_phase_id") != "PH-D06"
        or ph_d05_result_approval.get("next_phase_authorized") is not True
    ):
        failures.append("ph_d05_result_approval:BINDING_MISMATCH")

    ph_d06_frame = _load_object(root, PH_D06_FRAME_PATH)
    ph_d06_transition = _load_object(root, PH_D06_TRANSITION_PATH)
    ph_d06_preinventory = _load_object(root, PH_D06_PREINVENTORY_PATH)
    ph_d06_contract = _load_object(root, PH_D06_CONTRACT_PATH)
    ph_d06_manifest = _load_object(root, PH_D06_MANIFEST_PATH)
    ph_d06_rebuild = _load_object(root, PH_D06_REBUILD_X3_PATH)
    ph_d06_generation = _load_object(root, PH_D06_GENERATION_REPORT_PATH)
    ph_d06_source_blind = _load_object(root, PH_D06_SOURCE_BLIND_REPORT_PATH)
    ph_d06_llm_capture = _load_object(root, PH_D06_LLM_CAPTURE_REPORT_PATH)
    failures.extend(
        _content_digest_failures(
            ph_d06_frame,
            "rev3-work-block-frame:",
            "content_digest",
            "ph_d06_frame",
        )
    )
    ph_d06_read_boundaries = ph_d06_frame.get("read_only_data_boundaries")
    if not isinstance(ph_d06_read_boundaries, list):
        failures.append("ph_d06_frame:READ_ONLY_BOUNDARIES_MISSING")
    else:
        for boundary in ph_d06_read_boundaries:
            if not isinstance(boundary, str):
                failures.append("ph_d06_frame:READ_ONLY_BOUNDARY_INVALID")
                continue
            boundary_path = Path(boundary)
            if boundary_path.is_absolute() or ".." in boundary_path.parts:
                failures.append("ph_d06_frame:READ_ONLY_BOUNDARY_INVALID")
                continue
            if any(marker in boundary for marker in ("*", "?", "[")):
                exists = any(root.glob(boundary))
            else:
                exists = (root / boundary_path).exists()
            if not exists:
                failures.append(
                    "ph_d06_frame:READ_ONLY_BOUNDARY_MISSING:" + boundary
                )
    failures.extend(
        _content_digest_failures(
            ph_d06_transition,
            "rev3-phase-transition:",
            "content_digest",
            "ph_d06_transition",
        )
    )
    failures.extend(
        _content_digest_failures(
            ph_d06_preinventory,
            "rev3-ph-d06-hypothesis-candidate-preinventory:",
            "content_digest",
            "ph_d06_preinventory",
        )
    )
    for value, namespace, location in (
        (
            ph_d06_contract,
            "hds-arc3-hypothesis-candidate-generation-contract",
            "ph_d06_contract",
        ),
        (
            ph_d06_manifest,
            "hds-multi-hypothesis-corpus-manifest",
            "ph_d06_manifest",
        ),
        (
            ph_d06_rebuild,
            "hds-ph-d06-rebuild-x3",
            "ph_d06_rebuild",
        ),
        (
            ph_d06_generation,
            "hds-ph-d06-hypothesis-candidate-generation",
            "ph_d06_generation",
        ),
        (
            ph_d06_source_blind,
            "hds-ph-d06-source-blind-execution",
            "ph_d06_source_blind",
        ),
        (
            ph_d06_llm_capture,
            "hds-ph-d06-llm-capture",
            "ph_d06_llm_capture",
        ),
    ):
        failures.extend(
            _domain_content_digest_failures(
                value,
                namespace,
                "content_digest",
                location,
            )
        )
    for path, location in (
        (PH_D06_FRAME_PATH, "ph_d06_frame"),
        (PH_D06_TRANSITION_PATH, "ph_d06_transition"),
        (PH_D06_PREINVENTORY_PATH, "ph_d06_preinventory"),
        (PH_D06_CONTRACT_PATH, "ph_d06_contract"),
        (PH_D06_MANIFEST_PATH, "ph_d06_manifest"),
        (PH_D06_REBUILD_X3_PATH, "ph_d06_rebuild"),
        (PH_D06_GENERATION_REPORT_PATH, "ph_d06_generation"),
        (PH_D06_SOURCE_BLIND_REPORT_PATH, "ph_d06_source_blind"),
        (PH_D06_LLM_CAPTURE_REPORT_PATH, "ph_d06_llm_capture"),
    ):
        failures.extend(_canonical_document_failures(root, path, location))

    expected_ph_d06_runtime_evidence = {
        "archive_sha256": (
            "7ceaf4360f4b4ab44f31d8217cfdc70df8e12b61d9561b4900ee7af87176e50d"
        ),
        "asset_name": (
            "cpython-3.12.13+20260728-x86_64-unknown-linux-gnu-"
            "install_only_stripped.tar.gz"
        ),
        "entry_count": 4522,
        "executable_sha256": (
            "1e4461092175d186c4bcdb19ee2849a45d6e4d8d1f6a871e45f63418d52a4e35"
        ),
        "mount_path": "/python-runtime",
        "network_acquisition_during_build": False,
        "tree_digest": (
            "hds-ph-d06-python-runtime-tree:"
            "bb0341f8ca64f9830163873839b08ba8a0cb1f6abb9a56cc9762fb5ce9196d7f"
        ),
        "version": "3.12.13",
    }
    expected_ph_d06_runtime_contract = {
        "archive_or_runtime_in_git_allowed": False,
        "archive_sha256": expected_ph_d06_runtime_evidence["archive_sha256"],
        "asset_name": expected_ph_d06_runtime_evidence["asset_name"],
        "entry_count": 4522,
        "executable_sha256": expected_ph_d06_runtime_evidence["executable_sha256"],
        "network_acquisition_during_build_allowed": False,
        "required_version": "3.12.13",
        "runtime_archive_environment_key": ("ARC3_PH_D06_PYTHON_RUNTIME_ARCHIVE"),
        "runtime_root_environment_key": "ARC3_PH_D06_PYTHON_RUNTIME_ROOT",
        "source_blind_mount_path": "/python-runtime",
        "tree_digest": expected_ph_d06_runtime_evidence["tree_digest"],
    }
    ph_d06_budget = ph_d06_frame.get("resource_budget")
    if (
        ph_d06_frame.get("phase_id") != "PH-D06"
        or ph_d06_frame.get("status") != "FRAME_LOCKED"
        or ph_d06_frame.get("base_commit") != "5a2fab68a408f4c8fa1c00fa4d33eb1cfff769a3"
        or ph_d06_frame.get("base_tree") != "f43c60225774cc32e4ebcf2d2e2adc22ffe1139a"
        or not isinstance(ph_d06_budget, dict)
        or (
            ph_d06_budget.get("required_teacher_case_count"),
            ph_d06_budget.get("required_candidate_count_per_case"),
            ph_d06_budget.get("required_executable_candidate_count_per_case"),
            ph_d06_budget.get("required_rejected_adversarial_count_per_case"),
            ph_d06_budget.get("required_total_candidate_count"),
            ph_d06_budget.get("max_total_candidate_count"),
            ph_d06_budget.get("independent_build_process_count"),
            ph_d06_budget.get("max_ir_nodes_per_candidate"),
        )
        != (25, 18, 16, 2, 450, 500, 3, 4)
        or ph_d06_budget.get("required_gate_ids")
        != ["DG-03", "DG-04", "DG-05", "DG-08", "DG-12"]
        or ph_d06_budget.get("required_python_version") != "3.12.13"
        or ph_d06_budget.get("required_python_runtime_archive_sha256")
        != expected_ph_d06_runtime_evidence["archive_sha256"]
        or ph_d06_budget.get("required_python_runtime_tree_digest")
        != expected_ph_d06_runtime_evidence["tree_digest"]
        or ph_d06_budget.get("required_python_runtime_entry_count") != 4522
        or ph_d06_budget.get("required_python_executable_sha256")
        != expected_ph_d06_runtime_evidence["executable_sha256"]
        or ph_d06_budget.get("python_runtime_network_acquisition_during_build")
        is not False
        or any(
            ph_d06_budget.get(field) != 0
            for field in (
                "bridge_runtime_capability_count",
                "candidate_adoption_count",
                "causal_assertion_count",
                "environment_source_access_count",
                "fit_execution_count",
                "kaggle_mutation_count",
                "llm_call_count",
                "locked_final_access_count",
                "network_submission_count",
                "official_access_count",
                "real_intervention_execution_count",
                "rule_promotion_count",
            )
        )
    ):
        failures.append("ph_d06_frame:BOUNDARY_OR_BUDGET_MISMATCH")

    if (
        (
            ph_d06_transition.get("from_phase_id"),
            ph_d06_transition.get("to_phase_id"),
            ph_d06_transition.get("decision"),
        )
        != ("PH-D05", "PH-D06", "ENTRY_AUTHORIZED")
        or ph_d06_transition.get("from_phase_state_sha256")
        != ph_d05_attestation.get("phase_state_sha256")
        or ph_d06_transition.get("from_phase_implementation_commit")
        != ph_d05_attestation.get("implementation_commit")
        or ph_d06_transition.get("from_phase_implementation_tree")
        != ph_d05_attestation.get("implementation_tree")
        or ph_d06_transition.get("from_phase_evidence_commit")
        != ph_d05_attestation.get("evidence_commit")
        or ph_d06_transition.get("from_phase_evidence_tree")
        != ph_d05_attestation.get("evidence_tree")
        or ph_d06_transition.get("from_phase_evidence_payload_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
        or ph_d06_transition.get("authorization_digest")
        != ph_d05_result_approval.get("approval_artifact_digest")
        or ph_d06_transition.get("decision_capture_digest")
        != ph_d05_result_decision.get("owner_decision_content_digest")
        or ph_d06_transition.get("external_irreversible_action_authorized") is not False
    ):
        failures.append("ph_d06_transition:EVIDENCE_BINDING_MISMATCH")

    ph_d06_preinventory_authority = ph_d06_preinventory.get("authority")
    ph_d06_preinventory_source_blind = ph_d06_preinventory.get("source_blind_contract")
    ph_d06_preinventory_dirty = ph_d06_preinventory.get("preexisting_dirty_state")
    if (
        ph_d06_preinventory.get("phase_id") != "PH-D06"
        or ph_d06_preinventory.get("base_commit") != ph_d06_frame.get("base_commit")
        or ph_d06_preinventory.get("base_tree") != ph_d06_frame.get("base_tree")
        or not isinstance(ph_d06_preinventory_authority, dict)
        or ph_d06_preinventory_authority.get("input_evidence_commit")
        != ph_d05_attestation.get("evidence_commit")
        or ph_d06_preinventory_authority.get("input_evidence_tree")
        != ph_d05_attestation.get("evidence_tree")
        or ph_d06_preinventory_authority.get("input_evidence_payload_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
        or ph_d06_preinventory_authority.get("phase_entry_approval_digest")
        != ph_d05_result_approval.get("approval_artifact_digest")
        or ph_d06_preinventory_authority.get("phase_entry_decision_digest")
        != ph_d05_result_decision.get("owner_decision_content_digest")
        or not isinstance(ph_d06_preinventory_source_blind, dict)
        or ph_d06_preinventory_source_blind.get("python_runtime")
        != expected_ph_d06_runtime_contract
        or not isinstance(ph_d06_preinventory_dirty, dict)
        or ph_d06_preinventory_dirty.get("tracked_file_count") != 32
        or ph_d06_preinventory_dirty.get("aggregate_sha256")
        != "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
        or ph_d06_preinventory_dirty.get("allowed_to_modify") is not False
    ):
        failures.append("ph_d06_preinventory:BOUNDARY_MISMATCH")

    ph_d06_contract_authority = ph_d06_contract.get("authority")
    ph_d06_contract_output = ph_d06_contract.get("output_contract")
    if (
        ph_d06_contract.get("phase_id") != "PH-D06"
        or not isinstance(ph_d06_contract_authority, dict)
        or ph_d06_contract_authority.get("work_block_frame_digest")
        != ph_d06_frame.get("content_digest")
        or ph_d06_contract_authority.get("preinventory_digest")
        != ph_d06_preinventory.get("content_digest")
        or ph_d06_contract_authority.get("phase_transition_digest")
        != ph_d06_transition.get("content_digest")
        or ph_d06_contract_authority.get("phase_entry_approval_digest")
        != ph_d05_result_approval.get("approval_artifact_digest")
        or ph_d06_contract_authority.get("phase_entry_decision_digest")
        != ph_d05_result_decision.get("owner_decision_content_digest")
        or ph_d06_contract.get("python_runtime_contract")
        != expected_ph_d06_runtime_contract
        or not isinstance(ph_d06_contract_output, dict)
        or ph_d06_contract_output.get("candidate_manifest_digest")
        != ph_d06_manifest.get("content_digest")
        or ph_d06_contract_output.get("rebuild_x3_digest")
        != ph_d06_rebuild.get("content_digest")
        or ph_d06_contract_output.get("generation_report_digest")
        != ph_d06_generation.get("content_digest")
        or ph_d06_contract_output.get("source_blind_report_digest")
        != ph_d06_source_blind.get("content_digest")
        or ph_d06_contract_output.get("llm_capture_report_digest")
        != ph_d06_llm_capture.get("content_digest")
    ):
        failures.append("ph_d06_contract:AUTHORITY_OR_OUTPUT_MISMATCH")

    expected_candidate_families = [
        "MINIMAL_MECHANISM",
        "ALTERNATIVE_SELECTOR",
        "ALTERNATIVE_OPERATOR_ORDER",
        "ALTERNATIVE_ADJACENCY_ORDER",
        "NULL_NO_OP",
        "OBSERVATION_ERROR",
        "SURFACE_CORRELATION",
        "OVERFIT",
        "WRONG_TARGET",
        "WRONG_ORDER",
        "DELAYED_EFFECT",
        "DIFFERENT_GOAL",
        "COUNTER_IMMEDIATE_EFFECT",
        "RESET_MODEL",
        "BOUNDED_ENUM_ACTION_PRECONDITION",
        "BOUNDED_ENUM_PAYLOAD_PRECONDITION",
        "ANSWER_COPY_ADVERSARIAL",
        "TRAJECTORY_LOOKUP_ADVERSARIAL",
    ]
    ph_d06_packages = ph_d06_manifest.get("case_packages")
    if (
        ph_d06_manifest.get("status") != "MULTI_HYPOTHESIS_CORPUS_COMPLETE"
        or (
            ph_d06_manifest.get("source_teacher_case_count"),
            ph_d06_manifest.get("candidate_case_package_count"),
            ph_d06_manifest.get("candidate_count"),
            ph_d06_manifest.get("executable_candidate_count"),
            ph_d06_manifest.get("rejected_adversarial_count"),
            ph_d06_manifest.get("candidate_adoption_count"),
        )
        != (25, 25, 450, 400, 50, 0)
        or ph_d06_manifest.get("candidate_families") != expected_candidate_families
        or ph_d06_manifest.get("candidate_family_counts")
        != {family: 25 for family in expected_candidate_families}
        or ph_d06_manifest.get("alternative_adequacy_status") != "PASS"
        or ph_d06_manifest.get("automatic_adoption_forbidden") is not True
        or ph_d06_manifest.get("complete_action_sequence_copy_count") != 0
        or ph_d06_manifest.get("identity_routing_count") != 0
        or ph_d06_manifest.get("environment_source_access_count") != 0
        or ph_d06_manifest.get("llm_call_count") != 0
        or ph_d06_manifest.get("live_llm_required_for_rebuild") is not False
        or not isinstance(ph_d06_packages, list)
        or len(ph_d06_packages) != 25
        or any(
            ph_d06_manifest.get("phase_boundaries", {}).get(field) != 0
            for field in (
                "bridge_runtime_capability_count",
                "causal_assertion_count",
                "fit_execution_count",
                "kaggle_mutation_count",
                "official_access_count",
                "real_intervention_execution_count",
                "rule_promotion_count",
            )
        )
    ):
        failures.append("ph_d06_manifest:COVERAGE_OR_BOUNDARY_MISMATCH")

    if isinstance(ph_d06_packages, list):
        for package_index, item in enumerate(ph_d06_packages):
            location = f"ph_d06_package[{package_index}]"
            if not isinstance(item, dict):
                failures.append(location + ":PACKAGE_RECORD_INVALID")
                continue
            package_path = (
                root
                / PH_D06_ARTIFACT_ROOT
                / str(item.get("candidate_package_path", ""))
            )
            if not package_path.is_file():
                failures.append(location + ":PACKAGE_MISSING")
                continue
            package_bytes = package_path.read_bytes()
            if len(package_bytes) != item.get(
                "candidate_package_size_bytes"
            ) or hashlib.sha256(package_bytes).hexdigest() != item.get(
                "candidate_package_sha256"
            ):
                failures.append(location + ":COMPRESSED_BYTES_MISMATCH")
                continue
            try:
                raw_package = gzip.decompress(package_bytes)
                package_object = json.loads(
                    raw_package.decode("utf-8", errors="strict"),
                    object_pairs_hook=_strict_object_pairs,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError("non-finite JSON token: " + value)
                    ),
                )
            except (OSError, UnicodeDecodeError, ValueError):
                failures.append(location + ":PACKAGE_DECODE_INVALID")
                continue
            if not isinstance(package_object, dict):
                failures.append(location + ":PACKAGE_TYPE_INVALID")
                continue
            if (
                len(raw_package) != item.get("candidate_uncompressed_size_bytes")
                or hashlib.sha256(raw_package).hexdigest()
                != item.get("candidate_uncompressed_sha256")
                or raw_package
                != canonical_json(_nfc_json(package_object)).encode("utf-8") + b"\n"
            ):
                failures.append(location + ":UNCOMPRESSED_BYTES_MISMATCH")
            failures.extend(
                _domain_content_digest_failures(
                    package_object,
                    "hds-hypothesis-case-package",
                    "content_digest",
                    location,
                )
            )
            candidates = package_object.get("candidates")
            adequacy = package_object.get("alternative_adequacy")
            if (
                package_object.get("teacher_case_ref") != item.get("teacher_case_ref")
                or package_object.get("content_digest")
                != item.get("candidate_package_content_digest")
                or (
                    package_object.get("candidate_count"),
                    package_object.get("executable_candidate_count"),
                    package_object.get("rejected_adversarial_count"),
                    package_object.get("candidate_adoption_count"),
                )
                != (18, 16, 2, 0)
                or package_object.get("automatic_adoption_forbidden") is not True
                or package_object.get("candidate_families")
                != expected_candidate_families
                or not isinstance(adequacy, dict)
                or adequacy.get("status") != "PASS"
                or adequacy.get("selected_candidate_count") != 0
                or adequacy.get("selector_family_count", 0) < 2
                or adequacy.get("operator_ordering_family_count", 0) < 2
                or adequacy.get("non_strawman_count", 0) < 2
                or not isinstance(candidates, list)
                or len(candidates) != 18
            ):
                failures.append(location + ":CANDIDATE_INVENTORY_MISMATCH")
                continue
            rejection_codes: list[object] = []
            for candidate_index, candidate in enumerate(candidates):
                candidate_location = location + f".candidates[{candidate_index}]"
                if not isinstance(candidate, dict):
                    failures.append(candidate_location + ":TYPE_INVALID")
                    continue
                failures.extend(
                    _domain_content_digest_failures(
                        candidate,
                        "hds-hypothesis-candidate",
                        "content_digest",
                        candidate_location,
                    )
                )
                if (
                    candidate.get("ordinal") != candidate_index
                    or candidate.get("candidate_family")
                    != expected_candidate_families[candidate_index]
                    or candidate.get("teacher_case_ref")
                    != package_object.get("teacher_case_ref")
                    or candidate.get("automatic_adoption") is not False
                    or candidate.get("promotion_state") != "NOT_PROMOTED"
                    or candidate.get("causal_assertion_state") != "NOT_ASSERTED"
                ):
                    failures.append(candidate_location + ":STATE_MISMATCH")
                if candidate_index < 16:
                    hypothesis_ir = candidate.get("hypothesis_ir")
                    if (
                        candidate.get("executable") is not True
                        or candidate.get("execution_status") != "PASS"
                        or candidate.get("rejected") is not False
                        or candidate.get("rejection_code") is not None
                        or candidate.get("candidate_state") != "PENDING_PH_D07A"
                        or candidate.get("fit_status") != "NOT_EVALUATED"
                        or candidate.get("ir_node_count", 5) > 4
                        or not isinstance(hypothesis_ir, dict)
                    ):
                        failures.append(
                            candidate_location + ":EXECUTABLE_STATE_MISMATCH"
                        )
                    elif isinstance(hypothesis_ir, dict):
                        failures.extend(
                            _domain_content_digest_failures(
                                hypothesis_ir,
                                "hds-hypothesis-ir",
                                "content_digest",
                                candidate_location + ".hypothesis_ir",
                            )
                        )
                else:
                    rejection_codes.append(candidate.get("rejection_code"))
                    if (
                        candidate.get("executable") is not False
                        or candidate.get("execution_status")
                        != "REJECTED_BEFORE_EXECUTION"
                        or candidate.get("rejected") is not True
                        or candidate.get("candidate_state") != "REJECTED_DG_08"
                        or candidate.get("fit_status") != "NOT_ELIGIBLE"
                        or candidate.get("hypothesis_ir") is not None
                        or not isinstance(
                            candidate.get("rejected_payload_commitment"), str
                        )
                    ):
                        failures.append(
                            candidate_location + ":REJECTION_STATE_MISMATCH"
                        )
            if rejection_codes != [
                "IR_ANSWER_COPY_FORBIDDEN",
                "IR_IDENTITY_ROUTING_FORBIDDEN",
            ]:
                failures.append(location + ":REJECTION_CODES_MISMATCH")

    if (
        ph_d06_rebuild.get("status") != "PASS"
        or ph_d06_rebuild.get("independent_process_count") != 3
        or ph_d06_rebuild.get("candidate_case_package_count") != 25
        or ph_d06_rebuild.get("candidate_count") != 450
        or ph_d06_rebuild.get("compared_file_count_per_build") != 26
        or ph_d06_rebuild.get("byte_mismatch_count") != 0
    ):
        failures.append("ph_d06_rebuild:DETERMINISM_MISMATCH")

    ph_d06_process_results = ph_d06_source_blind.get("process_results")
    ph_d06_runtime_evidence = ph_d06_source_blind.get("python_runtime")
    ph_d06_mount_allowlist = ph_d06_source_blind.get("mount_allowlist")
    if (
        ph_d06_source_blind.get("status") != "PASS_SOURCE_BLIND_ESTABLISHED"
        or ph_d06_source_blind.get("independent_process_count") != 3
        or ph_d06_source_blind.get("candidate_generation_count") != 450
        or ph_d06_source_blind.get("candidate_adoption_count") != 0
        or ph_d06_source_blind.get("environment_source_access_count") != 0
        or ph_d06_source_blind.get("environment_source_mount_count") != 0
        or ph_d06_source_blind.get("repository_root_visibility_count") != 0
        or ph_d06_source_blind.get("secret_environment_key_count") != 0
        or ph_d06_source_blind.get(
            "same_process_source_access_then_candidate_generation_count"
        )
        != 0
        or ph_d06_source_blind.get("mount_namespace_pass_count") != 3
        or ph_d06_source_blind.get("network_namespace_pass_count") != 3
        or ph_d06_runtime_evidence != expected_ph_d06_runtime_evidence
        or not isinstance(ph_d06_mount_allowlist, list)
        or "/python-runtime:READ_ONLY_PINNED_PYTHON_3_12_13"
        not in ph_d06_mount_allowlist
        or not isinstance(ph_d06_process_results, list)
        or len(ph_d06_process_results) != 3
        or any(
            not isinstance(process, dict)
            or process.get("status") != "PASS"
            or process.get("candidate_generation_count") != 450
            or process.get("candidate_adoption_count") != 0
            or process.get("environment_source_access_count") != 0
            or process.get("environment_source_mount_observed") is not False
            or process.get("repository_root_visible") is not False
            or process.get("secret_environment_key_count") != 0
            or process.get("mount_namespace_enforced") is not True
            or process.get("network_namespace_enforced") is not True
            or process.get("python_version") != "3.12.13"
            or process.get("python_runtime_archive_sha256")
            != expected_ph_d06_runtime_evidence["archive_sha256"]
            or process.get("python_runtime_tree_digest")
            != expected_ph_d06_runtime_evidence["tree_digest"]
            or process.get("python_executable_sha256")
            != expected_ph_d06_runtime_evidence["executable_sha256"]
            for process in (
                ph_d06_process_results
                if isinstance(ph_d06_process_results, list)
                else []
            )
        )
    ):
        failures.append("ph_d06_source_blind:ISOLATION_MISMATCH")

    if (
        ph_d06_llm_capture.get("status") != "PASS_NO_LLM_DEPENDENCY"
        or ph_d06_llm_capture.get("llm_call_count") != 0
        or ph_d06_llm_capture.get("live_llm_required_for_rebuild") is not False
        or ph_d06_llm_capture.get("arbitrary_code_execution_count") != 0
        or ph_d06_llm_capture.get("deterministic_template_candidate_count") != 350
        or ph_d06_llm_capture.get("bounded_graph_enumeration_candidate_count") != 50
        or ph_d06_llm_capture.get("adversarial_generation_candidate_count") != 50
    ):
        failures.append("ph_d06_llm_capture:BOUNDARY_MISMATCH")

    if (
        ph_d06_generation.get("status") != "MULTI_HYPOTHESIS_CORPUS_COMPLETE"
        or (
            ph_d06_generation.get("teacher_case_count"),
            ph_d06_generation.get("candidate_case_package_count"),
            ph_d06_generation.get("candidate_count"),
            ph_d06_generation.get("executable_candidate_count"),
            ph_d06_generation.get("rejected_adversarial_count"),
            ph_d06_generation.get("candidate_adoption_count"),
        )
        != (25, 25, 450, 400, 50, 0)
        or ph_d06_generation.get("alternative_adequacy_status") != "PASS"
        or ph_d06_generation.get("answer_copy_generated_and_rejected_count") != 25
        or ph_d06_generation.get("trajectory_lookup_generated_and_rejected_count") != 25
        or ph_d06_generation.get("candidate_manifest_digest")
        != ph_d06_manifest.get("content_digest")
        or ph_d06_generation.get("rebuild_x3_digest")
        != ph_d06_rebuild.get("content_digest")
        or ph_d06_generation.get("source_blind_execution_digest")
        != ph_d06_source_blind.get("content_digest")
        or ph_d06_generation.get("llm_capture_digest")
        != ph_d06_llm_capture.get("content_digest")
        or ph_d06_generation.get("gates")
        != {
            "DG-03": "PASS",
            "DG-04": "PASS",
            "DG-05": "PASS",
            "DG-08": "PASS",
            "DG-12": "PASS",
        }
        or any(
            ph_d06_generation.get(field) != 0
            for field in (
                "byte_mismatch_count",
                "causal_assertion_count",
                "complete_action_sequence_copy_count",
                "fit_execution_count",
                "identity_routing_count",
                "real_intervention_execution_count",
                "rule_promotion_count",
                "source_access_count",
            )
        )
    ):
        failures.append("ph_d06_generation:GATE_OR_BINDING_MISMATCH")

    source_inventory = _load_object(root, PH_D01A_SOURCE_INVENTORY_PATH)
    failures.extend(
        _content_digest_failures(
            source_inventory,
            "hds-source-inventory-report:",
            "content_digest",
            "ph_d01a_source_inventory",
        )
    )
    if source_inventory.get("source_count") != 83:
        failures.append("ph_d01a_source_inventory:SOURCE_COUNT_MISMATCH")
    if source_inventory.get("policy_weight_admitted_source_count") != 0:
        failures.append("ph_d01a_source_inventory:POLICY_WEIGHT_ADMITTED")

    provenance = _load_object(root, PH_D01A_PROVENANCE_REPORT_PATH)
    failures.extend(
        _content_digest_failures(
            provenance,
            "hds-primary-source-provenance-report:",
            "content_digest",
            "ph_d01a_provenance",
        )
    )
    if provenance.get("source_inventory_digest") != (
        source_inventory.get("content_digest")
    ):
        failures.append("ph_d01a_provenance:INVENTORY_DIGEST_MISMATCH")
    if (
        provenance.get("raw_recording_provenance_count"),
        provenance.get("canonical_corpus_source_count"),
        provenance.get("provenance_relation_count"),
        provenance.get("covered_level_count"),
        provenance.get("covered_expected_action_count"),
        provenance.get("raw_trajectory_to_s5_provenance_complete"),
    ) != (25, 3, 75, 183, 11648, True):
        failures.append("ph_d01a_provenance:ACCOUNTING_MISMATCH")
    layer_policy = provenance.get("artifact_layer_policy")
    if not isinstance(layer_policy, dict):
        failures.append("ph_d01a_provenance:LAYER_POLICY_MISSING")
    elif (
        layer_policy.get("admitted_artifact_layer")
        != "PRIMARY_TEACHER_SOURCE"
        or layer_policy.get(
            "derived_distillation_evidence_admitted_source_count"
        )
        != 0
        or layer_policy.get(
            "governance_artifact_admitted_source_count"
        )
        != 0
        or layer_policy.get("policy_weight_admitted_source_count") != 0
        or layer_policy.get("forbidden_repository_source_count") != 0
    ):
        failures.append("ph_d01a_provenance:LAYER_POLICY_VIOLATION")
    if provenance.get("source_payload_access") != {
        "payload_parse_count": 0,
        "replay_execution_count": 0,
        "source_execution_count": 0,
    }:
        failures.append("ph_d01a_provenance:SOURCE_PAYLOAD_ACCESSED")

    manifest_plan = _load_object(root, PH_D01B_MANIFEST_PLAN_PATH)
    failures.extend(
        _content_digest_failures(
            manifest_plan,
            "hds-manifest-freeze-plan:",
            "content_digest",
            "ph_d01b_manifest_plan",
        )
    )
    source_blind_plan = _load_object(
        root, PH_D01B_SOURCE_BLIND_PLAN_PATH
    )
    failures.extend(
        _content_digest_failures(
            source_blind_plan,
            "hds-source-blind-execution-plan:",
            "content_digest",
            "ph_d01b_source_blind_plan",
        )
    )
    source_blind_record = _load_object(
        root, PH_D01B_SOURCE_BLIND_RECORD_PATH
    )
    failures.extend(
        _content_digest_failures(
            source_blind_record,
            "hds-source-blind-execution-record:",
            "content_digest",
            "ph_d01b_source_blind_record",
        )
    )
    source_blind_binding = manifest_plan.get("source_blind_execution")
    if not isinstance(source_blind_binding, dict):
        failures.append("ph_d01b_manifest_plan:SOURCE_BLIND_BINDING_MISSING")
    elif (
        source_blind_binding.get("plan_digest")
        != source_blind_plan.get("content_digest")
        or source_blind_binding.get("record_digest")
        != source_blind_record.get("content_digest")
    ):
        failures.append(
            "ph_d01b_manifest_plan:SOURCE_BLIND_BINDING_MISMATCH"
        )
    role_records = source_blind_record.get("role_records")
    assertions = source_blind_record.get("separation_assertions")
    if not isinstance(role_records, list) or [
        item.get("role_id") if isinstance(item, dict) else None
        for item in role_records
    ] != [
        "DISTILLATION_AUDITOR",
        "DISTILLATION_EXECUTOR",
        "REPLAY_HARNESS_MAINTAINER",
    ]:
        failures.append("ph_d01b_source_blind_record:ROLE_ORDER_MISMATCH")
    elif (
        any(
            item.get("repository_root_visible") is not False
            or item.get("mount_namespace_enforced") is not True
            or item.get("network_namespace_enforced") is not True
            or item.get("probe_status") != "PASS"
            for item in role_records
            if isinstance(item, dict)
        )
        or role_records[0].get(
            "environment_source_mount_observed"
        )
        is not False
        or role_records[1].get(
            "environment_source_mount_observed"
        )
        is not False
        or role_records[2].get(
            "environment_source_mount_observed"
        )
        is not True
    ):
        failures.append("ph_d01b_source_blind_record:PROBE_FAILURE")
    if not isinstance(assertions, dict) or (
        assertions.get("role_count") != 3
        or assertions.get("distinct_process_identity_count") != 3
        or assertions.get("distinct_checkout_projection_count") != 3
        or assertions.get(
            "same_process_source_access_then_candidate_generation_count"
        )
        != 0
        or assertions.get(
            "source_blind_execution_contract_established"
        )
        is not True
    ):
        failures.append(
            "ph_d01b_source_blind_record:SEPARATION_NOT_ESTABLISHED"
        )

    isolation = _load_object(root, PH_D01B_ISOLATION_REPORT_PATH)
    failures.extend(
        _content_digest_failures(
            isolation,
            "hds-environment-isolation-report:",
            "content_digest",
            "ph_d01b_isolation",
        )
    )
    if (
        isolation.get("source_blind_execution_record_digest")
        != source_blind_record.get("content_digest")
        or isolation.get("os_source_mount_read_only_enforced") is not True
        or isolation.get("source_blind_probe_process_count") != 3
        or isolation.get(
            "source_blind_execution_contract_established"
        )
        is not True
        or isolation.get("source_mutation_count") != 0
        or isolation.get("source_payload_semantic_parse_count") != 0
        or isolation.get("source_execution_count") != 0
        or isolation.get("teacher_replay_execution_count") != 0
        or isolation.get("current_rebind_network_call_count") != 0
    ):
        failures.append("ph_d01b_isolation:BOUNDARY_MISMATCH")

    environment_manifest = _load_object(
        root, PH_D01B_ENVIRONMENT_MANIFEST_PATH
    )
    failures.extend(
        _content_digest_failures(
            environment_manifest,
            "hds-environment-manifest:",
            "content_digest",
            "ph_d01b_environment_manifest",
        )
    )
    if (
        environment_manifest.get("isolation_report_digest")
        != isolation.get("content_digest")
    ):
        failures.append(
            "ph_d01b_environment_manifest:ISOLATION_BINDING_MISMATCH"
        )

    run_manifest = _load_object(root, PH_D01B_RUN_MANIFEST_PATH)
    failures.extend(
        _content_digest_failures(
            run_manifest,
            "hds-run-manifest:",
            "run_digest",
            "ph_d01b_run_manifest",
        )
    )

    freeze_report = _load_object(root, PH_D01B_FREEZE_REPORT_PATH)
    failures.extend(
        _content_digest_failures(
            freeze_report,
            "hds-source-manifest-freeze-report:",
            "content_digest",
            "ph_d01b_freeze_report",
        )
    )
    if (
        freeze_report.get("plan_digest")
        != manifest_plan.get("content_digest")
        or freeze_report.get("source_blind_execution_record_digest")
        != source_blind_record.get("content_digest")
        or freeze_report.get("isolation_report_digest")
        != isolation.get("content_digest")
        or freeze_report.get("phase_exit_claim")
        != "ARC3_TEACHER_SOURCE_FROZEN"
        or freeze_report.get(
            "source_blind_execution_contract_established"
        )
        is not True
        or freeze_report.get("accounting")
        != {
            "source_content_manifest_count": 8,
            "source_entry_count": 83,
            "acquisition_record_count": 8,
            "environment_manifest_count": 1,
            "run_manifest_count": 1,
            "raw_recording_verified_count": 25,
            "environment_archive_alias_verified_count": 50,
            "runtime_wheel_verified_count": 2,
            "source_blind_execution_record_count": 1,
        }
    ):
        failures.append("ph_d01b_freeze_report:ACCOUNTING_OR_BINDING_MISMATCH")

    source_manifest_paths = sorted(
        (
            root / "distillation/manifests/source_content"
        ).glob("*.json")
    )
    source_manifest_count = 0
    for path in source_manifest_paths:
        source_manifest = _load_object(
            root, path.relative_to(root)
        )
        failures.extend(
            _content_digest_failures(
                source_manifest,
                "hds-source-content-manifest:",
                "content_digest",
                "ph_d01b_source_manifest:" + path.name,
            )
        )
        count = source_manifest.get("source_count")
        if isinstance(count, int) and not isinstance(count, bool):
            source_manifest_count += count
    if len(source_manifest_paths) != 8 or source_manifest_count != 83:
        failures.append("ph_d01b_source_manifests:ACCOUNTING_MISMATCH")

    acquisition_paths = sorted(
        (
            root / "distillation/manifests/acquisition"
        ).glob("*.json")
    )
    for path in acquisition_paths:
        acquisition = _load_object(root, path.relative_to(root))
        failures.extend(
            _content_digest_failures(
                acquisition,
                "hds-acquisition-record:",
                "acquisition_digest",
                "ph_d01b_acquisition:" + path.name,
            )
        )
    if len(acquisition_paths) != 8:
        failures.append("ph_d01b_acquisitions:COUNT_MISMATCH")

    downstream_invalidation = _load_object(
        root, PH_D01B_DOWNSTREAM_INVALIDATION_PATH
    )
    failures.extend(
        _content_digest_failures(
            downstream_invalidation,
            "hds-ph-d01b-downstream-invalidation:",
            "content_digest",
            "ph_d01b_downstream_invalidation",
        )
    )
    expected_invalidated_artifacts = [
        {
            "path": "distillation/artifacts/reports/schema_conformance.json",
            "checked_sha256": (
                "1b4d69951d60025a1949f5019ca5aa07019ac0652ed3ffed2"
                "ae9be1eaa96e5c3"
            ),
            "expected_rebuild_sha256": (
                "eef085afd7638645222ffa0bd6905f77b441f3bba98b8038a"
                "bb0745174f78080"
            ),
            "owner_phase": "PH-D02B",
            "action": (
                "PRESERVE_CHECKED_BYTES_AND_REBUILD_ONLY_AFTER_"
                "PHASE_ORDERED_REVALIDATION"
            ),
        },
        {
            "path": (
                "distillation/artifacts/test_vectors/schema_examples/"
                "invalid_schema_bundles.json"
            ),
            "checked_sha256": (
                "83f90126ef5590db31956a17250d1a05db850f76eadf2fbbb"
                "4fb2103af1ae8dd"
            ),
            "expected_rebuild_sha256": (
                "e99c7909e6c2aa88ae1924780710780a8e929c0e6e0462763"
                "bc9d1ebc2fcd78b"
            ),
            "owner_phase": "PH-D02B",
            "action": (
                "PRESERVE_CHECKED_BYTES_AND_REBUILD_ONLY_AFTER_"
                "PHASE_ORDERED_REVALIDATION"
            ),
        },
        {
            "path": (
                "distillation/artifacts/test_vectors/schema_examples/"
                "valid_schema_examples.json"
            ),
            "checked_sha256": (
                "a40befab0e15a27a6c73168b42708c2b488fdf5498f458b64"
                "e5904a506cda253"
            ),
            "expected_rebuild_sha256": (
                "449efee6b1cac4800d5a970dc178a3b623ae3d7c31db34917"
                "cf76a3169d73e36"
            ),
            "owner_phase": "PH-D02B",
            "action": (
                "PRESERVE_CHECKED_BYTES_AND_REBUILD_ONLY_AFTER_"
                "PHASE_ORDERED_REVALIDATION"
            ),
        },
    ]
    if (
        downstream_invalidation.get("phase_id") != "PH-D01B"
        or downstream_invalidation.get("classification")
        != (
            "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE_"
            "REQUIRES_PHASE_ORDERED_REBUILD"
        )
        or downstream_invalidation.get("trigger_bindings")
        != {
            "source_blind_execution_record_digest": (
                source_blind_record.get("content_digest")
            ),
            "environment_isolation_report_digest": isolation.get(
                "content_digest"
            ),
            "environment_manifest_digest": environment_manifest.get(
                "content_digest"
            ),
            "run_manifest_digest": run_manifest.get("run_digest"),
            "source_manifest_freeze_report_digest": freeze_report.get(
                "content_digest"
            ),
        }
        or downstream_invalidation.get("invalidated_artifact_count") != 3
        or downstream_invalidation.get(
            "unaffected_rebuild_artifact_count"
        )
        != 39
        or downstream_invalidation.get("invalidated_artifacts")
        != expected_invalidated_artifacts
        or downstream_invalidation.get("phase_order")
        != {
            "current_phase": "PH-D01B",
            "next_phase": "PH-D02A",
            "invalidated_artifact_owner_phase": "PH-D02B",
            "ph_d02a_started": False,
            "ph_d02b_started": False,
            "current_phase_rebuild_permitted": False,
        }
        or downstream_invalidation.get("gates")
        != {
            "PH-D01B": "PASS_PENDING_FULL_REGRESSION",
            "PH-D02A": "NOT_STARTED",
            "PH-D02B": "SUSPEND",
        }
    ):
        failures.append(
            "ph_d01b_downstream_invalidation:CONTRACT_MISMATCH"
        )
    for invalidated_artifact in expected_invalidated_artifacts:
        artifact_path = root / invalidated_artifact["path"]
        if (
            not artifact_path.is_file()
            or hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            != invalidated_artifact["checked_sha256"]
        ):
            failures.append(
                "ph_d01b_downstream_invalidation:CHECKED_BYTES_MISMATCH:"
                + invalidated_artifact["path"]
            )

    phase_state = root / PH_R00_PHASE_STATE_PATH
    if hashlib.sha256(phase_state.read_bytes()).hexdigest() != (
        ph_r00_attestation.get("phase_state_sha256")
    ):
        failures.append(
            "ph_r00_evidence_attestation:PHASE_STATE_SHA256_MISMATCH"
        )
    historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D00A"
    )
    for relative_path in (
        "PH-D00A_WORK_BLOCK_FRAME.json",
        "D00A_PHASE_STATE.json",
        "OWNER_REVIEW_PACKAGE/artifact_manifest.json",
    ):
        if not (historical_root / relative_path).is_file():
            failures.append(
                "ph_d00a_historical_migration:MISSING:"
                + relative_path
            )

    ph_d00b_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D00B"
    )
    ph_d00b_historical_sources = [
        (
            "65d0ba27e3137a670c76db13893c10b6ffebd7b2",
            "control/rev3/PH-D00B_WORK_BLOCK_FRAME.json",
            "PH-D00B_WORK_BLOCK_FRAME.json",
        ),
        (
            "74a5c06fc2f4b0bc31e4ac4f6dd77aa06ed28dca",
            "control/rev3/D00B_PHASE_STATE.json",
            "D00B_PHASE_STATE.json",
        ),
        (
            "4f149ea2730568e2af89efef136a696b829c0601",
            "control/rev3/PHASE_TRANSITIONS/PH-D00A_TO_PH-D00B.json",
            "PHASE_TRANSITIONS/PH-D00A_TO_PH-D00B.json",
        ),
        (
            "25a4363fc1dfe78d47106f715db65c36d393210f",
            "control/rev3/PHASE_TRANSITIONS/PH-D00B_TO_PH-D01A.json",
            "PHASE_TRANSITIONS/PH-D00B_TO_PH-D01A.json",
        ),
    ]
    for package_name in (
        "artifact_manifest.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d00b_historical_sources.append(
            (
                "e7f99beff6e6fba343e6ce069434c6a28b040039",
                "control/rev3/PH-D00B_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    for source_commit, source_path, destination_path in (
        ph_d00b_historical_sources
    ):
        expected = _git_blob(root, source_commit, source_path)
        destination = ph_d00b_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d00b_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d00b_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d00b_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d01a_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D01A"
    )
    ph_d01a_historical_sources = [
        (
            "31a6f1eefabee1a19828c024b5619d11a835188f",
            "control/rev3/PH-D01A_WORK_BLOCK_FRAME.json",
            "PH-D01A_WORK_BLOCK_FRAME.json",
        ),
        (
            "50b8259fce783fc2cc28158756a020575eb5e25d",
            "control/rev3/D01A_PHASE_STATE.json",
            "D01A_PHASE_STATE.json",
        ),
        (
            "e7d14a12be4fef46854d08bef601f40a2da74941",
            "control/rev3/PHASE_TRANSITIONS/PH-D01A_TO_PH-D01B.json",
            "PHASE_TRANSITIONS/PH-D01A_TO_PH-D01B.json",
        ),
    ]
    for package_name in (
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d01a_historical_sources.append(
            (
                "50b8259fce783fc2cc28158756a020575eb5e25d",
                "control/rev3/PH-D01A_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    ph_d01a_historical_sources.append(
        (
            "9eee596736cc917d399041f875639892efe55f08",
            "control/rev3/PH-D01A_OWNER_REVIEW_PACKAGE/"
            "artifact_manifest.json",
            "OWNER_REVIEW_PACKAGE/artifact_manifest.json",
        )
    )
    for source_commit, source_path, destination_path in (
        ph_d01a_historical_sources
    ):
        expected = _git_blob(root, source_commit, source_path)
        destination = ph_d01a_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d01a_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d01a_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d01a_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d01b_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D01B"
    )
    ph_d01b_historical_sources = [
        (
            "190663cb0acb0aa44617addb6203e369607c37de",
            "control/rev3/PH-D01B_WORK_BLOCK_FRAME.json",
            "PH-D01B_WORK_BLOCK_FRAME.json",
        ),
        (
            "eecfa4ad497a0379b5f9808edd7ecd140bcf6929",
            "control/rev3/D01B_PHASE_STATE.json",
            "D01B_PHASE_STATE.json",
        ),
        (
            "ea24c69794393d56a1e3b79953c56c7bdd42fc0d",
            "control/rev3/PHASE_TRANSITIONS/PH-D01B_TO_PH-D02A.json",
            "PHASE_TRANSITIONS/PH-D01B_TO_PH-D02A.json",
        ),
    ]
    for package_name in (
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d01b_historical_sources.append(
            (
                "eecfa4ad497a0379b5f9808edd7ecd140bcf6929",
                "control/rev3/PH-D01B_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    ph_d01b_historical_sources.append(
        (
            "60737e3ca2c4fa5a9c3e1e9a2b1ba8540461351c",
            "control/rev3/PH-D01B_OWNER_REVIEW_PACKAGE/"
            "artifact_manifest.json",
            "OWNER_REVIEW_PACKAGE/artifact_manifest.json",
        )
    )
    for source_commit, source_path, destination_path in (
        ph_d01b_historical_sources
    ):
        expected = _git_blob(root, source_commit, source_path)
        destination = ph_d01b_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d01b_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d01b_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d01b_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d02a_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D02A"
    )
    ph_d02a_historical_sources = [
        (
            "12b23d017663f060d40d98320be0dafbab160638",
            "control/rev3/PH-D02A_WORK_BLOCK_FRAME.json",
            "PH-D02A_WORK_BLOCK_FRAME.json",
        ),
        (
            "ffa11f1181fe0a63118eba83a9e3c90090a0abb5",
            "control/rev3/D02A_PHASE_STATE.json",
            "D02A_PHASE_STATE.json",
        ),
        (
            "3b08867576ab0723570733a84e85093a1a0523ab",
            "control/rev3/PHASE_TRANSITIONS/PH-D02A_TO_PH-D02B.json",
            "PHASE_TRANSITIONS/PH-D02A_TO_PH-D02B.json",
        ),
    ]
    for package_name in (
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d02a_historical_sources.append(
            (
                "ffa11f1181fe0a63118eba83a9e3c90090a0abb5",
                "control/rev3/PH-D02A_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    ph_d02a_historical_sources.append(
        (
            "d07b6f6cb27aed386e06269b7c142e5caf618e78",
            "control/rev3/PH-D02A_OWNER_REVIEW_PACKAGE/"
            "artifact_manifest.json",
            "OWNER_REVIEW_PACKAGE/artifact_manifest.json",
        )
    )
    for source_commit, source_path, destination_path in (
        ph_d02a_historical_sources
    ):
        expected = _git_blob(root, source_commit, source_path)
        destination = ph_d02a_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d02a_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d02a_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d02a_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d02b_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D02B"
    )
    ph_d02b_historical_sources = [
        (
            "bab4c9b742f5a3b74b20653e17dd4b7532f1cdc3",
            "control/rev3/PH-D02B_WORK_BLOCK_FRAME.json",
            "PH-D02B_WORK_BLOCK_FRAME.json",
        ),
        (
            "b4db449881c0a8031d984498b5e4b216bcdf3ef1",
            "control/rev3/D02B_PHASE_STATE.json",
            "D02B_PHASE_STATE.json",
        ),
        (
            "f6daf398334a10aec8d9f0f4bc096289613d8d31",
            "control/rev3/PHASE_TRANSITIONS/PH-D02B_TO_PH-D02C.json",
            "PHASE_TRANSITIONS/PH-D02B_TO_PH-D02C.json",
        ),
    ]
    for package_name in (
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d02b_historical_sources.append(
            (
                "b4db449881c0a8031d984498b5e4b216bcdf3ef1",
                "control/rev3/PH-D02B_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    ph_d02b_historical_sources.append(
        (
            "69cf9c1d1d29bff14c68641858888967e32f93d7",
            "control/rev3/PH-D02B_OWNER_REVIEW_PACKAGE/"
            "artifact_manifest.json",
            "OWNER_REVIEW_PACKAGE/artifact_manifest.json",
        )
    )
    for source_commit, source_path, destination_path in (
        ph_d02b_historical_sources
    ):
        expected = _git_blob(root, source_commit, source_path)
        destination = ph_d02b_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d02b_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d02b_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d02b_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d02c_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D02C"
    )
    ph_d02c_historical_sources = [
        (
            "control/rev3/PH-D02C_WORK_BLOCK_FRAME.json",
            "PH-D02C_WORK_BLOCK_FRAME.json",
        ),
        (
            "control/rev3/D02C_PHASE_STATE.json",
            "D02C_PHASE_STATE.json",
        ),
        (
            "control/rev3/PHASE_TRANSITIONS/PH-D02C_TO_PH-D03A.json",
            "PHASE_TRANSITIONS/PH-D02C_TO_PH-D03A.json",
        ),
    ]
    for package_name in (
        "artifact_manifest.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        ph_d02c_historical_sources.append(
            (
                "control/rev3/PH-D02C_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    if len(ph_d02c_historical_sources) != 13:
        failures.append(
            "ph_d02c_historical_migration:INVENTORY_MISMATCH"
        )
    for source_path, destination_path in ph_d02c_historical_sources:
        expected = _git_blob(
            root,
            "9c9cf5a9790fae341ad1be45506c88e7a7f34b58",
            source_path,
        )
        destination = ph_d02c_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d02c_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d02c_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d02c_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    ph_d03a_historical_root = (
        root / "control/rev3/HISTORICAL_PRE_AUDIT/PH-D03A"
    )
    ph_d03a_historical_sources = [
        (
            "control/rev3/PH-D03A_WORK_BLOCK_FRAME.json",
            "PH-D03A_WORK_BLOCK_FRAME.json",
        ),
        (
            "control/rev3/D03A_CANDIDATE_STATE.json",
            "D03A_CANDIDATE_STATE.json",
        ),
    ]
    for package_name in (
        "artifact_manifest.json",
        "candidate_state_ref.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
        "validator_hardening_manifest.json",
        "validator_hardening_state.json",
        "validator_hardening_summary.md",
    ):
        ph_d03a_historical_sources.append(
            (
                "control/rev3/PH-D03A_OWNER_REVIEW_PACKAGE/"
                + package_name,
                "OWNER_REVIEW_PACKAGE/" + package_name,
            )
        )
    if len(ph_d03a_historical_sources) != 15:
        failures.append(
            "ph_d03a_historical_migration:INVENTORY_MISMATCH"
        )
    for source_path, destination_path in ph_d03a_historical_sources:
        expected = _git_blob(
            root,
            "70722de7df8278c866de0734c97206c9952d731d",
            source_path,
        )
        destination = ph_d03a_historical_root / destination_path
        if expected is None:
            failures.append(
                "ph_d03a_historical_migration:SOURCE_MISSING:"
                + source_path
            )
        elif not destination.is_file():
            failures.append(
                "ph_d03a_historical_migration:DESTINATION_MISSING:"
                + destination_path
            )
        elif destination.read_bytes() != expected:
            failures.append(
                "ph_d03a_historical_migration:CONTENT_MISMATCH:"
                + destination_path
            )

    asset_classification = _load_object(
        root, PH_R00_ASSET_CLASSIFICATION_PATH
    )
    failures.extend(
        _content_digest_failures(
            asset_classification,
            "rev3-asset-classification:",
            "content_digest",
            "ph_r00_asset_classification",
        )
    )
    if asset_classification.get("rev3_active_runtime_count") != 0:
        failures.append("ph_r00_asset_classification:RUNTIME_ACTIVE")
    if asset_classification.get(
        "rev3_active_runtime_capability_claim"
    ) != "NOT_ESTABLISHED":
        failures.append(
            "ph_r00_asset_classification:CAPABILITY_OVERCLAIM"
        )

    baseline = _load_object(root, PH_R00_BASELINE_PATH)
    failures.extend(
        _content_digest_failures(
            baseline,
            "rev3-pre-distillation-baseline:",
            "content_digest",
            "ph_r00_baseline",
        )
    )
    baseline_runtime = baseline.get("rev3_runtime")
    if not isinstance(baseline_runtime, dict):
        failures.append("ph_r00_baseline:RUNTIME_BOUNDARY_MISSING")
    elif (
        baseline_runtime.get("active_runtime_count") != 0
        or baseline_runtime.get("active_runtime_capability_claim")
        != "NOT_ESTABLISHED"
    ):
        failures.append("ph_r00_baseline:RUNTIME_OVERCLAIM")

    governance = _load_object(root, GOVERNANCE_CONTRACT_PATH)
    governed_selector = governance.get("current_selector")
    if not isinstance(governed_selector, dict):
        failures.append("governance:CURRENT_SELECTOR_MISSING")
    else:
        for key in (
            "active_phase",
            "current_work_class",
            "distilled_initial_state_bundle_status",
            "installation_status",
            "ph_d00a_status",
            "ph_d00b_status",
            "ph_d01a_status",
            "ph_d01b_status",
            "ph_d02a_status",
            "ph_d02b_status",
            "ph_d02c_status",
            "ph_d03a_status",
            "ph_d03b_status",
            "ph_d05_status",
            "ph_d06_status",
            "ph_r00_owner_authorization",
            "ph_r00_status",
            "ph_r1_status",
            "runtime_activation_status",
            "strategy_status",
        ):
            if governed_selector.get(key) != selector.get(key):
                failures.append(
                    f"governance.current_selector.{key}:MISMATCH"
                )
    active_work_block = governance.get("active_work_block")
    if not isinstance(active_work_block, dict):
        failures.append("governance:ACTIVE_WORK_BLOCK_MISSING")
    elif (
        active_work_block.get("phase_id") != "PH-D06"
        or active_work_block.get("path") != PH_D06_FRAME_PATH.as_posix()
        or active_work_block.get("content_digest") != ph_d06_frame.get("content_digest")
        or active_work_block.get("transition_digest")
        != ph_d06_transition.get("content_digest")
        or active_work_block.get("runtime_capability_addition_count") != 0
        or active_work_block.get(
            "external_irreversible_actions_authorized"
        )
        is not False
    ):
        failures.append("governance:ACTIVE_WORK_BLOCK_MISMATCH")
    governed_entry_approval = governance.get("phase_entry_approval")
    if not isinstance(governed_entry_approval, dict) or (
        governed_entry_approval.get("approval_artifact_digest")
        != ph_d05_result_approval.get("approval_artifact_digest")
        or governed_entry_approval.get("decision_capture_digest")
        != ph_d05_result_decision.get("owner_decision_content_digest")
        or governed_entry_approval.get("target_artifact_digest")
        != ph_d05_attestation.get("evidence_payload_digest")
        or governed_entry_approval.get("target_evidence_commit")
        != ph_d05_attestation.get("evidence_commit")
        or governed_entry_approval.get("from_phase") != "PH-D05"
        or governed_entry_approval.get("to_phase") != "PH-D06"
    ):
        failures.append("governance:PH_D06_ENTRY_APPROVAL_MISMATCH")
    governed_source_blind = governance.get("source_blind_execution_evidence")
    if not isinstance(governed_source_blind, dict) or (
        governed_source_blind.get("plan_digest")
        != source_blind_plan.get("content_digest")
        or governed_source_blind.get("record_digest")
        != source_blind_record.get("content_digest")
        or governed_source_blind.get("role_count") != 3
        or governed_source_blind.get(
            "same_process_source_access_then_candidate_generation_count"
        )
        != 0
        or governed_source_blind.get("candidate_execution_status")
        != "NOT_STARTED_PHASE_D01B"
        or governed_source_blind.get("evidence_semantics")
        != "IMMUTABLE_PH_D01B_POINT_IN_TIME_RESULT"
    ):
        failures.append("governance:SOURCE_BLIND_EVIDENCE_MISMATCH")
    governed_candidate_source_blind = governance.get(
        "current_candidate_source_blind_execution_evidence"
    )
    if not isinstance(governed_candidate_source_blind, dict) or (
        governed_candidate_source_blind.get("path")
        != PH_D06_SOURCE_BLIND_REPORT_PATH.as_posix()
        or governed_candidate_source_blind.get("record_digest")
        != ph_d06_source_blind.get("content_digest")
        or governed_candidate_source_blind.get("role_id") != "DISTILLATION_EXECUTOR"
        or governed_candidate_source_blind.get("status")
        != "PASS_SOURCE_BLIND_ESTABLISHED"
        or governed_candidate_source_blind.get("independent_process_count") != 3
        or governed_candidate_source_blind.get("candidate_generation_count") != 450
        or governed_candidate_source_blind.get("candidate_adoption_count") != 0
        or governed_candidate_source_blind.get("environment_source_access_count") != 0
        or governed_candidate_source_blind.get("environment_source_mount_count") != 0
        or governed_candidate_source_blind.get("repository_root_visibility_count") != 0
        or governed_candidate_source_blind.get(
            "same_process_source_access_then_candidate_generation_count"
        )
        != 0
        or governed_candidate_source_blind.get("python_runtime")
        != expected_ph_d06_runtime_evidence
    ):
        failures.append("governance:CURRENT_CANDIDATE_SOURCE_BLIND_MISMATCH")
    governed_invalidation = governance.get("downstream_invalidation_evidence")
    if not isinstance(governed_invalidation, dict) or (
        governed_invalidation.get("path")
        != PH_D01B_DOWNSTREAM_INVALIDATION_PATH.as_posix()
        or governed_invalidation.get("report_digest")
        != downstream_invalidation.get("content_digest")
        or governed_invalidation.get("invalidated_artifact_count") != 3
        or governed_invalidation.get(
            "invalidated_artifact_owner_phase"
        )
        != "PH-D02B"
        or governed_invalidation.get(
            "report_point_in_time_rebuild_permitted"
        )
        is not False
        or governed_invalidation.get(
            "live_ph_d02b_rebuild_permitted"
        )
        is not False
        or governed_invalidation.get(
            "live_ph_d02b_rebuild_completed"
        )
        is not True
        or governed_invalidation.get("evidence_semantics")
        != "IMMUTABLE_PH_D01B_POINT_IN_TIME_RESULT"
        or governed_invalidation.get(
            "report_point_in_time_ph_d02a_status"
        )
        != "NOT_STARTED"
        or governed_invalidation.get("live_ph_d02a_status")
        != "OWNER_APPROVED_PASS"
        or governed_invalidation.get("ph_d02b_status")
        != "OWNER_APPROVED_PASS"
    ):
        failures.append(
            "governance:DOWNSTREAM_INVALIDATION_EVIDENCE_MISMATCH"
        )

    profile = _load_object(root, BUILD_READY_PROFILE_PATH)
    if profile.get("profile_status") != (
        "OWNER_APPROVED_CONTRACT_NOT_YET_EVALUATED"
    ):
        failures.append("build_ready_profile:STATUS_MISMATCH")
    if profile.get("owner_approval_may_bypass_hard_minimum") is not False:
        failures.append("build_ready_profile:BYPASS_ENABLED")

    for schema_path in (
        STANDING_AUTHORIZATION_SCHEMA_PATH,
        DECISION_V2_SCHEMA_PATH,
    ):
        installed_schema = _load_object(root, schema_path)
        if installed_schema.get("additionalProperties") is not False:
            failures.append(f"{schema_path}:OPEN_SCHEMA")

    package = root / CORRECTION_PACKAGE_PATH
    if hashlib.sha256(package.read_bytes()).hexdigest() != (
        CORRECTION_PACKAGE_SHA256
    ):
        failures.append("correction_package:SHA256_MISMATCH")
    with ZipFile(package) as archive:
        names = archive.namelist()
        if not names or not all(name.isascii() for name in names):
            failures.append("correction_package:NON_ASCII_ENTRY")
        checksum_lines = (
            archive.read("SHA256SUMS").decode("ascii").splitlines()
        )
        checksums = {
            line.split("  ", 1)[1]: line.split("  ", 1)[0]
            for line in checksum_lines
        }
        for name, expected_sha in checksums.items():
            actual_sha = hashlib.sha256(archive.read(name)).hexdigest()
            if actual_sha != expected_sha:
                failures.append(
                    f"correction_package:{name}:SHA256_MISMATCH"
                )

    return {
        "check_count": 86,
        "failure_count": len(failures),
        "failures": sorted(set(failures)),
        "status": "PASS" if not failures else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
    )
    arguments = parser.parse_args()
    report = validate_repository(arguments.root.resolve())
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
