"""公開Action応答要約をHDSへshadow学習させ、後半をread-onlyで採点する。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from hds学習系統 import HDS学習系統, 外部入力

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "出力/ARC3-RUN-002-local/C2-003-after-dev-seed-31.json"
DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C1-002-shadow-dev-seed-31.json"
境界 = "ARC-AGI-3公開Action応答"
条件経路 = ("条件", "Action番号")
結果経路群 = {
    "可視変化あり": ("結果", "可視変化あり"),
    "level進行あり": ("結果", "level進行あり"),
    "新規盤面あり": ("結果", "新規盤面あり"),
}


def _入力(応答: dict[str, Any], *, 結果を含む: bool) -> 外部入力:
    条件 = {"Action番号": int(応答["action_id"])}
    内容: dict[str, Any] = {"条件": 条件}
    if 結果を含む:
        内容["結果"] = {
            "可視変化あり": int(応答["changed_cells"]) > 0,
            "level進行あり": int(応答["level_delta"]) > 0,
            "新規盤面あり": bool(応答["new_visible_board"]),
        }
    return 外部入力(内容=内容, 対象系境界=境界)


def _予測群(結果: Any, 経路: tuple[str, ...]) -> set[Any]:
    return {
        項目["予測値"]
        for 項目 in 結果.内容.get("予測群", [])
        if tuple(項目.get("結果経路", ())) == 経路
    }


def _結果値(応答: dict[str, Any], 名称: str) -> bool:
    return {
        "可視変化あり": int(応答["changed_cells"]) > 0,
        "level進行あり": int(応答["level_delta"]) > 0,
        "新規盤面あり": bool(応答["new_visible_board"]),
    }[名称]


def _多数派(応答群: list[dict[str, Any]], 名称: str, action_id: int | None = None) -> bool | None:
    対象 = [
        応答 for 応答 in 応答群
        if action_id is None or int(応答["action_id"]) == action_id
    ]
    件数 = Counter(_結果値(応答, 名称) for 応答 in 対象)
    if not 件数 or len(件数) > 1 and len(set(件数.values())) == 1:
        return None
    return 件数.most_common(1)[0][0]


def _環境評価(応答群: list[dict[str, Any]], *, 学習比率: float) -> dict[str, Any]:
    action群 = [
        応答 for 応答 in 応答群
        if type(応答.get("action_id")) is int and 1 <= 応答["action_id"] <= 7
    ]
    分割 = max(1, min(len(action群) - 1, int(len(action群) * 学習比率)))
    訓練群, 照会群 = action群[:分割], action群[分割:]
    hds = HDS学習系統()
    状態数 = Counter()
    更新版 = []
    開始 = time.perf_counter()
    最終学習結果 = None

    for 応答 in 訓練群:
        結果 = hds.処理する(_入力(応答, 結果を含む=True))
        最終学習結果 = 結果
        状態数[結果.内容.get("学習成立状態", "不明")] += 1
        更新版.append(結果.内容.get("現在状態版", 0))

    学習後台帳件数 = hds.エンジン.台帳.件数("観測台帳")
    集計 = {
        名称: {
            "後半実測件数": {"False": 0, "True": 0},
            "照会": 0,
            "単一予測": 0,
            "正答": 0,
            "誤答": 0,
            "複数予測": 0,
            "予測値件数": {"False": 0, "True": 0},
            "多数派基準正答": 0,
            "多数派基準正答_HDScoverage": 0,
            "Action別多数派正答": 0,
            "Action別多数派適用件数": 0,
            "Action別多数派正答_HDScoverage": 0,
            "Action別多数派_HDScoverage適用件数": 0,
            "HDS予測に含まれるAction番号": set(),
        }
        for 名称 in 結果経路群
    }
    for 応答 in 照会群:
        結果 = hds.照会する(_入力(応答, 結果を含む=False))
        for 名称, 経路 in 結果経路群.items():
            実測 = _結果値(応答, 名称)
            行 = 集計[名称]
            行["後半実測件数"][str(実測)] += 1
            全体多数派 = _多数派(訓練群, 名称)
            Action多数派 = _多数派(訓練群, 名称, int(応答["action_id"]))
            if 全体多数派 is not None:
                行["多数派基準正答"] += int(全体多数派 == 実測)
            if Action多数派 is not None:
                行["Action別多数派正答"] += int(Action多数派 == 実測)
                行["Action別多数派適用件数"] += 1
            予測 = _予測群(結果, 経路)
            if not 予測:
                continue
            行["照会"] += 1
            if len(予測) != 1:
                行["複数予測"] += 1
                continue
            行["単一予測"] += 1
            if 全体多数派 is not None:
                行["多数派基準正答_HDScoverage"] += int(全体多数派 == 実測)
            if Action多数派 is not None:
                行["Action別多数派正答_HDScoverage"] += int(Action多数派 == 実測)
                行["Action別多数派_HDScoverage適用件数"] += 1
            値 = next(iter(予測))
            行["予測値件数"][str(bool(値))] += 1
            行["HDS予測に含まれるAction番号"].add(int(応答["action_id"]))
            行["正答" if 値 == 実測 else "誤答"] += 1

    for 行 in 集計.values():
        行["HDS予測に含まれるAction番号"] = sorted(行["HDS予測に含まれるAction番号"])

    台帳件数 = hds.エンジン.台帳.件数("観測台帳")
    最終内容 = {} if 最終学習結果 is None else 最終学習結果.内容
    return {
        "学習Action数": len(訓練群),
        "後半照会Action数": len(照会群),
        "学習後経験台帳件数": 学習後台帳件数,
        "照会後経験台帳件数": 台帳件数,
        "学習状態分布": dict(sorted(状態数.items())),
        "状態版の最終": max(更新版, default=0),
        "最終有効原理群": [
            {
                "関係型": 原理.get("関係型"),
                "条件経路群": 原理.get("条件経路群"),
                "結果経路": 原理.get("結果経路"),
                "採用状態": 原理.get("採用状態"),
            }
            for 原理 in 最終内容.get("有効原理群", [])
        ],
        "最終有効原理数": len(最終内容.get("有効原理群", [])),
        "最終学習予測数": len(最終内容.get("予測群", [])),
        "後半予測": 集計,
        "経過秒": round(time.perf_counter() - 開始, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--train-fraction", type=float, default=0.75)
    args = parser.parse_args()
    if not 0.5 <= args.train_fraction < 1.0:
        parser.error("--train-fraction must be in [0.5, 1.0)")

    原票 = args.input.read_bytes()
    入力 = json.loads(原票.decode("utf-8"))
    結果 = {
        "評価": "公開Action応答のHDS shadow学習",
        "入力SHA256": hashlib.sha256(原票).hexdigest(),
        "訓練比率": args.train_fraction,
        "入力特徴": ["条件.Action番号", *[f"結果.{名前}" for 名前 in 結果経路群]],
        "除外": ["RESET", "game_id", "level_id", "GUID", "観測指紋", "盤面", "座標", "色番号", "trajectory"],
        "環境": [
            _環境評価(ゲーム["exploration"]["action_responses"], 学習比率=args.train_fraction)
            for ゲーム in 入力["games"]
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(結果, ensure_ascii=False, indent=2).encode("utf-8")
    args.output.write_bytes(raw)
    print(json.dumps({
        "environment_count": len(結果["環境"]),
        "input_sha256": 結果["入力SHA256"],
        "output": str(args.output),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": 結果["環境"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
