# ARC3 HDS蒸留先行 開発ロードマップ rev3

- Roadmap ID: `ARC3_HDS_DISTILLATION_FIRST_ROADMAP_REV3`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 基準commit: `6858a316241b101bb5a44fd1dd7854dc0fa146c0`
- 上位仕様: `ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md`
- Codex運用正本: root `AGENTS.md`
- HDS蒸留正本:
  - `HDS蒸留仕様書_ARC2_ARC3_rev2.md`
  - `HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`
- 日付: `2026-07-31`
- 状態: `OWNER_APPROVED`
- 導入状態: `INSTALLED`
- PH-R-1状態: `OWNER_APPROVED_PASS`
- 現在作業: `PH-D00A_HDS_DEPENDENCY_AUTHORITY_REBIND`
- Active phase: `PH-D00A`
- PH-D00A状態: `IN_PROGRESS`
- PH-R00状態: `OWNER_APPROVED_PASS`
- 原則: HDS構造データをOwner承認付きでfreezeするまで、AGI能力実装へ進まない

---

## 0. 全体依存順序

```text
REV3-DOC-FIX  Audit Correction
  ↓ Owner explicit approval
PH-R-1  Strategy Installation
  ↓
PH-R00  Strategy Rebaseline / Infrastructure Freeze
  ↓
PH-D00A ... PH-D14  HDS Distillation
  ↓
PH-B00 ... PH-B06   Distillation-to-AGI Bridge
  ↓
PH-A00 ... PH-A08   Distilled AGI Construction
  ↓
PH-E00 ... PH-E04   Evaluation / Competition / Official
```

Hard Gate:

```text
OWNER_APPROVED_REV3_CORRECTION
AND PH-R-1 STRATEGY_INSTALLATION_COMPLETE
```

が成立するまで、`PH-R00`以降を開始しない。

```text
PH-D14
AND HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

が成立するまで、`PH-B00`以降を開始しない。

```text
PH-B06
AND DISTILLED_INITIAL_STATE_BUNDLE_FROZEN
```

が成立するまで、`PH-A00`以降を開始しない。

---

# Track R — Strategy Rebaseline

## REV3-DOC-FIX — Audit Correction

### 目的

F-01〜F-17を文書・機械可読契約・配布artifactで是正する。Phase実装ではなく、Strategy Installationの前提を閉じる。

### 許可

- authority、Git evidence、artifact layer、M、Bridge、CV、coverage、schema、J、role、Owner capture、claim、evaluator、action surface、package契約の修正
- 監査前証拠のhistorical/non-authoritative分類
- deterministic package生成と文書回帰

### 禁止

- PH-R-1またはPH-R00開始
- HDS蒸留、Bridge、Runtime実装
- Rule/Phase/Bundle自己承認
- locked final、official、Kaggle

### Exit

```text
CODEX_IMPLEMENTATION_COMPLETE
CODEX_SELF_AUDIT_PASS
OWNER_REVIEW_REQUIRED
```

監査是正はOwnerが対象明示承認し、PH-R-1でstrategyを導入した。PH-R-1はexact evidenceへbindされたOwner承認で閉じ、PH-R00の対象明示Owner判断も成立している。

---

## PH-R-1 — Strategy Installation

### Current status

```text
OWNER_APPROVED_PASS
PH-R00_OWNER_APPROVED_PASS
PH-D00A_IN_PROGRESS
```

### Entry

- `OWNER_APPROVED_REV3_CORRECTION`
- `OwnerDecisionCapture`が是正artifact digest、evidence commit、許可遷移を一意に指定
- corrected package manifest/checksum PASS

### 目的

是正済みrev3をroot `AGENTS.md`、current selector、phase state schemaへ導入する。

### 実施

1. normative authorityとexecution controlを固定
2. corrected contract digestをcurrent authority manifestへ固定
3. 監査前phase evidenceを`HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE`へ分類
4. active phaseを未設定のままinstallation evidenceを生成
5. Owner Review PackageをEvidence Commitへ固定

### Exit

```text
STRATEGY_INSTALLATION_COMPLETE
OWNER_APPROVED_PASS
PH-R00_AUTHORIZED
```

PH-R00開始判断は、PH-R-1のexact evidence、OwnerDecisionCapture、ApprovalRecordへbindされて成立した。

## PH-R00 — Current HEAD Rebind / Infrastructure Freeze

### Current status

```text
OWNER_APPROVED_PASS
PH-D00A_IN_PROGRESS
```

### 目的

現行P16〜P21を、能力完成claimではなく、蒸留後に再利用する基盤候補としてcurrent HEADへbindする。

### 実施

1. current HEAD／treeを固定
2. full unit／integration／package／notebook regression
3. Implementation CommitとEvidence Commitを分離し、phase stateを`implementation_commit/tree`へbind
4. current P22、S5、compiled policyをquarantine
5. PH-R-1で導入済みselectorとauthority digestを検証
6. production import boundaryを追加
7. current auditをbaseline evidenceへ固定

### 成果物

```text
control/rev3/R00_PHASE_STATE.json
docs/strategy/REV3_STRATEGY_REBASELINE.md
docs/strategy/ASSET_CLASSIFICATION_REV3.json
docs/strategy/PRODUCTION_IMPORT_BOUNDARY_REV3.md
analysis/rev3/pre_distillation_infrastructure_baseline.json
```

### Preserve

- CognitiveSession
- Authority/Control/Semantic state
- Evidence Binding
- Atomic M
- typed causal M
- P-IR/L₀
- PBundle
- role registry
- version lineage

### Quarantine

- S5 runtime
- current compiled MLP
- current P22 artifacts
- current CV artifacts
- learned reset compatibility
- old official selector

### DoD

```text
current_head_bound = true
uncommitted_phase_evidence_count = 0
active_runtime_capability_claim = NOT_ESTABLISHED
quarantined_s5_dependency_in_production = 0
next_phase = PH-D00A
owner_approval = required
```

CodexはPH-R00の全DoD、required validation、failed requirement count 0、exact evidence bindを満たした場合だけ、standing authorizationを機械的に適用してPH-D00A entryを記録する。失敗または未証明gateでは停止する。

---

# Track D — HDS Distillation First

Track Dは、`HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`のARC3経路を正本として実行する。

`PH-D04`はARC2専用であり、ARC3 Trackでは`NOT_APPLICABLE`とする。ARC2蒸留は別Trackとして扱い、ARC3の`PH-D05`開始を阻害しない。

## PH-D00A — HDS Dependency / Authority Freeze

### Current status

```text
IN_PROGRESS
WORK_CLASS = PH-D00A_HDS_DEPENDENCY_AUTHORITY_REBIND
```

### 目的

HDS正本、権威順序、蒸留Scopeをdigestで固定する。

### 追加rev3条件

- ARC3 first
- AGI Runtimeへの接続禁止
- current compiled policyを入力禁止
- Ownerを唯一のpromotion authorityへ固定

### Exit

`DEPENDENCY_LOCK_PASS`

---

## PH-D00B — Distillation Repository Bootstrap

### 目的

蒸留をruntimeから分離したnamespace／repositoryとして構築する。

### 必須境界

```text
distillation/
bridge/       # この時点では空
runtime/      # read-only reference
```

### Exit

`DISTILLATION_SCOPE_GUARD_PASS`

---

## PH-D01A — Primary Source Inventory

### 目的

raw teacher evidence、trajectory、environment、wheel、seed、splitを列挙し、Primary Teacher Sourceだけをinventory化する。

### 必須

- source policy weightsは教師素材に数えない
- raw trajectoryとS5 corpusの対応関係をprovenanceとして記録
- public 25は`DISTILLATION_SOURCE`へ分類
- Derived Distillation EvidenceとGovernance Artifactsをsource inventoryへ入れない

### Exit

`PH_D01A_PRIMARY_SOURCE_INVENTORY_PASS`

---

## PH-D01B — Source Content / Acquisition / Run Manifest Freeze

### 目的

PH-D01AのPrimary Teacher Sourceについてcontent、acquisition、environment、run manifestをdigest固定する。

### 必須

- source codeを読めるのは`REPLAY_HARNESS_MAINTAINER`だけ
- `DISTILLATION_EXECUTOR`はsource treeをmountしない
- process identity、checkout digest、mount allowlist、access ledgerを固定
- SourceContentManifestへ後段生成物を入れない

### Exit

`ARC3_TEACHER_SOURCE_FROZEN`

---

## PH-D02A — Canonical Serialization / Digest Contract

### 目的

canonical JSON/JSONL、logical/physical digest、reference ID、versioningを固定する。

### Exit

`PH_D02A_CANONICAL_CONTRACT_PASS`

---

## PH-D02B — Schema Set / Bundle Contract

### 目的

HDS rev2の38 schemaと、`HDSStructureBundleManifest`、`OntologyTypeRecord`、`MechanismAssetRecord`、`ProbeObligationRecord`、`StructureCoverageProfile`、`BundleApprovalRecord`、`StructureBundleMigrationRecord`を固定する。

### 必須

- cross-file reference integrity
- unknown file rejection
- partial bundle rejection
- dependency lock
- one-to-one HDS schema mapping

### Exit

`PH_D02B_SCHEMA_SET_PASS`

---

## PH-D02C — Typed Causal IR / Interpreter / Verifier ABI

### 目的

次の構造カテゴリを実行可能IRとして固定し、offline interpreter/verifierで検査する。

- representation
- entity/relation
- state
- precondition
- effect/transition/delay
- goal/hazard
- order/composition
- probe
- rollback/reset
- boundary/failure/unresolved

### Exit

`DISTILLATION_IR_EXECUTABLE`

---

## PH-D03A — Golden Conformance Corpus Candidate

### 目的

実装適合用Golden candidateを生成し、schema、IR、interpreter、verifierへbindする。一般性証拠またはOwner承認済み期待値とは扱わない。

### Exit

```text
GOLDEN_CONFORMANCE_CANDIDATE_READY
OWNER_REVIEW_REQUIRED
```

---

## PH-D03B — Sealed Audit Corpus Freeze

### Entry

Golden expectationを対象明示した`OwnerDecisionCapture`とApprovalRecordを要求する。

### 目的

承認済み期待値を変更不能なsealed audit inputへfreezeし、Golden candidateと分離する。

### Exit

`DISTILLATION_CONFORMANCE_CORPUS_FROZEN`

---

## PH-D05 — ARC3 Teacher Trajectory Normalization

### 目的

全教師軌道をcanonical action/state/effect recordへ変換する。

### DoD追加

- ACTION1〜ACTION7/RESET
- ACTION6 x/y
- before/after
- available actions
- terminal/progress
- seed
- environment digest
- replay x3
- source access boundary

### Exit

`ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE`

---

## PH-D06 — Hypothesis Candidate Generation

### 目的

各教師caseから複数の実行可能機構候補を生成する。

### Codex権限

許可:

- deterministic templates
- bounded enumeration
- frozen LLM capture
- alternative/counter/null model生成

禁止:

- candidate自動採択
- source codeから答えを抜く
- natural languageだけでRule確定
- S5 logitsを因果証拠に使う

### Exit

`MULTI_HYPOTHESIS_CORPUS_COMPLETE`

---

## PH-D07A — Exact Fit Accounting

### 目的

各HypothesisIRの観測適合を計測し、exact fitを因果支持から分離する。

### Exit

`EXTENSIONAL_FIT_ACCOUNTED`

---

## PH-D07B — Counterfactual Intervention

### Entry

PH-D07Aのfit artifactをDerived Distillation Evidenceとして受理し、Primary Source manifestを変更しない。

### 目的

競合仮説を識別するinterventionを実行し、支持、反証、未識別を記録する。

### Exit

`COUNTERFACTUAL_COVERAGE_REPORTED`

---

## PH-D08 — Per-Case HDS Decision

### 目的

各caseをF/Md/Cm/Uへ射影する。

### 必須

- selected/held/rejected
- assertion/operation/adoption/evidence/closure/update
- SUSPEND保持
- FailureSignature
- open terms

### Exit

`HDS_CASE_RECORDS_COMPLETE`

---

## PH-D09 — Lossless Normalization

### 目的

意味を変更せず表現差だけを正規化し、NormalizationCertificateを生成する。

### Exit

`LOSSLESS_NORMALIZATION_COMPLETE`

---

## PH-D10 — Cross-Case Commonality

### 目的

正規化済みrecordから横断共通項とRule family候補を抽出する。一般化候補を自動昇格しない。

### Exit

`CANONICAL_STRUCTURE_GRAPH_COMPLETE`

---

## PH-D11 — Boundary / Near-Miss / Counterexample Audit

### 目的

適用境界、near-miss、negative、counterexample、failure signatureを抽出し、D10候補を反証監査する。

### Exit

`BOUNDARY_AND_COUNTEREXAMPLE_AUDIT_COMPLETE`

---

## PH-D12 — Evidence-Graded Promotion

### 目的

RuleAtom/RuleFamilyを証拠強度別にOwner採否へ送る。

### Codex出力

```text
PROPOSED
PROBATION
REJECTED
SUSPEND
OWNER_REVIEW_REQUIRED
```

Codex禁止:

```text
ACTIVE
PROMOTED_CORPUS_SCOPED
OWNER_APPROVED
```

をOwner承認なしに設定すること。

Owner採否は、対象Rule/RuleFamily digestと許可遷移を特定した`OwnerDecisionCapture`をCodexが機械転記した場合だけApprovalRecordへ変換する。Codexは判断内容を生成しない。

### Exit

`OWNER_APPROVED_PROMOTED_RULESET_AVAILABLE`

---

## PH-D13 — Frozen-Input Rebuild x3

### 目的

live LLM／live human decisionを除外して成果物を再構築する。

### Exit

`DISTILLATION_DETERMINISM_PASS`

---

## PH-D14 — Coverage / Structure Bundle Freeze

### 目的

HDSStructureBundleをfreezeし、AGI Build Readyを判定する。

### 必須成果物

```text
HDSStructureBundle
CoverageReport
AGI_BUILD_READY_PROFILE_V1 evaluation
ClaimLedger
OpenTermLedger
TaintReport
FrozenArtifactManifest
OwnerApprovalRecord
```

### Gate

```text
HDS_STRUCTURE_BUNDLE_FROZEN
HDS_STRUCTURE_BUNDLE_SCHEMA_PASS
AGI_BUILD_READY_PROFILE_V1_PASS
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

Owner Approvalだけでhard mandatory categoryのminimum evidence、independent case、negative pool、counterfactual coverage、allowed unresolved ratioを迂回しない。

### 失敗時

- AGI buildへ進まない
- coverage不足categoryをD06〜D12へ戻す
- locked finalは使わない
- Ruleの証拠基準を弱めない

---

# Track B — Distillation-to-AGI Bridge

## PH-B00 — Structure Bundle Intake Audit

### 目的

Owner承認済みHDSStructureBundleだけをBridge入力として受理する。

### 試験

- digest
- schema
- approval
- coverage
- taint
- unresolved category accounting
- source identity隔離
- unknown file rejection
- partial bundle rejection
- cross-reference integrity
- migration/dependency lock

### Exit

`STRUCTURE_BUNDLE_INTAKE_PASS`

---

## PH-B01 — Runtime Asset Eligibility Classification

### 目的

各Canonical StructureRecordへ一つのprimary classと、0件以上のtyped projectionを割り当てる。

### 分類規則

```text
primary_class:
  REPRESENTATION
  MECHANISM
  BOUNDARY
  HAZARD
  FAILURE
  UNRESOLVED
  ARCHIVE

target_projections[]:
  PProjection
  JDomainProjection
  MSeedProjection
  ProbeProjection
```

### DoD

- 全recordが一つの`primary_class`
- `target_projections[]`は複数可、各projectionに独立digest
- 同一evidence refの重複加点0
- P/J/M責任重複0
- unsupported active化0
- Owner承認なしPProjection active化0

### Exit

`RUNTIME_ASSET_ELIGIBILITY_CLOSED`

---

## PH-B02 — Distillation-to-AGI ABI

### 目的

HDS Causal IRからP-IR、J config、M0 recordへの型付き変換契約を固定する。

### 新規成果物

```text
docs/bridge/DISTILLATION_TO_AGI_ABI_V1.md
bridge/type_mapping.json
bridge/operator_mapping.json
bridge/evidence_mapping.json
bridge/failure_mapping.json
bridge/probe_mapping.json
```

### 必須試験

- type-preserving
- unknown mechanism reject
- scope preservation
- evidence state preservation
- exclusion preservation
- falsifier preservation
- no identity field
- no trajectory field

### Exit

`DISTILLATION_TO_AGI_ABI_FROZEN`

---

## PH-B03 — Compile P₀ / J Domain Profile₀ / M₀ / ProbeCatalog

### 目的

初期AGI能力bundleを生成する。

### P₀

- representation
- state
- transition
- goal/hazard
- composition
- probe/rollback

### J_CORE_OWNER_FROZEN

- purpose/value/risk/authority/adoption/global stop
- Bridgeによる変更禁止

### J_DOMAIN_PROFILE₀

- domain hazard signatures
- domain-specific probe obligations
- evidence requirements
- failure checklist
- applicability rules

### M₀

- active/probation/unresolved/archive

### Exit

`DISTILLED_INITIAL_STATE_CANDIDATE`

---

## PH-B04 — Non-Replay / Identity / S5 Dependency Audit

### 目的

初期bundleが教師軌道再生器ではないことを監査する。

### 必須試験

- game/task/level ID scan
- full state digest routing
- fixed sequence detection
- coordinate table detection
- exact action-surface head routing
- S5 weights dependency
- teacher package import
- source code dependency
- game order permutation

legal action mask、payload validation、action availability changeの観測は許可する。禁止するのはaction tupleだけによるpolicy head選択、identity proxy化、固定trajectory選択である。

### Exit

```text
IDENTITY_LEAK_COUNT = 0
TRAJECTORY_REPLAY_FINDING_COUNT = 0
S5_RUNTIME_DEPENDENCY_COUNT = 0
```

---

## PH-B05 — Isolated Structure Execution

### 目的

Bridge成果物がfixed L₀上で実行でき、構造的に異なる入力へ適用できることを確認する。

### 試験

- same L₀ different P
- representation changes by P
- rule scope
- unresolved→probe
- hazard→veto
- counter-hypothesis
- relevant candidate-specific Mの追加・除去・反転で判断が変わる
- irrelevant/stale/out-of-scope M追加でcandidate/actionが変わらない
- deterministic rebuild

### Exit

`DISTILLED_INITIAL_STATE_STRUCTURAL_PASS`

---

## PH-B06 — Owner Approval / Initial Bundle Freeze

### 目的

P₀/J Core/J Domain Profile₀/M₀/ProbeCatalogをOwnerが採否し、初期bundleをfreezeする。

### Codex状態

```text
CODEX_IMPLEMENTATION_COMPLETE
CODEX_SELF_AUDIT_PASS
OWNER_REVIEW_REQUIRED
```

### Owner状態

```text
OWNER_APPROVED_PASS
DISTILLED_INITIAL_STATE_BUNDLE_FROZEN
```

Owner承認は対象bundle digestと許可遷移を特定した`OwnerDecisionCapture`からのみ記録する。Codexはdecisionを生成しない。Owner承認なしにTrack Aへ進まない。

---

# Track A — Distilled AGI Construction

## PH-A00 — Runtime Substrate Rebase

### 目的

P16〜P21基盤をcurrent distilled bundleへ接続し、historical P22 policyをproduction pathから除去する。

### 実施

- active runtime一件
- distilled bundle loader
- S5/compiled policy import禁止
- RuntimeIdentity更新
- session/memory/P-IR rebind
- full regression

### Exit

`DISTILLED_RUNTIME_BOOTSTRAP_PASS`

---

## PH-A01 — Structure-Guided Compute Subject C

### 目的

CがP₀とMを引用して、state、mechanism、counter-hypothesis、candidate、probeを生成する。

### 必須因果試験

```text
same observation
+ causally eligible candidate-specific Mを追加・除去・反転
→ model/candidate/ranking/actionの少なくとも一つが変化

same observation
+ irrelevant/stale/out-of-scope Mを追加
→ candidate/action不変
```

### Exit

`STRUCTURE_GUIDED_C_PASS`

---

## PH-A02 — HDS Judgement Subject J

### 目的

Owner固定`J_CORE_OWNER_FROZEN`と蒸留済み`J_DOMAIN_PROFILE₀`を合成し、boundary/failure/probe資産をHDS Gateへ接続する。

### 必須

- exact fitを真因扱いしない
- evidence state別operation
- hazard veto
- probe/execute分離
- unresolved SUSPEND
- Owner-defined purpose boundary
- domain profileによるpurpose/risk/authority/global stop変更0

### Exit

`DISTILLED_HDS_J_PASS`

---

## PH-A03 — Causal M / Online Identification

### 目的

未知環境内でMが仮説支持・反証・適用範囲を更新し、未来行動を変える。

### 必須

- active/probation/archive
- delayed effect
- contradiction
- negative transfer
- rollback
- causal witness

### Exit

`MEMORY_CAUSAL_OFFICIAL_LIKE`

---

## PH-A04 — Autonomous Closed Loop

### 目的

外部逐次指示なしで、

```text
observe
→ frame
→ hypothesize
→ probe/act
→ reobserve
→ attribute
→ update M
→ next question
```

を継続する。

### Exit

`AUTONOMOUS_CLOSED_LOOP_PASS`

---

## PH-A05 — Cross-Level / Cross-Game Transfer

### 目的

scorecard-scoped Mを安全に再利用する。

### 必須

- episode overlay
- validated consolidation
- failure rollback
- irrelevant prior invariance
- game order permutation
- cross-game benefit witness
- negative transfer invalidation

### Exit

`SAFE_SCORECARD_TRANSFER_PASS`

---

## PH-A06 — Development Version Learning

### 目的

Runtime traceとM_devを次版P/J Domain Profile₀/M₀へ再コンパイルする。J Coreは再コンパイルしない。

### 制約

- DEVELOPMENT_TRAINのみ
- candidate isolation
- validation
- Owner promotion
- rejected candidate rollback
- locked final access 0

### Exit

`GOVERNED_VERSION_LEARNING_PASS`

---

## PH-A07 — Self-Contained Runtime Artifact

### 目的

一つのartifactへCode/L₀/P/J Core/J Domain Profile₀/M₀/Adapter/Resource Contractを固定する。

### 必須

- exact digest
- restart reproduction
- no teacher source
- no S5 dependency
- no runtime mutation
- deterministic package

### Exit

`DISTILLED_SINGLE_RUNTIME_ARTIFACT_FROZEN`

---

## PH-A08 — Internal AGI Conformance Audit

### 目的

Track A全requirementを独立に再監査する。

### 判定

```text
DISTILLED_RUNTIME_STRUCTURAL_READY
GENERIC_COMPLETION_NOT_YET_CLAIMED
```

Track Eへ進む。

---

# Track E — Evaluation and Official

## PH-E00 — Known Public Diagnostic Regression

### 目的

既知25ゲームを、能力証明ではなくdiagnosticとして実行する。

### 記録

- completed game/level
- mechanism coverage
- unresolved categories
- probe/action count
- memory causal witness
- failures
- no fallback
- identity leak

### Claim

`KNOWN_PUBLIC_REGRESSION`のみ。

---

## PH-E01 — Mechanism-Family Holdout / CV Procedure

### 目的

game foldだけでなく機構族holdoutを実行する。

### Holdout family

- action-effect
- goal
- hazard/reset
- delay/order
- pointer payload
- composition
- partial observation

### fold別必須経路

```text
source split
→ fold-specific HDS distillation
→ fold-specific HDSStructureBundle
→ fold-specific Bridge
→ fold-specific DistilledInitialStateBundle
→ fold-specific RuntimeIdentity
→ held-out-family evaluation
```

### 必須記録

- `held_out_family`
- `training_family_set`
- source split digest
- structure bundle digest
- initial bundle digest
- runtime identity digest
- `distinct_structure_bundle_count = fold_count`
- `distinct_initial_bundle_count = fold_count`
- `distinct_runtime_identity_count = fold_count`

### Claim

`CV_PROCEDURE_EVIDENCE`のみ。

### Exit

failureを隠さず、development loopへ戻す。  
single artifact completionとは呼ばない。

---

## PH-E02 — Independently Locked Single-Artifact Final

### 目的

一つのfrozen artifactを、独立locked evaluatorで一回だけ評価する。

### Gate

- evaluator digest
- one-time token
- artifact digest
- no development access
- no live Codex intervention
- no live human correction
- `LockedEvaluatorAuthority`とRuntime実装者の分離
- `LockedEvaluatorCustodian`とdevelopment roleの分離
- `OneTimeExecutionTokenIssuer`
- append-only `ConsumptionLedger`

### Exit

`SEALED_SINGLE_ARTIFACT_COMPLETE`

---

## PH-E03 — Competition Session / Packaging

### 目的

公式lifecycle、resource、package、scorecard Mを成立させる。

### 必須

- one scorecard/one session
- one make/environment
- idle timeout
- graceful stop
- package import closure
- output > 0
- exact artifact
- public/private scope handling

### Exit

`COMPETITION_READY`

---

## PH-E04 — Official Observation / Completion

### 順序

```text
OFFICIAL_RUN_ACCEPTED
→ OFFICIAL_PUBLIC_COMPLETE
→ OFFICIAL_PRIVATE_COMPLETE
→ OFFICIAL_FULL_COMPLETE
```

### 未完時

- scalar scoreだけで層帰属しない
- trace witnessがある場合のみ層へ帰属
- official resultをdevelopmentへ使うなら評価roleをCONSUMEDへ変更
- new versionは再度E02から

---

# Phase State Model

Codexが設定可能:

```text
NOT_STARTED
IN_PROGRESS
CODEX_IMPLEMENTATION_COMPLETE
CODEX_SELF_AUDIT_PASS
CODEX_REWORK_REQUIRED
OWNER_REVIEW_REQUIRED
SUSPEND
```

Ownerだけが設定可能:

```text
OWNER_APPROVED_PASS
OWNER_APPROVED_REWORK
OWNER_REJECTED
```

`PASS`単独を使用しない。

Owner状態の記録には`OwnerDecisionCapture`を必須とする。CodexはOwnerの対象明示判断を機械転記できるが、decisionまたは遷移を生成しない。

Ownerが全必要承認と連続進行を明示した場合は、OwnerStandingAuthorizationを
Approval Commitへ固定できる。各phaseのDoD PASS後、exact evidence digestへ
`OwnerDecisionCapture v2`を機械bindした場合だけ次のsequential phaseへ進む。
FAIL、未検証、順序違反では適用しない。不可逆な外部操作は対象外である。

Git evidence:

```text
Implementation Commit
  code/test/doc
  ↓
Evidence Commit
  phase state/review package
  target = implementation_commit/tree
  ↓
EvidenceCommitAttestation
  evidence_commit/tree + evidence_payload_digest
  ↓
Approval Commit
  OwnerDecisionCapture/ApprovalRecord
  target = evidence commit/digest
```

各commit payloadは自身のcommit/tree hashを要求しない。

---

# Codex Work Block規則

1. 一Work Blockは一phaseまたは一blocking failure修正だけ
2. base commit/treeを最初に固定
3. read orderを実行
4. FrameSpecを作成
5. 許可inputだけを開く
6. 最小sliceを実装
7. required tests
8. full regressionが必要なら実行
9. Implementation Commitを作成
10. `implementation_commit/tree`へphase stateとartifactをbind
11. self-auditとOwner Review Packageを生成
12. Evidence Commitを作成
13. 後続attestationへ`evidence_commit/tree`を記録
14. DoD PASSとfailed requirement count 0を証明し、Evidence Commitへbind
15. standing authorizationが適用可能な場合だけ、exact evidenceへApproval Commitを作成して次phaseへ進む

Codexは未証明phaseを承認しない。外部不可逆操作はstanding authorizationで実行しない。

---

# 直近のWork Blockと現在停止点

```text
Phase:
PH-D00A

目的:
HDS正本、権威順序、source-blind role、蒸留scopeをcurrent HEADへ
digest bindし、監査前PH-D00A成果をcurrent completion証拠へ再利用しない。

読む順序:
1. ユーザーの現在指示
2. PH-R00 EvidenceCommitAttestation / OwnerDecisionCapture / ApprovalRecord
3. PH-D00A WorkBlockFrame
4. root AGENTS.md
5. current authority manifest / selector / schemas
6. rev3仕様 / roadmap / INDEX
7. AGI/HDS上位正本

実施:
- HDS dependency inventoryとauthority lockのcurrent-head rebind
- source-blind roleとOwner-only promotion boundary
- dependency schema／auditor／manifest／report／Open Term Ledger
- 監査前PH-D00A control artifactのhistorical namespace移送
- deterministic report rebuildとfull regression
- Implementation / Evidence / Attestation分離

禁止:
- ARC task payload／teacher trajectoryアクセス
- HDS仮説生成／蒸留実行
- AGI能力実装
- P22改善
- official提出
- Rule/Phase/Bundle承認

終了:
DoD PASSとexact evidence bind後だけstanding authorizationをPH-D00B entryへ適用する。
```

PH-D00A evidence targetと許可遷移をexact bindできた場合だけ、次Work Blockを`PH-D00B`とする。

---

# Owner承認後も維持する固定依存

rev3では、

```text
構造データを先に作る
→ 構造データをOwnerが採択する
→ 構造データからAGI初期状態を作る
→ その後にAGI Runtimeを構築する
```

を不可逆なphase dependencyとして固定する。
