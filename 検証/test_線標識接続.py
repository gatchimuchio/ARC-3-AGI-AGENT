import unittest,json,gzip,os,tempfile,hashlib,pickle
from pathlib import Path
from unittest.mock import patch
from 接続.線標識接続 import 線標識候補を作る
from 接続.線標識教師CLI import 状態を読む,可逆保存,HDS学習系統
ROOT=Path(__file__).resolve().parents[1]
def 教材():return json.loads(gzip.decompress((ROOT/'記憶/公開教材/線標識.json.gz').read_bytes()))
def 意味(h):
 e=h.エンジン;ids={k:v for k,v in e.識別子.状態を書き出す().items()if k not in ('照会','学習判定')};return hashlib.sha256(pickle.dumps((e.最小支持数,e.最大条件数,ids,e.台帳.全取得(),e.状態.履歴(),e._原理履歴))).hexdigest()
class 境界(unittest.TestCase):
 def test_empty(self):
  for x in 教材()['問題例']:self.assertEqual(線標識候補を作る(x['問題'],[1,2,3,4,5],HDS学習系統())['状態'],'保留')
 def test_blank_invalid_actions(self):
  for frame,actions in [([[5]*64 for _ in range(64)],[1,2,3,4,5]),([],[]),([[True]*64 for _ in range(64)],[1,2,3,4,5]),(教材()['問題例'][0]['問題'],[1,2,3,4])]:self.assertEqual(線標識候補を作る(frame,actions,HDS学習系統())['状態'],'保留')
 def test_invalid_actions_before_query(self):
  class NoQuery:
   calls=0
   def 照会する(self,x):self.calls+=1;raise AssertionError('無効作用で照会してはならない')
  problem=教材()['問題例'][0]['問題']
  for actions in ([1,2,3,4,5,5],[1,2,3,4,5,-1],[1,2,3,4,5,8],[1,2,3,4,5,True],[1,2,3,4,5,'6']):
   h=NoQuery();r=線標識候補を作る(problem,actions,h)
   self.assertEqual(r['状態'],'保留');self.assertEqual(h.calls,0);self.assertEqual(r['途中を含む全照会'],[])
   self.assertEqual([x['作用']for x in r['全外部作用候補']],list(actions))
 def test_unexplained_pixel_before_query(self):
  class NoQuery:
   calls=0
   def 照会する(self,x):self.calls+=1;raise AssertionError('未説明画素で照会してはならない')
  frame=[list(row)for row in 教材()['問題例'][0]['問題']];frame[0][0]=2
  h=NoQuery();r=線標識候補を作る(frame,[1,2,3,4,5],h)
  self.assertEqual(r['状態'],'保留');self.assertEqual(h.calls,0);self.assertEqual(len(r['全描画残差']),2)
  self.assertTrue(all(any(x['位置']==[0,0]for x in rows)for rows in r['全描画残差']))
 def test_exception(self):
  class Fault:
   def 照会する(self,x):raise RuntimeError('注入故障')
  r=線標識候補を作る(教材()['問題例'][0]['問題'],[1,2,3,4,5],Fault());self.assertEqual(r['状態'],'保留');self.assertEqual(r['例外種別'],'RuntimeError');self.assertEqual(len(r['途中を含む全照会']),1)
 def test_reversible_no_overwrite(self):
  with tempfile.TemporaryDirectory()as td:
   p=Path(td)/'a.json.gz';可逆保存(p,{'集合':{(1,2)}});before=p.read_bytes();self.assertEqual(json.loads(gzip.decompress(before)),{'集合':[[1,2]]})
   with self.assertRaises(FileExistsError):可逆保存(p,{})
   self.assertEqual(p.read_bytes(),before)
 def test_save_failure(self):
  with tempfile.TemporaryDirectory()as td:
   p=Path(td)/'a.json.gz'
   with patch('接続.線標識教師CLI.os.link',side_effect=OSError('保存故障')):
    with self.assertRaises(OSError):可逆保存(p,{})
   self.assertFalse(p.exists());self.assertEqual(list(Path(td).iterdir()),[])
 def test_fixture(self):
  x=教材();self.assertEqual(len(x['全教師']),2143);self.assertEqual(sorted(t['元教師通番']for t in x['全教師']),list(range(2143)))
@unittest.skipUnless(os.environ.get('RE86_TEST_HDS'),'外部学習済みstateを明示。新規学習しない')
class 実状態(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  mem=int(next(s.split()[1]for s in Path('/proc/meminfo').read_text().splitlines()if s.startswith('MemAvailable:')))
  if mem<2400000:raise unittest.SkipTest('RAM余裕不足')
  cls.h=状態を読む(os.environ['RE86_TEST_HDS'],教材()['参照実state']['SHA256_復号']);cls.before=意味(cls.h);cls.results=[線標識候補を作る(x['問題'],[1,2,3,4,5,6],cls.h)for x in 教材()['問題例']]
 def test_first(self):
  r=self.results[0];self.assertEqual(r['最小作用数'],20);self.assertEqual(len(r['全体最短全経路']),9240);self.assertTrue(all(r['各最短経路の観測整合']));self.assertEqual(sum(a['状態']=='保留'for s in r['全最短分岐状態の全五候補']for a in s['全五候補']),1)
 def test_second(self):
  r=self.results[1];self.assertEqual((r['最短操作数'],r['全最短経路数'],r['観測条件付き支持経路数'],r['観測保留経路数']),(36,9513504,2979900,6533604));self.assertEqual((len(r['全最短DAG']),len(r['全再観測']),r['最短辺保留']),(117,312,10));self.assertFalse(r['全因子積画像検証'])
 def test_same_state_and_unknown(self):
  self.assertEqual(self.before,意味(self.h))
  for r in self.results:self.assertFalse(r['実行許可']);self.assertFalse(r['新規環境成功']);self.assertEqual(r['未対応外部作用'][0]['状態'],'保留')
 def test_dag_count(self):
  r=self.results[1];key=lambda s:json.dumps(s,separators=(',',':'));g={key(v['状態']):v['全最短辺']for v in r['全最短DAG']};obs={key(v['状態']):v['観測対応一致']for v in r['全再観測']};goals={key([v['目標中心'],v['選択巡回'][-1]])for v in r['全目標候補']if v['最短操作数']==36};start=key([[o['中心']for o in r['初期']['図形']],next(i for i,o in enumerate(r['初期']['図形'])if o['選択'])]);memo={}
  def count(s,admit):
   if (s,admit)in memo:return memo[s,admit]
   n=0 if admit and not obs[s]else int(s in goals)+sum(count(key(a['次状態']),admit)for a in g[s]);memo[s,admit]=n;return n
  self.assertEqual(count(start,False),9513504);self.assertEqual(count(start,True),2979900)
if __name__=='__main__':unittest.main()
