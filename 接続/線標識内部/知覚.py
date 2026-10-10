import itertools
from . import 基礎 as e
def 形(種類,r):
 if 種類=='直交十字':return frozenset({(x,0) for x in range(-r,r+1)}|{(0,y) for y in range(-r,r+1)})
 if 種類=='中心欠け斜十字':return 形('斜十字',r)-{(0,0)}
 if 種類=='斜十字':return frozenset({(x,x) for x in range(-r,r+1)}|{(x,-x) for x in range(-r,r+1)})
 if 種類=='菱形':return frozenset((x,y) for x in range(-r,r+1) for y in [r-abs(x),-(r-abs(x))])

def 点群(shape,pos):return {(pos[0]+x,pos[1]+y) for x,y in shape}

def 標識を読む(frame):
 markers=e.知覚初期(frame)['標識'];colored={(x,y) for y,row in enumerate(frame[:63]) for x,v in enumerate(row) if v==4};rings=set().union(*(set(t['画素']) for t in markers)) if markers else set();return markers,colored==rings

def 描画(init,os,order):
 f=[[5]*64 for _ in range(63)]
 for t in init['標識']:
  x,y=t['中心']
  for yy in range(y-1,y+2):
   for xx in range(x-1,x+2):f[yy][xx]=t['色'] if (xx,yy)==(x,y) else 4
 for i in order:
  for x,y in os[i]['点']:
   if 0<=x<64 and 0<=y<63:f[y][x]=os[i]['色']
 for o in os:
  if o['選択']:
   x,y=o['中心'];f[y][x]=0
 return f

def 幾何候補(frame,markers,colors,color,templates=None):
 masked=set().union(*({(x,y) for x in range(t['中心'][0]-1,t['中心'][0]+2) for y in range(t['中心'][1]-1,t['中心'][1]+2)} for t in markers));needed={(x,y) for y,row in enumerate(frame[:63]) for x,c in enumerate(row) if c==color and (x,y) not in masked};black=[(x,y) for y,row in enumerate(frame[:63]) for x,c in enumerate(row) if c==0]
 if len(black)!=1:return []
 configs=[]
 if templates is not None:
  for t in templates:
   shape=t['形'];anchor=min(needed) if needed else None;centers={(anchor[0]-x,anchor[1]-y) for x,y in shape} if anchor else {(x,y) for x in range(64) for y in range(63)}
   configs.extend((t['種類'],t['半径'],c,shape) for c in centers if 0<=c[0]<64 and 0<=c[1]<63)
 else:
  if not needed:return []
  anchor=min(needed)
  # 初めの必要画素を含む線の中心を全列挙。近傍/top-kではない。
  for kind in ['直交十字','斜十字','中心欠け斜十字','菱形']:
   centers={(x,y) for x in range(64) for y in range(63) if kind=='菱形' or (x==anchor[0] or y==anchor[1]) and kind=='直交十字' or abs(x-anchor[0])==abs(y-anchor[1]) and kind in ('斜十字','中心欠け斜十字')}
   for center in centers:
    dxs=[(x-center[0],y-center[1]) for x,y in needed]
    if kind=='直交十字':
     if any(x!=0 and y!=0 for x,y in dxs):continue
     minimum=max(max(abs(x),abs(y)) for x,y in dxs);radii=range(max(2,minimum),64)
    elif kind in ('斜十字','中心欠け斜十字'):
     if any(abs(x)!=abs(y) for x,y in dxs):continue
     minimum=max(abs(x) for x,y in dxs);radii=range(max(2,minimum),64)
    else:
     ds={abs(x)+abs(y) for x,y in dxs}
     if len(ds)!=1:continue
     radius=next(iter(ds));radii=[radius] if 2<=radius<64 else []
    configs.extend((kind,r,center,形(kind,r)) for r in radii)
 found=[];seen=set()
 for kind,r,center,shape in configs:
  mask=点群(shape,center);visible={(x,y) for x,y in mask if 0<=x<64 and 0<=y<63}
  if not needed<=visible or any(frame[y][x] not in colors|{0} for x,y in visible-masked):continue
  key=(kind,r,center)
  if key in seen:continue
  seen.add(key);found.append({'色':color,'種類':kind,'半径':r,'中心':center,'形':tuple(sorted(shape)),'点':mask,'選択':center==black[0]})
 return found

def 全分解(frame,init=None):
 if init is None:
  markers,whole=標識を読む(frame);colors={t['色'] for t in markers}
  if not whole or not 2<=len(colors)<=3 or any(c in (0,4,5) for c in colors):return {'候補':[],'保留理由':'標識又は二〜三色一色一図形の支持文法外'}
  init={'標識':markers};templates=None
 else:
  markers=init['標識'];colors={o['色'] for o in init['図形']};templates=init['図形']
 groups=[幾何候補(frame,markers,colors,c,[t for t in templates if t['色']==c] if templates is not None else None) for c in sorted(colors)];results=[]
 for os in itertools.product(*groups):
  if sum(o['選択'] for o in os)!=1:continue
  orders=[order for order in itertools.permutations(range(len(os))) if 描画(init,os,order)==frame[:63]]
  if orders:results.append({'図形':os,'全描画順序':orders})
 return {'候補':results,'標識':markers,'幾何候補数':[len(g) for g in groups],'保留理由':None if len(results)==1 else '全整合分解が非一意'}
