# ARC-AGI-3-Agents — ARC3 implementation substrate

このdirectoryは`ARC3CompletionAgent`の実装資産を保持する。**current strategy／phase／completion authorityではない。**

## Current Repository State

```text
strategy = ARC3_OFFICIAL_SAMPLE_GENERIC_COMPLETION_AGI_REV6
product_status = NOT_ESTABLISHED
active_point = R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE
```

現行権威はrepository rootの次だけを参照する。

- `../AGENTS.md`
- `../control/CURRENT_SELECTOR.json`
- `../control/rev6/CURRENT_TASK.json`
- active Point instruction

このdirectory内に残る`rev4`、`P1`〜`P22`、M3/M4/M5、certificate、bundle、local score等の記述・実装・testは、再利用可能な実装資産または履歴証拠であり、rev6 completion claimを自動成立させない。

## Implementation

主要package:

`arc3_agi_agent/`

保持されている責任構造:

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
```

rev6では、この既存substrateを捨てず、R0-P02で実能力・実score・実行経路を再基準化した後に採否する。

## Rebaseline Candidates

以下の入口は旧実装から保持されている。rev6で有効とみなす前にR0-P02以降で実測確認する。

```bash
uv sync --locked
uv run arc3-completion-product --mode offline --action-budget 4096
python -m pytest -q tests
python -m mypy arc3_agi_agent
ruff check arc3_agi_agent tests
```

Kaggle／competition mode／公式提出は、旧releaseや旧Notebookをそのままcurrent経路として再利用しない。

## Historical README

rev4時点でこのdirectoryがcurrent product runtimeを名乗っていたREADME原文は次へ保存する。

`../docs/history/rev4_runtime/ARC-AGI-3-Agents_README.md`

古いREADMEは当時の実装状況を読むための証拠であり、現在地点を選択しない。
