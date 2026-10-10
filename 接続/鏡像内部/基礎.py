import json,itertools
from hds学習系統 import 外部入力
GOAL='公開鏡像:黄標識の全被覆と成功遷移';MOVE='公開鏡像:選択役割と局所変位';LINK='公開鏡像:鏡軸と実測複製占有';SELECT='公開鏡像:クリック包含と選択'
D={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
def ask(h,f,b,key):
 r=h.照会する(外部入力(f,b));ps=[p for p in r.内容['予測群']if tuple(p['結果経路'])==(key,)];vs={p['予測値']for p in ps};return {'入力':f,'状態':r.状態,'値':next(iter(vs))if len(vs)==1 and r.状態!='断定保留'else None,'予測':ps,'HOLD':r.内容['断定保留理由群']}
def teach(h,f,b,src):
 r=h.処理する(外部入力(f,b));return {'境界':b,'教師':f,'出所':src,'状態':r.状態,'内容':r.内容,'追跡':r.追跡情報}
def components(pts):
 todo=set(pts);out=[]
 while todo:
  p=min(todo);todo.remove(p);q=[p]
  for x,y in q:
   for dx,dy in itertools.product((-1,0,1),repeat=2):
    z=(x+dx,y+dy)
    if z in todo:todo.remove(z);q.append(z)
  out.append(set(q))
 return out
def 元画素観測(f):
 cells={};unknown=[]
 for y in range(21):
  for x in range(21):
   tile=[f[y*3+j][x*3+i]for j in range(3)for i in range(3)];rim=set(tile[:4]+tile[5:]);c=tile[4]
   role='本体'if rim=={5}else'複製'if rim=={4}else'黄目標'if set(tile)=={11}else'鏡軸'if rim=={10}else'背景'if set(tile)=={9}else'不明'
   cells[x,y]={'役割':role,'中心':c}
   if role=='不明':unknown.append((x,y,tile))
 base={p for p,v in cells.items()if v['役割']=='本体'};copies={p for p,v in cells.items()if v['役割']=='複製'};targets={p for p,v in cells.items()if v['中心']==11 and v['役割']in('本体','複製','黄目標')}
 axes=[]
 for axis in (0,1):
  for pos in range(21):
   ps=[p for p,v in cells.items()if p[axis]==pos and v['役割']=='鏡軸']
   if len(ps)>=10:axes.append({'方向':axis,'位置':pos,'可動':any(cells[p]['中心']in(0,9)for p in ps),'選択':any(cells[p]['中心']==0 for p in ps)})
 objs=[{'点':p,'選択':any(cells[q]['中心']==0 for q in p)}for p in components(base)]
 sels=[{'役割':'本体','対象':o}for o in objs if o['選択']]+[{'役割':'鏡軸','対象':a}for a in axes if a['選択']]
 return {'本体':base,'複製':copies,'目標':targets,'軸':axes,'対象':objs,'選択':sels[0]if len(sels)==1 else None,'不明':unknown,'セル':cells}
def compact(s):return {k:v for k,v in s.items()if k!='セル'}
def orbit(pts,axes):
 out=set(pts)
 for a in axes:out|={tuple(2*a['位置']-v if i==a['方向']else v for i,v in enumerate(p))for p in out}
 return out
def visible(pts):return {p for p in pts if all(0<=v<21 for v in p)}
def fullcovered(s):return bool(s['目標'])and s['目標']<=s['本体']|s['複製']
def facts(s,a):
 sel=s['選択'];dx,dy=D[a]
 if not sel:return None
 if sel['役割']=='本体':
  o=sel['対象'];new={(x+dx,y+dy)for x,y in o['点']};valid=all(0<=x<21 and 0<=y<21 for x,y in new)
  return {'選択役割':'本体','入力作用':a,'移動後領域内':valid,'軸への垂直入力':False}
 z=sel['対象'];delta=(dx,dy)[z['方向']]
 return {'選択役割':'鏡軸','入力作用':a,'移動後領域内':0<=z['位置']+delta<21,'軸への垂直入力':delta!=0}
def encode(f,product):return {'前提直積':json.dumps(f,ensure_ascii=False,sort_keys=True,separators=(',',':'))}if product else f

def scene(frame):
 s=元画素観測(frame);axes=[]
 # 一つの直交軸だけなら各行/列にcyanセルは高々1。2個以上はこの方向の軸の証拠。
 for direction in (0,1):
  for position in range(21):
   pts=[p for p,v in s['セル'].items()if p[direction]==position and v['役割']=='鏡軸']
   if len(pts)>=2:axes.append({'方向':direction,'位置':position,'可動':any(s['セル'][p]['中心']in(0,9)for p in pts),'選択':False})
 s['軸']=axes
 for a in axes:
  pts=[p for p,v in s['セル'].items()if p[a['方向']]==a['位置']and v['役割']=='鏡軸'and not any(p[b['方向']]==b['位置']for b in axes if b is not a)]
  vals={s['セル'][p]['中心']for p in pts};a['選択']=bool(pts)and vals=={0};a['標識曖昧']=len(vals)>1
 for o in s['対象']:
  off=[p for p in o['点']if not any(p[a['方向']]==a['位置']for a in axes)];o['選択']=any(s['セル'][p]['中心']==0 for p in off)
 sels=[{'役割':'本体','対象':o}for o in s['対象']if o['選択']]+[{'役割':'鏡軸','対象':a}for a in axes if a['選択']]
 s['選択']=sels[0]if len(sels)==1 else None;s['選択不確定理由']=None if len(sels)==1 else '白点の軸役割除外後も一意でない';return s
