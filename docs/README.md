# 文書索引

文書は目的別に分離しています。

- [`architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md): `L0 / P / J / M`を含む現行システム構造
- [`architecture/P1_SAMPLE_EXECUTION_KERNEL.md`](architecture/P1_SAMPLE_EXECUTION_KERNEL.md): P1実行機構・OFFLINE sample接続の完了証拠
- [`architecture/AGI_MINIMUM_THREE_SPEC.md`](architecture/AGI_MINIMUM_THREE_SPEC.md): G1〜G5とC/J/M最小三構成の機能仕様
- [`architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md`](architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md): P2根本監査と未実装gap
- [`architecture/AGI_OBLIGATION_GRAPH.json`](architecture/AGI_OBLIGATION_GRAPH.json): 義務・主体・全8 subsetの機械可読graph
- [`architecture/P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md`](architecture/P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md): P3 compiler、dataset、provenance、holdoutの完了証拠
- [`architecture/P4_COMPUTE_SUBJECT_IMPLEMENTATION.md`](architecture/P4_COMPUTE_SUBJECT_IMPLEMENTATION.md): P4のP-A/P-B・計算主体C実装仕様と完了証拠
- [`architecture/P5_JUDGMENT_SUBJECT_IMPLEMENTATION.md`](architecture/P5_JUDGMENT_SUBJECT_IMPLEMENTATION.md): P5のtyped HDS Frame・standalone J実装と完了証拠
- [`architecture/P6_MEMORY_SUBJECT_IMPLEMENTATION.md`](architecture/P6_MEMORY_SUBJECT_IMPLEMENTATION.md): P6のversioned M・全storage operation・authority境界の完了証拠
- [`architecture/P7_PAIRWISE_SUBJECT_AUDIT.md`](architecture/P7_PAIRWISE_SUBJECT_AUDIT.md): P7の三pair実行・固有不足witness・非代行監査
- [`architecture/P8_TRINITY_TWO_CYCLE_CAUSALITY.md`](architecture/P8_TRINITY_TWO_CYCLE_CAUSALITY.md): P8のfull二周期循環・M因果・P/J/M分離証拠
- [`architecture/P9_MINIMUM_THREE_CERTIFICATE.md`](architecture/P9_MINIMUM_THREE_CERTIFICATE.md): P9の全8部分集合・除去証人・最小三構成証明
- [`architecture/P10_COMPLETE_SAMPLE_SOLVER.md`](architecture/P10_COMPLETE_SAMPLE_SOLVER.md): P10のOFFLINE solver、現行実測境界、失敗証拠
- [`architecture/P11_RELEASE_STATE.md`](architecture/P11_RELEASE_STATE.md): P11のP0/J0/M0、再現回帰、package、release manifest固定
- [`architecture/AGI_CLAIM_REGISTRY.md`](architecture/AGI_CLAIM_REGISTRY.md): claimごとのSUPPORTED/PARTIAL/REJECTED境界
- [`roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`](roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md): P0〜P14の全文正本
- [`roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`](roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md): P10の全183解析復元、能力cluster開発、late identity subtraction補正
- [`roadmap/ROADMAP.md`](roadmap/ROADMAP.md): 現行phase状態の索引
- [`migration/`](migration/): 旧資産の採用・隔離・拒否・再配置記録
- [`references/`](references/): 上位設計資料、外部仕様の引用、source map

権威順序は、現在のユーザー指示、root `AGENTS.md`、
P10作業では`roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`、
`roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`、
`architecture/AGI_MINIMUM_THREE_SPEC.md`、
`architecture/SYSTEM_ARCHITECTURE.md`、`roadmap/ROADMAP.md` の順です。
`references/`内の資料や旧資産は、現在フェーズや実行許可を上書きしません。
