"""PH-D03A Golden conformance candidate-corpus tests."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import cast

import pytest
from hds_distill.canonical import (
    DigestExclusionPolicy,
    content_derived_id,
    logical_content_digest,
)
from hds_distill.golden_corpus import (
    CASE_SPECS,
    GATE_ASSERTIONS,
    GATE_IDS,
    GATE_OBLIGATION_CHECKS,
    GOLDEN_ERROR_CODES,
    REQUIRED_ARTIFACT_CLASSES,
    GoldenCorpusError,
    build_golden_conformance_contract,
    build_golden_gate_coverage_report,
    build_golden_owner_review_request,
    build_phase_d03a_candidate_artifacts,
    validate_golden_candidate_set,
    validate_golden_gate_coverage,
    validate_golden_owner_review_request,
)
from hds_distill.interpreter import execute_program
from hds_distill.ir_types import IRContractError, JsonObject

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
PH_D03A_ENTRY_BASE_COMMIT = "70722de7df8278c866de0734c97206c9952d731d"


@lru_cache(maxsize=1)
def _encoded_artifacts() -> dict[str, bytes]:
    return build_phase_d03a_candidate_artifacts(REPOSITORY_ROOT)


@lru_cache(maxsize=1)
def _artifacts() -> dict[str, JsonObject]:
    return {
        path: cast(JsonObject, json.loads(payload))
        for path, payload in _encoded_artifacts().items()
    }


def _artifact(path: str) -> JsonObject:
    return copy.deepcopy(_artifacts()[path])


def _candidate_set() -> JsonObject:
    return _artifact("distillation/artifacts/golden/candidate_cases.json")


def _contract() -> JsonObject:
    return _artifact("distillation/input/golden_conformance_contract.json")


def _case(fixture_id: str) -> JsonObject:
    cases = cast(list[JsonObject], _candidate_set()["cases"])
    return next(item for item in cases if item["fixture_id"] == fixture_id)


def _rebind_digest_only(
    artifact: JsonObject,
    namespace: str,
) -> None:
    artifact["content_digest"] = ""
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=DigestExclusionPolicy(
            digest_fields=frozenset({"content_digest"}),
        ),
    )


def _rebind_id_artifact(
    artifact: JsonObject,
    *,
    namespace: str,
    id_field: str,
) -> None:
    policy = DigestExclusionPolicy(
        id_fields=frozenset({id_field}),
        digest_fields=frozenset({"content_digest"}),
    )
    artifact[id_field] = ""
    artifact["content_digest"] = ""
    artifact[id_field] = content_derived_id(
        namespace + "-id",
        artifact,
        policy=policy,
    )
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=policy,
    )


def test_authority_case_and_gate_inventories_are_exact() -> None:
    assert len(CASE_SPECS) == 16
    assert sum(spec["domain"] == "ARC2" for spec in CASE_SPECS) == 8
    assert sum(spec["domain"] == "ARC3" for spec in CASE_SPECS) == 8
    assert len({spec["fixture_id"] for spec in CASE_SPECS}) == 16
    assert GATE_IDS == tuple(f"DG-{index:02d}" for index in range(16))
    assert {spec["primary_gate_id"] for spec in CASE_SPECS} == set(GATE_IDS)
    assert set(GATE_ASSERTIONS) == set(GATE_IDS)
    assert set(GATE_OBLIGATION_CHECKS) == set(GATE_IDS)
    assert all(
        len(check_ids) == len(set(check_ids)) == 2
        for check_ids in GATE_OBLIGATION_CHECKS.values()
    )
    assert len(GOLDEN_ERROR_CODES) == len(set(GOLDEN_ERROR_CODES)) == 21


def test_contract_is_content_bound_candidate_only_and_phase_limited() -> None:
    contract = _contract()
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"contract_id"}),
        digest_fields=frozenset({"content_digest"}),
    )

    assert contract == build_golden_conformance_contract()
    assert contract["content_digest"] == logical_content_digest(
        "hds-golden-conformance-contract",
        contract,
        policy=policy,
    )
    assert contract["candidate_state"] == ("PROPOSED_PENDING_OWNER_APPROVAL")
    assert contract["candidate_only"] is True
    assert contract["synthetic_fixture_only"] is True
    assert contract["required_arc2_case_count"] == 8
    assert contract["required_arc3_case_count"] == 8
    assert contract["required_total_case_count"] == 16
    assert contract["required_hypothesis_count_per_case_minimum"] == 2
    assert contract["required_artifact_classes"] == list(REQUIRED_ARTIFACT_CLASSES)
    authority = cast(JsonObject, contract["authority"])
    assert authority == {
        "causal_ir_contract_digest": (
            "hds-causal-ir-contract:"
            "160048eb2d37ddd633c589b2bdb07f901d5db449648451ea8a10331039111678"
        ),
        "input_evidence_payload_digest": (
            "sha256:"
            "cb5c07dd9295ee47fa5f114ba9aff5d9f10106da2c6d2412adbea42080fe4a04"
        ),
        "input_phase_state_sha256": (
            "sha256:"
            "3a7e627ab0aee7f37346aee6b7ef5188bbe2ef257abd6302de5a358bc2d7293d"
        ),
        "phase_entry_approval_digest": (
            "owner-approval-record:"
            "2f01decd9706b8a69fc00c1ff7ad22d4ee79aa9c1bfc8667f21792e882235625"
        ),
        "phase_transition_digest": (
            "rev3-phase-transition:"
            "6a10c8cb7d86884e449054462d6407e33c5ea42b9b77387c84e3fad9dc9d0914"
        ),
        "preinventory_digest": (
            "rev3-ph-d03a-post-audit-golden-preinventory:"
            "4b961014e9845b9eac2965fcc83815622a441024352095babcd41ef866836fe0"
        ),
        "schema_contract_digest": (
            "hds-post-audit-causal-ir-schema-contract:"
            "8d4acb814448b2cba3dff39162a1191aaa490261247907151f9db0750a77b646"
        ),
            "work_block_frame_digest": (
                "rev3-work-block-frame:"
                "a035ddb7fda0e8a598d11f65154a5f45f31439d3c229019f60a2324ec9084530"
            ),
        }
    approval = cast(JsonObject, contract["approval_contract"])
    assert approval == {
        "allowed_mode": "SCHEMA_TEMPLATE",
        "approved_expectation_auto_update_allowed": False,
        "authoritative": False,
        "authority": "UNBOUND_SCHEMA_TEMPLATE",
        "decision": "SUSPEND",
        "golden_freeze_allowed": False,
        "owner_recorded_generation_allowed": False,
    }
    boundaries = cast(JsonObject, contract["phase_boundaries"])
    assert boundaries["golden_candidate_construction_started"] is True
    assert boundaries["golden_expected_artifact_freeze_started"] is False
    assert boundaries["owner_approval_generated_count"] == 0
    assert boundaries["sealed_corpus_started"] is False
    assert boundaries["source_payload_read_count"] == 0
    assert boundaries["teacher_trajectory_read_count"] == 0
    assert boundaries["real_intervention_execution_count"] == 0
    assert boundaries["causal_mechanism_assertion_count"] == 0
    assert boundaries["general_candidate_generation_count"] == 0
    assert boundaries["rule_promotion_count"] == 0
    assert boundaries["bridge_started"] is False
    assert boundaries["runtime_started"] is False
    assert boundaries["locked_final_access_count"] == 0
    assert boundaries["official_access_count"] == 0
    assert boundaries["network_submission_count"] == 0
    assert boundaries["kaggle_mutation_count"] == 0


def test_candidate_set_validates_all_sixteen_cases() -> None:
    contract = _contract()
    candidate_set = _candidate_set()
    validated = validate_golden_candidate_set(
        REPOSITORY_ROOT,
        contract,
        candidate_set,
    )

    assert len(validated) == 16
    assert candidate_set["arc2_case_count"] == 8
    assert candidate_set["arc3_case_count"] == 8
    assert candidate_set["case_count"] == 16
    assert candidate_set["content_specific_owner_approval_count"] == 0
    assert candidate_set["golden_frozen_case_count"] == 0
    assert candidate_set["sealed_case_count"] == 0
    assert [item["fixture_id"] for item in validated] == [
        spec["fixture_id"] for spec in CASE_SPECS
    ]


@pytest.mark.parametrize(
    "spec",
    CASE_SPECS,
    ids=lambda spec: cast(str, spec["fixture_id"]),
)
def test_every_case_has_required_human_auditable_artifacts(
    spec: Mapping[str, object],
) -> None:
    case = _case(cast(str, spec["fixture_id"]))
    hypotheses = cast(list[JsonObject], case["hypothesis_candidates"])
    exact = cast(list[JsonObject], case["exact_fit_results"])
    supporting = cast(JsonObject, case["supporting_records"])

    assert case["domain"] == spec["domain"]
    assert case["category"] == spec["category"]
    assert case["operator_focus"] == list(cast(tuple[str, ...], spec["operators"]))
    assert case["primary_gate_id"] == spec["primary_gate_id"]
    assert case["artifact_inventory"] == list(REQUIRED_ARTIFACT_CLASSES)
    assert case["candidate_state"] == ("PROPOSED_PENDING_OWNER_APPROVAL")
    assert len(hypotheses) >= 2
    assert len(exact) == len(hypotheses)
    assert case["raw_observation"]
    assert case["deterministic_derivation"]
    assert case["interpretation_hypothesis"]
    assert case["counterfactual_intervention_plan"]
    assert case["intervention_result"]
    assert case["hds_causal_record"]
    assert case["failure_signatures"]
    assert case["gate_result"]
    assert supporting["evidence_record"]
    assert len(cast(list[JsonObject], supporting["model_records"])) == len(hypotheses)
    assert supporting["decision_record"]
    assert supporting["open_term_record"]
    assert case["provisional_expected_artifact"]
    assert case["approval_record_template"]


def test_all_executable_hypotheses_reproduce_declared_results() -> None:
    candidate_set = _candidate_set()
    cases = cast(list[JsonObject], candidate_set["cases"])
    pass_count = 0
    error_count = 0
    suspension_count = 0
    for case in cases:
        descriptors = cast(
            list[JsonObject],
            case["hypothesis_candidates"],
        )
        for descriptor in descriptors:
            program = cast(JsonObject, descriptor["hypothesis_ir"])
            expected = cast(JsonObject, descriptor["expected_execution"])
            if expected["kind"] == "PASS":
                assert execute_program(program).as_json() == expected["result"]
                pass_count += 1
            elif expected["kind"] == "ERROR":
                with pytest.raises(IRContractError) as exc_info:
                    execute_program(program)
                assert exc_info.value.code == expected["error_code"]
                error_count += 1
            else:
                result = execute_program(program)
                assert expected["kind"] == "SUSPEND_RESOURCE"
                assert result.as_json() == expected["result"]
                assert result.status == "SUSPEND_RESOURCE"
                suspension_count += 1

    assert pass_count == 34
    assert error_count == 1
    assert suspension_count == 1


def test_exact_fit_records_never_establish_causality() -> None:
    candidate_set = _candidate_set()
    cases = cast(list[JsonObject], candidate_set["cases"])
    statuses: list[str] = []
    for case in cases:
        for result in cast(list[JsonObject], case["exact_fit_results"]):
            statuses.append(cast(str, result["fit_status"]))
            assert result["causal_establishment"] is False
            assert result["comparison_scope"] == (
                "SYNTHETIC_IMPLEMENTATION_CONFORMANCE_ONLY"
            )
            if result["fit_status"] == "LOCAL_EXACT_FIT":
                assert result["exact_match_count"] == 1
                assert result["matched_step_count"] == 1
                assert cast(JsonObject, result["comparison"])["equal"] is True
    assert statuses.count("LOCAL_EXACT_FIT") == 34
    assert statuses.count("NOT_EXECUTABLE") == 1
    assert statuses.count("INCONCLUSIVE_RESOURCE") == 1


def test_interventions_are_predeclared_reversible_and_synthetic_only() -> None:
    cases = cast(list[JsonObject], _candidate_set()["cases"])
    for case in cases:
        plan = cast(JsonObject, case["counterfactual_intervention_plan"])
        result = cast(JsonObject, case["intervention_result"])
        outcome = cast(JsonObject, result["observed_outcome"])
        safety_constraints = cast(
            list[object],
            plan["safety_constraints"],
        )
        assert plan["freeze_state"] == "PRE_RESULT_FROZEN"
        assert plan["reversibility"] == "REVERSIBLE"
        assert "SYNTHETIC_ONLY" in safety_constraints
        assert "NO_ENVIRONMENT_ACTION" in safety_constraints
        assert result["intervention_plan_ref"] == plan["intervention_plan_id"]
        assert result["result_state"] == "OBSERVED"
        assert result["operation_state"] == "HOLD"
        assert outcome["execution_scope"] == "SYNTHETIC_ONLY"
        assert outcome["causal_claim"] is None


def test_unsupported_opcode_and_resource_cases_fail_closed() -> None:
    impossible = _case("golden.arc2.impossible_unsupported_opcode")
    invalid = cast(list[JsonObject], impossible["hypothesis_candidates"])[1]
    with pytest.raises(IRContractError) as error:
        execute_program(cast(JsonObject, invalid["hypothesis_ir"]))
    assert error.value.code == "IR_UNKNOWN_OPCODE"
    invalid_fit = cast(list[JsonObject], impossible["exact_fit_results"])[1]
    assert invalid_fit["fit_status"] == "NOT_EXECUTABLE"
    assert invalid_fit["actual_error_code"] == "IR_UNKNOWN_OPCODE"

    resource = _case("golden.arc3.resource_suspension")
    descriptor = cast(
        list[JsonObject],
        resource["hypothesis_candidates"],
    )[1]
    result = execute_program(cast(JsonObject, descriptor["hypothesis_ir"]))
    assert result.status == "SUSPEND_RESOURCE"
    assert result.assertion_state == "SUSPEND"
    assert result.operation_state == "HOLD"
    assert result.evidence_state == "INCONCLUSIVE"
    assert result.reason_code == "SUSPEND_RESOURCE"


def test_gate_coverage_is_complete_without_fabricating_dg14() -> None:
    candidate_set = _candidate_set()
    report = _artifact("distillation/artifacts/reports/golden_gate_coverage.json")
    validate_golden_gate_coverage(candidate_set, report)
    entries = cast(list[JsonObject], report["gate_entries"])

    assert report == build_golden_gate_coverage_report(candidate_set)
    assert [entry["gate_id"] for entry in entries] == list(GATE_IDS)
    assert report["gate_count"] == 16
    assert report["covered_gate_count"] == 16
    assert report["missing_gate_ids"] == []
    assert report["pass_result_count"] == 15
    assert report["suspend_result_count"] == 1
    assert report["fail_result_count"] == 0
    assert report["coverage_complete"] is True
    assert report["declarative_gate_result_trusted"] is False
    assert report["behaviorally_recomputed_gate_count"] == 16
    for entry in entries:
        obligation = cast(JsonObject, entry["obligation_evidence"])
        gate_id = cast(str, entry["gate_id"])
        assert obligation["recomputed"] is True
        assert obligation["declarative_gate_result_trusted"] is False
        assert obligation["check_ids"] == list(
            GATE_OBLIGATION_CHECKS[gate_id]
        )
        assert obligation["result"] == entry["actual_result"]
        assert obligation["evidence_digests"]
        assert entry["actual_reason_codes"] == [
            GATE_ASSERTIONS[gate_id],
            "BEHAVIORALLY_RECOMPUTED",
        ]
    dg14 = next(item for item in entries if item["gate_id"] == "DG-14")
    assert dg14["actual_result"] == "SUSPEND"
    assert dg14["expected_assertion"] == (
        "SUSPEND_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    dg15 = next(item for item in entries if item["gate_id"] == "DG-15")
    assert dg15["actual_result"] == "PASS"
    assert dg15["expected_assertion"] == (
        "PASS_UNAPPROVED_COMMIT_AND_PROMOTION_REJECTED"
    )
    assert cast(
        JsonObject,
        next(item for item in entries if item["gate_id"] == "DG-08")[
            "obligation_evidence"
        ],
    )["negative_probe_codes"] == [
        "D03A_PRIVILEGED_ROUTING_FORBIDDEN"
    ]
    assert cast(JsonObject, dg14["obligation_evidence"])[
        "negative_probe_codes"
    ] == ["D03A_OWNER_APPROVAL_FABRICATION"]
    assert cast(JsonObject, dg15["obligation_evidence"])[
        "negative_probe_codes"
    ] == [
        "D03A_PROMOTION_FORBIDDEN",
        "D03A_PROMOTION_FORBIDDEN",
    ]


def test_approval_templates_are_non_authoritative_and_target_proposals() -> None:
    cases = cast(list[JsonObject], _candidate_set()["cases"])
    for case in cases:
        approval = cast(JsonObject, case["approval_record_template"])
        provisional = cast(
            JsonObject,
            case["provisional_expected_artifact"],
        )
        decision = cast(
            JsonObject,
            cast(JsonObject, case["supporting_records"])["decision_record"],
        )
        assert provisional["state"] == "PROPOSED_NOT_FROZEN"
        assert approval["approval_mode"] == "SCHEMA_TEMPLATE"
        assert approval["authoritative"] is False
        assert approval["authority"] == "UNBOUND_SCHEMA_TEMPLATE"
        assert approval["decision"] == "SUSPEND"
        assert approval["target_artifact_digest"] == provisional["content_digest"]
        assert decision["decision_mode"] == "SUSPEND"
        assert decision["selected_model_refs"] == []
        assert decision["operation_state"] == "HOLD"
        assert decision["update_state"] == "PROPOSED"


def test_owner_review_request_has_no_owner_decision_or_freeze() -> None:
    candidate_set = _candidate_set()
    coverage = _artifact("distillation/artifacts/reports/golden_gate_coverage.json")
    request = _artifact("distillation/artifacts/golden/owner_review_request.json")
    validate_golden_owner_review_request(
        candidate_set,
        coverage,
        request,
    )

    assert request == build_golden_owner_review_request(
        candidate_set,
        coverage,
    )
    assert request["request_state"] == ("AWAITING_CONTENT_SPECIFIC_OWNER_DECISION")
    assert request["target_count"] == 16
    assert request["owner_decision_present"] is False
    assert request["owner_approval_generated"] is False
    assert request["golden_freeze_started"] is False
    assert request["sealed_corpus_started"] is False
    assert request["automatic_expectation_update_allowed"] is False
    response = cast(JsonObject, request["owner_response_contract"])
    assert response["approval_mode"] == "OWNER_RECORDED"
    assert response["authority"] == "OWNER"
    assert response["authoritative"] is True
    assert response["trusted_external_digest_required"] is True
    assert response["codex_must_not_generate_response"] is True


def test_candidate_validator_rejects_top_level_approval_fabrication() -> None:
    candidate_set = _candidate_set()
    candidate_set["content_specific_owner_approval_count"] = 1
    _rebind_id_artifact(
        candidate_set,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )

    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_OWNER_APPROVAL_FABRICATION",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            candidate_set,
        )


def test_candidate_validator_rejects_case_freeze_and_privileged_route() -> None:
    frozen = _candidate_set()
    frozen_case = cast(list[JsonObject], frozen["cases"])[0]
    boundaries = cast(JsonObject, frozen_case["phase_boundaries"])
    boundaries["golden_expected_artifact_frozen"] = True
    _rebind_digest_only(frozen_case, "hds-golden-candidate-case")
    _rebind_id_artifact(
        frozen,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_GOLDEN_FREEZE_FORBIDDEN",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            frozen,
        )

    privileged = _candidate_set()
    privileged_case = cast(list[JsonObject], privileged["cases"])[0]
    descriptor = cast(
        list[JsonObject],
        privileged_case["hypothesis_candidates"],
    )[0]
    program = cast(JsonObject, descriptor["hypothesis_ir"])
    program["task_id"] = "forbidden-route"
    _rebind_digest_only(privileged_case, "hds-golden-candidate-case")
    _rebind_id_artifact(
        privileged,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_PRIVILEGED_ROUTING_FORBIDDEN",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            privileged,
        )


def test_candidate_validator_rejects_rebound_case_metadata_and_privilege(
) -> None:
    privileged = _candidate_set()
    privileged_case = cast(list[JsonObject], privileged["cases"])[0]
    privileged_case["task_id"] = "forbidden-case-route"
    _rebind_digest_only(privileged_case, "hds-golden-candidate-case")
    _rebind_id_artifact(
        privileged,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_PRIVILEGED_ROUTING_FORBIDDEN",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            privileged,
        )

    wrong_category = _candidate_set()
    wrong_category_case = cast(
        list[JsonObject],
        wrong_category["cases"],
    )[0]
    wrong_category_case["category"] = "REBOUND_WRONG_CATEGORY"
    _rebind_digest_only(
        wrong_category_case,
        "hds-golden-candidate-case",
    )
    _rebind_id_artifact(
        wrong_category,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_CASE_INVENTORY_MISMATCH",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            wrong_category,
        )


def test_candidate_validator_recomputes_exact_fit_and_intervention_result(
) -> None:
    wrong_fit = _candidate_set()
    wrong_fit_case = cast(list[JsonObject], wrong_fit["cases"])[0]
    exact = cast(list[JsonObject], wrong_fit_case["exact_fit_results"])[0]
    exact["fit_status"] = "NOT_EXECUTABLE"
    _rebind_digest_only(exact, "hds-golden-exact-fit-result")
    _rebind_digest_only(wrong_fit_case, "hds-golden-candidate-case")
    _rebind_id_artifact(
        wrong_fit,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_EXACT_FIT_MISMATCH",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            wrong_fit,
        )

    wrong_intervention = _candidate_set()
    wrong_intervention_case = cast(
        list[JsonObject],
        wrong_intervention["cases"],
    )[0]
    intervention_result = cast(
        JsonObject,
        wrong_intervention_case["intervention_result"],
    )
    intervention_result["reason_codes"] = ["REBOUND_FALSE_RESULT"]
    _rebind_id_artifact(
        intervention_result,
        namespace="hds-intervention-result",
        id_field="intervention_result_id",
    )
    _rebind_digest_only(
        wrong_intervention_case,
        "hds-golden-candidate-case",
    )
    _rebind_id_artifact(
        wrong_intervention,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_INTERVENTION_RESULT_MISMATCH",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            _contract(),
            wrong_intervention,
        )


def test_coverage_validator_rejects_rebound_summary_and_entry_mutation() -> None:
    candidate_set = _candidate_set()
    wrong_summary = _artifact(
        "distillation/artifacts/reports/golden_gate_coverage.json"
    )
    wrong_summary["pass_result_count"] = 14
    _rebind_id_artifact(
        wrong_summary,
        namespace="hds-golden-gate-coverage",
        id_field="report_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_GATE_COVERAGE_INCOMPLETE",
    ):
        validate_golden_gate_coverage(candidate_set, wrong_summary)

    wrong_entry = _artifact(
        "distillation/artifacts/reports/golden_gate_coverage.json"
    )
    entries = cast(list[JsonObject], wrong_entry["gate_entries"])
    entries[0]["fixture_id"] = "rebound.false.fixture"
    _rebind_id_artifact(
        wrong_entry,
        namespace="hds-golden-gate-coverage",
        id_field="report_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_GATE_COVERAGE_INCOMPLETE",
    ):
        validate_golden_gate_coverage(candidate_set, wrong_entry)


def test_owner_review_validator_rejects_rebound_target_mutation() -> None:
    candidate_set = _candidate_set()
    coverage = _artifact(
        "distillation/artifacts/reports/golden_gate_coverage.json"
    )
    request = _artifact(
        "distillation/artifacts/golden/owner_review_request.json"
    )
    targets = cast(list[JsonObject], request["targets"])
    targets[0]["provisional_expected_artifact_digest"] = (
        "hds-golden-provisional-expected-artifact:"
        + "0" * 64
    )
    _rebind_id_artifact(
        request,
        namespace="hds-golden-owner-review-request",
        id_field="review_request_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_REFERENCE_INVALID",
    ):
        validate_golden_owner_review_request(
            candidate_set,
            coverage,
            request,
        )


def test_coverage_and_review_validators_reject_authority_mutations() -> None:
    candidate_set = _candidate_set()
    coverage = _artifact("distillation/artifacts/reports/golden_gate_coverage.json")
    entries = cast(list[JsonObject], coverage["gate_entries"])
    entries.pop()
    _rebind_id_artifact(
        coverage,
        namespace="hds-golden-gate-coverage",
        id_field="report_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_GATE_COVERAGE_INCOMPLETE",
    ):
        validate_golden_gate_coverage(candidate_set, coverage)

    valid_coverage = _artifact(
        "distillation/artifacts/reports/golden_gate_coverage.json"
    )
    request = _artifact("distillation/artifacts/golden/owner_review_request.json")
    request["owner_decision_present"] = True
    _rebind_id_artifact(
        request,
        namespace="hds-golden-owner-review-request",
        id_field="review_request_id",
    )
    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_OWNER_APPROVAL_FABRICATION",
    ):
        validate_golden_owner_review_request(
            candidate_set,
            valid_coverage,
            request,
        )


def test_pre_audit_artifacts_are_snapshotted_and_current_bytes_are_rebuilt(
) -> None:
    rebuilt = _encoded_artifacts()

    assert len(rebuilt) == 4
    snapshot_paths = {
        "distillation/input/golden_conformance_contract.json": (
            "generated/golden_conformance_contract.json"
        ),
        "distillation/artifacts/golden/candidate_cases.json": (
            "generated/candidate_cases.json"
        ),
        "distillation/artifacts/reports/golden_gate_coverage.json": (
            "generated/golden_gate_coverage.json"
        ),
        "distillation/artifacts/golden/owner_review_request.json": (
            "generated/owner_review_request.json"
        ),
    }
    for relative_path, snapshot_relative_path in snapshot_paths.items():
        payload = rebuilt[relative_path]
        checked = (REPOSITORY_ROOT / relative_path).read_bytes()
        snapshot = (
            REPOSITORY_ROOT
            / "distillation"
            / "input"
            / "historical_pre_audit"
            / "PH-D03A"
            / snapshot_relative_path
        ).read_bytes()
        historical = subprocess.run(
            [
                "git",
                "show",
                PH_D03A_ENTRY_BASE_COMMIT + ":" + relative_path,
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert snapshot == historical
        assert checked == payload
        assert checked != historical
        decoded = json.loads(payload)
        assert isinstance(decoded, dict)


def test_three_independent_processes_rebuild_identical_bytes(
    tmp_path: Path,
) -> None:
    script = """
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from hds_distill.golden_corpus import build_phase_d03a_candidate_artifacts
root = Path(sys.argv[2])
artifacts = build_phase_d03a_candidate_artifacts(root)
print(json.dumps({
    path: hashlib.sha256(payload).hexdigest()
    for path, payload in reversed(tuple(artifacts.items()))
}, sort_keys=True, separators=(",", ":")))
"""
    outputs: list[str] = []
    for index, seed in enumerate(("11", "22", "33")):
        cwd = tmp_path / f"rebuild-{index}"
        cwd.mkdir()
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(DISTILLATION_SOURCE),
                str(REPOSITORY_ROOT),
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env=environment,
            timeout=120,
        )
        outputs.append(result.stdout.strip())

    assert len(set(outputs)) == 1
    expected = {
        path: hashlib.sha256(payload).hexdigest()
        for path, payload in _encoded_artifacts().items()
    }
    assert json.loads(outputs[0]) == expected


def test_golden_module_has_no_external_or_downstream_imports() -> None:
    source_path = (
        REPOSITORY_ROOT / "distillation" / "src" / "hds_distill" / "golden_corpus.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").lstrip(".").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = {
        "arc_agi",
        "bridge",
        "http",
        "kaggle",
        "requests",
        "runtime",
        "socket",
        "subprocess",
        "teacher",
        "urllib",
    }

    assert imported_roots.isdisjoint(forbidden)
    source = source_path.read_text(encoding="utf-8")
    assert "OWNER_RECORDED" in source
    assert "owner_recorded_generation_allowed" in source
    assert '"owner_recorded_generation_allowed": False' in source
    assert "write_phase_d03a_candidate_artifacts" in source


def test_contract_rejects_any_byte_level_mutation() -> None:
    contract = _contract()
    contract["candidate_only"] = False

    with pytest.raises(
        GoldenCorpusError,
        match="^D03A_CONTRACT_MISMATCH",
    ):
        validate_golden_candidate_set(
            REPOSITORY_ROOT,
            contract,
            _candidate_set(),
        )
