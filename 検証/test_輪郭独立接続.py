import gzip,json,copy,unittest,tempfile,os
from pathlib import Path
from 接続.輪郭接続 import 輪郭候補を作る,輪郭全応答を照合
from 接続.輪郭教師CLI import 教師を読む
from hds学習系統 import HDS学習系統
ROOT=Path(__file__).resolve().parent/'輪郭配置'
class Sentinel:
 def __init__(self):self.calls=0
 def 照会する(self,*a):self.calls+=1;raise AssertionError('HDSへ到達')
class 輪郭独立(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixture=json.loads(gzip.decompress((ROOT/'公開静的応答443.json.gz').read_bytes()));cls.frame=cls.fixture['初期観測'][0]['frame'][0]
 def _invalid(self,f):
  h=Sentinel();r=輪郭候補を作る(f,[1,2,3,4,5,6,7,'RESET'],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD');self.assertEqual({a['作用']for a in r['作用候補群']},{0,1,2,3,4,5,6,7});self.assertFalse(r['実行許可'])
 def test_65高さ(self):self._invalid(self.frame+[self.frame[-1]])
 def test_65幅(self):self._invalid([row+[1]for row in self.frame])
 def test_画素範囲(self):
  for v in(-1,16,True,1.5):
   f=copy.deepcopy(self.frame);f[0][0]=v;self._invalid(f)
 def test_非矩形(self):self._invalid([self.frame[0][:-1]]+self.frame[1:])
 def test_小寸法(self):self._invalid([[1]])
 def test_tuple正規化(self):
  r=輪郭候補を作る(tuple(map(tuple,self.frame)),[1,2,3,4,5],HDS学習系統());self.assertEqual(r['適用性']['状態'],'適用可能')
 def test_空HDS全候補保持(self):
  r=輪郭候補を作る(self.frame,[0,1,2,3,4,5,6,7],HDS学習系統(),経路も作る=True,段階展開上限=1);self.assertEqual(len(r['目標候補群']),6);self.assertEqual(len(r['全36構成候補']),36);self.assertTrue(all(x['状態']=='HOLD'for x in r['全36構成候補']));self.assertEqual(len(r['作用候補群']),8)
 def test_零予算前線保持(self):
  r=輪郭候補を作る(self.frame,[1,2,3,4,5],HDS学習系統(),経路も作る=True,段階展開上限=0);self.assertEqual(len(r['全36構成候補']),36);self.assertTrue(all(x['未展開前線数']==1 for x in r['全段階']))
 def test_HDS例外でも候補保持(self):
  h=Sentinel();r=輪郭候補を作る(self.frame,[1,5,6],h);self.assertEqual(h.calls,1);self.assertEqual(len(r['目標候補群']),6);self.assertEqual(len(r['全36構成候補']),36)
 def test_他8問題範囲外保持(self):
  for f in self.fixture['九初期盤面'][1:]:
   h=Sentinel();r=輪郭候補を作る(f,[1,2,3,4,5],h);self.assertEqual(h.calls,0);self.assertEqual(r['適用性']['状態'],'構造上不適用');self.assertIn('目標候補全域',r)
 def test_作用不正の全合法領域(self):
  h=Sentinel();r=輪郭候補を作る(self.frame,[1,True,6,7,0],h);self.assertEqual(h.calls,0);self.assertEqual({x['作用']for x in r['作用候補群']},{0,1,6,7})
 def test_教材661支持参照保持(self):
  p=教師を読む();self.assertEqual(len(p['教師']),661);self.assertEqual(sum(len(t['原観測参照'])for t in p['教師']),6738)
 def test_全443応答原票保持(self):self.assertEqual(len(self.fixture['全静的応答']),443)
 def test_RESET境界で照会0(self):
  pair=self.fixture['全静的応答'][0];r=copy.deepcopy(pair['応答']);r['action_input']['id']=0;h=Sentinel();out=輪郭全応答を照合(pair['前原票'],r,0,h);self.assertEqual(h.calls,0);self.assertEqual(out['状態'],'HOLD');self.assertEqual(len(out['全相']),len(r['frame']))
 def test_instance変更で照会0(self):
  pair=self.fixture['全静的応答'][0];r=copy.deepcopy(pair['応答']);r['guid']='別instance';h=Sentinel();out=輪郭全応答を照合(pair['前原票'],r,r['action_input']['id'],h);self.assertEqual(h.calls,0);self.assertEqual(out['状態'],'HOLD')
 def test_作用不一致で照会0(self):
  pair=self.fixture['全静的応答'][0];h=Sentinel();out=輪郭全応答を照合(pair['前原票'],pair['応答'],7,h);self.assertEqual(h.calls,0);self.assertEqual(out['状態'],'HOLD')
 def test_全相不正でも原票保持(self):
  pair=self.fixture['全静的応答'][0];r=copy.deepcopy(pair['応答']);r['frame'].append([[16]]);h=Sentinel();out=輪郭全応答を照合(pair['前原票'],r,r['action_input']['id'],h);self.assertEqual(h.calls,0);self.assertEqual(out['全応答原票'],r)
 def test_操作体向き不明で照会0(self):
  f=copy.deepcopy(self.frame)
  for y,row in enumerate(f[:60]):
   if 14 in row:
    x=row.index(14);f[y][x]=0;break
  h=Sentinel();r=輪郭候補を作る(f,[1,5,6],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD')
 def test_輪郭内部の未説明画素で照会0(self):
  f=copy.deepcopy(self.frame)
  for y,row in enumerate(f[:60]):
   if 2 in row:
    x=row.index(2);f[y][x]=1;break
  h=Sentinel();r=輪郭候補を作る(f,[1,5,6],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD')
 def test_段階例外で全前線保持(self):
  from 接続.輪郭内部.構成 import stage
  class M:
   start=((0,0),1,((1,0),(2,0),(3,0)),-1)
   def goal(self,s):return False
   def next(self,s,a):raise RuntimeError('故障注入')
  m=M();_,r,_=stage(m,[m.start,m.start[:1]+(2,)+m.start[2:]],0,(7,7))
  self.assertFalse(r['探索完了']);self.assertEqual(r['未展開前線数'],2);self.assertIn('故障注入',r['例外'])
 def test_単一起点例外で前線と全初回作用保持(self):
  from 接続.輪郭内部.構成 import stage
  class M:
   start=((0,0),1,((1,0),(2,0),(3,0)),-1)
   def goal(self,s):return False
   def next(self,s,a):raise RuntimeError('単一起点故障')
  m=M();_,r,_=stage(m,[m.start],0,(7,7))
  self.assertFalse(r['探索完了']);self.assertEqual(r['未展開前線数'],1)
  self.assertEqual([x['作用']for x in r['初回作用全候補']],list(range(1,6)))
  self.assertTrue(all(x['状態']=='HOLD'and'単一起点故障'in x['例外']for x in r['初回作用全候補']))
 def test_探索後の初回再照会例外も未完了(self):
  from 接続.輪郭内部.構成 import stage
  class M:
   start=((0,0),1,((1,0),(2,0),(3,0)),-1);calls=0
   def goal(self,s):return False
   def next(self,s,a):
    self.calls+=1
    if self.calls>5:raise RuntimeError('初回再照会故障')
    return None,'HOLD',None
  m=M();_,r,_=stage(m,[m.start],0,(7,7))
  self.assertFalse(r['探索完了']);self.assertEqual(r['未展開前線数'],0);self.assertEqual(r['処理状態数'],1)
  self.assertEqual(len(r['初回作用全候補']),5);self.assertIn('初回再照会故障',r['例外'])
 def test_初期強調枠色の再描画境界(self):
  f=copy.deepcopy(self.frame)
  from 接続.輪郭内部.知覚 import 読む
  x,y=next(r['位置']for r in 読む(f)['小枠']if r['枠']==4)
  for j in range(4):
   for i in range(4):
    if i in(0,3)or j in(0,3):f[y*4+j][x*4+i]=3
  h=Sentinel();r=輪郭候補を作る(f,[1,2,3,4,5],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD')
 def test_応答カウンタ欠損進捗矛盾は照会前HOLD(self):
  pair=self.fixture['全静的応答'][0]
  for case in ('missing','legacy_progress','conflict','total_change'):
   b=copy.deepcopy(pair['前原票']);a=copy.deepcopy(pair['応答'])
   if case=='missing':
    for d in(b,a):
     for k in('levels_completed','score','win_levels','win_score'):d.pop(k,None)
   elif case=='legacy_progress':
    for d in(b,a):d['score']=d.pop('levels_completed');d['win_score']=d.pop('win_levels')
    a['score']=b['score']+1
   elif case=='conflict':a['score']=a['levels_completed']+1
   else:a['win_levels']+=1
   h=Sentinel();r=輪郭全応答を照合(b,a,a['action_input']['id'],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全相']),len(a['frame']))
 def test_非座標実引数と出所不一致は照会前HOLD(self):
  pair=self.fixture['全静的応答'][0]
  for data in ({'x':63,'y':63},{'game_id':'different'},None):
   a=copy.deepcopy(pair['応答']);a['action_input']['data']=data;h=Sentinel();r=輪郭全応答を照合(pair['前原票'],a,a['action_input']['id'],h);self.assertEqual(h.calls,0);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全相']),len(a['frame']))
 def test_目標HOLDなら作用支持だけで構成採用しない(self):
  from 接続.輪郭内部.構成 import compose
  from unittest.mock import patch
  class M:
   start=((0,0),1,((1,0),(2,0),(3,0)),-1);slots=[(7,7),(8,7),(9,7)];gq={'値':None}
  m=M()
  def stage_stub(m,entries,target,dest,limit):
   return entries,{'探索完了':True,'出口未支持入口':[],'初回作用全候補':[]},{s:(s,[])for s in entries}
  with patch('接続.輪郭内部.構成.stage',stage_stub):r=compose(m)
  self.assertEqual(len(r['全36構成候補']),36);self.assertTrue(all(x['状態']=='HOLD'for x in r['全36構成候補']));self.assertEqual(r['全出口証人'],[])
if __name__=='__main__':unittest.main()
