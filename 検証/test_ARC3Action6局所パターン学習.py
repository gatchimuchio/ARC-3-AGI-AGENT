from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ARC3Action6局所パターン学習 import _LocalPatternMemory, _coordinate_feature


class Action6LocalPatternTests(unittest.TestCase):
    def test_feature_uses_generic_public_geometry_not_color_number_or_coordinates(self):
        board_a = ((0, 0, 1), (0, 1, 1), (2, 2, 2))
        board_b = ((5, 5, 3), (5, 3, 3), (4, 4, 4))
        feature_a = _coordinate_feature(board_a, 1, 1, 1)
        feature_b = _coordinate_feature(board_b, 3, 1, 1)

        self.assertEqual(feature_a, feature_b)
        self.assertNotIn("1|", feature_a)
        self.assertNotIn("3|", feature_b)

    def test_learned_feature_reward_changes_coordinate_score(self):
        memory = _LocalPatternMemory()
        memory.observe("rare|zero|edge", 0.5)
        memory.observe("rare|zero|edge", 0.5)
        memory.observe("common|three_plus|interior", -1.0)

        self.assertGreater(
            memory.score("rare|zero|edge"),
            memory.score("common|three_plus|interior"),
        )

    def test_snapshot_has_only_feature_statistics_and_round_trips(self):
        memory = _LocalPatternMemory()
        memory.observe("rare|zero|edge", 0.5)
        snapshot = memory.snapshot()
        serialized = json.dumps(snapshot, sort_keys=True)
        restored = _LocalPatternMemory.from_snapshot(snapshot)

        self.assertNotIn("game_id", serialized)
        self.assertNotIn("level_id", serialized)
        self.assertNotIn('"x"', serialized)
        self.assertNotIn('"y"', serialized)
        self.assertEqual(memory.digest(), restored.digest())


if __name__ == "__main__":
    unittest.main()
