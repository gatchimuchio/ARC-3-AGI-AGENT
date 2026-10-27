# C2-006 座標Action初手優先の検証

## 仮説

C2-003 holdout集計ではAction6（座標Action）だけがlevel進行を記録した。Action1/2/3/4/5/7には進行がなかった。現行方針は合法な未試行Actionを無作為順に試すため、Action6が使えるゲームでも初手が遅れる場合がある。未試行の座標Actionを最初に試すだけで進行が早まるかを測る。

## 比較条件

- 現行v4と、Action6が合法かつ座標を構成できる場合に初回の未試行Actionとして優先する方針を比較する。他Action、報酬係数、UCB、座標・色選択は固定。
- split seed `20261022` の開発5環境をAction seed 7/31/73、各80 Action、GAME_OVER後RESET有効で評価。
- 開発でcompleted levelsを維持し、2/3以上のseedで完了Action数またはno-opが改善し、GAME_OVERを増やさない場合だけholdout20環境をseed31で一度評価する。
- holdoutでもlevelsを維持し、完了Action数/no-op/GAME_OVERを悪化させない場合のみruntime候補へ採用する。holdoutでチューニングしない。
- Action6優先は全ゲーム共通の操作種類規則であり、game/level ID等による分岐は追加しない。条件未達なら既定値を変更しない。

## 実装

`観測駆動探索方針` に既定OFFの実験引数を追加し、評価器から有効化する。既定の現行動作を保持する。

## 完了条件

結果・artifact hash・採否を `検証/運転記録/ARC3-RUN-002_C2-006_座標Action初手評価_20261023.md` に記録する。
