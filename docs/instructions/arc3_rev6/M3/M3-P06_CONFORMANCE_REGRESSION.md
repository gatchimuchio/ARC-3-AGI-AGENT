# M3-P06 — Conformance Full Regression

- Point ID: `M3-P06_CONFORMANCE_REGRESSION`
- Depends on: M3-P01〜P05 PASS
- Next: `M4-P01_RELEASE_BUNDLE_COMPILATION`

## 目的

AGI適合修正後も同一ACTIVE_DEV bundleが公式全数完遂を維持することを確認する。

## 必須作業

1. M3-P01〜P05の結果を一覧化する。
2. fresh process／session／Mで25 gameを連続実行する。
3. same ACTIVE_DEV bundleを使用する。
4. C／J／M／P責任、memory causality、identity boundaryをtraceで再確認する。

## Hard Exit

```text
all_M3_points_PASS = true
clean_game_WIN_count = 25
clean_level_complete_count = 183
product_crash_count = 0
manual_intervention_count = 0
fixed_replay_count = 0
identity_router_count = 0
same_ACTIVE_DEV_bundle = true
```

## Claim Boundary

許可: `AGI_CONFORMANT_ACTIVE_DEV_FULL_SAMPLE_CLOSURE`

禁止: `PRODUCT_RELEASED`。releaseはM4完了後のみ。

## Failure Routing

全数回帰failureは責任に応じてM1／M2／M3へ戻す。M4へ進まない。
