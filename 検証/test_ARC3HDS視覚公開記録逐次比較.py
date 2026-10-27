"""Focused parser/projection/causal-order contracts; no model/SDK execution."""

from collections import Counter
import copy
from types import SimpleNamespace
import unittest

import ARC3HDS視覚公開記録逐次比較 as replay


class ReplayContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = replay.base._frozen_api()
        cls.runtime, cls.api, _, _ = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def fixture(self):
        frame = {"board": [[0, 1], [1, 0]], "state": "NOT_FINISHED", "score": 0}
        rows = [{**frame, "type": "initial", "action_num": 0, "action_display": "RESET"}]
        history = []
        for index in range(80):
            name, data = ("RESET", {}) if index == 0 else ("ACTION6", {"x": 0, "y": 1}) if index == 1 else ("ACTION1", {})
            history.append({"action": {"id": name, "data": data}})
            rows.append({**frame, "type": "action", "action_num": index + 1, "action_name": name,
                         "action_display": "MOUSE(row=1, col=0)" if index == 1 else name})
            if index == 1:
                rows.append({"type": "analysis", "board": "not an action response"})
        return rows, history

    def test_parser_initial_analysis_and_coordinate_join(self):
        rows, history = self.fixture()
        transitions, analysis = replay._parse_events(rows, history, self.api)
        self.assertEqual((len(transitions), analysis), (80, 1))
        self.assertEqual(sum(action.number == 0 for _, action, _ in transitions), 1)
        self.assertEqual(transitions[1][1], self.api.PublicAction(6, 0, 1))
        changed = copy.deepcopy(rows)
        changed[2]["action_display"] = "MOUSE(row=0, col=1)"
        with self.assertRaisesRegex(replay.base.ContractError, "mouse_coordinate_join"):
            replay._parse_events(changed, history, self.api)
        changed = copy.deepcopy(rows)
        changed[2]["action_num"] = 1
        with self.assertRaisesRegex(replay.base.ContractError, "contiguous_recorded_action"):
            replay._parse_events(changed, history, self.api)

    def test_reduced_projection_omits_only_unrecorded_availability(self):
        board = ((0, 1), (1, 0))
        recorded = replay.RecordedFrame(board, "NOT_FINISHED", 0)
        known = self.api.PublicFrame(board, "NOT_FINISHED", 0, (1, 6))
        for action in (self.api.PublicAction(1), self.api.PublicAction(6, 0, 1)):
            expected = self.api._query_content(known, action)
            del expected["作用前公開状態"]["作用可能数"]
            actual = replay._reduced_content(recorded, action, self.api)
            self.assertEqual(actual, expected)
            self.assertNotIn("作用可能数", actual["作用前公開状態"])
            self.assertFalse(hasattr(recorded, "available_actions"))

    def test_status_class_metrics_use_previous_labels_before_single_update(self):
        result = {"bridge_status": "queried", "authorization": False, "native_status": "出力",
                  "relevant_conflict_count": 0, "relevant_observation_request_count": 0,
                  "summary_is_truncated": False,
                  "rule_evidence": [{"principle_ref": "synthetic-reference", "native_state": "適用範囲付き暫定原理", "native_adoption_state": "有効"}],
                  "predictions": [{"value": "可視変化なし", "principle_ref": "synthetic-reference"}]}
        collector, strata, counts = replay.paired._Collector(), replay.Strata(), Counter()
        collector.current = SimpleNamespace(pending={"whole": result, "scoped": result}, runtime=self.runtime, native_causes={})
        previous = Counter({"盤面変化": 1})
        replay._score_pair(collector, strata, previous, counts, "可視変化なし")
        self.assertEqual(previous, Counter({"盤面変化": 1, "可視変化なし": 1}))
        report = strata.report()
        for arm in ("whole", "scoped"):
            status = report[arm]["native_status"]["出力"]
            self.assertEqual(status["precision"], 1.0)
            self.assertEqual(status["same_covered_strict_past_majority_precision"], 0.0)
            self.assertEqual(report[arm]["predicted_class"]["可視変化なし"]["precision"], 1.0)
            self.assertIsNone(report[arm]["predicted_class"]["レベル進行"]["precision"])
        self.assertEqual(collector.pairs["identical_strictly_previous_majority_counter_steps"], 1)


if __name__ == "__main__":
    unittest.main()
