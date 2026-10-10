"""観測通番・受付参照・待受作用を照合する外側境界。HDS/教師/旧freezeは変更しない。"""
from copy import deepcopy
from ..ARC3境界 import 観測する, _作用番号, _整数, 境界違反
from .知覚 import digest
from .学習照会 import HUD履歴を進める, 終端境界付き全候補


def _非空(value, name):
    if not isinstance(value, str) or not value.strip():
        raise 境界違反(name + 'が欠損')
    return value


def _作用(action, game):
    if not isinstance(action, dict) or 'id' not in action or not isinstance(action.get('data'), dict):
        raise 境界違反('公開Action形式が欠損')
    number = _作用番号(action['id'])
    data = dict(action['data'])
    if 'game_id' in data:
        if data.pop('game_id') != game:
            raise 境界違反('Actionのgame_idが公開観測と不一致')
    if number == 6:
        if set(data) != {'x', 'y'}:
            raise 境界違反('座標Actionの引数が不正')
        for axis in ('x', 'y'):
            _整数(data[axis], axis, 0, 63)
    elif data:
        raise 境界違反('非座標Actionの追加引数が未確認')
    return {'id': number, 'data': data}


def _保留(state, reason, event=None):
    return {'状態': 'HOLD', '理由': [reason], '次履歴': state,
            '受理観測': None, '受理更新回数': 0, '保持した受付票': event,
            '実行許可': False, '環境作用送信': False}


def 初期RESET待受を登録する(*, 接続識別子, 初期化識別子, 作用識別子, 期待観測通番, ゲーム識別子, 作用, 出所):
    """直前観測のないcollectorの送信前RESETを束縛。受付metadataから逆生成しない。"""
    try:
        stream = _非空(接続識別子, '接続識別子')
        init = _非空(初期化識別子, '初期化識別子')
        aid = _非空(作用識別子, '作用識別子')
        seq = _整数(期待観測通番, '期待観測通番', 0)
        game = _非空(ゲーム識別子, 'ゲーム識別子')
        if not isinstance(出所, dict) or 出所.get('発行段階') != '応答前':
            raise 境界違反('初期RESETの送信前由来が未確認')
        _非空(出所.get('記録参照'), '初期RESETの事前記録参照')
        action = _作用(作用, game)
        if action['id'] != 0:
            raise 境界違反('直前観測なしのbootstrapは明示RESETだけ')
        state = {'接続識別子': stream, '受理観測台帳': {}, '使用済み作用': {},
                 '待受作用': None, 'HUD履歴': None, '履歴区間': 0, '最新': None,
                 '初期化待受': {'初期化識別子': init, '作用識別子': aid, '期待観測通番': seq,
                                'ゲーム識別子': game, '作用': action, '公開原作用': deepcopy(作用),
                                '出所': deepcopy(出所)}}
        return {'状態': '初期RESET待受登録', '次履歴': state, '実行許可': False, '環境作用送信': False}
    except (境界違反, KeyError, TypeError, ValueError) as exc:
        return _保留(None, str(exc))


def 作用待受を登録する(state, *, 作用識別子, 直前観測識別子, 作用):
    """送信前に呼出側が作用を一意に束縛する。登録は送信/承認を意味しない。"""
    try:
        if not isinstance(state, dict):
            raise 境界違反('直前の受理観測がない')
        aid = _非空(作用識別子, '作用識別子')
        if 直前観測識別子 != state['最新']['観測識別子']:
            raise 境界違反('作用の直前観測が最新受理観測と一致しない')
        if state['待受作用'] is not None:
            raise 境界違反('未確定の待受作用が残る')
        if aid in state['使用済み作用']:
            raise 境界違反('使用済み作用識別子の再利用')
        action = _作用(作用, state['最新']['ゲーム識別子'])
        if action['id'] != 0:
            if state['最新']['公開状態'] != 'NOT_FINISHED':
                raise 境界違反('停止/完了状態への通常Action')
            if action['id'] not in state['最新']['available_actions']:
                raise 境界違反('前観測で利用可能でないAction')
        new = dict(state)
        new['待受作用'] = {'作用識別子': aid, '直前観測識別子': 直前観測識別子,
                          '期待観測通番': state['最新']['観測通番'] + 1,
                          '作用': action, '公開原作用': deepcopy(作用)}
        return {'状態': '待受登録', '次履歴': new, '実行許可': False, '環境作用送信': False}
    except (境界違反, KeyError, TypeError, ValueError) as exc:
        return _保留(state, str(exc))


def 順序付きHUDを進める(state, response, event):
    """一外部応答を受理する。重複画素ではなく観測/作用の識別子を照合する。

    event = 接続識別子、観測識別子、観測通番、直前観測識別子、作用識別子、種別。
    初期観測は直前/作用参照がNone。その他は登録済み待受に厳密対応する。
    """
    try:
        if not isinstance(event, dict):
            raise 境界違反('受付票がない')
        stream = _非空(event.get('接続識別子'), '接続識別子')
        oid = _非空(event.get('観測識別子'), '観測識別子')
        seq = _整数(event.get('観測通番'), '観測通番', 0)
        kind = event.get('種別')
        if kind not in ('初期観測', '作用応答', 'RESET応答', '初期RESET応答'):
            raise 境界違反('観測種別が不明')
        if not isinstance(response, dict):
            raise 境界違反('公開応答が辞書でない')
        required = {'guid', 'game_id', 'frame', 'state', 'levels_completed', 'win_levels', 'available_actions', 'full_reset', 'action_input'}
        if not required <= response.keys():
            raise 境界違反('公開応答の必須境界項目が欠損')
        _非空(response['guid'], 'guid')
        obs = 観測する(response, 観測通番=seq)
        if not obs.盤面列 or any(len(f) != 64 or any(len(row) != 64 for row in f) for f in obs.盤面列):
            raise 境界違反('64×64の全応答相が必要')
        actual = _作用(response['action_input'], obs.ゲーム識別子)
        receipt = {'観測通番': seq, '種別': kind, '直前観測識別子': event.get('直前観測識別子'),
                   '作用識別子': event.get('作用識別子'), '応答SHA256': digest(response),
                   'GUID': obs.実行識別子, '接続識別子': stream}
        if event.get('初期化識別子') is not None:
            receipt['初期化識別子'] = event['初期化識別子']
        passive_initial = state is None
        if state is None:
            if kind != '初期観測' or event.get('直前観測識別子') is not None or event.get('作用識別子') is not None or event.get('初期化識別子') is not None:
                raise 境界違反('初回には独立した初期観測受付が必要')
            new = {'接続識別子': stream, '受理観測台帳': {}, '使用済み作用': {},
                   '待受作用': None, 'HUD履歴': None, '履歴区間': 0}
            boundary = '独立初期観測境界'
        elif state.get('初期化待受') is not None:
            pending = state['初期化待受']
            if stream != state['接続識別子'] or kind != '初期RESET応答':
                raise 境界違反('bootstrap接続又は初期RESET応答種別が不一致')
            if event.get('直前観測識別子') is not None or event.get('初期化識別子') != pending['初期化識別子']:
                raise 境界違反('bootstrap初期化/前観測参照が不一致')
            if event.get('作用識別子') != pending['作用識別子'] or seq != pending['期待観測通番']:
                raise 境界違反('bootstrap作用識別子/通番が待受と不一致')
            if obs.ゲーム識別子 != pending['ゲーム識別子'] or actual != pending['作用']:
                raise 境界違反('bootstrap公開Action/ゲームが待受と不一致')
            new = dict(state)
            new['初期化待受'] = None
            new['初期化出所'] = deepcopy(pending)
            new['使用済み作用'] = {pending['作用識別子']: oid}
            boundary = '独立初期RESET応答境界'
        else:
            if stream != state['接続識別子']:
                raise 境界違反('別接続の観測を既存履歴へ混入')
            if oid in state['受理観測台帳']:
                old = state['受理観測台帳'][oid]
                raise 境界違反('既読観測の再送' if old == receipt else '既読観測識別子の内容/通番競合')
            if kind in ('初期観測', '初期RESET応答') or event.get('初期化識別子') is not None:
                raise 境界違反('既存履歴上で初期観測を再宣言')
            latest = state['最新']
            if seq <= latest['観測通番']:
                raise 境界違反('古い又は同じ観測通番')
            if seq != latest['観測通番'] + 1:
                raise 境界違反('観測通番の欠番。順序未確定')
            if event.get('直前観測識別子') != latest['観測識別子']:
                raise 境界違反('直前観測参照が最新受理観測と不一致')
            pending = state['待受作用']
            if pending is None:
                raise 境界違反('対応する待受作用がない')
            if event.get('作用識別子') != pending['作用識別子'] or seq != pending['期待観測通番']:
                raise 境界違反('応答の作用識別子/通番が待受と不一致')
            if actual != pending['作用']:
                raise 境界違反('公開action_inputが登録作用/座標と不一致')
            if obs.ゲーム識別子 != latest['ゲーム識別子']:
                raise 境界違反('ゲーム境界を同じ接続履歴に混入')
            reset = actual['id'] == 0
            if reset != (kind == 'RESET応答'):
                raise 境界違反('RESET作用と受付境界種別の不一致')
            if obs.全初期化 and not reset:
                raise 境界違反('未登録の初期化境界')
            if not reset and obs.実行識別子 != latest['GUID']:
                raise 境界違反('通常Action応答のインスタンス不一致')
            if not reset and obs.完了レベル数 not in (latest['完了数'], latest['完了数'] + 1):
                raise 境界違反('未説明の完了数境界')
            new = dict(state)
            new['使用済み作用'] = {**state['使用済み作用'], pending['作用識別子']: oid}
            new['待受作用'] = None
            boundary = '独立RESET境界' if reset else '独立レベル境界' if obs.完了レベル数 != latest['完了数'] else '順序一致'
            if boundary != '順序一致':
                new['履歴区間'] = state['履歴区間'] + 1
        # ここまで受理するまではHUDの加算関数を一切呼ばない。
        if passive_initial:
            # 初見id=0/full_resetは送信前pendingの証拠でない。表示からfreshを補完しない。
            frame = response['frame'][-1]
            black = all(v == 0 for v in frame[0] + frame[-1])
            count = None if black else 0
            new['HUD履歴'] = {'連続黒数': count, '上下HUD全黒': black, '外部観測参照': oid,
                              '応答SHA256': receipt['応答SHA256'], 'GUID': obs.実行識別子,
                              '完了数': obs.完了レベル数, '状態': 'HOLD' if black else '観測可能', '前状態のみ': True}
        else:
            new['HUD履歴'] = HUD履歴を進める(new['HUD履歴'], response, oid)
        new['受理観測台帳'] = {**new['受理観測台帳'], oid: receipt}
        new['最新'] = {'観測識別子': oid, '観測通番': seq, 'GUID': obs.実行識別子,
                       'ゲーム識別子': obs.ゲーム識別子, '完了数': obs.完了レベル数,
                       '公開状態': obs.状態, 'available_actions': list(obs.作用可能番号),
                       '末尾frameSHA256': digest(response['frame'][-1]), '観測指紋': obs.指紋}
        return {'状態': '受理', '境界': boundary, '次履歴': new, '受理観測': dict(new['最新']),
                '全相数': len(obs.盤面列), 'HUD更新回数': 1, '受理更新回数': 1,
                '個体履歴再初期化が必要': boundary != '順序一致',
                '実行許可': False, '環境作用送信': False}
    except (境界違反, KeyError, TypeError, ValueError, IndexError) as exc:
        return _保留(state, str(exc), event)


def 順序境界付き全候補(frame, available, hds, receipt, *, 現在履歴=None, 全個体対応=None, 直近水平実測同方向役割=None):
    """受理済みの現在観測だけを既存268へ渡す。拒否受付から候補を復活させない。"""
    valid = isinstance(receipt, dict) and receipt.get('状態') == '受理'
    state = receipt.get('次履歴') if valid else None
    if valid:
        valid = (isinstance(現在履歴, dict) and 現在履歴.get('最新') == state['最新'] and
                 現在履歴.get('接続識別子') == state['接続識別子'] and 現在履歴.get('待受作用') is None and
                 現在履歴.get('HUD履歴') == state['HUD履歴'] and
                 digest(frame) == state['最新']['末尾frameSHA256'] and
                 list(available or []) == state['最新']['available_actions'] and
                 receipt.get('受理観測') == state['最新'])
    if not valid:
        out = 終端境界付き全候補(frame, available, hds, 全個体対応=全個体対応,
                                直近水平実測同方向役割=直近水平実測同方向役割, HUD履歴=None)
        out['順序境界'] = {'状態': 'HOLD', '理由': '現在観測の受理又は対応が未確認'}
        return out
    if receipt['個体履歴再初期化が必要']:
        全個体対応 = None
        直近水平実測同方向役割 = None
    out = 終端境界付き全候補(frame, available, hds, 全個体対応=全個体対応,
                            直近水平実測同方向役割=直近水平実測同方向役割, HUD履歴=state['HUD履歴'])
    out['順序境界'] = {'状態': '受理', '観測参照': state['最新']['観測識別子'], '境界': receipt['境界']}
    return out
