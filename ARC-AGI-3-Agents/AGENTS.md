# Product Implementation Local Contract

この`AGENTS.md`は`ARC-AGI-3-Agents/`subtreeに適用し、root `AGENTS.md`を具体化する。
rootのauthority・evidence・failure・history規則は継承し、緩和しない。

## 1. Scope

このsubtreeはproduct implementationとpackage toolchainの領域である。
Current strategy／Pointを選択する権限は持たない。現在作業はroot `control/CURRENT_SELECTOR.json`から解決する。

実装変更時は、既存の`arc3_agi_agent/`、entry point、tests、scriptsを確認し、同じ責任を持つparallel packageやrunnerを増やさない。

## 2. Toolchain Authority

versionやdependencyは文章へ固定せず、次を正本とする。

1. `.python-version`
2. `pyproject.toml`
3. `uv.lock`
4. `pytest.ini`
5. source-local configuration

lock済み環境では`uv sync --locked`を基準とする。
dependencyを変更した場合は`pyproject.toml`と`uv.lock`を整合させる。

## 3. Change Boundary

- product behaviorを変える場合、責任moduleと既存consumerを特定する。
- public entrypointを増やす前に既存entrypointで実現不能か確認する。
- test専用経路をproduction capabilityとして扱わない。
- compatibility layer、fallback、adapterを追加して本体failureを隠さない。
- identity-specific answer routingやfixed successful replayでgeneric capabilityを代行しない。
- root `control/`、strategy、roadmap、release stateをproduct code変更の副作用で更新しない。

## 4. Verification

変更に応じて最小のtargeted checkから開始し、影響範囲まで広げる。

代表的なfull local checks:

```bash
uv sync --locked
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests
python -m mypy arc3_agi_agent
ruff check arc3_agi_agent agents/__init__.py agents/recorder.py tests/conftest.py tests/unit
```

すべてを毎変更で機械的に実行する必要はない。Current Taskと変更範囲に必要なcheckを選び、未実行のものは未実行と報告する。

official／platform validationが必要な能力claimは、local testで代替しない。

## 5. Generated and Package Assets

wheel、cache、generated report、runtime outputをsource codeと混同しない。
release／Kaggle用pathは外部consumerを持つ可能性があるため、見た目のcleanupだけでrename／moveしない。

## 6. Completion

product implementationの完了報告では、最低限以下を示す。

- changed module／entrypoint
- behavior delta
- tests／runtime checkと実結果
- regression影響
- 未確認のofficial／platform境界
- root Selectorを変更したか否か
