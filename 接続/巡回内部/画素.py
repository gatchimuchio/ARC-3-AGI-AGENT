"""固定知覚のみ。録画・解答・ID・HDSは参照しない。"""
def parse(a):
 if not isinstance(a,list) or len(a)!=64 or any(not isinstance(r,list) or len(r)!=64 for r in a) or any(type(v) is not int or not 0<=v<=15 for r in a for v in r):raise ValueError('64×64の整数色画素が必要')
 marks=[]
 for s in [1,2]:
  for y in range(2,64-4*s+1):
   for x in range(1,64-4*s+1):
    c=a[y][x]
    if c in [3,4,5,8,14]:continue
    if all(a[y+v][x+u]==4 for u,v in [(s,0),(2*s,0),(0,s),(0,2*s),(3*s,s),(3*s,2*s),(s,3*s),(2*s,3*s)]) and all(a[y+dy+v][x+dx+u]==c for dx,dy in [(0,0),(3*s,0),(0,3*s),(3*s,3*s)] for u in range(s) for v in range(s)):
     center={a[yy][xx] for yy in range(y+s,y+3*s) for xx in range(x+s,x+3*s)}
     if len(center)==1 and 4 not in center:marks.append({'範囲':[x,y,x+4*s-1,y+4*s-1],'標識色':c,'内容色':next(iter(center)),'一致':center=={c},'寸法':s})
 return {'標識群':marks,'全標識一致':bool(marks) and all(m['一致'] for m in marks)}

def components(a):
 seen=set();out=[]
 for y in range(3,64):
  for x in range(1,64):
   if (x,y) in seen or a[y][x] in (3,4,5):continue
   c=a[y][x];q=[(x,y)];seen.add((x,y));pts=[]
   while q:
    u,v=q.pop();pts.append((u,v))
    for xx,yy in [(u-1,v),(u+1,v),(u,v-1),(u,v+1)]:
     if 1<=xx<64 and 3<=yy<64 and (xx,yy) not in seen and a[yy][xx]==c:seen.add((xx,yy));q.append((xx,yy))
   xs,ys=zip(*pts);out.append({'色':c,'範囲':[min(xs),min(ys),max(xs),max(ys)],'画素数':len(pts)})
 return out

def perception(a):
 cs=components(a);arrows=[];tokens=[];marks=parse(a)['標識群'];scales=set(m['寸法'] for m in marks)
 for c in cs:
  x,y,r,b=c['範囲'];w,h=r-x+1,b-y+1
  if c['色'] in (8,14) and any((w,h) in [(3*s,4*s),(4*s,3*s)] and c['画素数']==10*s*s for s in scales):arrows.append(c)
  if c['色'] not in (8,14) and any(w==h==2*s and c['画素数']==4*s*s for s in scales):tokens.append(c)
 return {'操作標識':arrows,'トークン':tokens}

