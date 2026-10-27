from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from 検証.ARC3HDS公開遷移shadow評価 import _入力, _環境評価


class HDS公開遷移ShadowTests(unittest.TestCase):
    def test_HDS入力から識別子座標盤面とtrajectoryを除く(self):
        外部入力 = _入力(
            {
                "action_id": 6,
                "before_state": "NOT_FINISHED",
                "after_state": "NOT_FINISHED",
                "changed_cells": 1,
                "level_delta": 0,
                "new_visible_board": True,
                "game_id": "private-game-key",
                "level_id": "private-level-key",
                "guid": "private-run-key",
                "fingerprint": "private-observation-hash",
                "data": {"x": 17, "y": 29},
                "trajectory": [1, 2, 3],
            },
            結果を含む=True,
        )

        self.assertEqual(
            外部入力.内容,
            {
                "条件": {"Action番号": 6},
                "結果": {
                    "可視変化あり": True,
                    "level進行あり": False,
                    "新規盤面あり": True,
                },
            },
        )
        self.assertEqual(外部入力.対象系境界, "ARC-AGI-3公開Action応答")

    def test_後半照会はread_onlyで経験台帳を増やさない(self):
        応答群 = [
            {
                "action_id": (i % 2) + 1,
                "changed_cells": int(i % 2 == 0),
                "level_delta": 0,
                "new_visible_board": bool(i % 2 == 0),
            }
            for i in range(8)
        ]

        結果 = _環境評価(応答群, 学習比率=0.75)

        self.assertEqual(結果["学習Action数"], 6)
        self.assertEqual(結果["後半照会Action数"], 2)
        self.assertEqual(結果["学習後経験台帳件数"], 6)
        self.assertEqual(結果["照会後経験台帳件数"], 6)

    def test_RESETはHDS経験入力から除外する(self):
        応答群 = [
            {"action_id": 0, "changed_cells": 0, "level_delta": 0, "new_visible_board": False},
            *[
                {
                    "action_id": 1 + i % 2,
                    "changed_cells": i,
                    "level_delta": 0,
                    "new_visible_board": bool(i % 2),
                }
                for i in range(7)
            ],
        ]

        結果 = _環境評価(応答群, 学習比率=0.75)

        self.assertEqual(結果["学習Action数"], 5)
        self.assertEqual(結果["後半照会Action数"], 2)
        self.assertEqual(結果["照会後経験台帳件数"], 5)


if __name__ == "__main__":
    unittest.main()
