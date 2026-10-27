from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "HDS/学習系統/v0.4.2")]

from ARC3ProbabilisticMultiStep価値学習 import (
    _ProbabilisticValueMemory,
    _context_key,
)
from 接続.ARC3境界 import 観測する


def _observation(game_id: str):
    return 観測する(
        {
            "game_id": game_id,
            "guid": "test-run",
            "state": "NOT_FINISHED",
            "frame": [[[0, 1], [1, 1]]],
            "available_actions": [1, 2, 6],
            "levels_completed": 0,
            "win_levels": 3,
        },
        観測通番=0,
    )


class ProbabilisticMultiStepValueTests(unittest.TestCase):
    def test_context_excludes_game_identity(self):
        self.assertEqual(_context_key(_observation("game-a")), _context_key(_observation("game-b")))
        self.assertNotIn("game-a", _context_key(_observation("game-a")))

    def test_value_iteration_ranks_observed_positive_transition_above_terminal_noop(self):
        state = _context_key(_observation("game-a"))
        memory = _ProbabilisticValueMemory()
        memory.observe(state, 1, 0.5, state)
        memory.observe(state, 1, 0.5, state)
        memory.observe(state, 2, -1.0, None)

        self.assertGreater(memory.value(state, 1), memory.value(state, 2))

    def test_snapshot_round_trip_preserves_memory_without_identifiers(self):
        state = _context_key(_observation("game-a"))
        memory = _ProbabilisticValueMemory()
        memory.observe(state, 1, 0.5, state)
        snapshot = memory.snapshot()
        serialized = json.dumps(snapshot, sort_keys=True)
        restored = _ProbabilisticValueMemory.from_snapshot(snapshot)

        self.assertNotIn("game_id", serialized)
        self.assertNotIn("level_id", serialized)
        self.assertEqual(memory.digest(), restored.digest())
        self.assertEqual(memory.value(state, 1), restored.value(state, 1))


if __name__ == "__main__":
    unittest.main()
