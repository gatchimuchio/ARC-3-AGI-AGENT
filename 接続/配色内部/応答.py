"""API応答の全相を保持し、終端観測への一致と旧問題の完了を区別する。"""
from .知覚 import read
from .予測 import predict
from 接続.共通観測経路 import 作用応答を相別に記録する

def compare(h,previous,current,action,templates,optional_seen,*,actual_action=None):
 phases=作用応答を相別に記録する(previous,current,action['id']);out={'状態':'HOLD','相記録':phases,'全相':[],'予測':None,'実行許可':False,'次履歴':None,'保留':list(phases['保留理由群'])}
 def action_key(a):
  if not isinstance(a,dict) or type(a.get('id')) is not int or not isinstance(a.get('data',{}),dict):return None
  d={k:v for k,v in a.get('data',{}).items() if k!='game_id'}
  if a['id']==6 and (set(d)!={'x','y'} or any(type(v)is not int or not 0<=v<64 for v in d.values())):return None
  if a['id']!=6 and d:return None
  return a['id'],d
 if action_key(action) is None or action_key(actual_action)!=action_key(action):out['保留'].append('応答の実作用番号/引数が未確認または不一致')
 if previous.状態!='NOT_FINISHED':out['保留'].append('直前が実行中状態ではない')
 pred=predict(h,previous.最新盤面,action,templates,optional_seen);out['予測']=pred
 if pred['状態']=='HOLD':out['保留']+=pred['保留']
 before=read(previous.最新盤面);matched=[]
 for i,f in enumerate(current.盤面列):
  item={'相':i};out['全相'].append(item)
  try:p=read(f)
  except ValueError as e:
   item.update({'状態':'知覚HOLD','理由':str(e)});out['保留'].append(f'相{i}: 未説明の知覚不能相');continue
  old=p['参照']==before['参照'] and p['対象矩形']==before['対象矩形'];item['旧問題対応']=old
  if pred['状態']!='HOLD' and old:
   after=pred['後'];match=all(p[k]==after[k] for k in ('対象','方向','器具色','装置画素'));item['終端予測一致']=match
   item['状態']='終端予測一致' if match else '旧問題の途中相/未説明差分';item['画素残差']=[(x,y,a,b) for y,(r,s) in enumerate(zip(pred['予測盤面'],f)) for x,(a,b) in enumerate(zip(r,s)) if a!=b]
   if match:matched.append(i)
   # 末行残差も保存するが、この境界ではHUD作用を予測していない。
   item['盤面画素一致']=list(map(list,f[:-1]))==pred['予測盤面'][:-1]
   item['前盤面画素一致']=list(map(list,f[:-1]))==list(map(list,previous.最新盤面[:-1]))
   if not (item['盤面画素一致'] or item['前盤面画素一致']):out['保留'].append(f'相{i}: 前/予測盤面に一致しない未説明相')
  else:
   item['状態']='新問題/構造変更候補' if not old else 'HDS未支持'
   out['保留'].append(f'相{i}: 旧問題の支持された応答ではない')
 reset=action['id']==0 or current.全初期化 or current.実行識別子!=previous.実行識別子 or current.ゲーム識別子!=previous.ゲーム識別子
 progress=current.完了レベル数!=previous.完了レベル数 or current.状態!='NOT_FINISHED'
 out['終端一致相群']=matched;out['旧問題履歴破棄']=reset or progress
 if reset or progress:out['保留'].append('RESET/進捗/終端では旧履歴と次問題を分離');return out
 if not matched or matched[-1]!=len(current.盤面列)-1:out['保留'].append('API最新観測が支持された終端予測に一致しない')
 if not out['保留']:
  out['状態']='終端再観測一致';out['次履歴']={'小器具を観測済み':(bool(read(current.最新盤面)['小器具矩形群']) if sum(abs(v) for v in read(current.最新盤面)['方向'])==1 else optional_seen),'作用毎再照会':True}
 return out
