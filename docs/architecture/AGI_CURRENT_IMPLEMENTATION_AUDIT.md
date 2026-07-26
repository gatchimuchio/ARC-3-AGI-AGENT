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

## 9. P5 disposition

P5完了時点で`F-P2-003`を是正した。

- purpose/X/R/Mc/evidence/risk/budget/unknownを持つtyped HDS Frame
- C/P/Mなしのstandalone deterministic judgment
- accept/reject/reobserve/SUSPEND/STOP/ROLLBACK/compute request
- write/emit authorization判断とeffect capabilityの分離
- integrated HDSを同一判断coreへ接続し、旧判断fallbackを除去
- 676/676 P3 HDS Frame fixture適合とJ除去固有witness

`F-P2-004`以降は未解決である。P5 HDS判断は`PASS`、次phaseは
`P6_MEMORY_SUBJECT_M`とする。

## 10. P6 disposition

P6完了時点で`F-P2-004`を是正した。

- mutation 10種とread 5種を異なるstorage意味論として実装
- optimistic version conflict、snapshot history、指定版rollback
- active/archive分離、deterministic query、provenance ledger
- HDS owner-bound runtime adapterでpayload/version/single-useを検証
- 687/687 P3 memory lifecycle fixture適合
- MがG1/G2を代行しないこととM除去固有witnessを検証

`F-P2-005`と`F-P2-006`は未解決である。P6 HDS判断は`PASS`、次phaseは
`P7_PAIRWISE_SUBJECT_AUDIT`とする。

## 11. P7 disposition

P7完了時点で`F-P2-006`のpair部分を是正した。

- `{C,J}`、`{C,M}`、`{J,M}`が各自の成立責任を実行
- 各pairが欠落主体の責任でだけFAIL
- 固定witness三種の重複0
- missing-subject field/fallback、runtime write越境、生成代行0
- 同一pair instanceの再実行でevidence一致

`F-P2-005`と`F-P2-006`の全8 subset部分は未解決である。P7 HDS判断は
`PASS`、次phaseは`P8_THREE_SUBJECT_TWO_CYCLE_TRINITY`とする。

## 12. P8 disposition

P8完了時点で`F-P2-005`を是正した。

- full command/compute/judge/emit/observe/rejudge/write/finalizeを二周期実行
- cycle 2がcycle 1 post-write M version/digestを引用
- M-onlyでmemory-dependent predictionが変化
- P-onlyでC output、J-onlyでJ decision/authorizationだけが変化
- same-input replay一致、hidden global delta 0、authority越境0

`F-P2-006`の全8 subset部分は未解決である。P8 HDS判断は`PASS`、
次phaseは`P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`とする。

## 13. P9 disposition

P9完了時点で`F-P2-006`の全8 subset部分を是正した。

- 空集合、single 3件、pair 3件、full Trinityを固定順序で実行
- proper subset 7件FAIL、full set 1件PASS
- single removal 3件、pair failure 3件を固有witnessへ対応
- 欠落主体fieldと欠落主体固有出力の機能等価物漏れ0
- certificate、subset、witness、obligation graph、conformance reportを生成
- 同一入力・同一graphから5 artifactをbyte一致で再生成

`F-P2-010`の全sample攻略と`F-P2-008`のrelease freezeは未解決である。
P9 HDS判断は`PASS`、次phaseは`P10_COMPLETE_ARC3_SAMPLE_SOLVING`とする。

## 14. P10 disposition

P10完了監査で`F-P2-010`の全sample攻略部分を是正した。

- P-A、P-B、hybridを同一条件で比較し、content digest付き証拠へ固定
- S0からS5まで特権情報を順序通り減算し、各段183/183・error 0
- S5 Runtime Pはrender、available action、bounded history、受動Mだけを入力
- task/game/level ID routing、replay、answer map、固定action列、
  literal座標table、source/hidden stateのRuntime使用0
- GAME_OVER 12件をHDS rejection、outcome retention、policy resetで回復
- Mに保持した履歴が10,708件の未来decisionへ因果入力
- S4安定経験を明示compilerでversioned S5 parameter bodyへ更新
- seed 0のclosure report、全10,733 cycle traceを二回byte一致で再生成
- 全cycleのC出力、HDS判断、M/emission結果、kernel eventを圧縮JSONLへ保存し、
  game別closure trace digestと相互検証
- S6七摂動14,336件を測定し、結論を`MEASURED_NOT_PROVEN`へ限定

旧S5正本はgame別trace digestだけを保持し、roadmapの「全実行traceを保存」を
満たしていなかった。P0〜P11再監査でこれをblocking gapとして再開し、
full trace stream、manifest、tamper/coverage/byte-rerun testを追加した。

P10 HDS判断は、full trace二回再生成とP10 reproducibility auditがPASSした時点で
`PASS`とする。次phaseは`P11_RELEASE_STATE_FREEZE`である。

## 15. P11 disposition

P11完了時点で`F-P2-008`と`F-P2-010`のrelease固定部分を是正した。

- code commit/tree、Python 3.12.13、dependency lockを固定
- versioned/digest-bound P0、空のJ0/M0を固定
- dataset/compiler/seed/action budget/sample ZIPを固定
- S5 closure、全実行trace、authority、oracle、水平減算、S6証拠を束縛
- compileall、ruff、strict mypy、全unit/integration、diff、secret scanを固定
- fixed epochでwheelを二回buildし、byte/content/package digestを固定
- official connection、competition mode、Kaggleは未実行・P12以降へ保持

P11 HDS判断は、release manifestがcurrent code commitと全証拠を検証し、
regression 7/7、wheel byte一致を満たした時点で`PASS`とする。
未知task汎化とofficial readinessは引き続き未主張である。
