"""原票の隣接二観測を駆動源にする検証。環境接続は行わない。"""
import pathlib,sys,json,argparse,hashlib
根=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統
from 接続.ARC3境界 import 観測する
from 接続.図式観測 import _作用番号
from 接続.観測駆動一巡 import 記録観測の一巡を処理する

def 実行():
 p=argparse.ArgumentParser();p.add_argument('--状態',type=pathlib.Path,required=True);p.add_argument('--原票',type=pathlib.Path,required=True);p.add_argument('--原票SHA256',required=True);p.add_argument('--前行',type=int,required=True);p.add_argument('--応答行',type=int,required=True);p.add_argument('--図式教師',type=pathlib.Path,required=True);p.add_argument('--記憶先',type=pathlib.Path,required=True);a=p.parse_args()
 if a.前行<0 or a.応答行!=a.前行+1:raise ValueError('一作用対応は原票の隣接行に限る')
 b=a.原票.read_bytes()
 if hashlib.sha256(b).hexdigest()!=a.原票SHA256:raise ValueError('原票SHA不一致')
 行群=[json.loads(x)['data'] for x in b.splitlines() if x];前,後=行群[a.前行],行群[a.応答行]
 def 観測化(r,n):
  r=dict(r)
  if 'levels_completed' not in r and 'score' in r:r['levels_completed']=r['score'];r['win_levels']=r['win_score']
  return 観測する(r,観測通番=n)
 入力=後['action_input'];番号=_作用番号(入力['id']);引数={k:入力.get('data',{}).get(k) for k in ('x','y')} if 番号==6 else {}
 教師=json.loads(a.図式教師.read_bytes());支持=教師['適用支持'];支持['記号順位対応']={int(k):v for k,v in 支持['記号順位対応'].items()};系=HDS学習系統.読み込む(a.状態)
 出所={'原票SHA256':a.原票SHA256,'前行':a.前行,'応答行':a.応答行,'公開記録作用入力':入力,'開始学習状態SHA256':hashlib.sha256(a.状態.read_bytes()).hexdigest(),'新規環境実行':False}
 r=記録観測の一巡を処理する(系,観測化(前,a.前行),{'作用番号':番号,'引数':引数},観測化(後,a.応答行),記憶先=a.記憶先,出所=出所,図式適用支持=支持)
 系.保存する(pathlib.Path(r['記憶参照']['結果']).parent/'照会後HDS状態.json')
 print(json.dumps({'記憶参照':r['記憶参照'],'候補作用照合':r['記録']['候補との作用照合']['状態'],'次候補数':len(r['記録']['次観測候補']['次作用候補群']),'実行許可':False},ensure_ascii=False))
if __name__=='__main__':実行()
