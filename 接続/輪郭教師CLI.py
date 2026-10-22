"""公開661教師の再現用CLI。runtime入口は教材も実状態pathも読み込まない。"""
import argparse,gzip,json,hashlib,os,time,shutil,traceback
from .資源計測 import 最大常駐記憶量KiB
from pathlib import Path
from dataclasses import asdict
from .輪郭内部.モデル import 符号,照会

def 教師を読む():
 return json.loads(gzip.decompress((Path(__file__).resolve().parents[1]/'検証/輪郭配置/公開教師661.json.gz').read_bytes()))
def _save(h,out,name):
 tmp=out/(name+'.json.tmp');z=out/(name+'.json.gz.tmp');final=out/(name+'.json.gz');h.保存する(tmp);n=tmp.stat().st_size;check=hashlib.sha256()
 with tmp.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):check.update(b)
 digest=check.hexdigest()
 with tmp.open('rb')as src,gzip.open(z,'wb')as dst:shutil.copyfileobj(src,dst,1024*1024)
 check=hashlib.sha256()
 with gzip.open(z,'rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):check.update(b)
 assert check.hexdigest()==digest;os.replace(z,final);tmp.unlink();return {'経路':str(final),'展開bytes':n,'展開SHA256':digest,'圧縮bytes':final.stat().st_size}
def main():
 from hds学習系統 import HDS学習系統,外部入力
 p=argparse.ArgumentParser();p.add_argument('--教示',action='store_true');p.add_argument('--状態');p.add_argument('--盤面');p.add_argument('--出力',required=True);p.add_argument('--全段階',action='store_true');p.add_argument('--段階展開上限',type=int);a=p.parse_args();out=Path(a.出力);out.mkdir(exist_ok=False)
 if a.教示:
  plan=教師を読む();(out/'全入力計画.json').write_text(符号(plan));h=HDS学習系統();done=0;start=time.monotonic();report={'全計画数':len(plan['教師']),'保存':[]}
  try:
   with (out/'逐次入力.jsonl').open('x')as log:
    for i,t in enumerate(plan['教師'],1):
     if shutil.disk_usage(out).free<256*1024**2:raise RuntimeError('共用容量下限')
     log.write(符号({'段階':'投入前','番号':i,'教師':t})+'\n');log.flush();r=h.処理する(外部入力(t['内容'],t['境界']));done=i;log.write(符号({'段階':'投入後','番号':i,'結果':asdict(r)})+'\n');log.flush()
     if i%100==0:report['保存'].append(_save(h,out,'checkpoint'+str(i)))
   report['保存'].append(_save(h,out,'最終実状態'))
  except BaseException:
   report['例外']=traceback.format_exc();report['保存'].append(_save(h,out,'例外実状態'));raise
  finally:
   report.update({'完了入力数':done,'経過秒':time.monotonic()-start,'最大RSSKiB':最大常駐記憶量KiB()});(out/'資源結果.json').write_text(符号(report))
 else:
  if not a.状態:raise ValueError('--状態が必要。推論時は外部実状態を明示する')
  source=Path(a.状態)
  if source.suffix=='.gz':
   tmp=out/'入力実状態.json.tmp'
   with gzip.open(source,'rb')as src,tmp.open('wb')as dst:shutil.copyfileobj(src,dst,1024*1024)
   try:h=HDS学習系統.読み込む(tmp)
   finally:tmp.unlink()
  else:h=HDS学習系統.読み込む(source)
  plan=教師を読む()
 qs=[照会(h,b,json.loads(f))for b,f in sorted(set((t['境界'],t['内容']['前提'])for t in plan['教師']))];(out/'全73照会.json').write_text(符号(qs))
 if a.盤面:
  from .輪郭接続 import 輪郭候補を作る
  frame=json.loads(Path(a.盤面).read_text());r=輪郭候補を作る(frame,[1,2,3,4,5],h,経路も作る=a.全段階,段階展開上限=a.段階展開上限)
  with gzip.open(out/'全候補.json.gz','wt',encoding='utf-8')as f:json.dump(r,f,ensure_ascii=False,separators=(',',':'))
if __name__=='__main__':main()
