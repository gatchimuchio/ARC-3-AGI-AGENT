import unittest,json,gzip,sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from 接続.鎖教師CLI import 教材を教える
from 接続.鎖接続 import 鎖候補を作る
from 接続.鎖内部 import 候補 as C,格子 as S,状態 as M,探索,経路採否
class 鎖接続試験(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fixture=json.loads((ROOT/'入力/鎖教師/関係教材.json').read_text());cls.h=HDS学習系統.読み込む(Path(os.environ['CHAIN_TEST_HDS'])) if os.environ.get('CHAIN_TEST_HDS') else 教材を教える(cls.fixture);cls.obs=cls.fixture['初期観測'];cls.out=鎖候補を作る(cls.obs['frame'],cls.obs['available_actions'],cls.h,照会共有=True);cls.temp=tempfile.TemporaryDirectory();cls.snapshot=Path(cls.temp.name)/'状態.json';cls.h.保存する(cls.snapshot)
 def test_全8開発観測の方向候補(self):
  for o in self.fixture['開発観測群']:
   out=鎖候補を作る(o['frame'],[1,2,3,4],self.h,経路も作る=False,照会共有=True);self.assertEqual(len(out['作用候補群']),4);self.assertFalse(out['実行許可'])
 def test_全997教師(self):
  for t in self.fixture['教師群']:
   field=t['結果経路'];raw=self.h.照会する(外部入力({k:v for k,v in t['入力'].items() if k!=field},t['境界']));pred=[p['予測値'] for p in raw.内容['予測群'] if p['結果経路']==(field,)];self.assertEqual(raw.状態,'出力');self.assertEqual(set(pred),{t['入力'][field]})
 def test_214生画素次状態(self):
  with gzip.open(ROOT/'入力/鎖教師/214作用原画素.json.gz','rt',encoding='utf8') as f:rows=json.load(f)
  m=M.StateModel(self.h,share_queries=True)
  for r in rows:
   before,ctx=S.extract(r['前画素']);after,_=S.extract(r['後画素']);self.assertEqual(m.predict(before,ctx,r['作用']).get('次状態'),after)
 def test_全4101候補(self):self.assertEqual(len(self.out['作用候補群']),4101)
 def test_全座標(self):self.assertEqual(len({(r['作用']['data']['x'],r['作用']['data']['y']) for r in self.out['作用候補群'] if r['作用']['id']==6}),4096)
 def test_20経路保持(self):self.assertEqual(len(self.out['経路候補群']),20)
 def test_11支持9保留(self):self.assertEqual((self.out['支持経路数'],self.out['保留経路数']),(11,9))
 def test_32固有作用(self):self.assertEqual(len(self.out['作用照合群']),32)
 def test_2未知辺(self):
  held=[r for r in self.out['作用照合群'] if r['採否']=='断定保留'];self.assertEqual({(r['元状態'],r['作用'],r['先状態']) for r in held},{(1,4,6),(4,4,10)});self.assertTrue(all(r['予測整合'] is None for r in held))
 def test_280全段(self):self.assertEqual(sum(len(r['手順']) for r in self.out['経路候補群']),280)
 def test_保留を削除しない(self):self.assertTrue(self.out['全候補保持']);self.assertTrue(all(r['保留作用参照'] for r in self.out['経路候補群'] if r['採否']=='断定保留'))
 def test_最初経路のみ採用しない(self):self.assertEqual(self.out['採用順序'],[])
 def test_全実行保留(self):self.assertFalse(self.out['実行許可']);self.assertTrue(all(not r['実行許可'] for r in self.out['経路候補群']))
 def test_前線保持(self):self.assertEqual(len(self.out['探索記録']['未展開前線']),330)
 def test_未知辺保持(self):self.assertEqual(sum(r['予測']['状態']=='断定保留' for r in self.out['探索記録']['全辺群']),957)
 def test_空HDS(self):
  out=鎖候補を作る(self.obs['frame'],[1,2,3,4],HDS学習系統(),照会共有=True);self.assertEqual(out['経路候補群'],[]);self.assertTrue(all(x['採否']=='断定保留' for x in out['作用候補群']))
 def test_空画素(self):
  out=鎖候補を作る([],self.obs['available_actions'],self.h);self.assertEqual(len(out['作用候補群']),4101);self.assertEqual(out['適用性'],'未確認')
 def test_不整形画素(self):
  out=鎖候補を作る([[1],[]],[1,6],self.h);self.assertEqual(len(out['作用候補群']),4097);self.assertTrue(all(x['採否']=='断定保留' for x in out['作用候補群']))
 def test_65幅は全候補保持で公式境界保留(self):
  frame=[list(row)+[4] for row in self.obs['frame']];out=鎖候補を作る(frame,self.obs['available_actions'],self.h,照会共有=True)
  self.assertEqual(len(out['作用候補群']),4101);self.assertEqual(out['適用性'],'未確認');self.assertIn('盤面の横幅が公式範囲外',out['保留理由群']);self.assertTrue(all(r['採否']=='断定保留' for r in out['作用候補群']))
 def test_65高は全候補保持で公式境界保留(self):
  frame=[list(row) for row in self.obs['frame']]+[[4]*64];out=鎖候補を作る(frame,self.obs['available_actions'],self.h,照会共有=True)
  self.assertEqual(len(out['作用候補群']),4101);self.assertEqual(out['適用性'],'未確認');self.assertIn('盤面の高さまたは行幅が不正',out['保留理由群']);self.assertTrue(all(r['採否']=='断定保留' for r in out['作用候補群']))
 def test_tuple盤面を正規化する(self):
  frame=tuple(tuple(row) for row in self.obs['frame']);out=鎖候補を作る(frame,[1,2,3,4],self.h,経路も作る=False,照会共有=True)
  self.assertEqual(out['適用性'],'適用可能');self.assertEqual([r['採否'] for r in out['作用候補群']],['局所作用支持']*4)
 def test_逆方向意味不一致(self):self.assertFalse(経路採否.局所意味一致([8],[8,14],[8,14,9],4,[['同列']])[0])
 def test_既達成状態(self):
  s=self.out['探索記録'];end=s['状態群'][s['目標状態群'][0]];frame=S.render(end,s['文脈']);r=探索.search(frame,[1,2,3,4],self.h,share_queries=True);self.assertEqual(r['最短表示経路群'],[[]])
 def test_局所全段直列共有(self):
  s=self.out['探索記録'];a=経路採否.全経路を判定(s,self.h,照会共有=False);self.assertEqual(a['経路候補群'],self.out['経路候補群']);self.assertEqual(a['支持経路数'],11)
 def test_人工矛盾(self):
  h=HDS学習系統.読み込む(self.snapshot);t=next(t for t in self.fixture['教師群'] if t['結果経路']=='完成列一致' and t['入力']['完成列一致'] is True);h.処理する(外部入力({**t['入力'],'完成列一致':False},t['境界']));out=鎖候補を作る(self.obs['frame'],[1,2,3,4],h,照会共有=True);self.assertTrue(all(x['採否']=='断定保留' for x in out['作用候補群']));self.assertEqual(out['経路候補群'],[])
if __name__=='__main__':unittest.main()
