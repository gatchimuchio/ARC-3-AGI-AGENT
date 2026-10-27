from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3stateAction再訪監査 as audit
from 接続.観測駆動探索Action import 観測駆動探索方針


class _FirstChoice:
    @staticmethod
    def choice(values):
        return values[0]


def _observation(board=((1, 2), (2, 1)), actions=frozenset({1, 2}), state="NOT_FINISHED"):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=0,
    )


class StateActionRevisitAuditTests(unittest.TestCase):
    def setUp(self):
        self.previous_audit = audit._ACTIVE_AUDIT
        audit._ACTIVE_AUDIT = audit._AuditCounters()
        self.policy = audit._状態再訪監査方針(乱数種=1)

    def tearDown(self):
        audit._ACTIVE_AUDIT = self.previous_audit

    def test_records_known_noop_revisit_and_available_alternative(self):
        before = _observation(actions=frozenset({1}))
        action = self.policy.選ぶ(before)
        self.assertEqual(action.作用番号, 1)
        after = _observation(actions=frozenset({1}))
        receipt = self.policy.応答を記録する(before, action, after)
        self.assertEqual(receipt["可視変化セル数"], 0)

        revisited = _observation(actions=frozenset({1, 2}))
        choice = self.policy.選ぶ(revisited)

        self.assertEqual(choice.作用番号, 2)
        self.assertEqual(audit._ACTIVE_AUDIT.board_revisits, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.known_noop_with_legal_alternative, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.selected_known_noop_with_legal_alternative, 0)

    def test_counts_selected_known_noop_when_alternative_is_legal(self):
        before = _observation(actions=frozenset({1}))
        action = self.policy.選ぶ(before)
        self.policy.応答を記録する(before, action, _observation(actions=frozenset({1})))
        self.policy._回数[1] = 1
        self.policy._報酬合計[1] = 0.0
        self.policy._回数[2] = 1
        self.policy._報酬合計[2] = 0.0
        self.policy._総作用数 = 2
        self.policy._rng = _FirstChoice()

        choice = self.policy.選ぶ(_observation(actions=frozenset({1, 2})))

        self.assertEqual(choice.作用番号, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.selected_known_noop, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.selected_known_noop_with_legal_alternative, 1)

    def test_tracks_board_and_noop_across_game_over_reset(self):
        board = ((1, 2), (2, 1))
        initial = _observation(board=board, actions=frozenset({1}))
        action = self.policy.選ぶ(initial)
        self.policy.応答を記録する(
            initial, action, _observation(board=board, actions=frozenset({1}))
        )
        self.policy.選ぶ(_observation(board=board, state="GAME_OVER"))

        choice = self.policy.選ぶ(_observation(board=board, actions=frozenset({1, 2})))

        self.assertEqual(choice.作用番号, 2)
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_decisions, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_same_initial_board, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.post_reset_known_noop_with_legal_alternative, 1)


if __name__ == "__main__":
    unittest.main()
