"""Focused full-schema projection and live response-order contracts."""

from collections import Counter
import hashlib
from types import SimpleNamespace
import unittest

import ARC3作用点面積25公開環境比較 as live


class FullSchemaOrderContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = live.replay.base._frozen_api()
        _, cls.api, _, _ = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def frames(self):
        board = tuple((0,) * 9 for _ in range(9))
        after = [list(row) for row in board]
        after[0][0] = 1
        return self.api.PublicFrame(board, "NOT_FINISHED", 0, (1, 6)), self.api.PublicFrame(after, "NOT_FINISHED", 0, (1, 6))

    def test_full_teacher_uses_actual_available_actions_and_only_PRE_area(self):
        before, after = self.frames()
        action = self.api.PublicAction(6, 4, 4)
        contents = {}
        for label, enriched in (("previous", False), ("current", True)):
            arm = live.FullSchemaArm.__new__(live.FullSchemaArm)
            arm.api, arm.enriched = self.api, enriched

            def call(kind, content, owner=arm):
                self.assertEqual(kind, "update")
                owner.last_teacher_hash = live.replay.paired._digest(content)
                return {"bridge_status": "updated"}

            arm.core = SimpleNamespace(_call=call)
            arm.update(before, action, after)
            contents[label] = arm.teacher_content
            self.assertEqual(arm.teacher_content["作用前公開状態"]["作用可能数"], 2)
            self.assertEqual(arm.teacher_content[live.learning.TARGET], live.learning.EFFECT_BY_FLAGS[(False, True)])
        self.assertEqual(contents["current"]["作用前公開状態"][live.comparison.AREA], 81)
        self.assertEqual(live.comparison._without_area(contents["current"]), contents["previous"])

    def test_queries_before_SDK_response_then_scores_and_both_teachers(self):
        before, after = self.frames()
        action, events, api = self.api.PublicAction(6, 4, 4), [], self.api
        past_effect = live.learning.EFFECT_BY_FLAGS[(True, True)]

        class FakeArm:
            def __init__(self, label, enriched):
                self.label, self.enriched = label, enriched

            def query(self, observed, candidate):
                self.query_content = live.comparison._augment(api._query_content(observed, candidate), observed, candidate, self.enriched)
                self.last_input_hash = live.replay.paired._digest(self.query_content)
                events.append(self.label + "_query")
                return {"native_status": "断定保留", "native_hold_reasons": [], "target_counts": {},
                        "forecast_values": {past_effect}, "forecast_blocked": None}

            def update(self, observed, candidate, response):
                events.append(self.label + "_teacher")
                self.teacher_content = live.learning._teacher(observed, candidate, response, api)
                self.teacher_content["作用前公開状態"] = api._public_context(observed, candidate)
                live.comparison._augment(self.teacher_content, observed, candidate, self.enriched)
                self.last_teacher_hash = live.replay.paired._digest(self.teacher_content)

        previous, current = FakeArm("previous", False), FakeArm("current", True)
        scores, paired, aliases = live.learning.Scores(), live.comparison.PairedPrediction(), live.comparison.Aliases()
        counts, past = Counter(), Counter({past_effect: 1})
        digests = {label: hashlib.sha256() for label in ("previous", "current")}
        pending = live._query_pair(previous, current, before, action, lambda: None, counts)
        events.append("actual_SDK_step_returns_response")
        live._finish_response(previous, current, before, action, after, pending, past, scores, paired, aliases, counts, digests, lambda: None)
        self.assertEqual(events, ["previous_query", "current_query", "actual_SDK_step_returns_response", "previous_teacher", "current_teacher"])
        self.assertEqual(scores.total["A"]["matches"], 0)
        self.assertEqual(scores.total["B"]["matches"], 0)
        self.assertEqual(sum(past.values()), 2)
        self.assertEqual(digests["previous"].hexdigest(), digests["current"].hexdigest())


if __name__ == "__main__":
    unittest.main()
