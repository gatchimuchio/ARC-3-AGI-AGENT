import json
from . import 格子 as S
G=S.G
BOUNDARIES={r:'公開格子状態:単根矩形の'+r+'作用' for r in ('根','腕','珠')}
class StateModel:
 def __init__(self,h,*,share_queries=False):self.h=h;self.share_queries=share_queries;self.cache={};self.queries=[]
 def ask(self,role,key):
  k=(role,key)
  if self.share_queries and k in self.cache:return self.cache[k]
  out=self.h.照会する(G.外部入力({'関係前提':key},BOUNDARIES[role]));vs=[p['予測値'] for p in out.内容['予測群'] if tuple(p['結果経路'])==('状態作用',)]
  q={'境界':BOUNDARIES[role],'前提':key,'状態':out.状態 if vs else '断定保留','予測':vs,'内容':out.内容,'照会番号':len(self.queries)};self.queries.append(q)
  if self.share_queries:self.cache[k]=q
  return q
 def predict(self,state,context,action):
  g=S.geometry(state,context,action);labels={};qs=[];reasons=[]
  for role in ('根','腕'):
   q=self.ask(role,g['入力'][role]);qs.append(q)
   if q['状態']=='出力' and len(set(q['予測']))==1:labels[role]=q['予測'][0]
   else:reasons.append(role+'作用に支持なし/不確実性')
  labels['珠']={}
  for color,key in g['入力']['珠'].items():
   q=self.ask('珠',key);qs.append(q)
   if q['状態']=='出力' and len(set(q['予測']))==1:labels['珠'][color]=q['予測'][0]
   else:reasons.append('珠作用に支持なし/不確実性')
  result={'状態':'断定保留','前提':g,'予測作用':labels,'照会参照':[q['照会番号'] for q in qs],'保留理由':reasons,'実行許可':False}
  if reasons:return result
  if any(v not in ('不変','作用方向一格') for v in [labels['根'],labels['腕'],*labels['珠'].values()]):result['保留理由']=['更新語彙外'];return result
  try:nextstate=S.apply_predictions(state,context,action,labels)
  except ValueError as err:result['保留理由']=[str(err)];return result
  result.update({'状態':'可視格子次状態候補','次状態':nextstate,'次根色列':S.root_sequence(nextstate)})
  return result
