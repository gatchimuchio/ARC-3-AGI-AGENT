# P18 Atomic Event-Sourced Persistent Memory 実装証拠

- phase: `P18_ATOMIC_EVENT_SOURCED_PERSISTENT_MEMORY`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P19_TYPED_CAUSAL_MEMORY_CONSOLIDATION_NEGATIVE_TRANSFER`

## 履歴正本と原子的commit

`SemanticMemory`の履歴正本をappend-only `MemoryEvent` ledgerへ移した。
`MemoryImage`はimmutableな現在状態またはcheckpoint cacheであり、履歴正本ではない。

mutationは次の順序で行う。

```text
expected version確認
→ 全proposal/authorization検証
→ mandatory batchを規定priorityで局所simulation
→ immutable staged imageと単一aggregate eventを生成
→ backend transaction commit
→ authorization consume
→ live image swap
```

`prepare_batch()`はlive state、backend event、capabilityを変更しない。batch内の
一件でも不正、重複、active budget超過なら全件を拒否する。backendが失敗した場合も
event/state/receiptはcommitされず、live digestは不変である。

同じidempotency keyと同じ内容の再実行は既存receiptを返し、別内容とのkey衝突は
fail closedとする。一回のmandatory batchは一つのversion incrementと一つの
aggregate eventへ対応する。

## Backendと復旧

二つの同一contract backendを実装した。

- `InMemoryBackend`: deterministic test/development backend
- `SQLiteEventBackend`: WAL、`BEGIN IMMEDIATE` transaction、schema version、
  migration、checkpoint、restart replayを持つpersistent backend

SQLite backendはevent、receipt、current state、checkpointを同一transactionで
commitする。prepare後のprocess loss、およびcommit途中のfault injection後に
再起動しても、未commit eventまたは部分stateは観測されない。

rebuildは最新checkpointから後続eventをchain/version/state digest検証付きで
replayする。checkpointはinterval生成かつbounded retentionであり、
versionごとのfull-copy snapshotは保持しない。

## Canonical artifact

`canonical_json()`を`allow_nan=False`へ固定し、NaN/Infを拒否する。
logical content digestとphysical package digestを別API・別namespaceで保持する。
canonical ZIPはmember順、timestamp、permission、compressionを固定し、同一入力から
byte-identical packageを生成する。

## Runtime統合

`CognitiveSession`はbackendを明示注入でき、既定では`InMemoryBackend`を使う。
runtimeの一cycleから生じるmemory proposal群は、個別mutationではなく一つの
mandatory atomic batchとして処理する。batchがresource contractを超える場合は
部分適用せず`SEMANTIC_MEMORY_MANDATORY_BATCH_SUSPEND`を記録する。

`EventSourcedExperienceLedger`もappend-only digest chainを持ち、旧placeholder
ledgerを置換した。P17-Bのcandidate evidence、taint、episode rollback境界は維持した。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P18-001 lost_event_count = 0` | PASS | atomic event/state commit、restart replay |
| `P18-002 partial_mutation_count = 0` | PASS | prepare side-effect、max-active、backend-fault tests |
| `P18-003 restart_digest_match = true` | PASS | prepare/commit crashとledger rebuild tests |
| `P18-004 idempotency_violation_count = 0` | PASS | memory/backend idempotent replay test |
| `P18-005 full_copy_snapshot_per_version = false` | PASS | interval checkpoint、bounded retention test |
| `P18-006 canonical_digest = PASS` | PASS | non-finite rejection、logical/physical digest test |

## Validation

- P18 required tests: `12 / 12 PASS`
- P12/P17/P18 focused regression: `39 / 39 PASS`
- full unit suite: `599 / 599 PASS`
- targeted mypy: `10 source files PASS`
- targeted ruff: `PASS`
- compileall: `PASS`

## 残存境界

- causal record schema、support independence、consolidation、negative-transfer
  invalidation、cross-game promotionはP19まで無効である。
- P-IR/compiler/registry、governed development、CV/sealed final、
  Competition package、official observationは未開始である。
- 本証拠は未コミットworktreeへ結合されており、commit/treeによるrelease固定ではない。
- generic completion、Competition ready、official accepted/public/private/fullは
  未成立・未観測である。
