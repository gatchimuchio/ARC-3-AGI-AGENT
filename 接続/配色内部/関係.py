"""固定HDS公開APIで関係を学習。raw参照の集約と提示順を完全保存。"""
import json,time,resource,hashlib
from collections import defaultdict,deque
from dataclasses import asdict
from .知覚 import ROOT,BASE
from hds学習系統 import HDS学習系統,外部入力
COPY='公開色対応:参照色と解答候補色';MASK='公開塗布:器具側幾何と可視上書き';TURN='公開器具:現在方向と方向作用'
X='候補色は参照役割色と一致';Y='候補色は結果役割色と一致';MX='幾何領域候補に属する';MY='観測上この画素は器具色で上書き';TX='現在方向と方向作用';TY='後方向'
def sig(x):return json.dumps(x,separators=(',',':'),ensure_ascii=False)
def membership(direction,x,y,n,mode):
 dx,dy=direction;depth=dx*(2*x-n+1)+dy*(2*y-n+1);cross=-dy*(2*x-n+1)+dx*(2*y-n+1)
 if mode=='広域塗布':return depth>=0
 if mode=='小域塗布' and abs(dx)+abs(dy)==1:return depth>=n-5 and abs(cross)<=3
 return None

def query(h,b,x,y):
 q=h.照会する(外部入力(x,b));ps=[r['予測値'] for r in q.内容['予測群'] if tuple(r['結果経路'])==(y,)]
 return (ps[0] if q.状態!='断定保留' and len(set(map(sig,ps)))==1 else None),asdict(q)
