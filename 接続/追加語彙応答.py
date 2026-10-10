"""既採用の鎖/形状次状態モデルを全応答相へ照合する。実環境作用なし。"""
from .共通観測経路 import 作用応答を相別に記録する, _画素差分
from .追加語彙接続 import _公開値, 形状作用の範囲を読む
from .形状配置知覚 import 形状場面を読む, 全整合分解を読む
from .形状配置検証 import 可視前状態から作用を予測する, _構造
from .鎖内部 import 格子
from .鎖内部.状態 import StateModel


class _照会受信点:
    """同じ公開照会を一回だけ転送し、当該入力・応答・追跡を保持する。"""
    def __init__(self,系):
        self.系=系;self.記録=[]
    def 照会する(self,入力):
        from dataclasses import asdict
        from copy import deepcopy
        記録={'入力':_公開値(asdict(入力)),'応答':None,'例外':None}
        self.記録.append(記録)
        try:
            応答=self.系.照会する(入力)
        except Exception as e:
            記録['例外']={'型':type(e).__name__,'理由':str(e)}
            raise
        記録['応答']=_公開値(deepcopy({'状態':応答.状態,'内容':応答.内容,'追跡情報':応答.追跡情報}))
        return 応答


def _作用(値):
    if not isinstance(値,dict) or set(値)!={'作用番号','引数'}:return None
    n,d=値['作用番号'],値['引数']
    if type(n) is not int or n not in range(8) or not isinstance(d,dict):return None
    if n==6:
        if set(d)!={'x','y'} or any(type(v)is not int or not 0<=v<64 for v in d.values()):return None
    elif d:return None
    return n,d


def _鎖文脈(ctx):
    return {k:v for k,v in ctx.items() if k!='固定画素'}


def _鎖予測(系,盤面,作用):
    state,ctx=格子.extract(盤面);model=StateModel(系)
    divider=格子.G.parse(盤面)['区切り'];legend=盤面[divider:-1]
    pred=model.predict(state,ctx,作用['作用番号'])
    if pred['状態']!='可視格子次状態候補':raise ValueError(str(pred))
    def read(frame):
        now,context=格子.extract(frame)
        return {'意味状態':_公開値(now),'旧構造一致':_鎖文脈(context)==_鎖文脈(ctx) and frame[divider:-1]==legend}
    return {'前意味状態':_公開値(state),'予測意味状態':_公開値(pred['次状態']),
            '予測根拠':pred,'照会記録':model.queries,'画素予測':格子.render(pred['次状態'],ctx),
            '固定仮説':'単根/右軸/矩形/一意色珠。描画は線模様とレールを正規化し画素因果を保証しない。'},read


def _形状予測(系,盤面,作用):
    scene=形状場面を読む(盤面);scope=形状作用の範囲を読む(scene,盤面)
    if scope['状態']!='適用可能':raise ValueError(str(scope))
    inventory=[t['形'] for t in scene['対象']];before=全整合分解を読む(盤面,inventory)
    if len(before)!=1:raise ValueError('直前対象分解が一意でない')
    pred=可視前状態から作用を予測する(系,盤面,before[0],{'id':作用['作用番号'],'data':作用['引数']})
    if pred['理由']:raise ValueError(str(pred))
    before_points=set().union(*(t['点'] for t in before[0]))
    def read(frame):
        choices=全整合分解を読む(frame,inventory)
        if len(choices)!=1:raise ValueError('応答対象分解が一意でない')
        now=choices[0];points=set().union(*(t['点'] for t in now))
        outside=[(x,y,盤面[y][x],v) for y,row in enumerate(frame) for x,v in enumerate(row)
                 if y<63 and (x,y) not in before_points|points and v!=盤面[y][x]]
        return {'意味状態':_公開値(_構造(now)),'旧構造一致':not outside,'対象外差分':outside}
    return {'前意味状態':_公開値(_構造(before[0])),'予測意味状態':_公開値(_構造(pred['予測対象'])),
            '予測根拠':_公開値(pred),'照会記録':pred['照会記録'],'画素予測':None,
            '固定仮説':'二つの3×3青対象の形/位置/選択。対象跡の背景とマーカー/HUDの全画素予測は未確認。'},read


def 追加語彙の全応答を照合する(系,直前,現在,予測作用,語彙,*,記録作用=None):
    """意味状態の前/予測一致を全相に要求し、画素一致・不可視効果と混同しない。"""
    key=_作用(予測作用);actual=_作用(記録作用)
    n=actual[0] if actual is not None else key[0] if key is not None else -1
    # 不正作用は境界を通らない。観測そのものは全相保持する。
    phases=作用応答を相別に記録する(直前,現在,n)
    out={'状態':'保留','語彙':語彙,'相記録':phases,'全相照合':[],'予測':None,
         '保留理由群':list(phases['保留理由群']),'次履歴':None,'実行許可':False,
         '不可視状態差分':{'状態':'未観測'},'因果確定':False,'全画素応答成立':False}
    受信点=_照会受信点(系);out['当該HDS照会記録']=受信点.記録
    holds=out['保留理由群']
    if key is None or actual!=key:holds.append('予測作用と記録実作用の番号/引数が未確認又は不一致')
    if 直前.状態!='NOT_FINISHED':holds.append('直前が実行中でない')
    reset=n==0 or 現在.全初期化 or 直前.実行識別子!=現在.実行識別子 or 直前.ゲーム識別子!=現在.ゲーム識別子
    boundary=reset or 直前.完了レベル数!=現在.完了レベル数 or 現在.状態!='NOT_FINISHED'
    out['旧履歴破棄']=boundary
    if boundary:holds.append('RESET/進捗/終端境界。旧問題の応答と次問題を分離')
    if key is None:
        out['全相照合']=[{'相':i,'状態':'予測作用未確認'} for i in range(len(現在.盤面列))]
        return _公開値(out)
    try:
        maker={'根付き順序鎖':_鎖予測,'形状目標対応':_形状予測}[語彙]
        pred,read=maker(受信点,[list(r) for r in 直前.最新盤面],予測作用);out['予測']=pred
    except Exception as e:
        holds.append({'予測適用未確認':{'型':type(e).__name__,'理由':str(e)}})
        for i in range(len(現在.盤面列)):out['全相照合'].append({'相':i,'状態':'予測未確認'})
        return _公開値(out)
    for i,frame in enumerate(現在.盤面列):
        item={'相':i,'状態':'未確認'};out['全相照合'].append(item)
        if pred['画素予測'] is not None:item['全画素残差']=_画素差分(pred['画素予測'],frame)
        try:
            if len(frame)!=len(直前.最新盤面) or any(len(row)!=len(直前.最新盤面[0]) for row in frame):
                raise ValueError('応答盤面の寸法が直前と一致しない')
            seen=read([list(r) for r in frame]);item.update(seen)
        except Exception as e:
            item['解析未確認']={'型':type(e).__name__,'理由':str(e)};holds.append({'未確認相':i});continue
        item['前意味一致']=seen['意味状態']==pred['前意味状態'];item['予測意味一致']=seen['意味状態']==pred['予測意味状態']
        if not seen['旧構造一致'] or not(item['前意味一致'] or item['予測意味一致']):holds.append({'未説明相':i})
        item['状態']='予測意味一致' if item['予測意味一致'] and seen['旧構造一致'] else '前意味一致' if item['前意味一致'] and seen['旧構造一致'] else '未説明'
    if not out['全相照合'] or out['全相照合'][-1]['状態']!='予測意味一致':holds.append('最新相が支持された意味予測に一致しない')
    out['可視no-op']=pred['前意味状態']==pred['予測意味状態']
    if not holds:
        out['状態']='全相の意味応答照合成立'
        out['次履歴']={'最新観測指紋':現在.指紋,'最新観測通番':現在.観測通番,'作用毎再照会':True,'効力':'意味構造の照合だけ。隠れた変化と全画素因果は未確認'}
    return _公開値(out)
