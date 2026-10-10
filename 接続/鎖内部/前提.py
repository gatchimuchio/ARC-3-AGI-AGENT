import json,collections,itertools
from . import 画素 as G
goal=G
V={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
def active_roots(a,s):
 return [r for r in s['根'] if r['形']=='環' and sum(a[y][x]==0 for y in range(r['範囲'][1],r['範囲'][3]+1) for x in range(r['範囲'][0],r['範囲'][2]+1))>0]

def board_bounds(a,s):
 todo={(x,y) for y in range(s['区切り']) for x in range(len(a[0])) if a[y][x]==4};components=[]
 while todo:
  p=todo.pop();q=[p];comp=[p]
  while q:
   x,y=q.pop()
   for p in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
    if p in todo:todo.remove(p);q.append(p);comp.append(p)
  components.append(comp)
 if not components:return None
 sizes=sorted((len(c) for c in components),reverse=True)
 if len(sizes)>1 and sizes[0]==sizes[1]:return None
 comp=max(components,key=len)
 return [min(x for x,y in comp),min(y for x,y in comp),max(x for x,y in comp),max(y for x,y in comp)]

def status(a,s,goals):
 chains=goal.observed_chains(a,s);out=[]
 for g in goals:
  ps=[p for r in chains if r['根色']==g['根色'] for p in r['候補経路']]
  seqs=[p['列'] for p in ps] or [[]];prefix=[]
  for seq in seqs:
   n=0
   for x,y in zip(seq,g['順序色列']):
    if x!=y:break
    n+=1
   prefix.append(n)
  out.append({'根色':g['根色'],'目標列':g['順序色列'],'現列候補':seqs,'現対象候補':[p['対象'] for p in ps],
              '前置一致数候補':prefix,'完成':any(seq==g['順序色列'] for seq in seqs)})
 return out

def prior(a,act,goals):
 s=goal.parse(a);active=active_roots(a,s); st=status(a,s,goals)
 p={'目標状態':st,'選択根候補':[r['色'] for r in active],'操作':act,'保留':[]}
 if len(active)!=1:p['保留'].append('選択根が一意でない');return p
 r=active[0];d=axis(a,s,r)
 if d is None:p['保留'].append('盤面と根の方向未同定');return p
 vectors={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
 v=vectors.get(act.get('id'));p['根軸']=list(d)
 p['作用型']='クリック' if act.get('id')==6 else '軸伸長' if v==d else '軸収縮' if v==(-d[0],-d[1]) else '根横移動' if v else 'その他'
 gst=[g for g in st if g['根色']==r['色']]
 if len(gst)!=1:p['保留'].append('選択根は直接指定目標でない');return p
 g=gst[0]
 if len(g['現列候補'])!=1:p['保留'].append('現在鎖が多義');return p
 seq=g['現列候補'][0];n=g['前置一致数候補'][0];target=g['目標列']
 p['接続済列']=seq;p['目標列']=target;p['既列正順']=n==len(seq);p['次要求色']=target[len(seq)] if n==len(seq) and len(seq)<len(target) else None
 dx,dy=d;cx,cy=r['中心'];aligned=[]
 linked={t for ts in g['現対象候補'] for t in ts}
 for b in s['珠']:
  bx,by=b['中心'];dist=(bx-cx)*dx+(by-cy)*dy;perp=(bx-cx)*dy-(by-cy)*dx
  if dist>0 and abs(perp)<0.01 and b['対象'] not in linked:aligned.append((dist,b))
 aligned.sort(key=lambda z:z[0]);p['軸上未接続対象']=[b for _,b in aligned]
 # 選択軸の可視レール末端。これは固定画素計測でありHDS取得規則ではない。
 edge=(r['範囲'][2]-cx if dx==1 else cx-r['範囲'][0] if dx==-1 else r['範囲'][3]-cy if dy==1 else cy-r['範囲'][1])
 t=int(edge)+1;tip=None
 while True:
  x,y=int(cx+dx*t),int(cy+dy*t)
  if not(0<=x<len(a[0]) and 0<=y<s['区切り']):break
  if a[y][x] in (4,5):break
  tip=(x,y);t+=1
 p['可視末端']=tip
 if aligned:
  b=aligned[0][1];p['次対象']=b;
  p['次対象の既接続根']=[rr['根色'] for rr in goal.observed_chains(a,s) if rr['根色']!=r['色'] and any(b['対象'] in path['対象'] for path in rr['候補経路'])]
  p['次対象役割']='次要求一致' if b['色']==p['次要求色'] else '次要求不一致' if p['次要求色'] is not None else '既列違反または完成済'
  bounds=board_bounds(a,s); bx,by=b['中心']; pushed=[]; advance=1
  while True:
   px,py=bx+dx*6*advance,by+dy*6*advance
   if not(bounds[0]<=px<=bounds[2] and bounds[1]<=py<=bounds[3]) or a[int(py)][int(px)]==5:
    p['押出余地']='なし';p['幾何余白のみ']='なし';break
   occupants=[o for o in s['珠'] if abs(o['中心'][0]-px)<0.01 and abs(o['中心'][1]-py)<0.01]
   if occupants:pushed.extend(o['対象'] for o in occupants);advance+=1;continue
   p['幾何余白のみ']='あり';p['押出余地']='あり' if a[int(py)][int(px)]==4 else 'なし';break
  p['連鎖押出対象']=pushed
  if tip:
   ex=b['範囲'][0] if dx==1 else b['範囲'][2] if dx==-1 else b['範囲'][1] if dy==1 else b['範囲'][3]
   p['末端対象間隔']=abs(ex-(tip[0] if dx else tip[1]))-1
 else:p['次対象役割']='軸上対象なし'
 # 同一現在画素対象を使っている他の鎖を全て残す。
 p['他鎖共有対象']=[]
 for other in st:
  if other['根色']==r['色']:continue
  shared=linked & {t for ts in other['現対象候補'] for t in ts}
  if shared:p['他鎖共有対象'].append({'根色':other['根色'],'対象':sorted(shared),'完成':other['完成']})
 return p
def hit(o,x,y):
 x0,y0,x1,y1=o['範囲'];return x0<=x<=x1 and y0<=y<=y1

def click_features(frame,act,goals):
 s=G.parse(frame);x,y=act.get('data',{}).get('x'),act.get('data',{}).get('y')
 if x is None or y is None:return {'保留':['座標なし']}
 selected=[r['色'] for r in active_roots(frame,s)]
 targets=[{'場所':'盤面','根':r} for r in s['根'] if hit(r,x,y)] + [{'場所':'凡例','根':l['根']} for l in s['凡例'] if hit(l['根'],x,y)]
 if len(targets)>1:return {'保留':['クリック根が多義']}
 if not targets:return {'保留':[],'根対象':False,'根種':'根以外','選択済':False,'対象根色':None,'目標未充足':None,'前選択':selected}
 t=targets[0];r=t['根'];g=[q for q in status(frame,s,goals) if q['根色']==r['色']]
 return {'保留':[],'根対象':True,'根種':r['形'],'選択済':r['色'] in selected,'対象根色':r['色'],'目標未充足':not g[0]['完成'] if len(g)==1 else None,'前選択':selected,'場所':t['場所']}
def root_openings(frame,r):
 if r['形']!='環':return []
 x0,y0,x1,y1=r['範囲'];c=r['色'];out=[]
 for label,points in [('右',[(x1,y0+2),(x1,y0+3)]),('下',[(x0+2,y1),(x0+3,y1)]),('左',[(x0,y0+2),(x0,y0+3)]),('上',[(x0+2,y0),(x0+3,y0)])]:
  if all(frame[y][xx]!=c for xx,y in points):out.append(label)
 return out
def root_key(f):return json.dumps([f['根種'],f['選択済']],ensure_ascii=False,separators=(',',':'))

def retract_key(f):return json.dumps([f['尾部役割'],f['先頭根間隔'],f.get('尾部余剰線長'),bool(f['既接続他根'])],ensure_ascii=False,separators=(',',':'))

def movement_key(r):
 p=r['元作用記録']['前提'];shared=p.get('他鎖共有対象',[])
 return json.dumps([bool(shared),[s['完成'] for s in shared]],ensure_ascii=False,separators=(',',':'))
def descriptor(p,version='既存線と既接続を保持'):
 f=[p['次対象役割'],p.get('末端対象間隔'),p.get('押出余地')]
 if version=='幾何余白のみ':f[-1]=p.get('幾何余白のみ')
 if version=='既存線と既接続を保持':f.append(bool(p.get('次対象の既接続根')))
 return json.dumps(f,ensure_ascii=False,separators=(',',':'))
def opening_axis(frame,scene,root):
 directions={'右':(1,0),'下':(0,1),'左':(-1,0),'上':(0,-1)}
 openings=root_openings(frame,root)
 return directions[openings[0]] if len(openings)==1 else None

def retract_features(frame,p):
 scene=G.parse(frame);seq=p['接続済列'];color=p['選択根候補'][0]
 gs=next(g for g in p['目標状態'] if g['根色']==color);prefix=gs['前置一致数候補'][0]
 chains=G.observed_chains(frame,scene);chain=next(r for r in chains if r['根色']==color);ids=chain['候補経路'][0]['対象'] if chain['候補経路'] else []
 dx,dy=p['根軸'];root=next(r for r in scene['根'] if r['色']==color);cx,cy=root['中心']
 # 既存縮退教材は右/下だけ。この比較も逆軸に拡張しない。
 if (dx,dy) not in [(1,0),(0,1)]:return None
 ordered=sorted([((b['中心'][0]-cx)*dx+(b['中心'][1]-cy)*dy,b) for b in scene['珠'] if b['対象'] in ids],key=lambda z:z[0])
 f={'空鎖':not seq,'尾部役割':'なし' if not seq else '誤後続' if len(seq)>prefix else '正前置','先頭根間隔':ordered[0][0] if ordered else None,'既接続他根':[r['根色'] for r in chains if r['根色']!=color and any(set(ids)&set(z['対象']) for z in r['候補経路'])]}
 if ordered and p['可視末端']:
  b=ordered[-1][1];edge=b['範囲'][2] if dx else b['範囲'][3];f['尾部余剰線長']=(p['可視末端'][0] if dx else p['可視末端'][1])-edge
 return f
def ray_candidates(frame,root,split):
 cx,cy=root['中心'];x0,y0,x1,y1=root['範囲'];out=[]
 for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
  t=1;points=[]
  while True:
   px,py=int(cx+dx*t),int(cy+dy*t)
   if not(0<=px<len(frame[0]) and 0<=py<split):break
   if x0-1<=px<=x1+1 and y0-1<=py<=y1+1:t+=1;continue
   if frame[py][px] in (4,5):break
   points.append((px,py));t+=1
  if points:out.append({'方向':[dx,dy],'末端':points[-1]})
 return out

def features(frame,act,goals,goalcolor):
 s=G.parse(frame);controllers=active_roots(frame,s);allchains=G.observed_chains(frame,s);statuses=status(frame,s,goals)
 if len(controllers)!=1:return {'保留':['操作根が一意でない']}
 c=controllers[0];gc=[r for r in s['根'] if r['色']==goalcolor]
 if len(gc)!=1:return {'保留':['目標根が一意でない']}
 root=gc[0];rays=ray_candidates(frame,root,s['区切り'])
 if len(rays)!=1:return {'保留':['小根の接続方向が一意でない'],'方向候補':rays}
 chains=[p for r in allchains if r['根色']==c['色'] for p in r['候補経路']]
 cs=[p for r in allchains if r['根色']==goalcolor for p in r['候補経路']]
 held={i for p in chains for i in p['対象']};bound={i for p in cs for i in p['対象']}
 gs=next(x for x in statuses if x['根色']==goalcolor);n=gs['前置一致数候補'][0];target=gs['目標列'];nextcolor=target[n] if n<len(target) else None
 nextheld=[b for b in s['珠'] if b['対象'] in held and b['色']==nextcolor];shared=[b for b in s['珠'] if b['対象'] in held&bound]
 dx,dy=rays[0]['方向'];cx,cy=root['中心'];tx,ty=rays[0]['末端'];v=V.get(act['id'],(0,0));opening=root_openings(frame,c)
 direction='小根へ近付く' if v[0]*dx+v[1]*dy<0 else '小根から離れる' if v[0]*dx+v[1]*dy>0 else '小根に直交'
 def relation(b):
  x,y=b['中心'];perp=(x-cx)*dy-(y-cy)*dx;enddist=(x-tx)*dx+(y-ty)*dy
  return {'横ずれ':perp,'端超過距離':enddist,'同根接続':b['対象'] in bound}
 semantic={'方向':direction,'操作根開口':opening,'目標完成':gs['完成'],'共有対象関係':[relation(b) for b in shared],
           '次要求色保持関係':[relation(b) for b in nextheld],'操作方向':v}
 return {'保留':[],'関係':semantic,'操作根':c,'目標根':root,'保持対象':sorted(held),'共有対象':sorted(held&bound),'次要求色':nextcolor,'次要求保持対象':nextheld,'目標状態':gs,'小根線候補':rays}
def indirect_key(f):return json.dumps(f['関係'],ensure_ascii=False,sort_keys=True,separators=(',',':'))

axis=opening_axis
