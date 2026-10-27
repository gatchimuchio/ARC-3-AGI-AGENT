from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3既観測盤面循環遷移監査 as audit


def _observation(board, *, levels=0, state="NOT_FINISHED", actions=frozenset({1})):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=levels,
    )


class VisibleBoardCycleAuditTests(unittest.TestCase):
    def setUp(self):
        self.previous_audit = audit._ACTIVE_AUDIT
        audit._ACTIVE_AUDIT = audit._AuditCounters()
        self.policy = audit._既観測盤面循環監査方針(乱数種=1)

    def tearDown(self):
        audit._ACTIVE_AUDIT = self.previous_audit

    def _run_transition(self, after, *, seen=False):
        before_board = ((1, 2), (2, 1))
        action_before = _observation(before_board)
        if seen:
            self.policy._既観測盤面.add(after.最新盤面)
        action = self.policy.選ぶ(action_before)
        return self.policy.応答を記録する(action_before, action, after)

    def test_visible_nonterminal_transition_to_seen_board_is_counted(self):
        previously_seen = ((1, 2), (2, 2))
        receipt = self._run_transition(_observation(previously_seen), seen=True)

        self.assertTrue(receipt["盤面新規性"] is False)
        self.assertEqual(audit._ACTIVE_AUDIT.visible_nonterminal_transitions, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.transitions_to_previously_seen_board, 1)

    def test_novel_board_is_not_counted_as_cycle(self):
        receipt = self._run_transition(_observation(((1, 2), (2, 2))))

        self.assertTrue(receipt["盤面新規性"])
        self.assertEqual(audit._ACTIVE_AUDIT.visible_nonterminal_transitions, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.transitions_to_previously_seen_board, 0)

    def test_noop_progress_and_terminal_are_excluded_from_cycle_count(self):
        same_board = ((1, 2), (2, 1))
        self._run_transition(_observation(same_board), seen=True)
        self._run_transition(_observation(((1, 2), (2, 2)), levels=1), seen=True)
        self._run_transition(
            _observation(((1, 2), (2, 2)), state="GAME_OVER"),
            seen=True,
        )

        self.assertEqual(audit._ACTIVE_AUDIT.visible_nonterminal_transitions, 0)
        self.assertEqual(audit._ACTIVE_AUDIT.transitions_to_previously_seen_board, 0)


if __name__ == "__main__":
    unittest.main()
