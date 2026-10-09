import collections,inspect,itertools,json,pathlib,unittest
from unittest.mock import patch
from hds学習系統 import HDS学習系統,外部入力
from 接続.複合図式規則 import 複合図式攻略を照会する,複合公開教師を教える,標識適用保留理由,二色制約を解く,連動境界
資料=pathlib.Path(__file__).parent/'資料'
教師包=json.loads((資料/'複合図式公開教師.json').read_text());問題=json.loads((資料/'複合図式照合盤面.json').read_text())
支持=教師包['適用支持'];支持['記号順位対応']={int(k):v for k,v in 支持['記号順位対応'].items()}
class 複合図式試験(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # 境界単体試験用の小fixture。能力検証CLIは全818経験を投入する。
  頻度=collections.Counter();cls.単体教師=[]
  for t in 教師包['教師']:
   鍵=(t['種類'],json.dumps(t['入力'],sort_keys=True,ensure_ascii=False))
   if 頻度[鍵]<3:cls.単体教師.append(t);頻度[鍵]+=1
 def 学習機械(self):
  h=HDS学習系統();list(複合公開教師を教える(h,self.単体教師));return h
 def 照会(self,h=None,支持値=None,作用=None):
  return 複合図式攻略を照会する(問題['問題盤面'],問題['利用可能作用'] if 作用 is None else 作用,self.学習機械() if h is None else h,支持 if 支持値 is None else 支持値)
 def test_公開問題だけから条件付き13手と全目標を構成(self):
  r=self.照会();self.assertEqual(r['適用性']['状態'],'適用可能');self.assertFalse(r['保留理由群']);self.assertEqual(len(r['作用候補群']),13)
  self.assertEqual(len(r['終端目標照合']),22);self.assertTrue(all(c['一致'] for c in r['終端目標照合']));self.assertFalse(r['実行許可'])
 def test_空学習機械は解答や作用を補完しない(self):
  r=self.照会(HDS学習系統());self.assertTrue(r['保留理由群']);self.assertEqual(r['作用候補群'],[])
 def test_作用反証は解答と連動にも全体保留(self):
  h=self.学習機械();h.処理する(外部入力({'隣接方向の辺に標識あり':True,'隣接本体色が変わる':False},連動境界))
  r=self.照会(h);self.assertTrue(r['規則の不確実性']);self.assertFalse(r['作用候補群'])
 def test_不適用と解析失敗を区別(self):
  r=複合図式攻略を照会する([[0]*8 for _ in range(8)],[],HDS学習系統(),支持);self.assertEqual(r['適用性']['状態'],'構造上不適用')
  for f in (None,[],[[0],[0,1]],[[{}]],[[16]],[[-1]],[[False]],[[0]*65],[[0]]*65):
   r=複合図式攻略を照会する(f,[],HDS学習系統(),支持);self.assertEqual(r['適用性']['状態'],'未確認');self.assertTrue(r['保留理由群'])
  with patch('接続.複合図式規則.色見本候補を読む',side_effect=ValueError('fixture')):
   r=self.照会();self.assertEqual(r['適用性']['状態'],'未確認');self.assertTrue(r['保留理由群'])
 def test_教師支持欠損と未知色は保留(self):
  for s in ({},{'記号順位対応':[], '標識色群':None},{**支持,'標識色群':[]}):
   r=self.照会(支持値=s);self.assertTrue(r['保留理由群']);self.assertFalse(r['作用候補群'])
  self.assertIsNotNone(標識適用保留理由({'幅':3,'格子間隔':4,'標識画素':[[1,0,99]]},標識色群=[6]))
 def test_不完全な標識や縮尺は適用しない(self):
  for c in ({'幅':3,'格子間隔':4,'標識画素':[[0,0,6]]},{'幅':6,'格子間隔':8,'標識画素':[[2,0,6]]},{'幅':3,'格子間隔':8,'標識画素':[]}):self.assertIsNotNone(標識適用保留理由(c,標識色群=[6]))
 def test_利用可能作用を確認する(self):
  for actions in ([],[1],None):
   r=複合図式攻略を照会する(問題['問題盤面'],actions,self.学習機械(),支持);self.assertTrue(r['保留理由群']);self.assertFalse(r['作用候補群'])
 def test_全三変数制約は全探索と一致し候補を落とさない(self):
  n=3
  for columns in itertools.product(range(1<<n),repeat=n):
   for target in range(1<<n):
    expected=set()
    for x in range(1<<n):
     z=0
     for j,c in enumerate(columns):
      if (x>>j)&1:z^=c
     if z==target:expected.add(x)
    r=二色制約を解く(columns,target,n)
    if r is None:self.assertFalse(expected);continue
    actual={r['特解']}
    for v in r['同次解基底']:actual|={x^v for x in list(actual)}
    self.assertEqual(actual,expected);self.assertEqual(r['候補数'],len(expected))
 def test_教師以外の原票識別子や答えを推論引数に持たない(self):
  self.assertEqual(list(inspect.signature(複合図式攻略を照会する).parameters),['盤面','利用可能作用','学習系','適用支持']);self.assertEqual(len(教師包['教師']),818)
  with self.assertRaises(ValueError):list(複合公開教師を教える(HDS学習系統(),[{'種類':'未定義','入力':{}}]))
if __name__=='__main__':unittest.main()

class 原票評価境界試験(unittest.TestCase):
 def test_原票digestと複数応答を保留する(self):
  import tempfile,hashlib
  from 道具.複合図式教師検証 import 公開作用を照合する
  f=問題['問題盤面'];before={'frame':[f],'guid':'fixture','game_id':'fixture','available_actions':[6]}
  after={**before,'frame':[f,f],'action_input':{'id':6,'data':{'x':1,'y':1}}}
  raw=''.join(json.dumps({'data':x})+'\n' for x in (before,after)).encode()
  with tempfile.TemporaryDirectory() as d:
   pathlib.Path(d,'fixture.recording.jsonl').write_bytes(raw)
   p={'作用評価範囲':[{'実行識別子':'fixture','開始行':0,'終了行':1}]}
   t={'出所一覧':[{'実行識別子':'fixture','原票SHA256':'incorrect'}],'適用支持':支持}
   with self.assertRaises(ValueError):公開作用を照合する(HDS学習系統(),t,p,d)
   t['出所一覧'][0]['原票SHA256']=hashlib.sha256(raw).hexdigest();r=公開作用を照合する(HDS学習系統(),t,p,d)
   self.assertEqual(r['全操作数'],1);self.assertEqual(r['対応操作数'],0)
   self.assertEqual(r['記録'][0]['保留理由群'],[{'複数応答相':2}])
