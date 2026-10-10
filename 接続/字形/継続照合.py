"""前回の条件付き予測を公開応答全相へ照合する。外部作用は実行しない。"""
from copy import deepcopy
from ..共通観測経路 import 作用応答を相別に記録する
from .初回作用 import 初回作用を構成する,作用記号を読む
from .欄観測 import observe,query,可逆字形値
from .字形群制約 import 族値
from .応答知覚 import 応答観測
from .群到達手順 import B,X,Y


def _履歴(現在):
    p=observe(現在.最新盤面)
    out={'観測通番':現在.観測通番,'観測指紋':現在.指紋,'状態':p['状態']}
    if p['状態']=='成立':
        out.update({'選択欄':p['選択欄'],'欄群':p['欄群'],
                    '全欄族':[[族値(p['セル字形'][k]) for k in f] for f in p['欄群']],
                    '全欄実字形':[[可逆字形値(p['セル字形'][k]) for k in f] for f in p['欄群']]})
    return out


def 字形初回を照会する(学習系,現在):
    """単一の公開観測＋同一外部HDS。初回は過去instanceの履歴を継承しない。"""
    out=初回作用を構成する(学習系,現在.最新盤面,現在.作用可能番号)
    out['出所'].update({'観測通番':現在.観測通番,'観測指紋':現在.指紋,
                        '観測履歴':[_履歴(現在)],
                        '履歴の意味':'公開instance対応と実選択/字形の記録のみ。可視再訪をhidden同一性とはしない'})
    if 現在.状態!='NOT_FINISHED':
        out['保留理由群'].append({'種別':'公開状態境界','理由':'進行中以外は次の作用列を継続しない'})
        out['適用性']='未確認'
        for a in out['作用候補群']:a['提示実行順の先頭']=False
    return out


def 字形作用応答を照合する(学習系,直前,現在,前回照会,作用番号):
    """一致後も旧suffixを自動実行せず、現在観測から同じHDSで再照会する。

    ID/指紋は前後対応にのみ使用。目標選択/解法分岐には使用しない。
    RESET・進捗・別instanceでは旧手順を分離し、全相と全代替を保持する。
    """
    phases=作用応答を相別に記録する(直前,現在,作用番号)
    out={'状態':'HOLD','相記録':phases,'全相照合':[],'旧目標候補群':deepcopy(前回照会.get('目標候補群',[])),
         '旧作用候補群':deepcopy(前回照会.get('作用候補群',[])),
         '旧全候補関係群':deepcopy(前回照会.get('関係群',[])),
         '予測':None,'照会記録':[],'保留理由群':list(phases['保留理由群']),
         '後続手順判定':'HOLD','次照会':None,'履歴継承':False,
         '旧観測履歴':deepcopy(前回照会.get('出所',{}).get('観測履歴',[])),
         '観測履歴':deepcopy(前回照会.get('出所',{}).get('観測履歴',[])),
         '実行個体境界':'未確認','実行許可':False}
    holds=out['保留理由群']
    if 前回照会.get('出所',{}).get('観測通番')!=直前.観測通番 or 前回照会.get('出所',{}).get('観測指紋')!=直前.指紋:
        holds.append('前回照会と直前観測が対応しない')
    if 前回照会.get('適用性')!='適用可能':holds.append('前回のHDS/構造支持が未確認')
    try:action=作用記号を読む([作用番号])[0]
    except (TypeError,ValueError,IndexError):action=None;holds.append('作用記号が不正')
    increment=現在.完了レベル数-直前.完了レベル数
    reset=action==0 or 現在.全初期化 or increment<0 or 直前.実行識別子!=現在.実行識別子 or 直前.ゲーム識別子!=現在.ゲーム識別子
    out['実行個体境界']='初期化/別instance' if reset else '公開進捗/終端' if increment>0 or 現在.状態!='NOT_FINISHED' else '同じ公開instance候補'
    if reset or increment>0 or 現在.状態!='NOT_FINISHED':out['観測履歴']=[]
    try:
        perception=応答観測(直前.最新盤面,現在.盤面列,{})
        out['既存全相分類']=perception
        before=observe(直前.最新盤面)
    except (TypeError,ValueError,IndexError,KeyError) as e:
        holds.append('全相知覚例外: '+str(e));return out
    candidates=[a for a in 前回照会.get('作用候補群',[]) if a.get('作用番号')==action]
    procedures=[r['手順'] for r in 前回照会.get('関係群',[]) if r.get('関係')=='全条件付き有限手順']
    if reset:holds.append('旧instanceの予測/選択履歴を継承しない')
    if len(candidates)!=1 or len(procedures)!=1:
        holds.append('実作用に対応する前回支持予測が一意でない/未支持')
    # 未支持作用/RESETでも全相の観測内容は落とさない。
    if before.get('状態')!='成立':holds.append('直前の選択/欄配置が未確認')
    prediction=None
    if len(candidates)==len(procedures)==1 and before.get('状態')=='成立' and not reset:
        try:
            p=procedures[0];a=candidates[0];edge=a['学習支持辺'];graphs=p['欄群グラフ'];selected=p['カーソルグラフ']['初期節点'];nodes=[g['初期節点'] for g in graphs]
            observed_family=[[族値(before['セル字形'][k]) for k in field] for field in before['欄群']]
            if selected!=before['選択欄'] or [g['節点'][n] for g,n in zip(graphs,nodes)]!=observed_family:
                raise ValueError('前回グラフの起点と直前の実選択/全欄族が対応しない')
            if edge['状態']!='抽象支持' or not a.get('HDS条件付き支持') or edge['作用']!=action or a['対象欄']!=selected:
                raise ValueError('前回作用支持辺が対応しない')
            if action in (1,2):
                if edge['始点']!=nodes[selected]:raise ValueError('族作用の起点不一致')
                nodes[selected]=edge['終点']
            elif action in (3,4):
                if edge['始点']!=selected:raise ValueError('カーソル作用の起点不一致')
                selected=edge['終点']
            else:raise ValueError('作用の予測語彙が未対応')
            prediction={'選択欄':selected,'全欄族':[g['節点'][n] for g,n in zip(graphs,nodes)],
                        '変更対象欄':before['選択欄'] if action in (1,2) else None,
                        '予測実字形':'対象欄の正確な次実字形は未予測。非対象は保存を照合',
                        '根拠':deepcopy(a),'作用後再観測必須':True}
            out['予測']=prediction
        except (TypeError,ValueError,KeyError,IndexError) as e:
            holds.append('前回予測の対応/構成が未確認: '+str(e))
    holds.extend(perception['保留理由群'])
    old_values=[]
    for index,frame in enumerate(現在.盤面列):
        item={'相':index,'予測照合':'未確認','選択照合':'未確認','実字形記録':None}
        out['全相照合'].append(item)
        cls=perception['全応答相'][index] if index<len(perception['全応答相']) else None
        item['旧問題分類']=cls
        if not cls or not cls['固定問題内容一致']:
            item['分類']='旧問題と対応不成立'
            if not reset and increment==0:holds.append({'相':index,'理由':'進捗なしで旧問題固定内容/欄配置が変化または未確認'})
            continue
        actual=observe(frame)
        item['実字形記録']=cls.get('全欄実字形')
        item['実選択欄']=actual.get('選択欄')
        if actual.get('状態')!='成立':holds.append({'相':index,'理由':'実選択枠/役割が一意でない'})
        if prediction is None:continue
        expected=prediction['全欄族'];got=cls['全欄族']
        item['予測照合']='一致' if got==expected else '不一致'
        item['選択照合']='一致' if actual.get('状態')=='成立' and actual.get('選択欄')==prediction['選択欄'] else '不一致/未確認'
        item['全欄照合']=[]
        for fi,(target,value) in enumerate(zip(expected,got)):
            keys=before['欄群'][fi];old_exact=[可逆字形値(before['セル字形'][k]) for k in keys]
            exact=cls['全欄実字形'][fi];untouched=fi!=prediction['変更対象欄']
            detail={'欄':fi,'予測族':target,'観測族':value,'族一致':target==value,
                    '作用前実字形':old_exact,'作用後実字形':exact,'実字形不変':old_exact==exact,'非対象欄':untouched}
            item['全欄照合'].append(detail)
            if untouched and old_exact!=exact:holds.append({'相':index,'欄':fi,'理由':'非対象欄の実字形保存に不一致'})
        if item['予測照合']!='一致' or item['選択照合']!='一致':holds.append({'相':index,'理由':'前回予測と全欄族/選択の照合不一致'})
        goal=any(g.get('全欄目標')==got for g in 前回照会.get('目標候補群',[]))
        item['旧目標族充足']=goal;old_values.append(goal)
    if old_values and len(set(old_values))==1 and perception['状態']=='観測成立' and not reset:
        value,report=query(学習系,{X:old_values[0]},B,Y)
        out['照会記録'].append({'境界':B,'条件':{X:old_values[0]},'HDS':report,'予測':value})
        out['達成照合']={'旧目標族充足':old_values[0],'HDS完了増分予測':value,'実測完了増分あり':increment>0,'意味':'同じ応答で増分が観測されたか。未達を提出失敗や無効Actionとは呼ばない'}
        if type(value) is not bool or value!=(increment>0):holds.append('HDSの応答達成関係と観測が未支持/不一致')
    elif not reset:holds.append('旧問題の達成照会条件が一意でない')
    if increment>0 or 現在.状態!='NOT_FINISHED':holds.append('公開進捗/終端。旧手順suffixと選択履歴を新問題へ継承しない')
    if holds:return out
    nxt=字形初回を照会する(学習系,現在)
    if nxt['適用性']!='適用可能':
        holds.append({'次照会未支持':nxt['保留理由群']});out['次照会']=nxt;return out
    history=out['観測履歴']+[_履歴(現在)];nxt['出所']['観測履歴']=history
    out.update({'状態':'全相整合・再照会成立','後続手順判定':'旧suffixを実行せず現在観測から再照会','次照会':nxt,'履歴継承':True,'観測履歴':history})
    return out
