import sys,unittest,copy,tempfile,json
from pathlib import Path
from 接続.ARC3境界 import 観測する
from 接続.連動規則 import 順序付きHUDを進める,作用待受を登録する
from 接続.連動観測記録 import 記録観測の連動付記を処理する
from hds学習系統 import HDS学習系統

def data(action=1,guid='g'):
 f=[[5]*64 for _ in range(64)]
 for y in range(10,14):
  for x in list(range(10,14))+list(range(30,34)):f[y][x]=10
 return {'frame':[f],'guid':guid,'game_id':'fixture','state':'NOT_FINISHED','levels_completed':0,'win_levels':6,'available_actions':[1],'full_reset':False,'action_input':{'id':action,'data':{}}}
def initial(stream='s',seq=0):
 d=data();r=順序付きHUDを進める(None,d,{'接続識別子':stream,'観測識別子':'o'+str(seq),'観測通番':seq,'直前観測識別子':None,'作用識別子':None,'種別':'初期観測'});return d,r

def step(pair,d=None):
 before,r=pair;s=r['次履歴'];seq=s['最新']['観測通番']+1;d=d or data();aid='a'+str(seq)
 w=作用待受を登録する(s,作用識別子=aid,直前観測識別子=s['最新']['観測識別子'],作用=d['action_input']);assert w['状態']=='待受登録'
 r=順序付きHUDを進める(w['次履歴'],d,{'接続識別子':s['接続識別子'],'観測識別子':'o'+str(seq),'観測通番':seq,'直前観測識別子':s['最新']['観測識別子'],'作用識別子':aid,'種別':'RESET応答'if d['action_input']['id']==0 else'作用応答'});assert r['状態']=='受理';return d,r
class Count:
 def __init__(self):self.h=HDS学習系統();self.n=0
 def 照会する(self,x):self.n+=1;return self.h.照会する(x)
class 一巡前後(unittest.TestCase):
 def setUp(self):self.a=initial();self.b=step(self.a);self.c=step(self.b)
 def runpair(self,pre,post,change=None,hold=False):
  pd,pr=pre;d,r=post;h=Count();kwargs={'前受付':pr,'前履歴':pr['次履歴'],'現在受付':r,'現在履歴':r['次履歴'],'現在公開応答':d,'出所':{'人工試験':True}}
  if change:kwargs.update(change)
  with tempfile.TemporaryDirectory()as td:
   q=記録観測の連動付記を処理する(h,観測する(pd,観測通番=pr['次履歴']['最新']['観測通番']),{'作用番号':d['action_input']['id'],'引数':{}},観測する(d,観測通番=r['次履歴']['最新']['観測通番']),記憶先=td,**kwargs)
   if hold:
    self.assertEqual(q['状態'],'HOLD');self.assertEqual(q['記憶参照']['記憶種別'],'HOLD隔離証拠');self.assertEqual(h.n,0);self.assertFalse(q['正規Memory混入']);self.assertEqual(q['記録']['処理状態'],'HOLD隔離');self.assertNotIn('公開作用対応',q['記録'])
   else:self.assertEqual(q['記録']['処理状態'],'独立付記の照会完了');self.assertEqual(q['記録']['公開作用対応']['状態'],'一致');self.assertGreater(h.n,0)
   self.assertTrue(Path(q['記憶参照']['原票']).exists());self.assertTrue(Path(q['記憶参照']['結果']).exists());return q
 def test_正しい同一frameのB_Cは受理(self):self.runpair(self.b,self.c)
 def test_A_C非隣接は隔離(self):self.runpair(self.a,self.c,hold=True)
 def test_別connectionのB_Cは隔離(self):self.runpair(initial('foreign',seq=1),self.c,hold=True)
 def test_逆順は隔離(self):self.runpair(self.b,self.a,hold=True)
 def test_前受付未受理は隔離(self):self.runpair(self.b,self.c,{'前受付':{'状態':'HOLD'}},True)
 def test_現在受付破損は隔離(self):self.runpair(self.b,self.c,{'現在受付':{'状態':'受理','次履歴':{}}},True)
 def test_前正本指紋不一致は隔離(self):
  s=copy.deepcopy(self.b[1]['次履歴']);s['最新']['観測指紋']='wrong';self.runpair(self.b,self.c,{'前履歴':s},True)
 def test_現在正本待受中は隔離(self):
  s=copy.deepcopy(self.c[1]['次履歴']);s['待受作用']={'作用識別子':'pending'};self.runpair(self.b,self.c,{'現在履歴':s},True)
 def test_直前参照の改変は隔離(self):
  r=copy.deepcopy(self.c[1]);r['次履歴']['受理観測台帳']['o2']['直前観測識別子']='other';self.runpair(self.b,self.c,{'現在受付':r,'現在履歴':r['次履歴']},True)
 def test_正しいRESET境界は履歴を分離して保存(self):self.runpair(self.b,step(self.b,data(action=0,guid='new')))
 def test_RESET区間の改変は隔離(self):
  c=step(self.b,data(action=0,guid='new'));r=copy.deepcopy(c[1]);r['次履歴']['履歴区間']=0;self.runpair(self.b,c,{'現在受付':r,'現在履歴':r['次履歴']},True)
 def test_前観測frameの改変は隔離(self):
  pd=copy.deepcopy(self.b[0]);pd['frame'][0][2][2]=9;self.runpair((pd,self.b[1]),self.c,hold=True)
 def test_公開観測型破損も隔離(self):
  d,r=self.c;h=Count()
  with tempfile.TemporaryDirectory()as td:
   q=記録観測の連動付記を処理する(h,None,{'作用番号':1,'引数':{}},観測する(d,観測通番=2),前受付=self.b[1],前履歴=self.b[1]['次履歴'],現在受付=r,現在履歴=r['次履歴'],現在公開応答=d,記憶先=td,出所={'人工試験':True});self.assertEqual(q['状態'],'HOLD');self.assertEqual(h.n,0);self.assertFalse(q['正規Memory混入']);self.assertTrue(Path(q['記憶参照']['原票']).exists())

if __name__=='__main__':unittest.main()
