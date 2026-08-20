# ARC-3 AGI Agent

ARC Prize / ARC-AGI-3を対象に、同一のAGI責任構造で自律完遂する実行主体を開発・検証するrepositoryです。

このREADMEはrepositoryの入口だけを示します。**現在Point、product status、scoreはここに固定しません。**

## Current State

現在の作業状態の唯一の入口:

[`control/CURRENT_SELECTOR.json`](control/CURRENT_SELECTOR.json)

Selectorが現行の仕様、ロードマップ、Current Task、局所指示を選択します。

環境整合の確認:

```bash
python scripts/check_repository_environment.py
```

## Operating Contract

AI実装エージェント／コード監査者の恒久運用契約:

- [`AGENTS.md`](AGENTS.md)
- [`AUTHORITY_ORDER.md`](AUTHORITY_ORDER.md)
- [`docs/operations/REPOSITORY_OPERATING_MODEL.md`](docs/operations/REPOSITORY_OPERATING_MODEL.md)

戦略と実装環境を分離し、AGENTSやREADMEへCurrent Stateを複製しない方針です。

## Repository Map

```text
AGENTS.md                 repository-wide implementation contract
AUTHORITY_ORDER.md        authority / evidence / history boundary
control/                   current selector and strategy-specific state
docs/architecture/        upper architecture
docs/references/          HDS and reference specifications
docs/strategy/            strategy specifications
docs/roadmap/             implementation roadmaps
docs/instructions/        local execution instructions
docs/operations/          stable repository operating model
docs/history/             historical authority/document index
ARC-AGI-3-Agents/          product implementation and package toolchain
analysis/ evidence/        observations, reports, evaluation evidence
artifacts/ manifests/      generated/canonical supporting artifacts
release/                   preserved release assets
kaggle_notebooks/          preserved platform notebook assets
scripts/                   repository-level build/audit/validation tools
```

## Product Implementation

実装本体は現在、[`ARC-AGI-3-Agents/`](ARC-AGI-3-Agents/)にあります。
このsubtreeのローカル運用規則は[`ARC-AGI-3-Agents/AGENTS.md`](ARC-AGI-3-Agents/AGENTS.md)を参照します。

toolchainのversionは文章へ転記せず、subtreeの次のファイルを正本とします。

- `.python-version`
- `pyproject.toml`
- `uv.lock`
- `pytest.ini`

## Development Entry

1. repository operating contractを読む。
2. environment checkを通す。
3. `control/CURRENT_SELECTOR.json`からCurrent Taskを解決する。
4. 既存実装・tests・evidenceを確認する。
5. 現在Taskの目的に必要な最小因果差分だけを変更する。
6. relevant verificationを実行し、観測結果とclaimを分離して報告する。

## History

旧rev、旧phase、旧release、旧submissionは削除せず履歴証拠として保持します。
現行権威との境界は[`docs/history/README.md`](docs/history/README.md)を参照してください。
