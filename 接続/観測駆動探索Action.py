"""HDS判断と分離した、公開観測だけに基づくオンライン探索Action方針。"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any

from 接続.ARC3境界 import 境界違反, 観測


@dataclass(frozen=True)
class 探索Action:
    """候補/HDS確定と混同しない、1回分の探索出所付きAction。"""

    作用番号: int
    引数: dict[str, int]
    出所: str = "観測駆動探索"

    @property
    def name(self) -> str:
        return "RESET" if self.作用番号 == 0 else f"ACTION{self.作用番号}"


class 観測駆動探索方針:
    """公開盤面・合法Action・直前の公開応答から、次の一手だけを選ぶ。

    ゲーム識別子、HDS候補、問題回答は選択に使わない。応答の進捗と可視変化を
    同一run内のAction番号ごとに集計し、合法集合内のUCB値で次のActionを選ぶ。
    座標Actionは現盤面の最多色以外の未試行セルを先に調べる。
    """

    def __init__(
        self,
        *,
        乱数種: int | None = None,
        探索係数: float = 0.8,
        色探索係数: float | None = None,
        可視変化係数: float = 0.25,
        レベル進行報酬: float = 4.0,
        座標Action初手優先: bool = False,
        同盤無変化Action回避: bool = False,
    ) -> None:
        if not math.isfinite(探索係数) or 探索係数 <= 0:
            raise ValueError("探索係数は有限の正数でなければならない")
        if 色探索係数 is not None and (not math.isfinite(色探索係数) or 色探索係数 <= 0):
            raise ValueError("色探索係数は有限の正数でなければならない")
        if not math.isfinite(可視変化係数) or 可視変化係数 < 0:
            raise ValueError("可視変化係数は有限の非負数でなければならない")
        if not math.isfinite(レベル進行報酬) or レベル進行報酬 < 0:
            raise ValueError("レベル進行報酬は有限の非負数でなければならない")
        if type(座標Action初手優先) is not bool:
            raise ValueError("座標Action初手優先はboolでなければならない")
        if type(同盤無変化Action回避) is not bool:
            raise ValueError("同盤無変化Action回避はboolでなければならない")
        self._rng = random.Random(乱数種)
        self._探索係数 = 探索係数
        self._色探索係数 = 探索係数 if 色探索係数 is None else 色探索係数
        self._可視変化係数 = 可視変化係数
        self._レベル進行報酬 = レベル進行報酬
        self._座標Action初手優先 = 座標Action初手優先
        self._同盤無変化Action回避 = 同盤無変化Action回避
        self._回数: dict[int, int] = {}
        self._報酬合計: dict[int, float] = {}
        self._総作用数 = 0
        self._既観測盤面: set[tuple[tuple[int, ...], ...]] = set()
        self._座標試行: dict[tuple[tuple[int, ...], ...], set[tuple[int, int]]] = {}
        self._色回数: dict[int, int] = {}
        self._色報酬合計: dict[int, float] = {}
        self._選択座標色: int | None = None
        self._直近の選択: tuple[観測, 探索Action] | None = None
        self._同盤無変化Action: set[tuple[tuple[tuple[int, ...], ...], int]] = set()

    def 選ぶ(
        self,
        現在: 観測,
        *,
        HDS優先作用番号群: tuple[int, ...] = (),
    ) -> 探索Action | None:
        if 現在.状態 in ("NOT_PLAYED", "GAME_OVER"):
            return 探索Action(0, {}, 出所="SDKリセット")
        if 現在.状態 != "NOT_FINISHED":
            return None
        if 現在.最新盤面:
            self._既観測盤面.add(現在.最新盤面)
        合法 = tuple(sorted(a for a in 現在.作用可能番号 if 1 <= a <= 7))
        if not 合法:
            return None
        if self._同盤無変化Action回避:
            代替可能 = tuple(
                action
                for action in 合法
                if action == 6 or (現在.最新盤面, action) not in self._同盤無変化Action
            )
            if 代替可能:
                合法 = 代替可能

        # HDS contributes a ranking hint only. Keep SDK-legal and policy-filtered
        # actions as the authority; empty hints preserve the existing UCB path.
        hds_preferred = {
            action for action in HDS優先作用番号群 if type(action) is int and action in 合法
        }
        prioritized = tuple(action for action in 合法 if action in hds_preferred)
        if prioritized:
            合法 = prioritized

        # 未試行Actionを先に一度ずつ調べ、その後は公開応答から得たUCB値で選ぶ。
        未試行 = [a for a in 合法 if self._回数.get(a, 0) == 0]
        先行座標 = None
        if 未試行:
            if self._座標Action初手優先 and 6 in 未試行:
                先行座標 = self._座標を選ぶ(現在.最新盤面)
            作用番号 = 6 if 先行座標 is not None else self._rng.choice(未試行)
        else:
            log_total = math.log(max(2, self._総作用数))
            値 = {
                a: self._報酬合計[a] / self._回数[a]
                + self._探索係数 * math.sqrt(log_total / self._回数[a])
                + self._追加行動価値(現在, a)
                for a in 合法
            }
            最大 = max(値.values())
            作用番号 = self._rng.choice([a for a in 合法 if 値[a] == 最大])

        引数: dict[str, int] = {}
        self._選択座標色 = None
        if 作用番号 == 6:
            座標 = 先行座標 or self._座標を選ぶ(現在.最新盤面)
            if 座標 is None:
                return None
            引数 = {"x": 座標[0], "y": 座標[1]}
            self._選択座標色 = 座標[2]
        action = 探索Action(作用番号, 引数)
        self._直近の選択 = (現在, action)
        return action

    def 応答を記録する(self, 作用前: 観測, action: 探索Action, 作用後: 観測) -> dict[str, Any]:
        """作用前後の公開観測のみを記録し、次回の選択値を更新する。"""
        if action.出所 != "観測駆動探索":
            raise 境界違反("探索以外の出所を探索方針へ記録できない")
        if 作用前.状態 != "NOT_FINISHED" or 作用後.状態 not in ("NOT_FINISHED", "WIN", "GAME_OVER"):
            raise 境界違反("探索Actionの前後状態が不正")
        if action.作用番号 not in 作用前.作用可能番号:
            raise 境界違反("Actionが作用前観測の合法集合にない")
        if action.作用番号 == 6:
            if set(action.引数) != {"x", "y"}:
                raise 境界違反("座標Actionにx,yが必要")
            x, y = action.引数["x"], action.引数["y"]
            if type(x) is not int or type(y) is not int or not (0 <= x < 64 and 0 <= y < 64):
                raise 境界違反("座標Actionが公式範囲外")
        elif action.引数:
            raise 境界違反("単純Actionに引数を付けられない")
        if self._直近の選択 != (作用前, action):
            raise 境界違反("現在選択中のActionと作用応答が一致しない")

        前盤面 = 作用前.最新盤面
        後盤面 = 作用後.最新盤面
        変化数 = self._変化セル数(前盤面, 後盤面)
        比較面積 = max(1, sum(len(row) for row in 前盤面))
        増分 = max(0, 作用後.完了レベル数 - 作用前.完了レベル数)
        if (
            self._同盤無変化Action回避
            and 1 <= action.作用番号 <= 7
            and action.作用番号 != 6
            and 変化数 == 0
            and 増分 == 0
        ):
            self._同盤無変化Action.add((前盤面, action.作用番号))
        新盤面 = bool(後盤面) and 後盤面 not in self._既観測盤面
        報酬 = self._レベル進行報酬 * 増分 + (0.5 if 新盤面 else 0.0)
        報酬 += self._可視変化係数 * min(1.0, 変化数 / 比較面積)
        if 変化数 == 0 and 増分 == 0:
            報酬 -= 1.0

        self._回数[action.作用番号] = self._回数.get(action.作用番号, 0) + 1
        self._報酬合計[action.作用番号] = self._報酬合計.get(action.作用番号, 0.0) + 報酬
        色 = self._選択座標色
        if action.作用番号 == 6:
            if 色 is None:
                raise 境界違反("座標Actionの可視色出所がない")
            self._色回数[色] = self._色回数.get(色, 0) + 1
            self._色報酬合計[色] = self._色報酬合計.get(色, 0.0) + 報酬
        self._総作用数 += 1
        if 前盤面:
            self._既観測盤面.add(前盤面)
        if 後盤面:
            self._既観測盤面.add(後盤面)
        self._直近の選択 = None
        self._選択座標色 = None
        return {
            "出所": action.出所,
            "作用番号": action.作用番号,
            "作用前状態": 作用前.状態,
            "作用後状態": 作用後.状態,
            "完了レベル増分": 増分,
            "可視変化セル数": 変化数,
            "盤面新規性": 新盤面,
            "座標可視色": 色,
            "公開応答報酬": 報酬,
        }

    def _追加行動価値(self, 現在: 観測, 作用番号: int) -> float:
        """評価用policyが汎用状態価値を加算する拡張点。標準方針では0。"""
        del 現在, 作用番号
        return 0.0

    def 統計(self) -> dict[int, dict[str, float | int]]:
        return {
            action: {
                "回数": count,
                "平均公開報酬": self._報酬合計[action] / count,
            }
            for action, count in sorted(self._回数.items())
        }

    def _座標を選ぶ(self, 盤面: tuple[tuple[int, ...], ...]) -> tuple[int, int, int] | None:
        if not 盤面 or len(盤面) > 64 or any(not row or len(row) > 64 for row in 盤面):
            return None
        色座標: dict[int, list[tuple[int, int]]] = {}
        for y, row in enumerate(盤面):
            for x, color in enumerate(row):
                色座標.setdefault(color, []).append((x, y))
        色候補 = sorted(色座標)
        試行済み = self._座標試行.setdefault(盤面, set())
        未試行色座標 = {
            color: [point for point in 色座標[color] if point not in 試行済み] for color in 色候補
        }
        適格色 = [color for color in 色候補 if 未試行色座標[color]]
        if not 適格色:
            return None

        未試行色 = [color for color in 適格色 if self._色回数.get(color, 0) == 0]
        if 未試行色:
            color = self._rng.choice(未試行色)
        else:
            total = max(2, sum(self._色回数.values()))
            values = {
                color: self._色報酬合計[color] / self._色回数[color]
                + self._色探索係数 * math.sqrt(math.log(total) / self._色回数[color])
                for color in 適格色
            }
            best = max(values.values())
            color = self._rng.choice([color for color in 適格色 if values[color] == best])

        point = self._未試行座標を選ぶ(盤面, color, 未試行色座標[color])
        試行済み.add(point)
        return point[0], point[1], color

    def _未試行座標を選ぶ(
        self,
        盤面: tuple[tuple[int, ...], ...],
        色: int,
        未試行座標: list[tuple[int, int]],
    ) -> tuple[int, int]:
        """評価用座標方針の拡張点。標準方針は既存どおり一様抽選する。"""
        del 盤面, 色
        return self._rng.choice(未試行座標)

    @staticmethod
    def _変化セル数(前: tuple[tuple[int, ...], ...], 後: tuple[tuple[int, ...], ...]) -> int:
        if not 前 or not 後 or len(前) != len(後):
            return max(1, len(前) + len(後)) if 前 != 後 else 0
        return sum(
            1
            for old_row, new_row in zip(前, 後)
            for x in range(max(len(old_row), len(new_row)))
            if x >= len(old_row) or x >= len(new_row) or old_row[x] != new_row[x]
        )
