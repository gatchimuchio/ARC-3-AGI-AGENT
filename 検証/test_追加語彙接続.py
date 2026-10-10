import copy,json,pathlib,sys,unittest
from types import SimpleNamespace
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.追加語彙接続 import 形状作用の範囲を読む,形状語彙を接続する,鎖語彙を接続する,_盤面
from 接続.形状配置知覚 import 形状場面を読む
from 接続.共通観測経路 import 公開観測から候補を照会する
from 接続.ARC3境界 import 境界違反

def 結果(状態='構造上不適用',**kw):
 return {'適用性':{'状態':状態},'作用候補群':[],'目標候補群':[],'実行許可':False,**kw}
def 作用(n=1,xy=None):return {'作用番号':n,'引数':{} if xy is None else dict(zip(('x','y'),xy)),'実行許可':False}
def 経路(i,支持=True,候補=None):
 return {'経路参照':i,'採否':'全段支持' if 支持 else '断定保留','段階群':[{'作用候補群':候補 or [作用()], '実行許可':False}],
  '全目標充足':True,'保留理由群':[] if 支持 else ['未支持辺'],'実行許可':False}
class 追加語彙試験(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.例=json.loads((根/'検証/資料/形状配置照合資料.json').read_text())['例群']
  cls.鎖=json.loads((根/'入力/鎖教師/関係教材.json').read_text())['初期観測']['frame']
 def common(self,新,他=None):
  h=object();o=SimpleNamespace(最新盤面=((0,),),作用可能番号=(1,2,3,4,5,6),状態='NOT_FINISHED',観測通番=0,指紋='test')
  with patch('接続.共通観測経路.列図式候補',return_value=結果()),patch('接続.共通観測経路.複合図式候補',return_value=結果()),patch('接続.共通観測経路.鎖語彙を接続する',return_value=新) as a,patch('接続.共通観測経路.形状語彙を接続する',return_value=他 or 結果()) as b:
   r=公開観測から候補を照会する(h,o);self.assertIs(a.call_args.args[0],h);self.assertIs(b.call_args.args[0],h);return r
 def test_支持と未支持経路は共存(self):
  r=self.common(結果('適用可能',作用段階経路群=[経路(0),経路(1,False)]))
  self.assertEqual(r['状態'],'条件付き候補');self.assertEqual(len(r['次作用候補群']),1);self.assertEqual(len(r['候補経路群']),2)
  self.assertEqual(r['候補経路群'][1]['採否'],'保留');self.assertFalse(r['実行許可'])
 def test_同値座標と同じ作用の支持経路を削らない(self):
  r=self.common(結果('適用可能',作用段階経路群=[経路(i,候補=[作用(6,(x,0)) for x in range(9)]) for i in range(2)]))
  self.assertEqual(len(r['次作用候補群']),18)
  self.assertEqual(len({json.dumps(x['候補']['引数']) for x in r['次作用候補群']}),9)
 def test_後段未支持を先頭支持で埋めない(self):
  p=経路(0);p['段階群'].append({'作用候補群':[],'実行許可':False})
  r=self.common(結果('適用可能',作用段階経路群=[p,経路(1)]))
  self.assertEqual(len(r['候補経路群']),2);self.assertEqual([x['支持経路参照'] for x in r['次作用候補群']],[1])
 def test_目標適用性と作用適用性を別に保持(self):
  g=結果('適用可能',作用適用性={'状態':'構造上不適用'},目標候補群=[{'支持目標':True}])
  r=self.common(結果('適用可能',作用段階経路群=[経路(0)]),g)
  self.assertEqual(r['状態'],'条件付き候補');self.assertEqual(r['全目標候補群'][-1]['候補群'],g['目標候補群'])
  self.assertEqual(r['語彙別結果'][-1]['結果']['適用性']['状態'],'適用可能')
 def test_未同定と隔離は構造不適用にしない(self):
  for k,v,state in [('作用適用性',{'状態':'未確認'},'未確認'),('規則不確実性',[{'全体隔離':['反証']}],'HDS保留')]:
   g=結果('適用可能',**{k:v});r=self.common(結果('適用可能',作用段階経路群=[経路(0)]),g)
   self.assertEqual(r['状態'],state);self.assertFalse(r['次作用候補群']);self.assertEqual(r['語彙別結果'][-1]['結果']['適用性']['状態'],'適用可能')
 def test_tuple正規化と作用重複拒否(self):
  a,n=_盤面(((0,1),(2,3)),(1,6));self.assertEqual(a,[[0,1],[2,3]]);a[0][0]=4
  with self.assertRaises(境界違反):_盤面(((0,),),(1,1))
 def test_作用範囲外でも全目標関係を保持(self):
  h=HDS学習系統()
  for e in self.例[1:7]:
   r=形状語彙を接続する(h,e['問題盤面'],(1,2,3,4,6))
   self.assertEqual(r['適用性']['状態'],'適用可能');self.assertTrue(r['目標候補群']);self.assertFalse(r['作用段階経路群']);json.dumps(r)
 def test_未観測と結合は未知のまま(self):
  scene=形状場面を読む(self.例[0]['問題盤面']);frame=self.例[0]['問題盤面']
  self.assertEqual(形状作用の範囲を読む(scene,frame)['状態'],'適用可能')
  s=copy.deepcopy(scene);s['目標'][0]['未観測枠']=True
  self.assertEqual(形状作用の範囲を読む(s,frame)['状態'],'未確認')
  s=copy.deepcopy(scene);s['対象'][0]['点']=s['対象'][0]['点']|s['対象'][1]['点'];s['対象']=s['対象'][:1]
  self.assertEqual(形状作用の範囲を読む(s,frame)['状態'],'未確認')
 def test_鎖区切り不在と解析例外の区別(self):
  self.assertEqual(鎖語彙を接続する(object(),[[0]*64 for _ in range(64)],(1,))['適用性']['状態'],'構造上不適用')
  with patch('接続.追加語彙接続.鎖画素.parse',side_effect=ValueError('解析故障')):
   with self.assertRaisesRegex(ValueError,'解析故障'):鎖語彙を接続する(object(),self.鎖,(1,2,3,4,6))
 def test_起点零と複数と記号解析例外を区別(self):
  from 接続.列図式規則 import 候補を構成する,容器外形を観測する
  from collections import Counter
  bg=Counter(v for row in self.鎖 for v in row).most_common()[0][0]
  boxes=容器外形を観測する(self.鎖,bg)
  self.assertTrue(boxes);self.assertFalse(any(b['起点'] for b in boxes))
  r=候補を構成する(object(),self.鎖,作用可能番号=[1])
  self.assertEqual(r['適用性']['状態'],'構造上不適用')
  for boxes,token in [([{'起点':True,'枠群':[]},{'起点':True,'枠群':[]}],None),([{'起点':True,'枠群':[{'位置':[1,1]}]}],ValueError('記号解析故障'))]:
   with patch('接続.列図式規則.容器外形を観測する',return_value=boxes),patch('接続.列図式規則.記号を読む',side_effect=token):
    r=候補を構成する(object(),self.鎖,作用可能番号=[1])
   self.assertEqual(r['適用性']['状態'],'未確認')
 def test_共通入口の解析例外は未確認(self):
  o=SimpleNamespace(最新盤面=self.鎖,作用可能番号=(1,2,3,4,6),状態='NOT_FINISHED',観測通番=0,指紋='test')
  with patch('接続.共通観測経路.列図式候補',return_value=結果()),patch('接続.共通観測経路.複合図式候補',return_value=結果()),patch('接続.共通観測経路.鎖語彙を接続する',side_effect=ValueError('解析故障')),patch('接続.共通観測経路.形状語彙を接続する',return_value=結果()):
   r=公開観測から候補を照会する(object(),o)
  self.assertEqual(r['状態'],'未確認');self.assertEqual(r['語彙別結果'][2]['結果']['適用性']['状態'],'未確認')
if __name__=='__main__':unittest.main()
