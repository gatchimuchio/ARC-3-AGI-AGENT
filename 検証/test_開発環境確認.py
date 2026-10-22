"""環境診断の失敗境界と実形式の往復を確認する。"""
from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from 道具 import 開発環境確認 as 確認


class 偽作用:
    RESET = "RESET"
    ACTION1 = "ACTION1"


class 偽環境:
    def __init__(self, 観測あり=True, 作用=(1, 6)):
        self.呼出 = []
        self.観測あり = 観測あり
        self.作用 = 作用

    def step(self, action):
        self.呼出.append(action)
        if not self.観測あり:
            return None
        return SimpleNamespace(game_id="diagnostic-example", state="NOT_FINISHED",
                               levels_completed=0, win_levels=1, available_actions=self.作用,
                               frame=[[[0, len(self.呼出)]]], full_reset=False, guid="diagnostic")


class 環境診断試験(unittest.TestCase):
    def test_Parquet往復と描画は実ライブラリで実行する(self):
        結果 = 確認.Parquetと描画を確認する()
        self.assertEqual(結果["Parquet往復"], "成功")
        self.assertEqual(結果["PNG描画"], "成功")
        self.assertEqual(結果["競技提出形式の検証"], "未実施")

    def test_公式観測契約を通して一作用後の差分を保持する(self):
        環境 = 偽環境()
        結果 = 確認.観測経路を確認する(環境, 偽作用)
        self.assertEqual(環境.呼出, ["RESET", "ACTION1"])
        self.assertEqual(結果["初期盤面"], [1, 2])
        self.assertEqual(結果["変化セル数"], 1)
        self.assertEqual(結果["能力評価"], "未実施")

    def test_クリックしか使えない場合は診断座標を捏造しない(self):
        環境 = 偽環境(作用=(6,))
        結果 = 確認.観測経路を確認する(環境, 偽作用)
        self.assertEqual(環境.呼出, ["RESET"])
        self.assertIn("未実施", 結果["追加作用"])

    def test_公式環境の観測欠落は成功へ補完しない(self):
        with self.assertRaises(確認.確認失敗):
            確認.観測経路を確認する(偽環境(観測あり=False), 偽作用)

    def test_診断失敗は非zeroかつ後続検査も実行する(self):
        出力 = io.StringIO()
        with patch.object(確認, "版と読込を確認する", side_effect=確認.確認失敗("版不一致")), \
             patch.object(確認, "Parquetと描画を確認する", return_value={"確認": "実行済み"}), \
             patch.object(確認, "配布を確認する", return_value={}), \
             patch.object(確認, "Kaggleを確認する") as 外部, redirect_stdout(出力):
            終了 = 確認.main([])
        self.assertEqual(終了, 1)
        結果 = json.loads(出力.getvalue())
        self.assertEqual(結果["検査"]["形式と描画"]["確認"], "実行済み")
        外部.assert_not_called()

    def test_例外に含まれるSDK生ログを出さない(self):
        出力 = io.StringIO()
        with patch.object(確認, "版と読込を確認する", side_effect=RuntimeError("秘密の値")), \
             patch.object(確認, "Parquetと描画を確認する", return_value={}), \
             patch.object(確認, "配布を確認する", return_value={}), redirect_stdout(出力):
            self.assertEqual(確認.main([]), 1)
        self.assertNotIn("秘密の値", 出力.getvalue())

    def test_CompetitionModeはローカル診断で迂回しない(self):
        with patch.dict("os.environ", {"OPERATION_MODE": "competition"}):
            with self.assertRaises(確認.確認失敗):
                確認.オフラインを確認する(Path("unused"), "auto")

    def test_配布の改変と余分なファイルを検出する(self):
        with TemporaryDirectory() as tmp:
            基底 = Path(tmp)
            配布 = 基底 / "distribution"
            for 番号 in range(25):
                環境 = 配布 / "environment_files" / f"sample{番号}" / "version"
                環境.mkdir(parents=True)
                (環境 / "metadata.json").write_text("{}", encoding="utf-8")
                (環境 / "example.py").write_text("# fixture", encoding="utf-8")
            wheel = 配布 / "arc_agi_3_wheels"
            wheel.mkdir()
            for 名前 in ("arc_agi-0.9.8-py3-none-any.whl", "arcengine-0.9.3-py3-none-any.whl"):
                (wheel / 名前).write_bytes(b"fixture")
            (配布 / "A.txt").write_text("case-order", encoding="utf-8")
            (配布 / "a-lower.txt").write_text("case-order", encoding="utf-8")
            記録 = [{"パス": パス.relative_to(配布).as_posix(), "bytes": パス.stat().st_size,
                     "sha256": sha256(パス.read_bytes()).hexdigest()}
                    for パス in 配布.rglob("*") if パス.is_file()]
            マニフェスト = 基底 / "manifest.json"
            ZIP = 配布 / "fixture.zip"
            ZIP.write_bytes(b"archive")
            マニフェスト.write_text(json.dumps({"大会": 確認.大会, "ファイル": 記録,
                                                "ファイル数": len(記録),
                                                "総bytes": sum(項目["bytes"] for 項目 in 記録),
                                                "配布ZIP": {"ファイル": ZIP.name,
                                                           "bytes": ZIP.stat().st_size,
                                                           "sha256": sha256(ZIP.read_bytes()).hexdigest()}}),
                                  encoding="utf-8")
            self.assertEqual(確認.配布を確認する(配布, マニフェスト)["取得時記録との照合"], "成功")
            キャッシュ = 配布 / "environment_files" / "__pycache__"
            キャッシュ.mkdir()
            (キャッシュ / "fixture.pyc").write_bytes(b"generated")
            self.assertEqual(確認.配布を確認する(配布, マニフェスト)["取得ZIP照合"], "成功")
            ZIP.write_bytes(b"corrupt")
            with self.assertRaises(確認.確認失敗):
                確認.配布を確認する(配布, マニフェスト)
            ZIP.write_bytes(b"archive")
            (wheel / "arcengine-0.9.3-py3-none-any.whl").write_bytes(b"changed")
            with self.assertRaises(確認.確認失敗):
                確認.配布を確認する(配布, マニフェスト)
            (wheel / "arcengine-0.9.3-py3-none-any.whl").write_bytes(b"fixture")
            (配布 / "unexpected.py").write_text("# extra", encoding="utf-8")
            with self.assertRaises(確認.確認失敗):
                確認.配布を確認する(配布, マニフェスト)


if __name__ == "__main__":
    unittest.main()
