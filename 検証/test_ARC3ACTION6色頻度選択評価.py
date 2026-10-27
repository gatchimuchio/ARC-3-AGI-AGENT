import unittest

from 検証.ARC3探索Actionローカル評価 import (
    _ACTION6中間頻度色遅延ablation,
    _ACTION6座標ablation,
)


class Action6ColorFrequencyPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.board = (
            tuple((0,) * 10 for _ in range(6))
            + tuple((1,) * 10 for _ in range(3))
            + ((1,) + (2,) * 9,)
        )

    def test_prefers_dominant_and_rare_untried_colors(self):
        policy = _ACTION6中間頻度色遅延ablation(乱数種=7)

        result = policy._色候補を優先する(self.board, [0, 1, 2])

        self.assertEqual(result, [0, 2])
        self.assertEqual(policy._middle_frequency_color_deferrals, 1)

    def test_keeps_middle_colors_when_no_alternative_is_untried(self):
        policy = _ACTION6中間頻度色遅延ablation(乱数種=7)

        result = policy._色候補を優先する(self.board, [1])

        self.assertEqual(result, [1])
        self.assertEqual(getattr(policy, "_middle_frequency_color_deferrals", 0), 0)

    def test_exactly_ten_percent_is_middle_not_rare(self):
        board = tuple((0,) * 6 + (1,) * 3 + (2,) for _ in range(10))
        policy = _ACTION6中間頻度色遅延ablation(乱数種=7)

        result = policy._色候補を優先する(board, [0, 1, 2])

        self.assertEqual(result, [0])

    def test_equal_maximum_colors_are_both_dominant(self):
        board = ((0, 0, 1, 1, 2), (0, 0, 1, 1, 2))
        policy = _ACTION6中間頻度色遅延ablation(乱数種=7)

        result = policy._色候補を優先する(board, [0, 1, 2])

        self.assertEqual(result, [0, 1])

    def test_shared_coordinate_ablation_preserves_existing_candidate_set(self):
        policy = _ACTION6座標ablation()

        result = policy._色候補を優先する(self.board, [0, 1, 2])

        self.assertEqual(result, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
