import unittest

from 検証.ARC3探索Actionローカル評価 import _ACTION6中心距離順ablation
from 検証.ARC3ACTION6中心距離評価 import _gate


class Action6CenterDistanceAblationTests(unittest.TestCase):
    def test_selects_unique_nearest_untried_coordinate(self):
        policy = _ACTION6中心距離順ablation(乱数種=13)
        board = tuple((0, 0, 0) for _ in range(3))

        selected = policy._座標を選ぶ(board)

        self.assertEqual(selected, (1, 1, 0))
        self.assertIn((1, 1), policy._座標試行[board])

    def test_excludes_tried_center_and_chooses_uniform_tie_set_member(self):
        policy = _ACTION6中心距離順ablation(乱数種=13)
        board = tuple((0, 0, 0) for _ in range(3))
        policy._座標試行[board] = {(1, 1)}

        selected = policy._座標を選ぶ(board)

        self.assertIn(selected[:2], {(1, 0), (0, 1), (2, 1), (1, 2)})
        self.assertIn(selected[:2], policy._座標試行[board])

    def test_dev_gate_requires_two_seed_noop_reductions_and_total_reduction(self):
        result = {
            "previous": {
                "7": {"levels_completed": 1, "game_over_events": 0, "no_op_actions": 5},
                "31": {"levels_completed": 1, "game_over_events": 0, "no_op_actions": 5},
                "73": {"levels_completed": 1, "game_over_events": 0, "no_op_actions": 5},
            },
            "candidate": {
                "7": {
                    "levels_completed": 1,
                    "game_over_events": 0,
                    "no_op_actions": 4,
                    "policy_holds": 0,
                    "illegal_action_attempts": 0,
                    "duplicate_observation_steps": 0,
                },
                "31": {
                    "levels_completed": 1,
                    "game_over_events": 0,
                    "no_op_actions": 4,
                    "policy_holds": 0,
                    "illegal_action_attempts": 0,
                    "duplicate_observation_steps": 0,
                },
                "73": {
                    "levels_completed": 1,
                    "game_over_events": 0,
                    "no_op_actions": 6,
                    "policy_holds": 0,
                    "illegal_action_attempts": 0,
                    "duplicate_observation_steps": 0,
                },
            },
            "previous_matches_C2-003": {str(seed): {"baseline": True} for seed in (7, 31, 73)},
            "same_public_start_pairs": {str(seed): 5 for seed in (7, 31, 73)},
            "paired_environment_runs": {str(seed): 5 for seed in (7, 31, 73)},
        }

        gate = _gate("dev", result)

        self.assertTrue(gate["passed"])

    def test_holdout_gate_rejects_per_seed_noop_regression(self):
        previous = {
            str(seed): {
                "levels_completed": 1,
                "game_over_events": 0,
                "no_op_actions": 5,
                "policy_holds": 0,
                "illegal_action_attempts": 0,
                "duplicate_observation_steps": 0,
            }
            for seed in (7, 31, 73)
        }
        candidate = {seed: dict(counts) for seed, counts in previous.items()}
        candidate["7"]["no_op_actions"] = 6
        candidate["31"]["no_op_actions"] = 4
        candidate["73"]["no_op_actions"] = 4
        result = {
            "previous": previous,
            "candidate": candidate,
            "previous_matches_C2-003": {str(seed): {"baseline": True} for seed in (7, 31, 73)},
            "same_public_start_pairs": {str(seed): 20 for seed in (7, 31, 73)},
            "paired_environment_runs": {str(seed): 20 for seed in (7, 31, 73)},
        }

        gate = _gate("holdout", result)

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["no_op_not_higher_each_seed"])


if __name__ == "__main__":
    unittest.main()
