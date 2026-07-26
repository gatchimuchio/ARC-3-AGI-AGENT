# P12 Pre-Official AGI Conformance and Genericity Strategy

- phase: `P12_PRE_OFFICIAL_AGI_CONFORMANCE_AND_GENERICITY`
- baseline: frozen P11 `KnownSampleStudent`
- active implementation: separate `GenericAGIRuntime`
- normative acceptance: `docs/architecture/ARC3_AGI_ACCEPTANCE_SPEC_REV1.md`
- official API / `OperationMode.COMPETITION` / Kaggle / submission: forbidden

## 1. Goal

P11のknown-sample closureを変更せず、未知environmentで三主体の固有責任、
runtime/version learning、identity-free genericity、Competition契約のmock
適合を実行証拠で閉じる。

```text
KnownSampleStudent -- read-only regression baseline

GenericAGIRuntime:
  J.frame / next question
  → M selective retrieval
  → C Execute(L0,P)
  → independent models and diverse candidates
  → J G00-G15 / commit
  → authorized action, probe, rollback, suspend or stop
  → re-observation and attribution
  → J-authorized semantic M revision
  → next question
```

## 2. Absolute work-block order

| WB | Work | Exit gate |
|---|---|---|
| `WB-0` | external audit correction and claim reset | overclaim 0、P11 digest unchanged |
| `WB-1` | active-path ownership graph and S5 conformance audit | owner/gap/leak machine accounting |
| `WB-2` | separate GenericAGIRuntime | autonomous multi-cycle, no S5 fallback |
| `WB-3` | L0/C selective retrieval, nonlinear P, serial depth, model/candidate diversity | causal ablations |
| `WB-4` | HDS Judgement Subject and G00-G15 | J-only deltas and veto |
| `WB-5` | semantic mutable M | lifecycle operations and read/write causality |
| `WB-6` | generic P/action surface/relational representation | unseen action and holdout manifests |
| `WB-7` | runtime and version learning | candidate P promotion or rollback by blind holdout |
| `WB-8` | five-fold, mechanism, seven transformations, sealed evaluator | executable genericity report |
| `WB-9` | Competition contract mock dry-run | OFF-001〜008, no official connection |
| `WB-10` | resource/package/security/release gate | acceptance-wide content-bound decision |

後続WBの存在を理由に順序を飛ばさない。あるWBが`SUSPEND`なら原因と
rollback targetを記録し、公式接続へ進まない。

## 3. Runtime and evidence boundaries

Runtime入力:

- current rendered observation
- legal available actions
- action/effect history
- HDS-approved semantic M view
- identity-free, versioned P

Runtime禁止入力:

- task/game/level ID
- replay/answer map/trajectory position
- render-hash answer lookup
- source/hidden state
- game-specific operator routing
- KnownSampleStudent/Teacher fallback

Development/evaluation orchestrationはgame IDをfold accountingまたはenvironment
creationにのみ保持できる。C/P/J/Mへ渡してはならない。

## 4. Learning boundary

```text
runtime:
  observation → attribution → J authorization → semantic M revision

version:
  multiple evidence
  → PUpdateProposal
  → separate HDS compile authorization
  → immutable candidate P
  → blind holdout regression
  → promotion or rollback
```

runtimeはtrainerを直接呼ばず、candidate Pはactive Pを上書きしない。

## 5. Phase sequence after P12

```text
P12 pre-official AGI conformance and genericity
  ↓ all blocking requirements PASS and Owner phase authorization
P13 official ARC connection
  ↓ official compatibility PASS
P14 Kaggle CLI / official MCP route
  ↓ build/output/status PASS and explicit submission authorization
P15 actual submission and official-result optimization
```

P12で実施できるCompetition作業はmock/staging contract dry-runだけである。

## 6. Final HDS decision

`PRE_OFFICIAL_AGI_READY`は受入仕様の全blocking IDが実行証拠付き`PASS`の
場合だけ成立する。それ以外は次を出力する。

```text
assertion_state: SUSPEND
failed_requirement_ids: [...]
required_information: [...]
next_probe: ...
rollback_target: P11 frozen release
next_question: ...
```

## 7. Current audited result

- frozen runtime commit/tree:
  `a2a146976bb25ed84603e9f6b7f534e3b961b58b` /
  `4f1a245060b57eebc57dab208f96bb06966b1e56`
- frozen audit commit/tree:
  `ff6d3f6a85c2818c0f751c3b3fdc4f373d72f912` /
  `e2244e166766c388d87bf924956414b616c41f1a`
- acceptance: 57件中56件`PASS`
- remaining blocker: `GEN-001`
- whole-game evidence: 25/25 game、完了0、progress 1 game、
  4/5 fold progress 0、crash/leak/unknown-action/scorecard-close failure 0
- mechanism holdout、七変換、sealed 3 game、implicit replay audit、
  Competition mock、learning、resource/package/securityは`PASS`
- fresh KnownSampleStudent回帰: 25/25 game、183/183 level、
  10,733 action、error 0、RHAE 99.619936696%、frozen traceとbyte同一
- P11 release digest:
  `arc3_p11_release_state:e7d8ef522f8f0004a63875a7da3cdcc084684388325411a994e751d6e251eb8c`
  は不変
- final release state:
  `arc3-pre-official-agi-release-state-v1:a3b410ee1cf1705df81b46875fbbf2980a4e4936a124c3e7fba5d67673456f59`

したがって現行HDS判断は`SUSPEND`であり、P13公式接続は開始しない。
