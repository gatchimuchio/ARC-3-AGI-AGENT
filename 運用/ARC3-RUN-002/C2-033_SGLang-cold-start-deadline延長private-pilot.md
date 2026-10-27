# C2-033 SGLang cold-start deadline延長private-pilot

## 目的

C2-032のversion 7はprivate `ERROR`。SGLang 0.5.19+gd00d88efc8d6 / torch 2.13.0+cu130、RTX PRO 6000 Blackwellで38 weight shardの34/38（89%）を11分15秒時点までに読み込んだが、server launch後720秒のreadiness deadlineでbenchmark開始前に停止した。`/health_generate` HTTP 200は観測されていないため、route failureとは結論しない。cold-start時間がdeadlineを超えたことだけを対象とする。

## 変更範囲

- C2-032 version 7のNotebookをbaselineとし、変更前コピーを `出力/ARC3-RUN-002-local/C2-033-source/v7-submission.ipynb` に保存する。
- Notebook cell 5で定義する `SERVER_STARTUP_TIMEOUT` だけを720秒から1,080秒（18分）へ変更する。値を消費するcell 13の `/health_generate` probeとprocess-exit時のfail-closed条件は保持する。
- offline guard cell 18のラベルをC2-033へ更新する。game limit=1、pass=1、concurrency=1、max Actions=160、per-game runtime=1,200秒は変えない。
- model、prompt、solver/action、server args、retry/timeout policy、TRUE_SUBMISSION path、official candidate、HDS、`AGENTS.md`、`制御/現在状態.json`、正本pointerは変更しない。
- GPU/private/Internet無効を維持し、C2-033としてkernel version 8を一度だけpush/run。追加実行はしない。

## 判定条件

1. Notebookの変更cellがdeadline定義とoffline labelだけであること、nbformat/AST、metadata、SHA256を検査する。
2. ready 200が1,080秒内に記録され、benchmark開始時刻がready後である場合だけtimer分離のpilotが成立する。deadline切れまたはprocess exitなら保存出力を失敗証拠として閉じる。
3. benchmarkが始まった場合はfirst game ID/initial board/state/levelをv6 sk48と比較し、C2-030 auditでruntime/actions/levels/tokensを取得。previous/current/deltaと負の結果を記録する。
4. 単一環境の結果はruntime起動・timer境界に限って解釈し、solver能力や公式scoreへ一般化しない。
5. Competition Rerun・公式提出・採点は行わない。

## 前回証拠

- version 7 status `ERROR`。stream `DEADLINE after 720s from server launch`、Notebook例外 `offline benchmark not started`。
- `serve.log`: 34/38 shard at 11:15; v7 kernel log / serve.log SHA256はC2-032結果欄を参照。
- version 7 source Notebook SHA256 `d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922`。

## 採否

C2-032ではsolver/action変更なし。C2-033はreadiness deadlineのみを検証する。v8が失敗した場合はdeadlineを無制限に延ばさず、保存ログから次の原因を一件選び直す。

## 実行結果・採否（2026-10-24 JST追記）

- private kernel `tecchannn/arc3-model-guided-c2-025` version 8の状態をKaggle CLIで読み取り、`COMPLETE`を確認。current kernel log SHA256 `7a8fd7ab692ac4d83c2fbf91655db00a13076b8badbdcdb62a8110912e602387`、`serve.log` SHA256 `da2c531fa08b2a6b807dc5ee3712e93caeb7ddf0d05d8eec80a58518bf9a6b10`。
- version 8 Notebook SHA256 `449b57c9eca8f24a6338b5eb6f68d231a2fab4185073293a79c00581f85a5a05`。ログ上、推論readyはserver起動904秒後、benchmark開始は966.152秒後で、readyからbenchmarkまで約62秒。起動待ちがgame timerに入る状態は回避できた。
- 開発用benchmarkは `sk48-d8078629` 1 run、`gave_up`、8 level中1 level、88 actions、1200.059秒、WIN 0。history生成token 106,659、solver note 173,415、`final_generated_tokens`欄0。summary上のmean score 1.33はprivate開発用指標で、公式scoreではない。
- previousのversion 6同一game IDは1/8 level、41 actions、1200.173秒、WIN 0。version 8との差はactions `+47`、levels `0`、runtime `-0.114秒`、history tokens `+29,950`。開始盤面PNG SHA256 `8af64ad67d8f05d216355dd57c6f39eeb72266a26408517ce134817cda156c67`は一致と記録されているが、version 8のraw開始state/levelは出力から個別確認できていないため、deltaは記述比較に限り能力改善とは採らない。
- `benchmark_telemetry_audit.py`でjob elapsed `1200.171854秒`、game timer `1200.059224秒`、summary値との整合を確認。`C2-033-output.sha256`でbenchmark等19ファイルを検査し、19/19照合成功、不一致0。監査JSON SHA256 `f963778fce9420e241385ab90f2f474d179687bc72a06cdbfc797c7b015552ac`、manifest SHA256 `e0fef90488dbae44ee2942531efa2a3ff75dff6b8dd580dbff83a208a8d73d0f`。
- 採否：cold-start deadline延長によるreadiness-before-benchmarkは確認。solver能力・公式scoreの改善は未確認。追加private run、Competition Rerun、公式提出・採点は行わず、C2-033を閉じる。
