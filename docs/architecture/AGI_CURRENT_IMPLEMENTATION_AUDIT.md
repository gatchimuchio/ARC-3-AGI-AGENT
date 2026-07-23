# AGI最小三構成 現行実装根本監査

- audit phase: `P2_AGI_MINIMUM_THREE_AUDIT`
- audited commit: `9a1da1a0134ebd8c2afed747cc951b403168bbad`
- roadmap source SHA-256: `742d8237c2472fe63680b0006053b7de71e6fbb0cfc98bc6f1200bae4c77000b`
- roadmap repository LF SHA-256: `bd4e7545fcb6a6c25483ed86bfbedfa44f1ee731af687ed87806e2c6d98ad09b`
- conclusion: P0/P1の限定claimだけがSUPPORTED。AGI最小三構成claimは未成立
- document status: P2時点の監査snapshot。現行phase/statusはobligation graphと
  claim registryを正本とする

## 1. Work-block FrameSpec

```text
X:
  対象 = L0, P, C, J, M, environment, compiler, P0/J0/M0,
         emission, memory write, HDS Frame, cycle, stopping, rollback
  入力 = current source, tests, authority docs, attached roadmap
  変更範囲 = specification, obligation graph, claim/test/traceability audit

R:
  各要素をG1〜G5、state owner、updater、authority、call path、
  test、removal witness、equivalent leakへ対応付ける

Mc:
  同一性 = repository path + symbol + test node
  境界 = current checkout and OFFLINE sample evidence
  採否 = executable evidence only
  停止 = unaccounted element/claim/testが残ればSUSPEND
  rollback = audit文書とvalidator追加だけを戻せる限定差分
  完了 = 全要素accounting、過剰claim 0、P3以降順序確定

非目的:
  P/C/J/M実装、sample攻略、official/Kaggle接続

証拠境界:
  current repository files and executed tests

反証条件:
  未実装要素をSUPPORTEDと分類する
  current call pathに存在しないedgeを実装済みと記録する
  graphとclaim/test docsが不一致

回帰線:
  P1 authority、no-network、OFFLINE、identity-free禁止入力を維持
```

## 2. 現行成立範囲

### A-P2-001 — P0 foundation

- status: `SUPPORTED`
- evidence: protocol、typed IR、schema、verifier、checkpointとunit tests
- limitation: C/J/Mの単独成立は含まない

### A-P2-002 — P1 execution mechanism

- status: `SUPPORTED`
- evidence: 六L0 callable、single-removal、HDS authority、passive ADD-like M、OFFLINE action/re-observation
- limitation: 一action経路でありsample攻略、G4、最小三構成は含まない

### A-P2-003 — environment boundary

- status: `SUPPORTED`
- evidence: non-OFFLINE拒否、direct-step gate、owner-bound directive、signed result、integration no-network
- limitation: OS sandboxやofficial COMPETITION適合の証明ではない

## 3. 必須是正項目

### F-P2-001 — executable P不在

- severity: `BLOCKING`
- observation: `InstructionBodyContract`はlabel/authority契約であり、query可能な情報体ではない
- evidence: `PureLLMCompute`は`world_model.transform`と`candidate_surface.generate`を直接呼ぶ
- consequence: `C = Execute(L0, P)`不成立
- correction phase: `P4`

### F-P2-002 — Cの情報内容がcodeへ埋込み

- severity: `BLOCKING`
- observation: `roles.py`がhypothesis、confidence、candidate metricを固定保持
- consequence: P removal/swap、P-only因果が試験不能
- correction phase: `P4`

### F-P2-003 — Jはintegrated controllerでstandalone主体ではない

- severity: `BLOCKING`
- observation: `HDSController.judge`は内部proposal/closure/contextを直接受け、typed standalone HDS Frame fixture APIがない
- consequence: C/MなしでG2を単独証明できない
- correction phase: `P5`

### F-P2-004 — Mがfull mutable memoryではない

- severity: `BLOCKING`
- observation: operation labelは複数あるが、現行storageはDELETE以外を同型replacementとして扱う
- missing: REVISE、MERGE、SPLIT、REPLACE、INVALIDATE、REINDEX、ROLLBACK、ARCHIVE、QUERY、version conflict、active/archive
- consequence: G3未成立
- correction phase: `P6`

### F-P2-005 — G4時間因果未証明

- severity: `BLOCKING`
- observation: action後stateは次cycleへ入力されるが、Mだけを変更してfuture C/Jが変わるcontrolled testがない
- consequence: state propagationをlearningと呼べない
- correction phase: `P8`

### F-P2-006 — pair/subset証明不在

- severity: `BLOCKING`
- observation: 六L0責任のremoval auditはあるが、C/J/Mの三pairと全8 subsetの実行列挙がない
- consequence: 最小三構成を主張できない
- correction phase: `P7`, `P9`

### F-P2-007 — ARC3実証素材compiler不在

- severity: `BLOCKING`
- observation: current repoは25 environment source/metadataを持つが、全解析data accounting、identity-free corpus、C/J/M fixture、holdout manifestがない
- consequence: P-A/P-B trainingとstandalone J/M fixtureのprovenanceが閉じない
- correction phase: `P3`

### F-P2-008 — P0/J0/M0 release initial state不在

- severity: `MAJOR`
- observation: default constructorsはあるが、dataset/compiler/version/digestに束縛されたrelease bundleではない
- consequence: acquired capabilityの再起動再現性がない
- correction phase: `P11`

### F-P2-009 — rollbackは語彙だけ

- severity: `BLOCKING`
- observation: status/operation constantは存在するが、J condition、M version restore、result verificationがない
- consequence: J/Mの必須責任が未閉包
- correction phase: `P5`, `P6`

### F-P2-010 — P10/P11証拠不在

- severity: `EXPECTED_GAP`
- observation: 25 game各1 action smokeだけで、全level完了・release freezeはない
- consequence: sample complete/release-ready claimは禁止
- correction phase: `P10`, `P11`

## 4. 過剰主張監査

| 対象 | current wording | 判定 |
|---|---|---|
| P0 | foundation complete | 妥当 |
| P1 | execution mechanism complete/reclassified | 妥当 |
| C complete | 主張なし | 妥当 |
| J standalone | 主張なし | 妥当 |
| M full functions | 主張なし | 妥当 |
| two-cycle learning | 主張なし | 妥当 |
| AGI minimum three | 主張なし | 妥当 |
| sample complete | 主張なし | 妥当 |
| generalization | 主張なし | 妥当 |

P2 audit追加時点の過剰claim件数は`0`。

## 5. P3以降の実装順序決定

監査結果から、次のdependency chainを固定する。

```text
F-P2-007 dataset/compiler
  -> F-P2-001/F-P2-002 P and C
  -> F-P2-003 standalone J
  -> F-P2-004/F-P2-009 mutable M and rollback
  -> F-P2-006 pair audit
  -> F-P2-005 two-cycle causality
  -> F-P2-006 eight-subset certificate
  -> F-P2-010 sample solving
  -> F-P2-008 release freeze
```

## 6. P2 gate

P2はruntime capabilityを増やすphaseではなく、未実装と証拠境界を固定するphaseである。

完了条件:

- `AGI_MINIMUM_THREE_SPEC.md`: 全主体・義務・権限を固定
- `AGI_OBLIGATION_GRAPH.json`: G1〜G5、要素、edge、subset、claimを機械可読化
- `AGI_TRACEABILITY_MATRIX.md`: 全監査項目を実装/test/gapへ対応
- `AGI_CLAIM_REGISTRY.md`: unsupported claimを明示
- `AGI_TEST_MATRIX.md`: current/future testと反証条件を固定
- 本書: current implementation findingとP3以降順序を固定
- `test_agi_minimum_three_audit.py`: accountingと過剰claim禁止を実行検証

上記validatorがPASSした時点で、HDS判断は`PASS`、次phaseは`P3_ARC3_EVIDENCE_MATERIAL_COMPILER`とする。

## 7. P3 disposition

P3完了時点で`F-P2-007`のうち、次を是正した。

- 730/730 source accounting、parse error 0
- identity-free observation/transition/effect/hazard/progress/contradiction corpus
- C/J/M fixture分離
- source/record双方向provenance
- family/structure/action-mechanism holdout
- runtime identity/source filename漏洩0
- fixed seedによる全12生成物のbyte再現

実装・証拠は
[`P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md`](P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md)
を正本とする。

`F-P2-007`全体をCLOSEDとはしない。versioned P0/J0/M0を形成するlearning compilerは
P4/P5/P6/P11へ残るため、machine statusは`PARTIAL`である。P3 HDS判断は`PASS`、
次phaseは`P4_COMPUTE_SUBJECT_C`とする。

## 8. P4 disposition

P4完了時点で`F-P2-001`と`F-P2-002`を是正した。

- query可能・versioned・digest/provenance付きのP-A/P-Bを形成
- P3 C fixtureからP-Bを実学習し、holdout BCEをbaseline未満に維持
- `roles.py`の固定仮説/metricを除去し、P materialの実行mechanismへ縮退
- standalone CでG1を閉じ、J/M/write/emitの代行がないことをnegative test
- L0六責任/P/Cの8 single-removalを固有witnessで検証
- 25/25 OFFLINE sample cycleでP queryを観測

`F-P2-003`以降は未解決である。P4 HDS判断は`PASS`、次phaseは
`P5_JUDGMENT_SUBJECT_J`とする。
