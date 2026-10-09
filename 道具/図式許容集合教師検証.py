"""公開成功答えからの追加教師。出所/完成盤面は評価ハーネス限定。"""
import pathlib,sys,json,argparse,hashlib
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.複合図式規則 import 複合公開教師を教える
from 接続.図式許容集合 import 許容役割教師を教える,許容集合を含む図式攻略を照会する
from 接続.共通観測経路 import 公開観測から候補を照会する
from 接続.ARC3境界 import 観測する

def 実行():
 p=argparse.ArgumentParser();p.add_argument('--基底教師',type=pathlib.Path,required=True);p.add_argument('--追加教師',type=pathlib.Path,required=True);p.add_argument('--照合資料',type=pathlib.Path,required=True);p.add_argument('--基底状態',type=pathlib.Path);p.add_argument('--出力',type=pathlib.Path,required=True);a=p.parse_args();a.出力.mkdir(parents=True,exist_ok=True)
 基底=json.loads(a.基底教師.read_bytes());追加=json.loads(a.追加教師.read_bytes());資料=json.loads(a.照合資料.read_bytes());支持=基底['適用支持'];支持['記号順位対応']={int(k):v for k,v in 支持['記号順位対応'].items()}
 系=HDS学習系統.読み込む(a.基底状態) if a.基底状態 else HDS学習系統()
 if not a.基底状態:
  with (a.出力/'基底教師台帳.jsonl').open('w') as f:
   for r in 複合公開教師を教える(系,基底['教師']):f.write(json.dumps(r,ensure_ascii=False)+'\n')
 問題=資料['例群'][0];前=許容集合を含む図式攻略を照会する(問題['問題盤面'],問題['利用可能作用'],系,支持)
 with (a.出力/'追加教師台帳.jsonl').open('w') as f:
  for r in 許容役割教師を教える(系,追加['教師']):f.write(json.dumps(r,ensure_ascii=False)+'\n')
 系.保存する(a.出力/'学習状態.json')
 観測=観測する({'frame':[問題['問題盤面']],'state':'NOT_FINISHED','available_actions':問題['利用可能作用'],'game_id':'評価用観測','guid':'評価用実行','levels_completed':0,'win_levels':1},観測通番=1)
 共通=公開観測から候補を照会する(系,観測,図式適用支持=支持);後=next(x['結果'] for x in 共通['語彙別結果'] if x['語彙']=='複合配色')
 # 完成盤面はここからのみ評価に使用。runtimeへの入力は問題盤面だけ。
 比較=[]
 for 経路 in 後.get('全条件付き経路群',[]):
  色={(x,y):c for x,y,c in 経路['終端']};予測=[r[:] for r in 問題['問題盤面']]
  for 対象 in 後['目標候補群']:
   for x,y in 対象['本体画素']:予測[y][x]=色[tuple(対象['位置'])]
  完成照合=[]
  for 例 in 資料['例群']:
   完成=例['完成盤面_評価専用'];残差=[[x,y] for y,r in enumerate(予測) for x,c in enumerate(r) if c!=完成[y][x]]
   完成照合.append({'出所':例['出所'],'全本体一致':all(all(予測[y][x]==完成[y][x] for x,y in t['本体画素']) for t in 後['目標候補群']),'全画素残差':残差})
  比較.append({'完成照合_評価専用':完成照合})
 結果={'教師数':len(追加['教師']),'基底状態SHA256':hashlib.sha256(a.基底状態.read_bytes()).hexdigest() if a.基底状態 else None,'追加前':前,'共通照会':共通,'追加後':後,'完成比較':比較,'適用範囲':追加['適用範囲'],'実行許可':False}
 (a.出力/'検証結果.json').write_text(json.dumps(結果,ensure_ascii=False,indent=2));系.保存する(a.出力/'照会後状態.json');print('追加教師',len(追加['教師']),'経路数',len(後.get('全条件付き経路群',[])),'次作用数',len(共通['次作用候補群']),'保留',len(後['保留理由群']))
if __name__=='__main__':実行()
