"""公開座標作用を色見本列内の関係として教える。解答lookupを持たない。"""
from .図式観測 import _作用番号
from .図式解答教師 import 色見本候補を読む,パネルを検出する,_単色

境界='公開図式:座標作用による対象セルの色列内遷移'


def 色列(frame):
    groups=色見本候補を読む(frame)
    if len(groups)!=1:return None
    g=groups[0]
    if len({c['位置'][0] for c in g})==1:g=sorted(g,key=lambda c:c['位置'][1])
    elif len({c['位置'][1] for c in g})==1:g=sorted(g,key=lambda c:c['位置'][0])
    else:return None
    colors=[c['色'] for c in g]
    return colors if len(set(colors))==len(colors) else None


def 作用教師を読む(before,action,after):
    """1公開作用の教師。対象以外の変化も記録し、全状態の因果閉包を主張しない。"""
    try:番号=_作用番号(action.get('id'))
    except (ValueError,TypeError):return None,{'理由':'作用番号不正'}
    if 番号!=6:return None,{'理由':'座標作用以外'}
    if len(before)!=len(after) or any(len(a)!=len(b) for a,b in zip(before,after)):return None,{'理由':'frame寸法変更'}
    palette=色列(before)
    if palette is None:return None,{'理由':'色列未確定'}
    data=action.get('data',{});x,y=data.get('x'),data.get('y')
    if type(x) is not int or type(y) is not int:return None,{'理由':'座標欠損'}
    cells={(*c['位置'],c['幅']) for p in パネルを検出する(before)[0] for c in p['周辺セル'] if c['位置'][0]<=x<c['位置'][0]+c['幅'] and c['位置'][1]<=y<c['位置'][1]+c['幅']}
    if len(cells)!=1:return None,{'理由':'操作対象の単色セルを一意対応できない','候補':list(cells)}
    xx,yy,w=next(iter(cells));a=_単色(before,xx,yy,w);b=_単色(after,xx,yy,w)
    if a not in palette or b not in palette:return None,{'理由':'作用前後の色が列で対応しない'}
    i,j=palette.index(a),palette.index(b)
    effect='不変' if i==j else '次隣接色' if j==i+1 else '先頭色' if i==len(palette)-1 and j==0 else '他の遷移'
    outside=sum(before[py][px]!=after[py][px] for py in range(len(before)) for px in range(len(before[0])) if not(xx<=px<xx+w and yy<=py<yy+w))
    return {'入力':{'現在色は色列末尾':i==len(palette)-1},'結果':effect,'対象':[xx,yy,w],'前色':a,'後色':b,'色列':palette,'対象外変化画素数':outside,'因果確定':False},None


def 作用を教える(系,teachers):
    from hds学習系統 import 外部入力
    records=[]
    for t in teachers:
        r=系.処理する(外部入力({**t['入力'],'作用色関係':t['結果']},境界))
        records.append({**t,'経験参照':r.追跡情報.get('経験参照'),'状態':r.状態,'内容':r.内容})
    return records


def 次色を照会する(系,palette,current):
    from hds学習系統 import 外部入力
    if current not in palette or len(set(palette))!=len(palette):return {'状態':'HOLD','理由':'色列外'}
    i=palette.index(current);r=系.照会する(外部入力({'現在色は色列末尾':i==len(palette)-1},境界))
    values={p['予測値'] for p in r.内容['予測群'] if tuple(p['結果経路'])==('作用色関係',)}
    effect=next(iter(values)) if len(values)==1 and r.状態!='断定保留' else None
    value=palette[i+1] if effect=='次隣接色' and i+1<len(palette) else palette[0] if effect=='先頭色' else current if effect=='不変' else None
    return {'状態':'HOLD' if value is None else '候補','次色':value,'学習関係':effect,'HDS状態':r.状態,'HOLD理由':r.内容['断定保留理由群'],'予測':r.内容['予測群']}


def 許容色までの作用候補(系,palette,current,allowed):
    """学習済み効果だけで有限色列を探索。任意色を選ぶ操作は導入しない。"""
    route=[];seen=set()
    while current not in allowed:
        if current in seen:return {'状態':'HOLD','理由':'支持作用で目標制約へ到達しない','経路':route}
        seen.add(current);r=次色を照会する(系,palette,current)
        if r['状態']=='HOLD':return {'状態':'HOLD','理由':'次作用未確定','経路':route,'照会':r}
        route.append({'前色':current,**r});current=r['次色']
    return {'状態':'条件付き作用候補','経路':route,'到達候補色':current,'実行許可':False}


def 記録から作用教師を読む(path,expected_sha256,start,end):
    import json
    from hashlib import sha256
    from pathlib import Path
    raw=Path(path).read_bytes()
    if sha256(raw).hexdigest()!=expected_sha256:raise ValueError('作用教師の原票digest不一致')
    rows=[json.loads(s) for s in raw.decode().splitlines() if s.strip()]
    if not 1<=start<=end<len(rows):raise ValueError('作用教師範囲不正')
    teachers=[];holds=[]
    for n in range(start,end+1):
        before=rows[n-1].get('data',rows[n-1]);after=rows[n].get('data',rows[n])
        evidence={'原票SHA256':expected_sha256,'前行':n-1,'後行':n,'作用入力':after.get('action_input')}
        if not before.get('guid') or not before.get('game_id') or not before.get('frame') or not after.get('frame') or (before.get('guid'),before.get('game_id'))!=(after.get('guid'),after.get('game_id')):
            holds.append({**evidence,'理由':'frame欠損/instance/game境界'});continue
        if after.get('full_reset') or after['action_input'].get('id') in (0,'0','RESET'):
            holds.append({**evidence,'理由':'RESET'});continue
        try:
            action_id=_作用番号(after.get('action_input',{}).get('id'));available={_作用番号(x) for x in before.get('available_actions',[])}
        except (ValueError,TypeError):
            holds.append({**evidence,'理由':'作用番号/利用可能作用の形式不正'});continue
        if action_id not in available:
            holds.append({**evidence,'理由':'前観測で利用可能と確認できない作用'});continue
        t,e=作用教師を読む(before['frame'][-1],after['action_input'],after['frame'][0])
        if t:
            x,y,w=t['対象'];later=[_単色(f,x,y,w) for f in after['frame'][1:]]
            level_end=after.get('levels_completed')==before.get('levels_completed',-2)+1
            if later and not level_end and any(c!=t['後色'] for c in later):
                holds.append({**evidence,'理由':'作用内の対象色が途中と末尾で異なる','最初観測':t,'後続色':later});continue
            teachers.append({**t,**evidence,'after全frame数':len(after['frame']),'対象結果相':'最初の公開応答frame','level遷移':level_end})
        else:holds.append({**evidence,**e})
    return teachers,holds


def 攻略候補を構成する(系,frame):
    """HDSの解答・方針・作用予測を合成し、全対象の充足を改めて確認する。"""
    from .図式解答教師 import 作用方針を構成する
    policy=作用方針を構成する(系,frame);palette=色列(frame)
    holds=list(policy['全体保留理由']);cells=[];actions=[];discharged=[]
    if not palette:holds.append('作用色列が未確定')
    for c in policy['セル方針']:
        allowed=c.get('許容色',[])
        if c.get('HDS状態')=='断定保留' or c.get('HOLD理由') or c['方針'] not in ('保持','変更'):
            holds.append({'位置':c['位置'],'理由':'HDS方針/解答制約が未確定','原記録':c});continue
        if c['方針']=='保持':
            route={'状態':'条件付き作用候補','経路':[],'到達候補色':c['現在色']}
        elif palette:
            route=許容色までの作用候補(系,palette,c['現在色'],allowed)
        else:continue
        if route['状態']=='HOLD' or route.get('到達候補色') not in allowed:
            holds.append({'位置':c['位置'],'理由':'支持された作用で全解答条件の充足を確認できない','経路':route});continue
        if any(q.get('HDS状態')=='断定保留' or q.get('HOLD理由') for q in route['経路']):
            holds.append({'位置':c['位置'],'理由':'作用予測がHDS HOLD'});continue
        if len(allowed)>1:
            discharged.append({'位置':c['位置'],'元の保留':'完成色を一意に選べない','解消根拠':'学習した保持方針' if not route['経路'] else '学習した作用効果で最初に到達する色が全制約内','残した許容色':allowed,'採用候補色':route['到達候補色']})
        cells.append({**c,'到達候補色':route['到達候補色'],'全制約充足':True,'作用経路':route['経路']})
        x,y=c['位置'];w=c['幅']
        for step in route['経路']:actions.append({'作用種別':'座標作用','x':x+w//2,'y':y+w//2,'前色':step['前色'],'予測後色':step['次色'],'根拠':step['予測']})
    if not cells or len(cells)!=len(policy['セル方針']):holds.append('すべての対象セルを閉じていない')
    return {'状態':'HOLD' if holds else '全解答制約に整合する条件付き候補経路','上流方針状態':policy['状態'],
            '上流保留の検証':discharged,'残保留':holds,'対象セル':cells,'作用候補':actions,'実行許可':False,
            '境界':'解答/保持変更/作用効果の各HDS HOLDを維持。候補の実作用後の一致とfresh成功は未検証。'}
