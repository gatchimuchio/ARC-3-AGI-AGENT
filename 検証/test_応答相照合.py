import unittest,pathlib,sys
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from unittest.mock import patch
from 接続.ARC3境界 import 観測する
from 接続.応答相照合 import 公開応答相を照合する
from 接続.応答相照合 import 進行証拠をまとめる
class 進行試験(unittest.TestCase):
 def base(self):return {'応答全盤面':[0]*118,'完了数増分':1,'保留理由群':[]}
 def evidence(self):return [{'相':i,'旧構造一致':True,'目標判定':'条件付き目標一致'} for i in range(17)]
 def test_時刻非一意は進行支持を取り消さない(self):
  r=進行証拠をまとめる(self.base(),self.evidence());self.assertEqual(r['進行判定'],'公開完了増分と旧目標充足の支持あり');self.assertEqual(len(r['旧目標充足の全証拠']),17);self.assertFalse(r['作用因果確定']);self.assertFalse(r['実行許可'])
 def test_別実行境界は支持しない(self):
  b=self.base();b['保留理由群']=['異なる実行'];r=進行証拠をまとめる(b,self.evidence());self.assertEqual(r['進行判定'],'追加照合が必要')
 def test_目標だけ又は増分だけでは双方支持としない(self):
  b=self.base();b['完了数増分']=0
  for bb,ee in [(b,self.evidence()),(self.base(),[])]:self.assertEqual(進行証拠をまとめる(bb,ee)['進行判定'],'追加照合が必要')
 def test_重複範囲外対応を除いて保留(self):
  e=self.evidence();e.extend([e[0],{'相':118,'旧構造一致':True,'目標判定':'条件付き目標一致'}]);r=進行証拠をまとめる(self.base(),e);self.assertEqual(len(r['境界保留']),2);self.assertEqual(len(r['旧目標充足の全証拠']),17)

class 相接続試験(unittest.TestCase):
 def obs(self,frames,n,level=0,guid='A'):
  return 観測する({'frame':frames,'state':'NOT_FINISHED','game_id':'fixture','guid':guid,'levels_completed':level,'win_levels':2,'available_actions':[6]},観測通番=n)
 def old(self,a):return {'出所':{'観測通番':a.観測通番,'観測指紋':a.指紋},'規則不確実性':[],'語彙別結果':[{'語彙':'列展開','結果':{'適用性':{'状態':'適用可能'}}}]}
 def test_全相目標と全画素残差を別記録(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]],[[1]],[[2]]],1,1)
  with patch('接続.応答相照合._構造',return_value=({'固定構造':1},{})),patch('接続.応答相照合.照会',return_value=(True,{})),patch('接続.応答相照合.一致する',return_value=(True,{})):
   r=公開応答相を照合する(object(),a,b,6,self.old(a),予測盤面=[[1]])
  self.assertEqual(len(r['進行証拠']['旧目標充足の全証拠']),3);self.assertEqual([x['全画素一致'] for x in r['相別予測差分照合']],[True,True,False]);self.assertFalse(r['実行許可'])
 def test_目標だけ成立する別語彙で旧応答支持を失わない(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]],[[1]]],1,1);old=self.old(a)
  old['語彙別結果'].append({'語彙':'形状目標対応','結果':{'適用性':{'状態':'適用可能'},'作用適用性':{'状態':'構造上不適用'},'局所保留群':['目標のみの追加解釈']}})
  with patch('接続.応答相照合._構造',return_value=({},{})),patch('接続.応答相照合.照会',return_value=(True,{})),patch('接続.応答相照合.一致する',return_value=(True,{})):
   r=公開応答相を照合する(object(),a,b,6,old)
  self.assertEqual(r['進行証拠']['進行判定'],'公開完了増分と旧目標充足の支持あり');self.assertEqual(len(r['進行証拠']['旧目標充足の全証拠']),2)
  self.assertEqual(r['語彙適用境界'][1]['目標適用性']['状態'],'適用可能');self.assertEqual(old['語彙別結果'][1]['結果']['局所保留群'],['目標のみの追加解釈'])
 def test_別語彙作用未知と不正境界と全体隔離を無視しない(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]]],1,1)
  for scope,fault in [({'状態':'未確認'},False),({'状態':'誤った値'},False),(None,False),({'状態':'構造上不適用'},True)]:
   old=self.old(a);old['語彙別結果'].append({'語彙':'形状目標対応','結果':{'適用性':{'状態':'適用可能'},'作用適用性':scope}})
   if fault:old['規則不確実性']=['実HDS隔離']
   r=公開応答相を照合する(object(),a,b,6,old);self.assertIsNone(r['進行証拠']);self.assertTrue(r['保留理由群']);self.assertEqual(len(r['相記録']['応答全盤面']),1)
 def test_旧照会の観測対応を確認する(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]]],1,1);old=self.old(a);old['出所']['観測通番']=999
  r=公開応答相を照合する(object(),a,b,6,old,予測盤面=[[1]]);self.assertTrue(r['保留理由群']);self.assertFalse(r['相別予測差分照合']);self.assertIsNone(r['進行証拠'])
 def test_隔離と実行境界は進行根拠を結合しない(self):
  a=self.obs([[[0]]],0)
  for guid,fault in [('B',False),('A',True)]:
   b=self.obs([[[1]]],1,1,guid);old=self.old(a)
   if fault:old['規則不確実性']=['隔離']
   r=公開応答相を照合する(object(),a,b,6,old);self.assertTrue(r['保留理由群']);self.assertIsNone(r['進行証拠']);self.assertEqual(len(r['相記録']['応答全盤面']),1)
 def test_許容集合目標は同一HDSの再照会支持が必要(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]]],1,1);old=self.old(a);old['語彙別結果'][0]['語彙']='複合配色'
  cell={'位置':[0,0],'幅':1,'本体画素':[[0,0]],'標識画素':[],'許容色集合':[1]}
  for supported in (False,True):
   model={'保留理由群':[] if supported else ['追加教師未支持'],'目標候補群':[cell] if supported else []}
   with patch('接続.応答相照合._構造',return_value=({},{})),patch('接続.応答相照合.本体対象群を読む',return_value={(0,0):cell}),patch('接続.応答相照合.許容集合を含む図式攻略を照会する',return_value=model) as q:
    h=object();r=公開応答相を照合する(h,a,b,6,old);self.assertIs(q.call_args.args[2],h)
   self.assertEqual(r['進行証拠']['進行判定']=='公開完了増分と旧目標充足の支持あり',supported)
 def test_作用対象の装飾変化を目標充足に隠さない(self):
  a=self.obs([[[0]]],0);b=self.obs([[[1]]],1,1);old=self.old(a);old['語彙別結果'][0]['語彙']='複合配色';cell={'位置':[0,0],'幅':1,'本体画素':[[0,0]],'標識画素':[],'許容色集合':[1]}
  with patch('接続.応答相照合._構造',return_value=({},{})),patch('接続.応答相照合.本体対象群を読む',side_effect=[{(0,0):dict(cell,標識画素=[[0,0,6]])},{(0,0):cell}]),patch('接続.応答相照合.許容集合を含む図式攻略を照会する',return_value={'保留理由群':[],'目標候補群':[cell]}):
   r=公開応答相を照合する(object(),a,b,6,old)
  self.assertEqual(r['進行証拠']['進行判定'],'追加照合が必要');self.assertEqual(r['相別目標照合'][0]['対象目標照合'][0]['状態'],'対象対応未確認')
if __name__=='__main__':unittest.main()
