#!/usr/bin/env python3
"""Validate installed rev3 governance without external schema packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zipfile import ZipFile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = Path("control/rev3/REV3_CURRENT_SELECTOR.json")
SELECTOR_SCHEMA_PATH = Path(
    "docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V11.json"
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

    if selector.get("active_phase") != "PH-D02C":
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
    if selector.get("ph_d02c_status") != "IN_PROGRESS":
        failures.append("selector:PH_D02C_STATUS_MISMATCH")
    if selector.get("runtime_activation_status") != "SUSPEND":
        failures.append("selector:RUNTIME_ACTIVATION_ESCALATED")
    selector_entry_approval = selector.get("phase_entry_approval")
    if not isinstance(selector_entry_approval, dict):
        failures.append("selector:PH_D02C_ENTRY_APPROVAL_MISSING")
    elif (
        selector_entry_approval.get("approval_artifact_digest")
        != ph_d02b_result_approval.get("approval_artifact_digest")
    ):
        failures.append("selector:PH_D02C_ENTRY_APPROVAL_MISMATCH")
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
    schema_entries = ph_d02c_schema_contract.get("schema_entries")
    schema_authority = ph_d02c_schema_contract.get("authority")
    if (
        ph_d02c_schema_contract.get("phase_id") != "PH-D02C"
        or ph_d02c_schema_contract.get("base_schema_count") != 45
        or ph_d02c_schema_contract.get("derived_schema_count") != 45
        or ph_d02c_schema_contract.get("unchanged_schema_count") != 43
        or ph_d02c_schema_contract.get("changed_schema_count") != 2
        or ph_d02c_schema_contract.get("changed_schema_names")
        != ["HypothesisIR", "OperatorRegistry"]
        or not isinstance(schema_entries, list)
        or len(schema_entries) != 45
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
            for item in schema_entries
            if isinstance(item, dict)
        }
        if (
            len(actual_schema_files) != 45
            or actual_schema_files != expected_schema_files
        ):
            failures.append(
                "ph_d02c_schema_contract:SCHEMA_FILES_MISMATCH"
            )
        for item in schema_entries:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename")
            schema_path = (
                root / PH_D02C_SCHEMA_ROOT / filename
                if isinstance(filename, str)
                else None
            )
            if (
                schema_path is None
                or not schema_path.is_file()
                or hashlib.sha256(schema_path.read_bytes()).hexdigest()
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
        active_work_block.get("phase_id") != "PH-D02C"
        or active_work_block.get("path") != PH_D02C_FRAME_PATH.as_posix()
        or active_work_block.get("content_digest")
        != ph_d02c_frame.get("content_digest")
        or active_work_block.get("transition_digest")
        != ph_d02c_transition.get("content_digest")
        or active_work_block.get("runtime_capability_addition_count") != 0
        or active_work_block.get(
            "external_irreversible_actions_authorized"
        )
        is not False
    ):
        failures.append("governance:ACTIVE_WORK_BLOCK_MISMATCH")
    governed_source_blind = governance.get(
        "source_blind_execution_evidence"
    )
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
    governed_invalidation = governance.get(
        "downstream_invalidation_evidence"
    )
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
        "check_count": 64,
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
