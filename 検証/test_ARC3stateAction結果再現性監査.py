from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3stateAction結果再現性監査 as audit


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


class StateActionOutcomeAuditTests(unittest.TestCase):
    def setUp(self):
        self.previous_audit = audit._ACTIVE_AUDIT
        audit._ACTIVE_AUDIT = audit._AuditCounters()
        self.policy = audit._結果再現性監査方針(乱数種=1)

    def tearDown(self):
        audit._ACTIVE_AUDIT = self.previous_audit

    def _record_first_noop(self):
        before = _observation(actions=frozenset({1}))
        action = self.policy.選ぶ(before)
        self.assertEqual(action.作用番号, 1)
        self.policy.応答を記録する(before, action, _observation(actions=frozenset({1})))

    def _choose_repeated_pair(self):
        self.policy._回数[1] = 1
        self.policy._報酬合計[1] = 0.0
        self.policy._回数[2] = 1
        self.policy._報酬合計[2] = 0.0
        self.policy._総作用数 = 2
        self.policy._rng = _FirstChoice()
        before = _observation()
        action = self.policy.選ぶ(before)
        self.assertEqual(action.作用番号, 1)
        return before, action

    def test_repeated_state_action_outcome_category_match_is_counted(self):
        self._record_first_noop()
        before, action = self._choose_repeated_pair()

        self.policy.応答を記録する(before, action, _observation())

        self.assertEqual(audit._ACTIVE_AUDIT.repeated_state_action_selections, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_state_action_with_legal_alternative, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_match, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_mismatch, 0)

    def test_repeated_state_action_outcome_category_change_is_counted(self):
        self._record_first_noop()
        before, action = self._choose_repeated_pair()

        self.policy.応答を記録する(
            before,
            action,
            _observation(board=((1, 2), (2, 2))),
        )

        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_match, 0)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_mismatch, 1)

    def test_action6_is_excluded_from_discrete_pair_memory(self):
        before = _observation(actions=frozenset({6}))
        first = self.policy.選ぶ(before)
        self.assertEqual(first.作用番号, 6)
        self.policy.応答を記録する(before, first, _observation())

        self.assertEqual(audit._ACTIVE_AUDIT.discrete_action_responses, 0)
        self.assertEqual(self.policy._結果_by_state[before.最新盤面], {})


if __name__ == "__main__":
    unittest.main()
