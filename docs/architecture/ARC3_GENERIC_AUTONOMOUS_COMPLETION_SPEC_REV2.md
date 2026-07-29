# ARC3 汎用自律完遂主体 実装仕様書 rev2

- 仕様ID: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- 対象リポジトリ: `gatchimuchio/ARC-3-AGI-AGENT`
- 基準commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- 上位原理: `AGI_Trinity_Blueprint_v0_1` / `HDSフレーム_rev3.1a`
- 監査正本: `ARC3_汎用自律完遂主体_rev1再監査報告_rev2.md`
- 仕様状態: `DESIGN_CLOSED_FOR_PHASED_IMPLEMENTATION`
- 実装許可: P16からphase gate順に許可。並行着手は各phaseの非依存unitに限定
- 最上位目的: 未知のARC3環境を汎用自律主体が観測・学習・攻略し、公式評価をコンプリートする

---

## 0. 本仕様の固定結論

```text
Development
= mutable Code/L0
+ mutable P
+ mutable J implementation/configuration
+ permanent Experience Ledger
+ mutable persistent M_dev
+ HDS-controlled P/J0/M0 promotion

Competition
= frozen Code/L0
+ frozen P
+ frozen J implementation/configuration
+ process-local AuthorityState
+ mutable ControlState
+ mutable scorecard-scoped M_session
```

```text
C = Execute(Fixed_L0_Interpreter, P_IR)

Autonomous Runtime
= Trinity(C, J_hds, M)
+ AuthorityState
+ ControlState
+ Environment Adapter
```

固定Codeだけでは動的適応しない。固定Codeと固定Pへ可変Mを接続し、M更新が未来の計算・判断・行動を変えることで、公式評価中の動的適応を成立させる。

開発中は、経験をMへ蓄積し、安定構造をP/J0/M0へ再コンパイルする。Code自体も外部開発作業として更新できる。

---

## 1. 最上位目的と非目的

## 1.1 目的

> 未知のARC3環境を自ら観測し、操作意味、状態変数、因果関係、成功条件、危険条件を推定し、複数仮説と反対仮説を形成し、情報獲得行動を選択し、結果を記憶へ反映し、判断を更新しながら、公式評価環境を最後まで完遂する同一の汎用自律主体を開発する。

完成式:

```text
ARC3_AUTONOMOUS_COMPLETION
=
SAME_RUNTIME_ARTIFACT
AND AUTONOMOUS_CLOSED_LOOP
AND CANDIDATE_SPECIFIC_EVIDENCE
AND MEMORY_CAUSALITY
AND DEVELOPMENT_P_LEARNING
AND IDENTITY_FLOW_CONFORMANCE
AND SEALED_SINGLE_ARTIFACT_EVIDENCE
AND COMPETITION_SESSION_INTEGRITY
AND OFFICIAL_FULL_COMPLETE
```

## 1.2 非目的

次は本プロジェクトの完成ではない。

- 既知公開問題の正解軌道再生
- task/game/level別ルータ
- replay index参照
- answer map参照
- source / hidden state参照
- 既知trajectoryを圧縮しただけのMLP
- C/J/M/Pの形式的存在だけの証明
- synthetic環境での一部progress
- crashしないだけのagent
- 別runtimeの攻略能力と構造適合の合算
- 公開Leaderboard半分だけの100%をfull official completionと呼ぶこと

---

## 2. claim hierarchy

| Claim ID | 意味 | 完成扱い |
|---|---|---:|
| `STRUCTURAL_READY` | C/J/M/P、権限、traceが実装済み | しない |
| `KNOWN_PUBLIC_REGRESSION` | 公開25ゲーム・183levelの既知回帰 | しない |
| `MEMORY_CAUSAL` | Mだけの差で未来の計算・判断・行動が変わる | しない |
| `P_VERSION_LEARNING_CAUSAL` | 経験からP候補を生成・評価・昇格し再起動利用できる | しない |
| `CV_PROCEDURE_EVIDENCE` | 複数fold artifactによる開発手順の補助証拠 | しない |
| `TRANSFORMATION_STRESS_PASS` | 定義済み変換環境を完遂 | しない |
| `SEALED_SINGLE_ARTIFACT_COMPLETE` | 一つの固定artifactが一回限りのlocked evaluatorを完遂 | 中間証拠 |
| `COMPETITION_READY` | 公式lifecycle、資源、package、session Mが成立 | しない |
| `OFFICIAL_RUN_ACCEPTED` | exact artifactの公式runがCOMPLETEしscoreを返した | しない |
| `OFFICIAL_PUBLIC_COMPLETE` | Public scopeが100% | 部分完成 |
| `OFFICIAL_PRIVATE_COMPLETE` | Private scopeが100% | 部分完成 |
| `OFFICIAL_FULL_COMPLETE` | 同一artifactでfull official scopeが100% | 最終完成 |

`AGIがARC3を閉包した`という主張は`OFFICIAL_FULL_COMPLETE`まで禁止する。

---

## 3. 用語と状態所有

## 3.1 Code / L0

固定実行機構。次を所有する。

- P-IR parser / validator
- 型検査
- resource cost検査
- P-IR interpreter
- environment I/O adapter
- HDS承認済み副作用のmechanical execution
- deterministic trace

Codeは知識・能力・個別解法を直接保持しない。必要な計算規則はP-IRへ置く。

## 3.2 P

Layer-0が実行する命令形保持体。

保持対象:

- representation program
- state construction
- object/relation schema
- transition model
- precondition
- goal/hazard model
- exploration procedure
- composition procedure
- action/effect model
- candidate scoring
- parameter tensors

Pは最終採否、M commit、external emit、authority発行を行わない。

## 3.3 C

```text
C_t = Execute(L0, P^v, Observation_t, ComputeRequest_t, MemoryCitations_t)
```

出力:

- representation
- hypotheses
- counter-hypotheses
- predictions
- candidate proposals
- evidence bindings
- memory mutation proposals
- next-observation proposals
- uncertainty

Cは自分の提案を最終採用しない。

## 3.4 J / HDS

唯一の裁定主体。

- purpose / value / risk / X / R / Mcの確定
- compute command発行
- candidate採否
- probe / execute / reobserve / suspend / stop / rollback
- memory mutation authorization
- episode consolidation authorization
- development P/J0/M0 promotion authorization
- external action authorization

Jは仮説生成、実記憶write、environment stepを直接行わない。

## 3.5 SemanticMemory M

HDSが引用する現行判断根拠。

- 追記専用ではない
- active / overlay / archive / sealedを持つ
- versioned
- provenance付き
- rollback可能
- HDS authorizationなしにcommit不可

## 3.6 Experience Ledger

改変しない事実台帳。

- raw observation
- normalized observation
- compute request/result
- candidate
- HDS decision
- authorization
- action/result
- attribution
- memory proposal/receipt
- P/J0/M0 version
- resource measurement
- system failure

Experience LedgerはMの代替ではない。判断へ自動引用しない。

## 3.7 AuthorityState

process-local capability state。

- live session nonce
- issued capability
- consumed capability
- idempotency state

live tokenは永続化しない。restart時は再発行する。過去authorizationはLedgerの監査recordとしてのみ保持する。

## 3.8 ControlState

実行制御状態。

- cycle index
- current level/episode handle
- remaining action/time budget
- no-progress count
- next question
- pending probe
- stop boundary

ControlStateはSemanticMemoryではない。必要ならsession checkpointへ保存できるが、世界知識として検索しない。

## 3.9 CognitiveSession

一run / 一scorecardの主体同一性を束縛するcontainer。

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

---

## 4. 実行モードと可変性

```text
DEVELOPMENT
VALIDATION
LOCKED_FINAL
COMPETITION
```

| 要素 | DEVELOPMENT | VALIDATION | LOCKED_FINAL | COMPETITION |
|---|---:|---:|---:|---:|
| Code/L0 | 外部開発で可変 | 固定 | 固定 | 固定 |
| P | candidate生成・promotion可 | 固定 | 固定 | 固定 |
| J実装/config | 外部開発で可変 | 固定 | 固定 | 固定 |
| AuthorityState | runごと可変 | runごと可変 | runごと可変 | scorecard内可変 |
| ControlState | 可変 | 可変 | 可変 | 可変 |
| M | 永続M_dev | session | locked run | scorecard session |
| Experience Ledger | 永続 | 保存可 | sealed保存 | session内保存 |
| P online update | 禁止 | 禁止 | 禁止 | 禁止 |
| 開発結果の再利用 | 可 | 可 | 実行後はfinal証拠として再利用不可 | 次版開発信号には可 |

Code/P/Jが固定とは、実装artifactをrun中に変更しないことを意味する。AuthorityState、ControlState、Mまで固定する意味ではない。

---

## 5. Identity / taint boundary

## 5.1 型分離

```python
@dataclass(frozen=True)
class OrchestrationMetadata:
    scorecard_id: Tainted[str]
    game_id: Tainted[str]
    game_index: Tainted[int]
    environment_handle: Tainted[object]

@dataclass(frozen=True)
class DecisionObservation:
    rendered_layers: ...
    available_actions: ...
    action_payload_schema: ...
    terminal_state: ...
    progress_count: ...
    visible_effects: ...
```

`OrchestrationMetadata`はrunner/adapter境界だけが受け取る。C/P/J/Mのpublic APIは当該型を受け取れない。

## 5.2 許可と禁止

### 許可

- 現在renderから動的に導出した`x, y`
- 現在available action ID
- episode-local exact observation digest
- audit mapping内のgame ID
- evidence independenceを数える非検索用episode nonce

### 禁止

- game/task/level IDによるP/M検索・candidate ranking・action選択
- game orderによるルーティング
- replay index
- answer map
- 固定action sequence
- 事前記録されたgame固有座標表
- trajectory由来の座標列
- source/hidden state
- exact public frame digestのPまたはSESSION_GLOBAL key化
- opaque episode tokenをsemantic featureへ含めること

## 5.3 exact state digestのscope

- `WORKING` / `LEVEL_OVERLAY` / `EPISODE_OVERLAY`: 使用可
- `SESSION_GLOBAL`: normalized causal patternへ変換後のみ
- `P`: exact observation signature禁止

## 5.4 identity監査

文字列scanだけではPASSにしない。

- static type boundary
- serialized decision input inspection
- taint propagation test
- game order permutation
- metadata permutation
- action surface perturbation
- exact frame replacement
- source dependency audit
- P compiler evidence audit

を実行する。

---

## 6. RuntimeIdentityと同一主体

```text
RuntimeIdentity
=
code_tree_digest
+ l0_abi_version
+ p_logical_digest
+ j_implementation_digest
+ j_config_digest
+ m0_logical_digest
+ adapter_digest
+ dependency_lock_digest
```

次を全て満たす場合だけ一つの同一主体とする。

1. 同一RuntimeIdentity
2. 同一package
3. 同一L0 interpreter
4. 同一P logical digest
5. 同一J implementation/config
6. 同一M schema/engine
7. S5/Teacher/game-specific fallback 0
8. traceに全digestとsession lineageがある

5-foldの各Pは別RuntimeIdentityである。CV結果は同一主体完成claimに合算しない。

---

## 7. CognitiveSession lifecycle

## 7.1 scorecard lifecycle

```text
open scorecard
→ create one CognitiveSession
→ load frozen P/J0/M0
→ issue new process-local authority token
→ for each environment sequentially:
     begin episode transaction
     run levels
     consolidate or rollback episode
→ close scorecard
→ finalize session report
→ destroy M_session if COMPETITION
```

## 7.2 runtime injection

`GenericAGIRuntime`はM、P、J、authorityを内部新規作成してはならない。

```python
GenericAGIRuntime(
    environment=DecisionEnvironment,
    session=CognitiveSession,
    episode_handle=EpisodeHandle,
)
```

## 7.3 cross-game enablement

- P17-A: 同一session objectとlineageだけ成立。cross-game semantic promotionはOFF
- P17-B: candidate-specific evidence bindingとepisode rollbackを成立
- P19 PASS後: cross-game semantic promotionをON

---

## 8. Memory architecture

## 8.1 正本

Experience Event Ledgerを唯一の履歴正本とする。Memory snapshotは再構成を高速化するcacheであり、ledgerと矛盾した場合は破棄して再構成する。

## 8.2 memory regions

```text
SEALED
SESSION_GLOBAL
EPISODE_OVERLAY
LEVEL_OVERLAY
WORKING
ARCHIVE
```

### SEALED

目的、権限、禁止境界。run中変更不可。

### SESSION_GLOBAL

scorecard全体で再利用可能な、検証・consolidation済みのnormalized knowledge。

### EPISODE_OVERLAY

game内で有効。game完了前はSESSION_GLOBALへ直接影響しない。

### LEVEL_OVERLAY

level内の試行・仮説・failure。level成功時にEPISODEへ選別commit、level failure/reset時はrollback可能。

### WORKING

cycle local。active authorityではない。

### ARCHIVE

失効、置換、旧版。自動検索しない。

## 8.3 record schema

```text
record_id
schema_version
kind
state
scope_class
binding_key
statement
semantic_tokens
relations
precondition_program_digest
predicted_effect_program_digest
delay_window
applicability_predicates
evidence_event_ids
counter_evidence_event_ids
support_group_ids
contradiction_group_ids
hazard_group_ids
no_effect_group_ids
support_count
contradiction_count
hazard_count
no_effect_count
distinct_episode_support
confidence_ppm
execute_eligibility
probe_eligibility
falsification_condition
created_version
updated_version
rollback_pointer
provenance_digest
usage_count
last_verified_cycle
payload
```

## 8.4 kind

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

## 8.5 record ID

`current-hypothesis`等のglobal singleton IDは禁止する。

```text
record_id
= kind
+ normalized binding key digest
+ applicability scope digest
```

異なるprecondition・effect・scopeのrecordは別IDにする。

---

## 9. Candidate-specific Evidence Binding

## 9.1 EvidenceBindingKey

```python
@dataclass(frozen=True)
class EvidenceBindingKey:
    normalized_state_pattern_digest: str
    action_relation_digest: str
    precondition_digest: str
    predicted_effect_digest: str
    applicability_scope_digest: str
```

`action_relation_digest`はsurface ordinal単独で構成しない。

```text
current legal action
+ role/target binding
+ dynamic anchor class
+ observed/expected effect family
```

を含む。

## 9.2 CandidateEvidenceBinding

```python
@dataclass(frozen=True)
class CandidateEvidenceBinding:
    key: EvidenceBindingKey
    record_id: str
    record_digest: str
    match_tier: str
    precondition_match: bool
    effect_compatible: bool
    scope_applicable: bool
    support_count: int
    contradiction_count: int
    hazard_count: int
    confidence_ppm: int
    execute_eligible: bool
```

## 9.3 candidate provenance

候補は次を明示的に保持する。

```text
p_instruction_refs
representation_refs
prediction_refs
memory_binding_refs
counter_evidence_refs
runtime_version
```

memory citationはcandidateへ直接bindingする。compute result全体にcitationがあるだけでは不足する。

## 9.4 reproduced述語

```text
reproduced(candidate)
=
EXISTS binding IN candidate.evidence_bindings:
    binding.record_digest is in retrieved citations
    AND binding.precondition_match
    AND binding.effect_compatible
    AND binding.scope_applicable
    AND binding.execute_eligible
    AND binding.hazard_count == 0
    AND contradiction gate PASS
```

`has_any_memory_evidence`は採否に使用しない。

## 9.5 operation selection

```text
applicable hazard evidence
  → REJECT / ROLLBACK / alternative probe

execute-eligible reproduced evidence
  → EXECUTE candidate eligible

probation evidence only
  → BOUNDED_PROBE rankingへ使用可、EXECUTE根拠には不可

no applicable evidence
  → BOUNDED_PROBE
```

---

## 10. Causal record update semantics

## 10.1 evidence group

同じtransitionの重複traceを複数証拠として数えない。

```text
evidence_group_id
= normalized_before_pattern
+ action_relation
+ normalized_after_effect
+ temporal_window
+ non-search episode nonce
```

nonceは独立性計数にのみ使用し、retrieval/candidate featureには使わない。

## 10.2 fixed-point confidence

浮動小数の非決定性を避け、confidenceはppm整数で保持する。

```text
S = unique support groups
C = unique contradiction groups
H = unique hazard groups

confidence_ppm
= floor(1_000_000 * (1 + S) / (2 + S + C + 2H))
```

## 10.3 default EvidencePolicy

```text
local_min_support = 2
session_min_total_support = 3
session_min_distinct_episode_support = 2
active_confidence_ppm = 800_000
max_contradiction_ratio_ppm = 100_000
max_hazard_for_execute = 0
```

閾値はversioned HDS configに置く。run中変更しない。

## 10.4 state transition

```text
PROPOSED
  support = 0

PROBATION
  support >= 1
  but execute criteria未達

ACTIVE
  execute criteria達成

SUSPENDED
  hazard exact-match
  OR contradiction ratio超過
  OR applicability不明

REJECTED
  repeated contradictionで再利用不能

SUPERSEDED
  merge/replace済み

ARCHIVED
  現行引用対象外
```

## 10.5 localとsession global

- 一つのepisodeで2回再現: episode内EXECUTE根拠になり得る
- 一つのepisodeだけの知識: SESSION_GLOBALではPROBATION
- 2 episode以上で独立再現: SESSION_GLOBAL ACTIVE候補
- appearance変換だけの一致: causal precondition/effect一致を別途要求

## 10.6 failure

同一preconditionでのGAME_OVERは一件でもexact-match vetoに使える。ただし別scopeへ無限定一般化しない。

---

## 11. Tiered retrieval

```text
Tier 0: exact episode-local state/action relation
Tier 1: normalized role/topology/precondition
Tier 2: causal transition/effect/goal/hazard
Tier 3: semantic structural similarity
```

ranking:

```text
relevance
+ precondition fit
+ effect compatibility
+ scope fitness
+ support
+ confidence
+ recency
+ historical utility
- contradiction
- hazard
- stale penalty
```

Tier 3だけのmatchはprobe候補に限定する。

query resultはscoreだけでなく、各項目の分解、binding key、rejection reasonを返す。

---

## 12. Episode transaction

## 12.1 begin

```python
EpisodeTxn = session.memory.begin_episode(
    base_version=session.memory.version,
    episode_handle=non_searchable_handle,
)
```

## 12.2 level

- level開始時にLevelOverlay作成
- cycle mutationはLevelOverlayへcommit
- level progress/commit時にHDSがconsolidation proposalを審査
- level failure/reset時にsafe snapshotへrollback
- failure signatureは検証済み範囲だけEpisodeOverlayへ昇格可能

## 12.3 game

- final WIN: EpisodeOverlayからSESSION_GLOBAL候補を生成
- exception / timeout / unclosed failure: EpisodeOverlayをrollback
- raw eventsはLedgerに残す
- partial episode recordをSESSION_GLOBALへ直接残さない

## 12.4 negative-transfer controls

必須試験:

- game failure後にglobal M digestがpre-game safe digestへ戻る
- game順序permutationで性能が許容範囲内
- irrelevant prior episodeがcandidate rankingを変えない
- adversarial memory recordをJがveto
- negative transfer recordをSUSPEND/INVALIDATEできる

---

## 13. Atomic Memory Engine

## 13.1 source of truth

Event Ledgerを正本とする。

## 13.2 staging

```python
StagedTransition = memory.prepare_batch(
    expected_version=current_version,
    proposals=authorized_proposals,
)
```

prepare中にlive stateを変更しない。

検査:

- proposal schema
- authorization binding
- expected version
- duplicate idempotency key
- memory budget
- state invariants
- archive budget
- record validation
- taint boundary

## 13.3 atomic commit

```python
class MemoryBackend(Protocol):
    def commit(
        self,
        *,
        expected_version: int,
        event_batch: tuple[MemoryEvent, ...],
        next_image: MemoryImage,
        idempotency_key: str,
    ) -> CommitReceipt: ...
```

一transactionで次を行う。

1. expected version compare
2. event batch insert
3. state image/delta insert
4. receipt insert
5. commit

成功後だけlive memoryをnext imageへswapする。

## 13.4 backend

### InMemoryBackend

VALIDATION / LOCKED_FINAL / COMPETITION用。同じatomic contractを実装する。

### SQLiteEventBackend

DEVELOPMENT用。

- WAL
- foreign key ON
- transaction
- unique idempotency key
- schema version
- migration
- crash recovery
- content digest

## 13.5 checkpoint

versionごとのfull-copy snapshotは禁止する。

```text
Event Ledger
+ checkpoint every N events
+ retain K checkpoints
```

default:

```text
checkpoint_interval = 64 events
retained_checkpoints = 16
```

値はresource profileで調整する。

## 13.6 mutation batch priority

同一attributionの必須recordを一batchでcommitする。

priority例:

```text
1. FAILURE_SIGNATURE / ROLLBACK_POINTER
2. TRANSITION_RULE / ACTION_EFFECT
3. HYPOTHESIS / COUNTER / CONTRADICTION
4. WORLD_MODEL / GOAL / HAZARD
5. DECISION_RATIONALE / OPEN_TERM
```

budget不足で必須recordの一部だけcommitしてはならない。batch全体をSUSPENDする。

---

## 14. P-IR / L0 ABI

## 14.1 原則

Pがrepresentationを含む能力を獲得するには、固定Code/L0が実行可能な命令形IRが必要である。

任意Python生成、`eval`、dynamic import、filesystem/network I/Oは禁止する。

## 14.2 PIRProgram

```python
@dataclass(frozen=True)
class PIRProgram:
    schema_version: str
    l0_abi_version: str
    program_id: str
    representation_graph: TypedDAG
    model_graph: TypedDAG
    candidate_graph: TypedDAG
    parameter_manifest: ParameterManifest
    resource_manifest: PIRResourceManifest
    provenance: ProvenanceManifest
```

## 14.3 types

```text
Grid
GridHistory
GridDelta
Mask
RegionSet
ObjectSet
TrackSet
FeatureSet
RelationGraph
Representation
StateVector
Predicate
ActionSet
ActionBinding
EffectDistribution
GoalScore
HazardScore
UncertaintyScore
CandidateSet
ScalarI64
ScalarPPM
Bool
```

## 14.4 representation opcodes v1

| Opcode | 入力 | 出力 |
|---|---|---|
| `GRID_INPUT` | DecisionObservation | Grid |
| `HISTORY_INPUT` | bounded history | GridHistory |
| `TEMPORAL_DIFF` | GridHistory | GridDelta |
| `COLOR_PARTITION` | Grid | RegionSet |
| `REGION_PARTITION` | Grid | RegionSet |
| `CONNECTED_COMPONENTS` | Grid/Mask, connectivity | ObjectSet |
| `OBJECT_FEATURES` | ObjectSet | FeatureSet |
| `OBJECT_TRACK` | ObjectSet, GridHistory | TrackSet |
| `RELATION_GRAPH` | ObjectSet/TrackSet | RelationGraph |
| `ROLE_NORMALIZE` | ObjectSet, FeatureSet | ObjectSet |
| `TRANSFORM_CANONICALIZE` | ObjectSet, transform set | ObjectSet |
| `FEATURE_PROJECT` | typed inputs | Representation |

## 14.5 model opcodes v1

| Opcode | 入力 | 出力 |
|---|---|---|
| `STATE_BUILD` | Representation | StateVector |
| `PRECONDITION` | StateVector, parameter | Predicate |
| `TRANSITION` | StateVector, ActionBinding | EffectDistribution |
| `DELAY_MODEL` | EffectDistribution, history | EffectDistribution |
| `GOAL_MODEL` | StateVector/EffectDistribution | GoalScore |
| `HAZARD_MODEL` | StateVector/EffectDistribution | HazardScore |
| `COUNTER_MODEL` | model output | model output |
| `COMPOSE_MODEL` | model outputs | model output |
| `UNCERTAINTY_MODEL` | evidence/model | UncertaintyScore |

## 14.6 candidate opcodes v1

| Opcode | 入力 | 出力 |
|---|---|---|
| `ENUM_ACTIONS` | current legal action set | ActionSet |
| `BIND_ROLE` | ActionSet, ObjectSet | ActionBinding |
| `BIND_COORD_CURRENT_RENDER` | ActionBinding, current Grid | ActionBinding |
| `FILTER_PRECONDITION` | candidates, Predicate | CandidateSet |
| `SCORE_CANDIDATE` | model outputs | CandidateSet |
| `MAKE_PROBE` | uncertain candidates | CandidateSet |
| `TOPK` | CandidateSet, bounded k | CandidateSet |

`BIND_COORD_CURRENT_RENDER`は現在frameからのみ座標を導出する。事前座標表を受け取れない。

## 14.7 control semantics

- graphはacyclic
- bounded TOPK
- recursionなし
- unbounded loopなし
- node input/output type固定
- node順序はtopological + stable ID
- unknown opcode拒否
- unsupported ABI拒否
- resource costをcompile時とruntime時に検査

## 14.8 resource manifest

```text
max_nodes
max_tensor_bytes
max_objects
max_relations
max_candidates
max_memory_citations
worst_case_operation_cost
```

## 14.9 compatibility

```text
P.l0_abi_version == Runtime.supported_l0_abi_version
```

不一致はfail closed。Code変更でopcode/semanticsが変わる場合はABI versionを上げる。旧Pは明示migrationなしに使用しない。

---

## 15. P Bundleとdeterministic artifact

## 15.1 bundle

```text
PBundle/
  manifest.json
  program.json
  tensors/
  compiler_report.json
  evaluation_report.json
  promotion_report.json
```

## 15.2 logical digest

```text
p_logical_digest
= sha256(
    canonical program IR
    + ordered tensor logical digests
    + ABI version
    + compiler semantics version
)
```

## 15.3 tensor canonicalization

- allowed dtypeをmanifestで固定
- little-endian
- C contiguous
- tensor name昇順
- shape明示
- NaN / Inf禁止
- signed zero normalization方針固定
- raw canonical bytesからlogical digest

## 15.4 JSON canonicalization

- UTF-8
- key sort
- compact separator
- `allow_nan=False`
- integer / string / bool / null
- P-IRの確率・閾値は原則ppm整数

## 15.5 physical package digest

logical digestと別にZIP/wheel byte digestを保持する。

- entry order昇順
- timestamp固定
- permission固定
- compression method/level固定
- SOURCE_DATE_EPOCH固定

---

## 16. P compiler / version learning

## 16.1 入力

- DEVELOPMENT_TRAIN Ledger
- M_dev active/probation/archive
- explicit evidence selection manifest
- parent P
- current L0 ABI

## 16.2 出力

- symbolic P-IR candidate
- parametric tensor candidate
- hybrid candidate
- compiler report
- evidence digest
- taint report
- resource report

## 16.3 compiler対象

```text
representation pipeline
object/relation schema
state variables
preconditions
transition/effect/delay
goal/hazard
exploration policy
probe procedure
composition
candidate scoring
uncertainty
```

## 16.4 candidate isolation

candidate生成時にactive Pを変更しない。

```text
P_active
→ isolated P_candidate
→ validation
→ promotion or rollback
```

## 16.5 promotion metric

辞書順:

```text
1. completed environments
2. completed levels
3. true progress
4. crash / invalid action / identity leak
5. action efficiency
6. memory/resource cost
```

## 16.6 promotion gate

- DEVELOPMENT_VALIDATIONだけを使用
- LOCKED_FINALを使用しない
- known public regression非劣化
- blind dev-validation改善
- crash 0
- identity leak 0
- invalid action 0
- ABI compatible
- deterministic
- rollback targetあり

## 16.7 P/J0/M0 bundle

開発成果は次版initial stateへ再配線できる。

```text
InitialState^v
= P^v + J0^v + M0^v + Adapter^v
```

M0へexact public frame、game ID、answer、replayを含めない。

---

## 17. Development loop

```text
run
→ atomic ledger append
→ M_dev causal update
→ failure cluster / contradiction resolution
→ candidate compile trigger
→ P/J0/M0 candidate
→ DEVELOPMENT_VALIDATION
→ HDS promotion / rollback
→ code regression
→ next version
```

trigger:

```text
MANUAL
EVIDENCE_THRESHOLD
PHASE_END
FAILURE_CLUSTER
PLATEAU
DEV_VALIDATION_REGRESSION
```

`LOCKED_FINAL`結果をtriggerへ使わない。

Code更新は外部開発作業としてcommitへ固定する。自動自己改変は必要条件ではない。

---

## 18. Evaluation set governance

## 18.1 role registry

```text
DEVELOPMENT_TRAIN
DEVELOPMENT_VALIDATION
CV_HOLDOUT
LOCKED_FINAL
OFFICIAL_PUBLIC
OFFICIAL_PRIVATE
```

各dataset/evaluatorは、ID、digest、owner、access state、first access、consumed stateを台帳へ記録する。

## 18.2 public 25 games

- known regression
- development training
- development validation
- CV procedure evidence
- transformation stress

に使える。

公開25ゲームだけを最終未知汎用性証拠にしない。

## 18.3 cross-validation

foldごとに別P artifactを作る。

claim:

```text
CV_PROCEDURE_EVIDENCE
```

禁止claim:

```text
SAME_SINGLE_ARTIFACT_COMPLETE
```

## 18.4 LOCKED_FINAL

条件:

- evaluator内容・seed・mechanismをruntime開発側が未使用
- freeze前にevaluator digest/contractだけ固定
- one frozen RuntimeIdentity
- one execution
- result disclosure後は`CONSUMED`
- resultを開発へ使った時点でfinal証拠資格喪失

## 18.5 sealed evaluator最低要件

- runtime実装とは独立した生成・保管境界
- 複数状態表現
- temporal delay
- irreversible hazard
- multi-step mechanism composition
- single action反復だけでは解けない
- goal acquisition
- memory necessity
- rollback necessity
- source非参照
- full traceはevaluator側でcontent-boundに保持

---

## 19. 自律閉ループ

```text
OBSERVE
→ P-IR REPRESENT
→ FRAME
→ RETRIEVE candidate-specific M
→ MODEL SET
→ HYPOTHESES / COUNTER
→ ACTION / PROBE CANDIDATES
→ HDS JUDGMENT
→ ACT / PROBE / REOBSERVE / SUSPEND / STOP / ROLLBACK
→ REOBSERVE
→ ATTRIBUTE
→ STAGE MEMORY BATCH
→ HDS AUTHORIZE
→ ATOMIC COMMIT
→ NEXT QUESTION
→ NEXT CYCLE
```

未知状態では、証拠なしのEXECUTEを禁止する。可逆・低リスク・高情報のprobeを選ぶ。

停止できない循環は自律ではなく暴走と判定する。

---

## 20. Resource / official execution contract

## 20.1 ExternalExecutionContract

```text
contract_version
source_digest
competition_mode_required
one_scorecard
one_make_per_environment
inflight_score_forbidden
scorecard_idle_timeout_seconds
scorecard_max_open_seconds
notebook_runtime_limit_seconds
max_frame_size
coordinate_action_contract
```

公式source更新時はdigestを更新し、回帰を再実行する。

## 20.2 current verified values

- one scorecard
- one `make` per environment
- all available environments scored
- inflight score取得不可
- scorecard inactivity auto-close: 15分
- maximum scorecard open duration: 24時間
- private evaluation: 110 games、Public/Private半分ずつ
- max frame: 64×64
- ACTION6: dynamic `x, y`

## 20.3 timeout

未確認heartbeatへ依存しない。

```text
max_internal_silence
<= scorecard_idle_timeout - safety_margin
```

default safety margin: 300秒。

公式idle 900秒の場合、per-cycle hard timeoutは600秒以下とする。

- per-cycle timeout
- per-game timeout
- total scorecard timeout
- graceful SUSPEND/STOP
- close-scorecard reserve time

を設定する。

## 20.4 memory/resource bounds

- max active record
- max overlay record
- max archive record
- max event bytes
- max checkpoint bytes
- max query citations
- compaction threshold
- P-IR worst-case cost

を測定する。

---

## 21. Official completion predicates

## 21.1 accepted run

```text
OFFICIAL_RUN_ACCEPTED
=
submission_status == COMPLETE
AND output_bytes > 0
AND score_returned
AND exact_runtime_package_digest_verified
AND exact_p_logical_digest_verified
```

## 21.2 score normalization

score artifactはraw値、unit、scopeを保持する。

```text
raw_score
normalized_score_ppm
scope = PUBLIC_55 | PRIVATE_55 | FULL_110 | UNKNOWN
```

## 21.3 public/private/full

```text
OFFICIAL_PUBLIC_COMPLETE
=
OFFICIAL_RUN_ACCEPTED
AND scope == PUBLIC_55
AND normalized_score_ppm == 1_000_000
```

```text
OFFICIAL_PRIVATE_COMPLETE
=
exact same RuntimeIdentity / artifact
AND scope == PRIVATE_55
AND normalized_score_ppm == 1_000_000
```

```text
OFFICIAL_FULL_COMPLETE
=
(
  same artifact PUBLIC_55 == 100%
  AND same artifact PRIVATE_55 == 100%
)
OR
(
  organizer-exposed FULL_110 scope == 100%
)
```

100%の意味は公式methodologyに従い、全ゲーム・全level完遂かつ人間同等以上の効率である。

## 21.4 failure attribution

```text
trace witness available
→ specific Code/P/J/M/adapter/resource layerへ帰属可

scalar score only
→ AUDIT_INCONCLUSIVE_CAPABILITY_SHORTFALL
```

---

## 22. 現行リポジトリ変更仕様

## 22.1 preserve

- P0〜P9責任分離・除去監査
- P11/S5 historical known-sample baseline
- Generic C/J/M/P原型
- SemanticMemory mutation/authorization概念
- P candidate/promotion/rollback概念
- sequential competition runner

## 22.2 quarantine

- S5 active fallback
- Teacher/source/hidden/answer/replay runtime参照
- progress-only genericity PASS
- gameごとのM/P新規生成
- J private world-learning state
- global `has_memory_evidence`採否
- exact public frameのglobal/P lookup

## 22.3 change map

### `generic_types.py`

- typed DecisionContext
- EvidenceBindingKey
- CandidateEvidenceBinding
- typed candidate provenance
- taint-free APIs

### `generic_hds.py`

- global memory evidence logic削除
- candidate-specific reproduced
- AuthorityState / ControlState注入
- learned selector state削除
- episode/consolidation authorization

### `generic_compute.py`

- current fixed representation pathをP-IR interpreterへ移行
- candidate evidence binding
- tiered retrieval
- action relation key再設計

### `generic_memory.py`

- live direct mutation廃止
- staged immutable transition
- overlay
- typed causal record
- event-sourced backend contract
- bounded checkpoint

### `generic_runtime.py`

- CognitiveSession必須
- per-game M/J/P新規生成廃止
- level/episode transaction
- atomic batch commit
- session lineage trace

### `generic_learning.py`

- action bias限定からP-IR compilerへ置換
- data role validation
- isolated candidate
- logical/physical digest

### `generic_competition_runner.py`

- one CognitiveSession per scorecard
- per-game EpisodeTxn
- idle/resource monitoring
- failure rollback

### `agents/templates/generic_agi_agent.py`

- session injection
- default P生成廃止
- game identityをDecisionContextへ渡さない

### `schema.py`

- `allow_nan=False`
- logical/physical digest
- taint-aware serializer

---

## 23. 新規module

```text
arc3_agi_agent/runtime_identity.py
arc3_agi_agent/identity_boundary.py
arc3_agi_agent/generic_session.py
arc3_agi_agent/authority_state.py
arc3_agi_agent/control_state.py
arc3_agi_agent/memory_event.py
arc3_agi_agent/memory_image.py
arc3_agi_agent/memory_backend.py
arc3_agi_agent/memory_transaction.py
arc3_agi_agent/memory_overlay.py
arc3_agi_agent/memory_retrieval.py
arc3_agi_agent/memory_consolidation.py
arc3_agi_agent/evidence_binding.py
arc3_agi_agent/p_ir.py
arc3_agi_agent/p_ir_types.py
arc3_agi_agent/p_ir_interpreter.py
arc3_agi_agent/p_bundle.py
arc3_agi_agent/p_compiler_v2.py
arc3_agi_agent/p_registry.py
arc3_agi_agent/evaluation_registry.py
arc3_agi_agent/development_loop.py
arc3_agi_agent/autonomous_completion_audit.py
arc3_agi_agent/external_execution_contract.py
```

module数は責任境界を示す論理構成であり、実装時に循環依存を避けて統合してよい。

---

## 24. Blocking acceptance registry

## 24.1 Evidence

| ID | Requirement |
|---|---|
| `EVD-001` | candidate固有binding以外のM証拠でreproducedにならない |
| `EVD-002` | precondition/effect/scope不一致recordをEXECUTE根拠にしない |
| `EVD-003` | hazard exact-matchはvetoする |
| `EVD-004` | probation evidenceはprobe rankingのみ |
| `EVD-005` | memory bindingをcandidate traceへ保存する |

## 24.2 State ownership

| ID | Requirement |
|---|---|
| `STA-001` | learned world knowledgeはM正本 |
| `STA-002` | cycle/budget/no-progressはControlState |
| `STA-003` | capability/nonceはAuthorityState |
| `STA-004` | live authority tokenを永続化しない |
| `STA-005` | restart後は新token、旧authorization再利用不可 |

## 24.3 Memory transaction

| ID | Requirement |
|---|---|
| `MEM2-001` | prepare中にlive stateを変更しない |
| `MEM2-002` | event/state/receiptをatomic commit |
| `MEM2-003` | backend failure時にlive digest不変 |
| `MEM2-004` | episode/level overlay rollback |
| `MEM2-005` | full-copy snapshot増殖なし |
| `MEM2-006` | development restartでledgerから復元 |
| `MEM2-007` | cross-game promotionはP19 PASS後のみ |
| `MEM2-008` | memory ablationで未来行動因果が消える |

## 24.4 Identity

| ID | Requirement |
|---|---|
| `ID2-001` | C/P/J/M APIがOrchestrationMetadataを受け取れない |
| `ID2-002` | game order/opaque tokenをdecision featureにしない |
| `ID2-003` | exact state digestはepisode local以下 |
| `ID2-004` | current renderからのdynamic coordinateのみ許可 |
| `ID2-005` | metadata/order/permutation taint試験PASS |

## 24.5 P-IR

| ID | Requirement |
|---|---|
| `PIR-001` | fixed L0 interpreter上でrepresentation graphを交換可能 |
| `PIR-002` | typed DAG、unknown opcode reject |
| `PIR-003` | resource manifest検証 |
| `PIR-004` | no eval/import/I/O |
| `PIR-005` | ABI mismatch fail closed |
| `PIR-006` | logical digest deterministic |

## 24.6 Learning

| ID | Requirement |
|---|---|
| `LRN2-001` | M_dev/Ledgerからisolated P candidate生成 |
| `LRN2-002` | DEVELOPMENT_VALIDATIONだけでpromotion |
| `LRN2-003` | LOCKED_FINALをpromotionに使用しない |
| `LRN2-004` | promoted P/J0/M0から新process再現 |
| `LRN2-005` | rejected candidateでactive artifact不変 |

## 24.7 Evaluation

| ID | Requirement |
|---|---|
| `EVAL-001` | dataset role/access ledger |
| `EVAL-002` | CVをsingle artifact claimに使わない |
| `EVAL-003` | locked finalは一回使用、結果後CONSUMED |
| `EVAL-004` | final evaluator独立性manifest |
| `EVAL-005` | progressだけでcompletion PASSにしない |

## 24.8 Competition

| ID | Requirement |
|---|---|
| `OFF2-001` | one scorecard / one make / sequential |
| `OFF2-002` | one CognitiveSession per scorecard |
| `OFF2-003` | exact artifact digest report |
| `OFF2-004` | idle/duration/resource margin |
| `OFF2-005` | failure episode rollback |
| `OFF2-006` | output bytes > 0、score returned |
| `OFF2-007` | Public/Private/full claim分離 |

一件でもPASS以外なら次phaseへ進まない。

---

## 25. 必須試験

### Unit

```text
test_candidate_evidence_binding_is_specific
test_unrelated_memory_never_marks_reproduced
test_precondition_mismatch_forces_probe
test_hazard_binding_vetoes_execute
test_state_owner_separation
test_authority_token_not_restored
test_memory_prepare_has_no_side_effect
test_atomic_commit_failure_preserves_digest
test_episode_overlay_commit_and_rollback
test_checkpoint_rebuild
test_taint_boundary_rejects_metadata
test_dynamic_coordinate_allowed
test_precomputed_coordinate_rejected
test_p_ir_typecheck
test_p_ir_unknown_opcode_rejected
test_p_ir_resource_bound
test_p_bundle_logical_digest
test_nan_inf_rejected
test_canonical_tensor_digest
```

### Integration

```text
test_cycle_memory_changes_future_candidate
test_level_failure_rolls_back_overlay
test_level_success_consolidates_episode
test_game_exception_preserves_session_global
test_cross_game_probation_only_changes_probe
test_cross_game_active_rule_requires_independent_support
test_game_order_permutation
test_irrelevant_prior_memory_invariance
test_adversarial_memory_rejected
test_negative_transfer_invalidated
test_development_restart_rebuilds_memory
test_experience_to_p_ir_to_restart
test_same_runtime_identity_in_known_and_sealed_runs
test_no_s5_teacher_fallback
test_scorecard_shared_session
test_idle_timeout_guard
```

### Evaluation

```text
KNOWN_PUBLIC_REGRESSION
CV_PROCEDURE_EVIDENCE
TRANSFORMATION_STRESS_PASS
SEALED_SINGLE_ARTIFACT_COMPLETE
COMPETITION_READY
OFFICIAL_RUN_ACCEPTED
OFFICIAL_PUBLIC_COMPLETE
OFFICIAL_PRIVATE_COMPLETE
OFFICIAL_FULL_COMPLETE
```

---

## 26. Artifact contract

全machine-readable reportは最低限次を持つ。

```text
schema_version
code.commit
code.tree
runtime_identity
runtime_package_logical_digest
runtime_package_byte_digest
l0_abi_version
p.version
p.logical_digest
p.package_digest
j.implementation_digest
j.config_digest
m.schema_version
m.initial_logical_digest
m.final_logical_digest
m.initial_version
m.final_version
session_id
session_lineage_digest
authority_session_digest
control_initial_digest
control_final_digest
input_artifact_digest
evaluation_role
evaluation_access_state
external_execution_contract_digest
environment_manifest
seed
budget
command
status
failed_requirement_ids
content_digest
raw_evidence_pointers
```

completion reportは加えて次を持つ。

```text
completed_environment_count
completed_level_count
failed_environment_count
holdout_definition
runtime_identity_count
fallback_count
identity_leak_count
memory_causal_witness_count
p_causal_witness_count
score_scope
raw_score
normalized_score_ppm
official_submission_ref
```

---

## 27. 固定禁止事項

- candidateと無関係なM証拠をreproducedへ使う
- cross-game semantic promotionをP19前に有効化する
- M mutationをlive dictへ先に適用する
- LedgerとMemoryImageを別transactionで正本commitする
- P compiler前にP-IR/ABIを省略する
- CVの複数Pを一つの同一主体結果として合算する
- LOCKED_FINALをcandidate promotionへ反復利用する
- Jのworld knowledgeをprivate stateへ隠す
- AuthorityStateをSemanticMemoryへ混入する
- game ID、game order、opaque tokenをdecision featureへ使う
- current renderからの動的座標まで一律禁止する
- response retentionをenvironment completionと呼ぶ
- Public 100%だけでfull official completionを宣言する
- scalar scoreだけでCode/P/J/Mへ原因帰属する
- official scoreなしでofficial compatibilityをPASSにする

---

## 28. 最終固定式

```text
Development Learning
=
Experience
→ Atomic Ledger/M Update
→ Causal Consolidation
→ P/J0/M0 Candidate
→ Development Validation
→ HDS Promotion/Rollback
→ Next RuntimeIdentity
```

```text
Competition Autonomy
=
Frozen RuntimeIdentity
+ Scorecard-scoped CognitiveSession
+ Mutable Transactional M_session
+ Candidate-specific Evidence Binding
+ HDS-controlled Action/Memory
→ Unknown Environment Completion
```

```text
Final Completion
=
SEALED_SINGLE_ARTIFACT_COMPLETE
AND COMPETITION_READY
AND OFFICIAL_PUBLIC_COMPLETE
AND OFFICIAL_PRIVATE_COMPLETE
AND exact same RuntimeIdentity
```
