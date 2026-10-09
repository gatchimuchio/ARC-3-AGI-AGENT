"""ARC3公開インターフェースのE1契約テスト。実ゲームスコアの証拠ではない。"""
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from 接続.ARC3境界 import 境界違反, HDS確定作用, HDS観測入力, 作用を排出する, 観測する


class 偽作用:
    pass


class 偽環境:
    def __init__(self):
        self.calls = []

    def step(self, action, data=None, reasoning=None):
        self.calls.append((action, data, reasoning))
        return "実行結果"


class 偽公式Action:
    RESET = 偽作用()
    ACTION1 = 偽作用()
    ACTION6 = 偽作用()
    ACTION7 = 偽作用()


def 原票(**変更):
    v = {"game_id": "sample-v1", "state": "NOT_FINISHED", "levels_completed": 0,
         "win_levels": 2, "available_actions": [1, 6, 7],
         "frame": [[[0, 1], [2, 3]]], "full_reset": False, "guid": "session"}
    v.update(変更)
    return v


class 境界試験(unittest.TestCase):
    def test_実フレームと時系列を保持する(self):
        元 = 原票(frame=[[[0, 1], [2, 3]], [[1, 1], [2, 3]]])
        現 = 観測する(元, 観測通番=0)
        元["frame"][1][0][0] = 9
        self.assertEqual(現.最新盤面[0][0], 1)
        self.assertEqual(len(HDS観測入力(現)["盤面フレーム列"]), 2)
        self.assertEqual(現.指紋, 観測する(原票(frame=[[[0, 1], [2, 3]], [[1, 1], [2, 3]]]), 観測通番=0).指紋)

    def test_最新盤面変化とレベルを区別する(self):
        前 = 観測する(原票(), 観測通番=0)
        後 = 観測する(原票(frame=[[[0, 4], [2, 3]]], levels_completed=1), 観測通番=1)
        d = HDS観測入力(後, 前, 1)
        self.assertTrue(d["最新盤面比較可能"])
        self.assertEqual(d["最新盤面変化セル"], [[1, 0, 1, 4]])
        self.assertEqual(d["完了レベル増分"], 1)
        self.assertEqual(d["直前作用番号"], 1)

    def test_画面に変化なしでも状態遷移を捨てない(self):
        前 = 観測する(原票(), 観測通番=0)
        後 = 観測する(原票(state="GAME_OVER"), 観測通番=1)
        d = HDS観測入力(後, 前, 1)
        self.assertEqual(d["最新盤面変化セル"], [])
        self.assertEqual(d["状態遷移"], ["NOT_FINISHED", "GAME_OVER"])

    def test_初期化と寸法違いを差分なしと誤認しない(self):
        前 = 観測する(原票(), 観測通番=0)
        for 後 in (観測する(原票(frame=[[[1]]]), 観測通番=1), 観測する(原票(full_reset=True), 観測通番=1)):
            self.assertFalse(HDS観測入力(後, 前)["最新盤面比較可能"])

    def test_画素と不正な作用を拒否(self):
        for raw in (原票(frame=[[[16]]]), 原票(frame=[[[1.5]]]),
                    原票(frame=[[[0, 1], [1]]]), 原票(available_actions=[1, 1]),
                    原票(available_actions=[9]), 原票(state="UNKNOWN")):
            with self.subTest(raw=raw), self.assertRaises(境界違反):
                観測する(raw, 観測通番=0)

    def test_確定かつ合法な単純作用だけ通す(self):
        現 = 観測する(原票(), 観測通番=0)
        env = 偽環境()
        a = 作用を排出する(現, HDS確定作用(現.指紋, 1, "proof-1", "確定"), 偽公式Action, env)
        self.assertEqual(a, "実行結果")
        self.assertIs(env.calls[0][0], 偽公式Action.ACTION1)
        self.assertEqual(env.calls[0][1], {})
        self.assertEqual(env.calls[0][2]["HDS根拠参照"], "proof-1")
        self.assertFalse(hasattr(偽公式Action.ACTION1, "reasoning"))

    def test_座標Actionを境界検証する(self):
        現 = 観測する(原票(), 観測通番=0)
        env = 偽環境()
        ok = HDS確定作用(現.指紋, 6, "proof-6", "確定", {"x": 0, "y": 63})
        self.assertEqual(作用を排出する(現, ok, 偽公式Action, env), "実行結果")
        self.assertEqual(env.calls[0][1], {"x": 0, "y": 63})
        self.assertFalse(hasattr(偽公式Action.ACTION6, "data"))
        for data in ({}, {"x": 0}, {"x": 0, "y": 64}, {"x": True, "y": 2}, {"x": 1, "y": 1, "z": 2}):
            with self.subTest(data=data), self.assertRaises(境界違反):
                作用を排出する(現, HDS確定作用(現.指紋, 6, "proof-6", "確定", data), 偽公式Action, env)

    def test_不確定_根拠欠落_古い観測_禁止作用(self):
        現 = 観測する(原票(), 観測通番=0)
        env = 偽環境()
        for decision in (HDS確定作用(現.指紋, 1, "proof"),
                         HDS確定作用(現.指紋, 1, "", "確定"),
                         HDS確定作用("old", 1, "proof", "確定"),
                         HDS確定作用(現.指紋, 2, "proof", "確定"),
                         HDS確定作用(現.指紋, 1, "proof", "確定", {"x": 1})):
            with self.subTest(decision=decision), self.assertRaises(境界違反):
                作用を排出する(現, decision, 偽公式Action, env)
        self.assertEqual(env.calls, [])

    def test_RESETは初期とゲームオーバーのみ例外許可(self):
        env = 偽環境()
        for state in ("NOT_PLAYED", "GAME_OVER"):
            現 = 観測する(原票(state=state, available_actions=[]), 観測通番=0)
            self.assertEqual(作用を排出する(現, HDS確定作用(現.指紋, 0, "start", "確定"), 偽公式Action, env), "実行結果")
            self.assertIs(env.calls[-1][0], 偽公式Action.RESET)
        for state in ("NOT_FINISHED", "WIN"):
            現 = 観測する(原票(state=state, available_actions=[]), 観測通番=0)
            with self.assertRaises(境界違反):
                作用を排出する(現, HDS確定作用(現.指紋, 0, "start", "確定"), 偽公式Action, env)

    def test_異なるゲーム間では差分を作らない(self):
        with self.assertRaises(境界違反):
            HDS観測入力(観測する(原票(), 観測通番=0), 観測する(原票(game_id="another"), 観測通番=1))

    def test_同じ画像でも異なるターンとして扱う(self):
        前 = 観測する(原票(), 観測通番=0)
        後 = 観測する(原票(), 観測通番=1)
        self.assertNotEqual(前.指紋, 後.指紋)
        self.assertEqual(HDS観測入力(後, 前)["最新盤面変化セル"], [])
        env = 偽環境()
        with self.assertRaises(境界違反):
            作用を排出する(後, HDS確定作用(前.指紋, 1, "old", "確定"), 偽公式Action, env)
        with self.assertRaises(境界違反):
            HDS観測入力(前, 後)

    def test_実行識別子が変われば盤面差分を認めない(self):
        前 = 観測する(原票(), 観測通番=0)
        後 = 観測する(原票(guid="another"), 観測通番=1)
        self.assertFalse(HDS観測入力(後, 前)["最新盤面比較可能"])

    def test_公式enumの名前形式のactionにも対応(self):
        actions = [SimpleNamespace(name="ACTION1"), SimpleNamespace(name="ACTION6")]
        self.assertEqual(観測する(原票(available_actions=actions), 観測通番=0).作用可能番号, (1, 6))

    def test_不完全な観測と対応しない作用を拒否(self):
        for raw in (原票(game_id=""), 原票(available_actions=None),
                    原票(frame=[]), 原票(available_actions=0)):
            with self.subTest(raw=raw), self.assertRaises(境界違反):
                観測する(raw, 観測通番=0)
        with self.assertRaises(境界違反):
            HDS観測入力(観測する(原票(), 観測通番=0), 直前作用番号=1)


if __name__ == "__main__":
    unittest.main()
