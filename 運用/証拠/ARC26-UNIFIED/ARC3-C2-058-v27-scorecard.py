from __future__ import annotations
import hashlib, inspect, json
from pathlib import Path
from typing import Any
from arc_agi.scorecard import EnvironmentScoreCalculator
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT/'運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-outputcheck-20261025T1412Z'
CONTROL=ROOT/'出力/ARC3-RUN-003-local/C2-046/kaggle-output/slim'
STATUS=ROOT/'運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-complete-20261025T141624Z.json'
OUTPUT=ROOT/'運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-terminal-scorecard-v3.json'
EXPECTED_CONTROL_MEAN=19.309155943771326
START_FIELDS=('board','board_ascii','level','title','run_status','score','state','type','reward')
def sha256(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def load(path:Path)->dict[str,Any]:
 x=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(x,dict):raise ValueError(f'expected object: {path}')
 return x
def manifest(folder:Path)->tuple[int,int,str]:
 rows=[];total=0
 for p in sorted(x for x in folder.rglob('*') if x.is_file()):
  rel=p.relative_to(folder).as_posix();size=p.stat().st_size;digest=sha256(p);total+=size
  rows.append(f'{rel}\0{digest}\0{size}\n')
 return len(rows),total,hashlib.sha256(''.join(rows).encode()).hexdigest()
def first_event(folder:Path,game_id:str)->dict[str,Any]:
 p=folder/'artifacts'/f'{game_id}_p0_events.jsonl'
 with p.open(encoding='utf-8') as f:row=json.loads(next(f))
 if not isinstance(row,dict):raise ValueError(f'invalid initial event: {p}')
 return row
def score_run(run:dict[str,Any])->float:
 actions=run.get('actions_per_level');baselines=run.get('base_actions_per_level');levels=run.get('number_of_levels');completed=run.get('levels_completed')
 if not isinstance(actions,list) or not isinstance(baselines,list):raise ValueError('missing action arrays')
 if len(actions)!=len(baselines) or len(actions)!=levels:raise ValueError('per-level arrays do not match number_of_levels')
 if type(completed)is not int or not 0<=completed<=len(actions):raise ValueError('invalid completed-level count')
 if any(type(x)is not int or x<0 for x in actions):raise ValueError('invalid candidate action count')
 if any(type(x)is not int or x<=0 for x in baselines):raise ValueError('invalid public baseline action count')
 c=EnvironmentScoreCalculator()
 for i,(count,base) in enumerate(zip(actions,baselines),1):c.add_level(level_index=i,completed=i<=completed,actions_taken=count,baseline_actions=base)
 return float(c.to_score(include_levels=True).score)
def main()->None:
 if OUTPUT.exists():raise SystemExit(f'refusing to overwrite {OUTPUT}')
 status=load(STATUS)
 if status.get('version')!=27 or status.get('status')!='KernelWorkerStatus.COMPLETE':raise ValueError('exact kernel version 27 is not terminal COMPLETE')
 cand_doc=load(CANDIDATE/'benchmark.json');ctrl_doc=load(CONTROL/'benchmark.json')
 cand_rows=cand_doc.get('game_runs');ctrl_rows=ctrl_doc.get('game_runs')
 if not isinstance(cand_rows,list) or not isinstance(ctrl_rows,list) or len(cand_rows)!=3 or len(ctrl_rows)!=3:raise ValueError('expected three candidate and three control runs')
 cand={str(x['game_id']):x for x in cand_rows};ctrl={str(x['game_id']):x for x in ctrl_rows}
 if len(cand)!=3 or len(ctrl)!=3 or set(cand)!=set(ctrl):raise ValueError(f'candidate/control game IDs differ: {set(cand)} vs {set(ctrl)}')
 checks={};cscores={};bscores={};paired={}
 for gid in sorted(cand):
  ce=first_event(CANDIDATE,gid);be=first_event(CONTROL,gid)
  gchecks={f: (f in ce and f in be and ce[f]==be[f]) for f in START_FIELDS}
  gchecks['all_initial_event_fields_match']=all(gchecks.values())
  gchecks['number_of_levels_match']=cand[gid].get('number_of_levels')==ctrl[gid].get('number_of_levels')
  gchecks['public_baseline_actions_match']=cand[gid].get('base_actions_per_level')==ctrl[gid].get('base_actions_per_level')
  if not all(gchecks.values()):raise ValueError(f'paired initial conditions differ for {gid}: {gchecks}')
  cscore=score_run(cand[gid]);bscore=score_run(ctrl[gid])
  if abs(cscore-float(cand[gid]['final_score']))>1e-9:raise ValueError(f'candidate saved score mismatch {gid}')
  if abs(bscore-float(ctrl[gid]['final_score']))>1e-9:raise ValueError(f'control saved score mismatch {gid}')
  cscores[gid]=cscore;bscores[gid]=bscore;paired[gid]=cscore-bscore;checks[gid]=gchecks
 cmean=sum(cscores.values())/3;bmean=sum(bscores.values())/3;delta=cmean-bmean
 if abs(bmean-EXPECTED_CONTROL_MEAN)>1e-9:raise ValueError(f'C2-046 reference mean mismatch: {bmean}')
 cmetrics={gid:{'state':r.get('state'),'levels_completed':r.get('levels_completed'),'levels_total':r.get('number_of_levels'),'score':cscores[gid],'actions':sum(r['actions_per_level']),'generated_tokens_reported_field':r.get('final_generated_tokens'),'generated_tokens_history_sum':sum(int(x.get('generated_tokens') or 0) for x in r.get('history',[])),'uncached_input_tokens_history_sum':sum(int(x.get('uncached_input_tokens') or 0) for x in r.get('history',[])),'wallclock_seconds':r.get('final_wallclock_seconds')} for gid,r in cand.items()}
 bmetrics={gid:{'state':r.get('state'),'levels_completed':r.get('levels_completed'),'levels_total':r.get('number_of_levels'),'score':bscores[gid],'actions':sum(r['actions_per_level']),'generated_tokens_reported_field':r.get('final_generated_tokens'),'generated_tokens_history_sum':sum(int(x.get('generated_tokens') or 0) for x in r.get('history',[])),'uncached_input_tokens_history_sum':sum(int(x.get('uncached_input_tokens') or 0) for x in r.get('history',[])),'wallclock_seconds':r.get('final_wallclock_seconds')} for gid,r in ctrl.items()}
 ccount,cbytes,cmanifest=manifest(CANDIDATE);scorer=Path(inspect.getsourcefile(EnvironmentScoreCalculator) or '')
 result={'schema':'arc26-arc3-private-kernel-terminal-scorecard.v1','track':'ARC3','experiment_id':'ARC3-RUN-003/C2-058','kernel':'tecchannn/arc3-model-guided-c2-025','version':27,'status_evidence':STATUS.relative_to(ROOT).as_posix(),'candidate_notebook_sha256':'b72c8105c1916337d6016e224762afe3d9a0c3be24a4abb539b83591e6ca48d0','candidate_output_directory':CANDIDATE.relative_to(ROOT).as_posix(),'candidate_output_file_count':ccount,'candidate_output_total_bytes':cbytes,'candidate_output_manifest_sha256':cmanifest,'candidate_benchmark_sha256':sha256(CANDIDATE/'benchmark.json'),'control':'C2-046 slim','control_output_directory':CONTROL.relative_to(ROOT).as_posix(),'control_benchmark_sha256':sha256(CONTROL/'benchmark.json'),'score_source':'arc_agi.scorecard.EnvironmentScoreCalculator','score_source_file':scorer.relative_to(ROOT).as_posix(),'score_source_file_sha256':sha256(scorer),'scorecard_source_sha256':sha256(Path(__file__).resolve()),'paired_games':3,'paired_start_checks':checks,'candidate_per_game':cmetrics,'control_per_game':bmetrics,'candidate_scores':cscores,'control_scores':bscores,'paired_deltas':paired,'candidate_mean':cmean,'control_mean':bmean,'paired_mean_delta':delta,'improved_unchanged_regressed':[sum(x>1e-9 for x in paired.values()),sum(abs(x)<=1e-9 for x in paired.values()),sum(x<-1e-9 for x in paired.values())],'candidate_levels_completed':sum(int(r['levels_completed']) for r in cand.values()),'control_levels_completed':sum(int(r['levels_completed']) for r in ctrl.values()),'candidate_total_actions':sum(sum(r['actions_per_level']) for r in cand.values()),'control_total_actions':sum(sum(r['actions_per_level']) for r in ctrl.values()),'candidate_total_generated_tokens':sum(sum(int(x.get('generated_tokens') or 0) for x in r.get('history',[])) for r in cand.values()),'control_total_generated_tokens':sum(sum(int(x.get('generated_tokens') or 0) for x in r.get('history',[])) for r in ctrl.values()),'candidate_run_states':{s:sum(r.get('state')==s for r in cand.values()) for s in sorted({str(r.get('state')) for r in cand.values()})},'candidate_saved_scores_match_recomputed':True,'control_saved_scores_match_recomputed':True,'acceptance':'candidate mean > 19.309155943771326 and paired mean delta > 0','decision':'ACCEPT_LOCAL_CANDIDATE' if cmean>EXPECTED_CONTROL_MEAN and delta>0 else 'REJECT_C2-058','official_submission_or_quota_use':False,'supersedes':['ARC3-C2-058-v27-terminal-scorecard.json','ARC3-C2-058-v27-terminal-scorecard-v2.json'],'correction_note':'v1 had zero token fields, and v2 per-game control token fields were not history sums. v3 reports per-action history sums for both runs.','note':'Kaggle requests.jsonl download is partial; the local score uses complete benchmark.json and paired initial event records, not the request transcript.'}
 OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()