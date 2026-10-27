"""既存の公開HDS状態が提出agentの共通候補経路へ移植可能かを匿名監査する。"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "HDS" / "学習系統" / "v0.4.2")]

from hds学習系統 import HDS学習系統  # noqa: E402
from 接続.ARC3境界 import 観測する  # noqa: E402
from 接続.共通観測経路 import 公開観測から候補を照会する  # noqa: E402


def _展開HDS(path: Path) -> HDS学習系統:
    raw = gzip.decompress(path.read_bytes())
    with tempfile.TemporaryDirectory(prefix="arc3-prior-audit-") as folder:
        state_path = Path(folder) / "state.json"
        state_path.write_bytes(raw)
        return HDS学習系統.読み込む(state_path)


def _配色観測() -> dict[str, Any]:
    path = ROOT / "入力" / "配色教師" / "公開原票.json.gz"
    packs = json.loads(gzip.decompress(path.read_bytes()))
    for pack in packs:
        for row in pack["全行"]:
            data = row["data"]
            if data.get("state") == "NOT_FINISHED" and data.get("frame"):
                return data
    raise ValueError("配色の進行中公開観測がありません")


def _鏡像観測() -> dict[str, Any]:
    path = ROOT / "入力" / "鏡像教師" / "全公開原票.json.gz"
    packs = json.loads(gzip.decompress(path.read_bytes()))
    for group in packs.values():
        for row in group["原票"]:
            if row.get("state") == "NOT_FINISHED" and row.get("frame"):
                return row
    raise ValueError("鏡像の進行中公開観測がありません")


def _境界観測(raw: dict[str, Any]):
    # IDは探索・候補選択へ渡さず、境界形式を満たすfixture値だけを与える。
    public = {
        "game_id": "fixture",
        "state": raw["state"],
        "frame": raw["frame"],
        "available_actions": raw["available_actions"],
        "levels_completed": 0,
        "win_levels": 1,
        "guid": "fixture",
        "full_reset": False,
    }
    return 観測する(public, 観測通番=0)


def _照会(label: str, observation_label: str, system: HDS学習系統, raw: dict[str, Any]) -> dict[str, Any]:
    observation = _境界観測(raw)
    result = 公開観測から候補を照会する(system, observation)
    return {
        "HDS種別": label,
        "観測種別": observation_label,
        "状態": result.get("状態"),
        "作用候補数": len(result.get("次作用候補群", [])),
        "語彙別": [
            {
                "語彙": item["語彙"],
                "適用性": item["結果"].get("適用性", {}).get("状態"),
                "作用候補数": len(item["結果"].get("作用候補群", [])),
            }
            for item in result.get("語彙別結果", [])
        ],
        "実行許可": result.get("実行許可"),
    }


def main() -> int:
    observations = [("配色", _配色観測()), ("鏡像", _鏡像観測())]
    states = {
        "空": HDS学習系統(),
        "配色": _展開HDS(ROOT / "入力" / "配色教師" / "保存HDS.json.gz"),
        "鏡像": _展開HDS(ROOT / "入力" / "鏡像教師" / "保存HDS.json.gz"),
    }
    reports = []
    for observation_label, target in observations:
        for label, system in states.items():
            reports.append(_照会(label, observation_label, system, target))
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
