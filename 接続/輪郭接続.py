"""静的な輪郭配置の独立入口。外部HDS注入。SDK作用・答え読込みを行わない。"""
import itertools
from .ARC3境界 import _盤面列,_作用番号,観測する
from .共通観測経路 import 作用応答を相別に記録する,_画素差分
from .輪郭内部.知覚 import 読む,初期化,描画,状態を読む,初期輪郭画素を検査
from .輪郭内部.モデル import モデル
from .輪郭内部.構成 import compose

def _actions(values):
 actions=[];errors=[]
 if not isinstance(values,(list,tuple)):return [],['利用可能作用は列が必要']
 for v in values:
  try:
   a=_作用番号(v)
   if a in actions:errors.append('利用可能作用重複')
   else:actions.append(a)
  except Exception as e:errors.append(str(e))
 return actions,errors

def _hold(actions,reason):
 return [{'作用':a,'状態':'HOLD','領域':'外部契約の全座標 {(x,y)|0<=x<64,0<=y<64}。未評価' if a==6 else'作用記号全域','保留理由群':[reason]}for a in actions]

def 輪郭候補を作る(frame,available_actions,hds,*,経路も作る=False,段階展開上限=None):
 actions,errors=_actions(available_actions);out={'適用性':{'状態':'未確認'},'状態':'HOLD','対象群':[],'関係群':[],'目標候補群':[],'作用候補群':_hold(actions,'入力又は構造未確認'),'全36構成候補':[],'照会記録':[],'保留理由群':errors[:],'実行許可':False}
 if errors:return out
 try:
  f=_盤面列((frame,))[0]
  if len(f)!=64 or len(f[0])!=64:raise ValueError('64×64の固定知覚のみ支持')
  if 段階展開上限 is not None and(type(段階展開上限)is not int or 段階展開上限<0):raise ValueError('段階展開上限不正')
  p=読む(f);out['対象群']=p['小枠'];out['関係群']=[{'関係':'初期輪郭領域所属','領域':p['輪郭領域']}];slots=sorted({z for region in p['輪郭領域']for z in region})
  out['目標候補全域']={'集合定義':'輪郭位置群から小枠数個を選ぶ全組合せと全ラベル割当','輪郭位置群':slots,'小枠数':len(p['小枠']),'採否':'未評価'}
  if len(p['小枠'])!=3 or len(slots)!=3 or any(v in(5,12,15)for row in f[:60]for v in row):
   out['適用性']={'状態':'構造上不適用','理由':'3枠3目標位置・自律担体なしの静的構成範囲外'};out['保留理由群'].append('他8問題の動的作用は未達');return out
  状態を読む(f);初期輪郭画素を検査(f,p['輪郭領域'])
  initial,why=初期化(f)
  if why:raise ValueError(why)
  bg,start=initial
  if 描画(bg,start)[:60]!=[list(row)for row in f[:60]]:raise ValueError('初期対象・強調役割の再描画が可視画素と一致しない')
  if any(set(v for row in bg[y:y+4]for v in row[x:x+4])not in({1},{2,9})for y in range(0,60,4)for x in range(0,64,4)):
   raise ValueError('背景の固定静的語彙が未確認')
  out['適用性']={'状態':'適用可能'}
  out['目標候補群']=[{'割当':a,'状態':'HOLD'}for a in itertools.permutations(slots)]
  out['全36構成候補']=[{'割当':a,'順序':o,'状態':'HOLD','理由':'段階経路は未展開'}for a in itertools.permutations(slots)for o in itertools.permutations(range(3))]
  m=モデル(hds,f);out['照会記録'].append(m.gq)
  out['目標候補群']=[{'割当':a,'状態':'条件付き支持'if m.gq['値']=={'進捗応答':True}else'HOLD'}for a in itertools.permutations(slots)]
  out['全36構成候補']=[{'割当':a,'順序':o,'状態':'HOLD','理由':'段階経路は未展開'}for a in itertools.permutations(slots)for o in itertools.permutations(range(3))]
  candidates=[]
  for a in actions:
   if a not in range(1,6):candidates.extend(_hold([a],'未支持作用。RESETは別instance境界'));continue
   nxt,status,key=m.next(start,a);candidates.append({'作用':a,'状態':'条件付き空間予測支持'if nxt is not None else'HOLD','採否':status,'予測状態':nxt,'予測盤面':描画(bg,nxt)if nxt else None,'照会鍵':key,'未確認前提':['非対象保存','向き描画','予算位相・非終端']})
  out['作用候補群']=candidates;out['構成文脈']={'前盤面':f,'固定背景':bg,'初期状態':start,'目標位置群':slots,'使用可能作用':actions};out['状態']='条件付き候補'if any(x['状態']!='HOLD'for x in candidates)else'HOLD'
  if 経路も作る:
   if not all(a in actions for a in range(1,6)):out['保留理由群'].append('全段階構成には1–5の作用集合が必要。欠けた作用を使用しない')
   else:out.update(compose(m,段階展開上限))
  out['照会記録']=[m.gq]+list(m.cache.values())
  out['固定前提群']=['4画素テンプレート知覚','初期遮蔽床を1と置く描画','非対象枠の位置保存','保持枠共同変位と向き更新','対象以外を動かさない段階構成','空間状態の同一化は予算・hidden同値ではない']
 except Exception as e:
  out['保留理由群'].append(type(e).__name__+':'+str(e));out['状態']='HOLD';out['作用候補群']=_hold(actions,str(e))
 return out

def _明示カウンタを読む(raw,reasons):
 result=dict(raw)
 for modern,legacy in (('levels_completed','score'),('win_levels','win_score')):
  present=[raw[k]for k in (modern,legacy)if k in raw]
  if not present:reasons.append('完了カウンタ欠損:'+modern);continue
  if any(type(v)is not int or v<0 for v in present):reasons.append('完了カウンタ不正:'+modern);continue
  if len(set(present))!=1:reasons.append('新旧完了カウンタが矛盾:'+modern);continue
  result[modern]=present[0]
 return result

def 輪郭全応答を照合(前原票,応答,作用,hds,*,前通番=0,後通番=1):
 out={'状態':'HOLD','全応答原票':応答,'全相':[],'保留理由群':[],'実行許可':False,'後続手順採否':'HOLD。初回独立入口であり継続履歴の再構成は未実装'}
 try:
  before=_明示カウンタを読む(前原票,out['保留理由群']);after=_明示カウンタを読む(応答,out['保留理由群'])
  old=観測する(before,観測通番=前通番);new=観測する(after,観測通番=後通番);a=_作用番号(作用);ledger=作用応答を相別に記録する(old,new,a);out['相記録']=ledger;out['保留理由群']+=ledger['保留理由群']
  reported=応答.get('action_input')
  if not isinstance(reported,dict)or _作用番号(reported.get('id'))!=a:out['保留理由群'].append('応答内の実作用との対応未確認')
  if isinstance(reported,dict):
   data=reported.get('data',{})
   if not isinstance(data,dict):out['保留理由群'].append('実作用引数の形式が不正')
   else:
    if 'game_id'in data and data['game_id']!=new.ゲーム識別子:out['保留理由群'].append('実作用の出所ゲームが一致しない')
    args={k:v for k,v in data.items()if k!='game_id'}
    if a!=6 and args:out['保留理由群'].append('非座標作用に未確認の実引数がある')
    if a==6 and(set(args)!={'x','y'}or any(type(v)is not int or not 0<=v<64 for v in args.values())):out['保留理由群'].append('座標実作用の引数が不正')
  for i,f in enumerate(new.盤面列):out['全相'].append({'相':i,'盤面':f,'状態':'HOLD','空間残差':None,'予算行':f[63]if len(f)==64 else None})
  if any(len(f)!=64 or len(f[0])!=64 for f in old.盤面列+new.盤面列):out['保留理由群'].append('全相64×64範囲外')
  if old.状態!='NOT_FINISHED':out['保留理由群'].append('前観測が進行中ではない')
  if ledger['完了数増分']!=0 or new.状態!='NOT_FINISHED' or old.全レベル数!=new.全レベル数:out['保留理由群'].append('進捗・終端・全問題数境界。旧手順を引き継がない')
  if out['保留理由群']:return out
  proposal=輪郭候補を作る(old.最新盤面,list(old.作用可能番号),hds);out['旧候補']=proposal;matches=[c for c in proposal['作用候補群']if c['作用']==a and c.get('予測盤面')is not None]
  if len(matches)!=1:out['保留理由群'].append('作用前空間予測が一意に支持されない');return out
  predicted=matches[0]['予測盤面']
  for r in out['全相']:
   diff=_画素差分(predicted[:60],r['盤面'][:60]);r['空間残差']=diff;r['状態']='条件付き空間一致'if not diff['差分']else'空間不一致HOLD';r['未モデル化行群']=r['盤面'][60:]
  if ledger['完了数増分']!=0 or new.状態!='NOT_FINISHED':out['保留理由群'].append('進捗・終端・新問題境界。旧手順を引き継がない')
  elif any(r['状態']!='条件付き空間一致'for r in out['全相']):out['保留理由群'].append('不一致相がある。全相・全代替を保持して後続HOLD')
  else:out['状態']='全相の条件付き空間予測一致'
 except Exception as e:out['保留理由群'].append(type(e).__name__+':'+str(e))
 return out
