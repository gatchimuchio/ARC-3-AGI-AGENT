import unittest

import numpy as np

from 検証.ARC3複数Frame公開観測診断 import _grid_sequence, _transition_metrics


class MultiFrameAuditTests(unittest.TestCase):
    def test_grid_sequence_preserves_order_and_values(self):
        grids = [np.array([[0, 1], [2, 3]]), np.array([[3, 2], [1, 0]])]
        result = _grid_sequence(grids)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ((0, 1), (2, 3)))
        self.assertEqual(result[1], ((3, 2), (1, 0)))

    def test_transient_cells_count_only_changes_returned_to_prior_value(self):
        prior = type("Raw", (), {"frame": [np.array([[0, 0], [1, 1]])]})()
        response = type(
            "Raw",
            (),
            {
                "frame": [
                    np.array([[2, 0], [1, 1]]),
                    np.array([[0, 3], [1, 1]]),
                    np.array([[0, 0], [1, 1]]),
                ]
            },
        )()
        result = _transition_metrics(prior, response)
        self.assertEqual(result["response_count"], 1)
        self.assertEqual(result["response_frame_count"], 3)
        self.assertEqual(result["multi_frame_responses"], 1)
        self.assertEqual(result["distinct_response_grids"], 3)
        self.assertEqual(result["intermediate_grids_different_from_final"], 2)
        self.assertEqual(result["transient_cells_returning_to_prior_value"], 2)

    def test_missing_or_different_shape_frames_are_uncomparable(self):
        empty = type("Raw", (), {"frame": []})()
        frame = type("Raw", (), {"frame": [np.array([[0, 1]])]})()
        self.assertEqual(_transition_metrics(empty, frame)["uncomparable_transitions"], 1)
        mismatch = type("Raw", (), {"frame": [np.array([[0], [1]])]})()
        self.assertEqual(_transition_metrics(frame, mismatch)["uncomparable_transitions"], 1)


if __name__ == "__main__":
    unittest.main()
