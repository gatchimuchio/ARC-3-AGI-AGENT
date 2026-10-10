"""新固定候補文法:色別対グラフ閉包と編集見本の逆向き群制約。HDS中核は変更しない。"""
from collections import defaultdict
from itertools import product
from .字形原語 import *
def 族値(g):return ''.join('1' if v else '0' for row in min(軌道(g)) for v in row)

役割境界='字形課題:選択枠役割と解答対象'
役割入力='初期選択枠は見本領域'
役割結果='解答は見本を更新'


def 広い構文(frame):
    gs=字形群を読む(frame);ys=sorted({g['位置'][1] for g in gs})
    if len(ys)<3:return {'状態':'HOLD','理由':'群不足'}
    source=[g for g in gs if g['位置'][1]==ys[-2]];target=[g for g in gs if g['位置'][1]==ys[-1]]
    if len(source)!=1 or len(target)!=1:return {'状態':'HOLD','理由':'問題列が一意でない'}
    pairs=[]
    for y in ys[:-2]:
        row=[g for g in gs if g['位置'][1]==y]
        if len(row)%2:return {'状態':'HOLD','理由':'見本対不足'}
        pairs.extend(zip(row[::2],row[1::2]))
    marked=[]
    for i,g in enumerate(gs):
        x,y=g['位置'];w=7*len(g['字形']);n=sum(frame[yy][xx]==0 for yy in range(max(0,y-3),min(len(frame),y+10)) for xx in range(x,x+w))
        if n:marked.append(g['位置'][1] in ys[:-2])
    return {'状態':'構文成立','見本対':pairs,'入力':source[0],'表示目標':target[0],'初期選択枠は見本領域':marked[0] if len(set(marked))==1 else None}


def HDS真偽(model,data,boundary,key):
    from hds学習系統 import 外部入力
    q=model.照会する(外部入力(data,boundary));vs=[v['予測値'] for v in q.内容['予測群'] if tuple(v['結果経路'])==(key,)]
    return vs[0] if q.状態!='断定保留' and len(set(vs))==1 and type(vs[0]) is bool else None


def 対関係が利用可能(model):return all(HDS真偽(model,{入力名:b},境界,結果名)==b for b in (False,True))
def 列(g):return tuple(族値(m) for m in g['字形'])


def 固定見本グラフ(model,p):
    if not 対関係が利用可能(model):return {'状態':'HOLD','理由':'対所属関係未支持','候補':[]}
    if any(len(a['字形'])!=1 or len(b['字形'])!=1 for a,b in p['見本対']):return {'状態':'HOLD','理由':'単記号グラフ外','候補':[]}
    edges=defaultdict(set)
    for a,b in p['見本対']:
        x=(a['色'],列(a)[0]);y=(b['色'],列(b)[0]);edges[x].add(y);edges[y].add(x)
    goals=[]
    for shape in 列(p['入力']):
        start=(p['入力']['色'],shape);seen={start};todo=[start]
        while todo:
            node=todo.pop()
            for x in edges[node]-seen:seen.add(x);todo.append(x)
        goals.append(sorted(v for color,v in seen if color==p['表示目標']['色']))
    return {'状態':'目標族成立' if all(len(g)==1 for g in goals) else 'HOLD','理由':'有限の単記号対グラフ全閉包。方向の実字形と作用は未同定','候補':goals,'実行許可':False}


def 編集一段(model,p):
    if not 対関係が利用可能(model):return {'状態':'HOLD','理由':'対所属関係未支持','候補':[]}
    source,target=列(p['入力']),列(p['表示目標']);pairs=p['見本対']
    if any(a['色']!=p['入力']['色'] or b['色']!=p['表示目標']['色'] for a,b in pairs):return {'状態':'HOLD','理由':'一段と異なる色型','候補':[]}
    results=[];failures=defaultdict(int);rejections=[]
    def walk(s,t,assign,path):
        if s==len(source) and t==len(target):
            results.append({'使用順':path,'割当':{str(k):[list(a),list(b)] for k,(a,b) in assign.items()},'自由見本':[i for i in range(len(pairs)) if i not in assign]});return
        for i,(a,b) in enumerate(pairs):
            na,nb=len(a['字形']),len(b['字形'])
            if s+na>len(source) or t+nb>len(target):failures['観測列長不一致']+=1;rejections.append({'理由':'観測列長不一致','使用順前置':path+[i],'入力位置':s,'目標位置':t});continue
            value=(source[s:s+na],target[t:t+nb])
            if i in assign and assign[i]!=value:failures['同じ見本の再使用が矛盾']+=1;rejections.append({'理由':'同じ見本の再使用が矛盾','使用順前置':path+[i],'入力位置':s,'目標位置':t});continue
            if any((x==value[0])!=(y==value[1]) for x,y in assign.values()):failures['HDSの全所属同値に矛盾']+=1;rejections.append({'理由':'HDSの全所属同値に矛盾','使用順前置':path+[i],'入力位置':s,'目標位置':t});continue
            walk(s+na,t+nb,{**assign,i:value},path+[i])
    walk(0,0,{},[])
    return {'状態':'HOLD','理由':'実字形と作用到達性を保留。複数候補それ自体は不合格理由ではない','候補':results,'棄却理由数':dict(failures),'棄却枝':rejections,'実行許可':False}


def 編集二段(model,p):
    """有限の型付き二段逆置換。中間アルファベットは変数で保持し、未知実字形を創作しない。"""
    if not 対関係が利用可能(model):return {'状態':'HOLD','理由':'対所属関係未支持','候補':[]}
    source,target=列(p['入力']),列(p['表示目標']);sc,tc=p['入力']['色'],p['表示目標']['色'];pairs=p['見本対']
    middle=({b['色'] for a,b in pairs if a['色']==sc}&{a['色'] for a,b in pairs if b['色']==tc})-{sc,tc}
    if len(middle)!=1:return {'状態':'HOLD','理由':'二段の中間型未同定','候補':[]}
    mc=next(iter(middle));first=[(i,a,b) for i,(a,b) in enumerate(pairs) if (a['色'],b['色'])==(sc,mc)];second=[(i,a,b) for i,(a,b) in enumerate(pairs) if (a['色'],b['色'])==(mc,tc)]
    if len(first)+len(second)!=len(pairs) or any(len(a['字形'])!=1 for _,a,b in first+second) or any(len(b['字形'])!=1 for _,a,b in second):return {'状態':'HOLD','理由':'対応する二段文法外','候補':[]}
    results=[];fail=defaultdict(int);rejections=[]
    for use1 in product(range(len(first)),repeat=len(source)):
        left={};tokens=[];valid=True
        for input_symbol,k in zip(source,use1):
            i,a,b=first[k]
            if i in left and left[i]!=input_symbol:valid=False;break
            left[i]=input_symbol;tokens.extend((i,j) for j in range(len(b['字形'])))
        if not valid:fail['第一段同一見本の入力矛盾']+=1;rejections.append({'理由':'第一段同一見本の入力矛盾','第一段使用順':use1});continue
        if len(tokens)!=len(target):fail['中間列/目標列長不一致']+=1;rejections.append({'理由':'中間列/目標列長不一致','第一段使用順':use1});continue
        for use2 in product(range(len(second)),repeat=len(tokens)):
            out={};parent={};valid=True
            def find(x):
                parent.setdefault(x,x)
                if parent[x]!=x:parent[x]=find(parent[x])
                return parent[x]
            def union(a,b):parent[find(a)]=find(b)
            for var,t,k in zip(tokens,target,use2):
                i,a,b=second[k]
                if i in out and out[i]!=t:valid=False;break
                out[i]=t;union(('中間',)+var,('右入力',i))
            if not valid:fail['第二段同一見本の出力矛盾']+=1;rejections.append({'理由':'第二段同一見本の出力矛盾','第一段使用順':use1,'第二段使用順':use2});continue
            for i,a in out.items():
                for j,b in out.items():
                    if a==b:union(('右入力',i),('右入力',j))
            if any(find(('右入力',i))==find(('右入力',j)) and a!=b for i,a in out.items() for j,b in out.items()):fail['第二段同一中間記号の出力矛盾']+=1;rejections.append({'理由':'第二段同一中間記号の出力矛盾','第一段使用順':use1,'第二段使用順':use2});continue
            for i,a in left.items():
                for j,b in left.items():
                    vi=[('中間',i,n) for n in range(len(pairs[i][1]['字形']))];vj=[('中間',j,n) for n in range(len(pairs[j][1]['字形']))]
                    if a==b:
                        if len(vi)!=len(vj):valid=False;break
                        for x,y in zip(vi,vj):union(x,y)
            if not valid:fail['第一段同じ入力の出力長矛盾']+=1;rejections.append({'理由':'第一段同じ入力の出力長矛盾','第一段使用順':use1,'第二段使用順':use2});continue
            if any(find(('右入力',i))==find(('右入力',j)) and a!=b for i,a in out.items() for j,b in out.items()):fail['合成により第二段が矛盾']+=1;rejections.append({'理由':'合成により第二段が矛盾','第一段使用順':use1,'第二段使用順':use2});continue
            classes=defaultdict(list)
            for x in list(parent):classes[find(x)].append(x)
            distinct=[]
            for i,a in left.items():
                for j,b in left.items():
                    if i<j and a!=b:
                        vi=[find(('中間',i,n)) for n in range(len(pairs[i][1]['字形']))];vj=[find(('中間',j,n)) for n in range(len(pairs[j][1]['字形']))]
                        if vi==vj:valid=False;break
                        distinct.append((i,j))
            if not valid:fail['異なる第一段入力が同じ出力群']+=1;rejections.append({'理由':'異なる第一段入力が同じ出力群','第一段使用順':use1,'第二段使用順':use2});continue
            results.append({'第一段使用順':[first[k][0] for k in use1],'第二段使用順':[second[k][0] for k in use2],'第一段入力':{str(k):v for k,v in left.items()},'第二段出力':{str(k):v for k,v in out.items()},'中間同値類':[sorted(v,key=repr) for v in classes.values()],'第二段入力非同値':[(i,j) for i,a in out.items() for j,b in out.items() if i<j and a!=b],'第一段出力群非同値':distinct,'自由見本':[i for i in range(len(pairs)) if i not in left and i not in out]})
    return {'状態':'HOLD','理由':'中間実字形と作用到達性を保留。全象徴候補を保持し、複数性自体は不合格にしない','候補':results,'棄却理由数':dict(fail),'棄却枝':rejections,'実行許可':False}
