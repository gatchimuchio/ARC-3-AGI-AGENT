# C2-105 — 1回のPython呼び出し内の行動計画を8手で区切る診断

観測時刻: 2026-10-27T20:17:41Z
基準カーネル: tecchannn/arc3-model-guided-c2-025 version 29 / COMPLETE
候補Notebook SHA-256: 64C07C3C7988043533430683F9DF32C5E6776946E2FCD4578DDE0678DE5B1A1E

## 狙い

C2-104の「同じ合法Actionを連続選択した場合の制限」とは別の介入として、v28/v29の公開開始局ログでanalysis_stepあたり8手を超える行動列が観測されたため、Python snippetごとの実行Action上限を8手にする候補を作成した。8手後に最新状態をモデルへ返し、再観察・再計画を促す。ログのanalysis_stepはPython呼び出し境界と同一とは未確認である。

v28/v29の公開開始局ログをanalysis_stepごとに集計した結果:

| 基準 | analysis step数 | 8手超のstep | 8手超step内のaction数 | 8手目より後のaction数 |
|---|---:|---:|---:|---:|
| v28 | 95 | 12 | 145 | 49 |
| v29 | 106 | 15 | 180 | 60 |

これは再観察の診断根拠であり、analysis_stepをPython呼び出し境界と断定するものでも、再計画後の挙動やスコアを予測するものでもない。イベントファイルごとのSHA-256は証拠JSONに記録した。

## 候補と事前確認

- version 29 Notebook 64C07C3C7988043533430683F9DF32C5E6776946E2FCD4578DDE0678DE5B1A1Eを基に作成。Notebook cell 3だけ変更し、他のセルとkernel metadataは同一。
- python_tool_sandbox.pyのaction helperで、同一snippet内の実行済みAction数を数える。8手超の計画は残り枠までに切り詰め、実行結果と現在状態をモデルへ返した後にsnippetを停止する。
- Unified diff全hunkの行数整合を検証。変更hunkは旧行350/363、後続hunk開始位置も累積追加行数分移動した。
- cap境界の合成確認: 8手ちょうど、12手計画の先頭8手、snippet内で4手実行済みの場合の残り4手、上限到達後の拒否を確認。これは合成preflightであり、実ゲーム検証ではない。
- 候補Notebookはローカル 出力/ARC3-RUN-003-local/C2-105-action-plan-cap8/submission.ipynb。再生成スクリプト: [C2-105-build-action-plan-cap8.py](../../検証/ARC3-RUN-003/C2-105-build-action-plan-cap8.py)。

## 結果と運用状態

候補のprivate実行とスコアは NOT_MEASURED。Kaggle version 30へのpushは行っていない。最後に確認できた別候補C2-089のprivate push rejectionは2026-10-27T16:38:26ZのMaximum weekly GPU quota of 30.00 hours reached.で、reset時刻は提供されていない。新しい容量回復証拠がないため再試行していない。

公式履歴を2026-10-27T20:17:41Zに再読したところ、submission 57688735はCOMPLETE, public 28.07, private scoreなし。説明欄上は既存のlegacy visual C2-046 v13 fallbackであり、C2-105の得点ではない。比較元57577905のpublic 23.86からの差は+4.21。直近のquota証拠（2026-10-27T19:18:07Z）では当日1件使用、残り0、累計提出数8。2026-10-27T20:17:41Zの履歴にも新規提出はなく、この作業によるquota使用は0。

## 判断

C2-105は PREPARED_LOCAL_ONLY。スコア改善は未確認のため採用・昇格しない。GPU容量が回復した証拠を確認後、version 30としてprivate実行し、同一公開開始環境でv29およびC2-046 v13と比較する。公式の28.07はC2-046 v13 fallbackの結果として分離して記録する。

## 三点セット・保護対象

この作業開始時に現行v6共通3点セットとARC3 3点セットを再読し、hashを確認した。ファイルhashは証拠JSONとwork-ledgerに記録した。AGENTS.mdおよび制御/現在状態.jsonのhashも照合済みで、変更なし。

## 証拠

- Candidate build: 運用/証拠/ARC26-UNIFIED/ARC3-C2-105-action-plan-cap8-prepared-20261027T201256Z.json
- Review/trace/official snapshot: 運用/証拠/ARC26-UNIFIED/ARC3-C2-105-action-plan-cap8-review-20261027T201741Z.json
- Official raw history: 運用\証拠\ARC26-UNIFIED\ARC3-C2-105-official-history-raw-20261027T201741Z.json
- Latest official score and quota source: 運用\証拠\ARC26-UNIFIED\ARC3-C2-102-official-limits-raw-20261027T191807Z.txt
