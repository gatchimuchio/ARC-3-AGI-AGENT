import pathlib,sys,tempfile,json,unittest
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC3境界 import 観測する
from 接続.観測駆動一巡 import 記録観測の一巡を処理する,原記憶保存失敗,_候補予測を復元する,_公開報酬を記録する
from 接続 import 観測駆動一巡 as M

def obs(n=0,guid='A',actions=(5,6)):
 return 観測する({'game_id':'fixture','guid':guid,'state':'NOT_FINISHED','frame':[[[0,0],[0,0]]],'available_actions':list(actions),'levels_completed':0,'win_levels':1},観測通番=n)
def candidates(o,action=5,args=None):
 return {'状態':'条件付き候補','出所':{'観測通番':o.観測通番,'観測指紋':o.指紋},'規則不確実性':[],'保留理由群':[],
  '次作用候補群':[{'語彙':'複合配色','候補':{'作用番号':action,'引数':args or {},'実行許可':False}}],
  '語彙別結果':[{'語彙':'複合配色','結果':{'適用性':{'状態':'未確認'},'目標候補群':[{'位置':[0,0],'本体画素':[[0,0],[1,0],[0,1],[1,1]]}]}}]}
class 一巡試験(unittest.TestCase):
 def run_case(self,root,b=None,action=None,candidate=None):
  a=obs();b=b or obs(1);action=action or {'作用番号':5,'引数':{}};candidate=candidate or candidates(a)
  with patch('接続.観測駆動一巡.公開観測から候補を照会する',side_effect=[candidate,candidates(b)]) as q:
   r=記録観測の一巡を処理する(object(),a,action,b,記憶先=root,出所={'試験':'合成負例'})
   self.assertEqual(q.call_count,2)
  return r
 def test_一致と無変化でもhiddenなしと即断しない(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.run_case(d);e=r['記録'];self.assertEqual(e['候補との作用照合']['状態'],'完全一致');self.assertEqual(e['不可視状態差分']['状態'],'未観測');self.assertFalse(e['環境作用送信']);self.assertFalse(e['追加学習'])
   self.assertTrue(e['因果候補']['時間的先行確認']);self.assertEqual(e['可視差分']['作用応答先頭差分']['差分'],[]);self.assertTrue(pathlib.Path(r['記憶参照']['原票']).exists());self.assertTrue(pathlib.Path(r['記憶参照']['結果']).exists())
 def test_別座標の同じ本体でも厳密不一致を残す(self):
  with tempfile.TemporaryDirectory() as d:
   r=self.run_case(d,action={'作用番号':6,'引数':{'x':1,'y':0}},candidate=candidates(obs(),6,{'x':0,'y':0}))['記録']
   self.assertEqual(r['候補との作用照合']['状態'],'候補と不一致');self.assertEqual(r['候補と記録座標の可視関係'][0]['可視関係'],'同じ本体mask内の座標');self.assertFalse(r['環境作用送信'])
 def test_途中例外にも原票と失敗結果を保存(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('接続.観測駆動一巡.公開観測から候補を照会する',side_effect=RuntimeError('fixture')):
    with self.assertRaises(RuntimeError):記録観測の一巡を処理する(object(),obs(),{'作用番号':5,'引数':{}},obs(1),記憶先=d,出所={})
   self.assertEqual(len(list(pathlib.Path(d).glob('*/原票.json'))),1);r=json.loads(next(pathlib.Path(d).glob('*/結果.json')).read_text());self.assertEqual(r['処理状態'],'途中例外');self.assertEqual(r['失敗']['型'],'RuntimeError')
 def test_初回保存失敗ならHDS照会を始めない(self):
  with tempfile.TemporaryDirectory() as d,patch('接続.観測駆動一巡.証拠を確定する',side_effect=OSError('disk failure')),patch('接続.観測駆動一巡.公開観測から候補を照会する') as q:
   with self.assertRaises(原記憶保存失敗) as e:記録観測の一巡を処理する(object(),obs(),{'作用番号':5,'引数':{}},obs(1),記憶先=d,出所={})
   q.assert_not_called();self.assertIn('観測後状態',e.exception.未保存記録);self.assertTrue(pathlib.Path(e.exception.保存参照['一時証拠']).exists())
 def test_最終保存失敗でも原票と未保存結果を失わない(self):
  replace=M.証拠を確定する
  def fail(src,dst,**kwargs):
   if pathlib.Path(dst).name=='結果.json':raise OSError('result failure')
   return replace(src,dst,**kwargs)
  with tempfile.TemporaryDirectory() as d,patch('接続.観測駆動一巡.証拠を確定する',side_effect=fail):
   with self.assertRaises(原記憶保存失敗) as e:self.run_case(d)
   self.assertEqual(len(list(pathlib.Path(d).glob('*/原票.json'))),1);self.assertIn('次観測候補',e.exception.未保存記録);self.assertTrue(pathlib.Path(e.exception.保存参照['一時証拠']).exists())
 def test_既存結果の更新を許可する(self):
  with tempfile.TemporaryDirectory()as d:
   path=pathlib.Path(d)/'結果.json';M._保存する(path,{'状態':'受領'});M._保存する(path,{'状態':'照会完了'})
   self.assertEqual(json.loads(path.read_text()),{'状態':'照会完了'})
 def test_公開後故障でも元仮証拠と未保存記録を保持する(self):
  real=M.証拠を確定する
  def bad(src,dst,**kwargs):
   real(src,dst,**kwargs)
   raise OSError('人工公開後同期故障')
  with tempfile.TemporaryDirectory()as d,patch.object(M,'証拠を確定する',side_effect=bad):
   path=pathlib.Path(d)/'結果.json'
   with self.assertRaises(原記憶保存失敗)as e:M._保存する(path,{'状態':'照会完了'})
   self.assertTrue(path.exists());self.assertTrue(pathlib.Path(e.exception.保存参照['一時証拠']).exists());self.assertEqual(e.exception.未保存記録,{'状態':'照会完了'})
 def test_実行順序可用性の不整合を保存(self):
  for b,action in [(obs(1,'B'),{'作用番号':5,'引数':{}}),(obs(0),{'作用番号':5,'引数':{}}),(obs(1),{'作用番号':1,'引数':{}})]:
   with tempfile.TemporaryDirectory() as d:
    r=self.run_case(d,b,action)['記録'];self.assertTrue(r['可視差分']['保留理由群']);self.assertFalse(r['環境作用送信']);self.assertFalse(r['因果候補']['時間的先行確認'])
 def test_候補予測の前状態不一致を実測照合へ流さない(self):
  c=candidates(obs(),6,{'x':0,'y':0});c['次作用候補群'][0]['候補']['元候補']={'全対象予測差分':[{'対象':[0,0],'前':1,'後':2}]}
  p,r=_候補予測を復元する(obs(),c,[0]);self.assertIsNone(p);self.assertTrue(r['未確認'])
 def test_異なる予測を一つへ勝手に選ばない(self):
  import copy
  c=candidates(obs(),6,{'x':0,'y':0});c['次作用候補群'][0]['候補']['元候補']={'全対象予測差分':[{'対象':[0,0],'前':0,'後':1}]};c['次作用候補群'].append(copy.deepcopy(c['次作用候補群'][0]));c['次作用候補群'][1]['候補']['元候補']['全対象予測差分'][0]['後']=2
  p,r=_候補予測を復元する(obs(),c,[0,1]);self.assertIsNone(p);self.assertEqual(r['異なる画素予測数'],2);self.assertEqual(len(r['全候補予測']),2)
 def test_完了成功評価を報酬に読み替えない(self):
  for value in (None,{}, {'levels_completed':1,'state':'WIN'},{'success':True},{'reward':1},{'reward':True,'出所':{'原票':'fixture'}},{'reward':None,'出所':{'原票':'fixture'}}):
   self.assertEqual(_公開報酬を記録する(value)['状態'],'未観測')
  source={'原票':'公開fixture','field':'reward'};r=_公開報酬を記録する({'reward':0.0,'出所':source,'levels_completed':1});self.assertEqual(r['値'],0.0);self.assertEqual(r['出所'],source)
if __name__=='__main__':unittest.main()
