# C1-021 指示書：model v5公開25環境のtoken計測と深度別使用量の監査

- 指示ID：`ARC3-RUN-003-C1-021`
- 適用正本：v3.0／2026-10-24。旧版は参照専用。
- 初期HEAD：`8667e9b9512e328084050007d3bdedb1ae5e245f`。既存のdirty worktreeを保持し、stage／commit／resetしない。
- 公式状態：2026-10-24 02:16 UTCのread-only照会で提出`57577905`は`PENDING`、score空欄。追加提出・Rerunなし。

## 問い

C1-019／C1-020の公開25環境・保存済みv5出力について、公開level深度に伴いtoken使用量が増えるか、1200秒runtime capとtoken量に記述的な差があるかを監査する。入力token・wallclock telemetryの意味と限界も確認し、遅延原因や性能効果を誤認しない。

## 許可範囲

- `benchmark.json`、公開25件の`*_p0_events.jsonl`、`summary.txt`をread-onlyで使用する。C1-019で検証済みの80 Action／1200秒cap分類を集計の照合に使う。
- benchmark runとevent streamは処理中だけ内部keyで対応付ける。出力・記録にgame ID、filename、個別run、Action列、board、座標、board hash、hidden/evaluator値を含めない。
- 各Actionは公開event直前の`level`へ帰属する。集計は深度別件数・generated-token合計・平均と終了上限群の合計に限定する。
- `uncached_input_tokens`がゼロの場合は「入力token増加なし」と解釈せず、記録上測定されなかったとする。`wallclock_seconds`をAction単位の推論遅延として扱わない。
- model／prompt／Notebook／runtime／policy／HDS／agentを変更せず、Kaggleへの提出・Rerunをしない。

## 検証・受入

1. benchmark、summary、event content set、解析器、tests、集計JSONのSHA256を記録する。
2. 公開eventとbenchmark historyの25/25 run・Action件数が一致すること、generated-token合計がsummary記載と一致することを確認する。
3. 80 Action到達群と80未満のruntime cap群を匿名aggregateで照合する。小標本の相関を原因・改善効果に読み替えない。
4. 解析器をtargeted tests、Ruff、format check、`py_compile`で検証し、集計JSONに個票・識別子・盤面等がないことを確認する。
5. 採否、限界、公式提出のread-only再開点を追記型運転記録と台帳に保存する。

## 終了条件

観測されたtoken telemetryの範囲を特定し、入力tokenまたは推論遅延の深度効果が証明できるかを区別する。未証明ならモデル変更を作らず、次の調査点を明示してC1-021を閉じる。
