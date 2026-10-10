"""関節線のportable試験。保存状態は外部envから明示注入し、再学習しない。"""
import argparse
import builtins
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
HDS_ROOT=ROOT/'HDS/学習系統/v0.4.2'
if HDS_ROOT.is_dir():sys.path.insert(0,str(HDS_ROOT))
from hds学習系統 import HDS学習系統,外部入力
from 接続 import 関節線接続 as A
from 接続 import 関節線因子 as F
FIXTURE=ROOT/'検証/資料/関節線'
STATE_ENV='ARC_JOINTED_LINE_HDS_STATE'
COUNTER_ENV='ARC_JOINTED_LINE_COUNTER_STATE'
DECODED_SHA={'real':'259f20f72926a552ad5563b6169a567f5539df9045fb7496491cd0a5b3708d89','counter':'acf2589ec1ffd3ba1373c49bc156fe166f34bf42c53cea2ee98934e4626074a0'}

class 未設定(RuntimeError):pass

def 資料を読む(name):
    with gzip.open(FIXTURE/name,'rt',encoding='utf-8')as f:return json.load(f)

def 拒否(*args,**kwargs):raise AssertionError('学習またはruntime file IOは試験で禁止')

def 外部IOなし(function,*args,**kwargs):
    old,oldpath=builtins.open,Path.open
    builtins.open=拒否;Path.open=拒否
    try:return function(*args,**kwargs)
    finally:builtins.open=old;Path.open=oldpath

def 予測正規化(predictions):
    # 型.py 予測記録の外側tuple契約2箇所のみ。内部型/値は変換しない。
    return [{**p,'結果経路':list(p['結果経路']),'条件値群':list(p['条件値群'])}for p in predictions]

def 意味SHA(path):
    digest=hashlib.sha256();raw=hashlib.sha256();inside=False;pending=None;values={};size=0
    with Path(path).open('rb')as f:
        for line in f:
            raw.update(line);size+=len(line);s=line.decode().strip()
            if s=='"識別子状態",':inside=True
            elif s=='"台帳",':inside=False
            if pending:
                values[pending]=json.loads(s.rstrip(','));line=line[:len(line)-len(line.lstrip())]+b'0'+(b','if s.endswith(',')else b'')+b'\n';pending=None
            elif inside and s in ('"照会",','"学習判定",'):pending=s[1:-2]
            digest.update(line)
    if set(values)!={'照会','学習判定'}:raise ValueError('固定保存形式のカウンタ境界不一致')
    return {'意味SHA256':digest.hexdigest(),'復号SHA256':raw.hexdigest(),'カウンタ':values,'bytes':size}

def 資源を確認():
    # Linux ru_maxrss は fork/exec 前の親高水位も引き継ぎ得る。
    # 現在の exec 後アドレス空間の実測最大RSSを使う。取得不能なら省略しない。
    try:
        rows=[line.split() for line in Path('/proc/self/status').read_text().splitlines()
              if line.startswith('VmHWM:')]
        if len(rows)!=1 or len(rows[0])!=3 or rows[0][2]!='kB':
            raise ValueError('VmHWMの単位/形式が不明')
        if not rows[0][1].isascii() or not rows[0][1].isdecimal():
            raise ValueError('VmHWMの数値形式が不明')
        rss=int(rows[0][1])
        if rss<=0:raise ValueError('VmHWMが正でない')
    except (OSError,ValueError) as error:
        raise RuntimeError('検証過程の最大RSSを取得できない') from error
    if rss>950*1024:raise RuntimeError('RAM950MiB上限超過')
    return rss

def 状態を読む(kind,temporary_root):
    env=STATE_ENV if kind=='real' else COUNTER_ENV
    source=os.environ.get(env)
    if not source:raise 未設定(env+' 未設定。空state/再学習へ代替しない。')
    mem=Path('/proc/meminfo')
    if mem.exists():
        available=int(next(s.split()[1]for s in mem.read_text().splitlines()if s.startswith('MemAvailable:')))
        if available<2*1024*1024:raise RuntimeError('共有Available2GiB未満、外部state読込待機')
    source=Path(source)
    with source.open('rb')as f:compressed=f.read(2)==b'\x1f\x8b'
    raw=Path(temporary_root)/'一時state.json';size=0
    with (gzip.open(source,'rb')if compressed else source.open('rb'))as f,raw.open('wb')as w:
        while chunk:=f.read(1024*1024):
            size+=len(chunk)
            if size>101*1024*1024:raise RuntimeError('一時raw101MiB上限超過')
            w.write(chunk)
    before=意味SHA(raw)
    if before['復号SHA256']!=DECODED_SHA[kind]:raise ValueError('試験の外部state SHA不一致。別stateへ黙って代替しない。')
    h=HDS学習系統.読み込む(raw);raw.unlink();資源を確認();h.処理する=拒否
    return h,before,raw

def 全126を照会(h,kind):
    rows=[]
    for expected in 資料を読む('実1012r2全126照会.json.gz')['全126照会']:
        q=h.照会する(外部入力(expected['入力'],expected['境界']))
        if kind=='real':
            ok=q.状態==expected['期待状態'] and A._typed_equal(予測正規化(q.内容['予測群']),予測正規化(expected['期待予測群']))
        else:ok=q.状態=='断定保留'
        rows.append({'群':expected['群'],'索引':expected['索引'],'状態':q.状態,'一致':ok})
    if not all(r['一致']for r in rows):raise AssertionError('全126照会の契約不一致: '+repr([r for r in rows if not r['一致']]))
    return rows

def 初期6問を照合(h,kind):
    results=[]
    for index,item in enumerate(資料を読む('初期6問.json.gz')):
        b=外部IOなし(A.関節線候補を作る,item['frame'],item['available_actions'],h)
        assert not b['実行許可'] and not b['採用順序']
        assert len(b['全座標原始候補'])==4096
        assert len({(r['x'],r['y'])for r in b['全座標原始候補']})==4096
        for p in b['現在全準備選択領域']:
            coords=[tuple(x)for part in p['全同値領域']for x in part['全座標']]
            assert len(coords)==len(set(coords))==4096
        adopted=sum(q['採用可能']for q in b['全HDS照会'])
        if kind in ('empty','counter'):assert adopted==0
        if index==4:
            assert len(b['全端点因子'])==76 and b['全割当因子']['全直積数']==6400
            if kind=='real':assert b['全事象因子']['全族数']==160
        if index==5:assert b['全割当因子']['全直積数']==2359296
        results.append({'問題索引':index+1,'座標':4096,'採用可能照会':adopted,'状態':b['状態'],'全事象族':b.get('全事象因子',{}).get('全族数'),'端点族':len(b.get('全端点因子',[])),'割当':b.get('全割当因子',{}).get('全直積数')})
        資源を確認()
    return results

def 軽量境界を照合():
    class Broken:
        def 照会する(self,x):raise RuntimeError('試験用照会例外')
    class Raw:
        追跡情報={}
        def __init__(self,state,value,path=('観測作用結果',)):
            self.状態=state;self.内容={'予測群':[{'結果経路':path,'予測値':value}]}
    class Fake:
        def __init__(self,raw):self.raw=raw
        def 照会する(self,x):return self.raw
    frame=資料を読む('初期6問.json.gz')[4]['frame'];results=[]
    for actions in ([6,6],[6,17],[6,True],[6,'7']):
        b=外部IOなし(A.関節線候補を作る,frame,actions,Broken());assert b['状態']=='Action入力全体HOLD' and not b['全HDS照会'];results.append('不正Action照会0')
    for value in (True,1,'未知作用',[1],{'不明':1}):
        qs,effect=A._effect(A.照会束(Fake(Raw('出力',value))),[{}]);assert effect is None and not qs[0]['採用可能'];results.append('不正予測HOLD')
    qs,effect=A._effect(A.照会束(Fake(Raw('未知状態','選択だけ交換'))),[{}]);assert effect is None
    b=外部IOなし(A.関節線候補を作る,frame,[6],Broken());assert len(b['全座標原始候補'])==4096 and len(b['全端点因子'])==76 and not any(q['採用可能']for q in b['全HDS照会'])
    h=HDS学習系統();h.処理する=拒否
    altered=copy.deepcopy(frame);altered[0][0]=16
    b=外部IOなし(A.関節線候補を作る,altered,[6],h);assert b['状態']=='入力画素HOLD' and not b['全HDS照会']
    original=外部IOなし(A.関節線候補を作る,frame,[6],h);source=original['現在観測']['供給'][0];changed=copy.deepcopy(frame)
    for dx,dy in F.CIRCLE:changed[source['xy'][1]+dy][source['xy'][0]+dx]=5
    b=外部IOなし(A.関節線候補を作る,changed,[6],h);assert b['全割当因子']['全直積数']!=6400
    limited=外部IOなし(A.関節線候補を作る,frame,[6],h,資源枠={'端点族':1,'色DAG状態':1});assert limited['状態']=='資源全体HOLD' and limited['全端点因子']['全族数']==76
    for budget in ({'端点族':10**9},{'端点族':True},[1],{'未知':1}):
        b=外部IOなし(A.関節線候補を作る,frame,[6],Broken(),資源枠=budget);assert b['状態']=='資源枠入力HOLD' and not b['全HDS照会']
    base={'原理参照':'test','結果経路':('a',),'予測値':'値','条件値群':(('内部',),)}
    other={**base,'結果経路':['a'],'条件値群':list(base['条件値群'])};assert A._typed_equal(予測正規化([base]),予測正規化([other]))
    other['条件値群']=[['内部']];assert not A._typed_equal(予測正規化([base]),予測正規化([other]))
    try:original.実行する()
    except RuntimeError:pass
    else:raise AssertionError('実行不可型の違反')
    return {'個別型負例':results,'照会例外全候補保持':True,'入力差で割当変化':True,'資源全域HOLD':True,'内部条件型を保持':True,'実行不可':True}

def 実行(kind='empty'):
    start=time.time();result={'kind':kind,'fresh_success':0,'追加学習':0,'536M再検査':'このportable wrapperでは実行しない。独立凍結/監査の全数証拠へ分離。'}
    if kind=='empty':
        h=HDS学習系統();h.処理する=拒否;result['初期6問']=初期6問を照合(h,kind);result['境界']=軽量境界を照合()
    else:
        with tempfile.TemporaryDirectory(prefix='arc-jointed-state-')as td:
            h,before,raw=状態を読む(kind,td)
            result['全126']=全126を照会(h,kind);result['初期6問']=初期6問を照合(h,kind)
            h.保存する(raw);after=意味SHA(raw);assert before['意味SHA256']==after['意味SHA256'];result.update(Memory意味不変=True,前=before,後=after)
    result.update(最大RSS_KiB=資源を確認(),秒=time.time()-start)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=('empty','real','counter'),default='empty');parser.add_argument('--output',type=Path);args=parser.parse_args()
    try:result=実行(args.kind)
    except 未設定 as error:parser.exit(2,str(error)+'\n')
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        if args.output.exists():raise FileExistsError('既存証拠へ上書きしない: '+str(args.output))
        args.output.write_text(text)
    else:print(text)
