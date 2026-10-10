"""全候補・有限因子グラフ。外部注入HDSへ照会だけを行う。"""
import json
from collections import Counter,deque
from itertools import product
from .欄観測 import CURSOR,observe,query,語彙境界
from .字形群制約 import 広い構文,列,役割境界,役割入力,役割結果,編集一段,編集二段,対関係が利用可能,族値
from .字形原語 import 境界 as 所属境界,入力名 as 所属入力,結果名 as 所属結果
B='公開応答:旧問題の群制約と実測完了数変化'
X='応答先頭の識別可能な旧問題群制約充足'
Y='この応答で完了数が増加'
class 公開照会:
    def __init__(self, 系):
        self.系 = 系
        self.記録 = []
        self.cache = {}

    def 値(self, 内容, 境界, 結果):
        key = (json.dumps(内容, sort_keys=True), 境界, 結果)
        if key not in self.cache:
            value, report = query(self.系, 内容, 境界, 結果)
            self.cache[key] = (value, len(self.記録))
            self.記録.append({'境界': 境界, '条件': 内容, '結果名': 結果,
                              '予測': value, 'HDS': report})
        return self.cache[key]


def 群グラフ(照会, 初期):
    """各actionを全componentに同時適用。再訪を併合しても全辺/循環は残す。"""
    initial = tuple(初期)
    nodes, ids, todo, edges = [initial], {initial: 0}, deque([initial]), []
    while todo:
        current = todo.popleft()
        for action in (1, 2):
            effects = []
            for value in current:
                prediction, ref = 照会.値({'現在記号': value}, 語彙境界(action, '軌道族'), '次記号')
                effects.append({'現在族': value, '予測族': prediction, '照会参照': ref})
            edge = {'始点': ids[current], '作用': action, '成分効果': effects,
                    '必須次段階': '再観測', '現在instance検証': '未実行'}
            if any(e['予測族'] is None for e in effects):
                edge.update({'状態': 'HOLD', '終点': None, '理由': '一つ以上の成分作用をHDSが支持しない'})
            else:
                nxt = tuple(e['予測族'] for e in effects)
                if nxt not in ids:
                    ids[nxt] = len(nodes)
                    nodes.append(nxt)
                    todo.append(nxt)
                edge.update({'状態': '抽象支持', '終点': ids[nxt]})
            edges.append(edge)
    return {'初期節点': 0, '節点': [list(v) for v in nodes], '辺': edges,
            '全既知節点の両作用検査済み': len(edges) == 2 * len(nodes),
            '抽象閉包': all(e['状態'] != 'HOLD' for e in edges),
            '閉包意味': '学習した族写像の有限数学的閉包のみ。実字形/hidden stateの再帰同一性は未確認'}


def 巡回グラフ(照会, 欄数, 初期):
    edges = []
    for n in range(欄数):
        for action in (3, 4):
            relation, ref = 照会.値({'作用記号': 'ACTION' + str(action)}, CURSOR, '選択関係')
            # 固定関係語彙を解釈する。action番号から方向を手書きしない。
            target = (n - 1) % 欄数 if relation == '巡回前' else (n + 1) % 欄数 if relation == '巡回後' else None
            edges.append({'始点': n, '作用': action, '関係': relation, '終点': target,
                          '照会参照': ref, '状態': '抽象支持' if target is not None else 'HOLD',
                          '必須次段階': '再観測', '現在instance検証': '未実行'})
    return {'初期節点': 初期, '節点': list(range(欄数)), '辺': edges,
            '抽象閉包': all(e['終点'] is not None for e in edges)}


def 座標群(group):
    x, y = group['位置']
    return tuple((x + 7 * j, y, group['色']) for j in range(len(group['字形'])))


def 変数欄(var, pair_fields):
    if var[0] == '中間':
        return pair_fields[var[1]][1], var[2]
    if var[0] == '右入力':
        return pair_fields[var[1]][0], 0
    raise ValueError('未対応の変数型: ' + repr(var))


def 全関連対所属違反(goals, pair_fields, pair_types, used):
    reasons = []
    for i, (left, right) in enumerate(pair_fields):
        for j in range(i + 1, len(pair_fields)):
            if pair_types[i] != pair_types[j] or not ({i, j} & used):
                continue
            jl, jr = pair_fields[j]
            vectors = [goals.get(f, []) for f in (left, right, jl, jr)]
            if any(not v or None in v for v in vectors):
                continue
            source_equal, target_equal = vectors[0] == vectors[2], vectors[1] == vectors[3]
            if source_equal != target_equal:
                reasons.append({'理由': '全関連見本のHDS正負所属同値に違反', '対': [i, j],
                                '入力群同値': source_equal, '出力群同値': target_equal,
                                '使用見本との比較': sorted({i, j} & used)})
    return reasons


def 候補を具体化(candidate, graphs, pair_fields, pair_types=None):
    """全有限変数割当、全自由群ベクトルを検査。棄却条件は全て記録する。"""
    node_sets = [{tuple(v) for v in g['節点']} for g in graphs]
    fixed, classes = {}, candidate.get('中間同値類', [])
    if '割当' in candidate:
        for pair, values in candidate['割当'].items():
            for field, value in zip(pair_fields[int(pair)], values):
                fixed[field] = tuple(value)
    else:
        for pair, value in candidate['第一段入力'].items():
            fixed[pair_fields[int(pair)][0]] = (value,)
        for pair, value in candidate['第二段出力'].items():
            fixed[pair_fields[int(pair)][1]] = (value,)
    used = set(map(int, candidate['割当'])) if '割当' in candidate else set(map(int, candidate['第一段入力'])) | set(map(int, candidate['第二段出力']))
    if pair_types is None:
        pair_types = ['一段'] * len(pair_fields) if '割当' in candidate else [
            '第一段' if str(i) in candidate['第一段入力'] else '第二段' if str(i) in candidate['第二段出力'] else ('型未確認', i)
            for i in range(len(pair_fields))]
    domains, reports, mentioned = [], [], set()
    for cls in classes:
        component_domains = []
        for var in cls:
            field, component = 変数欄(var, pair_fields)
            mentioned.add(field)
            component_domains.append({'変数': var, '欄': field, '成分': component,
                                      '値域': sorted({v[component] for v in node_sets[field]}),
                                      '閉包': graphs[field]['抽象閉包']})
        domain = set(component_domains[0]['値域'])
        union = set(domain)
        for r in component_domains[1:]:
            domain &= set(r['値域'])
            union |= set(r['値域'])
        domains.append(sorted(domain))
        reports.append({'同値類': cls, '各出現の到達成分域': component_domains,
                        '完全積の共通域': sorted(domain),
                        '共通域外の厳密根拠': [
                            {'値': value, '不可能な出現': [r['変数'] for r in component_domains
                                                       if r['閉包'] and value not in r['値域']],
                             '未閉包の出現': [r['変数'] for r in component_domains
                                              if not r['閉包'] and value not in r['値域']]}
                            for value in sorted(union - domain)]})
    free = sorted(set(range(len(graphs))) - set(fixed) - mentioned)
    # 未指定群は成分の独立積でなく、到達した群ベクトルの全体を選ぶ。
    free_domains = [sorted(node_sets[field]) for field in free]
    outputs, rejected, held = [], [], []
    enumeration = 0
    for values in product(*domains):
        for free_values in product(*free_domains):
            enumeration += 1
            goals = {field: list(value) for field, value in fixed.items()}
            for cls, value in zip(classes, values):
                for var in cls:
                    field, component = 変数欄(var, pair_fields)
                    goals.setdefault(field, [None] * len(graphs[field]['節点'][0]))[component] = value
            for field, vector in zip(free, free_values):
                goals[field] = list(vector)
            reasons, holds = [], []
            for field in range(len(graphs)):
                vector = goals.get(field, [])
                if not vector or any(v is None for v in vector):
                    holds.append({'理由': '群成分の変数被覆不足', '欄': field, '目標': vector})
                elif tuple(vector) not in node_sets[field]:
                    reason = {'理由': '同期群到達集合の外', '欄': field, '目標': vector,
                              '成分別には到達': all(value in {v[j] for v in node_sets[field]}
                                                   for j, value in enumerate(vector))}
                    (reasons if graphs[field]['抽象閉包'] else holds).append(reason)
            for a, b in candidate.get('第一段出力群非同値', []):
                fa, fb = pair_fields[a][1], pair_fields[b][1]
                if goals[fa] == goals[fb]:
                    reasons.append({'理由': '第一段出力群の非同値違反', '対': [a, b], '共通群': goals[fa]})
            for a, b in candidate.get('第二段入力非同値', []):
                fa, fb = pair_fields[a][0], pair_fields[b][0]
                if goals[fa] == goals[fb]:
                    reasons.append({'理由': '第二段入力の非同値違反', '対': [a, b], '共通群': goals[fa]})
            reasons.extend(全関連対所属違反(goals, pair_fields, pair_types, used))
            record = {'変数同値類の値': list(values), '自由欄の群': {str(f): list(v) for f, v in zip(free, free_values)},
                      '全欄目標': [goals.get(f) for f in range(len(graphs))]}
            if reasons:
                rejected.append({**record, '全厳密棄却理由': reasons, '併存HOLD': holds})
            elif holds:
                held.append({**record, '保留理由群': holds})
            else:
                outputs.append({**record, '各欄目標節点': [graphs[f]['節点'].index(goals[f]) for f in range(len(graphs))],
                                '状態': '条件付き抽象到達可能', '実測証人': '未照合', '現在instance検証': '未実行'})
    return {'記号候補': candidate, '同値類域': reports, '自由欄': free,
            '全有限割当数': enumeration, '実行可能割当': outputs, '厳密棄却割当': rejected, 'HOLD割当': held,
            '空共通域': [i for i, d in enumerate(domains) if not d],
            '全域網羅': all(g['抽象閉包'] for g in graphs),
            '未知辺境界': [] if all(g['抽象閉包'] for g in graphs) else ['未知辺の先は未列挙。現在の有限到達域を全物理値域とはしない']}


def 条件付き手順(系, frame):
    """frameと外部注入HDSだけを使う。保存済み候補/完成frame/IDは受け取らない。"""
    observed, parsed, q = observe(frame), 広い構文(frame), 公開照会(系)
    out = {'状態': 'HOLD', '実行許可': False, '照会記録': q.記録}
    if observed['状態'] != '成立':
        return {**out, '理由': observed['理由']}
    role, role_ref = q.値({役割入力: parsed[役割入力]}, 役割境界, 役割結果)
    membership = [q.値({所属入力: b}, 所属境界, 所属結果)[0] for b in (False, True)]
    if type(role) is not bool or role != observed['見本編集役割'] or membership != [False, True]:
        return {**out, '理由': '役割または対所属関係のHDS支持不足', '役割照会': role_ref}
    fields = observed['欄群']
    graphs = [群グラフ(q, [族値(observed['セル字形'][k]) for k in field]) for field in fields]
    cursor = 巡回グラフ(q, len(fields), observed['選択欄'])
    pair_fields = []
    programs = []
    grammar = None
    if role:
        pair_fields = [[fields.index(座標群(group)) for group in pair] for pair in parsed['見本対']]
        # 色型による既存固定文法の適用。候補番号/レベル番号は使わない。
        grammar = 編集一段(系, parsed) if len({(a['色'], b['色']) for a, b in parsed['見本対']}) == 1 else 編集二段(系, parsed)
        pair_types = [(a['色'], b['色']) for a, b in parsed['見本対']]
        programs = [候補を具体化(c, graphs, pair_fields, pair_types) for c in grammar['候補']]
    achievement, achieve_ref = q.値({X: True}, B, Y)
    out.update({'状態': '条件付き有限手順成立' if role and any(c['実行可能割当'] for c in programs) else '抽象作用グラフ成立',
                '役割': '編集見本' if role else '解答欄', '欄': [list(f) for f in fields],
                '対の左右欄': pair_fields, '欄群グラフ': graphs, 'カーソルグラフ': cursor,
                '既存群文法': grammar, '全プログラム': programs,
                '達成条件照会': {'群制約充足時の予測': achievement, '照会参照': achieve_ref,
                                '適用時点': '実応答先頭の識別可能な旧問題frame。事前作用許可ではない'},
                '条件付き直積手順': {
                    '表現': '有限直積の因子化グラフ。全歩道を保持し、一つの作用列を選ばない',
                    '状態': '選択欄節点 × 各欄群節点 × {観測済み, 再観測必須}',
                    '抽象状態数_観測段階を除く': len(fields) * _積(len(g['節点']) for g in graphs),
                    '字形作用の持上げ': '観測済みの選択欄にある全成分へ同じACTION1/2を適用し、他欄は保存。対応する全局所辺を残す',
                    'カーソル作用の持上げ': '観測済み状態から全ACTION3/4辺を残し、全欄群を保存',
                    '作用前': '公開available_actionsに対象actionが含まれ、現在の役割/選択欄/全群ベクトルが観測済みであること',
                    '作用後': '必ず再観測必須へ。予測だけで次のactionへ連結しない',
                    '再観測照合': ['同じ問題・配置・固定内容を再識別', '選択欄と全欄の現在族ベクトルを読取',
                                   '予測した対象/非対象の変化を実測比較', '実字形は記録し族同値と同一視しない',
                                   '全応答frame、完了数変化、失敗/RESET/問題遷移を確認'],
                    '一致時': '現在の観測を起点に全ての支持済み辺/目標代替へ戻る',
                    '不一致または未知': 'HOLD。反証・未知を保存し、観測とHDS支持を更新するまで実行しない',
                    '達成': 'いずれかの全欄目標に一致しても、実応答の完了数増加を別途確認',
                    '方向条件': 'D4族内の正確な方向/hidden状態は未知。必要な場合は実字形作用の追加観測待ち',
                    '新規WIN': False}})
    return out


def _積(values):
    n = 1
    for v in values:
        n *= v
    return n


