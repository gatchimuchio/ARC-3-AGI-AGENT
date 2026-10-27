from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証 import ARC3ACTION6色結果再現性監査 as audit


def _observation(board, *, actions=frozenset({6}), state="NOT_FINISHED", levels=0):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=levels,
    )


class Action6ColorOutcomeAuditTests(unittest.TestCase):
    def setUp(self):
        self.previous_audit = audit._ACTIVE_AUDIT
        audit._ACTIVE_AUDIT = audit._AuditCounters()
        self.policy = audit._ACTION6色結果監査方針(乱数種=3)
        self.board = ((1, 2), (1, 2))
        self.policy._色回数.update({1: 1, 2: 1})
        self.policy._色報酬合計.update({1: 100.0, 2: -100.0})

    def tearDown(self):
        audit._ACTIVE_AUDIT = self.previous_audit

    def _select_and_record(self, after_board):
        before = _observation(self.board)
        action = self.policy.選ぶ(before)
        after = _observation(after_board)
        receipt = self.policy.応答を記録する(before, action, after)
        return action, receipt

    def test_same_board_color_with_other_color_available_is_counted(self):
        first, _ = self._select_and_record(((3, 2), (1, 2)))
        second, _ = self._select_and_record(((3, 2), (3, 2)))

        self.assertEqual(first.作用番号, 6)
        self.assertEqual(second.作用番号, 6)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_board_color_selections, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_board_color_with_alternative_color, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_match, 1)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_mismatch, 0)

    def test_no_op_is_a_distinct_mismatching_result_category(self):
        self._select_and_record(((3, 2), (1, 2)))
        self._select_and_record(self.board)

        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_match, 0)
        self.assertEqual(audit._ACTIVE_AUDIT.repeated_outcome_category_mismatch, 1)

    def test_color_opportunity_uses_only_untried_coordinates(self):
        observed = audit._ACTION6色結果監査方針(乱数種=3)
        observed._座標試行[self.board] = {(0, 0), (0, 1)}

        self.assertEqual(observed._未試行色候補(self.board), (2,))


if __name__ == "__main__":
    unittest.main()
