# C2-073 level-progress reward 16.0 held-out seed validation

## 目的と境界

C2-072のdev gateを通過したlevel-progress reward 4→16候補を、devに含めなかったpolicy/environment seedで検証する。公開25 Starter game全体を使い、seed 101/211/307の75 paired runとする。これは**seed holdout**であり、未見game IDへのtransfer holdoutとは主張しない。探索候補は係数16.0だけで、runtime/HDSへの採用判断にはこのscorecardだけで十分とは限らない。

## 固定条件

- public 25 games、`PYTHONHASHSEED=0`、`environment seed = policy seed = 101,211,307`。
- 各paired runは同じ公開開始観測、80 Action上限、`retry_game_over=False`。
- baseline level-progress reward 4.0、candidate 16.0。`visible_change_coefficient=0.0`、探索係数、座標/Action統計、score calculatorを同一に固定。
- 保存はseedごとおよび全体のaggregateのみ。game ID、game別行、盤面、Action軌跡は出力しない。

## 判定

75対の平均RHAE差が正、score改善数が後退数を上回り、level差が0以上、開始観測一致75/75、illegal/exception/duplicateが0の場合をseed robustness passとする。passしても「公式score改善」や未見game-ID転移とはみなさず、HDS/提出agent接続前にC1-023 full local agent scorecardで別途比較する。いずれかが満たせなければ候補を棄却しruntimeへ接続しない。

公式competition submission、Competition Rerun、Notebook/kernel push/edit、quota使用はしない。

## 結果

seed101/211/307の25公開game×3 paired holdoutで75/75 score ties。baseline/candidate RHAE平均とも`0.2594179528`、差0、level/WIN差0、same starts75/75、illegal/exception/duplicate0。Action trace changed9、Action6 +24、actions +25、no-ops +2、GAME_OVER -1だがscore差なし。**gate fail、係数16を棄却しruntimeへ接続しない。** JSON: `運用/証拠/ARC26-UNIFIED/P1-3_level-progress-reward16-seed-holdout_20261027.json`, SHA-256 `9d775b9ba77aa0de3dd1390ef76bad685045aef659809dd33a4bc322cb564270`。
