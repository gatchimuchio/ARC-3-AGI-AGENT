from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from arc3_agi_agent.local_capability import (
    evaluate_relation_bound_action_applicability,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_rev5_1_m3_p04_applicability_counterfactual import (  # noqa: E402
    OUTPUT_PATH,
    _base_grid,
    _canonical_json,
    _encoded,
    _observation,
    build_report,
)


def test_all_mandatory_families_pass_the_counterfactual_matrix() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M3_P04_PASS"
    family = report["mandatory_family_audit"]
    assert family["mandatory_family_count"] == family["audited_family_count"] == 1
    assert family["uncovered_family_count"] == 0
    assert family["surface_identity_selector_count"] == 0
    summary = report["summary"]
    assert summary["condition_preserving_case_count"] == 7
    assert summary["condition_preserving_pass_count"] == 7
    assert summary["condition_breaking_case_count"] == 5
    assert summary["condition_breaking_pass_count"] == 5
    assert summary["applicability_maintained_when_conditions_hold"] is True
    assert summary["action_principle_maintained_when_conditions_hold"] is True
    assert summary["non_applicable_when_condition_breaks"] is True
    assert summary["active_projection_removed_when_condition_breaks"] is True


def test_applicability_contract_fails_closed_on_each_required_boundary() -> None:
    grid = _base_grid()
    cases = {
        "NON_TERMINAL_STATE": _observation(
            "test-terminal",
            grid=grid,
            terminal_state="GAME_OVER",
        ),
        "ACTION_COMPLETE": _observation(
            "test-unsettled",
            grid=grid,
            action_complete=False,
        ),
        "CURRENT_RENDERED_LAYERS": _observation(
            "test-no-render",
            grid=None,
        ),
        "NON_CONTROL_LEGAL_ACTION": _observation(
            "test-no-external-action",
            grid=grid,
            actions=(0,),
        ),
    }

    for condition, observation in cases.items():
        evaluation = evaluate_relation_bound_action_applicability(observation)
        assert evaluation.validate() == ()
        assert evaluation.applicable is False
        assert condition in evaluation.missing_conditions
        assert evaluation.negative_conditions

    baseline = evaluate_relation_bound_action_applicability(
        _observation("test-baseline", grid=grid)
    )
    assert baseline.validate() == ()
    assert baseline.applicable is True
    assert baseline.missing_conditions == ()
    assert baseline.negative_conditions == ()


def test_m3_p04_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
