#!/usr/bin/env python3
"""公開教師から空の固定HDSへ逐次学習し、単体構造適用を再現する。外部作用なし。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.形状配置規則 import 目標対応全候補を読む,公開教師を教える,学習状態を保存する,規則を照会する,投射境界,局所境界,局所前提を符号化する
from 接続.形状配置探索 import 形状配置を構成する,全体最短経路を読む
from 接続.形状配置検証 import 公開前後でモデルを検証する
from 接続.形状配置知覚 import 初期対象を読む

def 整理する(値):
    if isinstance(値,dict):return {str(鍵):整理する(要素) for 鍵,要素 in 値.items()}
    if isinstance(値,(list,tuple)):return [整理する(要素) for 要素 in 値]
    if isinstance(値,(set,frozenset)):return [整理する(要素) for 要素 in sorted(値)]
    return 値

def 書く(先,値):
    先.write_text(json.dumps(整理する(値),ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')

def 意味状態(値):
    """永続化形式の識別子状態だけから照会・学習判定の独立採番を除く。"""
    複製=json.loads(json.dumps(値,ensure_ascii=False))
    for 鍵,内容 in 複製['__辞書__']:
        if 鍵=='識別子状態':
            内容['__辞書__']=[対 for 対 in 内容['__辞書__'] if 対[0] not in ('照会','学習判定')]
    return 複製

def 計数する(構成):
    全辺=[辺 for 群 in 構成.get('全辺',[]) for 辺 in 群['四方向と対象内全座標']]
    経路=全体最短経路を読む(構成)
    return {'状態数':len(構成.get('全状態',[])),'支持辺数':sum(辺['状態']=='支持' for 辺 in 全辺),
            '保留辺数':sum(辺['状態']=='保留' for 辺 in 全辺),'完成数':len(構成.get('全完成状態',[])),
            '全体最短作用数':経路['最短作用数'],'全体最短経路数':len(経路['全体最短経路群']),
            '完成識別子':構成.get('全完成状態識別子',[])}

def 再現する(出力,教師先,照合先,比較先=None):
    出力.mkdir(parents=True,exist_ok=False)
    資源=[];開始=time.perf_counter()
    def 計測(段階):
        資源.append({'段階':段階,'開始から秒':time.perf_counter()-開始,'最大常駐記憶量KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        書く(出力/'資源計測.json',資源)
    教師資料=json.loads(教師先.read_text());照合資料=json.loads(照合先.read_text())
    由来={'教師ファイル':教師先.name,'教師sha256':hashlib.sha256(教師先.read_bytes()).hexdigest(),
          '照合ファイル':照合先.name,'照合sha256':hashlib.sha256(照合先.read_bytes()).hexdigest(),
          '中核版':'v0.4.2','同じ一個の学習系':True,'実行許可':False,'新規環境成功':False,'盲検':False}
    書く(出力/'実行由来.json',由来)
    try:
        学習系=HDS学習系統();記録=[]
        with (出力/'逐次学習.jsonl').open('w',encoding='utf-8') as 流れ:
            for 項目 in 公開教師を教える(学習系,教師資料['教師']):
                記録.append(項目);流れ.write(json.dumps(整理する(項目),ensure_ascii=False)+'\n');流れ.flush()
        計測('空から363教師逐次学習')
        保存=学習状態を保存する(学習系,出力/'統合学習状態.json');書く(出力/'保存判定.json',保存)
        if 保存['状態']!='保存済み':raise RuntimeError('統合学習状態の保存保留')
        照会前=json.loads((出力/'統合学習状態.json').read_text())
        問題=照合資料['例群'][0]['問題盤面']
        モデル=公開前後でモデルを検証する(学習系,問題,照合資料['状態描画モデルの公開前後']);書く(出力/'公開前後モデル照合.json',モデル)
        if モデル['状態']!='照合成立':raise AssertionError('予測構造モデルの公開前後照合が未成立')
        照会記録=[]
        for 例 in 照合資料['独立監査の全型付き照会']:
            結果=規則を照会する(学習系,例['入力'],例['境界'],例['結果経路'])
            照会記録.append({'照会識別子':例['照会識別子'],'照会':結果,'値一致':結果['値']==例['出力']['値'],'状態一致':結果['状態']==例['出力']['状態']})
        書く(出力/'全型付き照会.json',照会記録)
        if not all(例['値一致'] and 例['状態一致'] for 例 in 照会記録):raise AssertionError('単一統合学習系の採否不一致')
        局所照合=[]
        for 例 in 照合資料['全局所観測照合']:
            結果=規則を照会する(学習系,局所前提を符号化する(例['修正前状態特徴'],'直積記号'),局所境界,'入力方向へ一単位進む')
            局所照合.append({'資料':例['資料'],'行':例['行'],'照会':結果,'実測':例['実測'],'一致':結果['値']==例['修正後照会']['値'] and 結果['状態']==例['修正後照会']['状態']})
        書く(出力/'全960局所照合.json',局所照合)
        if len(局所照合)!=960 or not all(例['一致'] for 例 in 局所照合):raise AssertionError('局所回帰不一致')
        全目標=[{'出所':例['出所'],**目標対応全候補を読む(例['問題盤面'],学習系)} for 例 in 照合資料['例群']]
        書く(出力/'全七問題目標対応.json',全目標)
        if sum(len(例['全候補']) for 例 in 全目標)!=104:raise AssertionError('全目標候補数不一致')
        構成=形状配置を構成する(問題,学習系)
        # 完成盤面を読む前に全候補・全分解・全辺・全最短親DAGを確定して保存する。
        書く(出力/'問題のみ全構成.json',構成);計測('全状態と全辺の構成保存')
        書く(出力/'全最短経路.json',全体最短経路を読む(構成))
        計数=計数する(構成);期待=照合資料['期待値']
        if any(値!=期待[鍵] for 鍵,値 in 計数.items()):raise AssertionError({'構成計数不一致':計数})
        完成盤面=照合資料['例群'][0]['完成盤面_評価専用']
        正解占有=sorted(対象['位置'] for 対象 in 初期対象を読む(完成盤面)['対象'])
        事後=[{'状態識別子':終点['状態識別子'],'占有一致':sorted(終点['対象位置'])==正解占有} for 終点 in 構成['全完成状態']]
        書く(出力/'原答え事後照合.json',{'グラフ先保存':True,'全終点':事後,'盲検':False})
        保存後=学習状態を保存する(学習系,出力/'照会後学習状態.json');書く(出力/'照会後保存判定.json',保存後)
        if 保存後['状態']!='保存済み':raise RuntimeError('照会後状態の保存保留')
        意味一致=意味状態(照会前)==意味状態(json.loads((出力/'照会後学習状態.json').read_text()))
        書く(出力/'照会意味状態比較.json',{'意味状態一致':意味一致,'除外':'識別子状態の照会と学習判定のみ。byte一致ではない。'})
        if not 意味一致:raise AssertionError('照会で記憶意味状態が変化')
        空=形状配置を構成する(問題,HDS学習系統());書く(出力/'空学習系対照.json',空)
        反証系=HDS学習系統.読み込む(出力/'統合学習状態.json')
        元=next(教師 for 教師 in 教師資料['教師'] if 教師['種類']=='投射')
        反証={**元,'内容':{**元['内容'],'接触対象変位':'0,0'},'由来':{'種類':'合成反例対照','元':元['由来'],'変更':'同じ前提の実測15,0を0,0へ反転。実教師ではない。'}}
        書く(出力/'反証投入.json',list(公開教師を教える(反証系,[反証])))
        反証保存=学習状態を保存する(反証系,出力/'反証学習状態.json')
        書く(出力/'反証保存判定.json',反証保存)
        if 反証保存['状態']!='保存済み':raise RuntimeError('反証学習状態の保存保留')
        反証構成=形状配置を構成する(問題,反証系);書く(出力/'反証全体対照.json',反証構成)
        対照=[計数する(値) for 値 in (空,反証構成)]
        if not all(例['状態数']==1 and 例['完成数']==0 and 例['支持辺数']==0 and 例['保留辺数']==6 for 例 in 対照):raise AssertionError('空または反証の全体保留が成立しない')
        if 比較先:
            比較資料=json.loads(比較先.read_text());結果群=[]
            for 通番,比較 in enumerate(比較資料['比較群']):
                比較系=HDS学習系統();ログ=list(公開教師を教える(比較系,比較['教師']))
                結果=[規則を照会する(比較系,入力,比較['境界'],比較['結果名']) for 入力 in 比較['照会']]
                保存比較=学習状態を保存する(比較系,出力/f'比較学習状態{通番}.json')
                記録比較={'名前':比較['名前'],'入力順教師':比較['教師'],'全学習':ログ,'全照会':結果,'保存':保存比較,'正本採用':False}
                書く(出力/f'比較{通番}.json',記録比較)
                if 保存比較['状態']!='保存済み':raise RuntimeError(f'比較学習状態{通番}の保存保留')
                結果群.append({'名前':比較['名前'],'状態群':[値['状態'] for 値 in 結果],'値群':[値['値'] for 値 in 結果]})
            書く(出力/'比較総括.json',結果群)
        計測('対照と比較完了')
        結論={**由来,'状態':'条件付きオフライン照合成立','教師数':len(記録),'構成計数':計数,'全終点事後一致':all(例['占有一致'] for 例 in 事後),'全対照':対照,'資源計測':資源,'保存失敗':False}
        書く(出力/'現在状態.json',結論)
        if not 結論['全終点事後一致']:raise AssertionError('原答えとの事後照合不一致')
        return 結論
    except Exception as 例外:
        計測('例外保留')
        書く(出力/'現在状態.json',{**由来,'状態':'保留','例外種別':type(例外).__name__,'理由':str(例外),'保存済み中間物は保持':True})
        raise

def main():
    引数=argparse.ArgumentParser(description=__doc__)
    引数.add_argument('--出力',type=Path,required=True,help='未作成の保存先。既存結果は上書きしない。')
    引数.add_argument('--教師',type=Path,default=根/'検証/資料/形状配置公開教師.json')
    引数.add_argument('--照合資料',type=Path,default=根/'検証/資料/形状配置照合資料.json')
    引数.add_argument('--比較',action='store_true',help='同じ観測集合の表現/入力順対照も逐次再学習する。')
    値=引数.parse_args()
    結果=再現する(値.出力,値.教師,値.照合資料,根/'検証/資料/形状配置比較教師.json' if 値.比較 else None)
    print(json.dumps(結果,ensure_ascii=False))

if __name__=='__main__':main()
