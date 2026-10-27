import unittest

from 検証.ARC3ACTION6GameOver特徴交差診断 import _record_joint_count


class Action6GameOverFeatureCrossTabTests(unittest.TestCase):
    def test_counts_outcomes_only_in_anonymous_joint_buckets(self):
        counts = {}
        features = {
            "selected_color_frequency": "rare_lt_10pct",
            "same_color_neighbors_4": "3_4",
            "relative_center_distance": "middle",
        }

        _record_joint_count(counts, features, "game_over")
        _record_joint_count(counts, features, "board_change")

        self.assertEqual(counts["middle"]["3_4"]["action6_responses"], 2)
        self.assertEqual(counts["middle"]["3_4"]["game_over"], 1)
        self.assertEqual(counts["middle"]["3_4"]["board_change"], 1)
        self.assertEqual(set(counts), {"middle"})
        self.assertEqual(set(counts["middle"]), {"3_4"})


if __name__ == "__main__":
    unittest.main()
