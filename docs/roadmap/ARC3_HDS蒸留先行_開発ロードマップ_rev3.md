# ARC3 HDS蒸留先行 開発ロードマップ rev3

- Roadmap ID: `ARC3_HDS_DISTILLATION_FIRST_ROADMAP_REV3`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 基準commit: `6858a316241b101bb5a44fd1dd7854dc0fa146c0`
- 上位仕様: `ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md`
- Codex運用正本: `ARC3_AGENTS_Codex開発運用契約_rev3.md`
- HDS蒸留正本:
  - `HDS蒸留仕様書_ARC2_ARC3_rev2.md`
  - `HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`
- 日付: `2026-07-30`
- 状態: `ACTIVE_STRATEGY_SELECTOR`
- 原則: HDS構造データをOwner承認付きでfreezeするまで、AGI能力実装へ進まない

---

## 0. 全体依存順序

```text
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

## PH-R00 — Current HEAD Rebind / Infrastructure Freeze

### 目的

現行P16〜P21を、能力完成claimではなく、蒸留後に再利用する基盤候補としてcurrent HEADへbindする。

### 実施

1. current HEAD／treeを固定
2. full unit／integration／package／notebook regression
3. phase stateをcommit/treeへ再生成
4. current P22、S5、compiled policyをquarantine
5. active selectorをrev3へ変更
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

Codexは`OWNER_APPROVED_PASS`を設定しない。

---

# Track D — HDS Distillation First

Track Dは、`HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`のARC3経路を正本として実行する。

`PH-D04`はARC2専用であり、ARC3 Trackでは`NOT_APPLICABLE`とする。ARC2蒸留は別Trackとして扱い、ARC3の`PH-D05`開始を阻害しない。

## PH-D00A — HDS Dependency / Authority Freeze

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

## PH-D01A/B — Source Inventory / Manifest Freeze

### 目的

raw teacher evidence、trajectory、environment、wheel、seed、splitを固定する。

### rev3追加

- source policy weightsは教師素材に数えない
- raw trajectoryとS5 corpusの対応関係をprovenanceとして記録
- source codeはreplay harnessだけが読める
- public 25はDISTILLATION_SOURCEへ分類

### Exit

`ARC3_TEACHER_SOURCE_FROZEN`

---

## PH-D02A/B/C — Canonical Schema / Typed Causal IR

### 目的

構造データの型、digest、IR、interpreterを先に閉じる。

### 必須カテゴリ

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

## PH-D03A/B — Golden / Sealed Audit Corpus

### 目的

実装適合試験と、期待値変更不能な監査入力を分離する。

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

## PH-D07A/B — Exact Fit / Counterfactual

### 目的

観測適合と因果支持を分離する。

### Exit

```text
EXTENSIONAL_FIT_ACCOUNTED
COUNTERFACTUAL_COVERAGE_REPORTED
```

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

## PH-D09〜D11 — Normalization / Commonality / Boundary

### 目的

lossless normalizationと一般化を分離し、横断共通項、near-miss、negative、counterexampleを抽出する。

### Exit

```text
CANONICAL_STRUCTURE_GRAPH_COMPLETE
BOUNDARY_AND_COUNTEREXAMPLE_AUDIT_COMPLETE
```

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
ClaimLedger
OpenTermLedger
TaintReport
FrozenArtifactManifest
OwnerApprovalRecord
```

### Gate

```text
HDS_STRUCTURE_BUNDLE_FROZEN
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

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

### Exit

`STRUCTURE_BUNDLE_INTAKE_PASS`

---

## PH-B01 — Runtime Asset Eligibility Classification

### 目的

各構造recordをP₀/J₀/M₀/ProbeCatalogへ分類する。

### 分類規則

```text
P_ELIGIBLE
J_ELIGIBLE
M_ACTIVE_ELIGIBLE
M_PROBATION_ONLY
PROBE_ONLY
ARCHIVE_ONLY
REJECTED
```

### DoD

- 全recordが一分類
- unsupported active化0
- Owner承認なしP_ELIGIBLE 0

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

## PH-B03 — Compile P₀ / J₀ / M₀ / ProbeCatalog

### 目的

初期AGI能力bundleを生成する。

### P₀

- representation
- state
- transition
- goal/hazard
- composition
- probe/rollback

### J₀

- HDS Gate
- evidence threshold
- hazard veto
- stop/rollback
- failure checklist

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
- memory citation changes candidate
- deterministic rebuild

### Exit

`DISTILLED_INITIAL_STATE_STRUCTURAL_PASS`

---

## PH-B06 — Owner Approval / Initial Bundle Freeze

### 目的

P₀/J₀/M₀/ProbeCatalogをOwnerが採否し、初期bundleをfreezeする。

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

Owner承認なしにTrack Aへ進まない。

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
+ different M citation
→ different model/candidate/probe
```

### Exit

`STRUCTURE_GUIDED_C_PASS`

---

## PH-A02 — HDS Judgement Subject J₀

### 目的

蒸留済みboundary/failure/probe資産をHDS Gateへ接続する。

### 必須

- exact fitを真因扱いしない
- evidence state別operation
- hazard veto
- probe/execute分離
- unresolved SUSPEND
- Owner-defined purpose boundary

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

Runtime traceとM_devを次版P/J₀/M₀へ再コンパイルする。

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

一つのartifactへCode/L₀/P/J₀/M₀/Adapter/Resource Contractを固定する。

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
9. artifactをcommitへbind
10. self-audit
11. Owner Review Package生成
12. 停止

Codexは次phaseへ自動進行しない。

---

# 最初のWork Block

```text
Phase:
PH-R00

目的:
現行HEADをpre-distillation infrastructure baselineとして再bindし、
S5/P22方策をactive completion pathから隔離する。

読む順序:
1. ユーザーの現在指示
2. ARC3_AGENTS_Codex開発運用契約_rev3.md
3. ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md
4. ARC3_HDS蒸留先行_開発ロードマップ_rev3.md
5. ARC3_現行実装監査_2026-07-30.md
6. HDS蒸留仕様書_ARC2_ARC3_rev2.md
7. HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md
8. 現行AGENTS.md
9. current phase state

実施:
- HEAD/tree固定
- phase evidence rebind
- full regression
- asset classification
- production import boundary
- active selector変更
- PH-R00 Owner Review Package

禁止:
- HDS蒸留開始
- AGI能力実装
- P22改善
- official提出
- Rule promotion
- 次phase着手

終了:
OWNER_REVIEW_REQUIREDで停止。
```

---

# 最終固定結論

rev3では、

```text
構造データを先に作る
→ 構造データをOwnerが採択する
→ 構造データからAGI初期状態を作る
→ その後にAGI Runtimeを構築する
```

を不可逆なphase dependencyとして固定する。
