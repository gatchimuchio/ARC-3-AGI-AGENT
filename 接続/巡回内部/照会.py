from dataclasses import asdict,is_dataclass
from hds学習系統 import 外部入力
GOAL='公開画素・四隅標識と中央色一致'
ACTION='公開画素・操作標識クリックと色移動'
def ask(h,kind,key,v,result):
 inp=外部入力({key:v},kind);record={'入力':asdict(inp),'結果経路':result}
 try:
  o=h.照会する(inp);raw=asdict(o) if is_dataclass(o) else {'状態':o.状態,'内容':o.内容,'追跡情報':getattr(o,'追跡情報',{})};ps=[p for p in o.内容['予測群'] if tuple(p['結果経路'])==(result,)]
  if o.状態!='出力' or not ps:decision='HOLD'
  elif all(p['予測値'] is True for p in ps):decision='支持'
  elif all(p['予測値'] is False for p in ps):decision='不支持'
  else:decision='HOLD'
  return {**record,'状態':o.状態,'原照会':raw,'予測群':ps,'判定':decision,'採用':decision=='支持'}
 except Exception as e:return {**record,'状態':'照会例外','原照会':{'例外':type(e).__name__,'理由':str(e)},'予測群':[],'判定':'例外','採用':False}
