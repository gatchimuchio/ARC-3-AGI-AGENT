"""保存状態優先。明示的な全再学習だけが1051入力を空HDSへ直列投入する。"""
from pathlib import Path
import sys,json,gzip,tempfile,os,argparse,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from .鏡像内部.採否 import 正準値
教材根=ROOT/'入力/鏡像教師'

def 資料を読む(name):
 p=教材根/name
 return json.loads(gzip.decompress(p.read_bytes()))if p.suffix=='.gz'else json.loads(p.read_text())

def 保存状態を読む(path=None):
 p=Path(path)if path else 教材根/'保存HDS.json.gz'
 if p.suffix!='.gz':return HDS学習系統.読み込む(p)
 with tempfile.TemporaryDirectory()as d:
  q=Path(d)/'状態.json';q.write_bytes(gzip.decompress(p.read_bytes()));return HDS学習系統.読み込む(q)

def 教材を教える(教材,hds=None,*,逐次記録=None):
 hds=HDS学習系統()if hds is None else hds;logs=[]
 for i,t in enumerate(教材['教師群']):
  if t['順序']!=i+1:raise ValueError('入力順の不整合')
  r=hds.処理する(外部入力(t['入力'],t['境界']))
  logs.append({'順序':i+1,'境界':t['境界'],'入力':t['入力'],'状態':r.状態,'内容':r.内容,'追跡':r.追跡情報})
  if 逐次記録 is not None:逐次記録(logs[-1])
 return hds,logs

def 確認保存(hds,path):
 """失敗時は例外。保存メソッドが黙って失敗しても完了としない。"""
 path=Path(path)
 with tempfile.TemporaryDirectory(dir=path.parent)as d:
  p=Path(d)/'状態.json';hds.保存する(p)
  if not p.is_file()or not p.stat().st_size:raise OSError('HDS状態の実ファイル未保存')
  HDS学習系統.読み込む(p)
  digest=hashlib.sha256(p.read_bytes()).hexdigest();os.replace(p,path)
 if not path.is_file()or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise OSError('保存後SHA256不一致')
 return {'保存完了':True,'SHA256':digest}

def 結果保存(path,value):
 path=Path(path);raw=json.dumps(正準値(value),ensure_ascii=False,separators=(',',':')).encode()
 with tempfile.TemporaryDirectory(dir=path.parent)as d:
  p=Path(d)/'結果.json';p.write_bytes(raw);os.replace(p,path)
 if path.read_bytes()!=raw:raise OSError('結果保存後照合不一致')

def main():
 p=argparse.ArgumentParser();p.add_argument('--全再学習',action='store_true');p.add_argument('--保存状態',type=Path);p.add_argument('--状態出力',type=Path);p.add_argument('--出力',type=Path,required=True);p.add_argument('--全検証',action='store_true');p.add_argument('--人工反証',action='store_true');p.add_argument('--全問題再構成',action='store_true');a=p.parse_args()
 if a.全再学習 and a.保存状態:p.error('保存状態読込と全再学習は排他')
 if a.全再学習 and not a.状態出力:p.error('全再学習には状態出力が必要')
 if a.全再学習:
  h=HDS学習系統()
  with a.出力.with_suffix('.逐次入力.jsonl').open('w')as stream:
   def 逐次記録(v):stream.write(json.dumps(正準値(v),ensure_ascii=False)+'\n');stream.flush()
   try:h,logs=教材を教える(資料を読む('関係教材.json'),h,逐次記録=逐次記録)
   except Exception as exc:
    逐次記録({'状態':'中断・未完了','例外':repr(exc)})
    try:確認保存(h,a.状態出力)
    except Exception as err:逐次記録({'状態':'途中状態保存失敗','例外':repr(err)})
    raise
  結果保存(a.出力.with_suffix('.全入力.json'),logs)
 else:h=保存状態を読む(a.保存状態)
 from .鏡像検証 import 検証する
 result=検証する(h,全原票=a.全検証,人工反証=a.人工反証)
 if a.全問題再構成:
  from .鏡像検証 import 初期問題を再構成
  result['全問題再構成']=初期問題を再構成(h)
  result['集計']['新入口再構成']=result['全問題再構成']['集計']
 if a.状態出力:result['保存']=確認保存(h,a.状態出力)
 result['再学習実行']=a.全再学習;result['実行許可']=False
 checks={'旧教師一致':result['集計']['旧44一致']==44 and result['集計']['保持203一致']==203,'全手順一致':result['集計']['全段成立']==46 and result['集計']['段採否']=={'条件付き支持':1524}}
 if a.全検証:
  raw=result['集計']['原票'];checks['全原票一致']=raw=={'全遷移':3245,'占有':{'占有一致':2694,'非方向':291,'gateHOLD':257,'非frame':3},'保持':{'一致':3102,'HOLD':143},'複数応答作用':17,'全応答相':54}
 if a.人工反証:checks['人工反証全HOLD']=result['集計']['人工反証247全HOLD']
 if a.全問題再構成:checks['新入口再構成一致']=result['集計']['新入口再構成']=={'問題数':16,'完成候補数':46,'手順数':46,'全段成立':46,'全段数':1524}
 result['検証一致']=checks
 結果保存(a.出力,result);print(json.dumps(result['集計'],ensure_ascii=False))
 if not all(checks.values()):raise SystemExit(1)
if __name__=='__main__':main()
