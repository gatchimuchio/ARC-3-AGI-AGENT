# M2-P05 — Full-Sample Product Closure

- Point ID: `M2-P05_FULL_SAMPLE_CLOSURE`
- Depends on: M2-P03／P04 PASS
- Next: `M3-P01_CJMP_ABLATION`

## 目的

一つのACTIVE_DEV bundleによるfull-sample完遂を、inspectableな実行証拠へ閉じる。

## 必須入力

- nonempty Run A／B／C evidence
- immutable bundle identity
- per-game rows
- level completion evidence
- failure／manual intervention counts

## 必須作業

1. A／B／Cの実行証拠を再集計する。
2. countをmanifestやteacher値から埋めず、run rowsから算出する。
3. identity／replay preliminary scanを行う。
4. M2 claim boundaryを`FULL_SAMPLE_ACTIVE_DEV_CLOSURE`に限定する。
5. release／AGI conformanceをまだ宣言しない。

## Hard Exit

```text
nonempty_full_run_count = 3
per_run_game_WIN_count = 25
per_run_level_complete_count = 183
one_agent_architecture = true
one_ACTIVE_DEV_ProductBundle = true
fixed_replay_finding_count = 0
identity_router_finding_count = 0
manual_intervention_count = 0
product_completion_released = false
```

## 禁止

- 空run artifact参照
- replay記述をresidueへ隠してzero扱い
- M3を同時完了
- RELEASE_FROZEN宣言

## Failure Routing

一項目でも未達なら該当M2 Pointへ戻る。
