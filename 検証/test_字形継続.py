import copy,hashlib,inspect,json,os,pathlib,sys,unittest
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統,外部入力
from 接続.ARC3境界 import 観測する
from 接続.字形 import 初回作用を構成する,字形初回を照会する,字形作用応答を照合する
from 接続.字形.応答知覚 import 境界,SCOPE_X,SCOPE_Y
資料=根/'検証/資料/字形'

def obs(raw,n):return 観測する(raw,観測通番=n)
def semantic(out):
 w=next(r['証人'] for r in out['関係群'] if r['関係']=='固定演算による一つの支持証人')
 return {'全目標':[g['全欄目標'] for g in out['目標候補群']],'提示先頭':[a['作用番号'] for a in out['作用候補群'] if a['提示実行順の先頭']],'証人step数':len(w['段階']),'既達維持HDS支持':w['全字形変更stepの既達維持HDS支持']}
class 空系試験(unittest.TestCase):
 def test_空系は保留で解なし(self):
  frame=json.loads((資料/'問題完成fixture.json').read_text())['問題群'][0]['問題盤面'];r=初回作用を構成する(HDS学習系統(),frame,[0,1,2,3,4,5,6,7]);self.assertEqual(r['適用性'],'未確認');self.assertFalse(r['作用候補群']);self.assertFalse(r['実行許可'])
 def test_runtimeファイルに外部読出しや新規HDSなし(self):
  for p in (根/'接続/字形').glob('*.py'):
   s=p.read_text();self.assertNotIn('/workspace/',s);self.assertNotIn('HDS学習系統()',s);self.assertNotIn('read_text(',s);self.assertNotIn('open(',s)

@unittest.skipUnless(os.environ.get('ARC_GLYPH_HDS_STATE'),'承認済み実状態をARC_GLYPH_HDS_STATEで指定する統合試験。再学習しない')
class 実状態継続試験(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=pathlib.Path(os.environ['ARC_GLYPH_HDS_STATE']);cls.h=HDS学習系統.読み込む(cls.path)
  cls.fixture=json.loads((資料/'問題完成fixture.json').read_text());cls.events=json.loads((資料/'公開応答fixture.json').read_text())['応答群']
  cls.outputs=[初回作用を構成する(cls.h,c['問題盤面'],c['作用可能番号']) for c in cls.fixture['問題群']]
 def event(self,action=1):return next(e for e in self.events if e['作用番号']==action and e['現在生観測']['levels_completed']==e['直前生観測']['levels_completed'])
 def prepare(self,e=None):
  e=e or self.event();a=obs(e['直前生観測'],e['原行']-1);b=obs(e['現在生観測'],e['原行']);return e,a,b,字形初回を照会する(self.h,a)
 def test_00_保存済み全目標と証人の意味一致(self):
  expected=json.loads((資料/'保存状態初回期待.json').read_text())['問題からの推論']
  for actual,old in zip(self.outputs,expected):
   s=semantic(actual)
   for key in s:self.assertEqual(s[key],old[key])
   self.assertFalse(actual['実行許可'])
  self.assertEqual([len(o['目標候補群']) for o in self.outputs],[1,1,1,1,2,420])
 def test_00b_全123証人段階と既達保存を再照合(self):
  count=0
  for out in self.outputs:
   proc=next(r['手順'] for r in out['関係群'] if r['関係']=='全条件付き有限手順');w=next(r['証人'] for r in out['関係群'] if r['関係']=='固定演算による一つの支持証人');graphs=proc['欄群グラフ'];nodes=[g['初期節点'] for g in graphs];cursor=proc['カーソルグラフ']['初期節点'];target=[g['節点'].index(v) for g,v in zip(graphs,w['目標全欄'])]
   for step in w['段階']:
    count+=1;before=list(nodes);e=step['学習支持辺'];self.assertEqual(step['選択欄前'],cursor)
    if step['種別']=='選択群変更':self.assertIn(e,graphs[cursor]['辺']);self.assertEqual(e['始点'],nodes[cursor]);nodes[cursor]=e['終点']
    else:self.assertIn(e,proc['カーソルグラフ']['辺']);self.assertEqual(e['始点'],cursor);cursor=e['終点']
    for f in step['保存する既達欄']:self.assertEqual(before[f],target[f]);self.assertEqual(nodes[f],target[f])
    self.assertEqual(step['必須次段階'],'再観測');self.assertFalse(step['実行許可'])
   self.assertEqual(nodes,target)
  self.assertEqual(count,123)
 def test_01_全作用領域保持(self):
  r=初回作用を構成する(self.h,self.fixture['問題群'][0]['問題盤面'],[0,1,2,3,4,5,6,7]);domains=next(x['候補領域'] for x in r['関係群'] if x['関係']=='学習範囲外の全使用可能作用領域');self.assertEqual({x['作用番号'] for x in domains},{0,5,6,7});self.assertIn('未評価座標候補領域',next(x for x in domains if x['作用番号']==6))
 def test_02_公開実応答四作用と全相(self):
  for action in (1,2,3,4):
   e,a,b,prior=self.prepare(self.event(action));r=字形作用応答を照合する(self.h,a,b,prior,action)
   self.assertEqual(r['状態'],'全相整合・再照会成立',r['保留理由群']);self.assertEqual(len(r['全相照合']),len(b.盤面列));self.assertEqual(len(r['相記録']['応答全盤面']),len(b.盤面列));self.assertTrue(r['履歴継承']);self.assertFalse(r['実行許可'])
 def test_03_進捗応答は全相を保持して旧suffix停止(self):
  e=next(e for e in self.events if e['現在生観測']['levels_completed']>e['直前生観測']['levels_completed']);e,a,b,prior=self.prepare(e);r=字形作用応答を照合する(self.h,a,b,prior,e['作用番号'])
  self.assertEqual(len(r['全相照合']),len(b.盤面列));self.assertEqual(r['後続手順判定'],'HOLD');self.assertFalse(r['履歴継承']);self.assertTrue(r['達成照合']['実測完了増分あり']);self.assertEqual(r['旧目標候補群'],prior['目標候補群'])
 def test_04_予測と応答不一致は全代替を保持(self):
  e,a,b,prior=self.prepare();raw=copy.deepcopy(e['現在生観測']);raw['frame']=[copy.deepcopy(e['直前生観測']['frame'][-1])];b=obs(raw,e['原行']);r=字形作用応答を照合する(self.h,a,b,prior,1)
  self.assertEqual(r['状態'],'HOLD');self.assertEqual(r['旧目標候補群'],prior['目標候補群']);self.assertEqual(r['旧作用候補群'],prior['作用候補群']);self.assertIsNone(r['次照会'])
 def test_05_同一族でない相混在も全相保持(self):
  e,a,b,prior=self.prepare();raw=copy.deepcopy(e['現在生観測']);raw['frame'].append(copy.deepcopy(e['直前生観測']['frame'][-1]));r=字形作用応答を照合する(self.h,a,obs(raw,e['原行']),prior,1);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全相照合']),len(raw['frame']));self.assertIn('混在',str(r['保留理由群']))
 def test_06_RESETと別instanceは可視同一でも履歴分離(self):
  e,a,b,prior=self.prepare()
  for mode in ('RESET','guid','full_reset'):
   raw=copy.deepcopy(e['現在生観測']);action=1
   if mode=='RESET':action=0
   elif mode=='guid':raw['guid']='別公開実行'
   else:raw['full_reset']=True
   r=字形作用応答を照合する(self.h,a,obs(raw,e['原行']),prior,action);self.assertEqual(r['実行個体境界'],'初期化/別instance');self.assertFalse(r['観測履歴']);self.assertEqual(r['旧観測履歴'],prior['出所']['観測履歴']);self.assertFalse(r['履歴継承']);self.assertIsNone(r['次照会']);self.assertEqual(len(r['相記録']['応答全盤面']),len(raw['frame']))
 def test_07_前回予測対応と実選択の不一致(self):
  e,a,b,prior=self.prepare(self.event(3));r=字形作用応答を照合する(self.h,a,b,prior,4);self.assertEqual(r['状態'],'HOLD');self.assertIn('選択',str(r['保留理由群']))
  prior=copy.deepcopy(prior);prior['出所']['観測通番']-=1;r=字形作用応答を照合する(self.h,a,b,prior,3);self.assertEqual(r['状態'],'HOLD');self.assertIn('対応',str(r['保留理由群']))
 def test_08_連続応答は実選択履歴を追加し毎回再照会(self):
  seq=[e for e in self.events if e['原行'] in (1,2,3)];a=obs(seq[0]['直前生観測'],0);prior=字形初回を照会する(self.h,a)
  for i,e in enumerate(seq,1):
   b=obs(e['現在生観測'],e['原行']);r=字形作用応答を照合する(self.h,a,b,prior,e['作用番号']);self.assertEqual(r['状態'],'全相整合・再照会成立',r['保留理由群']);self.assertEqual(len(r['観測履歴']),i+1);a=b;prior=r['次照会']
 def test_09_完成答えやファイルをruntimeへ渡さない(self):
  e,a,b,prior=self.prepare()
  with patch.object(pathlib.Path,'read_text',side_effect=AssertionError('runtimeファイル読出し')):r=字形作用応答を照合する(self.h,a,b,prior,e['作用番号'])
  self.assertEqual(r['状態'],'全相整合・再照会成立');self.assertEqual(list(inspect.signature(字形初回を照会する).parameters),['学習系','現在'])
 def test_10_非一意選択と実字形別記録(self):
  e,a,b,prior=self.prepare();raw=copy.deepcopy(e['現在生観測']);raw['frame']=[[[3 if v==0 else v for v in row] for row in f] for f in raw['frame']]
  r=字形作用応答を照合する(self.h,a,obs(raw,e['原行']),prior,1);self.assertEqual(r['状態'],'HOLD');self.assertFalse(r['履歴継承']);self.assertEqual(len(r['全相照合']),len(raw['frame']));self.assertIn('選択',str(r['保留理由群']))
  good=字形作用応答を照合する(self.h,a,b,prior,1);self.assertTrue(all(x['実字形記録'] is not None for x in good['全相照合']));self.assertTrue(all('作用前実字形' in c and '作用後実字形' in c for x in good['全相照合'] for c in x['全欄照合']))
 def test_11_未支持作用も全相と代替領域を保持(self):
  e,a,b,prior=self.prepare();r=字形作用応答を照合する(self.h,a,b,prior,6);self.assertEqual(r['状態'],'HOLD');self.assertIsNone(r['予測']);self.assertEqual(r['旧全候補関係群'],prior['関係群']);self.assertEqual(len(r['全相照合']),len(b.盤面列))
 def test_12_前回予測グラフ不正を例外で落とさず保留(self):
  e,a,b,prior=self.prepare();bad=copy.deepcopy(prior);candidate=next(x for x in bad['作用候補群'] if x['作用番号']==1);candidate['学習支持辺']['終点']=None
  r=字形作用応答を照合する(self.h,a,b,bad,1);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全相照合']),len(b.盤面列));self.assertIsNone(r['次照会']);self.assertIn('前回予測',str(r['保留理由群']))
 def test_zz_同一HDS反証は全体HOLDを保つ(self):
  self.h.処理する(外部入力({SCOPE_X:False,SCOPE_Y:True},境界(1)));r=初回作用を構成する(self.h,self.fixture['問題群'][0]['問題盤面'],[1,2,3,4]);self.assertEqual(r['適用性'],'未確認');self.assertFalse(r['作用候補群']);self.assertFalse(r['実行許可'])
