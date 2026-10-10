"""現在の単一HDSと公開観測を注入する独立API。dispatcher/実行gateを変更しない。"""
from dataclasses import asdict
from types import SimpleNamespace
from .ARC3境界 import 観測,境界違反
from .共通観測経路 import _作用候補を共通化する
from .連動内部.知覚 import 知覚,digest
from .連動内部.順序境界 import 初期RESET待受を登録する,作用待受を登録する,順序付きHUDを進める,順序境界付き全候補

class _全照会記録:
    def __init__(self,系):self.系=系;self.記録=[];self.例外=[]
    def 照会する(self,入力):
        row={'順序':len(self.記録),'入力':asdict(入力),'原照会':None,'例外':None};self.記録.append(row)
        try:
            result=self.系.照会する(入力)
            row['原照会']={'状態':result.状態,'内容':result.内容,'追跡情報':result.追跡情報}
            # 原照会の全内容を保持。取り出す予測以外を捨てない。
            return result
        except Exception as exc:
            error={'型':type(exc).__name__,'理由':str(exc)};row['例外']=error;self.例外.append(error)
            return SimpleNamespace(状態='断定保留',内容={'予測群':[],'断定保留理由群':['照会例外。原例外を保持']},追跡情報={})


def _基底(現在,出所):
    return {'適用性':{'状態':'未確認','根拠':[]},'作用適用性':{'状態':'未確認','根拠':['全環境応答/目標の必要十分性は未閉包']},
            '対象群':[],'関係群':[],'目標候補群':[],'作用候補群':[],'次作用候補群':[],
            '全作用群':[],'前提照会記録':[],'規則不確実性':[],'保留理由群':[],
            '応答全盤面':getattr(現在,'盤面列',()),'出所':出所,'順序根拠':None,'HUD根拠':None,
            '公式完了確認':getattr(現在,'状態',None)=='WIN','目標必要十分性':'HOLD',
            '実行許可':False,'環境作用送信':False,'追加学習':False,
            '未接続保証':['collector事前pending永続化','単一正本commit','保存失敗/再起動復元']}


def _具体作用へ展開する(groups,available):
    out=[]
    for index,c in enumerate(groups):
        number=c['id']
        args=({'x':x,'y':y}for y in range(64)for x in range(64))if number==6 else iter([{}])
        for a in args:
            item={'作用番号':number,'引数':a,'採否':c['状態'],'元作用群参照':index,'実行許可':False}
            normalized=_作用候補を共通化する(item,available)
            out.append({**normalized,'採否':c['状態'],'元作用群参照':index})
    return out


def 観測から候補を構成する(系,現在,*,受付,現在履歴,全個体対応=None,直近水平実測同方向役割=None,出所=None):
    """全局所候補/全HUD採否/全照会を返す。局所支持をgoal又は送信許可に昇格しない。"""
    result=_基底(現在,出所);trace=_全照会記録(系)
    try:
        if not isinstance(現在,観測):raise 境界違反('既存の公開観測型が必要')
        available=現在.作用可能番号
        state=受付.get('次履歴')if isinstance(受付,dict)else None
        linked=(isinstance(state,dict) and state.get('最新') is not None and
                現在.指紋==state['最新']['観測指紋'])
        gate_receipt=受付 if linked else {'状態':'HOLD'}
        data=順序境界付き全候補(現在.最新盤面,available,trace,gate_receipt,現在履歴=現在履歴,
                         全個体対応=全個体対応,直近水平実測同方向役割=直近水平実測同方向役割)
        result['全作用群']=data['全作用候補'];result['順序根拠']=data.get('順序境界')
        result['HUD根拠']=None if not linked else state.get('HUD履歴')
        scene=知覚(現在.最新盤面);result['対象群']=scene['駒'];result['関係群']=[{'固定知覚':scene,'個体仮説':全個体対応,'水平役割':直近水平実測同方向役割}]
        if not linked:result['保留理由群'].append('公開観測指紋と受付票の対応が未確認')
        if 現在.状態!='NOT_FINISHED':result['保留理由群'].append('進行中でない公開状態。全候補をHOLD')
        if 現在.状態!='NOT_FINISHED':
            for c in result['全作用群']:c['状態']='HOLD';c.setdefault('理由',[]).append('進行中でない公開状態')
        if trace.例外:
            for c in result['全作用群']:c['状態']='HOLD';c.setdefault('理由',[]).append('全照会中に例外。全候補採用を保留')
        result['作用候補群']=_具体作用へ展開する(result['全作用群'],available)
        result['適用性']={'状態':'適用可能'if not scene['HOLD']and len(scene['駒'])==2 else'未確認','根拠':['固定可視知覚の範囲。HDS作用支持は候補別に記録']}
        result['保留理由群']+=['局所駒変位以外と全応答相のモデルは未完','完成counterと可視関係の必要十分性は未確定','実collector/commit/復元は未接続']
    except Exception as exc:
        result['保留理由群'].append({'例外':type(exc).__name__,'理由':str(exc)})
        # 途中成果を保持し、利用可能全作用を未評価HOLDで補記する。成功候補へ落とさない。
        result['途中例外']={'型':type(exc).__name__,'理由':str(exc)}
        try:
            existing={c['id']for c in result['全作用群']}
            for a in 現在.作用可能番号:
                if a not in existing:
                    c={'id':a,'状態':'HOLD','理由':['候補構成途中例外で未評価'],'全個体対応候補':[],'実行許可':False}
                    if a==6:c['全座標領域']={'x':[0,63],'y':[0,63],'閉整数直積全数':4096}
                    result['全作用群'].append(c)
            for c in result['全作用群']:c['状態']='HOLD'
            result['作用候補群']=_具体作用へ展開する(result['全作用群'],現在.作用可能番号)
        except Exception as nested:result['未評価候補保持例外']={'型':type(nested).__name__,'理由':str(nested)}
    result['前提照会記録']=trace.記録
    result['規則不確実性']=[q for q in trace.記録 if q['例外'] or q['原照会']['状態']=='断定保留']
    result['局所支持作用番号']=[c['id']for c in result['全作用群']if c['状態']=='条件付き局所支持']
    return result
