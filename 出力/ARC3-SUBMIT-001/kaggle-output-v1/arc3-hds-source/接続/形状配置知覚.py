"""画素/初期形状のみの固定知覚。HDS学習・正解・個体IDを参照しない。"""
from collections import Counter as 頻度表, deque as 待ち行列
from .図式観測 import 成分群

def 外接矩形(画素群):
    return (min((x for x, y in 画素群)), min((y for x, y in 画素群)), max((x for x, y in 画素群)), max((y for x, y in 画素群)))

def 正規形(画素群):
    x, y, _, _ = 外接矩形(画素群)
    return tuple(sorted(((候補 - x, 要素 - y) for 候補, 要素 in 画素群)))

def 閉領域(画素群):
    x, y, X, Y = 外接矩形(画素群)
    domain = {(候補, 要素) for 候補 in range(x - 1, X + 2) for 要素 in range(y - 1, Y + 2)}
    参照値 = [(x - 1, y - 1)]
    outside = set(参照値)
    for 候補, 要素 in 参照値:
        for p in [(候補 - 1, 要素), (候補 + 1, 要素), (候補, 要素 - 1), (候補, 要素 + 1)]:
            if p in domain and p not in 画素群 and (p not in outside):
                outside.add(p)
                参照値.append(p)
    return domain - outside - set(画素群)

def 単色対象を読む(盤面):
    対象群 = []
    目標群 = []
    for 成分 in 成分群(盤面):
        色 = 成分['対応鍵'][0]
        画素群 = set(成分['点群'])
        内側 = 閉領域(画素群)
        if 色 in (14, 11):
            全域 = 画素群 | 内側
            対象群.append({'色': 色, '点': 全域, '形': 正規形(全域), '位置': 外接矩形(全域)[:2], '選択': any((盤面[y][x] == 0 for x, y in 内側)), '役割': '輪郭内マーカーを持つ操作図形候補' if 色 == 14 else '充填図形候補'})
        if 色 == 4 and 内側:
            目標群.append({'点': 内側, '形': 正規形(内側), '位置': 外接矩形(内側)[:2], '外枠': 画素群, '役割': '閉輪郭目標候補'})
    return {'対象': 対象群, '目標': 目標群}

def 初期対象を読む(盤面):
    場面 = 単色対象を読む(盤面)
    場面['対象'] = [対象 for 対象 in 場面['対象'] if 対象['色'] != 14]
    端白群 = set()
    for 成分 in 成分群(盤面):
        if 成分['対応鍵'][0] == 0 and any((x in (0, len(盤面[0]) - 1) or y in (0, len(盤面) - 1) for x, y in 成分['点群'])):
            端白群 |= set(成分['点群'])
    未処理 = {(x, y) for y, row in enumerate(盤面) for x, 成分 in enumerate(row) if 成分 in (14, 0) and (x, y) not in 端白群}
    while 未処理:
        始点 = min(未処理)
        未処理.remove(始点)
        画素群 = {始点}
        参照値 = [始点]
        for x, y in 参照値:
            for p in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
                if p in 未処理:
                    未処理.remove(p)
                    画素群.add(p)
                    参照値.append(p)
        if not any((盤面[y][x] == 14 for x, y in 画素群)):
            continue
        全域 = 画素群 | 閉領域(画素群)
        場面['対象'].append({'色': 14, '点': 全域, '形': 正規形(全域), '位置': 外接矩形(全域)[:2], '選択': any((盤面[y][x] == 0 for x, y in 画素群)), '役割': 'マーカーを含む色連結図形候補', '知覚由来': '色14と選択白0の和集合、閉領域充填'})
    場面['対象'].sort(key=lambda 対象: 対象['位置'])
    return 場面

def 形状場面を読む(盤面):
    場面 = 初期対象を読む(盤面)
    for 成分 in 成分群(盤面):
        if 成分['対応鍵'][0] != 4 or 閉領域(成分['点群']):
            continue
        画素群 = set(成分['点群'])
        x, y, X, Y = 外接矩形(画素群)
        if X - x < 2 or Y - y < 2:
            continue
        外枠 = {(候補, 要素) for 候補 in range(x, X + 1) for 要素 in range(y, Y + 1) if 候補 in (x, X) or 要素 in (y, Y)}
        if not 画素群 <= 外枠:
            continue
        未観測 = 外枠 - 画素群
        辺群 = [{(候補, y) for 候補 in range(x, X + 1)}, {(候補, Y) for 候補 in range(x, X + 1)}, {(x, 要素) for 要素 in range(y, Y + 1)}, {(X, 要素) for 要素 in range(y, Y + 1)}]
        if sum((s <= 画素群 for s in 辺群)) < 3 or not 未観測 or (not all((盤面[要素][候補] not in (1, 2, 4) for 候補, 要素 in 未観測))):
            continue
        内側 = {(候補, 要素) for 候補 in range(x + 1, X) for 要素 in range(y + 1, Y)}
        場面['目標'].append({'点': 内側, '形': 正規形(内側), '位置': (x + 1, y + 1), '外枠': 画素群, '未観測枠': 未観測, '役割': '三辺が見え一辺が別色に遮蔽された矩形目標仮説', '状態': '条件付き。四辺目は現在画像だけでは未確認'})
    return 場面

def 全整合分解を読む(盤面, 形状多重集合):
    白群 = {(x, y) for y, row in enumerate(盤面) for x, 値 in enumerate(row) if 値 == 0}
    標識群 = set()
    while 白群:
        先頭 = min(白群)
        白群.remove(先頭)
        連結群 = {先頭}
        待機 = [先頭]
        for x, y in 待機:
            for 参照値 in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
                if 参照値 in 白群:
                    白群.remove(参照値)
                    連結群.add(参照値)
                    待機.append(参照値)
        if not any((x in (0, len(盤面[0]) - 1) or y in (0, len(盤面) - 1) for x, y in 連結群)):
            標識群 |= 連結群
    必要画素 = {(x, y) for y, row in enumerate(盤面) for x, 値 in enumerate(row) if 値 in (14, 5)} | 標識群
    青群 = {(x, y) for y, row in enumerate(盤面) for x, 値 in enumerate(row) if 値 == 14}
    許容画素 = {(x, y) for y, row in enumerate(盤面) for x, 値 in enumerate(row) if 値 in (14, 5, 4)} | 標識群
    残形 = 頻度表((tuple(map(tuple, s)) for s in 形状多重集合))
    結果群 = []
    既出 = set()

    def 被覆を探索する(未被覆, 使用画素, 対象群):
        if not 未被覆:
            if any(残形.values()) or sum((対象['選択'] for 対象 in 対象群)) != 1:
                return
            結果名 = tuple(sorted(((対象['形'], 対象['位置'], 対象['選択']) for 対象 in 対象群)))
            if 結果名 not in 既出:
                既出.add(結果名)
                結果群.append(sorted(対象群, key=lambda 対象: 対象['位置']))
            return
        基準画素 = min(未被覆)
        for 形, 残数 in list(残形.items()):
            if not 残数:
                continue
            for sx, sy in 形:
                x, y = (基準画素[0] - sx, 基準画素[1] - sy)
                候補画素 = {(x + dx, y + dy) for dx, dy in 形}
                if 候補画素 & 使用画素 or not 候補画素 <= 許容画素 or (not 候補画素 & 青群):
                    continue
                残形[形] -= 1
                被覆を探索する(未被覆 - 候補画素, 使用画素 | 候補画素, 対象群 + [{'色': 14, '点': 候補画素, '形': 形, '位置': (x, y), '選択': bool(候補画素 & 標識群), '役割': '初期問題の形状多重集合による全正確被覆'}])
                残形[形] += 1
    被覆を探索する(必要画素, set(), [])
    return 結果群


def 盤面を検査する(盤面):
    if not isinstance(盤面,(list,tuple)) or len(盤面)!=64 or any(not isinstance(行,(list,tuple)) or len(行)!=64 for 行 in 盤面):
        raise ValueError('この固定知覚は64×64の公開盤面を必要とする')
    if any(type(値) is not int or not 0<=値<=15 for 行 in 盤面 for 値 in 行):
        raise ValueError('画素は0〜15の整数でなければならない')
