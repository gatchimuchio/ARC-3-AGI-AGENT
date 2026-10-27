import unittest

from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針
from 検証.ARC3探索Actionローカル評価 import _レベル進行時色統計resetablation
from 検証.ARC3レベル間色統計評価 import _gate


def _observation(number, board, *, levels=0):
    return 観測する(
        {
            "game_id": "public-test",
            "guid": "run",
            "state": "NOT_FINISHED",
            "frame": [board],
            "available_actions": [6],
            "levels_completed": levels,
            "win_levels": 3,
        },
        観測通番=number,
    )


def _stage_result(seeds, previous_noop, candidate_noop):
    previous = {}
    candidate = {}
    for seed in seeds:
        key = str(seed)
        previous[key] = {
            "levels_completed": 1,
            "no_op_actions": previous_noop,
            "game_over_events": 0,
        }
        candidate[key] = {
            "levels_completed": 1,
            "no_op_actions": candidate_noop,
            "game_over_events": 0,
            "policy_holds": 0,
            "illegal_action_attempts": 0,
            "duplicate_observation_steps": 0,
        }
    return {
        "seeds": list(seeds),
        "previous": previous,
        "candidate": candidate,
        "previous_matches_C2-003": {str(seed): {"match": True} for seed in seeds},
        "same_public_start_pairs": {str(seed): 5 for seed in seeds},
        "paired_environment_runs": {str(seed): 5 for seed in seeds},
    }


class LevelColorTransferTests(unittest.TestCase):
    def test_level_progress_clears_only_color_ucb_state(self):
        board = [[0, 1], [1, 0]]
        next_board = [[0, 1], [1, 2]]
        before = _observation(0, board)
        after = _observation(1, next_board, levels=1)
        previous = 観測駆動探索方針(乱数種=19)
        candidate = _レベル進行時色統計resetablation(乱数種=19)

        previous_action = previous.選ぶ(before)
        candidate_action = candidate.選ぶ(before)
        self.assertEqual(previous_action, candidate_action)
        previous.応答を記録する(before, previous_action, after)
        candidate.応答を記録する(before, candidate_action, after)

        self.assertEqual(candidate._回数, previous._回数)
        self.assertEqual(candidate._報酬合計, previous._報酬合計)
        self.assertEqual(candidate._rng.getstate(), previous._rng.getstate())
        self.assertEqual(candidate._色回数, {})
        self.assertEqual(candidate._色報酬合計, {})
        self.assertTrue(previous._色回数)

    def test_without_level_progress_color_ucb_state_is_kept(self):
        board = [[0, 1], [1, 0]]
        before = _observation(0, board)
        after = _observation(1, [[0, 1], [1, 2]])
        candidate = _レベル進行時色統計resetablation(乱数種=23)

        action = candidate.選ぶ(before)
        candidate.応答を記録する(before, action, after)

        self.assertTrue(candidate._色回数)
        self.assertTrue(candidate._色報酬合計)

    def test_dev_gate_requires_reproducible_noop_reduction_and_level_retention(self):
        result = _stage_result((7, 31, 73), 5, 4)

        gate = _gate("dev", result)

        self.assertTrue(gate["passed"])

        result["candidate"]["31"]["levels_completed"] = 0
        self.assertFalse(_gate("dev", result)["passed"])

    def test_holdout_gate_checks_each_seed_and_total_noop(self):
        result = _stage_result((31,), 5, 4)

        self.assertTrue(_gate("holdout", result)["passed"])

        result["candidate"]["31"]["game_over_events"] = 1
        self.assertFalse(_gate("holdout", result)["passed"])


if __name__ == "__main__":
    unittest.main()
