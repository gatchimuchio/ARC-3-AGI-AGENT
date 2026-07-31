#!/usr/bin/env python3
"""Validate installed rev3 governance without external schema packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zipfile import ZipFile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = Path("control/rev3/REV3_CURRENT_SELECTOR.json")
SELECTOR_SCHEMA_PATH = Path(
    "docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V6.json"
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
            isinstance(value, (int, float))
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

    if selector.get("active_phase") != "PH-D00B":
        failures.append("selector:ACTIVE_PHASE_MISMATCH")
    if selector.get("ph_r00_owner_authorization") != "ESTABLISHED":
        failures.append("selector:PH_R00_AUTHORIZATION_MISSING")
    if selector.get("ph_r00_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_R00_STATUS_MISMATCH")
    if selector.get("ph_d00a_status") != "OWNER_APPROVED_PASS":
        failures.append("selector:PH_D00A_STATUS_MISMATCH")
    if selector.get("ph_d00b_status") != "IN_PROGRESS":
        failures.append("selector:PH_D00B_STATUS_MISMATCH")
    if selector.get("runtime_activation_status") != "SUSPEND":
        failures.append("selector:RUNTIME_ACTIVATION_ESCALATED")
    selector_entry_approval = selector.get("phase_entry_approval")
    if not isinstance(selector_entry_approval, dict):
        failures.append("selector:PH_D00B_ENTRY_APPROVAL_MISSING")
    elif (
        selector_entry_approval.get("approval_artifact_digest")
        != ph_d00a_result_approval.get("approval_artifact_digest")
    ):
        failures.append("selector:PH_D00B_ENTRY_APPROVAL_MISMATCH")
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
        active_work_block.get("phase_id") != "PH-D00B"
        or active_work_block.get("path") != PH_D00B_FRAME_PATH.as_posix()
        or active_work_block.get("content_digest")
        != ph_d00b_frame.get("content_digest")
        or active_work_block.get("transition_digest")
        != ph_d00b_transition.get("content_digest")
        or active_work_block.get(
            "external_irreversible_actions_authorized"
        )
        is not False
    ):
        failures.append("governance:ACTIVE_WORK_BLOCK_MISMATCH")

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
        "check_count": 24,
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
