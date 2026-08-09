# ARC3開発実行契約 rev6

## Authority

1. Ownerの現在の明示指示
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev6.md`
5. `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev6.md`
6. `control/CURRENT_SELECTOR.json`
7. `control/rev6/CURRENT_TASK.json`
8. Current Taskが指定する独立Point指示書

rev5.1のM2〜M4閉包、release claim、関連artifactは履歴・失敗証拠であり、current completion evidenceではない。

## 実行規則

- `control/CURRENT_SELECTOR.json`のactive instructionだけを実行する。
- 一回の変更で複数Pointを完了しない。
- `auto_advance_allowed = false`。
- PointのHard Exit未達なら`REWORK_REQUIRED`。
- artifact存在、digest一致、test PASS、mock結果だけで能力Pointを完了しない。
- Capability Pointは公式サンプル環境の結果差分を要求する。
- 新しい空shell、parallel runner、J bypass、identity router、fixed replayを禁止する。

## Current Point

`R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`

実行指示:

`docs/instructions/arc3_rev6/R0/R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE.md`

このPointでは製品能力を変更しない。rev5.1の虚偽閉包を失効し、Current Product Statusを`NOT_ESTABLISHED`へ戻す。
