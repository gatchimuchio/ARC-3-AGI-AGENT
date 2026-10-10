"""独立・実行不可 API。呼出者が注入した HDS への照会のみを行う。"""
import copy
import itertools
import json
from . import 関節線因子 as F
from hds学習系統 import 外部入力

class 条件候補(dict):
    """作用実行を許可しない、未閉包条件族の結果型。"""
    def 実行する(self, *args, **kwargs):
        raise RuntimeError('条件候補は実行不可。後続事象と公式成功条件は未閉包。')

def _typed_equal(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,(list,tuple)):
        return len(a)==len(b) and all(_typed_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,dict):
        return len(a)==len(b) and all(any(_typed_equal(k,j) and _typed_equal(v,w) for j,w in b.items()) for k,v in a.items())
    return a==b

def _result_contract(path,value):
    vocab={
        '観測作用結果':('端点と選択不変','選択だけ交換','選択端点がクリック先かつ他端保持'),
        '可視照合結果':('可視反例なし','可視反例あり'),
        '公開完成配置の対応':('対応あり','対応なし'),
        '局所表示結果':('局所点滅あり','局所点滅なし')}
    if path in vocab:return type(value) is str and value in vocab[path]
    if path in ('可視中心色差分','RESET後供給柄全画素一致'):return type(value) is bool
    if path=='観測表示更新':
        if type(value) is not str:return False
        try:d=json.loads(value)
        except (ValueError,TypeError):return False
        return type(d) is dict and set(d)=={'後表示','局所点滅'} and type(d['局所点滅']) is bool and type(d['後表示']) is str and d['後表示'] in ('黒輪表示','元色輪表示')
    return True  # Generic private query tests; public API uses only the declared paths above.

class 照会束:
    def __init__(self,hds):
        self.hds=hds; self.cache={}; self.records=[]
    def __call__(self,content,boundary,path):
        key=(F.symbol(content),boundary,path)
        if key not in self.cache:
            r={'参照':len(self.records),'入力':content,'対象系境界':boundary,'文脈':{},'結果経路':path,'採用可能':False}
            try:
                q=self.hds.照会する(外部入力(content,boundary)); data=copy.deepcopy(q.内容)
                values=[p['予測値'] for p in data.get('予測群',[]) if isinstance(p.get('結果経路'),(tuple,list)) and tuple(p['結果経路'])==(path,)]
                unanimous=bool(values) and all(_typed_equal(v,values[0]) and _result_contract(path,v) for v in values)
                r.update(状態=q.状態,値=values,採用可能=q.状態=='出力' and unanimous,全内容=data,追跡=copy.deepcopy(q.追跡情報))
            except Exception as error:
                r.update(状態='照会例外HOLD',値=[],全内容={},追跡={},例外型=type(error).__name__,未評価域='この前提に依存する全候補をHOLD保持')
            self.cache[key]=r; self.records.append(r)
        return self.cache[key]

def _effect(ask,features):
    qs=[ask({'前状態関係':F.symbol(f)},F.MOVE_BOUNDARY,'観測作用結果') for f in features]
    if not all(q['採用可能'] for q in qs):return qs,None
    vals={v for q in qs for v in q['値'] if _result_contract('観測作用結果',v)}
    return qs,next(iter(vals)) if len(vals)==1 else None

def _action_domain(actions):
    good=[]; bad=[]
    if not isinstance(actions,(list,tuple)):
        return [],[{'入力':repr(actions),'状態':'Action一覧型不正HOLD'}]
    for index,a in enumerate(actions):
        if type(a) is not int: bad.append({'索引':index,'入力':repr(a),'状態':'Action型不正HOLD'})
        elif a in good: bad.append({'索引':index,'入力':a,'状態':'Action重複HOLD'})
        else:
            good.append(a)
            if not 0<=a<=7: bad.append({'索引':index,'入力':a,'状態':'Action契約範囲外HOLD'})
    return good,bad

def 関節線候補を作る(frame,available_actions,hds,*,観測履歴=None,資源枠=None):
    budget=資源枠 if 資源枠 is not None else {}; ask=照会束(hds); actions,bad=_action_domain(available_actions)
    result=条件候補(実行許可=False,採用順序=[],全事象達成='後続6事象を含め未閉包HOLD',fresh_success=0,
        SDK原始作用域=[{'action':a,'座標域':{'x':[0,63],'y':[0,63],'全数':4096} if a==6 else None,'状態':'全座標保持' if a==6 else '未対応作用HOLD'} for a in actions],
        不正Action候補=bad,全HDS照会=ask.records,未モデル化=['全画素描画','hidden状態','公式成功の必要十分条件'])
    result['元available_actions']=copy.deepcopy(available_actions)
    if bad:
        result.update(状態='Action入力全体HOLD',未評価域='元入力の全SDK原始作用域、HDS照会0',全座標原始候補=[])
        return result
    hard={'知覚部分集合':4096,'色DAG状態':50000,'端点族':100000,'事象族':100000,'割当照合':100000}
    if type(budget) is not dict or any(k not in hard or type(v) is not int or not 0<=v<=hard[k] for k,v in budget.items()):
        result.update(状態='資源枠入力HOLD',元資源枠=repr(budget),全座標原始候補=[],未評価域='全SDK域/全役割/全割当、HDS照会0')
        return result
    result['座標作用可用性']={'必要番号':6,'現在可用':6 in actions,'未可用時':'全端点/取得族の実作用HOLD、色到達代数のみ保持'}
    try: a=F.frame_array(frame)
    except (ValueError,TypeError) as e:
        result.update(状態='入力画素HOLD',理由=str(e),未評価域='全SDK原始作用域'); return result
    if 観測履歴 is not None:
        scene=copy.deepcopy(観測履歴)
        if scene.get('現在画素')!=a.tolist():
            result.update(状態='履歴と現在画素不一致HOLD',未評価域='全SDK原始作用域と全役割割当'); return result
    else: scene=F.initial_scene(frame,budget.get('知覚部分集合',4096))
    result['現在観測']=scene
    if scene.get('役割未説明画素'):
        result.update(状態='役割未説明画素HOLD',未評価域='全SDK座標域と全役割割当',全座標原始候補=[])
        return result
    states=scene['状態候補']; parts=scene['全分割候補']; wm=F.white(a)
    primitive=[]
    if 6 in actions:
        for y in range(64):
            for x in range(64):
                hypotheses=[]
                for state in states:
                    features,hits,means=F.action_features(a,state,parts,(x,y),wm); qs,effect=_effect(ask,features)
                    hypotheses.append({'前提':features,'HDS参照':[q['参照'] for q in qs],'作用予測':effect,'クリック対象候補':hits,'平均中心候補':means,
                                       '状態':'局所作用条件付き支持' if effect else 'HDS作用HOLD','合成関係参照':{'供給':'全供給取得関係×平均中心円盤接触','目標':'全目標位置関係因子×平均中心/目標輪接触または内包×実色履歴','表示':'全表示更新関係因子×作用前表示と選択個体帰属'},'未達前提':['未来の供給可視性','過去局所表示の帰属','中間重畳の全描画']})
                primitive.append({'x':x,'y':y,'候補':hypotheses,'実行許可':False})
    result['全座標原始候補']=primitive
    preparation=[]
    if len(states)==1:
        for endpoint in range(len(states[0]['端点'])):
            classes={}
            for row in primitive:
                h=row['候補'][0]; effect=h['作用予測']; refs=tuple(h['HDS参照'])
                ok=(effect=='選択だけ交換' and h['クリック対象候補']==[endpoint]) or (effect=='端点と選択不変' and states[0]['選択']==endpoint)
                status='選択準備支持' if ok else '準備関係HOLD' if effect is None else 'この準備目的に不適合'
                key=(status,refs)
                if key not in classes:classes[key]={'状態':status,'HDS参照':list(refs),'全座標':[]}
                classes[key]['全座標'].append([row['x'],row['y']])
            preparation.append({'端点':endpoint,'準備省略可能':states[0]['選択']==endpoint,'全原始座標数':len(primitive),'全同値領域':list(classes.values()),'範囲':'この現在状態のみ。中間状態は同じ述語を再評価'})
    result['現在全準備選択領域']=preparation
    if len(states)!=1 or len(parts)!=1 or scene.get('色履歴未閉包'):
        result.update(状態='対象帰属または色履歴HOLD',全役割直積='全状態×全分割×全供給/目標割当を未具体化HOLDとして保持'); return result
    state=states[0]; groups=parts[0]; sources=scene['供給']; graphs=[]; refs=[]; bypattern={}
    for gi,group in enumerate(groups):
        patterns=scene['中心色候補'][gi]
        if len(patterns)!=1:
            result.update(状態='中心色履歴未一意HOLD',全役割直積='全色候補×全供給/目標割当'); return result
        pattern=tuple(patterns[0])
        if pattern not in bypattern:
            bypattern[pattern]=len(graphs); graphs.append(F.color_graph(pattern,sources,ask,budget.get('色DAG状態',50000)))
        refs.append(bypattern[pattern])
    result['色DAG']=graphs; result['個体色DAG参照']=refs
    assignments=F.assignment_factor(graphs,refs,scene['目標'],scene['中心標識六'],ask,budget.get('割当照合',100000))
    result['全割当因子']=assignments
    result['全事象因子']=F.event_factor(assignments,groups,sources,budget.get('事象族',100000))
    result['全端点因子']=F.endpoint_families(state,groups,sources,budget.get('端点族',100000))
    acquisition=[]
    for gi,group in enumerate(groups):
        for si,source in enumerate(sources):
            role='未取得' if source['現在残存'] in ('全可視残存','部分可視残存') else '帰属HOLD' if source.get('最後の取得個体') is None else '同一個体' if source['最後の取得個体']==gi else '別個体'
            inp,b=F.acquisition_input(source['現在残存'],role,scene['中心色候補'][gi][0],source['pattern']); q=ask(inp,b,'可視中心色差分')
            acquisition.append({'個体':gi,'供給':si,'HDS参照':q['参照'],'条件付き観測支持':q['採用可能'] and role=='未取得',
                                '一般化':'未取得の公開支持前提内' if role=='未取得' else '再取得の希少/非識別HOLD',
                                '未達前提':['中心円盤接触','作用が受理されること','取得時点の実可視残存'],'実行許可':False})
    result['供給取得関係']=acquisition
    # Exact cached action semantics are retained for compact first-acquisition membership predicates.
    table={}
    for role,red,wh in itertools.product(('端点矩形外','選択端包囲矩形','非選択端包囲矩形','重複矩形'),(False,True),(False,True)):
        f={'端点包囲矩形との関係':role,'移動先端点輪郭が観測地形二に重なる':red,'移動候補中心が白色大領域へ接触':wh}
        qs,effect=_effect(ask,[f]); table[F.symbol(f)]={'作用予測':effect,'HDS参照':qs[0]['参照']}
    result['作用述語照会表']=table
    position=[]
    for color,contact,prior in itertools.product((False,True),repeat=3):
        feature={'色集合一致':color,'円盤輪接触または中心内包':contact,'同個体同目標の局所点滅を先に観測し未離脱':prior}
        q=ask({'局所受理前提':F.symbol(feature)},F.POSITION_BOUNDARY,'局所表示結果')
        position.append({'前提':feature,'HDS参照':q['参照'],'適用': '各予測平均中心×全目標の色集合/円盤輪幾何/厳密過去表示を評価','未確認':'点滅は公式受理の代用でない。履歴欠落は全真偽候補HOLD'})
    display=[]
    for prior,effect,collision,same in itertools.product(('元色輪表示','黒輪表示'),('端点移動','選択変更','端点と選択不変'),(False,True),(False,True)):
        feature={'作用前表示':prior,'作用結果':effect,'白衝突試行候補':collision,'作用前選択個体と目標一致個体が同一':same}
        q=ask({'目標表示前提':F.symbol(feature)},F.DISPLAY_BOUNDARY,'観測表示更新')
        normal=prior=='元色輪表示' and effect=='端点移動' and not collision and same
        collision_other=prior=='黒輪表示' and effect=='端点と選択不変' and collision and not same
        display.append({'前提':feature,'HDS参照':q['参照'],'条件付き採用':q['採用可能'] and (normal or collision_other),'希少/未観測HOLD':not(normal or collision_other),'適用境界':'色近接成立かつ元色輪表示、または白衝突試行。全目標/静止個体も保持'})
    result['全目標位置関係因子']=position
    result['全表示更新関係因子']=display
    resource_holds=[{'領域':key,'全未評価域':result[key]} for key in ('全割当因子','全事象因子','全端点因子') if isinstance(result[key],dict) and '資源HOLD' in result[key].get('状態','')]
    resource_holds += [{'領域':'色DAG','全未評価域':g} for g in graphs if g.get('状態')!='固定非零上書き族全被覆']
    result['資源未評価域']=resource_holds
    result['状態']='資源全体HOLD' if resource_holds else '全候補因子構成・経路未閉包HOLD'
    return result

def 関節線候補族に含まれる(bundle,action):
    """Primitive membership does not execute or choose an action."""
    if not isinstance(action,dict) or type(action.get('action')) is not int:
        return {'状態':'Action型不正HOLD','実行許可':False}
    identifier=action['action']; domain=next((d for d in bundle['SDK原始作用域'] if d['action']==identifier),None)
    if domain is None: return {'状態':'available_actions外HOLD','実行許可':False}
    if identifier!=6: return {'状態':'未対応作用HOLD','実行許可':False}
    x,y=action.get('x'),action.get('y')
    if type(x) is not int or type(y) is not int or not (0<=x<64 and 0<=y<64): return {'状態':'座標型/範囲不正HOLD','実行許可':False}
    rows=bundle.get('全座標原始候補',[])
    return rows[y*64+x] if rows else {'状態':'原始座標域内・知覚未確認HOLD','実行許可':False}

def _visual(state,a):
    pred=[{'xy':[x,y],'center':c,'selected':i==state['選択']} for i,(x,y,c) in enumerate(state['端点'])]; reasons=[]; overlay=[]
    for e in F.endpoints(a):
        if e not in pred: reasons.append({'完全可視端点が候補にない':e})
    for i,(x,y,c) in enumerate(state['端点']):
        if int(a[y,x])==c: continue
        if int(a[y,x]) in (2,5): reasons.append({'候補中心の背景露出':i,'画素':int(a[y,x])})
        else: overlay.append({'端点':i,'画素':int(a[y,x]),'状態':'前景上書きHOLD'})
    return not reasons,reasons,overlay

def 関節線観測を照合する(観測履歴,実観測作用,全応答相,hds,*,公式進行観測=False,終局観測=False):
    """現在までの観測を追加。公開進行ラベルは相の区切りのみに使用する。
    動いた試行相を最終受理に読み替えず、全枝・全相を返す。
    """
    ask=照会束(hds); result=条件候補(実行許可=False,全HDS照会=ask.records,全候補枝=[],全応答相照合=[],公式進行観測=bool(公式進行観測),局所点滅='未同定HOLD',局所受理候補='未同定HOLD',後続事象='未閉包HOLD')
    try: phases=[F.frame_array(f) for f in 全応答相]
    except (ValueError,TypeError) as e: result.update(状態='応答画素不正HOLD',理由=str(e)); return result
    if not phases: result['状態']='応答相なしHOLD'; return result
    if not isinstance(実観測作用,dict) or type(実観測作用.get('action')) is not int:
        result['状態']='実観測作用型不正HOLD'; return result
    if 実観測作用['action']==0:
        result.update(状態='公開RESET観測',次履歴=F.initial_scene(phases[-1]),RESET因果='実応答初期化のみ。可用作用へ追加しない'); return result
    x,y=実観測作用.get('x'),実観測作用.get('y')
    if 実観測作用['action']!=6 or type(x) is not int or type(y) is not int or not 0<=x<64 or not 0<=y<64:
        result['状態']='実観測作用/座標未対応HOLD'; return result
    before=F.frame_array(観測履歴['現在画素']); parts=観測履歴['全分割候補']; branches=[]
    for state in 観測履歴['状態候補']:
        candidates=[('不変',copy.deepcopy(state))]
        candidates += [('選択',{'端点':copy.deepcopy(state['端点']),'選択':i}) for i in range(len(state['端点']))]
        if state['選択'] is not None:
            moved=copy.deepcopy(state); moved['端点'][state['選択']][:2]=[x,y]; candidates.append(('移動',moved))
        features,hits,means=F.action_features(before,state,parts,(x,y)); qs,effect=_effect(ask,features)
        for label,target in candidates:
            observed='端点と選択不変' if target==state else '選択だけ交換' if target['端点']==state['端点'] else '選択端点がクリック先かつ他端保持'
            semantic=effect is None or effect==observed
            if semantic and effect=='選択だけ交換' and len(hits)==1: semantic=target['選択']==hits[0]
            branches.append({'前':state,'後':target,'族':label,'固定族内作用':observed,'最終作用関係適合':semantic,'HDS保留':effect is None,'HDS参照':[q['参照'] for q in qs]})
    for pi,a in enumerate(phases):
        checks=[]
        for bi,b in enumerate(branches):
            ok,reasons,overlay=_visual(b['後'],a)
            checks.append({'枝':bi,'可視適合':ok,'反例':reasons,'非可視HOLD':overlay})
        result['全応答相照合'].append({'相':pi,'種別':'全相可視照合・途中相を受理としない','全枝':checks})
    # Stable old-scene observation is prior to an explicitly reported new-scene frame.
    final=len(phases)-2 if 公式進行観測 and not 終局観測 and len(phases)>1 else len(phases)-1
    keep={}
    for bi,b in enumerate(branches):
        visual=result['全応答相照合'][final]['全枝'][bi]['可視適合']; b['最終可視適合']=visual; b['固定族内採否']=visual and b['最終作用関係適合']
        if b['固定族内採否']: keep[F.symbol(b['後'])]=b['後']
    result['全候補枝']=branches; result['安定相索引']=final
    new=copy.deepcopy(観測履歴); new['現在画素']=phases[final].tolist(); new['状態候補']=list(keep.values()); new['履歴相数']=new.get('履歴相数',0)+len(phases)
    new['保留理由群']=list(new.get('保留理由群',[])); new['色履歴未閉包']=False; color_records=[]
    if len(keep)==1 and len(parts)==1 and len(観測履歴['状態候補'])==1:
        oldstate=観測履歴['状態候補'][0]; state=next(iter(keep.values())); groups=parts[0]
        for gi,g in enumerate(groups):
            oldpatterns=観測履歴['中心色候補'][gi]; patterns={tuple(p) for p in oldpatterns}; moved=F.mean(oldstate,g)!=F.mean(state,g); center=F.mean(state,g)
            contacts=[(si,s) for si,s in enumerate(観測履歴['供給']) if moved and sum((center[k]-s['xy'][k])**2 for k in (0,1))<=20]
            if len(contacts)>1: new['色履歴未閉包']=True; color_records.append({'個体':gi,'状態':'同時複数供給の全順序HOLD'})
            elif contacts:
                si,source=contacts[0]; presence=F.source_status(before,oldstate,groups,source)['状態']; relation='未取得' if presence in ('全可視残存','部分可視残存') else '帰属HOLD' if source.get('最後の取得個体') is None else '同一個体' if source['最後の取得個体']==gi else '別個体'
                candidates=set()
                for old in oldpatterns:
                    inp,boundary=F.acquisition_input(presence,relation,old,source['pattern']); q=ask(inp,boundary,'可視中心色差分')
                    record={'個体':gi,'供給':si,'取得関係参照':q['参照'],'前可視役割':presence,'全演算':[]}
                    if presence in ('全可視残存','部分可視残存'):
                        for op in F.OPERATORS:
                            z=ask({'画素変換前提':F.symbol(F.color_features(old,source['pattern'],op))},F.COLOR_BOUNDARY,'可視照合結果')
                            supported=z['採用可能'] and z['値']==['可視反例なし']; unknown=not z['採用可能']
                            record['全演算'].append({'演算':op,'HDS参照':z['参照'],'固定族内支持':supported,'未確認':unknown})
                            if supported or unknown: candidates.add(F.transform(old,source['pattern'],op))
                        if not q['採用可能']: new['色履歴未閉包']=True
                    else:
                        candidates.add(tuple(old)); record['希少取得一般化']='非残存/遮蔽は因果HOLD'; new['色履歴未閉包']=True
                    color_records.append(record)
                patterns=candidates or patterns
            vals,visible=F.visible_core_pixels(phases[final],state,g); matched=[list(p) for p in sorted(patterns) if all(p[i]==vals[i] for i in visible)]
            new['中心色候補'][gi]=matched
            if len(matched)!=1: new['色履歴未閉包']=True
        for si,source in enumerate(new['供給']):
            observation=F.source_status(phases[final],state,groups,source); source['現在残存']=observation['状態']
            if observation['状態']=='元供給柄の非残存を可視支持': source['過去非残存']=True
            beforestatus=F.source_status(before,oldstate,groups,source)['状態']
            owners=[gi for gi,g in enumerate(groups) if F.mean(oldstate,g)!=F.mean(state,g) and sum((F.mean(state,g)[k]-source['xy'][k])**2 for k in (0,1))<=20]
            if beforestatus in ('全可視残存','部分可視残存') and observation['状態']=='元供給柄の非残存を可視支持' and len(owners)==1:
                source['最後の取得個体']=owners[0]; source['帰属範囲']='同作用の可視非残存と接触対応。普遍消費因果未確認'
    else: new['色履歴未閉包']=True
    result['中心色履歴照合']=color_records
    if len(new['状態候補'])==1 and len(parts)==1:
        new['役割未説明画素']=F.unexplained_pixels(phases[final],new['状態候補'][0],parts[0],new['供給'],new['目標'])
    else:new['役割未説明画素']=[{'状態':'帰属未一意につき全画素役割未確認'}]
    result['旧場面次履歴']=new
    result['次履歴']=F.initial_scene(phases[-1]) if 公式進行観測 and not 終局観測 else new
    result['状態']='固定候補族内一意' if len(keep)==1 else '全帰属候補HOLD'
    return result
