# C2-023 指示書：Action 5/6のlevel進行報酬統計反映監査

- 指示ID: `ARC3-RUN-002-C2-023`
- 版: 1.0 / 2026-10-23（JST）
- 区分: 読み取り専用の実装・artifact整合監査

## 根拠と目的

C6-003の固定environment seed 31・公開holdout 20環境・10 policy seedで、観測されたlevel進行27件のうち24件がAction 6、3件がAction 5だった。Action 6は進行が多い一方でno-opも多く、全応答のAction別平均報酬ではAction 5の方が高い。level進行報酬が応答報酬・Action別UCB統計・Action 6の色別統計へ正しく反映されているかを確認し、データ上の行動差と実装上の欠落を区別する。

この監査はC6-003結果の再集計であり、holdoutによる方針tuningや性能改善の主張ではない。

## 入力と固定条件

- 現行方針: `接続/観測駆動探索Action.py`
- 固定評価artifact: `出力/ARC3-RUN-002-local/C6-003-policy-seed-<seed>.json`、seed `7/11/17/29/31/43/59/73/83/101`
- split seed `20261022`、environment seed `31`、各run公開holdout20環境、最大80 Action、GAME_OVER後RESET
- 集計単位: 公開応答。ID、盤面、軌跡、game別値は記録レポートに出さず、Action 5/6と全体の匿名aggregateのみ保存する。

## 手順と保持条件

1. `応答を記録する`が公開level差分から報酬を作る式、Action別回数・報酬合計への反映、Action 6色統計への反映、および`選ぶ`のUCB参照箇所をコード上で追跡する。
2. 10個の保存済みJSONを読み取り専用で集計する。Action 5/6ごとにAction回数、完了level増分、no-op、GAME_OVER、平均・総公開報酬を求める。
3. 各応答に記録されたlevel増分・報酬と、gameごとの`policy_action_stats`最終値を突き合わせ、全run集約値が一致するか検証する。
4. 色別統計がartifactへ出力されない場合はコード上の経路確認に留め、実測整合済みとは主張しない。

- source、evaluator、test、HDS、runtime policy、Notebook/kernel、提出物は変更しない。
- no-op、GAME_OVER、可視変化を成功または失敗へ一律に読み替えない。
- Action IDを問題ごとの答え分岐に使わない。集計したAction番号は説明用であり、runtime規則にしない。
- 固定policy seedの最良選択、holdout上の係数調整、ゲーム個別出力を行わない。

## 完了条件

- ソース上の報酬からAction UCBまでのデータ経路と、artifact記録の一致・不一致を説明する。
- Action 5/6のprevious/current比較表、入力summary SHA、方針SHA、採否を運転記録へ保存する。
- 欠陥が見つかった場合だけ、別の修正指示書を作成して最小修正へ進む。欠陥がなければ方針を変更せず、結果から次の優先課題を選ぶ。
