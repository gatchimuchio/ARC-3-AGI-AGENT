"""外部HDSを照会する静的部分モデル。実環境同値・実行許可を主張しない。"""
import json
from .知覚 import 初期化,記号前提,読む,方向
目標境界="公開小枠:輪郭内所属と非静止状態から応答達成"
作用境界="公開小枠:局所前提から操作体と保持枠の共同作用"
def 符号(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def 照会(h,b,f):
 from hds学習系統 import 外部入力
 r=h.照会する(外部入力({'前提':符号(f)},b));ps=[p for p in r.内容['予測群'] if p['結果経路']==['結果'] or tuple(p['結果経路'])==('結果',)];vs={p['予測値'] for p in ps}
 return {'前提':f,'境界':b,'状態':r.状態,'予測群':ps,'値':json.loads(next(iter(vs))) if r.状態!='断定保留' and len(vs)==1 else None,'保留理由群':r.内容['断定保留理由群']}

class モデル:
 def __init__(self,h,frame):
  initial,why=初期化(frame)
  if why:raise ValueError(why)
  self.bg,self.start=initial;self.h=h;self.cache={};self.slots=sorted(set(p for r in 読む(frame)['輪郭領域']for p in r));self.gq=照会(h,目標境界,{'全枠が輪郭領域内':True,'非静止枠あり':False,'小枠数保存':True})
 def next(self,s,a):
  feature=記号前提(self.bg,s,a);key=符号(feature)
  if key not in self.cache:self.cache[key]=照会(self.h,作用境界,feature)
  q=self.cache[key];v=q['値']
  if v is None:return None,'HDS保留',key
  pos,face,rings,held=s;rs=list(rings)
  if a in 方向:
   dx,dy=方向[a];k=v['前進量'];new=(pos[0]+dx*k,pos[1]+dy*k)
   if held>=0:rs[held]=(rs[held][0]+dx*k,rs[held][1]+dy*k)
   nf=face if held>=0 else a
   if v['応答保持数']!=int(held>=0):return None,'静的表現外の保持変化',key
  elif a==5:
   new=pos;nf=face
   if held<0 and v['応答保持数']==1:
    dx,dy=方向[face];front=(pos[0]+dx,pos[1]+dy)
    if front not in rs:return None,'保持対象非同定',key
    held=rs.index(front)
   elif held>=0 and v['応答保持数']==0:held=-1
  else:return None,'未支持作用',key
  nxt=(new,nf,tuple(rs),held)
  if any(not(0<=x<16 and 0<=y<15)for x,y in [new]+rs):return None,'表示対象域外HOLD',key
  if len(set(rs))!=len(rs)or new in rs:return None,'排他的占有仮説と不整合',key
  return nxt,'条件付き空間支持',key
 def goal(self,s):return s[3]<0 and set(s[2])<=set(self.slots) and self.gq['値']=={'進捗応答':True}
