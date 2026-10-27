"""Small exact-shape geometry sanity checks, without any HDS calls."""

from types import SimpleNamespace
import unittest

import ARC3公開画素効果診断 as effects


def board(points, height=7, width=10):
    rows = [[0] * width for _ in range(height)]
    for x, y, color in points:
        rows[y][x] = color
    return tuple(map(tuple, rows))


class GeometrySanity(unittest.TestCase):
    def test_unique_rigid_translation_and_local_counts(self):
        before = board([(x, y, 1) for x in (1, 2) for y in (1, 2)])
        after = board([(x, y, 1) for x in (2, 3) for y in (1, 2)])
        values, counts, deltas, areas = effects._effects(SimpleNamespace(board=before), SimpleNamespace(number=6, x=1, y=1), SimpleNamespace(board=after))
        self.assertEqual(counts["unique_translated_correspondences"], 1)
        self.assertEqual(deltas, {(1, 0): 1})
        self.assertEqual(areas, {4: 1})
        self.assertEqual(values["changed_pixels"], 4)
        self.assertEqual(values["changed_pixels_in_unique_translation_union"], 4)
        self.assertEqual(values["target_local_3x3_changed_pixels"], 2)
        self.assertEqual(values["target_local_7x7_changed_pixels"], 4)

    def test_duplicate_shapes_remain_unknown(self):
        before = board([(1, 1, 1), (6, 3, 1)])
        after = board([(2, 1, 1), (7, 3, 1)])
        counts, deltas, _, _ = effects._translations(before, after)
        self.assertEqual(counts["ambiguous_shape_groups"], 1)
        self.assertEqual(counts["ambiguous_before_components"], 2)
        self.assertEqual(counts["ambiguous_after_components"], 2)
        self.assertEqual(counts["unique_translated_correspondences"], 0)
        self.assertEqual(deltas, {})

    def test_recoloring_is_not_same_color_motion_and_noop_has_zero_motion(self):
        before = board([(1, 1, 1), (2, 1, 1)])
        recolored = board([(1, 1, 2), (2, 1, 2)])
        counts, deltas, _, _ = effects._translations(before, recolored)
        self.assertEqual(counts["unique_translated_correspondences"], 0)
        self.assertEqual(deltas, {})
        counts, deltas, _, _ = effects._translations(before, before)
        self.assertEqual(counts["unique_translated_correspondences"], 0)
        self.assertEqual(deltas, {})


if __name__ == "__main__":
    unittest.main()
