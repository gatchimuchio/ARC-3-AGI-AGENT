from . import 基礎 as e
from . import 基礎 as v
from .再識別 import all_decompositions,selected_hypotheses,normalize
def observed(frame,shapes,expected_axes):
 s=v.scene(frame);B=s['本体'];blocked=s['目標']|{p for p in B if any(p[a['方向']]==a['位置']for a in s['軸'])};W={p for p in B-blocked if s['セル'][p]['中心']==0};axsel=[i for i,a in enumerate(s['軸'])if a['選択']];ds,domain=all_decompositions(B,shapes);hs=selected_hypotheses(ds,W,s['目標'],s['軸'],axsel[0]if len(axsel)==1 else None);reason=[]
 if s['不明']or len(s['軸'])!=expected_axes:reason.append('セル/軸の知覚不確定')
 if len(axsel)>1:reason.append('選択軸の一意性不成立')
 if len(hs)!=1:reason.append('前観測だけで分解/選択対応が一意ではない')
 if hs and hs[0]['選択対応'][0]=='本体'and not W:reason.append('白標識なし。候補一つでも明示選択証拠と数えない')
 if not W and not axsel:reason.append('明示的な選択標識を観測できない')
 return {'観測':e.compact(s),'白標識':W,'軸':s['軸'],'分解探索':domain,'全選択仮説':hs,'HOLD':reason}
def subject(obs):
 h=obs['全選択仮説'][0];role,i=h['選択対応']
 if role=='鏡軸':return ('軸',obs['軸'][i]['方向'])
 sig=normalize(h['構成群'][i]);matches=[j for j,p in enumerate(h['構成群'])if normalize(p)==sig]
 return ('形',tuple(sorted(sig)))if len(matches)==1 else None
