# P17-A CognitiveSession / State Ownership 実装証拠

- phase: `P17_A_COGNITIVE_SESSION_AND_STATE_OWNERSHIP`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P17_B_EVIDENCE_BINDING_TAINT_SAFE_EPISODE_TRANSACTION`

## 実装結果

scorecard/run単位の主体containerを`CognitiveSession`として実装した。
`GenericAGIRuntime`は次の三引数だけを受け取り、M、J、P、authorityを
内部生成しない。

```python
GenericAGIRuntime(
    environment=environment,
    session=cognitive_session,
    episode_handle=episode_handle,
)
```

runnerはscorecardごとに一件だけsessionを作り、全gameのagentへ同じobjectを
注入する。agent templateはgameごとの`HybridRelationalInstructionBody`生成を
行わない。

## State ownership

| State | 唯一の所有者 | 実装 |
|---|---|---|
| live token、issued/consumed capability、decision registry | `AuthorityState` | `authority_state.py` |
| cycle、budget、no-progress、next question、pending probe | `ControlState` | `control_state.py` |
| active/working/archive/sealed semantic record | `SemanticMemory` | `generic_memory.py` |
| frozen P logical reference | `FrozenPReference` | `generic_session.py` |
| RuntimeIdentity / ResourceContract / HDS config | `CognitiveSession` | `generic_session.py` |
| episode/level isolation boundary | `MemoryOverlay` | `memory_overlay.py` |
| orchestration taint rejection | `IdentityBoundary` | `identity_boundary.py` |

HDSの旧`_selector_deltas`と`_value_actions`は`ControlState`へ移し、
`legacy_structural_compatibility`で明示したepisode-local互換状態とした。
episode開始・終了時に必ず消去し、session-global意味知識として検索しない。

## Episode boundary

P17-Aではcross-game semantic promotionを強制的に`DISABLED`とした。

```text
begin episode
→ capture base M version / active digest
→ begin level
→ execute game-local cycle writes
→ end level
→ HDS-authorized rollback to the pre-episode base
→ verify active digest equality
→ clear episode-local ControlState
```

成功gameを含め、全episode writeを終了時に基底へ戻す。過去episode由来recordは
active queryへ残らず、次gameのcandidate rankingを変更しない。rollback不能時は
sessionをpoisonedとして後続episodeを拒否する。

P17-AのoverlayはP18のatomic event-sourced memoryではない。現行Mの
direct mutation、full-copy snapshot、archive保持はP18で置換する。

## Identity boundary

`OrchestrationMetadata`と`Tainted[T]`をrunner境界専用型として追加した。
scorecard ID、game ID、game index、environment handleはruntimeへ渡さない。
opaque episode handleはRuntime/Control境界だけで使用し、C/P/J/Mのdecision
contextへ入れない。各cycleでobservation、memory view、HDS frame、
compute result、decisionを`IdentityBoundary`へ通し、違反時はfail closedする。

`RuntimeIdentity`は次の八fieldを測定する。

```text
code_tree_digest
l0_abi_version
p_logical_digest
j_implementation_digest
j_config_digest
m0_logical_digest
adapter_digest
dependency_lock_digest
```

P17-A検証時の一例は
`runtime-identity:57c6184d84ca165951670da8506ed7f2cf7b041e19602e3ad042b5d14c5ef948`
である。これは現行uncommitted worktreeのsourceに対する測定値であり、
commit/package固定値ではない。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P17A-001 shared_session_count = 1` | PASS | runner injection test、report field |
| `P17A-002 per_game_new_memory_count = 0` | PASS | shared object identity test |
| `P17A-003 per_game_new_p_count = 0` | PASS | shared frozen P identity test |
| `P17A-004 cross_game_semantic_promotion = DISABLED` | PASS | overlay hard gate、episode rollback test |
| `P17A-005 state_owner_violation_count = 0` | PASS | owner graph audit |
| `P17A-006 identity_boundary = PASS` | PASS | taint rejection、serialized decision inspection |

必須試験は次を含む。

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

追加で、prior episode後もcandidate rankingとselected semantic keyが一致することを
検証した。

## Validation

- P17-A + generic runtime + P12 genericity + notebook contract:
  `25 passed`
- full unit suite初回: `571 passed, 1 failed`
- 初回失敗:
  `KAGGLE_RUNTIME_IMPORT_CLOSURE_INCOMPLETE`
- classification: `product regression caused by current P17-A imports`
- correction:
  historical notebook builderのallow-listへP17-A依存moduleを追加
- targeted rerun: `1 passed`
- P17-A phase-state/content-binding rerun: `10 passed`
- final full unit result: `574 / 574 PASS`
- targeted mypy: `12 source files PASS`
- targeted ruff: `PASS`（初回の誤った相対path指定はenvironment command error。
  正しいpathで再実行してPASS）
- compileall: `PASS`

Notebook contractの回帰修正は既存build形状のimport closure維持だけである。
P23のCompetition package完成、Notebook更新、Kaggle実行・提出は行っていない。

## 残存境界

- global `has_memory_evidence`とcandidate非固有`reproduced`は未修正。
  P17-Bのblocking対象である。
- current memory engineはatomic batch / event-source / restart replayではない。
  P18のblocking対象である。
- causal consolidationとcross-game promotionはOFF。P19 PASS前に有効化しない。
- P-IR、compiler、governed development、CV/sealed、Competition package、
  official observationは未開始。
- generic completion、Competition ready、official accepted/public/private/fullは
  引き続き未成立・未観測である。
