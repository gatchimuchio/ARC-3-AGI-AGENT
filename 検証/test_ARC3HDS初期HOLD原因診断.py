from __future__ import annotations

import json
import unittest

from 検証.ARC3HDS初期HOLD原因診断 import (
    _accumulate_vocabulary,
    _empty_vocabulary_summary,
    _reason_categories,
    _state_label,
    _summarize_vocabulary,
)


class HDSInitialHoldReasonAuditTests(unittest.TestCase):
    def test初回進行状態をその他へ落とさない(self):
        self.assertEqual(_state_label("NOT_FINISHED"), "NOT_FINISHED")
        self.assertEqual(_state_label("unknown-state-secret"), "その他")

    def test理由は安全な分類へ変換し文字列を保持しない(self):
        categories = _reason_categories(
            [
                {"段階": "内容HDS", "理由": "private board 7,8"},
                {"例外": "KeyError", "理由": "game-id-secret"},
                "raw coordinates 17,29",
                {"段階": ["unexpected", "mutable"]},
            ]
        )

        self.assertEqual(categories["段階:内容HDS"], 1)
        self.assertEqual(categories["例外理由"], 1)
        self.assertEqual(categories["定型文字列理由"], 1)
        self.assertEqual(categories["段階:その他"], 1)
        self.assertNotIn("private board", json.dumps(categories))
        self.assertNotIn("game-id-secret", json.dumps(categories))
        self.assertNotIn("17,29", json.dumps(categories))

    def test語彙集計は適用状態と件数だけを公開する(self):
        candidate_result = {
            "適用性": {
                "状態": "未確認",
                "根拠": [{"段階": "作用HDS", "理由": "color=9, x=10"}],
            },
            "作用適用性": {"状態": "構造上不適用", "根拠": ["secret-level-id"]},
            "目標候補群": [{"位置": [3, 4], "色": 11}],
            "作用候補群": [{"作用番号": 6, "引数": {"x": 3, "y": 4}}],
            "保留理由群": ["game-id-secret"],
            "規則不確実性": [{"原理識別子": "private-rule-id"}],
            "未採用理由群": [{"trajectory": [1, 2, 3]}],
            "実行許可": False,
            "game_id": "secret-game-id",
        }

        summary = _summarize_vocabulary(candidate_result)

        self.assertEqual(summary["適用性状態"], "未確認")
        self.assertEqual(summary["作用適用性状態"], "構造上不適用")
        self.assertEqual(summary["目標候補数"], 1)
        self.assertEqual(summary["作用候補数"], 1)
        self.assertEqual(summary["規則不確実性件数"], 1)
        self.assertEqual(summary["未採用理由件数"], 1)
        serialized = json.dumps(summary, ensure_ascii=False)
        for excluded in (
            "secret-level-id",
            "game-id-secret",
            "private-rule-id",
            "secret-game-id",
            "trajectory",
            "色",
            "位置",
            "引数",
        ):
            self.assertNotIn(excluded, serialized)

    def testaggregateは語彙状態と理由カテゴリを加算する(self):
        aggregate = _empty_vocabulary_summary()
        summary = _summarize_vocabulary(
            {
                "適用性": {"状態": "適用可能"},
                "作用適用性": {"状態": "適用可能"},
                "目標候補群": [{}, {}],
                "作用候補群": [{}],
                "保留理由群": [{"未確認語彙": ["private-vocabulary-result"]}],
                "規則不確実性": [],
                "未採用理由群": [],
                "実行許可": False,
            }
        )

        _accumulate_vocabulary(aggregate, summary)
        _accumulate_vocabulary(aggregate, summary)

        self.assertEqual(aggregate["照会件数"], 2)
        self.assertEqual(aggregate["適用性状態"]["適用可能"], 2)
        self.assertEqual(aggregate["目標候補数合計"], 4)
        self.assertEqual(aggregate["作用候補数合計"], 2)
        self.assertEqual(aggregate["保留理由カテゴリ"]["構造化理由"], 2)
        self.assertEqual(aggregate["実行許可申告件数"], 0)


if __name__ == "__main__":
    unittest.main()
