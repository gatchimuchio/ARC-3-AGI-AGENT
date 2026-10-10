import unittest,os,gzip,json,hashlib,gc
from pathlib import Path
from 接続.輪郭接続 import 輪郭候補を作る,輪郭全応答を照合
from 接続.輪郭内部.モデル import モデル,照会
from 接続.輪郭内部.知覚 import 状態を読む
from 接続.輪郭内部.構成 import stage
from 接続.輪郭教師CLI import 教師を読む
from hds学習系統 import HDS学習系統
R=Path(__file__).resolve().parent/'輪郭配置'
@unittest.skipUnless(os.environ.get('WA_TEST_HDS'),'WA_TEST_HDSで承認済み実661を注入')
class 実状態(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.h=HDS学習系統.読み込む(Path(os.environ['WA_TEST_HDS']));cls.f=json.load(gzip.open(R/'公開静的応答443.json.gz','rt'));cls.frame=cls.f['初期観測'][0]['frame'][0];cls.expected=json.load(gzip.open(R/'境界付き期待値.json.gz','rt'))
 @classmethod
 def tearDownClass(cls):del cls.h;gc.collect()
 def test_実661全73教示照会(self):
  ts=教師を読む()['教師'];qs={(t['境界'],t['内容']['前提']):json.loads(t['内容']['結果'])for t in ts};self.assertEqual(len(qs),73)
  for(b,f),v in qs.items():self.assertEqual(照会(self.h,b,json.loads(f))['値'],v)
 def test_凍結31照会意味一致(self):
  for q in self.expected['全31照会']:self.assertEqual(照会(self.h,q['境界'],q['前提'])['値'],q['値'])
 def test_6目標と全局所作用(self):
  r=輪郭候補を作る(self.frame,[0,1,2,3,4,5,6,7],self.h);self.assertEqual(len(r['目標候補群']),6);self.assertTrue(all(x['状態']=='条件付き支持'for x in r['目標候補群']));self.assertEqual(len(r['全36構成候補']),36);self.assertEqual(len(r['作用候補群']),8)
 def test_第0段階全閉鎖と圧縮集合一致(self):
  m=モデル(self.h,self.frame);exits,q,_=stage(m,[m.start],0,m.slots[0]);e=self.expected['第0段階'];self.assertTrue(q['探索完了']);self.assertEqual(q['状態数'],e['状態数']);self.assertEqual(len(exits),e['出口数']);self.assertEqual(hashlib.sha256(q['全状態集合'].encode()).hexdigest(),e['全状態ビット集合文字列SHA256']);self.assertTrue(all(r['状態']=='条件付き後続経路あり'for r in q['初回作用全候補']))
 def test_443公開空間作用(self):
  m=モデル(self.h,self.frame)
  for pair in self.f['全静的応答']:
   before=状態を読む(pair['前原票']['frame'][-1]);after=状態を読む(pair['応答']['frame'][0]);nxt,_,_=m.next(before,pair['応答']['action_input']['id']);self.assertIsNotNone(nxt);self.assertEqual(nxt[:2],after[:2]);self.assertEqual(set(nxt[2]),set(after[2]));self.assertEqual(set()if nxt[3]<0 else{nxt[2][nxt[3]]},set()if after[3]<0 else{after[2][after[3]]})
 def test_初回全相と故障相保持(self):
  import copy
  pair=self.f['全静的応答'][0];a=pair['応答']['action_input']['id'];r=輪郭全応答を照合(pair['前原票'],pair['応答'],a,self.h);self.assertEqual(r['状態'],'全相の条件付き空間予測一致');bad=copy.deepcopy(pair['応答']);bad['frame'].append(copy.deepcopy(bad['frame'][-1]));bad['frame'][-1][0][0]=2;r=輪郭全応答を照合(pair['前原票'],bad,a,self.h);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全相']),2);self.assertIn('HOLD',r['後続手順採否'])
if __name__=='__main__':unittest.main()
