import unittest

from 検証.ARC3ACTION6同色近傍評価 import _gate, _neighbor_bucket
from 検証.ARC3探索Actionローカル評価 import _ACTION6同色近傍ありablation


class Action6SameColorNeighborTests(unittest.TestCase):
    @staticmethod
    def _stage_result(stage, seeds):
        previous = {}
        candidate = {}
        for seed in seeds:
            key = str(seed)
            previous[key] = {
                "levels_completed": 1,
                "no_op_actions": 5,
                "game_over_events": 2,
            }
            candidate[key] = {
                "levels_completed": 1,
                "no_op_actions": 4 if seed in (7, 31) else 5,
                "game_over_events": 2,
                "policy_holds": 0,
                "illegal_action_attempts": 0,
                "duplicate_observation_steps": 0,
            }
        env_count = 5 if stage == "dev" else 20
        return {
            "seeds": list(seeds),
            "previous": previous,
            "candidate": candidate,
            "previous_matches_C2-003": {
                str(seed): {"all_metrics": True} for seed in seeds
            },
            "same_public_start_pairs": {str(seed): env_count for seed in seeds},
            "paired_environment_runs": {str(seed): env_count for seed in seeds},
        }

    def test_neighbor_bucket_uses_orthogonal_matching_cells(self):
        board = ((0, 0, 1), (1, 1, 1), (1, 1, 0))

        self.assertEqual(_neighbor_bucket(board, 2, 2), "0")
        self.assertEqual(_neighbor_bucket(board, 0, 0), "1_2")
        self.assertEqual(_neighbor_bucket(((2, 2, 2), (2, 2, 2), (2, 2, 2)), 1, 1), "3_4")

    def test_dev_gate_requires_two_seed_noop_reductions(self):
        gate = _gate("dev", self._stage_result("dev", (7, 31, 73)))

        self.assertTrue(gate["passed"])

        result = self._stage_result("dev", (7, 31, 73))
        result["candidate"]["31"]["no_op_actions"] = 5
        self.assertFalse(_gate("dev", result)["passed"])

    def test_holdout_gate_requires_total_noop_reduction(self):
        gate = _gate("holdout", self._stage_result("holdout", (7, 31, 73)))

        self.assertTrue(gate["passed"])

        result = self._stage_result("holdout", (7, 31, 73))
        result["candidate"]["7"]["no_op_actions"] = 5
        result["candidate"]["31"]["no_op_actions"] = 5
        result["candidate"]["73"]["no_op_actions"] = 5
        self.assertFalse(_gate("holdout", result)["passed"])

    def test_prefers_same_color_connected_untried_coordinates(self):
        board = ((0, 0, 1), (1, 1, 1), (1, 1, 0))
        policy = _ACTION6同色近傍ありablation(乱数種=11)
        policy._色回数.update({0: 1, 1: 1})
        policy._色報酬合計.update({0: 10.0, 1: 0.0})

        selected = policy._座標を選ぶ(board)

        self.assertIn(selected, {(0, 0, 0), (1, 0, 0)})
        self.assertIn(selected[:2], policy._座標試行[board])

    def test_falls_back_to_isolated_coordinate_after_connected_cells_are_tried(self):
        board = ((0, 0, 1), (1, 1, 1), (1, 1, 0))
        policy = _ACTION6同色近傍ありablation(乱数種=11)
        policy._色回数.update({0: 1, 1: 1})
        policy._色報酬合計.update({0: 10.0, 1: 0.0})
        policy._座標試行[board] = {(0, 0), (1, 0)}

        selected = policy._座標を選ぶ(board)

        self.assertEqual(selected, (2, 2, 0))

    def test_falls_back_when_selected_color_has_no_connected_cell(self):
        board = ((0, 1, 1), (1, 1, 1), (1, 1, 1))
        policy = _ACTION6同色近傍ありablation(乱数種=11)
        policy._色回数.update({0: 1, 1: 1})
        policy._色報酬合計.update({0: 10.0, 1: 0.0})

        selected = policy._座標を選ぶ(board)

        self.assertEqual(selected, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
