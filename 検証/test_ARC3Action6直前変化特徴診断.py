from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "検証")]

from ARC3Action6直前変化特徴診断 import _Audit, _PreviousChangeContext, _policy_type
from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針


def _observation(number, board, *, state="NOT_FINISHED", levels=0):
    return 観測する(
        {
            "game_id": "synthetic-public",
            "guid": "synthetic-run",
            "state": state,
            "frame": [board],
            "available_actions": [6],
            "levels_completed": levels,
            "win_levels": 5,
        },
        観測通番=number,
    )


class PreviousChangeFeatureTests(unittest.TestCase):
    def test_mask_is_only_the_immediately_preceding_public_transition(self):
        context = _PreviousChangeContext()
        first = _observation(0, [[0, 0], [0, 0]])
        second = _observation(1, [[1, 0], [0, 0]])
        third = _observation(2, [[1, 0], [0, 1]])
        self.assertEqual(context.feature(first.最新盤面, 0, 0), "unknown")
        self.assertEqual(context.observe(first, second), "comparable_response")
        self.assertEqual(context.feature(second.最新盤面, 0, 0), "changed")
        self.assertEqual(context.feature(second.最新盤面, 1, 1), "unchanged")
        context.observe(second, third)
        self.assertEqual(context.feature(third.最新盤面, 0, 0), "unchanged")
        self.assertEqual(context.feature(third.最新盤面, 1, 1), "changed")

    def test_terminal_level_shape_and_reset_boundaries_clear_context(self):
        first = _observation(0, [[0, 0], [0, 0]])
        second = _observation(1, [[1, 0], [0, 0]])
        cases = (
            (_observation(2, [[1, 1], [0, 0]], state="GAME_OVER"), "terminal_clear"),
            (_observation(2, [[1, 1], [0, 0]], levels=1), "level_transition_clear"),
            (_observation(2, [[1, 1, 0]]), "shape_change_clear"),
        )
        for after, reason in cases:
            with self.subTest(reason=reason):
                context = _PreviousChangeContext()
                context.observe(first, second)
                self.assertEqual(context.observe(second, after), reason)
                self.assertEqual(context.feature(after.最新盤面, 0, 0), "unknown")

        audit = _Audit()
        policy = _policy_type(audit, 0)(乱数種=9)
        policy._previous_change.observe(first, second)
        reset = policy.選ぶ(_observation(2, [[1, 0], [0, 0]], state="GAME_OVER"))
        self.assertEqual(reset.作用番号, 0)
        self.assertEqual(policy._previous_change.feature(second.最新盤面, 0, 0), "unknown")

    def test_observer_preserves_action_sequence_and_rng_through_lifecycle(self):
        audit = _Audit()
        baseline = 観測駆動探索方針(乱数種=43, 可視変化係数=0.0)
        observer = _policy_type(audit, 7)(乱数種=43, 可視変化係数=0.0)
        board_a = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
        board_b = [[0, 1, 1], [1, 0, 1], [0, 1, 0]]
        frames = [
            _observation(0, board_a),
            _observation(1, board_b),
            _observation(2, board_a),
            _observation(3, board_b, levels=1),
            _observation(4, board_a, levels=1, state="GAME_OVER"),
            _observation(5, board_a, levels=0),
            _observation(6, board_b),
        ]
        for before, after in zip(frames, frames[1:]):
            previous_action = baseline.選ぶ(before)
            observed_action = observer.選ぶ(before)
            self.assertEqual(previous_action, observed_action)
            self.assertEqual(baseline._rng.getstate(), observer._rng.getstate())
            if previous_action.作用番号 != 0:
                self.assertEqual(
                    baseline.応答を記録する(before, previous_action, after),
                    observer.応答を記録する(before, observed_action, after),
                )
        self.assertEqual(audit.counts["action6_responses"], 5)

    def test_aggregate_records_distinct_game_counts_without_identifiers(self):
        audit = _Audit()
        audit.record("changed", "level_progress", 1001, 3, 4, 0)
        audit.record("changed", "level_progress", 1001, 1, 1, 0)
        audit.record("changed", "level_progress", 2002, 2, 1, 0)
        snapshot = audit.snapshot()
        changed = snapshot["selected_feature_outcomes"][0]
        self.assertEqual(changed["outcomes"]["level_progress"]["responses"], 3)
        self.assertEqual(changed["outcomes"]["level_progress"]["distinct_public_games"], 2)
        self.assertEqual(snapshot["counts"]["selected_color_both_groups_opportunities"], 3)
        self.assertEqual(snapshot["both_groups_distinct_public_games"], 2)
        encoded = json.dumps(snapshot)
        for raw in ("1001", "2002", '"x"', '"y"', '"mask"', '"board"'):
            self.assertNotIn(raw, encoded)


if __name__ == "__main__":
    unittest.main()
