# C1-022 指示書：保存済みv5のtoken counter差分出所監査

- 指示ID：`ARC3-RUN-003-C1-022`
- 適用正本：v3.0／2026-10-24。旧版は参照専用。
- 初期HEAD：`8667e9b9512e328084050007d3bdedb1ae5e245f`。既存dirty worktreeを保持し、stage／commit／resetしない。
- 公式状態：提出`57577905`の最新観測は2026-10-24 02:16 UTCで`PENDING`。照会間隔を守り、提出・Rerunを行わない。

## 問い

C1-021で確認したsummary/history generated-token合計`2,134,037`とsolver_note token合計`2,162,266`の差`28,229`が、計数範囲の違い・終了群・保存版sourceのどこから生じるかを調べる。差の意味が特定できなければ未解決として残す。

## 許可範囲

- 保存済みpublic v5のbenchmark/history、summary、25 event stream、C1-021集計をread-onlyで使う。必要ならKaggleから提出Notebook v5のsourceをread-only取得し、記録済みSHAと照合する。
- run keyは処理中だけjoinに使い、出力は全体および80 Action到達／1200秒cap群のaggregateのみ。個別run、ID、filename、prompt、board、Action列、hidden/evaluator情報を出力・保存しない。
- 提出Notebook・model・prompt・runtime・policy・HDS・agentを変更しない。Kaggle提出、Rerun、quota消費なし。

## 検証・受入

1. C1-021の入力SHAと25/25 event-history alignmentを維持して再照合する。
2. history generated-token合計とsolver_note token合計の差について、保存版sourceの計数scopeで説明できるか確認する。個別値を記録せず、符号件数・群別合計のみを使う。
3. 提出版v5 sourceを特定できない場合、現在のworking Notebookを提出版の代用にせず、出所未確認として止める。
4. 匿名出力を監査し、再現・照合結果と未解決点を追記型C1運転記録・台帳へ残す。

## 終了条件

counter差の範囲を根拠付きで説明するか、資料不足・scope不明として未解決と判定する。いずれの場合もtoken差を能力・性能差として解釈しない。
