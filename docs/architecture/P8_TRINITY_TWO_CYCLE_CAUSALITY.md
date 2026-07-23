# P8 三主体Trinity二周期因果・完了証拠

- phase: `P8_THREE_SUBJECT_TWO_CYCLE_TRINITY`
- state: `COMPLETE`
- predecessor: `P7_PAIRWISE_SUBJECT_AUDIT`
- successor: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`
- runtime scope: identity-free full C/J/M OFFLINE kernel and controlled probes
- official / competition connection: prohibited
- HDS judgment: `PASS`

## 1. Work-block FrameSpec

```text
X:
  P4 C/P-A/P-B
  P5 J
  P6 M
  P7 pair insufficiency evidence
  fixed identity-free observation

R:
  full cycle:
    J command -> C compute(P, Observation, M) -> J judgment
    -> J-authorized emit -> observed result -> J result judgment
    -> J-authorized C write -> M -> J finalize
  causal isolation:
    fix two of P/J/M and vary exactly one

Mc:
  cycle-2 proposal cites cycle-1 post-write M version/digest
  M-only changes C output
  P-only changes C output
  J-only leaves C output unchanged and changes judgment/authorization
  same input replay is byte/digest deterministic
  no hidden global state or authority bypass

non-goals:
  all-eight-subset certificate, sample solving, release freeze
```

## 2. Full two-cycle execution

各cycleで次のoperation順序を実traceから検証した。

```text
COMPUTE_COMMAND_ISSUED
HYPOTHESES_AND_CANDIDATES_PROPOSED
CLOSURE_DECISION
AUTHORIZED_EXTERNAL_EMIT_EXECUTED
EMISSION_RESULT_OBSERVED
EMISSION_RESULT_JUDGED
AUTHORIZED_MEMORY_WRITE_EXECUTED
CYCLE_FINALIZED
```

M version遷移:

```text
cycle 1 compute input: 0
cycle 1 post-write   : 1
cycle 2 compute input: 1
cycle 2 post-write   : 2
```

cycle 2の`compute_memory_digest`はcycle 1 post-write snapshot digestと一致する。
`ComputeProposal`と`KernelResult`は入力Mのversion/digestを明示保持し、HDSは
bindingと異なるmemory citationを`PROPOSAL_MEMORY_CITATION_MISMATCH`で拒否する。
M更新payloadにも入力Mのversion/digestを残す。

## 3. Controlled causal isolation

すべて同じObservationとfresh Contextを使用し、変更した入力factorを機械列挙した。

| 比較 | changed inputs | 固定 | 観測された変更 |
|---|---|---|---|
| M-only | `M` | P-A、default J | proposal、hypotheses、predictions、candidates、output proposals、J選択 |
| P-only | `P` | learned M、default J | proposal、hypotheses、predictions、candidates、output proposals、J選択 |
| J-only | `J` | P-A、learned M | J judgment/status/selection/authorizationのみ |

M-onlyでは直接memory-dependentな`predictions`の変化を必須とした。P-onlyは
P-A symbolicとP-B parametricを同一L0/J/Mで交換した。

J-onlyのため`HDSFramePolicy`をtyped J-side stateとして追加した。defaultと
controlled-stop policyの比較ではC proposal/hypotheses/predictions/candidatesが
完全一致し、standalone J statusだけが`ACCEPT -> STOP`、effect authorizationが
`true -> false`へ変化した。

各probeを同じ入力で再実行して完全一致を確認し、changed inputが一因子以外に
増えた場合はhidden-global-state violationとしてFAILする。

## 4. 権限境界

- Jだけがcompute commandとeffect authorizationを発行する
- Cはproposalと許可済みeffect実行だけを行う
- Mはexplicit/authorized operation以外で更新しない
- emission result観測・J再判断より前のmemory writeを許可しない
- stale/tampered M citationを拒否する
- invalid J Frame policyはeffect前にfail-closedする

## 5. 検証

- P8 dedicated tests: 7 PASS
- compileall: PASS
- full unit suite: 180 PASS
- strict mypy: PASS
- ruff: PASS
- integration: 2 PASS
- 25 sample OFFLINE 1-action regression: 25/25 execution、error 0
- controlled report digest:
  `fb772836dfcb4628f68f0581cd2765063585c0fb4f094a691ea04af5f0078758`

P8はG4 temporal causality、G5 full two-cycle loop、P/J/M causal attributionを
`SUPPORTED`とする。全8 subsetの有限列挙、最小証明certificate、全sample攻略、
汎化、release固定は未成立。次phaseはP9。
