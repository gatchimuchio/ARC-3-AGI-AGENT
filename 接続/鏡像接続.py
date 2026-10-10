"""公開画素・全外部作用・同一外部HDSを受ける鏡像族の独立入口。"""
from pathlib import Path
import sys,itertools,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'HDS/学習系統/v0.4.2'))
from .鏡像内部 import 基礎 as 基, 目標, 履歴
from .鏡像内部.採否 import 採否,画素から前観測,正準値,合成手順を再照合
from .鏡像内部.再識別 import all_decompositions,selected_hypotheses,normalize
from .鏡像内部.手順 import 手順を作る

def 鏡像作用を照合(前観測,既観測形状,作用,hds,*,観測履歴=None):
 """意味観測入口。既観測形状は現在問題の観測に由来し、解/予定対象は受け取らない。"""
 try:
  axes=前観測['軸'];B=前観測['黒占有'];T=前観測['黄目標'];selected=前観測['可視選択軸索引']
  if not B or not T or not 1<=len(axes)<=2 or len({a['方向']for a in axes})!=len(axes):raise ValueError('非空本体/目標と1〜2直交軸が必要')
  if any(a['方向']not in(0,1)or not 0<=a['位置']<21 for a in axes):raise ValueError('軸の観測領域外')
  if selected is not None and(type(selected)is not int or not 0<=selected<len(axes)):raise ValueError('選択軸索引が観測と不整合')
  if type(作用['id'])is not int:raise ValueError('外部作用番号が整数でない')
  if 作用['id']==6 and any(type(作用['data'][k])is not int or not 0<=作用['data'][k]<64 for k in('x','y')):raise ValueError('クリックの外部座標領域外')
  return 採否(前観測,既観測形状,作用,hds,観測履歴)
 except (KeyError,ValueError,TypeError,IndexError)as err:
  return {'状態':'HOLD','保留理由群':[str(err)],'前観測':前観測,'作用':作用,'次観測照合用予測':None,'実行許可':False}

def 鏡像候補を作る(frame,available_actions,hds,*,既観測形状=None,観測履歴=None,経路も作る=True):
 actions=list(available_actions);out={'作用候補群':[],'全完成候補群':[],'経路候補群':[],'保留理由群':[],'実行許可':False,'採用順序':[]}
 try:
  obs,scene,why=画素から前観測(frame)
  if 基.visible(基.orbit(scene['本体'],scene['軸']))-scene['本体']!=scene['複製']:why.append('現在複製占有が固定鏡映候補と一致しない')
 except (ValueError,TypeError,IndexError)as exc:obs=None;why=[str(exc)]
 out['保留理由群'].extend(why)
 if obs is None or why:
  for a in actions:out['作用候補群'].append({'id':a,'状態':'HOLD','全座標領域':{'x':list(range(64)),'y':list(range(64)),'積全数':4096}if a==6 else None,'理由':why})
  return out
 shapes=既観測形状 if 既観測形状 is not None else [normalize(o['点'])for o in scene['対象']]
 out['既観測形状']=shapes;out['形状由来']='呼出側の観測履歴'if 既観測形状 is not None else'今回を初期観測とする8近傍形状。継続時は初期形状を必ず渡す'
 # SDKクリック4096点を21×21セル＋画面端で損失なく同値類化。全座標を残す。
 for a in actions:
  if a==6:
   groups={}
   for x,y in itertools.product(range(64),repeat=2):groups.setdefault((x//3,y//3),[]).append((x,y))
   classes=[]
   for coords in groups.values():
    x,y=coords[0];r=採否(obs,shapes,{'id':6,'data':{'x':x,'y':y}},hds,観測履歴)
    classes.append({'全同値座標':coords,'照合':r})
   out['作用候補群'].append({'id':6,'全座標数':4096,'座標同値類群':classes})
  else:out['作用候補群'].append({'id':a,'照合':採否(obs,shapes,{'id':a,'data':{}},hds,観測履歴)})
 ds,domain=all_decompositions(obs['黒占有'],shapes);hs=selected_hypotheses(ds,obs['白標識'],obs['黄目標'],obs['軸'],obs['可視選択軸索引'])
 if 観測履歴 is not None:hs=履歴.filter_history(hs,obs['軸'],観測履歴)
 out['全現在仮説']=hs;out['分解探索']=domain
 for hyp in hs:
  s=copy.deepcopy(scene);s['対象']=[{'点':p,'選択':hyp['選択対応']==('本体',i)}for i,p in enumerate(hyp['構成群'])];role,i=hyp['選択対応'];s['選択']={'役割':role,'対象':s['対象'][i]if role=='本体'else s['軸'][i]}
  goals=目標.candidates(hds,frame,s);out['全完成候補群'].append({'現在仮説':hyp,'全配置':goals})
  if 経路も作る:
   plans=手順を作る(hds,s,actions,goals)
   for plan in plans['全完成配置に対する手順']:
    plan['全観測履歴再照合']=合成手順を再照合(obs,shapes,plan['具体手順'],hds,観測履歴)
   out['経路候補群'].append({'現在仮説':hyp,'手順構成':plans})
 out['条件']=['二軸閉包は固定演算、HDS単軸教師と区別','空像のD4全同値候補を保持','各作用後の全応答/得点/状態/取消/リセットを再照合','経路は合成予測。実行許可を与えない']
 return out

def 鏡像全応答を照合(前照合,応答,hds,*,既観測形状,前得点=None,前状態=None,前完了レベル数=None):
 """全応答相を保存し、末尾一致だけでは未知途中相を消さない。SDKキーは外部契約。"""
 if not isinstance(応答,dict)or not isinstance(応答.get('frame'),(list,tuple)):
  return {'状態':'HOLD','全応答原票':応答,'全応答相':[],'次観測履歴':None,'保留理由群':['外部応答/全frame列の型が不正'],'実行許可':False}
 phases=応答['frame'];records=[];prediction=None;newhistory=None;再照会=None
 def 作用引数(a):
  if not isinstance(a,dict)or 'id'not in a or not isinstance(a.get('data',{}),dict):return None
  return (a['id'],{k:v for k,v in a.get('data',{}).items()if k!='game_id'})
 expected=作用引数(前照合.get('作用'));actual=作用引数(応答.get('action_input'))
 boundary=(前状態 is None or 応答.get('state')!=前状態 or not any(k in 応答 for k in('score','levels_completed'))
  or ('score'in 応答 and (前得点 is None or 応答['score']!=前得点))
  or ('levels_completed'in 応答 and (前完了レベル数 is None or 応答['levels_completed']!=前完了レベル数))
  or bool(応答.get('full_reset'))or (actual is not None and actual[0]==0)
  or expected is None or actual is None or expected!=actual)

 for i,frame in enumerate(phases):
  try:
   obs,s,why=画素から前観測(frame)
   if 再照会 is None:
    if all(k in 前照合 for k in('前観測','作用')):
     再照会=鏡像作用を照合(前照合['前観測'],既観測形状,前照合['作用'],hds,観測履歴=前照合.get('入力履歴'))
    else:再照会={'状態':'HOLD','保留理由群':['元の観測/作用証拠がなく現在HDSで再照会できない'],'次観測照合用予測':None}
    prediction=再照会.get('次観測照合用予測')
   goal=基.ask(hds,{'黄標識全被覆':基.fullcovered(s)},基.GOAL,'成功遷移')
   if goal['値']is None:why.append('現在HDSの目標照会がHOLD')
   if 再照会['状態']=='HOLD':why.append('現在HDSの元作用/保持再照会がHOLD')
   ds,domain=all_decompositions(obs['黒占有'],既観測形状);hs=selected_hypotheses(ds,obs['白標識'],obs['黄目標'],obs['軸'],obs['可視選択軸索引'])
   matches=履歴.filter_history(hs,obs['軸'],prediction)if prediction is not None else []
   occupancy=[]
   for p in (prediction or {}).get('全予測',[]):
    base=set().union(*(set(map(tuple,x))for x in p['構成群']));copies=基.visible(基.orbit(base,p['軸']))-base
    occupancy.append(base==s['本体']and copies==s['複製'])
   ok=bool(matches)and bool(occupancy)and all(occupancy)and not why and not boundary
   records.append({'相':i,'原画素':frame,'前観測':obs,'全分解':ds,'全選択仮説':hs,'履歴整合仮説':matches,'全占有一致':occupancy,'状態':'観測一致'if ok else'HOLD','保留理由群':why+(['作用実引数不一致、得点/状態/完了レベル数/リセット境界または前境界値未提供']if boundary else[]),'目標照会':goal})
  except (ValueError,TypeError,IndexError)as exc:records.append({'相':i,'原画素':frame,'状態':'HOLD','保留理由群':[str(exc)]})
 if records and all(r['状態']=='観測一致'for r in records):newhistory=prediction
 return {'現在HDS元作用再照会':再照会,'全応答原票':応答,'全応答相':records,'状態':'全応答一致'if newhistory is not None else'HOLD','次観測履歴':newhistory,'不可視差分':'公開未観測','呼出側対応条件':['同一環境GUID','直前観測に対応する実行済み作用と応答順序'],'実行許可':False}
