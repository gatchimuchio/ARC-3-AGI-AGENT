"""既観測形状と現在の可視黒占有から全和集合一致分解。予定/答え/内部IDは受け取らない。"""
import itertools

def normalize(points):
 x=min(p[0]for p in points);y=min(p[1]for p in points);return frozenset((a-x,b-y)for a,b in points)

def all_decompositions(visible_black, observed_shapes):
 B=frozenset(map(tuple,visible_black));domains=[]
 if not B or not observed_shapes or any(not s for s in observed_shapes):return [], {"全形状候補数":[],"全直積数":0,"一致分解数":0,"保留理由":"空占有/空形状の空割当を支持しない"}
 for shape in observed_shapes:
  S=normalize(shape);anchor=min(S);candidates=set()
  for b in B:
   dx,dy=b[0]-anchor[0],b[1]-anchor[1];P=frozenset((x+dx,y+dy)for x,y in S)
   if P<=B:candidates.add(P)
  domains.append(sorted(candidates,key=lambda p:tuple(sorted(p))))
 results=[]
 for ps in itertools.product(*domains):
  if frozenset().union(*ps)==B:results.append(ps)
 return results,{'全形状候補数':[len(x)for x in domains],'全直積数':__import__('math').prod(map(len,domains)),'一致分解数':len(results),'重複禁止なし':True}

def selected_hypotheses(decompositions,white_centers,targets,axes,observed_axis_selection):
 """重なった対象の白点遮蔽は全許容。軸/黄標識で識別できない点を証拠に使わない。"""
 W=frozenset(map(tuple,white_centers));T=frozenset(map(tuple,targets));out=[]
 for parts in decompositions:
  blocked=T|{p for p in frozenset().union(*parts)if any(p[a['方向']]==a['位置']for a in axes)}
  if observed_axis_selection is not None:
   if not W:out.append({'構成群':parts,'選択対応':('鏡軸',observed_axis_selection)})
   continue
  for i,P in enumerate(parts):
   other=frozenset().union(*(Q for j,Q in enumerate(parts)if j!=i));minimum=P-other-blocked;maximum=P-blocked
   if minimum<=W<=maximum:out.append({'構成群':parts,'選択対応':('本体',i)})
 return out
