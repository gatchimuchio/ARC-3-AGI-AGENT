# ARC3 文書索引 — CURRENT rev6

このindexは、現行開発と履歴資産を分離するための入口である。

## CURRENT

### 上位設計

- `architecture/AGI三主体統合設計正本_v0_2.md`
- `references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`

### ARC3 rev6 三点セット

- `strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev6.md`
- `roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev6.md`
- `instructions/arc3_rev6/INDEX.md`

### 機械可読CURRENT

- `../control/CURRENT_SELECTOR.json`
- `../control/rev6/CURRENT_TASK.json`
- `../control/rev6/ROADMAP_MANIFEST.json`

現在地点は`R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`、製品状態は`NOT_ESTABLISHED`、自動遷移は禁止。

## IMPLEMENTATION SUBSTRATE

実装本体は`../ARC-AGI-3-Agents/arc3_agi_agent/`に保持する。
このdirectoryの存在、過去のP番号、test、certificate、bundle、local scoreはcurrent completion claimを自動的に成立させない。

## HISTORICAL / REFERENCE ONLY

次は削除しないが、current selectorとして扱わない。

- rev2／rev3／rev4／rev5.1のstrategy・roadmap・instructions
- P0〜P22関連文書・control・artifact
- PH-D系の蒸留・authority・scope資料
- `../release/ARC3CompletionAgent-v1.0/`
- `../release/rev5_1/`
- `../kaggle_notebooks/`内のrev5.1 submission資産
- rev5.1以前のcompletion／release自己申告artifact

履歴分類の入口は`history/README.md`を参照する。

## Authority Rule

現行権威はroot `AGENTS.md`と`../control/CURRENT_SELECTOR.json`に従う。
古い文書に`current`、`PASS`、`RELEASED`等の記載が残っていても、それは当時の状態記録でありrev6を上書きしない。
