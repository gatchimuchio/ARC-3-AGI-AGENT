"""固定知覚。既存4連結成分を使用し、ID/教師/答えへアクセスしない。"""
import itertools
from ..図式観測 import 成分群
方向={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
def 外接(点):return (min(x for x,y in 点),min(y for x,y in 点),max(x for x,y in 点),max(y for x,y in 点))

def 正規(点):
 x,y,_,_=外接(点);return tuple(sorted((a-x,b-y) for a,b in 点))

def 知覚初期(盤面):
 # 既存4連結成分を再利用。3×3黄環とその中心色を固定知覚の候補とする。
 標識=[];未解決=[]
 for c in 成分群(盤面):
  if c['対応鍵'][0]!=4:continue
  pts=set(c['点群']);x,y,X,Y=外接(pts)
  if X-x==2 and Y-y==2 and pts=={(a,b) for a in range(x,X+1) for b in range(y,Y+1) if a in (x,X) or b in (y,Y)}:
   標識.append({'中心':(x+1,y+1),'色':盤面[y+1][x+1],'画素':pts})
  else:未解決.append({'理由':'完全な三画素標識環ではない','画素':pts})
 標識.sort(key=lambda t:t['中心']);隠蔽=set().union(*({(x,y) for x in range(t['中心'][0]-1,t['中心'][0]+2) for y in range(t['中心'][1]-1,t['中心'][1]+2)} for t in 標識)) if 標識 else set()
 黒=[(x,y) for y,row in enumerate(盤面[:63]) for x,c in enumerate(row) if c==0]
 図形=[];色群=sorted({t['色'] for t in 標識})
 for 色 in 色群:
  pts={(x,y) for y,row in enumerate(盤面[:63]) for x,c in enumerate(row) if c==色 and (x,y) not in 隠蔽}
  if len(黒)==1 and any((黒[0][0]+dx,黒[0][1]+dy) in pts for dx,dy in 方向.values()):pts|=set(黒)
  if not pts:continue
  x,y,X,Y=外接(pts);cx,cy=(x+X)//2,(y+Y)//2
  mask={(a,cy) for a in range(x,X+1)}|{(cx,b) for b in range(y,Y+1)}
  if pts!=mask or X-x!=Y-y or (X-x)%2 or X-x<4:
   未解決.append({'理由':'現在の直交十字全文法外または遮蔽','色':色,'実観測点':pts});continue
  図形.append({'色':色,'中心':(cx,cy),'半径':(X-x)//2,'形':tuple(sorted((a-cx,b-cy) for a,b in mask)),'点':mask,'選択':(cx,cy) in 黒})
 文法内=len(図形)==2 and len(色群)==2 and not 未解決 and len(黒)==1 and all(t['色'] not in (0,4,5) for t in 標識) and sum(o['選択'] for o in 図形)==1
 return {'標識':標識,'図形':図形,'選択黒点':黒,'保留':未解決,'適用可能':文法内,'固定知覚':'三画素黄環と中心色、二つの色別直交十字、黒一点の選択役割候補。'}

def 形の点(図形,中心):return {(中心[0]+dx,中心[1]+dy) for dx,dy in 図形['形']}

def 現在全分解(盤面,初期):
 # 初期図形の形状と標識だけ。現在真個体位置や答えは入力しない。
 黒=[(x,y) for y,row in enumerate(盤面[:63]) for x,c in enumerate(row) if c==0]
 if len(黒)!=1:return []
 隠蔽=set().union(*({(x,y) for x in range(t['中心'][0]-1,t['中心'][0]+2) for y in range(t['中心'][1]-1,t['中心'][1]+2)} for t in 初期['標識']))
 色群={o['色'] for o in 初期['図形']};全候補=[]
 for o in 初期['図形']:
  必要={(x,y) for y,row in enumerate(盤面[:63]) for x,c in enumerate(row) if c==o['色'] and (x,y) not in 隠蔽}
  candidates=[]
  for cy in range(63):
   for cx in range(64):
    # 完全十字の同じ行/列上でなければ可視の同色点を覆えない。
    if any(x!=cx and y!=cy for x,y in 必要):continue
    mask=形の点(o,(cx,cy));visible={(x,y) for x,y in mask if 0<=x<64 and 0<=y<63}
    if not 必要<=visible:continue
    if any(盤面[y][x] not in 色群|{0} for x,y in visible-隠蔽):continue
    if 黒[0] in visible and 黒[0]!=(cx,cy):continue
    candidates.append({'色':o['色'],'中心':(cx,cy),'半径':o['半径'],'形':o['形'],'点':mask,'選択':(cx,cy)==黒[0]})
  全候補.append(candidates)
 結果=[]
 for os in itertools.product(*全候補):
  if sum(o['選択'] for o in os)!=1:continue
  # まだ描画順の物理を確定しない。全被覆の必要条件だけで候補を残す。
  結果.append(list(os))
 return 結果

def 被覆関係(対象,標識):
 return all(any(t['色']==o['色'] and tuple(t['中心']) in o['点'] for o in 対象) for t in 標識)
