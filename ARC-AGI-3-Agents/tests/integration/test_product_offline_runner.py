from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

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
