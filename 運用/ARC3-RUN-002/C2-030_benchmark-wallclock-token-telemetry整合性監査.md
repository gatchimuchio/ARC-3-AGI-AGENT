# C2-030 benchmark wallclock・token telemetry整合性監査

## 目的と範囲

C2-027/v5およびC2-029/v6の既存private出力だけを使い、全体実行時間・per-game時間・生成tokenをどの欄から採るか確定する。summary表示の混同はbenchmark能力の差と誤認され得るため、同じ比較手順で再計算できるローカル監査ツールを追加する。

新規Kaggle実行、Competition Rerun、公式提出・採点はしない。Notebook、model、prompt、solver、HDS、公式候補、hidden/evaluator情報は変更・使用しない。IDは出力対応付けにのみ用いる。

## 実装

- 道具/benchmark_telemetry_audit.pyはbenchmark start/endからjob elapsedを算出し、各runの累積final_wallclock_secondsを隣接差へ直す。summaryのtotal wallclock/token、history generated_tokens、solver_noteのtokens=、final_generated_tokens欄を併記する。
- --manifestを渡すとbenchmarkのある出力directoryをrootとして各SHA256を照合する。source/harnessの由来を断定せず、summaryの値がどの計算と一致したかだけを検出する。
- 検証/test_benchmark_telemetry_audit.pyは累積timerとjob elapsedの区別、history/solver_note/final token照合、timer逆行拒否を検査する。
- 出力は出力/ARC3-RUN-002-local/C2-030-telemetry-audit/v5.jsonとv6.json。

## 実測結果

| run | benchmark start/end elapsed | summary total wallclock | cumulative timerの合計 | history tokens | solver_note tokens | manifest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| C2-027/v5, 25 run | 15,657.695秒 | 228,187.6秒 | 228,187.620秒 | 2,134,037 | 2,162,266 | 164/164一致 |
| C2-029/v6, 3 run | 3,200.794秒 | 6,673.7秒 | 6,673.737秒 | 358,198 | 389,877 | 32/32一致 |

両summaryのtotal wallclockはjob elapsedではなく、run順に累積したfinal_wallclock_secondsの総和に一致した。v5/v6で再現したため、今後全体時間はbenchmarkのstart_time/end_time差を正とし、per-game経過時間は逐次run順で累積timerの隣接差を使う。summaryのwallclock欄は全体時間比較に採用しない。

summaryのtotal tokensは両runともhistory合計に一致したが、solver_noteとの差はv5 +28,229（bp35 +2,149、r11l +8,046、sp80 +18,034）、v6 +31,679（sk48）。全runのfinal_generated_tokens欄は0で精密消費量として採用しない。token集計はhistory合計を保存し、solver_noteとの差・final欄は別列として保持する。

v5の全25 runはgave_up/WIN 0、v6の3 runもgave_up/WIN 0。C2-029のlevel delta +2はゲーム別に+1,+3,-2で一様ではなく、horizonの能力改善とは判定しない。公式結果への換算・候補昇格はしない。

## 検証・証拠

- targeted pytest: 3 passed。Ruff: utility/test両ファイルPASS。
- C2-030/v5 audit JSON SHA256 e7dbc4f1f00dcb8d83cd4b583c98809c6fb2a8270d06764c1f92cf5345de7e18
- C2-030/v6 audit JSON SHA256 d353dc4e9f95939bc5f7078024b24f1fbaa1f3b1bcd1180e5c242a0a1aa8ff02。
- source/history変更は運用記録、README/提出ledger、監査ツールとtargeted test、audit JSONのみ。AGENTS.md、制御/現在状態.json、正本ポインタ、model/prompt/solver、official candidateは変更なし。
- 現在のmain HEADは8667e9b9512e328084050007d3bdedb1ae5e245f。既存の未コミット作業は保持し、commit/stage/resetはしない。
- Kaggle read-only照会 2026-10-23 21:12 UTC: model-guided kernel status COMPLETE。公式latest candidate ref 57541830 COMPLETE/public 0.25、baseline ref 57527856 COMPLETE/public 0.00。今日のsubmissionは1、残り0。private runは公式提出枠を使っていない。通常runとCompetition Rerunは別段階で、後者の操作が日次提出枠を消費する。[ARC Prize 2026 docs](https://docs.arcprize.org/arc-prize-2026)

## 採否・次工程

計測解釈を固定し、今後の所要時間比較はaudit JSONのjob_elapsed_seconds、per-gameはelapsed_since_previous_game_seconds、tokenはhistory_generated_tokensを基準にする。外部summary generator自体の修正はこのrepoにsourceがないため行わない。

次の一課題C2-031はv6のsk48 runtime-cap runのrequest/turn予算・analyzer待ちを既存transcript、requests、serve/kernel logsで時間軸に沿って監査する。timeout一件やserver startupの観測を能力原因と早合点せず、経過時間の内訳・tool実行・Action数に結び付ける。変更・Kaggle rerun・公式提出は行わず、根因が特定できなければ新しいsolver変更を作らず次の性能課題を選ぶ。