# P19 Typed Causal Memory / Consolidation / Negative Transfer 実装証拠

- phase: `P19_TYPED_CAUSAL_MEMORY_CONSOLIDATION_NEGATIVE_TRANSFER`
- status: `PASS`
- date: `2026-07-30`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- code binding: `UNCOMMITTED_WORKTREE`
- next phase: `P20_A_FIXED_L0_INSTRUCTION_SET_P_IR_ABI`

## Typed causal record

`SemanticRecord`のpayloadへ暗黙のcounterを置く経路を、明示schemaを持つ
`CausalRecord`へ置換した。recordは次を保持する。

- normalized state/action/effectから成るcandidate固有binding key
- precondition、learned effect、delay window、applicability scope
- unique evidence groupとevent provenance
- support / contradiction / hazardの独立group数
- ppm整数のconfidence
- `PROPOSED / PROBATION / ACTIVE / SUSPENDED / REJECTED`
- execute / probe eligibility

evidence group IDはnormalized before、action relation、normalized after、
delay window、non-search episode nonceから決まり、同一groupの重複引用を
二重加算しない。exact hazardはexecuteを常にvetoする。

## Retrieval、consolidation、negative transfer

retrievalはTier 0〜3とscore breakdownを返す。applicability不一致、
contradiction、hazardを独立評価し、Tier 3はprobe専用とした。typed schemaを
持たずにexecute eligibilityを主張するrecordはfail closedで除外する。

成功episodeのlevel/episode causal recordは、episode overlayのrollback後に
一つのatomic promotion batchとしてsession-globalへconsolidateする。
一episodeだけの知識は`PROBATION`に留まり、独立二episodeかつ規定support/confidenceを
満たす場合だけ`ACTIVE`候補になる。identity payloadはsession-global化前に除去する。
失敗episodeはpromotionせず、base digestへrollbackする。

negative-transfer判定は`ACCEPT / IGNORE / VETO / INVALIDATE / REJECT`を型として
返す。irrelevant priorは候補順位を変えず、exact hazardはvetoし、
矛盾でsuspend/rejectされたrecordにはinvalidation proposalを生成する。

## J world-knowledge migration

旧`ControlState.selector_deltas`と`value_actions`を除去し、候補選択へ影響する
構造知識をMのtyped causal recordへ移した。Jはevidence policyとpromotion可否を
判断するが、私有world-learning stateを保持しない。

`GenericAGIRuntime`は各outcomeを`ACTION_EFFECT`または`HAZARD_MODEL` causal recordへ
変換し、P18のmandatory atomic batchへ渡す。三つの独立成功episodeを通した
integration試験では、session-global recordがsupport 3、distinct episode 3で
`ACTIVE`へ到達し、後続候補計算へ実際に影響した。

## Gate

| Gate | Result | Evidence |
|---|---|---|
| `P19-001 typed_causal_record = PASS` | PASS | schema/policy/round-trip tests |
| `P19-002 memory_causal_witness_count > 0` | PASS | runtime active causal witness 1以上 |
| `P19-003 cross_level_transfer = PASS` | PASS | level→episode→session consolidation test |
| `P19-004 negative_transfer_suite = PASS` | PASS | irrelevance/order/adversarial/invalidation tests |
| `P19-005 hidden_j_world_knowledge_count = 0` | PASS | ControlState/HDS source audit |
| `P19-006 cross_game_semantic_promotion = ENABLED` | PASS | gated session defaultとruntime integration |

## Validation

- P19 required tests: `14 / 14 PASS`
- P19 runtime promotion integration: `1 / 1 PASS`
- P12/package/P19 focused regression: `26 / 26 PASS`
- full unit suite: `615 / 615 PASS`
- targeted mypy: `14 source files PASS`
- targeted ruff: `PASS`
- compileall: `PASS`

## 残存境界

- P-IR、L0 ABI、P compiler/bundle/registryはP20-A/Bまで未開始である。
- governed development、CV/sealed final、Competition package、official observationは
  未開始である。
- 本証拠は未コミットworktreeへ結合されており、commit/treeによるrelease固定ではない。
- generic completion、Competition ready、official accepted/public/private/fullは
  未成立・未観測である。
