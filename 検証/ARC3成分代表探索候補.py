"""評価用：基準点の同色連結成分から公開画素上の代表点を選ぶ。"""

from __future__ import annotations

from collections.abc import Sequence

from 接続.図式観測 import 成分群


def 代表座標(
    盤面: Sequence[Sequence[int]],
    色: int,
    未試行座標: Sequence[tuple[int, int]],
    基準座標: tuple[int, int],
) -> tuple[tuple[int, int], str]:
    """基準点の成分内の未試行代表画素を返す。使えない場合は基準点へ戻る。

    成分は画素の連結性を示すだけで、物体や目標とはみなさない。
    呼出側は基準点を既存方針の乱数で先に選び、合法性を検査する。
    """
    未試行 = set(未試行座標)
    x, y = 基準座標
    if (
        基準座標 not in 未試行
        or not 0 <= y < len(盤面)
        or not 0 <= x < len(盤面[y])
        or 盤面[y][x] != 色
    ):
        return 基準座標, "基準不正"

    成分 = next((項目["点群"] for 項目 in 成分群(盤面) if 基準座標 in 項目["点群"]), None)
    面積 = sum(len(row) for row in 盤面)
    if not 成分 or len(成分) == 1 or len(成分) == 面積:
        return 基準座標, "区別不能"

    件数 = len(成分)
    合計x = sum(px for px, _ in 成分)
    合計y = sum(py for _, py in 成分)
    重心近傍 = min(
        成分,
        key=lambda 点: (
            (点[0] * 件数 - 合計x) ** 2 + (点[1] * 件数 - 合計y) ** 2,
            点[1],
            点[0],
        ),
    )
    候補 = (
        重心近傍,
        min(成分, key=lambda 点: (点[0], 点[1])),
        min(成分, key=lambda 点: (-点[0], 点[1])),
        min(成分, key=lambda 点: (点[1], 点[0])),
        min(成分, key=lambda 点: (-点[1], 点[0])),
    )
    for 点 in dict.fromkeys(候補):
        if 点 in 未試行:
            return 点, "代表点"
    return 基準座標, "代表点試行済み"
