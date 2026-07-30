# 工学的AGI実装仕様書 v0.2

**副題：コード拘束型の三主体Runtimeと外部Meta-Trinityの実装契約**

| 項目 | 内容 |
|---|---|
| 著者・最終採否 | 大平鉄兵（三代目観測者／HDS創始者） |
| 実装主体 | Codex |
| 文章生成支援 | ChatGPT |
| 版 | v0.2 |
| 日付 | 2026-07-30 |
| 状態 | 段階実装仕様・現行実装とのgap監査済み・全体完成未証明 |
| 上位正本 | `AGI三主体統合設計正本_v0_2.md` |
| 基準repository | `gatchimuchio/ARC-3-AGI-AGENT` |
| 基準commit | `baa03f3ba7648503d5d212d6afe9c956c56984fc` |

---

## 0. 実装固定式

```text
Development
=
MetaTrinity(
  Owner / HDS Native,
  Codex / LLM,
  Repository / Artifacts
)
→ mutable Code
→ mutable P
→ mutable J config/implementation
→ persistent M_dev
→ version candidate
```

```text
Runtime
=
CognitiveSession(
  frozen Code/L₀,
  frozen P,
  frozen J implementation/config,
  mutable AuthorityState,
  mutable ControlState,
  mutable transactional M,
  append-only ExperienceLedger,
  EnvironmentAdapter
)
```

```text
C = Execute(Fixed_L0_Interpreter, P_IR)

AutonomousRuntime
=
Trinity(C, J_hds, M)
```

本番RuntimeはCode／P／Jの自己書換えを行わない。  
本番中の動的適応は、J統治下のM更新によって成立させる。

---

# 1. 実装責任

## 1.1 Code／L₀

所有責任：

- P-IR parser
- schema／type validator
- resource cost validator
- deterministic interpreter
- observation normalization
- candidate generation pipelineのmechanical execution
- HDS commandのsingle-use検証
- HDS承認済みaction／memory commitのmechanical execution
- canonical trace
- ABI mismatch拒否

禁止：

- 個別問題のanswer保持
- game/task/level ID routing
- 最終採否
- active memoryの無承認write
- external actionの無承認emit
- 自己P昇格

## 1.2 P

保持責任：

- representation program
- state abstraction
- object／relation schema
- transition／precondition
- goal／hazard
- exploration／probe
- composition
- candidate scoring
- learned parameters
- version／provenance／logical digest

禁止：

- final authority
- memory commit
- environment I/O
- runtime identity参照
- answer lookup
- fixed successful trajectory

## 1.3 C

出力責任：

- representations
- ModelSet
- hypotheses
- counter-hypotheses
- predictions
- action／probe candidates
- CandidateEvidenceBinding候補
- MemoryMutationProposal
- next observation／question proposal
- unresolved terms

禁止：

- 自己選択
- external emit
- active memory commit
- P promotion

## 1.4 J／HDS

唯一の裁定責任：

- Purpose／Value／Risk
- X／R／Mc
- Frame
- Gate Stack
- candidate採否
- probe／execute／reobserve
- SUSPEND／STOP／rollback
- memory authorization
- episode consolidation authorization
- action authorization
- development P／J₀／M₀ promotion
- next question生成

禁止：

- 仮説計算の代行
- memory backendへの直接write
- environment stepの直接実行
- live artifactの自己書換え

## 1.5 M

保持責任：

- current hypotheses
- counter-hypotheses
- transition／action-effect
- world／state／goal／hazard model
- procedure
- failure signature
- rollback pointer
- open term
- decision rationale
- evidence／counter-evidence
- scope／applicability／confidence

Mは単なるログ配列ではない。

---

# 2. Package Architecture

推奨module構成：

```text
src/engineering_agi/
  core/
    types.py
    canonical.py
    errors.py
    identity.py
  l0/
    abi.py
    parser.py
    validator.py
    interpreter.py
    cost_model.py
    trace.py
  p/
    ir.py
    opcode_registry.py
    bundle.py
    compiler.py
    registry.py
    evaluator.py
  compute/
    representation.py
    retrieval.py
    model_set.py
    predictions.py
    candidates.py
    evidence_binding.py
  hds/
    frame.py
    gates.py
    judgement.py
    authorization.py
    attribution.py
    promotion.py
  memory/
    records.py
    query.py
    engine.py
    transaction.py
    consolidation.py
    backends.py
    checkpoint.py
  session/
    authority_state.py
    control_state.py
    cognitive_session.py
    episode.py
  ledger/
    events.py
    store.py
    replay.py
  adapters/
    base.py
    arc2.py
    arc3.py
  development/
    loop.py
    datasets.py
    evaluation.py
    release.py
  audit/
    claim_registry.py
    taint.py
    ablation.py
    conformance.py
```

現行`ARC-3-AGI-AGENT`へ段階導入する場合は、既存`generic_*` moduleを移行元とする。

---

# 3. 基本型

## 3.1 Observation

```python
@dataclass(frozen=True)
class DecisionObservation:
    observation_digest: str
    rendered_layers: tuple
    available_actions: tuple[int, ...]
    action_payload_schema: tuple
    terminal_state: str
    progress_count: int
    visible_effects: tuple[str, ...]
    resource_snapshot: "ResourceSnapshot"
```

禁止field：

- task_id
- game_id
- level_id
- replay_index
- answer_map
- source_state
- hidden_state
- orchestration order

## 3.2 OrchestrationMetadata

```python
@dataclass(frozen=True)
class OrchestrationMetadata:
    scorecard_id: Tainted[str]
    environment_id: Tainted[str]
    environment_index: Tainted[int]
    environment_handle: Tainted[object]
```

この型はrunner／adapter境界だけが受け取る。  
C／P／J／M APIへ渡してはならない。

## 3.3 ComputeRequest

```yaml
ComputeRequest:
  request_id: string
  frame_digest: string
  purpose: object
  goal_tokens: [string]
  observation_digest: string
  memory_version: integer
  memory_query: object
  constraints: object
  required_outputs: [string]
  forbidden_outputs: [string]
  resource_budget: object
  authority_capability: opaque
```

## 3.4 ComputeResult

```yaml
ComputeResult:
  request_id: string
  representation: object
  memory_citations: []
  model_set: []
  predictions: []
  candidates: []
  candidate_evidence_bindings: []
  memory_mutation_proposals: []
  next_observation_proposals: []
  unresolved_terms: []
  stages: []
  uncertainty_ppm: integer
  content_digest: string
```

## 3.5 HDSDecision

```yaml
HDSDecision:
  decision_id: string
  frame_digest: string
  compute_result_digest: string
  assertion_state: PASS | SUSPEND | FAIL
  operation_state: EXECUTE | PROBE | REOBSERVE | HOLD | ROLLBACK | STOP
  adoption_state: ACTIVE | PROBATION | QUARANTINE | REJECTED
  evidence_state: object
  closure_state: object
  selected_candidate_id: string | null
  held_candidate_ids: []
  rejected_candidate_ids: []
  gate_results: []
  reasons: []
  required_information: []
  next_question: string
  next_observation: string
  stop_condition: string
  memory_update_authorized: boolean
  external_action_authorized: boolean
  content_digest: string
```

---

# 4. State Ownership

## 4.1 AuthorityState

```python
@dataclass
class AuthorityState:
    session_nonce: bytes
    issued_compute: dict[str, Capability]
    issued_action: dict[str, Capability]
    issued_memory: dict[str, Capability]
    issued_rollback: dict[str, Capability]
    consumed_capabilities: set[str]
```

規則：

- capabilityはsingle-use
- observation／candidate／decision／memory versionへcontent binding
- live tokenをserializeしない
- restart後は新token
- 旧capabilityは再利用不可
- 過去authorizationはledger上の監査記録

## 4.2 ControlState

```python
@dataclass
class ControlState:
    cycle_index: int
    remaining_budget: int
    no_progress_count: int
    current_phase: str
    current_question: str
    stop_condition: str
    episode_handle: str
    level_handle: str
```

ControlStateはworld knowledgeの正本ではない。

## 4.3 SemanticMemory

学習された世界知識はSemanticMemoryを正本とする。  
Jのprivate fieldへ次を保持してはならない。

- learned action semantics
- selector delta
- value action class
- transition rule
- hazard association
- goal model

---

# 5. CognitiveSession

## 5.1 型

```python
@dataclass
class CognitiveSession:
    session_id: str
    mode: RuntimeMode
    runtime_identity: RuntimeIdentity
    authority: AuthorityState
    control: ControlState
    memory: SemanticMemory
    ledger: ExperienceLedger
    p_bundle: PBundle
    hds_config: HDSConfiguration
    resource_contract: ResourceContract
    identity_boundary: IdentityBoundary
```

## 5.2 Lifecycle

```text
create session
→ verify RuntimeIdentity
→ load frozen P / J₀ / M₀
→ issue process-local authority
→ begin episode transaction
→ run cycle / level
→ consolidate or rollback
→ next episode
→ finalize ledger / report
→ close session
```

## 5.3 Runtime injection

RuntimeはP、J、M、authorityを内部生成しない。

```python
GenericAGIRuntime(
    environment=DecisionEnvironment(...),
    session=session,
    episode=episode_handle,
)
```

## 5.4 Scorecard scope

ARC3 Competitionでは一scorecardにつき一CognitiveSessionとする。

- environmentごとにnew runtime objectを生成してもよい
- P／J config／M／ledger／authority lineageはsession共有
- cross-game semantic promotionはEvidence Binding・transaction・negative transfer control完了後だけ有効化

---

# 6. Memory Engine

## 6.1 Regions

```text
SEALED
SESSION_GLOBAL
EPISODE_OVERLAY
LEVEL_OVERLAY
WORKING
ARCHIVE
```

## 6.2 MemoryRecord

```yaml
MemoryRecord:
  record_id: string
  record_version: integer
  kind: string
  state: ACTIVE | PROBATION | SUSPENDED | ARCHIVED | SEALED
  scope_class: string
  statement: string
  semantic_tokens: []
  relations: []
  preconditions: []
  predicted_effects: []
  applicability: object
  evidence_event_ids: []
  counter_evidence_event_ids: []
  support_count: integer
  contradiction_count: integer
  hazard_count: integer
  confidence_ppm: integer
  falsification_condition: object
  created_version: integer
  updated_version: integer
  rollback_pointer: integer
  provenance_digest: string
  content_digest: string
```

## 6.3 Kind

```text
PURPOSE_BOUNDARY
HYPOTHESIS
COUNTER_HYPOTHESIS
CONTRADICTION
FAILURE_SIGNATURE
PROCEDURE_CAPABILITY
WORLD_MODEL
STATE_MODEL
TRANSITION_RULE
ACTION_EFFECT
GOAL_MODEL
HAZARD_MODEL
OBJECT_SCHEMA
RELATION_SCHEMA
EXPLORATION_POLICY
DECISION_RATIONALE
OPEN_TERM
ROLLBACK_POINTER
```

## 6.4 Transaction

mutationはlive objectへ直接適用しない。

```text
1. expected version verify
2. immutable next imageをprepare
3. schema／budget／authority／invariant validate
4. event + next image + receiptをatomic commit
5. commit成功後だけlive pointer swap
```

backend failure時は、

```text
live version
live digest
active records
archive
```

が一切変わらない。

## 6.5 Event Source

Experience Event Ledgerを履歴正本とする。

```yaml
ExperienceEvent:
  event_id: string
  session_id: string
  episode_handle: string
  cycle_index: integer
  event_type: string
  observation_before_digest: string | null
  action_digest: string | null
  observation_after_digest: string | null
  attribution_digest: string | null
  decision_digest: string
  proposal_digest: string | null
  authorization_digest: string | null
  old_memory_version: integer
  new_memory_version: integer
  content_digest: string
```

snapshotはcacheであり、ledgerから再構築可能でなければならない。

## 6.6 Episode overlay

```text
SESSION_GLOBAL base
→ begin EPISODE_OVERLAY
→ cycle writes
→ level consolidation
→ game result
   ├ PASS / validated → selected recordsだけSESSION_GLOBALへcommit
   └ FAIL / exception → overlay rollback
```

失敗episodeの暫定知識を後続environmentへ漏らさない。

---

# 7. Candidate-specific Evidence Binding

## 7.1 EvidenceBindingKey

```yaml
EvidenceBindingKey:
  normalized_state_pattern: string
  action_relation: string
  preconditions: []
  predicted_effects: []
  applicability_scope: object
  representation_version: string
  content_digest: string
```

## 7.2 CandidateEvidenceBinding

```yaml
CandidateEvidenceBinding:
  candidate_id: string
  binding_key: object
  cited_record_ids: []
  exact_support_ids: []
  probation_support_ids: []
  contradiction_ids: []
  hazard_ids: []
  support_count: integer
  contradiction_count: integer
  reproduced: boolean
  applicability_passed: boolean
  content_digest: string
```

## 7.3 Reproduced predicate

```text
reproduced(candidate)
=
candidate-bound record exists
AND precondition applicable
AND action relation matches
AND predicted effect matches
AND minimum repeated support satisfied
AND contradiction threshold not exceeded
AND exact hazard veto absent
```

無関係なM recordが一件あるだけで`reproduced=True`にしてはならない。

## 7.4 Operation selection

```text
exact hazard evidence
→ VETO / SUSPEND / alternative probe

insufficient evidence
→ reversible low-risk probe

candidate-specific reproduced evidence
→ EXECUTE候補

unclosed contradiction
→ REOBSERVE / SUSPEND
```

---

# 8. Retrieval

## 8.1 Tier

```text
Tier 0: exact episode-local state／relation
Tier 1: normalized role／topology／action surface
Tier 2: causal precondition／transition／effect
Tier 3: structural semantic similarity
```

Tier 3だけでEXECUTEを確定しない。

## 8.2 Scoring

```text
score
=
relevance
+ scope fitness
+ applicability
+ verified support
+ causal utility
+ recency
- contradiction
- hazard
- stale penalty
- negative-transfer penalty
```

## 8.3 Archive

ARCHIVEは明示要求なしにretrievalへ混入させない。

---

# 9. P-IR／L₀ ABI

## 9.1 原則

representationを固定Python codeへ閉じ込めず、固定Interpreter上で交換可能なP-IRへ置く。

```text
Observation
→ P-IR Representation Graph
→ State／Relation Model
→ Prediction
→ Candidate
```

## 9.2 PIRProgram

```yaml
PIRProgram:
  pir_version: string
  abi_version: string
  input_types: []
  representation_graph: object
  model_graph: object
  candidate_graph: object
  parameter_refs: []
  resource_manifest: object
  provenance: object
  logical_digest: string
```

## 9.3 Type system

```text
Grid
Cell
CellSet
Region
Object
ObjectSet
RelationGraph
State
Action
ActionPayload
Effect
Goal
Hazard
Boolean
Scalar
Sequence
```

## 9.4 Opcode classes

### Representation

```text
COMPONENT_EXTRACT
COLOR_PARTITION
REGION_PARTITION
TOPOLOGY_BUILD
TEMPORAL_DIFF
OBJECT_TRACK
ROLE_NORMALIZE
TRANSFORM_INVARIANT
```

### Model

```text
STATE
PRECONDITION
EFFECT
DELAY
TRANSITION
HAZARD
GOAL
COMPOSE
NEGATE
COUNTER_MODEL
```

### Candidate

```text
LEGAL_ACTION_BIND
DYNAMIC_COORDINATE_BIND
INFORMATION_PROBE
SEQUENCE_PLAN
ROLLBACK_PLAN
STOP_PROPOSAL
```

## 9.5 禁止

- eval
- exec
- arbitrary import
- filesystem I/O
- network
- subprocess
- runtime package mutation
- unknown opcode silently ignore

## 9.6 ABI

```text
interpreter_version
PIR schema version
opcode registry digest
type system digest
resource cost model digest
serialization version
```

不一致はfail closed。

---

# 10. P Bundle

```text
PBundle/
  manifest.json
  program.json
  parameters/
  compiler_report.json
  evaluation_report.json
  promotion_report.json
```

manifest：

```text
p_version
parent_p_digest
logical_digest
physical_package_digest
pir_digest
parameter_logical_digest
compiler_digest
evidence_digest
code_compatibility
created_from_ledger_digest
created_from_memory_version
identity_free
deterministic_seed
promotion_decision_digest
rollback_target
```

## 10.1 Canonicalization

- JSON key order
- Unicode NFC
- float normalization
- tensor dtype／endian／shape固定
- tensor name order固定
- NaN／Inf禁止
- archive entry order固定
- timestamp normalized
- logical digestとpackage byte digestを分離

---

# 11. Version Learning

## 11.1 入力

- DEVELOPMENT_TRAIN ledger
- M_dev active／probation／archive
- failure signatures
- HDS蒸留済みstatic assets
- explicit evidence selection
- current P
- current J₀／M₀
- compiler version

## 11.2 Candidate

候補はactive artifactから隔離する。

```text
active VersionBundle
→ compile isolated candidate
→ DEVELOPMENT_VALIDATION
→ compare
→ HDS promotion / rollback
```

## 11.3 Promotion priority

```text
task completion
level completion
true progress
crash / invalid action / identity leak
action efficiency
resource use
```

## 11.4 禁止

- LOCKED_FINALを反復promotionへ利用
- official private resultをblind finalのまま再利用
- candidate自身のself-promotion
- rejected candidateによるactive mutation
- action biasだけをP学習完成と呼ぶ

---

# 12. HDS蒸留pipeline境界

HDS蒸留は別repository／別artifactとして実装する。

入力：

- 正解付きARC2教師素材
- 検証済みARC3 teacher trajectory

出力：

- HDSCausalRecord
- HypothesisIR
- RuleAtom
- RuleFamily
- BoundaryRecord
- CounterexampleRecord
- FailureSignature
- CoverageReport
- FrozenArtifactManifest

現時点では、

```text
Distillation Output
→ P Compiler Input
```

の正式ABIは未固定である。

したがって、蒸留pipeline実装中にAGI runtimeへ接続してはならない。  
蒸留成果物freeze後に、別仕様でP-IR変換・採否・回帰条件を固定する。

---

# 13. Runtime State Machine

```text
BOOT
→ VERIFY_RUNTIME_IDENTITY
→ INITIALIZE_SESSION
→ BEGIN_EPISODE
→ OBSERVE
→ FRAME
→ RETRIEVE
→ COMPUTE
→ JUDGE
   ├ SUSPEND
   ├ STOP
   ├ REOBSERVE
   ├ ROLLBACK
   ├ PROBE
   └ EXECUTE
→ EMIT_AUTHORIZED_ACTION
→ OBSERVE_RESULT
→ ATTRIBUTE
→ STAGE_MEMORY_BATCH
→ AUTHORIZE_MEMORY
→ ATOMIC_COMMIT
→ NEXT_QUESTION
→ LOOP
→ CONSOLIDATE_OR_ROLLBACK_EPISODE
→ FINALIZE
```

停止状態：

```text
GOAL_REACHED
SUSPEND_UNCLOSED
SUSPEND_INSUFFICIENT_EVIDENCE
STOP_RISK_BOUNDARY
STOP_OWNER_BOUNDARY
ROLLBACK_REQUIRED
RESOURCE_LIMIT
SYSTEM_FAULT
```

停止できないloopは自律ではなく暴走。

---

# 14. Development State Machine

```text
FREEZE_INPUTS
→ RUN_ACTIVE_VERSION
→ APPEND_LEDGER
→ UPDATE_M_DEV
→ CLUSTER_FAILURES
→ HDS_DISTILL / CONSOLIDATE
→ COMPILE_VERSION_CANDIDATE
→ DEVELOPMENT_VALIDATION
→ HDS_PROMOTE_OR_ROLLBACK
→ REGRESSION
→ FREEZE_NEXT_VERSION
```

Code変更：

```text
Owner instruction
→ Codex branch
→ implementation
→ test
→ audit
→ Owner commit/adoption
```

runtime自身によるCode self-rewriteは含めない。

---

# 15. Evaluation Governance

role：

```text
DEVELOPMENT_TRAIN
DEVELOPMENT_VALIDATION
CV_HOLDOUT
LOCKED_FINAL
OFFICIAL_PUBLIC
OFFICIAL_PRIVATE
```

## 15.1 Cross-validation

foldごとに別RuntimeIdentityを作る。

```text
CV result
= development procedure evidence
≠ one single artifact completion
```

## 15.2 Locked Final

- evaluator内容を開発に使用しない
- freeze前にcontract／digestのみ固定
- 一RuntimeIdentity
- 一回実行
- 結果開示後はCONSUMED
- 結果を開発へ使えばfinal資格喪失

---

# 16. Identity／Taint

許可：

- 現在renderから動的導出した座標
- 現在available actions
- episode-local exact digest
- audit-only identity mapping

禁止：

- game IDによる検索・ranking・action
- game order
- opaque tokenをsemantic feature化
- replay index
- answer map
- fixed action sequence
- pre-recorded coordinate table
- exact public state digestのP化
- source／hidden state

監査：

- static type boundary
- serialized decision input
- taint propagation
- identity permutation
- game order permutation
- metadata replacement
- source dependency
- P compiler evidence audit

---

# 17. Resource Contract

```yaml
ResourceContract:
  max_cycles: integer
  max_actions: integer
  max_wall_seconds: integer
  max_api_silence_seconds: integer
  max_memory_records: integer
  max_memory_bytes: integer
  max_checkpoint_bytes: integer
  max_query_citations: integer
  max_pir_cost: integer
  max_llm_calls: integer
  graceful_stop_margin_seconds: integer
```

超過時はbounded SUSPEND／STOP。

---

# 18. Artifact Contract

全report：

```text
schema_version
spec_version
code_commit
code_tree_digest
runtime_identity
l0_abi_version
p_logical_digest
j_implementation_digest
j_config_digest
m0_logical_digest
adapter_digest
dependency_lock_digest
session_id
authority_lineage_digest
control_lineage_digest
memory_initial_version
memory_final_version
ledger_digest
input_manifest_digest
resource_contract_digest
status
failed_requirement_ids
content_digest
raw_evidence_pointers
```

completion report：

```text
completed_task_count
completed_level_count
failed_task_count
identity_leak_count
fallback_count
memory_causal_witness_count
p_learning_witness_count
sealed_evaluator_digest
official_scope
official_score
official_submission_ref
```

---

# 19. Acceptance Registry

## 19.1 Structure

- `STR-001`：C／J／M責任重複0
- `STR-002`：PとM分離
- `STR-003`：action／memory commitはJ authority必須
- `STR-004`：RuntimeIdentity追跡可能
- `STR-005`：fallback 0

## 19.2 Evidence

- `EVD-001`：candidate固有M binding
- `EVD-002`：precondition／effect／scope一致
- `EVD-003`：hazard exact-match veto
- `EVD-004`：probation evidenceはprobeのみ
- `EVD-005`：binding trace保存

## 19.3 Memory

- `MEM-001`：prepare中live state不変
- `MEM-002`：event／image／receipt atomic
- `MEM-003`：failure時digest不変
- `MEM-004`：episode overlay rollback
- `MEM-005`：ledgerから復元
- `MEM-006`：M ablationで行動差消失
- `MEM-007`：cross-game promotionは条件完了後

## 19.4 P-IR

- `PIR-001`：fixed L₀上でrepresentation交換
- `PIR-002`：typed IR
- `PIR-003`：unknown opcode reject
- `PIR-004`：resource validate
- `PIR-005`：ABI mismatch fail closed
- `PIR-006`：deterministic logical digest

## 19.5 Learning

- `LRN-001`：M／Ledgerからisolated candidate
- `LRN-002`：validation-only promotion
- `LRN-003`：promoted bundleからrestart
- `LRN-004`：rejected candidateでactive不変
- `LRN-005`：HDS蒸留assetのprovenance保持

## 19.6 Autonomy

- `AUT-001`：上位目的だけで複数cycle
- `AUT-002`：counter-hypothesis
- `AUT-003`：probe／execute分離
- `AUT-004`：memory causal witness
- `AUT-005`：正当なSUSPEND／STOP
- `AUT-006`：locked evaluator完遂

## 19.7 Official

- `OFF-001`：one scorecard／one session
- `OFF-002`：one environment one make
- `OFF-003`：exact artifact digest
- `OFF-004`：output bytes > 0
- `OFF-005`：score returned
- `OFF-006`：Public／Private／Full分離
- `OFF-007`：same RuntimeIdentity

一件でもblocking `PASS`以外なら完成claimを出さない。

---

# 20. Current Repository Mapping

| 現行module | 扱い |
|---|---|
| `generic_compute.py` | C／L₀原型。P-IR化・Evidence Binding強化 |
| `generic_hds.py` | J原型。証拠結合bug修正、learned stateをMへ移行 |
| `generic_memory.py` | M原型。immutable staging／event source／atomic backendへ置換 |
| `generic_runtime.py` | loop原型。CognitiveSession注入へ変更 |
| `generic_learning.py` | version loop原型。action biasからP compiler v2へ拡張 |
| `generic_competition_runner.py` | sequential lifecycle原型。一scorecard一session化 |
| `generic_agi_agent.py` | adapter原型。per-game P／M生成廃止 |
| S5／Teacher | historical regression／teacher materialのみ。active fallback禁止 |

---

# 21. Implementation Order

```text
1. Claim／Code Boundary／State Ownershipを正本化
2. CognitiveSession container
3. Evidence Binding修正
4. Episode overlay
5. Atomic Event-Sourced Memory
6. Typed Causal Memory
7. P-IR／L₀ ABI
8. P Compiler／Version Bundle
9. Governed Development Loop
10. HDS蒸留pipelineを別途実装
11. 蒸留→P接続仕様
12. Locked single-artifact evaluation
13. Official packaging／submission
```

HDS蒸留は独立parallel trackとして進められるが、Runtimeへの接続は第11段階まで禁止する。

---

# 22. 完成判定

```text
THEORY_DEFINED
≠
AGI_COMPLETED
```

```text
STRUCTURAL_READY
≠
AUTONOMOUS_COMPLETE
```

```text
KNOWN_SAMPLE_REGRESSION
≠
GENERICITY
```

```text
MEMORY_CAUSAL
+ P_VERSION_LEARNING_CAUSAL
+ SEALED_SINGLE_ARTIFACT_COMPLETE
+ COMPETITION_READY
+ OFFICIAL_FULL_COMPLETE
=
ARC実証上の工学的AGI完成条件
```

---

# 23. 最終結論

本実装は、生命体の自己成立様式を完全複製しない。

実装対象は、

> **Code／P／Jが固定された実行中でも、Mを因果的に更新し、次の問い・判断・行動を自ら変え、未知課題を完遂できるRuntime。**

そのRuntimeを成長させる外側には、

> **OwnerをMeta-J、CodexをMeta-C、RepositoryをMeta-Mとする開発Meta-Trinity。**

が存在する。

現在はこの二層を明示的に分離し、各層の責任・証拠・完成claimを個別に閉じる。
