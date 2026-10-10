import importlib.util,pathlib,tempfile,unittest,hashlib,json
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('巡回公開教師を教示.py');spec=importlib.util.spec_from_file_location('teacher',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
GOOD={'具体時刻位置':[],'具体時刻復元後SHA256':hashlib.sha256(b'{}').hexdigest(),'原94保存SHA256':'x'}
class 保存境界(unittest.TestCase):
 def evidence(self,td,caught,raw):
  r=caught.exception.失敗記録;p=pathlib.Path(r['未完証拠path']);self.assertEqual(p.read_text(),raw);self.assertTrue(pathlib.Path(r['失敗理由path']).exists());self.assertFalse((pathlib.Path(td)/'state.json').exists())
 def test_途中書込例外は別証拠保持(self):
  class Failed:
   def 保存する(self,p):p.write_text('{');raise OSError('人工部分保存故障')
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(m.保存失敗) as caught:m.検証して新規保存する(Failed(),{},pathlib.Path(td)/'state.json')
   self.evidence(td,caught,'{')
 def test_意味不一致は別証拠保持(self):
  class Failed:
   def 保存する(self,p):p.write_text('{}')
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(m.保存失敗) as caught:m.検証して新規保存する(Failed(),{**GOOD,'具体時刻復元後SHA256':'wrong'},pathlib.Path(td)/'state.json')
   self.evidence(td,caught,'{}')
 def test_既存ファイル不変(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'state.json';p.write_text('既存')
   with self.assertRaises(FileExistsError):m.検証して新規保存する(None,{},p)
   self.assertEqual(p.read_text(),'既存')
 def test_確定時競合も上書きしない(self):
  class Fake:
   def 保存する(self,p):p.write_text('{}')
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'state.json';real=m.os.link
   def raced(src,dst):p.write_text('競合');return real(src,dst)
   with patch.object(m.HDS学習系統,'読み込む',return_value=None),patch.object(m.os,'link',side_effect=raced):
    with self.assertRaises(m.保存失敗) as caught:m.検証して新規保存する(Fake(),GOOD,p)
   self.assertEqual(p.read_text(),'競合');self.assertEqual(pathlib.Path(caught.exception.失敗記録['未完証拠path']).read_text(),'{}')
 def test_標準再読込故障も未確定(self):
  class Fake:
   def 保存する(self,p):p.write_text('{}')
  with tempfile.TemporaryDirectory() as td,patch.object(m.HDS学習系統,'読み込む',side_effect=ValueError('標準読込失敗')):
   with self.assertRaises(m.保存失敗) as caught:m.検証して新規保存する(Fake(),GOOD,pathlib.Path(td)/'state.json')
   self.evidence(td,caught,'{}')
 def test_指定外時刻も意味差分として検出(self):
  d={'具体時刻位置':[{'path':['x'],'原時刻':'2026-01-01T00:00:00+00:00'}]};a={'x':'2026-01-02T00:00:00+00:00','時点':'unknown-a'};b={**a,'時点':'unknown-b'};self.assertNotEqual(m.意味SHA(a,d),m.意味SHA(b,d))
if __name__=='__main__':unittest.main()
