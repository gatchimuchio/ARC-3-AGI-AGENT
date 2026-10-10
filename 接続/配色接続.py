"""現在画素と同一外部HDSから、配色目標・作用候補・条件付き手順を構成する。"""
from .ARC3境界 import _盤面列,_作用番号,観測する
from .配色内部.知覚 import read
from .配色内部.予測 import all_candidates,close_paths,predict
from .配色内部.手順 import solve
from .配色内部.関係 import sig
from .配色内部.受理 import alternatives
from .配色内部.固定文法 import 配置文法,受理文法
from .配色内部.応答 import compare

def _未確認候補(actions,reason):
 out=[]
 for a in actions:
  if a==6:out.extend({'作用':{'id':6,'data':{'x':x,'y':y}},'状態':'HOLD','保留':[reason]} for y in range(64) for x in range(64))
  else:out.append({'作用':{'id':a,'data':{}},'状態':'HOLD','保留':[reason]})
 return out

def _履歴を読む(frame,history):
 s=read(frame)
 if history is None:return bool(s['小器具矩形群']) if sum(abs(v) for v in s['方向'])==1 else None
 if not isinstance(history,dict) or history.get('参照')!=s['参照'] or history.get('対象矩形')!=s['対象矩形'] or (history.get('小器具を観測済み') is not None and type(history.get('小器具を観測済み'))is not bool):raise ValueError('現在問題と観測履歴の対応が未確認')
 return bool(s['小器具矩形群']) if sum(abs(v) for v in s['方向'])==1 else history['小器具を観測済み']

def 配色候補を作る(frame,available_actions,hds,*,観測履歴=None,経路も作る=True):
 out={'状態':'HOLD','全作用候補':[],'全目標候補':[],'全代表経路':[],'保留理由群':[],'実行許可':False}
 actions=[]
 try:
  actions=[_作用番号(a) for a in available_actions]
  if len(set(actions))!=len(actions):raise ValueError('利用可能作用が重複')
  f=_盤面列((frame,))[0];scene=read(f);seen=_履歴を読む(f,観測履歴)
  prior=配置文法.get(sig([scene['方向'],bool(scene['小器具矩形群'])]),[])
  if len(prior)!=1 or sig(prior[0]['画素'])!=sig(scene['装置画素']):raise ValueError('現在器具の役割画素が12配置文法の範囲外')
 except (ValueError,TypeError,IndexError,KeyError) as exc:
  out['保留理由群'].append(str(exc));out['全作用候補']=_未確認候補(actions,str(exc));return out
 try:
  candidates=all_candidates(hds,f,actions,配置文法,seen);out['全作用候補']=candidates['全候補'];out['全固有予測']=candidates['全固有予測']
  out['全目標候補']=alternatives(hds,read(f),受理文法)
  if 経路も作る:
   paths=close_paths(hds,f,actions,配置文法,小器具支持=seen);out['全代表経路']=paths['全代表経路'];out['探索']=solve(hds,f,小器具支持=seen)
  out['状態']='条件付き候補' if any(c['状態']!='HOLD' for c in out['全作用候補']) else 'HOLD'
 except Exception as exc:out['保留理由群'].append(type(exc).__name__+':'+str(exc));out['状態']='HOLD';out['全作用候補']=_未確認候補(actions,str(exc));out['全代表経路']=[]
 out['適用限界']=['10×10知覚と12器具形状は固定文法','3受理視点は公開応答と整合する仮説で真の必要十分条件は未確定','全最短塗布列を保持。方向の代表経路であり全作用最短を保証しない','短対角以外の完成候補と未支持クリックは排除しない','画素予測の最下行の表示領域候補は未モデル化。全残差を保存','毎作用後の全相gateを満たすまで後続実行不可']
 return out

def 配色全応答を照合(前原票,応答,作用,hds,*,観測履歴=None,前通番=0,後通番=1):
 out={'状態':'HOLD','全応答原票':応答,'全相':[],'次履歴':None,'保留':['入力境界未確認'],'実行許可':False}
 try:
  for r in (前原票,応答):
   if not isinstance(r,dict):raise ValueError('公開応答は辞書が必要')
   frames=_盤面列(r.get('frame'))
   if any(len(f)!=64 or len(f[0])!=64 for f in frames):raise ValueError('全応答相は64×64の公開範囲に限定')
   if not any(k in r for k in ('score','levels_completed')):raise ValueError('進捗カウンタ未観測')
   for k in ('score','levels_completed'):
    if k in r and(type(r[k])is not int or r[k]<0):raise ValueError('進捗カウンタ型不正')
   if 'score'in r and 'levels_completed'in r and r['score']!=r['levels_completed']:raise ValueError('二つの進捗カウンタが不整合')
  def obs(r,n):return 観測する({**r,'levels_completed':r.get('levels_completed',r.get('score'))},観測通番=n)
  old=obs(前原票,前通番);new=obs(応答,後通番);seen=_履歴を読む(old.最新盤面,観測履歴)
  out=compare(hds,old,new,作用,配置文法,seen,actual_action=応答.get('action_input'));out['全応答原票']=応答
  if out.get('次履歴'):
   s=read(new.最新盤面);out['次履歴'].update({'参照':s['参照'],'対象矩形':s['対象矩形']})
 except Exception as exc:out['状態']='HOLD';out['次履歴']=None;out['保留']=[type(exc).__name__+':'+str(exc)]
 return out
