#!/usr/bin/env python3
"""既存の公開原票とrepoだけを読む。環境実行、通信、再学習、書込なし。"""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--teachers',type=Path,required=True);p.add_argument('--ledger',type=Path,default=Path(__file__).with_name('教材版適用境界.json'));a=p.parse_args()
d=json.loads(a.ledger.read_text());errors=[];checked=0

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
for name,expected in d['priorSHA256'].items():
 if sha(a.repo/'記憶/事前記憶/v0.4'/name)!=expected:errors.append('prior digest: '+name)
for family in d['7教示系']:
 if sha(a.repo/family['repo出所'])!=family['出所ファイルSHA256']:errors.append('family digest: '+family['教示系'])
refs={}
for level in d['全183索引枠']:
 for x in level['資料別最初候補']:refs.setdefault(x['原票session'],{}).setdefault(x['行0基準'],set()).add(x['末尾画素SHA256'])
for game in d['全25ゲーム']:
 for source in game['資料']:
  sid=source['公開原票URL'].rsplit('/',1)[-1];path=a.teachers/(sid+'.recording.jsonl');count=0;ids=set();wins=set();seen=set();hashes=hashlib.sha256()
  with path.open('rb') as f:
   for raw in f:
    hashes.update(raw)
    if not raw.strip():continue
    obj=json.loads(raw);r=obj.get('data',obj)
    if 'frame' not in r:continue
    if count in refs.get(sid,{}):
     actual=hashlib.sha256(json.dumps(r['frame'][-1],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
     if refs[sid][count]!={actual}:errors.append(f'pixel: {sid}:{count}')
     seen.add(count)
    ids.add(r.get('game_id'));wins.add(r.get('win_levels',r.get('win_score')));count+=1
  if hashes.hexdigest()!=source['SHA256']:errors.append('recording digest: '+sid)
  if count!=source['記録行数']:errors.append('recording rows: '+sid)
  if ids!=set(game['教材完全版ID']):errors.append('game version: '+sid)
  if wins!=set(source['win_levels']):errors.append('win levels: '+sid)
  if seen!=set(refs.get(sid,{})):errors.append('missing pixel references: '+sid)
  checked+=1
for extra in d['追加資料']:
 sid=extra['公開URL'].rsplit('/',1)[-1]
 if sha(a.teachers/(sid+'.recording.jsonl'))!=extra['SHA256']:errors.append('supplement digest: '+sid)
assert len(d['全25ゲーム'])==25 and len(d['全183索引枠'])==183
print(json.dumps({'主原票数':checked,'追加原票数':len(d['追加資料']),'不一致':errors,'現在環境実行':False,'学習':False,'変更':False},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
