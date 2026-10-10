import json,itertools,collections,math
from . import 知覚 as p,規則 as f
def 方向入力(a):return {'前状態作用直積':json.dumps({'作用番号':a,'前方中心は画面内':True},ensure_ascii=False,sort_keys=True,separators=(',',':'))}

def 構成(frame,h):
 raw=p.全分解(frame);qs=[]
 def ask(k,v):
  q=f.照会(h,k,v);qs.append(q);return q['値']
 if not raw['候補']:return {'状態':'保留','理由':'固定知覚候補なし','全初期候補':raw}
 accepted=[];decisions=[]
 for c in raw['候補']:
  votes=[ask('中心構造',{'図形種類':o['種類'].replace('中心欠け','')}) for o in c['図形']];ok=all(v is not None and v==((0,0) in o['形']) for o,v in zip(c['図形'],votes));decisions.append({'候補':c,'中心構造支持':votes,'採用':ok})
  if ok:accepted.append(c)
 if len(accepted)!=1:return {'状態':'保留','理由':'中心構造のHDS支持後も非一意','全初期候補採否':decisions,'全照会':qs}
 os=accepted[0]['図形'];init={'標識':raw['標識'],'図形':os};colors=[o['色'] for o in os]
 goal=[ask('目標',{'全標識の同色線被覆':v}) for v in [False,True]];keep=[ask('保存',{'作用関係':v}) for v in ['方向作用','選択作用']];moves={a:ask('方向',方向入力(a))for a in p.e.方向};sw={(i,j):ask('三図形選択',{'現在選択色と候補色':json.dumps([a,b],separators=(',',':'))}) for i,a in enumerate(colors)for j,b in enumerate(colors)};depth={(i,j):ask('描画',{'候補色と相手色':json.dumps([a,b])})for i,a in enumerate(colors)for j,b in enumerate(colors)if i!=j}
 if goal!=[False,True] or keep!=[True,True] or any(v is None for v in list(moves.values())+list(sw.values())+list(depth.values())):return {'状態':'保留','理由':'構成要素の支持不足','全照会':qs,'全初期候補採否':decisions}
 nxtsel={i:[j for j in range(3)if sw[i,j]]for i in range(3)}
 orders=[o for o in itertools.permutations(range(3))if all((o.index(i)>o.index(j))==v for (i,j),v in depth.items())]
 if len(orders)!=1 or any(len(v)!=1 for v in nxtsel.values()):return {'状態':'保留','理由':'全選択又は描画順序非一意','全照会':qs}
 nxtsel={i:v[0]for i,v in nxtsel.items()};order=orders[0];selected=next(i for i,o in enumerate(os)if o['選択']);visit=[selected]
 for _ in range(2):visit.append(nxtsel[visit[-1]])
 if len(set(visit))!=3 or nxtsel[visit[-1]]!=selected:return {'状態':'保留','理由':'三図形一巡が成立しない','全照会':qs}
 deltas={a:tuple(map(int,v.split(',')))for a,v in moves.items()}
 if set(deltas.values())!={(0,-3),(0,3),(-3,0),(3,0)}:return {'状態':'保留','理由':'固定並進文法外','全照会':qs}
 factors=[]
 for o in os:
  targets=[t for t in init['標識']if t['色']==o['色']];positions={tuple(o['中心']):0};q=collections.deque(positions);edges=[];parents=collections.defaultdict(list)
  while q:
   pos=q.popleft();out=[]
   for a,(dx,dy)in deltas.items():
    nxt=(pos[0]+dx,pos[1]+dy);valid=0<=nxt[0]<64 and 0<=nxt[1]<63
    if valid:
     if nxt not in positions:positions[nxt]=positions[pos]+1;q.append(nxt)
     if positions[nxt]==positions[pos]+1:parents[nxt].append((pos,a))
    out.append({'作用':a,'次中心':nxt,'状態':'抽象候補'if valid else'保留'})
   edges.append({'中心':pos,'全四方向':out})
  allpos=[];goals=[]
  for y in range(64):
   for x in range(64):
    pos=(x,y);covered=bool(targets)and all(tuple(t['中心'])in p.点群(o['形'],pos)for t in targets);allpos.append({'中心':pos,'同色標識被覆':covered,'到達格子内':pos in positions})
    if covered and pos in positions:goals.append(pos)
  factors.append({'色':o['色'],'全中心候補4096':allpos,'全可達中心':list(positions),'距離':positions,'全四方向候補':edges,'全最短親':parents,'全目標中心':goals})
 specs=[]
 for ends in itertools.product(*(g['全目標中心']for g in factors)):
  needed=[i for i,pos in enumerate(ends)if pos!=tuple(os[i]['中心'])];switches=max((visit.index(i)for i in needed),default=0);length=sum(factors[i]['距離'][pos]for i,pos in enumerate(ends))+switches;specs.append({'目標中心':ends,'選択巡回':visit[:switches+1],'選択回数':switches,'最短操作数':length})
 if not specs:return {'状態':'保留','理由':'幾何目標なし','全照会':qs,'全因子':factors}
 minimum=min(s['最短操作数']for s in specs);start=(tuple(tuple(o['中心'])for o in os),selected);dag=collections.defaultdict(set);endsset=set()
 for spec in specs:
  if spec['最短操作数']!=minimum:continue
  state=start
  for block,i in enumerate(spec['選択巡回']):
   target=spec['目標中心'][i];stack=[target];seen=set()
   while stack:
    pos=stack.pop()
    if pos in seen:continue
    seen.add(pos)
    for before,a in factors[i]['全最短親'].get(pos,[]):
     stack.append(before);poses=list(state[0]);poses[i]=before;beforestate=(tuple(poses),i);poses=list(state[0]);poses[i]=pos;afterstate=(tuple(poses),i);dag[beforestate].add((a,afterstate))
   poses=list(state[0]);poses[i]=target;state=(tuple(poses),i)
   if block<len(spec['選択巡回'])-1:
    after=(state[0],nxtsel[i]);dag[state].add((5,after));state=after
  endsset.add(state)
 states=set(dag)|{s for outs in dag.values()for a,s in outs}|endsset;cache={}
 def apply(state,a):
  poses,i=state
  if a==5:return poses,nxtsel[i]
  dx,dy=deltas[a];v=list(poses);v[i]=(v[i][0]+dx,v[i][1]+dy)
  return (tuple(v),i)if 0<=v[i][0]<64 and 0<=v[i][1]<63 else None
 def observe(s):
  if s in cache:return cache[s]
  poses,i=s;objs=[{**o,'中心':pos,'点':p.点群(o['形'],pos),'選択':j==i}for j,(o,pos)in enumerate(zip(os,poses))];render=p.描画(init,objs,order)+[frame[63]];parsed=p.全分解(render,init)
  def canonical(v):return [(o['色'],tuple(o['中心']),o['選択'],o['種類'])for o in v]
  overlap=any(tuple(t['中心'])==poses[i] for t in init['標識']);ok=len(parsed['候補'])==1 and canonical(parsed['候補'][0]['図形'])==canonical(objs) and not overlap;cache[s]={'状態':s,'全分解':parsed,'観測対応一致':ok,'選択中心標識重合':overlap,'保留理由':'中心標識重合時の黒点可視性が未支持' if overlap else None};return cache[s]
 audits=[]
 for s in sorted(states):
  current=observe(s);acts=[]
  for a in [1,2,3,4,5]:
   nxt=apply(s,a);obs=observe(nxt)if nxt is not None else None;acts.append({'作用':a,'次状態':nxt,'状態':'条件付き支持'if current['観測対応一致']and obs and obs['観測対応一致']else'保留','最短親辺':(a,nxt)in dag[s]})
  audits.append({'状態':s,'全五候補':acts})
 memo={}
 def count(s):
  if s in memo:return memo[s]
  memo[s]=int(s in endsset)+sum(count(n)for a,n in dag[s]);return memo[s]
 total=count(start);supportedmemo={}
 def supportedcount(s):
  if s in supportedmemo:return supportedmemo[s]
  if not observe(s)['観測対応一致']:supportedmemo[s]=0;return 0
  supportedmemo[s]=int(s in endsset)+sum(supportedcount(n)for a,n in dag[s]);return supportedmemo[s]
 supported=supportedcount(start);held=sum(a['最短親辺']and a['状態']=='保留'for s in audits for a in s['全五候補'])
 for factor in factors:
  factor['距離']=[{'中心':pos,'距離':d}for pos,d in factor['距離'].items()];factor['全最短親']=[{'中心':pos,'親':v}for pos,v in factor['全最短親'].items()]
 return {'状態':'条件付き最短候補あり'if supported else'保留','全初期候補採否':decisions,'初期':init,'全照会':qs,'全因子':factors,'全目標候補':specs,'最短操作数':minimum,'全最短経路数':total,'観測条件付き支持経路数':supported,'観測保留経路数':total-supported,'全最短DAG':[{'状態':s,'全最短辺':[{'作用':a,'次状態':n}for a,n in sorted(dag[s])]}for s in sorted(states)],'全最短分岐全五候補':audits,'全再観測':list(cache.values()),'最短辺保留':held,'抽象因子積状態数':3*math.prod(len(g['全可達中心'])for g in factors),'全因子積画像検証':False,'下限根拠':'各図形の格子最短距離和と、HDS支持選択一巡で必要図形を訪問する最小回数。最短時は再訪問なし。全目標直積と全最短親DAGを保持。','新規環境成功':False,'実行許可':False}
