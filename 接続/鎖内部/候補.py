import json
from . import 画素 as G, 前提 as A
_prior=A.prior
def normalize_available(values):
 out=[]
 for x in values:
  if hasattr(x,'name'):x=x.name
  if isinstance(x,str):x=0 if x=='RESET' else int(x[6:]) if x.startswith('ACTION') and x[6:].isdigit() else None
  if type(x) is not int or not 0<=x<=7:raise ValueError('available_actionsの作用番号が不正')
  if x in out:raise ValueError('available_actionsの重複')
  out.append(x)
 return sorted(out)

def full_domain(available):
 for n in normalize_available(available):
  if n==6:
   for y in range(64):
    for x in range(64):yield {'id':6,'data':{'x':x,'y':y}}
  else:yield {'id':n,'data':{}}

def evaluate(frame,available,h,*,share_queries=False):
 domain=list(full_domain(available));base={'適用性':'未確認','対象群':[],'関係群':[],'目標候補群':[],'作用候補群':[],'保留理由群':[],'照会記録':[],'出所':{'候補生成':'SDK作用領域の全数列挙','固定前提':'既存知覚/関係語彙、開口軸の私有依存注入','実学習':'外部から注入された同一HDSの有効対応のみ'},'実行許可':False}
 try:
  scene=G.parse(frame);go=G.reconstruct(frame,h);selected=A.active_roots(frame,scene)
 except (ValueError,TypeError) as err:
  base['保留理由群']=[str(err)];base['作用候補群']=[{'候補番号':i,'作用':act,'採否':'断定保留','理由':[str(err)],'実行許可':False} for i,act in enumerate(domain)];base['探索順序']=list(range(len(domain)));return base
 base['対象群']=scene['根']+scene['珠'];base['目標候補群']=go.get('目標',[]);base['関係群']=go.get('共有対象関係',[])
 goals=base['目標候補群'];goalready=go['状態']=='目標候補生成';base['適用性']='適用可能' if goalready else '未確認'
 if not goalready:base['保留理由群'].append('目標候補が未確定')
 if len(selected)!=1:base['保留理由群'].append('選択根が一意でない')
 cache={}
 def ask(boundary,inp,path):
  key=json.dumps([boundary,inp,path],ensure_ascii=False,sort_keys=True)
  if not share_queries or key not in cache:
   raw=h.照会する(G.外部入力(inp,boundary));vs=[x['予測値'] for x in raw.内容['予測群'] if tuple(x['結果経路'])==(path,)];status=raw.状態 if vs else '断定保留';idx=len(base['照会記録'])
   record={'照会番号':idx,'境界':boundary,'入力':inp,'状態':status,'予測':vs,'内容':raw.内容,'元照会追跡':raw.追跡情報};base['照会記録'].append(record);cache[key]=record
  return cache[key]
 for idx,act in enumerate(domain):
  record={'候補番号':idx,'作用':act,'採否':'断定保留','理由':[],'局所予測':[],'照会参照':[],'実行許可':False};queries=[]
  if not goalready or len(selected)!=1:record['理由']=list(base['保留理由群'])
  elif act['id']==6:
   f=A.click_features(frame,act,goals)
   if f['保留']:record['理由']=f['保留']
   elif act['data']['x']>=len(frame[0]) or act['data']['y']>=len(frame):record['理由']=['可視画素の外側座標']
   else:
    queries=[ask('公開画素・根選択',{'作用前提':A.root_key(f)},'目標作用')];record['対象関係']=f
  elif act['id'] not in (1,2,3,4):record['理由']=['この作用の遷移教師がない']
  elif selected[0]['色'] not in [x['根色'] for x in goals]:
   for g in goals:
    f=A.features(frame,act,goals,g['根色'])
    if f['保留']:record['理由']+=f['保留'];continue
    queries.append(ask('公開画素・操作根から小根への間接制御',{'制御関係':A.indirect_key(f)},'目標前置作用'))
  else:
   p=_prior(frame,act,goals);record['対象関係']=p
   if p['保留']:record['理由']=p['保留']
   elif p['作用型']=='軸伸長':queries=[ask('公開画素・目標鎖への軸伸長作用',{'目標接続前提':A.descriptor(p)},'実測順序作用')]
   elif p['作用型']=='軸収縮':
    f=A.retract_features(frame,p)
    if f is None:record['理由']=['逆軸縮退の支持なし']
    else:queries=[ask('公開画素・誤後続と正前置の縮退',{'作用前提':A.retract_key(f)},'目標作用')]
   elif p['作用型']=='根横移動':queries=[ask('公開画素・横移動の他鎖保護',{'作用前提':A.movement_key({'元作用記録':{'前提':p}})},'目標作用')]
  record['照会参照']=[q['照会番号'] for q in queries];record['局所予測']=[q['予測'] for q in queries]
  if queries and all(q['状態']=='出力' and len(set(q['予測']))==1 for q in queries) and not record['理由']:
   record['採否']='局所作用支持';record['理由']=['局所目標作用にHDS支持あり。完全次状態と経路/安全性は別判定']
  elif not record['理由']:record['理由']=['HDS予測なし・未知条件・競合・隔離のいずれか']
  base['作用候補群'].append(record)
 base['探索順序']=list(range(len(domain)))
 base['探索順序の由来']='固定SDK番号→y→x。全候補保持。採否からの削除/優先枝限定なし。'
 return base
