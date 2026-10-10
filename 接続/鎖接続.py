"""公開画素・available_actions・外部注入HDSによる鎖候補/経路の独立入口。"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'HDS/学習系統/v0.4.2'))
from .鎖内部 import 候補, 探索, 経路採否
from .ARC3境界 import _盤面列, 境界違反

def 鎖候補を作る(frame,available_actions,hds,*,経路も作る=True,照会共有=False):
 try:
  frame=[list(row) for row in _盤面列((frame,))[0]]
 except 境界違反 as err:
  # 不正観測でもSDKの全候補領域を保持し、HDSへは照会しない。
  out=候補.evaluate([],available_actions,hds,share_queries=照会共有)
  out['保留理由群']=[str(err)]
  for candidate in out['作用候補群']:candidate['理由']=[str(err)]
  out.update({'経路適用性':'未確認','経路候補群':[],'作用照合群':[],'実行許可':False})
  return out
 out=候補.evaluate(frame,available_actions,hds,share_queries=照会共有)
 out['経路候補群']=[];out['作用照合群']=[];out['実行許可']=False
 if not 経路も作る:return out
 if out['適用性']!='適用可能':
  out['保留理由群'].append('目標または観測が未確定のため経路未生成');return out
 try:search=探索.search(frame,available_actions,hds,share_queries=照会共有)
 except (ValueError,TypeError) as err:
  out['経路適用性']='未確認';out['保留理由群'].append(str(err));return out
 gate=経路採否.全経路を判定(search,hds,照会共有=照会共有)
 out.update(gate);out['探索記録']=search;out['経路適用性']='適用可能' if search['状態']=='条件付き目標経路' else '未確認'
 if gate['保留経路数']:out['保留理由群'].append('旧局所規則未支持/整合未確認の経路を削除せず保持')
 out['採用順序']=[]
 out['保留理由群'].append('支持経路は条件付き候補。実環境採用は常時HOLD')
 return out
