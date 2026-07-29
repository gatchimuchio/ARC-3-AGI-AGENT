# P17-B Evidence Binding / Taint / Episode Transaction 実装証拠

- phase: `P17_B_EVIDENCE_BINDING_TAINT_SAFE_EPISODE_TRANSACTION`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P18_ATOMIC_EVENT_SOURCED_PERSISTENT_MEMORY`

## Candidate-specific evidence

全候補へ次の`EvidenceBindingKey`を付与した。

```text
normalized_state_pattern_digest
action_relation_digest
precondition_digest
predicted_effect_digest
applicability_scope_digest
```

`action_relation_digest`はcurrent legal action、role/target、dynamic anchor、
expected-effect classから作り、surface ordinal単独では構成しない。literal座標、
game/task/level ID、exact public frame signatureはkeyに含めない。

取得recordは候補ごとに`CandidateEvidenceBinding`へ変換する。ACTIVE、exact
precondition/effect/scope、support 2件以上、confidence 750,000 ppm以上、
contradiction 0、hazard 0を全て満たしたrecordだけが`execute_eligible`となる。
payload上の`execute_eligibility=true`だけではEXECUTEできない。

HDSの旧global evidence判定を除去し、次へ置換した。

```text
exact hazard binding        → candidate veto
reproduced exact binding    → EXECUTE eligible
probation / mismatch / none → bounded PROBE
REPRODUCED_ONLY + no match  → SUSPEND
```

compute result全体にunrelated citationが存在しても候補はreproducedにならない。
各候補はP instruction、representation、prediction、memory binding、
counter-evidence、runtime versionをtyped provenanceとして保持する。

## Taint boundary

`OrchestrationMetadata`はrunner/adapter境界に限定し、`DecisionContext`とは型分離した。
C/P/J/M public APIはscorecard ID、game ID、game order、environment handle、
opaque episode handleを受け取らない。各cycleのDecisionContextはrendered
observation、available action、payload schema、episode-local observation digest、
memory version、cycle、purposeだけを保持する。

opaque `EpisodeHandle`およびControlState内のhandle fieldはserializerから除外した。
metadata/order permutationは同じsemantic candidate rankingとselectionを生成する。

pointer actionの座標はcurrent renderのcomponent/roleからcycle内で導出し、
current observation digestへ結合する。`PRECOMPUTED`、trajectory、
orchestration由来の座標はfail closedで拒否する。

## Safe episode transaction

`EpisodeTransaction`がepisode開始時にSESSION_GLOBAL active digestとversionを固定し、
level overlay、episode overlay、ControlStateを同一opaque handleへ結合する。

```text
begin episode
→ capture SESSION_GLOBAL base
→ begin level overlay
→ run episode-local writes
→ close level
→ HDS-authorized rollback to base
→ verify final active digest == base digest
→ clear control/overlay
```

失敗・例外を含め、P17-Bでは全episode writeを終了時にdiscardする。
digest不一致またはpromotion発生時はtransactionを`FAILED_CLOSED`にする。
consolidationおよびcross-game semantic promotionは引き続き`DISABLED`である。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P17B-001 unrelated_evidence_false_positive = 0` | PASS | unrelated citation + `REPRODUCED_ONLY` test |
| `P17B-002 candidate_binding_coverage = 100%` | PASS | all generated candidates carry key and typed provenance |
| `P17B-003 failure_overlay_leak = 0` | PASS | failure rollback and active-digest equality test |
| `P17B-004 tainted_decision_input_count = 0` | PASS | API/type/serialization/permutation tests |
| `P17B-005 cross_game_semantic_promotion = DISABLED` | PASS | transaction hard gate and receipt |

必須11試験にcandidate binding coverage試験を追加した計12試験がPASSした。

## Validation

- P17-B dedicated: `12 / 12 PASS`
- phase-state content binding: `1 / 1 PASS`
- corrected P12 operational audit: `1 / 1 PASS`
- final full unit suite: `586 / 586 PASS`
- targeted mypy: `9 source files PASS`
- targeted ruff: `PASS`
- compileall: `PASS`

初回focused回帰では、旧P12 retrieval fixtureがP17-Bのbinding keyを持たず
`L0-001/M-004/M-005/REG-003`を落とした。fixtureを同じruntime key builderで
構築するcompiler-authorized recordへ移行し、製品回帰を解消した。

## 残存境界

- 現行SemanticMemoryはdirect mutation、full-copy snapshot、in-memory provenanceで、
  atomic batch、event log、checkpoint、crash recoveryを持たない。P18対象である。
- causal consolidation、independent support、negative-transfer invalidation、
  cross-game promotionはP19前には有効化しない。
- P-IR/compiler/registry、governed development、CV/sealed final、
  Competition package、official observationは未開始である。
- generic completion、Competition ready、official accepted/public/private/fullは
  未成立・未観測である。
