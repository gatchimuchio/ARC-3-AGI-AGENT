import sys,json,gzip,hashlib,unittest,uuid,os,tempfile
from pathlib import Path
from unittest.mock import patch
if __package__:
 from . import 公開教師を教示 as M
else:
 import 公開教師を教示 as M
P=Path(__file__).resolve().parent;OUT=Path(os.environ.get('ARC_PAIRED_SAVE_TEST_DIR') or tempfile.mkdtemp(prefix='arc-paired-save-evidence-'))
SHA=hashlib.sha256(b'{}').hexdigest();GOOD={'具体時刻位置':[],'具体時刻復元後SHA256':SHA,'原state復号SHA256':SHA}
class 保存境界(unittest.TestCase):
 def setUp(self):self.p=OUT/(self._testMethodName+'-'+uuid.uuid4().hex);self.p.mkdir(parents=True);self.out=self.p/'state.json.gz'
 def fake(self,h,path):
  with gzip.open(path,'wb')as f:f.write(b'{}')
  return SHA,2
 def assertEvidence(self,exc,*,final=False):
  d=exc.exception.失敗記録;self.assertFalse(d['成功']);self.assertEqual(self.out.exists(),final);self.assertTrue(Path(d['失敗理由path']).exists())
  if d['未完証拠path']:self.assertTrue(Path(d['未完証拠path']).exists())
  (self.p/'検査結果.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
 def test_途中保存失敗を保持(self):
  def bad(h,path):path.write_bytes(b'partial');raise OSError('人工途中保存失敗')
  with patch.object(M,'_圧縮仮保存',side_effect=bad):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e);self.assertEqual(Path(e.exception.失敗記録['未完証拠path']).read_bytes(),b'partial')
 def test_意味不一致を保持(self):
  with patch.object(M,'_圧縮仮保存',side_effect=self.fake):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,{**GOOD,'具体時刻復元後SHA256':'bad'},self.out)
  self.assertEvidence(e)
 def test_標準再読込失敗を保持(self):
  with patch.object(M,'_圧縮仮保存',side_effect=self.fake),patch.object(M,'_標準再読込',side_effect=ValueError('人工標準読込失敗')):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e)
 def test_既存先を上書きしない(self):
  self.out.write_text('既存')
  with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e,final=True);self.assertEqual(self.out.read_text(),'既存')
 def test_確定時競合を上書きしない(self):
  actual=os.link
  def race(src,dst):Path(dst).write_text('競合');return actual(src,dst)
  with patch.object(M,'_圧縮仮保存',side_effect=self.fake),patch.object(M,'_標準再読込',return_value=None),patch.object(M,'_bytes',return_value=iter([b'{}'])),patch.object(M.os,'link',side_effect=race):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e,final=True);self.assertEqual(self.out.read_text(),'競合')
 def test_再符号化型byte不一致は未確定(self):
  with patch.object(M,'_圧縮仮保存',side_effect=self.fake),patch.object(M,'_標準再読込',return_value=None),patch.object(M,'_bytes',return_value=iter([b'wrong'])):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e)
 def test_確定後dir同期失敗も成功にしない(self):
  calls=0;real=M.os.fsync
  def bad(fd):
   nonlocal calls
   calls+=1
   if calls==2:raise OSError('人工dir同期失敗')
   return real(fd)
  with patch.object(M,'_圧縮仮保存',side_effect=self.fake),patch.object(M,'_標準再読込',return_value=None),patch.object(M,'_bytes',return_value=iter([b'{}'])),patch.object(M.os,'fsync',side_effect=bad):
   with self.assertRaises(M.保存失敗)as e:M.検証して新規保存する(None,GOOD,self.out)
  self.assertEvidence(e,final=True)
 def test_教示前fixture例外も逐次証拠を保持(self):
  log=self.p/'progress.jsonl.gz'
  with patch.object(M,'教示する',side_effect=ValueError('人工fixture検証失敗')),patch.object(sys,'argv',['cli','--fixture',str(self.p/'bad.gz'),'--output',str(self.out),'--log',str(log)]):
   with self.assertRaises(M.保存失敗)as e:M.main()
  self.assertEvidence(e);self.assertEqual(Path(e.exception.失敗記録['未完証拠path']),log)
 def test_指定外の同名時点も差分になる(self):
  d={'具体時刻位置':[{'path':['x'],'原時刻':'2026-01-01T00:00:00+00:00'}]};a={'x':'2026-01-02T00:00:00+00:00','時点':'A'};b={**a,'時点':'B'}
  self.assertNotEqual(M.意味SHA(a,d),M.意味SHA(b,d));(self.p/'検査結果.json').write_text('{"指定外同名key差分検出":true}')
 def test_小人工stateの標準core同形式保存再読込(self):
  h=M.HDS学習系統();h.処理する(M.外部入力({'人工保存試験':1},'保存器の人工対照'))
  native=self.p/'小標準.json';h.保存する(native);data=json.loads(native.read_text());sha=hashlib.sha256()
  for s in json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':')).iterencode(data):sha.update(s.encode())
  d={**GOOD,'具体時刻復元後SHA256':sha.hexdigest()};r=M.検証して新規保存する(h,d,self.out)
  self.assertTrue(r['成功']);self.assertEqual(json.load(gzip.open(self.out,'rt')),data);(self.p/'検査結果.json').write_text(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':unittest.main()
