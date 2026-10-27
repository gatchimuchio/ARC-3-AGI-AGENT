"""専用配色・鏡像接続の候補を匿名集計し、HOLDのまま保持する。"""
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
from 接続.配色接続 import 配色候補を作る  # noqa: E402
from 接続.鏡像接続 import 鏡像候補を作る  # noqa: E402


def _HDSを読む(path: Path) -> HDS学習系統:
    raw = gzip.decompress(path.read_bytes())
    with tempfile.TemporaryDirectory(prefix="arc3-special-prior-audit-") as folder:
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


def _集計(接続: str, 観測: str, result: dict[str, Any]) -> dict[str, Any]:
    actions = result.get("作用候補群", [])
    return {
        "connector": 接続,
        "observation": 観測,
        "candidate_count": len(actions),
        "hold_count": sum(action.get("状態") == "HOLD" for action in actions),
        "other_state_count": sum(action.get("状態") != "HOLD" for action in actions),
        "permission": result.get("実行許可"),
    }


def main() -> int:
    palette = _配色観測()
    mirror = _鏡像観測()
    palette_state = _HDSを読む(ROOT / "入力" / "配色教師" / "保存HDS.json.gz")
    mirror_state = _HDSを読む(ROOT / "入力" / "鏡像教師" / "保存HDS.json.gz")

    checks = [
        (
            "palette",
            "palette",
            配色候補を作る(palette["frame"][0], palette["available_actions"], palette_state),
        ),
        (
            "mirror",
            "mirror",
            鏡像候補を作る(mirror["frame"][0], mirror["available_actions"], mirror_state),
        ),
        (
            "mirror",
            "palette",
            鏡像候補を作る(palette["frame"][0], palette["available_actions"], mirror_state),
        ),
    ]
    print(json.dumps([_集計(*check) for check in checks], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
