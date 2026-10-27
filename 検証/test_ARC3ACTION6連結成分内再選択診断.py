import unittest

from 検証.ARC3ACTION6連結成分内再選択診断 import _component_cells, _summarize


class Action6ComponentRepeatDiagnosticTest(unittest.TestCase):
    def test_同色の4近傍だけを成分として集める(self):
        board = (
            (0, 1, 0),
            (1, 0, 1),
            (0, 1, 0),
        )

        self.assertEqual(_component_cells(board, 0, 0), frozenset({(0, 0)}))
        self.assertEqual(
            _component_cells(((2, 2, 0), (2, 0, 2)), 0, 0),
            frozenset({(0, 0), (1, 0), (0, 1)}),
        )

    def test_再選択の率とbucket抑制を匿名集計する(self):
        samples = []
        for seed in (7, 31):
            for repeated in (False, True):
                for index in range(10):
                    samples.append(
                        {
                            "seed": seed,
                            "run": f"{seed}:main",
                            "repeated_component": repeated,
                            "size_bucket": "3_4",
                            "no_op": repeated and index < 6,
                            "game_over": False,
                            "level_progress": index < (2 if not repeated else 1),
                        }
                    )
        for seed, count in ((7, 6), (31, 3)):
            for index in range(count):
                samples.append(
                    {
                        "seed": seed,
                        "run": f"{seed}:sparse",
                        "repeated_component": False,
                        "size_bucket": "1",
                        "no_op": False,
                        "game_over": False,
                        "level_progress": False,
                    }
                )
        for index in range(10):
            samples.append(
                {
                    "seed": 7,
                    "run": "7:single-seed",
                    "repeated_component": True,
                    "size_bucket": "9_plus",
                    "no_op": False,
                    "game_over": False,
                    "level_progress": False,
                }
            )

        result = _summarize(samples, no_hold_illegal_duplicate_regression=True)

        self.assertEqual(result["component_reselection"]["actions"], 30)
        self.assertEqual(result["no_op_delta_percentage_points"], 40.0)
        self.assertEqual(len(result["per_seed_summary"]), 3)
        self.assertEqual(
            result["per_seed_summary"][2]["component_reselection"]["actions"],
            "suppressed (<10)",
        )
        self.assertTrue(result["preconditions"]["reselection_level_progress_rate_not_above_first"])
        self.assertTrue(result["preconditions"]["eligible_for_dev_ablation"])
        self.assertEqual(
            {
                row["component_size"]
                for row in result["component_size_buckets_suppressed_below_10_across_two_seeds"]
            },
            {"3_4"},
        )
        self.assertNotIn(
            "seed", result["component_size_buckets_suppressed_below_10_across_two_seeds"][0]
        )

    def test_level進行は件数でなく率を比較する(self):
        samples = []
        for index in range(20):
            samples.append(
                {
                    "seed": 7,
                    "run": "first",
                    "repeated_component": False,
                    "size_bucket": "2",
                    "no_op": False,
                    "game_over": False,
                    "level_progress": index < 2,
                }
            )
        for index in range(2):
            samples.append(
                {
                    "seed": 7,
                    "run": "repeat",
                    "repeated_component": True,
                    "size_bucket": "2",
                    "no_op": False,
                    "game_over": False,
                    "level_progress": index == 0,
                }
            )

        result = _summarize(samples)

        self.assertFalse(result["preconditions"]["reselection_level_progress_rate_not_above_first"])


if __name__ == "__main__":
    unittest.main()
