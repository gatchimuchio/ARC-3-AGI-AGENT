from __future__ import annotations

from arc3_agi_agent.product_capability import load_product_initial_state
from arc3_agi_agent.product_genericity import (
    run_active_product_transformation_evaluation,
)


def test_active_product_identity_completes_semantic_transformations() -> None:
    initial = load_product_initial_state()
    report = run_active_product_transformation_evaluation()

    assert report["status"] == "PASS"
    assert report["transformation_completion"] == {
        "completed": 7,
        "required": 7,
    }
    assert report["active_p_body_digest"] == initial.p_bundle.body.digest()
    assert report["product_initial_state_logical_digest"] == initial.logical_digest
    assert report["same_runtime_identity_for_all_environments"] is True
    assert report["product_p_j0_m0_identity_bound"] is True
    assert report["identity_boundary_passed"] is True
    assert report["semantic_environment_completion_executed"] is True
    assert report["locked_evaluator"] is False
    assert report["final_generic_claim"] == "NOT_AUTHORIZED"
    assert report["product_completion_allowed"] is False
