"""既存一巡の原記憶保存/相記録を再利用する独立付記。正本commitやAction送信をしない。"""
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from .ARC3境界 import 観測,観測する,境界違反
from .共通観測経路 import 作用応答を相別に記録する
from .観測駆動一巡 import _保存する,_記録作用を検査する,原記憶保存失敗
from .連動規則 import 観測から候補を構成する
from .連動内部.知覚 import 知覚,digest
from .連動内部.順序境界 import _作用


def _一巡前後を照合する(直前,現在,記録作用,前受付,前履歴,現在受付,現在履歴,現在公開応答):
    if not isinstance(直前,観測)or not isinstance(現在,観測):raise 境界違反('境界検査済みの前後公開観測が必要')
    action=_記録作用を検査する(記録作用)
    snapshots=[]
    for label,obs,receipt,authoritative in (('前',直前,前受付,前履歴),('現在',現在,現在受付,現在履歴)):
        if not isinstance(receipt,dict)or receipt.get('状態')!='受理':raise 境界違反(label+'受付が未受理')
        state=receipt['次履歴'];latest=state['最新'];oid=latest['観測識別子']
        if receipt['受理観測']!=latest or obs.指紋!=latest['観測指紋']:raise 境界違反(label+'観測ID/指紋と受理票が不一致')
        if not isinstance(authoritative,dict) or authoritative.get('待受作用')is not None:raise 境界違反(label+'正本が欠損又は待受中')
        for field in ('最新','接続識別子','HUD履歴','履歴区間'):
            if authoritative.get(field)!=state.get(field):raise 境界違反(label+'正本と受理票が不一致:'+field)
        entry=state['受理観測台帳'][oid]
        if authoritative['受理観測台帳'].get(oid)!=entry or entry['観測通番']!=obs.観測通番:raise 境界違反(label+'受理台帳が破損/通番不一致')
        snapshots.append((state,latest,entry))
    ps,pl,pe=snapshots[0];cs,cl,ce=snapshots[1]
    if ps['接続識別子']!=cs['接続識別子'] or 直前.ゲーム識別子!=現在.ゲーム識別子:raise 境界違反('前後connection/gameが不一致')
    if 現在.観測通番!=直前.観測通番+1 or ce['直前観測識別子']!=pl['観測識別子']:raise 境界違反('非隣接/順序逆転又は直前観測参照が不一致')
    if cs['受理観測台帳'].get(pl['観測識別子'])!=pe or 現在履歴['受理観測台帳'].get(pl['観測識別子'])!=pe:raise 境界違反('現在台帳の前観測証拠が前受付と不一致')
    aid=ce['作用識別子']
    if not aid or cs['使用済み作用'].get(aid)!=cl['観測識別子']or 現在履歴['使用済み作用'].get(aid)!=cl['観測識別子']:raise 境界違反('現在作用の消費済み対応が未確認')
    if digest(現在公開応答)!=ce['応答SHA256'] or 観測する(現在公開応答,観測通番=現在.観測通番).指紋!=現在.指紋:
        raise 境界違反('公開応答原票と受理票/現在観測が不一致')
    public_action=_作用(現在公開応答['action_input'],現在.ゲーム識別子)
    if action!={'作用番号':public_action['id'],'引数':public_action['data']}:raise 境界違反('記録作用と独立公開action_inputが不一致')
    reset=action['作用番号']==0
    if ce['種別']!=('RESET応答'if reset else'作用応答'):raise 境界違反('前後RESET境界種別が不一致')
    if not reset and 直前.実行識別子!=現在.実行識別子:raise 境界違反('通常Actionの前後GUIDが不一致')
    if not reset and 現在.完了レベル数 not in(直前.完了レベル数,直前.完了レベル数+1):raise 境界違反('通常Actionの完了境界が未確認')
    expected='独立RESET境界'if reset else'独立レベル境界'if 現在.完了レベル数!=直前.完了レベル数 else'順序一致'
    if 現在受付['境界']!=expected or cs['履歴区間']!=ps['履歴区間']+int(expected!='順序一致'):raise 境界違反('前後の履歴区間/RESET境界が不一致')
    return action,{'状態':'一致','前観測ID':pl['観測識別子'],'現在観測ID':cl['観測識別子'],'前通番':直前.観測通番,'現在通番':現在.観測通番,
                   '作用ID':aid,'境界':expected,'根拠':'隣接受理票/単一正本/全応答SHA/公開action_inputを照合','環境送信証明':False}


def 記録観測の連動付記を処理する(学習系,直前,記録作用,現在,*,前受付,前履歴,現在受付,現在履歴,現在公開応答,記憶先,出所,
                     前個体対応=None,前水平役割=None,現在個体対応=None,現在水平役割=None):
    """公開記録/人工fixture用。collectorの送信前pending保存や正本commitの代替ではない。"""
    record={'方式':'公開記録観測駆動の連動独立付記','作用発生主体':'呼出側の公開記録。agent実行を主張しない',
            '観測前状態':asdict(直前)if isinstance(直前,観測)else 直前,'作用':記録作用,'観測後状態':asdict(現在)if isinstance(現在,観測)else 現在,'出所':出所,
            '前受付':前受付,'現在受付':現在受付,'前正本履歴':前履歴,'現在正本履歴':現在履歴,
            '局所履歴入力':{'前個体対応':前個体対応,'前水平役割':前水平役割,'現在個体対応':現在個体対応,'現在水平役割':現在水平役割},'公開応答':現在公開応答,'処理状態':'原票受領','失敗':None,'保留条件':[],
            '実行許可':False,'環境作用送信':False,'追加学習':False,'正本履歴commit':False,
            '未接続保証':['実collector事前pending永続化','受理原記憶後の正本commit','再起動復元']}
    # 不正/未受理の前後対応は正規Runtime Memoryへ入れず、照会前にHOLD隔離する。
    valid=True
    try:
        action,proof=_一巡前後を照合する(直前,現在,記録作用,前受付,前履歴,現在受付,現在履歴,現在公開応答)
        record['公開作用対応']=proof
    except Exception as exc:
        valid=False;record['処理状態']='HOLD隔離';record['失敗']={'型':type(exc).__name__,'理由':str(exc)}
        record['保留条件'].append('前後対応未成立。HDS照会/正規Memory混入をしない')
    ref={'記憶種別':'Runtime Memory原記憶'if valid else'HOLD隔離証拠','一巡識別子':uuid4().hex}
    try:
        directory=Path(記憶先)/(ref['一巡識別子']if valid else'HOLD隔離証拠/'+ref['一巡識別子']);directory.mkdir(parents=True,exist_ok=False)
    except Exception as exc:raise 原記憶保存失敗(str(exc),record,ref)from exc
    ref.update({'原票':str(directory/'原票.json'),'結果':str(directory/'結果.json')})
    _保存する(directory/'原票.json',record)
    if not valid:
        _保存する(directory/'結果.json',record)
        return {'状態':'HOLD','記憶参照':ref,'記録':record,'実行許可':False,'正本履歴commit':False,'正規Memory混入':False}
    try:
        before=観測から候補を構成する(学習系,直前,受付=前受付,現在履歴=前履歴,全個体対応=前個体対応,
                         直近水平実測同方向役割=前水平役割,出所=出所)
        record['前候補']=before
        matching=[i for i,c in enumerate(before['作用候補群'])if c['作用番号']==action['作用番号']and c['引数']==action['引数']]
        record['候補との作用照合']={'一致候補番号':matching,'状態':'完全一致'if matching else'候補と不一致',
                          '注意':'全候補に含むことと、HDS支持/採用/実行とは別'}
        record['可視差分']=作用応答を相別に記録する(直前,現在,action['作用番号'])
        record['全相知覚']=[{'応答相':i,'知覚':知覚(f)}for i,f in enumerate(現在.盤面列)]
        groups=[c for c in before['全作用群']if c['id']==action['作用番号']]
        record['局所予測照合']=[]
        for c in groups:
            for hyp in c['全個体対応候補']:
                predictions=sorted(tuple(x)for x in hyp['予測個体位置'])
                record['局所予測照合'].append({'前個体配置':hyp['前個体配置'],'予測個体位置':predictions,'局所採否':c['状態'],
                    '全相比較':[{'応答相':p['応答相'],'駒位置一致':bool(predictions)and predictions==sorted(tuple(x)for x in p['知覚']['駒']),
                            '知覚HOLD':p['知覚']['HOLD']}for p in record['全相知覚']],
                    '因果確定':False,'目標必要十分性':'HOLD'})
        record['次観測候補']=観測から候補を構成する(学習系,現在,受付=現在受付,現在履歴=現在履歴,
                        全個体対応=現在個体対応,直近水平実測同方向役割=現在水平役割,出所=出所)
        record['失敗条件']={'公開終了状態':現在.状態,'失敗終了を観測':現在.状態=='GAME_OVER'}
        record['成立条件']={'公開完了増分':現在.完了レベル数-直前.完了レベル数,'目標因果':'未確定'}
        record['保留条件']+=record['可視差分']['保留理由群']+before['保留理由群']+record['次観測候補']['保留理由群']
        record['処理状態']='独立付記の照会完了'
    except Exception as exc:
        record['処理状態']='途中例外';record['失敗']={'型':type(exc).__name__,'理由':str(exc)}
        record['保留条件'].append('一巡未完了。原票/全途中成果を保持し規則へ昇格しない')
        _保存する(directory/'結果.json',record)
        raise
    _保存する(directory/'結果.json',record)
    return {'記憶参照':ref,'記録':record,'実行許可':False,'正本履歴commit':False}
