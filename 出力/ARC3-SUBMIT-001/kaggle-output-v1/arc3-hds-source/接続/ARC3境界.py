"""ARC-AGI-3の公開FrameData/GameActionとHDS判断の間に置く、戦略非依存の境界。

観測は外部の事実として保存し、HDSが確定した作用だけを外部SDKへ排出する。
このモジュール自身は作用の選択・学習・ゲーム別攻略を行わない。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


class 境界違反(ValueError):
    """不正な観測または未確定・不正なActionを検出した。"""


def _属性(対象: Any, 名前: str, 既定: Any = None) -> Any:
    if isinstance(対象, Mapping):
        return 対象.get(名前, 既定)
    return getattr(対象, 名前, 既定)


def _列(値: Any, 項目: str) -> list | tuple:
    if hasattr(値, "tolist"):
        値 = 値.tolist()
    if not isinstance(値, (list, tuple)):
        raise 境界違反(f"{項目}は配列でなければならない")
    return 値


def _整数(値: Any, 項目: str, 最小: int, 最大: int | None = None) -> int:
    if type(値) is not int or 値 < 最小 or (最大 is not None and 値 > 最大):
        raise 境界違反(f"{項目}の範囲または型が不正")
    return 値


def _作用番号(値: Any) -> int:
    if hasattr(値, "name"):
        値 = 値.name
    if isinstance(値, str):
        if 値 == "RESET":
            return 0
        if 値.startswith("ACTION") and 値[6:] in {str(x) for x in range(1, 8)}:
            return int(値[6:])
    return _整数(値, "available_actions", 0, 7)


def _盤面列(元: Any) -> tuple[tuple[tuple[int, ...], ...], ...]:
    if 元 is None:
        return ()
    結果 = []
    for 層 in _列(元, "frame"):
        行群 = []
        for 行 in _列(層, "frameの層"):
            画素群 = tuple(_整数(画素, "画素", 0, 15) for 画素 in _列(行, "frameの行"))
            if not 画素群 or len(画素群) > 64:
                raise 境界違反("盤面の横幅が公式範囲外")
            行群.append(画素群)
        if not 1 <= len(行群) <= 64 or len({len(行) for 行 in 行群}) != 1:
            raise 境界違反("盤面の高さまたは行幅が不正")
        結果.append(tuple(行群))
    return tuple(結果)


@dataclass(frozen=True)
class 観測:
    ゲーム識別子: str
    観測通番: int
    状態: str
    完了レベル数: int
    全レベル数: int
    作用可能番号: tuple[int, ...]
    盤面列: tuple[tuple[tuple[int, ...], ...], ...]
    全初期化: bool
    実行識別子: str | None
    指紋: str

    @property
    def 最新盤面(self) -> tuple[tuple[int, ...], ...]:
        return self.盤面列[-1] if self.盤面列 else ()


@dataclass(frozen=True)
class HDS確定作用:
    """HDS判定系が発行する形式。未確認の自己申告を検証済みと見なさない。"""

    観測指紋: str
    作用番号: int
    根拠参照: str
    判定: str = "未確定"
    引数: Mapping[str, Any] = field(default_factory=dict)


def 観測する(生観測: Any, *, 観測通番: int) -> 観測:
    """公式FrameData等を検査して複製する。通番は実行側で単調増加させる。

    盤面が変化しなくてもhidden stateが変化し得るため、観測値だけを指紋にしない。
    """
    _整数(観測通番, "観測通番", 0)
    状態 = _属性(生観測, "state")
    状態 = getattr(状態, "name", 状態)
    if 状態 not in ("NOT_PLAYED", "NOT_FINISHED", "WIN", "GAME_OVER"):
        raise 境界違反("未知の公式状態")
    ゲーム識別子 = _属性(生観測, "game_id") or ""
    if not isinstance(ゲーム識別子, str):
        raise 境界違反("game_idの型が不正")
    if 状態 != "NOT_PLAYED" and not ゲーム識別子:
        raise 境界違反("進行後のゲーム識別子が欠落")
    完了数 = _整数(_属性(生観測, "levels_completed", 0), "levels_completed", 0)
    全数 = _整数(_属性(生観測, "win_levels", 0), "win_levels", 0)
    if 全数 and 完了数 > 全数:
        raise 境界違反("レベル完了数が全レベル数を超過")
    生作用可能 = _属性(生観測, "available_actions")
    if 生作用可能 is None and 状態 == "NOT_PLAYED":
        生作用可能 = []
    作用可能 = tuple(_作用番号(x) for x in _列(生作用可能, "available_actions"))
    if len(作用可能) != len(set(作用可能)):
        raise 境界違反("使用可能作用の重複")
    盤面列 = _盤面列(_属性(生観測, "frame"))
    if 状態 == "NOT_FINISHED" and not 盤面列:
        raise 境界違反("進行中の盤面が欠落")
    全初期化 = _属性(生観測, "full_reset", False)
    if type(全初期化) is not bool:
        raise 境界違反("full_resetの型が不正")
    実行識別子 = _属性(生観測, "guid")
    if 実行識別子 is not None and not isinstance(実行識別子, str):
        raise 境界違反("guidの型が不正")
    原票 = (ゲーム識別子, 観測通番, 状態, 完了数, 全数, 作用可能, 盤面列, 全初期化, 実行識別子)
    指紋 = sha256(json.dumps(原票, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return 観測(ゲーム識別子, 観測通番, 状態, 完了数, 全数, 作用可能, 盤面列, 全初期化, 実行識別子, 指紋)


def HDS観測入力(現在: 観測, 直前: 観測 | None = None, 直前作用番号: int | None = None) -> dict[str, Any]:
    """全フレームを保持し、最新盤面差分と状態遷移を区別して出力する。"""
    if 直前 is not None and 直前.ゲーム識別子 != 現在.ゲーム識別子:
        raise 境界違反("異なるゲーム間の状態差分は形成できない")
    if 直前 is not None and 直前.観測通番 >= 現在.観測通番:
        raise 境界違反("観測通番の順序が不正")
    if 直前 is None and 直前作用番号 is not None:
        raise 境界違反("対応する直前観測のない作用を関連付けできない")
    if 直前作用番号 is not None:
        _整数(直前作用番号, "直前作用番号", 0, 7)
    比較可能 = bool(直前 is not None and not 現在.全初期化
                 and 直前.実行識別子 == 現在.実行識別子
                 and len(直前.最新盤面) == len(現在.最新盤面)
                 and all(len(a) == len(b) for a, b in zip(直前.最新盤面, 現在.最新盤面)))
    変化群: list[list[int]] = []
    if 比較可能:
        for y, (旧行, 新行) in enumerate(zip(直前.最新盤面, 現在.最新盤面)):
            for x, (旧値, 新値) in enumerate(zip(旧行, 新行)):
                if 旧値 != 新値:
                    変化群.append([x, y, 旧値, 新値])
    return {
        "外部境界": "ARC-AGI-3",
        "ゲーム識別子": 現在.ゲーム識別子,  # 出所識別。作用決定に使用しない
        "観測通番": 現在.観測通番,
        "現在状態": 現在.状態,
        "完了レベル数": 現在.完了レベル数,
        "全レベル数": 現在.全レベル数,
        "作用可能番号": list(現在.作用可能番号),
        "盤面フレーム列": [[list(行) for 行 in 層] for 層 in 現在.盤面列],
        "観測指紋": 現在.指紋,
        "状態遷移": None if 直前 is None else [直前.状態, 現在.状態],
        "完了レベル増分": None if 直前 is None else 現在.完了レベル数 - 直前.完了レベル数,
        "最新盤面比較可能": 比較可能,
        "最新盤面変化セル": 変化群,
        "直前作用番号": 直前作用番号,  # 時間的先行のみ。因果確定ではない
        "全初期化": 現在.全初期化,
    }


def 作用を排出する(現在: 観測, 判断: HDS確定作用, 公式GameAction: Any, 環境: Any) -> Any:
    """HDS確定・合法性を照合し、SDKのstepへリクエスト単位で送る。

    GameActionは共有enumのためset_data/reasoningで変異させない。
    """
    if 判断.判定 != "確定" or not isinstance(判断.根拠参照, str) or not 判断.根拠参照.strip():
        raise 境界違反("HDS確定根拠がないため作用は保留")
    if len(判断.根拠参照.encode("utf-8")) > 4096:
        raise 境界違反("根拠参照が外部転送上限を超過")
    if 判断.観測指紋 != 現在.指紋:
        raise 境界違反("古い観測に対する作用は排出できない")
    番号 = _整数(判断.作用番号, "作用番号", 0, 7)
    if 現在.状態 == "WIN":
        raise 境界違反("終了したゲームには作用できない")
    if 番号 not in 現在.作用可能番号 and not (
        番号 == 0 and 現在.状態 in ("NOT_PLAYED", "GAME_OVER")
    ):
        raise 境界違反("現在の公式available_actionsに含まれない")
    if not isinstance(判断.引数, Mapping):
        raise 境界違反("Action引数の型が不正")
    if 番号 == 6:
        if set(判断.引数) != {"x", "y"}:
            raise 境界違反("座標Actionはx,yの指定が必要")
        引数 = {key: _整数(判断.引数[key], key, 0, 63) for key in ("x", "y")}
    else:
        if 判断.引数:
            raise 境界違反("単純Actionには引数を渡さない")
        引数 = {}
    名前 = "RESET" if 番号 == 0 else f"ACTION{番号}"
    try:
        作用 = getattr(公式GameAction, 名前)
        送信 = 環境.step
    except AttributeError as エラー:
        raise 境界違反("外部SDKのAction契約と一致しない") from エラー
    # APIへのリクエストごとに新しい辞書を渡し、Enum上に座標や根拠が残らないようにする。
    return 送信(作用, data=引数, reasoning={"HDS根拠参照": 判断.根拠参照, "観測指紋": 現在.指紋})
