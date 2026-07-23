# ARC-AGI-3 Agents — P1 OFFLINE実行パッケージ

このディレクトリはARC-AGI-3公式agent基盤に、本リポジトリの
P1 Layer-0 execution mechanismを統合した実行パッケージです。公式基盤の原READMEは
[`UPSTREAM_README.md`](UPSTREAM_README.md) に参照用として保存しています。

## 現在の実行入口

Python 3.12とロック済み依存関係を使用します。

```bash
uv sync --locked
uv run python sample_main.py --all-samples --max-actions 1
```

editable / wheel install後は次のentry pointも同じ入口です。

```bash
arc3-p1-samples --all-samples --max-actions 1
```

この入口は保持済み公式sampleを `OperationMode.OFFLINE` だけで各1 action実行し、
HDS承認、外部放出、再観測、context / passive memory更新、次判断までを検査します。
独立した命令形保持体`P`は未接続であり、P2のinstruction-body形成やP3の攻略実績には
加算しません。

## 検証

```bash
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests
python -m mypy arc3_agi_agent
ruff check \
  arc3_agi_agent \
  agents/__init__.py \
  agents/recorder.py \
  tests/conftest.py \
  tests/unit
python sample_main.py --all-samples --max-actions 1
```

このP1回帰入口では公式API、`OperationMode.COMPETITION`、Kaggle経路を使用しません。現在の
authority、禁止事項、main-only Git運用はリポジトリrootの `AGENTS.md` を正本と
します。
