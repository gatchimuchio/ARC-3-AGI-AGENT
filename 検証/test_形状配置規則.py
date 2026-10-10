"""公開fixtureだけによる構造適用API回帰。ゲーム環境/evaluator/旧実験のimportなし。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.形状配置規則 import 目標対応全候補を読む,公開教師を教える,規則を照会する,学習状態を保存する,局所前提を読む,投射前提を読む,目標境界,局所境界,局所前提を符号化する
from 接続.形状配置探索 import 形状配置を構成する,全体最短経路を読む
from 接続.形状配置知覚 import 初期対象を読む,形状場面を読む,全整合分解を読む,盤面を検査する
from 接続.形状配置検証 import 公開前後でモデルを検証する
from 道具.形状配置教師検証 import 整理する,意味状態,計数する

class 形状配置検証(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.教師=json.loads((根/'検証/資料/形状配置公開教師.json').read_text())
        cls.資料=json.loads((根/'検証/資料/形状配置照合資料.json').read_text())
        cls.比較=json.loads((根/'検証/資料/形状配置比較教師.json').read_text())
        cls.系=HDS学習系統();cls.学習=list(公開教師を教える(cls.系,cls.教師['教師']))
        cls.問題=cls.資料['例群'][0]['問題盤面'];cls.構成=形状配置を構成する(cls.問題,cls.系)

    def test_01_全教師順序と種類(self):
        self.assertEqual(len(self.学習),363)
        self.assertEqual([x['種類'] for x in self.教師['教師']],['局所作用']*145+['目標対応']*20+['選択']*175+['投射']*23)
        self.assertEqual([x['教師通番'] for x in self.学習],list(range(363)))

    def test_02_問題のみ全グラフ計数(self):
        for k,v in 計数する(self.構成).items():self.assertEqual(v,self.資料['期待値'][k],k)

    def test_03_全8132状態と48792辺が旧証拠と一致(self):
        g=self.構成
        projection={'状態':[[n['状態識別子'],n['対象位置'],n['選択対象'],n['最短作用数'],n['全最短前駆']] for n in g['全状態']],
                    '辺':[[n['状態識別子'],[[e['作用'],e['状態'],e['次状態'],e.get('全同値座標'),e['根拠'],e.get('前状態関係')] for e in n['四方向と対象内全座標']]] for n in g['全辺']],
                    '終点':g['全完成状態識別子']}
        digest=hashlib.sha256(json.dumps(整理する(projection),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,self.資料['期待値']['全状態全辺正規形sha256'])

    def test_04_全候補座標分割(self):
        for 群 in self.構成['全辺']:
            辺=群['四方向と対象内全座標'];self.assertEqual({e['作用'] for e in 辺 if e['作用']!=6},{1,2,3,4})
            点=[tuple(p) for e in 辺 if e['作用']==6 for p in e['全同値座標']]
            self.assertEqual(len(点),18);self.assertEqual(len(set(点)),18);self.assertIn('除く全点は保留',群['対象外全座標'])

    def test_05_全支持辺が根拠と後状態を持つ(self):
        for 群 in self.構成['全辺']:
            for 辺 in 群['四方向と対象内全座標']:
                if 辺['状態']=='支持':self.assertTrue(辺['根拠']);self.assertIn(辺['次状態'],range(8132))
                else:self.assertIsNone(辺['次状態'])

    def test_06_全最短親DAGの全辺が支持(self):
        状態=self.構成['全状態'];辺群=self.構成['全辺']
        for 子 in 状態:
            for 親 in 子['全最短前駆']:
                self.assertEqual(状態[親['前状態']]['最短作用数']+1,子['最短作用数'])
                self.assertTrue(any(e['次状態']==子['状態識別子'] and e['作用']==親['作用'] and e['状態']=='支持' for e in 辺群[親['前状態']]['四方向と対象内全座標']))

    def test_07_八最短経路と四終点を保持(self):
        経路=全体最短経路を読む(self.構成)
        self.assertEqual([x['最短作用数'] for x in 経路['全終点最短距離']],[11,12,20,21])
        self.assertEqual(len(経路['全体最短経路群']),8)
        self.assertTrue(all(len(x)==11 for x in 経路['全体最短経路群']))

    def test_08_全状態で全観測分解を保持(self):
        self.assertEqual(len(self.構成['全観測分解']),8132)
        for 例,状態 in zip(self.構成['全観測分解'],self.構成['全状態']):
            self.assertEqual(例['状態識別子'],状態['状態識別子']);self.assertEqual(len(例['全可視分解']),1)
            self.assertEqual(sorted(o['位置'] for o in 例['全可視分解'][0]),sorted(状態['対象位置']))
            self.assertEqual(sum(o['選択'] for o in 例['全可視分解'][0]),1)

    def test_09_同一363状態の全37型付き照会(self):
        self.assertEqual(len(self.資料['独立監査の全型付き照会']),37)
        for 例 in self.資料['独立監査の全型付き照会']:
            結果=規則を照会する(self.系,例['入力'],例['境界'],例['結果経路'])
            self.assertEqual(結果['値'],例['出力']['値']);self.assertEqual(結果['状態'],例['出力']['状態'])

    def test_10_公開19前後がモデルと一致(self):
        結果=公開前後でモデルを検証する(self.系,self.問題,self.資料['状態描画モデルの公開前後'])
        self.assertEqual(結果['状態'],'照合成立');self.assertEqual(len(結果['全前後照合']),19)
        self.assertEqual(結果['露出確認画素数'],18);self.assertFalse(結果['背景不一致'])

    def test_11_公開原票境界欠損は保留(self):
        例=copy.deepcopy(self.資料['状態描画モデルの公開前後'][:1]);例[0]['同じ実行']=False
        self.assertEqual(公開前後でモデルを検証する(self.系,self.問題,例)['状態'],'保留')

    def test_12_空状態で全体保留(self):
        例=計数する(形状配置を構成する(self.問題,HDS学習系統()))
        self.assertEqual((例['状態数'],例['支持辺数'],例['保留辺数'],例['完成数']),(1,0,6,0))

    def test_13_反証は全領域と全体を保留(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'状態.json';self.系.保存する(p);h=HDS学習系統.読み込む(p)
        元=next(x for x in self.教師['教師'] if x['種類']=='投射')
        self.assertEqual(元['内容']['接触対象変位'],'15,0')
        list(公開教師を教える(h,[{**元,'内容':{**元['内容'],'接触対象変位':'0,0'}}]))
        for 例 in self.資料['独立監査の全型付き照会']:
            結果=規則を照会する(h,例['入力'],例['境界'],例['結果経路']);self.assertEqual(結果['状態'],'断定保留');self.assertIsNone(結果['値'])
        例=計数する(形状配置を構成する(self.問題,h));self.assertEqual((例['状態数'],例['支持辺数'],例['保留辺数'],例['完成数']),(1,0,6,0))

    def test_14_保存例外は保存保留(self):
        with patch.object(self.系,'保存する',side_effect=OSError('保存媒体失敗')):
            結果=学習状態を保存する(self.系,'未保存.json')
        self.assertEqual(結果['状態'],'保存保留');self.assertEqual(結果['例外種別'],'OSError');self.assertFalse(結果['実行許可'])

    def test_15_照会で記憶意味状態は変化しない(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'前.json',Path(d)/'後.json';self.系.保存する(a)
            規則を照会する(self.系,{'形状一致':True},目標境界,'成功占有形と対応');self.系.保存する(b)
            self.assertNotEqual(a.read_bytes(),b.read_bytes());self.assertEqual(意味状態(json.loads(a.read_text())),意味状態(json.loads(b.read_text())))

    def test_16_入力盤面検査(self):
        for bad in ([],[[1]*63]*64,[[True]*64]*64,[[16]*64]*64):
            with self.assertRaises(ValueError):盤面を検査する(bad)
        盤面を検査する(self.問題)

    def test_17_非支持構造は保留(self):
        盤面=copy.deepcopy(self.問題);盤面[0][0]=12
        self.assertEqual(形状配置を構成する(盤面,self.系)['状態'],'保留')

    def test_18_自由関係は前状態のみで再現(self):
        前=copy.deepcopy(self.問題);対象=初期対象を読む(前)['対象'][0]
        self.assertEqual(局所前提を読む(前,対象,1),{'移動先自由':True,'搬送候補相対配置':'[]'})
        横,縦=next(iter(対象['点']));前[縦-3][横]=2
        self.assertFalse(局所前提を読む(前,対象,1)['移動先自由'])

    def test_19_第24投射教師を正本から除外し全分解保存(self):
        保留=self.教師['観測保留'];self.assertEqual(len(保留['曖昧原観測']),1)
        self.assertEqual(len(保留['全可視分解と前提照会']),2)
        self.assertFalse(any(x['由来'].get('前行')==130 and x['種類']=='投射' for x in self.教師['教師']))

    def test_20_全七問題二出所の原問題と完成盤面保持(self):
        self.assertEqual(len(self.資料['例群']),14)
        for 例 in self.資料['例群']:
            盤面を検査する(例['問題盤面']);盤面を検査する(例['完成盤面_評価専用'])
            self.assertTrue(形状場面を読む(例['問題盤面'])['目標'])

    def test_21_四終点は原答えに事後一致(self):
        正解=sorted(o['位置'] for o in 初期対象を読む(self.資料['例群'][0]['完成盤面_評価専用'])['対象'])
        for 終点 in self.構成['全完成状態']:self.assertEqual(sorted(終点['対象位置']),正解)

    def test_22_入力順比較と実反例を保持(self):
        self.assertEqual(len(self.比較['比較群']),6);self.assertEqual([len(x['教師']) for x in self.比較['比較群']],[145]*4+[24]*2)
        self.assertEqual(len(self.比較['実反例16']),16)

    def test_23_実行と新規環境成功を許可しない(self):
        self.assertFalse(self.構成['実行許可']);self.assertFalse(self.構成['新規環境成功'])

    def test_24_旧実験やゲーム識別子に依存しない(self):
        for p in (根/'接続').glob('形状配置*.py'):
            s=p.read_text();self.assertNotIn('/workspace/',s);self.assertNotIn('ka59',s);self.assertNotIn('import experiment',s)

    def test_25_全104目標候補を同じ学習系で照会(self):
        群=[目標対応全候補を読む(例['問題盤面'],self.系) for 例 in self.資料['例群']]
        self.assertEqual(sum(len(例['全候補']) for 例 in 群),104)
        for 場面 in 群:
            for 候補 in 場面['全候補']:
                self.assertEqual(候補['照会']['値'],候補['対象']['形']==候補['目標']['形'])
                if '未観測枠' in 候補['目標'] and 候補['照会']['値']:self.assertEqual(候補['状態'],'条件付き支持')

    def test_26_内部schemaのキーは日本語(self):
        import re
        許可={'id','data','x','y'}
        def 確認(値):
            if isinstance(値,dict):
                for 鍵,要素 in 値.items():
                    self.assertTrue(鍵 in 許可 or re.search('[ぁ-んァ-ン一-龥]',鍵),鍵);確認(要素)
            elif isinstance(値,(list,tuple)):
                for 要素 in 値:確認(要素)
        for 値 in (self.教師,self.資料,self.比較,self.構成):確認(値)

    def test_27_全割当候補を剪定しない(self):
        群=[目標対応全候補を読む(例['問題盤面'],self.系) for 例 in self.資料['例群']]
        self.assertEqual(sum(len(例['全割当候補']) for 例 in 群),94)
        self.assertTrue(any(候補['状態']=='不対応支持' for 例 in 群 for 候補 in 例['全割当候補']))

    def test_28_全960局所回帰と保留を保持(self):
        self.assertEqual(len(self.資料['全局所観測照合']),960)
        for 例 in self.資料['全局所観測照合']:
            結果=規則を照会する(self.系,局所前提を符号化する(例['修正前状態特徴'],'直積記号'),局所境界,'入力方向へ一単位進む')
            self.assertEqual(結果['値'],例['修正後照会']['値']);self.assertEqual(結果['状態'],例['修正後照会']['状態'])
            self.assertNotEqual(例['現結果'],'不一致')

    def test_29_空盤面の空割当を支持しない(self):
        結果=目標対応全候補を読む([[1]*64 for _ in range(64)],HDS学習系統())
        self.assertEqual(結果['全候補'],[]);self.assertEqual(結果['全割当候補'],[])
        self.assertFalse(結果['実行許可'])

    def _保存故障を検査する(self,故障名,比較あり):
        import 道具.形状配置教師検証 as 検証器
        # 正常経路で検査済みの363状態と全グラフを再利用。故障gateだけを独立に試す。
        with tempfile.TemporaryDirectory() as d:
            基底=Path(d)/'基底.json';self.系.保存する(基底)
            元保存=検証器.学習状態を保存する
            class 複製機械:
                def __new__(cls):return HDS学習系統.読み込む(基底)
                読み込む=HDS学習系統.読み込む
            def 故障保存(系,先):
                if 先.name==故障名:
                    with patch.object(系,'保存する',side_effect=OSError('保存経路の故障注入')):
                        return 元保存(系,先)
                return 元保存(系,先)
            空構成=形状配置を構成する(self.問題,HDS学習系統())
            出力=Path(d)/'故障検査'
            with patch.object(検証器,'HDS学習系統',複製機械),patch.object(検証器,'公開教師を教える',side_effect=lambda h,t:iter([{'検査':'既検証状態再利用'} for _ in t])),patch.object(検証器,'形状配置を構成する',side_effect=[self.構成,空構成,空構成]),patch.object(検証器,'学習状態を保存する',side_effect=故障保存):
                with self.assertRaisesRegex(RuntimeError,'保存保留'):
                    検証器.再現する(出力,根/'検証/資料/形状配置公開教師.json',根/'検証/資料/形状配置照合資料.json',根/'検証/資料/形状配置比較教師.json' if 比較あり else None)
            現在=json.loads((出力/'現在状態.json').read_text())
            self.assertEqual(現在['状態'],'保留');self.assertNotIn('保存失敗',現在)
            self.assertFalse((出力/故障名).exists());self.assertTrue((出力/'逐次学習.jsonl').exists())
            判定=json.loads((出力/('比較0.json' if 比較あり else '反証保存判定.json')).read_text())
            self.assertEqual((判定['保存'] if 比較あり else 判定)['状態'],'保存保留')

    def test_30_反証状態保存失敗で完了にしない(self):
        self._保存故障を検査する('反証学習状態.json',False)

    def test_31_比較状態保存失敗で完了にしない(self):
        self._保存故障を検査する('比較学習状態0.json',True)

if __name__=='__main__':unittest.main()
