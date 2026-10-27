from __future__ import annotations

import math
import pathlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3視覚HDS接続候補 import PublicAction, PublicFrame, VisualHDSBridge, render_hint


def _frame(board=((0, 1), (2, 1)), state="NOT_FINISHED", levels=0, actions=(1, 6)):
    return PublicFrame(board, state, levels, actions)


def _bridge(updates=2, queries=2, seconds=10.0):
    return VisualHDSBridge(update_budget=updates, query_budget=queries, hds_seconds_budget=seconds)


class VisualHDSBridgeTests(unittest.TestCase):
    def test_frame_accepts_only_public_fields_and_copies_mutable_inputs(self):
        rows = [[0, 1], [2, 1]]
        frame = PublicFrame(rows, "NOT_FINISHED", 0, [1, 6])
        rows[0][0] = 9
        self.assertEqual(frame.board, ((0, 1), (2, 1)))
        with self.assertRaises(TypeError):
            PublicFrame(((0,),), "NOT_FINISHED", 0, (1,), game_id="not-a-frame-field")
        with self.assertRaises(ValueError):
            _frame(board=((True,),))
        with self.assertRaises(ValueError):
            _frame(actions=(1, 1))

    def test_actual_hds_update_and_query_keep_native_memory_without_authority(self):
        bridge = _bridge()
        before = _frame()
        action = PublicAction(6, 1, 1)
        updated = bridge.update(before, action, _frame(board=((0, 2), (2, 1))))
        self.assertEqual(updated["bridge_status"], "updated")
        self.assertIn(updated["native_status"], {"出力", "断定保留"})
        observations = bridge._hds.エンジン.台帳.取得("観測台帳")
        self.assertEqual(len(observations), 6)
        self.assertEqual(bridge.prior_report["loaded_count"], 5)
        self.assertEqual(bridge.stats["prior_updates_succeeded"], 5)
        content = observations[-1].原入力
        self.assertEqual(set(content), {"作用前公開状態", "作用", "公開応答区分"})
        self.assertIn("対象局所配置", content["作用前公開状態"])
        self.assertEqual(content["公開応答区分"], "盤面変化")
        queried = bridge.query(before, action)
        self.assertEqual(queried["bridge_status"], "queried")
        self.assertEqual(len(bridge._hds.エンジン.台帳.取得("観測台帳")), 6)
        for result in (updated, queried):
            self.assertFalse(result["authorization"])
            self.assertTrue(result["continue_visual_solver"])
        self.assertEqual(bridge.stats["updates_succeeded"], 1)
        self.assertEqual(bridge.stats["queries_succeeded"], 1)

    def test_game_over_is_not_taught_as_a_board_change(self):
        bridge = _bridge()
        output = SimpleNamespace(状態="断定保留", 内容={})
        with patch.object(bridge._hds, "処理する", return_value=output) as update:
            bridge.update(
                _frame(), PublicAction(6, 1, 1), _frame(board=((9, 9), (9, 9)), state="GAME_OVER")
            )
        self.assertEqual(update.call_args.args[0].内容["公開応答区分"], "GAME_OVER")

    def test_public_lifecycle_outcomes_have_explicit_precedence(self):
        bridge = _bridge(updates=4)
        output = SimpleNamespace(状態="断定保留", 内容={})
        after_frames = (
            _frame(state="WIN", levels=1),
            _frame(state="GAME_OVER", levels=1),
            _frame(levels=1),
            _frame(),
        )
        with patch.object(bridge._hds, "処理する", return_value=output) as update:
            for after in after_frames:
                bridge.update(_frame(), PublicAction(1), after)
        self.assertEqual(
            [call.args[0].内容["公開応答区分"] for call in update.call_args_list],
            ["勝利", "GAME_OVER", "レベル進行", "可視変化なし"],
        )

    def test_reset_is_a_boundary_and_never_a_learning_update(self):
        bridge = _bridge(updates=0)
        with patch.object(bridge._hds, "処理する") as update:
            result = bridge.update(_frame(state="GAME_OVER"), PublicAction(0), _frame())
        update.assert_not_called()
        self.assertEqual(result["bridge_status"], "skipped_reset")
        self.assertEqual(result["stats"]["skipped_resets"], 1)
        self.assertEqual(result["stats"]["updates_attempted"], 0)
        self.assertEqual(
            bridge.update(_frame(), PublicAction(0), _frame())["bridge_status"], "rejected"
        )

    def test_illegal_actions_and_outside_target_do_not_reach_hds(self):
        bridge = _bridge()
        with patch.object(bridge._hds, "処理する") as update:
            rejected = bridge.update(_frame(), PublicAction(2), _frame())
            outside = bridge.update(_frame(), PublicAction(6, 63, 63), _frame())
        update.assert_not_called()
        self.assertEqual(rejected["bridge_status"], "rejected")
        self.assertEqual(outside["bridge_status"], "rejected")
        self.assertEqual(bridge.stats["updates_attempted"], 0)
        self.assertEqual(
            bridge.query(_frame(state="WIN"), PublicAction(1))["bridge_status"], "rejected"
        )

    def test_exhausted_count_or_time_budget_keeps_visual_solver_running(self):
        for bridge in (_bridge(updates=0, queries=0), _bridge(seconds=0.0)):
            with self.subTest(bridge=bridge):
                with (
                    patch.object(bridge._hds, "処理する") as update,
                    patch.object(bridge._hds, "照会する") as query,
                ):
                    results = (
                        bridge.update(_frame(), PublicAction(1), _frame()),
                        bridge.query(_frame(), PublicAction(1)),
                    )
                update.assert_not_called()
                query.assert_not_called()
                for result in results:
                    self.assertEqual(result["bridge_status"], "budget_exhausted")
                    self.assertTrue(result["continue_visual_solver"])
                    self.assertFalse(result["authorization"])

    def test_hds_error_is_visible_and_consumes_attempt_budget_without_retry(self):
        bridge = _bridge(updates=1)
        with patch.object(bridge._hds, "処理する", side_effect=RuntimeError("synthetic failure")):
            failed = bridge.update(_frame(), PublicAction(1), _frame())
        self.assertEqual(failed["bridge_status"], "hds_error")
        self.assertEqual(failed["error_type"], "RuntimeError")
        self.assertTrue(failed["continue_visual_solver"])
        self.assertEqual(bridge.stats["update_errors"], 1)
        self.assertEqual(bridge.stats["updates_attempted"], 1)
        self.assertEqual(bridge.stats["updates_succeeded"], 0)
        self.assertEqual(
            bridge.update(_frame(), PublicAction(1), _frame())["bridge_status"], "budget_exhausted"
        )

    def test_time_budget_stops_later_hds_calls_after_one_inflight_overrun(self):
        bridge = _bridge(seconds=1.0)
        output = SimpleNamespace(状態="断定保留", 内容={})
        with (
            patch.object(bridge._hds, "処理する", return_value=output),
            patch("ARC3視覚HDS接続候補.time.perf_counter", side_effect=(10.0, 12.0)),
        ):
            first = bridge.update(_frame(), PublicAction(1), _frame())
        self.assertEqual(first["bridge_status"], "updated")
        self.assertEqual(first["stats"]["update_seconds"], 2.0)
        self.assertGreaterEqual(first["stats"]["total_hds_seconds"], 2.0)
        self.assertTrue(first["stats"]["time_budget_exhausted"])
        with patch.object(bridge._hds, "照会する") as query:
            second = bridge.query(_frame(), PublicAction(1))
        query.assert_not_called()
        self.assertEqual(second["blocked_by"], ["total_hds_seconds"])
        self.assertTrue(second["continue_visual_solver"])

    def test_query_returns_only_bounded_relevant_native_judgments(self):
        bridge = _bridge()
        relevant = {"結果経路": ["公開応答区分"], "予測値": "盤面変化", "原理参照": "native-rule"}
        rule = {
            "結果経路": ["公開応答区分"],
            "原理識別子": "native-rule",
            "版": 1,
            "状態": "適用範囲付き暫定原理",
            "採用状態": "有効",
            "関係型": "決定的対応関係",
            "条件経路群": [["作用", "番号"]],
            "適用範囲": {"条件数": 1, "条件種類数": 2, "確認範囲": "観測済み条件値"},
        }
        output = SimpleNamespace(
            状態="断定保留",
            内容={
                "予測群": [relevant] * 8 + [{"結果経路": ["unrelated"], "予測値": "ignored"}],
                "有効原理群": [rule] * 8,
                "断定保留理由群": ["native uncertainty"],
            },
        )
        with patch.object(bridge._hds, "照会する", return_value=output):
            result = bridge.query(_frame(), PublicAction(1))
        self.assertEqual(result["native_status"], "断定保留")
        self.assertEqual(result["relevant_prediction_count"], 8)
        self.assertEqual(len(result["predictions"]), 4)
        self.assertEqual(len(result["rule_evidence"]), 4)
        self.assertTrue(result["summary_is_truncated"])
        self.assertFalse(result["authorization"])
        self.assertEqual(render_hint(result), "")
        result["native_status"] = "出力"
        self.assertIn("native-rule", render_hint(result))
        self.assertEqual(render_hint(result, max_chars=10), "")
        result["predictions"] = []
        self.assertEqual(render_hint(result), "")

    def test_pilot_requires_explicit_finite_budgets(self):
        for invalid in (None, math.inf, -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                VisualHDSBridge(update_budget=invalid, query_budget=1, hds_seconds_budget=1.0)
        for invalid in (None, math.inf, math.nan, -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                VisualHDSBridge(update_budget=1, query_budget=1, hds_seconds_budget=invalid)


if __name__ == "__main__":
    unittest.main()
