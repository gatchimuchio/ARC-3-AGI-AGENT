"""現在画素と同じ外部HDSから代表解・全最短塗布列。完成答え/IDを受け取らない。"""
from collections import deque
from .知覚 import read
from .関係 import query,COPY,X,Y,MASK,MX,MY,TURN,TX,TY,membership,sig
DIRECTIONS=[(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1)]

def goal(h,s):
 cache={};target=[];holds=[]
 for y,row in enumerate(s['参照']):
  dest=[]
  for x,v in enumerate(row):
   allowed=[]
   for p in s['色見本']:
    c=p['色'];b=c==v
    if b not in cache:cache[b]=query(h,COPY,{X:b},Y)[0]
    if cache[b] is None:holds.append([x,y,c,'色対応HDS未支持'])
    elif cache[b] is True:allowed.append(c)
   if len(allowed)!=1:holds.append([x,y,allowed,'色の一意性未成立']);dest.append(None)
   else:dest.append(allowed[0])
  target.append(dest)
 return target,holds

def rotation_graph(h):
 edges=[]
 for d in DIRECTIONS:
  for a in (1,2,3,4):
   v,q=query(h,TURN,{TX:sig([list(d),a])},TY)
   edges.append({'前方向':list(d),'作用':a,'後方向':None if v is None else __import__('json').loads(v),'状態':'HOLD' if v is None else '支持','照会':q})
 return edges

def rotate_path(edges,start,target):
 q=deque([tuple(start)]);parents={tuple(start):None}
 while q:
  at=q.popleft()
  if at==tuple(target):
   path=[]
   while parents[at] is not None:old,e=parents[at];path.append(e);at=old
   return path[::-1]
  for e in edges:
   if tuple(e['前方向'])==at and e['後方向'] is not None and tuple(e['後方向']) not in parents:parents[tuple(e['後方向'])]=(at,e);q.append(tuple(e['後方向']))
 return None

def solve(h,frame,*,小器具支持=None):
 try:s=read(frame)
 except Exception as e:return {'状態':'HOLD','理由':str(e),'実行許可':False}
 target,holds=goal(h,s);out={'状態':'HOLD','代表目標':target,'受理代替':'画素完全一致は代表解の一族。95/100の公開受理解もあり、必要条件とはしない。未説明代替はHOLDで保持。','保留':holds,'実行許可':False}
 if holds:return out
 n=s['大きさ'];flat=sum(target,[]);initial=sum(s['対象'],[]);maskcache={};masks=[];unavailable=[]
 for mode in ('広域塗布','小域塗布'):
  for d in DIRECTIONS:
   if mode=='小域塗布' and (abs(d[0])+abs(d[1])!=1 or not (bool(s['小器具矩形群']) if 小器具支持 is None else 小器具支持)):unavailable.append({'種類':mode,'方向':d,'理由':'小器具/固定幾何語彙外'});continue
   bits=0;missing=[]
   for y in range(n):
    for x in range(n):
     m=membership(d,x,y,n,mode);key=(mode,m)
     if key not in maskcache:maskcache[key]=query(h,MASK+':'+mode,{MX:m},MY)[0]
     v=maskcache[key]
     if type(v) is not bool:missing.append([x,y])
     elif v:bits|=1<<(y*n+x)
   if missing:unavailable.append({'種類':mode,'方向':d,'理由':'上書き関係HDS未支持','画素':missing})
   else:masks.append({'種類':mode,'方向':list(d),'領域':bits})
 # 固定の上書き依存計算。逆向きに最後の同色領域を剥がす全幅BFS。
 start=(1<<(n*n))-1;todo=deque([start]);depth={start:0};parents={start:[]};goals=[];edges=[];rejected=[];best=None
 while todo:
  rem=todo.popleft();dep=depth[rem]
  if best is not None and dep>best:break
  if all(not(rem>>i&1) or flat[i]==initial[i] for i in range(n*n)):
   goals.append(rem);best=dep;continue
  if best is not None:continue
  for mi,m in enumerate(masks):
   overlap=rem&m['領域'];cs={flat[i] for i in range(n*n) if overlap>>i&1}
   if len(cs)!=1:rejected.append({'残':str(rem),'候補':mi,'理由':'未確定領域が空/複色','色候補':sorted(cs)});continue
   c=next(iter(cs));nxt=rem&~m['領域'];edge={'前残':str(rem),'後残':str(nxt),'塗布':{**m,'色':c}};edges.append(edge)
   if nxt not in depth:depth[nxt]=dep+1;parents[nxt]=[edge];todo.append(nxt)
   elif depth[nxt]==dep+1:parents[nxt].append(edge)
 def walks(node):
  if node==start:return [[]]
  return [[e]+p for e in parents[node] for p in walks(int(e['前残']))]
 paths=[p for g in goals for p in walks(g)];rotation=rotation_graph(h);plans=[]
 for path in paths:
  canvas=[r[:] for r in s['対象']];direction=s['方向'];steps=[];ph=[]
  for e in path:
   stamp=e['塗布'];rp=rotate_path(rotation,direction,stamp['方向'])
   if rp is None:ph.append({'理由':'方向作用経路HDS未支持','方向':stamp['方向']});break
   steps.extend({'作用':a['作用'],'種類':'方向','予測方向':a['後方向'],'再観測必須':True} for a in rp);direction=stamp['方向']
   palette=[p for p in s['色見本'] if p['色']==stamp['色']]
   steps.append({'作用':6,'位置':palette[0]['クリック'],'種類':'色選択','予測色':stamp['色'],'再観測必須':True})
   step={'作用':5 if stamp['種類']=='広域塗布' else 6,'種類':stamp['種類'],'方向':direction,'予測色':stamp['色'],'再観測必須':True}
   if step['作用']==6:
    # 座標は作用直前の再知覚で小器具領域を読み直す。予定座標を作らない。
    step['位置']='作用直前観測の一意な小器具矩形中心。未観測ならHOLD'
   steps.append(step)
   for y in range(n):
    for x in range(n):
     if stamp['領域']>>(y*n+x)&1:canvas[y][x]=stamp['色']
  plans.append({'塗布列':path,'具体方向/色作用候補':steps,'終端':canvas,'目標一致':canvas==target,'保留':ph,'実行許可':False})
 out.update({'状態':'条件付き代表解経路' if plans and all(p['目標一致'] for p in plans) else 'HOLD','全最短塗布経路':plans,'塗布候補全域':masks,'未対応候補':unavailable,'方向候補全32':rotation,'探索':{'状態数':len(depth),'全辺':edges,'全親':{str(k):v for k,v in parents.items()},'全棄却':rejected,'残前線':list(todo),'最短塗布数':best},'実作用/応答再観測':'未実行。色/方向/対象外deltaと新問題境界の再照合が必要'})
 return out
