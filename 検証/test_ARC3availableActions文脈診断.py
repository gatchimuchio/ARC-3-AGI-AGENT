import unittest

from 検証.ARC3availableActions文脈診断 import _summarize


class AvailableActions文脈集計Test(unittest.TestCase):
    def test_反復文脈とAction応答率の方向を匿名集計する(self):
        samples = []
        for seed in (7, 31, 73):
            for _ in range(10):
                samples.append(
                    {
                        "seed": seed,
                        "run": str(seed),
                        "available_actions": [1, 2, 6],
                        "action_id": 6,
                        "no_op": False,
                        "game_over": False,
                        "level_progress": False,
                    }
                )
            for index in range(10):
                samples.append(
                    {
                        "seed": seed,
                        "run": str(seed),
                        "available_actions": [1, 2, 3, 6],
                        "action_id": 6,
                        "no_op": index < 6,
                        "game_over": False,
                        "level_progress": False,
                    }
                )
        samples.append(
            {
                "seed": 7,
                "run": "rare",
                "available_actions": [7],
                "action_id": 7,
                "no_op": True,
                "game_over": False,
                "level_progress": False,
            }
        )

        result = _summarize(samples)

        self.assertEqual(result["total_actions"], 61)
        self.assertEqual(result["distinct_available_action_sets"], 3)
        self.assertEqual(result["within_run"]["runs"], 4)
        self.assertEqual(result["within_run"]["runs_with_multiple_sets"], 3)
        self.assertGreater(result["within_run"]["total_signature_transitions"], 0)
        self.assertEqual(len(result["eligible_available_action_sets"]), 2)
        self.assertEqual(result["eligible_context_action_count"], 2)
        self.assertNotIn("seed", result["eligible_context_actions"][0])
        pair = result["repeated_action_context_pairs"][0]
        self.assertEqual(pair["action_id"], 6)
        self.assertEqual(abs(pair["consistent_no_op_direction_seeds"]), 3)

    def test_反復不足の文脈は適格化しない(self):
        result = _summarize(
            [
                {
                    "seed": 7,
                    "run": "single",
                    "available_actions": [1, 6],
                    "action_id": 6,
                    "no_op": True,
                    "game_over": False,
                    "level_progress": False,
                }
            ]
        )

        self.assertEqual(result["total_actions"], 1)
        self.assertEqual(result["eligible_available_action_sets"], [])
        self.assertEqual(result["eligible_context_action_count"], 0)
        self.assertEqual(result["repeated_action_context_pairs"], [])


if __name__ == "__main__":
    unittest.main()
