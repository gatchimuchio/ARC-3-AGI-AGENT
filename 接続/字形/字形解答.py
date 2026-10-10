"""公開frame/available_actionsと外部HDSによる解答関係候補。実行権限を発行しない。"""
from dataclasses import asdict
from .字形原語 import *
from .字形群制約 import *


def 公開教師を教える(系,教師群):
    from hds学習系統 import 外部入力
    return [asdict(系.処理する(外部入力(t['内容'],t['境界']))) for t in 教師群]


def _照会(系,内容,対象境界,結果,記録):
    from hds学習系統 import 外部入力
    q=系.照会する(外部入力(内容,対象境界));記録.append({'境界':対象境界,'条件':内容,'HDS':asdict(q)})
    values=[p['予測値'] for p in q.内容['予測群'] if tuple(p['結果経路'])==(結果,)]
    return values[0] if q.状態!='断定保留' and len({repr(v) for v in values})==1 else None


def 字形解答を構成する(系,frame,available_actions):
    out={'適用性':'未確認','対象群':[],'関係群':[],'目標候補群':[],'作用候補群':[],'保留理由群':[],'照会記録':[],
         '出所':{'HDS学習':['見本左右群の軌道所属関係','選択枠役割から解答対象','公開の可視記号族作用'],
                '固定候補演算':['7×7字形と群の知覚','D4軌道同一視','全順序付き群分解','単記号対グラフ閉包','逆向き群割当','二段の記号変数同値制約'],
                '作用境界':'D4軌道をすべて生成/選択できるとは仮定しない'},'実行許可':False}
    try:
        actions=[]
        for a in available_actions:
            a=getattr(a,'name',a)
            if isinstance(a,str):a=({'RESET':0,**{'ACTION'+str(i):i for i in range(1,8)}}).get(a)
            if type(a) is not int or not 0<=a<=7:raise ValueError('available_actionsの外部記号が不正')
            actions.append(a)
        p=広い構文(frame)
        if p['状態']!='構文成立':
            out['適用性']='構造上不適用';out['保留理由群'].append({'種別':'構造文法','理由':p['理由']});return out
        out['対象群']=[{'役割':'見本対','対':p['見本対']},{'役割':'入力列','群':p['入力']},{'役割':'表示目標または解答列','群':p['表示目標']}]
        if p[役割入力] is None:out['保留理由群'].append({'種別':'作用条件不足','理由':'選択枠の役割を一意に観測できない'});return out
        role=_照会(系,{役割入力:p[役割入力]},役割境界,役割結果,out['照会記録'])
        relation=[_照会(系,{入力名:b},境界,結果名,out['照会記録']) for b in (False,True)]
        if type(role) is not bool or relation!=[False,True]:
            disputed=any(q['HDS']['内容'].get('係争中原理群') or q['HDS']['内容'].get('競合群') for q in out['照会記録'])
            out['保留理由群'].append({'種別':'HDS隔離/競合' if disputed else 'HDS未支持','理由':'解答役割または対所属関係をHDSが支持しない'});return out
        out['適用性']='適用可能';out['関係群'].append({'関係':'見本左右の所属同値','HDS支持':True,'解答役割':'見本編集' if role else '解答列編集'})
        goal_sequences=[]
        if role:
            colors={(a['色'],b['色']) for a,b in p['見本対']};result=編集一段(系,p) if len(colors)==1 else 編集二段(系,p)
            out['目標候補群']=result['候補'];out['関係群'].append({'固定演算':'逆向き群制約','棄却理由数':result.get('棄却理由数',{}),'棄却枝':result.get('棄却枝',[])})
            out['保留理由群'].append({'種別':'作用条件不足','理由':'各候補の実字形・同一欄の到達履歴・未指定中間字形が未確認。複数の支持済み解自体は不確実性と同一視しない'})
        else:
            simple=問題を読む(frame)
            if simple['状態']=='構文成立':
                result=解答を構成する(系,{k:v for k,v in simple.items() if k not in ('現在解答','群')})
                for c in result['候補群']:
                    seq=[族値(f[0]) for f in c['字形候補因子']];goal_sequences.append(seq)
                    out['目標候補群'].append({'入力分解':c['入力分解'],'目標記号族列':seq,'意味':'方向同一視した目標内容。D4画像集合は操作可能性を意味しない'})
            else:
                result=固定見本グラフ(系,p)
                if result['候補'] and all(len(c)==1 for c in result['候補']):
                    seq=[c[0] for c in result['候補']];goal_sequences.append(seq);out['目標候補群'].append({'目標記号族列':seq,'固定演算':'対グラフ閉包'})
                elif result['候補']:out['目標候補群'].append({'目標記号族候補因子':result['候補']})
            if not out['目標候補群']:out['保留理由群'].append({'種別':'関係未同定','理由':result.get('理由','候補なし')})
            target=p['表示目標'];x,y=target['位置'];marked=[]
            for j,m in enumerate(target['字形']):
                n=sum(frame[yy][xx]==0 for yy in range(max(0,y-3),min(len(frame),y+10)) for xx in range(x+7*j,x+7*j+7))
                if n==14:marked.append(j)
            if len(marked)==1 and goal_sequences:
                slot=marked[0];current=族値(target['字形'][slot]);desired={seq[slot] for seq in goal_sequences if len(seq)==len(target['字形'])}
                if current not in desired:
                    for action in (1,2):
                        if action not in actions:continue
                        value=_照会(系,{'現在記号':current},f'公開解答記号循環:軌道族:ACTION{action}','次記号',out['照会記録'])
                        if value in desired:out['作用候補群'].append({'作用番号':action,'対象欄':slot,'位置':[x+7*slot,y],'予測目標族':value,'採用範囲':'可視記号族の観測支持範囲','実字形確認':'次の実観測が必要','実行許可':False})
                        elif value is None:out['保留理由群'].append({'種別':'HDS作用未支持','作用番号':action,'理由':'この現在記号族の次状態予測なし'})
            out['保留理由群'].append({'種別':'作用条件不足','理由':'同一欄の実字形履歴と作用後の達成判定は別途必要。cursor移動方針は未実装'})
        if not out['目標候補群']:
            out['適用性']='未確認'
            if not any(r['種別']=='関係未同定' for r in out['保留理由群']):out['保留理由群'].append({'種別':'関係未同定','理由':result.get('理由','固定候補文法内で目標を構成できない')})
        out['保留理由群'].append({'種別':'実験実行境界','理由':'この接続は目標/作用候補のみ。live作用とfresh成功は未実行'})
        return out
    except (ValueError,TypeError,KeyError,IndexError) as e:
        out['適用性']='未確認';out['保留理由群'].append({'種別':'入力/接続例外','理由':type(e).__name__+': '+str(e)});return out
