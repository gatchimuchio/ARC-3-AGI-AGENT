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
    "docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V3.json"
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
DECISION_V2_SCHEMA_PATH = Path(
    "docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V2.json"
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

    if selector.get("active_phase") is not None:
        failures.append("selector:ACTIVE_PHASE_FORBIDDEN")
    if selector.get("ph_r00_owner_authorization") != "NOT_ESTABLISHED":
        failures.append("selector:PH_R00_AUTHORIZATION_ESCALATED")
    if selector.get("runtime_activation_status") != "SUSPEND":
        failures.append("selector:RUNTIME_ACTIVATION_ESCALATED")

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
        "check_count": 12,
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
