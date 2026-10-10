import unittest,json,gzip
from 接続.鏡像教師CLI import 教材根,資料を読む,保存状態を読む,教材を教える
from 接続.鏡像接続 import 鏡像作用を照合,鏡像全応答を照合
from 接続.鏡像内部.採否 import 画素から前観測
from 接続.鏡像内部 import 基礎 as e
from 接続.鏡像内部.再識別 import normalize
from hds学習系統 import HDS学習系統

class 鏡像教材多相(unittest.TestCase):
 def test_1051実経験と入力順一致(self):
  def 復号(v):
   if isinstance(v,list):return [復号(x)for x in v]
   if not isinstance(v,dict):return v
   if '__辞書__'in v:return {復号(k):復号(x)for k,x in v['__辞書__']}
   if '__組__'in v:return tuple(復号(x)for x in v['__組__'])
   return {k:復号(x)for k,x in v.items()}
  state=復号(json.loads(gzip.decompress((教材根/'保存HDS.json.gz').read_bytes())))
  experience=state['台帳']['観測台帳'];teachers=資料を読む('関係教材.json')['教師群']
  self.assertEqual(len(experience),1051);self.assertEqual(len(teachers),1051)
  for x,t in zip(experience,teachers):
   self.assertEqual(x['値']['原入力'],t['入力']);self.assertEqual(x['値']['対象系境界'],t['境界'])
 def test_外部HDSへの実入力(self):
  h=HDS学習系統();t={'教師群':[{'順序':i+1,'境界':'模擬保存検証','入力':{'観測':bool(i%2),'結果':bool(i%2)}}for i in range(6)]}
  actual=[];same,logs=教材を教える(t,h,逐次記録=actual.append);self.assertIs(same,h);self.assertEqual(len(logs),6);self.assertEqual(actual,logs)
  self.assertEqual(e.ask(h,{'観測':True},'模擬保存検証','結果')['値'],True)
 def test_公開全17作用54相を保持(self):
  h=保存状態を読む();outputs=[]
  for source,pack in 資料を読む('全公開原票.json.gz').items():
   rows=pack['原票'];s=e.scene(rows[0]['frame'][-1]);shapes=[normalize(o['点'])for o in s['対象']]
   for n in range(1,len(rows)):
    a,b=rows[n-1],rows[n]
    if not a.get('frame')or not b.get('frame'):continue
    if len(b['frame'])>1:
     obs,_,_=画素から前観測(a['frame'][-1]);pre=鏡像作用を照合(obs,shapes,b['action_input'],h)
     r=鏡像全応答を照合(pre,b,h,既観測形状=shapes,前得点=a['score'],前状態=a['state']);outputs.append((source,n,r))
     self.assertEqual(len(r['全応答相']),len(b['frame']));self.assertFalse(r['実行許可'])
    if b['score']>a['score']or b['action_input']['id']==0:
     s=e.scene(b['frame'][-1]);shapes=[normalize(o['点'])for o in s['対象']]
  self.assertEqual(len(outputs),17);self.assertEqual(sum(len(r['全応答相'])for _,_,r in outputs),54)
  r=next(r for source,n,r in outputs if source=='開発資料'and n==75)
  self.assertEqual([x['状態']for x in r['全応答相']],['観測一致','観測一致','HOLD','観測一致','HOLD','観測一致','HOLD','観測一致'])
  self.assertEqual(r['状態'],'HOLD');self.assertIsNone(r['次観測履歴'])
if __name__=='__main__':unittest.main()
