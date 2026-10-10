"""字形教師の公開HDS投入/保存済み実状態検証。既定で再学習しない。"""
import argparse,hashlib,json,resource,sys,time
from dataclasses import asdict
from pathlib import Path
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統,外部入力
from 接続.字形.欄観測 import query

資料=根/'検証/資料/字形'
正本SHA='d8a50812c89cacf62edf088c0e9bf81bf93f32823df3c269cecec5b373511275'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def 検証(path):
 if digest(path)!=正本SHA:raise ValueError('承認済み全1992入力stateのSHAと異なる')
 h=HDS学習系統.読み込む(path);p=json.loads((資料/'保存状態54照会.json').read_text());reports=[]
 for (b,x,y),expected in zip(p['仕様'],p['期待']):
  value,q=query(h,x,b,y);row={'境界':b,'条件':x,'結果':value,'状態':q['状態'],'競合':q['内容'].get('競合群',[]),'係争':q['内容'].get('係争中原理群',[])}
  reports.append({'実測':row,'期待':expected,'一致':row==expected})
 assert len(reports)==54 and all(r['一致'] for r in reports)
 return {'状態':'保存実状態の54照会一致','再学習':False,'照会群':reports,'実行許可':False}
def 全量教示(dest):
 dest.mkdir(parents=True,exist_ok=False);teachers=json.loads((資料/'全1992教師.json').read_text())['教師群'];assert len(teachers)==1992
 h=HDS学習系統();start=time.perf_counter();count=0
 specs=json.loads((資料/'保存状態54照会.json').read_text())['仕様']
 with (dest/'運転記録.jsonl').open('x') as f:
  def log(x):f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush()
  def save(name):
   t=time.perf_counter();p=dest/name;h.保存する(p);log({'実記憶保存':name,'入力済み数':count,'保存バイト数':p.stat().st_size,'秒':time.perf_counter()-t,'SHA256':digest(p),'プロセス最大常駐KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
  try:
   for i,t in enumerate(teachers,1):
    log({'入力開始':i,'教師':t});r=h.処理する(外部入力(t['内容'],t['境界']));count=i;log({'入力完了':i,'全処理結果':asdict(r)})
    if i in (391,1992):
     if i==391:save('実状態_'+str(i)+'.json')
     # 承認済み全量runと同じ前後54照会順。教師数/内容を変えない。
     for b,x,y in specs:
      value,q=query(h,x,b,y);log({'段階':'作用保存教示前' if i==391 else '作用保存教示後','照会境界':b,'条件':x,'結果名':y,'予測':value,'HDS照会':q})
     if i==1992:save('実状態_'+str(i)+'.json')
    elif i in (791,1191,1591):save('実状態_'+str(i)+'.json')
   result={'状態':'全量教示保存完了','HDS入力数':count,'経過秒':time.perf_counter()-start,'プロセス最大常駐KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'実行許可':False};log(result);return result
  except BaseException as e:
   log({'処理例外':type(e).__name__,'内容':str(e),'入力済み数':count})
   try:save('例外実状態.json')
   except BaseException as se:log({'例外時保存失敗':type(se).__name__,'内容':str(se)})
   raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--方式',choices=['保存検証','全量教示'],default='保存検証');p.add_argument('--状態',type=Path);p.add_argument('--出力先',type=Path);a=p.parse_args()
 if a.方式=='保存検証':
  if not a.状態:p.error('保存検証には--状態が必要。既定で再学習しない')
  result=検証(a.状態)
 else:
  if not a.出力先:p.error('全量教示には未作成の--出力先が必要')
  result=全量教示(a.出力先)
 print(json.dumps(result,ensure_ascii=False))
