"""単一の外部HDSに通常入力/照会する。解答、原票、IDはruntime入力に取らない。"""
from .知覚 import 符号,前提,知覚,方向,作用番号
境界='公開連動:大駒の前方地形と作用相対変位'

def 照会(h,facts):
    from hds学習系統 import 外部入力
    if facts.get('操作対象関係')=='履歴不明':return {'状態':'HOLD','値':None,'理由':['水平方向の過去実測がなく、左右から補完しない']}
    r=h.照会する(外部入力({'前提直積':符号(facts)},境界));ps=[p for p in r.内容['予測群']if tuple(p['結果経路'])==('相対変位',)];vs={p['予測値']for p in ps}
    v=next(iter(vs))if r.状態!='断定保留'and len(vs)==1 and next(iter(vs))in(-1,0,1)else None
    return {'状態':'条件付き局所支持'if v is not None else'HOLD','値':v,'HDS状態':r.状態,'理由':r.内容['断定保留理由群'],'予測':ps,'入力':facts}

def 全候補(frame,available,h,*,全個体対応=None,直近水平実測同方向役割=None):
    """履歴は確認済み前観測/作用/応答に由来すること。現在frameだけでは水平役割を補わない。"""
    if not isinstance(available,(list,tuple))or not available:return {'全作用候補':[],'作用空間状態':'HOLD','理由':['利用可能作用が欠損または空。作用を補完しない'],'実行許可':False}
    s=知覚(frame);holds=list(s['HOLD']);hypotheses=全個体対応 if 全個体対応 is not None else [tuple(s['駒'])]
    if len(s['駒'])!=2:holds.append('二個体知覚の範囲外')
    for hyp in hypotheses:
        if len(hyp)!=2 or sorted(map(tuple,hyp))!=sorted(map(tuple,s['駒'])):holds.append('履歴と可視占有が一致しない')
    if not hypotheses:holds.append('個体対応履歴が欠損')
    if 直近水平実測同方向役割 not in(None,0,1):holds.append('水平実測役割不正')
    result=[]
    for raw in available:
        try:a=作用番号(raw)
        except (TypeError,ValueError):
            result.append({'原作用':raw,'状態':'HOLD','理由':['作用形式不正'],'実行許可':False});continue
        item={'id':a,'実行許可':False,'全個体対応候補':[]}
        if a==6:item.update({'状態':'HOLD','理由':['座標作用の選択/機構効果が未学習'],'全座標領域':{'x':[0,63],'y':[0,63],'閉整数直積全数':4096}})
        elif a not in 方向:item.update({'状態':'HOLD','理由':['非方向作用が未学習']})
        elif holds:item.update({'状態':'HOLD','理由':holds})
        else:
            for hyp in hypotheses:
                qs=[照会(h,前提(frame,hyp,s['幅'],a,role,直近水平実測同方向役割))for role in(0,1)];points=[]
                if all(q['値']is not None for q in qs):
                    dx,dy=方向[a];points=[(p[0]+q['値']*dx*s['幅'],p[1]+q['値']*dy*s['幅'],p[2])for p,q in zip(hyp,qs)]
                item['全個体対応候補'].append({'前個体配置':hyp,'全局所照会':qs,'予測個体位置':points})
            values={符号(sorted(c['予測個体位置']))for c in item['全個体対応候補']if c['予測個体位置']}
            ok=len(values)==1 and all(c['予測個体位置']for c in item['全個体対応候補'])
            item.update({'状態':'条件付き局所支持'if ok else'HOLD','理由':[]if ok else['全現在仮説の局所変位が未確定/不一致'],'占有合流候補':ok and any(len(set(tuple(p[:2])for p in c['予測個体位置']))==1 for c in item['全個体対応候補'])})
        result.append(item)
    return {'全作用候補':result,'目標判定':'HOLD:完成counterと可視関係の必要十分性は未確定','全環境応答予測':'HOLD:局所駒変位以外と全応答相のモデルは未完','実行許可':False}

HUD境界='公開連動:上下HUDの過去観測と次作用失敗終端'

def HUD履歴を進める(前履歴,応答,外部観測参照):
    """一つの外部Action応答につき末尾画素だけを一回更新。途中8相も1観測である。"""
    if not isinstance(応答,dict)or not 応答.get('frame')or not 外部観測参照:return {'連続黒数':None,'状態':'HOLD','理由':'応答または外部観測参照が欠損'}
    from .知覚 import digest
    f=応答['frame'][-1]
    if 知覚(f)['幅']is None and(len(f)!=64 or any(len(row)!=64 for row in f)):return {'連続黒数':None,'状態':'HOLD','理由':'frame寸法不正'}
    current_sha=digest(応答)
    if 前履歴 and 前履歴.get('外部観測参照')==外部観測参照:
        if 前履歴.get('応答SHA256')!=current_sha:return {'連続黒数':None,'状態':'HOLD','理由':'同一外部観測参照の応答が競合'}
        return dict(前履歴)
    try:a=作用番号(応答.get('action_input',{}).get('id'))
    except (TypeError,ValueError):a=None
    reset=a==0 or bool(応答.get('full_reset'))or(前履歴 is not None and (前履歴.get('GUID')!=応答.get('guid')or 前履歴.get('完了数')!=応答.get('levels_completed')))
    black=all(v==0 for v in f[0]+f[-1]);old=None if 前履歴 is None else 前履歴.get('連続黒数')
    count=0 if not black else 1 if reset else old+1 if type(old)is int else None
    return {'連続黒数':count,'上下HUD全黒':black,'外部観測参照':外部観測参照,'応答SHA256':current_sha,'GUID':応答.get('guid'),'完了数':応答.get('levels_completed'),'状態':'観測可能'if count is not None else'HOLD','前状態のみ':True}

def HUD失敗を照会(h,a,連続黒数):
    from hds学習系統 import 外部入力
    if type(連続黒数)is not int or 連続黒数<0:return {'状態':'HOLD','失敗終端':None,'理由':['HUD過去履歴が欠損']}
    payload={'前提直積':符号({'上下端全黒の連続外部観測数':連続黒数,'作用番号':a})};r=h.照会する(外部入力(payload,HUD境界));ps=[p for p in r.内容['予測群']if tuple(p['結果経路'])==('次応答はGAME_OVER',)];vs={p['予測値']for p in ps};value=next(iter(vs))if len(vs)==1 and r.状態!='断定保留'else None
    return {'状態':'HOLD'if value is None else'失敗終端支持'if value else'この境界内で失敗終端なし支持','失敗終端':value,'入力':payload,'HDS状態':r.状態,'予測':ps,'理由':r.内容['断定保留理由群']}

def 終端境界付き全候補(frame,available,h,*,全個体対応=None,直近水平実測同方向役割=None,HUD履歴=None):
    r=全候補(frame,available,h,全個体対応=全個体対応,直近水平実測同方向役割=直近水平実測同方向役割)
    count=None if HUD履歴 is None else HUD履歴.get('連続黒数')
    if len(frame)!=64 or any(len(row)!=64 for row in frame):count=None
    elif HUD履歴 is not None and HUD履歴.get('上下HUD全黒')!=all(v==0 for v in frame[0]+frame[-1]):count=None
    for c in r['全作用候補']:
        c['元局所状態']=c['状態'];guard=HUD失敗を照会(h,c.get('id'),count);c['失敗境界照会']=guard
        if guard['失敗終端']is not False:
            c['状態']='HOLD';c.setdefault('理由',[]).append('失敗終端支持'if guard['失敗終端']else'失敗境界未支持')
    return r
