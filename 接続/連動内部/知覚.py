"""公開画素の連結成分・正方形全被覆・幾何的個体対応。固定知覚であってHDS学習ではない。"""
from collections import Counter
from itertools import permutations, product
import json, hashlib
方向={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}

def 符号(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(符号(x).encode()).hexdigest()
def 作用番号(v):return int(str(v).replace('ACTION','')) if str(v)!='RESET' else 0

def 成分(f,colors=(1,10)):
    todo={(x,y) for y,row in enumerate(f) for x,c in enumerate(row) if c in colors and 0<y<63};out=[]
    while todo:
        p=min(todo);todo.remove(p);q=[p];c=f[p[1]][p[0]]
        for x,y in q:
            for z in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if z in todo and f[z[1]][z[0]]==c:todo.remove(z);q.append(z)
        out.append({'色':c,'画素':q})
    return out

def 知覚(f,幅=None):
    if not isinstance(f,(list,tuple))or len(f)!=64 or any(not isinstance(row,(list,tuple))or len(row)!=64 for row in f)or any(type(v)is not int or not 0<=v<=15 for row in f for v in row):return {'幅':None,'駒':[],'HOLD':['64×64/整数色範囲外'],'全被覆':[]}
    cc=成分(f);dims=[min(max(x for x,y in c['画素'])-min(x for x,y in c['画素'])+1,max(y for x,y in c['画素'])-min(y for x,y in c['画素'])+1)for c in cc]
    w=幅 or (min(dims) if dims else None);out=[];holds=[]
    if w not in (4,5):return {'幅':w,'駒':[],'HOLD':['可視正方形幅が4/5以外または欠損'],'全被覆':[]}
    # 同色正方形による全正確被覆。最小画素を含む全平行移動を残す。
    color_covers=[]
    for color in (1,10):
        pts={(x,y)for c in cc if c['色']==color for x,y in c['画素']};covers=[]
        def go(rem,used):
            if not rem:covers.append(sorted(used));return
            px,py=min(rem)
            for ox in range(px-w+1,px+1):
                for oy in range(py-w+1,py+1):
                    sq={(ox+i,oy+j)for i in range(w)for j in range(w)}
                    if sq<=rem:go(rem-sq,used+[(ox,oy,color)])
        if len(pts)>2*w*w:holds.append('大駒が二個体境界を超える');color_covers.append([]);continue
        go(pts,[]);color_covers.append(covers)
    covers=[sorted(a+b)for a,b in product(*color_covers)];covers=list({符号(c):c for c in covers}.values())
    if len(covers)!=1:holds.append('正方形分解が一意でない')
    return {'幅':w,'駒':covers[0]if len(covers)==1 else [],'全被覆':covers,'HOLD':holds}

def 局所地形(f,p,w,a):
    dx,dy=方向[a]
    edges={Counter(f[y][x]for y in range(1,63)).most_common(1)[0][0]for x in(0,63)}
    def surface(sign):
        x,y,c=p;vals=Counter();shapes=set()
        for j in range(w):
            for i in range(w):
                xx=x+i+dx*w*sign;yy=y+j+dy*w*sign
                v=f[yy][xx] if 0<=xx<64 and 0<=yy<64 else -1
                role='大駒'if v in (1,10)else'灰床'if v==5 else '外周背景'if v in edges else '模様青'if v==8 else '黄領域'if v==14 else '暗領域'if v==12 else '小赤印'if v==9 else '画面外'if v==-1 else f'内部色{v}'
                vals[role]+=1
                if 0<=xx<64 and 0<=yy<64 and v not in edges|{1,10,5,8,9,0}:
                    comp={(xx,yy)};todo=[(xx,yy)]
                    for qx,qy in todo:
                        for z in((qx-1,qy),(qx+1,qy),(qx,qy-1),(qx,qy+1)):
                            if z not in comp and 0<=z[0]<64 and 0<=z[1]<64 and f[z[1]][z[0]]==v:comp.add(z);todo.append(z)
                    width=max(q[0]for q in comp)-min(q[0]for q in comp)+1;height=max(q[1]for q in comp)-min(q[1]for q in comp)+1
                    shapes.add((role,'単位正方形'if width==height==w and len(comp)==w*w else '非単位成分',width/w,height/w,len(comp)/(w*w)))
        from fractions import Fraction
        halo=Counter()
        if shapes:
            ox=x+dx*w*sign;oy=y+dy*w*sign
            for py in range(oy-w,oy+2*w):
                for px in range(ox-w,ox+2*w):
                    if ox<=px<ox+w and oy<=py<oy+w:continue
                    if not(0<=px<64 and 0<=py<64):kind='画面外'
                    else:
                        color=f[py][px];kind='大駒'if color in(1,10)else'灰床'if color==5 else'外周背景'if color in edges else'模様青'if color==8 else'小赤印'if color==9 else'内部色'
                    halo[kind]+=1
        return {'面積比':{k:str(Fraction(v,w*w))for k,v in sorted(vals.items())},'接触色成分幾何':sorted(shapes),'特殊成分周囲一単位環':{k:str(Fraction(v,8*w*w))for k,v in sorted(halo.items())}}
    return {'入力同方向':surface(1),'入力逆方向':surface(-1)}

def 前提(f,h,w,a,role,anchor=None):
    p=h[role]
    relation='非選択表示'if p[2]==1 else '垂直同軸'if a in(1,2)else'履歴不明'if anchor is None else '直近実測水平同方向役割'if role==anchor else '直近実測水平反転役割'
    return {'操作対象関係':relation,'作用':a,'大駒表示色':p[2],**局所地形(f,p,w,a)}

def 全対応(before,after,w,a):
    """方向物理を仮定せず、同一位置/軸上±1単位の全対応。復帰・別軸移動はHOLD。"""
    if len(before)!=2 or len(after)!=2 or a not in 方向:return []
    dx,dy=方向[a];out=[]
    for perm in permutations(after):
        effects=[]
        for p,q in zip(before,perm):
            dd=(q[0]-p[0],q[1]-p[1]);values=[k for k in(-1,0,1)if dd==(k*dx*w,k*dy*w)]
            if len(values)!=1:break
            effects.append(values[0])
        else:out.append({'後役割配置':perm,'相対変位':effects})
    return out
