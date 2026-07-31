"""PH-D03B commitment-only, one-use Sealed Audit Corpus.

The checked sealed namespace contains approved digest commitments, not
expected-artifact plaintext.  The audit path returns only ``PASS`` or
``FAIL`` and consumes a corpus version on its first valid audit attempt.
This module does not normalize teacher data, execute an ARC environment,
promote rules, import a runtime, or grant Owner authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal, Never, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_bytes,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
    verify_canonical_json_document_bytes,
)
from .ir_types import JsonObject

SEALED_AUDIT_CONTRACT_VERSION: Final = "hds-sealed-audit-contract-v1"
SEALED_COMMITMENT_SET_VERSION: Final = (
    "hds-sealed-expected-commitment-set-v1"
)
SEALED_RUNNER_CONTRACT_VERSION: Final = (
    "hds-sealed-audit-runner-contract-v1"
)
SEALED_MANIFEST_VERSION: Final = "hds-sealed-audit-manifest-v1"
SEALED_FREEZE_REPORT_VERSION: Final = "hds-sealed-audit-freeze-report-v1"
SEALED_SUBMISSION_VERSION: Final = "hds-sealed-audit-submission-v1"
SEALED_LEDGER_VERSION: Final = "hds-sealed-audit-consumption-ledger-v1"

CORPUS_VERSION: Final = "ph-d03b-v1"
EXPECTED_COMMITMENT_COUNT: Final = 16
SEALED_ARTIFACT_COUNT: Final = 5

PH_D03B_FRAME_DIGEST: Final = (
    "rev3-work-block-frame:"
    "3f741cd961329e719c657bcef91b82984042ce835ff29163640a48121aebea89"
)
PH_D03B_PREINVENTORY_DIGEST: Final = (
    "rev3-ph-d03b-sealed-audit-preinventory:"
    "93cba39fa00975f2412b7be7843f26aff5faae14271de845c9b08985338a3cc5"
)
PH_D03B_TRANSITION_DIGEST: Final = (
    "rev3-phase-transition:"
    "3b063d6a78bbd4acc79b9a299badcefd7a22890f286db6d18d96233bc65d24a6"
)
PH_D03A_IMPLEMENTATION_COMMIT: Final = (
    "0bb43aebf069ab6e6a6e1107c871a2a56ad6efcc"
)
PH_D03A_EVIDENCE_COMMIT: Final = (
    "cc20fe82ab2aba6ae8159bb2c761b4dabe05886c"
)
PH_D03A_EVIDENCE_PAYLOAD_DIGEST: Final = (
    "sha256:"
    "8c7c1c2b80239eb23e1c72e6bad3a71d9f43b203ac5a6fe4d8e93da3ba6bc309"
)
PH_D03A_TARGET_BUNDLE_DIGEST: Final = (
    "ph-d03a-exact-target-bundle:"
    "c5c2dfbf9c79157592fbfd33d692355977041e1eafe36db5bd679cfed66aa41a"
)
PH_D03A_DECISION_DIGEST: Final = (
    "sha256:"
    "33f13a39d4f2238b7fe329feb6dd0115e248ac222f39d0cb57c573a64fe454be"
)
PH_D03A_APPROVAL_DIGEST: Final = (
    "owner-approval-record:"
    "a9c552468bd6f656148030de28b914c2d6ad9b2bc095462ee6ba3e50f4cbe00a"
)

CONTRACT_PATH: Final = Path("distillation/input/sealed_audit_contract.json")
COMMITMENTS_PATH: Final = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/"
    "expected_commitments.json"
)
MANIFEST_PATH: Final = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/manifest.json"
)
RUNNER_CONTRACT_PATH: Final = Path(
    "distillation/frozen/sealed_audit/ph_d03b_v1/runner_contract.json"
)
FREEZE_REPORT_PATH: Final = Path(
    "distillation/artifacts/reports/sealed_audit_freeze.json"
)

TARGET_BUNDLE_PATH: Final = Path(
    "control/rev3/PH-D03A_OWNER_REVIEW_PACKAGE/exact_target_bundle.json"
)
DECISION_PATH: Final = Path(
    "control/rev3/OWNER_DECISION_CAPTURES/"
    "PH-D03A_TO_PH-D03B_20260731.json"
)
APPROVAL_PATH: Final = Path(
    "control/rev3/OWNER_APPROVAL_RECORDS/"
    "PH-D03A_TO_PH-D03B_20260731.json"
)
ATTESTATION_PATH: Final = Path(
    "control/rev3/PH-D03A_EVIDENCE_ATTESTATION.json"
)
CANDIDATE_SET_PATH: Final = Path(
    "distillation/artifacts/golden/candidate_cases.json"
)
GATE_COVERAGE_PATH: Final = Path(
    "distillation/artifacts/reports/golden_gate_coverage.json"
)
OWNER_REVIEW_REQUEST_PATH: Final = Path(
    "distillation/artifacts/golden/owner_review_request.json"
)

EXACT_INPUTS: Final[dict[Path, tuple[str, str]]] = {
    TARGET_BUNDLE_PATH: (
        "4a9087767a7dd85b7fc9be477c86ca94d6defb1d245443f804f5035c8bed57b3",
        PH_D03A_TARGET_BUNDLE_DIGEST,
    ),
    DECISION_PATH: (
        "3d3b2bd4e95be8f3006eea00961d128f81010756f125fe9a1730f09b33b3d668",
        PH_D03A_DECISION_DIGEST,
    ),
    APPROVAL_PATH: (
        "a1a0261cfde24cd95eb74d3be78fa30ffa0192083e054b5fb45cafa48c462e42",
        PH_D03A_APPROVAL_DIGEST,
    ),
    ATTESTATION_PATH: (
        "9f57b64c90aae1501aaae1c3a91fb288b362cd6f0988d54a8898dc2eb7ea75e6",
        PH_D03A_EVIDENCE_PAYLOAD_DIGEST,
    ),
    CANDIDATE_SET_PATH: (
        "36f1e31c586862e0bf7b1e985fdc4b5066994805d33600d930ff6ff85f76f685",
        "hds-golden-candidate-set:"
        "3e94a4814e542ae899bc38dae405461507decdea21a8926553eafca725ea09c2",
    ),
    GATE_COVERAGE_PATH: (
        "b687a9867c8393831ba31fc7fae92b735f41716c351741920c66b11a15ecd4b8",
        "hds-golden-gate-coverage:"
        "65492ed189b0cdc07a60dc65465a99b7f2b0d05d5e96d598cdc4435ff0ca9fef",
    ),
    OWNER_REVIEW_REQUEST_PATH: (
        "dfd2d238784b708a82b998b0e32fe2b4cc44503cdd1670fe0a1b0921b610143c",
        "hds-golden-owner-review-request:"
        "496c3f17a1cd6a79d9d3e979fa0a60848d4ff13ff69cf0d80e94b36ebf575ec4",
    ),
}

SEALED_ERROR_CODES: Final = (
    "D03B_INPUT_DRIFT",
    "D03B_AUTHORITY_MISMATCH",
    "D03B_TARGET_COUNT_MISMATCH",
    "D03B_TARGET_MISMATCH",
    "D03B_EXPECTED_PLAINTEXT_FORBIDDEN",
    "D03B_CONTENT_DIGEST_MISMATCH",
    "D03B_REFERENCE_INVALID",
    "D03B_NONCANONICAL_ARTIFACT",
    "D03B_LEDGER_INSIDE_REPOSITORY",
    "D03B_CORPUS_VERSION_CONSUMED",
    "D03B_SUBMISSION_INVALID",
    "D03B_AUDIT_MISMATCH",
)

AuditStatus = Literal["PASS", "FAIL"]


class SealedAuditError(ValueError):
    """A stable fail-closed PH-D03B sealed-audit error."""


def _fail(code: str, context: str | None = None) -> Never:
    if code not in SEALED_ERROR_CODES:
        raise AssertionError("unknown PH-D03B error code")
    raise SealedAuditError(code + (":" + context if context else ""))


def _policy(id_field: str | None = None) -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({id_field}) if id_field else frozenset(),
        digest_fields=frozenset({"content_digest"}),
    )


def _bind(
    artifact: JsonObject,
    *,
    namespace: str,
    id_field: str | None = None,
) -> JsonObject:
    artifact["content_digest"] = ""
    if id_field is not None:
        artifact[id_field] = ""
        artifact[id_field] = content_derived_id(
            namespace + "-id",
            artifact,
            policy=_policy(id_field),
        )
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=_policy(id_field),
    )
    return artifact


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_object(
    project_root: Path,
    relative_path: Path,
    *,
    expected_sha256: str | None = None,
    require_canonical: bool = False,
) -> tuple[JsonObject, bytes]:
    path = project_root / relative_path
    try:
        payload = path.read_bytes()
    except OSError:
        _fail("D03B_INPUT_DRIFT", relative_path.as_posix())
    if expected_sha256 is not None and _sha256(payload) != expected_sha256:
        _fail("D03B_INPUT_DRIFT", relative_path.as_posix())
    if require_canonical:
        try:
            value = verify_canonical_json_document_bytes(payload)
        except (TypeError, ValueError):
            _fail("D03B_NONCANONICAL_ARTIFACT", relative_path.as_posix())
    else:
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail("D03B_INPUT_DRIFT", relative_path.as_posix())
    if not isinstance(value, dict):
        _fail("D03B_INPUT_DRIFT", relative_path.as_posix())
    return value, payload


def _exact_sources(
    project_root: Path,
) -> dict[Path, tuple[JsonObject, bytes]]:
    result: dict[Path, tuple[JsonObject, bytes]] = {}
    canonical_paths = {
        CANDIDATE_SET_PATH,
        GATE_COVERAGE_PATH,
        OWNER_REVIEW_REQUEST_PATH,
    }
    for path, (expected_sha256, _) in EXACT_INPUTS.items():
        result[path] = _read_object(
            project_root,
            path,
            expected_sha256=expected_sha256,
            require_canonical=path in canonical_paths,
        )
    return result


def _verify_authority(
    sources: Mapping[Path, tuple[JsonObject, bytes]],
) -> None:
    target_bundle = sources[TARGET_BUNDLE_PATH][0]
    decision = sources[DECISION_PATH][0]
    approval = sources[APPROVAL_PATH][0]
    attestation = sources[ATTESTATION_PATH][0]
    if (
        target_bundle.get("content_digest")
        != PH_D03A_TARGET_BUNDLE_DIGEST
        or target_bundle.get("target_count") != EXPECTED_COMMITMENT_COUNT
        or decision.get("owner_decision_content_digest")
        != PH_D03A_DECISION_DIGEST
        or decision.get("gate_result_digest")
        != PH_D03A_TARGET_BUNDLE_DIGEST
        or decision.get("decision")
        != (
            "APPROVE_ALL_SIXTEEN_PROVISIONAL_EXPECTATIONS_"
            "AND_AUTHORIZE_NEXT_PHASE_ENTRY"
        )
        or approval.get("approval_artifact_digest")
        != PH_D03A_APPROVAL_DIGEST
        or approval.get("owner_decision_capture_digest")
        != PH_D03A_DECISION_DIGEST
        or approval.get("target_evidence_commit")
        != PH_D03A_EVIDENCE_COMMIT
        or approval.get("target_artifact_digest")
        != PH_D03A_EVIDENCE_PAYLOAD_DIGEST
        or approval.get("approved_transition")
        != "PH-D03A_TO_PH-D03B"
        or approval.get("next_phase_id") != "PH-D03B"
        or approval.get("next_phase_authorized") is not True
        or attestation.get("evidence_commit")
        != PH_D03A_EVIDENCE_COMMIT
        or attestation.get("implementation_commit")
        != PH_D03A_IMPLEMENTATION_COMMIT
        or attestation.get("evidence_payload_digest")
        != PH_D03A_EVIDENCE_PAYLOAD_DIGEST
        or attestation.get("exact_target_bundle_digest")
        != PH_D03A_TARGET_BUNDLE_DIGEST
    ):
        _fail("D03B_AUTHORITY_MISMATCH")


def _expected_digests(
    sources: Mapping[Path, tuple[JsonObject, bytes]],
) -> tuple[str, ...]:
    target_bundle = sources[TARGET_BUNDLE_PATH][0]
    candidate_set = sources[CANDIDATE_SET_PATH][0]
    raw_targets = target_bundle.get("targets")
    raw_cases = candidate_set.get("cases")
    if (
        not isinstance(raw_targets, list)
        or len(raw_targets) != EXPECTED_COMMITMENT_COUNT
        or not isinstance(raw_cases, list)
        or len(raw_cases) != EXPECTED_COMMITMENT_COUNT
    ):
        _fail("D03B_TARGET_COUNT_MISMATCH")
    cases: dict[str, Mapping[str, JsonValue]] = {}
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            _fail("D03B_TARGET_MISMATCH")
        fixture_id = raw_case.get("fixture_id")
        if not isinstance(fixture_id, str) or fixture_id in cases:
            _fail("D03B_TARGET_MISMATCH")
        cases[fixture_id] = cast(Mapping[str, JsonValue], raw_case)
    digests: list[str] = []
    for raw_target in raw_targets:
        if not isinstance(raw_target, Mapping):
            _fail("D03B_TARGET_MISMATCH")
        fixture_id = raw_target.get("fixture_id")
        expected_digest = raw_target.get(
            "provisional_expected_artifact_digest"
        )
        case = cases.get(cast(str, fixture_id))
        if (
            not isinstance(fixture_id, str)
            or not isinstance(expected_digest, str)
            or case is None
            or raw_target.get("requested_decision") != "APPROVE"
            or raw_target.get("candidate_case_digest")
            != case.get("content_digest")
        ):
            _fail("D03B_TARGET_MISMATCH")
        expected = case.get("provisional_expected_artifact")
        if not isinstance(expected, Mapping):
            _fail("D03B_TARGET_MISMATCH")
        recomputed = logical_content_digest(
            "hds-golden-provisional-expected-artifact",
            expected,
            policy=DigestExclusionPolicy(
                digest_fields=frozenset({"content_digest"}),
            ),
        )
        if (
            expected.get("fixture_id") != fixture_id
            or expected.get("content_digest") != expected_digest
            or not hmac.compare_digest(recomputed, expected_digest)
        ):
            _fail("D03B_TARGET_MISMATCH")
        digests.append(expected_digest)
    if len(set(digests)) != EXPECTED_COMMITMENT_COUNT:
        _fail("D03B_TARGET_COUNT_MISMATCH")
    return tuple(sorted(digests))


def _source_records(
    sources: Mapping[Path, tuple[JsonObject, bytes]],
) -> list[JsonValue]:
    return _source_records_from_payloads(
        {path: source[1] for path, source in sources.items()}
    )


def _source_records_from_payloads(
    payloads: Mapping[Path, bytes],
) -> list[JsonValue]:
    records: list[JsonValue] = []
    for path in sorted(EXACT_INPUTS, key=lambda item: item.as_posix()):
        _, expected_bound_digest = EXACT_INPUTS[path]
        try:
            payload = payloads[path]
        except KeyError:
            _fail("D03B_INPUT_DRIFT", path.as_posix())
        records.append(
            {
                "path": path.as_posix(),
                "sha256": _sha256(payload),
                "bound_digest": expected_bound_digest,
                "access_mode": (
                    "RAW_HASH_ONLY_AT_AUDIT_TIME"
                    if path
                    in {
                        CANDIDATE_SET_PATH,
                        GATE_COVERAGE_PATH,
                        OWNER_REVIEW_REQUEST_PATH,
                    }
                    else "CONTROL_AUTHORITY_BINDING"
                ),
            }
        )
    return records


def build_sealed_audit_contract() -> JsonObject:
    """Build the immutable PH-D03B contract."""

    contract: JsonObject = {
        "schema_version": SEALED_AUDIT_CONTRACT_VERSION,
        "contract_id": "",
        "phase_id": "PH-D03B",
        "corpus_version": CORPUS_VERSION,
        "authority": {
            "work_block_frame_digest": PH_D03B_FRAME_DIGEST,
            "preinventory_digest": PH_D03B_PREINVENTORY_DIGEST,
            "phase_transition_digest": PH_D03B_TRANSITION_DIGEST,
            "input_evidence_commit": PH_D03A_EVIDENCE_COMMIT,
            "input_evidence_payload_digest": (
                PH_D03A_EVIDENCE_PAYLOAD_DIGEST
            ),
            "exact_target_bundle_digest": PH_D03A_TARGET_BUNDLE_DIGEST,
            "content_specific_owner_decision_digest": (
                PH_D03A_DECISION_DIGEST
            ),
            "content_specific_owner_approval_digest": (
                PH_D03A_APPROVAL_DIGEST
            ),
        },
        "freeze_contract": {
            "expected_commitment_count": EXPECTED_COMMITMENT_COUNT,
            "expected_storage": "DIGEST_COMMITMENTS_ONLY",
            "expected_plaintext_stored_count": 0,
            "automatic_expectation_update_allowed": False,
            "new_approval_required_for_any_change": True,
            "source_digest_freeze_required": True,
            "golden_and_sealed_namespaces_distinct": True,
        },
        "runner_contract": {
            "output_values": ["FAIL", "PASS"],
            "output_additional_fields_allowed": False,
            "failure_expected_plaintext_disclosure": False,
            "failure_expected_digest_disclosure": False,
            "failure_fixture_identifier_disclosure": False,
            "submission_digest_recomputation_required": True,
            "consume_policy": "CONSUME_ON_FIRST_AUDIT_ATTEMPT",
            "ledger_location": "CALLER_SUPPLIED_OUTSIDE_REPOSITORY",
        },
        "gate_contract": {
            "required_gate_ids": ["DG-06", "DG-14"],
            "DG-06": "PASS_ORIGIN_AND_CLAIM_BOUNDARY_PRESERVED",
            "DG-14": "PASS_CONTENT_SPECIFIC_OWNER_AUTHORITY_BOUND",
        },
        "claim_boundary": {
            "allowed": "DISTILLATION_CONFORMANCE_CORPUS_FROZEN",
            "prohibited": [
                "GENERALITY_PROVEN",
                "REAL_TEACHER_EXACT_FIT",
                "CAUSAL_MECHANISM_ESTABLISHED",
                "RULE_PROMOTED",
                "STRUCTURE_BUNDLE_OWNER_APPROVED",
                "BRIDGE_READY",
                "RUNTIME_READY",
                "OFFICIAL_READY",
            ],
        },
        "stable_error_codes": list(SEALED_ERROR_CODES),
        "digest_excluded_fields": [
            "content_digest",
            "contract_id",
        ],
        "content_digest": "",
    }
    return _bind(
        contract,
        namespace="hds-sealed-audit-contract",
        id_field="contract_id",
    )


def build_expected_commitments(project_root: Path) -> JsonObject:
    """Freeze approved expectations as an unlabeled digest commitment set."""

    sources = _exact_sources(project_root)
    _verify_authority(sources)
    digests = _expected_digests(sources)
    artifact: JsonObject = {
        "schema_version": SEALED_COMMITMENT_SET_VERSION,
        "commitment_set_id": "",
        "phase_id": "PH-D03B",
        "corpus_version": CORPUS_VERSION,
        "commitment_count": len(digests),
        "commitments": list(digests),
        "commitment_order": "LEXICOGRAPHIC_DIGEST_ORDER",
        "label_disclosure": "NONE",
        "fixture_identifier_count": 0,
        "expected_plaintext_stored_count": 0,
        "source_target_bundle_digest": PH_D03A_TARGET_BUNDLE_DIGEST,
        "owner_decision_digest": PH_D03A_DECISION_DIGEST,
        "owner_approval_digest": PH_D03A_APPROVAL_DIGEST,
        "automatic_update_allowed": False,
        "digest_excluded_fields": [
            "content_digest",
            "commitment_set_id",
        ],
        "content_digest": "",
    }
    return _bind(
        artifact,
        namespace="hds-sealed-expected-commitment-set",
        id_field="commitment_set_id",
    )


def build_runner_contract(
    commitments: Mapping[str, JsonValue],
) -> JsonObject:
    """Build the status-only, one-use audit-runner contract."""

    artifact: JsonObject = {
        "schema_version": SEALED_RUNNER_CONTRACT_VERSION,
        "runner_contract_id": "",
        "phase_id": "PH-D03B",
        "corpus_version": CORPUS_VERSION,
        "commitment_set_digest": commitments["content_digest"],
        "input_contract": {
            "schema_version": SEALED_SUBMISSION_VERSION,
            "artifact_count": EXPECTED_COMMITMENT_COUNT,
            "recompute_logical_digest": True,
            "trust_declared_content_digest": False,
        },
        "output_contract": {
            "allowed_stdout_bytes_hex": [
                "4641494c0a",
                "504153530a",
            ],
            "allowed_values": ["FAIL", "PASS"],
            "additional_fields_allowed": False,
            "stderr_allowed": False,
            "expected_plaintext_disclosure": False,
            "expected_digest_disclosure": False,
            "fixture_identifier_disclosure": False,
            "mismatch_location_disclosure": False,
        },
        "consumption_contract": {
            "policy": "CONSUME_ON_FIRST_AUDIT_ATTEMPT",
            "atomic_reservation_required": True,
            "reserved_state_counts_as_consumed": True,
            "ledger_must_be_outside_repository": True,
            "reuse_result": "FAIL",
        },
        "digest_excluded_fields": [
            "content_digest",
            "runner_contract_id",
        ],
        "content_digest": "",
    }
    return _bind(
        artifact,
        namespace="hds-sealed-audit-runner-contract",
        id_field="runner_contract_id",
    )


def build_sealed_manifest(
    project_root: Path,
    contract: Mapping[str, JsonValue],
    commitments: Mapping[str, JsonValue],
    runner_contract: Mapping[str, JsonValue],
    encoded_inputs: Mapping[Path, bytes],
) -> JsonObject:
    """Bind sealed artifacts and raw source bytes without copying plaintext."""

    sources = _exact_sources(project_root)
    _verify_authority(sources)
    source_records = _source_records(sources)
    source_set_digest = logical_content_digest(
        "hds-sealed-source-set",
        {"sources": source_records},
        policy=DigestExclusionPolicy(),
    )
    artifact: JsonObject = {
        "schema_version": SEALED_MANIFEST_VERSION,
        "sealed_manifest_id": "",
        "phase_id": "PH-D03B",
        "corpus_version": CORPUS_VERSION,
        "freeze_status": "DISTILLATION_CONFORMANCE_CORPUS_FROZEN",
        "version_state": "FROZEN_UNCONSUMED",
        "source_set_digest": source_set_digest,
        "source_artifact_count": len(source_records),
        "source_artifacts": source_records,
        "sealed_artifacts": [
            {
                "path": CONTRACT_PATH.as_posix(),
                "sha256": _sha256(encoded_inputs[CONTRACT_PATH]),
                "content_digest": contract["content_digest"],
            },
            {
                "path": COMMITMENTS_PATH.as_posix(),
                "sha256": _sha256(encoded_inputs[COMMITMENTS_PATH]),
                "content_digest": commitments["content_digest"],
            },
            {
                "path": RUNNER_CONTRACT_PATH.as_posix(),
                "sha256": _sha256(encoded_inputs[RUNNER_CONTRACT_PATH]),
                "content_digest": runner_contract["content_digest"],
            },
        ],
        "expected_commitment_count": EXPECTED_COMMITMENT_COUNT,
        "expected_plaintext_stored_count": 0,
        "expected_storage": "OWNER_APPROVED_DIGEST_COMMITMENTS_ONLY",
        "golden_namespace": "distillation/artifacts/golden",
        "sealed_namespace": (
            "distillation/frozen/sealed_audit/ph_d03b_v1"
        ),
        "golden_and_sealed_namespaces_distinct": True,
        "implementation_expected_plaintext_access_allowed": False,
        "runner_output_contract": "PASS_OR_FAIL_ONLY",
        "consumption_policy": "CONSUME_ON_FIRST_AUDIT_ATTEMPT",
        "consumption_ledger_location": (
            "CALLER_SUPPLIED_MUTABLE_PATH_OUTSIDE_REPOSITORY"
        ),
        "actual_audit_consumption_count": 0,
        "gate_results": {
            "DG-06": "PASS_ORIGIN_AND_CLAIM_BOUNDARY_PRESERVED",
            "DG-14": "PASS_CONTENT_SPECIFIC_OWNER_AUTHORITY_BOUND",
        },
        "claim_boundary": (
            "FROZEN_IMPLEMENTATION_CONFORMANCE_INPUT_NOT_GENERALITY_PROOF"
        ),
        "digest_excluded_fields": [
            "content_digest",
            "sealed_manifest_id",
        ],
        "content_digest": "",
    }
    return _bind(
        artifact,
        namespace="hds-sealed-audit-manifest",
        id_field="sealed_manifest_id",
    )


def build_freeze_report(
    manifest: Mapping[str, JsonValue],
    commitments: Mapping[str, JsonValue],
    runner_contract: Mapping[str, JsonValue],
) -> JsonObject:
    """Build deterministic PH-D03B freeze and gate evidence."""

    artifact: JsonObject = {
        "schema_version": SEALED_FREEZE_REPORT_VERSION,
        "report_id": "",
        "phase_id": "PH-D03B",
        "corpus_version": CORPUS_VERSION,
        "manifest_digest": manifest["content_digest"],
        "commitment_set_digest": commitments["content_digest"],
        "runner_contract_digest": runner_contract["content_digest"],
        "status": "PASS",
        "exit_state": "DISTILLATION_CONFORMANCE_CORPUS_FROZEN",
        "checks": {
            "approved_target_count": EXPECTED_COMMITMENT_COUNT,
            "frozen_commitment_count": EXPECTED_COMMITMENT_COUNT,
            "unique_commitment_count": EXPECTED_COMMITMENT_COUNT,
            "source_digests_frozen": True,
            "expected_plaintext_stored_count": 0,
            "automatic_expectation_update_allowed": False,
            "runner_output_values": ["FAIL", "PASS"],
            "failure_expected_plaintext_disclosure": False,
            "version_consumption_policy": (
                "CONSUME_ON_FIRST_AUDIT_ATTEMPT"
            ),
            "golden_and_sealed_namespaces_distinct": True,
        },
        "gate_entries": [
            {
                "gate_id": "DG-06",
                "result": "PASS",
                "reason_code": (
                    "PASS_ORIGIN_AND_CLAIM_BOUNDARY_PRESERVED"
                ),
                "behaviorally_recomputed": True,
            },
            {
                "gate_id": "DG-14",
                "result": "PASS",
                "reason_code": (
                    "PASS_CONTENT_SPECIFIC_OWNER_AUTHORITY_BOUND"
                ),
                "behaviorally_recomputed": True,
            },
        ],
        "failed_requirement_count": 0,
        "actual_sealed_corpus_execution_count": 0,
        "digest_excluded_fields": [
            "content_digest",
            "report_id",
        ],
        "content_digest": "",
    }
    return _bind(
        artifact,
        namespace="hds-sealed-audit-freeze-report",
        id_field="report_id",
    )


def _forbidden_plaintext_key(value: object) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                return "NON_STRING_KEY"
            if key in {
                "provisional_expected_artifact",
                "expected_artifact",
                "expected_payload",
                "fixture_id",
            }:
                return key
            found = _forbidden_plaintext_key(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _forbidden_plaintext_key(child)
            if found is not None:
                return found
    return None


def _validate_bound_artifact(
    artifact: Mapping[str, JsonValue],
    *,
    namespace: str,
    id_field: str,
) -> None:
    if artifact.get("content_digest") != logical_content_digest(
        namespace,
        artifact,
        policy=_policy(id_field),
    ):
        _fail("D03B_CONTENT_DIGEST_MISMATCH", namespace)
    if artifact.get(id_field) != content_derived_id(
        namespace + "-id",
        artifact,
        policy=_policy(id_field),
    ):
        _fail("D03B_CONTENT_DIGEST_MISMATCH", id_field)


def validate_expected_commitments(
    commitments: Mapping[str, JsonValue],
) -> None:
    _validate_bound_artifact(
        commitments,
        namespace="hds-sealed-expected-commitment-set",
        id_field="commitment_set_id",
    )
    raw = commitments.get("commitments")
    if (
        commitments.get("schema_version")
        != SEALED_COMMITMENT_SET_VERSION
        or commitments.get("corpus_version") != CORPUS_VERSION
        or commitments.get("phase_id") != "PH-D03B"
        or commitments.get("commitment_count")
        != EXPECTED_COMMITMENT_COUNT
        or not isinstance(raw, list)
        or len(raw) != EXPECTED_COMMITMENT_COUNT
        or not all(isinstance(item, str) for item in raw)
        or commitments.get("fixture_identifier_count") != 0
        or commitments.get("expected_plaintext_stored_count") != 0
        or commitments.get("automatic_update_allowed") is not False
        or commitments.get("commitment_order")
        != "LEXICOGRAPHIC_DIGEST_ORDER"
        or commitments.get("label_disclosure") != "NONE"
        or commitments.get("source_target_bundle_digest")
        != PH_D03A_TARGET_BUNDLE_DIGEST
        or commitments.get("owner_decision_digest")
        != PH_D03A_DECISION_DIGEST
        or commitments.get("owner_approval_digest")
        != PH_D03A_APPROVAL_DIGEST
    ):
        _fail("D03B_TARGET_COUNT_MISMATCH")
    typed_raw = cast(list[str], raw)
    if (
        typed_raw != sorted(typed_raw)
        or len(set(typed_raw)) != EXPECTED_COMMITMENT_COUNT
    ):
        _fail("D03B_TARGET_COUNT_MISMATCH")
    forbidden = _forbidden_plaintext_key(commitments)
    if forbidden is not None:
        _fail("D03B_EXPECTED_PLAINTEXT_FORBIDDEN", forbidden)


def validate_sealed_audit_contract(
    contract: Mapping[str, JsonValue],
) -> None:
    """Validate the immutable PH-D03B authority and disclosure contract."""

    _validate_bound_artifact(
        contract,
        namespace="hds-sealed-audit-contract",
        id_field="contract_id",
    )
    authority = contract.get("authority")
    freeze = contract.get("freeze_contract")
    runner = contract.get("runner_contract")
    gates = contract.get("gate_contract")
    if (
        contract.get("schema_version") != SEALED_AUDIT_CONTRACT_VERSION
        or contract.get("phase_id") != "PH-D03B"
        or contract.get("corpus_version") != CORPUS_VERSION
        or not isinstance(authority, Mapping)
        or authority.get("work_block_frame_digest") != PH_D03B_FRAME_DIGEST
        or authority.get("preinventory_digest")
        != PH_D03B_PREINVENTORY_DIGEST
        or authority.get("phase_transition_digest")
        != PH_D03B_TRANSITION_DIGEST
        or authority.get("input_evidence_commit")
        != PH_D03A_EVIDENCE_COMMIT
        or authority.get("input_evidence_payload_digest")
        != PH_D03A_EVIDENCE_PAYLOAD_DIGEST
        or authority.get("exact_target_bundle_digest")
        != PH_D03A_TARGET_BUNDLE_DIGEST
        or authority.get("content_specific_owner_decision_digest")
        != PH_D03A_DECISION_DIGEST
        or authority.get("content_specific_owner_approval_digest")
        != PH_D03A_APPROVAL_DIGEST
        or not isinstance(freeze, Mapping)
        or freeze.get("expected_commitment_count")
        != EXPECTED_COMMITMENT_COUNT
        or freeze.get("expected_storage") != "DIGEST_COMMITMENTS_ONLY"
        or freeze.get("expected_plaintext_stored_count") != 0
        or freeze.get("automatic_expectation_update_allowed") is not False
        or freeze.get("new_approval_required_for_any_change") is not True
        or freeze.get("golden_and_sealed_namespaces_distinct") is not True
        or not isinstance(runner, Mapping)
        or runner.get("output_values") != ["FAIL", "PASS"]
        or runner.get("output_additional_fields_allowed") is not False
        or runner.get("failure_expected_plaintext_disclosure") is not False
        or runner.get("failure_expected_digest_disclosure") is not False
        or runner.get("failure_fixture_identifier_disclosure") is not False
        or runner.get("consume_policy")
        != "CONSUME_ON_FIRST_AUDIT_ATTEMPT"
        or runner.get("ledger_location")
        != "CALLER_SUPPLIED_OUTSIDE_REPOSITORY"
        or not isinstance(gates, Mapping)
        or gates.get("required_gate_ids") != ["DG-06", "DG-14"]
    ):
        _fail("D03B_REFERENCE_INVALID", "contract")
    forbidden = _forbidden_plaintext_key(contract)
    if forbidden is not None:
        _fail("D03B_EXPECTED_PLAINTEXT_FORBIDDEN", forbidden)


def validate_runner_contract(
    runner_contract: Mapping[str, JsonValue],
    commitments: Mapping[str, JsonValue],
) -> None:
    _validate_bound_artifact(
        runner_contract,
        namespace="hds-sealed-audit-runner-contract",
        id_field="runner_contract_id",
    )
    output = runner_contract.get("output_contract")
    consumption = runner_contract.get("consumption_contract")
    input_contract = runner_contract.get("input_contract")
    if (
        runner_contract.get("schema_version")
        != SEALED_RUNNER_CONTRACT_VERSION
        or runner_contract.get("phase_id") != "PH-D03B"
        or runner_contract.get("corpus_version") != CORPUS_VERSION
        or runner_contract.get("commitment_set_digest")
        != commitments.get("content_digest")
        or not isinstance(input_contract, Mapping)
        or input_contract.get("schema_version") != SEALED_SUBMISSION_VERSION
        or input_contract.get("artifact_count")
        != EXPECTED_COMMITMENT_COUNT
        or input_contract.get("recompute_logical_digest") is not True
        or input_contract.get("trust_declared_content_digest") is not False
        or not isinstance(output, Mapping)
        or output.get("allowed_stdout_bytes_hex")
        != ["4641494c0a", "504153530a"]
        or output.get("allowed_values") != ["FAIL", "PASS"]
        or output.get("additional_fields_allowed") is not False
        or output.get("stderr_allowed") is not False
        or output.get("expected_plaintext_disclosure") is not False
        or output.get("expected_digest_disclosure") is not False
        or output.get("fixture_identifier_disclosure") is not False
        or output.get("mismatch_location_disclosure") is not False
        or not isinstance(consumption, Mapping)
        or consumption.get("policy")
        != "CONSUME_ON_FIRST_AUDIT_ATTEMPT"
        or consumption.get("atomic_reservation_required") is not True
        or consumption.get("reserved_state_counts_as_consumed") is not True
        or consumption.get("ledger_must_be_outside_repository")
        is not True
        or consumption.get("reuse_result") != "FAIL"
    ):
        _fail("D03B_REFERENCE_INVALID", "runner_contract")


def _validate_manifest_invariants(
    manifest: Mapping[str, JsonValue],
) -> None:
    _validate_bound_artifact(
        manifest,
        namespace="hds-sealed-audit-manifest",
        id_field="sealed_manifest_id",
    )
    if (
        manifest.get("schema_version") != SEALED_MANIFEST_VERSION
        or manifest.get("corpus_version") != CORPUS_VERSION
        or manifest.get("freeze_status")
        != "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
        or manifest.get("phase_id") != "PH-D03B"
        or manifest.get("version_state") != "FROZEN_UNCONSUMED"
        or manifest.get("source_artifact_count") != len(EXACT_INPUTS)
        or manifest.get("expected_commitment_count")
        != EXPECTED_COMMITMENT_COUNT
        or manifest.get("expected_plaintext_stored_count") != 0
        or manifest.get("golden_and_sealed_namespaces_distinct")
        is not True
        or manifest.get("implementation_expected_plaintext_access_allowed")
        is not False
        or manifest.get("runner_output_contract")
        != "PASS_OR_FAIL_ONLY"
        or manifest.get("consumption_policy")
        != "CONSUME_ON_FIRST_AUDIT_ATTEMPT"
        or manifest.get("consumption_ledger_location")
        != "CALLER_SUPPLIED_MUTABLE_PATH_OUTSIDE_REPOSITORY"
        or manifest.get("actual_audit_consumption_count") != 0
        or manifest.get("gate_results")
        != {
            "DG-06": "PASS_ORIGIN_AND_CLAIM_BOUNDARY_PRESERVED",
            "DG-14": "PASS_CONTENT_SPECIFIC_OWNER_AUTHORITY_BOUND",
        }
    ):
        _fail("D03B_REFERENCE_INVALID", "manifest")
    forbidden = _forbidden_plaintext_key(manifest)
    if forbidden is not None:
        _fail("D03B_EXPECTED_PLAINTEXT_FORBIDDEN", forbidden)


def validate_sealed_manifest(
    project_root: Path,
    manifest: Mapping[str, JsonValue],
    contract: Mapping[str, JsonValue],
    commitments: Mapping[str, JsonValue],
    runner_contract: Mapping[str, JsonValue],
    encoded_inputs: Mapping[Path, bytes],
) -> None:
    _validate_manifest_invariants(manifest)
    sealed = manifest.get("sealed_artifacts")
    expected_sealed = [
        {
            "path": CONTRACT_PATH.as_posix(),
            "sha256": _sha256(encoded_inputs[CONTRACT_PATH]),
            "content_digest": contract["content_digest"],
        },
        {
            "path": COMMITMENTS_PATH.as_posix(),
            "sha256": _sha256(encoded_inputs[COMMITMENTS_PATH]),
            "content_digest": commitments["content_digest"],
        },
        {
            "path": RUNNER_CONTRACT_PATH.as_posix(),
            "sha256": _sha256(encoded_inputs[RUNNER_CONTRACT_PATH]),
            "content_digest": runner_contract["content_digest"],
        },
    ]
    if sealed != expected_sealed:
        _fail("D03B_REFERENCE_INVALID", "sealed_artifacts")
    sources = _exact_sources(project_root)
    source_records = _source_records(sources)
    if manifest.get("source_artifacts") != source_records:
        _fail("D03B_INPUT_DRIFT", "source_artifacts")
    expected_source_set_digest = logical_content_digest(
        "hds-sealed-source-set",
        {"sources": source_records},
        policy=DigestExclusionPolicy(),
    )
    if manifest.get("source_set_digest") != expected_source_set_digest:
        _fail("D03B_INPUT_DRIFT", "source_set_digest")
def validate_freeze_report(
    report: Mapping[str, JsonValue],
    manifest: Mapping[str, JsonValue],
    commitments: Mapping[str, JsonValue],
    runner_contract: Mapping[str, JsonValue],
) -> None:
    _validate_bound_artifact(
        report,
        namespace="hds-sealed-audit-freeze-report",
        id_field="report_id",
    )
    entries = report.get("gate_entries")
    if (
        report.get("schema_version") != SEALED_FREEZE_REPORT_VERSION
        or report.get("status") != "PASS"
        or report.get("exit_state")
        != "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
        or report.get("manifest_digest")
        != manifest.get("content_digest")
        or report.get("commitment_set_digest")
        != commitments.get("content_digest")
        or report.get("runner_contract_digest")
        != runner_contract.get("content_digest")
        or report.get("failed_requirement_count") != 0
        or report.get("actual_sealed_corpus_execution_count") != 0
        or not isinstance(entries, list)
        or [item.get("gate_id") for item in entries if isinstance(item, Mapping)]
        != ["DG-06", "DG-14"]
        or any(
            not isinstance(item, Mapping)
            or item.get("result") != "PASS"
            or item.get("behaviorally_recomputed") is not True
            for item in entries
        )
    ):
        _fail("D03B_REFERENCE_INVALID", "freeze_report")


def build_phase_d03b_artifacts(project_root: Path) -> dict[str, bytes]:
    """Build and validate all five deterministic PH-D03B artifacts."""

    contract = build_sealed_audit_contract()
    validate_sealed_audit_contract(contract)
    commitments = build_expected_commitments(project_root)
    validate_expected_commitments(commitments)
    runner_contract = build_runner_contract(commitments)
    validate_runner_contract(runner_contract, commitments)
    encoded_inputs = {
        CONTRACT_PATH: canonical_json_document_bytes(contract),
        COMMITMENTS_PATH: canonical_json_document_bytes(commitments),
        RUNNER_CONTRACT_PATH: canonical_json_document_bytes(runner_contract),
    }
    manifest = build_sealed_manifest(
        project_root,
        contract,
        commitments,
        runner_contract,
        encoded_inputs,
    )
    validate_sealed_manifest(
        project_root,
        manifest,
        contract,
        commitments,
        runner_contract,
        encoded_inputs,
    )
    report = build_freeze_report(
        manifest,
        commitments,
        runner_contract,
    )
    validate_freeze_report(
        report,
        manifest,
        commitments,
        runner_contract,
    )
    objects: dict[Path, Mapping[str, JsonValue]] = {
        CONTRACT_PATH: contract,
        COMMITMENTS_PATH: commitments,
        MANIFEST_PATH: manifest,
        RUNNER_CONTRACT_PATH: runner_contract,
        FREEZE_REPORT_PATH: report,
    }
    encoded = {
        path.as_posix(): canonical_json_document_bytes(value)
        for path, value in sorted(
            objects.items(),
            key=lambda item: item[0].as_posix(),
        )
    }
    if len(encoded) != SEALED_ARTIFACT_COUNT:
        _fail("D03B_REFERENCE_INVALID", "artifact_count")
    return encoded


def write_phase_d03b_artifacts(project_root: Path) -> dict[str, str]:
    """Write only deterministic PH-D03B-owned artifact paths."""

    artifacts = build_phase_d03b_artifacts(project_root)
    result: dict[str, str] = {}
    for relative_path, payload in artifacts.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        result[relative_path] = _sha256(payload)
    return result


def _load_runtime_bundle(
    project_root: Path,
) -> tuple[JsonObject, JsonObject]:
    manifest, _ = _read_object(
        project_root,
        MANIFEST_PATH,
        require_canonical=True,
    )
    commitments, commitment_bytes = _read_object(
        project_root,
        COMMITMENTS_PATH,
        require_canonical=True,
    )
    runner_contract, runner_bytes = _read_object(
        project_root,
        RUNNER_CONTRACT_PATH,
        require_canonical=True,
    )
    contract, contract_bytes = _read_object(
        project_root,
        CONTRACT_PATH,
        require_canonical=True,
    )
    validate_sealed_audit_contract(contract)
    _validate_manifest_invariants(manifest)
    validate_expected_commitments(commitments)
    validate_runner_contract(runner_contract, commitments)
    sealed = manifest.get("sealed_artifacts")
    expected = [
        {
            "path": CONTRACT_PATH.as_posix(),
            "sha256": _sha256(contract_bytes),
            "content_digest": contract.get("content_digest"),
        },
        {
            "path": COMMITMENTS_PATH.as_posix(),
            "sha256": _sha256(commitment_bytes),
            "content_digest": commitments.get("content_digest"),
        },
        {
            "path": RUNNER_CONTRACT_PATH.as_posix(),
            "sha256": _sha256(runner_bytes),
            "content_digest": runner_contract.get("content_digest"),
        },
    ]
    if sealed != expected:
        _fail("D03B_REFERENCE_INVALID", "runtime_bundle")
    source_payloads: dict[Path, bytes] = {}
    for raw_path, (expected_sha256, _) in EXACT_INPUTS.items():
        try:
            payload = (project_root / raw_path).read_bytes()
        except OSError:
            _fail("D03B_INPUT_DRIFT", raw_path.as_posix())
        if not hmac.compare_digest(_sha256(payload), expected_sha256):
            _fail("D03B_INPUT_DRIFT", raw_path.as_posix())
        source_payloads[raw_path] = payload
    expected_sources = _source_records_from_payloads(source_payloads)
    if manifest.get("source_artifacts") != expected_sources:
        _fail("D03B_REFERENCE_INVALID", "source_artifacts")
    expected_source_set_digest = logical_content_digest(
        "hds-sealed-source-set",
        {"sources": expected_sources},
        policy=DigestExclusionPolicy(),
    )
    if manifest.get("source_set_digest") != expected_source_set_digest:
        _fail("D03B_REFERENCE_INVALID", "source_set_digest")
    return manifest, commitments


def _ledger_outside_repository(
    project_root: Path,
    ledger_path: Path,
) -> Path:
    root = project_root.resolve()
    parent = ledger_path.parent.resolve()
    resolved = parent / ledger_path.name
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    _fail("D03B_LEDGER_INSIDE_REPOSITORY")


def _claim_ledger(
    ledger_path: Path,
    manifest: Mapping[str, JsonValue],
) -> bool:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    reservation: JsonObject = {
        "schema_version": SEALED_LEDGER_VERSION,
        "corpus_version": CORPUS_VERSION,
        "sealed_manifest_digest": manifest["content_digest"],
        "state": "RESERVED_CONSUMED",
        "result": None,
    }
    payload = canonical_json_document_bytes(reservation)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(ledger_path, flags, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    return True


def _finalize_ledger(
    ledger_path: Path,
    manifest: Mapping[str, JsonValue],
    *,
    status: AuditStatus,
    submission_sha256: str,
) -> None:
    completed: JsonObject = {
        "schema_version": SEALED_LEDGER_VERSION,
        "corpus_version": CORPUS_VERSION,
        "sealed_manifest_digest": manifest["content_digest"],
        "state": "CONSUMED",
        "result": status,
        "submission_sha256": submission_sha256,
    }
    payload = canonical_json_document_bytes(completed)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".sealed-audit-ledger.",
        dir=ledger_path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, ledger_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _submission_commitments(payload: bytes) -> tuple[str, ...]:
    try:
        value = verify_canonical_json_document_bytes(payload)
    except (TypeError, ValueError):
        _fail("D03B_SUBMISSION_INVALID")
    if not isinstance(value, dict):
        _fail("D03B_SUBMISSION_INVALID")
    artifacts = value.get("artifacts")
    if (
        set(value)
        != {
            "artifact_count",
            "artifacts",
            "corpus_version",
            "schema_version",
        }
        or
        value.get("schema_version") != SEALED_SUBMISSION_VERSION
        or value.get("corpus_version") != CORPUS_VERSION
        or value.get("artifact_count") != EXPECTED_COMMITMENT_COUNT
        or not isinstance(artifacts, list)
        or len(artifacts) != EXPECTED_COMMITMENT_COUNT
    ):
        _fail("D03B_SUBMISSION_INVALID")
    digests: list[str] = []
    for raw in artifacts:
        if not isinstance(raw, Mapping):
            _fail("D03B_SUBMISSION_INVALID")
        declared = raw.get("content_digest")
        if not isinstance(declared, str):
            _fail("D03B_SUBMISSION_INVALID")
        recomputed = logical_content_digest(
            "hds-golden-provisional-expected-artifact",
            raw,
            policy=DigestExclusionPolicy(
                digest_fields=frozenset({"content_digest"}),
            ),
        )
        if not hmac.compare_digest(declared, recomputed):
            _fail("D03B_SUBMISSION_INVALID")
        digests.append(recomputed)
    if len(set(digests)) != EXPECTED_COMMITMENT_COUNT:
        _fail("D03B_SUBMISSION_INVALID")
    return tuple(sorted(digests))


def audit_sealed_submission(
    project_root: Path,
    submission_path: Path,
    ledger_path: Path,
) -> AuditStatus:
    """Run one status-only audit attempt and consume the corpus version."""

    try:
        manifest, commitments = _load_runtime_bundle(project_root)
        external_ledger = _ledger_outside_repository(
            project_root,
            ledger_path,
        )
    except (OSError, TypeError, ValueError):
        return "FAIL"
    try:
        if not _claim_ledger(external_ledger, manifest):
            return "FAIL"
    except OSError:
        return "FAIL"

    status: AuditStatus = "FAIL"
    submission_sha256 = "0" * 64
    try:
        payload = submission_path.read_bytes()
        submission_sha256 = _sha256(payload)
        actual = _submission_commitments(payload)
        expected_raw = commitments.get("commitments")
        if not isinstance(expected_raw, list) or not all(
            isinstance(item, str) for item in expected_raw
        ):
            _fail("D03B_REFERENCE_INVALID", "commitments")
        expected = tuple(cast(list[str], expected_raw))
        actual_aggregate = hashlib.sha256(
            canonical_json_bytes(list(actual))
        ).digest()
        expected_aggregate = hashlib.sha256(
            canonical_json_bytes(list(expected))
        ).digest()
        if hmac.compare_digest(actual_aggregate, expected_aggregate):
            status = "PASS"
    except (OSError, TypeError, ValueError):
        status = "FAIL"
    try:
        _finalize_ledger(
            external_ledger,
            manifest,
            status=status,
            submission_sha256=submission_sha256,
        )
    except OSError:
        return "FAIL"
    return status


__all__ = [
    "COMMITMENTS_PATH",
    "CONTRACT_PATH",
    "CORPUS_VERSION",
    "FREEZE_REPORT_PATH",
    "MANIFEST_PATH",
    "RUNNER_CONTRACT_PATH",
    "SEALED_ERROR_CODES",
    "SEALED_SUBMISSION_VERSION",
    "SealedAuditError",
    "audit_sealed_submission",
    "build_expected_commitments",
    "build_freeze_report",
    "build_phase_d03b_artifacts",
    "build_runner_contract",
    "build_sealed_audit_contract",
    "build_sealed_manifest",
    "validate_expected_commitments",
    "validate_freeze_report",
    "validate_runner_contract",
    "validate_sealed_audit_contract",
    "validate_sealed_manifest",
    "write_phase_d03b_artifacts",
]
