"""公開の完成見本から指示図→解答セル関係を学ぶ限定的な接続。

3×3小図と拡大された周囲8セルの対応は固定の知覚文法。
指示記号の極性と解答はHDSに教える。game ID/解答盤面を照会へ渡さない。
"""
from collections import Counter,defaultdict

境界='公開図式:小図と拡大周辺セルの関係'
結果名='解答セルは中心色と一致'


def _単色(f,x,y,w):
    if x<0 or y<0 or y+w>len(f) or x+w>len(f[0]):return None
    values={v for row in f[y:y+w] for v in row[x:x+w]}
    return next(iter(values)) if len(values)==1 else None


def パネルを検出する(f):
    if not f or not f[0] or any(len(r)!=len(f[0]) for r in f):raise ValueError('矩形frameが必要')
    採用=[];不成立=[]
    for s in range(1,min(len(f),len(f[0]))//9+1):
        w=3*s;step=4*s
        for y in range(len(f)-w+1):
            for x in range(len(f[0])-w+1):
                z=[[_単色(f,x+j*s,y+i*s,s) for j in range(3)] for i in range(3)]
                if any(v is None for row in z for v in row):continue
                symbols={z[i][j] for i in range(3) for j in range(3) if (i,j)!=(1,1)}
                if len(symbols)!=2 or z[1][1] in symbols:continue
                cells=[]
                for dy in [-1,0,1]:
                    for dx in [-1,0,1]:
                        if dx==dy==0:continue
                        xx,yy=x+dx*step,y+dy*step
                        cells.append({'相対位置':[dx,dy],'指示記号順位':sorted(symbols).index(z[dy+1][dx+1]),
                                      '現在色':_単色(f,xx,yy,w),'位置':[xx,yy],'幅':w})
                p={'小図位置':[x,y],'単位幅':s,'中心色':z[1][1],'指示記号色':sorted(symbols),'周辺セル':cells,
                   '間隙色':f[y][x-s] if x>=s else None}
                if all(c['現在色'] is not None for c in cells):採用.append(p)
                else:不成立.append({**p,'理由':'周囲8単色セルが揃わず、この文法では解答条件を構成できない'})
    return 採用,不成立


def 見本を選ぶ(f,panels):
    """背景と異なる強調領域がある場面だけ、非強調パネルを見本候補にする。"""
    counts=Counter(v for row in f for v in row);background=counts.most_common(1)[0][0]
    if not any(p['間隙色']!=background for p in panels):return []
    return [p for p in panels if p['間隙色']==background]


def 見本を教える(系,panels):
    from hds学習系統 import 外部入力
    records=[]
    for p in panels:
        for c in p['周辺セル']:
            内容={'指示記号順位':c['指示記号順位'],結果名:c['現在色']==p['中心色']}
            r=系.処理する(外部入力(内容,境界))
            records.append({'教師':内容,'小図位置':p['小図位置'],'セル位置':c['位置'],
                            '経験参照':r.追跡情報.get('経験参照'),'状態':r.状態,'内容':r.内容})
    return records


def 色見本候補を読む(frame):
    """画面端に接する等寸法の単色正方形列。色cycleの因果証明ではない。"""
    from .図式観測 import 成分群
    squares=[]
    for c in 成分群(frame):
        pts=c['点群'];xs=[x for x,y in pts];ys=[y for x,y in pts]
        x,y=min(xs),min(ys);w=max(xs)-x+1;h=max(ys)-y+1
        if w==h and w>=2 and len(pts)==w*w:squares.append((x,y,w,frame[y][x]))
    groups=[];left=set(range(len(squares)))
    while left:
        todo=[left.pop()];group=[]
        while todo:
            i=todo.pop();group.append(squares[i]);x,y,w,_=squares[i]
            adjacent=[j for j in left if squares[j][2]==w and ((squares[j][0]==x and abs(squares[j][1]-y)==w) or (squares[j][1]==y and abs(squares[j][0]-x)==w))]
            for j in adjacent:left.remove(j);todo.append(j)
        if len(group)>=2 and any(x==0 or y==0 or x+w==len(frame[0]) or y+w==len(frame) for x,y,w,c in group):
            groups.append([{'位置':[x,y],'幅':w,'色':c} for x,y,w,c in group])
    return groups


def 解答を構成する(系,frame):
    from hds学習系統 import 外部入力
    panels,rejected=パネルを検出する(frame)
    observed={p['中心色'] for p in panels}|{c['現在色'] for p in panels for c in p['周辺セル']}
    swatches=色見本候補を読む(frame)
    palette=observed|{c['色'] for g in swatches for c in g}
    scope_holds=[]
    if len(swatches)!=1:scope_holds.append('利用色の見本列を一意に観測できず、候補色の閉包は未確認')
    if rejected:scope_holds.append('小図候補の一部が文法適用外。全盤面の採用を保留')
    constraints=defaultdict(list);queries=[]
    for p in panels:
        for c in p['周辺セル']:
            r=系.照会する(外部入力({'指示記号順位':c['指示記号順位']},境界))
            predictions=[q for q in r.内容['予測群'] if tuple(q['結果経路'])==(結果名,)]
            values={q['予測値'] for q in predictions}
            usable=r.状態!='断定保留' and len(values)==1 and all(type(v) is bool for v in values)
            allowed=({p['中心色']} if next(iter(values)) else palette-{p['中心色']}) if usable else set()
            key=(*c['位置'],c['幅'])
            constraints[key].append({'候補色':sorted(allowed),'利用可能':usable,'小図位置':p['小図位置'],'現在色制約充足':(c['現在色']==p['中心色'])==next(iter(values)) if usable else None})
            queries.append({'セル':c,'小図位置':p['小図位置'],'状態':r.状態,'予測':predictions,'HOLD理由':r.内容['断定保留理由群']})
    keys=list(constraints)
    for i,(x,y,w) in enumerate(keys):
        for xx,yy,ww in keys[i+1:]:
            if max(x,xx)<min(x+w,xx+ww) and max(y,yy)<min(y+w,yy+ww):
                scope_holds.append('異なるセル領域が部分重複。合成未対応')
    answers=[];clicks=[];holds=[]
    for (x,y,w),cs in sorted(constraints.items()):
        colors=set(palette)
        for c in cs:colors&=set(c['候補色'])
        if not all(c['利用可能'] for c in cs) or len(colors)!=1:
            holds.append({'位置':[x,y],'幅':w,'制約':cs,'残候補':sorted(colors)});continue
        desired=next(iter(colors));current=_単色(frame,x,y,w)
        answer={'位置':[x,y],'幅':w,'現在色':current,'解答色':desired,'制約':cs};answers.append(answer)
        if desired!=current:clicks.append({'x':x+w//2,'y':y+w//2,'現在色':current,'要求色':desired,
                                         '実行状態':'未実行。座標作用の効果を観測して各手後に再照会する'})
    adopted=not(holds or scope_holds or not answers)
    return {'状態':'HOLD' if not adopted else 'パネル解答候補成立','全体保留理由':scope_holds,'色見本候補':swatches,'候補採用条件':'検出した色列が利用色を列挙するという知覚仮説。live作用で要検証','実行許可':False,'パネル数':len(panels),'色候補':sorted(palette),
            'セル制約':[{'位置':[x,y],'幅':w,'現在色':_単色(frame,x,y,w),'制約':cs} for (x,y,w),cs in sorted(constraints.items())],'解答セル':answers,'未採用差分候補':clicks if not adopted else [],'クリック対象':clicks if adopted else [],'HOLDセル':holds,'照会':queries,'文法適用外候補':rejected,
            '範囲':'検出した周辺セル制約のみ。盤面全体の機構閉包・fresh成功を意味しない'}


方針境界='公開図式:現在の解答制約充足と作用要否'


def 方針を教える(系,問題frame,完成frame):
    """入力は問題側の条件だけ。保持/変更ラベルは成功完成frameから測定する。"""
    from hds学習系統 import 外部入力
    if len(問題frame)!=len(完成frame) or any(len(a)!=len(b) for a,b in zip(問題frame,完成frame)):raise ValueError('解答frame寸法変更')
    before=解答を構成する(系,問題frame);records=[];unresolved=[]
    for cell in before['セル制約']:
        x,y=cell['位置'];answer=_単色(完成frame,x,y,cell['幅'])
        facts=[c['現在色制約充足'] for c in cell['制約']]
        if answer is None or any(v is None for v in facts):unresolved.append(cell);continue
        data={'現在セルが全解答制約を満たす':all(facts),'作用方針':'保持' if answer==cell['現在色'] else '変更'}
        r=系.処理する(外部入力(data,方針境界))
        records.append({'教師':data,'位置':[x,y],'現在色':cell['現在色'],'成功解答色':answer,'経験参照':r.追跡情報.get('経験参照'),'状態':r.状態,'内容':r.内容})
    return records,unresolved


def 作用方針を構成する(系,問題frame):
    from hds学習系統 import 外部入力
    base=解答を構成する(系,問題frame);records=[]
    for cell in base['セル制約']:
        facts=[c['現在色制約充足'] for c in cell['制約']]
        if any(v is None for v in facts):records.append({**cell,'方針':'HOLD','理由':'解答制約未確定'});continue
        r=系.照会する(外部入力({'現在セルが全解答制約を満たす':all(facts)},方針境界))
        values={v['予測値'] for v in r.内容['予測群'] if tuple(v['結果経路'])==('作用方針',)}
        policy=next(iter(values)) if r.状態!='断定保留' and len(values)==1 else 'HOLD'
        colors=set(base['色候補'])
        for c in cell['制約']:colors&=set(c['候補色'])
        records.append({**cell,'方針':policy,'許容色':sorted(colors),'HDS状態':r.状態,'HOLD理由':r.内容['断定保留理由群']})
    changes=[c for c in records if c['方針']=='変更'];unknown=[c for c in records if c['方針'] not in ('保持','変更') or (c['方針']=='変更' and len(c['許容色'])!=1)]
    return {'セル方針':records,'変更対象':changes,'保持数':sum(c['方針']=='保持' for c in records),'未確定':unknown,'全体保留理由':base['全体保留理由'],
            '状態':'HOLD' if unknown or base['全体保留理由'] or not records else '条件付き作用方針成立','実行許可':False,
            '注記':'保持は学習した制約充足に対する方針。未同定の成功条件や作用効果の閉包を保証しない'}
