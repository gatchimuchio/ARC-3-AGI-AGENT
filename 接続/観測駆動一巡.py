"""公開記録を駆動源にした一巡。環境stepを呼ばず、作用権限を作らない。"""
from dataclasses import asdict
import json,os,pathlib,tempfile,uuid,math
from .ARC3境界 import 観測,_作用番号,_整数,境界違反
from .共通観測経路 import 公開観測から候補を照会する,作用応答を相別に記録する
from .応答相照合 import 公開応答相を照合する

class 原記憶保存失敗(RuntimeError):
    def __init__(self,理由,記録,参照):
        super().__init__(理由);self.未保存記録=記録;self.保存参照=参照

def _保存する(宛先,記録):
    """別名一時ファイルを完了させてから公開。失敗した一時証拠は削除しない。"""
    一時=None
    try:
        内容=json.dumps(記録,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
        with tempfile.NamedTemporaryFile(dir=宛先.parent,prefix=宛先.name+'.',suffix='.未完了',delete=False) as f:
            一時=f.name;f.write(内容);f.flush();os.fsync(f.fileno())
        os.replace(一時,宛先)
        親=os.open(宛先.parent,os.O_RDONLY | os.O_DIRECTORY)
        try:os.fsync(親)
        finally:os.close(親)
    except Exception as e:
        raise 原記憶保存失敗(str(e),記録,{'宛先':str(宛先),'一時証拠':一時}) from e

def _記録作用を検査する(作用):
    if not isinstance(作用,dict) or set(作用)!={'作用番号','引数'}:raise 境界違反('記録作用の正本形式が不正')
    番号=_作用番号(作用['作用番号']);引数=作用['引数']
    if not isinstance(引数,dict):raise 境界違反('記録作用引数が辞書でない')
    if 番号==6:
        if set(引数)!={'x','y'}:raise 境界違反('記録座標引数が不正')
        for 軸 in ('x','y'):_整数(引数[軸],軸,0,63)
    elif 引数:raise 境界違反('非座標作用に未知の引数')
    return {'作用番号':番号,'引数':dict(引数)}

def _対象関係を照合する(前候補,作用):
    記録=[]
    if 作用['作用番号']!=6:return 記録
    x,y=作用['引数']['x'],作用['引数']['y']
    for i,c in enumerate(前候補['次作用候補群']):
        a=c['候補']
        if a['作用番号']!=6:continue
        xx,yy=a['引数']['x'],a['引数']['y']
        語彙=next(v['結果'] for v in 前候補['語彙別結果'] if v['語彙']==c['語彙'])
        対応=[t for t in 語彙.get('目標候補群',[]) if [x,y] in t.get('本体画素',[]) and [xx,yy] in t.get('本体画素',[])]
        記録.append({'候補番号':i,'可視関係':'同じ本体mask内の座標' if len(対応)==1 else '対象役割一致は未確認',
                    '対象':対応[0]['位置'] if len(対応)==1 else None,'因果同一性':'未確定',
                    '条件':'既存の対象単位作用モデルの適用域内での可視対応。座標依存の反例を排除しない'})
    return 記録

def _候補予測を復元する(直前,前候補,候補番号群):
    全予測=[];未確認=[]
    for i in 候補番号群:
        c=前候補['次作用候補群'][i];元=c['候補'].get('元候補',{});差分群=元.get('全対象予測差分')
        if not isinstance(差分群,list) or not 差分群:
            未確認.append({'候補番号':i,'理由':'全対象画素予測の形式が未対応'});continue
        語彙=next(v['結果'] for v in 前候補['語彙別結果'] if v['語彙']==c['語彙'])
        対象={tuple(t['位置']):t for t in 語彙.get('目標候補群',[]) if '位置' in t}
        予測=[list(r) for r in 直前.最新盤面];割当={};不明=None
        for d in 差分群:
            鍵=d.get('対象',d.get('位置'));前=d.get('前',d.get('前色'));後=d.get('後',d.get('後色'))
            if not isinstance(鍵,(list,tuple)) or tuple(鍵) not in 対象 or type(後) is not int or not 0<=後<=15:
                不明='予測対象又は後色が未対応';break
            画素=対象[tuple(鍵)].get('本体画素',[])
            if not 画素:不明='予測本体maskがない';break
            for x,y in 画素:
                if 直前.最新盤面[y][x]!=前 or ((x,y) in 割当 and 割当[x,y]!=後):不明='予測前提又は画素割当が矛盾';break
                割当[x,y]=後;予測[y][x]=後
            if 不明:break
        if 不明:未確認.append({'候補番号':i,'理由':不明});continue
        全予測.append({'候補番号':i,'予測盤面':予測,'固定保存仮説':'非予測画素は変化しないというモデル。全応答相との残差で監査する'})
    異なる予測={json.dumps(x['予測盤面']) for x in 全予測}
    一意=全予測[0]['予測盤面'] if len(異なる予測)==1 and not 未確認 else None
    return 一意,{'全候補予測':全予測,'未確認':未確認,'異なる画素予測数':len(異なる予測),'因果確定':False}

def _公開報酬を記録する(公開評価):
    if not isinstance(公開評価,dict) or 'reward' not in 公開評価:
        return {'状態':'未観測'}
    値=公開評価['reward'];出所=公開評価.get('出所')
    if type(値) not in (int,float) or (type(値) is float and not math.isfinite(値)) or not isinstance(出所,dict) or not 出所:
        return {'状態':'未観測','理由':'明示報酬の値又は公開出所が未確認'}
    return {'状態':'公開評価に明示された報酬','値':値,'出所':出所}

def 記録観測の一巡を処理する(学習系,直前,記録作用,現在,*,記憶先,出所,図式適用支持=None,公開評価=None):
    """記録作用の一致も不一致も保存し、再観測から次の候補まで照会する。

    新しい教師経験は投入しない。保存はRuntime Memory原記憶の蓄積であり
    規則の採用/改訂ではない。環境や確定作用を受け取らない。
    """
    if not isinstance(直前,観測) or not isinstance(現在,観測):raise 境界違反('境界検査済みの観測が必要')
    記録={'方式':'公開記録観測駆動','作用発生主体':'公開教師記録','観測前状態':asdict(直前),
          '作用':記録作用,'観測後状態':asdict(現在),'出所':出所,'公開評価':公開評価,
          '不可視状態差分':{'状態':'未観測'},'報酬':_公開報酬を記録する(公開評価),
          '因果候補':{'時間的先行確認':False,'因果確定':False},'実行許可':False,'環境作用送信':False,
          '追加学習':False,'処理状態':'原票受領','失敗':None,'保留条件':[]}
    参照={'記憶種別':'Runtime Memory原記憶','一巡識別子':uuid.uuid4().hex}
    try:
        先=pathlib.Path(記憶先)/参照['一巡識別子'];先.mkdir(parents=True,exist_ok=False)
    except Exception as e:raise 原記憶保存失敗(str(e),記録,参照) from e
    参照.update({'原票':str(先/'原票.json'),'結果':str(先/'結果.json')})
    _保存する(先/'原票.json',記録)
    try:
        正規作用=_記録作用を検査する(記録作用)
        前候補=公開観測から候補を照会する(学習系,直前,図式適用支持=図式適用支持);記録['前候補']=前候補
        一致=[]
        for i,c in enumerate(前候補['次作用候補群']):
            a=c['候補']
            if a['作用番号']==正規作用['作用番号'] and a['引数']==正規作用['引数']:一致.append(i)
        記録['候補との作用照合']={'一致候補番号':一致,'状態':'完全一致' if 一致 else '候補と不一致',
                          '注意':'一致してもエージェントが実行/採用した作用とは扱わない。近傍座標を同一化しない。'}
        可視関係=_対象関係を照合する(前候補,正規作用);記録['候補と記録座標の可視関係']=可視関係
        役割一致=[r['候補番号'] for r in 可視関係 if r['可視関係']=='同じ本体mask内の座標']
        予測,予測記録=_候補予測を復元する(直前,前候補,一致 or 役割一致)
        予測記録['適用根拠']='作用引数完全一致' if 一致 else '条件付き本体役割一致。座標依存の反例は未排除' if 役割一致 else '観測作用に対応する候補予測なし'
        記録['予測差分']=予測記録
        相=公開応答相を照合する(学習系,直前,現在,正規作用['作用番号'],前候補,図式適用支持=図式適用支持,予測盤面=予測,予測作用=正規作用 if 一致 else None,記録作用=正規作用)
        記録['因果候補']['時間的先行確認']=not bool(相['相記録']['保留理由群'])
        記録['応答照合']=相;記録['可視差分']=相['相記録'];記録['保留条件']+=相['保留理由群']
        記録['成立条件']={'進行証拠':相['進行証拠'],'公開完了増分':相['相記録']['完了数増分']}
        記録['失敗条件']={'公開終了状態':現在.状態,'失敗終了を観測':現在.状態=='GAME_OVER'}
        記録['対象役割と関係']=[{'語彙':x['語彙'],'対象群':x['結果'].get('対象群',[]),'関係群':x['結果'].get('関係群',[]),'目標候補群':x['結果'].get('目標候補群',[])} for x in 前候補['語彙別結果']]
        記録['作用前提']={'直前利用可能作用':直前.作用可能番号,'前候補保留':前候補['保留理由群'],'候補は未実行':True}
        記録['反証候補']={'確定':False,'照合参照':'応答照合','理由':'候補不一致や次問題への画面切替を規則反証へ自動昇格しない'}
        記録['適用範囲']={'語彙別結果参照':'前候補','新規実行検証':False}
        記録['次観測候補']=公開観測から候補を照会する(学習系,現在,図式適用支持=図式適用支持)
        記録['処理状態']='観測駆動一巡の照会完了'
    except Exception as e:
        記録['処理状態']='途中例外';記録['失敗']={'型':type(e).__name__,'理由':str(e)}
        記録['保留条件'].append('一巡未完了。原票を保持し規則へ昇格しない')
        _保存する(先/'結果.json',記録)
        raise
    _保存する(先/'結果.json',記録)
    return {'記憶参照':参照,'記録':記録,'実行許可':False}
