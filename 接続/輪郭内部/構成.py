"""全割当×全処理順。全入口・出口・未展開前線・全作用辺を因子化して保持。"""
import base64,itertools,collections

def index(s,target):
 p,face,rings,held=s;return (((p[0]+16*p[1])*4+face-1)*240+rings[target][0]+16*rings[target][1])*2+int(held>=0)
def bitmap(states,target):
 bits=bytearray(57600)
 for s in states:
  n=index(s,target);bits[n//8]|=1<<(n%8)
 return base64.b64encode(bits).decode('ascii')
def transition(m,s,a,target):
 if m.goal(s):return None,'旧問題達成後HOLD',None
 nxt,status,key=m.next(s,a)
 if nxt is not None and(nxt[3]not in(-1,target)or any(nxt[2][i]!=s[2][i]for i in range(len(s[2]))if i!=target)):
  return None,'構成範囲外:他対象作用。全作用候補を不可能としない',key
 return nxt,status,key

def stage(m,entries,target,dest,limit=None):
 states=list(entries);ids={s:i for i,s in enumerate(states)};parents=[None]*len(states);rev=[[]for _ in states];exits=[];counts=collections.Counter();cursor=0
 failure=None
 try:
  while cursor<len(states)and(limit is None or cursor<limit):
   s=states[cursor]
   if s[2][target]==dest and s[3]<0:exits.append(cursor)
   for a in range(1,6):
    nxt,status,key=transition(m,s,a,target);counts[status]+=1
    if nxt is not None:
     if nxt not in ids:ids[nxt]=len(states);states.append(nxt);parents.append((cursor,a));rev.append([])
     rev[ids[nxt]].append(cursor)
   cursor+=1
 except Exception as e:failure=type(e).__name__+':'+str(e)
 win=set(exits);work=list(exits)
 for dst in work:
  for src in rev[dst]:
   if src not in win:win.add(src);work.append(src)
 proofs={}
 for end in exits:
  cur=end;actions=[]
  while parents[cur]is not None:
   p,a=parents[cur];actions.append(a);cur=p
  proofs[states[end]]=(states[cur],list(reversed(actions)))
 first=[]
 if len(entries)==1 and entries[0]==m.start:
  for a in range(1,6):
   try:
    nxt,status,key=transition(m,m.start,a,target);first.append({'作用':a,'状態':'条件付き後続経路あり' if nxt in ids and ids[nxt]in win else 'HOLD','局所採否':status})
   except Exception as e:
    detail=type(e).__name__+':'+str(e)
    if failure is None:failure=detail
    first.append({'作用':a,'状態':'HOLD','局所採否':'初回作用照会例外','例外':detail})
 out={'例外':failure,'途中評価辺数':sum(counts.values())-cursor*5,'対象':target,'配置先':dest,'基準小枠位置群':entries[0][2]if entries else [],'状態数':len(states),'処理状態数':cursor,'全辺数':cursor*5,'全状態集合':bitmap(states,target),'未展開前線集合':bitmap(states[cursor:],target),'未展開前線数':len(states)-cursor,'全入口':entries,'全出口':[states[i]for i in exits],'出口到達支持状態集合':bitmap((states[i]for i in win),target),'出口未支持入口':[s for s in entries if ids[s]not in win],'全辺採否':dict(counts),'初回作用全候補':first,'探索完了':failure is None and cursor==len(states),'辺定義':'全処理済み状態×作用1..5へtransitionを適用。戻り辺/HOLD/範囲外辺も含む。未展開状態の辺は未評価。','集合形式':'base64ビット集合。番号=(((操作体x+16y)*4+向き-1)*240+対象枠x+16y)*2+保持bit。非対象は基準小枠位置で固定。','固定前提':'非対象保存、描画、空間同一化、非終端・予算許容。実環境hidden同一性は未確認。'}
 return [states[i]for i in exits],out,proofs

def compose(m,limit=None):
 if len(m.start[2])!=3 or len(m.slots)!=3:raise ValueError('3枠3目標位置の静的構成のみ支持')
 cache={};results=[];witnesses=[]
 for assignment in itertools.permutations(m.slots):
  for order in itertools.permutations(range(3)):
   entries=[m.start];prefix=[];refs=[];complete=True
   for target in order:
    prefix.append((target,assignment[target]));key=tuple(prefix)
    if key not in cache:cache[key]=stage(m,entries,target,assignment[target],limit)
    outputs,q,proofs=cache[key];refs.append(key);entries=outputs
    if not q['探索完了']:complete=False;break
    if not entries:break
   supported=m.gq['値']=={'進捗応答':True}and bool(entries)and len(refs)==3 and complete and all(not cache[k][1]['出口未支持入口']for k in refs)
   row={'割当':assignment,'順序':order,'状態':'条件付き支持'if supported else'HOLD','段階参照':refs,'未展開後続段階':order[len(refs):],'最終出口数':len(entries),'初回作用全候補':cache[refs[0]][1]['初回作用全候補']};results.append(row)
   if supported:
    for end in entries:
     current=end;parts=[]
     for key in reversed(refs):current,part=cache[key][2][current];parts.append(part)
     assert current==m.start
     witnesses.append({'割当':assignment,'順序':order,'終点':end,'作用列':[a for part in reversed(parts)for a in part]})
 return {'全36構成候補':results,'全段階':[{'参照':k,**v[1]}for k,v in cache.items()],'全出口証人':witnesses,'固定証人提示順':'全支持候補を保持した上で作用番号順BFSの親を提示。HDSが学んだ選好ではない。','実行許可':False}
