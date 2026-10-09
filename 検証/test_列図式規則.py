"""自己完結した列図式接続の契約回帰。公開データは環境変数で明示供給する。"""
import unittest,json,os,sys,copy,tempfile,inspect,builtins
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from 接続.列図式規則 import (一致する,候補を構成する,観測から候補を構成する,候補台帳を構成する,
                           役割境界,目標境界,作用境界)
from 接続.ARC3境界 import 観測する
from 道具.列図式教師検証 import 公開原票を読む,教師を取り込む,評価する,遷移作用を測る,完了数

class 固定語彙境界(unittest.TestCase):
    def scene(self,tokens,target):return {'目標列':target,'容器群':[{'色':8,'起点':True,'枠群':[{'記号':t} for t in tokens]}]}
    def test_有限余剰出力を前置列で誤採用しない(self):
        s=self.scene([{'色':1,'中空':False},{'色':2,'中空':False},{'色':3,'中空':False}],[1,2]);ok,r=一致する(s,{False:'出力',True:'参照'});self.assertFalse(ok);self.assertEqual(r['出力列'],[1,2,3]);self.assertEqual(r['比較範囲'],'全出力列')
    def test_生産的反復だけ目標長比較(self):
        s=self.scene([{'色':1,'中空':False},{'色':8,'中空':True}],[1,1]);ok,r=一致する(s,{False:'出力',True:'参照'});self.assertTrue(ok);self.assertEqual(r['展開構造'],'生産的反復')
    def test_非生産的循環HOLD(self):
        s=self.scene([{'色':8,'中空':True},{'色':1,'中空':False}],[1,1]);ok,r=一致する(s,{False:'出力',True:'参照'});self.assertFalse(ok);self.assertEqual(r['構造状態'],'HOLD')
    def test_公式盤面契約不正は未確認(self):
        for f in ([],[[16]],[[1],[2,3]],[[4]*65],[[1,2],[2,1]]):
            r=候補を構成する(HDS学習系統(),f,作用可能番号=[6]);self.assertEqual(r['適用性']['状態'],'未確認');self.assertTrue(r['保留理由群']);self.assertFalse(r['実行許可'])
    def test_必須構造のない盤面は当該文法に不適用(self):
        r=候補を構成する(HDS学習系統(),[[4]*64 for _ in range(64)],作用可能番号=[6]);self.assertEqual(r['適用性']['状態'],'構造上不適用');self.assertEqual(r['規則不確実性'],[]);self.assertEqual(r['目標候補群'],[])
    def test_正本候補キーは日本語(self):
        r=候補を構成する(HDS学習系統(),[],作用可能番号=[]);self.assertTrue(all(not k.isascii() for k in r));self.assertNotIn('runtime_permission',r);self.assertNotIn('goal_candidates',r)
    def test_runtime入口に解答録画環境IDを受け取らない(self):
        self.assertEqual(list(inspect.signature(候補を構成する).parameters),['系','盤面','作用可能番号','出所'])
        source=inspect.getsource(sys.modules['接続.列図式規則']);self.assertNotIn('sys.path',source);self.assertNotIn('experiment',source);self.assertNotIn('read_text(',source);self.assertNotIn('.step(',source)

@unittest.skipUnless(os.environ.get('ARC_PUBLIC_TEACHER') and os.environ.get('ARC_PUBLIC_SHA256'),'公開教師path/digestを明示して実行')
class 公開教師保持評価(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.digest=os.environ['ARC_PUBLIC_SHA256'];cls.rows=公開原票を読む(os.environ['ARC_PUBLIC_TEACHER'],cls.digest);cls.tmp=tempfile.TemporaryDirectory();cls.memory=Path(cls.tmp.name)/'model.json';h=HDS学習系統()
        cls.training=教師を取り込む(h,cls.rows,[12,43,59,256],[(1,59),(226,256)],[(1,59)],原票SHA256=cls.digest);h.保存する(cls.memory)
        cls.evaluations=評価する(h,cls.rows,[0,12,43,59,78,144,167,225],[12,43,59,78,144,167,225,256],原票SHA256=cls.digest)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def h(self):return HDS学習系統.読み込む(self.memory)
    def f(self,n=59):return self.rows[n]['frame'][-1]
    def run_candidate(self,h=None,n=59,available=(5,6),origin=None):return 候補を構成する(h or self.h(),self.f(n),作用可能番号=available,出所=origin)
    def test_全8候補集合と公開解答包含(self):
        self.assertEqual([len(x['結果']['目標候補群']) for x in self.evaluations],[1,1,1,1,1,1,5,4]);self.assertTrue(all(x['公開完成割当を候補集合に含む'] for x in self.evaluations));self.assertTrue(all(x['結果']['実行許可'] is False for x in self.evaluations))
    def test_複数整合解と規則不確実を区別(self):
        for x in self.evaluations[-2:]:r=x['結果'];self.assertTrue(r['複数整合解']);self.assertEqual(r['規則不確実性'],[]);self.assertEqual(r['解答選択状態'],'複数整合解');self.assertEqual(r['作用候補群'],[])
    def test_不完全失敗と未同定作用を保持(self):
        records=self.training['教師記録'];self.assertEqual(sum('教師'in r for r in records),78);self.assertEqual(sum(r.get('目標教師使用') is False for r in records),4);measured=[r['実測'] for r in records if r['種別']=='作用観測'];self.assertEqual(sum(r['状態']=='HOLD' for r in measured),12);self.assertEqual(sum(r['状態']=='可視変化なし' for r in measured),6)
    def test_未学習は規則保留(self):
        r=self.run_candidate(HDS学習系統());self.assertEqual(r['目標候補群'],[]);self.assertEqual(r['作用候補群'],[]);self.assertTrue(r['規則不確実性']);self.assertFalse(r['複数整合解'])
    def test_同一系の内容作用矛盾は全体HOLD(self):
        for boundary,facts in [(役割境界,{'記号は中空':True,'列展開役割':'出力'}),(目標境界,{'終端条件に応じた列が一致':True,'提出が受理された':False}),(作用境界,{'解答作業':'在庫記号を選択','必要行動ID':5})]:
            h=self.h();h.処理する(外部入力(facts,boundary));r=self.run_candidate(h);self.assertEqual(r['目標候補群'],[]);self.assertEqual(r['作用候補群'],[]);self.assertTrue(r['規則不確実性'])
    def test_利用不可作用は内容候補を保ったまま停止(self):
        r=self.run_candidate(available=[1,2,3,4,5]);self.assertEqual(len(r['目標候補群']),1);self.assertEqual(r['規則不確実性'],[]);self.assertEqual(r['作用候補群'],[]);self.assertTrue(any(x['段階']=='合法性' for x in r['保留理由群']))
    def test_出所IDに意味判断を依存しない(self):
        h=self.h();a=self.run_candidate(h,origin={'資料参照':'A'});b=self.run_candidate(h,origin={'資料参照':'B'});a.pop('出所');b.pop('出所');self.assertEqual(a,b)
    def test_既存観測のゲーム識別子を意味入力にしない(self):
        raw=copy.deepcopy(self.rows[59]);raw['levels_completed']=raw['score'];raw['win_levels']=raw['win_score'];obs=観測する(raw,観測通番=59)
        class 観測射影:
            最新盤面=obs.最新盤面;作用可能番号=obs.作用可能番号;状態=obs.状態;指紋=obs.指紋;観測通番=obs.観測通番
            @property
            def ゲーム識別子(self):raise AssertionError('ID参照禁止')
        self.assertEqual(len(観測から候補を構成する(self.h(),観測射影())['作用候補群']),1)
    def test_runtime読込排出なし(self):
        h=self.h();f=self.f()
        with patch.object(builtins,'open',side_effect=AssertionError('runtime read')),patch('接続.ARC3境界.作用を排出する',side_effect=AssertionError('emission')):
            r=候補を構成する(h,f,作用可能番号=[5,6]);self.assertEqual(len(r['作用候補群']),1)
    def test_台帳は日本語未実行で全候補を保持(self):
        r=self.run_candidate(n=167);ledger=候補台帳を構成する(r);self.assertEqual(len(ledger['目標候補群']),5);self.assertFalse(ledger['実行許可']);self.assertIsNone(ledger['実測差分']);self.assertTrue(all(not k.isascii() for k in ledger))
    def test_座標は移動した現盤面へ追従(self):
        a=self.run_candidate();f=[[4]+row[:-1] for row in self.f()];b=候補を構成する(self.h(),f,作用可能番号=[5,6]);self.assertEqual(a['作用候補群'][0]['引数'],{'x':11,'y':59});self.assertEqual(b['作用候補群'][0]['引数'],{'x':12,'y':59})
    def test_保持19遷移の効果分類と対象差を隠さない(self):
        h=self.h();same=alternate=noop=0
        for i in range(60,79):
            before,after=self.rows[i-1],self.rows[i];r=候補を構成する(h,before['frame'][-1],作用可能番号=before['available_actions']);p=r['作用候補群'][0]
            observed=遷移作用を測る(before['frame'][-1],after['frame'][-1],after['action_input'],完了数(after)>完了数(before))
            if observed['状態']=='可視変化なし':noop+=1;continue
            self.assertEqual(p['作業'],observed['作用']);self.assertEqual(p['作用番号'],observed['行動ID'])
            if observed['作用']=='完成列提出':agrees=True
            elif observed['作用']=='選択記号を空欄へ割当':agrees=p['対象']['位置']==observed['対象位置']
            else:agrees=(p['対象']['色'],p['対象']['中空'])==(observed['選択記号']['色'],observed['選択記号']['中空'])
            same+=agrees;alternate+=not agrees
        self.assertEqual((same,alternate,noop),(13,2,4))
    def test_反証を解消せずHDSを再初期化しない(self):
        h=self.h();h.処理する(外部入力({'解答作業':'在庫記号を選択','必要行動ID':5},作用境界));r1=self.run_candidate(h);r2=self.run_candidate(h);self.assertEqual(r1['作用候補群'],[]);self.assertEqual(r2['作用候補群'],[]);self.assertTrue(r2['規則不確実性'])
if __name__=='__main__':unittest.main(verbosity=2)
