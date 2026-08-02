# ARC-3 AGI Agent

ARC Prize 2026 / ARC-AGI-3向けに、**HDSで成功軌道をタスク分解し、汎用構造と命令形Pを抽出して、同一のC／J／Mエージェントで実行する**repositoryです。

## 現行正本

- [実装仕様書 rev4](docs/strategy/ARC3_HDS直接抽出_汎用構造命令形P_実装仕様書_rev4.md)
- [開発ロードマップ rev4](docs/roadmap/ARC3_HDS直接抽出_開発ロードマップ_rev4.md)
- [Codex開発契約](AGENTS.md)
- [Current Task](control/rev4/CURRENT_TASK.json)

rev3のHDS蒸留多段工程、P0〜P22、S0〜S6は履歴・再利用資産であり、現在の作業selectorではありません。

## 最上位目的

```text
成功軌道・回答・観測記録
→ HDS Task Decomposition
→ Generic Structure Library
→ Imperative PBundle
→ ARC3 Agent Integration
→ 25 game／183 level full execution
→ Official submission
```

## 現在の状態

```text
Strategy : ARC3_HDS_DIRECT_STRUCTURE_AND_IMPERATIVE_P_REV4
Phase    : P1_TASK_DECOMPOSITION
Runtime  : SUSPEND until PBundle integration
Official : NOT_STARTED
```

現在は、PH-D05で整備済みの25 game／183 levelのcanonical teacher trajectoryを主入力として、全成功stepを次へ分解します。

- 状態
- 対象／役割
- 関係
- 前提条件
- 操作
- 即時／遅延効果
- progress／terminal寄与
- hazard／failure

## 六工程

1. `P1_TASK_DECOMPOSITION`
2. `P2_GENERIC_STRUCTURE_EXTRACTION`
3. `P3_IMPERATIVE_P_COMPILATION`
4. `P4_AGENT_INTEGRATION`
5. `P5_FULL_EXECUTION_REPAIR_LOOP`
6. `P6_OFFICIAL_PACKAGING_AND_EVALUATION`

文書、schema、evidence、approvalを独立phaseとして増殖させません。

## 再利用する既存資産

- PH-D05 canonical teacher trajectories
- raw recording／before-after／progress／terminal
- typed IR／interpreter／operator registry
- C／J／M／Trinity実装
- P16〜P21 Runtime substrate候補
- Kaggle lifecycle／output contract資産

## 最終成果物

```text
TaskDecompositionCorpus
ARC3StructureLibrary
ARC3PBundle
GenericARC3Agent
FullExecutionReport
KaggleSubmissionArtifact
```

完成判定はartifact数やtest数ではなく、汎用構造とPが実際にagentで使用され、全数実行結果へ変換されたかで行います。
