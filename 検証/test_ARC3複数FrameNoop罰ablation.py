import unittest

from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針
from 検証.ARC3探索Actionローカル評価 import _中間Frame差分no_op罰ablation


def _observation(number, frames, actions=(1,), *, levels=0):
    return 観測する(
        {
            "game_id": "public-test",
            "guid": "run",
            "state": "NOT_FINISHED",
            "frame": frames,
            "available_actions": list(actions),
            "levels_completed": levels,
            "win_levels": 3,
        },
        観測通番=number,
    )


class IntermediateFrameNoopAblationTests(unittest.TestCase):
    def test_only_intermediate_noop_penalty_is_cancelled(self):
        board = [[0, 0], [1, 1]]
        transient = [[2, 0], [1, 1]]
        before = _observation(0, [board])
        after = _observation(1, [transient, board])

        previous = 観測駆動探索方針(乱数種=5)
        previous_action = previous.選ぶ(before)
        previous_result = previous.応答を記録する(before, previous_action, after)
        candidate = _中間Frame差分no_op罰ablation(乱数種=5)
        candidate_action = candidate.選ぶ(before)
        candidate_result = candidate.応答を記録する(before, candidate_action, after)

        self.assertEqual(previous_action.作用番号, candidate_action.作用番号)
        self.assertEqual(previous_result["公開応答報酬"], -1.0)
        self.assertEqual(candidate_result["公開応答報酬"], 0.0)
        self.assertEqual(candidate._報酬合計[candidate_action.作用番号], 0.0)

    def test_noop_without_different_intermediate_frame_keeps_penalty(self):
        board = [[0, 0], [1, 1]]
        before = _observation(0, [board])
        after = _observation(1, [board])
        candidate = _中間Frame差分no_op罰ablation(乱数種=5)

        action = candidate.選ぶ(before)
        response = candidate.応答を記録する(before, action, after)

        self.assertEqual(response["公開応答報酬"], -1.0)

    def test_action6_correction_updates_both_ucb_reward_totals(self):
        board = [[0, 1], [1, 0]]
        transient = [[2, 1], [1, 0]]
        before = _observation(0, [board], actions=(6,))
        after = _observation(1, [transient, board], actions=(6,))
        candidate = _中間Frame差分no_op罰ablation(乱数種=5)

        action = candidate.選ぶ(before)
        response = candidate.応答を記録する(before, action, after)
        color = response["座標可視色"]

        self.assertEqual(response["公開応答報酬"], 0.0)
        self.assertEqual(candidate._報酬合計[6], 0.0)
        self.assertEqual(candidate._色報酬合計[color], 0.0)


if __name__ == "__main__":
    unittest.main()
