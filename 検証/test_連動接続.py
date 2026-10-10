import sys,unittest,copy,tempfile,json,resource
from pathlib import Path
from 接続.ARC3境界 import 観測する
from 接続.連動規則 import 観測から候補を構成する,順序付きHUDを進める,作用待受を登録する
from 接続.連動観測記録 import 記録観測の連動付記を処理する
from hds学習系統 import HDS学習系統

def response(black=False,phases=1,action=1):
 f=[[5]*64 for _ in range(64)]
 for y in range(10,14):
  for x in list(range(10,14))+list(range(30,34)):f[y][x]=10
 if black:f[0]=[0]*64;f[-1]=[0]*64
 return {'frame':[f for _ in range(phases)],'guid':'g','game_id':'fixture','state':'NOT_FINISHED','levels_completed':0,'win_levels':6,'available_actions':[1,2,3,4,5,6],'full_reset':False,'action_input':{'id':action,'data':{}}}
def initial(d):return 順序付きHUDを進める(None,d,{'接続識別子':'s','観測識別子':'o0','観測通番':0,'直前観測識別子':None,'作用識別子':None,'種別':'初期観測'})
def after(r,d):
 w=作用待受を登録する(r['次履歴'],作用識別子='a1',直前観測識別子='o0',作用=d['action_input'])
 return 順序付きHUDを進める(w['次履歴'],d,{'接続識別子':'s','観測識別子':'o1','観測通番':1,'直前観測識別子':'o0','作用識別子':'a1','種別':'作用応答'})
class 接続試験(unittest.TestCase):
 def test_公開6作用と4096クリックを全保持(self):
  d=response();r=initial(d);q=観測から候補を構成する(HDS学習系統(),観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴'])
  self.assertEqual([c['id']for c in q['全作用群']],[1,2,3,4,5,6]);self.assertEqual(len(q['作用候補群']),4101)
  self.assertEqual({(a['引数']['x'],a['引数']['y'])for a in q['作用候補群']if a['作用番号']==6},{(x,y)for x in range(64)for y in range(64)})
  self.assertFalse(q['実行許可']);self.assertEqual(q['次作用候補群'],[]);self.assertEqual(q['作用適用性']['状態'],'未確認');self.assertTrue(q['前提照会記録'])
 def test_利用可能7とRESETも捨てずHOLD(self):
  d=response();d['available_actions']=[0,7,6];r=initial(d);q=観測から候補を構成する(HDS学習系統(),観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertEqual([x['id']for x in q['全作用群']],[0,7,6]);self.assertEqual(len(q['作用候補群']),4098);self.assertTrue(all(a['採否']=='HOLD'for a in q['作用候補群']))
 def test_空availabilityは補完しない(self):
  d=response();d['available_actions']=[];r=initial(d);q=観測から候補を構成する(HDS学習系統(),観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertEqual(q['全作用群'],[]);self.assertEqual(q['作用候補群'],[])
 def test_観測指紋不一致は全HOLD(self):
  d=response();r=initial(d);d['guid']='other';q=観測から候補を構成する(HDS学習系統(),観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertTrue(all(c['状態']=='HOLD'for c in q['全作用群']));self.assertEqual(q['順序根拠']['状態'],'HOLD')
 def test_停止状態は全HOLDと公式WINを別記録(self):
  for status in('WIN','GAME_OVER','NOT_PLAYED'):
   d=response();d['state']=status;r=initial(d);q=観測から候補を構成する(HDS学習系統(),観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertTrue(all(c['状態']=='HOLD'for c in q['全作用群']));self.assertEqual(q['公式完了確認'],status=='WIN')
 def test_全照会例外を保存し後続候補も処理(self):
  class Broken:
   def __init__(self):self.n=0
   def 照会する(self,x):self.n+=1;raise RuntimeError('人工失敗'+str(self.n))
  h=Broken();d=response();r=initial(d);q=観測から候補を構成する(h,観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertGreater(h.n,6);self.assertEqual(h.n,len(q['前提照会記録']));self.assertTrue(all(x['例外']for x in q['前提照会記録']));self.assertEqual(len(q['作用候補群']),4101);self.assertTrue(all(x['採否']=='HOLD'for x in q['作用候補群']))
 def test_全相を一巡付記で残しcommitを主張しない(self):
  d=response();d['available_actions']=[1];r=initial(d);e=copy.deepcopy(d);e['frame']=[e['frame'][0]for _ in range(3)];s=after(r,e)
  with tempfile.TemporaryDirectory()as td:
   q=記録観測の連動付記を処理する(HDS学習系統(),観測する(d,観測通番=0),{'作用番号':1,'引数':{}},観測する(e,観測通番=1),前受付=r,前履歴=r['次履歴'],現在受付=s,現在履歴=s['次履歴'],現在公開応答=e,記憶先=td,出所={'人工試験':True})
   self.assertEqual(len(q['記録']['全相知覚']),3);self.assertEqual(len(q['記録']['可視差分']['応答全盤面']),3);self.assertFalse(q['正本履歴commit']);self.assertTrue(Path(q['記憶参照']['結果']).exists())
 def test_4096座標は候補索引で支持経験を増やさない(self):
  class Count:
   def __init__(self):self.h=HDS学習系統();self.calls=[]
   def 照会する(self,x):self.calls.append(x);return self.h.照会する(x)
  counts=[]
  for av in([1,2,3,4,5],[1,2,3,4,5,6]):
   h=Count();d=response();d['available_actions']=av;r=initial(d);q=観測から候補を構成する(h,観測する(d,観測通番=0),受付=r,現在履歴=r['次履歴']);counts.append(len(h.calls))
   self.assertEqual(len(h.h.エンジン.台帳._台帳.get('観測台帳',[])),0)
   if 6 in av:
    click=[a for a in q['作用候補群']if a['作用番号']==6];self.assertEqual(len(click),4096);self.assertEqual({a['元作用群参照']for a in click},{5})
  self.assertEqual(counts[1]-counts[0],1)
 def test_公開Actionとの不一致を一巡失敗として保存(self):
  d=response();d['available_actions']=[1,2];r=initial(d);e=copy.deepcopy(d);s=after(r,e)
  with tempfile.TemporaryDirectory()as td:
   q=記録観測の連動付記を処理する(HDS学習系統(),観測する(d,観測通番=0),{'作用番号':2,'引数':{}},観測する(e,観測通番=1),前受付=r,前履歴=r['次履歴'],現在受付=s,現在履歴=s['次履歴'],現在公開応答=e,記憶先=td,出所={'人工試験':True})
   self.assertEqual(q['状態'],'HOLD');self.assertFalse(q['正規Memory混入']);v=json.loads(Path(q['記憶参照']['結果']).read_text());self.assertEqual(v['処理状態'],'HOLD隔離');self.assertIn('action_input',v['失敗']['理由'])

if __name__=='__main__':unittest.main()
