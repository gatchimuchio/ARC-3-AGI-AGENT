from __future__ import annotations

import json
import unittest

from 検証.ARC3形状作用ゲート条件診断 import (
    _condition_results,
    summarize_conditions,
)

_SUPPORTED_SHAPE = tuple(sorted((x, y) for x in range(3) for y in range(3)))


def _supported_scene() -> tuple[dict, list[list[int]], dict]:
    board = [[0] * 64 for _ in range(64)]
    objects = [
        {"色": 14, "形": _SUPPORTED_SHAPE, "点": set(range(9)), "選択": index == 0}
        for index in range(2)
    ]
    targets = [{"形": _SUPPORTED_SHAPE, "外枠": set()} for _ in range(2)]
    scene = {"対象": objects, "目標": targets, "game_id": "must-not-escape"}
    gate = {"状態": "適用可能", "根拠": ["private reason must not escape"]}
    return scene, board, gate


class ShapeActionGateConditionAuditTests(unittest.TestCase):
    def test_all_existing_gate_conditions_are_counted(self):
        scene, board, _ = _supported_scene()
        conditions = _condition_results(scene, board)

        self.assertEqual(len(conditions), 10)
        self.assertTrue(all(conditions.values()))

    def test_unsupported_color_transport_and_selection_are_detected(self):
        scene, board, _ = _supported_scene()
        scene["対象"][1]["色"] = 11
        scene["対象"][0]["選択"] = False
        board[0][0] = 12
        conditions = _condition_results(scene, board)

        self.assertFalse(conditions["対象色がモデル支持"])
        self.assertFalse(conditions["搬送候補なし"])
        self.assertFalse(conditions["選択対象が一意"])

    def test_aggregate_contains_only_counts_and_safe_statuses(self):
        first = _supported_scene()
        second = _supported_scene()
        second[0]["game_id"] = "second-secret"
        second[2]["状態"] = "secret-status"
        aggregate = summarize_conditions([first, second, *[_supported_scene() for _ in range(3)]])

        serialized = json.dumps(aggregate, ensure_ascii=False)
        self.assertNotIn("must-not-escape", serialized)
        self.assertNotIn("second-secret", serialized)
        self.assertNotIn("private reason", serialized)
        self.assertNotIn("secret-status", serialized)
        self.assertEqual(aggregate["初回進行中観測件数"], 5)
        self.assertEqual(aggregate["条件別成立件数"]["盤面寸法支持"], {"成立": 5, "不成立": 0})
        self.assertEqual(aggregate["作用ゲート状態件数"], {"適用可能": 4, "その他": 1})


if __name__ == "__main__":
    unittest.main()
