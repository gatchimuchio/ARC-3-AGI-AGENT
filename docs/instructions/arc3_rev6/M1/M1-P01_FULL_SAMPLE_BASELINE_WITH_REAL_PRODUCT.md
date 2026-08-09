# M1-P01 — 実製品による全25 Game Baseline

- Point ID: `M1-P01_FULL_SAMPLE_BASELINE_WITH_REAL_PRODUCT`
- Depends on: M0-P07 PASS
- Next: `M1-P02_CAPABILITY_GAP_SELECTION`
- Product capability change: 原則禁止

## 目的

M0で成立した実製品を公式25 gameへ接続し、未完遂を実行failureとして観測する。

## 入力

- one ACTIVE_DEV ProductBundle
- M0 basis regression results
- official sample environments
- existing official product path

## 必須実行条件

```text
fresh process
fresh CognitiveSession
one ProductBundle
one product runtime path
all 25 official games attempted
no teacher playback
no source-state injection
```

## 必須作業

1. 全25 gameを実製品で実行する。
2. game／level／action／stop reason／failureを記録する。
3. failureを構造原因へ分類する。
4. 表面game名ではなくCapability Gapへclusterする。
5. 各clusterにaffected game／level数、blocking severity、再利用性を付ける。

## Failure Class

```text
OBSERVATION_LOSS
REPRESENTATION_ERROR
ENTITY_ROLE_ERROR
RELATION_ERROR
GOAL_INDUCTION_ERROR
MECHANISM_INDUCTION_ERROR
PRECONDITION_ERROR
ACTION_BINDING_ERROR
EFFECT_PREDICTION_ERROR
DELAY_ATTRIBUTION_ERROR
PLAN_ERROR
PROBE_ERROR
JUDGEMENT_ERROR
MEMORY_RETRIEVAL_ERROR
MEMORY_UPDATE_ERROR
ROLLBACK_ERROR
LEVEL_TRANSFER_ERROR
GAME_TRANSFER_ERROR
RESOURCE_ERROR
```

## 出力

`analysis/product/rev6/m1/full_sample_real_product_baseline.json`

## Hard Exit

```text
official_games_attempted = 25
mock_game_count = 0
teacher_playback_count = 0
failure_clusters_nonempty_or_25_of_25_WIN = true
real_game_and_level_counts_recorded = true
highest_leverage_gap_identified = true
```

## 禁止

- 過去のrev5.1 25/25自己申告を流用
- empty run artifact
- current failureをpackage／runnerの外装で隠す
- 複数gapの同時実装

## Failure Routing

実行経路そのものが壊れる場合のみ、同Point内で最小修正し、25 game baselineを取り直す。
