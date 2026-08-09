# R0-P01 — rev5.1虚偽閉包の失効

- Point ID: `R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`
- Entry: `control/CURRENT_SELECTOR.json`が本Pointを指定
- Next: `R0-P02_REAL_STATE_REBASELINE`
- 能力変更: 禁止

## 目的

rev5.1のM2〜M4完了、RELEASE_FROZEN、PRODUCT_RELEASEDを製品完成証拠として失効し、実状態へ戻す。

## 入力

- `control/rev5_1/CURRENT_TASK.json`
- `analysis/product/rev5_1/m2_full_sample_product_closure.json`
- `analysis/product/rev5_1/m2_p01_clean_run_a.json`
- `analysis/product/rev5_1/full_mapping_closure.json`
- `analysis/product/rev5_1/m4_p06_submission_result.json`
- `analysis/product/rev6/REV5_1_INVALIDATION.json`

## 必須作業

1. endpoint `25/25 WIN・183/183`とofficial public score `0.06`を比較する。
2. Clean Run A参照ファイルが空であることを確認する。
3. Full Mapping Closure内のreplay関連記述とzero replay自己申告の矛盾を確認する。
4. rev5.1 artifactを削除せず`HISTORICAL_NONAUTHORITATIVE_FOR_COMPLETION`へ分類する。
5. product statusを`NOT_ESTABLISHED`へ戻す。
6. release parentとしてrev5.1 bundleを使用禁止にする。

## 出力

`analysis/product/rev6/R0_P01_INVALIDATION_CLOSURE.json`

必須field:

```text
invalidated_claims
observed_conflicts
preserved_historical_paths
current_product_status
release_parent_eligibility
next_point
```

## Hard Exit

```text
product_status = NOT_ESTABLISHED
rev5_1_completion_authority = REVOKED
rev5_1_release_parent_eligible = false
old_artifacts_preserved = true
product_code_change_count = 0
```

## 禁止

- 0.06をrelease成功と扱う
- 新しい能力実装
- 次Point以降の同時実行
- 旧artifact削除による証拠隠蔽

## Failure Routing

矛盾を確認できない場合は`SUSPEND_EVIDENCE_CONFLICT`。Hard Exit達成後のみR0-P02へ進む。
