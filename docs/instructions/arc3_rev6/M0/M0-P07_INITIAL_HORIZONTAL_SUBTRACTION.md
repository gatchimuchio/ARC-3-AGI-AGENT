# M0-P07 — 初期水平引き算

- Point ID: `M0-P07_INITIAL_HORIZONTAL_SUBTRACTION`
- Depends on: M0-P06 PASS
- Next: `M1-P01_FULL_SAMPLE_BASELINE_WITH_REAL_PRODUCT`

## 目的

basis間の同型能力をGenericMechanismFamilyへ統合し、最初のACTIVE_DEV能力を確定する。

## 比較軸

```text
purpose
input responsibility
precondition
operation
transition/effect
goal/hazard
order/plan
applicability
```

## 必須作業

1. 色、座標、名称、action literalをparameterへ分離する。
2. positive、negative、boundary Caseを保持する。
3. Applicability Predicateを現在観測だけで評価可能にする。
4. identity／replay featureを除外する。
5. PROBATION_DEV能力を昇格・維持・降格する。
6. 全basis gameをregressionする。

## 昇格Hard Gate

```text
independent_support_cases >= 2
negative_cases >= 1
boundary_cases >= 1
behavior_delta_observed = true
identity_router_finding_count = 0
fixed_replay_finding_count = 0
basis_regression_failures = 0
```

## Hard Exit

```text
cross_game_ACTIVE_DEV_family_count >= 1
all_basis_games_WIN = true
one_active_development_bundle = true
```

## 禁止

- 文字列の一般化だけで昇格
- self-declared support counts
- runtimeで使われないfamilyの進捗計上

## Failure Routing

Gate未達能力はPROBATION_DEVまたはDomain-Local Residueに留め、M1で追加Caseを得る。
