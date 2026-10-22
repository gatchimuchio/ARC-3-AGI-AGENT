"""明示的に起動したときだけ固定HDSへ94経験を教示する。runtimeから参照しない。"""
import argparse,gzip,json,hashlib,os,tempfile,copy
from datetime import datetime
from pathlib import Path
from hds学習系統 import HDS学習系統,外部入力
from 接続.証拠保存 import 証拠を確定する

def 意味SHA(data,d):
 normalized=copy.deepcopy(data)
 for entry in d['具体時刻位置']:
  path=entry['path'];node=normalized
  for k in path[:-1]:node=node[k]
  value=node[path[-1]]
  if not isinstance(value,str) or datetime.fromisoformat(value).tzinfo is None:raise ValueError('具体時刻位置がtimezone付き時刻でない')
  node[path[-1]]=entry['原時刻']
 return hashlib.sha256(json.dumps(normalized,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class 保存失敗(RuntimeError):
 def __init__(self,reason,record):super().__init__(reason);self.失敗記録=record

def 教示する(fixture):
 with gzip.open(fixture,'rt',encoding='utf-8') as f:d=json.load(f)
 ts=d['教師'];assert len(ts)==94 and [t['投入順'] for t in ts]==list(range(94))
 sources={s['session_id']:s['sha256'] for s in d['公開資料']}
 for t in ts:
  assert t['出所']['原資料SHA256']==sources[t['出所']['資料']]
  assert t['入力']['文脈']=={} and all(t['入力'][k] is None for k in ['主体','対象','目的'])
 h=HDS学習系統()
 for t in ts:
  for q in d['照会順']:
   if q['教師投入直前']==t['投入順']:h.照会する(外部入力(**q['入力']))
  h.処理する(外部入力(**t['入力']))
 return h,d

def _最終名へ確定する(temporary,output):
 証拠を確定する(temporary,output,置換を許可=False)

def 検証して新規保存する(h,d,output):
 output=Path(output)
 if output.exists():raise FileExistsError('既存状態を上書きしない')
 temporary=None
 try:
  with tempfile.NamedTemporaryFile(prefix='.'+output.name+'.未完-',dir=output.parent,delete=False) as f:temporary=Path(f.name)
  h.保存する(temporary)
  data=temporary.read_bytes();meaning=意味SHA(json.loads(data),d);sha=hashlib.sha256(data).hexdigest()
  if meaning!=d['具体時刻復元後SHA256']:raise AssertionError('時刻を除く全保存意味が原94と一致しない')
  # HDS公開読込でも保存形式の再読込を確認する。
  HDS学習系統.読み込む(temporary)
  # WindowsのFlushFileBuffersに必要な書込権限だけ確保し、内容は変更しない。
  with temporary.open('r+b') as f:os.fsync(f.fileno())
  _最終名へ確定する(temporary,output)
  temporary.unlink();temporary=None
  return {'具体1576時刻位置だけ復元した全保存意味一致':True,'保存意味SHA256':meaning,'入力数':94,'出力SHA256':sha,'原94完全一致':sha==d['原94保存SHA256']}
 except Exception as e:
  record={'理由':str(e),'型':type(e).__name__,'最終path':str(output),'未完証拠path':str(temporary) if temporary else None,'最終path存在':output.exists()}
  if temporary is not None:
   try:
    failure=temporary.with_name(temporary.name+'.失敗理由.json');failure.write_text(json.dumps(record,ensure_ascii=False,indent=2));record['失敗理由path']=str(failure)
   except Exception as save_error:record['失敗理由保存例外']=str(save_error)
  raise 保存失敗(str(e),record) from e

def main():
 p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,default=Path(__file__).with_name('巡回公開教師94.json.gz'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('既存状態を上書きしない')
 h,d=教示する(a.fixture);result=検証して新規保存する(h,d,a.output);result['fixtureSHA256']=hashlib.sha256(a.fixture.read_bytes()).hexdigest();print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except 保存失敗 as e:
  print(json.dumps({'保存HOLD':e.失敗記録},ensure_ascii=False));raise
