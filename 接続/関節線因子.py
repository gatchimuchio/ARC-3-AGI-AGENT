"""固定画素知覚・有限代数。録画/候補行列/ID/ファイルを参照しない。"""
import itertools
import json
import math
import numpy as np

END = ((0,-2),(-1,-1),(0,-1),(1,-1),(-2,0),(-1,0),(1,0),(2,0),(-1,1),(0,1),(1,1),(0,2))
CIRCLE = tuple((x,y) for y in range(-2,3) for x in range(-2,3) if (abs(x),abs(y)) != (2,2))
RING = ((-1,-3),(1,-3),(-2,-2),(2,-2),(-3,-1),(3,-1),(-3,1),(3,1),(-2,2),(2,2),(-1,3),(1,3))
MOVE_BOUNDARY = '公開画素:単一二端点個体の座標作用関係'
COLOR_BOUNDARY = '公開取得画素:供給可用時の円盤相対画素変換'
GOAL_BOUNDARY = '公開完成画素:中心色構成と輪状目標の対応'
POSITION_BOUNDARY = '公開移動応答:中心目標の近接色一致と局所表示履歴'
DISPLAY_BOUNDARY = '公開表示更新:色近接成立かつ元色輪表示または白衝突試行'
ACQUIRE_KIND = '座標作用対象中心色観測'
RESET_KIND = 'RESET供給柄観測'

def symbol(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'))

def frame_array(frame):
    if not isinstance(frame, (list,tuple,np.ndarray)):
        raise ValueError('盤面型未確認')
    if len(frame) != 64 or any(len(row) != 64 for row in frame):
        raise ValueError('64×64の公開座標領域と不一致')
    if any(type(v) is bool or not isinstance(v,(int,np.integer)) or not 0 <= int(v) <= 15 for row in frame for v in row):
        raise ValueError('未知画素値/不明色/非整数画素を解釈しない')
    return np.asarray(frame,dtype=np.uint8)

def endpoints(a):
    out=[]
    for y in range(64):
        for x in range(1,64):
            offsets=[(dx,dy) for dx,dy in END if 0<=x+dx<64 and 0<=y+dy<64]
            if len(offsets)<8: continue
            for border in (0,3):
                if int(a[y,x]) not in (0,3) and all(a[y+dy,x+dx]==border for dx,dy in offsets):
                    out.append({'xy':[x,y],'selected':border==0,'center':int(a[y,x])})
    return out

def circles(a):
    out=[]
    for y in range(2,62):
        for x in range(2,62):
            vals=[int(a[y+dy,x+dx]) for dx,dy in CIRCLE]
            if not set(vals)&{1,2,3,5} and all(a[y+dy,x+dx]==5 for dx,dy in ((-2,-2),(2,-2),(-2,2),(2,2))):
                out.append({'xy':[x,y],'pattern':vals,'colors':sorted(set(vals))})
    return out

def rings(a):
    out=[]
    for y in range(3,61):
        for x in range(3,61):
            vals=[int(a[y+dy,x+dx]) for dx,dy in RING]
            if not set(vals)&{0,1,2,3,5} and all(a[y+dy,x+dx]==5 for dx,dy in ((0,-3),(0,3),(-3,0),(3,0),(-3,-3),(3,-3),(-3,3),(3,3))):
                out.append({'xy':[x,y],'pattern':vals,'colors':sorted(set(vals))})
    return out

def components(a,color,diagonal=False):
    left=set((int(x),int(y)) for y,x in zip(*np.where(a==color)))
    out=[]
    steps=list(itertools.product((-1,0,1),repeat=2)) if diagonal else [(1,0),(-1,0),(0,1),(0,-1)]
    while left:
        todo=[left.pop()]; region=set(todo)
        for x,y in todo:
            for dx,dy in steps:
                p=x+dx,y+dy
                if p in left: left.remove(p); region.add(p); todo.append(p)
        out.append(region)
    return out

def white(a):
    return set().union(*(c for c in components(a,10) if len(c)>21))

def partitions(a,ends,budget=4096):
    # Budget leaves an explicit symbolic remainder; it never selects a top-k partition.
    n=len(ends); subsets=[]; blue=components(a,1,True)
    def touch(s,t):
        return any((x+dx,y+dy) in t for x,y in s for dx,dy in itertools.product((-1,0,1),repeat=2))
    def attached(i,c):
        x,y=ends[i][:2]; ep={(x+dx,y+dy) for dx,dy in END+((0,0),)}
        cp={(c[0]+dx,c[1]+dy) for dx,dy in CIRCLE}
        return touch(ep,cp) or any(touch(b,ep) and touch(b,cp) for b in blue)
    total=(1<<n)-n-1
    if total>budget:
        return [],[],{'全端点部分集合数':total,'未評価域':'全サイズ2以上の部分集合','理由':'知覚分割資源枠HOLD'}
    for k in range(2,n+1):
        for ids in itertools.combinations(range(n),k):
            c=tuple(sum(ends[i][ax] for i in ids)//k for ax in (0,1))
            if not (2<=c[0]<62 and 2<=c[1]<62): continue
            vals=[int(a[c[1]+dy,c[0]+dx]) for dx,dy in CIRCLE]
            if not set(vals)&{1,2,3,5}:
                subsets.append({'端点番号':list(ids),'中心':list(c),'pattern':vals,'全端点の可視線接続':all(attached(i,c) for i in ids)})
    covers=[]
    def visit(left,path):
        if not left: covers.append(path); return
        first=min(left)
        for s in subsets:
            ids=set(s['端点番号'])
            if first in ids and ids<=left and s['全端点の可視線接続']: visit(left-ids,path+[s])
    visit(set(range(n)),[])
    return subsets,covers,None

def mean(state,group):
    ids=group['端点番号']
    return [sum(state['端点'][i][ax] for i in ids)//len(ids) for ax in (0,1)]

def unexplained_pixels(a,state,groups,sources,goals):
    covered=set((int(x),int(y)) for y,x in zip(*np.where(np.isin(a,[1,2,5])))); covered|=white(a)
    # A black component that touches the visible image boundary is retained as a frame role.
    for component in components(a,0):
        if any(x in (0,63) or y in (0,63) for x,y in component): covered|=component
    for x,y,color in state['端点']: covered.update((x+dx,y+dy) for dx,dy in END+((0,0),))
    for group in groups:
        x,y=mean(state,group); covered.update((x+dx,y+dy) for dx,dy in CIRCLE)
    for source in sources:
        x,y=source['xy']; covered.update((x+dx,y+dy) for dx,dy in CIRCLE)
    for goal in goals:
        x,y=goal['xy']; covered.update((x+dx,y+dy) for dx,dy in RING)
    return [[x,y,int(a[y,x])] for y in range(64) for x in range(64) if (x,y) not in covered]

def initial_scene(frame,budget=4096):
    a=frame_array(frame); visible=endpoints(a); selected=[i for i,e in enumerate(visible) if e['selected']]
    state={'端点':[[*e['xy'],e['center']] for e in visible],'選択':selected[0] if len(selected)==1 else None}
    subs,parts,remainder=partitions(a,state['端点'],budget)
    groups=parts[0] if len(parts)==1 else []
    centers={tuple(g['中心']) for g in groups}; nodes=circles(a)
    supplies=[{**c,'最後の取得個体':None,'過去非残存':False,'現在残存':'全可視残存'} for c in nodes if tuple(c['xy']) not in centers and len(c['colors'])==2 and 0 in c['colors']]
    unknown=[c for c in nodes if tuple(c['xy']) not in centers and not (len(c['colors'])==2 and 0 in c['colors'])]
    hold=[]
    if len(selected)!=1: hold.append('選択端点未一意')
    if len(parts)!=1: hold.append('個体分割未一意')
    if not groups: hold.append('平均中心の対象帰属未確認')
    if unknown: hold.append('色円盤の供給役割未確認')
    if remainder: hold.append(remainder)
    goals=rings(a); unexplained=unexplained_pixels(a,state,groups,supplies,goals)
    if unexplained: hold.append('役割未説明画素HOLD')
    pins=[]
    for g in groups:
        vals=g['pattern']; center=CIRCLE.index((0,0)); rest=[v for i,v in enumerate(vals) if i!=center]
        pins.append(vals[center]==6 and len(set(rest))==1 and rest[0]!=6)
    return {'現在画素':a.tolist(),'状態候補':[state] if selected else [],'全部分集合候補':subs,'全分割候補':parts,'供給':supplies,'目標':goals,'役割未説明画素':unexplained,'中心標識六':pins,'中心色候補':[[g['pattern']] for g in groups],'保留理由群':hold,'未確認円盤':unknown,'由来':'今回観測のみ','履歴相数':1}

def source_status(a,state,groups,source):
    blocked=set()
    for x,y,c in state['端点']:
        blocked.update((x+dx,y+dy) for dx,dy in END+((0,0),))
    for group in groups:
        x,y=mean(state,group); blocked.update((x+dx,y+dy) for dx,dy in CIRCLE)
    x,y=source['xy']; vals=[int(a[y+dy,x+dx]) for dx,dy in CIRCLE]
    visible=[i for i,(dx,dy) in enumerate(CIRCLE) if (x+dx,y+dy) not in blocked and vals[i]!=1]
    bad=[i for i in visible if vals[i]!=source['pattern'][i]]
    colored=[i for i in visible if source['pattern'][i]!=0 and vals[i]==source['pattern'][i]]
    status='元供給柄の非残存を可視支持' if bad else '全可視残存' if len(visible)==21 else '部分可視残存' if colored else '遮蔽HOLD'
    return {'状態':status,'可視画素':visible,'可視不一致':bad,'現在値':vals}

def action_features(a,state,parts,xy,white_mask=None):
    x,y=xy; hits=[i for i,(xx,yy,c) in enumerate(state['端点']) if abs(xx-x)<=2 and abs(yy-y)<=2]
    role='重複矩形' if len(hits)>1 else '端点矩形外' if not hits else '選択端包囲矩形' if hits[0]==state['選択'] else '非選択端包囲矩形'
    red=any(a[y+dy,x+dx]==2 for dx,dy in END+((0,0),) if 0<=x+dx<64 and 0<=y+dy<64)
    wm=white(a) if white_mask is None else white_mask; values=set(); means=[]
    if not wm or role!='端点矩形外' or red: values.add(False)
    for partition in parts:
        group=next((g for g in partition if state['選択'] in g['端点番号']),None)
        if group is None: continue
        n=len(group['端点番号']); c=[sum((xy[ax] if i==state['選択'] else state['端点'][i][ax]) for i in group['端点番号'])//n for ax in (0,1)]; means.append(c)
        if wm and role=='端点矩形外' and not red:
            values.update(any((c[0]+dx,c[1]+dy) in wm for dx,dy in shape) for shape in (END+((0,0),),CIRCLE))
    if not values: values={False,True}
    return [{'端点包囲矩形との関係':role,'移動先端点輪郭が観測地形二に重なる':bool(red),'移動候補中心が白色大領域へ接触':bool(w)} for w in sorted(values)],hits,means

def color_features(old,source,operator):
    return {'有色供給と既存が異なる':any(v and v!=p for p,v in zip(old,source)),
            '有色供給と異なる既存有色が重なる':any(v and p and v!=p for p,v in zip(old,source)),
            '零供給位置に既存有色がある':any(not v and p for p,v in zip(old,source)), '演算候補':operator}

def transform(old,source,operator):
    if operator=='非零供給画素で上書き': return tuple(v if v else p for p,v in zip(old,source))
    if operator=='空き零だけ補充': return tuple(p if p else v for p,v in zip(old,source))
    if operator=='供給円盤で全置換': return tuple(source)
    if operator=='変化なし': return tuple(old)
    raise ValueError('未知演算')

OPERATORS=('非零供給画素で上書き','空き零だけ補充','供給円盤で全置換','変化なし')

def acquisition_input(presence,owner_relation,old,source):
    f={'作用種':'中心移動後の円盤接触','供給柄の作用前可視役割':presence,'既取得個体との関係':owner_relation,
       '非零上書きと履歴再構成した作用前色が異なる':any(v and v!=p for p,v in zip(old,source)),
       '公開操作種':'座標入力','観測対象役割':'作用対象個体の中心','観測操作':'作用前後の中心相対画素色差比較'}
    return {ACQUIRE_KIND+'前提':symbol(f)},'公開供給観測:'+ACQUIRE_KIND+'・作用対象個体の中心'

def color_graph(initial,sources,ask,state_budget=50000):
    m=len(sources); n=1<<m
    if n>state_budget:
        return {'状態':'全供給mask記号HOLD','全mask数':n,'未評価域':'全順序/全mask','初期':list(initial),'供給':sources,'実行許可':False}
    states=[{'mask':0,'pattern':tuple(initial),'allpaths':1,'supportedpaths':1}]; at=[{} for _ in range(n)]; at[0][tuple(initial)]=0; edges=[]; refs={}; complete=True
    for mask in range(n):
        for old,sid in list(at[mask].items()):
            for si,source in enumerate(sources):
                if mask>>si&1: continue
                facts={}; support=False
                for op in OPERATORS:
                    feature=symbol(color_features(old,source['pattern'],op)); q=ask({'画素変換前提':feature},COLOR_BOUNDARY,'可視照合結果'); facts[op]=q['参照']; refs[q['参照']]=q
                    if op==OPERATORS[0]: support=q['採用可能'] and q['値']==['可視反例なし']
                new=transform(old,source['pattern'],OPERATORS[0]); nm=mask|1<<si
                if new not in at[nm]:
                    if len(states)>=state_budget:
                        complete=False; return {'状態':'資源枠HOLD','全mask数':n,'状態群':states,'辺群':edges,'未評価域':{'開始mask':mask,'開始状態':sid,'供給':si,'残り':'この辺以降を含む全未具体化直積'},'全候補述語':'全mask×全相対画素の非零上書き遷移','実行許可':False}
                    at[nm][new]=len(states); states.append({'mask':nm,'pattern':new,'allpaths':0,'supportedpaths':0})
                target=at[nm][new]; states[target]['allpaths']+=states[sid]['allpaths']; states[target]['supportedpaths']+=states[sid]['supportedpaths'] if support else 0
                edges.append((sid,si,target,support,tuple(facts[op] for op in OPERATORS)))
    return {'状態':'固定非零上書き族全被覆','全mask数':n,'状態群':states,'辺群':edges,'全順序列数':sum(s['allpaths'] for s in states),
            '再取得HOLD層':{'全辺数':sum(s['mask'].bit_count() for s in states),'述語':'各状態のmaskにある全供給を再適用。最終色正規化にのみ同値、可用性/経路はHOLD'},'未知演算族':'未照会/未支持演算はHOLDとして保持。非零上書き族の不成立で排除しない。'}

def endpoint_families(state,groups,sources,budget=100000):
    total=len(sources)*sum(sum(math.perm(len(g['端点番号']),k) for k in range(1,len(g['端点番号'])+1)) for g in groups)
    if total>budget:
        return {'状態':'端点族全域資源HOLD','全族数':total,'全未評価述語':'全個体×全供給×全非空順序付き端点部分集合×4096座標の直積','候補切捨て':False,'実行許可':False}
    out=[]
    for gi,g in enumerate(groups):
        n=len(g['端点番号'])
        for si,source in enumerate(sources):
            region=[[x,y] for y in range(64) for x in range(64) if (x-source['xy'][0])**2+(y-source['xy'][1])**2<=20]
            for k in range(1,n+1):
                for order in itertools.permutations(g['端点番号'],k):
                    out.append({'番号':len(out),'個体':gi,'供給':si,'順序付き可動端点':list(order),'k':k,'生座標組数':4096**k,
                                '平均中心接触領域':region,'最後の端点因子':{'個体端点数':n,'剰余域':list(range(n)),'式':'n*中心+剰余-固定端点和-先行可動端点和'},
                                '準備選択域':{'全域':'各移動前の4096全クリック座標','支持述語':'候補中間状態で所望端点の矩形にのみ属し、実クリック先ENDと地形2の接触値を使った同HDS選択交換関係が出力。未確認はHOLD','HDS参照域':'作用述語照会表の矩形role×実地形2接触×白接触false全区分','数値計数':'端点移動座標組に対する準備選択の存在。全選択action列の数ではない。','中間座標':'固定端点矩形ヒット数+既移動端点矩形ヒット数。各準備クリックを独立判定'},
                                '白地形なしの数値判定実装済み':k<=2,'状態':'条件付き有限族' if k<=2 else '3以上端点数値未確認HOLD',
                                '未確認':['現時点以降の供給可視性','重畳/描画未モデル化','後続事象','同端点再移動は別HOLD層'],'実行許可':False})
    return out

def assignment_factor(graphs,body_refs,goals,pins,ask,budget=100000):
    m=graphs[0]['全mask数'] if graphs else 1
    comparisons=sum(len(graphs[ref].get('状態群',[])) for ref in body_refs)*len(goals)
    if comparisons>budget:
        return {'状態':'割当全域資源HOLD','全供給割当数':m**len(body_refs),'全目標割当数':len(goals)**len(body_refs),'全直積数':m**len(body_refs)*len(goals)**len(body_refs),'未評価比較数':comparisons,'全未評価述語':'全個体mask×全目標番号×全色DAG状態、共有/未知演算HOLDを含む','個体別':[],'実行許可':False}
    entries=[]
    for gi,ref in enumerate(body_refs):
        graph=graphs[ref]; per=[[] for _ in goals]; closed=[[] for _ in goals]
        for sid,s in enumerate(graph.get('状態群',[])):
            colors=set(s['pattern']); colors=colors-{6} if pins[gi] else colors
            for ti,target in enumerate(goals):
                relation='一致' if colors==set(target['colors']) else '不一致'; q=ask({'中心と目標の色集合関係':relation},GOAL_BOUNDARY,'公開完成配置の対応')
                if relation=='一致':
                    per[ti].append((s['mask'],sid,q['参照']))
                    if s['supportedpaths'] and q['採用可能'] and q['値']==['対応あり']: closed[ti].append(s['mask'])
        entries.append({'個体':gi,'全目標色一致状態':per,'支持mask':list(map(lambda x:sorted(set(x)),closed))})
    m=graphs[0]['全mask数'] if graphs else 1
    return {'全供給割当数':m**len(body_refs),'全目標割当数':len(goals)**len(body_refs),'全直積数':m**len(body_refs)*len(goals)**len(body_refs),
            '個体別':entries,'全領域':'全個体mask×全目標番号、共有を禁止しない','共有供給':'HOLD','色不成立':'固定演算族内だけの判定。未知演算族HOLD'}

def event_factor(assignments,groups,sources,budget=100000):
    if assignments.get('状態')=='割当全域資源HOLD':
        return {'状態':'事象族全域資源HOLD','全未評価述語':'親の全割当×各個体全供給順×全shuffle、共有/反復はHOLD','実行許可':False}
    if len(groups)!=2:
        return {'状態':'一般個体shuffle記号HOLD','全個体':len(groups),'述語':'全個体供給順/目標最終接近の全shuffle','実行許可':False}
    entries=assignments['個体別']; possibilities=[]
    upper=math.prod(sum(map(len,e['支持mask'])) for e in entries)
    if upper>budget:
        return {'状態':'事象族全域資源HOLD','mask目標直積上界':upper,'全未評価述語':'全非共有mask対×各個体全供給順×全shuffle。共有/反復も親直積でHOLD保持','候補切捨て':False,'実行許可':False}
    for g0,g1 in itertools.product(range(len(entries[0]['支持mask'])),range(len(entries[1]['支持mask']))):
        for m0,m1 in itertools.product(entries[0]['支持mask'][g0],entries[1]['支持mask'][g1]):
            if m0&m1: continue  # This subset is reported separately; shared assignments remain in assignments.
            possibilities.append((g0,g1,m0,m1))
    total=0; factors=[]
    for g0,g1,m0,m1 in possibilities:
        k0,k1=m0.bit_count(),m1.bit_count(); count=math.factorial(k0)*math.factorial(k1)*math.comb(k0+k1+2,k0+1); total+=count
        factors.append({'目標割当':[g0,g1],'供給mask':[m0,m1],'各個体全供給順数':[math.factorial(k0),math.factorial(k1)],'各順序の支持判定':'全順列保持。各辺HDS支持/HOLDは色DAGの同じ辺参照。maskに支持経路があることを全順列支持へ拡張しない','全shuffle数':math.comb(k0+k1+2,k0+1),'全事象族数':count})
    return {'状態':'供給非共有の色支持部分族・経路未閉包HOLD','全族数':total,'因子':factors,'共有/未知順序':'親の全割当因子でHOLD保持','繰返し事象':'別HOLD層。最後出現同値性を経路へ使わない','実行許可':False}

def visible_core_pixels(a,state,group):
    c=mean(state,group); masks=set()
    for x,y,color in state['端点']:
        masks.update((x+dx,y+dy) for dx,dy in END+((0,0),))
    vals=[]; visible=[]
    for i,(dx,dy) in enumerate(CIRCLE):
        x,y=c[0]+dx,c[1]+dy
        if not (0<=x<64 and 0<=y<64): vals.append(None); continue
        val=int(a[y,x]); vals.append(val)
        if (x,y) not in masks and val!=1: visible.append(i)
    return vals,visible

FIRST_CODES={0:'最終平均中心が指定接触域外',1:'準備選択HOLD',2:'第1移動不成立',3:'第1作用HDS_HOLD',4:'第1移動で先行取得候補',5:'供給関係HOLD',6:'第2移動不成立',7:'第2作用HDS_HOLD',8:'未知前提HOLD',9:'中間中心/選択端点重畳HOLD',10:'意図供給の途中端点遮蔽HOLD',11:'二移動の局所条件支持・未来供給可視性HOLD',12:'一移動の局所条件支持・取得受理前提付き'}

def first_acquisition_block(scene,family,action_table,begin=0,end=64):
    """全座標直積の一片。ファイル/旧計数を参照せず現在像から計算。
    3+端点、白地形、複数帰属は全域HOLDとして返し、数値完了へ数えない。
    """
    if 'k' not in family:
        return {'状態':'端点族未具体化HOLD','全未評価域':family}
    if len(scene['状態候補'])!=1 or len(scene['全分割候補'])!=1:
        return {'状態':'帰属全域HOLD','全座標数':family['生座標組数']}
    a=frame_array(scene['現在画素'])
    if white(a) or family['k']>2:
        return {'状態':'白地形または3以上端点の全域HOLD','全座標数':family['生座標組数']}
    if type(begin) is not int or type(end) is not int or not 0<=begin<=end<=4096:
        raise ValueError('座標索引区間不正')
    state=scene['状態候補'][0]; groups=scene['全分割候補'][0]; sources=scene['供給']; gi,si=family['個体'],family['供給']; order=family['順序付き可動端点']; members=groups[gi]['端点番号']; n=len(members)
    pos=np.array([p[:2] for p in state['端点']],dtype=np.int16); pts=np.array([(x,y) for y in range(64) for x in range(64)],dtype=np.int16); src=np.array([s['xy'] for s in sources],dtype=np.int16)
    red=np.array([any(a[y+dy,x+dx]==2 for dx,dy in END+((0,0),) if 0<=x+dx<64 and 0<=y+dy<64) for x,y in pts])
    def effects(hits,selectedhit,reds):
        role=np.where(hits>1,3,np.where(hits==0,0,np.where(selectedhit,1,2))); out=np.full(role.shape,2,dtype=np.uint8)
        for rid,name in enumerate(('端点矩形外','選択端包囲矩形','非選択端包囲矩形','重複矩形')):
            for blocked in (False,True):
                feature={'端点包囲矩形との関係':name,'移動先端点輪郭が観測地形二に重なる':blocked,'移動候補中心が白色大領域へ接触':False}
                value=action_table.get(symbol(feature),{}).get('作用予測')
                code=2 if value is None else 1 if value=='選択端点がクリック先かつ他端保持' else 0
                out[(role==rid)&(reds==blocked)]=code
        return out
    first=order[0]; initial=pos[members].sum(axis=0); hits=np.max(abs(pts[:,None,:]-pos[None,:,:]),axis=2)<=2; eff1=effects(hits.sum(axis=1),hits[:,first],red); c1=(initial-pos[first]+pts)//n
    # All preparation click-equivalence regions are represented; no preferred click is selected.
    prep=(hits.sum(axis=1)==1)&hits[:,first]
    if first!=state['選択']:
        supported_prep=np.zeros(4096,dtype=bool)
        for blocked in (False,True):
            selection_feature={'端点包囲矩形との関係':'非選択端包囲矩形','移動先端点輪郭が観測地形二に重なる':blocked,'移動候補中心が白色大領域へ接触':False}
            if action_table.get(symbol(selection_feature),{}).get('作用予測')=='選択だけ交換': supported_prep|=prep&(red==blocked)
        if not supported_prep.any():
            shape=(end-begin,) if family['k']==1 else (end-begin,4096)
            return np.full(shape,1,dtype=np.uint8)
    if family['k']==1:
        geometric=np.sum((c1-src[si])**2,axis=1)<=20
        return np.where(~geometric,0,np.where(eff1==2,3,np.where(eff1==0,2,12))).astype(np.uint8)[begin:end]
    second=order[1]; fixed=initial-pos[first]-pos[second]; static=pos[[i for i in range(len(pos)) if i!=first]]; static_hits=(np.max(abs(pts[:,None,:]-static[None,:,:]),axis=2)<=2).sum(axis=1); selectedhit=np.max(abs(pts-pos[second]),axis=1)<=2
    firsttouch=np.any(np.sum((c1[:,None,:]-src[None,:,:])**2,axis=2)<=20,axis=1)
    pre=np.where(eff1==2,3,np.where(eff1==0,2,np.where(firsttouch,4,0))).astype(np.uint8)
    merged=np.zeros(4096,dtype=bool)
    for other,g in enumerate(groups):
        if other!=gi: merged|=np.sum((c1-np.array(mean(state,g)))**2,axis=1)<=20
    occluded=np.array([tuple(map(int,pos[second]-c)) in CIRCLE for c in c1]); shade={(dx-ex,dy-ey) for dx,dy in CIRCLE for ex,ey in END+((0,0),)}; shadeflag=np.array([tuple(map(int,p-src[si])) in shade for p in pts]); stage=np.where(merged|occluded,9,np.where(shadeflag,10,11))
    prep2=pts[np.max(abs(pts-pos[second]),axis=1)<=2]; prep2_red=red[np.max(abs(pts-pos[second]),axis=1)<=2]
    static_prep_hits=(np.max(abs(prep2[:,None,:]-static[None,:,:]),axis=2)<=2).sum(axis=1)
    known_selection=np.zeros(len(prep2),dtype=bool)
    for blocked in (False,True):
        sf={'端点包囲矩形との関係':'非選択端包囲矩形','移動先端点輪郭が観測地形二に重なる':blocked,'移動候補中心が白色大領域へ接触':False}
        if action_table.get(symbol(sf),{}).get('作用予測')=='選択だけ交換':known_selection|=prep2_red==blocked
    prep2_possible=np.any((static_prep_hits[None,:]+(np.max(abs(pts[:,None,:]-prep2[None,:,:]),axis=2)<=2)==1)&known_selection[None,:],axis=1)
    stage=np.where(prep2_possible,stage,1)
    aa=pts[begin:end]; cx=(fixed[0]+aa[:,0,None]+pts[None,:,0])//n; cy=(fixed[1]+aa[:,1,None]+pts[None,:,1])//n
    geometric=(cx-src[si,0])**2+(cy-src[si,1])**2<=20; dynamic=np.max(abs(pts[None,:,:]-aa[:,None,:]),axis=2)<=2; nh=static_hits[None,:]+dynamic
    eff2=effects(nh,np.broadcast_to(selectedhit,nh.shape),np.broadcast_to(red,nh.shape))
    out=np.where(eff2==2,7,np.where(eff2==0,6,stage[begin:end,None])); out=np.where(pre[begin:end,None]!=0,pre[begin:end,None],out)
    return np.where(geometric,out,0).astype(np.uint8)
