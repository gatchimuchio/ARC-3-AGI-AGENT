from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3RESET後ActionUCB持越し監査 as audit
from 接続.観測駆動探索Action import 観測駆動探索方針


def _observation(board, *, state="NOT_FINISHED", levels=0, actions=frozenset({1, 2})):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=levels,
    )


class PostResetActionUcbAuditTests(unittest.TestCase):
    def setUp(self):
        self.previous_audit = audit._ACTIVE_AUDIT
        audit._ACTIVE_AUDIT = audit._AuditCounters()
        self.policy = audit._RESET後Action統計監査方針(乱数種=19)
        self.board = ((1, 2), (2, 1))
        self.policy._initial_public_condition = (
            "NOT_FINISHED",
            0,
            (1, 2),
            self.board,
        )
        self.policy._既観測盤面.add(self.board)
        self.policy._回数.update({1: 2, 2: 2})
        self.policy._報酬合計.update({1: 2.0, 2: 1.0})
        self.policy._総作用数 = 4

    def tearDown(self):
        audit._ACTIVE_AUDIT = self.previous_audit

    def test_reset_decision_is_audited_without_clearing_live_statistics(self):
        action_before_reset = dict(self.policy._回数)
        reset = self.policy.選ぶ(_observation(self.board, state="GAME_OVER", actions=frozenset()))
        choice = self.policy.選ぶ(_observation(self.board))

        self.assertEqual(reset.作用番号, 0)
        self.assertIn(choice.作用番号, (1, 2))
        self.assertEqual(self.policy._回数, action_before_reset)
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_decisions, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.same_as_initial_public_condition, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_board_previously_seen, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.legal_actions_with_prior_statistics, 2)
        self.assertEqual(audit._ACTIVE_AUDIT.decisions_all_legal_actions_previously_sampled, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.shadow_comparisons, 1)

    def test_shadow_does_not_change_live_policy_rng_or_action_choice(self):
        baseline = 観測駆動探索方針(乱数種=19)
        baseline._既観測盤面.add(self.board)
        baseline._回数.update({1: 2, 2: 2})
        baseline._報酬合計.update({1: 2.0, 2: 1.0})
        baseline._総作用数 = 4
        expected = baseline.選ぶ(_observation(self.board))

        self.policy.選ぶ(_observation(self.board, state="GAME_OVER", actions=frozenset()))
        actual = self.policy.選ぶ(_observation(self.board))

        self.assertEqual(actual, expected)

    def test_no_reset_context_uses_base_policy_without_shadow_comparison(self):
        choice = self.policy.選ぶ(_observation(self.board))

        self.assertIn(choice.作用番号, (1, 2))
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_decisions, 0)
        self.assertEqual(audit._ACTIVE_AUDIT.shadow_comparisons, 0)


if __name__ == "__main__":
    unittest.main()
