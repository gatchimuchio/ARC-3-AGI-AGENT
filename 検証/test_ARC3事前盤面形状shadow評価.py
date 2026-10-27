from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from 検証.ARC3事前盤面形状shadow評価 import (  # noqa: E402
    _board_features,
    _input,
    _samples_from_trace,
)


class BoardMorphologyShadowTests(unittest.TestCase):
    def test盤面色分布を匿名カテゴリへ離散化する(self):
        self.assertEqual(
            _board_features(((1, 1, 1, 2),)),
            {"事前盤面色分布帯": "色数1-2;最多色50%-75%"},
        )
        self.assertEqual(
            _board_features(((1, 1, 1, 1, 2),)),
            {"事前盤面色分布帯": "色数1-2;最多色75%超"},
        )
        self.assertEqual(
            _board_features(((1, 1, 2, 2),)),
            {"事前盤面色分布帯": "色数1-2;最多色50%以下"},
        )
        self.assertEqual(
            _board_features(((1, 2, 3, 4),)),
            {"事前盤面色分布帯": "色数3-4;最多色50%以下"},
        )
        self.assertEqual(
            _board_features(((1, 2, 3, 4, 5),)),
            {"事前盤面色分布帯": "色数5+;最多色50%以下"},
        )
        self.assertIsNone(_board_features(None))
        self.assertIsNone(_board_features(((1, 2), ())))

    def testHDS入力はActionと合成カテゴリだけ(self):
        sample = {
            "action_id": 6,
            "changed_cells": 1,
            "level_delta": 0,
            "new_visible_board": True,
            "board_features": {"事前盤面色分布帯": "色数3-4;最多色50%以下"},
            "game_id": "private-game-key",
            "level_id": "private-level-key",
            "data": {"x": 17, "y": 29},
            "trajectory": [1, 2, 3],
        }

        external_input = _input(sample, include_board=True, include_result=False)

        self.assertEqual(
            external_input.内容,
            {
                "条件": {
                    "Action番号": 6,
                    "事前盤面色分布帯": "色数3-4;最多色50%以下",
                }
            },
        )
        self.assertEqual(external_input.対象系境界, "ARC-AGI-3公開Action応答")

    def test事前特徴を同じ応答へ対応付けRESETと比較不能行を除外する(self):
        responses = [
            {
                "action_id": 1,
                "changed_cells": 1,
                "level_delta": 0,
                "new_visible_board": True,
                "lifecycle_action": False,
            },
            {
                "action_id": 0,
                "changed_cells": 0,
                "level_delta": 0,
                "new_visible_board": False,
                "lifecycle_action": True,
            },
            {
                "action_id": 2,
                "changed_cells": 0,
                "level_delta": 1,
                "new_visible_board": False,
                "lifecycle_action": False,
            },
            {
                "action_id": 3,
                "changed_cells": 0,
                "level_delta": 0,
                "new_visible_board": False,
                "lifecycle_action": False,
            },
        ]
        features = [
            {"事前盤面色分布帯": "色数1-2;最多色75%超"},
            {"事前盤面色分布帯": "色数3-4;最多色50%以下"},
            {"事前盤面色分布帯": "色数5+;最多色50%以下"},
            None,
        ]

        samples = _samples_from_trace(responses, features)

        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0]["action_id"], 1)
        self.assertEqual(
            samples[0]["board_features"],
            {"事前盤面色分布帯": "色数1-2;最多色75%超"},
        )
        self.assertEqual(samples[1]["action_id"], 2)
        self.assertEqual(
            samples[1]["board_features"],
            {"事前盤面色分布帯": "色数5+;最多色50%以下"},
        )
        with self.assertRaises(ValueError):
            _samples_from_trace(responses, features[:-1])


if __name__ == "__main__":
    unittest.main()
