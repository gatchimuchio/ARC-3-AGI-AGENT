# ARC3 HDS蒸留先行 汎用自律完遂主体 実装仕様書 rev3

- 仕様ID: `ARC3_HDS_DISTILLATION_FIRST_AUTONOMOUS_COMPLETION_SPEC_REV3`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 戦略改定基準commit: `6858a316241b101bb5a44fd1dd7854dc0fa146c0`
- 旧仕様: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- 上位正本:
  - `AGI三主体統合設計正本_v0_2.md`
  - `HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
  - `工学的AGI実装仕様書_v0_2.md`
- 下位依存仕様:
  - `HDS蒸留仕様書_ARC2_ARC3_rev2.md`
- 現状監査:
  - `ARC3_現行実装監査_2026-07-30.md`
- 是正監査:
  - `docs/audits/ARC3_HDS_DISTILLATION_FIRST_REV3_AUDIT_RESOLUTION_2026-07-31.md`
- 日付: `2026-07-31`
- 仕様状態: `OWNER_APPROVED`
- 導入状態: `INSTALLED`
- PH-R-1状態: `OWNER_APPROVED_PASS`
- 現在作業: `PH-R00_CURRENT_HEAD_REBIND`
- Active phase: `PH-R00`
- PH-R00状態: `IN_PROGRESS`
- 最上位目的: HDSで教師素材から構造データを先に蒸留・凍結し、その成果物だけを長期能力の上流入力として、未知ARC3環境を汎用自律完遂する工学的AGI Instanceを構築する

---

## 0. 戦略改定の提案結論

旧戦略は、先にAGI Runtimeの一般構造を組み、公開ゲームの軌道圧縮やonline学習によって能力を後から埋める順序だった。

rev3では順序を反転する。

```text
Ownerによる是正内容の明示承認
→ PH-R-1 Strategy Installation
→ PH-R00 Current HEAD Infrastructure Freeze
→ 教師素材
→ HDS蒸留
→ 構造データ
→ 証拠・境界・反例付き静的freeze
→ Distillation-to-AGI Bridge
→ P₀ / J_CORE_OWNER_FROZEN / J_DOMAIN_PROFILE₀ / M₀
→ AGI Runtime構築
→ online同定・記憶更新
→ locked evaluation
→ official evaluation
```

最重要不変条件:

```text
OWNER_APPROVED_REV3_CORRECTION
AND STRATEGY_INSTALLATION_COMPLETE
になるまで、
PH-R00以降を開始してはならない。

HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
になるまで、
AGI能力実装・P22方策最適化・公式提出準備を進めてはならない。
```

`OWNER_APPROVED_REV3_CORRECTION`とStrategy InstallationはPH-R-1で成立した。
PH-R00開始の対象明示Owner判断もexact PH-R-1 evidenceへbindされ、
`OWNER_AUTHORIZED_PH-R00 = ESTABLISHED`である。これはPH-R00だけを許可し、
HDS蒸留、Bridge、Runtime、外部操作を許可しない。

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

> 正解付きARC3教師素材から、状態、対象、関係、action-effect、precondition、goal、hazard、順序、遅延、probe、rollback、compositionの構造をHDSで蒸留し、証拠状態・適用範囲・反例・未閉包を明示した構造資産へ変換する。その構造資産をP₀／J_DOMAIN_PROFILE₀／M₀へ型付きでコンパイルし、Owner固定のJ Coreと合成して、未知ARC3環境で観測・仮説・probe・行動・再観測・記憶更新を自律循環する同一の工学的AGI Instanceを構築する。

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
AND RELEVANT_MEMORY_CAUSALITY
AND IRRELEVANT_MEMORY_INVARIANCE
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

### 2.4 Authority planes

規範権威と実行制御を分離する。

```text
Normative Authority:
Ownerの現在の明示指示
→ AGI三主体統合設計正本
→ HDS内部正本
→ 工学的AGI実装仕様
→ ARC3 rev3実装仕様
→ HDS蒸留仕様
→ ARC3ロードマップ
→ HDS蒸留ロードマップ

Execution Control:
Ownerの現在の明示指示
→ root AGENTS.md
→ OwnerDecisionCaptureで根拠化されたOwner承認済みPhase State
→ WorkBlockFrame
→ committed evidence
```

Execution ControlはNormative Authorityの定義・責任・安全境界を変更しない。過去のphase state、ApprovalRecord、transition、artifact-local `next_*`は履歴証拠であってcurrent selectorではない。

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

### 4.1 Artifact layer contract

蒸留artifactを三層へ分離し、後段生成物を`SourceContentManifest`へ入れない。

#### Primary Teacher Source

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

#### Derived Distillation Evidence

- deterministic derivation
- exact-fit result
- counterfactual intervention plan/result
- normalization certificate
- counterexample
- boundary record
- failure signature

Derived layerは参照したPrimary source digestとderivation implementation digestを必須とし、Primary sourceのfreeze条件にはしない。

#### Governance Artifacts

- PromotionDecision
- OwnerDecisionCapture
- ApprovalRecord
- BundleApprovalRecord
- EvidenceCommitAttestation

Governance layerは対象artifact digestへbindし、教師観測または因果証拠として加点しない。

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

### 4.4 Source-blind execution

関数引数だけでなく、role、checkout、process、mountを分離する。

```text
Replay Harness Maintainer:
  environment source access = allowed
  hypothesis generation = forbidden

Distillation Executor:
  environment source mount = forbidden
  input = observable API / frozen recording only

Distillation Auditor:
  input = access ledger / process manifest / artifact digest only
```

候補生成はsource treeを含まない別checkoutまたは隔離processで行う。process identity、checkout digest、mount allowlist、source access countを`SourceBlindExecutionRecord`へ固定する。同一主体がsource access後に候補生成した場合は`SOURCE_BLIND_NOT_ESTABLISHED`とし、promotion入力へ使わない。

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

正式な機械可読契約は`docs/strategy/contracts/HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json`とする。

`manifest.json`必須field:

```text
bundle_schema_version
bundle_id
source_content_manifest_digest
dependency_lock_digest
canonical_serialization
logical_digest
physical_package_digest
required_file_inventory
record_count_by_type
cross_reference_index_digest
coverage_profile_digest
taint_report_digest
migration_record_digest
bundle_approval_record_digest
```

bundle record type:

```text
OntologyTypeRecord
MechanismAssetRecord
ProbeObligationRecord
StructureCoverageProfile
BundleApprovalRecord
StructureBundleMigrationRecord
```

各recordは`schema_version`、stable ID、`content_digest`を持つ。HDS rev2の38 schemaを内包するrecordは`hds_schema_ref`とそのlogical digestを保持し、一対一mappingを契約fileへ固定する。

整合条件:

- canonical JSONはUTF-8、NFC、key sort、余分な空白なし、末尾LFあり
- JSONLは一record一行で`record_id`昇順
- logical digestはphysical filename、mtime、ZIP metadataを除外
- physical package digestは配布bytes全体を対象
- 全referenceはbundle内indexまたは明示dependencyに解決
- unknown file、unknown schema version、dangling reference、duplicate ID、部分bundleをfail closedで拒否
- migrationはsource/target schema、transform digest、lossless判定、rollback pathを必須化
- dependency lock不一致時は読み込まない

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
primary_class
target_projections
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

`primary_class`は一件だけ持つ。`target_projections[]`は`PProjection`、`JDomainProjection`、`MSeedProjection`、`ProbeProjection`を複数保持でき、各projectionは独立digestを持つ。同一evidence refはprojection数にかかわらずcoverageまたはscoreへ一度だけ加算する。

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
8. `AGI_BUILD_READY_PROFILE_V1`の全hard mandatory categoryが個別thresholdを満たす
9. hard mandatory categoryの`allowed_unresolved_ratio = 0`
10. unresolved recordは非mandatory categoryに限り、typed `ProbeObligationRecord`とresource boundを持つ
11. 同一evidenceのcategory間・projection間重複加点0
12. CoverageReportをOwnerが採択
13. `HDS_STRUCTURE_BUNDLE_OWNER_APPROVED`

全件SUSPENDでもpipeline処理は完了し得るが、AGI Build Readyにはならない。

機械可読profileは`docs/strategy/contracts/AGI_BUILD_READY_PROFILE_V1.json`で固定する。少なくとも次をhard mandatoryとする。

- observation projection
- entity/relation
- state variable
- action surface/payload
- precondition
- action-effect/transition
- goal/terminal
- hazard/reset
- probe/falsification

各categoryは`minimum_evidence_grade`、`minimum_independent_case_count`、`negative_pool_requirement`、`minimum_counterfactual_case_count`、`allowed_unresolved_ratio`を持つ。Owner Approvalだけでhard minimumを迂回できず、変更には仕様改訂と新しいprofile digestが必要である。

---

## 7. Distillation-to-AGI Bridge

### 7.1 目的

HDS構造資産を、Runtimeが実行・引用できる初期能力へ変換する。

```text
HDSStructureBundle
→ Bridge Compiler
→ P₀
→ J_DOMAIN_PROFILE₀
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

#### J_CORE_OWNER_FROZEN

- purpose
- value criteria
- risk ceiling
- authority boundary
- adoption authority
- global stop policy

`J_CORE_OWNER_FROZEN`は教師corpusまたはBridgeから生成しない。変更にはOwnerの対象明示指示、専用`OwnerDecisionCapture`、新しいApprovalRecordを必要とする。

#### J_DOMAIN_PROFILE₀

- domain hazard signatures
- domain-specific probe obligations
- evidence requirements
- failure checklist
- applicability rules

Runtime Jは`J_CORE_OWNER_FROZEN + J_DOMAIN_PROFILE₀`で構成し、domain profileがpurpose、risk ceiling、authority、global stopを緩和することを禁止する。

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

Bridgeは次のcardinalityを採用する。

```text
Canonical StructureRecord
  ├── PProjection
  ├── JDomainProjection
  ├── MSeedProjection
  └── ProbeProjection
```

- canonical recordは一件
- `primary_class`は一件
- `target_projections[]`は複数可
- projectionごとに独立digest
- evidence refは全projection横断で一度だけscoreへ加算
- P/J/M間の責任重複とJ Core越権をBridge auditで拒否

| 証拠状態 | P₀ | J_DOMAIN_PROFILE₀ | M₀ |
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

available actionsとpayload schemaは正当な観測である。legal action mask、payload validation、action availability changeの観測を許可する。禁止するのは、exact action tupleだけによる専用policy head選択、environment identity proxy化、固定trajectory選択である。

---

## 8. DistilledInitialStateBundle

```text
DistilledInitialStateBundle/
  manifest.json
  p_bundle/
  j_core_owner_frozen.json
  j_domain_profile_0.json
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
j_core_digest
j_domain_profile_digest
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

Mの因果性を次の二試験へ分ける。

```text
Relevant Memory Causal Witness:
  applicabilityを満たすcandidate-specific recordを
  追加・除去・反転すると、
  hypothesis / candidate / ranking / predicted effect / action
  の少なくとも一つが変わる

Irrelevant Memory Invariance:
  applicability不一致、無関係scope、stale、またはarchive recordを
  追加してもcandidateとactionが変わらない
```

任意のM差で出力変更を要求しない。変化を要求するのは`causally_eligible = true`かつcandidate-specificなcitationだけである。両試験を同じObservation、P、resource budget、random seedで対にして実行する。

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

関連M更新は未来のC/J/actionを因果的に変え、無関係M更新は変えてはならない。

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
root AGENTS.md
```

を正本とする。

### 11.1 Git evidence model

Git証拠は自己参照を避ける。

```text
Implementation Commit:
  implementation_commit
  implementation_tree

Evidence Commit:
  phase state
  Owner Review Package
  target = implementation_commit/tree

EvidenceCommitAttestation:
  evidence_commit
  evidence_tree
  target = evidence_payload_digest

Approval Commit:
  OwnerDecisionCapture
  ApprovalRecord
  target = evidence_commit + evidence_payload_digest
```

Evidence payloadは自身を含む`evidence_commit`を要求しない。ApprovalRecordも自身を含む`approval_commit`を要求しない。後続attestationまたはGit refだけが直前commitを記録する。

### 11.2 OwnerDecisionCapture

CodexはOwnerの明示判断を機械的に転記できるが、判断内容を生成できない。

```text
owner_decision_id
source_instruction_ref
source_instruction_digest
target_artifact_digest
target_evidence_commit
allowed_transition
decision
reason_codes
captured_by
capture_is_mechanical = true
owner_decision_content_digest
```

対象artifact、遷移、decisionがOwner指示から一意に得られない場合はrecordを作らず、`OWNER_DECISION_NOT_ESTABLISHED`とする。

### 11.3 OwnerStandingAuthorization

Ownerがroadmap内の必要承認を全て与え、連続実装を明示した場合は、
`OwnerStandingAuthorization`として機械転記できる。

これはunknown artifactの事前PASSではない。各phaseのrequired DoDが全てPASSし、
failed requirementが0件で、implementation/evidence commitとpayload digestが
exact bindされた後だけ、`OwnerDecisionCapture v2`を生成する。

```text
Standing Owner instruction
  ↓
OwnerStandingAuthorization
  ↓ phase DoD PASS + exact evidence binding
OwnerDecisionCapture v2
  ↓
ApprovalRecord
  ↓
next sequential phase
```

FAIL、未検証、順序違反、digest mismatchでは適用しない。external submission、
one-time locked access、credential変更、課金・公開は別の明示実行指示を必要とする。

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

各family foldを独立end-to-end branchとして再構築する。

```text
for each held_out_family:
  source split
  → fold-specific HDS distillation
  → fold-specific HDSStructureBundle
  → fold-specific Bridge
  → fold-specific DistilledInitialStateBundle
  → fold-specific RuntimeIdentity
  → held-out-family evaluation
```

各foldは`held_out_family`、`training_family_set`、source split digest、structure bundle digest、initial bundle digest、runtime identity digestを記録する。全foldについて、

```text
distinct_structure_bundle_count = fold_count
distinct_initial_bundle_count = fold_count
distinct_runtime_identity_count = fold_count
```

を要求する。機械可読契約は`docs/strategy/contracts/MECHANISM_FAMILY_CV_CONTRACT_V1.json`とする。CV結果はprocedure evidenceであり、single-artifact claimへ合算しない。

### 12.4 Locked final

- independently generated
- runtime実装者から内容隔離
- one frozen artifact
- one-time execution
- result開示後CONSUMED
- developmentへ使った時点でfinal資格喪失

独立主体:

- `LockedEvaluatorAuthority`: evaluator versionと更新を承認
- `LockedEvaluatorCustodian`: sealed inputと鍵を保管
- `OneTimeExecutionTokenIssuer`: artifact/evaluator digestへ一回限りtokenを発行
- `ConsumptionLedgerWriter`:実行、開示、development転用、`CONSUMED`を追記

Runtime実装者、Distillation Executor、Bridge実装者は上記authority/custodianと兼務しない。兼務またはrole ledger欠落時は`INDEPENDENT_LOCKED_FINAL_NOT_ESTABLISHED`とする。

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

正式IDは本節の`Claim`列に統一する。6章のprocessing stateとの対応は`docs/strategy/contracts/CLAIM_REGISTRY_REV3.json`を正本とし、次へ固定する。

```text
PIPELINE_IMPLEMENTATION_COMPLETE
  → HDS_DISTILLATION_PIPELINE_COMPLETE
CORPUS_PROCESSING_COMPLETE
  → HDS_CORPUS_PROCESSED
FROZEN_ARTIFACT_COMPLETE
  → HDS_STRUCTURE_BUNDLE_FROZEN
```

左辺はpipeline内部状態、右辺は外部claim IDであり、左辺だけでclaimを発行しない。

| Claim | 意味 | 完成扱い |
|---|---|---:|
| `INFRASTRUCTURE_BASELINE_FROZEN` | P16〜P21基盤を現行HEADへbind | しない |
| `HDS_DISTILLATION_PIPELINE_COMPLETE` | 蒸留pipeline実装 | しない |
| `HDS_CORPUS_PROCESSED` | 全教師case処理 | しない |
| `HDS_STRUCTURE_BUNDLE_FROZEN` | 構造資産freeze | しない |
| `HDS_STRUCTURE_BUNDLE_OWNER_APPROVED` | Ownerがcoverageを採択 | AGI build開始条件 |
| `DISTILLATION_TO_AGI_ABI_FROZEN` | Bridge契約freeze | しない |
| `DISTILLED_INITIAL_STATE_BUNDLE_FROZEN` | P₀/J Core/J Domain/M₀ freeze | しない |
| `DISTILLED_RUNTIME_STRUCTURAL_READY` | active runtimeがdistilled assetsのみ使用 | しない |
| `MEMORY_CAUSAL_OFFICIAL_LIKE` | relevant Mで判断が変わり、irrelevant Mで不変 | しない |
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
- `DST-010` source-blind process/checkout/mount separation
- `DST-011` AGI_BUILD_READY_PROFILE_V1 hard minimums
- `DST-012` bundle schema/cross-reference/unknown-file/partial rejection

### 14.2 Bridge

- `BRG-001` structure-to-P/J/M mapping完全
- `BRG-002` unsupported rule active化0
- `BRG-003` case identity flow 0
- `BRG-004` trajectory/answer map 0
- `BRG-005` S5 weight dependency 0
- `BRG-006` L₀ ABI PASS
- `BRG-007` initial bundle deterministic
- `BRG-008` Owner approval
- `BRG-009` one primary class + typed multi-projection
- `BRG-010` evidence duplicate scoring 0
- `BRG-011` J_CORE_OWNER_FROZEN不変

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
- `AGI-011` relevant-M causal witness
- `AGI-012` irrelevant-M invariance

### 14.4 Evaluation

- `EVAL-001` known publicをblind扱いしない
- `EVAL-002` CVをsingle artifact扱いしない
- `EVAL-003` mechanism-family holdout
- `EVAL-004` locked final one-time
- `EVAL-005` official scope分離
- `EVAL-006` fold-specific structure/initial/runtime identity
- `EVAL-007` locked evaluator authority/custodian/token/consumption separation

一件でもblocking requirementがPASS以外なら完成claimを出さない。

---

## 15. 現行repository変更方針

### 15.1 Freeze first

監査是正内容をOwnerが明示承認し、PH-R-1でStrategy Installationを完了した後に限り、現行HEADへbaselineをbindする。

```text
PRE_DISTILLATION_INFRASTRUCTURE_BASELINE
```

としてcommit/tree/package/testを固定する。

### 15.2 Active selector

現在のselector:

```text
Strategy = OWNER_APPROVED
Installation = INSTALLED
Active phase = PH-R00
Current work = PH-R00_CURRENT_HEAD_REBIND
PH-R-1 = OWNER_APPROVED_PASS
PH-R00 = IN_PROGRESS
PH-R00 Owner authorization = ESTABLISHED
DistilledInitialStateBundle = NOT_FROZEN
Runtime activation = SUSPEND
```

導入済みphase順序:

```text
PH-R-1
→ PH-R00
→ PH-D00A ... PH-D14
→ PH-B00 ... PH-B06
→ PH-A00 ... PH-A08
→ PH-E00 ... PH-E04
```

P22以降の旧selectorはhistoricalへ移す。

導入承認は次へ固定する。

```text
OwnerDecisionCapture =
sha256:58d3caa32976cf6288818e58e225228d4e0e5a1c710c44f67ee164561ea931dd

ApprovalRecord =
owner-approval-record:32de1b2446b1dfc5fdecd187a65077cbb5f1569a115aa6dbebfc08ad3b1970b8
```

この導入承認の範囲は監査是正採択とPH-R-1開始だけである。PH-R00 entryは別のOwnerDecisionCapture／ApprovalRecordへ固定され、将来artifactの事前採択を含まない。

監査前のPH-R00〜PH-D03A state、transition、ApprovalRecord、review packageは削除しないが、`HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE`とする。是正後のphase passまたはactivation根拠へ再利用しない。

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

### 15.5 Deterministic distribution package

監査・承認へ渡すZIPは、全entry名をASCII-safeにし、固定timestamp、
stable sort、固定compressionで再構築可能にする。root entryとして
`MANIFEST.json`と`SHA256SUMS`を必須化し、前者はsource path、archive
path、size、SHA-256、logical digestを、後者は全payloadのbyte digestを
保持する。logical digestとphysical package digestを混同せず、どちらか
一方でも不一致なら承認対象として受理しない。

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

## 17. Owner承認後の固定式

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
→ P₀ + J_CORE_OWNER_FROZEN + J_DOMAIN_PROFILE₀ + M₀ + ProbeCatalog
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
+ Relevant-M Causal Witness
+ Irrelevant-M Invariance
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
