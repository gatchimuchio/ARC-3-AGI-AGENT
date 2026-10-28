"""図式攻略用の純粋な画面観測。学習/解答/作用選択を含まない。

未採用診断から利用中の2つの純粋関数だけを分離し、旧実験への依存を持たない。
"""
from collections import deque

def _作用番号(値):
    if 値 == "RESET":
        return 0
    if isinstance(値, str) and 値.startswith("ACTION"):
        値 = int(値[6:])
    if type(値) is not int or not 0 <= 値 <= 7:
        raise ValueError("未知の作用番号")
    return 値


def 成分群(盤面):
    残 = {(x,y) for y in range(len(盤面)) for x in range(len(盤面[y]))}
    結果 = []
    # min(残) を成分ごとに繰り返すと、微小成分が多い盤面では二乗時間になる。
    # 最初に一度だけ同じ順序へ並べ、探索済みの点を飛ばす。
    for 始 in sorted(残):
        if 始 not in 残:
            continue
        色 = 盤面[始[1]][始[0]]
        点群,待機 = {始},deque([始])
        残.remove(始)
        while 待機:
            x,y = 待機.popleft()
            for 点 in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 点 in 残 and 盤面[点[1]][点[0]] == 色:
                    残.remove(点)
                    点群.add(点)
                    待機.append(点)
        左,上 = min(x for x,y in 点群),min(y for x,y in 点群)
        形 = tuple(sorted((x-左,y-上) for x,y in 点群))
        結果.append({"対応鍵":(色,形),"位置":(左,上),"点群":frozenset(点群)})
    return 結果

