"""PH-D06 bounded hypothesis generation and privilege-boundary tests."""

from __future__ import annotations

import copy
import gzip
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.canonical import canonical_json_document_bytes
from hds_distill.causal_ir import type_check_program
from hds_distill.hypothesis_generation import (
    CANDIDATE_FAMILIES,
    CANDIDATES_PER_CASE,
    EXECUTABLE_CANDIDATE_COUNT,
    HypothesisGenerationError,
    generate_case_candidates,
    validate_corpus_budget,
)
from hds_distill.interpreter import execute_program
from hds_distill.ir_types import JsonObject

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PACKAGE = (
    REPOSITORY_ROOT / "distillation/artifacts/teacher/arc3/ph_d05_v1/packages/"
    "ar25-0c556536.json.gz"
)


@lru_cache(maxsize=1)
def _teacher_package() -> JsonObject:
    with gzip.open(SAMPLE_PACKAGE, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError("PH_D06_TEST_PACKAGE_NOT_OBJECT")
    return cast(JsonObject, value)


@lru_cache(maxsize=1)
def _case_package() -> JsonObject:
    return generate_case_candidates(_teacher_package())


def _candidate_rows() -> list[Mapping[str, Any]]:
    return cast(list[Mapping[str, Any]], _case_package()["candidates"])


def test_candidate_inventory_is_exact_bounded_and_not_adopted() -> None:
    package = _case_package()
    candidates = _candidate_rows()

    assert package["phase_id"] == "PH-D06"
    assert package["candidate_count"] == CANDIDATES_PER_CASE == 18
    assert package["executable_candidate_count"] == EXECUTABLE_CANDIDATE_COUNT
    assert package["rejected_adversarial_count"] == 2
    assert package["candidate_adoption_count"] == 0
    assert package["automatic_adoption_forbidden"] is True
    assert tuple(row["candidate_family"] for row in candidates) == (CANDIDATE_FAMILIES)
    assert all(row["automatic_adoption"] is False for row in candidates)
    assert all(row["promotion_state"] == "NOT_PROMOTED" for row in candidates)
    assert all(row["causal_assertion_state"] == "NOT_ASSERTED" for row in candidates)


def test_every_admitted_candidate_is_typed_and_executable() -> None:
    admitted = [row for row in _candidate_rows() if row["executable"] is True]
    assert len(admitted) == 16
    for row in admitted:
        program = cast(Mapping[str, object], row["hypothesis_ir"])
        checked = type_check_program(program)
        result = execute_program(program)
        assert checked.domain == "ARC3"
        assert len(checked.nodes) <= 4
        assert row["execution_status"] == "PASS"
        assert cast(str, row["execution_witness_digest"]).startswith(
            "hds-ph-d06-execution-witness:"
        )
        assert result.outputs


def test_answer_copy_and_identity_route_are_generated_then_rejected() -> None:
    rejected = [row for row in _candidate_rows() if row["rejected"] is True]
    assert [row["candidate_family"] for row in rejected] == [
        "ANSWER_COPY_ADVERSARIAL",
        "TRAJECTORY_LOOKUP_ADVERSARIAL",
    ]
    assert [row["rejection_code"] for row in rejected] == [
        "IR_ANSWER_COPY_FORBIDDEN",
        "IR_IDENTITY_ROUTING_FORBIDDEN",
    ]
    for row in rejected:
        assert row["hypothesis_ir"] is None
        assert row["candidate_state"] == "REJECTED_DG_08"
        assert row["execution_status"] == "REJECTED_BEFORE_EXECUTION"
        assert cast(str, row["rejected_payload_commitment"]).startswith(
            "hds-rejected-candidate-payload-commitment:"
        )


def test_alternative_adequacy_has_independent_competitor_families() -> None:
    adequacy = cast(Mapping[str, Any], _case_package()["alternative_adequacy"])
    assert adequacy["status"] == "PASS"
    assert adequacy["fit_evaluation_status"] == "DEFERRED_TO_PH_D07A"
    assert adequacy["non_strawman_count"] >= 2
    assert adequacy["observation_compatible_competitor_count"] >= 2
    assert adequacy["selector_family_count"] >= 2
    assert adequacy["operator_ordering_family_count"] >= 2
    assert adequacy["answer_copy_generated_and_rejected_count"] == 1
    assert adequacy["trajectory_lookup_generated_and_rejected_count"] == 1
    assert adequacy["selected_candidate_count"] == 0


def test_generation_is_identity_invariant_and_does_not_route_by_game() -> None:
    original = copy.deepcopy(_teacher_package())
    changed = copy.deepcopy(original)
    trajectory = cast(JsonObject, changed["detailed_trajectory"])
    trajectory["game_id"] = "identity-must-not-route"
    trajectory["recording_file"] = "identity-must-not-route.recording"
    trajectory["trajectory_id"] = "identity-must-not-route"

    assert canonical_json_document_bytes(generate_case_candidates(original)) == (
        canonical_json_document_bytes(generate_case_candidates(changed))
    )
    source = cast(Mapping[str, Any], _case_package()["source_provenance"])
    assert source["identity_fields_consumed_for_routing"] == 0
    assert source["complete_action_sequence_copied"] is False
    assert source["environment_source_access_count"] == 0
    assert source["hidden_state_access_count"] == 0


def test_generation_is_byte_deterministic() -> None:
    first = canonical_json_document_bytes(generate_case_candidates(_teacher_package()))
    second = canonical_json_document_bytes(generate_case_candidates(_teacher_package()))
    assert first == second


def test_budget_overflow_suspends_before_authoritative_output() -> None:
    with pytest.raises(HypothesisGenerationError) as case_error:
        generate_case_candidates(
            _teacher_package(),
            max_candidates_per_case=CANDIDATES_PER_CASE - 1,
        )
    assert case_error.value.code == "SUSPEND_RESOURCE"
    assert case_error.value.detail == "CASE_BUDGET"

    validate_corpus_budget(25)
    with pytest.raises(HypothesisGenerationError) as corpus_error:
        validate_corpus_budget(28)
    assert corpus_error.value.code == "SUSPEND_RESOURCE"
    assert corpus_error.value.detail == "CORPUS_BUDGET"


def test_phase_boundaries_remain_closed() -> None:
    boundaries = cast(Mapping[str, Any], _case_package()["phase_boundaries"])
    assert set(boundaries.values()) == {0}
    assert _case_package()["gates"] == {
        "DG-03": "PASS_TYPED_EXECUTABLE_IR",
        "DG-04": "PASS_MULTIPLE_COMPETING_HYPOTHESES",
        "DG-05": "PASS_ALTERNATIVE_ADEQUACY",
        "DG-08": "PASS_PRIVILEGED_ADVERSARIAL_REJECTION",
        "DG-12": "PASS_CONTENT_BOUND_DETERMINISM",
    }
