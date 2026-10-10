import unittest,json,os,pathlib,types,gzip,tempfile
from 接続.巡回規則 import 候補を構成する,観測から候補を構成する
from 接続.共通観測経路 import _作用候補を共通化する
from 接続.ARC3境界 import 観測する
BASE=pathlib.Path(__file__).parent

def frame(name='単純閉路'):return json.loads((BASE/'fixture'/(name+'.json')).read_text())
class 仮照会:
 def __init__(self):self.calls=[];self.hold=False
 def 照会する(self,i):
  self.calls.append(i);key,v=next(iter(i.内容.items()));result={'全標識色一致':'完了カウンタ更新','操作標識矩形内':'トークン色移動','候補は矢印向き一位置巡回':'全トークン予測色一致','候補は標識向き一位置巡回':'全トークン予測色一致'}[key]
  return types.SimpleNamespace(状態='断定保留' if self.hold else '出力',内容={'予測群':[] if self.hold else [{'結果経路':(result,),'予測値':v,'原理参照':'単体試験の仮出力'}]})
class 接続単体(unittest.TestCase):
 def test_全状態辺goal最短親(self):
  h=仮照会();r=候補を構成する(h,frame(),作用可能番号=[6]);g=r['全遷移計画'];self.assertEqual(len(g['全状態']),20);self.assertEqual(len(g['全作用辺']),40);self.assertEqual(len(g['全目標状態']),1);self.assertEqual(g['最短目標距離'],5);self.assertEqual(len(r['作用候補群']),2);self.assertEqual(len(r['次作用候補群']),1);self.assertFalse(r['実行許可'])
  self.assertEqual(sum(len(n['全最短親']) for n in g['全状態']),20)
  for a in r['作用候補群']:self.assertFalse(_作用候補を共通化する(a,(6,))['実行許可'])
 def test_現在HDSを毎回照会(self):
  h=仮照会();r=候補を構成する(h,frame(),作用可能番号=[6]);n=len(h.calls);self.assertTrue(r['作用候補群']);h.hold=True;r=候補を構成する(h,frame(),作用可能番号=[6]);self.assertGreater(len(h.calls),n);self.assertFalse(r['作用候補群']);self.assertEqual(r['全遷移計画']['網羅性'],'未着手');self.assertTrue(r['規則不確実性'])
 def test_ID変更と出所非使用(self):
  def obs(gid):return 観測する({'game_id':gid,'frame':[frame()],'state':'NOT_FINISHED','available_actions':[6]},観測通番=3)
  a=観測から候補を構成する(仮照会(),obs('arbitrary-a'));b=観測から候補を構成する(仮照会(),obs('unrelated-b'));a.pop('出所');b.pop('出所');self.assertEqual(a,b)
  class 禁止ID:
   状態='NOT_FINISHED';最新盤面=frame();作用可能番号=(6,);観測通番=1;指紋='opaque'
   @property
   def ゲーム識別子(self):raise AssertionError('ゲームIDを読んだ')
   @property
   def 完了レベル数(self):raise AssertionError('levelを読んだ')
  self.assertTrue(観測から候補を構成する(仮照会(),禁止ID())['作用候補群'])
 def test_途中状態と範囲外(self):
  r=候補を構成する(仮照会(),frame('途中閉路'),作用可能番号=[6]);self.assertEqual(r['全遷移計画']['最短目標距離'],4)
  r=候補を構成する(仮照会(),frame('分断十字'),作用可能番号=[6]);self.assertFalse(r['作用候補群']);self.assertTrue(r['未同定作用群'])
 def test_空未知不正は照会前HOLD(self):
  bad=frame();bad[3][3]=13
  for f in (None,[],[[0]],[[4]*64]*64,[[16]*64]*64,bad):
   h=仮照会();r=候補を構成する(h,f,作用可能番号=[6]);self.assertFalse(r['作用候補群']);self.assertEqual(len(h.calls),0);self.assertFalse(r['実行許可'])
 def test_非進行状態と利用可能作用(self):
  h=仮照会();r=候補を構成する(h,frame(),作用可能番号=[]);self.assertFalse(r['作用候補群']);self.assertFalse(h.calls)
  for state in ('WIN','GAME_OVER','NOT_PLAYED'):
   r=観測から候補を構成する(h,types.SimpleNamespace(状態=state,観測通番=1,指紋='x'));self.assertFalse(r['作用候補群']);self.assertFalse(h.calls)

class 採否保持(unittest.TestCase):
 def test_全kの原照会を保持(self):
  h=仮照会();r=候補を構成する(h,frame(),作用可能番号=[6]);ms=r['全遷移計画']['作用モデル群']
  for m in ms:
   qs=m['全変位候補判定'];self.assertEqual([q['相対変位'] for q in qs],list(range(20)));self.assertEqual([q['HDS判定']['判定'] for q in qs].count('支持'),1)
   for q in qs:self.assertIn('原照会',q['HDS判定']);self.assertEqual(q['HDS判定']['入力']['文脈'],{})
 def test_一候補照会例外と正常候補を保持(self):
  class 一回故障(仮照会):
   def 照会する(self,i):
    if len(self.calls)==2:self.calls.append(i);raise RuntimeError('一候補だけ故障')
    return super().照会する(i)
  r=候補を構成する(一回故障(),frame(),作用可能番号=[6]);self.assertEqual(len(r['作用モデル群']),1)
  held=[q for v in r['未同定作用群'] for q in v.get('全変位候補判定',[])];self.assertEqual(len(held),20);self.assertTrue(any(q['HDS判定']['判定']=='例外' for q in held));self.assertTrue(r['規則不確実性'])
 def test_作用計算例外でグラフを捨てない(self):
  from unittest.mock import patch
  from 接続.巡回内部.単純閉路 import shift
  calls=[0]
  def failed(*a):
   calls[0]+=1
   if calls[0]==2:raise RuntimeError('作用計算の一回故障')
   return shift(*a)
  with patch('接続.巡回内部.計画.shift',side_effect=failed):r=候補を構成する(仮照会(),frame(),作用可能番号=[6])
  g=r['全遷移計画'];self.assertGreater(len(g['全状態']),1);self.assertGreater(len(g['全作用辺']),0);self.assertEqual(len(g['未評価作用辺']),1);self.assertEqual(g['網羅性'],'未完了');self.assertEqual(r['計画状態'],'HOLD');self.assertEqual(len(r['作用候補群']),2);self.assertFalse(r['次作用候補群'])
 def test_非クリック作用を捨てない(self):
  r=候補を構成する(仮照会(),frame(),作用可能番号=[0,1,5,6,7]);self.assertEqual([v['作用番号'] for v in r['未評価作用候補群']],[0,1,5,7]);self.assertTrue(all(v['採否']=='HOLD' for v in r['未評価作用候補群']))
 def test_観測上の目標充足を公式完了にしない(self):
  from 接続.巡回内部.計画 import models
  from 接続.巡回内部.単純閉路 import shift
  from 接続.巡回内部.画素 import perception
  f=frame();h=仮照会();ms,_=models(f,h);p=perception(f);m=next(m for m in ms if m['符号']==-1);cs=shift([t['色'] for t in p['トークン']],m['位置列'],-1,5)
  for t,c in zip(p['トークン'],cs):
   x,y,r,b=t['範囲']
   for yy in range(y,b+1):
    for xx in range(x,r+1):f[yy][xx]=c
  r=候補を構成する(h,f,作用可能番号=[6]);self.assertTrue(r['観測目標充足']);self.assertFalse(r['公式完了確認']);self.assertEqual(r['計画状態'],'観測目標充足');self.assertFalse(r['次作用候補群']);self.assertIn(0,r['全遷移計画']['全目標状態']);self.assertEqual(len(r['全遷移計画']['全状態']),20)
 def test_巨大または重複支持域は切り詰めない(self):
  from 接続.巡回内部.計画 import domain_size
  ms=[{'位置列':[i,i+1],'変位':1} for i in range(0,20,2)];n,reason=domain_size(tuple(range(20)),ms);self.assertEqual(n,1024);self.assertIsNone(reason)
  n,reason=domain_size(tuple(range(3)),[{'位置列':[0,1],'変位':1},{'位置列':[1,2],'変位':1}]);self.assertIsNone(n);self.assertTrue(reason)

class 画素資源境界(unittest.TestCase):
 def test_未説明背景と標識空隙(self):
  from 接続.巡回内部.画素 import perception,parse
  import copy
  f=frame();p=perception(f);mark=parse(f)['標識群'][0];arrow=p['操作標識'][0];x,y,r,b=arrow['範囲']
  blank=next((xx,yy) for yy in range(y,b+1) for xx in range(x,r+1) if f[yy][xx]==4)
  mx,my,_,_=mark['範囲'];d=mark['寸法'];gap=(mx+d,my)
  for point,color in [(blank,13),(blank,3),(gap,13),(gap,3),((30,30),3)]:
   bad=copy.deepcopy(f);xx,yy=point;bad[yy][xx]=color;h=仮照会();r=候補を構成する(h,bad,作用可能番号=[6]);self.assertFalse(h.calls);self.assertFalse(r['作用候補群'])
 def test_外部資源上限とfrontier(self):
  r=候補を構成する(仮照会(),frame(),作用可能番号=[6],検証状態上限=19);g=r['全遷移計画'];self.assertEqual(r['計画状態'],'HOLD');self.assertEqual(g['全到達状態数算定'],20);self.assertEqual(g['未展開状態'],[0]);self.assertEqual(len(r['作用候補群']),2);self.assertFalse(r['次作用候補群']);self.assertEqual(g['全作用辺'],[])
  r=候補を構成する(仮照会(),frame(),作用可能番号=[6],検証状態上限=20);self.assertEqual(len(r['全遷移計画']['全状態']),20)
  for value in (0,-1,True,None):
   r=候補を構成する(仮照会(),frame(),作用可能番号=[6],検証状態上限=value);self.assertEqual(r['計画状態'],'HOLD');self.assertFalse(r['次作用候補群'])
 def test_WIN入口と可視完成の区別(self):
  h=仮照会();r=観測から候補を構成する(h,types.SimpleNamespace(状態='WIN',観測通番=1,指紋='x',作用可能番号=(6,)));self.assertTrue(r['公式完了確認']);self.assertFalse(r['作用候補群']);self.assertFalse(h.calls)

@unittest.skipUnless(os.environ.get('ARC_LOOP_TRAINED_HDS'),'実94状態の明示指定なし')
class 実HDS接続(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from hds学習系統 import HDS学習系統
  cls.Type=HDS学習系統;cls.h=HDS学習系統.読み込む(os.environ['ARC_LOOP_TRAINED_HDS'])
 def test_実94と空(self):
  r=候補を構成する(self.h,frame(),作用可能番号=[6]);self.assertEqual(r['全遷移計画']['最短目標距離'],5);self.assertEqual(len(r['全遷移計画']['全状態']),20)
  r=候補を構成する(self.Type(),frame(),作用可能番号=[6]);self.assertFalse(r['作用候補群']);self.assertEqual(r['全遷移計画']['網羅性'],'未着手')
 def test_実95反証(self):
  path=os.environ.get('ARC_LOOP_CONTRADICTION_HDS')
  if not path:self.skipTest('実95圧縮状態の明示指定なし')
  with gzip.open(path,'rb') as f:data=f.read()
  with tempfile.NamedTemporaryFile() as f:
   f.write(data);f.flush();bad=self.Type.読み込む(f.name)
  r=候補を構成する(bad,frame(),作用可能番号=[6]);self.assertFalse(r['作用候補群']);self.assertEqual(r['全遷移計画']['網羅性'],'未着手');self.assertTrue(r['規則不確実性'])
if __name__=='__main__':unittest.main()
