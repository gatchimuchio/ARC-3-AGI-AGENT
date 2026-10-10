"""予定個体IDを受け取らず、全観測仮説と支持された過去作用だけを照合する。"""
import json
from . import 基礎 as e, 履歴 as m
from .再識別 import all_decompositions, selected_hypotheses
from .作用 import effect

def 正準値(v):
 if isinstance(v,dict):return {k:正準値(x)for k,x in v.items()}
 if isinstance(v,(set,frozenset)):return [正準値(x)for x in sorted(v)]
 if isinstance(v,(tuple,list)):return [正準値(x)for x in v]
 return v

def 採否(obs,shapes,action,hds,history=None):
 ds,domain=all_decompositions(obs['黒占有'],shapes)
 hs=selected_hypotheses(ds,obs['白標識'],obs['黄目標'],obs['軸'],obs['可視選択軸索引'])
 visible=list(hs)
 if history is not None:hs=m.filter_history(hs,obs['軸'],history)
 effects=[];keys=set();holds=[];nexts=[];supports=[]
 if not hs:holds.append('現在観測と支持履歴に整合する非空仮説がない')
 for h in hs:
  ef=effect(h,obs['軸'],action,hds);effects.append(ef)
  if 'HOLD'in ef:holds.append(ef['HOLD']);continue
  for o in ef['候補']:keys.add(json.dumps(正準値(o['効果']),ensure_ascii=False,sort_keys=True))
  if action['id']in e.D:
   f,reason=m.facts({'全選択仮説':[h],'軸':obs['軸']},action)
   q=e.ask(hds,e.encode(f,True),m.BOUNDARY,m.RESULT)if f else None
   supports.append({'前提':f,'照会':q,'理由':reason})
   if not q or q['値']is not True:holds.append('作用後の同一選択保持が未支持')
   else:nexts.extend(o['次仮説']for o in ef['候補'])
  else:
   supports.append({'照会':ef['照会'],'由来':'既存のクリック/軸循環後選択教師'})
   nexts.extend(o['次仮説']for o in ef['候補'])
 if len(keys)!=1:holds.append('全仮説の占有差分/次選択対応が一致しない')
 return {'前観測':obs,'既観測形状':shapes,'作用':action,'入力履歴':history,'状態':'HOLD'if holds else'条件付き支持','分解探索':domain,'全分解':ds,'全可視仮説':visible,'全履歴整合仮説':hs,'全作用照会':effects,'保持照会':supports,'相異効果数':len(keys),'保留理由群':holds,'次観測照合用予測':{'全予測':nexts,'前観測仮説':hs,'既経過作用':action,'支持':supports}if not holds else None,'実行許可':False}

def 画素から前観測(frame):
 if not isinstance(frame,(list,tuple))or len(frame)!=64 or any(not isinstance(r,(list,tuple))or len(r)!=64 for r in frame):raise ValueError('64×64公開画素が必要')
 if any(type(v)is not int or not 0<=v<16 for row in frame for v in row):raise ValueError('画素値の外部契約違反')
 s=e.scene(frame);B=s['本体'];ax=s['軸'];selected=[i for i,a in enumerate(ax)if a['選択']]
 blocked=s['目標']|{p for p in B if any(p[a['方向']]==a['位置']for a in ax)}
 obs={'黒占有':B,'白標識':{p for p in B-blocked if s['セル'][p]['中心']==0},'黄目標':s['目標'],'軸':ax,'可視選択軸索引':selected[0]if len(selected)==1 else None}
 why=[]
 if s['不明']:why.append('知覚文法外セルを保持')
 if not B or not s['目標']or not 1<=len(ax)<=2:why.append('非空の本体/目標および1〜2軸が必要')
 if len(selected)>1 or any(a['標識曖昧']for a in ax):why.append('軸選択標識が不確定')
 return obs,s,why

def 合成手順を再照合(初期観測,既観測形状,手順,hds,履歴=None):
 """全事後仮説から保守的前観測を合成する条件付き試験。実行履歴ではない。"""
 branches=[(初期観測,履歴)];records=[];holds=[]
 for step in 手順:
  action=step.get('作用',step.get('代表作用'));checks=[];nextbranches=[]
  if action is None:holds.append('具体作用なし');records.append({'元段':step,'状態':'HOLD'});break
  for obs,history in branches:
   r=採否(obs,既観測形状,action,hds,history);checks.append(r)
   if r['状態']=='HOLD':holds.extend(r['保留理由群']);continue
   memory=r['次観測照合用予測']
   for p in memory['全予測']:
    parts=p['構成群'];axes=p['軸'];B=set().union(*parts);blocked=set(map(tuple,obs['黄目標']))|{v for v in B if any(v[a['方向']]==a['位置']for a in axes)};role,i=p['選択対応']
    W=parts[i]-set().union(*(v for j,v in enumerate(parts)if j!=i))-blocked if role=='本体'else set()
    after={'黒占有':B,'白標識':W,'黄目標':obs['黄目標'],'軸':axes,'可視選択軸索引':i if role=='鏡軸'else None}
    nextbranches.append((after,memory))
  records.append({'作用':action,'全分岐採否':checks,'全次観測候補数':len(nextbranches),'状態':'HOLD'if any(r['状態']=='HOLD'for r in checks)or not checks else'条件付き支持'})
  branches=nextbranches
  if not branches:break
 return {'全段':records,'全段成立':len(records)==len(手順)and all(r['状態']=='条件付き支持'for r in records),'保留理由群':holds,'合成観測で未実測':True,'実行許可':False}
