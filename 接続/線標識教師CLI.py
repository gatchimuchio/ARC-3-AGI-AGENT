"""既存外部HDSと問題だけから全候補を再現。教材教師は学習せず出典として検証可能。"""
from pathlib import Path
import argparse,gzip,json,hashlib,tempfile,os,sys,shutil
from .線標識接続 import 線標識候補を作る
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統

def 正準化(v):
 if isinstance(v,(set,frozenset)):return sorted(v)
 raise TypeError(type(v).__name__)
def 状態を読む(path,期待SHA=None):
 path=Path(path);h=hashlib.sha256()
 with tempfile.TemporaryDirectory()as td:
  raw=Path(td)/'state.json'
  opener=gzip.open if path.suffix=='.gz'else open
  with opener(path,'rb')as src,raw.open('wb')as dst:
   for b in iter(lambda:src.read(1048576),b''):h.update(b);dst.write(b)
  if 期待SHA is not None and h.hexdigest()!=期待SHA:raise ValueError('復号state SHA不一致')
  return HDS学習系統.読み込む(raw)
def 可逆保存(path,value):
 path=Path(path)
 if path.exists():raise FileExistsError('既存成果への上書き禁止: '+str(path))
 path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),default=正準化).encode();encoded=gzip.compress(raw,mtime=0) if path.suffix=='.gz'else raw
 if path.suffix=='.gz'and gzip.decompress(encoded)!=raw:raise IOError('gzip復号不一致')
 fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
 try:
  with os.fdopen(fd,'wb')as f:f.write(encoded);f.flush();os.fsync(f.fileno())
  os.link(tmp,path) # 競合時も既存成果を上書きしない
 finally:os.unlink(tmp)
 return {'出力':str(path),'復号SHA256':hashlib.sha256(raw).hexdigest(),'保存バイト':len(encoded)}
def main():
 a=argparse.ArgumentParser();a.add_argument('--状態',required=True);a.add_argument('--問題',required=True);a.add_argument('--出力',required=True);a.add_argument('--状態SHA');args=a.parse_args()
 if Path(args.出力).exists():raise FileExistsError(args.出力)
 mem=int(next(s.split()[1]for s in Path('/proc/meminfo').read_text().splitlines()if s.startswith('MemAvailable:')))
 if mem<2400000:raise RuntimeError('利用可能RAMが2.4GB未満。state読込を保留')
 if shutil.disk_usage(tempfile.gettempdir()).free<600*1024*1024:raise RuntimeError('一時状態復号のディスク余裕不足')
 with open(args.問題)as f:frame=json.load(f)
 h=状態を読む(args.状態,args.状態SHA);r=線標識候補を作る(frame,[1,2,3,4,5],h);print(json.dumps(可逆保存(args.出力,r),ensure_ascii=False))
if __name__=='__main__':main()
