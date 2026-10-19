"""Pure existing-overwrite composition. All graph edges kept; no runtime API."""
import collections,json,heapq
class Hold(ValueError):pass
def sig(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def quotient(initial,goal,directions,membership):
 groups={}
 for y in range(len(initial)):
  for x in range(len(initial[y])):
   bits=tuple(membership(d,x,y,len(initial),'広域塗布')for d in directions)
   if any(type(b)is not bool for b in bits):raise Hold('untyped membership')
   # Refine by before/goal values: never merge observably different cells.
   groups.setdefault((bits,initial[y][x],goal[y][x]),[]).append([x,y])
 atoms=[{'signature':list(k[0]),'initial':k[1],'goal':k[2],'cells':v}for k,v in groups.items()]
 return atoms

def obligations(atoms,operations,max_edges=12288):
 start=(1<<len(atoms))-1;todo=collections.deque([start]);seen={start};edges=[]
 while todo:
  rem=todo.popleft()
  for i,op in enumerate(operations):
   overlap=rem&op['mask'];bad=[j for j,a in enumerate(atoms)if overlap>>j&1 and a['goal']!=op['color']];nxt=rem&~op['mask']
   edges.append({'required_after':rem,'operation':i,'required_before':None if bad else nxt,'contradictions':bad,'self_loop':not bad and nxt==rem})
   if not bad and nxt not in seen:seen.add(nxt);todo.append(nxt)
   if len(edges)>=max_edges and(todo or i+1<len(operations)):
    return {'status':'HOLD_RESOURCE','states':sorted(seen),'all_edges':edges,'finite_bound':1<<len(atoms),'frontier':list(todo),'interrupted_state':rem,'next_operation':i+1}
 return {'status':'COMPLETE','states':sorted(seen),'all_edges':edges,'finite_bound':1<<len(atoms)}

def full_closure(atoms,operations,start_tool,start_direction,effect,prepare,max_states=512,max_edges=12288):
 """Exact all-edge closure; explicit resource frontier causes global HOLD, never pruning."""
 start=(tuple(a['initial']for a in atoms),start_tool,tuple(start_direction));states=[start];index={start:0};edges=[];queue=collections.deque([0]);failure=None
 while queue and failure is None:
  source=queue.popleft();canvas,tool,direction=states[source]
  for oid,op in enumerate(operations):
   if len(edges)>=max_edges:
    failure='explicit complete-edge retention resource budget';break
   row={'source':source,'operation':oid,'target':None,'status':'HOLD'}
   try:
    preparation=prepare(tool,direction,op['color'],op['direction'])
    result,evidence=effect(canvas,op,atoms)
    target=(tuple(result),op['color'],tuple(op['direction']))
    if target not in index:
     if len(states)>=max_states:raise MemoryError('explicit graph retention resource budget')
     index[target]=len(states);states.append(target);queue.append(index[target])
    row.update(target=index[target],status='CONDITIONAL_SUPPORTED',preparation=preparation,effect=evidence,self_loop=index[target]==source)
   except Hold as e:row['reason']=str(e)
   except MemoryError as e:row['reason']=str(e);failure=str(e)
   edges.append(row)
   if failure:break
 goal=tuple(a['goal']for a in atoms);goals=[i for i,s in enumerate(states)if s[0]==goal]
 reverse=collections.defaultdict(list)
 for i,e in enumerate(edges):
  if e['target']is not None:reverse[e['target']].append((e['source'],i))
 distance={g:0 for g in goals};todo=collections.deque(goals)
 while todo:
  at=todo.popleft()
  for previous,edge in reverse[at]:
   if previous not in distance:distance[previous]=distance[at]+1;todo.append(previous)
 # Exact positive external-operation cost: learned TURN distance + qualified COPY + paint.
 cost={g:0 for g in goals};heap=[(0,g)for g in goals];heapq.heapify(heap)
 while heap:
  current,at=heapq.heappop(heap)
  if cost[at]!=current:continue
  for previous,eid in reverse[at]:
   prep=edges[eid]['preparation'];weight=1+prep['turn_distance']+int(prep['copy_required']);candidate=current+weight
   if previous not in cost or candidate<cost[previous]:cost[previous]=candidate;heapq.heappush(heap,(candidate,previous))
 optimal_first=[i for i,e in enumerate(edges)if e['source']==0 and e['target']in cost and 1+e['preparation']['turn_distance']+int(e['preparation']['copy_required'])+cost[e['target']]==cost.get(0)]
 witnesses={}
 # One finite witness per supporting first edge; all graph alternatives remain in ledger.
 for eid,e in enumerate(edges):
  if e['source']!=0 or e['target']not in distance:continue
  path=[eid];at=e['target']
  while cost[at]:
   candidates=[(j,x)for j,x in enumerate(edges)if x['source']==at and x['target']in distance and cost[x['target']]+1+x['preparation']['turn_distance']+int(x['preparation']['copy_required'])==cost[at]]
   j,x=candidates[0];path.append(j);at=x['target']
  witnesses[str(eid)]=path
 if failure:witnesses={}
 return {'status':'COMPLETE_CONDITIONAL_CLOSURE'if failure is None else 'HOLD_RESOURCE','failure':failure,'states':[{'canvas':list(c),'tool':t,'direction':list(d)}for c,t,d in states],'all_edges':edges,'goal_states':goals,'remaining_macro_distance':{str(k):v for k,v in distance.items()},'complete_witnesses_by_first_edge':witnesses,'remaining_external_cost':{str(k):v for k,v in cost.items()},'cost_reducing_first_edges':optimal_first if failure is None else [],'unexpanded_frontier':list(queue),'interrupted_source':source if failure else None,'next_operation':oid if failure else None,'all_operations_per_expanded_state':len(operations),'execution_permission':False}
