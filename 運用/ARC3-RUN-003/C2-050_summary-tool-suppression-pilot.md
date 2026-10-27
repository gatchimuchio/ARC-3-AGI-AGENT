# C2-050: Rolling Summary Without Tools

## 仮説

C2-047のlive logでは rolling summary 中に `python` tool call が発生した。空のcontentで要約をスキップした試行と、7,980文字のsummaryを残してtool callを破棄した応答が観測された。`_maybe_append_rolling_summary` は通常ターンのtool schemaをそのまま `_chat_completion` に渡している。summaryはturn loop外でsandbox/action budgetもなく、tool callを実行できない。summary requestだけ `tools=None` とし、空の要約試行と破棄される呼び出しを避ける。

## 変更範囲

C2-047 version 14を複製し、`_maybe_append_rolling_summary` の `tools=tools` 一箇所を `tools=None` に変更する。他設定、prompt、summary interval (32768 tokens)、history replacement、対象game、seed、action/runtime上限は固定する。

## 現状と実行ゲート

C2-047のKaggle latest runは2026-10-24 17:11 UTC時点で `RUNNING`。C2-047のterminal結果とlocal scorecardを確認してから、C2-050をpush/runするか決める。準備中の候補であり、未push・未実行。

## 評価

C2-047とC2-046 slimの同じ3公開gameをpaired比較する。score、完了level、action効率、timeout/runtimeを確認し、summaryの成功/空応答/tool-call rejectionの記録を比較する。C2-046 slimのlocal mean 19.309156を超え、paired mean差が正で、summary履歴置換が確認できることを候補採用ゲートとする。これはKaggle公式scoreではない。公式改善の成立条件は、後続のKaggle publicScoreが現best 23.86を超えること。

## 安全条件

GPU、private、internet disabled、3 public games、seed 0、1 pass、concurrency 1、160 actions/game、1200 seconds/game、startup timeout 1800 seconds。C2-047のrunがterminalになる前に新しいGPU runを起動しない。公式submissionは行わない。

## 2026-10-24 17:27 UTC: candidate sequencing update

C2-050 remains local-only and is deferred while the selected C2-048 version-15 cross-level-retention pilot runs. C2-047 terminal scorecard regressed on all 3 matched games; no new summary-based run is started before the C2-048 result is reviewed.


## 2026-10-24 19:07 UTC: C2-050 pre-run gate review

C2-048 v15 is terminal and its paired gate failed, so its 25-game expansion is not run. This clears the sequencing hold on C2-050. C2-047 v14 scored 5.952381 versus C2-046 v13 at 19.309156, with paired deltas -33.333333, -2.777778, and -3.959214; all three games regressed.

C2-050 remains the single-change summary-tool fix: parsed notebook sources differ in one cell and one line, replacing tools=tools with tools=None in _maybe_append_rolling_summary; all other cell source lines are equal, metadata bytes are unchanged, and candidate-manifest hashes match. Its controlled private three-game pilot is approved to proceed under the existing experiment contract (seed 0, one pass, concurrency 1, GPU on, internet off, 160 actions/game, 1,200 seconds/game). The acceptance gate remains a mean above 19.309156, positive paired mean delta, and verified summary-history replacement. This is not an official competition rerun or submission. At this record's timestamp, push/run had not yet occurred.

Pre-run review evidence: ARC3-C2-050-pre-run-review-20261024T1907Z.json.


## 2026-10-24 19:14 UTC: duplicate C2-050 remote runs

After the C2-050 push, Kaggle reported version 17. Exact status checks show both versions 16 and 17 RUNNING. Version 16 existed before this task's push; its origin is unknown. Pulling both exact versions showed identical serialized notebooks and metadata, with all 25 source cells equal to the local C2-050 candidate. Version 17 is therefore a duplicate of the already-running version 16.

This violates the experiment's concurrency=1 control. Do not use either output as an adoption scorecard; they are diagnostic only unless the overlap is disproven. No further push, private run, official rerun, or competition submission is permitted while these versions run. The Kaggle CLI has no cancel command; the SDK cancellation method needs a session id that the exact-version status response did not expose. The computer-use helper failed during initialization, and no UI action was performed. Version 16 was not touched.

Incident evidence: ARC3-C2-050-duplicate-run-incident-20261024T1914Z.json.


## 2026-10-24 19:15 UTC: scope clarification for pre-run observation

The 19:07 pre-run note's “push/run had not yet occurred” refers to the push initiated by this task. The first exact-version status observation after that push found version 16 already RUNNING; its origin and whether it was active before the version-17 push are unknown. The version-17 push and source duplication are recorded in the incident evidence. The incident record is the current authority for remote run status.

## 2026-10-24 19:23 UTC: version 16 terminal error, version 17 still running

A fresh exact-version status query reports version 16 as ERROR and version 17 as RUNNING. Version 16 output was recovered into a separate directory. Its kernel log records the 1,800-second server-readiness deadline and says the offline benchmark did not start; repeated sitecustomize warnings report missing wrapt, but the logs do not establish that as the cause. The candidate change was not evaluated in version 16.

The concurrency=1 gate was already breached when both versions were RUNNING at 19:14 UTC. Both versions remain diagnostic only and are ineligible for candidate adoption. Since version 17 is now the only RUNNING version, it is left to reach terminal status. No new push, private run, official rerun, or competition submission is started.

Evidence: ARC3-C2-050-v16-terminal-error-20261024T192335Z.json; recovered logs are listed there by path and SHA-256. Next: track version 17 to terminal and retrieve its outputs separately.
## 2026-10-24 19:44 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 19:49:11 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T1944Z.json.

## 2026-10-24 19:49 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR. Version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 19:54:23 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T1949Z.json.

## 2026-10-24 19:54 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 19:59:36 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T1954Z.json.

## 2026-10-24 20:00 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 20:05:01 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T2000Z.json.

## 2026-10-24 20:05 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 20:10:33 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T2005Z.json.

## 2026-10-24 20:10 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 20:15:41 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T2010Z.json.

## 2026-10-24 20:16 UTC: exact version 17 status recheck

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 remains KernelWorkerStatus.RUNNING. Version 16 remains terminal ERROR; version 17 output is not yet recovered. The duplicate-run concurrency gate was breached, so neither run is eligible for adoption. No new run or competition submission was started. Next exact-version check is due at 20:21:41 UTC.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T2016Z.json.

## 2026-10-24 20:22 UTC: exact version 17 reached terminal state

Kaggle exact-version status for tecchannn/arc3-model-guided-c2-025/17 changed from RUNNING to COMPLETE. Version 16 remains ERROR. Output for version 17 has not yet been recovered. The duplicate-run concurrency gate was breached, so both versions remain diagnostic-only and ineligible for adoption. No competition submission was started. Next action: retrieve exact version 17 outputs and inspect only diagnostic evidence.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-status-20261024T2022Z.json.

## 2026-10-24 20:22 UTC: exact version 17 output recovered and audited

Version 17 is COMPLETE and its exact-version output archive has been recovered. The aggregate private benchmark summary reports 3 games, 1 pass, 3 runs, 0 wins, 243 actions, 3/21 levels completed, mean 4.91, median 0.44, and 7,209.4 seconds total job wallclock. The stated mean gate (>19.309156) fails. The duplicate-run concurrency gate also remains breached, so the candidate is diagnostic-only and ineligible for adoption. Official ARC3 submission 57577905 remains COMPLETE/public_score 23.86; no competition submission was made.

Only aggregate summary data was recorded; transcripts, request logs, per-game cards, intermediate states, and raw event logs were not inspected or used for solver changes.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-050-v17-aggregate-audit-20261024T2022Z.json.
