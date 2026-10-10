"""巡回語彙の独立候補API。同じHDSを都度照会し、外部Actionは発行しない。"""
from .巡回内部.計画 import plan,checked_scene,unevaluated_actions
from .ARC3境界 import _整数

def _基底(出所,作用=()):
 return {'適用性':{'状態':'未確認','根拠':[]},'作用適用性':{'状態':'未確認','根拠':[]},'対象群':[],'関係群':[],'目標候補群':[],'作用候補群':[],'次作用候補群':[],'保留理由群':[],'規則不確実性':[],'前提照会記録':[],'全遷移計画':None,'未同定作用群':[],'未評価作用候補群':unevaluated_actions(作用),'観測目標充足':False,'公式完了確認':False,'出所':出所,'実行許可':False}

def 候補を構成する(系,盤面,*,作用可能番号=(),出所=None,検証状態上限=100):
 """出所は返却用のみ。ゲーム/level/filename/hashで知覚・規則・計画を選ばない。"""
 result=_基底(出所,作用可能番号)
 try:
  frame,p,parsed=checked_scene(盤面,作用可能番号);result['対象群']=p['トークン'];result['関係群']=parsed['標識群']
  r=plan(frame,系,作用可能番号,state_limit=検証状態上限);graph=r['全遷移計画'];result['計画状態']=r['状態'];result['全遷移計画']=graph;result['保留理由群']=[r['理由']];result['未同定作用群']=r['未同定作用'];result['未評価作用候補群']=r['未評価作用候補群'];result['作用モデル群']=r['作用モデル群'];result['探索資源境界']=r.get('全到達状態数算定');result['観測目標充足']=r['観測目標充足'];result['前提照会記録']=[{'種類':k,'判定':v} for k,v in graph.get('前提判定',{}).items()]
  evaluated=[q['判定'] for q in result['前提照会記録']]+[d['HDS判定'] for c in result['作用モデル群']+result['未同定作用群'] for d in c.get('全変位候補判定',[])]
  result['規則不確実性']=[{'入力':q['入力'],'状態':q['状態'],'判定':q['判定']} for q in evaluated if q['判定'] in ('HOLD','例外')]
  result['目標候補群']=[{'対象番号':i,'必要色':c} for i,c in graph['目標']]
  for i,m in enumerate(graph['作用モデル群']):
   x,y,r,b=m['標識']['範囲'];args={'x':(x+r)//2,'y':(y+b)//2}
   for k in ('x','y'):_整数(args[k],k,0,63)
   result['作用候補群'].append({'作用番号':6,'引数':args,'作用モデル番号':i,'最短達成経路の初手':False,'採否':'HOLD','意味':'限定巡回の次色モデル。目標計画採否は別','実行許可':False})
  if graph['網羅性']!='学習済み限定作用内の全到達集合':
   result['適用性']['根拠']=['HDS未支持、知覚/照会/作用例外、または全探索の適用範囲外'];result['次作用状態']='HOLD。部分グラフ・未展開・未評価候補を保持';return result
  result['適用性']={'状態':'適用可能','根拠':['標識色目標の知覚とHDS対応が支持']}
  if not graph['全目標状態']:
   result['作用適用性']={'状態':'未確認','根拠':['学習済み作用内の全到達集合にgoalがない。未知作用はHOLDで保持']};result['次作用状態']='限定作用内で未到達';return result
  result['作用適用性']={'状態':'適用可能','根拠':['限定作用の全到達集合で目標候補へ到達する経路を保持']}
  todo=list(graph['全目標状態']);seen=set();first=set()
  while todo:
   i=todo.pop()
   if i in seen:continue
   seen.add(i)
   for edge in graph['全状態'][i]['全最短親']:
    if edge['親']==0:first.add(edge['作用番号'])
    else:todo.append(edge['親'])
  for a in result['作用候補群']:
   a['最短達成経路の初手']=a['作用モデル番号'] in first;a['採否']='条件付き効果候補'
   if a['最短達成経路の初手']:result['次作用候補群'].append(a)
  result['次作用状態']='観測目標充足のため初手なし。公式完了は未確認' if result['観測目標充足'] else '全goalへの最短経路の全初手候補を保持'
  return result
 except Exception as e:
  result['適用性']={'状態':'未確認','根拠':[{'例外':type(e).__name__,'理由':str(e)}]};result['作用適用性']={'状態':'未確認','根拠':['候補構成が完了しなかった']};result['保留理由群'].append({'例外':type(e).__name__,'理由':str(e)});result['次作用候補群']=[];result['次作用状態']='HOLD。処理済みの候補/グラフは保持';return result

def 観測から候補を構成する(系,現在,*,検証状態上限=100):
 """既存公開観測のNOT_FINISHEDだけを受ける。識別子は読まない。"""
 try:
  if 現在.状態!='NOT_FINISHED':
   result=_基底({'観測通番':現在.観測通番,'観測指紋':現在.指紋},getattr(現在,'作用可能番号',()));result['保留理由群']=['進行中でない公開状態'];result['公式完了確認']=現在.状態=='WIN';result['次作用状態']='進行中でないので提案しない';return result
  return 候補を構成する(系,現在.最新盤面,作用可能番号=現在.作用可能番号,出所={'観測通番':現在.観測通番,'観測指紋':現在.指紋},検証状態上限=検証状態上限)
 except Exception as e:
  result=_基底(None);result['保留理由群']=[{'例外':type(e).__name__,'理由':str(e)}];return result
