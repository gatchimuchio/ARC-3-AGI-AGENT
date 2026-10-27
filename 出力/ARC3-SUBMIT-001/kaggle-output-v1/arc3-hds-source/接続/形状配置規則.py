"""日本語正本の形状・選択・局所・投射関係。学習は固定HDSの通常API。"""
import json
from collections import Counter as 頻度表
from .形状配置知覚 import 外接矩形
方向候補={1:(0,-3),2:(0,3),3:(-3,0),4:(3,0)}
目標境界="公開図形:輪郭目標と成功占有形の対応"
局所境界="公開図形:自由隣接と搬送候補の局所配置から相対変位"
投射境界="公開図形:接触対象の前方地形と投射変位"
選択境界="公開図形:座標作用の包含対象と選択マーカー"

def 局所前提を読む(盤面, obj, 作用番号):
    dx, dy = 方向候補[作用番号]
    新領域 = {(x + dx, y + dy) for x, y in obj['点']} - obj['点']
    範囲内 = all((0 <= x < len(盤面[0]) and 0 <= y < len(盤面) for x, y in 新領域))
    free = 範囲内 and {盤面[y][x] for x, y in 新領域} <= {1, 4}
    x, y = obj['位置']
    前方 = (dx // 3, dy // 3)
    側方 = (-前方[1], 前方[0])
    搬送群 = sorted((((候補 - x) * 前方[0] + (要素 - y) * 前方[1], (候補 - x) * 側方[0] + (要素 - y) * 側方[1], 値) for 要素, row in enumerate(盤面) for 候補, 値 in enumerate(row) if 値 in (12, 13)))
    return {'移動先自由': free, '搬送候補相対配置': json.dumps(搬送群, separators=(',', ':'))}

def 投射前提を読む(盤面, 選択索引群, 被接触対象, 作用番号):
    dx, dy = 方向候補[作用番号]
    前方列 = []
    対象領域 = set(map(tuple, 被接触対象['点']))
    選択領域 = set(map(tuple, 選択索引群['点']))
    for 段 in range(1, 22):
        移動先領域 = {(x + dx * 段, y + dy * 段) for x, y in 対象領域}
        差分領域 = 移動先領域 - 対象領域
        役割頻度 = 頻度表()
        for x, y in 差分領域:
            if not (0 <= x < 64 and 0 <= y < 64):
                役割 = '画面外'
            elif (x, y) in 選択領域:
                役割 = '選択対象'
            else:
                値 = 盤面[y][x]
                役割 = '壁背景' if 値 in (2, 3) else '紫帯' if 値 == 15 else '搬送候補' if 値 in (12, 13) else '別図形' if 値 in (11, 14, 5, 0) else '床輪郭' if 値 in (1, 4) else f'未同定色{値}'
            役割頻度[役割] += 1
        前方列.append(dict(sorted(役割頻度.items())))
    return {'前方接触関係': json.dumps({'選択形': 選択索引群['形'], '被接触形': 被接触対象['形'], '全前方地形': 前方列}, ensure_ascii=False, separators=(',', ':'))}

def 局所前提を符号化する(前状態特徴, 表現):
    return 前状態特徴 if 表現 == '独立二特徴' else {'前状態の直積関係': json.dumps(前状態特徴, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}

def 規則を照会する(学習系, 内容, 境界, 結果名):
    from hds学習系統 import 外部入力
    r = 学習系.照会する(外部入力(内容, 境界))
    全前駆 = [p for p in r.内容['予測群'] if tuple(p['結果経路']) == (結果名,)]
    値群 = {p['予測値'] for p in 全前駆}
    return {'入力': 内容, '状態': r.状態, '値': next(iter(値群)) if r.状態 != '断定保留' and len(値群) == 1 else None, '予測': 全前駆, '保留': r.内容['断定保留理由群']}


def 公開教師を教える(学習系, 教師列):
    """順序を保持した通常の逐次入力。完成/出典は照会条件へ混ぜない。"""
    from hds学習系統 import 外部入力
    for 通番, 教師 in enumerate(教師列):
        if not isinstance(教師.get('内容'), dict) or not isinstance(教師.get('境界'), str):
            raise ValueError('教師は日本語の内容・境界を必要とする')
        応答 = 学習系.処理する(外部入力(教師['内容'], 教師['境界']))
        yield {'教師通番':通番,'種類':教師.get('種類'),'教師':教師['内容'],'境界':教師['境界'],
               '由来':教師.get('由来'),'状態':応答.状態,'内容':応答.内容,'追跡':応答.追跡情報}

def 学習状態を保存する(学習系, 保存先):
    """保存できない状態を保存済みや完了と呼ばない。coreは変更しない。"""
    try:
        学習系.保存する(保存先)
        return {'状態':'保存済み','保存先':str(保存先),'実行許可':False}
    except Exception as 例外:
        return {'状態':'保存保留','保存先':str(保存先),'例外種別':type(例外).__name__,
                '理由':str(例外),'実行許可':False}

def 目標対応全候補を読む(盤面,学習系):
    """原問題だけから全対象×全目標を照会する。原答えは引数に取らない。"""
    from .形状配置知覚 import 形状場面を読む,盤面を検査する
    盤面を検査する(盤面);場面=形状場面を読む(盤面);候補群=[]
    for 対象番号,対象 in enumerate(場面['対象']):
        for 目標番号,目標 in enumerate(場面['目標']):
            照会=規則を照会する(学習系,{'形状一致':対象['形']==目標['形']},目標境界,'成功占有形と対応')
            候補群.append({'対象番号':対象番号,'目標番号':目標番号,'対象':対象,'目標':目標,
                          '照会':照会,'状態':'条件付き支持' if 照会['値'] is True and '未観測枠' in 目標 else '支持' if 照会['値'] is True else '不対応支持' if 照会['値'] is False else '保留',
                          '実行許可':False})
    from itertools import permutations as 全順列
    全割当=[];索引={(候補['対象番号'],候補['目標番号']):候補 for 候補 in 候補群}
    if 場面['対象'] and 場面['目標'] and len(場面['対象'])==len(場面['目標']):
        for 配列 in 全順列(range(len(場面['目標']))):
            対応=list(enumerate(配列));関係=[索引[対] for 対 in 対応]
            状態='不対応支持' if any(例['照会']['値'] is False for 例 in 関係) else '保留' if any(例['照会']['値'] is None for 例 in 関係) else '条件付き支持' if any(例['状態']=='条件付き支持' for 例 in 関係) else '支持'
            全割当.append({'対応':対応,'状態':状態,'実行許可':False})
    return {'観測':場面,'全候補':候補群,'全割当候補':全割当,'実行許可':False,'新規環境成功':False}
