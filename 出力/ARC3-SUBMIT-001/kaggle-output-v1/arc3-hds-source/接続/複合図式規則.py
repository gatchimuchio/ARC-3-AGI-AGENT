"""公開複合図式の攻略候補。HDS は呼出元が注入する。fresh 実行権限なし。"""
import collections
from hds学習系統 import 外部入力
from .図式解答教師 import _単色, 色見本候補を読む
from .図式作用教師 import 色列, 次色を照会する
from .ARC3境界 import _盤面列, 境界違反
解答境界 = '公開小図の記号と周辺解答対象役割'
連動境界 = '公開配色対象:作用対象の隣接方向標識と隣接本体応答'

def 複合図式を読む(f):
    if not f or not f[0] or any((len(行) != len(f[0]) for 行 in f)):
        return {'HOLD': '矩形frameでない'}
    色列値 = 色列(f)
    if 色列値 is None:
        return {'HOLD': '色列不明'}
    色頻度 = collections.Counter((v for 行 in f for v in 行))
    m = max(色頻度.values())
    背景候補 = [k for k, v in 色頻度.items() if v == m]
    if len(背景候補) != 1:
        return {'HOLD': '背景最多色が同率'}
    背景色 = 背景候補[0]
    小図群 = []
    for s in range(1, min(len(f), len(f[0])) // 9 + 1):
        for y in range(len(f) - 3 * s + 1):
            for x in range(len(f[0]) - 3 * s + 1):
                z = [[_単色(f, x + j * s, y + i * s, s) for j in range(3)] for i in range(3)]
                if any((v is None for 行 in z for v in 行)):
                    continue
                記号集合 = {z[i][j] for i in range(3) for j in range(3) if (i, j) != (1, 1)}
                if z[1][1] in 色列値 and 2 <= len(記号集合) <= 3 and (not 記号集合 & set(色列値)):
                    小図群.append({'位置': [x, y], '単位幅': s, '中心色': z[1][1], '記号配置': z})
    記号色群 = sorted({v for i in 小図群 for 行 in i['記号配置'] for v in 行 if v not in 色列値})
    参照対象群 = []
    for 小図 in 小図群:
        x, y = 小図['位置']
        s = 小図['単位幅']
        w = 3 * s
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == dy == 0:
                    continue
                xx, yy = (x + dx * 4 * s, y + dy * 4 * s)
                値 = None
                本体画素 = []
                装飾画素 = []
                if xx < 0 or yy < 0 or xx + w > len(f[0]) or (yy + w > len(f)):
                    役割 = '画面外'
                else:
                    画素群 = [(px, py, f[py][px]) for py in range(yy, yy + w) for px in range(xx, xx + w)]
                    中心色 = _単色(f, xx + s, yy + s, s)
                    if {c for px, py, c in 画素群} == {背景色}:
                        役割 = '背景'
                    elif any((i['位置'] == [xx, yy] and i['単位幅'] == s for i in 小図群)):
                        役割 = '指示小図'
                        値 = 中心色
                    elif 中心色 in 色列値 and {v for px, py, v in 画素群 if v in 色列値} == {中心色}:
                        役割 = '単色' if len({v for px, py, v in 画素群}) == 1 else '装飾付き'
                        値 = 中心色
                        本体画素 = [[px, py] for px, py, v in 画素群 if v in 色列値]
                        装飾画素 = [[px, py, v] for px, py, v in 画素群 if v not in 色列値]
                    else:
                        役割 = '未同定'
                参照対象群.append({'小図位置': [x, y], '対象位置': [xx, yy], '幅': w, '記号順位': 記号色群.index(小図['記号配置'][dy + 1][dx + 1]), '役割': 役割, '中心色': 小図['中心色'], '現在色': 値, '本体画素': 本体画素, '装飾画素': 装飾画素})
    格子位相群 = {(i['位置'][0] % (4 * i['単位幅']), i['位置'][1] % (4 * i['単位幅']), i['単位幅']) for i in 小図群}
    適用保留群 = []
    if len(格子位相群) != 1:
        適用保留群.append('小図の格子/縮尺仮説が非一意')
    被覆位置群 = {tuple(t['対象位置']) for t in 参照対象群 if t['役割'] in ('単色', '装飾付き')}
    盤面対象群 = []
    表示重複群 = []
    色見本群 = 色見本候補を読む(f)
    for ox, oy, s in 格子位相群:
        w = 3 * s
        for y in range(oy, len(f) - w + 1, 4 * s):
            for x in range(ox, len(f[0]) - w + 1, 4 * s):
                if any((i['位置'] == [x, y] and i['単位幅'] == s for i in 小図群)):
                    continue
                中心色 = _単色(f, x + s, y + s, s)
                値群 = {v for 行 in f[y:y + w] for v in 行[x:x + w]}
                if 中心色 not in 色列値 or 値群 & set(色列値) != {中心色}:
                    continue
                重複 = any((max(x, c['位置'][0]) < min(x + w, c['位置'][0] + c['幅']) and max(y, c['位置'][1]) < min(y + w, c['位置'][1] + c['幅']) for g in 色見本群 for c in g))
                (表示重複群 if 重複 else 盤面対象群).append([x, y])
    未拘束群 = sorted(set(map(tuple, 盤面対象群)) - 被覆位置群)
    if 未拘束群:
        適用保留群.append({'未拘束編集対象候補': 未拘束群})
    return {'色列': 色列値, '記号色群': 記号色群, '小図群': 小図群, '参照対象群': 参照対象群, '格子位相群': list(格子位相群), '盤面対象候補': 盤面対象群, '色見本重複': 表示重複群, '未拘束対象群': 未拘束群, '適用保留理由群': 適用保留群}

def 複合目標を照会する(h, 解析, *, 記号順位対応):
    if 'HOLD' in 解析:
        return {'状態': 'HOLD', '保留理由群': [解析], '解答群': [], '非割当候補群': [], '照会記録': [], '実行許可': False}
    保留群 = list(解析['適用保留理由群'])
    解答群 = []
    非割当群 = []
    照会群 = []
    制約群 = collections.defaultdict(list)
    if any((記号順位対応.get(c) != i for i, c in enumerate(解析['記号色群']))):
        保留群.append('記号順位の教師支持がない')
    if 保留群:
        return {'状態': 'HOLD', '保留理由群': 保留群, '解答群': [], '非割当候補群': [], '照会記録': [], '実行許可': False}
    for t in 解析['参照対象群']:
        r = h.照会する(外部入力({'指示記号順位': t['記号順位']}, 解答境界))
        ps = [p for p in r.内容['予測群'] if tuple(p['結果経路']) == ('解答対象役割',)]
        値群 = {p['予測値'] for p in ps}
        役割予測 = next(iter(値群)) if len(値群) == 1 and r.状態 != '断定保留' else None
        q = {'対象': t, '予測': 役割予測, 'HDS状態': r.状態, 'HOLD': r.内容['断定保留理由群'], '根拠': ps}
        照会群.append(q)
        if 役割予測 == '成功解で直接配色割当なし' and t['役割'] in ('画面外', '背景', '指示小図'):
            非割当群.append({**q, '適用根拠': '公開role仮説が非配色構造と対応。成功教師からの条件付き転用。域外色/hidden状態は予測しない'})
            continue
        if t['役割'] not in ('単色', '装飾付き') or 役割予測 not in ('中心色一致', '中心色非一致'):
            保留群.append(q)
            continue
        許容色 = {t['中心色']} if 役割予測 == '中心色一致' else set(解析['色列']) - {t['中心色']}
        制約群[*t['対象位置'], t['幅']].append((許容色, t))
    鍵群 = list(制約群)
    for i, (x, y, w) in enumerate(鍵群):
        for xx, yy, ww in 鍵群[i + 1:]:
            if max(x, xx) < min(x + w, xx + ww) and max(y, yy) < min(y + w, yy + ww):
                保留群.append({'部分重複': [[x, y, w], [xx, yy, ww]]})
    for 鍵, cs in 制約群.items():
        許容色 = set(解析['色列'])
        for 色群, t in cs:
            許容色 &= 色群
        if len(許容色) != 1 or len({(tuple(map(tuple, t['本体画素'])), tuple(map(tuple, t['装飾画素']))) for _, t in cs}) != 1:
            保留群.append({'対象': 鍵, '色またはmask非一意': sorted(許容色)})
            continue
        t = cs[0][1]
        解答群.append({'位置': list(鍵[:2]), '幅': 鍵[2], '予測色': next(iter(許容色)), '現在色': t['現在色'], '本体画素': t['本体画素'], '装飾画素': t['装飾画素']})
    if not 解答群:
        保留群.append('配色対象を閉じていない')
    return {'状態': 'HOLD' if 保留群 else '観測成功解の非割当に基づく条件付き解答候補', '保留理由群': 保留群, '解答群': 解答群, '非割当候補群': 非割当群, '照会記録': 照会群, '実行許可': False}

def 本体対象群を読む(盤面, p):
    セル群 = {}
    格子位相群 = p.get('格子位相群', [])
    if len(格子位相群) != 1:
        return セル群
    s = 格子位相群[0][2]
    w = 3 * s
    for x, y in p['盤面対象候補']:
        色列値 = p['色列']
        値群 = {盤面[yy][xx] for yy in range(y, y + w) for xx in range(x, x + w) if 盤面[yy][xx] in 色列値}
        if len(値群) != 1:
            continue
        セル群[x, y] = {'位置': [x, y], '幅': w, '格子間隔': 4 * s, '本体色': next(iter(値群)), '本体画素': [[xx, yy] for yy in range(y, y + w) for xx in range(x, x + w) if 盤面[yy][xx] in 色列値], '標識画素': [[xx - x, yy - y, 盤面[yy][xx]] for yy in range(y, y + w) for xx in range(x, x + w) if 盤面[yy][xx] not in 色列値]}
    return セル群

def 方向辺に標識がある(セル, dx, dy):
    w = セル['幅']
    s = w // 3
    return any((dx == -1 and x < s and (s <= y < 2 * s) or (dx == 1 and x >= 2 * s and (s <= y < 2 * s)) or (dy == -1 and y < s and (s <= x < 2 * s)) or (dy == 1 and y >= 2 * s and (s <= x < 2 * s)) for x, y, v in セル['標識画素']))

def 隣接応答を照会する(h, 標識あり):
    r = h.照会する(外部入力({'隣接方向の辺に標識あり': 標識あり}, 連動境界))
    ps = [p for p in r.内容['予測群'] if tuple(p['結果経路']) == ('隣接本体色が変わる',)]
    vs = {p['予測値'] for p in ps}
    v = next(iter(vs)) if len(vs) == 1 and r.状態 != '断定保留' else None
    return {'予測': v, '状態': r.状態, 'HOLD': r.内容['断定保留理由群'], '原理群': ps}

def 連動対象群を照会する(h, セル群, 対象, *, 標識色群):
    x, y = 対象['位置']
    結果 = []
    保留群 = []
    照会群 = []
    適用保留 = 標識適用保留理由(対象, 標識色群=標識色群)
    if 適用保留:
        return ([], [{'標識適用外': 適用保留}], [])
    for 鍵, c in セル群.items():
        if list(鍵) == 対象['位置']:
            結果.append(鍵)
            continue
        dx, dy = (鍵[0] - x, 鍵[1] - y)
        s = 対象['格子間隔']
        if (dx, dy) not in ((s, 0), (-s, 0), (0, s), (0, -s)):
            continue
        q = 隣接応答を照会する(h, 方向辺に標識がある(対象, dx // s, dy // s))
        照会群.append({'対象': 鍵, **q})
        if q['予測'] is None:
            保留群.append(q)
        elif q['予測']:
            結果.append(鍵)
    return (結果, 保留群, 照会群)

def 標識適用保留理由(セル, *, 標識色群):
    w = セル.get('幅', 0)
    if w <= 0 or w % 3 or セル.get('格子間隔') != 4 * (w // 3):
        return '3×3小区画と一歩格子の対応が不明'
    s = w // 3
    標識画素 = セル.get('標識画素', [])
    標識点群 = {(x, y) for x, y, v in 標識画素}
    if not {v for x, y, v in 標識画素}.issubset(set(標識色群)):
        return '標識役割の色に教師支持がない'
    if len({v for x, y, v in 標識画素}) > 1:
        return '複数の標識色の役割が未同定'
    標識領域群 = [{(x, y) for y in range(by * s, (by + 1) * s) for x in range(bx * s, (bx + 1) * s)} for bx, by in ((1, 0), (0, 1), (2, 1), (1, 2))]
    if 標識点群 - set.union(set(), *標識領域群):
        return '支持された辺中央役割の外に標識がある'
    if any((標識点群 & b and (not b <= 標識点群) for b in 標識領域群)):
        return '標識小区画が部分的で未同定'
    return None

def 二色制約を解く(作用列, 目標差分, n):
    行群 = [sum(((c >> i & 1) << j for j, c in enumerate(作用列))) | (目標差分 >> i & 1) << n for i in range(n)]
    主変数群 = []
    r = 0
    for c in range(n):
        k = next((i for i in range(r, n) if 行群[i] >> c & 1), None)
        if k is None:
            continue
        行群[r], 行群[k] = (行群[k], 行群[r])
        for i in range(n):
            if i != r and 行群[i] >> c & 1:
                行群[i] ^= 行群[r]
        主変数群.append(c)
        r += 1
    if any((v & (1 << n) - 1 == 0 and v >> n & 1 for v in 行群)):
        return None
    特解 = sum(((行群[i] >> n & 1) << c for i, c in enumerate(主変数群)))
    自由変数群 = [c for c in range(n) if c not in 主変数群]
    基底群 = []
    for c in 自由変数群:
        基底群.append(1 << c | sum(((行群[i] >> c & 1) << p for i, p in enumerate(主変数群))))
    return {'特解': 特解, '同次解基底': 基底群, '候補数': 1 << len(基底群), '集合表現': 'すべての操作偶奇解を欠落なく符号化。順序交換と冗長な偶数回操作は同値類として扱い列挙しない'}

def 複合図式攻略を照会する(盤面, 利用可能作用, 学習系, 適用支持):
    """公開frameだけから候補を構成。原票ID/row/完成答えを受け取らない。

    二色トグル・辺中央標識・対象装飾保持・作用可換性を条件とする。
    制約消去は固定演算であり、HDSが学習したアルゴリズムとは扱わない。
    """
    from .図式観測 import _作用番号
    結果 = {'適用性': {'状態': '未確認', '根拠': []}, '対象群': [], '関係群': [], '目標候補群': [], '作用候補群': [], '保留理由群': [], '照会記録': [], '出所': {'入力': '公開盤面と利用可能作用、教師由来適用支持'}, '実行許可': False, '規則の不確実性': [], '複数整合解': None, '未採用候補と理由': [], '固定適用仮説': ['二色の可逆な色列遷移', '辺中央の完全な標識subcell', '標識画素は維持される', '作用効果は状態に依存せず可換', '最下段の外部表示とhidden状態の変化は予測対象外']}
    try:
        盤面 = _盤面列([盤面])[0]
    except (境界違反, TypeError, IndexError) as exc:
        結果['保留理由群'].append({'公開盤面の境界違反': str(exc)})
        return 結果
    try:
        色見本群 = 色見本候補を読む(盤面)
        if not 色見本群:
            結果['適用性'] = {'状態': '構造上不適用', '根拠': ['この語彙の可視色列構造がない']}
            return 結果
        解析 = 複合図式を読む(盤面)
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        結果['保留理由群'].append({'解析失敗': type(exc).__name__, '理由': str(exc)})
        return 結果
    if 'HOLD' in 解析:
        結果['保留理由群'].append(解析)
        return 結果
    if len(解析['色列']) != 2 or not 解析['小図群']:
        結果['適用性'] = {'状態': '構造上不適用', '根拠': ['二色かつ小図格子という構造条件を満たさない']}
        return 結果
    対象辞書 = 本体対象群を読む(盤面, 解析)
    if not 対象辞書 or 解析['適用保留理由群']:
        結果['保留理由群'] += 解析['適用保留理由群'] or ['対象対応が閉じない']
        return 結果
    if not any((c['標識画素'] for c in 対象辞書.values())):
        結果['適用性'] = {'状態': '構造上不適用', '根拠': ['装飾付き対象を持つ語彙の構造条件がない']}
        return 結果
    結果['適用性'] = {'状態': '適用可能', '根拠': ['二色・小図格子・装飾付き対象の可視対応']}
    結果['対象群'] = list(対象辞書.values())
    if not isinstance(適用支持, dict) or '記号順位対応' not in 適用支持 or '標識色群' not in 適用支持:
        結果['保留理由群'].append('教師由来の記号/標識支持がない')
        return 結果
    if (not isinstance(適用支持['記号順位対応'], dict)
        or not isinstance(適用支持['標識色群'], (list, tuple))
        or any(type(v) is not int for v in 適用支持['標識色群'])):
        結果['保留理由群'].append('教師由来適用支持の形式が不正')
        return 結果
    目標 = 複合目標を照会する(学習系, 解析, 記号順位対応=適用支持['記号順位対応'])
    結果['目標候補群'] = 目標['解答群']
    結果['関係群'] = 目標['非割当候補群']
    結果['照会記録'] += 目標['照会記録']
    結果['保留理由群'] += 目標['保留理由群']
    鍵群 = sorted(対象辞書)
    作用列 = []
    for 鍵 in 鍵群:
        対応, 保留, 照会 = 連動対象群を照会する(学習系, 対象辞書, 対象辞書[鍵], 標識色群=適用支持['標識色群'])
        結果['保留理由群'] += 保留
        結果['照会記録'] += 照会
        作用列.append(sum((1 << 鍵群.index(k) for k in 対応)))
    for 色 in 解析['色列']:
        照会 = 次色を照会する(学習系, 解析['色列'], 色)
        結果['照会記録'].append(照会)
        if 照会['状態'] == 'HOLD' or 照会.get('次色') == 色:
            結果['保留理由群'].append({'二色トグル未成立': 照会})
    目標色 = {tuple(c['位置']): c['予測色'] for c in 目標['解答群']}
    if set(目標色) != set(鍵群):
        結果['保留理由群'].append('全対象の目標制約が閉じない')
    try:
        作用集合 = {_作用番号(v) for v in 利用可能作用}
    except (TypeError, ValueError):
        作用集合 = set()
        結果['保留理由群'].append('利用可能作用の形式が不明')
    if 6 not in 作用集合:
        結果['保留理由群'].append('公開座標作用が利用可能と確認できない')
    結果['規則の不確実性'] = [q for q in 結果['照会記録'] if q.get('HDS状態', q.get('状態')) == '断定保留' or q.get('HOLD') or q.get('HOLD理由')]
    if 結果['保留理由群'] or 結果['規則の不確実性']:
        return 結果
    差分 = sum(((対象辞書[k]['本体色'] != 目標色[k]) << i for i, k in enumerate(鍵群)))
    解集合 = 二色制約を解く(作用列, 差分, len(鍵群))
    結果['複数整合解'] = 解集合
    if 解集合 is None:
        結果['保留理由群'].append('支持作用では全目標へ到達しない')
        return 結果
    if 解集合['候補数'] != 1:
        結果['未採用候補と理由'].append({'候補集合': 解集合, '理由': '全整合解を保持。後段の代表選択は未実装'})
        return 結果
    状態色 = {k: c['本体色'] for k, c in 対象辞書.items()}
    for j, 鍵 in enumerate(鍵群):
        if not 解集合['特解'] >> j & 1:
            continue
        全対象差分 = []
        for i, 対象鍵 in enumerate(鍵群):
            if not 作用列[j] >> i & 1:
                continue
            照会 = 次色を照会する(学習系, 解析['色列'], 状態色[対象鍵])
            if 照会['状態'] == 'HOLD':
                結果['保留理由群'].append(照会)
                結果['作用候補群'] = []
                return 結果
            全対象差分.append({'位置': list(対象鍵), '前色': 状態色[対象鍵], '後色': 照会['次色'], '根拠': 照会})
            状態色[対象鍵] = 照会['次色']
        結果['作用候補群'].append({'作用番号': 6, '座標': [鍵[0] + 対象辞書[鍵]['幅'] // 2, 鍵[1] + 対象辞書[鍵]['幅'] // 2], '全対象予測差分': 全対象差分, '選択根拠': '唯一の操作偶奇解。可換モデル内の座標順代表', '実行許可': False})
    結果['終端目標照合'] = [{'位置': list(k), '予測色': 状態色[k], '目標色': 目標色[k], '一致': 状態色[k] == 目標色[k]} for k in 鍵群]
    return 結果

def 複合公開教師を教える(学習系, 教師群):
    """明示された教師列を通常の公開吸気APIへ順に渡す。"""
    from .図式作用教師 import 境界 as 色作用境界
    境界群 = {'解答': 解答境界, '連動': 連動境界, '色作用': 色作用境界}
    for 教師 in 教師群:
        if 教師.get('種類') not in 境界群 or not isinstance(教師.get('入力'), dict):
            raise ValueError('教師の意味種類または入力が不正')
        応答 = 学習系.処理する(外部入力(教師['入力'], 境界群[教師['種類']]))
        yield {'教師': 教師, '状態': 応答.状態, '根拠': 応答.追跡情報, '内容': 応答.内容}
