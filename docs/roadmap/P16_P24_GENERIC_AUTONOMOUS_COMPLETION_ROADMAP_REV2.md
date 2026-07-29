# ARC3 汎用自律完遂主体 開発ロードマップ P16–P24 rev2

- ロードマップID: `P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2`
- 対象リポジトリ: `gatchimuchio/ARC-3-AGI-AGENT`
- 基準commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- 上位仕様: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- 監査正本: `ARC3_汎用自律完遂主体_rev1再監査報告_rev2.md`
- 実装方針: P0〜P15はhistorical evidenceとして保存し、active selectorをP16以降へ移す
- 実装規則: phase gateを飛ばさない。後続phaseのproduction pathを先行有効化しない

---

## 0. 全体構造

```text
P16
  Claim / threat / evaluation / official predicate
   ↓
P17-A
  CognitiveSession container
  Authority / Control / Semantic state separation
  Episode overlay skeleton
  cross-game semantic promotion OFF
   ↓
P17-B
  Candidate-specific evidence binding
  decision-input taint boundary
  episode failure rollback
   ↓
P18
  Atomic event-sourced persistent memory
  canonical digest / crash recovery
   ↓
P19
  Typed causal records
  applicability / contradiction / consolidation
  negative-transfer control
  cross-game semantic promotion ON
   ↓
P20-A
  Fixed L0 instruction set
  P-IR / type system / Code-P ABI
   ↓
P20-B
  Symbolic / parametric / hybrid compiler
  registry / isolated evaluator / restart
   ↓
P21
  TRAIN + DEVELOPMENT_VALIDATION development loop
  Code/P/J0/M0 version learning
   ↓
P22-A
  Public known regression
  CV procedure evidence
  transformation stress
   ↓
P22-B
  One frozen artifact
  independently locked final evaluator
  one-time execution
   ↓
P23
  Final competition packaging
  scorecard-scoped M_session
  idle/resource/package contract
   ↓
P24
  Exact artifact official submission
  Public / Private / Full scope observation
```

packaging CI、resource smoke、identity scanはP17から毎phase実行する。ただし`COMPETITION_READY`昇格はP23でのみ行う。

---

## 1. 既存資産の処理

## Preserve

- P0〜P9の責任分離・権限・ablation証拠
- P11 release state
- S5 183/183 known-public baseline
- GenericAGIRuntimeのC/J/M/P loop原型
- SemanticMemoryのrecord/mutation/version/authorization概念
- P candidate/promotion/rollback概念
- sequential competition runner
- P13〜P15のKaggle提出障害証拠

## Quarantine

- S5 active runtime fallback
- Teacher / source / hidden / answer / replayのruntime参照
- progress-only genericity PASS
- gameごとのM/P/J新規生成
- global `has_memory_evidence`によるEXECUTE
- J private world-learning state
- exact public frame digestによるglobal routing
- response retentionをcompletionと呼ぶ評価

## Replace

- current `SemanticMemory.apply_authorized()` direct mutation
- simple token-overlap retrieval
- `surface:{ordinal}`中心のcross-game key
- action-bias限定P compiler
- rev1の5-fold/single-artifact混同
- rev1の非atomic MemoryBackend

---

# P16 — Rebaseline / Threat Model / Evaluation Governance

## 目的

完成claim、active runtime、評価独立性、identity threat、official completion predicateを正本化する。

## 変更対象

```text
README.md
AGENTS.md
docs/architecture/AGI_CLAIM_REGISTRY.md
docs/architecture/AGI_TEST_MATRIX.md
docs/architecture/ARC3_AGI_ACCEPTANCE_SPEC_REV1.md
docs/architecture/ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2.md
docs/roadmap/P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2.md
```

## 実施事項

1. P11/S5を`KNOWN_PUBLIC_REGRESSION`へ固定
2. P12 genericityを`LOCAL_GENERIC_PROGRESS`へ再分類
3. holdout completion 0を明記
4. S5とGenericの成果合算禁止
5. active runtime候補をGeneric系一件に固定
6. RuntimeIdentity定義を追加
7. identity/taint threat modelを追加
8. dynamic coordinate許可、precomputed coordinate禁止を明記
9. evaluation role registryを追加
10. CVとsingle-artifact final claimを分離
11. Public / Private / Full official claimを分離
12. official scalar scoreだけの原因帰属禁止
13. rev1文書をhistorical draftへ降格
14. P16以降をAGENTS.mdの最上位work selectorへ設定

## 新規成果物

```text
docs/audit/ARC3_GENERIC_REAUDIT_REV2.md
docs/architecture/ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2.md
docs/roadmap/P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2.md
docs/security/IDENTITY_TAINT_THREAT_MODEL.md
docs/evaluation/EVALUATION_ROLE_REGISTRY_SPEC.md
docs/official/OFFICIAL_COMPLETION_PREDICATES.md
```

## 必須試験

- docs claim consistency
- all claim has evidence boundary
- no `AGI complete` / `ARC3 closed` active claim
- RuntimeIdentity fields complete
- phase authority order deterministic

## 完了ゲート

```text
P16-001 claim_overstatement_count = 0
P16-002 active_runtime_candidate_count = 1
P16-003 evaluation_role_registry = PASS
P16-004 identity_threat_model = PASS
P16-005 official_completion_predicate = PASS
P16-006 rev1_status = HISTORICAL_DRAFT
```

---

# P17-A — CognitiveSession Container / State Ownership

## 目的

scorecard/run単位の主体containerを作る。ただし意味記憶のcross-game再利用はまだ有効化しない。

## 新規module

```text
arc3_agi_agent/runtime_identity.py
arc3_agi_agent/generic_session.py
arc3_agi_agent/authority_state.py
arc3_agi_agent/control_state.py
arc3_agi_agent/memory_overlay.py
arc3_agi_agent/identity_boundary.py
```

## 変更対象

```text
arc3_agi_agent/generic_runtime.py
arc3_agi_agent/generic_hds.py
arc3_agi_agent/generic_competition_runner.py
agents/templates/generic_agi_agent.py
arc3_agi_agent/generic_types.py
```

## 実施事項

### CognitiveSession

- one session per scorecard/run
- frozen P reference
- HDS config reference
- process-local AuthorityState
- ControlState
- SemanticMemory reference
- ExperienceLedger interface placeholder
- ResourceContract
- RuntimeIdentity

### Runtime injection

- `GenericAGIRuntime.__post_init__`内のM/J/P/authority新規生成を廃止
- `GenericAGIRuntime(environment, session, episode_handle)`へ変更
- GenericAGIAgentのgameごとの`HybridRelationalInstructionBody()`生成を廃止
- runnerがscorecard前にsessionを一件生成
- 全agentへ同じsessionを渡す

### State ownership

- `_cycle_index`、`_no_progress_count`、`_last_question`をControlStateへ移す
- issued/consumed capabilityをAuthorityStateへ移す
- `_selector_deltas`、`_value_actions`はこのphaseではlegacy quarantine。判断へ使用しないかepisode-local compatibility flagで隔離

### Overlay skeleton

- begin/end episode API
- begin/end level API
- overlayは作るがSESSION_GLOBAL promotionはOFF
- game failure時overlay discard

## 禁止

- prior game memoryをcandidate rankingへ使う
- cross-game record promotion
- Evidence Binding未修正のまま共有M evidenceをEXECUTEへ使う

## 必須試験

```text
test_one_session_per_scorecard
test_runtime_does_not_create_memory
test_runtime_does_not_create_p
test_authority_control_semantic_separation
test_new_scorecard_new_authority
test_old_authorization_rejected
test_episode_overlay_discard_on_exception
test_game_metadata_not_in_decision_context
```

## 完了ゲート

```text
P17A-001 shared_session_count = 1
P17A-002 per_game_new_memory_count = 0
P17A-003 per_game_new_p_count = 0
P17A-004 cross_game_semantic_promotion = DISABLED
P17A-005 state_owner_violation_count = 0
P17A-006 identity_boundary = PASS
```

---

# P17-B — Evidence Binding / Taint Boundary / Safe Episode Transaction

## 目的

共有Mの証拠を、現在候補へ因果的・候補固有に結合し、失敗episodeの汚染を防止する。

## 新規module

```text
arc3_agi_agent/evidence_binding.py
arc3_agi_agent/decision_context.py
arc3_agi_agent/taint.py
arc3_agi_agent/episode_transaction.py
```

## 変更対象

```text
arc3_agi_agent/generic_types.py
arc3_agi_agent/generic_compute.py
arc3_agi_agent/generic_hds.py
arc3_agi_agent/generic_runtime.py
arc3_agi_agent/generic_memory.py
```

## 実施事項

### Evidence Binding

- `EvidenceBindingKey`
- `CandidateEvidenceBinding`
- typed candidate provenance
- candidate-specific memory refs
- precondition/effect/scope match
- execute eligibility
- hazard veto

### global bug removal

- `has_memory_evidence`をcandidate採否から削除
- `reproduced = has_memory_evidence`へ縮約される式を削除
- unrelated recordでEXECUTEにならない

### Taint boundary

- OrchestrationMetadataとDecisionContextの型分離
- game ID / order / scorecard ID / opaque handleをC/P/J/M APIから排除
- exact state digestをepisode localへ制限
- dynamic coordinate test

### Episode transaction

- level overlay
- episode overlay
- failure/exception rollback
- SESSION_GLOBAL base digest保持
- consolidationはまだdisabled

## 必須試験

```text
test_unrelated_memory_never_marks_reproduced
test_matching_record_can_mark_reproduced
test_precondition_mismatch_forces_probe
test_effect_mismatch_forces_probe
test_hazard_exact_match_veto
test_probation_never_authorizes_execute
test_failure_rolls_back_episode_overlay
test_game_order_not_visible
test_opaque_handle_not_serializable
test_dynamic_xy_from_render_allowed
test_precomputed_xy_rejected
```

## 完了ゲート

```text
P17B-001 unrelated_evidence_false_positive = 0
P17B-002 candidate_binding_coverage = 100%
P17B-003 failure_overlay_leak = 0
P17B-004 tainted_decision_input_count = 0
P17B-005 cross_game_semantic_promotion = DISABLED
```

---

# P18 — Atomic Event-Sourced Persistent Memory

## 目的

開発用永久Mと公式用session Mを、同じatomic contractで実装する。

## 新規module

```text
arc3_agi_agent/memory_event.py
arc3_agi_agent/memory_image.py
arc3_agi_agent/memory_backend.py
arc3_agi_agent/memory_transaction.py
arc3_agi_agent/experience_ledger.py
arc3_agi_agent/canonical_artifact.py
```

## 変更対象

```text
arc3_agi_agent/generic_memory.py
arc3_agi_agent/generic_runtime.py
arc3_agi_agent/schema.py
```

## 実施事項

### Event-sourced authority

- Event Ledgerを履歴正本
- snapshotはcache
- expected version compare
- idempotency key
- prepare / validate / commit / live swap

### Backend

- InMemoryBackend
- SQLiteEventBackend
- WAL
- transaction
- schema migration
- crash recovery
- replay rebuild

### Mutation

- live dict先行変更廃止
- immutable staged image
- batch priority
- mandatory batch all-or-nothing
- backend failure時live digest不変

### Checkpoint

- full-copy per version廃止
- interval checkpoint
- bounded retention
- rebuild performance measurement

### Canonicalization

- `allow_nan=False`
- logical/physical digest分離
- fixed timestamp/order
- NaN/Inf拒否

## 必須試験

```text
test_prepare_has_no_live_side_effect
test_max_active_failure_is_atomic
test_backend_failure_preserves_live_digest
test_event_and_state_atomic_commit
test_idempotent_replay
test_crash_after_prepare
test_crash_during_commit
test_restart_rebuild_from_ledger
test_checkpoint_rebuild
test_schema_migration
test_nan_inf_rejected
test_logical_and_package_digest_separated
```

## 完了ゲート

```text
P18-001 lost_event_count = 0
P18-002 partial_mutation_count = 0
P18-003 restart_digest_match = true
P18-004 idempotency_violation_count = 0
P18-005 full_copy_snapshot_per_version = false
P18-006 canonical_digest = PASS
```

---

# P19 — Typed Causal Memory / Consolidation / Negative Transfer Control

## 目的

Mを短期履歴から、前提・因果・反証・適用範囲を持つ意味記憶へ完成させる。

## 新規module

```text
arc3_agi_agent/causal_record.py
arc3_agi_agent/evidence_policy.py
arc3_agi_agent/memory_retrieval.py
arc3_agi_agent/memory_consolidation.py
arc3_agi_agent/negative_transfer.py
```

## 変更対象

```text
arc3_agi_agent/generic_memory.py
arc3_agi_agent/generic_compute.py
arc3_agi_agent/generic_hds.py
arc3_agi_agent/generic_runtime.py
```

## 実施事項

### Typed causal record

- binding key
- precondition
- effect
- delay window
- scope
- support/contradiction/hazard group
- fixed-point confidence
- execute/probe eligibility

### Retrieval

- Tier 0〜3
- score breakdown
- applicability check
- contradiction/hazard penalty
- Tier 3はprobeのみ

### Update rules

- unique evidence group
- confidence ppm式
- PROPOSED / PROBATION / ACTIVE / SUSPENDED / REJECTED
- exact hazard veto
- contradiction invalidation

### Consolidation

- level overlay → episode
- episode → session global
- one episode knowledgeはSESSION_GLOBAL PROBATION
- independent 2 episode以上でACTIVE候補
- exact frame/identity除去

### J knowledge migration

- selector delta/value action等のworld knowledgeをM recordへ移行
- Control/Authority stateは移さない

### Negative transfer

- irrelevant memory invariance
- order permutation
- adversarial record
- bad promotion rollback

### Enablement

P19の全gate PASS後にのみcross-game semantic promotionをONにする。

## 必須試験

```text
test_support_contradiction_confidence
test_duplicate_evidence_not_double_counted
test_delayed_effect_record
test_exact_hazard_veto
test_one_episode_record_is_probation
test_two_episode_support_can_activate
test_cross_level_transfer
test_cross_game_transfer_after_activation
test_irrelevant_prior_invariance
test_game_order_permutation
test_adversarial_record_rejected
test_negative_transfer_invalidated
test_j_has_no_private_world_learning_state
test_memory_ablation_changes_future_action
```

## 完了ゲート

```text
P19-001 typed_causal_record = PASS
P19-002 memory_causal_witness_count > 0
P19-003 cross_level_transfer = PASS
P19-004 negative_transfer_suite = PASS
P19-005 hidden_j_world_knowledge_count = 0
P19-006 cross_game_semantic_promotion = ENABLED
```

---

# P20-A — Fixed L0 Instruction Set / P-IR / ABI

## 目的

固定Code上で、Pがrepresentation、state、transition、goal、hazard、candidate生成を交換可能にする。

## 新規module

```text
arc3_agi_agent/p_ir_types.py
arc3_agi_agent/p_ir.py
arc3_agi_agent/p_ir_validator.py
arc3_agi_agent/p_ir_interpreter.py
arc3_agi_agent/p_ir_resource.py
arc3_agi_agent/p_ir_abi.py
```

## 変更対象

```text
arc3_agi_agent/generic_compute.py
arc3_agi_agent/generic_types.py
arc3_agi_agent/schema.py
```

## 実施事項

### ISA v1

- representation opcodes
- model opcodes
- candidate opcodes
- typed DAG
- bounded TOPK
- no recursion / unbounded loop
- no arbitrary code / I/O

### ABI

- `l0_abi_version`
- opcode version
- type version
- semantics digest
- resource cost model
- incompatibility reject

### Runtime integration

```text
DecisionObservation
→ P representation graph
→ P model graph
→ P candidate graph
→ C typed output
```

current fixed `represent_observation()`はcompatibility fixtureへ降格し、P-IR programとして再表現する。

## 必須試験

```text
test_same_l0_two_representation_programs
test_representation_change_changes_compute
test_unknown_opcode_rejected
test_type_mismatch_rejected
test_cycle_rejected
test_resource_bound_rejected
test_dynamic_coordinate_opcode
test_no_arbitrary_python
test_abi_mismatch_rejected
test_interpreter_deterministic
```

## 完了ゲート

```text
P20A-001 p_ir_schema = FROZEN_V1
P20A-002 l0_abi = FROZEN_V1
P20A-003 representation_swappable = true
P20A-004 arbitrary_code_surface = 0
P20A-005 deterministic_interpreter = PASS
```

---

# P20-B — P Compiler v2 / Bundle / Registry

## 目的

M_devとLedgerの安定構造を、P-IRとcanonical tensorsへコンパイルし、隔離評価・昇格・再起動利用する。

## 新規module

```text
arc3_agi_agent/p_bundle.py
arc3_agi_agent/p_compiler_v2.py
arc3_agi_agent/p_registry.py
arc3_agi_agent/p_evaluator.py
arc3_agi_agent/initial_state_compiler.py
```

## 変更対象

```text
arc3_agi_agent/generic_learning.py
arc3_agi_agent/generic_compute.py
```

## compiler対象

```text
representation
object/relation schema
state variables
preconditions
transition/effect/delay
goal/hazard
exploration/probe
composition
candidate scoring
uncertainty
```

## 実施事項

- symbolic compiler
- parametric compiler
- hybrid compiler
- evidence selection manifest
- taint scan
- isolated candidate
- logical P digest
- physical package digest
- P registry lineage
- HDS promotion/rollback
- P/J0/M0 initial-state bundle
- new process restart

## 必須試験

```text
test_compile_symbolic_p_ir
test_compile_parametric_tensors
test_compile_hybrid_bundle
test_candidate_isolated_from_active
test_same_l0_p_swap
test_evidence_manifest_complete
test_identity_taint_rejected
test_known_regression_non_degrading
test_dev_validation_completion_first
test_promotion
test_rollback
test_restart_from_promoted_initial_state
test_bundle_byte_reproducibility
```

## 完了ゲート

```text
P20B-001 compiler_semantics_versioned = true
P20B-002 candidate_isolation = PASS
P20B-003 dev_validation_improved = true
P20B-004 promotion_decision = PROMOTE
P20B-005 restart_reproduction = PASS
P20B-006 identity_leak_count = 0
```

---

# P21 — Governed Development Loop / Joint Optimization

## 目的

Code、P、J0、M0を開発中に継続更新する。ただしLOCKED_FINALを開発信号へ使わない。

## 新規module

```text
arc3_agi_agent/evaluation_registry.py
arc3_agi_agent/data_access_ledger.py
arc3_agi_agent/development_loop.py
arc3_agi_agent/version_lineage.py
analysis/development_runs/
analysis/runtime_versions/
```

## 実施事項

### Dataset roles

- DEVELOPMENT_TRAIN
- DEVELOPMENT_VALIDATION
- CV_HOLDOUT
- LOCKED_FINAL
- OFFICIAL_PUBLIC
- OFFICIAL_PRIVATE

### Loop

```text
TRAIN run
→ M_dev update
→ failure cluster
→ P/J0/M0 candidate
→ DEVELOPMENT_VALIDATION
→ promote/rollback
→ Code regression
→ next version
```

### Code update

- external commit
- ABI change時version bump
- P migrationまたはreject
- M schema migration
- full regression

### CV

- foldごと別RuntimeIdentity
- procedure evidenceのみ
- single artifact claim禁止

### Locked final

- development loopから参照不可
- resultをtriggerに使用不可

## 必須試験

```text
test_dataset_role_access_control
test_locked_final_access_rejected
test_cv_artifacts_are_distinct
test_cv_not_counted_as_same_runtime
test_three_version_lineage
test_code_abi_migration
test_memory_schema_migration
test_rejected_candidate_preserves_active
test_active_runtime_count_one
test_no_s5_fallback
```

## 完了ゲート

```text
P21-001 data_access_violation_count = 0
P21-002 locked_final_access_count = 0
P21-003 version_lineage = PASS
P21-004 active_runtime_count = 1
P21-005 development_loop_closed = true
P21-006 fallback_count = 0
```

---

# P22-A — Public Regression / CV Procedure / Stress

## 目的

同一active runtimeの公開能力を回帰し、開発手順の汎化傾向と変換耐性を測る。最終blind claimには使わない。

## A. Known public active runtime

- Generic active runtimeのみ
- 25/25 game
- 183/183 level
- S5 fallback 0
- full trace
- M causal witness

claim:

```text
KNOWN_PUBLIC_REGRESSION
```

## B. Cross-validation

- 5-fold
- foldごと別P/RuntimeIdentity
- training data完全分離
- resultはprocedure evidence

claim:

```text
CV_PROCEDURE_EVIDENCE
```

## C. Transformation stress

- COLOR
- ROTATION
- REFLECTION
- LAYOUT
- OBJECT_COUNT
- ORDER
- UNSEEN_COMPOSITION

response retentionではなくenvironment completion。

claim:

```text
TRANSFORMATION_STRESS_PASS
```

## D. Memory necessity

- read ablation
- write ablation
- consolidation ablation
- rollback ablation
- session-global ablation

## 必須成果物

```text
analysis/autonomous_completion/public_regression.json
analysis/autonomous_completion/cv_manifest.json
analysis/autonomous_completion/transformation_completion.json
analysis/autonomous_completion/memory_ablation.json
```

## 完了ゲート

```text
P22A-001 known_public_games = 25/25
P22A-002 known_public_levels = 183/183
P22A-003 cv_fold_count = 5
P22A-004 cv_runtime_identity_count = 5
P22A-005 transformation_completion = 7/7
P22A-006 memory_ablation_degrades = true
P22A-007 final_generic_claim = NOT_AUTHORIZED
```

---

# P22-B — Independently Locked Single-Artifact Final

## 目的

一つの固定RuntimeIdentityを、開発へ未使用のlocked evaluatorで一回だけ評価する。

## evaluator contract

- runtime実装から独立した生成・保管境界
- freeze前にcontract/digestだけ公開
- seed/mechanism/instances非公開
- multiple representation forms
- delayed effect
- irreversible hazard
- multi-step composition
- memory necessity
- rollback necessity
- single-action repetitionでは解けない
- source非参照

## 実施順序

```text
1. candidate RuntimeIdentityをfreeze
2. package/logical digest固定
3. LOCKED_FINAL access ledger確認
4. evaluator digest照合
5. one execution
6. resultをsealed artifactへ保存
7. evaluatorをCONSUMEDへ変更
```

## 失敗時

- resultを開発へ使った場合、当該evaluatorはDEVELOPMENT_VALIDATIONへ降格
- 新しいLOCKED_FINALなしに再度final claimしない

## 必須試験

```text
test_locked_evaluator_unseen_before_freeze
test_one_runtime_identity
test_one_execution_only
test_evaluator_consumed_after_run
test_no_source_access
test_full_trace_bound
test_completion_not_progress_only
```

## 完了ゲート

```text
P22B-001 runtime_identity_count = 1
P22B-002 evaluator_access_before_freeze = 0
P22B-003 execution_count = 1
P22B-004 sealed_environment_completion = 100%
P22B-005 crash = 0
P22B-006 identity_leak = 0
P22B-007 claim = SEALED_SINGLE_ARTIFACT_COMPLETE
```

---

# P23 — Competition Session / Resource / Packaging

## 目的

P22-Bのexact artifactを公式scorecard lifecycleへ変更なく接続する。

## 継続CI

P17以降、各commitで次を実行する。

- package build
- import smoke
- source/Teacher exclusion
- secret scan
- normal Notebook smoke
- memory/resource smoke

P23では最終artifactをfreezeする。

## 変更対象

```text
arc3_agi_agent/generic_competition_runner.py
agents/templates/generic_agi_agent.py
arc3_agi_agent/external_execution_contract.py
kaggle_notebooks/submission.ipynb
kaggle_notebooks/build-report.json
```

## 実施事項

### Lifecycle

- OperationMode.COMPETITION
- one scorecard
- one make per environment
- sequential one active environment
- one CognitiveSession
- one fixed P
- scorecard-scoped M_session
- episode transaction
- no inflight score dependency

### Resource

- external contract digest
- per-cycle hard timeout
- per-game timeout
- max API silence
- idle safety margin
- total scorecard duration
- close reserve
- memory upper bound
- P-IR worst-case cost

### Package

- exact runtime package
- logical/physical digest
- deterministic wheel/archive
- no training/Teacher/sealed evaluator source
- collectible submission output before risky bootstrap
- private failure telemetry within exposed contract

### Order robustness

- environment order permutation local test
- irrelevant prior M invariance
- failed episode rollback

## 必須試験

```text
test_one_scorecard
test_one_make_per_environment
test_one_cognitive_session
test_shared_runtime_identity
test_scorecard_idle_guard
test_total_duration_guard
test_memory_bound_110_projection
test_failed_episode_rollback
test_environment_order_permutation
test_package_logical_digest
test_package_byte_digest
test_notebook_source_roundtrip
test_output_parquet_collectible
test_scorecard_close
```

## 完了ゲート

```text
P23-001 local_competition_completion = PASS
P23-002 scorecard_count = 1
P23-003 session_count = 1
P23-004 runtime_identity_count = 1
P23-005 memory_bound = PASS
P23-006 idle_margin = PASS
P23-007 package_reproducible = PASS
P23-008 notebook_normal_run = COMPLETE
P23-009 output_bytes > 0
P23-010 claim = COMPETITION_READY
```

---

# P24 — Official Observation / Public-Private-Full Completion

## 目的

exact P23 artifactを公式評価へ一回提出し、scopeを分離して観測する。

## 提出前gate

- Owner明示許可
- exact commit/tree
- runtime package logical/byte digest
- P logical/package digest
- Notebook version/source digest
- daily submission limit
- prior submission state
- P23全gate PASS

## 実施

```text
1. exact artifactをsubmit
2. status / bytes / score / scopeを記録
3. artifact digest一致を検証
4. Public scoreを分類
5. final Private score公開時に同一artifactを照合
6. Full completion predicateを評価
```

## 判定

```text
ERROR or no score
→ OFFICIAL_NOT_OBSERVED
```

```text
COMPLETE + score returned + score < 100%
→ OFFICIAL_RUN_ACCEPTED
→ capability shortfall
→ traceなしなら AUDIT_INCONCLUSIVE_CAPABILITY_SHORTFALL
```

```text
Public scope 100%
→ OFFICIAL_PUBLIC_COMPLETE
```

```text
Private scope 100%
→ OFFICIAL_PRIVATE_COMPLETE
```

```text
same exact artifact
AND Public 100%
AND Private 100%
→ OFFICIAL_FULL_COMPLETE
```

主催者がFULL_110 scope scoreを直接返す場合は、その100%を代替述語として使用できる。

## 未完時のloop

公式結果を開発へ使用した時点で、その結果はdevelopment signalになる。

```text
P24 incomplete
→ evidenceをLedgerへ記録
→ P21へ戻る
→ new RuntimeIdentity
→ P22-B用のnew LOCKED_FINALを用意
→ P23
→ next authorized P24
```

同じLOCKED_FINALを最終証拠として再利用しない。

## 完了ゲート

```text
P24-001 submission_status = COMPLETE
P24-002 output_bytes > 0
P24-003 exact_artifact_digest = VERIFIED
P24-004 public_scope_score = 100%
P24-005 private_scope_score = 100%
P24-006 same_runtime_identity = true
P24-007 claim = OFFICIAL_FULL_COMPLETE
```

---

# Phase dependency matrix

| Phase | 必須前提 | 有効化される機能 | 有効化禁止 |
|---|---|---|---|
| P16 | なし | claim/threat/eval正本 | runtime変更 |
| P17-A | P16 | shared container | semantic reuse |
| P17-B | P17-A | safe candidate binding / overlay rollback | cross-game promotion |
| P18 | P17-B | atomic persistent M | causal promotion |
| P19 | P18 | causal M / cross-game promotion | P representation learning |
| P20-A | P19 | P-IR interpreter | candidate compile promotion |
| P20-B | P20-A | P compiler/registry | locked final使用 |
| P21 | P20-B | governed development loop | final claim |
| P22-A | P21 | public/CV/stress evidence | single-artifact final claim |
| P22-B | P22-A | sealed single-artifact claim | artifact変更 |
| P23 | P22-B | competition ready | official submission without Owner |
| P24 | P23 + Owner | official observation | overclaim |

---

# 最初の実装slice

最初のwork blockはP16だけとする。

次のwork blockはP17-Aのcontainerとstate ownershipだけとする。

```text
Work Block 1: P16
  claim correction
  threat model
  evaluation role registry
  official predicates

Work Block 2: P17-A
  CognitiveSession
  AuthorityState
  ControlState
  SemanticMemory injection
  overlay skeleton
  semantic cross-game reuse OFF

Work Block 3: P17-B
  Evidence Binding
  taint boundary
  episode rollback
```

共有Mの性能改善を急いでP17-Aへ混入しない。

---

# 最終固定結論

開発対象は一つである。

> 開発中はCode・P・J0・M0を継続更新し、公式評価では固定RuntimeIdentityとscorecard内可変M_sessionを用いて、未知環境を自律的に学習・攻略し、公式Public/Privateの両scopeをコンプリートする同一主体。

```text
Direction only      = 不足
Shared object only  = 不足
Memory log only     = 不足
Progress only       = 不足
Public only         = 不足

Candidate-bound causal M
+ Fixed L0 / executable P-IR
+ Atomic state transition
+ One frozen artifact / unused final evaluator
+ Exact official public/private completion
= 必要
```
