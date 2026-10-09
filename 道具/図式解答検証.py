"""明示した公開記録の見本→HDS→未投入問題の解答を照合する。ネット接続なし。"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.図式解答教師 import パネルを検出する,見本を選ぶ,見本を教える,解答を構成する,方針を教える,作用方針を構成する

from 接続.図式作用教師 import 記録から作用教師を読む,作用を教える,許容色までの作用候補,色列,攻略候補を構成する

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--teacher-row',type=int,required=True);p.add_argument('--problem-row',type=int,required=True);p.add_argument('--answer-row',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--policy-teacher-answer-row',type=int)
    p.add_argument('--action-teacher-manifest',type=Path)
    a=p.parse_args();raw=a.source.read_bytes()
    if sha256(raw).hexdigest()!=a.sha256:raise ValueError('原票digest不一致')
    rows=[json.loads(s).get('data',json.loads(s)) for s in raw.decode().splitlines() if s.strip()]
    t,b,e=[rows[i] for i in (a.teacher_row,a.problem_row,a.answer_row)]
    if len({(v['guid'],v['game_id']) for v in (t,b,e)})!=1:raise ValueError('instance/game版境界')
    if not a.teacher_row<a.problem_row<a.answer_row:raise ValueError('教師・問題・解答の行順')
    if e['levels_completed']!=b['levels_completed']+1:raise ValueError('実成功遷移の裏付けがない解答')
    panels,rejected=パネルを検出する(t['frame'][-1]);refs=見本を選ぶ(t['frame'][-1],panels)
    if not refs:raise ValueError('公開画面から完成見本のroleを区別できない')
    h=HDS学習系統();training=見本を教える(h,refs)
    policy_training=None
    if a.policy_teacher_answer_row is not None:
        n=a.policy_teacher_answer_row;pa=rows[n]
        if not a.teacher_row<n<=a.problem_row or (pa['guid'],pa['game_id'])!=(t['guid'],t['game_id']) or pa['levels_completed']!=t['levels_completed']+1:raise ValueError('保持変更の教師範囲不正')
        policy_training=方針を教える(h,t['frame'][-1],pa['frame'][0])
    action_training=[];action_holds=[]
    if a.action_teacher_manifest:
        for entry in json.loads(a.action_teacher_manifest.read_text()):
            ts,hs=記録から作用教師を読む(entry['path'],entry['sha256'],entry['start'],entry['end'])
            action_training.extend(ts);action_holds.extend(hs)
        action_training=作用を教える(h,action_training)
    # 問題側の完成解答frameは学習/照会へ渡さない。
    empty=解答を構成する(HDS学習系統(),b['frame'][-1]);result=解答を構成する(h,b['frame'][-1])
    checks=[]
    for c in result['解答セル']:
        x,y=c['位置'];w=c['幅'];actual={v for row in e['frame'][0][y:y+w] for v in row[x:x+w]}
        checks.append({'位置':[x,y],'予測色':c['解答色'],'実解答色':sorted(actual),'一致':actual=={c['解答色']}})
    a.output.mkdir(parents=True,exist_ok=False)
    artifacts={'教師':training,'空HDS':empty,'推論解答':result,'解答照合':checks,
               '原理':{'有効':[asdict(x) for x in h.エンジン._有効原理群()],'隔離':[asdict(x) for x in h.エンジン._係争中原理群()]},
               '出所':{'path':str(a.source),'SHA256':a.sha256,'game_id':b['game_id'],'guid':b['guid'],'teacher_row':a.teacher_row,'problem_row':a.problem_row,'answer_row':a.answer_row,'解答frame':0,'見本数':len(refs),'教師適用外':rejected,'最終未見評価':False,'fresh実行':False,
                        'code_SHA256':{str(f.relative_to(ROOT)):sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),ROOT/'接続/図式解答教師.py',ROOT/'接続/図式作用教師.py',ROOT/'接続/図式観測.py',*(ROOT/'HDS/学習系統/v0.4.2').rglob('*.py')]}}}
    if policy_training is not None:
        artifacts['方針教師']={'教師':policy_training[0],'適用外':policy_training[1],'完成答え行':a.policy_teacher_answer_row}
        artifacts['作用方針']=作用方針を構成する(h,b['frame'][-1])
    if a.action_teacher_manifest:
        artifacts['作用教師']={'教師':action_training,'適用外':action_holds,'manifest':json.loads(a.action_teacher_manifest.read_text())}
        if policy_training is not None:
            palette=色列(b['frame'][-1])
            artifacts['作用候補']=[{'位置':c['位置'],'幅':c['幅'],**許容色までの作用候補(h,palette,c['現在色'],c['許容色'])} for c in artifacts['作用方針']['変更対象']] if palette else []
        artifacts['統合攻略候補']=攻略候補を構成する(h,b['frame'][-1])
        unified_checks=[]
        for c in artifacts['統合攻略候補']['対象セル']:
            x,y=c['位置'];w=c['幅'];actual={v for row in e['frame'][0][y:y+w] for v in row[x:x+w]}
            unified_checks.append({'位置':[x,y],'候補色':c['到達候補色'],'全解答制約充足':c['全制約充足'],'公式完成色':sorted(actual),'完成例一致':actual=={c['到達候補色']}})
        artifacts['統合完成例照合']=unified_checks
    for name,value in artifacts.items():(a.output/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    h.保存する(a.output/'HDS状態.json')
    print(json.dumps({'教師セル':len(training),'制約':len(result['照会']),'解答セル':len(checks),'解答一致':sum(c['一致'] for c in checks),'HOLD':len(result['HOLDセル']),'クリック対象':len(result['クリック対象']),'状態':result['状態']},ensure_ascii=False))


if __name__=='__main__':main()
