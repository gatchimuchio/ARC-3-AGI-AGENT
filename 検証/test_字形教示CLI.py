"""CLIの全入力/保存/例外記録の配線試験。学習性能の評価ではない。"""
import json,pathlib,sys,tempfile,unittest
from dataclasses import dataclass
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 道具 import 字形教示検証 as cli
@dataclass
class 処理結果:
 状態:str='試験用応答'
class 配線用系:
 def __init__(self,fail=None):self.inputs=[];self.saves=[];self.fail=fail
 def 処理する(self,x):
  if self.fail==len(self.inputs)+1:raise RuntimeError('試験用処理例外')
  self.inputs.append((x.対象系境界,x.内容));return 処理結果()
 def 保存する(self,p):self.saves.append(len(self.inputs));p.write_text(json.dumps({'試験入力数':len(self.inputs)}))
class 全量CLI配線試験(unittest.TestCase):
 def test_全1992入力順と前後照会保存位置(self):
  h=配線用系();calls=[]
  def q(model,x,b,y):calls.append((len(h.inputs),b,x,y));return None,{'試験用照会':True}
  with tempfile.TemporaryDirectory() as tmp,patch.object(cli,'HDS学習系統',return_value=h),patch.object(cli,'query',side_effect=q):
   dest=pathlib.Path(tmp)/'new';r=cli.全量教示(dest);records=[json.loads(x) for x in (dest/'運転記録.jsonl').read_text().splitlines()]
  teachers=json.loads((cli.資料/'全1992教師.json').read_text())['教師群'];self.assertEqual(h.inputs,[(t['境界'],t['内容']) for t in teachers]);self.assertEqual(h.saves,[391,791,1191,1591,1992]);self.assertEqual([n for n,*_ in calls],[391]*54+[1992]*54);self.assertEqual(sum('入力開始' in x for x in records),1992);self.assertEqual(sum('入力完了' in x for x in records),1992);self.assertEqual(r['HDS入力数'],1992)
 def test_例外までの全入力結果と実状態保存(self):
  h=配線用系(fail=12)
  with tempfile.TemporaryDirectory() as tmp,patch.object(cli,'HDS学習系統',return_value=h):
   dest=pathlib.Path(tmp)/'new'
   with self.assertRaises(RuntimeError):cli.全量教示(dest)
   records=[json.loads(x) for x in (dest/'運転記録.jsonl').read_text().splitlines()];self.assertTrue((dest/'例外実状態.json').exists())
  self.assertEqual(h.saves,[11]);self.assertEqual(sum('入力開始' in x for x in records),12);self.assertEqual(sum('入力完了' in x for x in records),11);self.assertTrue(any('処理例外' in x for x in records))
