"""固定の単一閉路候補文法。"""
from .画素 import perception,parse
from .直線 import direction

def observe(a):
 p=perception(a);ts=p['トークン'];marks=parse(a)['標識群'];scales={m['寸法'] for m in marks}
 if len(scales)!=1:return {'適合':False,'理由':'尺度一意でない'}
 step=3*next(iter(scales));cs=[((t['範囲'][0]+t['範囲'][2])/2,(t['範囲'][1]+t['範囲'][3])/2) for t in ts];positions=set(cs);adj=[]
 for i,(x,y) in enumerate(cs):
  ns=[]
  for j,(u,v) in enumerate(cs):
   if i==j:continue
   dx,dy=abs(x-u),abs(y-v)
   if (dx,dy) in [(step,0),(0,step)]:ns.append(j)
   elif dx==dy==step and (x,v) not in positions and (u,y) not in positions:ns.append(j)
  adj.append(ns)
 if not ts or any(len(ns)!=2 for ns in adj):return {'適合':False,'理由':'単一閉路の次数2条件外','次数':[len(v) for v in adj]}
 start=min(range(len(cs)),key=lambda i:(cs[i][1],cs[i][0]));seq=[start];prev=start;cur=min(adj[start],key=lambda i:(cs[i][1],cs[i][0]))
 while cur!=start:
  if cur in seq:return {'適合':False,'理由':'閉路追跡不整合'}
  seq.append(cur);prev,cur=cur,next(i for i in adj[cur] if i!=prev)
 if len(seq)!=len(ts):return {'適合':False,'理由':'複数の独立閉路を含む'}
 area=sum(cs[i][0]*cs[j][1]-cs[j][0]*cs[i][1] for i,j in zip(seq,seq[1:]+seq[:1]))
 if area<0:seq=[seq[0]]+list(reversed(seq[1:]))
 xs,ys=zip(*cs);cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2;controls=[]
 for ar in p['操作標識']:
  dx,dy=direction(a,ar);x,y,r,b=ar['範囲'];ax,ay=(x+r)/2,(y+b)/2
  if dy==0 and ay==cy and ((ax<min(xs) and dx==-1) or (ax>max(xs) and dx==1)):
   controls.append({'操作標識':ar,'向き':[dx,dy],'時計方向係数':dx})
 if len(controls)!=2 or {c['時計方向係数'] for c in controls}!={-1,1}:return {'適合':False,'理由':'閉路中心帯の対向外向き標識がない'}
 return {'適合':True,'対象':ts,'時計順位置番号':seq,'操作群':controls,'隣接候補':adj}
def shift(before,seq,sign,k):
 out=before.copy()
 for t,i in enumerate(seq):out[seq[(t+sign*k)%len(seq)]]=before[i]
 return out
