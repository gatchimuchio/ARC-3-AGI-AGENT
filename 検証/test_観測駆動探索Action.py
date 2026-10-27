from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "HDS/学習系統/v0.4.2")]

from 接続.ARC3境界 import 境界違反, 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針


def 観測(n, board, actions=(1, 2), *, levels=0, game="public-a", state="NOT_FINISHED"):
    return 観測する(
        {
            "game_id": game,
            "guid": "run",
            "state": state,
            "frame": [board],
            "available_actions": list(actions),
            "levels_completed": levels,
            "win_levels": 3,
        },
        観測通番=n,
    )


class 観測駆動探索Tests(unittest.TestCase):
    def test_選択は現在の合法作用だけを使い応答を次選択へ反映(self):
        policy = 観測駆動探索方針(乱数種=8)
        board0 = [[0, 0], [0, 0]]
        board1 = [[1, 0], [0, 0]]
        before1 = 観測(0, board0, actions=(1, 2))
        action1 = policy.選ぶ(before1)
        self.assertIn(action1.作用番号, (1, 2))
        after1 = 観測(1, board1, actions=(1, 2), levels=1)
        first = policy.応答を記録する(before1, action1, after1)
        self.assertEqual(first["出所"], "観測駆動探索")
        self.assertEqual(first["完了レベル増分"], 1)
        self.assertAlmostEqual(first["公開応答報酬"], 4.5625)

        action2 = policy.選ぶ(after1)
        self.assertNotEqual(action1.作用番号, action2.作用番号)
        after2 = 観測(2, board1, actions=(1, 2), levels=1)
        second = policy.応答を記録する(after1, action2, after2)
        self.assertLess(second["公開応答報酬"], first["公開応答報酬"])
        self.assertAlmostEqual(second["公開応答報酬"], -1.0)

        action3 = policy.選ぶ(after2)
        self.assertEqual(action3.作用番号, action1.作用番号)

    def test_可視変化報酬係数だけを分離できる(self):
        before = 観測(0, [[0, 0], [0, 0]], actions=(1,))
        after = 観測(1, [[1, 0], [0, 0]], actions=(1,))

        default = 観測駆動探索方針(乱数種=5)
        default_action = default.選ぶ(before)
        default_reward = default.応答を記録する(before, default_action, after)

        ablated = 観測駆動探索方針(乱数種=5, 可視変化係数=0.0)
        ablated_action = ablated.選ぶ(before)
        ablated_reward = ablated.応答を記録する(before, ablated_action, after)

        self.assertAlmostEqual(default_reward["公開応答報酬"], 0.5625)
        self.assertAlmostEqual(ablated_reward["公開応答報酬"], 0.5)

    def test_レベル進行報酬係数だけを分離できる(self):
        before = 観測(0, [[0, 0], [0, 0]], actions=(1,))
        after = 観測(1, [[1, 0], [0, 0]], actions=(1,), levels=1)
        policy = 観測駆動探索方針(乱数種=5, レベル進行報酬=8.0)

        action = policy.選ぶ(before)
        response = policy.応答を記録する(before, action, after)

        self.assertAlmostEqual(response["公開応答報酬"], 8.5625)

    def test_色UCB係数をActionUCB係数から分離できる(self):
        def 選択色(色係数):
            policy = 観測駆動探索方針(
                乱数種=5,
                探索係数=0.8,
                色探索係数=色係数,
            )
            policy._色回数.update({0: 1, 1: 4})
            policy._色報酬合計.update({0: 0.0, 1: 1.2})
            current = 観測(0, [[0, 1]], actions=(6,))
            policy.選ぶ(current)
            return policy._選択座標色

        self.assertEqual(選択色(None), 0)
        self.assertEqual(選択色(0.8), 0)
        self.assertEqual(選択色(0.4), 1)

    def test_色UCB係数は有限の正数に限定する(self):
        for value in (0.0, -0.1, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                観測駆動探索方針(色探索係数=value)

    def test_同盤で無変化だった離散Actionは代替があれば避ける(self):
        policy = 観測駆動探索方針(乱数種=5, 同盤無変化Action回避=True)
        board = [[0, 0], [1, 1]]
        before = 観測(0, board, actions=(1, 2))
        first = policy.選ぶ(before)
        after = 観測(1, board, actions=(1, 2))
        policy.応答を記録する(before, first, after)

        second = policy.選ぶ(after)

        self.assertNotEqual(first.作用番号, second.作用番号)

    def test_代替がない場合は同盤無変化Actionを候補へ戻す(self):
        policy = 観測駆動探索方針(乱数種=5, 同盤無変化Action回避=True)
        board = [[0, 0], [1, 1]]
        before = 観測(0, board, actions=(1,))
        first = policy.選ぶ(before)
        after = 観測(1, board, actions=(1,))
        policy.応答を記録する(before, first, after)

        second = policy.選ぶ(after)

        self.assertEqual(second.作用番号, 1)

    def test_盤面が変われば過去の同盤無変化記録で選択を除外しない(self):
        policy = 観測駆動探索方針(乱数種=5, 同盤無変化Action回避=True)
        before = 観測(0, [[0, 0], [1, 1]], actions=(1,))
        first = policy.選ぶ(before)
        after = 観測(1, [[0, 1], [1, 1]], actions=(1,))
        policy.応答を記録する(before, first, after)

        second = policy.選ぶ(after)

        self.assertEqual(second.作用番号, 1)

    def test_座標Action初手優先は合法で未試行の場合だけ選ぶ(self):
        policy = 観測駆動探索方針(乱数種=9, 座標Action初手優先=True)
        current = 観測(0, [[0, 0], [1, 1]], actions=(1, 6))

        action = policy.選ぶ(current)

        self.assertEqual(action.作用番号, 6)
        self.assertIn(action.引数["x"], range(2))
        self.assertIn(action.引数["y"], range(2))

    def test_座標Actionは可視色ごとの応答を使い未試行セルを選ぶ(self):
        policy = 観測駆動探索方針(乱数種=3)
        board = [[0, 0, 0], [0, 5, 5], [0, 0, 0]]
        before = 観測(0, board, actions=(6,))
        first = policy.選ぶ(before)
        self.assertEqual(first.作用番号, 6)
        self.assertTrue(0 <= first.引数["x"] < 3 and 0 <= first.引数["y"] < 3)
        after = 観測(1, board, actions=(6,))
        policy.応答を記録する(before, first, after)
        second = policy.選ぶ(after)
        self.assertNotEqual(first.引数, second.引数)

    def test_UCB最上位色が枯渇しても未試行座標のある色へ進む(self):
        policy = 観測駆動探索方針(乱数種=4)
        before = 観測(0, [[2, 2], [4, 4]], actions=(6,))
        policy._色回数.update({2: 1, 4: 1})
        policy._色報酬合計.update({2: 10.0, 4: -10.0})
        policy._座標試行[before.最新盤面] = {(0, 0), (1, 0)}

        action = policy.選ぶ(before)

        self.assertIsNotNone(action)
        self.assertEqual(action.作用番号, 6)
        self.assertIn((action.引数["x"], action.引数["y"]), {(0, 1), (1, 1)})
        self.assertEqual(policy._選択座標色, 4)
        after = 観測(1, [[2, 2], [4, 4]], actions=(6,))
        policy.応答を記録する(before, action, after)

    def test_全色の座標を試行済みなら安全に停止する(self):
        policy = 観測駆動探索方針(乱数種=4)
        before = 観測(0, [[2, 4]], actions=(6,))
        policy._色回数.update({2: 1, 4: 1})
        policy._座標試行[before.最新盤面] = {(0, 0), (1, 0)}
        self.assertIsNone(policy.選ぶ(before))

    def test_ゲーム識別子を変えても同じ可視入力では同じ選択(self):
        board = [[0, 1], [1, 0]]
        first = 観測駆動探索方針(乱数種=12).選ぶ(観測(0, board, game="game-a"))
        second = 観測駆動探索方針(乱数種=12).選ぶ(観測(0, board, game="game-b"))
        self.assertEqual(first, second)

    def test_ゲームオーバーでは探索でなくSDKリセットを返す(self):
        policy = 観測駆動探索方針(乱数種=12)
        action = policy.選ぶ(
            観測(5, [[0, 0]], actions=(6,), state="GAME_OVER")
        )
        self.assertEqual(action.作用番号, 0)
        self.assertEqual(action.引数, {})
        self.assertEqual(action.出所, "SDKリセット")

    def test_候補の出所や作用前合法性に違反した応答を拒否(self):
        policy = 観測駆動探索方針(乱数種=1)
        before = 観測(0, [[0]], actions=(1,))
        action = policy.選ぶ(before)
        after = 観測(1, [[0]], actions=(1,))
        action = type(action)(action.作用番号, action.引数, "HDS確定")
        with self.assertRaises(境界違反):
            policy.応答を記録する(before, action, after)


if __name__ == "__main__":
    unittest.main()
