# P21 Governed Development Loop / Joint Optimization 実装証拠

- phase: `P21_GOVERNED_DEVELOPMENT_LOOP_JOINT_OPTIMIZATION`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P22_A_PUBLIC_CV_TRANSFORMATION_STRESS`

## Dataset access governance

`EvaluationRegistry`は全datasetをID、digest、owner、role、access state、
first access event、execution count、consumed stateへ登録する。
`DataAccessLedger`は許可・拒否の双方をprevious digest付きのappend-only eventへ
固定する。拒否された要求は実アクセスではないためviolationに数えず、
development loopから許可外roleへ到達する経路を作らない。

development loopで許可するroleは次だけである。

- `DEVELOPMENT_TRAIN`: TRAIN run、M_dev update、failure cluster、candidate compile
- `DEVELOPMENT_VALIDATION`: candidate evaluation、promotion decision、known regression

`LOCKED_FINAL`、`OFFICIAL_PUBLIC`、`OFFICIAL_PRIVATE`はdevelopment triggerに
使用できない。grantはregistry固有tokenへ結合し、外部生成したgrantを拒否する。

## Governed loop

実装した閉ループは次である。

```text
DEVELOPMENT_TRAIN access
→ versioned M_dev update
→ failure cluster digest
→ P/J0/M0 candidate compile
→ isolated DEVELOPMENT_VALIDATION
→ HDS promote/reject/rollback
→ external Code commit + full regression gate
→ InitialState / RuntimeIdentity / version lineage update
```

評価不合格candidateはHDSのsingle-use rejection capabilityで`REJECTED`へ移し、
active Pを変更しない。promotion後にinitial-state compile、Code manifest、
ABI/M schema migration、lineage更新のいずれかが失敗した場合は、直前のstable Pへ
自動rollbackしてactive RuntimeIdentityを保持する。

fallback実装は持たず、legacy fallback要求はfail closedで拒否する。

## Code / P / M migration

各runtime versionはexternal Git commit、source-tree digest、L0 ABI、
P logical digest、J0/M0 InitialState digest、memory schema、
RuntimeIdentityへcontent-boundする。

- opcode/semantics変更時はL0 ABI version変更を必須化する
- ABI変更時はPを`MIGRATED`または`REJECTED`にする
- migrated P digestをtarget Pへ照合する
- memory schema変更時はdeterministic migrationとfull regressionを必須化する
- code source-tree digestをtarget RuntimeIdentityへ照合する
- lineage eventをparent/target/transition digestへ結合する
- lifecycle変更はruntime logical identityを変更しない

三世代lineageでも同時activeは一件だけである。

## Cross-validation boundary

CV foldはfoldごとに別P logical artifact、別InitialState、別RuntimeIdentityを
必須化する。同一Pまたは同一RuntimeIdentityの再利用を拒否する。
集約結果のclaimは`CV_PROCEDURE_EVIDENCE`だけであり、
`SAME_SINGLE_ARTIFACT_COMPLETE`には数えない。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P21-001 data_access_violation_count = 0` | PASS | policy-enforced access ledger |
| `P21-002 locked_final_access_count = 0` | PASS | development access rejection |
| `P21-003 version_lineage = PASS` | PASS | three-version / migration / digest tests |
| `P21-004 active_runtime_count = 1` | PASS | promote/reject/rollback invariants |
| `P21-005 development_loop_closed = true` | PASS | complete train-to-version report |
| `P21-006 fallback_count = 0` | PASS | fail-closed fallback test |

## Validation

- P21 required tests: `10 / 10 PASS`
- additional transactional rollback: `1 / 1 PASS`
- state content binding: `1 / 1 PASS`
- P20-B/P21 focused regression: `25 / 25 PASS`
- full unit suite: `654 / 654 PASS`
- targeted mypy: `5 source files PASS`
- targeted ruff: `PASS`
- compileall: `PASS`

## 残存境界

- known public regression、fold実行、transformation stressの実測はP22-Aまで未開始。
- rev2 `LOCKED_FINAL`のprovision/freeze/一回実行はP22-Bまで未開始。
- Competition session/resource/package gateはP23まで未開始。
- official observationはP23全gateとOwner明示許可が揃うP24まで禁止する。
- 本証拠は未コミットworktreeへ結合されており、commit/treeによるrelease固定ではない。
