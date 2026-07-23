# ARC-3 AGI Agent ロードマップ索引

## 正本

現行ロードマップの全文正本は次である。

- [`AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`](AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md)
- source attachment SHA-256: `742d8237c2472fe63680b0006053b7de71e6fbb0cfc98bc6f1200bae4c77000b`
- repository LF-normalized SHA-256: `bd4e7545fcb6a6c25483ed86bfbedfa44f1ee731af687ed87806e2c6d98ad09b`

本索引はphase状態だけを保持し、正本本文を重複しない。

## 現在状態

| Phase | 名称 | 状態 |
|---|---|---|
| P0 | Clean Restart Foundation | 完了 |
| P1 | Execution Mechanism Foundation | 完了・再分類 |
| P2 | AGI最小三構成仕様・根本監査 | 完了 |
| P3 | ARC3実証素材コンパイラ | 完了 |
| P4 | 計算主体Cの単独実装 | 現在 |
| P5 | HDS判断主体Jの単独実装 | 未開始 |
| P6 | 記憶主体Mの単独実装 | 未開始 |
| P7 | 二主体接続監査 | 未開始 |
| P8 | 三主体Trinity循環 | 未開始 |
| P9 | 全8部分集合監査 | 未開始 |
| P10 | ARC3全sample完全攻略 | 未開始 |
| P11 | 完成状態固定 | 未開始 |
| P12 | 公式ARC環境接続 | current request外 |
| P13 | Kaggle提出経路 | current request外 |
| P14 | 実提出・公式結果最適化 | current request外 |

## 現在のphase gate

P4では次だけを行う。

- P-A記号・規則graph型instruction body
- P-B実学習parameter型instruction body
- P-A/P-B共通interface、schema、version、digest、provenance
- 同一Layer-0によるP-A/P-B交換実行
- C単独のhypothesis/counter-hypothesis/prediction/candidate proposal
- L0六責任とPの除去監査

P4ではJの最終判断、Mの確定mutation、external emit、sample攻略、公式接続、
Kaggle作業を実行・完了扱いしない。P3 provenance manifestをruntime入力へ
渡してはならない。

## 監査正本

- [`AGI_MINIMUM_THREE_SPEC.md`](../architecture/AGI_MINIMUM_THREE_SPEC.md)
- [`AGI_OBLIGATION_GRAPH.json`](../architecture/AGI_OBLIGATION_GRAPH.json)
- [`AGI_TRACEABILITY_MATRIX.md`](../architecture/AGI_TRACEABILITY_MATRIX.md)
- [`AGI_CLAIM_REGISTRY.md`](../architecture/AGI_CLAIM_REGISTRY.md)
- [`AGI_TEST_MATRIX.md`](../architecture/AGI_TEST_MATRIX.md)
- [`AGI_CURRENT_IMPLEMENTATION_AUDIT.md`](../architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md)

後続phaseの存在を理由に、現在phaseを飛ばしてはならない。
