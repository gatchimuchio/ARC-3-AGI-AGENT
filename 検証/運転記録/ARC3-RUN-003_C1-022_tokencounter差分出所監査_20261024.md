# ARC3-RUN-003 C1-022：保存済みv5 token counter差分の出所監査

## 対象・条件

C1-021で残ったhistory generated-tokenとsolver_note token合計差28,229の出所をread-onlyで調査した。Kaggle APIからのNotebook取得は403 Forbiddenだったが、保存済みNotebook `出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb` のSHA256がC1-020に記録された提出版v5 SHA256と完全一致したため、この保存sourceを照合に使用した。

Notebook metadataで接続されている公開source bundle `dfranzen/taaf-kaggle-source-bundle-copy`からrunner `solver.py`だけをread-only取得した。ファイルSHA256は`65ddfcdbe8c24fdc31246ff018b51469827b21c38995243a36a818adbed33370`で、Tufalabs公開sourceのcommit `7652836056c59e044f093e3c13ed7438c814169e`にある同ファイルと一致した。dataset listingの最終更新は2026-09-28で、v5提出以前の更新は観測されていない。

benchmark 25 runとpublic event streamは処理中のみ内部keyで照合。レポートとJSONはgroup/全体aggregateに限定し、個別run・識別子・action trace・boardを保存していない。

## 結果

| 上限群 | run | history token | solver_note token | 差 | solver_noteが多いrun | 同値run | 少ないrun | analysis event |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 80 Action到達 | 21 | 1,585,051 | 1,585,051 | 0 | 0 | 21 | 0 | 599 |
| 80未満・1200秒runtime cap | 4 | 548,986 | 577,215 | 28,229 | 3 | 1 | 0 | 163 |
| 全体 | 25 | 2,134,037 | 2,162,266 | 28,229 | 3 | 22 | 0 | 762 |

差は全て4件のruntime-cap群に限られる。C1-021と同様、個票値は表示・保存していない。

提出版v5 sourceでは`generated_tokens` propertyが`_session_generated_tokens`を返す。全usageの生成tokenをsession counterへ加算し、rolling summary responseも`_accumulate_usage_tokens(..., count_toward_turn=False)`でsession合計へ入れる一方、turn counterには加えない。

一致したrunner sourceは開始時の累積token値をbaselineとして保持し、各実行Actionでは`current_tokens - token_baseline`を`GameAPI.execute_action(generated_tokens=...)`へ渡してからbaselineを更新する。終了時の`finally`はanalyzerの最終累積token値を`run.solver_note = tokens=...`へ保存する。従って、全Action historyのgenerated-token合計と最終solver_noteとの差は、最後に履歴記録されたAction後に増えたsession tokenと一致する。データではこの差28,229はruntime-cap 4 runに限られ、そのうち3 runにpositive差、1 runに差なし。差のscopeは「未Action記録の終了後session生成token」と特定できた。

このtokenがrolling summary、最後の未実行判断、別の終端処理のどれから発生したかはaggregateだけでは観測できない。分析event 762件にもrequest種別の識別情報はなく、具体的な生成内容やcapを誘発した因果は主張しない。

## 採否・限界

**counter差のscopeは解決、生成request種別は未確定。** 21件の80 Action群ではhistoryとsolver_noteが一致し、runtime-cap 4件における28,229は最後のAction以後の累積生成tokenとして説明できた。summary total tokens `2,134,037`はhistory合計と一致するため修正しない。token差を能力・性能・推論時間として解釈せず、モデル・runtime・Notebookは変更しない。

## 検証・出所

- benchmark：`7237a2d2150820ee2aadc8ba986dcb67a12e495bd934bd686583b1cd32ebdcd2`
- summary：`38d0954973a4cbb1d7c94b94463b100fdb18d3f760849b411e248f072a0f21ac`
- C2-027 comparison：`4bd0bf8b3f966f098d0a8ddca98038f1abdd8a5836af02718d528fb2282a730b`
- 25 event content set：C1-021で検証済み `d8653cb231ed8e07d16c9b1f4ee82a20c664da98d896da3e266ec78f9e0fdeac`
- 保存提出版v5 Notebook：`5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc`（C1-020記録SHAと一致）
- Kaggle source bundle `solver.py`：`65ddfcdbe8c24fdc31246ff018b51469827b21c38995243a36a818adbed33370`（upstream commit `7652836056c59e044f093e3c13ed7438c814169e`の同ファイルと一致）
- runnerのcounter実装：[solver.py at pinned upstream commit](https://github.com/Tufalabs/duck-harness/blob/7652836056c59e044f093e3c13ed7438c814169e/ARC3-Inference/inference/framework/solver.py)。匿名aggregate：[C1-022 JSON](../../出力/ARC3-RUN-003-local/C1-022-token-counter-scope.json)。JSON SHA256 `4f3620cf8e2adeed76ecae96230adc3bc4cfb2135d14bf151e5128e929a52c68`。
- Kaggle read-only pullは403 Forbidden。ローカルのhash一致sourceを使い、Notebook再提出や編集はしていない。

## 再開点

C1-022は局所完了、counter範囲は未解決。C1-018公式提出`57577905`は02:16 UTC時点でPENDING、score空欄。次回は02:46〜03:16 UTCを目安に同一IDをread-only照会する。外部runnerのtoken writer sourceが別途取得可能になった時だけ差のscopeを再検証する。
