import unittest

from 検証.ARC3ACTION6座標特徴診断 import _cell_features


class Action6CoordinateFeatureTests(unittest.TestCase):
    def test_features_use_relative_color_neighbors_and_center_buckets(self):
        board = (
            (0, 0, 0),
            (0, 1, 1),
            (0, 1, 2),
        )

        result = _cell_features(board, 1, 1)

        self.assertEqual(
            result,
            {
                "selected_color_frequency": "middle_10_to_50pct",
                "same_color_neighbors_4": "1_2",
                "relative_center_distance": "central",
            },
        )

    def test_rare_color_outer_cell_has_no_identity_or_coordinate_output(self):
        board = (
            (0, 0, 0, 0),
            (0, 0, 0, 0),
            (0, 0, 0, 0),
            (0, 0, 0, 1),
        )

        result = _cell_features(board, 3, 3)

        self.assertEqual(result["selected_color_frequency"], "rare_lt_10pct")
        self.assertEqual(result["same_color_neighbors_4"], "0")
        self.assertEqual(result["relative_center_distance"], "outer")
        self.assertNotIn("color", result)
        self.assertNotIn("x", result)
        self.assertNotIn("y", result)

    def test_rejects_invalid_board_or_coordinate(self):
        with self.assertRaises(ValueError):
            _cell_features(((0, 1), (0,)), 0, 0)
        with self.assertRaises(ValueError):
            _cell_features(((0,),), 1, 0)


if __name__ == "__main__":
    unittest.main()
