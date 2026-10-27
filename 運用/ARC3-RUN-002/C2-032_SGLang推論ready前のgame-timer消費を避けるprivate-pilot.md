# C2-032 SGLang推論ready前のgame timer消費を避けるprivate pilot

## 目的

C2-031でv6 sk48の1,200.173秒runtimeに対しrequest_timeoutは36.05秒1件だけだった。一方、Notebook cell13はHTTP /healthの200でserver readyとし、cell18の履歴コメントとv6のConnectionError/precaching記録は最初のgame timer中にmodel loadが続いた説明と整合する。実推論が可能になってからoffline benchmarkを開始し、first-game timerをstartupと分離できるか一度だけ検査する。

## 対象・変更範囲

- candidate: private kernel tecchannn/arc3-model-guided-c2-025 version 6、先頭環境sk48-d8078629、version 6の同一初期状態。
- backup: 現行submission.ipynbを出力/ARC3-RUN-002-local/C2-032-source/v6-submission.ipynbへ退避し、SHA256を記録する。
- cell13のreadiness probeを127.0.0.1:8001/health_generateへ変更する。health_generate成功（HTTP 200）でreadyとし、server process終了・12分deadlineではoffline pilotをbenchmark開始前に失敗させる。
- startup deadlineはNotebook開始時刻からではなく、server Popen直後のt0から12分とする。12分値は増やさない。
- cell18のoffline-only guardをARC3_DEV_GAME_LIMIT=1、max Actions=160、per-game runtime=1,200秒、逐次1 passへ設定。solver/model/prompt/timeout policyは変更しない。
- TRUE_SUBMISSION側のCompetition gateway・action/solver path、SGLang server arguments、HDS、公式candidate、AGENTS.md、制御/現在状態.json、正本pointerは変更しない。Notebook metadataのprivate/GPU/Internet無効も保持する。
- health_generateのresponseは起動readiness probeに限る。ゲームAction、正解情報、ID別policy分岐を追加しない。

## 実施・受入条件

1. v6 backup hash、notebook diff、metadata、nbformatを検査し、変更がcell13 readiness waitとcell18 offline cap/labelだけであることを確認。
2. SGLang pinned runtimeでhealth_generate routeが存在するか確認し、HTTP 200がbenchmark開始前に観測された場合だけrunする。12分で不成立なら同じrunを再試行せず、その失敗artifactを保存する。
3. private kernel version 7を一度だけpush/run。outer timeoutは7,200秒、GPU/private/Internet無効。
4. benchmark初期board/state/levelをv6のsk48と直接照合。job elapsedとper-game elapsedはC2-030 auditを使う。
5. v6のsk48 41 Actions/1 level/WIN 0からprevious/current/deltaを示す。request timeout、levels、actions、runtime、tokensを記録する。single-run差で一般化・公式scoreを主張しない。
6. Competition Rerun・公式提出・採点はしない。採否後にC2-033を作る。

## 境界

成功してもこれはcold-start/runtime budgetingの開発試験であり、solver能力改善・公式score改善を意味しない。公式提出quotaは今回消費しない。
## 実行開始記録

2026-10-23 UTC、Notebook version 7をprivate kernel tecchannn/arc3-model-guided-c2-025へpush。直後のread-only statusはRUNNING。変更Notebook SHA256 d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922。v6退避SHA256 fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a。offline game limit=1、max Actions=160、runtime=1,200秒、model/prompt/solverは不変更。metadataはprivate/GPU有効/Internet無効のまま。Competition Rerun・公式提出・採点は行っていない。
## 実行結果・採否（2026-10-23 21:34 UTC）

- Kaggle private kernel version 7 は `ERROR`。version指定でログを回収。保存物は `出力/ARC3-RUN-002-local/C2-032-kaggle-output/v7/arc3-model-guided-c2-025.log`（SHA256 `24ae6a54f64977729d5b074e58fa9562fe44bce53bd8ecc49742bd098165a6af`）と `serve.log`（SHA256 `e2b578339fd168e08b6c1bdebf197990124dc65f8f3bb0504272b8ff21762d40`）のみ。benchmark/summary/submission artifactは存在しない。
- server環境はSGLang `0.5.19+gd00d88efc8d6`、torch `2.13.0+cu130`、RTX PRO 6000 Blackwell。`serve.log`は38 shardのうち34 shard（89%）を読み込み、11分15秒時点で残り4 shard。server launchから720秒のready deadlineで `DEADLINE ... inference readiness was not confirmed`。Papermillはcell In [6]で `SGLang inference readiness was not confirmed; offline benchmark not started` を記録した。
- `/health_generate` のHTTP 200は未観測。失敗はready deadline前のモデル読み込み未完了と整合するが、health route自体の成否は判定できない。offline benchmark未開始のためv6 sk48（41 Actions、1 level、1,200.173秒）とのcurrent/deltaはN/A。solver/action、初期board、tokenは観測されていない。
- fail-closed条件は成立し、game timerが未ready時間を含む試験は実行されなかった。solver能力改善・timer分離の実証とは扱わない。Notebook version 7のSHA256は `d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922`。公式Competition Rerun、提出、採点は未実施。
- 採否：`/health_generate` gateは保持。12分のdeadlineではcold-startが完了しない実測のため、原因をhealth routeやsolverへ帰属せず、次のC2-033でstartup deadlineだけを延長して一度だけprivate検証する。再実行・公式候補昇格なし。
