# ARC-AGI-3 Agents — P1実行核 / P3証拠compiler / C・J・M単独主体

このディレクトリはARC-AGI-3公式agent基盤に、本リポジトリの
P1 Layer-0 execution mechanismを統合した実行パッケージです。公式基盤の原READMEは
[`UPSTREAM_README.md`](UPSTREAM_README.md) に参照用として保存しています。

P3では`arc3_agi_agent.evidence_compiler`を追加し、730件の解析・metadata sourceから
identity-freeなC/J/M fixtureを生成済みです。P4では共通`InstructionBody`契約、
P-A記号規則graph、P-B学習済みsigmoid matrix、standalone Cを実装しました。
P5ではtyped HDS Frameとstandalone Jを実装し、integrated HDSも同じ判断coreへ
接続しました。P6では全15 storage operation、version、snapshot、rollback、
active/archiveを持つstandalone Mを実装しました。P7では三pairの固有不足を
実行監査しました。P8ではfull二周期TrinityとP/J/M因果分離を実証しました。
現在phaseはP9です。

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
独立した命令形保持体P-Aが全cycleで照会されます。この1-action回帰はP4の
実行経路証拠ですが、P10の攻略実績には加算しません。

P3 compilerのinstalled entry point:

```bash
arc3-compile-evidence \
  --analysis-dir /path/to/analysis \
  --environment-dir ../environment_files \
  --output-dir ../datasets \
  --manifest-dir ../manifests \
  --source-revision "<revision>+working-tree-content-manifest"
```

生成済みdatasetの境界と再現証拠は
[`../docs/architecture/P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md`](../docs/architecture/P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md)
を参照してください。

P4 instruction-body compilerのinstalled entry point:

```bash
arc3-compile-instruction-bodies \
  --dataset-dir ../datasets \
  --dataset-manifest ../manifests/dataset_manifest.json \
  --output-dir arc3_agi_agent/bundles
```

P4 bundleとC単独証拠は
[`../docs/architecture/P4_COMPUTE_SUBJECT_IMPLEMENTATION.md`](../docs/architecture/P4_COMPUTE_SUBJECT_IMPLEMENTATION.md)
を参照してください。

J/Mの単独実装証拠は
[`../docs/architecture/P5_JUDGMENT_SUBJECT_IMPLEMENTATION.md`](../docs/architecture/P5_JUDGMENT_SUBJECT_IMPLEMENTATION.md)
と
[`../docs/architecture/P6_MEMORY_SUBJECT_IMPLEMENTATION.md`](../docs/architecture/P6_MEMORY_SUBJECT_IMPLEMENTATION.md)
を参照してください。

P7 pair監査証拠は
[`../docs/architecture/P7_PAIRWISE_SUBJECT_AUDIT.md`](../docs/architecture/P7_PAIRWISE_SUBJECT_AUDIT.md)
を参照してください。

P8二周期因果証拠は
[`../docs/architecture/P8_TRINITY_TWO_CYCLE_CAUSALITY.md`](../docs/architecture/P8_TRINITY_TWO_CYCLE_CAUSALITY.md)
を参照してください。

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
