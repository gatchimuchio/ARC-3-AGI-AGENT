"""問題画素と外部HDSだけを受ける独立線標識接続。外部step/教材読込/学習はしない。"""
from .線標識内部 import 基礎,二図形,三図形,知覚

def 線標識候補を作る(問題,利用可能作用,hds):
 try:actions=list(利用可能作用)
 except (TypeError,ValueError)as exc:return {"状態":"保留","理由":"利用可能作用一覧が不正","例外":str(exc),"実行許可":False}
 trace=[]
 class 照会記録:
  def 照会する(self,inp):
   row={"入力":inp.内容,"境界":inp.対象系境界};trace.append(row)
   try:
    out=hds.照会する(inp);row.update({"状態":out.状態,"内容":out.内容,"追跡":out.追跡情報});return out
   except Exception as exc:row.update({"例外種別":type(exc).__name__,"例外":str(exc)});raise
 query=照会記録()
 held={'状態':'保留','実行許可':False,'新規環境成功':False,'途中を含む全照会':trace,'全外部作用候補':[{'作用':a,'状態':'保留'}for a in actions]}
 try:
  if len(問題)!=64 or any(len(row)!=64 for row in 問題):raise ValueError('64×64画素が必要')
  if any(type(v)is not int or not 0<=v<=15 for row in 問題 for v in row):raise ValueError('有限整数パレット0〜15のみ')
  if any(type(a)is not int or not 0<=a<=7 for a in actions) or len(set(actions))!=len(actions):raise ValueError('利用可能作用は重複のない整数0〜7のみ')
  if not set(range(1,6))<=set(actions):raise ValueError('全四方向と選択作用の外部提供が必要')
  initial=基礎.知覚初期(問題)
  if initial['適用可能']:
   # 既存描画器の全2順を残し、対象外画素を背景へ黙って置換しない。
   actual=[list(row)for row in 問題[:63]]
   reconstructions=[知覚.描画(initial,initial['図形'],order)for order in ([0,1],[1,0])]
   if not any(frame==actual for frame in reconstructions):
    residuals=[[{'位置':[x,y],'観測':actual[y][x],'再描画':frame[y][x]}for y in range(63)for x in range(64)if frame[y][x]!=actual[y][x]]for frame in reconstructions]
    return {**held,'理由':'二図形の全描画順で初期可視画素が一致しない','全描画順候補':[[0,1],[1,0]],'全描画残差':residuals,'未照合領域':'最下行HUD'}
   result=二図形.構成(問題,query);family='二色直交十字'
  else:
   parsed=知覚.全分解(問題)
   if not parsed['候補']or any(len(c['図形'])!=3 for c in parsed['候補']):return {**held,'理由':'二図形又は三色一色一図形の固定文法外','全初期分解':parsed}
   result=三図形.構成(問題,query);family='三色線図形'
  result.update({'途中を含む全照会':trace,'構成文法':family,'実行許可':False,'新規環境成功':False,'未対応外部作用':[{'作用':a,'状態':'保留','理由':'未学習の作用'}for a in actions if a not in range(1,6)],'限界':['初期問題用。継続履歴・第3問以降未対応','全因子積の画素再構成は未検証','完成答え全画素は未照合','外部実環境成功なし']})
  return result
 except Exception as exc:
  return {**held,'理由':'例外による全体保留','例外種別':type(exc).__name__,'例外':str(exc)}
