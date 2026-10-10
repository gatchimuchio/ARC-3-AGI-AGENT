"""採用stateを外部注入。state未指定はskipを明示し、fixtureをruntime lookupへ渡さない。"""
import os,json,gzip,gc,unittest,hashlib
from pathlib import Path
from hds学習系統 import HDS学習系統
from 検証.連動教示.公開教師を教示 import _標準再読込
from 検証.連動教示.同形式保存 import 同形式JSON,遅延値
from 接続.連動内部.学習照会 import 照会,HUD失敗を照会
from 接続.連動規則 import 観測から候補を構成する,順序付きHUDを進める
from 接続.ARC3境界 import 観測する
from test_連動接続 import response,initial

def semantic(h):
 e=h.エンジン;ids=e.識別子.状態を書き出す()
 for k in('照会','学習判定'):ids.pop(k,None)
 value={'形式版':3,'最小支持数':e.最小支持数,'最大条件数':e.最大条件数,'識別子状態':ids,'台帳':e.台帳._台帳,'状態履歴':e.状態._履歴,'原理履歴':e._原理履歴};sha=hashlib.sha256()
 for s in 同形式JSON(ensure_ascii=False,sort_keys=True,separators=(',',':')).iterencode(遅延値(value)):sha.update(s.encode())
 return sha.hexdigest()
class 実状態試験(unittest.TestCase):
 def load(self,env):
  path=os.environ.get(env)
  if not path:self.skipTest(env+' 未指定。実state試験は未実施')
  return _標準再読込(Path(path))
 def verify(self,h,supported):
  fixture=Path(os.environ.get('ARC_PAIRED_TEACHER_FIXTURE',str(Path(__file__).with_name('連動教示')/'公開教師268.json.gz')))
  d=json.load(gzip.open(fixture,'rt'));before=semantic(h);seen=set();n=0
  for t in d['教師']:
   x=t['入力']['内容'];key=(t['入力']['対象系境界'],x['前提直積'])
   if key in seen:continue
   seen.add(key);facts=json.loads(x['前提直積'])
   if'相対変位'in x:
    q=照会(h,facts);self.assertEqual(q['値'],x['相対変位']if supported else None)
   else:
    q=HUD失敗を照会(h,facts['作用番号'],facts['上下端全黒の連続外部観測数']);self.assertEqual(q['失敗終端'],x['次応答はGAME_OVER']if supported else None)
   n+=1
  self.assertEqual(n,165)
  frame=response();r=initial(frame);q=観測から候補を構成する(h,観測する(frame,観測通番=0),受付=r,現在履歴=r['次履歴'])
  self.assertEqual(len(q['作用候補群']),4101);self.assertFalse(q['実行許可'])
  if not supported:self.assertTrue(all(c['状態']=='HOLD'for c in q['全作用群']))
  for full in(False,True):
   black=response(True,action=0);black['full_reset']=full;r=initial(black);q=観測から候補を構成する(h,観測する(black,観測通番=0),受付=r,現在履歴=r['次履歴']);self.assertIsNone(r['次履歴']['HUD履歴']['連続黒数']);self.assertTrue(all(c['状態']=='HOLD'for c in q['全作用群']))
  self.assertEqual(semantic(h),before)
 def test_実268(self):
  h=self.load('ARC_PAIRED_TRAINED_HDS');self.verify(h,True);del h;gc.collect()
 def test_人工反証269(self):
  h=self.load('ARC_PAIRED_CONTRADICTION_HDS');self.verify(h,False);del h;gc.collect()
 def test_空HDS(self):self.verify(HDS学習系統(),False)
if __name__=='__main__':unittest.main()
