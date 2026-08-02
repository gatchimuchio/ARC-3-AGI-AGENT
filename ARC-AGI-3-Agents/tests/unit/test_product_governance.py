from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from arc3_agi_agent.product_governance import (
    ARC3_CURRENT_SELECTOR_PATH,
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING,
    ARC3_LEGACY_REV3_IS_CURRENT,
    ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
    ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
    ARC3_PRODUCT_ACTIVE_MILESTONE,
    ARC3_PRODUCT_ENDPOINT,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _complete_report() -> dict[str, object]:
    progress = [8] * 8 + [7] * 17
    assert sum(progress) == 183
    return {
        "advertised_game_count": 25,
        "started_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "lifecycle_failure_count": 0,
        "active_agent_peak": 1,
        "scorecard_open_count": 1,
        "scorecard_close_count": 1,
        "scorecard_closed": True,
        "shared_session_count": 1,
        "resource_action_budget_per_episode": 4096,
        "hds_stop_after_no_progress": 650,
        "state_owner_violation_count": 0,
        "identity_boundary": "PASS",
        "runtime_policy_changed": False,
        "orchestration_game_index": [
            {"game_index": index, "game_id": f"sample-{index:02d}"}
            for index in range(25)
        ],
        "results": [
            {
                "game_index": index,
                "actions_executed": index + 1,
                "progress_count": progress[index],
                "final_state": "WIN",
                "stop_reason": "GOAL_REACHED",
            }
            for index in range(25)
        ],
    }


def test_product_governance_constants_match_endpoint() -> None:
    assert ARC3_CURRENT_SELECTOR_PATH == "control/rev4/CURRENT_TASK.json"
    assert ARC3_PRODUCT_ACTIVE_MILESTONE == "M3_INTEGRATED_AGI_CAPABILITY"
    assert ARC3_OFFICIAL_SAMPLE_GAME_TARGET == 25
    assert ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET == 183
    assert ARC3_DEVELOPMENT_ACTION_BUDGET == 4096
    assert ARC3_KNOWN_SUCCESS_ACTION_CEILING == 1519
    assert ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING == 644
    assert ARC3_PRODUCT_NO_PROGRESS_LIMIT == 650
    assert ARC3_LEGACY_REV3_IS_CURRENT is False
    assert ARC3_PRODUCT_ENDPOINT.validate() == ()


def test_product_endpoint_accepts_only_the_full_measured_result() -> None:
    metrics = ARC3_PRODUCT_ENDPOINT.metrics(_complete_report())

    assert metrics["product_endpoint_failure_count"] == 0
    assert metrics["product_endpoint_failures"] == ()
    assert metrics["product_game_win_count"] == 25
    assert metrics["product_level_completion_count"] == 183
    assert metrics["product_completion_established"] is True
    assert metrics["product_baseline_executable"] is True
    assert metrics["product_baseline_status"] == ("PRODUCT_BASELINE_EXECUTABLE")
    assert metrics["product_status"] == "COMPLETE"


def test_product_baseline_accepts_bounded_reports_without_claiming_wins() -> None:
    report = _complete_report()
    results = report["results"]
    assert isinstance(results, list)
    for row in results:
        row["progress_count"] = 0
        row["final_state"] = "NOT_FINISHED"
        row["stop_reason"] = "RESOURCE_LIMIT"

    metrics = ARC3_PRODUCT_ENDPOINT.metrics(report)

    assert metrics["product_baseline_failure_count"] == 0
    assert metrics["baseline_report_complete"] is True
    assert metrics["product_baseline_executable"] is True
    assert metrics["product_completion_established"] is False
    assert metrics["product_endpoint_failures"] == (
        "PRODUCT_GAME_WIN_COUNT_MISMATCH",
        "PRODUCT_LEVEL_COMPLETION_COUNT_MISMATCH",
    )


def test_product_endpoint_rejects_duplicate_index_and_open_scorecard() -> None:
    report = _complete_report()
    results = report["results"]
    assert isinstance(results, list)
    results[-1]["game_index"] = 0
    report["scorecard_closed"] = False

    metrics = ARC3_PRODUCT_ENDPOINT.metrics(report)
    endpoint_failures = metrics["product_endpoint_failures"]

    assert metrics["product_completion_established"] is False
    assert isinstance(endpoint_failures, tuple)
    assert "PRODUCT_GAME_INDEX_COVERAGE_MISMATCH" in endpoint_failures
    assert "PRODUCT_SCORECARD_NOT_CLOSED" in endpoint_failures


def test_rev4_current_task_and_legacy_boundary_are_explicit() -> None:
    current = _json(REPOSITORY_ROOT / ARC3_CURRENT_SELECTOR_PATH)
    classification = _json(
        REPOSITORY_ROOT / "control" / "rev4" / "LEGACY_REV3_CLASSIFICATION.json"
    )

    assert current["schema_version"] == "arc3-product-current-task-v2"
    assert current["active_milestone"] == ARC3_PRODUCT_ACTIVE_MILESTONE
    assert current["legacy_rev3"]["current_selector"] is False
    assert classification["classification"] == "HISTORICAL_REUSE_ONLY"
    assert classification["current_selector"] is False
    assert classification["runtime_activation_eligible"] is False
    assert classification["phase_authority_eligible"] is False


def test_m0_current_baseline_is_byte_bound_and_honest() -> None:
    current = _json(REPOSITORY_ROOT / ARC3_CURRENT_SELECTOR_PATH)
    evidence = current["current_evidence"]
    assert isinstance(evidence, dict)
    baseline_path = REPOSITORY_ROOT / str(evidence["baseline_report_path"])
    baseline = _json(baseline_path)

    assert (
        hashlib.sha256(baseline_path.read_bytes()).hexdigest()
        == evidence["baseline_report_sha256"]
    )
    assert evidence["baseline_report_status"] == "EXECUTED"
    assert evidence["baseline_report_complete"] is True
    assert evidence["m0_exit_status"] == "PRODUCT_BASELINE_EXECUTABLE"
    assert baseline["started_game_count"] == 25
    assert baseline["completed_game_count"] == 25
    assert baseline["product_bounded_report_count"] == 25
    assert baseline["budget_impossible_game_count"] == 0
    assert baseline["adapter_crash_count"] == 0
    assert baseline["scorecard_lifecycle_leak_count"] == 0
    assert baseline["product_game_win_count"] == 0
    assert baseline["product_level_completion_count"] == 3
    assert baseline["product_completion_established"] is False
    assert (
        evidence["product_endpoint_failures"] == baseline["product_endpoint_failures"]
    )


def test_m1_runtime_surface_is_byte_bound_and_complete() -> None:
    current = _json(REPOSITORY_ROOT / ARC3_CURRENT_SELECTOR_PATH)
    evidence = current["current_evidence"]
    assert isinstance(evidence, dict)
    report_path = REPOSITORY_ROOT / str(evidence["m1_report_path"])
    report = _json(report_path)

    assert (
        hashlib.sha256(report_path.read_bytes()).hexdigest()
        == evidence["m1_report_sha256"]
    )
    assert report["exit_status"] == "OFFICIAL_RUNTIME_SURFACE_COMPLETE"
    assert report["failure_reasons"] == []
    assert report["inspected_game_count"] == 25
    assert report["total_win_level_count"] == 183
    assert report["hds_authorized_game_count"] == 25
    assert report["external_action_game_count"] == 25
    assert report["reobserved_game_count"] == 25
    assert report["scorecard_closed"] is True


def test_m2_product_capability_is_byte_bound_and_active() -> None:
    current = _json(REPOSITORY_ROOT / ARC3_CURRENT_SELECTOR_PATH)
    evidence = current["current_evidence"]
    assert isinstance(evidence, dict)
    report_path = REPOSITORY_ROOT / str(evidence["m2_report_path"])
    report = _json(report_path)
    digest_body = dict(report)
    expected_content_digest = digest_body.pop("content_digest")
    actual_content_digest = "arc3-product-m2-acceptance:" + hashlib.sha256(
        json.dumps(
            digest_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert (
        hashlib.sha256(report_path.read_bytes()).hexdigest()
        == evidence["m2_report_sha256"]
    )
    assert expected_content_digest == actual_content_digest
    assert report["exit_status"] == "PRODUCT_CAPABILITY_BUNDLE_ACTIVE"
    assert report["failure_reasons"] == []
    gates = report["gates"]
    assert isinstance(gates, dict)
    assert len(gates) == 14
    assert set(gates.values()) == {True}
    assert report["product_result"]["actions_executed"] == 75
    assert report["product_result"]["progress_count"] == 6
    assert report["product_result"]["final_state"] == "WIN"
    assert report["p_removal_ablation"]["actions_executed"] == 128
    assert report["p_removal_ablation"]["progress_count"] == 0
    assert report["p_removal_ablation"]["final_state"] == "NOT_FINISHED"


def test_rev4_product_governance_validator_passes() -> None:
    script = REPOSITORY_ROOT / "scripts" / "validate_rev4_product_governance.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["failure_count"] == 0
    assert report["check_count"] >= 20
