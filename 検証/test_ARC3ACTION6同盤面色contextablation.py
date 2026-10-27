from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3ACTION6同盤面色contextablation as context
from 接続.観測駆動探索Action import 観測駆動探索方針


def _observation(board, *, actions=frozenset({6}), state="NOT_FINISHED"):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=0,
    )


class Action6SameBoardColorContextTests(unittest.TestCase):
    def test_unknown_board_uses_base_color_choice(self):
        board = ((1, 2), (1, 2))
        baseline = 観測駆動探索方針(乱数種=11)
        candidate = context._ACTION6同盤面色報酬方針(乱数種=11)

        self.assertEqual(candidate.選ぶ(_observation(board)), baseline.選ぶ(_observation(board)))

    def test_known_board_color_mean_changes_only_temporary_color_rewards(self):
        board = ((1, 2), (1, 2))
        policy = context._ACTION6同盤面色報酬方針(乱数種=1)
        policy._色回数.update({1: 2, 2: 2})
        policy._色報酬合計.update({1: 10.0, 2: 0.0})
        policy._盤面色報酬[board] = {2: (1, 20.0)}
        original_global_rewards = policy._色報酬合計.copy()

        choice = policy.選ぶ(_observation(board))

        self.assertEqual(choice.作用番号, 6)
        self.assertEqual(policy._選択座標色, 2)
        self.assertEqual(policy._色報酬合計, original_global_rewards)
        self.assertEqual(policy._回数, {})

    def test_action6_public_reward_is_recorded_by_board_and_selected_color(self):
        board = ((1, 2), (1, 2))
        policy = context._ACTION6同盤面色報酬方針(乱数種=5)
        before = _observation(board)
        action = policy.選ぶ(before)
        after = _observation(((3, 2), (1, 2)))

        receipt = policy.応答を記録する(before, action, after)
        color = receipt["座標可視色"]

        self.assertEqual(policy._盤面色報酬[board][color][0], 1)
        self.assertEqual(policy._盤面色報酬[board][color][1], receipt["公開応答報酬"])

    def test_discrete_action_choice_ignores_board_color_context(self):
        board = ((1, 2), (1, 2))
        policy = context._ACTION6同盤面色報酬方針(乱数種=7)
        policy._回数.update({1: 4, 6: 4})
        policy._報酬合計.update({1: 100.0, 6: -100.0})
        policy._総作用数 = 8
        policy._色回数[2] = 1
        policy._色報酬合計[2] = 0.0
        policy._盤面色報酬[board] = {2: (1, 100.0)}

        choice = policy.選ぶ(_observation(board, actions=frozenset({1, 6})))

        self.assertEqual(choice.作用番号, 1)


if __name__ == "__main__":
    unittest.main()
