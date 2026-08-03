# M1-P04 — Capability実装

- Point ID: `M1-P04_CAPABILITY_IMPLEMENTATION`
- Depends on: M1-P03 PASS
- Next: `M1-P05_AFFECTED_GAME_CLOSURE`
- Product code／bundle change: 必須

## 目的

HDS CaseSet解析を、実製品が使用する一つの能力差分へ変換する。

## 実装責任

次から最小責任部品を選ぶ。

```text
P_dev
J_dev
M_dev
C representation／hypothesis／planner
J gate／authorization／stop
M retrieval／update／consolidation
Adapter observation／action binding
Resource configuration
```

## 必須作業

1. typed capabilityを実装する。
2. source Case、Applicability、falsification、asset stateを保持する。
3. actual product runtimeへloadする。
4. C／J／Mの使用traceを取得する。
5. expected behavior deltaを局所実行で確認する。
6. 既存product path以外を作らない。

## Asset State

初回は`PROBATION_DEV`。既存ACTIVE_DEV修正の場合はrevision lineageを保持する。

## Hard Exit

```text
product_runtime_loads_capability = true
capability_use_trace_count > 0
expected_unit_behavior_delta_observed = true
parallel_product_path_count = 0
identity_feature_count = 0
trajectory_playback_count = 0
```

## 禁止

- analysis artifactだけの変更
- self-declared support count
- release bundleへの直接反映
- complete action sequenceの格納

## Failure Routing

capabilityが実行されない場合は本Pointの実装不良。M1-P05へ進まない。
