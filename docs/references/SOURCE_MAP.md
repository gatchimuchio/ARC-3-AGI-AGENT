# 参照仕様・引用マップ

本リポジトリでは、参照資料を「権威ラベル」として貼るのではなく、採用する責任境界・停止条件・検証方法を明示して引用します。

## 1. 旧ARC実装・証拠資産

基準commit:

- [`gatchimuchio/ARC-Layer-0-Functional-Compliance@0970dc6`](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/tree/0970dc6a56addf2f2ca494efbf80ef919e2e3a12)

主要参照:

- [ARC3_WORK_CONTROL.md](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/ARC3_WORK_CONTROL.md)
  - 最上位目的と代替目的の分離
  - runtime禁止入力
  - HDS command → compute → judgment → authorized write/emit → re-observation
- [ARC3_HDS_LAYER0_MAXIMUM_AGENT_AUTHORITY.md](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/ARC3_HDS_LAYER0_MAXIMUM_AGENT_AUTHORITY.md)
  - ARC-native六責任
  - removal witness
  - 旧runtimeが最大構成に未適合だった監査結果
- [trinity_protocol.py](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/agent/trinity_protocol.py)
  - 非対称権限とbounded lifecycleの直接移植元
- [arc3_ir/types.py](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/agent/arc3_ir/types.py)
  - typed IRの直接移植元
- [arc3_ir/schema.py](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/agent/arc3_ir/schema.py)
  - canonical serializationとruntime identity-free検査の直接移植元
- [hds_verifier/verifier.py](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/agent/hds_verifier/verifier.py)
  - rendered evidence verifierの直接移植元
- [full-task completion audit](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/analysis/arc3_full_task_analysis_completion_audit_latest.json)
  - 657分析JSON、233 stale score、未閉包義務の棚卸し根拠
- [local score oracle](https://github.com/gatchimuchio/ARC-Layer-0-Functional-Compliance/blob/0970dc6a56addf2f2ca494efbf80ef919e2e3a12/analysis/arc3_local_score_oracle_latest.json)
  - 旧generic-only結果の参照。新baselineではない

## 2. TCP / Closure Phase Ψ / 神の領域原理

基準commit:

- [`gatchimuchio/closure-phase-specs@8bc41d6`](https://github.com/gatchimuchio/closure-phase-specs/tree/8bc41d6a298938dd9763cd06dfe68afa6f1b896d)

採用箇所:

- [TCP v0.8](https://github.com/gatchimuchio/closure-phase-specs/blob/8bc41d6a298938dd9763cd06dfe68afa6f1b896d/02_TCP_v0_8_bilingual.md)
  - world-descriptionを `W := (X, R, M)` で閉じる
  - `M` はidentity、boundary、judgment、stoppingを固定するclosure function
  - 未閉包・未観測・境界隣接では `SUSPEND` を有効出力にする
- [Closure Phase Ψ v0.7](https://github.com/gatchimuchio/closure-phase-specs/blob/8bc41d6a298938dd9763cd06dfe68afa6f1b896d/01_Closure_Phase_Psi_v0_7_bilingual.md)
  - Ψを内部物質ではなく、固定条件下の反復観測で残るsignature residualの同値類として扱う
  - capability、knowledge、emotion、closure phaseを混同しない
- [repository README](https://github.com/gatchimuchio/closure-phase-specs/blob/8bc41d6a298938dd9763cd06dfe68afa6f1b896d/README.md)
  - 評価モードはbeliefではなくconformance
  - 公開仕様と封印されたHDS実装境界を分離する

ARC3への変換:

- candidateごとに `X/R/Mc` を保持
- 未観測mechanicを事実化しない
- forced actionより `SUSPEND` / bounded probeを優先
- closureの証拠を単発scoreではなく反復signatureで測る

## 3. LLM Layer-0機能責任

基準commit:

- [`gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification@7726901`](https://github.com/gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification/tree/7726901d1baf0c5bd10d35dae689542adf8b36de)

主要参照:

- [README.ja.md](https://github.com/gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification/blob/7726901d1baf0c5bd10d35dae689542adf8b36de/README.ja.md)

採用する方法:

- 最小責任境界を固定する
- 各責任の機能等価物を含めて除去監査する
- full setだけでなくproper subsetを検査する
- ラベル存在ではなく除去時の観測可能な喪失を証拠にする
- 実装方式と機能責任を分離する

採用しない主張:

- LLMの六役割がそのままARCエージェントの存在論的必要条件である、という転用

ARC3では、方法論を次のARC-native責任へ射影します。

```text
SYMBOL_SPACE
CONTEXT_STATE
TRANSFORM_OR_WORLD_MODEL
CANDIDATE_SURFACE
FITTING_OR_SUCCESS_CRITERION
EMISSION_INTERFACE
```

## 4. 引用規則

- 参照commitを固定する
- source-derived factと新repoでの設計判断を分ける
- 原文が主張しない性能・真理・AGI達成を追加しない
- private旧repoのコードは移植元pathとblob SHAをmanifestへ残す
- public仕様の用語は、そのscopeと非目的を併記する
