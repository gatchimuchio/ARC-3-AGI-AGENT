# P5 HDS判断主体J 実装・完了証拠

- phase: `P5_JUDGMENT_SUBJECT_J`
- state: `COMPLETE`
- predecessor: `P4_COMPUTE_SUBJECT_C`
- successor: `P6_MEMORY_SUBJECT_M`
- runtime scope: identity-free HDS Frame / bundled OFFLINE regression
- official / competition connection: prohibited
- HDS judgment: `PASS`

## 1. Work-block FrameSpec

```text
X:
  P3 hds_frames 676 records
  standalone typed HDS Frame
  existing integrated HDSController

R:
  supplied purpose/X/R/Mc/evidence/risk/budget/unknowns
    -> standalone deterministic judgment
    -> integrated capability-bearing HDSDecision adapter

Mc:
  J creates no hypothesis/candidate
  J reads no P or M
  J writes no memory and executes no external action
  missing X/R/Mc -> SUSPEND
  hazard -> REJECT
  insufficient evidence -> REOBSERVE
  exhausted budget -> STOP
  contradiction -> REJECT
  rollback condition + reference -> ROLLBACK
  J removal -> fixed functional-loss witness

non-goals:
  M operation implementation, pair/Trinity/subset proof, sample solving
```

## 2. 実装

`arc3_agi_agent/judgment.py`:

- `HDSX`, `HDSR`, `HDSMc`
- `JudgmentCandidate`
- `HDSFrame`
- `JudgmentComputeRequest`
- `StandaloneJudgmentDecision`
- `HDSJudgmentSubject`
- `StandaloneJudgmentHarness`

`arc3_agi_agent/judgment_fixtures.py`はP3のidentity-free
`datasets/hds_frames/records.jsonl`をtyped Frameへ変換する。これはJの入力adapterで
あり、J自身はcandidateを生成しない。

判断優先順位:

```text
closed Frame
  -> active stopping condition
  -> hazard veto
  -> unknown / reobserve
  -> budget stop
  -> rollback
  -> contradiction reject
  -> no candidate / compute request
  -> admissible candidate accept
  -> rejected candidate reject
  -> reobserve or suspend
```

既存integrated `HDSController.judge`も同じ`HDSJudgmentSubject`へFrameを渡し、
standalone判断をowner-bound `HDSDecision`へ変換する。旧判断fallbackは残していない。

## 3. 権限境界

standalone Jの出力に含まれるwrite/emit flagは判断結果であり、effect adapterが
消費できるcapabilityではない。実際のsingle-use capability発行、memory mutation、
external emissionは既存`HDSController`の所有・binding検査を通る。

JのAPIは`judge(self, frame)`だけであり、次を入力・実行しない。

- `InstructionBody` / P
- `PureLLMCompute` / C
- `PassiveMemory` / M
- hypothesis/candidate generation
- `apply_authorized`
- `execute_emission`

J removal witness:

```text
JUDGMENT_SUBJECT_REMOVED_NO_G2_ACCEPTANCE_STOP_OR_AUTHORIZATION
```

## 4. P3 fixture適合

全676 Frameをparse、identity-free検査、二重決定一致、decision validationへ通した。

```text
ACCEPT           27
REJECT          613
REOBSERVE         2
COMPUTE_REQUEST  34
total           676
```

この分布はP3 fixtureに対する決定的適合証拠であり、sample攻略性能の主張ではない。

## 5. 検証

- `compileall`: PASS
- `pytest tests/unit`: 158 PASS
- strict mypy: 21 source PASS
- ruff: PASS
- integration: 2 PASS
- 25 sample OFFLINE 1-action regression: 25/25 complete、error 0
- standalone J status/negative/removal tests: 15 PASS

P5はG2 standaloneだけを`SUPPORTED`とする。M full G3、G4、pair、Trinity、
全8 subset、sample攻略、汎化、release固定は未成立。次phaseはP6。
