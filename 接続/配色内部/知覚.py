"""固定知覚文法。色矩形見本/同寸正方形/色見本列/赤枠器具。意味関係は含まない。"""
import sys
from pathlib import Path
from collections import Counter,deque
BASE=Path(__file__).resolve().parents[2]
ROOT=BASE
sys.path[:0]=[str(BASE),str(BASE/'HDS/学習系統/v0.4.2')]
from 接続.ARC3境界 import _盤面列
from 接続.図式観測 import 成分群

def bbox(ps):return min(x for x,y in ps),min(y for x,y in ps),max(x for x,y in ps)+1,max(y for x,y in ps)+1

def connected(ps):
 ps=set(ps);out=[]
 while ps:
  p=min(ps);ps.remove(p);q=[p];s={p}
  while q:
   x,y=q.pop()
   for dx in (-1,0,1):
    for dy in (-1,0,1):
     n=(x+dx,y+dy)
     if n in ps:ps.remove(n);q.append(n);s.add(n)
  out.append(s)
 return out

def read(frame):
 f=_盤面列((frame,))[0];h=len(f);w=len(f[0])
 if h!=64 or w!=64:raise ValueError('公開器具の知覚範囲は64×64に限定')
 counts=Counter(v for r in f for v in r).most_common();bg=counts[0][0]
 if len(counts)>1 and counts[0][1]==counts[1][1]:raise ValueError('背景候補が同率で未確認')
 comps=成分群(f);frames=[];pal=[]
 for c in comps:
  ps=c['点群'];x,y,X,Y=bbox(ps);color=f[y][x] if (x,y) in ps else next(f[b][a] for a,b in ps)
  if color==4 and X-x==Y-y and X-x>=12 and x==0 and y==0:frames.append((x,y,X,Y))
  if color==4 and X-x==Y-y==5:
   vals={f[b][a] for b in range(y+1,Y-1) for a in range(x+1,X-1)}
   if len(vals)==1:pal.append({'色':next(iter(vals)),'矩形':[x,y,X,Y],'クリック':[(x+X-1)//2,(y+Y-1)//2]})
 if len(frames)!=1 or not pal:raise ValueError('参照枠/色見本文法未確認')
 x,y,X,Y=frames[0];inside=connected((a,b) for b in range(y,Y) for a in range(x,X) if f[b][a] not in (bg,4))
 refs=[p for p in inside if bbox(p)[2]-bbox(p)[0]==bbox(p)[3]-bbox(p)[1] and len(p)==(bbox(p)[2]-bbox(p)[0])**2]
 if len(refs)!=1:raise ValueError('見本正方形が一意でない')
 rx,ry,rX,rY=bbox(refs[0]);size=rX-rx
 if size!=10:raise ValueError('現在の固定知覚は観測済み10格子の文法に限定')
 reference=[list(r[rx:rX]) for r in f[ry:rY]]
 parts=connected((a,b) for b in range(Y,h-1) for a in range(w) if f[b][a]!=bg)
 canvases=[p for p in parts if bbox(p)[2]-bbox(p)[0]==bbox(p)[3]-bbox(p)[1]==size and len(p)==size*size and all(f[b][a]!=2 for a,b in p)]
 if len(canvases)!=1:raise ValueError('器具遮蔽/対象正方形不確定')
 cx,cy,cX,cY=bbox(canvases[0]);canvas=[list(r[cx:cX]) for r in f[cy:cY]]
 red=connected((a,b) for b in range(Y,h-1) for a in range(w) if f[b][a]==2)
 if not red:raise ValueError('器具枠なし')
 red.sort(key=len,reverse=True);tx,ty,tX,tY=bbox(red[0]);sign=lambda z:(z>0)-(z<0);direction=(sign(tx+tX-cx-cX),sign(ty+tY-cy-cY))
 toolparts=[p for p in parts if p & red[0]]
 if len(toolparts)!=1:raise ValueError('器具領域の接続不確定')
 colors=Counter(f[b][a] for a,b in toolparts[0] if f[b][a] not in (bg,2))
 if len(colors)!=1 or direction==(0,0):raise ValueError('器具色/方向が一意でない')
 handles=[list(bbox(p)) for p in red[1:] if len(p)>=4]
 device=set().union(*(p for p in parts if any(p & r for r in red)))
 pixels=sorted((a-cx,b-cy,'枠' if f[b][a]==2 else ('固定黒' if f[b][a]==0 and (a,b) not in toolparts[0] else '色')) for a,b in device)
 return {'装置画素':pixels,'背景色':bg,'参照':reference,'参照矩形':[rx,ry,rX,rY],'対象':canvas,'対象矩形':[cx,cy,cX,cY],'色見本':sorted(pal,key=lambda p:p['矩形']),'器具色':next(iter(colors)),'方向':list(direction),'器具矩形':[tx,ty,tX,tY],'小器具矩形群':handles,'大きさ':size}

def classify(s,a):
 i=a['id'];d=a.get('data',{})
 if i in (1,2,3,4):return {'役割':'方向','番号':i}
 if i==5:return {'役割':'広域塗布','番号':i}
 if i==6:
  x,y=d['x'],d['y'];hit=lambda b:b[0]<=x<b[2] and b[1]<=y<b[3]
  p=[z for z in s['色見本'] if hit(z['矩形'])]
  if len(p)==1:return {'役割':'色選択','番号':i,'色':p[0]['色']}
  h=[b for b in s['小器具矩形群'] if hit(b)]
  if len(h)==1:return {'役割':'小域塗布','番号':i}
 return {'役割':'未対応','番号':i}
