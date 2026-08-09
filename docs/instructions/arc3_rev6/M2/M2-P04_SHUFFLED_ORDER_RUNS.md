# M2-P04 — Shuffled Order Runs

- Point ID: `M2-P04_SHUFFLED_ORDER_RUNS`
- Depends on: M2-P03 PASS
- Next: `M2-P05_FULL_SAMPLE_CLOSURE`

## 目的

game順序依存、cross-game contamination、暗黙identity routeを検出する。

## 実行契約

```text
Run B: deterministic shuffle seed B
Run C: deterministic shuffle seed C
fresh process/session/M for each run
same immutable ProductBundle as Run A
```

## 必須作業

1. B／Cの順序を保存する。
2. 各runで25 game／183 levelを実行する。
3. per-game functional resultをAと比較する。
4. M transfer、resource、failure、action count差を解析する。
5. 順序依存が見つかればM2-P02へ戻る。

## Hard Exit

```text
Run_B_game_WIN_count = 25
Run_B_level_complete_count = 183
Run_C_game_WIN_count = 25
Run_C_level_complete_count = 183
orders_are_distinct = true
same_bundle_all_runs = true
blocking_order_dependency_count = 0
manual_intervention_count = 0
```

## 禁止

- game IDで順序別policy選択
- runごとにP／M0変更
- mismatchを許容誤差として隠す

## Failure Routing

順序依存はM2-P02でmemory scope／transfer／resourceを修正し、A／B／Cを再実行する。
