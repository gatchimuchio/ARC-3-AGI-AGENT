"""自作の小さな記号系だけで、保存した純粋探索部品を検証する。"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ここ = Path(__file__).resolve().parent
実装パス = ここ / "planner.py"
仕様 = importlib.util.spec_from_file_location("保存探索部品", 実装パス)
探索 = importlib.util.module_from_spec(仕様)
仕様.loader.exec_module(探索)


def 自作作用(盤面, 操作, 原子):
    return [
        操作["color"] if 操作["mask"] >> 添字 & 1 else 値
        for 添字, 値 in enumerate(盤面)
    ], {"由来": "この検証内で作った記号操作"}


def 自作準備(器具, 方向, 色, 次方向):
    return {
        "turn_distance": int(tuple(方向) != tuple(次方向)),
        "copy_required": 器具 != 色,
    }


class 合成探索検証(unittest.TestCase):
    def test_原版同一性と外部依存の不存在(self):
        内容 = 実装パス.read_bytes()
        self.assertEqual(
            hashlib.sha256(内容).hexdigest(),
            "93ab443a14235e303953be36fefac5be05e360a6e0cebb760eb8363c9cd6dcea",
        )
        木 = ast.parse(内容)
        読込 = [
            別名.name
            for 節 in ast.walk(木) if isinstance(節, ast.Import)
            for 別名 in 節.names
        ]
        self.assertEqual(読込, ["collections", "json", "heapq"])
        self.assertFalse(any(isinstance(節, ast.ImportFrom) for 節 in ast.walk(木)))
        禁止名 = {
            "open", "eval", "exec", "__import__", "compile",
            "game_id", "level_id", "guid", "nonce",
        }
        self.assertFalse({
            節.id for 節 in ast.walk(木) if isinstance(節, ast.Name)
        } & 禁止名)
        self.assertFalse(any(
            isinstance(節, ast.Attribute) and 節.attr in
            {"read_bytes", "read_text", "write_bytes", "write_text", "connect"}
            for 節 in ast.walk(木)
        ))

    def test_観測値と目標と作用範囲を混同しない商(self):
        元 = [[0, 0], [0, 1]]
        目標 = [[1, 1], [2, 1]]
        def 所属(方向, 横, 縦, 辺長, 種別):
            self.assertEqual(種別, "広域塗布")
            return (横 == 0) if 方向 == "左列" else (縦 == 0)
        原子 = 探索.quotient(元, 目標, ["左列", "上行"], 所属)
        全座標 = [座標 for 原子一個 in 原子 for 座標 in 原子一個["cells"]]
        self.assertEqual(sorted(全座標), [[0, 0], [0, 1], [1, 0], [1, 1]])
        self.assertEqual(len(原子), 4)
        for 原子一個 in 原子:
            for 横, 縦 in 原子一個["cells"]:
                self.assertEqual(原子一個["initial"], 元[縦][横])
                self.assertEqual(原子一個["goal"], 目標[縦][横])
        with self.assertRaisesRegex(探索.Hold, "untyped membership"):
            探索.quotient([[0]], [[1]], ["仮"], lambda *引数: 1)

    def test_後向き義務は矛盾と自己ループを残す(self):
        原子 = [{"initial": 0, "goal": 1}, {"initial": 0, "goal": 2}]
        操作 = [
            {"color": 1, "mask": 1},
            {"color": 2, "mask": 2},
            {"color": 9, "mask": 3},
        ]
        結果 = 探索.obligations(原子, 操作)
        self.assertEqual(結果["status"], "COMPLETE")
        self.assertEqual(結果["states"], [0, 1, 2, 3])
        self.assertEqual(len(結果["all_edges"]), 12)
        self.assertTrue(any(辺["contradictions"] for 辺 in 結果["all_edges"]))
        self.assertTrue(any(辺["self_loop"] for 辺 in 結果["all_edges"]))
        途中 = 探索.obligations(原子, 操作, max_edges=1)
        self.assertEqual(途中["status"], "HOLD_RESOURCE")
        self.assertEqual(len(途中["all_edges"]), 1)
        self.assertEqual(途中["next_operation"], 1)

    def test_全辺と費用と完全な証明経路(self):
        原子 = [{"initial": 0, "goal": 1}, {"initial": 0, "goal": 2}]
        操作 = [
            {"color": 1, "direction": [0, 1], "mask": 1},
            {"color": 2, "direction": [1, 0], "mask": 2},
            {"color": 3, "direction": [0, 1], "mask": 3},
        ]
        結果 = 探索.full_closure(原子, 操作, 0, [0, 1], 自作作用, 自作準備)
        self.assertEqual(結果["status"], "COMPLETE_CONDITIONAL_CLOSURE")
        self.assertEqual(len(結果["all_edges"]), len(結果["states"]) * len(操作))
        費用 = {番号: 0 for 番号 in 結果["goal_states"]}
        while True:
            前 = dict(費用)
            for 辺 in 結果["all_edges"]:
                if 辺["target"] in 前:
                    準備 = 辺["preparation"]
                    重み = 1 + 準備["turn_distance"] + int(準備["copy_required"])
                    始点 = 辺["source"]
                    費用[始点] = min(費用.get(始点, 10**9), 前[辺["target"]] + 重み)
            if 費用 == 前:
                break
        self.assertEqual({str(鍵): 値 for 鍵, 値 in 費用.items()}, 結果["remaining_external_cost"])
        self.assertEqual(費用[0], 5)
        最適先頭 = []
        for 番号, 辺 in enumerate(結果["all_edges"]):
            if 辺["source"] == 0 and 辺["target"] in 費用:
                準備 = 辺["preparation"]
                重み = 1 + 準備["turn_distance"] + int(準備["copy_required"])
                if 重み + 費用[辺["target"]] == 費用[0]:
                    最適先頭.append(番号)
        self.assertEqual(最適先頭, 結果["cost_reducing_first_edges"])
        for 先頭, 経路 in 結果["complete_witnesses_by_first_edge"].items():
            self.assertEqual(経路[0], int(先頭))
            現在 = 0
            for 番号 in 経路:
                辺 = 結果["all_edges"][番号]
                self.assertEqual(辺["source"], 現在)
                現在 = 辺["target"]
            self.assertIn(現在, 結果["goal_states"])
        self.assertFalse(結果["execution_permission"])

    def test_部分修復と全面上書きは達成扱いしない(self):
        原子 = [{"initial": 0, "goal": 1}, {"initial": 0, "goal": 2}]
        for 操作 in [
            [{"color": 1, "direction": [0, 1], "mask": 1}],
            [{"color": 1, "direction": [0, 1], "mask": 3},
             {"color": 2, "direction": [0, 1], "mask": 3}],
        ]:
            結果 = 探索.full_closure(原子, 操作, 0, [0, 1], 自作作用, 自作準備)
            self.assertEqual(結果["goal_states"], [])
            self.assertEqual(結果["complete_witnesses_by_first_edge"], {})
            self.assertEqual(結果["cost_reducing_first_edges"], [])
            self.assertEqual(len(結果["all_edges"]), len(結果["states"]) * len(操作))

    def test_作用側の保留も辺として残す(self):
        原子 = [{"initial": 0, "goal": 1}]
        操作 = [{"color": 1, "direction": [0, 1], "mask": 1},
                {"color": 9, "direction": [0, 1], "mask": 1}]
        def 保留付き作用(盤面, 選択, 原子):
            if 選択["color"] == 9:
                raise 探索.Hold("自作の未支持条件")
            return 自作作用(盤面, 選択, 原子)
        結果 = 探索.full_closure(原子, 操作, 0, [0, 1], 保留付き作用, 自作準備)
        保留 = [辺 for 辺 in 結果["all_edges"] if 辺["operation"] == 1]
        self.assertEqual(len(保留), len(結果["states"]))
        self.assertTrue(all(辺["status"] == "HOLD" and 辺["target"] is None for 辺 in 保留))

    def test_資源境界では途中証明を使用させない(self):
        原子 = [{"initial": 0, "goal": 1}, {"initial": 0, "goal": 2}]
        操作 = [{"color": 1, "direction": [0, 1], "mask": 1},
                {"color": 2, "direction": [1, 0], "mask": 2}]
        for 上限 in [{"max_states": 1}, {"max_edges": 1}]:
            結果 = 探索.full_closure(原子, 操作, 0, [0, 1], 自作作用, 自作準備, **上限)
            self.assertEqual(結果["status"], "HOLD_RESOURCE")
            self.assertEqual(結果["complete_witnesses_by_first_edge"], {})
            self.assertEqual(結果["cost_reducing_first_edges"], [])
            self.assertFalse(結果["execution_permission"])
            self.assertIsNotNone(結果["interrupted_source"])

    def test_空操作の既達成状態に実行権限を足さない(self):
        結果 = 探索.full_closure([{"initial": 1, "goal": 1}], [], 1, [0, 1], 自作作用, 自作準備)
        self.assertEqual(結果["goal_states"], [0])
        self.assertEqual(結果["remaining_external_cost"], {"0": 0})
        self.assertEqual(結果["all_edges"], [])
        self.assertFalse(結果["execution_permission"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

