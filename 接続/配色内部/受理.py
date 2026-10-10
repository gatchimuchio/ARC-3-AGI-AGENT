"""受理の因果を一つへ潰さない固定仮説族。HDSは各視点と実受理の対応を学習。"""
from .関係 import query
B='公開配色:応答受理と整合する候補視点';X='この候補視点は充足';Y='実応答で進捗あり'
NAMES=['一致数の単調閾値族','短い対角差分族','短い対角かつ見本境界差分族']
def errors(ref,canvas):return [(x,y,ref[y][x],v) for y,r in enumerate(canvas) for x,v in enumerate(r) if v!=ref[y][x]]
def descriptor(ref,canvas):
 e=errors(ref,canvas);n=len(ref);coords=[(x,y) for x,y,a,b in e]
 diag=not e or len({x+y for x,y in coords})==1 or len({x-y for x,y in coords})==1
 boundary=all(any(0<=x+dx<n and 0<=y+dy<n and ref[y+dy][x+dx]!=ref[y][x] for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))) for x,y in coords)
 return {'不一致数':len(e),'全差分位置と色':e,'一直線対角':diag,'全差分は見本色境界':boundary}
def features(ref,canvas,spec):
 d=descriptor(ref,canvas);scores=[len(ref)**2-d['不一致数']>=t for t in spec['単調閾値候補']]
 return [scores[0] if len(set(scores))==1 else None,d['不一致数']<=spec['短差分上限'] and d['一直線対角'],d['不一致数']<=spec['短差分上限'] and d['一直線対角'] and d['全差分は見本色境界']]
def assess(h,ref,canvas,spec):
 fs=features(ref,canvas,spec);out=[]
 for name,v in zip(NAMES,fs):
  pred=None if v is None else query(h,B+':'+name,{X:v},Y)[0];out.append({'視点':name,'入力':v,'予測':pred})
 return {'状態':'条件付き受理候補' if all(r['予測'] is True for r in out) else '条件付き非進捗予測' if all(r['予測'] is False for r in out) else 'HOLD','全視点':out,'差分記述':descriptor(ref,canvas)}
def alternatives(h,scene,spec):
 ref=scene['参照'];n=len(ref);colors=[p['色'] for p in scene['色見本']];out=[];held=[];seen=set()
 candidates=[((),None)]
 for x in range(n):
  for y in range(n):
   for dx,dy in ((1,1),(1,-1)):
    for k in range(1,spec['短差分上限']+1):
     pts=tuple((x+j*dx,y+j*dy) for j in range(k))
     if all(0<=a<n and 0<=b<n for a,b in pts):candidates.extend((pts,c) for c in colors)
 cache={}
 for pts,c in candidates:
  canvas=[r[:] for r in ref]
  for x,y in pts:canvas[y][x]=c
  key=tuple(map(tuple,canvas))
  if key in seen:continue
  seen.add(key);fs=tuple(features(ref,canvas,spec))
  if fs not in cache:
   cache[fs]=[None if v is None else query(h,B+':'+name,{X:v},Y)[0] for name,v in zip(NAMES,fs)]
  item={'変更座標':pts,'色':c,'一致数':n*n-len(errors(ref,canvas)),'視点条件':fs,'予測':cache[fs]}
  (out if all(v is True for v in cache[fs]) else held).append(item)
 return {'全条件付き代替':out,'全HOLD代替':held,'注意':'固定の短対角・単色変更候補全域。これ以外の全可能画像は未評価であり排除しない。各候補の作用到達性は未評価。'}
