# M1-P02 — Capability Gap選定

- Point ID: `M1-P02_CAPABILITY_GAP_SELECTION`
- Depends on: M1-P01または前回M1-P06
- Next: `M1-P03_HDS_CASESET_ANALYSIS`

## 目的

次に閉じる製品能力不足を一つだけ選び、Capability Closure Unitを固定する。

## 選定軸

```text
affected game count
affected level count
endpoint blocking severity
cross-game reuse potential
dependency order
implementation cost
regression risk
observability of result delta
```

## 必須作業

1. failure clusterを比較する。
2. 一つのgapだけを選ぶ。
3. affected CaseSetを固定する。
4. expected behavior deltaとendpoint deltaを定義する。
5. likely responsible componentを仮置きする。
6. 代理解を禁止事項として列挙する。

## 出力

`analysis/product/rev6/m1/units/<unit_id>/closure_unit.json`

必須field:

```text
unit_id
product_gap
affected_games
affected_levels
failure_signature
expected_behavior_delta
expected_game_level_delta
responsibility_hypotheses
forbidden_shortcuts
```

## Hard Exit

```text
selected_gap_count = 1
affected_case_count > 0
expected_delta_is_measurable = true
responsibility_is_hypothesis_not_claim = true
```

## 禁止

- 複数gapを一括実装
- game単位の答え追加
- 実測不能な「改善」
- shell／runner／schemaをgapに偽装

## Failure Routing

選定gapが観測不能ならM1-P01のclusterへ戻り、測定可能な単位へ分解する。
