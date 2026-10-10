"""承認済み知覚/欄語彙。日本語正本。ID/ファイル/HDS生成に依存しない。"""
from dataclasses import asdict
from functools import lru_cache
from .字形原語 import 字形群を読む,軌道
from .字形群制約 import 広い構文,族値
from hds学習系統 import 外部入力
CURSOR='公開選択作用:役割別欄の相対巡回'
def selected(frame,key):
    x,y,c=key;return sum(frame[yy][xx]==0 for yy in range(max(0,y-3),min(len(frame),y+10)) for xx in range(x,x+7))
def 可逆字形値(g):return ''.join('1' if v else '0' for row in g for v in row)
def 語彙境界(action,kind):return f'公開解答記号循環:{kind}:ACTION{action}'
def query(model,data,boundary,outkey):
    q=model.照会する(外部入力(data,boundary));vs=[v['予測値'] for v in q.内容['予測群'] if tuple(v['結果経路'])==(outkey,)]
    p=vs[0] if q.状態!='断定保留' and len(set(vs))==1 else None
    return p,asdict(q)

@lru_cache(maxsize=None)
def view(frame):
    gs=字形群を読む(frame);p=広い構文(frame)
    if p['状態']!='構文成立':return {'状態':'HOLD','理由':p['理由']}
    cells={};groups=[]
    for g in gs:
        x,y=g['位置'];ks=[]
        for j,m in enumerate(g['字形']):
            k=(x+7*j,y,g['色']);cells[k]=m;ks.append(k)
        groups.append(tuple(ks))
    role=p['初期選択枠は見本領域']
    if type(role) is not bool:return {'状態':'HOLD','理由':'選択領域の役割を一意に観測できない'}
    # 固定の知覚/相対順序語彙。ACTION番号から選択先を定義しない。
    fields=tuple(g for g in groups if g[0][1]<p['入力']['位置'][1]) if role else tuple((k,) for k in cells if k[1]==p['表示目標']['位置'][1])
    marked=tuple(k for k in cells if selected(frame,k)==14)
    matches=[i for i,f in enumerate(fields) if set(f)==set(marked)]
    return {'状態':'成立' if len(matches)==1 else 'HOLD','理由':None if len(matches)==1 else '選択枠と役割別欄が一意に一致しない','見本編集役割':role,'欄群':fields,'選択欄':matches[0] if len(matches)==1 else None,'選択セル群':marked,'セル字形':cells,'配置':tuple(groups),'固定セル字形':tuple((k,m) for k,m in cells.items() if not any(k in f for f in fields))}

def observe(frame):return view(tuple(tuple(r) for r in frame))

def compatible(a,b):return a['状態']==b['状態']=='成立' and a['配置']==b['配置'] and a['欄群']==b['欄群'] and a['固定セル字形']==b['固定セル字形']

