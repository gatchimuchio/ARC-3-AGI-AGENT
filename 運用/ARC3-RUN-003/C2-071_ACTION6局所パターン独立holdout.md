# C2-071 — ACTION6局所パターンの独立10ゲーム未見評価

## 背景・境界

C2-067/069ではUCB weight`0.35/0.7`が同一結果（dev15対でΔRHAE`+0.004360858`、improvement1/regression0/tie14）となり、C2-070でもtrain 5→10ゲームで同値だった。事前dev gate`+0.01`は未達なので**候補採用条件を満たしていない**。反復した小差の転移再現性だけを、別の未評価公開game群で判定する。

## 固定条件

- shuffle seed `20261027`。train windows `0..4`と`10..14`の計10ゲーム×40 Actionで学習、holdoutは未見windows `15..24`の10公開ゲーム×seeds `7,31,73`、各80 Action。以前のdev windows `5..9`はこの評価に含めない。
- candidateはUCB weight`0.35`。baselineは現行policy、初期盤面/合法集合/環境seed/方針seedをpair一致させる。
- 主要指標は公式EnvironmentScoreCalculatorのRHAE。holdout replication条件は平均ΔRHAE`>=+0.005`、improvement数>regression数、level差非負、Illegal/duplicate/error 0。満たしてもshared runtimeへ自動採用せず、25環境全体の再評価が別途必要。

## 採否

条件を満たさなければACTION6局所memory候補を棄却する。どの結果でもこのlocal experimentだけを公式score改善と称さず、Kaggle quota/submission/Notebook/kernelは使用しない。
