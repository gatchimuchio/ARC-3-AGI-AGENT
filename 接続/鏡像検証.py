"""教師の再投入なしで保存HDSと自己完結公開fixtureを全照合する。"""
import collections,copy,json
from dataclasses import asdict
from .鏡像教師CLI import 資料を読む
from .鏡像接続 import 鏡像作用を照合
from .鏡像内部 import 基礎 as e, 履歴 as m, 観測対応 as v
from .鏡像内部.再識別 import normalize
from .鏡像内部.採否 import 画素から前観測
from hds学習系統 import 外部入力

結果鍵={e.GOAL:'成功遷移',e.LINK:'鏡映予測複製と実測が一致',e.MOVE:'実測局所変位',e.SELECT:'後選択','公開鏡像:可視性別D4候補':'複製と観測整合','公開鏡像:軸からの選択循環':'後選択役割',m.BOUNDARY:m.RESULT}

class 読取照会共有:
 """この検証呼出しの間だけ、同一外部HDSの全入力一致照会を共有。学習経路なし。"""
 def __init__(self,hds):self.外部HDS=hds;self.照会表={}
 def 照会する(self,入力):
  key=json.dumps(asdict(入力),ensure_ascii=False,sort_keys=True)
  if key not in self.照会表:self.照会表[key]=self.外部HDS.照会する(入力)
  return self.照会表[key]

def 検証する(hds,*,全原票=False,人工反証=False):
 records=[];counts=collections.Counter();old=[];new=[];照会対象=読取照会共有(hds)
 for x in 資料を読む('旧44照会.json.gz'):
  x=x['旧'];q=e.ask(照会対象,x['照会']['入力'],x['境界'],結果鍵[x['境界']]);old.append({'入力':x['照会']['入力'],'境界':x['境界'],'照会':q,'一致':q['値']==x['期待']})
 for t in 資料を読む('関係教材.json')['教師群'][848:]:
  f={k:v for k,v in t['入力'].items()if k!=m.RESULT};q=e.ask(照会対象,f,t['境界'],m.RESULT);new.append({'境界':t['境界'],'入力':f,'照会':q,'一致':q['値']==t['入力'][m.RESULT]})
 for f in 資料を読む('46手順前観測.json.gz'):
  history=None;steps=[]
  for s in f['全前観測']:
   r=鏡像作用を照合(s['前観測'],f['既観測形状'],s['作用'],照会対象,観測履歴=history)
   steps.append({'手':s['手'],'旧固定条件':s['旧固定条件'],'照合':r});counts[r['状態']]+=1
   # 合成fixtureの直前作用を経過済みと置く独立閉包試験。runtime履歴確定には全応答APIが必要。
   history=r['次観測照合用予測']
  records.append({'資料索引':[f['資料'],f['開始'],f['候補番号']],'全段':steps,'全段成立':all(s['照合']['状態']=='条件付き支持'for s in steps),'合成fixture':True,'実行許可':False})
 result={'旧44照会':old,'保持203照会':new,'全46手順':records,'集計':{'旧44一致':sum(x['一致']for x in old),'保持203一致':sum(x['一致']for x in new),'全手順':len(records),'全段':sum(counts.values()),'段採否':dict(counts),'全段成立':sum(x['全段成立']for x in records)},'実行許可':False}
 if 全原票:
  raw=原票を検証(照会対象);result['全原票照合']=raw;result['集計']['原票']=raw['集計']
 if 人工反証:
  bad=copy.deepcopy(hds);f={'前提直積':'{"クリックは別対象固有領域":false,"作用クラス":"方向候補1-4","前選択役割":"本体","選択可能対象が複数":true}',m.RESULT:False}
  r=bad.処理する(外部入力(f,m.BOUNDARY));qs=[e.ask(bad,x['入力'],x['境界'],結果鍵[x['境界']])for x in old+new]
  result['反証隔離試験']={'人工入力':f,'処理状態':r.状態,'全247照会':qs,'全HOLD':all(q['値']is None for q in qs)};result['集計']['人工反証247全HOLD']=result['反証隔離試験']['全HOLD']
 return result

def 原票を検証(h):
 occupancy=collections.Counter();persistence=collections.Counter();records=[];phases=[]
 for source,pack in 資料を読む('全公開原票.json.gz').items():
  rows=pack['原票'];initial=e.scene(rows[0]['frame'][-1]);shapes=[normalize(o['点'])for o in initial['対象']];na=len(initial['軸'])
  for n in range(1,len(rows)):
   a,b=rows[n-1],rows[n];rec={'資料索引':[source,n],'全応答原票':b}
   if not a.get('frame')or not b.get('frame'):
    occupancy['非frame']+=1;persistence['HOLD']+=1;rec['状態']='非frame終端';records.append(rec);continue
   s=e.scene(a['frame'][-1]);act=b['action_input'];obs,_,_=画素から前観測(a['frame'][-1]);selected=[x for x in s['軸']if x['選択']]
   if len(b['frame'])>1:phases.append({'資料索引':[source,n],'全相':[{'相':i,'原画素':f,'知覚':e.compact(e.scene(f))}for i,f in enumerate(b['frame'])]})
   if act['id']not in e.D or b.get('full_reset'):state='非方向'
   elif s['不明']or len(selected)>1 or len(s['軸'])!=na:state='前知覚HOLD'
   else:
    r=鏡像作用を照合(obs,shapes,act,h);rec['占有採否']=r
    if r['状態']=='HOLD':state='gateHOLD'
    else:
     t=e.scene(b['frame'][0]);p=r['次観測照合用予測']['全予測'][0];B=set().union(*p['構成群']);C=e.visible(e.orbit(B,p['軸']))-B;state='占有一致'if B==t['本体']and C==t['複製']else'反証'
   occupancy[state]+=1;rec['占有状態']=state
   pre=v.observed(a['frame'][-1],shapes,na);post=v.observed(b['frame'][-1],shapes,na);holds=pre['HOLD']+post['HOLD']
   if b['score']!=a['score']or b['state']!=a['state']or b.get('full_reset')or act['id']==0:holds.append('問題/状態/RESET境界')
   state='HOLD';q=None
   if not holds:
    x,y=v.subject(pre),v.subject(post);facts,reason=m.facts(pre,act)
    if x is None or y is None:holds.append('同形対象で同一性不確定')
    elif reason:holds.append(reason)
    else:q=e.ask(h,e.encode(facts,True),m.BOUNDARY,m.RESULT);state='HOLD'if q['値']is None else'一致'if q['値']==(x==y)else'反証'
   persistence[state]+=1;rec['保持照合']={'前観測':pre,'後観測':post,'照会':q,'状態':state,'保留理由群':holds};records.append(rec)
   if b['score']>a['score']or act['id']==0:
    initial=e.scene(b['frame'][-1]);shapes=[normalize(o['点'])for o in initial['対象']];na=len(initial['軸'])
 return {'全原票照合':records,'全複数応答相':phases,'集計':{'全遷移':len(records),'占有':dict(occupancy),'保持':dict(persistence),'複数応答作用':len(phases),'全応答相':sum(len(p['全相'])for p in phases)}}

def 初期問題を再構成(hds):
 """完成答え/既知手順を渡さず、公開初期画素だけから全16問題を再構成。"""
 from .鏡像接続 import 鏡像候補を作る
 h=読取照会共有(hds);records=[]
 for source,pack in 資料を読む('全公開原票.json.gz').items():
  rows=pack['原票']
  # 完走資料であることは検証対象の選定のみ。runtime関数には画素とSDK作用だけを渡す。
  if not any(r.get('state')=='WIN'for r in rows):continue
  starts=[0]+[i for i in range(1,len(rows))if rows[i].get('frame')and rows[i]['score']>rows[i-1]['score']and rows[i]['state']!='WIN']
  for i in starts:
   r=鏡像候補を作る(rows[i]['frame'][-1],rows[i]['available_actions'],h)
   plans=[p for a in r['経路候補群']for p in a['手順構成']['全完成配置に対する手順']]
   records.append({'資料索引':[source,i],'全候補':r,'完成候補数':sum(x['全配置']['条件充足配置数']for x in r['全完成候補群']),'手順数':len(plans),'全段成立':sum(p['全観測履歴再照合']['全段成立']for p in plans),'全段数':sum(len(p['具体手順'])for p in plans)})
 return {'全問題':records,'集計':{'問題数':len(records),'完成候補数':sum(x['完成候補数']for x in records),'手順数':sum(x['手順数']for x in records),'全段成立':sum(x['全段成立']for x in records),'全段数':sum(x['全段数']for x in records)}}
