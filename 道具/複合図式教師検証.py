"""可搬な公開教師から学習し、問題盤面だけで攻略候補を構成して事後評価する。"""
import argparse,hashlib,json,pathlib,sys,time
根=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.複合図式規則 import 複合公開教師を教える,複合図式攻略を照会する

def 教師経験を台帳化する(経験):
    教師=経験['教師'];出所=教師['出所'];入力=教師['入力'];種類=教師['種類']
    対象=出所.get('照合対象',出所.get('対象位置',出所.get('作用対象')))
    役割={'連動':'作用対象の直交隣接本体','解答':'小図の参照対象','色作用':'クリック対象本体'}[種類]
    実測={'観測教師値':入力,'前色':出所.get('前色'),'後色':出所.get('後色')}
    return {'対象':対象,'役割':役割,'関係':入力,'状態':{'前色':出所.get('前色')},
            '前提':{'種類':種類,'原票対応':出所},'作用':None if 種類=='解答' else {'種類':'公開座標作用','対象':出所.get('作用対象')},
            '予測差分':None,'実測差分':実測,'保存条件':['原票digest/行/対象の対応'],'成功条件':[],
            '失敗条件':['原票または対応の不一致'],'保留条件':経験['内容'].get('断定保留理由群',[]),
            '反例':None,'適用範囲':'公開二色図式・辺中央標識の条件付きモデル',
            '由来':{'種類':['公開環境観測','HDS実学習','新規固定文法'],'原票':出所},
            '支持経験':経験['根拠'],'HDS記録':経験,'実行許可':False}

def 候補を台帳化する(候補):
    return [{'対象':r['座標'],'役割':'操作可能本体候補','関係':r['全対象予測差分'],
             '状態':{'全対象前色':[{'位置':d['位置'],'色':d['前色']} for d in r['全対象予測差分']]},
             '前提':候補['固定適用仮説'],'作用':{'作用番号':r['作用番号'],'座標':r['座標']},
             '予測差分':r['全対象予測差分'],'実測差分':None,'保存条件':['装飾画素の維持'],
             '成功条件':['終端で全目標制約を充足'],'失敗条件':['予測外deltaまたは新規HOLD'],
             '保留条件':['fresh未実行、hidden文脈の安定は未確認'],'反例':None,
             '適用範囲':候補['適用性'],'由来':{'種類':['HDS実学習','新規固定文法'],'選択理由':r['選択根拠']},
             '支持経験':[d['根拠'] for d in r['全対象予測差分']],'実行許可':False}
            for r in 候補['作用候補群']]

def 実行():
    引数=argparse.ArgumentParser()
    引数.add_argument('--教師',type=pathlib.Path,required=True)
    引数.add_argument('--問題',type=pathlib.Path,required=True)
    引数.add_argument('--出力',type=pathlib.Path,required=True)
    引数.add_argument('--原票ディレクトリ',type=pathlib.Path)
    設定=引数.parse_args();設定.出力.mkdir(parents=True,exist_ok=True)
    教師原票=設定.教師.read_bytes();教師包=json.loads(教師原票)
    問題=json.loads(設定.問題.read_bytes());支持=教師包['適用支持'];支持['記号順位対応']={int(k):v for k,v in 支持['記号順位対応'].items()}
    系=HDS学習系統();開始=time.monotonic();教師記録=[]
    with (設定.出力/'教師台帳.jsonl').open('w') as 台帳:
        for 番号,経験 in enumerate(複合公開教師を教える(系,教師包['教師']),1):
            台帳.write(json.dumps(教師経験を台帳化する(経験),ensure_ascii=False)+'\n');教師記録.append(経験)
            if 番号%50==0:台帳.flush();print('教師',番号,'秒',round(time.monotonic()-開始,1),flush=True)
    系.保存する(設定.出力/'学習状態.json')
    空候補=複合図式攻略を照会する(問題['問題盤面'],問題['利用可能作用'],HDS学習系統(),支持)
    候補=複合図式攻略を照会する(問題['問題盤面'],問題['利用可能作用'],系,支持)
    (設定.出力/'候補台帳.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in 候補を台帳化する(候補)))
    # ここからのみ完成答えを読む。推論入口や教師へ渡さない。
    完成=問題['完成盤面_評価専用'];予測=[行[:] for 行 in 問題['問題盤面']];対象={tuple(c['位置']):c for c in 候補['目標候補群']}
    for 作用 in 候補['作用候補群']:
        for 差分 in 作用['全対象予測差分']:
            セル=対象[tuple(差分['位置'])]
            if any(予測[y][x]!=差分['前色'] for x,y in セル['本体画素']):raise ValueError('候補作用の前状態が矛盾')
            for x,y in セル['本体画素']:予測[y][x]=差分['後色']
    照合=[{'位置':list(位置),'一致':all(予測[y][x]==完成[y][x] for x,y in セル['本体画素'])} for 位置,セル in 対象.items()]
    残差=[[x,y] for y,行 in enumerate(予測) for x,v in enumerate(行) if v!=完成[y][x]]
    結果={'教師数':len(教師記録),'教師原票SHA256':hashlib.sha256(教師原票).hexdigest(),'出所一覧':教師包['出所一覧'],
          '空学習機械':空候補,'候補':候補,'完成照合_評価専用':照合,'全frame残差':残差,
          '盤面一致_最下段除外':bool(照合) and all(y==len(予測)-1 for x,y in 残差),'fresh実行':False,
          '低位対応外':教師包['低位作用対応外'],'制限':'公開教師からの条件付きモデル候補。環境Actionは一切実行していない。'}
    (設定.出力/'検証結果.json').write_text(json.dumps(結果,ensure_ascii=False,indent=2))
    if 設定.原票ディレクトリ:
        作用照合=公開作用を照合する(系,教師包,問題,設定.原票ディレクトリ)
        (設定.出力/'全作用照合.json').write_text(json.dumps(作用照合,ensure_ascii=False,indent=2))
    print('教師',len(教師記録),'条件付き作用',len(候補['作用候補群']),'完成一致',sum(c['一致'] for c in 照合),'/',len(照合),'保留',len(候補['保留理由群']),flush=True)

def 公開作用を照合する(系, 教師包, 問題, 原票ディレクトリ):
    """出所指定はこの評価ハーネスだけが扱う。runtimeへID/rowを渡さない。"""
    from 接続.複合図式規則 import 複合図式を読む,本体対象群を読む,連動対象群を照会する
    from 接続.図式作用教師 import 次色を照会する
    from 接続.図式観測 import _作用番号
    出所={s['実行識別子']:s for s in 教師包['出所一覧']};記録=[]
    for 指定 in 問題['作用評価範囲']:
        識別子=指定['実行識別子'];出典=出所[識別子]
        原票=(pathlib.Path(原票ディレクトリ)/(識別子+'.recording.jsonl')).read_bytes()
        if hashlib.sha256(原票).hexdigest()!=出典['原票SHA256']:raise ValueError('評価原票SHA不一致')
        行群=[json.loads(s)['data'] for s in 原票.splitlines() if s]
        for 番号 in range(指定['開始行']+1,指定['終了行']+1):
            前,後=行群[番号-1],行群[番号];作用=後.get('action_input',{});結果={'出所':出典,'行':番号,'作用入力':作用,'保留理由群':[],'全frame残差':[],'盤面一致_最下段除外':False}
            記録.append(結果)
            if (not 前.get('frame') or not 後.get('frame') or (前.get('guid'),前.get('game_id'))!=(後.get('guid'),後.get('game_id'))):結果['保留理由群'].append('観測欠損/実行境界');continue
            try:作用番号=_作用番号(作用.get('id'));可用={_作用番号(x) for x in 前.get('available_actions',[])}
            except (ValueError,TypeError):結果['保留理由群'].append('作用形式不明');continue
            if 作用番号!=6 or 作用番号 not in 可用 or 後.get('full_reset'):結果['保留理由群'].append('対応外作用/RESET');continue
            # 最初/末尾を同一視しない。この限定照合では複数応答相を保留する。
            if len(後['frame'])!=1:結果['保留理由群'].append({'複数応答相':len(後['frame'])});continue
            f=前['frame'][-1];g=後['frame'][0]
            if len(f)!=len(g) or any(len(a)!=len(b) for a,b in zip(f,g)):結果['保留理由群'].append('寸法変更');continue
            解析=複合図式を読む(f)
            if 'HOLD' in 解析:結果['保留理由群'].append(解析);continue
            if len(解析['色列'])!=2 or 解析['適用保留理由群']:
                結果['保留理由群'].append('二色/全対象対応の適用域外');continue
            セル群=本体対象群を読む(f,解析);x,y=作用.get('data',{}).get('x'),作用.get('data',{}).get('y')
            if type(x)!=int or type(y)!=int:結果['保留理由群'].append('座標欠損');continue
            対象=[c for (xx,yy),c in セル群.items() if xx<=x<xx+c['幅'] and yy<=y<yy+c['幅']]
            if len(対象)!=1:結果['保留理由群'].append('本体対象を一意に対応できない');continue
            変化対象,保留,照会=連動対象群を照会する(系,セル群,対象[0],標識色群=教師包['適用支持']['標識色群'])
            結果['保留理由群']+=保留;結果['照会記録']=照会;予測=[r[:] for r in f]
            for 鍵 in 変化対象:
                c=セル群[鍵];q=次色を照会する(系,解析['色列'],c['本体色']);結果['照会記録'].append(q)
                if q['状態']=='HOLD':結果['保留理由群'].append(q);continue
                for xx,yy in c['本体画素']:予測[yy][xx]=q['次色']
            残差=[[xx,yy] for yy,r in enumerate(予測) for xx,v in enumerate(r) if g[yy][xx]!=v]
            結果['全frame残差']=残差;結果['全frame一致']=not 残差;結果['盤面一致_最下段除外']=not 結果['保留理由群'] and all(yy==len(f)-1 for xx,yy in 残差)
    return {'全操作数':len(記録),'対応操作数':sum(not r['保留理由群'] for r in 記録),'盤面一致数':sum(r['盤面一致_最下段除外'] for r in 記録),'全frame一致数':sum(r.get('全frame一致',False) and not r['保留理由群'] for r in 記録),'記録':記録,'fresh実行':False}

if __name__=='__main__':実行()
