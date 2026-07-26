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
| P10 | ARC3全sample完全攻略 | 完了 |
| P11 | 完成状態固定 | 完了 |
| P12 | 公式ARC環境接続 | current request外 |
| P13 | Kaggle提出経路 | current request外 |
| P14 | 実提出・公式結果最適化 | current request外 |

## 現在のphase gate

P10は完全閉包先行・水平減算の順で閉じた。

- S0〜S5: 全段`PASS`
- S5 Runtime Student: 25/25 game、183/183 level、10,733 action、error 0
- S5入力: rendered observation、available action、bounded history、受動M
- local oracle: completion 100%、RHAE 99.619936696%
- S5 full rerun: 二回byte-identical
- S6: 25 game・183 levelを覆う2,048 record、七摂動14,336 measurement
- S6 full rerun: 二回byte-identical
- S6 claim: `MEASURED_NOT_PROVEN`

P11は次を固定して完了した。

- code commit/tree、dependency lock、Python versionの固定
- P0/J0/M0、dataset/compiler、seed、action budgetの固定
- P0〜P10 full regressionとtracked secret scan
- reproducible wheel buildとpackage内容・digest監査
- 全sample・authority・水平減算・S6証拠のrelease manifestへの束縛

- code commit: `dca7be72c82389334ed2c3d585ec3c90c2b53914`
- regression: 7/7 PASS、tracked secret finding 0
- wheel: 二回byte一致、SHA-256
  `79a5c0de76efb795bb6025e5fd434f6ce25acc472f76c0d4bb543fd2122699d6`
- release digest:
  `arc3_p11_release_state:70ffdd4395d0f50b312c002b226bd8c92ec1818597e913a72310dd1739177848`

P11はRuntime P、score、sample能力を変更していない。公式接続、
`OperationMode.COMPETITION`、Kaggle作業はP12以降でありcurrent request外。
現在実行中のphaseはない。

## 監査正本

- [`AGI_MINIMUM_THREE_SPEC.md`](../architecture/AGI_MINIMUM_THREE_SPEC.md)
- [`AGI_OBLIGATION_GRAPH.json`](../architecture/AGI_OBLIGATION_GRAPH.json)
- [`AGI_TRACEABILITY_MATRIX.md`](../architecture/AGI_TRACEABILITY_MATRIX.md)
- [`AGI_CLAIM_REGISTRY.md`](../architecture/AGI_CLAIM_REGISTRY.md)
- [`AGI_TEST_MATRIX.md`](../architecture/AGI_TEST_MATRIX.md)
- [`AGI_CURRENT_IMPLEMENTATION_AUDIT.md`](../architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md)

後続phaseの存在を理由に、現在phaseを飛ばしてはならない。
