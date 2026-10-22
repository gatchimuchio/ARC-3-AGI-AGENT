"""明示起動専用268教示CLI。runtimeから参照しない。core不変・新規保存限定。"""
import argparse,gzip,json,hashlib,os,tempfile,uuid,gc,time,sys
from 接続.資源計測 import 最大常駐記憶量KiB
from 接続.証拠保存 import 証拠を確定する
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from hds学習系統 import HDS学習系統,外部入力
if __package__:
 from .同形式保存 import 同形式JSON,遅延値,全内容
else:
 from 同形式保存 import 同形式JSON,遅延値,全内容

class 保存失敗(RuntimeError):
 def __init__(self,reason,record):super().__init__(reason);self.失敗記録=record

def _失敗(reason,output,temporary=None):
 record={'理由':str(reason),'型':type(reason).__name__,'最終path':str(output),'未完証拠path':str(temporary)if temporary else None,'最終path存在':Path(output).exists(),'成功':False}
 try:
  p=Path(output).with_name('.'+Path(output).name+'.'+uuid.uuid4().hex+'.失敗.json')
  with p.open('x',encoding='utf8')as f:json.dump(record,f,ensure_ascii=False,indent=2)
  record['失敗理由path']=str(p)
 except Exception as exc:record['失敗理由保存例外']=str(exc)
 return 保存失敗(str(reason),record)

def _新規先(output):
 output=Path(output)
 if output.exists():raise _失敗(FileExistsError('既存状態を上書きしない'),output)
 if not output.parent.is_dir():raise _失敗(FileNotFoundError('保存先親dirがない'),output)
 return output

def _bytes(h):
 for s in 同形式JSON(ensure_ascii=False,separators=(',',':')).iterencode(遅延値(全内容(h))):yield s.encode('utf8')

def _圧縮仮保存(h,path):
 sha=hashlib.sha256();size=0
 with gzip.open(path,'wb')as f:
  buf=bytearray()
  for b in _bytes(h):
   buf.extend(b)
   if len(buf)>=65536:sha.update(buf);size+=len(buf);f.write(buf);buf.clear()
  if buf:sha.update(buf);size+=len(buf);f.write(buf)
 return sha.hexdigest(),size

def 意味SHA(data,d):
 """比較専用にparseしたJSONだけを変更。具体leaf以外は一切除外しない。"""
 seen=set()
 for entry in d['具体時刻位置']:
  path=entry['path'];key=tuple(path)
  if key in seen:raise ValueError('時刻leaf位置の重複')
  seen.add(key);node=data
  for k in path[:-1]:node=node[k]
  value=node[path[-1]]
  if not isinstance(value,str)or datetime.fromisoformat(value).tzinfo is None:raise ValueError('指定leafがtimezone付き時刻でない')
  node[path[-1]]=entry['原時刻']
 sha=hashlib.sha256()
 for s in json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':')).iterencode(data):sha.update(s.encode())
 return sha.hexdigest()

def _標準再読込(path):
 path=Path(path);original=Path.read_text
 def read(p,*args,**kw):
  if p==path:
   with gzip.open(p,'rt',encoding='utf8')as f:return f.read()
  return original(p,*args,**kw)
 with patch.object(Path,'read_text',read):return HDS学習系統.読み込む(path)

def _最終名へ確定する(temporary,output):
 証拠を確定する(temporary,output,置換を許可=False)

def 検証して新規保存する(h,d,output):
 output=_新規先(output);temporary=None
 try:
  with tempfile.NamedTemporaryFile(prefix='.'+output.name+'.未完-',suffix='.gz',dir=output.parent,delete=False)as f:temporary=Path(f.name)
  sha,size=_圧縮仮保存(h,temporary)
  decoded=hashlib.sha256();count=0
  with gzip.open(temporary,'rb')as f:
   for b in iter(lambda:f.read(65536),b''):decoded.update(b);count+=len(b)
  if sha!=decoded.hexdigest()or size!=count or not count:raise ValueError('保存全byte復号SHA/size不一致')
  with gzip.open(temporary,'rt')as f:data=json.load(f)
  meaning=意味SHA(data,d);del data;gc.collect()
  if meaning!=d['具体時刻復元後SHA256']:raise ValueError('具体時刻leaf以外の全保存内容が原268と一致しない')
  reloaded=_標準再読込(temporary)
  again=hashlib.sha256()
  for b in _bytes(reloaded):again.update(b)
  del reloaded;gc.collect()
  if again.hexdigest()!=sha:raise ValueError('標準core再読込後の全型/全byte再符号化が不一致')
  # WindowsのFlushFileBuffersは書込権限が必要。内容はここでは変更しない。
  with temporary.open('r+b')as f:os.fsync(f.fileno())
  _最終名へ確定する(temporary,output)
  temporary.unlink();temporary=None
  return {'成功':True,'入力数':268,'保存意味SHA256':meaning,'原268と具体時刻leaf以外全一致':True,'全型標準再読込再符号化一致':True,'復号SHA256':sha,'復号bytes':size,'gzipbytes':output.stat().st_size,'具体時刻leaf数':len(d['具体時刻位置']),'原268復号byte一致':sha==d['原state復号SHA256']}
 except Exception as exc:raise _失敗(exc,output,temporary)from exc

def 教示する(fixture,progress=None):
 with gzip.open(fixture,'rt',encoding='utf8')as f:d=json.load(f)
 ts=d['教師'];assert len(ts)==268 and[t['投入順']for t in ts]==list(range(268));assert d['事前照会順']==[]
 sources={x['sha256']for x in d['公開資料']};seen=set()
 for t in ts:
  x=t['入力'];assert set(x)=={'内容','対象系境界','主体','対象','目的','文脈'}and x['文脈']=={}and all(x[k]is None for k in('主体','対象','目的'))
  raw=t['全由来'][0]['原票SHA256'];assert raw in sources and all(r['原票SHA256']==raw for r in t['全由来'])
  key=(raw,x['対象系境界'],json.dumps(x['内容'],ensure_ascii=False,sort_keys=True,separators=(',',':')));assert key not in seen;seen.add(key)
 h=HDS学習系統()
 for t in ts:
  result=h.処理する(外部入力(**t['入力']))
  if progress:progress({'投入順':t['投入順'],'入力':t['入力'],'全由来':t['全由来'],'状態':result.状態,'内容':result.内容,'追跡情報':result.追跡情報})
 return h,d

def アドレス空間制限を設定する():
 """350MiBの実制限を要求する。対応外OSで無制限の再学習へ代替しない。"""
 if sys.platform!='linux':
  raise RuntimeError('350MiB制限付き連動教示はLinux専用。WindowsではWSL/Linuxを使用してください。')
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(350*1024*1024,350*1024*1024))

def main():
 start=time.monotonic()
 p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,default=Path(__file__).with_name('公開教師268.json.gz'));p.add_argument('--output',type=Path,required=True);p.add_argument('--log',type=Path,required=True);a=p.parse_args()
 try:
  アドレス空間制限を設定する()
  _新規先(a.output)
  if a.log.exists():raise _失敗(FileExistsError('逐次logを上書きしない'),a.output)
  with a.log.open('xb')as raw,gzip.GzipFile(fileobj=raw,mode='wb')as log:
   def progress(r):log.write((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode());log.flush()
   h,d=教示する(a.fixture,progress)
  result=検証して新規保存する(h,d,a.output);result.update({'fixtureSHA256':hashlib.sha256(a.fixture.read_bytes()).hexdigest(),'秒':time.monotonic()-start,'最大RSSKiB':最大常駐記憶量KiB(),'追加学習対象':'独立空系のみ。旧268/現mainstate不変','実行許可':False});print(json.dumps(result,ensure_ascii=False))
 except 保存失敗:raise
 except Exception as exc:raise _失敗(exc,a.output,a.log if a.log.exists()else None)from exc

if __name__=='__main__':
 try:main()
 except 保存失敗 as exc:print(json.dumps({'保存HOLD':exc.失敗記録},ensure_ascii=False));raise
