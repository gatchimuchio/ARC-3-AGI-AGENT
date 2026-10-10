import sys,json,tempfile,unittest,copy,gzip
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE),str(BASE/'HDS/学習系統/v0.4.2')]
from 接続.配色接続 import 配色候補を作る,配色全応答を照合
from 接続.配色教師CLI import 資料を読む,保存状態を読む,確認保存,教材を教える,検証する
from 接続.配色内部.関係 import HDS学習系統,外部入力,COPY,X,Y
from 接続.配色内部.予測 import predict,クリック位置の支持
from 接続.配色内部.知覚 import read
from 接続.配色内部.固定文法 import 配置文法
class 配色検証(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.raw=資料を読む('公開原票.json.gz')[0]['全行'];cls.rows=[r['data'] for r in cls.raw];cls.frame=cls.rows[0]['frame'][-1];cls.h=保存状態を読む()
 def response(self,b=None,a=None,action=None,h=None,history=None):
  b=copy.deepcopy(self.rows[4]) if b is None else b;a=copy.deepcopy(self.rows[3]) if a is None else a
  return 配色全応答を照合(a,b,b.get('action_input') if action is None else action,self.h if h is None else h,観測履歴=history,前通番=3,後通番=4)
 def test_空状態全候補保留(self):
  r=配色候補を作る(self.frame,[1,2,3,4,5,6],HDS学習系統(),経路も作る=False);self.assertEqual(len(r['全作用候補']),4101);self.assertTrue(all(c['状態']=='HOLD' for c in r['全作用候補']))
 def test_盤面境界は照会前(self):
  bad=[[],None,[[0],[]],[[True]],[[16]],[[-1]],[[1.0]],[['1']],[[0]*65 for _ in range(64)],[[0]*64 for _ in range(65)],self.frame[:-1],[r[:-1]for r in self.frame]]
  class 拒否:
   def __init__(self):self.回数=0
   def 照会する(self,*a):self.回数+=1;raise AssertionError('境界前照会')
  for f in bad:
   spy=拒否();r=配色候補を作る(f,[1,2,3,4,5,6],spy);self.assertEqual(spy.回数,0);self.assertEqual(r['状態'],'HOLD');self.assertEqual(len(r['全作用候補']),4101);self.assertNotIn('境界前照会',str(r))
 def test_空白盤面空解を成功としない(self):
  r=配色候補を作る([[5]*64 for _ in range(64)],[1,6],self.h);self.assertEqual(r['状態'],'HOLD');self.assertEqual(r['全代表経路'],[])
 def test_tuple入力正規化(self):
  r=配色候補を作る(tuple(map(tuple,self.frame)),[1],HDS学習系統(),経路も作る=False);self.assertEqual(len(r['全作用候補']),1)
 def test_未知クリック全座標保持(self):
  r=配色候補を作る(self.frame,[6],self.h,経路も作る=False);self.assertEqual(len(r['全作用候補']),4096);self.assertTrue(any(c['状態']=='HOLD' for c in r['全作用候補']));self.assertTrue(any(c['状態']!='HOLD' for c in r['全作用候補']))
 def test_未観測矩形端は同値としない(self):
  s=read(self.frame);x,y,_,_=s['色見本'][0]['矩形'];self.assertFalse(クリック位置の支持(s,{'id':6,'data':{'x':x,'y':y}}))
 def test_固定黒の保存(self):
  for row in (64,65,73,77):
   p=predict(self.h,self.rows[row-1]['frame'][-1],self.rows[row]['action_input'],配置文法,True);self.assertEqual(p['予測盤面'][:-1],self.rows[row]['frame'][-1][:-1])
 def test_正常応答全相(self):
  r=self.response();self.assertEqual(r['状態'],'終端再観測一致');self.assertIsNotNone(r['次履歴']);self.assertEqual(len(r['全相']),len(self.rows[4]['frame']))
 def test_未知中間相で履歴を渡さない(self):
  b=copy.deepcopy(self.rows[4]);b['frame'].insert(1,[[5]*64 for _ in range(64)]);r=self.response(b);self.assertEqual(r['状態'],'HOLD');self.assertIsNone(r['次履歴'])
 def test_未説明画素中間相(self):
  b=copy.deepcopy(self.rows[4]);f=copy.deepcopy(b['frame'][-1]);f[25][0]=9;b['frame'].insert(0,f);self.assertEqual(self.response(b)['状態'],'HOLD')
 def test_実作用不一致(self):
  self.assertEqual(self.response(action={'id':1,'data':{}})['状態'],'HOLD')
  b=copy.deepcopy(self.rows[4]);b['action_input']={'id':6,'data':{'x':3,'y':3}};self.assertEqual(self.response(b,action={'id':6,'data':{'x':4,'y':3}})['状態'],'HOLD')
 def test_応答作用不在(self):
  b=copy.deepcopy(self.rows[4]);b.pop('action_input');self.assertEqual(self.response(b,action={'id':2,'data':{}})['状態'],'HOLD')
 def test_前終端進捗reset(self):
  a=copy.deepcopy(self.rows[3]);a['state']='WIN';self.assertEqual(self.response(a=a)['状態'],'HOLD')
  for key,value in [('score',1),('full_reset',True),('state','WIN')]:
   b=copy.deepcopy(self.rows[4]);b[key]=value;r=self.response(b);self.assertEqual(r['状態'],'HOLD');self.assertIsNone(r['次履歴'])
 def test_counter境界(self):
  for value in (None,True,-1,1.0):
   b=copy.deepcopy(self.rows[4]);b['score']=value;self.assertEqual(self.response(b)['状態'],'HOLD')
  b=copy.deepcopy(self.rows[4]);b.pop('score');self.assertEqual(self.response(b)['状態'],'HOLD')
 def test_履歴別問題拒否(self):
  self.assertEqual(self.response(history={'参照':[],'対象矩形':[],'小器具を観測済み':True})['状態'],'HOLD')
 def test_現在HDSを再照会(self):self.assertEqual(self.response(h=HDS学習系統())['状態'],'HOLD')
 def test_人工反証全体gate(self):
  h=保存状態を読む();h.処理する(外部入力({X:True,Y:False},COPY));self.assertEqual(self.response(h=h)['状態'],'HOLD');r=配色候補を作る(self.frame,[1,6],h,経路も作る=False);self.assertTrue(all(c['状態']=='HOLD' for c in r['全作用候補']))
 def test_保存無出力破損例外(self):
  class 無保存:
   def 保存する(self,p):pass
  class 破損:
   def 保存する(self,p):Path(p).write_text('broken')
  class 例外:
   def 保存する(self,p):raise OSError('fault')
  for h in (無保存(),破損(),例外()):
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'結果.gz'
    with self.assertRaises(Exception):確認保存(h,p)
    self.assertFalse(p.exists())
 def test_保存可逆gzip(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'状態.gz';r=確認保存(HDS学習系統(),p);self.assertTrue(r['保存完了']);self.assertIsInstance(保存状態を読む(p),HDS学習系統)
 def test_未観測小器具はなしと同一視しない(self):
  for row in range(1,len(self.rows)):
   a=self.rows[row-1]
   if 'frame'not in a:continue
   try:scene=read(a['frame'][-1])
   except ValueError:continue
   if sum(abs(v) for v in scene['方向'])!=2:continue
   for action in (1,2,3,4):
    r=predict(self.h,a['frame'][-1],{'id':action,'data':{}},配置文法,None)
    if r['状態']=='HOLD' and any('有無を未観測'in v for v in r['保留']):return
  self.fail('未知の可視配置分岐をHOLDにする反例が見つからない')
 def test_現在器具の未観測形状は保留(self):
  f=copy.deepcopy(self.frame);s=read(f);x,y,X,Y=s['器具矩形']
  # 枠内部に1画素の別役割を入れ、外接矩形だけの一致では支持しない。
  target=next((a,b) for b in range(y,Y) for a in range(x,X) if f[b][a]==s['器具色'])
  f[target[1]][target[0]]=2
  r=predict(self.h,f,{'id':1,'data':{}},配置文法,False)
  self.assertEqual(r['状態'],'HOLD');self.assertTrue(any('12配置'in v for v in r['保留']))
 def test_応答全相の寸法色境界は照会前(self):
  class 拒否:
   def __init__(self):self.回数=0
   def 照会する(self,*args):self.回数+=1;raise AssertionError('境界前照会')
  for frame in (self.frame[:-1],[row[:-1]for row in self.frame],[[16]*64 for _ in range(64)]):
   b=copy.deepcopy(self.rows[4]);b['frame'].insert(1,frame)
   spy=拒否();r=self.response(b,h=spy);self.assertEqual(spy.回数,0);self.assertEqual(r['状態'],'HOLD');self.assertNotIn('AssertionError',str(r['保留']))
 def _全6未成立(self,h):
  result=検証する(h)
  self.assertEqual(result['集計']['経路数'],0)
  self.assertEqual(len(result['全問題']),6)
  for p in result['全問題']:
   self.assertFalse(p['モデル終端検査']['代表目標全一致'])
   self.assertFalse(p['モデル終端検査']['非空経路'])
   self.assertEqual(p['モデル終端検査']['状態'],'未成立/HOLD')
 def test_CLI空HDSは全6未成立(self):self._全6未成立(HDS学習系統())
 def test_CLI人工反証は全6未成立(self):
  h=保存状態を読む();h.処理する(外部入力({X:True,Y:False},COPY));self._全6未成立(h)
 def test_CLI解法例外は全6未成立(self):
  with patch('接続.配色内部.予測.solve',side_effect=RuntimeError('解法故障')):self._全6未成立(HDS学習系統())
 def test_1548順序教材を保持(self):
  records=資料を読む('関係教材.json.gz');self.assertEqual(len(records),1548);self.assertEqual(records[0]['境界'],'公開器具:現在方向と方向作用')
 def test_全14完成と95点2例保持(self):
  p=資料を読む('問題と完成.json.gz');self.assertEqual(len(p),14);self.assertEqual(sum(x['一致画素数']==95 for x in p),2)
if __name__=='__main__':unittest.main()
