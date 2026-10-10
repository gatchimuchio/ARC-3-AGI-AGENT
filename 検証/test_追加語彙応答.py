import pathlib,sys,unittest
from unittest.mock import patch
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC3境界 import 観測する
from 接続.追加語彙応答 import 追加語彙の全応答を照合する

def obs(n,frames=None,**kw):
    d={'game_id':'fixture','guid':'same','frame':frames or [[[0,0],[0,0]]],'state':'NOT_FINISHED','available_actions':[1,6],'levels_completed':0,'win_levels':1};d.update(kw)
    return 観測する(d,観測通番=n)
A={'作用番号':1,'引数':{}}
def model(h,f,a):
    pred={'前意味状態':0,'予測意味状態':1,'画素予測':None,'照会記録':[]}
    def read(frame):
        if frame[0][0]==3:raise ValueError('test unknown phase')
        return {'意味状態':frame[0][0],'旧構造一致':True}
    return pred,read
class 応答試験(unittest.TestCase):
    def run_case(self,b=None,a=A,actual=A):
        with patch('接続.追加語彙応答._鎖予測',model):
            return 追加語彙の全応答を照合する(object(),obs(0),b or obs(1,[[[1,0],[0,0]]]),a,'根付き順序鎖',記録作用=actual)
    def test_全相と意味だけの範囲(self):
        r=self.run_case(obs(1,[[[0,0],[0,0]],[[1,0],[0,0]]]))
        self.assertEqual(r['状態'],'全相の意味応答照合成立');self.assertEqual(len(r['全相照合']),2)
        self.assertFalse(r['全画素応答成立']);self.assertFalse(r['実行許可']);self.assertEqual(r['不可視状態差分']['状態'],'未観測')
    def test_未知中間を捨てない(self):
        for v in (2,3):
            r=self.run_case(obs(1,[[[v,0],[0,0]],[[1,0],[0,0]]]))
            self.assertEqual(r['状態'],'保留');self.assertEqual(len(r['全相照合']),2);self.assertIsNone(r['次履歴'])
    def test_最新一致が必要(self):
        r=self.run_case(obs(1,[[[1,0],[0,0]],[[0,0],[0,0]]]))
        self.assertEqual(r['状態'],'保留')
    def test_実作用厳密対応(self):
        for act in (None,{'作用番号':6,'引数':{'x':1,'y':1}}, {'作用番号':True,'引数':{}}):
            self.assertEqual(self.run_case(actual=act)['状態'],'保留')
    def test_履歴境界を継がない(self):
        for kwargs in ({'guid':'other'},{'levels_completed':1},{'full_reset':True},{'state':'GAME_OVER'}):
            r=self.run_case(obs(1,[[[1,0],[0,0]]],**kwargs));self.assertTrue(r['旧履歴破棄']);self.assertIsNone(r['次履歴'])
    def test_順序と可用性(self):
        self.assertEqual(self.run_case(obs(0,[[[1,0],[0,0]]]))['状態'],'保留')
        self.assertEqual(self.run_case(a={'作用番号':2,'引数':{}},actual={'作用番号':2,'引数':{}})['状態'],'保留')
    def test_無変化は不可視不変を意味しない(self):
        def no_op(h,f,a):
            p,read=model(h,f,a);p['予測意味状態']=0;return p,read
        with patch('接続.追加語彙応答._鎖予測',no_op):
            r=追加語彙の全応答を照合する(object(),obs(0),obs(1),A,'根付き順序鎖',記録作用=A)
        self.assertTrue(r['可視no-op']);self.assertFalse(r['因果確定'])
    def test_予測例外でも全相保存(self):
        with patch('接続.追加語彙応答._鎖予測',side_effect=RuntimeError('fixture')):
            r=追加語彙の全応答を照合する(object(),obs(0),obs(1),A,'根付き順序鎖',記録作用=A)
        self.assertEqual(r['状態'],'保留');self.assertEqual(len(r['全相照合']),1)

class 共通接続試験(unittest.TestCase):
    def test_観測一巡から実作用と候補一致を分離する(self):
        import tempfile
        from 接続.観測駆動一巡 import 記録観測の一巡を処理する
        def candidate(o,number):
            return {'状態':'条件付き候補','出所':{'観測通番':o.観測通番,'観測指紋':o.指紋},'規則不確実性':[], '保留理由群':[],
                '次作用候補群':[{'語彙':'根付き順序鎖','候補':{'作用番号':number,'引数':{},'実行許可':False}}],
                '語彙別結果':[{'語彙':'根付き順序鎖','結果':{'適用性':{'状態':'適用可能'},'作用適用性':{'状態':'適用可能'},'目標候補群':[]}}]}
        for number in (1,2):
            a,b=obs(0),obs(1,[[[1,0],[0,0]]])
            with tempfile.TemporaryDirectory() as d,patch('接続.観測駆動一巡.公開観測から候補を照会する',side_effect=[candidate(a,number),candidate(b,number)]),patch('接続.追加語彙応答._鎖予測',model):
                r=記録観測の一巡を処理する(object(),a,A,b,記憶先=d,出所={'試験':'合成接続境界'})['記録']
            g=r['応答照合']['意味応答照合']
            self.assertEqual(g['状態'],'全相の意味応答照合成立' if number==1 else '保留')
            self.assertEqual(r['候補との作用照合']['状態'],'完全一致' if number==1 else '候補と不一致')
            self.assertFalse(r['環境作用送信']);self.assertFalse(r['追加学習'])
            self.assertEqual(g['相記録']['選択作用番号'],1)
            self.assertNotIn('作用番号が不正',g['相記録']['保留理由群'])
    def test_実空HDSの形状予測は保留(self):
        import json
        from hds学習系統 import HDS学習系統
        data=json.loads((根/'検証/資料/形状配置照合資料.json').read_text())['状態描画モデルの公開前後'][0]
        a=obs(0,[data['前盤面']],available_actions=data['前作用可能番号']);b=obs(1,[data['後盤面']])
        raw=data['作用_外部契約'];act={'作用番号':raw['id'],'引数':{k:v for k,v in raw['data'].items() if k!='game_id'}}
        r=追加語彙の全応答を照合する(HDS学習系統(),a,b,act,'形状目標対応',記録作用=act)
        self.assertEqual(r['状態'],'保留');self.assertIsNone(r['次履歴']);self.assertFalse(r['実行許可'])

class 語彙名接続試験(unittest.TestCase):
    def test_採用済み共通形状名で応答へ到達する(self):
        from 接続.応答相照合 import 公開応答相を照合する
        a,b=obs(0),obs(1,[[[1,0],[0,0]]])
        source={'出所':{'観測通番':a.観測通番,'観測指紋':a.指紋},'規則不確実性':[],
                '語彙別結果':[{'語彙':'形状目標対応','結果':{'適用性':{'状態':'適用可能'},'作用適用性':{'状態':'適用可能'}}}]}
        with patch('接続.追加語彙応答._形状予測',model):
            r=公開応答相を照合する(object(),a,b,1,source,予測作用=A,記録作用=A)
        self.assertEqual(r['意味応答照合']['状態'],'全相の意味応答照合成立')
        self.assertEqual(r['意味応答照合']['語彙'],'形状目標対応')

class 外側作用境界試験(unittest.TestCase):
    def test_相記録と内側作用が違えば保留(self):
        from 接続.応答相照合 import 公開応答相を照合する
        a,b=obs(0,available_actions=[1,2]),obs(1,[[[1,0],[0,0]]],available_actions=[1,2])
        source={'出所':{'観測通番':a.観測通番,'観測指紋':a.指紋},'規則不確実性':[],
                '語彙別結果':[{'語彙':'形状目標対応','結果':{'適用性':{'状態':'適用可能'},'作用適用性':{'状態':'適用可能'}}}]}
        with patch('接続.追加語彙応答._形状予測',model):
            r=公開応答相を照合する(object(),a,b,1,source,予測作用={'作用番号':2,'引数':{}},記録作用={'作用番号':2,'引数':{}})
        self.assertTrue(r['保留理由群']);self.assertEqual(len(r['相記録']['応答全盤面']),1)
        self.assertNotIn('意味応答照合',r)

class 寸法境界試験(unittest.TestCase):
    def test_応答寸法欠落を旧構造一致にしない(self):
        with patch('接続.追加語彙応答._形状予測',model):
            r=追加語彙の全応答を照合する(object(),obs(0),obs(1,[[[1,0]]]),A,'形状目標対応',記録作用=A)
        self.assertEqual(r['状態'],'保留');self.assertIsNone(r['次履歴'])
        self.assertNotIn('旧構造一致',r['全相照合'][0]);self.assertIn('寸法',r['全相照合'][0]['解析未確認']['理由'])



class 照会記録試験(unittest.TestCase):
    def test_予測保留に入力応答追跡を全て保持する(self):
        import json
        from hds学習系統 import HDS学習系統
        data=json.loads((根/'検証/資料/形状配置照合資料.json').read_text())['状態描画モデルの公開前後'][0]
        a=obs(0,[data['前盤面']],available_actions=data['前作用可能番号']);b=obs(1,[data['後盤面']])
        raw=data['作用_外部契約'];act={'作用番号':raw['id'],'引数':{k:v for k,v in raw['data'].items() if k!='game_id'}}
        r=追加語彙の全応答を照合する(HDS学習系統(),a,b,act,'形状目標対応',記録作用=act)
        self.assertEqual(r['状態'],'保留');self.assertTrue(r['当該HDS照会記録'])
        for q in r['当該HDS照会記録']:
            self.assertIn('対象系境界',q['入力']);self.assertIn('文脈',q['入力']);self.assertIn('追跡情報',q['応答']);self.assertEqual(q['応答']['内容']['予測群'],[])
        json.dumps(r,ensure_ascii=False,allow_nan=False)
    def test_転送一回と例外入力を保持する(self):
        from 接続.追加語彙応答 import _照会受信点
        from hds学習系統 import 外部入力
        from unittest.mock import Mock
        inner=Mock();inner.照会する.side_effect=RuntimeError('query failure');r=_照会受信点(inner);input=外部入力({'可視':'fixture'},'試験境界',文脈={'出所':'fixture'})
        with self.assertRaises(RuntimeError):r.照会する(input)
        inner.照会する.assert_called_once_with(input);self.assertEqual(r.記録[0]['入力']['文脈'],{'出所':'fixture'});self.assertEqual(r.記録[0]['例外']['型'],'RuntimeError')

if __name__=='__main__':unittest.main()
