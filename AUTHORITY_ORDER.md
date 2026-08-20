# ARC3 Current Authority — rev6

このroot文書は、repositoryの**現行権威面だけ**を示す。
旧rev2／rev3／rev4／rev5.1、P0〜P22、PH-D系、過去のApprovalRecord・release・submission資産は履歴証拠であり、current selectorではない。

## Normative Authority

1. Ownerの現在の明示指示
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev6.md`
5. `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev6.md`

## Execution Control

1. Ownerの現在の明示指示
2. root `AGENTS.md`
3. `control/CURRENT_SELECTOR.json`
4. `control/rev6/CURRENT_TASK.json`
5. Current Taskが指定する独立Point指示書

`control/CURRENT_SELECTOR.json`に指定されない旧control state、phase state、roadmap、artifact-local next指示は、現行作業を選択できない。

## Current State

```text
strategy = ARC3_OFFICIAL_SAMPLE_GENERIC_COMPLETION_AGI_REV6
product_status = NOT_ESTABLISHED
active_point = R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE
auto_advance_allowed = false
```

R0-P01の閉包artifactが成立しても、selectorは自動更新しない。次Pointへの遷移は別のOwner判断として扱う。

## Historical Root Authority

rev3時点の旧`AUTHORITY_ORDER.md`は、内容を変更せず次へ退避する。

`docs/history/rev3_root/AUTHORITY_ORDER.md`

旧文書は当時の設計・判断・失敗を読むための証拠であり、rev6の意味や現在地点を変更しない。
