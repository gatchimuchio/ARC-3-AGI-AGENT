# ARC-3 AGI Agent ロードマップ索引

## 正本

現行ロードマップの全文正本は次である。

- [`P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2.md`](P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2.md)
- source/repository SHA-256:
  `c8897ce4b379865aea091b04cdf3a1f772a5f3765ef20744998e58d65ba6c687`
- upper specification:
  [`ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2.md`](../architecture/ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2.md)
- specification SHA-256:
  `9746e981e504e46b8563aa8a342aa567937762363d66a288ff8235a5c29591c2`

本索引はphase状態だけを保持し、正本本文を重複しない。

P0〜P15の旧ロードマップとP10補正はhistorical evidence boundaryとして保持する。

- [`AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`](AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md)
- [`P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`](P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md)

## 現在状態

| Phase | 名称 | 状態 |
|---|---|---|
| P0 | Clean Restart Foundation | 完了 |
| P1 | Execution Mechanism Foundation | 完了・再分類 |
| P2 | AGI最小三構成仕様・根本監査 | 完了 |
| P3 | ARC3実証素材コンパイラ | 完了 |
| P4 | 計算主体Cの単独実装 | 完了 |
| P5 | HDS判断主体Jの単独実装 | 完了 |
| P6 | 記憶主体Mの単独実装 | 完了 |
| P7 | 二主体接続監査 | 完了 |
| P8 | 三主体Trinity循環 | 完了 |
| P9 | 全8部分集合監査 | 完了 |
| P10 | ARC3全sample完全攻略 | 完了 |
| P11 | 完成状態固定 | 完了 |
| P12 | Pre-official AGI conformance / genericity | historical rev1 complete |
| P13 | 旧公式ARC環境接続 | historical incomplete |
| P14 | 旧Kaggle提出経路 | historical preflight |
| P15 | 旧実提出・結果 | historical incomplete、official scoreなし |
| P16 | Claim / threat / evaluation rebaseline | 完了・6/6 PASS |
| P17-A | CognitiveSession / state ownership | 完了・6/6 PASS |
| P17-B | Evidence binding / taint / overlay rollback | 完了・5/5 PASS |
| P18 | Atomic event-sourced memory | 完了・6/6 PASS |
| P19 | Causal memory / consolidation | 完了・6/6 PASS |
| P20-A | Fixed L0 / typed P-IR | 完了・5/5 PASS |
| P20-B | P compiler / bundle / registry | 完了・6/6 PASS |
| P21 | Governed development loop | 完了・6/6 PASS |
| P22-A | Known public / CV / transformation stress | 進行中・focused public 1/25 PASS |
| P22-B | Sealed single-artifact final | 未開始 |
| P23 | Competition session / resource / package | 未開始 |
| P24 | Official observation | 未開始・Owner許可必須 |

## 現在のphase gate

最終完了phaseは`P21_GOVERNED_DEVELOPMENT_LOOP_JOINT_OPTIMIZATION`である。
現行work blockは`P22_A_PUBLIC_CV_TRANSFORMATION_STRESS`である。
compiled PのGeneric runtime統合とfocused public 1/25はPASSしたが、
全25 game / 183 level、CV、七変換、memory ablationは未完了である。

```text
P16-001 claim_overstatement = 0
P16-002 active_runtime_count = 1
P16-003 evaluation_role_registry = PASS
P16-004 identity_taint_threat_model = PASS
P16-005 completion_predicates = PASS
P16-006 rev1_status = HISTORICAL_NON_BLOCKING
```

P20-Aは5/5、P20-Bは6/6 gateをPASSした。P21ではdataset access ledger、
versioned M_dev、CV artifact分離、Code/P/M migration、三世代lineage、
active runtime一件性を実装し、6/6 gateをPASSした。
次に許可されるwork blockはP22-Aのknown public/CV/stress評価だけである。

## Historical evidence boundary

P10は完全閉包先行・水平減算の順で閉じた。

- S0〜S5: 全段`PASS`
- S5 Runtime Student: 25/25 game、183/183 level、10,733 action、error 0
- S5入力: rendered observation、available action、bounded history、受動M
- local oracle: completion 100%、RHAE 99.619936696%
- S5 full rerun: 二回byte-identical
- S5 full execution trace: 全10,733 cycle保存、closure相互検証、
  trace/manifest二回byte-identical
- S6: 25 game・183 levelを覆う2,048 record、七摂動14,336 measurement
- S6 full rerun: 二回byte-identical
- S6 claim: `MEASURED_NOT_PROVEN`

P11は次を固定して完了した。

- code commit/tree、dependency lock、Python versionの固定
- P0/J0/M0、dataset/compiler、seed、action budgetの固定
- P0〜P10 full regressionとtracked secret scan
- reproducible wheel buildとpackage内容・digest監査
- 全sample・全実行trace・authority・水平減算・S6証拠のrelease manifestへの束縛

- code commit: `823c51b68d7f1a2570a3c68f8f21a3819c650154`
- regression: 7/7 PASS、tracked secret finding 0
- wheel: 二回byte一致、SHA-256
  `a2f7c400753a553b49247ce7627e2b966fd152153b53064e7403e553659e551a`
- release digest:
  `arc3_p11_release_state:e7d8ef522f8f0004a63875a7da3cdcc084684388325411a994e751d6e251eb8c`

P11はRuntime P、score、sample能力を変更していない。P11/S5は
known-sample closure baselineとして凍結する。P12はoperational
AGI conformance、genericity、Competition contract mock dry-runを実装・反証し、
rev1 blocking受入57/57 PASSで完了した。この判定は
`HISTORICAL_NON_BLOCKING`であり、rev2 generic completionを意味しない。
P13〜P15ではOwner明示許可により、
25ゲームの逐次ローカルcompetition互換12/12と、Kaggle Notebook
version 8通常実行・公式placeholder row/column/type照合をPASSした。実提出APIは
versions 4、5、7、8から四回呼び、refs `55040966` / `55043205` /
`55045360` / `55049227`はすべてKaggle system error、scoreなし・
total bytes 0で終了した。version 7でformat単独原因、version 8で
全ゲーム同時thread競合単独原因を棄却した。episode APIは受理済みrefsにも0を
返すためgateway位置の根拠にしない。当時のHDS snapshotはSUSPENDで、
official scoreは得られなかった。当時の次候補は公式parquetの実行前fallback、
private failure telemetry、
environment release隔離を含み、Notebook 25/25・unit 555/555・integration 8/8・
64x64負荷監査をPASSした。Kaggle version 10として通常実行COMPLETE、
source 4セル一致、traceback/error 0、2648-byte出力回収もPASSした。
version 9はMCP転送時の文字列省略で壊れた未提出artifactとして棄却した。
これらはP16以降のactive selector、提出指示、`COMPETITION_READY`証拠ではない。

## 監査正本

- [`AGI_MINIMUM_THREE_SPEC.md`](../architecture/AGI_MINIMUM_THREE_SPEC.md)
- [`AGI_OBLIGATION_GRAPH.json`](../architecture/AGI_OBLIGATION_GRAPH.json)
- [`AGI_TRACEABILITY_MATRIX.md`](../architecture/AGI_TRACEABILITY_MATRIX.md)
- [`AGI_CLAIM_REGISTRY.md`](../architecture/AGI_CLAIM_REGISTRY.md)
- [`AGI_TEST_MATRIX.md`](../architecture/AGI_TEST_MATRIX.md)
- [`AGI_CURRENT_IMPLEMENTATION_AUDIT.md`](../architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md)
- [`ARC3_AGI_ACCEPTANCE_SPEC_REV1.md`](../architecture/ARC3_AGI_ACCEPTANCE_SPEC_REV1.md)
- [`EXTERNAL_AGI_CONFORMANCE_AUDIT_REV1.md`](../audit/EXTERNAL_AGI_CONFORMANCE_AUDIT_REV1.md)
- [`P12_PRE_OFFICIAL_GENERICITY_STRATEGY.md`](P12_PRE_OFFICIAL_GENERICITY_STRATEGY.md)
- [`ARC3_GENERIC_REAUDIT_REV2.md`](../audit/ARC3_GENERIC_REAUDIT_REV2.md)
- [`IDENTITY_TAINT_THREAT_MODEL.md`](../security/IDENTITY_TAINT_THREAT_MODEL.md)
- [`EVALUATION_ROLE_REGISTRY_SPEC.md`](../evaluation/EVALUATION_ROLE_REGISTRY_SPEC.md)
- [`OFFICIAL_COMPLETION_PREDICATES.md`](../official/OFFICIAL_COMPLETION_PREDICATES.md)

後続phaseの存在を理由に、現在phaseを飛ばしてはならない。
