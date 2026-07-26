from __future__ import annotations

import pytest

from arc3_agi_agent.teacher.s6_generalization import (
    S6_GENERALIZATION_SCHEMA_VERSION,
    S6_REQUIRED_FAMILIES,
)
from arc3_agi_agent.teacher.solution_graph_compiler import (
    _s5_evidence_passes,
    _s6_evidence_measured,
)


def _evidence() -> tuple[dict[str, object], ...]:
    closure: dict[str, object] = {
        "all_complete": True,
        "complete_inventory": True,
        "environment_count": 25,
        "completed_environment_count": 25,
        "completed_levels": 183,
        "deterministic_seed": 0,
        "error_count": 0,
        "hds_stage_decision": "PASS",
        "next_stage_authorized": True,
        "runtime_student": True,
        "operation_mode": "offline",
        "instruction_body_digest": "policy",
        "content_digest": "closure",
    }
    compilation: dict[str, object] = {
        "teacher_forced_error_count": 0,
        "quantized_teacher_forced_error_count": 0,
        "runtime_artifact_contains_training_examples": False,
        "runtime_policy_digest": "policy",
        "content_digest": "compilation",
    }
    audit: dict[str, object] = {
        "status": "PASS",
        "runtime_policy_digest": "policy",
        "closure_report_digest": "closure",
        "policy_compilation_report_digest": "compilation",
    }
    return closure, compilation, audit


def test_s5_structure_gate_requires_three_agreeing_evidence_sets() -> None:
    closure, compilation, audit = _evidence()

    assert _s5_evidence_passes(closure, compilation, audit) is True


def test_s5_structure_gate_rejects_digest_disagreement() -> None:
    closure, compilation, audit = _evidence()
    audit["runtime_policy_digest"] = "different-policy"

    with pytest.raises(
        ValueError,
        match="S5_AUDIT_POLICY_DIGEST_MISMATCH",
    ):
        _s5_evidence_passes(closure, compilation, audit)


def _s6_evidence() -> tuple[dict[str, object], dict[str, object]]:
    policy_digest = "policy"
    report: dict[str, object] = {
        "schema_version": S6_GENERALIZATION_SCHEMA_VERSION,
        "status": "COMPLETE",
        "selected_record_count": 2048,
        "covered_game_count": 25,
        "covered_level_count": 183,
        "required_family_count": 7,
        "measured_family_count": 7,
        "total_measurement_count": 14_336,
        "baseline_policy_action_error_count": 0,
        "baseline_policy_pointer_error_count": 0,
        "baseline_unknown_action_surface_count": 0,
        "exception_count": 0,
        "full_environment_completion_executed": False,
        "semantic_ground_truth_available": False,
        "generalization_claim": "MEASURED_NOT_PROVEN",
        "hds_decision": "S6_MEASURED_HOLD_GENERALIZATION_CLAIM",
        "source_runtime_policy_digest": policy_digest,
        "families": [
            {
                "family_id": family_id,
                "measurement_count": 2048,
                "exception_count": 0,
                "unknown_action_surface_count": 0,
                "predicted_unavailable_action_count": 0,
                "semantic_correctness": "NOT_AVAILABLE",
            }
            for family_id in S6_REQUIRED_FAMILIES
        ],
    }
    compilation: dict[str, object] = {
        "runtime_policy_digest": policy_digest,
    }
    return report, compilation


def test_s6_gate_records_measurement_without_generalization_claim() -> None:
    report, compilation = _s6_evidence()

    assert _s6_evidence_measured(report, compilation) is True


def test_s6_gate_rejects_semantic_claim_inflation() -> None:
    report, compilation = _s6_evidence()
    report["generalization_claim"] = "PASS"

    with pytest.raises(
        ValueError,
        match="S6_REPORT_INVALID:generalization_claim",
    ):
        _s6_evidence_measured(report, compilation)
