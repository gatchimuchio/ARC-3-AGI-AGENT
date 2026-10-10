"""公開完成見本で対の対応を学ぶ。固定知覚/D4/順序文法とHDS学習を分離。"""
from dataclasses import asdict
from functools import lru_cache
from itertools import product

境界='字形群:見本対の軌道所属対応'
入力名='入力群は見本左群の軌道列に属する'
結果名='解答群は見本右群の軌道列に属する'


def 回転(a):
    return tuple(tuple(row) for row in zip(*a[::-1]))


def 変換(a,反転,回数):
    b=tuple(tuple(reversed(r)) for r in a) if 反転 else a
    for _ in range(回数):b=回転(b)
    return b


@lru_cache(None)
def 軌道(a):
    return tuple(sorted({変換(a,f,k) for f in (False,True) for k in range(4)}))


def 軌道列(g):return tuple(min(軌道(a)) for a in g)


def 字形群を読む(frame):
    """固定文法:連結する背景色矩形、7高、7の倍数幅、黒5が字形。色IDで解法分岐しない。"""
    if not frame or any(len(r)!=len(frame[0]) for r in frame):raise ValueError('矩形frameが必要')
    h,w=len(frame),len(frame[0]);seen=set();groups=[]
    for y in range(h):
        for x in range(w):
            if (x,y) in seen or frame[y][x]==5:continue
            c=frame[y][x];todo=[(x,y)];seen.add((x,y));points=[]
            while todo:
                xx,yy=todo.pop();points.append((xx,yy))
                for p,q in ((xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)):
                    if 0<=p<w and 0<=q<h and (p,q) not in seen and frame[q][p]==c:seen.add((p,q));todo.append((p,q))
            x0=min(p for p,q in points);x1=max(p for p,q in points);y0=min(q for p,q in points);y1=max(q for p,q in points)
            if y1-y0+1!=7 or (x1-x0+1)%7:continue
            region=[row[x0:x1+1] for row in frame[y0:y1+1]]
            if not all(v in (5,c) for r in region for v in r) or not any(v==5 for r in region for v in r):continue
            if any(v!=c for v in region[0]+region[-1]) or any(r[0]!=c or r[-1]!=c for r in region):continue
            masks=tuple(tuple(tuple(frame[y0+dy][xx+dx]==5 for dx in range(7)) for dy in range(7)) for xx in range(x0,x1+1,7))
            groups.append({'位置':(x0,y0),'色':c,'字形':masks})
    return sorted(groups,key=lambda g:(g['位置'][1],g['位置'][0]))


def 問題を読む(frame):
    groups=字形群を読む(frame);ys=sorted({g['位置'][1] for g in groups})
    if len(ys)<3:return {'状態':'HOLD','理由':'見本行と入力/解答行の文法未成立','群':groups}
    query=[g for g in groups if g['位置'][1]==ys[-2]];output=[g for g in groups if g['位置'][1]==ys[-1]]
    if len(query)!=1 or len(output)!=1 or query[0]['色']==output[0]['色']:return {'状態':'HOLD','理由':'入力/解答の単一行役割未同定','群':groups}
    pairs=[]
    for y in ys[:-2]:
        row=[g for g in groups if g['位置'][1]==y]
        if len(row)%2:return {'状態':'HOLD','理由':'見本対の左右群不足','群':groups}
        for a,b in zip(row[::2],row[1::2]):
            if (a['色'],b['色'])!=(query[0]['色'],output[0]['色']):return {'状態':'HOLD','理由':'複数アルファベット/逆向き対の合成は未同定','群':groups}
            pairs.append((a['字形'],b['字形']))
    return {'状態':'構文成立','見本対':tuple(pairs),'入力':query[0]['字形'],'解答欄':output[0]['位置'],'解答長':len(output[0]['字形']),'現在解答':output[0]['字形']}


def 全分解(sequence,dictionary):
    """全分解を保持。長さ上限・beam・top-kは使用しない。"""
    seq=軌道列(sequence);ds=[軌道列(g) for g in dictionary]
    @lru_cache(None)
    def walk(pos):
        if pos==len(seq):return ((),)
        return tuple(((i,pos,pos+len(g)),)+tail for i,g in enumerate(ds) if seq[pos:pos+len(g)]==g for tail in walk(pos+len(g)))
    return walk(0)


def 教師対応を読む(problem,answer):
    """入力側/完成側を独立に全分解し、順序で対応。異なる分解を勝手に選ばない。"""
    left=全分解(problem['入力'],[a for a,b in problem['見本対']]);right=全分解(answer,[b for a,b in problem['見本対']])
    alignments=[(a,b) for a in left for b in right if len(a)==len(b)]
    if not alignments:return [],{'状態':'HOLD','理由':'同数群への入力/完成独立分解が存在しない','入力分解数':len(left),'完成分解数':len(right)}
    possibilities=[]
    for a,b in alignments:
        records=[]
        for (_,s,e),(_,t,u) in zip(a,b):
            for pa,pb in problem['見本対']:
                records.append((軌道列(problem['入力'][s:e])==軌道列(pa),軌道列(answer[t:u])==軌道列(pb)))
        possibilities.append(tuple(records))
    if len(set(possibilities))!=1:return [],{'状態':'HOLD','理由':'独立分解で教師ラベルが変わる','対応分解数':len(alignments)}
    return [{入力名:x,結果名:y} for x,y in possibilities[0]],{'状態':'教師対応成立','対応分解数':len(alignments),'入力分解数':len(left),'完成分解数':len(right)}


def 教える(system,records):
    from hds学習系統 import 外部入力
    return [asdict(system.処理する(外部入力(r,境界))) for r in records]


def 解答を構成する(system,problem):
    """APIに完成解答/ID/pathなし。HDS予測を満たすすべての目標内容を因子化して保持。"""
    from hds学習系統 import 外部入力
    if problem['状態']!='構文成立':return {'状態':'HOLD','理由':problem['理由'],'候補群':[]}
    queries={}
    for value in (False,True):
        q=system.照会する(外部入力({入力名:value},境界));pred=[v['予測値'] for v in q.内容['予測群'] if tuple(v['結果経路'])==(結果名,)]
        usable=q.状態!='断定保留' and len(set(pred))==1 and all(type(v) is bool for v in pred)
        queries[value]={'値':pred[0] if usable else None,'HDS':asdict(q)}
    if any(q['値'] is None for q in queries.values()):return {'状態':'HOLD','理由':'HDS関係未成立/係争/不足','候補群':[],'照会':queries}
    seq=problem['入力'];pairs=problem['見本対'];rejected=[]
    @lru_cache(None)
    def walk(pos):
        if pos==len(seq):return ((),)
        allpaths=[]
        for i,(a,b) in enumerate(pairs):
            if pos+len(a)>len(seq):continue
            belongs=軌道列(seq[pos:pos+len(a)])==軌道列(a)
            if queries[belongs]['値'] is True:
                violations=[]
                for j,(other_a,other_b) in enumerate(pairs):
                    expected=queries[軌道列(seq[pos:pos+len(a)])==軌道列(other_a)]['値']
                    actual=軌道列(b)==軌道列(other_b)
                    if expected!=actual:violations.append({'見本対':j,'HDS予測所属':expected,'候補所属':actual})
                if violations:
                    rejected.append({'入力位置':pos,'候補見本対':i,'理由':'HDS全所属関係に反する','反証':violations});continue
                for tail in walk(pos+len(a)):allpaths.append(((i,pos,pos+len(a)),)+tail)
        return tuple(allpaths)
    candidates=[]
    for path in walk(0):
        factors=[軌道(mask) for i,s,e in path for mask in pairs[i][1]]
        if len(factors)!=problem['解答長']:continue # observed output length is an exact structural constraint
        candidates.append({'入力分解':path,'字形候補因子':factors,'候補数':__import__('math').prod(map(len,factors))})
    unique=len(candidates)==1 and all(len(f)==1 for f in candidates[0]['字形候補因子'])
    return {'状態':'目標内容一意' if unique else 'HOLD','理由':'方向/対称性が未同定。候補を全保持' if candidates else '見本群で入力列を被覆できない','候補群':candidates,'棄却辺':rejected,'照会':queries,'実行許可':False,'固定文法':'D4軌道、左から右の順序付き群置換。共有変換結合は未学習、推論で使用しない'}


def 候補に含まれる(result,answer):
    return any(len(c['字形候補因子'])==len(answer) and all(mask in factor for mask,factor in zip(answer,c['字形候補因子'])) for c in result['候補群'])
