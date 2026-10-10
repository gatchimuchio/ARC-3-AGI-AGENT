import unittest,tempfile,json
from pathlib import Path
from 接続.鏡像教師CLI import 保存状態を読む,資料を読む,確認保存
from 接続.鏡像接続 import 鏡像候補を作る,鏡像作用を照合,鏡像全応答を照合
from 接続.鏡像内部.採否 import 画素から前観測,正準値
from 接続.鏡像内部.再識別 import all_decompositions,normalize
from 接続.鏡像内部 import 基礎 as e
from hds学習系統 import HDS学習系統

class 鏡像検証(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.h=保存状態を読む();cls.raw=資料を読む('全公開原票.json.gz')['成功資料']['原票']
 def test_画素境界は照会前に拒否する(self):
  class 照会禁止:
   def 照会する(self,入力):raise AssertionError('不正画素がHDSへ到達')
  frames=[None,[[9]*64 for _ in range(65)],[[9]*63 for _ in range(64)]]
  for value in (16,-1,True,9.0,'9'):
   f=[[9]*64 for _ in range(64)];f[0][0]=value;frames.append(f)
  for f in frames:
   out=鏡像候補を作る(f,[1,6,7],照会禁止())
   self.assertEqual(len(out['作用候補群']),3);self.assertTrue(out['保留理由群']);self.assertFalse(out['経路候補群'])
   out=鏡像全応答を照合({'次観測照合用予測':None},{'frame':[f]},照会禁止(),既観測形状=[])
   self.assertEqual(out['状態'],'HOLD');self.assertEqual(len(out['全応答相']),1)
 def test_空割当を支持しない(self):
  for b,s in [([],[]),([],[[[0,0]]]),([[1,1]],[[]])]:self.assertEqual(all_decompositions(b,s)[0],[])
  o=鏡像候補を作る([[9]*64 for _ in range(64)],[1,6,7],self.h)
  self.assertEqual(len(o['作用候補群']),3);self.assertFalse(o['経路候補群']);self.assertTrue(o['保留理由群']);self.assertFalse(o['実行許可'])
 def test_保存失敗を完了としない(self):
  class 無書出:
   def 保存する(self,p):pass
  class 明示失敗:
   def 保存する(self,p):raise OSError('模擬保存失敗')
  with tempfile.TemporaryDirectory()as d:
   path=Path(d)/'状態.json';path.write_text('既存保存を保持')
   for h in (無書出(),明示失敗()):
    with self.assertRaises(OSError):確認保存(h,path)
    self.assertEqual(path.read_text(),'既存保存を保持')
 def test_選択曖昧を勝手に絞らない(self):
  B=[(0,0),(1,0),(4,0),(5,0)];obs={'黒占有':B,'白標識':[],'黄目標':B,'軸':[{'方向':0,'位置':10,'可動':False}],'可視選択軸索引':None}
  r=鏡像作用を照合(obs,[[(0,0),(1,0)]]*2,{'id':4,'data':{}},self.h)
  self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全可視仮説']),4);self.assertIsNone(r['次観測照合用予測'])
 def test_全外部候補と全完成候補(self):
  r=鏡像候補を作る(self.raw[0]['frame'][-1],self.raw[0]['available_actions'],self.h)
  self.assertEqual([a['id']for a in r['作用候補群']],self.raw[0]['available_actions'])
  click=next(a for a in r['作用候補群']if a['id']==6)
  self.assertEqual(sum(len(c['全同値座標'])for c in click['座標同値類群']),4096)
  self.assertEqual(sum(g['全配置']['条件充足配置数']for g in r['全完成候補群']),1)
  plans=[p for x in r['経路候補群']for p in x['手順構成']['全完成配置に対する手順']]
  self.assertEqual(len(plans),1);self.assertEqual(plans[0]['具体操作数'],15);self.assertTrue(plans[0]['全観測履歴再照合']['全段成立']);self.assertFalse(r['実行許可'])
 def test_空HDSが学習支持を代用しない(self):
  f=資料を読む('46手順前観測.json.gz')[0];s=f['全前観測'][0]
  self.assertEqual(鏡像作用を照合(s['前観測'],f['既観測形状'],s['作用'],HDS学習系統())['状態'],'HOLD')
 def test_過去支持を現在HDS隔離より優先しない(self):
  import copy
  from hds学習系統 import 外部入力
  a,b=self.raw[0],self.raw[1];obs,scene,_=画素から前観測(a['frame'][-1]);shapes=[normalize(o['点'])for o in scene['対象']]
  pre=鏡像作用を照合(obs,shapes,b['action_input'],self.h)
  bad=copy.deepcopy(self.h);bad.処理する(外部入力({'黄標識全被覆':True,'成功遷移':False},e.GOAL))
  for h in(HDS学習系統(),bad):
   out=鏡像全応答を照合(pre,b,h,既観測形状=shapes,前得点=a['score'],前状態=a['state'])
   self.assertEqual(out['状態'],'HOLD');self.assertIsNone(out['次観測履歴'])
  modern={k:v for k,v in b.items()if k!='score'};modern['levels_completed']=0
  out=鏡像全応答を照合(pre,modern,self.h,既観測形状=shapes,前状態=a['state'],前完了レベル数=0)
  self.assertEqual(out['状態'],'全応答一致')
  mismatch={**b,'action_input':{'id':4,'data':{}}}
  out=鏡像全応答を照合(pre,mismatch,self.h,既観測形状=shapes,前得点=a['score'],前状態=a['state'])
  self.assertEqual(out['状態'],'HOLD');self.assertIsNone(out['次観測履歴'])
  for kwargs,response in [({},b),({'前得点':a['score']},b),({'前得点':a['score'],'前状態':a['state']},{**b,'levels_completed':0}),({'前得点':a['score'],'前状態':a['state'],'前完了レベル数':0},{**b,'levels_completed':1})]:
   out=鏡像全応答を照合(pre,response,self.h,既観測形状=shapes,**kwargs)
   self.assertEqual(out['状態'],'HOLD');self.assertIsNone(out['次観測履歴'])
 def test_全応答と履歴JSON往復(self):
  a,b=self.raw[0],self.raw[1];obs,s,_=画素から前観測(a['frame'][-1]);shapes=[normalize(o['点'])for o in s['対象']]
  r=鏡像作用を照合(obs,shapes,b['action_input'],self.h)
  r=json.loads(json.dumps(正準値(r),ensure_ascii=False))
  out=鏡像全応答を照合(r,b,self.h,既観測形状=shapes,前得点=a['score'],前状態=a['state'])
  self.assertEqual(out['状態'],'全応答一致');self.assertIsNotNone(out['次観測履歴'])
  bad={**b,'frame':[b['frame'][0],[[9]*64 for _ in range(64)],b['frame'][-1]]}
  out=鏡像全応答を照合(r,bad,self.h,既観測形状=shapes,前得点=a['score'],前状態=a['state'])
  self.assertEqual(len(out['全応答相']),3);self.assertEqual(out['状態'],'HOLD');self.assertIsNone(out['次観測履歴'])
  self.assertEqual(鏡像全応答を照合(r,{**b,'frame':[]},self.h,既観測形状=shapes)['状態'],'HOLD')
if __name__=='__main__':unittest.main()
