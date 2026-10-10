"""公開配置文法による条件付き描画/再知覚。作用選択/色/上書きは同じHDSへ照会。"""
import json
from collections import defaultdict,Counter
from .知覚 import ROOT,read,classify
from .関係 import *
from .手順 import DIRECTIONS,solve

from .固定文法 import クリック支持相対位置

def クリック位置の支持(s,action):
 if action['id']!=6:return True
 role=classify(s,action);a=action['data'];name=role['役割']
 boxes=[p['矩形'] for p in s['色見本'] if p['色']==role.get('色')] if name=='色選択' else s['小器具矩形群'] if name=='小域塗布' else []
 if len(boxes)!=1:return False
 x,y,X,Y=boxes[0]
 return sig([name,X-x,Y-y,a['x']-x,a['y']-y]) in クリック支持相対位置

def predict(h,frame,action,templates,optional_seen):
 try:
  s=read(frame)
  if type(action.get('id')) is not int or not 0<=action['id']<=7:raise ValueError('作用番号不正')
  if action['id']==6 and any(type(action.get('data',{}).get(k)) is not int or not 0<=action['data'][k]<64 for k in ('x','y')):raise ValueError('クリック座標不正')
  prior=templates.get(sig([s['方向'],bool(s['小器具矩形群'])]),[])
  if len(prior)!=1 or sig(prior[0]['画素'])!=sig(s['装置画素']):raise ValueError('現在器具の役割画素が12配置文法の範囲外')
  role=classify(s,action)
  if not クリック位置の支持(s,action):raise ValueError('クリック相対位置の公開支持なし。矩形全座標同値は未確認')
 except (ValueError,TypeError,KeyError) as e:return {'状態':'HOLD','保留':[str(e)],'実行許可':False}
 kind=role['役割'];direction=s['方向'];color=s['器具色'];canvas=[r[:] for r in s['対象']];holds=[];q=[]
 if kind=='方向':
  v,r=query(h,TURN,{TX:sig([direction,action['id']])},TY);q.append(r)
  if v is None:holds.append('方向HDS未支持')
  else:direction=json.loads(v)
 elif kind=='色選択':
  cs=[]
  for p in s['色見本']:
   v,r=query(h,COPY,{X:p['色']==role['色']},Y);q.append(r)
   if v is None:holds.append('色対応HDS未支持')
   elif v:cs.append(p['色'])
  if len(cs)!=1:holds.append('色候補非一意')
  else:color=cs[0]
 elif kind in ('広域塗布','小域塗布'):
  cache={}
  for y in range(s['大きさ']):
   for x in range(s['大きさ']):
    m=membership(direction,x,y,s['大きさ'],kind)
    if m not in cache:cache[m]=query(h,MASK+':'+kind,{MX:m},MY) if m is not None else (None,None)
    v,r=cache[m]
    if type(v) is not bool:holds.append('上書きHDS/形状未支持')
    elif v:canvas[y][x]=color
  q.extend(r for v,r in cache.values())
 else:holds.append('公開クリック等の効果未同定')
 out={'状態':'HOLD','前':s,'役割':role,'作用':action,'照会':q,'保留':holds,'実行許可':False}
 if holds:return out
 if optional_seen is None and sum(abs(z) for z in direction)==1:
  out['全配置候補']=[{'小器具有無':v,'配置候補':templates.get(sig([direction,v]),[])} for v in (False,True)]
  holds.append('小器具の有無を未観測。可視配置の二候補を一つにできない');return out
 visible_optional=bool(optional_seen) and sum(abs(z) for z in direction)==1
 key=sig([direction,visible_optional]);variants=templates.get(key,[])
 if len(variants)!=1:holds.append('公開器具配置テンプレート非一意/未観測');return out
 f=[list(r) for r in frame];cx,cy,cX,cY=s['対象矩形']
 for x,y,typ in s['装置画素']:f[cy+y][cx+x]=s['背景色']
 for y in range(s['大きさ']):
  for x in range(s['大きさ']):f[cy+y][cx+x]=canvas[y][x]
 for x,y,typ in variants[0]['画素']:
  if not(0<=cx+x<len(f[0]) and 0<=cy+y<len(f)):holds.append('予測器具が画面外');return out
  f[cy+y][cx+x]=2 if typ=='枠' else (0 if typ=='固定黒' else color)
 if kind=='色選択':
  for p in s['色見本']:
   x,y,right,bottom=p['矩形']
   for xx in range(x,right):f[bottom][xx]=0 if p['色']==color else 3
 try:post=read(f)
 except ValueError as e:holds.append('予測画素の再知覚失敗:'+str(e));return out
 if post['対象']!=canvas or post['方向']!=direction or post['器具色']!=color:holds.append('予測と再知覚が不整合');return out
 out.update({'状態':'条件付き次観測','予測盤面':f,'後':post,'配置由来':'過去の可視器具形状の役割テンプレート。独立した固定描画prior、HDS発明ではない。'})
 return out

def all_candidates(h,frame,available,templates,optional_seen):
 s=read(frame);actions=[{'id':a,'data':{}} for a in available if a!=6]
 if 6 in available:actions.extend({'id':6,'data':{'x':x,'y':y}} for y in range(64) for x in range(64))
 # 同一可視前提は一回だけ照会。全合法座標の対応は残す。
 cache={};out=[]
 for action in actions:
  role=classify(s,action);key=sig([role,クリック位置の支持(s,action)])
  if key not in cache:cache[key]=predict(h,frame,action,templates,optional_seen)
  p=cache[key];out.append({'作用':action,'役割':role,'状態':p['状態'],'保留':p['保留'],'予測参照':key})
 return {'全候補':out,'全固有予測':cache,'実行許可':False}

def close_paths(h,frame,available,templates,*,小器具支持=None):
 result=solve(h,frame,小器具支持=小器具支持);initial=read(frame);optional=bool(initial['小器具矩形群']) if sum(abs(v) for v in initial['方向'])==1 else 小器具支持;closed=[]
 for plan in result.get('全最短塗布経路',[]):
  current=frame;steps=[];holds=[]
  for high in plan['具体方向/色作用候補']:
   s=read(current);a={'id':high['作用'],'data':{}}
   if a['id']==6:
    if high['種類']=='色選択':x,y=next(p['クリック'] for p in s['色見本'] if p['色']==high['予測色'])
    else:
     if len(s['小器具矩形群'])!=1:holds.append('現在可視小器具が非一意');break
     x0,y0,x1,y1=s['小器具矩形群'][0];x,y=(x0+x1-1)//2,(y0+y1-1)//2
    a['data']={'x':x,'y':y}
   if a['id'] not in available:holds.append('作用使用可能性未確認');break
   pred=predict(h,current,a,templates,optional);steps.append({'作用':a,'前観測':s,'予測':pred,'実観測':'未実行。実環境では全相照合してから次段へ','実行許可':False})
   if pred['状態']=='HOLD':holds.extend(pred['保留']);break
   current=pred['予測盤面']
  final=read(current);closed.append({'全段':steps,'終端':final['対象'],'目標一致':final['対象']==result['代表目標'],'保留':holds,'実行許可':False})
 return {'全代表経路':closed,'初期全候補':all_candidates(h,frame,available,templates,optional),'実行許可':False}
