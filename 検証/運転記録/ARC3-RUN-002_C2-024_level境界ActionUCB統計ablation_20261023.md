# ARC3-RUN-002 C2-024 level境界Action UCB統計初期化ablation

- 実施日: 2026-10-23 JST
- 対象指示: [C2-024指示書](../../運用/ARC3-RUN-002/C2-024_level境界でのActionUCB統計初期化ablation.md)
- 判定: **Action番号別UCB統計だけをlevel進行後に初期化しても、dev 15/15環境で応答列・指標の差はなかった。不採用、holdout未実施。runtime/candidate v4は維持。**

## 方法と実装

C4-001の全方針統計resetおよびC4-002/003のAction 6色統計resetとは分け、Action番号別の回数・報酬合計・総作用数だけを初期化し、乱数状態・色統計・既観測盤面・座標試行を保持する評価専用flagを追加した。評価器は作用後の公開完了level差分を記録してから統計を消す。開始公開盤面・state・合法Action集合の一致は実行中に対で照合した。

split seed 20261022のdev 5環境×environment seed 7/31/73、各最大80 Action、GAME_OVER後SDK RESETでbaseline/currentを比較した。seed 7は評価自体をメモリ内で完了したが、Cドライブ空き容量が0 byteとなりraw JSONを保存できなかった。seed 31/73のJSONは保存済み。匿名のseed別集計は[C2-024 summary](../../出力/ARC3-RUN-002-local/C2-024-action-ucb-level-reset-dev-summary.json)に記録した。

## previous / current / delta

| seed | Actions | completed levels | no-op | GAME_OVER / RESET | WIN / HOLD / illegal / duplicate | 同一開始 / 応答列一致 |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 400 / 400 | 1 / 1 | 9 / 9 | 6/6 / 6/6 | 0 / 0 / 0 / 0 | 5/5 / 5/5 |
| 31 | 400 / 400 | 1 / 1 | 9 / 9 | 6/6 / 6/6 | 0 / 0 / 0 / 0 | 5/5 / 5/5 |
| 73 | 400 / 400 | 1 / 1 | 17 / 17 | 6/6 / 6/6 | 0 / 0 / 0 / 0 | 5/5 / 5/5 |
| 合計 | 1,200 / 1,200 | 3 / 3 | 35 / 35 | 18/18 / 18/18 | 0 / 0 / 0 / 0 | 15/15 / 15/15 |

baselineとAction統計reset variantの公開Action応答列は全15環境対で完全一致した。進行後に統計resetが実行されても、その後の公開応答に差を作らなかったため、no-op総数減少という事前条件を満たさない。未使用holdoutへ進まず、不採用とする。

## 検証・採否

- targeted tests: 6 passed。Ruff check/format、compileall、CLI help、git diff --check pass。git diff --checkは既存CRLF/LF警告のみ。
- 匿名seed別summary SHA-256 `7F33DA4FBC852042CF83AF8597815040B95232F4B9DCDDF7AFE146E4206ADF86`。
- 評価器SHA-256 BA8F89BF09077622F5C67E0BA310B5C2AC68D240412178A371B7E2A3F6C22088、targeted test SHA-256 D0C43530FF95047E1BB49DE430A74A71287C15A2502949693F174FFCE0E3DA9E。
- seed 31 artifact SHA-256 FEB33454FF57BCAFF4019B4788CEADCA36E15722FC302EF59DD72D31C6D26530、seed 73 artifact SHA-256 E9DAE49FC927F1A353F99FF6D7B5A22E38D4EC4CF580D0CFDCC014E03B095D2D。seed 7はraw JSONなし。summaryには個別game ID、盤面、trajectoryを含めない。
- C2-024は評価器/testだけ。candidate v4、提出runtime、HDS、Notebook/kernel、公式submission 57541830（public 0.25）は不変更。このローカル比較は公式性能の差を示さない。

次単位はC2の反復係数調整を避け、C0の原因台帳とC1/C3の既存HDS・観測結果を再照合して、次の異なる故障候補を選定する。
