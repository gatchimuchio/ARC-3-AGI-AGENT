# M2-P03 — Clean Rerun Until Pass

- Point ID: `M2-P03_CLEAN_RERUN_UNTIL_PASS`
- Depends on: M2-P02修正
- Next: `M2-P04_SHUFFLED_ORDER_RUNS`

## 目的

公式順序clean runを繰り返し、同一bundleで25/25 WIN・183/183を成立させる。

## 必須作業

1. 各試行をfresh process／session／Mから開始する。
2. 修正済みbundleを固定する。
3. 全25 gameを再実行する。
4. failureがあればM2-P02へ戻す。
5. PASS runの各game row、level count、trace refsを保存する。

## Hard Exit

```text
Run_A_game_WIN_count = 25
Run_A_level_complete_count = 183
Run_A_failed_game_count = 0
Run_A_product_crash_count = 0
manual_intervention_count = 0
bundle_mutation_during_run = 0
run_evidence_nonempty = true
```

## 禁止

- 途中からrun再開してclean扱い
- failure gameの除外
- level countのmanifest値代入
- teacher solutionによる補完

## Failure Routing

Hard Exit未達はM2-P02へ戻る。25/25自己申告だけでM2-P04へ進まない。
