# M0-P01 — Capability Coverage Matrix

- Point ID: `M0-P01_CAPABILITY_COVERAGE_MATRIX`
- Depends on: R0-P02 PASS
- Next: `M0-P02_BASIS_SET_SELECTION`
- 深層解析: 禁止

## 目的

25 game／183 levelが要求する能力面を浅く一巡し、basis選定の入力を一枚に固定する。

## 入力

- 公式sample metadata／environment source
- PH-D05 manifest／action counts／frame metadata
- R0-P02 RealStateBaseline

## Matrix列

```text
game_id_development_key
level_count
input_modality
action_surface
uses_RESET
uses_ACTION6
uses_ACTION7
max_layer_count
temporal_or_animation
known_delayed_effect
phase_change
known_action_horizon
rollback_or_game_over
spatial_binding_type
goal_structure
planning_depth_estimate
currently_supported_by_product
coverage_gap
```

`game_id`は開発時照合に限り、runtime selectorへ流さない。

## 必須作業

1. 全25 gameを一行ずつ記録する。
2. level合計が183になることを確認する。
3. mandatory capability surfaceを抽出する。
4. 現行productが対応済み／未対応／UNKNOWNを区別する。
5. basis選定へ不要な深層mechanism reportを作らない。

## 出力

- `analysis/product/rev6/capability_coverage_matrix.json`
- 同内容の人間可読tableは任意。PrimaryはJSON一つ。

## Hard Exit

```text
game_rows = 25
level_sum = 183
mandatory_surfaces_explicit = true
coverage_gaps_explicit = true
deep_HDS_case_count = 0
new_shell_or_runner_count = 0
```

## 禁止

- 全gameのTaskMechanismRecord作成
- basis選定前のP/J/M実装
- 照合IDをruntime feature化

## Failure Routing

UNKNOWNは保持し、M0-P02で追加basis条件として扱う。
