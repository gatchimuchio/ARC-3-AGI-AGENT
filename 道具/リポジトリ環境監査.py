#!/usr/bin/env python3
"""日本語基底ARC3 repositoryの最小環境契約を検証する。"""

from __future__ import annotations

import json
from pathlib import Path


ルート = Path(__file__).resolve().parents[1]

必須ファイル = (
    "README.md",
    "AGENTS.md",
    "制御/現在状態.json",
    "運用/権限順序.md",
    "運用/日本語基底方針.md",
    "運用/リポジトリ運用モデル.md",
    "設計/AGI三主体構成.md",
    "HDS/README.md",
    "ミニドラ/README.md",
    "記憶/README.md",
    "入力/README.md",
    "接続/README.md",
    "戦略/README.md",
    "検証/README.md",
)

旧正本禁止語 = (
    "ARC3_OFFICIAL_SAMPLE_GENERIC_COMPLETION_AGI_REV6",
    "R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE",
    "ARC3_GENERIC_COMPLETION_AGI_ROADMAP_REV6",
)


def 失敗(理由: str) -> None:
    raise SystemExit(f"リポジトリ環境監査失敗: {理由}")


def main() -> None:
    for 相対path in 必須ファイル:
        if not (ルート / 相対path).is_file():
            失敗(f"必須ファイル欠落: {相対path}")

    状態path = ルート / "制御/現在状態.json"
    try:
        状態 = json.loads(状態path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as 例外:
        失敗(f"現在状態を読めない: {例外}")

    if 状態.get("基底言語") != "日本語":
        失敗("基底言語が日本語ではない")
    if 状態.get("状態") != "再設計中":
        失敗("再初期化時点の状態が再設計中ではない")
    if 状態.get("戦略") is not None:
        失敗("戦略未選択契約に反する")
    if 状態.get("自動遷移") is not False:
        失敗("自動遷移は禁止")

    構成 = 状態.get("AGI構成", {})
    期待構成 = {
        "入力判断主体": "HDS",
        "LLM主体": "ミニドラ",
        "記憶主体": "記憶",
        "HDSコンパイラ管轄": "HDS",
    }
    if 構成 != 期待構成:
        失敗("AGI三主体構成が固定契約と不一致")

    安定文書 = (
        "README.md",
        "AGENTS.md",
        "運用/権限順序.md",
        "運用/日本語基底方針.md",
        "運用/リポジトリ運用モデル.md",
        "設計/AGI三主体構成.md",
    )
    for 相対path in 安定文書:
        本文 = (ルート / 相対path).read_text(encoding="utf-8")
        for 禁止語 in 旧正本禁止語:
            if 禁止語 in 本文:
                失敗(f"旧戦略の現在値が安定文書へ混入: {相対path}")

    print(
        json.dumps(
            {
                "状態": "合格",
                "基底言語": "日本語",
                "戦略": None,
                "AGI構成": "HDS + ミニドラ + 記憶",
                "必須ファイル数": len(必須ファイル),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
