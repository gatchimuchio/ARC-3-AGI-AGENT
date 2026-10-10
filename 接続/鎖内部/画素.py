import json,itertools,collections
from hds学習系統 import 外部入力
BOUNDARY="公開画素・根付き順序目標候補"
def parse(a):
 if not isinstance(a,list) or not a or not isinstance(a[0],list) or not a[0] or any(not isinstance(row,list) or len(row)!=len(a[0]) for row in a):
  raise ValueError('非空矩形画素配列が必要')
 if any(type(v) is not int or not 0<=v<=15 for row in a for v in row):
  raise ValueError('画素色値の範囲外')
 h,w=len(a),len(a[0]); separators=[y for y in range(h//2,h-1) if set(a[y])=={4} and set(a[y+1])=={4} and sum(v in (1,2,3) for v in a[y-1])>=w//2]
 if len(separators)!=1:raise ValueError('全幅凡例区切り未確認')
 split=separators[0]; covered=set(); roots=[]
 for y in range(h-5):
  for x in range(w-5):
   c=a[y][x]
   if c<=5:continue
   if all(a[y][x+i]==c for i in range(6)) and all(a[y+j][x]==c for j in range(1,5)) and all(a[y+j][x+5]==c for j in [1,4]) and all(a[y+j][x+i]==c for j in [2,3] for i in [2,3]):
    roots.append({'色':c,'範囲':[x,y,x+5,y+5],'中心':[x+2.5,y+2.5],'形':'環'})
    covered.update((xx,yy) for yy in range(y,y+6) for xx in range(x,x+6))
 beads=[]; unknown=[]; seen=set(covered)
 for y in range(h):
  for x in range(w):
   if (x,y) in seen or a[y][x]<=5:continue
   c=a[y][x]; todo=[(x,y)]; seen.add((x,y)); comp=[]
   while todo:
    xx,yy=todo.pop();comp.append((xx,yy))
    for u,v in [(xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)]:
     if 0<=u<w and 0<=v<h and (u,v) not in seen and a[v][u]==c:seen.add((u,v));todo.append((u,v))
   x0,x1=min(p[0] for p in comp),max(p[0] for p in comp); y0,y1=min(p[1] for p in comp),max(p[1] for p in comp)
   o={'色':c,'範囲':[x0,y0,x1,y1],'中心':[(x0+x1)/2,(y0+y1)/2]}
   if x1-x0==1 and y1-y0==1:o['形']='小方形';roots.append(o)
   elif (x1-x0+1,y1-y0+1) in [(4,4),(6,4),(4,6)]:beads.append(o)
   else:unknown.append(o)
 for i,b in enumerate(beads):b['対象']=f'画素対象:{i}'
 legendroots=sorted([r for r in roots if r['中心'][1]>split],key=lambda r:r['中心'][0]); legends=[]
 for i,r in enumerate(legendroots):
  right=legendroots[i+1]['範囲'][0] if i+1<len(legendroots) else w
  bs=sorted([b for b in beads if b['中心'][1]>split and r['中心'][0]<b['中心'][0]<right],key=lambda b:b['中心'][0])
  legends.append({'根':r,'列':[b['色'] for b in bs],'珠':bs})
 return {'区切り':split,'凡例':legends,'根':[r for r in roots if r['中心'][1]<split],'珠':[b for b in beads if b['中心'][1]<split],'未対応画素':unknown}

def observed_chains(a,s):
 out=[]
 for r in s['根']:
  cx,cy=r['中心']; paths=[]
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
   aligned=[]
   for b in s['珠']:
    bx,by=b['中心'];distance=(bx-cx)*dx+(by-cy)*dy;perp=(bx-cx)*dy-(by-cy)*dx
    if distance>0 and abs(perp)<0.01:aligned.append((distance,b))
   aligned.sort(key=lambda v:v[0]); connected=[]
   for distance,b in aligned:
    # 全中心線の各画素がレール・根・珠に属すことを要求。空間を飛び越えない。
    valid=True
    for t in range(1,int(distance)+1):
     px,py=int(cx+dx*t),int(cy+dy*t)
     rx0,ry0,rx1,ry1=r['範囲']; pad=1 if r['形']=='小方形' else 0
     if rx0-pad<=px<=rx1+pad and ry0-pad<=py<=ry1+pad:continue
     if a[py][px] in (4,5):valid=False;break
    if valid:connected.append(b)
   if connected:paths.append({'方向':[dx,dy],'列':[b['色'] for b in connected],'対象':[b['対象'] for b in connected]})
  out.append({'根色':r['色'],'候補経路':paths})
 return out

def candidates(s):
 """全根×全凡例×重複を除く全順列。削除するのは同一色列の重複だけ。"""
 for root in s['根']:
  for legend in s['凡例']:
   for seq in sorted(set(itertools.permutations(legend['列']))):
    yield {'根色':root['色'],'候補列':list(seq),'凡例根色':legend['根']['色'],'凡例列':legend['列'],
           '特徴':{'根一致':root['色']==legend['根']['色'],'順序一致':list(seq)==legend['列']}}

def encode(features):
 return {'根順序関係':json.dumps([features['根一致'],features['順序一致']],separators=(',',':'))}

def query(h,features):
 o=h.照会する(外部入力(encode(features),BOUNDARY)); labels=[p['予測値'] for p in o.内容['予測群'] if p['結果経路']==('完成列一致',)]
 return {'状態':o.状態,'予測':labels,'内容':o.内容}

def reconstruct(a,h):
 """答え画像、記録ID、level ID、採点器を受け取らない。"""
 try:s=parse(a)
 except ValueError as e:return {'状態':'断定保留','理由':str(e)}
 decisions=[]; accepted=[]; held=[]
 if len({r['色'] for r in s['根']})!=len(s['根']) or len({r['根']['色'] for r in s['凡例']})!=len(s['凡例']):
  return {'状態':'断定保留','理由':'同色根の対応が曖昧','解析':s}
 if s['未対応画素']:return {'状態':'断定保留','理由':'未対応画素','解析':s}
 for c in candidates(s):
  q=query(h,c['特徴']);c['判定']={'状態':q['状態'],'予測':q['予測']};decisions.append(c)
  if q['状態']=='出力' and q['予測'] and set(q['予測'])=={True}:accepted.append(c)
  elif q['状態']!='出力' or not q['予測']:held.append(c)
 goals=[]
 for color,seq in sorted(set((c['根色'],tuple(c['候補列'])) for c in accepted)):
  options=[[b['対象'] for b in s['珠'] if b['色']==c] for c in seq]
  # 一つの直線鎖内では同じ珠を二度通らない。他の鎖との共有は禁止しない。
  bindings=[list(t) for t in itertools.product(*options) if len(t)==len(set(t))]
  goals.append({'根色':color,'順序色列':list(seq),'対象割当候補':bindings})
 shared=[]
 for ga,gb in itertools.combinations(goals,2):
  for ia,ca in enumerate(ga['順序色列']):
   for ib,cb in enumerate(gb['順序色列']):
    aa={b[ia] for b in ga['対象割当候補']};bb={b[ib] for b in gb['対象割当候補']}
    if aa&bb:shared.append({'根対':[ga['根色'],gb['根色']],'順序対':[ia,ib],'共有候補':sorted(aa&bb),'共有必須':len(aa)==len(bb)==1})
 current=observed_chains(a,s)
 for g in goals:
  paths=[p for r in current if r['根色']==g['根色'] for p in r['候補経路']]
  g['現観測経路']=paths
  g['未充足順序候補']=[i for i,c in enumerate(g['順序色列']) if not paths or any(i>=len(p['列']) or p['列'][i]!=c for p in paths)]
 return {'状態':'断定保留' if held or not goals or any(not g['対象割当候補'] for g in goals) else '目標候補生成','共有対象関係':shared,'目標':goals,'全候補':decisions,'保留候補数':len(held),'解析':s,
         '作用前提':{'必要条件':['根と珠の選択・移動・接続の可視因果を別途確認','複数鎖で共有する珠を保持','既達成鎖を壊さない作用の確認'],'行動採用':'断定保留','理由':'完成列教師は安全な移動作用を同定しない'}}
