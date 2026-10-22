#!/usr/bin/env python3
"""開発環境を検査する。外部通信と公式環境実行は明示optionで分離する。"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import importlib
from importlib.metadata import version
import io
import json
import logging
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ルート = Path(__file__).resolve().parents[1]
大会 = "arc-prize-2026-arc-agi-3"
固定版 = {
    "arc-agi": "0.9.8",
    "arcengine": "0.9.3",
    "numpy": "2.4.4",
    "kaggle": "2.2.4",
    "kagglesdk": "0.1.37",
    "hds-learning-system": "0.4.2",
}


class 確認失敗(RuntimeError):
    """秘密情報を含まない診断メッセージ。"""


def 版と読込を確認する() -> dict:
    if sys.version_info[:2] != (3, 12):
        raise 確認失敗("Python 3.12が必要です。")
    版 = {名前: version(名前) for 名前 in 固定版}
    if any(版[名前] != 期待 for 名前, 期待 in 固定版.items()):
        raise 確認失敗("固定依存の版が不一致です。uv sync --lockedを実行してください。")
    # kaggleのimport自体は認証を開始するため、通常検査ではmetadataだけ確認する。
    for 名前 in ("arc_agi", "arcengine", "numpy", "pandas", "pyarrow", "hds学習系統"):
        importlib.import_module(名前)
    for 名前 in ("matplotlib", "jupyterlab", "ipykernel", "pytest", "ruff"):
        版[名前] = version(名前)
    return {"Python": sys.version.split()[0], "依存版": 版, "HDS読込": "成功"}


def Parquetと描画を確認する() -> dict:
    import matplotlib
    import numpy as np
    import pandas as pd

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    with TemporaryDirectory(prefix="arc3-format-check-") as tmp:
        保存先 = Path(tmp)
        元 = pd.DataFrame({"診断番号": [0, 1], "観測値": [3, 7]})
        元.to_parquet(保存先 / "diagnostic.parquet", index=False)
        復元 = pd.read_parquet(保存先 / "diagnostic.parquet")
        if not 元.equals(復元):
            raise 確認失敗("Parquet往復で値が変化しました。")
        図, 軸 = plt.subplots(figsize=(2, 2))
        try:
            軸.imshow(np.array([[0, 1], [2, 3]]), vmin=0, vmax=15)
            図.savefig(保存先 / "diagnostic.png")
        finally:
            plt.close(図)
        if not (保存先 / "diagnostic.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise 確認失敗("PNGを生成できません。")
    return {"Parquet往復": "成功", "PNG描画": "成功", "競技提出形式の検証": "未実施"}


def 配布を確認する(配布: Path, マニフェスト: Path | None = None) -> dict:
    配布 = 配布.resolve()
    環境 = 配布 / "environment_files"
    metadata = sorted(環境.glob("*/*/metadata.json"))
    if len(metadata) != 25:
        raise 確認失敗("Kaggle公開環境25個が揃っていません。配布データを取得してください。")
    for パス in metadata:
        内容 = json.loads(パス.read_text(encoding="utf-8"))
        if not isinstance(内容, dict) or not list(パス.parent.glob("*.py")):
            raise 確認失敗("公開環境のmetadataまたは実行ファイルが欠落しています。")
    for 名前 in ("arc_agi-0.9.8-py3-none-any.whl", "arcengine-0.9.3-py3-none-any.whl"):
        if not (配布 / "arc_agi_3_wheels" / 名前).is_file():
            raise 確認失敗("競技配布のSDK wheelが固定版と一致しません。")
    マニフェスト = マニフェスト or ルート / "接続" / "Kaggle配布マニフェスト.json"
    if not マニフェスト.is_file():
        raise 確認失敗("Kaggle配布マニフェストがありません。取得記録を確認してください。")
    原票 = json.loads(マニフェスト.read_text(encoding="utf-8"))
    if 原票.get("大会") != 大会:
        raise 確認失敗("取得マニフェストの大会が一致しません。")
    ZIP記録 = 原票.get("配布ZIP", {})
    ZIP名 = ZIP記録.get("ファイル")
    ZIP照合 = "未実施（展開済み配布だけを検査）"
    if ZIP名 and (配布 / ZIP名).is_file():
        ZIP = 配布 / ZIP名
        if (ZIP.stat().st_size != ZIP記録["bytes"]
                or sha256(ZIP.read_bytes()).hexdigest() != ZIP記録["sha256"]):
            raise 確認失敗("取得ZIPのサイズ・SHA256が取得記録と一致しません。")
        ZIP照合 = "成功"
    # SDKが公開環境をimportした時のPython cacheは、配布原本の集合に含めない。
    ファイル = sorted((パス for パス in 配布.rglob("*")
                     if パス.is_file() and "__pycache__" not in パス.relative_to(配布).parts
                     and パス.relative_to(配布).as_posix() != ZIP名),
                    key=lambda パス: パス.relative_to(配布).as_posix())
    記録 = [
        {"path": パス.relative_to(配布).as_posix(), "size": パス.stat().st_size,
         "sha256": sha256(パス.read_bytes()).hexdigest()}
        for パス in ファイル
    ]
    期待 = sorted(
        ({"path": 項目["パス"], "size": 項目["bytes"], "sha256": 項目["sha256"]}
         for 項目 in 原票["ファイル"]), key=lambda x: x["path"])
    if (期待 != 記録 or 原票.get("ファイル数") != len(記録)
            or 原票.get("総bytes") != sum(項目["size"] for 項目 in 記録)):
        raise 確認失敗("配布データのサイズ・SHA256・ファイル集合が取得記録と一致しません。")
    指紋 = sha256(json.dumps(記録, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"公開環境数": len(metadata), "配布ファイル数": len(記録), "配布SHA256": 指紋,
            "取得時記録との照合": "成功", "取得ZIP照合": ZIP照合, "SDK wheel": "固定版と一致"}


def 観測経路を確認する(環境, 公式作用) -> dict:
    """診断限定。HDSの判断・学習・攻略能力を代行しない。"""
    from 接続.ARC3境界 import HDS観測入力, 観測する

    生観測 = 環境.step(公式作用.RESET)
    if 生観測 is None:
        raise 確認失敗("公式環境のRESETが観測を返しませんでした。")
    初期 = 観測する(生観測, 観測通番=0)
    入力 = HDS観測入力(初期)
    if not 初期.盤面列:
        raise 確認失敗("公式環境の初期フレームが空です。")
    候補 = [番号 for 番号 in 初期.作用可能番号 if 番号 not in (0, 6)]
    結果 = {"ゲーム": 初期.ゲーム識別子, "初期状態": 初期.状態,
            "初期盤面": [len(初期.最新盤面), len(初期.最新盤面[0])],
            "HDS観測入力": "成功", "観測指紋": 入力["観測指紋"],
            "追加作用": "未実施（単純作用なし）", "能力評価": "未実施"}
    if 候補 and 初期.状態 == "NOT_FINISHED":
        番号 = 候補[0]
        生結果 = 環境.step(getattr(公式作用, f"ACTION{番号}"))
        if 生結果 is None:
            raise 確認失敗("公式環境が診断作用の観測を返しませんでした。")
        次 = 観測する(生結果, 観測通番=1)
        変化 = HDS観測入力(次, 初期, 番号)
        結果.update({"追加作用": f"ACTION{番号}を1回", "作用後状態": 次.状態,
                     "変化セル数": len(変化["最新盤面変化セル"])})
    return 結果


def オフラインを確認する(配布: Path, ゲーム: str) -> dict:
    # 競技での強制modeを上書きして迂回しない。ローカル診断は競技環境で実行しない。
    if os.getenv("OPERATION_MODE", "").strip().lower() == "competition":
        raise 確認失敗("Competition ModeではローカルOFFLINE診断を実行できません。")
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    ログ = logging.getLogger("arc3.environment-doctor")
    ログ.handlers = [logging.NullHandler()]
    ログ.propagate = False
    with TemporaryDirectory(prefix="arc3-offline-check-") as tmp:
        アーケード = Arcade(operation_mode=OperationMode.OFFLINE,
                         environments_dir=str((配布 / "environment_files").resolve()),
                         recordings_dir=tmp, logger=ログ)
        if アーケード.operation_mode != OperationMode.OFFLINE:
            raise 確認失敗("公式SDKがOFFLINEになっていません。")
        環境一覧 = アーケード.get_environments()
        if not 環境一覧:
            raise 確認失敗("公式SDKがローカル公開環境を検出できません。")
        識別子 = sorted(項目.game_id for 項目 in 環境一覧)[0] if ゲーム == "auto" else ゲーム
        try:
            環境 = アーケード.make(識別子, seed=0, save_recording=False)
            if 環境 is None:
                raise 確認失敗("指定した公開環境をローカルで生成できません。")
            return {"動作mode": "OFFLINE", "検出環境数": len(環境一覧),
                    **観測経路を確認する(環境, GameAction)}
        finally:
            アーケード.close_scorecard()


def Kaggleを確認する() -> dict:
    # import時も含めSDKの生ログを外へ出さない。資格情報や提出の内容は返さない。
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle import api

            応答 = api.competition_list_files(大会, page_size=1000)
            履歴 = api.competition_submissions(大会, page_size=1)
        return {"認証済み大会読取": "成功", "大会": 大会,
                "配布一覧件数": len(応答.files), "履歴読取": "成功",
                "履歴先頭ページ件数": len(履歴 or []), "競技提出": "未実施"}
    except (Exception, SystemExit) as エラー:
        状態 = getattr(getattr(エラー, "response", None), "status_code", None)
        if isinstance(状態, int):
            raise 確認失敗(f"Kaggle認証済み読取に失敗しました（HTTP {状態}）。") from None
        raise 確認失敗("Kaggle認証済み読取に失敗しました。利用者ホームの認証設定を確認してください。") from None


def main(argv: list[str] | None = None) -> int:
    引数解析 = argparse.ArgumentParser(description=__doc__)
    引数解析.add_argument("--data-dir", type=Path, default=ルート / "入力" / "Kaggle")
    引数解析.add_argument("--offline-game", nargs="?", const="auto", metavar="GAME_ID")
    引数解析.add_argument("--kaggle", action="store_true", help="認証済みの大会読取を実行")
    引数 = 引数解析.parse_args(argv)
    # python 道具/開発環境確認.py と module実行の両方で現行の接続層を参照する。
    if str(ルート) not in sys.path:
        sys.path.insert(0, str(ルート))
    結果 = {"状態": "合格", "対象": "ARC3開発環境", "検査": {}}
    検査 = [("版と読込", 版と読込を確認する), ("形式と描画", Parquetと描画を確認する),
            ("Kaggle配布", lambda: 配布を確認する(引数.data_dir))]
    if 引数.offline_game:
        検査.append(("公開環境のオフライン動作", lambda: オフラインを確認する(引数.data_dir, 引数.offline_game)))
    else:
        結果["公開環境の実行"] = "未実施（--offline-gameで実行）"
    if 引数.kaggle:
        検査.append(("Kaggle接続", Kaggleを確認する))
    else:
        結果["Kaggle外部通信"] = "未実施（--kaggleで実行）"
    for 名前, 実行 in 検査:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                内容 = 実行()
            結果["検査"][名前] = {"状態": "合格", **内容}
        except (Exception, SystemExit) as エラー:
            結果["状態"] = "不合格"
            詳細 = str(エラー) if isinstance(エラー, 確認失敗) else f"{type(エラー).__name__}（詳細ログは非表示）"
            結果["検査"][名前] = {"状態": "不合格", "理由": 詳細}
    print(json.dumps(結果, ensure_ascii=False, indent=2))
    return 0 if 結果["状態"] == "合格" else 1


if __name__ == "__main__":
    raise SystemExit(main())
