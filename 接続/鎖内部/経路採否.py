"""格子モデルの全最短経路を旧局所規則へ照合。未知経路も保持する。"""
from . import 候補 as C, 格子 as S

def 全最短経路(search):
 parents=search['全同深さ親']
 def visit(j):
  if j==0:return [[]]
  return [path+[{'元状態':p['状態'],'作用':p['作用'],'先状態':j}] for p in parents.get(j,parents.get(str(j),[])) for path in visit(p['状態'])]
 return [path for end in search['目標状態群'] for path in visit(end)]

def 局所意味一致(before,after,target,action,prediction):
 if action in (1,2):expected='全目標色列保持' if before==after else None
 elif action==4:
  expected='同列' if before==after else ('正順一珠接続' if after==target[:len(after)] else '非正順一珠接続') if len(after)==len(before)+1 and after[:-1]==before else None
 elif action==3:
  expected='同列' if before==after else ('正前置除去' if before==target[:len(before)] else '誤後続除去') if before and after==before[:-1] else None
 else:expected=None
 return expected is not None and prediction==[[expected]],expected

def 全経路を判定(search,hds,*,照会共有=False):
 if search.get('状態')!='条件付き目標経路':return {'経路候補群':[],'作用照合群':[],'支持経路数':0,'保留経路数':0,'実行許可':False}
 paths=全最短経路(search);checks=[];cache={};results=[]
 def state(i):
  r=search['状態群'][i];return (r[0],r[1],tuple(tuple(b) for b in r[2]))
 for i,path in enumerate(paths):
  steps=[]
  for step in path:
   key=(step['元状態'],step['作用'],step['先状態'])
   if key not in cache:
    before,after=state(key[0]),state(key[2]);frame=S.render(before,search['文脈']);local=C.evaluate(frame,[key[1]],hds,share_queries=照会共有)
    chosen=local['作用候補群'][0];consistent,expected=局所意味一致(S.root_sequence(before),S.root_sequence(after),search['目標列'],key[1],chosen.get('局所予測',[]));supported=chosen['採否']=='局所作用支持';idx=len(checks)
    record={'照合番号':idx,**step,'旧局所候補':chosen,'照会記録':local['照会記録'],'期待局所意味':expected,'局所支持':supported,'予測整合':consistent if supported else None,'採否':'両規則支持' if supported and consistent else '断定保留','保留理由':[] if supported and consistent else ['旧局所規則が未知/隔離/支持なし'] if not supported else ['格子次状態と旧局所規則の整合未確認'],'実行許可':False};checks.append(record);cache[key]=idx
   steps.append({**step,'作用照合参照':cache[key]})
  held=[s['作用照合参照'] for s in steps if checks[s['作用照合参照']]['採否']!='両規則支持'];results.append({'経路番号':i,'手順':steps,'採否':'両規則支持' if not held else '断定保留','保留作用参照':held,'実行許可':False})
 return {'経路候補群':results,'作用照合群':checks,'支持経路数':sum(r['採否']=='両規則支持' for r in results),'保留経路数':sum(r['採否']=='断定保留' for r in results),'全候補保持':len(results)==len(paths),'実行許可':False}
