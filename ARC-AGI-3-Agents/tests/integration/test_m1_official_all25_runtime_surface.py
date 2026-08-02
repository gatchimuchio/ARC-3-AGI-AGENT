from __future__ import annotations

import tempfile
from pathlib import Path

from arc3_agi_agent.product_runtime_surface import (
    M1_POINTER_CATEGORIES,
    M1_RUNTIME_SURFACE_EXIT,
    inspect_official_runtime_surface,
)


def test_all_official_initial_frames_close_m1_runtime_surface() -> None:
    environments = Path(__file__).resolve().parents[3] / "environment_files"
    with tempfile.TemporaryDirectory(prefix="arc3-m1-acceptance-") as temporary:
        report = inspect_official_runtime_surface(
            environments_dir=environments,
            recordings_dir=Path(temporary) / "recordings",
        )

    assert report["exit_status"] == M1_RUNTIME_SURFACE_EXIT
    assert report["failure_reasons"] == []
    assert report["advertised_game_count"] == 25
    assert report["inspected_game_count"] == 25
    assert report["total_win_level_count"] == 183
    assert report["multi_frame_initial_game_count"] >= 2
    assert report["normal_action_union"] == list(range(1, 8))
    assert report["legal_action_union"] == list(range(8))
    assert set(report["pointer_categories"]) >= M1_POINTER_CATEGORIES
    assert report["hds_authorized_game_count"] == 25
    assert report["external_action_game_count"] == 25
    assert report["reobserved_game_count"] == 25
    assert report["single_cognitive_session_count"] == 1
    assert report["episode_count"] == 25
    assert report["scorecard_closed"] is True
