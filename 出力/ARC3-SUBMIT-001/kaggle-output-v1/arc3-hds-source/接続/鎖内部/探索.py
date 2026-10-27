import json,collections
from . import 状態 as M
S=M.S;C=S.C;G=M.G
def search(frame,available,h,*,share_queries=False):
 start,ctx=S.extract(frame);goal=G.reconstruct(frame,h)
 if goal['状態']!='目標候補生成':return {'状態':'断定保留','理由':'目標が未確定'}
 goals=goal['目標'];target=next(g['順序色列'] for g in goals if g['根色']==ctx['根色'])
 domain=list(C.full_domain(available));groups=collections.defaultdict(list)
 for i,act in enumerate(domain):groups[act['id']].append(i)
 model=M.StateModel(h,share_queries=share_queries);states=[start];indices={start:0};depth=[0];parents=collections.defaultdict(list);todo=collections.deque([0]);edges=[];goalids=[0] if S.root_sequence(start)==target else [];goaldepth=0 if goalids else None
 while todo:
  i=todo[0]
  if goaldepth is not None and depth[i]>=goaldepth:break
  todo.popleft();st=states[i]
  for act,refs in groups.items():
   out=model.predict(st,ctx,act);edge={'元状態':i,'候補群参照':act,'作用番号':act,'予測':out}
   if out['状態']=='可視格子次状態候補':
    nxt=out['次状態']
    if nxt not in indices:
     j=len(states);indices[nxt]=j;states.append(nxt);depth.append(depth[i]+1);todo.append(j)
    j=indices[nxt];edge['先状態']=j
    if depth[j]==depth[i]+1:parents[j].append({'状態':i,'作用':act})
    if S.root_sequence(nxt)==target and j not in goalids:goalids.append(j);goaldepth=depth[j]
   edges.append(edge)

 paths=[]
 # 一つの表示手順をSDK辞書順に取り出す。全同深さ親関係は別に保持。
 for end in goalids:
  path=[];j=end
  while j:
   par=parents[j][0];path.append({'元状態':par['状態'],'作用':par['作用'],'先状態':j});j=par['状態']
  paths.append(list(reversed(path)))
 return {'状態':'条件付き目標経路' if paths else '断定保留','初期状態':start,'文脈':ctx,'目標':goals,'目標列':target,'全候補領域':domain,'全候補群':dict(groups),'状態群':states,'深さ':depth,'全辺群':edges,'全同深さ親':dict(parents),'目標状態群':goalids,'最短表示経路群':paths,'未展開前線':list(todo),'照会記録':model.queries,'探索停止理由':'最初の目標深さの全直前状態を展開済み。より長い経路の前線は保持' if paths else '全支持到達状態の前線が空','全域証明':False,'実行許可':False}
