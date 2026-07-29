# ARC3 Identity / Taint Threat Model

- model ID: `ARC3_IDENTITY_TAINT_THREAT_MODEL_REV2`
- phase introduced: `P16`
- specification: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- model status: `PASS`
- runtime enforcement status: `PARTIAL_CURRENT`, completion target `P17-B`

## Assets

- 汎用decision pathのidentity independence
- HDS authorityとsingle-use capability
- P/Mの意味内容
- LOCKED_FINALの未参照性
- official artifactとscore scopeの同一性
- Experience Ledgerの監査完全性
- credentialと外部実行境界

## Trust boundaries

```text
OrchestrationMetadata
  -> runner / environment adapter only
  -X-> DecisionContext / C / P / J / M

DecisionObservation
  -> P representation / C / J / candidate-bound M retrieval

AuthorityState
  -> mechanical executors
  -X-> serialized SemanticMemory / restored token

Development data
  -> Ledger / compiler under role policy
  -X-> LOCKED_FINAL before freeze

Teacher / source / replay
  -> historical development evidence only
  -X-> runtime package and runtime decision input
```

## Taint classes

| Taint | Sources | Forbidden sinks |
|---|---|---|
| `ORCHESTRATION_IDENTITY` | scorecard/game/task/level ID、game index/order、opaque handle | C/P/J/M input、retrieval、candidate rank、action choice |
| `SOURCE_PRIVILEGE` | environment source、hidden state、evaluator internals | runtime package、P/M、decision trace |
| `SOLUTION_PRIVILEGE` | replay、answer map、fixed action sequence、trajectory座標 | active runtime、P/M lookup |
| `PRECOMPUTED_COORDINATE` | game固有座標表、trajectory由来座標 | action payload生成 |
| `EXACT_STATE_GLOBAL` | exact public frame digest/signature | `SESSION_GLOBAL` key、P、cross-game route |
| `EVALUATION_ACCESS` | fold membership、LOCKED_FINAL content/result | training、promotion、compiler trigger |
| `AUTHORITY_CAPABILITY` | live nonce/token、issued capability | persistence、M、replay after restart |
| `CONTROL_STATE` | cycle、budget、no-progress、pending probe | world-knowledge retrieval、P compile evidence |
| `SECRET` | Kaggle/API token、cookie、session secret | Git、logs、reports、P/M |

## Allowed declassification

- 現在renderから同cycleに動的導出した`x, y`は
  `CURRENT_RENDER_COORDINATE`としてaction payloadに使用できる。
- exact observation digestは`WORKING`、`LEVEL_OVERLAY`、
  `EPISODE_OVERLAY`に限り使用できる。
- cross-game利用前に、exact digest、ID、order、opaque tokenを除去し、
  normalized causal precondition/effect/scopeへ変換する。
- episode nonceは独立証拠groupの重複排除にだけ使い、
  retrieval/candidate featureへ含めない。
- game IDはaudit mappingとenvironment lifecycleにだけ使用する。

## Explicit rejection rules

- current renderからの動的座標まで禁止してはならない。
- 事前座標、ID route、replay route、exact-frame global routeはfail closedする。
- `OrchestrationMetadata`を受け取るC/P/J/M APIを追加しない。
- capabilityをserializeした時点で失効扱いにする。
- LOCKED_FINALへfreeze前にcontent accessがあればそのevaluatorを開発用へ降格する。
- scalar scoreだけからCode/P/J/Mの原因を断定しない。

## Required controls

| Control | Phase |
|---|---|
| static typed `DecisionContext` / `OrchestrationMetadata` boundary | P17-B |
| serialized decision-input inspection | P17-B |
| taint propagation and sink rejection | P17-B |
| metadata/game-order permutation | P17-B/P22 |
| exact-frame replacement and dynamic-coordinate tests | P17-B |
| candidate compiler evidence taint audit | P20-B |
| evaluation access ledger | P21 |
| package source/Teacher/secret exclusion | continuous/P23 |

## Threat-model gate versus enforcement gate

P16の`identity_taint_threat_model = PASS`は、asset、source、sink、
declassification、control、反証条件が閉じたことだけを意味する。
runtime enforcementはP17-B以降の試験がPASSするまで`PARTIAL_CURRENT`である。
