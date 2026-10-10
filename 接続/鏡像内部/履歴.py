from .再識別 import normalize
from . import 基礎 as e
BOUNDARY="公開鏡像:可視対応による作用後の選択対象保持"
RESULT="作用後も同一対象選択"
def canonical_parts(parts):return sorted((tuple(sorted(normalize(p))),tuple(sorted(map(tuple,p))))for p in parts)
def selected_key(hyp,axes):
 role,idx=hyp['選択対応'];return (role,tuple(sorted(map(tuple,hyp['構成群'][idx]))))if role=='本体'else(role,axes[idx]['方向'],axes[idx]['位置'])

def filter_history(hyps,axes,memory):
 if memory is None:return list(hyps)
 matches=[]
 for h in hyps:
  for pred in memory['全予測']:
   if canonical_parts(h['構成群'])==canonical_parts(pred['構成群'])and[(a['方向'],a['位置'])for a in axes]==[(a['方向'],a['位置'])for a in pred['軸']]and selected_key(h,axes)==selected_key(pred,pred['軸']):matches.append(h);break
 return matches
def facts(obs,action):
 h=obs['全選択仮説'][0];role,idx=h['選択対応'];act=action['id'];other=False
 if act in e.D:kind='方向候補1-4'
 elif act==5:kind='循環候補5'
 elif act==6:
  kind='座標候補6';point=(action['data']['x']//3,action['data']['y']//3);hits=[i for i,p in enumerate(h['構成群'])if point in p]
  if len(hits)>1:return None,'クリックが複数対象に重複し包含対応不確定'
  # 軸包含クリックは別の未学習作用として保留する。
  if not hits and any(point[a['方向']]==a['位置']and a['可動']for a in obs['軸']):return None,'可動軸包含クリック効果は未同定'
  other=bool(hits)and(role!='本体'or hits[0]!=idx)
 else:return None,'方向/循環/座標以外。取消等の選択履歴前提を未同定'
 return {'作用クラス':kind,'前選択役割':'本体'if role=='本体'else'鏡軸','選択可能対象が複数':len(h['構成群'])+sum(a['可動']for a in obs['軸'])>1,'クリックは別対象固有領域':other},None
