from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from arc3_agi_agent.product_runner import run_arc3_completion_offline


def test_product_path_runs_one_bundled_game_without_network() -> None:
    environments = Path(__file__).resolve().parents[3] / "environment_files"
    with (
        tempfile.TemporaryDirectory(prefix="arc3-product-recordings-") as output,
        patch.dict(os.environ, {"OPERATION_MODE": "offline"}, clear=False),
        patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("network request forbidden"),
        ),
        patch(
            "socket.create_connection",
            side_effect=AssertionError("network socket forbidden"),
        ),
    ):
        report = run_arc3_completion_offline(
            environments_dir=environments,
            requested_games=("LS20",),
            recordings_dir=Path(output),
            action_budget=1,
        )

    assert report["operation_mode"] == "offline"
    assert report["offline_environment_available_count"] == 25
    assert report["offline_environment_selected_count"] == 1
    assert report["advertised_game_count"] == 1
    assert report["started_game_count"] == 1
    assert report["completed_game_count"] == 1
    assert report["failed_game_count"] == 0
    assert report["lifecycle_failure_count"] == 0
    assert report["scorecard_closed"] is True
    assert report["product_action_budget_per_game"] == 1
    assert report["known_budget_impossibility"] is True
    assert report["product_baseline_executable"] is False
    assert report["product_completion_established"] is False


@pytest.mark.integration
@pytest.mark.slow
def test_product_path_preserves_render_history_and_level_reset_contract() -> None:
    environments = Path(__file__).resolve().parents[3] / "environment_files"
    with (
        tempfile.TemporaryDirectory(prefix="arc3-product-r11l-") as output,
        patch.dict(os.environ, {"OPERATION_MODE": "offline"}, clear=False),
        patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("network request forbidden"),
        ),
        patch(
            "socket.create_connection",
            side_effect=AssertionError("network socket forbidden"),
        ),
    ):
        report = run_arc3_completion_offline(
            environments_dir=environments,
            requested_games=("R11L",),
            recordings_dir=Path(output),
            action_budget=200,
        )

    assert report["failed_game_count"] == 0
    assert report["lifecycle_failure_count"] == 0
    assert report["scorecard_closed"] is True
    results = report["results"]
    assert isinstance(results, list)
    assert len(results) == 1
    row = results[0]
    assert row["game_index"] == 0
    assert row["actions_executed"] == 152
    assert row["progress_count"] == 6
    assert row["final_state"] == "WIN"
    assert row["stop_reason"] == "GOAL_REACHED"
    assert row["failure_signatures"] == ()
    assert row["memory_citation_count"] == 1062
    assert row["memory_citation_ids"] == (
        "product-seed:action-surface",
        "product-seed:goal-progress",
        "product-seed:hazard-boundary",
        "product-seed:ordered-composition",
        "product-seed:reset-recovery",
        "product-seed:role-relation",
        "product-seed:temporal-observation",
    )
    assert row["executed_plan_count"] == 152
    assert row["hds_plan_commit_count"] == 152
    assert row["initial_plan_count"] == 1
    assert row["revised_plan_count"] == 151
    assert row["rollback_plan_count"] > 0
    assert row["failed_hypothesis_invalidation_count"] > 0
    assert (
        row["post_rollback_replan_count"]
        == row["rollback_plan_count"]
    )
    assert row["memory_bound_plan_count"] >= 151
    assert row["competing_hypothesis_plan_count"] == 152
    assert row["multi_representation_plan_count"] == 152
    assert row["subgoal_plan_count"] == 152
    assert row["max_plan_step_count"] == 4
    assert row["failure_attribution_count"] == 0
