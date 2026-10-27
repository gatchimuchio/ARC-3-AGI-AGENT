# C6-003 評価器seed制御とCLIヘルプ修復

## 目的

C6-002はrun seedを`LocalEnvironmentWrapper`、探索policy、random baseline RNGへ同時に渡したため、環境差とpolicy RNG差を分離できなかった。また、評価器の`--help`はliteral `%`を含むhelp文字列で`ValueError: unsupported format character`となる。ローカル評価器のseed制御を明確化し、helpを正常化する。

## 変更範囲

- 対象は`検証/ARC3探索Actionローカル評価.py`と関連testのみ。提出agent、`接続/観測駆動探索Action.py`、HDS、Notebook/kernel、保護対象は変更しない。
- `--seed`は従来どおりLocalEnvironmentWrapperおよびrandom baselineのseedとして維持する。
- 新しいoptional `--policy-seed`を追加し、exploration policyだけに渡す。未指定時は既存互換のため`--seed`を使う。
- `--help`内のpercent表記をargparseで安全な表記に直し、help commandがexit 0になることを確認する。

## 検証

1. `python -X utf8 検証/ARC3探索Actionローカル評価.py --help`がexit 0となり、`--seed`、`--policy-seed`、既存主要flagが出ること。
2. policy-seed未指定の既存seed 31 runがC6-002同条件のseed31またはC6-001既存seed31と集計一致すること。
3. 固定environment seed 31、固定split seed `20261022`、公開holdout20環境、80 Action、GAME_OVER後RESETのまま、policy seed 7/11/17/29/31/43/59/73/83/101を比較する。開始状態が全条件で20/20一致すること。
4. levels、WIN、Actions、no-op、GAME_OVER/RESET、HOLD、illegal、duplicateをseed別に匿名集計する。baselineは同じenvironment seed31で固定し、local public結果をKaggle hidden scoreへ外挿しない。

## 採否

この単位は評価器の変更のみでruntime policyを採否しない。policy seed間でlevels/WINが動く場合はruntime stochasticityの影響が実測されたとして、必要なら次の指示書で決定的seedの候補を公開初期観測だけから生成する案を評価する。ほぼ安定ならseed制御をperformance fixとしてruntimeへ入れず、別のAction因果課題を選ぶ。

出力は`出力/ARC3-RUN-002-local/C6-003-policy-seed-<seed>.json`と匿名summary `C6-003-policy-seed-summary.json`。採否記録は`検証/運転記録/ARC3-RUN-002_C6-003_評価器seed制御とCLIヘルプ修復_20261023.md`へ保存する。
