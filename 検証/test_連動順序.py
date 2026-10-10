import sys,unittest,copy,json,resource
from pathlib import Path
from 接続.連動内部.順序境界 import 初期RESET待受を登録する,作用待受を登録する,順序付きHUDを進める,順序境界付き全候補
from hds学習系統 import HDS学習系統

class 順序試験(unittest.TestCase):
 def response(self,black=False,phases=1,action=1,**kw):
  frame=[[5]*64 for _ in range(64)]
  for y in range(10,14):
   for x in list(range(10,14))+list(range(30,34)):frame[y][x]=10
  if black:frame[0]=[0]*64;frame[-1]=[0]*64
  d={'frame':[frame for _ in range(phases)],'guid':'g','game_id':'公開型','state':'NOT_FINISHED','levels_completed':0,'win_levels':6,'available_actions':[1,2,3,4,5,6],'full_reset':False,'action_input':{'id':action,'data':{'game_id':'公開型'}}}
  d.update(kw);return d
 def event(self,seq,oid,prev=None,aid=None,kind='作用応答',stream='s'):
  return {'接続識別子':stream,'観測通番':seq,'観測識別子':oid,'直前観測識別子':prev,'作用識別子':aid,'種別':kind}
 def start(self,black=False):
  d=self.response(black);r=順序付きHUDを進める(None,d,self.event(0,'start',kind='初期観測'));self.assertEqual(r['状態'],'受理');return r
 def step(self,r,seq,oid,black=True,action=1,phases=1,**kw):
  state=r['次履歴'];aid='a'+str(seq);d=self.response(black,phases,action,**kw);w=作用待受を登録する(state,作用識別子=aid,直前観測識別子=state['最新']['観測識別子'],作用=d['action_input']);self.assertEqual(w['状態'],'待受登録')
  e=self.event(seq,oid,state['最新']['観測識別子'],aid,'RESET応答'if action==0 else'作用応答');n=順序付きHUDを進める(w['次履歴'],d,e);self.assertEqual(n['状態'],'受理');return n,d,e
 def assertHoldUnchanged(self,state,d,e):
  before=copy.deepcopy(state);r=順序付きHUDを進める(state,d,e);self.assertEqual(r['状態'],'HOLD');self.assertEqual(state,before);self.assertIs(r['次履歴'],state);return r
 def test_A_B_A遅延再送は加算しない(self):
  a,da,ea=self.step(self.start(),1,'A');b,db,eb=self.step(a,2,'B');self.assertEqual(b['次履歴']['HUD履歴']['連続黒数'],2);self.assertHoldUnchanged(b['次履歴'],da,ea)
 def test_A_A隣接再送は加算しない(self):
  a,d,e=self.step(self.start(),1,'A');self.assertHoldUnchanged(a['次履歴'],d,e)
 def test_同画面同作用でも新真正応答は加算(self):
  a,da,_=self.step(self.start(),1,'A');b,db,_=self.step(a,2,'B');self.assertEqual(da,db);self.assertEqual(b['次履歴']['HUD履歴']['連続黒数'],2)
 def test_8相を一回だけ加算(self):
  a,_,_=self.step(self.start(),1,'A',phases=8);self.assertEqual(a['全相数'],8);self.assertEqual(a['次履歴']['HUD履歴']['連続黒数'],1)
 def test_同観測識別子異内容はHOLD(self):
  a,d,e=self.step(self.start(),1,'A');d['frame'][0][4][4]=12;self.assertHoldUnchanged(a['次履歴'],d,e)
 def test_同参照に新通番を付け直してもHOLD(self):
  a,d,e=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');e={**e,'観測通番':3,'直前観測識別子':'B','作用識別子':'a3'};self.assertHoldUnchanged(b['次履歴'],d,e)
 def test_新観測参照でも古い通番はHOLD(self):
  a,d,e=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');self.assertHoldUnchanged(b['次履歴'],d,{**e,'観測識別子':'renamed'})
 def test_欠番はHOLDで後の正しい応答を受理できる(self):
  s=self.start()['次履歴'];d=self.response(True);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];e=self.event(2,'A','start','a1');self.assertHoldUnchanged(w,d,e);r=順序付きHUDを進める(w,d,{**e,'観測通番':1});self.assertEqual(r['状態'],'受理')
 def test_通番欠損負数boolはHOLD(self):
  s=self.start()['次履歴'];d=self.response(True)
  for bad in(None,-1,True):self.assertHoldUnchanged(s,d,self.event(bad,'A','start','a1'))
 def test_作用識別子の再利用はHOLD(self):
  a,d,e=self.step(self.start(),1,'A');r=作用待受を登録する(a['次履歴'],作用識別子='a1',直前観測識別子='A',作用=d['action_input']);self.assertEqual(r['状態'],'HOLD')
 def test_待受なしの新観測はHOLD(self):
  s=self.start()['次履歴'];self.assertHoldUnchanged(s,self.response(True),self.event(1,'A','start','a1'))
 def test_二重待受はHOLD(self):
  s=self.start()['次履歴'];d=self.response(True);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];r=作用待受を登録する(w,作用識別子='a2',直前観測識別子='start',作用=d['action_input']);self.assertEqual(r['状態'],'HOLD')
 def test_直前参照不一致はHOLD(self):
  s=self.start()['次履歴'];d=self.response(True);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,d,self.event(1,'A','wrong','a1'))
 def test_作用IDまたは方向が違えばHOLD(self):
  s=self.start()['次履歴'];d=self.response(True);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,d,self.event(1,'A','start','wrong'));d2=self.response(True,action=2);self.assertHoldUnchanged(w,d2,self.event(1,'A','start','a1'))
 def test_クリック座標不一致はHOLD(self):
  s=self.start()['次履歴'];d=self.response(True,action=6);d['action_input']['data'].update(x=10,y=10);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];d['action_input']['data']['x']=11;self.assertHoldUnchanged(w,d,self.event(1,'A','start','a1'))
 def test_現在非対応の作用登録はHOLD(self):
  s=self.start()['次履歴'];r=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用={'id':7,'data':{}});self.assertEqual(r['状態'],'HOLD')
 def test_別GUID通常応答はHOLD(self):
  s=self.start()['次履歴'];d=self.response(True,guid='other');w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,d,self.event(1,'A','start','a1'))
 def test_別接続と別ゲームはHOLD(self):
  s=self.start()['次履歴'];d=self.response(True);self.assertHoldUnchanged(s,d,self.event(1,'A','start','a1',stream='other'));d['game_id']='other';self.assertHoldUnchanged(s,d,self.event(1,'A','start','a1'))
 def test_RESETは独立履歴で既読台帳を消さない(self):
  a,da,ea=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');r,d,e=self.step(b,3,'reset',black=False,action=0,guid='new');self.assertEqual(r['境界'],'独立RESET境界');self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],0);self.assertIn('A',r['次履歴']['受理観測台帳']);self.assertHoldUnchanged(r['次履歴'],da,ea)
 def test_RESET種別不一致はHOLD(self):
  s=self.start()['次履歴'];d=self.response(False,action=0);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,d,self.event(1,'R','start','a1'))
 def test_未登録full_resetはHOLD(self):
  s=self.start()['次履歴'];d=self.response(False,full_reset=True);w=作用待受を登録する(s,作用識別子='a1',直前観測識別子='start',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,d,self.event(1,'A','start','a1'))
 def test_レベル境界は個体履歴初期化(self):
  a,_,_=self.step(self.start(),1,'A',black=False,levels_completed=1);self.assertEqual(a['境界'],'独立レベル境界');self.assertTrue(a['個体履歴再初期化が必要'])
 def test_旧受理票を現在として再利用しない(self):
  a,da,ea=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');h=HDS学習系統();r=順序境界付き全候補(da['frame'][-1],[1,2,3,4,5,6],h,a,現在履歴=b['次履歴']);self.assertEqual(r['順序境界']['状態'],'HOLD');self.assertTrue(all(c['状態']=='HOLD'for c in r['全作用候補']))
 def test_拒否受付を渡しても候補を復活させない(self):
  a,da,ea=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');bad=self.assertHoldUnchanged(b['次履歴'],da,ea);r=順序境界付き全候補(da['frame'][-1],[1,2,3,4,5,6],HDS学習系統(),bad,現在履歴=b['次履歴']);self.assertTrue(all(c['状態']=='HOLD'for c in r['全作用候補']))
 def test_初見黒画面は履歴数を推測しない(self):
  r=self.start(True);self.assertIsNone(r['次履歴']['HUD履歴']['連続黒数'])
 def test_必須公開項目欠損はHOLD(self):
  d=self.response();del d['action_input'];r=順序付きHUDを進める(None,d,self.event(0,'start',kind='初期観測'));self.assertEqual(r['状態'],'HOLD')
 def test_真正無画面変化の5も別応答(self):
  a,_,_=self.step(self.start(),1,'A',action=5);b,_,_=self.step(a,2,'B',action=5);self.assertEqual(b['次履歴']['HUD履歴']['連続黒数'],2)
 def test_真正同画面同座標の6も別応答(self):
  r=self.start();d=self.response(True,action=6);d['action_input']['data'].update(x=10,y=10)
  for seq,oid in ((1,'A'),(2,'B')):
   s=r['次履歴'];w=作用待受を登録する(s,作用識別子='a'+str(seq),直前観測識別子=s['最新']['観測識別子'],作用=d['action_input']);self.assertEqual(w['状態'],'待受登録')
   r=順序付きHUDを進める(w['次履歴'],d,self.event(seq,oid,s['最新']['観測識別子'],'a'+str(seq)));self.assertEqual(r['状態'],'受理')
  self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],2)
 def test_待受中の遅延Aで待受を消さずCを受理(self):
  a,da,ea=self.step(self.start(),1,'A');b,_,_=self.step(a,2,'B');d=self.response(True);w=作用待受を登録する(b['次履歴'],作用識別子='a3',直前観測識別子='B',作用=d['action_input'])['次履歴'];self.assertHoldUnchanged(w,da,ea)
  r=順序付きHUDを進める(w,d,self.event(3,'C','B','a3'));self.assertEqual(r['状態'],'受理');self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],3)
 def test_待受中の旧受理票で候補を復活させない(self):
  a,d,e=self.step(self.start(),1,'A');w=作用待受を登録する(a['次履歴'],作用識別子='a2',直前観測識別子='A',作用=d['action_input'])['次履歴']
  r=順序境界付き全候補(d['frame'][-1],[1,2,3,4,5,6],HDS学習系統(),a,現在履歴=w);self.assertEqual(r['順序境界']['状態'],'HOLD');self.assertTrue(all(c['状態']=='HOLD'for c in r['全作用候補']))
 def test_既存履歴の初期再宣言はHOLD(self):
  a,d,e=self.step(self.start(),1,'A');self.assertHoldUnchanged(a['次履歴'],d,self.event(2,'new',kind='初期観測'))

 def boot(self,**kw):
  args={'接続識別子':'s','初期化識別子':'init','作用識別子':'reset-a','期待観測通番':0,'ゲーム識別子':'公開型','作用':{'id':0,'data':{'game_id':'公開型'}},'出所':{'発行段階':'応答前','記録参照':'collector-test-pending-0'}};args.update(kw);return 初期RESET待受を登録する(**args)
 def bevent(self,**kw):
  e=self.event(0,'start',aid='reset-a',kind='初期RESET応答');e['初期化識別子']='init';e.update(kw);return e
 def test_初見黒RESET表示だけでは履歴数を補完しない(self):
  for a in(0,'RESET',1,5):
   for full in(False,True):
    r=順序付きHUDを進める(None,self.response(True,action=a,full_reset=full),self.event(0,'start',kind='初期観測'));self.assertEqual(r['状態'],'受理');self.assertIsNone(r['次履歴']['HUD履歴']['連続黒数']);self.assertEqual(r['次履歴']['HUD履歴']['状態'],'HOLD')
 def test_初見黒RESET後も黒なら不明を維持(self):
  r=順序付きHUDを進める(None,self.response(True,action=0),self.event(0,'start',kind='初期観測'));a,_,_=self.step(r,1,'A');self.assertIsNone(a['次履歴']['HUD履歴']['連続黒数']);b,_,_=self.step(a,2,'B',black=False);self.assertEqual(b['次履歴']['HUD履歴']['連続黒数'],0)
 def test_初見非黒はmetadataによらず画素からゼロ(self):
  for a in(0,3,5):
   r=順序付きHUDを進める(None,self.response(False,action=a),self.event(0,'start',kind='初期観測'));self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],0)
 def test_初見黒RESETの全候補はHOLD(self):
  d=self.response(True,action=0);r=順序付きHUDを進める(None,d,self.event(0,'start',kind='初期観測'));q=順序境界付き全候補(d['frame'][-1],[1,2,3,4,5,6],HDS学習系統(),r,現在履歴=r['次履歴']);self.assertTrue(all(c['状態']=='HOLD'for c in q['全作用候補']))
 def test_bootstrap自分の事前RESET応答なら黒一回(self):
  w=self.boot();self.assertEqual(w['状態'],'初期RESET待受登録');before=copy.deepcopy(w['次履歴']);r=順序付きHUDを進める(w['次履歴'],self.response(True,action=0),self.bevent());self.assertEqual(r['状態'],'受理');self.assertEqual(r['境界'],'独立初期RESET応答境界');self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],1);self.assertEqual(w['次履歴'],before);self.assertEqual(r['次履歴']['使用済み作用'],{'reset-a':'start'})
 def test_bootstrap待受なしのRESET応答はHOLD(self):
  self.assertHoldUnchanged(None,self.response(True,action=0),self.bevent())
 def test_bootstrap初期化参照と作用参照と通番を検査(self):
  w=self.boot()['次履歴'];d=self.response(True,action=0)
  for k,v in(('初期化識別子',None),('初期化識別子','wrong'),('作用識別子','wrong'),('観測通番',1),('直前観測識別子','fake'),('接続識別子','other'),('種別','初期観測')):
   self.assertHoldUnchanged(w,d,self.bevent(**{k:v}))
 def test_bootstrap公開Action不一致はHOLD後に正しく受理(self):
  w=self.boot()['次履歴'];self.assertHoldUnchanged(w,self.response(True,action=1),self.bevent());r=順序付きHUDを進める(w,self.response(True,action=0),self.bevent());self.assertEqual(r['状態'],'受理')
 def test_bootstrapゲーム不一致はHOLD(self):
  d=self.response(True,action=0,game_id='other');d['action_input']['data']['game_id']='other';self.assertHoldUnchanged(self.boot()['次履歴'],d,self.bevent())
 def test_bootstrap由来なし事後由来はHOLD(self):
  for bad in(None,{}, {'発行段階':'応答後','記録参照':'x'},{'発行段階':'応答前','記録参照':''}):self.assertEqual(self.boot(出所=bad)['状態'],'HOLD')
 def test_bootstrap通常Actionは登録不可(self):
  self.assertEqual(self.boot(作用={'id':1,'data':{}})['状態'],'HOLD')
 def test_bootstrap再送と後日の遅延再送はHOLD(self):
  d=self.response(True,action=0);e=self.bevent();r=順序付きHUDを進める(self.boot()['次履歴'],d,e);self.assertHoldUnchanged(r['次履歴'],d,e);a,_,_=self.step(r,1,'A');self.assertHoldUnchanged(a['次履歴'],d,e)
 def test_bootstrap消費済み作用IDは再利用不可(self):
  r=順序付きHUDを進める(self.boot()['次履歴'],self.response(True,action=0),self.bevent());w=作用待受を登録する(r['次履歴'],作用識別子='reset-a',直前観測識別子='start',作用={'id':0,'data':{}});self.assertEqual(w['状態'],'HOLD')
 def test_bootstrap複数相でも末尾一回(self):
  r=順序付きHUDを進める(self.boot()['次履歴'],self.response(True,phases=8,action=0),self.bevent());self.assertEqual(r['全相数'],8);self.assertEqual(r['次履歴']['HUD履歴']['連続黒数'],1)
 def test_受動初期観測に勝手なinit参照を混ぜない(self):
  self.assertHoldUnchanged(None,self.response(True,action=0),{**self.event(0,'start',kind='初期観測'),'初期化識別子':'fake'})

if __name__=='__main__':unittest.main()
