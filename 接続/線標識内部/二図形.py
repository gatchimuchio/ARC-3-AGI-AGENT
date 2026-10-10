import json,itertools,collections,math
from . import 基礎 as e,規則 as f,知覚 as p
def 作用入力(act,free=True):return {'前状態作用直積':json.dumps({'前方中心は画面内':free,'作用番号':act},ensure_ascii=False,sort_keys=True,separators=(',',':'))}

def 構成(frame,h):
 init=e.知覚初期(frame)
 if not init['適用可能']:return {'状態':'保留','理由':'観測した二色二十字の固定文法外','初期知覚':init,'実行許可':False}
 os=init['図形'];qs=[]
 def ask(kind,inp):
  q=f.照会(h,kind,inp);qs.append(q);return q['値']
 goal=[ask('目標',{'全標識の同色線被覆':v}) for v in [False,True]]
 keep=[ask('保存',{'作用関係':a}) for a in ['方向作用','選択作用']]
 switch=[ask('選択',{'候補は現在非選択':v}) for v in [False,True]]
 move={a:ask('方向',作用入力(a)) for a in e.方向}
 depth=[ask('描画',{'候補色と相手色':json.dumps([os[i]['色'],os[j]['色']])}) for i,j in [(0,1),(1,0)]]
 if goal!=[False,True] or keep!=[True,True] or switch!=[False,True] or any(v is None for v in move.values()) or depth not in ([True,False],[False,True]):
  return {'状態':'保留','理由':'同一HDSで全構成要素の支持が閉じない','全照会':qs,'実行許可':False}
 deltas={a:tuple(map(int,v.split(','))) for a,v in move.items()};order=[1,0] if depth==[True,False] else [0,1]
 if p.描画(init,os,order)!=[list(row)for row in frame[:63]]:return {'状態':'保留','理由':'HDS支持描画順と初期可視画素が一致しない','全照会':qs,'未照合領域':'最下行HUD','実行許可':False}
 # この構成器は四つの反対称な直交並進だけを扱う。値はHDS照会で取得する。
 if any(len(d)!=2 for d in deltas.values()) or set(deltas.values())!={(0,-3),(0,3),(-3,0),(3,0)}:return {'状態':'保留','理由':'前状態格子文法と支持された作用変位が一致しない','全照会':qs,'実行許可':False}
 factors=[]
 for obj in os:
  targets=[t for t in init['標識'] if t['色']==obj['色']];positions={obj['中心']:0};queue=collections.deque([obj['中心']]);edges=[];pred=collections.defaultdict(list)
  while queue:
   pos=queue.popleft();actions=[]
   for act,(dx,dy) in deltas.items():
    nxt=(pos[0]+dx,pos[1]+dy);valid=0<=nxt[0]<64 and 0<=nxt[1]<63
    if valid:
     if nxt not in positions:positions[nxt]=positions[pos]+1;queue.append(nxt)
     if positions[nxt]==positions[pos]+1:pred[nxt].append((pos,act))
    actions.append({'作用':act,'状態':'抽象関係候補' if valid else '保留','次中心':nxt if valid else None,'理由':None if valid else '選択黒点が可視画面外。観測HOLDを仮定で解除しない'})
   edges.append({'中心':pos,'全四方向':actions})
  goals=[];allpos=[]
  for y in range(64):
   for x in range(64):
    points=e.形の点(obj,(x,y));covered=bool(targets) and all(tuple(t['中心']) in points for t in targets);reachable=(x,y) in positions
    allpos.append({'中心':(x,y),'全同色標識被覆':covered,'到達格子内':reachable,'状態':'幾何目標候補' if covered and reachable else '保留' if y==63 else '幾何対応不成立又は到達格子外'})
    if covered and reachable:goals.append((x,y))
  factors.append({'対象色':obj['色'],'初期中心':obj['中心'],'全中心候補4096':allpos,'全可達中心':list(positions),'距離':positions,'全四方向辺':edges,'全最短親':pred,'目標中心群':goals})
 selected=next(i for i,o in enumerate(os) if o['選択']);goals=list(itertools.product(*(v['目標中心群'] for v in factors)));planspec=[]
 def paths(i,goal):
  if goal==os[i]['中心']:return [[]]
  return [p+[a] for before,a in factors[i]['全最短親'][goal] for p in paths(i,before)]
 for endpoints in goals:
  needed=[i for i,pos in enumerate(endpoints) if pos!=os[i]['中心']]
  for visiting in itertools.permutations(needed):
   actor=selected;length=0
   for i in visiting:
    if actor!=i:length+=1;actor=i
    length+=factors[i]['距離'][endpoints[i]]
   planspec.append({'目標中心':endpoints,'対象処理順':visiting,'最小作用数':length})
 if not planspec:return {'状態':'保留','理由':'全目標の幾何割当がない','全照会':qs,'全因子':factors,'実行許可':False}
 minimum=min(x['最小作用数'] for x in planspec);allpaths=[]
 for spec in planspec:
  if spec['最小作用数']!=minimum:continue
  choices=[paths(i,spec['目標中心'][i]) for i in spec['対象処理順']]
  for ps in itertools.product(*choices):
   actionpath=[];actor=selected
   for i,path in zip(spec['対象処理順'],ps):
    if actor!=i:actionpath.append(5);actor=i
    actionpath+=path
   allpaths.append(actionpath)
 # 全最短候補の全分岐状態と、その全5候補を再観測する。枝を距離で削らない。
 start=(tuple(o['中心'] for o in os),selected);states={start};pathstates=[]
 def apply(state,act):
  poses,actor=state
  if act==5:return (poses,1-actor)
  dx,dy=deltas[act];out=list(poses);out[actor]=(out[actor][0]+dx,out[actor][1]+dy)
  return (tuple(out),actor) if 0<=out[actor][0]<64 and 0<=out[actor][1]<63 else None
 for path in allpaths:
  state=start;ids=[state]
  for act in path:state=apply(state,act);assert state is not None;states.add(state);ids.append(state)
  pathstates.append(ids)
 cache={}
 def observe(state):
  if state in cache:return cache[state]
  poses,actor=state;objects=[{**obj,'中心':pos,'点':e.形の点(obj,pos),'選択':i==actor} for i,(obj,pos) in enumerate(zip(os,poses))];render=p.描画(init,objects,order)+[list(frame[63])];choices=e.現在全分解(render,init)
  def canonical(objs):return sorted((o['色'],tuple(o['中心']),o['選択']) for o in objs)
  overlap=any(tuple(t['中心'])==poses[actor] for t in init['標識']);ok=len(choices)==1 and canonical(choices[0])==canonical(objects) and not overlap;cache[state]={'中心群':poses,'選択索引':actor,'全分解':choices,'観測対応一致':ok,'選択中心標識重合':overlap};return cache[state]
 audits=[]
 for state in sorted(states):
  current=observe(state);actions=[]
  for act in list(deltas)+[5]:
   nxt=apply(state,act);check=observe(nxt) if nxt is not None else None;ok=current['観測対応一致'] and check is not None and check['観測対応一致']
   actions.append({'作用':act,'状態':'条件付き支持' if ok else '保留','次中心選択':nxt,'次観測対応一致':check['観測対応一致'] if check else False})
  audits.append({'状態':state,'現観測対応':current,'全五候補':actions})
 supported=[all(observe(s)['観測対応一致'] for s in path) for path in pathstates]
 # tuple-key dictionaries are encoded as full ordered lists, not dropped JSON keys.
 for factor in factors:
  factor['距離']=[{'中心':pos,'最小作用数':d} for pos,d in factor['距離'].items()];factor['全最短親']=[{'中心':pos,'全親':p} for pos,p in factor['全最短親'].items()]
 return {'状態':'条件付き最短候補あり' if any(supported) else '保留','初期知覚':init,'全HDS照会':qs,'全因子':factors,'因子積の全状態数':2*math.prod(len(x['全可達中心']) for x in factors),'因子積の境界':'全中心組合せ×選択2値。合成規則の全候補を保持するが、全組合せの画像可識別性は未検査。実行採用ではない。','全目標と処理順候補':planspec,'最小作用数':minimum,'全体最短全経路':allpaths,'各最短経路の観測整合':supported,'全最短分岐状態の全五候補':audits,'全再観測状態':list(cache.values()),'最短下限の証明':'各対象の四近傍最短距離の和と必要な選択交替数。合成モデルでは線位置の相互作用なし。全目標割当/対象順を比較し全最短親を展開。','一般因果閉包':False,'新規環境成功':False,'実行許可':False}
