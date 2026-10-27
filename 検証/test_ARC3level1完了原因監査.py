from __future__ import annotations

from 検証.ARC3level1完了原因監査 import _action_kind_and_outcome, _new_counts


def test_coordinate_noop_is_aggregated_without_coordinate_values() -> None:
    categorized = _action_kind_and_outcome(
        {
            "action_id": 6,
            "level_delta": 0,
            "changed_cells": 0,
            "after_state": "NOT_FINISHED",
            "lifecycle_action": False,
            "data": {"x": 32, "y": 17},
        }
    )

    assert categorized == ("coordinate", "no_op")
    assert _new_counts()["coordinate"]["selected"] == 0


def test_level_progress_takes_precedence_over_other_response_categories() -> None:
    categorized = _action_kind_and_outcome(
        {
            "action_id": 2,
            "level_delta": 1,
            "changed_cells": 0,
            "after_state": "GAME_OVER",
            "lifecycle_action": False,
        }
    )

    assert categorized == ("discrete", "level_progress")


def test_reset_is_not_mixed_with_gameplay_action_categories() -> None:
    categorized = _action_kind_and_outcome(
        {
            "action_id": 0,
            "level_delta": 0,
            "changed_cells": 0,
            "after_state": "NOT_FINISHED",
            "lifecycle_action": True,
        }
    )

    assert categorized is None
