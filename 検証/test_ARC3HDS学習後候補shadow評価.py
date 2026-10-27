from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from 検証.ARC3HDS学習後候補shadow評価 import (
    _anonymous_summary,
    _候補signatureを読む,
    _input_is_id_free,
)
from 検証.ARC3HDS公開遷移shadow評価 import _入力


class HDS学習後候補ShadowTests(unittest.TestCase):
    def test_HDS入力に識別情報盤面座標trajectoryが含まれない(self):
        external = _入力(
            {
                "action_id": 6,
                "changed_cells": 3,
                "level_delta": 1,
                "new_visible_board": True,
                "game_id": "game-key",
                "level_id": "level-key",
                "guid": "run-key",
                "board": [[1, 2], [3, 4]],
                "data": {"x": 9, "y": 12},
                "trajectory": [1, 2, 3],
            },
            結果を含む=True,
        )
        self.assertTrue(_input_is_id_free(external))
        self.assertEqual(set(external.内容["条件"]), {"Action番号"})
        self.assertEqual(
            set(external.内容["結果"]), {"可視変化あり", "level進行あり", "新規盤面あり"}
        )

    def test_candidate_signature_must_be_non_authorizing_and_legal(self):
        candidate = {
            "実行許可": False,
            "次作用候補群": [
                {
                    "実行許可": False,
                    "候補": {"作用番号": 6, "引数": {"x": 2, "y": 4}, "実行許可": False},
                }
            ],
        }
        signatures = _候補signatureを読む(candidate, {1, 6})
        self.assertEqual(len(signatures), 1)
        summary = _anonymous_summary(signatures)
        self.assertEqual(summary, {"候補数": 1, "Action番号別候補数": {"6": 1}})
        self.assertNotIn("x", str(summary))
        self.assertNotIn("y", str(summary))

    def test_nonlegal_or_authorized_candidate_fails_closed(self):
        candidate = {
            "実行許可": False,
            "次作用候補群": [
                {
                    "実行許可": False,
                    "候補": {"作用番号": 7, "引数": {}, "実行許可": False},
                }
            ],
        }
        with self.assertRaises(RuntimeError):
            _候補signatureを読む(candidate, {1, 6})
        candidate["実行許可"] = True
        with self.assertRaises(RuntimeError):
            _候補signatureを読む(candidate, {1, 6, 7})


if __name__ == "__main__":
    unittest.main()
