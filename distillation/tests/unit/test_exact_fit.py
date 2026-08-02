"""PH-D07A extensional fit accounting and causal-boundary tests."""

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
from hds_distill.exact_fit import (
    FIT_AXES,
    ExactFitError,
    _observed_binding,
    _step_contexts,
    evaluate_case,
)
from hds_distill.hypothesis_generation import generate_case_candidates
from hds_distill.ir_types import JsonObject

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PACKAGE = (
    REPOSITORY_ROOT
    / "distillation/artifacts/teacher/arc3/ph_d05_v1/packages/"
    "ar25-0c556536.json.gz"
)


@lru_cache(maxsize=1)
def _teacher_package() -> JsonObject:
    with gzip.open(SAMPLE_PACKAGE, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError("PH_D07A_TEST_TEACHER_NOT_OBJECT")
    return cast(JsonObject, value)


@lru_cache(maxsize=1)
def _candidate_package() -> JsonObject:
    return generate_case_candidates(_teacher_package())


@lru_cache(maxsize=1)
def _fit_case() -> JsonObject:
    return evaluate_case(_candidate_package(), _teacher_package())


def _results() -> list[Mapping[str, Any]]:
    return cast(list[Mapping[str, Any]], _fit_case()["fit_results"])


def test_every_candidate_is_accounted_against_every_relevant_teacher_step() -> None:
    case = _fit_case()
    results = _results()

    assert case["phase_id"] == "PH-D07A"
    assert case["teacher_step_count"] == 503
    assert case["candidate_count"] == 18
    assert case["eligible_candidate_count"] == 16
    assert case["rejected_ineligible_candidate_count"] == 2
    assert case["candidate_step_evaluation_count"] == 16 * 503
    assert len(results) == 18
    for result in results[:16]:
        assert result["teacher_step_count"] == 503
        assert result["evaluated_step_count"] == 503
        assert (
            result["matched_step_count"] + result["mismatch_step_count"]
            == 503
        )


def test_fit_state_never_establishes_causality_selection_or_promotion() -> None:
    results = _results()
    eligible = [
        item
        for item in results
        if item["evaluation_eligibility"] == "ELIGIBLE_EXECUTABLE_IR"
    ]

    assert eligible
    assert {item["fit_status"] for item in eligible} <= {
        "LOCAL_EXACT_FIT",
        "FALSIFIED",
        "INCONCLUSIVE_RESOURCE",
    }
    for result in results:
        assert result["causal_support_state"] == "NOT_ESTABLISHED"
        assert result["candidate_selection_state"] == "UNSELECTED"
        assert result["candidate_adoption_state"] == "NOT_ADOPTED"
        assert result["promotion_state"] == "NOT_PROMOTED"
        assert result["intervention_execution_state"] == "NOT_RUN_PH_D07A"
        if result["fit_status"] == "LOCAL_EXACT_FIT":
            assert result["mechanism_support_state"] in {
                "OBSERVED_COMPATIBLE",
                "LOCAL_EXACT_FIT",
            }
            if (
                result["output_type"] == "Boolean"
                and result["positive_activation_count"] == 0
            ):
                assert result["mechanism_support_state"] == "OBSERVED_COMPATIBLE"

    boundaries = cast(Mapping[str, Any], _fit_case()["phase_boundaries"])
    assert set(boundaries.values()) == {0}


def test_fit_axes_are_declared_and_unclaimed_axes_are_not_imputed() -> None:
    case = _fit_case()
    counts = cast(Mapping[str, int], case["axis_candidate_counts"])

    assert tuple(counts) == FIT_AXES
    assert sum(counts.values()) == 16
    assert counts["RAW_ACTION_MATCH"] == 3
    assert counts["STEP_PRECONDITION"] == 3
    assert counts["ORDERING"] == 3
    assert counts["TERMINAL_CONTRIBUTION"] == 3
    assert counts["PREDICTED_EFFECT"] == 1
    assert counts["STATE_ABSTRACTION"] == 1
    assert counts["TRANSITION"] == 2


def test_privilege_adversaries_remain_rejected_and_are_never_fit_executed() -> None:
    rejected = [
        item
        for item in _results()
        if item["evaluation_eligibility"] == "NOT_ELIGIBLE_DG_08"
    ]

    assert len(rejected) == 2
    assert [item["candidate_family"] for item in rejected] == [
        "ANSWER_COPY_ADVERSARIAL",
        "TRAJECTORY_LOOKUP_ADVERSARIAL",
    ]
    assert [item["rejection_code"] for item in rejected] == [
        "IR_ANSWER_COPY_FORBIDDEN",
        "IR_IDENTITY_ROUTING_FORBIDDEN",
    ]
    for result in rejected:
        assert result["fit_status"] == "NOT_ELIGIBLE_DG_08"
        assert result["evaluated_step_count"] == 0
        assert result["exact_fit"] is False


def test_fit_is_recomputed_not_copied_from_generation_compatibility_label() -> None:
    eligible = _results()[:16]
    assert any(
        item["generation_observation_compatible_label"] is True
        and item["fit_status"] == "FALSIFIED"
        for item in eligible
    )
    assert all(item["comparison_trace_digest"] for item in eligible)
    assert all(
        len(cast(list[object], item["mismatch_samples"])) <= 16
        for item in eligible
    )


def test_identity_metadata_does_not_route_or_change_fit_bytes() -> None:
    changed = copy.deepcopy(_teacher_package())
    trajectory = cast(JsonObject, changed["detailed_trajectory"])
    trajectory["game_id"] = "identity-must-not-route"
    trajectory["recording_file"] = "identity-must-not-route.recording"
    trajectory["trajectory_id"] = "identity-must-not-route"
    changed["game_id"] = "identity-must-not-route"

    assert canonical_json_document_bytes(
        evaluate_case(_candidate_package(), changed)
    ) == canonical_json_document_bytes(_fit_case())


def test_observed_step_mutation_changes_fit_evidence() -> None:
    changed = copy.deepcopy(_teacher_package())
    trajectory = cast(JsonObject, changed["detailed_trajectory"])
    steps = cast(list[JsonObject], trajectory["steps"])
    action = cast(JsonObject, steps[0]["action"])
    available = cast(list[int], action["available_actions_before"])
    action["action_id"] = next(
        item for item in available if item != action["action_id"]
    )

    changed_result = evaluate_case(_candidate_package(), changed)
    assert changed_result["content_digest"] != _fit_case()["content_digest"]


def test_unknown_observed_binding_fails_closed() -> None:
    context = _step_contexts(_teacher_package())[0]

    with pytest.raises(
        ExactFitError,
        match="^PH_D07A_OBSERVED_BINDING_UNSUPPORTED",
    ):
        _observed_binding("unsupported_observed_binding", context)


def test_case_evaluation_is_byte_deterministic() -> None:
    first = canonical_json_document_bytes(
        evaluate_case(_candidate_package(), _teacher_package())
    )
    second = canonical_json_document_bytes(
        evaluate_case(_candidate_package(), _teacher_package())
    )
    assert first == second


def test_gate_result_is_accounting_not_causal_establishment() -> None:
    assert _fit_case()["gates"] == {
        "DG-07": "PASS_EXTENSIONAL_FIT_ACCOUNTED",
        "DG-08": "PASS_PRIVILEGE_REJECTION_PRESERVED",
        "DG-09": "PASS_FIT_CAUSAL_SEPARATION",
    }
