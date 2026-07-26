# ARC3 AGI 外部適合監査 rev1

- audit id: `EXTERNAL_AGI_CONFORMANCE_AUDIT_REV1`
- source package: `ARC3_AGI_監査修正パッケージ_rev1.zip`
- source package SHA-256:
  `566506d3de7e60667fcc2d6c7ca061c857702a63652e7f0ed29a4db15b5f328f`
- scope: frozen P11 known-sample release and the active S5 call path
- current correction phase: `P12_PRE_OFFICIAL_AGI_CONFORMANCE_AND_GENERICITY`
- official API / Competition / Kaggle: forbidden

Package内5文書の保持先:

| Source entry | Repository disposition |
|---|---|
| `00_ARC3_初回監査訂正と差戻し一覧_rev1.md` | 本監査書のclaim訂正と`O-001`〜`O-018` |
| `01_ARC3_AGI修正戦略_rev1.md` | `P12_PRE_OFFICIAL_GENERICITY_STRATEGY.md` |
| `02_Codex実装修正指示書_rev1.md` | `AGENTS.md`、P12実装、machine-readable reports |
| `03_ARC3_AGI受入仕様書_rev1.md` | `ARC3_AGI_ACCEPTANCE_SPEC_REV1.md` |
| `ARC3_AGI_監査修正統合版_rev1.md` | authority順序とP12 final gate |

## 1. 訂正後の主張

```text
MINIMUM_THREE_STRUCTURAL_CERTIFICATE: SUPPORTED
KNOWN_SAMPLE_CLOSURE: PASS
REPRODUCIBLE_RELEASE_FREEZE: PASS
S5_OPERATIONAL_AGI_CONFORMANCE: SUSPEND
GENERICITY: NOT_ESTABLISHED
OFFICIAL_COMPATIBILITY: NOT_EVALUATED
OFFICIAL_READINESS: BLOCKED
OFFICIAL_SCORE: NOT_AVAILABLE
```

P11の25 game / 183 level、10,733 action、RHAE
99.619936696%、full trace、weights、manifest、digestは変更しない。これらは
保持済みsampleに対するfrozen `KnownSampleStudent`の証拠であり、未知環境の
汎化、operational AGI conformance、公式互換性を証明しない。

## 2. Blocking findings

| ID | Finding | Required correction |
|---|---|---|
| `O-001` | Layer-0 F1の選択的・関係条件付き参照がactive S5 pathで証明されていない | retrieval traceと除去時の固有劣化を示す |
| `O-002` | Layer-0 F3が一つのP-selected actionをIRへ包装する経路へ縮退し得る | `represent→retrieve→model→predict→candidate`を状態依存で実行する |
| `O-003` | Cの複数仮説・候補が独立生成ではなく形式的複製になり得る | 独立modelと意味的に異なる合法action候補を生成する |
| `O-004` | Jがauthorization gateに留まり、独立Judgement Subjectである証拠が不足 | purpose/risk/Mc/evidenceのJ-only変更で採否を変える |
| `O-005` | S5 Mは`max_entries=1`のbounded action historyで、意味記憶主体に不足 | hypothesis、反証、failure、procedure、rationale等をactive Mへ保持する |
| `O-006` | 4,269,485 parameter・train error 0のS5 Pは暗黙replayの可能性を排除していない | whole-game/mechanism holdoutとreplay probeを実行する |
| `O-007` | 同一actionを`ACTION`/`BOUNDED_PROBE`として複製している | action、target、planの異なる候補を数える |
| `O-008` | HDS G00〜G15、F/Md/Cm/U、next-questionがactive S5 loopで未実証 | full DecisionRecordとgate ablationを実行する |
| `O-009` | P/Cが先にactionを固定しJが追認するfunctional self-commitの危険がある | C proposalとJ commitを因果分離する |
| `O-010` | bounded history conditioningだけではruntime/version learningを証明しない | semantic M因果とP candidate promotion/rollbackを実行する |
| `O-011` | exact action-surface headは未知合法surfaceで例外停止し得る | shared action modelとlegal maskを実装する |
| `O-012` | absolute pixel/palette/coordinate依存が残る | object/role/relation/topology/relative geometryを導入する |
| `O-013` | S6は静的response測定でsemantic correctnessを持たない | 七変換をenvironmentとして実行しcompletionを測る |
| `O-014` | official Competition adapterは未実装 | 公式接続せずmock contract dry-runを先に閉じる |
| `O-015` | Competition reset責任が未検証 | level reset semanticsをmockで検証する |
| `O-016` | 400/429/5xx、single-make、exactly-onceが未検証 | bounded retry、dedup、SUSPENDをmockで実行する |
| `O-017` | resource/package/securityのpre-official証拠が不足 | latency/RSS/package/secret/source/network監査を生成する |
| `O-018` | P9 certificateとS5 operational conformance、trainer/evaluator独立性を混同していた | claimを分離しsealed evaluatorを別processにする |

全findingはblockingである。対応する受入IDが実行証拠付きで`PASS`になるまで、
`PRE_OFFICIAL_AGI_READY`を主張してはならない。

## 3. P11 immutability boundary

次はread-only baselineである。

- `analysis/release/P11_RELEASE_STATE.json`
- `analysis/release/P11_REGRESSION_REPORT.json`
- `analysis/release/P10_REPRODUCIBILITY_AUDIT.json`
- `analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json`
- `analysis/runtime/S5_FULL_EXECUTION_TRACE.jsonl.gz`
- `analysis/runtime/S5_FULL_EXECUTION_TRACE_MANIFEST.json`
- `ARC-AGI-3-Agents/arc3_agi_agent/bundles/s5_rendered_policy_v1.json`
- `ARC-AGI-3-Agents/arc3_agi_agent/bundles/s5_rendered_policy_v1.npz`
- `analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.*`

固定digest:

```text
arc3_p11_release_state:
e7d8ef522f8f0004a63875a7da3cdcc084684388325411a994e751d6e251eb8c
```

## 4. HDS disposition

```text
assertion_state: SUSPEND
operation_state: CONTINUE_P12_CORRECTION
rollback_target: P11 frozen release
official_connection: FORBIDDEN
next_question:
  Can the separate GenericAGIRuntime close every blocking acceptance item
  without mutating or falling back to KnownSampleStudent?
```

## 5. Correction execution result

`GenericAGIRuntime`と独立監査器を実装し、受入57件を固定runtime
commit `a2a146976bb25ed84603e9f6b7f534e3b961b58b`、固定audit commit
`ff6d3f6a85c2818c0f751c3b3fdc4f373d72f912`で実行した。

- 56/57 requirement: `PASS`
- `GEN-001`: `SUSPEND`
- whole-game holdout: 25/25 gameを各一回実行、完了0、progress 1 game、
  4/5 fold progress 0
- runtime crash、identity/source leak、unknown-action exception、
  scorecard close failure: 各0
- mechanism holdout、七変換、sealed 3 game、implicit replay audit:
  `PASS`
- operational C/J/M/P/Trinity/learning、Competition mock、
  resource/package/security: `PASS`
- fresh frozen-baseline回帰: 183/183、RHAE 99.619936696%、
  P11固定hash全件不変
- official connection / `OperationMode.COMPETITION` / Kaggle: 未実行

よって外部監査の過大claimは是正されたが、genericity完成claimは成立しない。
`PRE_OFFICIAL_AGI_READY`とP13移行は引き続き`SUSPEND`とする。
