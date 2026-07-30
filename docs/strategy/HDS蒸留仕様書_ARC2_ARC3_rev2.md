# HDS蒸留仕様書 ARC2／ARC3 rev2

**副題：正解拘束・介入監査付きの実行可能機構蒸留系**

| 項目 | 内容 |
|---|---|
| 著者・最終採否 | 大平鉄兵（三代目観測者／HDS創始者） |
| 実装主体 | Codex |
| 文章生成支援 | ChatGPT |
| 版 | rev2 |
| 日付 | 2026-07-30 |
| 状態 | rev1監査指摘反映済み・段階実装仕様・実コード未監査 |
| 対象 | ARC-AGI-2／ARC-AGI-3の正解付き公開素材・検証済み教師素材 |
| Scope | **蒸留のみ**。未知問題への活用、ソルバー、エージェント、RAG、本番攻略は対象外 |

---

## 0. 固定結論

本仕様が実装するのは、次の静的変換である。

```text
正解付き教師素材
→ 観測と決定的導出の分離
→ 複数の実行可能機構仮説
→ 正解拘束によるexact fit検証
→ 教師拘束内counterfactual intervention
→ HDSによる採択・保留・棄却
→ corpus-scopedな機構記録
→ 横断共通項・境界・反例・失敗署名
→ evidence-graded RuleAtom／RuleFamily
→ 静的成果物freeze
→ END
```

本仕様は、世界の一意な「真因」を同定したと主張しない。

正解再現によって証明できるのは、まず**観測適合性**である。  
因果強度は、独立事例での再現、候補内部の除去試験、ARC3教師環境への介入、反例、再現制御を通過した範囲だけ段階的に昇格させる。

本仕様における「因果」「機構」は、常に次の境界付きで扱う。

```text
CLOSED_WITHIN:
  hypothesis_language_version
  observed_case_set
  intervention_set
  candidate_budget
  resource_budget
  evidence_boundary
  domain_adapter_version
```

したがって、本仕様の最終成果は、

> **指定教師corpusと明示された仮説言語・介入集合の範囲内で、正解と整合し、反証監査を通過した実行可能機構資産**

である。

---

# 1. 権威・依存資料・成立根拠

## 1.1 権威順序

判断が衝突する場合は次の順で解決する。

1. 大平鉄兵による現在の明示指示
2. 本仕様書 rev2
3. `HDSフレーム_rev3_1a_内部用統合仕様.md`
4. `HDSフレーム_rev3_1_外向け仕様.md`
5. 本ロードマップ rev2
6. 凍結済みApprovalRecord
7. 各PhaseのFrame／Manifest／Run Report
8. HDS Black-Box Translator
9. rev1文書
10. 実装者の推定

Codexは、上位資料の欠落を推測で埋めてはならない。  
未固定事項は`SUSPEND`とし、Open Term Ledgerへ記録する。

## 1.2 HDS正本ロック

| 資料 | SHA-256 |
|---|---|
| `HDSフレーム_rev3_1a_内部用統合仕様.md` | `6f55471c0bb3b2b54d434ac05ac09ee24ef69fda3f2f024e5f762696e822216c` |
| `HDSフレーム_rev3_1_外向け仕様.md` | `d7cbbf4c981621509e124077ae66cc49bd29b2271fbf94194c6786d2a5a8724a` |
| `HDS_SelfContained_Prompt_v1_2_utf8bom.txt` | `33b8a35176a0cc2f18502befb4a53cfbbf378b35e36b911888fa534a8b377b50` |

実装開始時に再計算し、不一致なら全Phaseを`SUSPEND`する。

## 1.3 HDS Black-Box Translatorの位置づけ

参照repository：

```text
gatchimuchio/HDS-BlackBox-Translator
commit: b501cc77c94048421af8efdb2e866c22b06f7208
```

先行実績として成立しているもの：

```text
候補・評価・policy・PV・選択結果
→ Objective / Axes / Alternatives / Risk / Choice
→ Premise / Reason / Tradeoff / Decision
→ 決定論的・監査可能な構造化説明
```

先行実績として**成立していないもの**：

- 未知機構の自動帰納
- 実行可能仮説言語
- 反実仮想介入
- 世界の一意な内部因果同定
- 多数事例からのRuleAtom自動昇格

したがって成立根拠は次のように限定する。

```text
HDS Black-Box Translator
  = 証拠・候補・選択をHDS判断構造へ射影できる先行実績

ARC正解付き教師素材
  = 機構仮説へ強い外部拘束を与える素材

本仕様で新規実装するもの
  = typed Causal IR
  + candidate generator
  + exact-fit verifier
  + teacher-bound intervention verifier
  + cross-case generalizer
  + evidence-graded promotion
```

---

# 2. Scope Lock

## 2.1 MUST：許可する能力

1. 原本・依存・環境の凍結
2. ARC2 challenge／solutionのoffline読込
3. ARC3既知成功軌道のdeterministic replay
4. Frozen teacher caseに対するHypothesisIR実行
5. Known prefixを再生した教師拘束内介入
6. exact output／transition／terminal比較
7. 複数仮説生成
8. HDS Frame／ModelSet／Gate／Decision／Update台帳
9. corpus内の横断整列・共通項抽出
10. 境界・反例・FailureSignatureの生成
11. evidence-graded RuleAtom／RuleFamily候補生成
12. Owner採否をApprovalRecordとして凍結
13. 全成果物のcanonical serialization、digest、再構築
14. 蒸留coverageの計測・開示

## 2.2 MUST NOT：禁止する能力

- 未ラベルの未知ARC taskへのanswer生成
- ARC2 solver
- ARC3 production agent
- 公式環境での自律探索
- 本番action policy
- 推論時検索・RAG
- 蒸留知識のLLM投入
- Kaggle submission artifact生成
- competition API接続
- AGI Runtimeへの接続
- C／J／M／Pへの実装統合
- スコア最適化
- self-update runtime
- source codeからの答え直接抽出
- case ID、task ID、game IDによる規則routing
- answer lookup table
- 正解gridまたは正解action列のRuleAtom化

## 2.3 Scope Guard

禁止判定はファイル名blacklistで行わない。

CIは次を監査する。

- import graph
- entrypoint
- official ARC API呼出
- network access
- unlabeled taskを受け取るpublic callable
- submission形式の出力
- case／game identityをselectorに使うIR
- full answer literalまたはfixed action sequence
- runtime／production packageへの依存

許可されたoffline interpreterやteacher replay harnessを、`solver`という文字列だけで誤検出してはならない。

---

# 3. 証拠・因果・閉包の強度

## 3.1 観測適合集合

ARC2教師集合を、

```text
D = {(x1, y1), ..., (xn, yn)}
```

とすると、

```text
Compatible(D) = {h | ∀(xi, yi) ∈ D, Execute(h, xi) = yi}
```

である。

`h ∈ Compatible(D)`は、観測された教師例との整合を示す。  
それだけでは一意な真因を示さない。

ARC3成功軌道では、直接観測できるのは訪問済みの、

```text
T(si, ai) = s(i+1)
```

だけである。未実行action、順序交換、step削除、payload変更の結果は介入なしには断定しない。

## 3.2 MechanismSupportState

HDSの`EvidenceState`とは別に、Domain Adapter側で次を保持する。

| 状態 | 意味 |
|---|---|
| `OBSERVED_COMPATIBLE` | 観測教師素材と矛盾しない |
| `LOCAL_EXACT_FIT` | 一task／一trajectory内の全教師単位をexactに再現 |
| `STRUCTURAL_RECURRENCE` | 独立した複数caseで同型機構が再現 |
| `BOUNDARY_OBSERVED` | supportとnear-miss／negative poolの差が観測済み |
| `COUNTERFACTUAL_SUPPORTED` | 事前定義介入で必要性・順序・効果が支持された |
| `REPRODUCIBLE_CONTROL` | 独立条件で機構の起動・停止・効果を再現制御 |
| `FALSIFIED` | 正解・介入・反例により棄却 |
| `INCONCLUSIVE` | 証拠不足または候補非識別 |

## 3.3 HDS EvidenceStateとの対応

| MechanismSupportState | HDS EvidenceState |
|---|---|
| `OBSERVED_COMPATIBLE` | `OBSERVED` |
| `LOCAL_EXACT_FIT` | `LOCAL_FIT` |
| `STRUCTURAL_RECURRENCE` | `STRUCTURAL_RECURRENCE` |
| `BOUNDARY_OBSERVED` | `STRUCTURAL_RECURRENCE`または`GENERALIZATION_CANDIDATE` |
| `COUNTERFACTUAL_SUPPORTED` | `GENERALIZATION_CANDIDATE` |
| `REPRODUCIBLE_CONTROL` | `REPRODUCED` |
| `FALSIFIED` | `FALSIFIED` |
| `INCONCLUSIVE` | `INCONCLUSIVE` |

対応は機械的な一対一昇格ではない。HDS Gate結果を併記する。

## 3.4 閉包表現

単独の`CLOSED`を使用しない。

```json
{
  "closure_state": "CLOSED_FOR_ASSERTION",
  "closed_within": {
    "hypothesis_language_version": "hds-causal-ir-v1",
    "observed_case_set_digest": "...",
    "intervention_set_digest": "...",
    "candidate_budget": 256,
    "resource_profile_id": "distill-default-v1",
    "evidence_boundary": "teacher-corpus-and-declared-interventions-only",
    "limitations": [
      "unobserved mechanisms may remain",
      "not an ontological true-cause claim"
    ]
  }
}
```

---

# 4. HDS準拠構造

## 4.1 DistillationFrame：F / Frame・Ground

事実抽出をFそのものと同一視しない。

```text
RawObservation / DeterministicDerivation
→ DistillationFrameを構成
→ Fを閉じる
```

`DistillationFrame`必須field：

```text
frame_id
spec_version
hds_dependency_digest
domain
purpose
X
R_observable
Mc
source_scope
evidence_boundary
hypothesis_language_version
candidate_budget
intervention_budget
resource_profile_id
authority_boundary
non_goals
stop_conditions
rollback_conditions
unresolved_terms
```

## 4.2 Md / ModelSet

各caseで最低限次を生成する。

- baseline
- alternative
- counter_hypothesis
- null_model
- no_op
- observation_error
- delayed_effect（ARC3）
- wrong_target
- wrong_order
- overfit
- surface_correlation
- answer_copy／trajectory_lookup候補（棄却用adversarial candidate）

各ModelRecordは、

```text
statement
HypothesisIR digest
assumptions
supporting evidence
contradicting evidence
expected observations
falsification procedure
valid scope
resource requirement
risks
confidence_ppm
status
```

を持つ。

## 4.3 Cm / Commit・Check

Cmは単一choiceを必須にしない。

```text
selected_model_ids[]
held_model_ids[]
rejected_model_ids[]
```

を持つ。

独立状態軸：

- `assertion_state`
- `operation_state`
- `adoption_state`
- `evidence_state`
- `mechanism_support_state`
- `closure_state`
- `update_state`

例：

```text
assertion_state = SUSPEND
operation_state = PROBE
adoption_state = QUARANTINE
evidence_state = LOCAL_FIT
mechanism_support_state = LOCAL_EXACT_FIT
closure_state = PARTIALLY_CLOSED
```

## 4.4 U / Update

Uは静的台帳更新であり、runtime自己更新ではない。

```text
outcome
→ attribution
→ local model revision
→ repeated validation
→ reusable rule candidate
→ separate Owner authorization
→ frozen artifact
```

Candidate generatorが自分の候補を自動昇格してはならない。

## 4.5 HDSCausalRecord

一caseの最終静的記録は最低限次を持つ。

```text
record_id
record_version
frame_ref
raw_observation_refs
deterministic_derivation_refs
interpretation_hypothesis_refs
model_ids
selected_model_ids
held_model_ids
rejected_model_ids
gate_result_refs
decision_ref
intervention_result_refs
outcome_attribution_refs
failure_signature_refs
open_term_refs
assertion_state
operation_state
evidence_state
mechanism_support_state
closure_state
closed_within
claim_refs
update_proposal_refs
content_digest
```

自然言語summaryは補助fieldであり、機械判定の正本ではない。

## 4.6 Distillation Gate Registry

Phase IDと衝突しないようGate IDを`DG-00`〜`DG-15`とする。

| Gate | 内容 |
|---|---|
| `DG-00` | Coordinate／Frame整合 |
| `DG-01` | Open Term |
| `DG-02` | X／R／Mc／Scope Closure |
| `DG-03` | Hypothesis実行可能性 |
| `DG-04` | Counter-Hypothesis存在 |
| `DG-05` | Alternative Adequacy／strawman禁止 |
| `DG-06` | Evidence強度・由来・欠損 |
| `DG-07` | Extensional Exact Fit |
| `DG-08` | Tautology／Answer Copy／Recursion |
| `DG-09` | Projection／因果過剰主張 |
| `DG-10` | Intervention可逆性・安全性 |
| `DG-11` | Temporal Attribution／順序・遅延 |
| `DG-12` | Resource Boundary |
| `DG-13` | Surface Correlation／Shadow |
| `DG-14` | Authority／Approval |
| `DG-15` | Commit／Promotion |

---

# 5. 入力・Source契約

## 5.1 Manifestの三分離

### SourceContentManifest

内容同一性の正本。hash対象。

```text
manifest_id
manifest_version
source_profile
domain
repository_relative_posix_paths
file_sha256
file_size
directory_merkle_root
upstream_repository
upstream_commit_or_release
split_role
answer_visibility
development_usage
contamination_class
license
content_digest
```

### AcquisitionRecord

取得状況。SourceContentManifestのhash対象外。

```text
acquisition_id
source_content_manifest_id
acquired_at
local_path
mtime
acquisition_actor
transport
notes
acquisition_digest
```

### RunManifest

実行環境・command・開始終了時刻を別管理。

## 5.2 ARC2 Source Profile

基準bundle：

```text
arc-prize-2026-arc-agi-2.zip
SHA-256:
d00746ef4e06a515ad53bde4dff276dc8ef5a26829a0ebeafc8cf8ba6371abaa
```

| ファイル | SHA-256 | split_role | answer_visibility |
|---|---|---|---|
| `arc-agi_training_challenges.json` | `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5` | `TRAIN_TEACHER` | challenge |
| `arc-agi_training_solutions.json` | `9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9` | `TRAIN_TEACHER` | visible |
| `arc-agi_evaluation_challenges.json` | `e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8` | `PUBLIC_EVALUATION_TEACHER` | challenge |
| `arc-agi_evaluation_solutions.json` | `84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1` | `PUBLIC_EVALUATION_TEACHER` | visible |
| `arc-agi_test_challenges.json` | `232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83` | `UNLABELED_TEST` | unavailable |

Adapter Profile：

```text
ARC2_KAGGLE_CHALLENGE_SOLUTION
ARC2_OFFICIAL_TASK_JSON
ARC2_INTERNAL_NORMALIZED_CORPUS
```

公開evaluation解答を蒸留に使用した場合、そのsplitは`PUBLIC_EVALUATION_CONSUMED`と記録し、以後blind評価証拠として使用しない。

## 5.3 ARC3 Source Profile

基準bundle：

```text
arc-prize-2026-arc-agi-3.zip
SHA-256:
c72400a32db5e48da9014baf893b48016b300e9a6a77bd5d505de2b1ec61d645
```

基準runtime：

| Artifact | SHA-256 |
|---|---|
| `arcengine-0.9.3-py3-none-any.whl` | `5f9739d6d0055780a4581fd6fe09066bb08775c4c8212c9adcca2eb008aef59c` |
| `arc_agi-0.9.8-py3-none-any.whl` | `aeca1663db342e91cb8fc96cf0c83e2fa39db1640bc1298e80a8d522e3af70f3` |

Source Profile：

```text
ARC3_ENVIRONMENT_SOURCE_BUNDLE
ARC3_RAW_TEACHER_RECORDING
ARC3_CANONICAL_TEACHER_TRAJECTORY
```

Environment sourceはreplay harnessだけが読める。Candidate generator、HDS decomposer、cross-case generalizerへsource codeを渡してはならない。

## 5.4 ARC3 ActionRecord

Raw actionは意味ラベル`UP`等へ置換しない。

```json
{
  "action_record_version": "arc3-action-record-v1",
  "step_index": 0,
  "action_id": 6,
  "action_enum": "ACTION6",
  "payload": {"x": 12, "y": 34},
  "available_actions_before": [1, 2, 6],
  "available_actions_after": [1, 2, 6],
  "is_complex": true,
  "raw_action_digest": "...",
  "semantic_hypothesis_id": null
}
```

`semantic_hypothesis_id`は推論層に属し、raw evidenceとは分離する。

## 5.5 ARC3 TeacherTrajectory

必須field：

```text
trajectory_version
trajectory_id
source_content_manifest_id
environment_artifact_digest
environment_version
arc_agi_wheel_digest
arcengine_wheel_digest
python_version
os_manifest_digest
seed
reset_mode
observation_projection_version
trajectory_source
verification_method
raw_recording_digest
canonical_trajectory_digest
initial_frame_digest
steps[]
final_terminal_state
level_completion_count
score_or_progress
```

各step：

```text
before_frame_digest
before_canonical_frame
level_index_before
terminal_state_before
available_actions_before
ActionRecord
after_frame_digest
after_canonical_frame
level_index_after
terminal_state_after
available_actions_after
visible_diff
progress_delta
```

timestamp、GUID、絶対pathはraw recordingに保持してよいが、canonical trajectory digestから除外する。

## 5.6 Identity／Provenance境界

Source／Orchestration層では、再現と由来追跡のためtask ID、game ID、level IDを保持してよい。

ただし、次の型はidentity fieldを受け取ってはならない。

- `HypothesisIR`
- `ModelRecord`の機構selector
- `RuleAtom`
- `RuleFamily`
- candidate ranking input
- cross-case unification key

case identityは、artifact参照用のprovenance pointerとしてのみ保持し、機構の成立条件、selector、branch、parameterへ変換しない。

CIは文字列scanだけでなく、型境界、serialization、IR linter、data-flow testでidentity流入を検査する。

## 5.7 Replay Isolation

ARC3 replay／interventionは次を必須とする。

- network disabled
- source mount read-only
- secrets absent
- subprocess isolation
- filesystem write allowlist
- Python／OS／wheel hash固定
- CPU／memory／wall-time制限
- stdout／stderr／exit code保存
- seed固定
- environment sourceをcandidate generatorへ渡さない

---

# 6. 証拠型の三分離

## 6.1 RawObservation

直接取得された値だけを保持する。

- raw grid
- input／output pair
- raw action
- before／after frame
- available actions
- terminal
- progress
- source pointer

## 6.2 DeterministicDerivation

決定的アルゴリズムによる導出。

必須：

```text
derivation_id
algorithm_id
algorithm_version
configuration
input_evidence_refs
output
output_type
content_digest
```

例：

- cell delta
- color histogram
- 4-neighbor component
- 8-neighbor component
- bounding box
- exact shape signature
- frame diff
- action-effect delta

`object`、`movement`、`symmetry role`等の意味ラベルをここへ直接入れない。

## 6.3 InterpretationHypothesis

推論を保持する。

- object candidate
- controllable entity
- movement candidate
- copied structure
- goal candidate
- action semantics
- causal role
- order necessity
- irreversibility

RawObservation／DeterministicDerivationをEvidenceRecordとして参照する。

---

# 7. Canonical Serialization／Digest契約

## 7.1 Canonical JSON

- UTF-8
- key lexicographic order
- compact separators
- Unicode NFC
- pathはrepository-relative POSIX
- NaN／Infinity禁止
- boolとintを混同しない
- confidenceはfloatではなく`confidence_ppm`（0〜1,000,000整数）
- setはsorted arrayへ正規化
- timestampはcontent digestから除外
- IDとdigest field自身をdigest計算から除外
- unknown field禁止

## 7.2 Artifact Digest

```text
logical_content_digest
physical_package_digest
```

を分離する。

NPZ／ZIP等は、

- dtype
- endian
- shape
- tensor name order
- archive entry order
- timestamp normalization
- NaN／Inf禁止

を固定する。

## 7.3 LLM Capture

LLMを候補生成へ使う場合、決定論stageと分離する。

```text
LLM capture phase
→ raw response保存
→ prompt／model／parameters／request digest固定
→ capture freeze
→ deterministic parse／validate／compile x3
```

D13相当の再構築ではlive LLMを呼ばない。

## 7.4 Human Approval

Owner採否もlive判断を再実行しない。

凍結済みApprovalRecordを決定論再構築の入力とする。

---

# 8. Schema Inventory

JSON Schema正本を次の38件に固定する。

1. `DependencyLock`
2. `SourceProfile`
3. `SourceContentManifest`
4. `AcquisitionRecord`
5. `EnvironmentManifest`
6. `RunManifest`
7. `ResourceProfile`
8. `OperatorRegistry`
9. `ARC2TeacherCase`
10. `ARC3TeacherTrajectory`
11. `ARC3ActionRecord`
12. `RawObservation`
13. `DeterministicDerivation`
14. `InterpretationHypothesis`
15. `EvidenceRecord`
16. `DistillationFrame`
17. `HypothesisIR`
18. `CounterfactualInterventionPlan`
19. `InterventionResult`
20. `LLMCaptureRecord`
21. `ModelRecord`
22. `GateResult`
23. `DecisionRecord`
24. `HDSCausalRecord`
25. `RuleAtom`
26. `RuleFamily`
27. `BoundaryRecord`
28. `CounterexampleRecord`
29. `FailureSignature`
30. `NormalizationCertificate`
31. `PromotionDecision`
32. `ApprovalRecord`
33. `OpenTermRecord`
34. `ClaimRecord`
35. `DistillationAudit`
36. `CoverageReport`
37. `CompletionStateRegistry`
38. `FrozenArtifactManifest`

全schemaは、

```text
schema_version
content_digest
```

を持つ。

参照先IDは、参照対象schemaで必ず定義する。

---

# 9. Typed Causal IR／Hypothesis DSL

## 9.1 目的

`CausalHypothesis`を自然言語だけで保持しない。  
HypothesisIRはoffline interpreterで実行できなければならない。

## 9.2 HypothesisIR

```text
HypothesisIR
├── ir_version
├── domain
├── input_types
├── SelectorGraph
├── Preconditions
├── OperatorGraph
├── OrderingConstraints
├── StopConditions
├── PredictedEffects
├── Invariants
├── Exclusions
├── FalsificationProcedures
├── ResourceCost
└── Provenance
```

## 9.3 共通型

```text
Grid
Cell
CellSet
Region
ObjectCandidate
ObjectSet
RelationGraph
Scalar
Color
Vector
Sequence
Boolean
State
ActionRecord
Trajectory
Event
Effect
TerminalState
```

## 9.4 Operator Registry Entry

各opcodeは次を必須とする。

```text
opcode
opcode_version
domain
input_types
output_type
parameter_schema
preconditions
execution_semantics
invalid_operation_semantics
deterministic
side_effect_free
resource_cost
commutes_with[]
canonicalization_rule
test_vectors[]
content_digest
```

最低限の型署名例：

```text
RECOLOR(Grid, CellSet, Color) -> Grid
TRANSLATE(CellSet, Vector, CollisionPolicy) -> CellSet
OVERLAY(Grid, Grid, PrecedenceRule) -> Grid
MATCH_ACTION_ID(ActionRecord, Integer) -> Boolean
MATCH_ACTION_PAYLOAD(ActionRecord, PayloadPredicate) -> Boolean
PREDICT_TRANSITION(State, ActionPattern) -> State
GOAL_PREDICATE(State) -> Boolean
```

selectorが0件、1件、複数件を返す場合のcardinality semanticsをopcodeごとに固定し、暗黙に`first`を選ばない。

## 9.5 ARC2 Operator Registry v1

最低限：

```text
SELECT_CELLS
SELECT_COMPONENTS_4
SELECT_COMPONENTS_8
SELECT_BY_COLOR
SELECT_BY_SIZE
SELECT_BY_SHAPE
SELECT_BY_RELATION
UNIQUE
ARGMIN
ARGMAX
IDENTITY
RECOLOR
TRANSLATE
ROTATE_90
ROTATE_180
ROTATE_270
REFLECT_HORIZONTAL
REFLECT_VERTICAL
COPY
CROP
PAD
TILE
FILL
OUTLINE
CONNECT
MASK
OVERLAY
DELETE
EXTRACT
COUNT
COUNT_ENCODE
REPEAT_N
COMPOSE
```

## 9.6 ARC3 Operator Registry v1

最低限：

```text
DERIVE_STATE_FIELD
TRACK_ENTITY
MATCH_ACTION_ID
MATCH_ACTION_PAYLOAD
PRECONDITION
PREDICT_EFFECT
PREDICT_TRANSITION
DELAYED_EFFECT
GOAL_PREDICATE
HAZARD_PREDICATE
ORDER_BEFORE
ORDER_ADJACENT
REPEAT_N
REPEAT_UNTIL_OBSERVED
RESET_EFFECT
TERMINAL_CONTRIBUTION
INVARIANT
EXCLUSION
```

ARC3 IRはraw action IDとpayloadを扱う。ゲーム固有意味はInterpretationHypothesisとして参照する。

## 9.7 Interpreter semantics

- pure／offline
- deterministic
- no network
- no arbitrary Python
- no `eval`／`exec`
- versioned opcode registry
- type mismatchは`IR_TYPE_ERROR`
- unknown opcodeは`IR_UNKNOWN_OPCODE`
- precondition不成立は`IR_PRECONDITION_UNSATISFIED`
- resource超過は`SUSPEND_RESOURCE`
- invalid operationは暗黙補正せず明示FAIL
- operator orderを勝手に交換しない
- 可換性はopcode registryに証明済みpairとして登録された場合だけ許可

## 9.8 Code／IR ABI

```text
interpreter_version
ir_schema_version
opcode_registry_digest
type_system_digest
resource_cost_model_digest
serialization_version
```

不一致P／IRは実行拒否する。

## 9.9 Answer Copy／Tautology禁止

HypothesisIR／RuleAtomは次を含んではならない。

- case ID、task ID、game IDによるbranch
- full input digest lookup
- full answer grid literal
- per-case output coordinate table
- fixed successful action sequence
- source filename routing
- replay index routing

例外的なconstantは、入力依存計算で導出できるか、複数独立caseで同一constant ruleが支持される場合だけ候補化する。

---

# 10. Candidate Generation

## 10.1 入力

Candidate generatorが受け取れるもの：

- RawObservation
- DeterministicDerivation
- Teacher answer／success trajectory
- DistillationFrame
- versioned operator registry
- resource profile

受け取れないもの：

- environment source code
- hidden state
- case-specific answer lookup table
- Ownerの非凍結判断
- sealed audit expected output

## 10.2 候補族

最低限：

- minimal mechanism
- alternative selector
- alternative operator order
- null／no-op
- observation error
- surface correlation
- overfit
- wrong target
- wrong order
- answer copy adversarial
- trajectory lookup adversarial
- delayed effect（ARC3）
- different goal（ARC3）

Alternative Adequacyの最低条件：

- selector familyが異なる候補を最低1件
- operator／ordering familyが異なる候補を最低1件
- 少なくとも一部の観測を説明できる競合候補を含む
- 明白に不可能な候補だけをcounterとして数えない
- strawman比率、競合候補のfit範囲、区別可能な介入を記録する

## 10.3 生成方式

1. deterministic template generation
2. bounded graph enumeration
3. optional frozen LLM candidate capture

LLMはHypothesisIR JSON候補だけを出す。任意コードを生成・実行しない。

---

# 11. Verification

## 11.1 Extensional Exact-Fit Verifier

### ARC2

HypothesisIRを全train inputへ適用し、output gridを完全一致比較する。

記録：

```text
pair_count
exact_match_count
cell_mismatch_count
shape_mismatch
extra_change
missing_change
fit_status
```

### ARC3

Recorded teacher trajectoryに対し、

- precondition
- action match
- predicted effect
- state abstraction
- ordering
- terminal contribution

をstep単位で比較する。

Exact fitは`LOCAL_EXACT_FIT`までであり、因果確定ではない。

## 11.2 Counterfactual Intervention Verifier

### ARC2 Candidate Intervention

正解入力を固定し、候補プログラムを介入する。

- `REMOVE_OPERATOR`
- `REPLACE_SELECTOR`
- `PERTURB_PARAMETER`
- `SWAP_OPERATOR_ORDER`
- `REMOVE_PRECONDITION`
- `REPLACE_STOP_CONDITION`

介入後に正解再現が失われるかを測る。  
これは仮説言語内の必要性証拠であり、世界の真因証明ではない。

### ARC3 Teacher-Bound Intervention

- `DELETE_STEP`
- `REPEAT_STEP`
- `SWAP_ADJACENT`
- `SUBSTITUTE_ACTION`
- `PERTURB_ACTION_PAYLOAD`
- `REPLAY_PREFIX_THEN_ALTERNATIVE`
- `REPLAY_WITH_SEED_VARIATION`

制約：

- frozen teacher caseだけを使う
- 同じseed／initial stateから既知prefixを再生
- alternativeは当該stepの`available_actions_before`から選ぶ
- adaptive online search禁止
- intervention planを実行前にfreeze
- budget超過時はSUSPEND
- GAME_OVER／WIN／progress／no-effect／delayed effectを保存

介入は、単に候補を壊すだけでなく、可能な限り複数の競合候補で予測が分岐するものを優先する。

`COUNTERFACTUAL_SUPPORTED`へ昇格するには最低限、

- candidate固有のFalsificationProcedureに対応する
- 競合候補間で事前予測が異なる
- 実観測が少なくとも一方を棄却または明確に弱める
- intervention planが結果観測前にfreezeされている

ことを要求する。

安全または実行可能な識別介入が存在しない場合、`LOCAL_EXACT_FIT`または`STRUCTURAL_RECURRENCE`に留め、介入不能理由をOpen Termへ記録する。

介入していない属性を断定しない。

```text
order_observed
necessity_unverified
irreversibility_unverified
reversal_not_observed
```

等の限定表現を使用する。

---

# 12. Normalization／Generalization

## 12.1 三分離

### LOSSLESS_NORMALIZATION

情報を失わない変換。

- alpha rename
- repository-relative path
- coordinate origin normalization
- variable renaming
- canonical ordering（意味的順序を壊さない範囲）

逆写像を持つ。

### SEMANTIC_REWRITE

条件付き等価性を証明できる変換。

必要：

- equivalence evidence
- assumptions
- supported cases
- intervention evidence
- rewrite certificate

### GENERALIZATION_CANDIDATE

未観測の意味を追加する候補。

例：

```text
RIGHTを3回
→ repeat(direction=RIGHT, count=3)
```

はlosslessに近い。

```text
RIGHTを3回
→ boundary_or_goalまでrepeat
```

は新しいstop conditionを追加するためGeneralization Candidateである。

## 12.2 NormalizationCertificate

```text
certificate_id
normalization_class
source_record_digest
canonical_record_digest
rewrite_rule_id
variable_mapping
inverse_mapping
required_assumptions
equivalence_evidence
information_loss
status
```

## 12.3 Cross-Domain境界

rev2ではARC2 RuleAtomとARC3 RuleAtomを直接統合しない。

許可：

- HDS Gate項目
- Failure Class
- Evidence State
- 一般的監査質問

禁止：

- ARC2／ARC3機構を`CROSS_DOMAIN` RuleAtomへ昇格
- bridge ontologyなしのmechanism merge

---

# 13. Cross-Case Commonality Extraction

## 13.1 前提

入力できるのは、

- exact-fit済みHypothesisIR
- NormalizationCertificate付きcanonical form
- evidence state
- support／negative pool
- case independence metadata

## 13.2 Typed Graph Unification

- type-preserving variable unification
- operator sequence保持
- precondition／effect／exclusion分離
- unification timeout
- graph size limit
- unsupported mergeはSUSPEND

## 13.3 Support Selection

support setを後付けで都合よく選ばない。

必須：

```text
support_selection_method
candidate_generation_cutoff
independent_case_definition
negative_pool_definition
near_miss_definition
```

---

# 14. RuleAtom／RuleFamily Promotion

## 14.1 状態

```text
SUPPORTED_SINGLE
LOCAL_FIT
STRUCTURAL_RECURRENCE
BOUNDARY_OBSERVED
COUNTERFACTUAL_SUPPORTED
PROMOTED_CORPUS_SCOPED
REPRODUCIBLE_CONTROL
FALSIFIED
INCONCLUSIVE
```

## 14.2 RuleAtom必須field

```text
rule_id
rule_version
domain
mechanism_template_ir
trigger
preconditions
effect
invariants
exclusions
valid_scope
support_case_ids
negative_pool_ids
near_miss_ids
counterexample_ids
support_selection_method
alternative_adequacy
intervention_coverage
evidence_state
mechanism_support_state
adoption_state
closure_boundary
provenance
normalization_certificate_refs
promotion_decision_ref
approval_ref
```

生成時の`adoption_state`は`PROPOSED`または`PROBATION`。  
最初から`ACTIVE`／`PROMOTED`にしない。

## 14.3 Promotion Gate

`PROMOTED_CORPUS_SCOPED`には最低限必要：

1. task内全教師単位でexact fit
2. 独立caseでstructural recurrence
3. predeclared negative pool
4. 複数の非strawman alternative
5. boundaryまたはnear-miss観測
6. 可能な範囲でcounterfactual support
7. identity／answer-copy audit PASS
8. deterministic rebuild PASS
9. explicit valid scope
10. Owner ApprovalRecord

一回成功を直接昇格しない。

---

# 15. FailureSignature

```text
signature_id
target
target_version
attempted_hypothesis_id
hds_failure_class
domain_failure_code
cognition_stage
surface_symptom
structural_cause
trigger
affected_scope
unaffected_scope
violated_assumption
evidence_state
public_local_boundary
repair_requirement
recovery
next_probe_axes
reusable_check
regression_risk
recurrence_count
status
provenance
```

`wrong_target`、`wrong_order`等はdomain failure codeであり、HDS failure classの代替ではない。

Failure ClassはHDS rev3.1aの分類を正本とする。

---

# 16. ApprovalRecord

```text
approval_id
authority
target_artifact_digest
previous_state
next_state
decision
reason_codes
evidence_refs
spec_version
approved_at
approval_artifact_digest
```

`approved_at`はApprovalRecord自身の監査情報として保持するが、対象artifactのlogical digestへ混入させない。

D13相当の再構築ではApprovalRecordを入力し、人間判断を再実行しない。

---

# 17. Resource Boundary

`ResourceProfile`をversioned configとして凍結する。

初期baseline：

```text
candidate_count_budget = 256
candidate_graph_node_limit = 128
arc2_intervention_budget = 64
arc3_intervention_budget = 128
interpreter_step_limit = 100000
unification_timeout_ms = 60000
per_case_wall_seconds = 900
memory_limit_mb = 4096
llm_call_budget = 8
```

超過時：

```text
assertion_state = SUSPEND
operation_state = HOLD
evidence_state = INCONCLUSIVE
reason_code = SUSPEND_RESOURCE
```

予算超過を失敗や因果不成立へ変換しない。

---

# 18. Determinism／Reproducibility

## 18.1 再構築run

決定論runの入力：

- frozen source
- frozen environment
- frozen schemas
- frozen Causal IR registry
- frozen LLM raw captures
- frozen ApprovalRecords
- frozen resource profile

禁止：

- live LLM
- live human approval
- wall-clock依存ID
- absolute path
- mtime依存
- unordered iteration

## 18.2 x3契約

同一入力から3回再構築し、次を一致させる。

- logical artifact digests
- case HDS records
- RuleAtom／RuleFamily
- FailureSignature
- CoverageReport
- FrozenArtifactManifest

物理package digestはcanonical packaging後に一致させる。

---

# 19. Completion State

単一の`DISTILLATION_COMPLETE`を使用しない。

| 状態 | 定義 |
|---|---|
| `PIPELINE_IMPLEMENTATION_COMPLETE` | 全工程の実装・単体／統合試験PASS |
| `CORPUS_PROCESSING_COMPLETE` | 全source caseに処理結果が存在 |
| `CAUSAL_ASSET_COVERAGE_REPORTED` | 全caseの証拠状態・未閉包を集計 |
| `PROMOTED_RULESET_AVAILABLE` | 一件以上のOwner承認済みRuleAtom／Family |
| `DISTILLATION_COVERAGE_ACCEPTED` | Ownerがcoverage・未閉包・品質を採否 |
| `FROZEN_ARTIFACT_COMPLETE` | exact inputから同一成果物を再構築可能 |

最終宣言は次に限定する。

> 指定された教師corpusに対する蒸留pipelineの実行と成果物freezeを完了した。各機構主張の証拠状態、適用範囲、介入coverageおよび未閉包項目はCoverageReportとClaim Ledgerに固定した。

## 19.1 CoverageReport必須field

```text
source_case_count
processed_case_count
observed_compatible_count
local_exact_fit_count
structural_recurrence_count
boundary_observed_count
counterfactual_supported_count
reproducible_control_count
multi_causal_count
partial_count
suspend_count
falsified_count
promoted_rule_count
provenance_complete_count
coverage_by_domain
coverage_by_source_profile
resource_suspension_count
open_term_count
```

全caseがSUSPENDでも`CORPUS_PROCESSING_COMPLETE`にはなり得るが、`DISTILLATION_COVERAGE_ACCEPTED`を自動PASSしてはならない。

---

# 20. Repository／Artifact構成

```text
README.md
SCOPE_LOCK.md
DEPENDENCY_LOCK.md
pyproject.toml

src/hds_distill/
  canonical/
  manifests/
  adapters/
    arc2/
    arc3/
  evidence/
  ir/
    common/
    arc2/
    arc3/
    interpreter/
  candidates/
  verification/
    exact_fit/
    interventions/
  hds/
  normalization/
  alignment/
  promotion/
  audit/

schemas/
  dependency_lock.schema.json
  source_profile.schema.json
  source_content_manifest.schema.json
  acquisition_record.schema.json
  environment_manifest.schema.json
  run_manifest.schema.json
  resource_profile.schema.json
  operator_registry.schema.json
  arc2_teacher_case.schema.json
  arc3_teacher_trajectory.schema.json
  arc3_action_record.schema.json
  raw_observation.schema.json
  deterministic_derivation.schema.json
  interpretation_hypothesis.schema.json
  evidence_record.schema.json
  distillation_frame.schema.json
  hypothesis_ir.schema.json
  counterfactual_intervention_plan.schema.json
  intervention_result.schema.json
  llm_capture_record.schema.json
  model_record.schema.json
  gate_result.schema.json
  decision_record.schema.json
  hds_causal_record.schema.json
  rule_atom.schema.json
  rule_family.schema.json
  boundary_record.schema.json
  counterexample_record.schema.json
  failure_signature.schema.json
  normalization_certificate.schema.json
  promotion_decision.schema.json
  approval_record.schema.json
  open_term_record.schema.json
  claim_record.schema.json
  distillation_audit.schema.json
  coverage_report.schema.json
  completion_state_registry.schema.json
  frozen_artifact_manifest.schema.json

profiles/
  source/
  resource/
  operator_registry/

tests/
  golden/
  sealed/
  unit/
  integration/

artifacts/
  source_content_manifests/
  acquisition_records/
  environment_manifests/
  run_manifests/
  raw_observations/
  deterministic_derivations/
  interpretation_hypotheses/
  llm_captures/
  candidates/
  intervention_plans/
  intervention_results/
  hds_records/
  rule_atoms/
  rule_families/
  boundary_records/
  counterexamples/
  failure_signatures/
  approvals/
  reports/
  frozen/
```

Golden Corpusは実装適合試験。  
Sealed Audit Corpusは変更不能な監査入力。どちらも一般性の証明とは呼ばない。

---

# 21. 最終不変条件

```text
Distillation only
≠ Solver
≠ Agent
≠ Runtime utilization
```

```text
Exact fit
≠ Unique true cause
```

```text
Hypothesis
→ executable IR
→ exact fit
→ intervention
→ cross-case recurrence
→ boundary
→ evidence-graded promotion
```

```text
Candidate generation
≠ Self-commit
```

```text
ARC2 rule
≠ ARC3 rule
```

```text
Frozen artifact
= canonical source
+ canonical environment
+ schemas
+ IR registry
+ frozen captures
+ approvals
+ deterministic build
```

---

# 22. rev1監査指摘の閉鎖対応

| Finding | rev2対応 |
|---|---|
| F-01 | MechanismSupportState、CLOSED_WITHIN、exact fit／因果分離 |
| F-02 | Translatorを射影先行実績へ限定、新規必要能力を明示 |
| F-03 | Typed Causal IR、opcode、型、interpreter、ABI |
| F-04 | offline teacher-bound executionを許可、behavioral scope guard |
| F-05 | canonical ACTION1〜7、payload、wheel／env／seed binding |
| F-06 | ARC3 counterfactual interventionと未検証表現 |
| F-07 | ARC2 source profile、split、answer visibility、contamination |
| F-08 | DistillationFrame、F／Md／Cm／U、独立状態軸 |
| F-09 | RawObservation／DeterministicDerivation／InterpretationHypothesis |
| F-10 | Content／Acquisition／Run manifest分離、LLM capture freeze |
| F-11 | 38 schemaとdirectoryを一致 |
| F-12 | normalization三分離、certificate、cross-domain promotion禁止 |
| F-13 | evidence-graded promotion、negative pool、alternative adequacy |
| F-14 | HDS準拠FailureSignature |
| F-15 | ApprovalRecord、Golden／Sealed分離 |
| F-16 | Completion StateとCoverageReport分離 |

---

# 23. 固定結論

本仕様により、Codexが実装する対象は次で閉じる。

> **正解付き多数事例から、複数の実行可能機構仮説を生成し、正解と教師拘束内介入によって反証し、HDSの証拠・状態・権限分離を維持したまま、corpus-scopedな規則・境界・反例・失敗署名へ圧縮し、静的成果物として凍結する。**

成果物の検索、投入、推論、行動、攻略への利用は、別仕様まで実装してはならない。
