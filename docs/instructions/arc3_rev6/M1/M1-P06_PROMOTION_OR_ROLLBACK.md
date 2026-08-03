# M1-P06 — 能力Promotion／Rollback

- Point ID: `M1-P06_PROMOTION_OR_ROLLBACK`
- Depends on: M1-P05 Hard Exit
- Next: `M1-P07_ALL_GAME_MAPPING_CLOSURE`または`M1-P02_CAPABILITY_GAP_SELECTION`

## 目的

実行結果に基づき、能力をACTIVE_DEVへ昇格、PROBATION維持、降格、rollbackのいずれかへ確定する。

## 昇格条件

```text
independent_case_support >= 2
negative_or_boundary_case >= 1
target_behavior_delta_observed = true
affected_game_or_level_delta_observed = true
regression_failures = 0
identity_router_findings = 0
fixed_replay_findings = 0
```

## 必須作業

1. M1-P03〜P05の証拠を集約する。
2. 既存familyとの水平引き算を行う。
3. applicability scopeを更新する。
4. asset stateを決定する。
5. rollback時は旧bundleへ戻し、failureを再登録する。

## 出力

`analysis/product/rev6/m1/units/<unit_id>/promotion_decision.json`

## Hard Exit

```text
asset_state in [ACTIVE_DEV, PROBATION_DEV, REJECTED, ROLLED_BACK]
decision_bound_to_actual_execution = true
next_scope_defined = true
```

## 禁止

- support countの手入力だけで昇格
- Owner権限を装った自動release
- regression無視
- 一回成功のACTIVE_DEV化

## Next Routing

- 全25 game／183 level mapping未閉包 → M1-P02へ戻る
- 全て個別完遂・mapping完了 → M1-P07へ
