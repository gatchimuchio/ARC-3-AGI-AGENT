"""Small locality-encoder and causal teacher-order contracts."""

from collections import Counter
from types import SimpleNamespace
import unittest

import ARC3作用点効果HDS学習診断 as learning


def frame(changed=(), state="NOT_FINISHED", levels=0):
    rows = [[0] * 9 for _ in range(9)]
    for x, y in changed:
        rows[y][x] = 1
    return learning.replay.RecordedFrame(rows, state, levels)


class LearningContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = learning.replay.base._frozen_api()
        _, cls.api, _, _ = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_four_effect_categories_and_clipped_pre_target(self):
        action, before = self.api.PublicAction(6, 4, 4), frame()
        for local, remote in learning.EFFECT_BY_FLAGS:
            points = ([(4, 4)] if local else []) + ([(0, 0)] if remote else [])
            self.assertEqual(learning._effect(before, action, frame(points)), learning.EFFECT_BY_FLAGS[(local, remote)])
        corner = self.api.PublicAction(6, 0, 0)
        self.assertEqual(learning._effect(before, corner, frame([(3, 3)])), learning.EFFECT_BY_FLAGS[(True, False)])
        self.assertEqual(learning._effect(before, corner, frame([(4, 4)])), learning.EFFECT_BY_FLAGS[(False, True)])

    def test_teacher_preserves_progress_failure_and_omits_nonmouse_target(self):
        before = frame()
        mouse = self.api.PublicAction(6, 4, 4)
        progress = learning._teacher(before, mouse, frame([(4, 4)], levels=1), self.api)
        failure = learning._teacher(before, mouse, frame(state="GAME_OVER"), self.api)
        self.assertEqual(progress["公開応答区分"], "レベル進行")
        self.assertEqual(failure["公開応答区分"], "GAME_OVER")
        self.assertIn(learning.TARGET, failure)
        other = learning._teacher(before, self.api.PublicAction(1), frame([(4, 4)]), self.api)
        self.assertNotIn(learning.TARGET, other)
        self.assertNotIn("作用可能数", progress["作用前公開状態"])
        query = learning.replay._reduced_content(before, mouse, self.api)
        self.assertNotIn(learning.TARGET, query)
        self.assertNotIn("公開応答区分", query)

    def test_two_queries_and_both_scores_precede_single_B_teacher(self):
        events = []
        previous_effect = learning.EFFECT_BY_FLAGS[(True, True)]

        class FakeArm:
            def __init__(self, name, learned):
                self.name, self.learned, self.last_input_hash = name, learned, "same-before-input"

            def query(self, before, action):
                events.append(self.name + "_query")
                return {"native_status": "断定保留", "native_hold_reasons": [], "target_counts": {},
                        "forecast_values": {self.learned} if self.learned else set(),
                        "forecast_blocked": None if self.learned else "no_rule"}

            def update(self, before, action, after):
                events.append(self.name + "_teacher")
                self.learned = learning._effect(before, action, after)

        a, b = FakeArm("A", None), FakeArm("B", previous_effect)
        previous, scores, counts = Counter({previous_effect: 1}), learning.Scores(), Counter()
        learning._step(a, b, frame(), self.api.PublicAction(6, 4, 4), frame([(0, 0)]), previous, scores, counts, lambda: None)
        self.assertEqual(events, ["A_query", "B_query", "B_teacher"])
        self.assertIsNone(a.learned)
        self.assertEqual(scores.total["B"]["matches"], 0)
        self.assertEqual(scores.total["B"]["previous_majority_matches"], 0)
        self.assertEqual(sum(previous.values()), 2)
        self.assertEqual(previous[learning.EFFECT_BY_FLAGS[(False, True)]], 1)
        report = scores.report()
        self.assertIsNone(report["A"]["overall"]["precision"])
        self.assertEqual(report["A"]["overall"]["precision_status"], "UNMEASURED")
        self.assertEqual(counts["B_shared_public_updates"], 1)


if __name__ == "__main__":
    unittest.main()
