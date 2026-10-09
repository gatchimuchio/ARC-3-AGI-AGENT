import copy
import unittest
from test_図式解答教師 import frame,P
from hds学習系統 import HDS学習系統
from 接続.図式解答教師 import パネルを検出する,見本を教える,方針を教える
from 接続.図式作用教師 import 作用教師を読む,作用を教える,次色を照会する,許容色までの作用候補,色列,攻略候補を構成する


class 図式作用教師試験(unittest.TestCase):
    def examples(self):
        a=frame(P);b=copy.deepcopy(a)
        for y in range(4,10):
            for x in range(4,10):b[y][x]=8
        action={'id':6,'data':{'x':7,'y':7}}
        forward,e=作用教師を読む(a,action,b);self.assertIsNone(e)
        backward,e=作用教師を読む(b,action,a);self.assertIsNone(e)
        return a,b,action,forward,backward

    def test_二色実測の関係を三色色列へ適用して目標条件を満たす(self):
        a,b,act,forward,backward=self.examples();h=HDS学習系統()
        self.assertEqual(次色を照会する(h,[9,8,12],9)['状態'],'HOLD')
        作用を教える(h,[forward,backward,forward])
        self.assertEqual(次色を照会する(h,[9,8,12],9)['次色'],8)
        self.assertEqual(次色を照会する(h,[9,8,12],8)['次色'],12)
        self.assertEqual(次色を照会する(h,[9,8,12],12)['次色'],9)
        r=許容色までの作用候補(h,[9,8,12],9,[8,12]);self.assertEqual(len(r['経路']),1);self.assertEqual(r['到達候補色'],8)
        r=許容色までの作用候補(h,[9,8,12],9,[12]);self.assertEqual(len(r['経路']),2)

    def test_不変反証も教師として残し隔離を維持する(self):
        a,b,act,fwd,back=self.examples();h=HDS学習系統();作用を教える(h,[fwd,back,fwd])
        unchanged,e=作用教師を読む(a,act,a);self.assertEqual(unchanged['結果'],'不変')
        records=作用を教える(h,[unchanged]);self.assertEqual(len(records),1)
        self.assertEqual(次色を照会する(h,[9,8],9)['状態'],'HOLD')

    def test_解答方針作用を統合し隔離時は採用しない(self):
        completed=frame(P);problem=copy.deepcopy(completed)
        for p in パネルを検出する(problem)[0]:
            for c in p['周辺セル']:
                x,y=c['位置']
                for yy in range(y,y+c['幅']):
                    for xx in range(x,x+c['幅']):problem[yy][xx]=9
        h=HDS学習系統();見本を教える(h,パネルを検出する(completed)[0]);方針を教える(h,problem,completed)
        a,b,act,fwd,back=self.examples();作用を教える(h,[fwd,back,fwd])
        result=攻略候補を構成する(h,problem)
        self.assertFalse(result['残保留']);self.assertEqual(len(result['対象セル']),8);self.assertEqual(len(result['作用候補']),4);self.assertFalse(result['実行許可'])
        unchanged,_=作用教師を読む(a,act,a);作用を教える(h,[unchanged])
        result=攻略候補を構成する(h,problem);self.assertEqual(result['状態'],'HOLD');self.assertFalse(result['作用候補'])

    def test_対象外作用と寸法変更を教師にしない(self):
        a,b,act,fwd,back=self.examples()
        self.assertIsNone(作用教師を読む(a,{'id':1,'data':{}},b)[0])
        self.assertIsNone(作用教師を読む(a,act,b[:-1])[0])


if __name__=='__main__':unittest.main()
