# M3-P01 — C／J／M／P Ablation

- Point ID: `M3-P01_CJMP_ABLATION`
- Depends on: M2-P05 PASS
- Next: `M3-P02_MEMORY_CAUSALITY`

## 目的

full-sample結果が三主体AGI構造に依存していることを削除試験で確認する。

## 必須試験

```text
C ablation: new representation／hypothesis／plan generation loss
J ablation: external action／ACTIVE M commit denied
M ablation: learning delta loss and failed behavior repetition
P ablation: ARC3 capability loss
```

## 必須作業

1. 同一代表Case／初期状態を使う。
2. 一主体ずつ除去する。
3. 機能等価物が他componentへ残っていないか追跡する。
4. expected lossとobserved lossを比較する。
5. responsibility leakがあれば修正し、M2 full runを回帰する。

## Hard Exit

```text
C_ablation_expected_loss = observed
J_ablation_blocks_external_action = true
M_ablation_removes_learning_delta = true
P_ablation_removes_ARC3_capability = true
functional_equivalent_leak_count = 0
M2_regression_after_repairs = PASS
```

## 禁止

- test doubleだけのablation
- feature flagが実際にcomponentを残す状態
- J除去時のfallback action

## Failure Routing

責任混線があれば該当componentを修正し、本Pointを再実行する。
