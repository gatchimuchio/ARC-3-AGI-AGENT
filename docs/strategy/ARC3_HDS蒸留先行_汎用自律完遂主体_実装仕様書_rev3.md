# ARC3 HDS蒸留先行 汎用自律完遂主体 実装仕様書 rev3

- 仕様ID: `ARC3_HDS_DISTILLATION_FIRST_AUTONOMOUS_COMPLETION_SPEC_REV3`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 戦略改定基準commit: `6858a316241b101bb5a44fd1dd7854dc0fa146c0`
- 旧仕様: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- 上位正本:
  - `AGI三主体統合設計正本_v0_2.md`
  - `工学的AGI実装仕様書_v0_2.md`
  - `HDSフレーム_rev3_1a_内部用統合仕様.md`
  - `HDS蒸留仕様書_ARC2_ARC3_rev2.md`
- 現状監査:
  - `ARC3_現行実装監査_2026-07-30.md`
- 日付: `2026-07-30`
- 仕様状態: `STRATEGY_REBASELINED_DISTILLATION_FIRST`
- 最上位目的: HDSで教師素材から構造データを先に蒸留・凍結し、その成果物だけを長期能力の上流入力として、未知ARC3環境を汎用自律完遂する工学的AGI Instanceを構築する

---

## 0. 戦略改定の固定結論

旧戦略は、先にAGI Runtimeの一般構造を組み、公開ゲームの軌道圧縮やonline学習によって能力を後から埋める順序だった。

rev3では順序を反転する。

```text
教師素材
→ HDS蒸留
→ 構造データ
→ 証拠・境界・反例付き静的freeze
→ Distillation-to-AGI Bridge
→ P₀ / J₀ / M₀
→ AGI Runtime構築
→ online同定・記憶更新
→ locked evaluation
→ official evaluation
```

最重要不変条件:

```text
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
になるまで、
AGI能力実装・P22方策最適化・公式提出準備を進めてはならない。
```

既に実装されたP16〜P21は廃棄しない。  
それらは、蒸留成果物を受け取るための**基盤候補**として凍結する。


戦略変更の直接根拠は、現行P22の独立5-fold holdoutが25実行・0環境完遂・0level完遂であり、既知軌道圧縮から未学習ゲームへ攻略能力が転移していないことである。  
したがって、同じ方策を延命するのではなく、教師素材から機構構造を先に抽出する。

現行P22のS5由来compiled policyは、

```text
HISTORICAL_KNOWN_SAMPLE_STUDENT
```

へ隔離し、最終AGI Runtimeのactive P、fallback、promotion parentとして使用しない。

---

## 1. 最上位目的と完成式

### 1.1 目的

> 正解付きARC3教師素材から、状態、対象、関係、action-effect、precondition、goal、hazard、順序、遅延、probe、rollback、compositionの構造をHDSで蒸留し、証拠状態・適用範囲・反例・未閉包を明示した構造資産へ変換する。その構造資産をP₀／J₀／M₀へ型付きでコンパイルし、未知ARC3環境で観測・仮説・probe・行動・再観測・記憶更新を自律循環する同一の工学的AGI Instanceを構築する。

### 1.2 完成式

```text
ARC3_ENGINEERING_AGI_COMPLETE
=
HDS_DISTILLATION_PIPELINE_COMPLETE
AND HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
AND DISTILLATION_TO_AGI_ABI_FROZEN
AND DISTILLED_INITIAL_STATE_BUNDLE_FROZEN
AND SAME_RUNTIME_ARTIFACT
AND AUTONOMOUS_CLOSED_LOOP
AND MEMORY_CAUSALITY
AND STRUCTURE_GUIDED_ONLINE_IDENTIFICATION
AND IDENTITY_FLOW_CONFORMANCE
AND SEALED_SINGLE_ARTIFACT_COMPLETE
AND COMPETITION_SESSION_INTEGRITY
AND OFFICIAL_FULL_COMPLETE
```

### 1.3 非目的

次は完成ではない。

- S5教師軌道の再圧縮
- 既知25ゲームの100%
- exact available-action surfaceによる暗黙router
- game/task/level ID router
- replay index
- fixed trajectory
- answer map
- source/hidden state
- 自然言語だけのRule集
- exact fitだけの因果確定
- synthetic visual transformation 7/7
- micro-world memory ablationだけ
- P-IR infrastructureだけ
- P/J/Mの形式的存在
- Codexが継続主体であるという扱い
- Codexの自己採否によるphase completion
- Public scoreだけによるfull completion

---

## 2. 戦略上の責任分離

### 2.1 Development Meta-Trinity

```text
Meta-J = 大平鉄兵
Meta-C = Codex / ChatGPT / LLM
Meta-M = Git Repository / 仕様 / Ledger / Artifact
```

- Meta-Jは目的、境界、採否、phase遷移、Rule昇格、完成claimを所有する。
- Meta-Cは解析、候補生成、実装、試験、自己監査、証拠生成を担当する。
- Meta-Mは継続状態、入力、変更、失敗、証拠、版、承認を保持する。

CodexはRuntimeのJではない。  
CodexはAGIそのものでもない。  
Codexは、Ownerに委任された開発計算主体である。

### 2.2 Runtime Trinity

```text
C = Execute(L₀, P)

Runtime AGI
=
Trinity(
  C: 計算主体,
  J: HDS判断主体,
  M: 可変記憶主体
)
```

- `C`は仮説・counter-hypothesis・予測・候補・probe案を生成する。
- `J`はFrame、Gate、採否、action、rollback、memory commit、STOPを裁定する。
- `M`は現在の判断根拠と経験を保持・改訂する。
- `P`は蒸留構造と開発経験から作られた長期命令形である。

### 2.3 CodexとRuntimeの境界

Codexが教師素材を見て作った判断を、runtimeの自律判断として数えない。

```text
Codex development work
≠
Runtime autonomy
```

Runtime artifactへ入れてよいのは、所定のBridge Gateを通過した構造資産だけである。

---

## 3. 現行資産の再分類

### 3.1 Preserve as Infrastructure Candidate

以下は再利用候補として保持する。

- `CognitiveSession`
- `AuthorityState`
- `ControlState`
- `IdentityBoundary`
- candidate-specific Evidence Binding
- episode overlay
- atomic event-sourced memory
- typed causal memory
- negative transfer control
- P-IR type system
- fixed L₀ interpreter
- PBundle packaging
- dataset role registry
- version lineage
- official lifecycle adapter
- deterministic trace

これらは、現行HEADへ再bind・再試験した後にだけ基盤正本へ昇格できる。

### 3.2 Quarantine

以下はactive completion pathから外す。

- `generic_autonomous_policy_v1.json`
- `generic_autonomous_policy_v1.npz`
- S5 weights migration
- known-public compiled MLP
- current P22 public completion artifact
- current 5-fold nearest-centroid artifacts
- current transformation stressを一般性証明とするclaim
- learned reset cycleへ依存するknown trajectory compatibility
- rev1 P12 genericity claim
- P13〜P15旧提出selector

用途:

- historical regression
- failure analysis
- teacher compression baseline
- performance comparison
- non-generalization witness

用途外:

- final P parent
- fallback
- locked evaluator
- official agent
- genericity claim

### 3.3 Replace

次を新規に作る。

```text
Teacher Evidence
→ HDS Distillation
→ HDSStructureBundle
→ Distillation-to-AGI Bridge
→ DistilledInitialStateBundle
→ DistilledAGIRuntime
```

---

## 4. HDS蒸留入力契約

### 4.1 正本入力

ARC3蒸留の正本は、MLP weightsではなく次である。

- raw teacher recording
- canonical teacher trajectory
- before/after render
- raw ACTION1〜ACTION7 / RESET
- ACTION6 payload
- available actions before/after
- terminal state
- level progress
- seed/reset mode
- environment/runtime digest
- provenance
- counterfactual intervention result
- Owner ApprovalRecord

### 4.2 使用禁止入力

蒸留candidate generatorへ次を渡さない。

- current compiled MLP logits
- hidden state
- environment source code
- game-specific answer map
- successful trajectory lookup
- task/game identity as feature
- P22 public completion output as causal truth
- official private result

### 4.3 教師素材と評価素材

```text
DISTILLATION_SOURCE
DEVELOPMENT_VALIDATION
CV_PROCEDURE
LOCKED_FINAL
OFFICIAL_PUBLIC
OFFICIAL_PRIVATE
```

を分離する。

公開25ゲームを蒸留に使った時点で、それらはblind finalではない。  
以後はknown-corpus regressionとして扱う。

---

## 5. HDS構造データ

### 5.1 HDSStructureBundle

```text
HDSStructureBundle/
  manifest.json
  source_manifests/
  ontology/
    entity_types.json
    relation_types.json
    state_variable_types.json
    action_surface_types.json
  mechanisms/
    representation_rules.jsonl
    selector_rules.jsonl
    precondition_rules.jsonl
    action_effect_rules.jsonl
    transition_rules.jsonl
    delayed_effect_rules.jsonl
    goal_rules.jsonl
    hazard_rules.jsonl
    order_rules.jsonl
    composition_rules.jsonl
    rollback_reset_rules.jsonl
    probe_rules.jsonl
  boundaries/
    applicability_boundaries.jsonl
    near_misses.jsonl
    counterexamples.jsonl
    exclusions.jsonl
  failures/
    failure_signatures.jsonl
  unresolved/
    open_terms.jsonl
    unresolved_mechanisms.jsonl
    required_probe_schemas.jsonl
  evidence/
    case_records/
    intervention_results/
    promotion_decisions/
    approvals/
  reports/
    coverage_report.json
    determinism_report.json
    taint_report.json
  frozen_artifact_manifest.json
```

### 5.2 必須構造カテゴリ

1. observation/representation
2. object/entity
3. relation/topology
4. state variable
5. action semantics
6. precondition
7. immediate effect
8. delayed effect
9. transition
10. goal/terminal
11. hazard/failure
12. order/dependency
13. composition
14. probe/information gain
15. rollback/reset
16. applicability boundary
17. failure signature
18. unresolved/probe obligation

### 5.3 各構造record

必須field:

```text
record_id
record_version
domain
mechanism_type
HypothesisIR
trigger
preconditions
predicted_effects
invariants
exclusions
valid_scope
support_case_refs
negative_case_refs
counterexample_refs
intervention_refs
evidence_state
mechanism_support_state
adoption_state
closure_boundary
falsification_procedure
provenance
approval_ref
content_digest
```

### 5.4 証拠状態

```text
OBSERVED_COMPATIBLE
LOCAL_EXACT_FIT
STRUCTURAL_RECURRENCE
BOUNDARY_OBSERVED
COUNTERFACTUAL_SUPPORTED
PROMOTED_CORPUS_SCOPED
REPRODUCIBLE_CONTROL
FALSIFIED
INCONCLUSIVE
```

exact fitだけでPへ入れない。

---

## 6. HDS蒸留完了条件

単一の`DISTILLATION_COMPLETE`を使わない。

```text
PIPELINE_IMPLEMENTATION_COMPLETE
CORPUS_PROCESSING_COMPLETE
CAUSAL_ASSET_COVERAGE_REPORTED
PROMOTED_RULESET_AVAILABLE
DISTILLATION_COVERAGE_ACCEPTED
FROZEN_ARTIFACT_COMPLETE
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

### 6.1 AGI Build Ready Gate

次を全て満たすまでBridge Trackへ進まない。

1. 全source caseがaccounting済み
2. provenance complete率100%
3. raw observationとinferenceが型分離済み
4. exact fitとcausal evidenceが分離済み
5. Rule promotionがOwner承認済み
6. identity/answer-copy finding 0
7. deterministic rebuild x3一致
8. required category全てについて、
   - approved ruleが存在する、または
   - unresolved mechanismとrequired probe schemaが明示される
9. CoverageReportをOwnerが採択
10. `HDS_STRUCTURE_BUNDLE_OWNER_APPROVED`

全件SUSPENDでもpipeline処理は完了し得るが、AGI Build Readyにはならない。

---

## 7. Distillation-to-AGI Bridge

### 7.1 目的

HDS構造資産を、Runtimeが実行・引用できる初期能力へ変換する。

```text
HDSStructureBundle
→ Bridge Compiler
→ P₀
→ J₀
→ M₀
→ ProbeCatalog
→ DistilledInitialStateBundle
```

### 7.2 出力

#### P₀

- representation P-IR
- state construction
- relation graph
- precondition/effect/transition operators
- goal/hazard predicates
- composition procedure
- probe procedure
- rollback/reset procedure
- typed parameters

#### J₀

- HDS Frame template
- Gate configuration
- required evidence policy
- hazard veto
- probe/execute threshold
- promotion/consolidation policy
- stop/rollback boundary
- failure checklist

#### M₀

- approved causal records
- structural priors
- known boundaries
- hazard records
- failure signatures
- unresolved mechanism records
- probation hypotheses
- no case identity

#### ProbeCatalog

- missing information
- safe intervention
- discriminating observation
- expected outcomes by hypothesis
- stop condition
- resource cost

### 7.3 資産別昇格先

| 証拠状態 | P₀ | J₀ | M₀ |
|---|---:|---:|---:|
| `LOCAL_EXACT_FIT` | 禁止 | 禁止 | `PROBATION`のみ |
| `STRUCTURAL_RECURRENCE` | 原則禁止 | checklist候補 | `PROBATION` |
| `BOUNDARY_OBSERVED` | 条件付き候補 | 境界候補 | `PROBATION` |
| `COUNTERFACTUAL_SUPPORTED` | candidate | Gate候補 | `ACTIVE`候補 |
| `PROMOTED_CORPUS_SCOPED` | Owner承認後可 | Owner承認後可 | Owner承認後可 |
| `REPRODUCIBLE_CONTROL` | 可 | 可 | 可 |
| `INCONCLUSIVE` | 禁止 | probe obligation | unresolved |
| `FALSIFIED` | 禁止 | failure checklist | archive |

### 7.4 Bridge禁止事項

- full action sequence
- exact answer trajectory
- case ID branch
- game order
- exact source digest routing
- pre-recorded coordinates
- teacher action surface head
- S5 weights copy
- MLP migration
- natural languageを未検証のままopcode化
- unsupported generalization
- Owner ApprovalRecordなしのactive昇格

---

## 8. DistilledInitialStateBundle

```text
DistilledInitialStateBundle/
  manifest.json
  p_bundle/
  j0_config.json
  m0_snapshot/
  probe_catalog.json
  bridge_report.json
  taint_report.json
  non_replay_report.json
  compatibility_report.json
  approval_record.json
```

manifest必須field:

```text
bundle_version
parent_structure_bundle_digest
bridge_compiler_version
p_logical_digest
j0_digest
m0_digest
probe_catalog_digest
l0_abi_version
identity_free
trajectory_free
answer_map_free
runtime_source_tree_digest
owner_approval_digest
logical_digest
physical_package_digest
```

---

## 9. AGI Runtime構築契約

### 9.1 active P

最終Runtimeのactive Pは、`DistilledInitialStateBundle`から読み込む。

```text
load_compiled_autonomous_instruction_body()
```

をproduction completion pathで呼ばない。

S5 compiled policyはhistorical diagnosticに限定する。

### 9.2 C

Cは次を行う。

```text
Observation
+ P₀ structure
+ M_t citations
→ current state representation
→ mechanism hypotheses
→ counter-hypotheses
→ predicted action effects
→ discriminating probes
→ action candidates
```

M citationが変われば、

- hypothesis set
- candidate generation
- candidate ranking
- predicted effect
- selected probe/action

の少なくとも一つが変わらなければならない。

### 9.3 J

JはHDSとして、

- Frameを固定
- open termを検出
- multiple modelを比較
- evidence strengthを検査
- hazardをveto
- probe/execute/reobserveを選択
- memory commitを承認
- rollback/stopを承認

する。

Pの推奨をそのままcommitしない。

### 9.4 M

Mは、

- current mechanism hypotheses
- action/effect evidence
- contradiction
- hazard
- delayed effect
- goal progress
- failure signature
- probe result
- applicability scope

を保持する。

M更新は未来のC/J/actionを因果的に変える必要がある。

### 9.5 online mechanism identification

```text
initial hypotheses from P₀/M₀
→ current observationとの適用可能性評価
→ discriminating probe
→ outcome attribution
→ support/contradiction更新
→ active mechanism selection
→ execution
→ reobservation
```

未知機構が既存ruleに一致しない場合、fallback answerを出さず、probeまたはSUSPENDする。

---

## 10. 実行モード

| 要素 | DEVELOPMENT | LOCKED_FINAL | COMPETITION |
|---|---:|---:|---:|
| Code/L₀ | Codex実装で可変 | 固定 | 固定 |
| HDSStructureBundle | version更新可 | 固定 | 固定 |
| Bridge Compiler | version更新可 | 固定 | 固定 |
| P | candidate生成可 | 固定 | 固定 |
| J implementation/config | candidate生成可 | 固定 | 固定 |
| M₀ | candidate生成可 | 固定 | 固定 |
| Runtime M | 永続M_dev | run-local | scorecard-local |
| Ledger | 永続 | sealed保存 | session保存 |
| Code online rewrite | 禁止 | 禁止 | 禁止 |
| P online promotion | 禁止 | 禁止 | 禁止 |
| M online update | 可 | 可 | 可 |
| Teacher source access | distillation only | 禁止 | 禁止 |

---

## 11. Codexの役割

Codexは、

```text
Development Meta-C
=
分析器
+ 実装器
+ 試験実行器
+ 証拠生成器
+ 自己監査器
```

である。

Codexは次を所有しない。

- 最上位目的
- HDS最終採否
- Rule promotion
- phase promotion
- Owner Approval
- completion claim
- official submission authorization
- locked final access authorization
- AGI RuntimeのJ
- 長期継続主体としての自己同一性

Codexの詳細運用は、

```text
ARC3_AGENTS_Codex開発運用契約_rev3.md
```

を正本とする。

---

## 12. Evaluation Governance

### 12.1 Known public

公開25ゲームは蒸留sourceかつdevelopment regressionである。  
blind genericity evidenceではない。

### 12.2 CV

CVは、

- distillation procedure
- Bridge compiler
- development method

の補助証拠である。

foldごとに別artifactとなるため、single-artifact completionではない。

### 12.3 Mechanism-family holdout

単なるgame foldに加え、次を分離する。

- action-effect family
- goal family
- hazard/reset family
- delay/order family
- pointer payload family
- composition family
- partial observation family

holdout familyを蒸留・P buildから除外したartifactで評価する。

### 12.4 Locked final

- independently generated
- runtime実装者から内容隔離
- one frozen artifact
- one-time execution
- result開示後CONSUMED
- developmentへ使った時点でfinal資格喪失

### 12.5 Official

```text
OFFICIAL_RUN_ACCEPTED
OFFICIAL_PUBLIC_COMPLETE
OFFICIAL_PRIVATE_COMPLETE
OFFICIAL_FULL_COMPLETE
```

を分離する。

---

## 13. Claim Hierarchy rev3

| Claim | 意味 | 完成扱い |
|---|---|---:|
| `INFRASTRUCTURE_BASELINE_FROZEN` | P16〜P21基盤を現行HEADへbind | しない |
| `HDS_DISTILLATION_PIPELINE_COMPLETE` | 蒸留pipeline実装 | しない |
| `HDS_CORPUS_PROCESSED` | 全教師case処理 | しない |
| `HDS_STRUCTURE_BUNDLE_FROZEN` | 構造資産freeze | しない |
| `HDS_STRUCTURE_BUNDLE_OWNER_APPROVED` | Ownerがcoverageを採択 | AGI build開始条件 |
| `DISTILLATION_TO_AGI_ABI_FROZEN` | Bridge契約freeze | しない |
| `DISTILLED_INITIAL_STATE_BUNDLE_FROZEN` | P₀/J₀/M₀ freeze | しない |
| `DISTILLED_RUNTIME_STRUCTURAL_READY` | active runtimeがdistilled assetsのみ使用 | しない |
| `MEMORY_CAUSAL_OFFICIAL_LIKE` | official-like環境でM差が未来行動を変える | しない |
| `MECHANISM_IDENTIFICATION_CAUSAL` | probeで競合仮説を識別 | しない |
| `KNOWN_PUBLIC_REGRESSION` | 既知25ゲーム回帰 | しない |
| `CV_PROCEDURE_EVIDENCE` | fold別補助証拠 | しない |
| `SEALED_SINGLE_ARTIFACT_COMPLETE` | one artifact locked完遂 | 中間 |
| `COMPETITION_READY` | lifecycle/resource/package | しない |
| `OFFICIAL_RUN_ACCEPTED` | score返却 | しない |
| `OFFICIAL_PUBLIC_COMPLETE` | Public 100% | 部分 |
| `OFFICIAL_PRIVATE_COMPLETE` | Private 100% | 部分 |
| `OFFICIAL_FULL_COMPLETE` | Full 100% | 最終 |

---

## 14. Blocking Acceptance

### 14.1 Distillation

- `DST-001` source manifest complete
- `DST-002` raw/computed/inferred型分離
- `DST-003` typed HypothesisIR
- `DST-004` exact fitとcausal evidence分離
- `DST-005` counterfactual verifier
- `DST-006` coverage report
- `DST-007` identity/answer-copy finding 0
- `DST-008` deterministic rebuild x3
- `DST-009` Owner approval

### 14.2 Bridge

- `BRG-001` structure-to-P/J/M mapping完全
- `BRG-002` unsupported rule active化0
- `BRG-003` case identity flow 0
- `BRG-004` trajectory/answer map 0
- `BRG-005` S5 weight dependency 0
- `BRG-006` L₀ ABI PASS
- `BRG-007` initial bundle deterministic
- `BRG-008` Owner approval

### 14.3 Runtime

- `AGI-001` active Pはdistilled bundle由来
- `AGI-002` S5 fallback 0
- `AGI-003` multiple hypotheses
- `AGI-004` discriminating probe
- `AGI-005` candidate-specific evidence
- `AGI-006` memory causal witness
- `AGI-007` negative transfer rollback
- `AGI-008` identity leak 0
- `AGI-009` same runtime artifact
- `AGI-010` valid SUSPEND/STOP

### 14.4 Evaluation

- `EVAL-001` known publicをblind扱いしない
- `EVAL-002` CVをsingle artifact扱いしない
- `EVAL-003` mechanism-family holdout
- `EVAL-004` locked final one-time
- `EVAL-005` official scope分離

一件でもblocking requirementがPASS以外なら完成claimを出さない。

---

## 15. 現行repository変更方針

### 15.1 Freeze first

現行HEADへ全phase stateを再bindする。

```text
PRE_DISTILLATION_INFRASTRUCTURE_BASELINE
```

としてcommit/tree/package/testを固定する。

### 15.2 Active selector

`AGENTS.md`のactive selectorを次へ変更する。

```text
PH-R00
→ PH-D00A ... PH-D14
→ PH-B00 ... PH-B06
→ PH-A00 ... PH-A08
→ PH-E00 ... PH-E04
```

P22以降の旧selectorはhistoricalへ移す。

### 15.3 Production import boundary

最終runtime packageから次へのproduction importを禁止する。

- `teacher/`
- `s5_runtime`
- `compiled_policy`のS5 bundle loader
- current P22 CV artifacts
- current known-public weights
- answer/trajectory corpus

### 15.4 Distillation repository boundary

HDS蒸留は別packageまたは明確なdevelopment-only namespaceに置く。

```text
distillation/
bridge/
runtime/
```

を分離する。

---

## 16. 固定禁止事項

1. 蒸留完了前のAGI能力最適化
2. current P22 MLPの延命
3. S5をfallbackに戻す
4. Codexによる自動Rule promotion
5. Codexによる自動phase PASS
6. uncommitted worktreeをphase証拠にする
7. live LLM outputを決定論artifactに混入
8. holdout結果をdevelopmentへ反復利用
9. exact fitを真因と呼ぶ
10. synthetic visual stressをgenericityと呼ぶ
11. runtimeへteacher sourceを同梱
12. active decisionへcase identityを渡す
13. source codeからmechanismを直接抽出
14. PがJ権限を代行
15. M recordが候補固有でないままEXECUTE
16. unsupported ruleを安全defaultとして実行
17. official scoreだけで原因を層へ帰属
18. Owner承認なしの完成claim

---

## 17. 最終固定式

```text
HDS Distillation
=
Teacher Evidence
→ Executable Hypotheses
→ Exact Fit
→ Counterfactual Audit
→ HDS Decision
→ Cross-Case Structure
→ Boundary / Failure / Unresolved
→ Owner-Approved Structure Bundle
```

```text
Distilled AGI Initial State
=
Bridge(
  HDSStructureBundle
)
→ P₀ + J₀ + M₀ + ProbeCatalog
```

```text
ARC3 Engineering AGI
=
Trinity(
  Execute(L₀, P),
  J_hds,
  M
)
+ DistilledInitialStateBundle
+ Online Mechanism Identification
+ Governed Development Meta-Trinity
```

---

## 18. 最終判定

rev3の戦略は、

> **AGIを先に作って正解を覚えさせるのではなく、正解付き多数事例からHDSで構造を先に抽出し、その構造を長期能力・判断規範・初期記憶へ変換した後にAGI Runtimeを構築する。**

という順序へ固定する。

この順序により、

```text
既知軌道圧縮
```

と、

```text
構造を引用して未知環境を同定・完遂する主体
```

を分離する。
