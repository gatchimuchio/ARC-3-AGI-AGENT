import copy,unittest
import pathlib,sys
_基底 = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_基底), str(_基底 / 'HDS/学習系統/v0.4.2')]
from unittest.mock import patch
from 接続.ARC3境界 import 観測する
from 接続.共通観測経路 import 公開観測から候補を照会する,作用応答を相別に記録する
class 公開入力:
 最新盤面=((0,),);作用可能番号=(5,6);状態='NOT_FINISHED';観測通番=1;指紋='observation'
 @property
 def ゲーム識別子(self):raise AssertionError('解法選択でIDを読んだ')
 @property
 def 完了レベル数(self):raise AssertionError('解法選択でレベル番号を読んだ')
def 語彙結果(適用='適用可能',作用=None,保留=None,不確実=None,複数=False):
 return {'適用性':{'状態':適用,'根拠':['fixture']},'目標候補群':[{'目標':'fixture'}] if 適用=='適用可能' else [],
         '作用候補群':作用 or [],'保留理由群':保留 or [],'規則不確実性':不確実 or [],'複数整合解':複数,'実行許可':False}
def 作用(n=0):return {'作用番号':6,'引数':{'x':0,'y':0},'番号':n,'実行許可':False}
class 共通照会試験(unittest.TestCase):
 def setUp(self):
  # 既存二語彙の採否回帰。新語彙は別の実盤面試験で全照会する。
  for name in ('鎖語彙を接続する','形状語彙を接続する'):
   p=patch('接続.共通観測経路.'+name,return_value=語彙結果('構造上不適用'))
   p.start();self.addCleanup(p.stop)

 def run_case(self,a,b):
  h=object()
  with patch('接続.共通観測経路.列図式候補',return_value=a) as x,patch('接続.共通観測経路.複合図式候補',return_value=b) as y:
   result=公開観測から候補を照会する(h,公開入力(),図式適用支持={})
   self.assertIs(x.call_args.args[0],h);self.assertIs(y.call_args.args[2],h)
  return result
 def test_構造上不適用の理由を全体HOLDと混ぜない(self):
  r=self.run_case(語彙結果(作用=[作用()]),語彙結果('構造上不適用',保留=['構造違い']))
  self.assertEqual(r['状態'],'条件付き候補');self.assertEqual(len(r['次作用候補群']),1);self.assertFalse(r['保留理由群']);self.assertEqual(len(r['未採用理由群']),3)
 def test_順序付き経路は先頭だけを現在作用とし全経路を保持(self):
  r=self.run_case(語彙結果('構造上不適用'),語彙結果(作用=[作用(i) for i in range(3)]))
  self.assertEqual(len(r['次作用候補群']),1);self.assertEqual(len(r['候補経路群'][0]['経路']),3)
  self.assertEqual(r['次作用候補群'][0]['候補']['元候補']['番号'],0);self.assertFalse(r['実行許可'])
 def test_次作用の代替候補は先頭へ切り詰めない(self):
  r=self.run_case(語彙結果(作用=[作用(0),作用(1)]),語彙結果('構造上不適用'));self.assertEqual(len(r['次作用候補群']),2)
 def test_規則隔離は両語彙の作用を保留(self):
  r=self.run_case(語彙結果(不確実=['隔離']),語彙結果(作用=[作用()]));self.assertEqual(r['状態'],'HDS保留');self.assertFalse(r['次作用候補群'])
  self.assertEqual(r['語彙別結果'][1]['結果']['適用性']['状態'],'適用可能')
 def test_複数整合解を規則不確実性と混ぜない(self):
  a=語彙結果(保留=['選択未実装'],複数=True);a['目標候補群']=[{'解':i} for i in range(5)]
  r=self.run_case(a,語彙結果('構造上不適用'));self.assertEqual(r['状態'],'複数整合解を保持');self.assertFalse(r['規則不確実性']);self.assertEqual(len(r['全目標候補群'][0]['候補群']),5)
 def test_解析不明や複数適用は任意選択しない(self):
  for b in (語彙結果('未確認'),語彙結果(作用=[作用()])):
   r=self.run_case(語彙結果(作用=[作用()]),b);self.assertEqual(r['状態'],'未確認');self.assertFalse(r['次作用候補群']);self.assertEqual(len(r['語彙別結果']),4)
 def test_例外を構造上不適用へ隠さない(self):
  with patch('接続.共通観測経路.列図式候補',side_effect=ValueError('fixture')),patch('接続.共通観測経路.複合図式候補',return_value=語彙結果(作用=[作用()])):
   r=公開観測から候補を照会する(object(),公開入力());self.assertEqual(r['語彙別結果'][0]['結果']['適用性']['状態'],'未確認');self.assertFalse(r['次作用候補群'])
 def test_語彙は勝手に実行許可できない(self):
  a=語彙結果(作用=[作用()]);a['実行許可']=True;r=self.run_case(a,語彙結果('構造上不適用'));self.assertEqual(r['状態'],'未確認');self.assertFalse(r['次作用候補群'])
 def test_終了と不正観測では語彙を呼ばない(self):
  for state,frame in [('WIN',((0,),)),('NOT_FINISHED',((16,),)),('NOT_FINISHED',tuple((0,) for _ in range(65)))]:
   obs=公開入力();obs.状態=state;obs.最新盤面=frame
   with patch('接続.共通観測経路.列図式候補',side_effect=AssertionError('should not run')),patch('接続.共通観測経路.複合図式候補',side_effect=AssertionError('should not run')):
    r=公開観測から候補を照会する(object(),obs);self.assertFalse(r['次作用候補群'])
 def test_開始停止完了の状態を区別する(self):
  for state,expected in [('NOT_PLAYED','開始前観測'),('GAME_OVER','停止観測'),('WIN','完了観測')]:
   obs=公開入力();obs.状態=state
   self.assertEqual(公開観測から候補を照会する(object(),obs)['状態'],expected)
 def test_作用契約不正は元候補を保持して保留(self):
  for a in [{'作用番号':6,'座標':[64,0],'実行許可':False}, {'作用番号':1,'引数':{},'実行許可':False}, {'作用番号':6,'引数':{'x':0,'y':0},'実行許可':True}]:
   r=self.run_case(語彙結果(作用=[a]),語彙結果('構造上不適用'))
   self.assertEqual(r['状態'],'候補保留');self.assertFalse(r['次作用候補群']);self.assertEqual(r['語彙別結果'][0]['結果']['作用候補群'],[a])
def 観測(frames,n,level=0,guid='A',state='NOT_FINISHED',reset=False):
 return 観測する({'frame':frames,'game_id':'fixture','guid':guid,'state':state,'levels_completed':level,'win_levels':2,'available_actions':[6],'full_reset':reset},観測通番=n)
class 応答相試験(unittest.TestCase):
 def test_旧完成と新状態を分離し一作用として保持(self):
  a=観測([[[0]]],0);b=観測([[[1]],[[2]]],1,level=1);r=作用応答を相別に記録する(a,b,6)
  self.assertEqual(r['作用応答先頭差分']['差分'][0]['後'],1);self.assertEqual(r['次計画用盤面'],((2,),));self.assertEqual(r['作用選択回数'],1)
  self.assertEqual(len(r['作用内相間差分群']),1);self.assertEqual([x['応答相'] for x in r['完成評価候補群']],[0,1]);self.assertFalse(r['因果確定'])
 def test_進行なしの複数応答も別作用に増やさない(self):
  r=作用応答を相別に記録する(観測([[[0]]],0),観測([[[1]],[[2]],[[3]]],1),6)
  self.assertEqual(r['作用選択回数'],1);self.assertEqual(len(r['作用内相間差分群']),2);self.assertEqual(r['完成評価候補群'],[])
 def test_異なる実行初期化未進行を因果で結ばない(self):
  a=観測([[[0]]],0)
  for b,n in [(観測([[[1]]],1,guid='B'),6),(観測([[[1]]],1,reset=True),6),(観測([[[1]]],0),6),(観測([[[1]]],1),0)]:
   r=作用応答を相別に記録する(a,b,n);self.assertTrue(r['保留理由群']);self.assertIsNone(r['作用応答先頭差分']);self.assertTrue(r['応答全盤面'])
 def test_空終了frameでも公開終端状態は失わない(self):
  r=作用応答を相別に記録する(観測([[[0]]],0),観測([],1,state='GAME_OVER'),6)
  self.assertEqual(r['前後公開状態'][1],'GAME_OVER');self.assertTrue(r['保留理由群']);self.assertIsNone(r['作用応答先頭差分'])
 def test_完成増分だけで先頭や末尾を選ばない(self):
  for frames in ([[[1]]], [[[1]],[[1]],[[2]]], [[[i%16]] for i in range(118)]):
   r=作用応答を相別に記録する(観測([[[0]]],0),観測(frames,1,level=1),6)
   self.assertEqual(len(r['完成評価候補群']),len(frames));self.assertIsNone(r['完成相採否']['採用相'])
   self.assertEqual(r['完成相採否']['状態'],'未確認');self.assertEqual(len(r['作用内相間差分群']),len(frames)-1)
   self.assertEqual(r['作用選択回数'],1);self.assertFalse(r['因果確定'])
if __name__=='__main__':unittest.main()
