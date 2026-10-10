import json,collections,itertools
from . import 候補 as C
G=C.G;A=C.A
V={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
def extract(frame):
 s=G.parse(frame)
 if len(s['根'])!=1 or s['根'][0]['形']!='環':raise ValueError('単一環状根以外の状態生成は未学習')
 root=s['根'][0]
 if A.opening_axis(frame,s,root)!=(1,0):raise ValueError('右向き根以外の状態生成は未学習')
 bg=[(x,y) for y in range(s['区切り']) for x,v in enumerate(frame[y]) if v==4 and not(root['範囲'][0]<=x<=root['範囲'][2] and root['範囲'][1]<=y<=root['範囲'][3])]
 box=[min(x for x,y in bg),min(y for x,y in bg),max(x for x,y in bg),max(y for x,y in bg)] if bg else None
 if not box:raise ValueError('主領域不明')
 x0,y0,x1,y1=box
 if (x1-x0+1)%6 or (y1-y0+1)%6:raise ValueError('6画素格子の矩形でない')
 if any(frame[y][x]==5 for y in range(y0,y1+1) for x in range(x0,x1+1)):raise ValueError('矩形内障害物は未学習')
 if s['未対応画素']:raise ValueError('未対応画素あり')
 w,h=(x1-x0+1)//6,(y1-y0+1)//6;cx,cy=root['中心']
 if cx!=x0-3.5:raise ValueError('左辺制御根でない')
 row=(cy-y0-2.5)/6
 if not row.is_integer() or not 0<=row<h:raise ValueError('根の格子外')
 beads=[]
 for b in s['珠']:
  x,y=b['中心'];xx=(x-x0-2.5)/6;yy=(y-y0-2.5)/6
  if not xx.is_integer() or not yy.is_integer() or not(0<=xx<w and 0<=yy<h):raise ValueError('珠の格子外')
  beads.append((b['色'],int(xx),int(yy)))
 if len({b[0] for b in beads})!=len(beads):raise ValueError('同色珠の個体対応が未確定')
 if len({b[1:] for b in beads})!=len(beads):raise ValueError('同一セルの珠が多義')
 # 軸上の可視線末端。root右境界を長さ0とする。
 px=int(cx+2.5);yy=int(cy);tip=px
 while tip+1<len(frame[0]) and frame[yy][tip+1] not in (4,5):tip+=1
 delta=tip-(cx+2.5)
 # 珠終端でcap一画素だけ省略される可視形。次の整数格子端が一意の場合だけ許す。
 if delta%6==5 and frame[yy][tip]>5 and tip+1<=x1 and frame[yy][tip+1]==4:delta+=1
 length=delta/6
 if not length.is_integer() or not 0<=length<=w:raise ValueError('線末端の格子外')
 state=(int(row),int(length),tuple(sorted(beads)))
 context={'幅':w,'高さ':h,'領域':box,'根色':root['色'],'根列':cx,'固定画素':frame,'語彙':'単根/右軸/矩形/一意色珠'}
 return state,context

def render(state,context):
 row,length,beads=state;w,h=context['幅'],context['高さ'];x0,y0,x1,y1=context['領域'];cx=context['根列'];cy=y0+2.5+6*row;color=context['根色'];a=[list(r) for r in context['固定画素']]
 for y in range(y0,y1+1):
  for x in range(x0,x1+1):a[y][x]=4
 # 全可動根帯と固定レールを再描画。色2/3の細部は抽出語彙では同じレール。
 left=int(cx-2.5);right=int(cx+2.5)
 for y in range(y0,y1+1):
  for x in range(left,right+1):a[y][x]=5
 for y in range(y0+2,y1-1):
  for x in (int(cx),int(cx)+1):a[y][x]=2
 ry=int(cy-2.5)
 for dy in range(6):
  for dx in range(6):a[ry+dy][left+dx]=color if dy in (0,5) or dx in (0,5) or (dy in (2,3) and dx in (2,3)) else 0
 end=right+6*length
 for yy in (int(cy),int(cy)+1):
  for x in range(right,end+1):a[yy][x]=1 if (x+yy)%3 else 2
 for color,col,rr in beads:
  bx=x0+1+6*col;by=y0+1+6*rr
  for y in range(by,by+4):
   for x in range(bx,bx+4):a[y][x]=color
 return a

def geometry(state,context,action):
 row,length,beads=state;w,h=context['幅'],context['高さ'];v=V.get(action,(0,0));dx,dy=v;attached={c for c,x,y in beads if y==row and x<length};bycell={(x,y):c for c,x,y in beads};pos={c:(x,y) for c,x,y in beads}
 mode='軸伸長' if action==4 else '軸縮退' if action==3 else '根横移動' if action in (1,2) else 'クリック' if action==6 else '未観測作用'
 touch=any(y==row and x==length-1 for c,x,y in beads)
 seeds=set(attached) if mode in ('軸縮退','根横移動') or (mode=='軸伸長' and touch) else set()
 if mode=='軸伸長' and (length,row) in bycell:seeds.add(bycell[(length,row)])
 closure=set(seeds);todo=list(seeds);space=True
 while todo:
  c=todo.pop();x,y=pos[c];xx,yy=x+dx,y+dy
  if not(0<=xx<w and 0<=yy<h):space=False;continue
  other=bycell.get((xx,yy))
  if other is not None and other not in closure:closure.add(other);todo.append(other)
 rootspace=0<=row+dy<h
 touch=any(y==row and x==length-1 for c,x,y in beads)
 common={'作用型':mode,'根境界内':rootspace,'依存移動空間':space,'腕下限':length==0,'腕上限':length==w,'腕端接触':touch}
 inputs={'根':json.dumps([mode,rootspace,space],ensure_ascii=False,separators=(',',':')),'腕':json.dumps([mode,length==0,length==w],ensure_ascii=False,separators=(',',':'))}
 inputs['珠']={c:json.dumps([mode,c in attached,c in closure,space,touch,rootspace],ensure_ascii=False,separators=(',',':')) for c,x,y in beads}
 return {'入力':inputs,'関係':common,'接続珠':sorted(attached),'依存移動珠':sorted(closure),'変位語彙':v}

def observed_labels(before,after,action):
 br,bl,bb=before;ar,al,ab=after;dx,dy=V.get(action,(0,0));out={}
 out['根']='不変' if ar==br else '作用方向一格' if dy and ar-br==dy else '語彙外'
 axial=1 if action==4 else -1 if action==3 else 0
 out['腕']='不変' if al==bl else '作用方向一格' if axial and al-bl==axial else '語彙外'
 amap={c:(x,y) for c,x,y in ab};out['珠']={}
 for c,x,y in bb:
  if c not in amap:out['珠'][c]='語彙外';continue
  xx,yy=amap[c];out['珠'][c]='不変' if (xx,yy)==(x,y) else '作用方向一格' if (dx,dy)!=(0,0) and (xx-x,yy-y)==(dx,dy) else '語彙外'
 return out

def apply_predictions(state,context,action,labels):
 row,length,beads=state;dx,dy=V.get(action,(0,0));axial=1 if action==4 else -1 if action==3 else 0
 if labels['根']=='作用方向一格':row+=dy
 if labels['腕']=='作用方向一格':length+=axial
 new=tuple((c,x+dx if labels['珠'][c]=='作用方向一格' else x,y+dy if labels['珠'][c]=='作用方向一格' else y) for c,x,y in beads)
 w,h=context['幅'],context['高さ']
 if not(0<=row<h and 0<=length<=w) or any(not(0<=x<w and 0<=y<h) for c,x,y in new) or len({(x,y) for c,x,y in new})!=len(new):raise ValueError('生成状態が格子/占有制約に反する')
 return (row,length,new)

def root_sequence(state):
 row,length,beads=state;return [c for c,x,y in sorted(beads,key=lambda z:z[1]) if y==row and x<length]
