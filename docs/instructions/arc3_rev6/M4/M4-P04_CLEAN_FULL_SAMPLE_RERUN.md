# M4-P04 — Clean Full-Sample Rerun

- Point ID: `M4-P04_CLEAN_FULL_SAMPLE_RERUN`
- Depends on: M4-P03 PASS
- Next: `M4-P05_KAGGLE_NORMAL_RUN`
- Product sample release gate: 本Point

## 目的

clean install済みの同一release artifactで公式sample 25 game／183 levelを再現完遂する。

## 実行契約

```text
fresh process
fresh session/M
release artifact only
one RELEASE_FROZEN ProductBundle
25 official sample games
no development tree
no teacher replay
```

## 必須作業

1. 全25 gameを連続実行する。
2. 各game rowとtrace refsを保存する。
3. level countをrun resultから集計する。
4. bundle／runtime identityがfreezeと一致することを確認する。
5. manual intervention／replay／identity findingを確認する。

## Hard Exit

```text
clean_release_game_WIN_count = 25
clean_release_level_complete_count = 183
failed_game_count = 0
product_crash_count = 0
manual_intervention_count = 0
fixed_replay_count = 0
identity_router_count = 0
same_release_artifact = true
run_evidence_nonempty = true
```

## Claim Boundary

Hard Exit後に許可:

`ARC3_OFFICIAL_SAMPLE_PRODUCT_COMPLETE`

まだ禁止:

`ARC3_COMPETITION_PRIVATE_COMPLETE`

## Failure Routing

failureはM1／M2／M3へ戻す。M4 artifactをその場で変更しない。
