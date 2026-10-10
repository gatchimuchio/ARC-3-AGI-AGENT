"""公開列図式のID非依存runtime。教師/録画/解答/環境stepを読まない。
固定知覚・列操作・全割当探索と、注入された同一HDSの対応学習を区別する。
"""
from collections import Counter
from copy import deepcopy
import itertools
from hds学習系統 import 外部入力
from .図式観測 import 成分群
from .ARC3境界 import 観測

役割境界='公開列図式:記号外形と展開役割'
目標境界='公開列図式:有限全列または生産的反復の目標長一致と提出受理'
作用境界='公開列図式:観測された解答作業と行動ID'
構造境界='公開列図式:枠付き順序スロット・在庫記号・目標列'
class 知覚不適用(ValueError):
    pass

適用前提=['4画素記号・6画素枠間隔・10画素容器の固定知覚仮説',
          '同色容器参照・標識付き起点・行順目標列の固定仮説',
          '有限全列/生産的反復前置列という固定操作語彙',
          'HDSが記号役割・受理関係・作業行動IDを支持しHOLDしない']
def 記号を読む(f,x,y,bg):
 a=[r[x:x+4] for r in f[y:y+4]]
 if len(a)!=4 or any(len(r)!=4 for r in a):raise ValueError('記号寸法不成立')
 flat=[v for r in a for v in r];rim=[a[dy][dx] for dy in range(4) for dx in range(4) if dy in (0,3) or dx in (0,3)];center=[a[dy][dx] for dy in (1,2) for dx in (1,2)]
 if len(set(flat))==1 and flat[0]!=bg:return {'色':flat[0],'中空':False}
 if len(set(rim))==1 and rim[0]!=bg and set(center)=={bg}:return {'色':rim[0],'中空':True}
 if set(rim)=={bg} and len(set(center))==1:return None
 raise ValueError('記号文法不成立')

def 容器外形を観測する(frame,bg):
 h=len(frame);w=len(frame[0])
 boxes=[]
 for y in range(h-9):
  x=0
  while x<w:
   c=frame[y][x];end=x+1
   while end<w and frame[y][end]==c:end+=1
   n=end-x
   if c!=bg and n>=16 and (n-4)%6==0 and all(frame[yy][x]==c and frame[yy][end-1]==c for yy in range(y,y+10)):
    brackets=[frame[y-1][x-1] if x and y else bg,frame[y-1][end] if end<w and y else bg,frame[y+10][x-1] if x and y+10<h else bg,frame[y+10][end] if end<w and y+10<h else bg]
    selected=len(set(brackets))==1 and brackets[0] not in (bg,c)
    slots=[]
    for j in range((n-4)//6):
     xx=x+3+6*j;yy=y+3
     slots.append({'位置':[xx,yy],'記号':None})
    boxes.append({'色':c,'位置':[x,y],'起点':selected,'枠群':slots})
   x=end
 return boxes

def 図式を観測する(frame):
 if not frame or not frame[0] or any(len(r)!=len(frame[0]) for r in frame):raise ValueError('空または非矩形盤面')
 h=len(frame);w=len(frame[0]);counts=Counter(v for r in frame for v in r).most_common()
 if len(counts)>1 and counts[0][1]==counts[1][1]:raise ValueError('背景候補同数で未確定')
 bg=counts[0][0]
 boxes=容器外形を観測する(frame,bg)
 if not boxes:raise 知覚不適用('固定文法の枠付き容器が観測できない')
 if not any(b['起点'] for b in boxes):raise 知覚不適用('固定文法に必須の四隅標識付き起点が存在しない')
 for b in boxes:
  for slot in b['枠群']:
   slot['記号']=記号を読む(frame,*slot['位置'],bg)
 if sum(b['起点'] for b in boxes)!=1:raise ValueError('標識付き起点/容器を一意に確認できない')
 if len({b['色'] for b in boxes})!=len(boxes):raise ValueError('同色容器の参照先が複数')
 top=min(b['位置'][1] for b in boxes);bottom=max(b['位置'][1]+10 for b in boxes)
 target=[]
 for y in range(top-5):
  for x in range(w-5):
   c=frame[y][x]
   if c==bg:continue
   rim=[frame[y+dy][x+dx] for dy in range(6) for dx in range(6) if dy in (0,5) or dx in (0,5)]
   inside={frame[y+dy][x+dx] for dy in range(1,5) for dx in range(1,5)}
   if len(set(rim))==1 and len(inside)==1 and c not in inside:target.append((y,x,c))
 if not target:raise 知覚不適用('固定文法の目標記号行がない')
 target_rows=sorted({y for y,x,c in target})
 if any(b-a!=7 for a,b in zip(target_rows,target_rows[1:])):raise ValueError('目標行間隔が不明')
 inventory=[]
 for y in range(bottom,h-3):
  for x in range(w-3):
   try:t=記号を読む(frame,x,y,bg)
   except ValueError:continue
   if t is not None:inventory.append({'位置':[x,y],'記号':t})
 # all 4x4 tokens are disjoint; ambiguous overlapping instances reject
 for i,a in enumerate(inventory):
  for b in inventory[i+1:]:
   if abs(a['位置'][0]-b['位置'][0])<4 and abs(a['位置'][1]-b['位置'][1])<4:raise ValueError('在庫記号の解釈領域が重複')
 return {'背景色':bg,'目標列':[c for y,x,c in sorted(target)],'容器群':boxes,'在庫群':inventory}

def 列を生成する(scene,役割,長さ):
 boxes={b['色']:b for b in scene['容器群']};root=next(b for b in scene['容器群'] if b['起点']);out=[];active=set();repeated=False;ancestors=[]
 # Shape validity is checked before interpreting, including unreachable slots.
 for b in scene['容器群']:
  for s in b['枠群']:
   if s['記号'] is None:raise ValueError('未記入スロット')
   if 役割[s['記号']['中空']]=='参照' and s['記号']['色'] not in boxes:raise ValueError('参照先なし')
 def cycle(b,stack):
  if b['色'] in stack:return True
  return any(cycle(boxes[s['記号']['色']],stack+(b['色'],)) for s in b['枠群'] if 役割[s['記号']['中空']]=='参照')
 cyclic=cycle(root,())
 def finite(b):
  result=[]
  for s in b['枠群']:
   t=s['記号']
   result.extend([t['色']] if 役割[t['中空']]=='出力' else finite(boxes[t['色']]))
  return result
 if not cyclic:
  full=finite(root)
  return {'出力列':full,'目標長到達':len(full)==長さ,'生産的再入観測':False,'展開構造':'有限終端','比較範囲':'全出力列','過剰出力数':max(0,len(full)-長さ)}
 def visit(b):
  nonlocal repeated
  key=(b['色'],len(out))
  if key in active:raise ValueError('非生産的循環:同じ参照先へ出力増加なしで再入')
  if b['色'] in ancestors:repeated=True
  active.add(key);ancestors.append(b['色'])
  for s in b['枠群']:
   if len(out)>=長さ:break
   t=s['記号'];op=役割[t['中空']]
   if op=='出力':out.append(t['色'])
   elif op=='参照':visit(boxes[t['色']])
   else:raise ValueError('未知の役割')
  ancestors.pop();active.remove(key)
 visit(root)
 if not repeated:raise ValueError('循環候補だが目標長までに生産的再入未確認:判定範囲外')
 return {'出力列':out,'目標長到達':len(out)==長さ,'生産的再入観測':repeated,'展開構造':'生産的反復','比較範囲':'目標長前置列'}

def 一致する(scene,roles):
 try:
  r=列を生成する(scene,roles,len(scene['目標列']));return r['出力列']==scene['目標列'],r
 except ValueError as e:return False,{'構造状態':'HOLD','理由':str(e)}

def 照会(h,boundary,facts,key):
 r=h.照会する(外部入力(facts,boundary));p=[q for q in r.内容.get('予測群',[]) if tuple(q['結果経路'])==(key,)];values={q['予測値'] for q in p}
 return (next(iter(values)) if r.状態!='断定保留' and len(values)==1 else None),{'状態':r.状態,'予測':p,'保留理由':r.内容.get('断定保留理由群',[])}

def 内容候補を構成する(h,scene):
 roles={};queries={}
 for hollow in (False,True):roles[hollow],queries['中空' if hollow else '塗り潰し']=照会(h,役割境界,{'記号は中空':hollow},'列展開役割')
 if any(v is None for v in roles.values()):return {'状態':'HOLD','理由':'展開役割未学習または係争','照会':queries}
 yes,yq=照会(h,目標境界,{'終端条件に応じた列が一致':True},'提出が受理された');no,nq=照会(h,目標境界,{'終端条件に応じた列が一致':False},'提出が受理された')
 if yes is not True or no is not False:return {'状態':'HOLD','理由':'提出受理関係が未成立','正例照会':yq,'負例照会':nq}
 slots=[s for b in scene['容器群'] for s in b['枠群'] if s['記号'] is None];tokens=[s['記号'] for s in scene['在庫群']]
 if len(slots)!=len(tokens):raise ValueError('在庫と空欄の全単射文法が未成立')
 seen=set();solutions=[];failures=Counter();tested=0
 for perm in itertools.permutations(tokens):
  k=tuple((t['色'],t['中空']) for t in perm)
  if k in seen:continue
  seen.add(k);tested+=1
  for s,t in zip(slots,perm):s['記号']=t
  match,detail=一致する(scene,roles)
  if match:solutions.append({'割当':[{'位置':s['位置'],'色':t['色'],'中空':t['中空']} for s,t in zip(slots,perm)],'列生成':detail})
  else:failures[detail.get('理由','目標列不一致')]+=1
 for s in slots:s['記号']=None
 return {'状態':'唯一解答候補' if len(solutions)==1 else '複数解答候補' if solutions else 'HOLD','候補数':len(solutions),'全数確認した相異なる割当数':tested,'候補':solutions,'不採用理由集計':dict(failures),'実行許可':False,'作用対象':solutions[0]['割当'][0] if len(solutions)==1 and solutions[0]['割当'] else None,'照会':queries,'正例照会':yq,'負例照会':nq,'注意':'複数候補は目標列上で同値。未実行候補の環境受理を実測したとは主張しない'}

def 選択を読む(frame,scene):
 choices=[]
 for item in scene['在庫群']:
  x,y=item['位置'];bg=scene['背景色']
  if x<1 or y<1 or x+4>=len(frame[0]) or y+4>=len(frame):continue
  rim=[frame[y-1+dy][x-1+dx] for dy in range(6) for dx in range(6) if dy in (0,5) or dx in (0,5)]
  if len(set(rim))==1 and rim[0] not in (bg,item['記号']['色']):choices.append(item)
 if len(choices)>1:raise ValueError('選択中在庫が複数候補')
 return choices[0] if choices else None

def _参照群(値):
 refs=set()
 def walk(v):
  if isinstance(v,dict):
   for k,x in v.items():
    if k in ('原理参照','経験参照') and isinstance(x,str):refs.add(x)
    else:walk(x)
  elif isinstance(v,(list,tuple)):
   for x in v:walk(x)
 walk(値);return sorted(refs)

def _照会保留(値):
 if isinstance(値,dict):
  if 値.get('状態')=='断定保留' or 値.get('保留理由'):return True
  return any(_照会保留(v) for v in 値.values())
 if isinstance(値,(list,tuple)):return any(_照会保留(v) for v in 値)
 return False

def _対象関係(frame,scene):
 # Reuse existing generic component observation instead of introducing another CC engine.
 components=[]
 for i,c in enumerate(成分群(frame)):
  x,y=c['位置'];pts=c['点群'];components.append({'参照':f'成分:{i}','役割':'可視連結成分','位置':[x,y],'色':frame[y][x],'画素数':len(pts),'外接矩形':[min(a for a,b in pts),min(b for a,b in pts),max(a for a,b in pts)+1,max(b for a,b in pts)+1]})
 objects=list(components);relations=[]
 objects.append({'参照':'目標列','役割':'固定知覚による目標列候補','記号列':scene['目標列']})
 for i,b in enumerate(scene['容器群']):
  ref=f'容器:{i}';objects.append({'参照':ref,'役割':'標識付き起点候補' if b['起点'] else '容器候補','色':b['色'],'位置':b['位置'],'由来':'新規固定文法'})
  for j,s in enumerate(b['枠群']):
   sr=f'{ref}/枠:{j}';t=s['記号'];objects.append({'参照':sr,'役割':'未記入枠' if t is None else '記入済み枠','位置':s['位置'],'幅':4,'記号':None if t is None else {'色':t['色'],'中空':t['中空']}});relations.append({'関係':'内包と順序','親':ref,'子':sr,'順序':j})
   if t and t['中空']:
    for k,other in enumerate(scene['容器群']):
     if other['色']==t['色']:relations.append({'関係':'中空記号と容器の同色','記号':sr,'容器':f'容器:{k}','注意':'参照という役割はHDS照会後に扱う'})
 for i,t in enumerate(scene['在庫群']):objects.append({'参照':f'在庫:{i}','役割':'在庫記号候補','位置':t['位置'],'幅':4,'色':t['記号']['色'],'中空':t['記号']['中空']})
 return objects,relations

def 作用候補を構成する(系,盤面,図式,内容):
    if 内容.get('候補数')!=1:
        return {'状態':'HOLD','理由':'複数整合解から一意の実行対象を選ぶ方針は未採用','規則不確実性':False}
    selected=選択を読む(盤面,図式);assignments=内容['候補'][0]['割当']
    if not assignments:operation='完成列提出';data={};target=None
    elif selected:
        matching=[a for a in assignments if {'色':a['色'],'中空':a['中空']}==selected['記号']]
        if not matching:return {'状態':'HOLD','理由':'選択記号が未解決割当に不一致','規則不確実性':False}
        target=sorted(matching,key=lambda a:(a['位置'][1],a['位置'][0]))[0];operation='選択記号を空欄へ割当';data={'x':target['位置'][0]+2,'y':target['位置'][1]+2}
    else:
        target=sorted(assignments,key=lambda a:(a['位置'][1],a['位置'][0]))[0];tokens=[t for t in 図式['在庫群'] if t['記号']=={'色':target['色'],'中空':target['中空']}]
        if not tokens:return {'状態':'HOLD','理由':'要求記号が在庫にない','規則不確実性':False}
        item=sorted(tokens,key=lambda a:(a['位置'][1],a['位置'][0]))[0];operation='在庫記号を選択';data={'x':item['位置'][0]+2,'y':item['位置'][1]+2}
    action,query=照会(系,作用境界,{'解答作業':operation},'必要行動ID')
    if action is None:return {'状態':'HOLD','理由':'作業と行動IDのHDS対応が未確定','照会':query,'規則不確実性':True}
    return {'状態':'作用候補','作業':operation,'行動':{'id':action,'data':data},'解答対象':target,'照会':query,'実行許可':False}


def 候補を構成する(系,盤面,*,作用可能番号=(),出所=None):
    """同一の外部HDS、現在盤面、公開available_actionsだけで候補を構成する。"""
    result={'適用性':{'状態':'未確認','根拠':[],'前提':適用前提},'対象群':[],'関係群':[],
            '目標候補群':[],'作用候補群':[],'保留理由群':[],'規則不確実性':[],
            '解答選択状態':'未確認','複数整合解':False,'照会記録':[],
            '出所':{'構造境界':構造境界,'観測出所':deepcopy(出所 or {}),
                    '固定部分':['知覚文法','列操作語彙','全割当探索','作業順序化'],
                    'HDS照会部分':['記号役割','列受理対応','作業行動ID']},'実行許可':False}
    try:
        if not 盤面 or not 盤面[0] or not 1<=len(盤面)<=64 or any(len(r)!=len(盤面[0]) for r in 盤面) or not 1<=len(盤面[0])<=64 or any(type(v)is not int or not 0<=v<=15 for r in 盤面 for v in r):raise ValueError('公式盤面の矩形整数範囲外')
        if any(type(v)is not int or not 0<=v<=7 for v in 作用可能番号) or len(set(作用可能番号))!=len(作用可能番号):raise ValueError('利用可能作用の契約不正')
        scene=図式を観測する(盤面);objects,relations=_対象関係(盤面,scene)
        result.update({'適用性':{'状態':'適用可能','根拠':['固定知覚仮説に条件付きで合致'],'前提':適用前提},'対象群':objects,'関係群':relations})
        goal=内容候補を構成する(系,scene)
        result['目標候補群']=deepcopy(goal.get('候補',[]));result['全割当確認数']=goal.get('全数確認した相異なる割当数')
        result['不採用理由集計']=deepcopy(goal.get('不採用理由集計',{}));queries={k:deepcopy(goal[k]) for k in ('照会','正例照会','負例照会') if k in goal}
        result['照会記録'].append({'段階':'内容','記録':queries})
        if _照会保留(queries) or goal.get('状態')=='HOLD' and '候補数' not in goal:
            reason={'段階':'内容HDS','理由':goal.get('理由','HDS照会が未確定')};result['規則不確実性'].append(reason);result['保留理由群'].append(reason);result['解答選択状態']='規則保留';return result
        count=goal.get('候補数',0)
        if count==0:
            result['解答選択状態']='候補なし';result['保留理由群'].append({'段階':'内容','理由':goal.get('理由','現在の固定語彙内で整合割当がない')});return result
        if count>1:
            result['解答選択状態']='複数整合解';result['複数整合解']=True;result['保留理由群'].append({'段階':'実行方針','理由':'支持条件を満たす複数解を全保持。任意の一解を選ぶ方針は未採用','候補数':count});return result
        result['解答選択状態']='一意整合解';action=作用候補を構成する(系,盤面,scene,goal)
        result['照会記録'].append({'段階':'作用','記録':deepcopy(action.get('照会',{}))})
        if action.get('状態')!='作用候補':
            reason={'段階':'作用','理由':action.get('理由','作用未確定')};result['保留理由群'].append(reason)
            if action.get('規則不確実性'):result['規則不確実性'].append(reason)
            return result
        if _照会保留(action.get('照会',{})) or not _参照群(action.get('照会',{})):
            reason={'段階':'作用HDS','理由':'HDS保留または支持参照欠損'};result['保留理由群'].append(reason);result['規則不確実性'].append(reason);return result
        number=action['行動']['id'];args=action['行動'].get('data',{})
        if type(number)is not int or not 0<=number<=7:raise ValueError('作用番号型/範囲不正')
        if number not in 作用可能番号:result['保留理由群'].append({'段階':'合法性','理由':'利用可能作用に含まれない','要求作用':number});return result
        if number==6 and (set(args)!={'x','y'} or any(type(args[k])is not int or not 0<=args[k]<64 for k in args)):raise ValueError('座標作用引数不正')
        if number!=6 and args:raise ValueError('非座標作用の余分引数')
        result['作用候補群'].append({'作用番号':number,'引数':dict(args),'作業':action['作業'],'対象':deepcopy(action.get('解答対象')),'根拠参照':_参照群(action['照会']),'状態':'未実行候補','実行許可':False})
        return result
    except 知覚不適用 as e:
        result['適用性']={'状態':'構造上不適用','根拠':[str(e)],'前提':適用前提};result['保留理由群'].append({'段階':'固定知覚文法','理由':str(e)});return result
    except (ValueError,KeyError,TypeError) as e:
        result['保留理由群'].append({'段階':'知覚または接続契約','理由':str(e)});result['作用候補群']=[];return result


def 観測から候補を構成する(系,現在:観測):
    if 現在.状態!='NOT_FINISHED':
        return {'適用性':{'状態':'未確認','根拠':['進行中の観測ではない']},'対象群':[],'関係群':[],
                '目標候補群':[],'作用候補群':[],'保留理由群':[{'段階':'状態境界','理由':現在.状態}],
                '規則不確実性':[],'解答選択状態':'未確認','複数整合解':False,'照会記録':[],
                '出所':{'観測指紋':現在.指紋,'観測通番':現在.観測通番},'実行許可':False}
    return 候補を構成する(系,[list(r) for r in 現在.最新盤面],作用可能番号=現在.作用可能番号,
                         出所={'観測指紋':現在.指紋,'観測通番':現在.観測通番})


def 候補台帳を構成する(記録):
    """日本語正本。実在しない英語共通APIを新設しない。書込みは呼出側が管理。"""
    return {'種別':'未実行候補','対象':deepcopy(記録['対象群']),'役割':'可視列図式の条件付き役割',
            '関係':deepcopy(記録['関係群']),'状態':'HOLD' if 記録['保留理由群'] else '未実行候補',
            '前提':deepcopy(記録['適用性']),'作用':deepcopy(記録['作用候補群']),
            '予測差分':None,'実測差分':None,'保留条件':deepcopy(記録['保留理由群']),
            '規則不確実性':deepcopy(記録['規則不確実性']),'複数整合解':記録['複数整合解'],
            '反例':None,'適用範囲':'固定知覚/操作語彙に条件付き。fresh未実行',
            '由来':deepcopy(記録['出所']),'支持':_参照群(記録['照会記録']),
            '目標候補群':deepcopy(記録['目標候補群']),'実行許可':False}
