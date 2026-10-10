"""固定の直線候補文法。録画や状態ファイルを読まない。"""
from .画素 import perception,parse

def direction(a,ar):
 x,y,r,b=ar['範囲'];c=ar['色']
 if b-y>r-x:
  left=sum(a[v][x]==c for v in range(y,b+1));right=sum(a[v][r]==c for v in range(y,b+1));return (-1,0) if left<right else (1,0)
 top=sum(a[y][u]==c for u in range(x,r+1));bottom=sum(a[b][u]==c for u in range(x,r+1));return (0,-1) if top<bottom else (0,1)
def observe(a):
 p=perception(a);ts=p['トークン'];ars=p['操作標識'];centers=[((t['範囲'][0]+t['範囲'][2])/2,(t['範囲'][1]+t['範囲'][3])/2) for t in ts];scales={m['寸法'] for m in parse(a)['標識群']}
 if len(scales)!=1:return []
 step=3*next(iter(scales));out=[]
 for ar in ars:
  dx,dy=direction(a,ar);axis=0 if dx else 1;cross=1-axis;sign=dx or dy;x,y,r,b=ar['範囲'];ac=((x+r)/2,(y+b)/2)
  opponents=[other for other in ars if direction(a,other)==(-dx,-dy) and abs(((other['範囲'][cross]+other['範囲'][cross+2])/2)-ac[cross])<0.01]
  for other in opponents:
   bc=((other['範囲'][0]+other['範囲'][2])/2,(other['範囲'][1]+other['範囲'][3])/2);lo,hi=sorted([ac[axis],bc[axis]])
   aligned=sorted([i for i,c in enumerate(centers) if abs(c[cross]-ac[cross])<0.01],key=lambda i:centers[i][axis]);run=[i for i in aligned if lo<centers[i][axis]<hi]
   if len(run)<2:continue
   reasons=[]
   if any(centers[j][axis]-centers[i][axis]!=step for i,j in zip(run,run[1:])):reasons.append('列内に不連続')
   if len(run)!=len(aligned):reasons.append('同一直線上の離れた対象群がある')
   attached=[]
   for i in [run[0],run[-1]]:
    neigh=[j for j,c in enumerate(centers) if j not in run and max(abs(c[0]-centers[i][0]),abs(c[1]-centers[i][1]))==step]
    attached.append(bool(neigh))
   if all(attached):reasons.append('両端に列外接続がある')
   out.append({'操作標識':ar,'向き':[dx,dy],'対向操作標識':other,'列位置番号':run,'列対象':[ts[i] for i in run],'固定知覚適合':not reasons,'保留理由':reasons,'両端の列外接続':attached})
 return out
