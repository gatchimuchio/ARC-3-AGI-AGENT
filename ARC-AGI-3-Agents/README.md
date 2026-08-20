# ARC-AGI-3-Agents — Product Implementation Substrate

このdirectoryは`ARC3CompletionAgent`の実装資産とpackage toolchainを保持する。
**current strategy／Point／product status／completion authorityは保持しない。**

## Current Work Resolution

現在作業はrepository rootから解決する。

- `../AGENTS.md`: repository-wide operating contract
- `AGENTS.md`: このsubtreeのlocal implementation contract
- `../AUTHORITY_ORDER.md`: authority / evidence boundary
- `../control/CURRENT_SELECTOR.json`: current workの唯一の入口

このREADMEから現在Pointを推定しない。

## Implementation

主要package:

`arc3_agi_agent/`

既存のentrypoint、agents、tests、audit tools、bundles等は、新規実装を作る前に再利用可能性を確認する。
過去世代の名称を持つmoduleやscriptが存在していても、その名称だけでcurrent／historicalを判定しない。

## Toolchain

versionやdependencyは文章へ転記せず、次を正本とする。

- `.python-version`
- `pyproject.toml`
- `uv.lock`
- `pytest.ini`

環境構築:

```bash
uv sync --locked
```

代表的なlocal verification:

```bash
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests
python -m mypy arc3_agi_agent
ruff check arc3_agi_agent agents/__init__.py agents/recorder.py tests/conftest.py tests/unit
```

実際に必要なcheckはCurrent Taskと変更範囲に応じて選択する。
未実行checkをPASSと報告しない。

## Evidence Boundary

このsubtreeに実装、test、bundle、certificate、local score等が存在しても、それ自体でofficial capabilityやcompletionは成立しない。
claimはroot operating contractのEvidence Levelに従い、対応する実測結果へ接続する。

## External / Platform Boundary

release、Kaggle Notebook、competition mode、official access等は、このREADMEの記述だけではcurrent execution pathにならない。
Current TaskとOwner権限で明示的に選択された場合だけ使用する。

## Historical Documentation

過去にこのdirectoryがcurrent product runtimeを名乗っていたREADME原文は次へ保存している。

`../docs/history/rev4_runtime/ARC-AGI-3-Agents_README.md`

旧READMEは当時の実装状況を読むための証拠であり、現在地点を選択しない。
