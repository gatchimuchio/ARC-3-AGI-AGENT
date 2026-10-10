"""外部state未指定時は軽量境界のみ。実stateは明示env時に独立読込。"""
import os
import json
import unittest
import subprocess
import sys
from pathlib import Path
from 検証.関節線接続.検証する import STATE_ENV,COUNTER_ENV

def 独立過程で実行(kind):
    # ru_maxrss はプロセス全寿命の最大値。先行する別試験の高水位を
    # 本試験の950MiB上限と混同しないよう、同じCLIを直列の新規過程で実行する。
    root=Path(__file__).resolve().parents[1]
    completed=subprocess.run(
        [sys.executable,'-m','検証.関節線接続.検証する','--kind',kind],
        cwd=root,env=os.environ.copy(),capture_output=True,text=True)
    if completed.returncode:
        raise RuntimeError('独立検証過程が失敗: '+str(completed.returncode)+'\n'+completed.stdout+'\n'+completed.stderr)
    report=json.loads(completed.stdout)
    if report.get('kind')!=kind:
        raise AssertionError('検証種別が一致しない')
    return report

class 関節線portable検証(unittest.TestCase):
    def test_空状態と全候補境界(self):
        report=独立過程で実行('empty')
        self.assertTrue(all(r['採用可能照会']==0 for r in report['初期6問']))
        self.assertTrue(report['境界']['実行不可'])

    @unittest.skipUnless(os.environ.get(STATE_ENV),STATE_ENV+' 未設定: 実state未実施')
    def test_実1012r2の126照会と初期6問(self):
        report=独立過程で実行('real')
        self.assertEqual(len(report['全126']),126)
        self.assertTrue(report['Memory意味不変'])
        print(json.dumps(report,ensure_ascii=False),flush=True)

    @unittest.skipUnless(os.environ.get(COUNTER_ENV),COUNTER_ENV+' 未設定: 独立反証未実施')
    def test_独立反証の全HOLD(self):
        report=独立過程で実行('counter')
        self.assertTrue(all(r['採用可能照会']==0 for r in report['初期6問']))
        self.assertTrue(report['Memory意味不変'])
        print(json.dumps(report,ensure_ascii=False),flush=True)
