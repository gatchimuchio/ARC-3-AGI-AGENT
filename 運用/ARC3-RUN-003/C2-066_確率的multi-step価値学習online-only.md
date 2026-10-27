# C2-066 — 確率価値モデルの同一ゲーム内オンライン学習

## 問い

C2-065の事前学習value priorは未見dev15対でscore `-0.056678097`、level差`-1`、9対でaction traceを変えた。これがcross-game transferのnegative transferか、確率価値モデル自体の不適合かを切り分ける。train分割を使わず、各devゲームの最初から公開遷移のみで更新する。

## 固定条件

- C2-065と同じ公開split seed `20261027`、同じ未見5ゲーム、seeds `7,31,73`、80 Action上限、同一開始状態のpaired比較。
- baselineは現行の観測駆動UCB。candidateは空のID-free value memoryから各episode内でオンライン更新し、episode終了時に破棄する。別ゲーム間で情報を混ぜない。
- context、reward、Dirichlet-backoff Bellman反復、prior weight `0.5`はC2-065と同一。事前学習経験だけを0にする。
- primary metric RHAE。dev gateは平均差`>= +0.01`、improvement数がregression数以上、level合計を減らさず、start mismatch/illegal/duplicate/contract errorが0。
- 同一ゲーム内のprior-supportedなaction列変化数、開始盤面一致、更新数、学習後memory hashを記録する。

## 採否

gate未達ならprobabilistic modelを棄却し、runtime/Notebookへ接続しない。通過時のみ残り未見15ゲームで別holdout確認を行う。C2-065は別実験として棄却のまま保持する。

## 境界

公開SDK観測のみ。ゲーム/レベル識別子・answer map・固定軌跡なし。Kaggle submission、quota、Notebook/kernelの変更なし。
