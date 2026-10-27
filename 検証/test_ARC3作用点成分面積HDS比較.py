"""Small component-area and paired temporal/fallback contracts."""

from collections import Counter
import hashlib
import unittest

import ARC3作用点成分面積HDS比較 as comparison


def frame(points=(), size=9):
    board = [[0] * size for _ in range(size)]
    for x, y in points:
        board[y][x] = 1
    return comparison.replay.RecordedFrame(board, "NOT_FINISHED", 0)


class ComponentOrderContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = comparison.replay.base._frozen_api()
        _, cls.api, _, _ = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_exact_four_connected_area_and_color_permutation(self):
        before = frame([(1, 1), (2, 1), (2, 2), (3, 3)], 4)
        self.assertEqual(comparison._area(before, self.api.PublicAction(6, 1, 1)), 3)
        self.assertEqual(comparison._area(before, self.api.PublicAction(6, 3, 3)), 1)
        permuted = comparison.replay.RecordedFrame(tuple(tuple(7 if cell == 0 else 2 for cell in row) for row in before.board), "NOT_FINISHED", 0)
        self.assertEqual(comparison._area(permuted, self.api.PublicAction(6, 1, 1)), 3)

    def test_only_pre_area_added_and_nonmouse_omitted(self):
        before, after = frame([(4, 4)]), frame([(4, 4), (5, 4)])
        action = self.api.PublicAction(6, 4, 4)
        previous = comparison.learning._teacher(before, action, after, self.api)
        current = comparison._augment(comparison.learning._teacher(before, action, after, self.api), before, action, True)
        self.assertEqual(current["作用前公開状態"][comparison.AREA], 1)
        self.assertEqual(comparison._without_area(current), previous)
        other = self.api.PublicAction(1)
        content = comparison._augment(comparison.learning._teacher(before, other, after, self.api), before, other, True)
        self.assertNotIn(comparison.AREA, content["作用前公開状態"])
        self.assertNotIn(comparison.learning.TARGET, content)

    def test_queries_scores_then_two_teachers_and_fixed_fallback(self):
        events, api = [], self.api
        both = comparison.learning.EFFECT_BY_FLAGS[(True, True)]
        remote = comparison.learning.EFFECT_BY_FLAGS[(False, True)]

        def result(value):
            return {"native_status": "断定保留", "native_hold_reasons": [], "target_counts": {},
                    "forecast_values": {value} if value else set(), "forecast_blocked": None if value else "no_rule"}

        class FakeArm:
            def __init__(self, label, enriched, forecast):
                self.label, self.enriched, self.forecast = label, enriched, forecast

            def query(self, before, action):
                events.append(self.label + "_query")
                self.query_content = comparison._augment(comparison.replay._reduced_content(before, action, api), before, action, self.enriched)
                self.last_input_hash = comparison.replay.paired._digest(self.query_content)
                return result(self.forecast)

            def update(self, before, action, after):
                events.append(self.label + "_teacher")
                self.teacher_content = comparison._augment(comparison.learning._teacher(before, action, after, api), before, action, self.enriched)
                self.last_teacher_hash = comparison.replay.paired._digest(self.teacher_content)

        previous, current = FakeArm("previous", False, both), FakeArm("current", True, remote)
        past, scores = Counter({both: 1}), comparison.learning.Scores()
        paired, aliases, counts = comparison.PairedPrediction(), comparison.Aliases(), Counter()
        digests = {label: hashlib.sha256() for label in ("previous", "current")}
        comparison._step(previous, current, frame(), self.api.PublicAction(6, 4, 4), frame([(0, 0)]), past, scores, paired, aliases, counts, digests, lambda: None)
        self.assertEqual(events, ["previous_query", "current_query", "previous_teacher", "current_teacher"])
        self.assertEqual(paired.report()["fixed_offline_all_point_fallback"]["current_minus_previous_correct"], 1)
        self.assertEqual(sum(past.values()), 2)
        self.assertEqual(digests["previous"].hexdigest(), digests["current"].hexdigest())
        no_prior = comparison.PairedPrediction()
        no_prior.record(result(both), result(remote), remote, Counter())
        report = no_prior.report()["fixed_offline_all_point_fallback"]
        self.assertEqual(report["both_abstain_no_prior_Action6_effect"], 1)
        self.assertNotIn("matched_scored_points", report)
        fallback = comparison.PairedPrediction()
        fallback.record(result(None), result(remote), remote, Counter({both: 1}))
        report = fallback.report()["fixed_offline_all_point_fallback"]
        self.assertEqual(report["previous_majority_fallback_used"], 1)
        self.assertEqual(report["current_minus_previous_correct"], 1)


if __name__ == "__main__":
    unittest.main()
