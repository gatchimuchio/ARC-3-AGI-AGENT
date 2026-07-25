# ARC-3 AGI Agent ロードマップ索引

## 正本

現行ロードマップの全文正本は次である。

- [`AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`](AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md)
- source attachment SHA-256: `742d8237c2472fe63680b0006053b7de71e6fbb0cfc98bc6f1200bae4c77000b`
- repository LF-normalized SHA-256: `bd4e7545fcb6a6c25483ed86bfbedfa44f1ee731af687ed87806e2c6d98ad09b`

本索引はphase状態だけを保持し、正本本文を重複しない。

P10の現行開発単位と証拠境界は、次の補正正本を追加適用する。

- [`P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`](P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md)
- source attachment SHA-256: `113ac0516e500679792e57fbc73f21ad078d19929ae39c11ff185ac1f9a353ef`

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
| P10 | ARC3全sample完全攻略 | 現在 |
| P11 | 完成状態固定 | 未開始 |
| P12 | 公式ARC環境接続 | current request外 |
| P13 | Kaggle提出経路 | current request外 |
| P14 | 実提出・公式結果最適化 | current request外 |

## 現在のphase gate

P10では次だけを行う。

- 保持済みOFFLINE sampleの全game / 全level攻略
- P3 provenanceに拘束した全705 analysis sourceと183行の開発分析記憶
- mechanics / failure / blocker / capability coverage単位の横断開発
- task-aware Development Memoryからidentity-free Runtime Pへのlate subtraction
- game単位checkpoint、exact-condition resume、oracle互換集約
- `LOCAL_PROBE -> CLUSTER_STABLE -> COMPOSABLE`のHDS段階判定
- identity-free P0候補、M0候補、ARC3用HDS Frameの形成
- P-A / P-B / hybridの同一条件比較
- failureのM保持と明示的compilerによる次版P形成
- error、GAME_OVER、timeout、無限loop、max-action停止の解消
- 全trace保存と同一release条件での再現確認

現行境界はactive P `v27 / v27 / v26`、HDS採用済み`35 / 183`である。
C2の事後visible-effect observerだけを`CLUSTER_STABLE`、C3の非循環predictorを
`LOCAL_PROBE / HOLD`とする。C10は一段可視因果文脈で
`CLUSTER_STABLE`、C2+C10は`COMPOSABLE`へ到達したが、Runtime P候補の
target completion deltaが0だったためHDSは`REJECT`した。

C7 target-contact harnessは凍結済み288 probeを負の証拠に限定して移植し、
`LOCAL_PROBE / CLOSED_NEGATIVE`とした。KA59 remaining-boundaryへ適用した
C5 bounded-old-action-replay候補も、8回発火してtarget delta 0だったため
`LOCAL_PROBE / CLOSED_NEGATIVE_AXIS`である。active P、score、35/183境界は
変更しない。次の未埋込high-support work blockは
`WB-C12_layout_mode_commit_discriminator`。現行標準オラクルは
`35 / 183`、RHAE `18.821945363%`で、P11開始はHOLDである。

P10ではrelease state固定、公式接続、Kaggle作業を実行・完了扱いしない。

## 監査正本

- [`AGI_MINIMUM_THREE_SPEC.md`](../architecture/AGI_MINIMUM_THREE_SPEC.md)
- [`AGI_OBLIGATION_GRAPH.json`](../architecture/AGI_OBLIGATION_GRAPH.json)
- [`AGI_TRACEABILITY_MATRIX.md`](../architecture/AGI_TRACEABILITY_MATRIX.md)
- [`AGI_CLAIM_REGISTRY.md`](../architecture/AGI_CLAIM_REGISTRY.md)
- [`AGI_TEST_MATRIX.md`](../architecture/AGI_TEST_MATRIX.md)
- [`AGI_CURRENT_IMPLEMENTATION_AUDIT.md`](../architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md)

後続phaseの存在を理由に、現在phaseを飛ばしてはならない。
