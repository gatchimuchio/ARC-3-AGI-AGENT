"""配色教材の入力順・処理結果・保存を保持する。既定は保存状態の読込。"""
from pathlib import Path
import sys,json,gzip,tempfile,hashlib,os,argparse,time
from .資源計測 import 最大常駐記憶量KiB
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from dataclasses import asdict
from .鏡像教師CLI import 結果保存 as _通常結果保存
教材根=ROOT/'入力/配色教師'

def 資料を読む(name):return json.loads(gzip.decompress((教材根/name).read_bytes()))

def 保存状態を読む(path=None):
 p=Path(path) if path else 教材根/'保存HDS.json.gz'
 if p.suffix!='.gz':return HDS学習系統.読み込む(p)
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)/'状態.json';q.write_bytes(gzip.decompress(p.read_bytes()));return HDS学習系統.読み込む(q)

def 確認保存(hds,path):
 path=Path(path)
 with tempfile.TemporaryDirectory(dir=path.parent) as d:
  p=Path(d)/'状態.json';hds.保存する(p)
  if not p.is_file() or not p.stat().st_size:raise OSError('HDS実状態未保存')
  HDS学習系統.読み込む(p)
  raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest();q=Path(d)/'保存物'
  q.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw)
  recovered=gzip.decompress(q.read_bytes()) if path.suffix=='.gz' else q.read_bytes()
  if hashlib.sha256(recovered).hexdigest()!=digest:raise OSError('保存内容の復号SHA不一致')
  os.replace(q,path)
 return {'保存完了':True,'復号SHA256':digest,'保存SHA256':hashlib.sha256(path.read_bytes()).hexdigest()}

def 教材を教える(records,hds=None,*,逐次記録=None,checkpoint=None):
 hds=HDS学習系統() if hds is None else hds
 for i,r in enumerate(records,1):
  if 逐次記録:逐次記録({'順序':i,'教師':r})
  result=hds.処理する(外部入力(r['内容'],r['境界']))
  if 逐次記録:逐次記録({'結果順序':i,'結果':asdict(result)})
  if checkpoint and (i%100==0 or i==len(records)):checkpoint(hds,i)
 return hds

def 検証する(hds,*,全原票=False):
 from .配色接続 import 配色候補を作る,配色全応答を照合
 from .配色内部.知覚 import read
 raw=資料を読む('公開原票.json.gz');pairs=資料を読む('問題と完成.json.gz');problems=[]
 for p in pairs:
  if p['資料']!=0:continue
  f=raw[0]['全行'][p['初期行']]['data']['frame'][-1];r=配色候補を作る(f,[1,2,3,4,5,6],hds)
  paths=r['全代表経路'];成立=bool(paths) and all(x['目標一致'] and not x['保留'] for x in paths)
  problems.append({'初期行':p['初期行'],'再構成':r,'モデル終端検査':{'状態':'条件付きモデル成立' if 成立 else '未成立/HOLD','非空経路':bool(paths),'代表目標全一致':成立}})
 out={'全問題':problems,'実行許可':False,'再学習なし':True}
 if 全原票:
  reports=[]
  for source in raw:
   history=None;rows=source['全行']
   for i in range(1,len(rows)):
    a,b=rows[i-1]['data'],rows[i]['data'];r=配色全応答を照合(a,b,b.get('action_input'),hds,観測履歴=history,前通番=i-1,後通番=i)
    reports.append({'資料':source['来歴'],'行':i,'全応答照合':r});history=r.get('次履歴')
  out['全原票照合']=reports
 # 完成答えは構成後の評価にだけ使う。
 from .配色内部.受理 import alternatives
 from .配色内部.固定文法 import 受理文法
 completion=[]
 for pair in pairs:
  frame=raw[pair['資料']]['全行'][pair['初期行']]['data']['frame'][-1]
  scene=read(frame);candidates=alternatives(hds,scene,受理文法);answer=pair['終端候補'][-1][1]['対象'];matches=[]
  for i,c in enumerate(candidates['全条件付き代替']):
   canvas=[row[:] for row in scene['参照']]
   for x,y in c['変更座標']:canvas[y][x]=c['色']
   if canvas==answer:matches.append(i)
  completion.append({'資料':pair['資料'],'完成行':pair['完了行'],'一致画素数':pair['一致画素数'],'事後包含候補番号':matches,'実完成':answer})
 out['完成事後包含']=completion
 out['集計']={'問題数':len(problems),'経路数':sum(len(x['再構成']['全代表経路']) for x in problems),'全段':sum(len(p['全段']) for x in problems for p in x['再構成']['全代表経路'])}
 return out

def 結果保存(path,value):
 path=Path(path)
 if path.suffix!='.gz':return _通常結果保存(path,value)
 with tempfile.TemporaryDirectory(dir=path.parent) as d:
  p=Path(d)/'結果.json.gz'
  with gzip.open(p,'wt',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,separators=(',',':'))
  with gzip.open(p,'rt',encoding='utf-8') as f:json.load(f)
  os.replace(p,path)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--全再学習',action='store_true');ap.add_argument('--保存状態',type=Path);ap.add_argument('--状態出力',type=Path);ap.add_argument('--出力',required=True,type=Path);ap.add_argument('--全原票',action='store_true');a=ap.parse_args()
 if a.全再学習 and (a.保存状態 or not a.状態出力):ap.error('再学習は読込と排他、状態出力を必須とする')
 start=time.perf_counter()
 if a.全再学習:
  h=HDS学習系統()
  with a.出力.with_suffix('.入力.jsonl').open('x') as f:
   def log(r):f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
   def checkpoint(h,i):log({'途中保存':i,**確認保存(h,a.状態出力.with_name(a.状態出力.name+f'.{i}.gz'))})
   try:h=教材を教える(資料を読む('関係教材.json.gz'),h,逐次記録=log,checkpoint=checkpoint)
   except Exception as exc:
    log({'状態':'中断','例外':repr(exc)})
    try:確認保存(h,a.状態出力.with_name(a.状態出力.name+'.中断.gz'))
    except Exception as err:log({'状態':'中断保存失敗','例外':repr(err)})
    raise
 else:h=保存状態を読む(a.保存状態)
 result=検証する(h,全原票=a.全原票)
 if a.状態出力:result['保存']=確認保存(h,a.状態出力)
 result['再学習なし']=not a.全再学習;result['資源']={'秒':time.perf_counter()-start,'peak_RSS_KiB':最大常駐記憶量KiB()}
 結果保存(a.出力,result);print(json.dumps(result['集計'],ensure_ascii=False))
if __name__=='__main__':main()
