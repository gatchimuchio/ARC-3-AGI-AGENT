import pathlib,sys,json,collections,unittest
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統,外部入力
from 接続.複合図式規則 import 複合公開教師を教える
from 接続.図式許容集合 import 許容集合を含む図式攻略を照会する,許容役割教師を教える,許容役割境界,条件付き操作を合成する,許容集合適用保留
from 接続.共通観測経路 import 公開観測から候補を照会する
from 接続.ARC3境界 import 観測する
資料=根/'検証/資料';基底=json.loads((資料/'複合図式公開教師.json').read_text());追加=json.loads((資料/'図式許容集合教師.json').read_text());問題=json.loads((資料/'図式許容集合照合.json').read_text())['例群'][0];支持=基底['適用支持'];支持['記号順位対応']={int(k):v for k,v in 支持['記号順位対応'].items()}
class 許容集合試験(unittest.TestCase):
 def 系(self,追加あり=True):
  h=HDS学習系統();頻度=collections.Counter();小教師=[]
  for t in 基底['教師']:
   k=(t['種類'],json.dumps(t['入力'],sort_keys=True));頻度[k]+=1
   if 頻度[k]<=3:小教師.append(t)
  list(複合公開教師を教える(h,小教師))
  if 追加あり:list(許容役割教師を教える(h,追加['教師']))
  return h
 def query(self,h):return 許容集合を含む図式攻略を照会する(問題['問題盤面'],問題['利用可能作用'],h,支持)
 def test_二つの支持経路を保持(self):
  r=self.query(self.系());self.assertFalse(r['保留理由群']);self.assertEqual([len(p['作用候補']) for p in r['全条件付き経路群']],[21,22]);self.assertTrue(all(p['全目標充足'] for p in r['全条件付き経路群']));self.assertFalse(r['実行許可'])
 def test_追加教師なしは許容集合を補完しない(self):
  r=self.query(self.系(False));self.assertTrue(r['保留理由群']);self.assertFalse(r['全条件付き経路群'])
 def test_追加役割反証は全体保留(self):
  h=self.系();h.処理する(外部入力({'図式から参照される':False,'成功完成で色列全色の支持あり':False},許容役割境界));r=self.query(h);self.assertTrue(r['保留理由群']);self.assertFalse(r['全条件付き経路群'])
 def test_共通入口は各経路の先頭を保持(self):
  o=観測する({'frame':[問題['問題盤面']],'state':'NOT_FINISHED','available_actions':問題['利用可能作用'],'game_id':'任意名','guid':'任意実行','levels_completed':0,'win_levels':1},観測通番=1)
  r=公開観測から候補を照会する(self.系(),o,図式適用支持=支持);self.assertEqual(r['状態'],'条件付き候補');self.assertEqual(len(r['次作用候補群']),2);self.assertEqual([len(p['経路']) for p in r['候補経路群']],[21,22]);self.assertFalse(r['規則不確実性']);self.assertFalse(r['実行許可'])
 def test_部分照会HOLDを完成にしない(self):
  k=(0,0);r=条件付き操作を合成する([k],{k:0},{k:{0,1}},[1],1,lambda _: {'状態':'HOLD'});self.assertFalse(r['全目標充足']);self.assertFalse(r['合成完了'])
 def test_未支持の構造範囲を拒否(self):
  p={'色列':[0,1,2],'格子位相群':[1],'参照対象群':[1]};c={'位置':[0,0],'標識画素':[]};self.assertTrue(許容集合適用保留(p,c,0,[(0,0)],[]))
if __name__=='__main__':unittest.main()
