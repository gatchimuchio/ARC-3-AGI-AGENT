from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from 検証.ARC3Frame特徴公開遷移shadow評価 import (  # noqa: E402
    _frame_features,
    _input,
    _samples_from_trace,
)


class FrameFeatureShadowTests(unittest.TestCase):
    def test_直前Frame条件は公開真偽要約だけ(self):
        sample = {
            "action_id": 6,
            "changed_cells": 1,
            "level_delta": 0,
            "new_visible_board": True,
            "previous_frame_features": {
                "直前複数Frame": True,
                "直前中間Grid差分": False,
                "直前一時Cell差分": True,
            },
            "game_id": "private-game-key",
            "level_id": "private-level-key",
            "data": {"x": 17, "y": 29},
            "trajectory": [1, 2, 3],
        }

        外部入力 = _input(sample, include_frame_features=True, include_result=False)

        self.assertEqual(
            外部入力.内容,
            {
                "条件": {
                    "Action番号": 6,
                    "直前複数Frame": True,
                    "直前中間Grid差分": False,
                    "直前一時Cell差分": True,
                }
            },
        )
        self.assertEqual(外部入力.対象系境界, "ARC-AGI-3公開Action応答")

    def test_same_response_frame特徴は次サンプル条件になりRESET結果は除外(self):
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
                "level_delta": 0,
                "new_visible_board": False,
                "lifecycle_action": False,
            },
        ]
        metrics = [
            {
                "uncomparable_transitions": 0,
                "multi_frame_responses": 0,
                "intermediate_grids_different_from_final": 0,
                "transient_cells_returning_to_prior_value": 0,
            },
            {
                "uncomparable_transitions": 0,
                "multi_frame_responses": 1,
                "intermediate_grids_different_from_final": 1,
                "transient_cells_returning_to_prior_value": 4,
            },
            {
                "uncomparable_transitions": 0,
                "multi_frame_responses": 0,
                "intermediate_grids_different_from_final": 0,
                "transient_cells_returning_to_prior_value": 0,
            },
        ]

        samples = _samples_from_trace(responses, metrics)

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["action_id"], 2)
        self.assertEqual(
            samples[0]["previous_frame_features"],
            {
                "直前複数Frame": True,
                "直前中間Grid差分": True,
                "直前一時Cell差分": True,
            },
        )

    def test_comparison不能够な直前Frameは特徴として捏造しない(self):
        metrics = {
            "uncomparable_transitions": 1,
            "multi_frame_responses": 0,
            "intermediate_grids_different_from_final": 0,
            "transient_cells_returning_to_prior_value": 0,
        }
        self.assertIsNone(_frame_features(metrics))


if __name__ == "__main__":
    unittest.main()
