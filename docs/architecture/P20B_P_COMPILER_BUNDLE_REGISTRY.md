# P20-B P Compiler v2 / Bundle / Registry 実装証拠

- phase: `P20_B_P_COMPILER_V2_BUNDLE_REGISTRY`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P21_GOVERNED_DEVELOPMENT_LOOP_JOINT_OPTIMIZATION`

## Compiler boundary

`PCompilerV2`は`DEVELOPMENT_TRAIN`のtyped causal record、明示的な
`EvidenceSelectionManifest`、parent P、現行L0 ABIだけを入力にする。
selected record ID/digest、ledger event digest、ledger digestを完全に照合し、
identity/taintまたは`LOCKED_FINAL`由来入力をfail closedで拒否する。

同一compilerは次の三形式を隔離候補として生成する。

- symbolic P-IR
- parametric canonical tensor
- hybrid P-IR + canonical tensor

compile対象はrepresentation、object/relation schema、state variable、
precondition、transition/effect/delay、goal/hazard、exploration/probe、
composition、candidate scoring、uncertaintyの全契約である。candidate生成中に
active Pを変更せず、parent logical digestへ結合する。

## Deterministic P bundle

`PBundle`のcanonical package memberは次のとおりである。

```text
manifest.json
program.json
tensors/*
compiler_report.json
evaluation_report.json
promotion_report.json
```

logical digestはcanonical program、名前順tensor logical digest、L0 ABI、
compiler semantics versionへ結合する。tensorは許可dtype、little-endian、
shape、canonical raw bytesを固定し、NaN/Infを拒否し、浮動値はppm整数へ
量子化してsigned zeroを正規化する。物理ZIPはentry順、timestamp、permission、
compressionを固定し、logical digestとは別のphysical digestを保持する。
loaderは復元後のlogical/physical bytes一致を再検証する。

## Evaluation / registry

`IsolatedPBundleEvaluator`は`DEVELOPMENT_VALIDATION`だけを受け入れ、評価順を
completed environments、completed levels、true progress、crash/invalid
action/identity leak、action efficiency、memory/resource costに固定する。
known regression非劣化、blind validation改善、ABI互換、決定性、
rollback targetをpromotion条件にする。

`PRegistryAuthority`だけがsingle-use promotion/rollback capabilityを発行する。
`PRegistry`はactive、candidate、previous stable、rejected、lineageを分離し、
promotion後もrollback targetを保持する。同時activeは一件である。

## Initial state restart

`InitialStateCompiler`はpromoted P、J0、identity-free M0をcanonical
`InitialState` packageへ固定する。exact public frame、game/level ID、answer、
replayを拒否する。package bytesを読み直した新しい`CognitiveSession`が、
同じP-IR digestとM0を再現することを新process restart境界として検証した。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P20B-001 compiler_semantics_versioned = true` | PASS | compiler report / manifest binding |
| `P20B-002 candidate_isolation = PASS` | PASS | active byte preservation test |
| `P20B-003 dev_validation_improved = true` | PASS | completion-first isolated evaluator |
| `P20B-004 promotion_decision = PROMOTE` | PASS | HDS capability / registry lineage |
| `P20B-005 restart_reproduction = PASS` | PASS | initial-state package round-trip |
| `P20B-006 identity_leak_count = 0` | PASS | evidence taint and M0 rejection tests |

## Validation

- P20-B required tests: `13 / 13 PASS`
- state content binding: `1 / 1 PASS`
- focused learning/package/P20 regression: `43 / 43 PASS`
- full unit suite: `641 / 641 PASS` in `322.77s`
- targeted mypy: `6 source files PASS`
- targeted ruff: `PASS`
- compileall: `PASS`

## 残存境界

- data access ledger、CV runtime separation、三世代lineage、Code ABI/M schema
  migrationを閉じるgoverned development loopはP21まで未開始である。
- LOCKED_FINAL、Competition packaging、official submissionを使用していない。
- 本証拠は未コミットworktreeへ結合されており、commit/treeによるrelease固定ではない。
- generic completion、sealed single-artifact completion、Competition ready、
  official accepted/public/private/fullは未成立・未観測である。
