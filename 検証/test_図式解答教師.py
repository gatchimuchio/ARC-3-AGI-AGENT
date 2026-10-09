import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from 接続.図式解答教師 import パネルを検出する,見本を教える,解答を構成する,境界,結果名,方針を教える,作用方針を構成する


def frame(pattern,center=8,other=9,invert=False):
    # 知覚文法の回帰用fixture。公式能力評価の教師には使わない。
    f=[[5]*32 for _ in range(32)]
    for dy in range(3):
        for dx in range(3):
            color=center if bool(pattern[dy][dx]) != invert else other
            for y in range(4+dy*8,10+dy*8):
                for x in range(4+dx*8,10+dx*8):f[y][x]=color
    for dy in range(3):
        for dx in range(3):
            c=center if dx==dy==1 else 0 if pattern[dy][dx] else 2
            for y in range(12+dy*2,14+dy*2):
                for x in range(12+dx*2,14+dx*2):f[y][x]=c
    for y in range(4):
        for x in range(30,32):f[y][x]=other if y<2 else center
    return f

P=[[False,True,False],[True,True,False],[False,True,True]]


class 図式解答教師試験(unittest.TestCase):
    def test_見本から学ぶ極性で新色の解答を構成する(self):
        refs=パネルを検出する(frame(P))[0];self.assertEqual(len(refs),1)
        h=HDS学習系統();見本を教える(h,refs)
        target=frame(P,center=12)
        for p in パネルを検出する(target)[0]:
            for c in p['周辺セル']:
                x,y=c['位置']
                for yy in range(y,y+c['幅']):
                    for xx in range(x,x+c['幅']):target[yy][xx]=9
        original=copy.deepcopy(target)
        empty=解答を構成する(HDS学習系統(),target);self.assertEqual(empty['クリック対象'],[]);self.assertEqual(len(empty['HOLDセル']),8)
        got=解答を構成する(h,target);self.assertEqual(len(got['解答セル']),8);self.assertEqual(len(got['クリック対象']),4);self.assertFalse(got['HOLDセル']);self.assertEqual(target,original)
        inverse=HDS学習系統();見本を教える(inverse,パネルを検出する(frame(P,invert=True))[0])
        other=解答を構成する(inverse,target)
        self.assertNotEqual([c['解答色'] for c in got['解答セル']],[c['解答色'] for c in other['解答セル']])

    def test_反証隔離を回避せずHOLDする(self):
        h=HDS学習系統();見本を教える(h,パネルを検出する(frame(P))[0])
        h.処理する(外部入力({'指示記号順位':0,結果名:False},境界))
        result=解答を構成する(h,frame(P))
        self.assertEqual(result['状態'],'HOLD');self.assertEqual(result['クリック対象'],[])

    def test_攻略条件充足から保持変更を実際に学ぶ(self):
        completed=frame(P);problem=copy.deepcopy(completed)
        for p in パネルを検出する(problem)[0]:
            for c in p['周辺セル']:
                x,y=c['位置']
                for yy in range(y,y+c['幅']):
                    for xx in range(x,x+c['幅']):problem[yy][xx]=9
        h=HDS学習系統();見本を教える(h,パネルを検出する(completed)[0])
        self.assertEqual(作用方針を構成する(h,problem)['状態'],'HOLD')
        records,unresolved=方針を教える(h,problem,completed)
        self.assertEqual(len(records),8);self.assertFalse(unresolved)
        result=作用方針を構成する(h,problem)
        self.assertEqual(result['保持数'],4);self.assertEqual(len(result['変更対象']),4);self.assertFalse(result['未確定'])

    def test_未被覆と部分重複と色列不足を採用しない(self):
        f=frame(P);panels,_=パネルを検出する(f);h=HDS学習系統();見本を教える(h,panels)
        with patch('接続.図式解答教師.パネルを検出する',return_value=(panels,[{'理由':'未被覆'}])):
            r=解答を構成する(h,f);self.assertEqual(r['状態'],'HOLD');self.assertFalse(r['クリック対象'])
        overlapping=copy.deepcopy(panels[0]);overlapping['周辺セル'][0]['位置'][0]+=1
        with patch('接続.図式解答教師.パネルを検出する',return_value=(panels+[overlapping],[])):
            r=解答を構成する(h,f);self.assertIn('異なるセル領域が部分重複。合成未対応',r['全体保留理由']);self.assertFalse(r['クリック対象'])
        for y in range(4):
            for x in range(30,32):f[y][x]=5
        r=解答を構成する(h,f);self.assertEqual(r['状態'],'HOLD');self.assertFalse(r['クリック対象'])

    def test_不完全パネルと不正frameを保持する(self):
        f=frame(P);f[4][4]=3
        accepted,rejected=パネルを検出する(f)
        self.assertFalse(accepted);self.assertTrue(rejected)
        with self.assertRaises(ValueError):パネルを検出する([[1],[1,2]])


if __name__=='__main__':unittest.main()
