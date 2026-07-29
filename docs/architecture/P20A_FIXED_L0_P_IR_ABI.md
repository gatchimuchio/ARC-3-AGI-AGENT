# P20-A Fixed L0 Instruction Set / P-IR / ABI 実装証拠

- phase: `P20_A_FIXED_L0_INSTRUCTION_SET_P_IR_ABI`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P20_B_P_COMPILER_V2_BUNDLE_REGISTRY`

## Frozen ISA v1

Pが固定Codeへ任意Pythonを渡す経路を作らず、rev2で規定された
representation/model/candidate opcodeを有限集合として実装した。

- schema: `arc3-p-ir-schema-v1`
- L0 ABI: `arc3-l0-abi-v1`
- opcode set: `arc3-p-ir-opcodes-v1`
- type system: `arc3-p-ir-types-v1`
- semantics digest: opcode signature、type集合、cost modelへcontent-bound

各programは三つの`TypedDAG`、parameter manifest、resource manifest、
identity-free provenanceを持つ。node input/output型、graph kind、external input、
required outputをcompile前に検査する。unknown opcode、型不一致、cycle、unsupported
ABI、semantics digest不一致はすべてfail closedである。

## Resource / security boundary

static validatorとruntime accountingの両方で次を検査する。

- node数
- tensor bytes
- object数
- relation数
- candidate数
- memory citation数
- worst-case operation cost
- bounded `TOPK`

program parameterはJSON primitiveとbounded tupleだけを許可する。callable、
Python/code/module/import/eval/exec、filesystem/network/path/URL/commandを示す
keyまたは実行文字列を拒否する。interpreterは固定opcode dispatchだけを持ち、
program由来の`eval`、dynamic import、filesystem/network I/Oを実行しない。

## Runtime integration

従来の`represent_observation()`と`action_descriptors()`は固定decision pathではなく
compatibility opcode semanticsへ降格した。標準sessionでも次の経路を通る。

```text
DecisionObservation
→ representation TypedDAG
→ selective M retrieval
→ model TypedDAG
→ candidate TypedDAG
→ existing P-A/P-B compatibility scorer
→ C typed output
```

`spatial-relational`、`topology-minimal`、`shape-centric`のrepresentation programを
同一L0 interpreterで交換できる。program変更はrepresentation、P logical digest、
compute result digestを実際に変える。現在renderから生成した座標だけに
`CURRENT_RENDER_DERIVED` provenanceを付け、事前座標を受け取らない。

`GenericComputeResult`はP-IR logical digest、execution digest、L0 ABI versionを
保持する。`CognitiveSession`はbodyとP-IR programを別々にfreezeし、runtime identityは
両方のlogical identityへ結合した。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P20A-001 p_ir_schema = FROZEN_V1` | PASS | typed schema/round-trip/typecheck tests |
| `P20A-002 l0_abi = FROZEN_V1` | PASS | ABI/semantics digestとmismatch rejection |
| `P20A-003 representation_swappable = true` | PASS | two-program interpreter/runtime tests |
| `P20A-004 arbitrary_code_surface = 0` | PASS | finite opcode/parameter security test |
| `P20A-005 deterministic_interpreter = PASS` | PASS | byte/logical/execution equality test |

## Validation

- P20-A required tests: `10 / 10 PASS`
- additional P-IR typecheck: `1 / 1 PASS`
- P17〜P19 focused regression: `57 / 57 PASS`
- package/Notebook/runtime focused regression: `20 / 20 PASS`
- full unit suite: `627 / 627 PASS`
- targeted mypy: `11 source files PASS`
- targeted ruff: `PASS`

## 残存境界

- M_dev/Ledgerからのsymbolic/parametric/hybrid compiler、isolated candidate、
  registry promotion/rollback、initial-state restartはP20-Bまで未開始である。
- governed development、CV/sealed final、Competition package、official observationは
  未開始である。
- 本証拠は未コミットworktreeへ結合されており、commit/treeによるrelease固定ではない。
- generic completion、Competition ready、official accepted/public/private/fullは
  未成立・未観測である。
