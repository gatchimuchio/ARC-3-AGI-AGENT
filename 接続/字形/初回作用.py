"""全目標へ至る初回作用を有限グラフで照会する。実行はしない。

固定演算: 群局所到達性とカーソルSCCの因子化到達判定。最短/進捗優先ではなく
「その初回辺の後に少なくとも一つ目標へ至る有限歩道がある」の全候補を返す。
available_actionsは現在の初回辺だけに適用し、将来の使用可能性は毎回再観測する。
全候補の採否と、一つの支持証人を固定順序で提示する処理は別。提示順はHDS学習としない。
"""
from collections import deque
from ..ARC3境界 import _盤面列,境界違反
from .群到達手順 import 条件付き手順
from .字形解答 import 字形解答を構成する
from .字形群制約 import 広い構文
from .欄観測 import query
from .応答知覚 import 境界 as スコープ境界, SCOPE_X, SCOPE_Y


def 作用記号を読む(available_actions):
    out=[]
    for a in available_actions:
        a=getattr(a,'name',a)
        if isinstance(a,str):a={'RESET':0,**{'ACTION'+str(i):i for i in range(1,8)}}.get(a)
        if type(a) is not int or not 0<=a<=7:raise ValueError('available_actionsの外部記号が不正')
        if a not in out:out.append(a)
    return out


def 全到達集合(graph):
    """未知辺は追加しない。各節点からの全既知到達集合を有限閉包で返す。"""
    adjacent={i:[] for i in graph['節点']} if graph['節点'] and isinstance(graph['節点'][0],int) else {i:[] for i in range(len(graph['節点']))}
    for e in graph['辺']:
        if e['状態']=='抽象支持' and e['終点'] is not None:adjacent[e['始点']].append(e['終点'])
    reach={}
    for start in adjacent:
        seen={start};todo=deque([start])
        while todo:
            x=todo.popleft()
            for y in adjacent[x]:
                if y not in seen:seen.add(y);todo.append(y)
        reach[start]=seen
    return reach


def 訪問歩道がある(cursor_reach,start,required):
    """必要欄のSCCが到達順序で鎖を作ることは、全欄を訪問する歩道存在の必要十分条件。

    同一SCCの中は任意に訪問できる。異なるSCCではDAGを逆戻りできないため、
    必要SCCが比較不能なら同じ歩道で両方を訪問できない。歩道列挙/枝刈りは不要。
    """
    required=tuple(required)
    inaccessible=[v for v in required if v not in cursor_reach[start]]
    incomparable=[(a,b) for j,a in enumerate(required) for b in required[j+1:] if b not in cursor_reach[a] and a not in cursor_reach[b]]
    return not inaccessible and not incomparable,{'未到達必須欄':inaccessible,'同一歩道で両訪問できない欄対':incomparable}


def 因子到達判定(procedure,local_reach,cursor_reach,start_cursor,start_nodes,target_nodes):
    required=[];reasons=[];unknown=False
    for f,(s,t) in enumerate(zip(start_nodes,target_nodes)):
        graph=procedure['欄群グラフ'][f]
        if t is None or t not in local_reach[f][s]:
            reasons.append({'理由':'目標群へ至る既知局所歩道なし','欄':f,'始点':s,'目標節点':t,'閉包':graph['抽象閉包']})
            unknown|=not graph['抽象閉包']
        elif s!=t:required.append(f)
    okay,visit=訪問歩道がある(cursor_reach,start_cursor,required)
    if not okay:
        reasons.append({'理由':'必要欄すべてを訪問する既知カーソル歩道なし',**visit})
        unknown|=not procedure['カーソルグラフ']['抽象閉包']
    status='条件付き到達可能' if not reasons else 'HOLD' if unknown else '既知抽象グラフ内で到達不能'
    return {'状態':status,'変更必須欄':required,'根拠':reasons,'現在instance検証':'未実行','将来作用の使用可能性':'各作用前の再観測が必要'}


def 有限歩道(graph,start,target):
    """全グラフを変えず、固定BFSで一つの最短証人だけを抽出する。"""
    todo=deque([start]);parent={start:None};edge_to={}
    while todo:
        at=todo.popleft()
        if at==target:
            path=[]
            while parent[at] is not None:path.append(edge_to[at]);at=parent[at]
            return list(reversed(path))
        for e in graph['辺']:
            if e['始点']==at and e['状態']=='抽象支持' and e['終点'] is not None and e['終点'] not in parent:
                parent[e['終点']]=at;edge_to[e['終点']]=e;todo.append(e['終点'])
    return None


def 全必須欄の訪問証人(cursor,start,required):
    """有限(カーソル,未訪問欄集合)上の正確なBFS。局所辺を削除しない。"""
    initial=(start,frozenset(set(required)-{start}));todo=deque([initial]);parent={initial:None};edge_to={}
    while todo:
        state=todo.popleft();at,remaining=state
        if not remaining:
            path=[]
            while parent[state] is not None:path.append(edge_to[state]);state=parent[state]
            return list(reversed(path))
        for e in cursor['辺']:
            if e['始点']!=at or e['状態']!='抽象支持' or e['終点'] is None:continue
            nxt=(e['終点'],remaining-{e['終点']})
            if nxt not in parent:parent[nxt]=state;edge_to[nxt]=e;todo.append(nxt)
    return None


def 証人手順(procedure,target_nodes,first):
    graphs=procedure['欄群グラフ'];cursor=procedure['カーソルグラフ'];nodes=[g['初期節点'] for g in graphs];selected=cursor['初期節点'];steps=[]
    def append(kind,edge):
        nonlocal selected
        achieved=[i for i,(s,t) in enumerate(zip(nodes,target_nodes)) if s==t]
        field=selected
        step={'作用番号':edge['作用'],'種別':kind,'選択欄前':field,'学習支持辺':edge,'保存する既達欄':achieved,'必須次段階':'再観測','実行許可':False}
        if kind=='選択群変更':
            if field in achieved and edge['終点']!=nodes[field]:return False
            step['現在群']=graphs[field]['節点'][nodes[field]];step['予測群']=graphs[field]['節点'][edge['終点']];nodes[field]=edge['終点'];step['今回成立する欄']=[field] if nodes[field]==target_nodes[field] and field not in achieved else []
        else:selected=edge['終点'];step['選択欄後']=selected;step['今回成立する欄']=[]
        steps.append(step);return True
    if not append(first['種別'],first['辺']):return None
    required=[i for i,(s,t) in enumerate(zip(nodes,target_nodes)) if s!=t]
    route=全必須欄の訪問証人(cursor,selected,required)
    if route is None:return None
    def finish_selected():
        if nodes[selected]==target_nodes[selected]:return True
        path=有限歩道(graphs[selected],nodes[selected],target_nodes[selected])
        if path is None:return False
        return all(append('選択群変更',edge) for edge in path)
    if not finish_selected():return None
    for edge in route:
        if not append('選択欄変更',edge) or not finish_selected():return None
    return {'段階':steps,'到達終状態':nodes,'全欄目標成立':nodes==target_nodes,'既達欄を以後保存':True,'各step再観測必須':True,'実行許可':False}


def 固定証人を提示(procedure,goals,initial_edges,actions):
    current=[g['初期節点'] for g in procedure['欄群グラフ']];selected=procedure['カーソルグラフ']['初期節点'];n=len(current)
    if any(g['各欄目標節点']==current for g in goals):return {'状態':'既に族目標一致','段階':[],'実行許可':False,'次段階':'実応答の達成条件を確認'}
    # 全候補を保持した上での証人提示順。候補番号/録画/完成答えは使わない。
    def content_key(goal):
        nodes=goal['各欄目標節点'];return (sum(s!=t for s,t in zip(current,nodes)),tuple(tuple(goal['全欄目標'][(selected+j)%n]) for j in range(n)))
    for goal in sorted(goals,key=content_key):
        nodes=goal['各欄目標節点'];viable={r['作用番号'] for r in goal.get('初回作用到達判定',[]) if r['状態']=='条件付き到達可能'}
        edges=[e for e in initial_edges if e['辺']['作用'] in actions and e['辺']['作用'] in viable]
        # 未達の現在欄を先に直す。同種の二作用は学習グラフ記載順を固定tie-breakとする。
        edges.sort(key=lambda e:0 if current[selected]!=nodes[selected] and e['種別']=='選択群変更' else 1)
        for first in edges:
            witness=証人手順(procedure,nodes,first)
            if witness and witness['全欄目標成立']:
                return {'状態':'条件付き実行順候補','目標全欄':goal['全欄目標'],**witness,
                        '固定選定の由来':'既達の欄ベクトルを多く保存する目標から、現在選択欄を先に未達修正し、BFSで必要欄を訪問する。値同数の目標は選択欄起点の族ベクトル辞書順、辺同順は学習グラフ記載順。この順序/短さはHDSの学習成果ではない。',
                        '全代替保持':'この証人の提示で目標/辺/初回作用を削除しない。各stepは再観測一致を条件に再計算する'}
    return {'状態':'保存条件付き証人は未構成','段階':[],'理由':'全候補の継続可能性とは別に、既達欄維持と現在使用可能作用を満たす証人を構成できない','実行許可':False}


def 初回作用を構成する(系,frame,available_actions):
    out={'適用性':'未確認','対象群':[],'関係群':[],'目標候補群':[],'作用候補群':[],'保留理由群':[],'照会記録':[],
         '出所':{'HDS学習':['外部注入された同一HDSの解答役割/所属/族作用/カーソル作用'],
                '固定候補演算':['全目標の有限群到達構成','局所全到達閉包','カーソルSCC到達順序の必要十分判定','初回辺後から目標に至る有限歩道の存在判定'],
                '選定意味':'最短/進捗優先を加えず、戻り道や迂回を含めて目標へ至りうる全初回作用を保持する。単一の実行作用を選ばない',
                'available_actions意味':'現在の初回作用を制約する。未来の可用性を仮定した実行許可は出さず、各作用前に再観測する'},'実行許可':False}
    try:
        actions=作用記号を読む(available_actions)
        try:
            frame=_盤面列((frame,))[0]
        except (境界違反,TypeError,ValueError,IndexError) as e:
            # 無効な盤面から幾何候補や座標範囲を推定しない。合法作用記号は全保持。
            domains=[]
            for action in actions:
                item={'作用番号':action,'状態':'HOLD','理由':'盤面の外部契約が不正で対象/効果を未評価','実行許可':False}
                if action==6:
                    item['未評価座標候補領域']={'集合':'{(x,y) | 外部ACTION6契約で合法な座標(x,y)}',
                        '外部合法域':'未確認。無効盤面の寸法から確定しない',
                        '列挙省略の意味':'集合記法で全域を保持。無効盤面内への限定や候補選別はしない'}
                else:item['未評価対象']='RESETの作用対象/効果' if action==0 else 'ACTION'+str(action)+'の作用対象/効果'
                domains.append(item)
            out['関係群'].append({'関係':'盤面不正時の全使用可能作用領域','候補領域':domains})
            out['保留理由群'].append({'種別':'入力/盤面境界','理由':type(e).__name__+': '+str(e),'HDS照会':'未実施'})
            return out
        unknown_actions=[]
        for action in actions:
            if action in (1,2,3,4):continue
            item={'作用番号':action,'状態':'HOLD','理由':'この接続の学習済み作用グラフに含まれず、作用対象/効果が未評価','実行許可':False}
            if action==6:
                item['未評価座標候補領域']={'集合':'{(x,y) | 外部ACTION6契約で合法な座標(x,y)}','外部合法域':'未確認。観測frame外を勝手に除外しない',
                    '観測frame内全整数座標の部分域':{'x':[0,len(frame[0])-1] if frame and frame[0] else None,'y':[0,len(frame)-1] if frame else None},'列挙省略の意味':'集合記法で全域を保持。座標のtop-k/beam/heuristic選別はしない'}
            elif action==0:item['未評価対象']='RESETによるepisode/問題/復旧効果。現在の同一instanceグラフへ混入しない'
            else:item['未評価対象']='外部ACTION'+str(action)+'の対象と効果'
            unknown_actions.append(item);out['保留理由群'].append({'種別':'未評価外部作用','候補領域':item})
        out['関係群'].append({'関係':'学習範囲外の全使用可能作用領域','候補領域':unknown_actions})
        if 広い構文(frame)['状態']!='構文成立':
            out['適用性']='構造上不適用';out['保留理由群'].append({'種別':'構造文法','理由':'既存字形群文法が成立しない'});return out
        procedure=条件付き手順(系,frame)
        out['照会記録']=procedure['照会記録']
        out['関係群'].append({'関係':'全条件付き有限手順','手順':procedure})
        if '欄群グラフ' not in procedure:
            disputed=any(r['HDS']['内容'].get('係争中原理群') or r['HDS']['内容'].get('競合群') for r in out['照会記録'])
            out['保留理由群'].append({'種別':'HDS隔離/競合' if disputed else 'HDS未支持','理由':procedure.get('理由','作用グラフ未構成')});return out
        graphs=procedure['欄群グラフ'];cursor=procedure['カーソルグラフ'];n=len(graphs)
        out['対象群']=[{'役割':procedure['役割'],'選択欄':cursor['初期節点'],'欄群':procedure['欄']}]
        if procedure['役割']=='編集見本':
            for program in procedure['全プログラム']:
                for assignment in program['実行可能割当']:
                    out['目標候補群'].append({'全欄目標':assignment['全欄目標'],'各欄目標節点':assignment['各欄目標節点'],'記号制約':program['記号候補'],'具体割当':assignment})
        else:
            base=字形解答を構成する(系,frame,actions);out['照会記録'].extend(base['照会記録'])
            for goal in base['目標候補群']:
                sequence=goal.get('目標記号族列')
                if sequence is None or len(sequence)!=n:
                    out['保留理由群'].append({'種別':'目標構文未確認','目標':goal});continue
                vectors=[[v] for v in sequence]
                nodes=[g['節点'].index(v) if v in g['節点'] else None for g,v in zip(graphs,vectors)]
                out['目標候補群'].append({'全欄目標':vectors,'各欄目標節点':nodes,'目標構成':goal})
        local=[全到達集合(g) for g in graphs];cr=全到達集合(cursor);current=[g['初期節点'] for g in graphs];selected=cursor['初期節点']
        initial_edges=[]
        for edge in graphs[selected]['辺']:
            if edge['始点']==current[selected]:initial_edges.append({'種別':'選択群変更','対象欄':selected,'辺':edge})
        for edge in cursor['辺']:
            if edge['始点']==selected:initial_edges.append({'種別':'選択欄変更','対象欄':selected,'辺':edge})
        out['関係群'].append({'関係':'初回全辺とavailable_actions','使用可能作用':actions,'全辺':initial_edges})
        counts={};edge_states={}
        for transition in initial_edges:
            e=transition['辺'];a=e['作用'];counts[a]=0;edge_states[a]=[]
            if a not in actions:continue
            if e['状態']!='抽象支持' or e['終点'] is None:
                out['保留理由群'].append({'種別':'HDS作用未支持','作用番号':a,'理由':'初回辺がHDS未支持/HOLD'});continue
            next_cursor=e['終点'] if a in (3,4) else selected
            next_nodes=list(current)
            if a in (1,2):next_nodes[selected]=e['終点']
            for goal in out['目標候補群']:
                result=因子到達判定(procedure,local,cr,next_cursor,next_nodes,goal['各欄目標節点'])
                goal.setdefault('初回作用到達判定',[]).append({'作用番号':a,**result})
                edge_states[a].append(result['状態'])
                counts[a]+=result['状態']=='条件付き到達可能'
            if counts[a]:
                out['作用候補群'].append({'作用番号':a,'種別':transition['種別'],'対象欄':selected,'学習支持辺':e,'到達可能目標数':counts[a],
                    'HDS条件付き支持':True,'公開一手群の直接実測':'このAPIの入力だけでは未照合。未照合を一律不採用条件にしない',
                    '実字形/hidden状態':'未検証','必須次段階':'再観測','実行許可':False})
            else:
                out['保留理由群'].append({'種別':'目標到達HOLD' if 'HOLD' in edge_states[a] else '既知目標への歩道なし','作用番号':a,'全目標判定':edge_states[a]})
        for goal in out['目標候補群']:
            goal['現在目標一致']=goal['各欄目標節点']==current
        witness=固定証人を提示(procedure,out['目標候補群'],initial_edges,actions)
        scopes={};scope_conflict=False
        for action in (1,2):
            reports={}
            for selected_input in (False,True):
                value,report=query(系,{SCOPE_X:selected_input},スコープ境界(action),SCOPE_Y)
                out['照会記録'].append({'境界':スコープ境界(action),'条件':{SCOPE_X:selected_input},'予測':value,'HDS':report})
                reports[selected_input]={'予測':value,'HDS':report}
                scope_conflict|=(value is not None and value!=selected_input) or report['状態']=='断定保留'
            scopes[action]={'非選択欄族不変をHDSが支持':reports[False]['予測'] is False,
                            '選択欄族変化をHDSが支持':reports[True]['予測'] is True,
                            '照会':reports,'注意':'選択欄が変化するという支持だけで、目標へ近づく/達成するとは判定しない'}
        for step in witness.get('段階',[]):
            if step['種別']=='選択群変更':
                scope=scopes[step['作用番号']]
                step['既達欄維持のHDS支持']=scope['非選択欄族不変をHDSが支持']
                step['目標更新の根拠']='選択群の各成分HDS作用予測と、具体的な欄目標ベクトルの照合'
            else:
                step['既達欄維持の由来']='公開カーソル作用で全字形不変を観測した固定グラフ持上げ。ACTION1/2スコープ則とは区別'
        witness['作用範囲のHDS支持']=scopes
        witness['全字形変更stepの既達維持HDS支持']=all(step.get('既達欄維持のHDS支持',True) for step in witness.get('段階',[]))
        witness['スコープ未学習時の境界']='HDS維持支持がない場合は固定局所作用持上げを条件とする証人。実行許可はなく、学習済みスコープ支持と同一視しない'
        if scope_conflict:
            witness['状態']='HOLD:作用スコープ競合'
            out['保留理由群'].append({'種別':'HDS作用スコープ競合','理由':'非選択族保存/選択族変化とHDSが競合。全代替は保存するが実行順の推奨を停止する'})
        out['関係群'].append({'関係':'固定演算による一つの支持証人','証人':witness})
        first_action=witness['段階'][0]['作用番号'] if witness.get('段階') and not scope_conflict else None
        for candidate in out['作用候補群']:
            candidate['提示実行順の先頭']=candidate['作用番号']==first_action
            if candidate['作用番号'] in (1,2):candidate['作用範囲HDS支持']=scopes[candidate['作用番号']]
        if out['目標候補群']:
            out['適用性']='適用可能'
            if any(g['現在目標一致'] for g in out['目標候補群']):out['保留理由群'].append({'種別':'可視族目標一致','理由':'目標族一致は実応答の成功確認と別。目標から出て戻る歩道も全初回候補意味では保持する'})
        else:out['保留理由群'].append({'種別':'関係未同定','理由':'現在のHDSと固定候補文法から具体目標が得られない'})
        out['保留理由群'].append({'種別':'実験実行境界','理由':'各作用後の全応答再観測が必須。抽象到達可能/直接実測/現在instance成立を区別し、live実行許可は出さない'})
        return out
    except (ValueError,TypeError,KeyError,IndexError) as e:
        out['適用性']='未確認';out['保留理由群'].append({'種別':'入力/接続例外','理由':type(e).__name__+': '+str(e)});return out

# 名前は外部接続用途の別名だけ。別アルゴリズム/別HDSを作らない。
初回作用接続=初回作用を構成する
