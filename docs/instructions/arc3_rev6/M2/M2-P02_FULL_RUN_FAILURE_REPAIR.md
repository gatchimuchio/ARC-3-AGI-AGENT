# M2-P02 — Full-Run Failure修正

- Point ID: `M2-P02_FULL_RUN_FAILURE_REPAIR`
- Depends on: M2-P01 failure set
- Next: `M2-P03_CLEAN_RERUN_UNTIL_PASS`
- Product capability change: 必須または明示的config修正

## 目的

個別gameでは発生せず、連続full runで発生したfailureをHDSで責任分解して閉じる。

## 対象例

```text
stale cross-game memory
negative transfer
resource accumulation
game-order dependency
session lifecycle leak
Applicability誤適用
state owner drift
rollback contamination
```

## 必須作業

1. failure発生前後のM、J、P、resourceを比較する。
2. baseline、transfer hypothesis、resource hypothesis、lifecycle hypothesisを競合させる。
3. 最小責任部品を選ぶ。
4. scope／retrieval／consolidation／resource／lifecycleの必要箇所だけ修正する。
5. failure再現Caseと既完遂gameを回帰する。

## Hard Exit

```text
target_full_run_failure_reproduced_before_fix = true
target_failure_not_reproduced_after_fix = true
local_regression_failures = 0
completed_game_regression_failures = 0
new_parallel_runtime_count = 0
```

## 禁止

- failureをrunnerでcatchして成功扱い
- Mを全消去して原因を隠す
- game IDによるmemory scope
- full run evidenceの書換え

## Failure Routing

修正後もfailureが残る場合は本Point内でHDS ModelSetを更新する。原因が一般Capability不足ならM1-P02へ戻る。
