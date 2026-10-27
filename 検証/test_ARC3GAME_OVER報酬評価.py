import unittest

from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針
from 検証.ARC3GAME_OVER応答罰評価 import _gate
from 検証.ARC3探索Actionローカル評価 import _GAME_OVER罰ablation


def _observation(number, board, *, state="NOT_FINISHED", levels=0):
    return 観測する(
        {
            "game_id": "public-test",
            "guid": "run",
            "state": state,
            "frame": [board],
            "available_actions": [6] if state == "NOT_FINISHED" else [],
            "levels_completed": levels,
            "win_levels": 3,
        },
        観測通番=number,
    )


def _gate_result(game_over_values=(5, 5, 6)):
    previous = {}
    candidate = {}
    for seed, game_over in zip((7, 31, 73), game_over_values):
        key = str(seed)
        previous[key] = {
            "levels_completed": 1,
            "no_op_actions": 5,
            "game_over_events": 6,
        }
        candidate[key] = {
            "levels_completed": 1,
            "no_op_actions": 5,
            "game_over_events": game_over,
            "policy_holds": 0,
            "illegal_action_attempts": 0,
            "duplicate_observation_steps": 0,
        }
    return {
        "previous": previous,
        "candidate": candidate,
        "previous_matches_C2-003": {
            str(seed): {"all_metrics": True} for seed in (7, 31, 73)
        },
        "same_public_start_pairs": {str(seed): 5 for seed in (7, 31, 73)},
        "paired_environment_runs": {str(seed): 5 for seed in (7, 31, 73)},
    }


class GameOverRewardTests(unittest.TestCase):
    def test_gate_requires_gameover_reduction_in_two_seeds_without_regression(self):
        self.assertTrue(_gate(_gate_result())["passed"])

        result = _gate_result((5, 6, 6))
        self.assertFalse(_gate(result)["passed"])

        result = _gate_result()
        result["candidate"]["31"]["levels_completed"] = 0
        self.assertFalse(_gate(result)["passed"])

    def test_game_over_penalizes_action_and_selected_color_by_one(self):
        board = [[0, 0], [1, 1]]
        before = _observation(0, board)
        after = _observation(1, [[0, 1], [1, 1]], state="GAME_OVER")
        previous = 観測駆動探索方針(乱数種=37)
        candidate = _GAME_OVER罰ablation(乱数種=37)
        previous_action = previous.選ぶ(before)
        candidate_action = candidate.選ぶ(before)
        self.assertEqual(previous_action, candidate_action)

        previous_result = previous.応答を記録する(before, previous_action, after)
        candidate_result = candidate.応答を記録する(before, candidate_action, after)
        color = candidate_result["座標可視色"]

        self.assertEqual(candidate_result["公開応答報酬"], previous_result["公開応答報酬"] - 1.0)
        self.assertEqual(candidate._報酬合計[6], previous._報酬合計[6] - 1.0)
        self.assertEqual(candidate._色報酬合計[color], previous._色報酬合計[color] - 1.0)

    def test_no_extra_penalty_when_level_progresses(self):
        board = [[0, 0], [1, 1]]
        before = _observation(0, board)
        after = _observation(1, [[0, 1], [1, 1]], state="GAME_OVER", levels=1)
        previous = 観測駆動探索方針(乱数種=41)
        candidate = _GAME_OVER罰ablation(乱数種=41)
        previous_action = previous.選ぶ(before)
        candidate_action = candidate.選ぶ(before)

        previous_result = previous.応答を記録する(before, previous_action, after)
        candidate_result = candidate.応答を記録する(before, candidate_action, after)

        self.assertEqual(candidate_result["公開応答報酬"], previous_result["公開応答報酬"])
        self.assertEqual(candidate._報酬合計, previous._報酬合計)
        self.assertEqual(candidate._色報酬合計, previous._色報酬合計)


if __name__ == "__main__":
    unittest.main()
