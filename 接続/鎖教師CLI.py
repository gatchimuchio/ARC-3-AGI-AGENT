"""自己完結公開関係教材を空HDSへ教え、独立鎖入口を検査するCLI。"""
from pathlib import Path
import sys,json,argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統, 外部入力
from .鎖接続 import 鎖候補を作る

def 教材を教える(教材,hds=None):
 hds=HDS学習系統() if hds is None else hds
 for t in 教材['教師群']:hds.処理する(外部入力(t['入力'],t['境界'],文脈=t['文脈']))
 return hds

def main():
 p=argparse.ArgumentParser();p.add_argument('--教材',type=Path,default=ROOT/'入力/鎖教師/関係教材.json');p.add_argument('--出力',type=Path,required=True);p.add_argument('--共有照会',action='store_true');p.add_argument('--保存状態',type=Path);a=p.parse_args()
 fixture=json.loads(a.教材.read_text());h=教材を教える(fixture);o=fixture['初期観測'];result=鎖候補を作る(o['frame'],o['available_actions'],h,照会共有=a.共有照会);a.出力.write_text(json.dumps(result,ensure_ascii=False))
 if a.保存状態:h.保存する(a.保存状態)
 print(json.dumps({'作用候補数':len(result['作用候補群']),'支持経路数':result.get('支持経路数',0),'保留経路数':result.get('保留経路数',0),'実行許可':result['実行許可']},ensure_ascii=False))
if __name__=='__main__':main()
