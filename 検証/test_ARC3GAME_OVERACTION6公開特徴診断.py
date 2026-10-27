import unittest

from 検証.ARC3GAME_OVERACTION6公開特徴診断 import _classify_outcome


class Action6GameOverFeatureDiagnosticTests(unittest.TestCase):
    def test_game_over_has_priority_over_level_delta_and_board_change(self):
        self.assertEqual(_classify_outcome("GAME_OVER", 1, 3), "game_over")

    def test_level_progress_and_decrease_precede_board_change(self):
        self.assertEqual(_classify_outcome("NOT_FINISHED", 1, 3), "level_progress")
        self.assertEqual(_classify_outcome("NOT_FINISHED", -1, 3), "level_decrease")

    def test_no_op_and_board_change_are_disjoint(self):
        self.assertEqual(_classify_outcome("NOT_FINISHED", 0, 0), "no_op")
        self.assertEqual(_classify_outcome("NOT_FINISHED", 0, 1), "board_change")


if __name__ == "__main__":
    unittest.main()
