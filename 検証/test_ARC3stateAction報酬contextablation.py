from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証.ARC3stateAction報酬contextablation import _同盤Action報酬文脈方針
from 接続.観測駆動探索Action import 観測駆動探索方針


def _observation(board=((1, 2), (2, 1)), actions=frozenset({1, 2}), state="NOT_FINISHED"):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=0,
    )


class SameBoardActionRewardContextTests(unittest.TestCase):
    def test_unseen_board_matches_base_policy(self):
        current = _observation()
        baseline = 観測駆動探索方針(乱数種=13)
        candidate = _同盤Action報酬文脈方針(乱数種=13)

        self.assertEqual(candidate.選ぶ(current), baseline.選ぶ(current))

    def test_same_board_reward_changes_only_temporary_global_mean(self):
        board = ((1, 2), (2, 1))
        policy = _同盤Action報酬文脈方針(乱数種=1)
        policy._回数.update({1: 2, 2: 2})
        policy._報酬合計.update({1: 0.0, 2: 0.0})
        policy._総作用数 = 4
        policy._盤面Action報酬[board] = {2: (1, 2.0)}
        original_global_rewards = policy._報酬合計.copy()

        choice = policy.選ぶ(_observation(board=board))

        self.assertEqual(choice.作用番号, 2)
        self.assertEqual(policy._報酬合計, original_global_rewards)

    def test_other_board_uses_unmodified_global_choice(self):
        policy = _同盤Action報酬文脈方針(乱数種=4)
        policy._回数.update({1: 2, 2: 2})
        policy._報酬合計.update({1: 0.5, 2: 0.0})
        policy._総作用数 = 4
        policy._盤面Action報酬[((1, 2), (2, 1))] = {2: (1, 10.0)}
        expected = 観測駆動探索方針(乱数種=4)
        expected._回数.update({1: 2, 2: 2})
        expected._報酬合計.update({1: 0.5, 2: 0.0})
        expected._総作用数 = 4
        other_board = ((3, 3), (2, 1))

        self.assertEqual(
            policy.選ぶ(_observation(board=other_board)),
            expected.選ぶ(_observation(board=other_board)),
        )

    def test_observed_reward_is_recorded_only_for_discrete_state_action(self):
        policy = _同盤Action報酬文脈方針(乱数種=2)
        before = _observation(actions=frozenset({1}))
        action = policy.選ぶ(before)
        receipt = policy.応答を記録する(before, action, _observation(actions=frozenset({1})))

        self.assertEqual(policy._盤面Action報酬[before.最新盤面][1], (1, receipt["公開応答報酬"]))

    def test_action6_is_not_added_to_discrete_state_action_memory(self):
        policy = _同盤Action報酬文脈方針(乱数種=2)
        before = _observation(actions=frozenset({6}))
        action = policy.選ぶ(before)
        policy.応答を記録する(before, action, _observation())

        self.assertNotIn(before.最新盤面, policy._盤面Action報酬)


if __name__ == "__main__":
    unittest.main()
