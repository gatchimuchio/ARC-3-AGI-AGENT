"""raw入口は公式盤面契約を照会前に確認する。学習性能の試験ではない。"""
import copy,json,pathlib,sys,unittest
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.字形 import 初回作用を構成する
from 接続.字形 import 初回作用 as module
class 照会禁止系:
 def __init__(self):self.count=0
 def 照会する(self,*args,**kwargs):self.count+=1;raise AssertionError('盤面guard前のHDS照会')
class 字形盤面境界試験(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.frame=json.loads((根/'検証/資料/字形/問題完成fixture.json').read_text())['問題群'][0]['問題盤面']
 def invalid(self,frame):
  h=照会禁止系();r=初回作用を構成する(h,frame,['RESET',1,'ACTION2',3,4,5,6,7]);self.assertEqual(h.count,0);self.assertEqual(r['適用性'],'未確認');self.assertFalse(r['照会記録']);self.assertFalse(r['目標候補群']);self.assertFalse(r['作用候補群']);self.assertFalse(r['実行許可'])
  domains=next(x['候補領域'] for x in r['関係群'] if x['関係']=='盤面不正時の全使用可能作用領域');self.assertEqual([x['作用番号'] for x in domains],list(range(8)));self.assertTrue(all(x['状態']=='HOLD' for x in domains));area=next(x['未評価座標候補領域'] for x in domains if x['作用番号']==6);self.assertIn('合法',area['集合']);self.assertNotIn('観測frame内全整数座標の部分域',area);self.assertIn('無効盤面',area['外部合法域']);return r
 def test_高さ65はHDS照会0で全作用保持(self):self.invalid(copy.deepcopy(self.frame)+[[3]*64])
 def test_幅65はHDS照会0で全作用保持(self):self.invalid([row+[3] for row in copy.deepcopy(self.frame)])
 def test_画素16と負数はHDS照会0(self):
  for value in (16,-1):
   with self.subTest(value=value):f=copy.deepcopy(self.frame);f[0][0]=value;self.invalid(f)
 def test_bool_float_strは厳密intとして通さない(self):
  for value in (True,False,1.0,'1',None):
   with self.subTest(value=value):f=copy.deepcopy(self.frame);f[0][0]=value;self.invalid(f)
 def test_非矩形と空盤面と空行と非配列(self):
  f=copy.deepcopy(self.frame);f[0].pop()
  for value in (f,[],[[]],None,'invalid'):
   with self.subTest(value_type=type(value).__name__):self.invalid(value)
 def test_合法tupleとlistは同じtuple盤面へ正規化(self):
  expected=tuple(tuple(row) for row in self.frame)
  for frame in (copy.deepcopy(self.frame),expected):
   seen=[]
   def observe_only(h,normalized):seen.append(normalized);return {'照会記録':[],'理由':'試験用知覚通過'}
   with patch.object(module,'条件付き手順',side_effect=observe_only):r=初回作用を構成する(照会禁止系(),frame,[1,2,3,4])
   self.assertEqual(seen,[expected]);self.assertTrue(all(type(row) is tuple for row in seen[0]));self.assertFalse(any(x['種別']=='入力/盤面境界' for x in r['保留理由群']))
