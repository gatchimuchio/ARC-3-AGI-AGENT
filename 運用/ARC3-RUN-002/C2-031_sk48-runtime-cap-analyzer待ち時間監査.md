# C2-031 sk48 runtime-cap runのanalyzer待ち時間監査

## 目的

C2-029/v6のsk48は41件のhistory action、完了1 level、runtime約1,200秒でgave_upした。kernel logはaction 42で36.05秒のread timeout、tool call 0件を記録する。1回のtimeoutだけを失敗原因と決めず、既存証拠からbenchmark時間内のmodel request、turn-token yield、tool実行、analyzer startup/retryの寄与を分ける。

## 対象・禁止事項

- 対象は出力/ARC3-RUN-002-local/C2-029-kaggle-output/v6/ 内のbenchmark.json、transcripts/sk48-d8078629_p0.txt、requests.jsonl、serve.log、arc3-model-guided-c2-025.log、C2-029-comparison.json。
- Notebook、model、prompt、solver policy、HDS、提出候補、公式入力を編集しない。IDは証拠の対応づけにのみ用いる。
- Kaggle kernel rerun、Competition Rerun、公式提出・採点を行わない。証拠に存在しないrequest durationや原因を補間しない。
- 1つの時系列だけをまとめる。action42以外の代表runへ一般化しない。

## 受入条件

1. v6 benchmarkのelapsed約1,200.173秒とC2-030 auditを基準に、kernel/service/transcript/requestのclock originと対応付けを明示。
2. request/response count、turn-token-budget yield、tool call、read timeout、ConnectionError/retryの件数を可能な範囲で直接集計。
3. 36.05秒timeoutが占める時間と残る不明時間を区別し、runtime-cap原因を単一事象へ還元しない。
4. 結果を追記し、性能改善が未確認ならsolver変更を採用せず、次の一課題C2-032を作成する。
## 2026-10-23 21:13 UTC 実行結果

- v6 sk48 benchmark elapsedは1,200.173秒。transcriptは20:04:46の最初のstepから20:24:10のaction42 requestまで進み、そのrequestはread timeout 36.05秒、0 tool call preservedでyieldした。kernel logのrun終了は約20:24:46で、timeout 1件は約36秒を消費したが、runtime上限の約3%に過ぎない。これだけを1,200秒到達の原因とはしない。
- sk48 transcriptにturn_token_budget yield 7件、request_timeout 1件。request log全体には381 records（request 191 / response 190）、finish_reasonはtool_calls 187、length 3。requests.jsonlに時刻列・game ID列がなく、モデルrequestごとの所要時間やsk48内訳は再構成できない。未対応の1 requestはtimeout記録と整合するが、ID/time absentのため直接joinはできない。
- kernel logはゲーム開始時のwarmup RESET/analyzer ConnectionError、900秒startup retry設定を記録。serve.logはSGLang server argsを19:53:47に出力し、benchmark startは20:04:46。62 files/185.40GBのprecachingに876.95秒というkernel記録、Notebook cell 18の既存コメント「v2 became ready 8m32s after the first game timer started」は、モデル実推論readyがゲームtimer後まで遅れた履歴と整合する。cell 13はHTTP /health 200で進み、これは実推論readyを検証していない可能性がある。
- server.logにはwrapt欠落・rope設定警告もあるが、同じrun内で以後inference requestが応答しており、単独原因とは判定しない。
- SGLang公式Native API docsは/healthをserver health、/health_generateを1 token generationによるhealth checkと区別している（https://github.com/sgl-project/sglang/blob/main/docs_new/docs/basic_usage/native_api.mdx）。Kaggle wheelhouse内の厳密なversion契約は未確認なので、次のprivate testで実際の応答とready時刻を確かめる。
- 判定: timeout単体原因説は支持されない。一方、model load/precacheがfirst-game timerと重なった説明は強く支持されるが、benchmark・transcript・serviceのclockを完全joinするrequest timestampは欠ける。source変更や性能改善をこの診断だけから主張しない。
- 次工程C2-032は既存offline-only guard内でhealth_generateによる実推論readiness待ちを行い、timeout時計をserver起動から12分へ設定したprivate 1-game pilot。readinessが期限内に得られない場合はbenchmarkへ進まず失敗としてartifactを保持する。