# M1-P05 — Affected Game閉包

- Point ID: `M1-P05_AFFECTED_GAME_CLOSURE`
- Depends on: M1-P04 PASS
- Next: `M1-P06_PROMOTION_OR_ROLLBACK`
- Official sample execution: 必須

## 目的

実装した能力によってtarget Failure Signatureを減少または消失させ、affected game／levelを前進させる。

## 必須作業

1. affected CaseSetをactual official sample environmentで再実行する。
2. before／afterのfailure countを比較する。
3. game WIN／level complete deltaを記録する。
4. 新しいfailureへ移動した場合は別Signatureへ分類する。
5. basisおよび既完遂gameをregressionする。
6. target failureが閉じるまで最小修正を反復する。

## Hard Exit

最低一つ:

```text
target_failure_count_after < target_failure_count_before
game_WIN_delta > 0
level_complete_delta > 0
same_failed_hypothesis_repetition_removed = true
```

かつ:

```text
manual_intervention_count = 0
fixed_replay_count = 0
basis_regression_failures = 0
J_bypass_count = 0
```

## 禁止

- mock差分でPASS
- target Caseを教師行動列で完遂
- unrelated test数の増加を改善扱い
- failureをログから削除して減少扱い

## Failure Routing

- target failure不変 → M1-P03またはP04へ戻る
- 別failureへ移動 → 現Unitを閉じ、新SignatureでM1-P02へ
- regression発生 → P04へ戻りscope／applicability修正
