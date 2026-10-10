"""現在画素と注入HDSから、限定作用の全到達集合を返す。"""
import collections
from .画素 import perception,parse,components
from ..ARC3境界 import _盤面列,_作用番号
from .照会 import ask,GOAL,ACTION
from .直線 import observe as lines
from .単純閉路 import observe as loops,shift
LINE_BOUND='公開画素・適合直線列の相対巡回と実測次色'
LOOP_BOUND='公開画素・単一閉路の標識方向と巡回実測'
def checked_scene(frame,available):
 normalized=_盤面列([frame])
 if len(normalized)!=1 or len(normalized[0])!=64 or any(len(r)!=64 for r in normalized[0]):raise ValueError('固定知覚は64×64のみ')
 frame=[list(r) for r in normalized[0]]
 if not isinstance(available,(list,tuple)):raise ValueError('利用可能作用が欠落または不正')
 acts=tuple(_作用番号(v) for v in available)
 if len(acts)!=len(set(acts)) or 6 not in acts:raise ValueError('利用可能なクリック作用が一意にない')
 parsed=parse(frame);p=perception(frame)
 if not parsed['標識群'] or not p['トークン'] or not p['操作標識']:raise ValueError('目標標識・対象・操作標識のいずれかが空')
 covered=set()
 for o in p['トークン']:
  x,y,r,b=o['範囲'];covered.update((u,v) for u in range(x,r+1) for v in range(y,b+1))
 for o in p['操作標識']:
  x,y,r,b=o['範囲'];w,h=r-x+1,b-y+1
  masks=[('011','111','111','011'),('110','111','111','110'),('0110','1111','1111'),('1111','1111','0110')]
  matches=[]
  for mask in masks:
   if w%len(mask[0]) or h%len(mask):continue
   d=w//len(mask[0])
   if d!=h//len(mask):continue
   if all(frame[y+v][x+u]==(o['色'] if mask[v//d][u//d]=='1' else 4) for v in range(h) for u in range(w)):
    matches.append({(x+u,y+v) for v in range(h) for u in range(w) if mask[v//d][u//d]=='1'})
  if len(matches)!=1:raise ValueError('操作標識の実画素形状が固定マスクと一致しない')
  covered.update(matches[0])
 for m in parsed['標識群']:
  x,y,_,_=m['範囲'];d=m['寸法']
  for dx,dy in [(0,0),(3*d,0),(0,3*d),(3*d,3*d)]:covered.update((x+dx+u,y+dy+v) for u in range(d) for v in range(d))
 background=[(x,y) for y in range(3,64) for x in range(1,64) if frame[y][x]==4]
 if not background:raise ValueError('盤面背景が空')
 xs,ys=zip(*background);left,right,top,bottom=min(xs),max(xs),min(ys),max(ys)
 for y in range(3,64):
  for x in range(1,64):
   inside=left<=x<=right and top<=y<=bottom
   if (x,y) in covered:
    if not inside:raise ValueError('知覚対象が盤面背景矩形外')
   elif frame[y][x]!=(4 if inside else 3):raise ValueError('役割未説明の画素または背景矩形内の穴')
 return frame,p,parsed

def models(frame,h):
 p=perception(frame);out=[];held=[]
 try:gs=lines(frame)
 except Exception as e:gs=[];held.append({'種類':'直線知覚','例外':type(e).__name__,'理由':str(e)})
 for g in gs:
  if not g['固定知覚適合']:
   held.append({'種類':'直線','標識':g['操作標識'],'固定文法候補':g,'理由':g['保留理由']});continue
  seq=g['列位置番号'];ar=g['操作標識'];candidates=[];decisions=[]
  for k in range(len(seq)):
   q=ask(h,LINE_BOUND,'候補は矢印向き一位置巡回',k==1,'全トークン予測色一致');decisions.append({'相対変位':k,'HDS判定':q})
   if q['採用']:candidates.append(k)
  if any(d['HDS判定']['判定'] in ('HOLD','例外') for d in decisions) or len(candidates)!=1:held.append({'標識':ar,'理由':'相対変位のHDS採否が非一意または未支持','全変位候補判定':decisions});continue
  out.append({'種類':'直線','位置列':seq,'符号':sum(g['向き']),'変位':candidates[0],'標識':ar,'全変位候補判定':decisions})
 try:g=loops(frame)
 except Exception as e:g={'適合':False,'例外':type(e).__name__,'理由':str(e)}
 if not g['適合']:held.append({'種類':'単純閉路','固定文法候補':g,'理由':g.get('理由')})
 else:
  for ctrl in g['操作群']:
   seq=g['時計順位置番号'];candidates=[];decisions=[]
   for k in range(len(seq)):
    q=ask(h,LOOP_BOUND,'候補は標識向き一位置巡回',k==1,'全トークン予測色一致');decisions.append({'相対変位':k,'HDS判定':q})
    if q['採用']:candidates.append(k)
   if any(d['HDS判定']['判定'] in ('HOLD','例外') for d in decisions) or len(candidates)!=1:held.append({'標識':ctrl['操作標識'],'理由':'閉路変位のHDS採否が非一意または未支持','全変位候補判定':decisions});continue
   out.append({'種類':'単一閉路','位置列':seq,'符号':ctrl['時計方向係数'],'変位':candidates[0],'標識':ctrl['操作標識'],'全変位候補判定':decisions})
 known={tuple(m['標識']['範囲']) for m in out}
 held.extend({'標識':ar,'理由':'具体的な経路/移動先が未同定'} for ar in p['操作標識'] if tuple(ar['範囲']) not in known)
 return out,held

def domain_size(initial,ms):
 supports={}
 for m in ms:
  seq=tuple(m['位置列']);support=frozenset(seq)
  if m['変位']!=1:return None,'一位置巡回以外の全到達数は未検証'
  if support in supports and supports[support]!=seq:return None,'同じ対象群の異なる巡回順序は未検証'
  supports[support]=seq
 keys=list(supports)
 if any(a & b for i,a in enumerate(keys) for b in keys[i+1:]):return None,'異なる巡回列の重なりは未学習の作用合成境界。候補を削って探索しない'
 total=1
 for seq in supports.values():
  colors=[initial[i] for i in seq]
  period=next(k for k in range(1,len(seq)+1) if all(colors[i]==colors[(i+k)%len(seq)] for i in range(len(seq))))
  total*=period
 return total,None

def unevaluated_actions(available):
 if not isinstance(available,(list,tuple)):return [{'原入力':available,'採否':'HOLD','理由':'利用可能作用の配列が欠落または不正'}]
 out=[]
 for v in available:
  try:n=_作用番号(v)
  except Exception as e:out.append({'原入力':v,'採否':'HOLD','理由':str(e)});continue
  if n!=6:out.append({'作用番号':n,'採否':'HOLD','理由':'この語彙では未評価の作用番号'})
 return out

def _plan(frame,h,available,progress):
 frame,p,parsed=checked_scene(frame,available);marks=parsed['標識群'];progress['段階']='前提照会'
 goal=ask(h,GOAL,'全標識色一致',True,'完了カウンタ更新');action=ask(h,ACTION,'操作標識矩形内',True,'トークン色移動');progress['前提判定']={'目標':goal,'作用':action}
 ms,held=models(frame,h);progress['作用モデル群']=ms;progress['未同定作用群']=held
 if not goal['採用'] or not action['採用']:return finish(progress,'HOLD','目標または旧作用がHDS未支持/保留')
 targets=[]
 for m in marks:
  x,y,_,_=m['範囲'];s=m['寸法'];matches=[i for i,t in enumerate(p['トークン']) if t['範囲']==[x+s,y+s,x+3*s-1,y+3*s-1]]
  if len(matches)!=1:progress['未解決目標'].append({'標識':m,'対応候補':matches})
  else:targets.append((matches[0],m['標識色']))
 progress['目標']=targets
 if progress['未解決目標']:return finish(progress,'HOLD','標識の対象対応が非一意')
 initial=tuple(t['色'] for t in p['トークン']);progress['全状態'].append({'番号':0,'トークン色':list(initial),'最短距離':0,'全最短親':[]});progress['未展開状態']=[0];progress['観測目標充足']=all(initial[i]==c for i,c in targets)
 bound,reason=domain_size(initial,ms);progress['全到達状態数算定']=bound
 if reason or bound>progress['検証状態上限']:return finish(progress,'HOLD',reason or '独立巡回の全到達集合が外部指定の検証資源境界を超える。学習した不可能条件ではない')
 progress['段階']='全到達探索';queue=collections.deque([initial]);index={initial:0};nodes=progress['全状態'];edges=progress['全作用辺'];goals=progress['全目標状態'];failed=progress['未評価作用辺']
 while queue:
  state=queue.popleft();si=index[state];progress['展開中状態']=si;progress['未展開状態']=[index[x] for x in queue]
  if all(state[i]==c for i,c in targets):goals.append(si)
  for mi,m in enumerate(ms):
   try:
    nxt=tuple(shift(list(state),m['位置列'],m['符号'],m['変位']))
    if len(nxt)!=len(state):raise ValueError('作用後対象数が変化')
   except Exception as e:failed.append({'始点':si,'作用番号':mi,'例外':type(e).__name__,'理由':str(e)});continue
   if nxt not in index:
    index[nxt]=len(nodes);nodes.append({'番号':index[nxt],'トークン色':list(nxt),'最短距離':nodes[si]['最短距離']+1,'全最短親':[]});queue.append(nxt)
   ni=index[nxt];edges.append({'始点':si,'作用番号':mi,'終点':ni})
   if nodes[ni]['最短距離']==nodes[si]['最短距離']+1:nodes[ni]['全最短親'].append({'親':si,'作用番号':mi})
  progress['未展開状態']=[index[x] for x in queue];progress['展開中状態']=None
 progress['最短目標距離']=min((nodes[i]['最短距離'] for i in goals),default=None);progress['網羅性']='未完了' if failed else '学習済み限定作用内の全到達集合';progress['段階']='探索終了'
 if failed:return finish(progress,'HOLD','作用評価例外があり全体の到達/最短性は未確認。部分グラフを保持')
 state='観測目標充足' if progress['観測目標充足'] else '条件付き計画' if goals else 'HOLD'
 return finish(progress,state,'学習済み作用内の全到達集合。未同定/未評価作用を含めた解閉包ではない')

def finish(progress,state,reason):
 return {'状態':state,'理由':reason,'探索状態数':len(progress['全状態']),'全遷移計画':progress,'作用モデル群':progress['作用モデル群'],'未同定作用':progress['未同定作用群'],'未評価作用候補群':progress['未評価作用候補群'],'全到達状態数算定':progress.get('全到達状態数算定'),'観測目標充足':progress['観測目標充足'],'公式完了確認':False,'実行許可':False}

def plan(frame,h,available=(6,),*,state_limit=100):
 progress={'検証状態上限':state_limit,'資源境界の由来':'既定100は公開小対照で検証した計算上限。自然法則や不可能性の学習結果ではない','段階':'入力検証','全状態':[],'全作用辺':[],'全目標状態':[],'最短目標距離':None,'全到達状態数算定':None,'未展開状態':[],'展開中状態':None,'未評価作用辺':[],'作用モデル群':[],'未同定作用群':[],'未評価作用候補群':unevaluated_actions(available),'目標':[],'未解決目標':[],'網羅性':'未着手','観測目標充足':False,'公式完了確認':False}
 try:
  if type(state_limit) is not int or state_limit<1:raise ValueError('検証状態上限は正の整数が必要')
  return _plan(frame,h,available,progress)
 except Exception as e:
  progress['例外']={'型':type(e).__name__,'理由':str(e)};progress['網羅性']='未完了'
  return finish(progress,'HOLD','入力/知覚/照会/探索の例外。処理済み候補とfrontierを保持')
