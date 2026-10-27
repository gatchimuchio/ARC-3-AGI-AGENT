from __future__ import annotations

from types import SimpleNamespace
import unittest

from 検証.ARC3既観測盤面循環応答penaltyablation import _既観測盤面循環応答罰方針


def _observation(board, *, levels=0, state="NOT_FINISHED", actions=frozenset({1})):
    return SimpleNamespace(
        状態=state,
        最新盤面=board,
        作用可能番号=actions,
        完了レベル数=levels,
    )


class VisibleBoardCyclePenaltyTests(unittest.TestCase):
    def _transition(self, *, action_id=1, after_board=None, after_state="NOT_FINISHED", levels=0):
        policy = _既観測盤面循環応答罰方針(乱数種=1)
        before_board = ((1, 2), (2, 1))
        after_board = after_board or ((1, 2), (2, 2))
        if action_id == 6:
            before = _observation(before_board, actions=frozenset({6}))
        else:
            before = _observation(before_board, actions=frozenset({action_id}))
        action = policy.選ぶ(before)
        policy._既観測盤面.add(after_board)
        after = _observation(after_board, levels=levels, state=after_state)
        receipt = policy.応答を記録する(before, action, after)
        return policy, action, receipt

    def test_seen_visible_nonterminal_board_gets_exact_additional_penalty(self):
        policy, action, receipt = self._transition()

        self.assertFalse(receipt["盤面新規性"])
        self.assertAlmostEqual(receipt["公開応答報酬"], -0.9375)
        self.assertAlmostEqual(policy._報酬合計[action.作用番号], -0.9375)

    def test_novel_board_has_no_additional_penalty(self):
        policy = _既観測盤面循環応答罰方針(乱数種=1)
        before = _observation(((1, 2), (2, 1)), actions=frozenset({1}))
        action = policy.選ぶ(before)
        receipt = policy.応答を記録する(
            before, action, _observation(((3, 2), (2, 2)), actions=frozenset({1}))
        )

        self.assertTrue(receipt["盤面新規性"])
        self.assertGreaterEqual(receipt["公開応答報酬"], 0.0)

    def test_action6_updates_selected_color_reward_as_well(self):
        policy, action, receipt = self._transition(action_id=6)
        color = receipt["座標可視色"]

        self.assertIsNotNone(color)
        self.assertAlmostEqual(policy._報酬合計[6], -0.9375)
        self.assertAlmostEqual(policy._色報酬合計[color], -0.9375)

    def test_level_progress_terminal_and_noop_are_excluded(self):
        policy, _, progressed = self._transition(levels=1)
        self.assertGreaterEqual(progressed["公開応答報酬"], 4.0)

        policy, _, terminal = self._transition(after_state="GAME_OVER")
        self.assertNotEqual(terminal["公開応答報酬"], -1.0)

        policy = _既観測盤面循環応答罰方針(乱数種=1)
        board = ((1, 2), (2, 1))
        before = _observation(board, actions=frozenset({1}))
        action = policy.選ぶ(before)
        noop = policy.応答を記録する(before, action, _observation(board))
        self.assertEqual(noop["公開応答報酬"], -1.0)
        self.assertEqual(policy._報酬合計[1], -1.0)


if __name__ == "__main__":
    unittest.main()
