from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3RESET後ActionUCBclearablation as ablation


def _observation(board, *, state="NOT_FINISHED", actions=frozenset({1, 2})):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=0,
    )


class PostResetActionUcbClearTests(unittest.TestCase):
    def setUp(self):
        self.previous_counter = ablation._ACTIVE_CLEAR_COUNTER
        ablation._ACTIVE_CLEAR_COUNTER = [0]
        self.policy = ablation._RESET後Action統計clear方針(乱数種=29)
        self.board = ((1, 2), (2, 1))
        self.policy._既観測盤面.add(self.board)
        self.policy._座標試行[self.board] = {(0, 0)}
        self.policy._回数.update({1: 3, 2: 4})
        self.policy._報酬合計.update({1: 2.0, 2: 1.5})
        self.policy._総作用数 = 7
        self.policy._色回数.update({1: 2, 2: 3})
        self.policy._色報酬合計.update({1: 0.5, 2: -1.0})

    def tearDown(self):
        ablation._ACTIVE_CLEAR_COUNTER = self.previous_counter

    def test_game_over_reset_clears_only_ucb_statistics_before_next_action(self):
        reset = self.policy.選ぶ(_observation(self.board, state="GAME_OVER", actions=frozenset()))
        self.assertEqual(reset.作用番号, 0)
        self.assertEqual(self.policy._回数, {1: 3, 2: 4})

        choice = self.policy.選ぶ(_observation(self.board))

        self.assertIn(choice.作用番号, (1, 2))
        self.assertEqual(self.policy._回数, {})
        self.assertEqual(self.policy._報酬合計, {})
        self.assertEqual(self.policy._総作用数, 0)
        self.assertEqual(self.policy._色回数, {})
        self.assertEqual(self.policy._色報酬合計, {})
        self.assertIn(self.board, self.policy._既観測盤面)
        self.assertEqual(self.policy._座標試行[self.board], {(0, 0)})
        self.assertEqual(ablation._ACTIVE_CLEAR_COUNTER, [1])

    def test_non_reset_observation_does_not_clear_statistics(self):
        choice = self.policy.選ぶ(_observation(self.board))

        self.assertIn(choice.作用番号, (1, 2))
        self.assertEqual(self.policy._回数, {1: 3, 2: 4})
        self.assertEqual(self.policy._報酬合計, {1: 2.0, 2: 1.5})
        self.assertEqual(self.policy._総作用数, 7)
        self.assertEqual(ablation._ACTIVE_CLEAR_COUNTER, [0])

    def test_initial_reset_does_not_arm_game_over_clear(self):
        action = self.policy.選ぶ(_observation(self.board, state="NOT_PLAYED", actions=frozenset()))
        self.assertEqual(action.作用番号, 0)

        choice = self.policy.選ぶ(_observation(self.board))

        self.assertIn(choice.作用番号, (1, 2))
        self.assertEqual(self.policy._回数, {1: 3, 2: 4})
        self.assertEqual(ablation._ACTIVE_CLEAR_COUNTER, [0])

    def test_aggregate_records_reset_clear_count(self):
        aggregate = ablation._empty_aggregate()
        ablation._add_result(
            aggregate,
            {
                "actions": 1,
                "levels_completed": 0,
                "final_state": "NOT_FINISHED",
                "no_op_actions": 0,
                "game_over_events": 0,
                "reset_actions": 1,
                "reset_stat_clears": 1,
                "illegal_action_attempts": 0,
                "duplicate_observation_steps": 0,
                "stop_reason": "action_limit",
                "action_responses": [{}],
            },
        )

        self.assertEqual(aggregate["reset_stat_clears"], 1)


if __name__ == "__main__":
    unittest.main()
