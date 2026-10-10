"""固定4画素知覚・描画・局所語彙。HDS学習とは分離。"""
from ..形状配置知覚 import 外接矩形
方向={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
def 読む(f):
 rings=[]; player=[]; targets=[]
 for y in range(0,60,4):
  for x in range(0,64,4):
   t=[row[x:x+4] for row in f[y:y+4]]; s={v for row in t for v in row}; edge=[t[j][i] for j in range(4) for i in range(4) if i in(0,3) or j in(0,3)]
   if all(t[j][i]==9 for j in(1,2) for i in(1,2)) and len(set(edge))==1 and edge[0] in(0,3,4,5):rings.append({'位置':(x//4,y//4),'枠':edge[0]})
   if 14 in s:player.append((x//4,y//4))
   if 9 in s and 2 in s:targets.append((x//4,y//4))
 # rectangular outlined regions are separated; exposed cells infer bounding rectangle; overlap ambiguity retained later
 todo=set(targets);regions=[]
 while todo:
  st=todo.pop(); c={st}; q=[st]
  for x,y in q:
   for p in[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
    if p in todo:todo.remove(p);c.add(p);q.append(p)
  a,b,A,B=外接矩形(c);regions.append([(x,y) for y in range(b,B+1) for x in range(a,A+1)])
 return {'小枠':rings,'操作体':player,'輪郭領域':regions}

def 初期化(f):
 p=読む(f)
 if len(p['操作体'])!=1:return None,'操作体非一意'
 if any(v in(5,12,15) for row in f[:60] for v in row):return None,'自律担体または特殊地形を含み、この静的条件付き手順は未対応'
 if any(r['枠'] not in(3,4) for r in p['小枠']):return None,'初期非静止枠'
 bg=[list(r) for r in f];rings=tuple(r['位置'] for r in p['小枠']);pos=p['操作体'][0]
 for x,y in rings+(pos,):
  for j in range(4):
   for i in range(4):bg[y*4+j][x*4+i]=1
 face=next((a for a,(dx,dy) in 方向.items() if all(f[pos[1]*4+j][pos[0]*4+i]==0 for j in range(4) for i in range(4) if (dy==-1 and j==0)or(dy==1 and j==3)or(dx==-1 and i==0)or(dx==1 and i==3))),1)
 return (bg,(pos,face,rings,-1)),None

def 描画(bg,s):
 pos,face,rings,held=s;f=[r[:] for r in bg];dx,dy=方向[face];front=(pos[0]+dx,pos[1]+dy)
 for n,(x,y) in enumerate(rings):
  edge=0 if n==held else 3 if held<0 and (x,y)==front else 4
  for j in range(4):
   for i in range(4):f[y*4+j][x*4+i]=9 if i in(1,2) and j in(1,2) else edge
 x,y=pos
 for j in range(4):
  for i in range(4):f[y*4+j][x*4+i]=0 if (dy==-1 and j==0)or(dy==1 and j==3)or(dx==-1 and i==0)or(dx==1 and i==3) else 14
 return f

def 記号前提(bg,s,a):
 pos,face,rings,held=s;vx,vy=方向[face];near=(pos[0]+vx,pos[1]+vy);hasnear=held<0 and near in rings
 own={pos}|({rings[held]} if held>=0 else set())
 def tile(p):
  if p in own:return '自対象跡'
  x,y=p
  if not(0<=x<16 and 0<=y<15):return '観測対象外境界'
  if p in rings:return '3,9' if hasnear and p==near else '4,9'
  return ','.join(map(str,sorted({v for row in bg[y*4:y*4+4] for v in row[x*4:x*4+4]})))
 if a in 方向:
  dx,dy=方向[a];base={'操作':'方向移動','保持数':int(held>=0),'移動先地形列':[tile((p[0]+dx,p[1]+dy)) for p in [pos]+([rings[held]]if held>=0 else [])]}
 else:base={'操作':'把持切替','保持数':int(held>=0),'隣接強調数':int(hasnear)}
 base.update({'移動先周辺の特殊色15':False,'特殊色15隣接関係':[['操作体',[False]*4]]+([[0,[False]*4]]if held>=0 else [[3,[False]*4]]if hasnear else []),'操作体移動先を囲む縞':False})
 return base

def 状態を読む(f):
 p=読む(f)
 if len(p['操作体'])!=1:raise ValueError('操作体非一意')
 pos=p['操作体'][0];matches=[]
 for a,(dx,dy)in 方向.items():
  if all(f[pos[1]*4+j][pos[0]*4+i]==(0 if(dy==-1 and j==0)or(dy==1 and j==3)or(dx==-1 and i==0)or(dx==1 and i==3)else 14)for j in range(4)for i in range(4)):matches.append(a)
 if len(matches)!=1:raise ValueError('操作体の向きテンプレートが非一意又は未確認')
 rings=tuple(sorted(r['位置']for r in p['小枠']));held=[r['位置']for r in p['小枠']if r['枠']==0]
 if len(held)>1 or any(r['枠']==5 for r in p['小枠']):raise ValueError('静的保持対応未確認')
 return pos,matches[0],rings,rings.index(held[0])if held else-1

def 初期輪郭画素を検査(f,regions):
 for region in regions:
  x0=min(p[0]for p in region)*4;x1=(max(p[0]for p in region)+1)*4-1;y0=min(p[1]for p in region)*4;y1=(max(p[1]for p in region)+1)*4-1
  if any(f[y][x]!=(9 if x in(x0,x1)or y in(y0,y1)else 2)for y in range(y0,y1+1)for x in range(x0,x1+1)):raise ValueError('初期輪郭の完全可視矩形テンプレートが未確認')
