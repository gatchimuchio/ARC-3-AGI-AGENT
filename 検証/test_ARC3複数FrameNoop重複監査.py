import unittest

import numpy as np

from 検証.ARC3複数FrameNoop重複監査 import _classify, _snapshot


def _raw(frames, levels=0):
    return type("Raw", (), {"frame": frames, "levels_completed": levels})()


class MultiFrameNoopAuditTests(unittest.TestCase):
    def test_snapshot_does_not_follow_later_sdk_grid_mutation(self):
        grid = np.array([[0, 1]])
        raw = _raw([grid])
        saved = _snapshot(raw)
        grid[0, 1] = 2
        self.assertEqual(saved.frame[0].tolist(), [[0, 1]])

    def test_transient_multiframe_is_counted_as_policy_noop(self):
        before = _raw([np.array([[0, 0], [1, 1]])])
        after = _raw(
            [
                np.array([[2, 0], [1, 1]]),
                np.array([[0, 3], [1, 1]]),
                np.array([[0, 0], [1, 1]]),
            ]
        )
        result = _classify("ACTION5", before, after)
        self.assertEqual(result["policy_noop_penalty"], 1)
        self.assertEqual(result["evaluation_noop_actions"], 1)
        self.assertEqual(result["policy_noop_multiframe"], 1)
        self.assertEqual(result["policy_noop_intermediate_diff"], 1)
        self.assertEqual(result["policy_noop_transient_cell_occurrences"], 2)

    def test_reset_and_positive_level_progress_are_not_noop(self):
        board = [np.array([[0, 0]])]
        before = _raw(board, 0)
        unchanged = _raw([np.array([[0, 0]])], 1)
        self.assertEqual(_classify("ACTION1", before, unchanged)["policy_noop_penalty"], 0)
        self.assertEqual(_classify("RESET", before, before)["policy_noop_penalty"], 0)

    def test_policy_penalty_and_reported_noop_are_distinct_on_level_decrease(self):
        board = [np.array([[0, 0]])]
        before = _raw(board, 1)
        after = _raw([np.array([[0, 0]])], 0)
        result = _classify("ACTION1", before, after)
        self.assertEqual(result["policy_noop_penalty"], 1)
        self.assertEqual(result["evaluation_noop_actions"], 0)
        self.assertEqual(result["level_decrease_responses"], 1)


if __name__ == "__main__":
    unittest.main()
