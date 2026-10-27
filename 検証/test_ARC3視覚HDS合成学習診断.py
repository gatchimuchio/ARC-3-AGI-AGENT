"""C2-078実HDS出力の部分予測とglobal HOLDを混同しない回帰fixture。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))

from ARC3視覚HDS接続候補 import _native_summary, render_hint


class SyntheticLearningProbeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = json.loads(
            (ROOT / "運用/証拠/ARC26-UNIFIED/C2-078_synthetic-learning-probe.json").read_text(
                encoding="utf-8"
            )
        )

    def test_supported_target_predictions_are_visible_while_global_hold_remains(self):
        expected_values = {1: "盤面変化", 2: "可視変化なし"}
        for query in self.probe["queries"]:
            with self.subTest(action=query["action_number"]):
                native = query["native_output"]
                summary = _native_summary(SimpleNamespace(状態=native["状態"], 内容=native["内容"]))
                self.assertEqual(summary["native_status"], "断定保留")
                self.assertEqual(summary["relevant_conflict_count"], 0)
                self.assertEqual(summary["relevant_observation_request_count"], 0)
                self.assertEqual(summary["relevant_prediction_count"], 1)
                prediction = summary["predictions"][0]
                self.assertEqual(prediction["value"], expected_values[query["action_number"]])
                supported_refs = {
                    rule["principle_ref"]
                    for rule in summary["rule_evidence"]
                    if rule["native_state"] == "適用範囲付き暫定原理"
                    and rule["native_adoption_state"] == "有効"
                }
                self.assertIn(prediction["principle_ref"], supported_refs)
                display = {"bridge_status": "queried", "authorization": False, **summary}
                self.assertEqual(render_hint(display), "")
                self.assertFalse(query["bridge_result"]["authorization"])

    def test_global_hold_paths_are_retained_and_do_not_concern_target_outcome(self):
        for query in self.probe["queries"]:
            content = query["native_output"]["内容"]
            affected = {
                tuple(row["結果経路"])
                for key in ("係争中原理群", "識別不能群")
                for row in content[key]
            }
            self.assertTrue(affected)
            self.assertNotIn(("公開応答区分",), affected)
            self.assertEqual(
                content["断定保留理由群"],
                [
                    "原因未確定で隔離中の原理が存在する",
                    "現観測だけでは複数の関係候補を識別できない",
                ],
            )


if __name__ == "__main__":
    unittest.main()
