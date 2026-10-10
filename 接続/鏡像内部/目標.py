import itertools,collections
from . import 基礎 as e
def candidates(h,frame,観測=None):
 s=e.scene(frame)if 観測 is None else 観測;g=e.ask(h,{'黄標識全被覆':True},e.GOAL,'成功遷移');links=[e.ask(h,{'単軸方向':a['方向']},e.LINK,'鏡映予測複製と実測が一致')for a in s['軸']]
 r={'観測':e.compact(s),'目標照会':g,'鏡映照会':links,'実行許可':False,'全配置数':0,'候補':[],'保留':[]}
 if s['不明']or not s['目標']or not 1<=len(s['対象'])<=2 or not 1<=len(s['軸'])<=2:r['保留'].append('固定知覚範囲外');return r
 if g['値']is not True or any(q['値']is not True for q in links):r['保留'].append('HDS目標/鏡映支持未成立');return r
 if len(s['軸'])>1:r['保留'].append('二軸合成は単軸教師範囲外。以下は固定鏡映文法の条件付き全配置')
 targets=sorted(s['目標']);full=(1<<len(targets))-1;doms=[]
 for o in s['対象']:
  minx=min(x for x,y in o['点']);maxx=max(x for x,y in o['点']);miny=min(y for x,y in o['点']);maxy=max(y for x,y in o['点']);doms.append([{'変位':(dx,dy),'点':{(x+dx,y+dy)for x,y in o['点']}}for dx in range(-minx,21-maxx)for dy in range(-miny,21-maxy)])
 r['本体全変位領域']=[[v['変位']for v in d]for d in doms];r['軸全位置領域']=[list(range(21))if a['可動']else[a['位置']]for a in s['軸']];r['構造不成立数']=0
 for ps in itertools.product(*r['軸全位置領域']):
  axes=[{**a,'位置':p}for a,p in zip(s['軸'],ps)];opts=[]
  for dom in doms:
   a=[]
   for d in dom:
    occ=e.orbit(d['点'],axes);mask=sum(1<<i for i,p in enumerate(targets)if p in occ);a.append((d,mask))
   opts.append(a)
  r['全配置数']+=__import__('math').prod(map(len,opts))
  # 全積を同じ被覆bitmaskで完全に圧縮。同値類の全変位を保持する。
  grouped=[]
  for opt in opts:
   group=collections.defaultdict(list)
   for d,mask in opt:group[mask].append(d['変位'])
   grouped.append(group)
  for masks in itertools.product(*[list(d)for d in grouped]):
   covered=0
   for m in masks:covered|=m
   if covered!=full:continue
   r['候補'].append({'軸位置':ps,'被覆同値類':list(masks),'対象全変位類':[grouped[i][m]for i,m in enumerate(masks)],'完全積候補数':__import__('math').prod(len(grouped[i][m])for i,m in enumerate(masks))})
 r['条件充足配置数']=sum(c['完全積候補数']for c in r['候補']);r['不採用配置数']=r['全配置数']-r['条件充足配置数'];r['保留'].append('選択/衝突/回転/undo/全経路実測とfresh成功が未閉包')
 return r
