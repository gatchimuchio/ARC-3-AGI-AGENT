# ARC3-RUN-003 C2-047: rolling-summary context compaction

## 2026-10-25: private pilot prepared

- 起点は C2-046 slim version 12。変更は環境設定2項目のみ: `ARC3_SUMMARY_INTERVAL_TOKENS=32768`、`ARC3_SUMMARY_REPLACES_HISTORY=True`。
- Notebook SHA256: `9339fc194f8db3124b610fd24075d91745c796185e6274c670e80c6caa58c1fd`; metadata SHA256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.
- 固定条件: private/GPU/Internet無効、公開offline 3件、seed 0、1 pass、逐次、160 actions/game、1,200秒/game、startup deadline 1,800秒。公式rerun/submission/quota使用なし。
- C2-046 slimで request本文（画像ブロックを除く）は初回18,847文字、中央値38,197、p90 53,385、最終56,395、最大59,854。request 249、prompt tokens 17,277,615、level 7/21、timeout 2/3。履歴増大を圧縮して実行余力を戻す仮説を検証する。
- 判定条件と集計項目は `運用/ARC3-RUN-003/C2-047_rolling-summary-context-compaction-pilot.md` を参照。
- Kaggle push/version/status: 未実施。

## 2026-10-24 16:04 UTC: version 14 pushed

- Kaggle CLI reported `Kernel version 14 successfully pushed` for `tecchannn/arc3-model-guided-c2-025`; the push was issued once. Exact-version read-only status is `KernelWorkerStatus.RUNNING` (observed immediately after push).
- Kernel metadata remains private, GPU enabled, Internet disabled. This is the 3-game offline benchmark candidate; no official competition rerun/submission or quota use was made. Completion logs will be checked for readiness, summary replacement, terminal status, and aggregate metrics.

## 2026-10-24 16:05 UTC: post-push audit refinement

- Source inspection shows `ARC3_SUMMARY_TURN_CONTEXT` defaults false and the summary instruction does not impose a length cap. Keep the run as pushed; audit whether summaries actually compact requests, whether World model/Plan markers are reinjected after replacement, and whether level-change context is stale. These are explicit rejection conditions; no further version was pushed.

## 2026-10-24 16:06 UTC: configuration defaults recorded

- Manifest now records the inherited defaults `ARC3_SUMMARY_TURN_CONTEXT=False` and `ARC3_SUMMARY_ENABLE_THINKING=False`; notebook source/hash are unchanged from pushed version 14.

## 2026-10-24 16:07 UTC: status follow-up

- Read-only exact-version status for `tecchannn/arc3-model-guided-c2-025/14` remains `KernelWorkerStatus.RUNNING`. No rerun, duplicate push, or official submission.

## 2026-10-24 16:09 UTC: live-output check

- Exact version 14 remains `KernelWorkerStatus.RUNNING`; `kaggle kernels logs` returned no live log content. This is not a terminal result; no restart or duplicate push.

## 2026-10-24 16:10 UTC: exact-version output lookup

- Version 14 remains `KernelWorkerStatus.RUNNING`. Exact-version output lookup for `.log` artifacts returned no files while running. No restart or duplicate push.

## 2026-10-24 16:12 UTC: scorecard baseline verified

- Recomputed C2-046 off/slim `benchmark.json` per-run scores with the repository's official `EnvironmentScoreCalculator` scorer (`検証/ARC3モデルv5公開25scorecard再採点.py`); saved `final_score` matches 6/6.
- Paired 3-game public scorecard: off mean 12.735567, slim mean 19.309156, mean delta +6.573589; two paired improvements, one regression. This is local public scorecard evidence, not Kaggle submission score.
- Updated C2-047 decision rule: use paired scorecard as primary; require a positive mean delta and mean above the C2-046 slim reference before treating it as a score-improvement candidate. Runtime and timeout reductions alone do not count as score gain.

## 2026-10-24 16:15 UTC: historical v5 subset reference

- The three C2-046 game keys overlap with the saved v5 25-environment benchmark; all per-run scores were recalculated using the official local scorecard function. Means on the common-key subset: v5 4.761905, off 12.735567, slim 19.309156; slim-v5 sorted paired deltas are +2.777778, +7.530642, +33.333333.
- Existing v5 comparison artifact reports v5/local-v4 board/state/level matches 3/3 for this subset; C2-046 reports off/slim start matches 3/3. A direct cross-pipeline board-hash join was not available, so this is secondary directional evidence, not official Kaggle score or the primary C2-047 gate. No IDs are retained here.

## 2026-10-24 16:15 UTC: status remains live

- Read-only exact-version check still reports `KernelWorkerStatus.RUNNING` for version 14. This confirms the same private run remains active; no retry or replacement push.

## 2026-10-24 16:19 UTC: token telemetry provenance checked

- `requests.jsonl` response `usage` is the authoritative prompt-token source. C2-046 off: 210 responses, total 14,684,991, median 71,349, p90 110,701, max 118,555, cached share 92.40%. Slim: 247 responses, total 17,277,615, median 74,390, p90 105,462, max 116,437, cached share 94.26%. `benchmark.json` `uncached_input_tokens` is 0 and is excluded from prompt-token comparisons.
- Exact-version Kaggle status at this observation remains `KernelWorkerStatus.RUNNING`; no live output/logs yet.

## Cross-level memory scope clarification

- The C2-047 notebook inherits `ARC3_WM_WIPE_ON_LEVEL=1` from C2-046. Its experiment tests rolling-summary compression with the same within-level memory lifecycle; it does not test cross-level memory retention. A separately prepared C2-048 will test retain-and-revise after version 14 is reviewed.

## 2026-10-24 16:24 UTC: level-weighted score diagnostic

- Evaluator-capped per-level mean score contribution in the C2-046 paired baseline, off→slim: level 1 1.828→3.882; level 2 5.474→4.316; level 3 5.433→4.762; level 4 0→6.349. C2-047 inherits the same level-wipe behavior and targets context cost; it will be evaluated for whether compression improves score/efficiency without conflating cross-level retention.
- Exact-version status checked at 2026-10-24 16:24 UTC: `KernelWorkerStatus.RUNNING`; no restart or duplicate push.

## 2026-10-24 16:26 UTC: status and log recheck

- Exact version 14 remains `KernelWorkerStatus.RUNNING`; exact-version `.log` output lookup returned no files. Existing run remains active; no restart or duplicate push.

## 2026-10-24 16:33 UTC: exact-version recheck

- Version 14 remains `KernelWorkerStatus.RUNNING`. No restart, duplicate push, or output-log result. C2-048 remains prepared but deferred until this run reaches terminal status.

## Candidate wiring audit (2026-10-24 UTC)

Re-read the saved notebooks and embedded patch. C2-047 differs from C2-046 slim only in cell 5 and sets the 32,768-token summary interval and history replacement flag. The embedded implementation reads both settings. Its inherited context drain target is 58*1024=59,392 tokens, about 1.8 summary intervals; review the completed run for summaries occurring before/at context drain and for usable compressed context. Summary generation defaults to `max_tokens=8192`, with thinking and turn-context disabled unless separately set. This is a configuration audit only; score and summary quality remain unobserved while version 14 runs.
## 2026-10-24 16:39 UTC: exact-version status

- Version 14 remains `KernelWorkerStatus.RUNNING`; filtered output lookup returned no benchmark, summary, or log files. No restart or duplicate push.
- C2-049 is prepared locally as a one-setting follow-up and its notebook/metadata hashes match the manifest. It has not been pushed or run.
## 2026-10-24 16:43 UTC: exact-version recheck

- Version 14 remains `KernelWorkerStatus.RUNNING`; no output files have appeared. No restart or duplicate push.
- C2-048 notebook and metadata hashes match its manifest; it remains deferred until version 14 is terminal and reviewed.

## Runtime field audit (2026-10-24 UTC)

Validated the C2-046 timing convention against `benchmark.json`: `game_runs[].started_at` is the shared benchmark start; `final_wallclock_seconds` is cumulative, and the last value matches total benchmark duration. Per-game elapsed is the successive delta. Public local control elapsed values were 1118.1, 1055.9, and 1081.6 seconds (0/3 at the 1200-second cap); slim values were 1200.1, 1200.0, and 787.5 seconds (2/3 at the cap). C2-047 evaluation must use these deltas, not the cumulative field.

## 2026-10-24 UTC: official objective and status-selector correction

Kaggle CLI submission history re-read at approximately 16:49 UTC confirms submission 57577905 `SubmissionStatus.COMPLETE`, publicScore 23.86, privateScore blank. This is the official result to beat; the local 3-game/public-25 scorecards are only candidate filters and do not establish a delta against that hidden aggregate.

Correction to prior status wording: Kaggle CLI 2.2.4 parses but does not send the `/14` suffix for `kernels status` or `kernels output`; those calls report the latest run for the kernel slug, not a version-selected status. `kernels list --mine` reports `lastRunTime=2026-10-24T16:03:47`, matching the C2-047 version-14 push at 16:04 UTC, so the slug-level `RUNNING` observation is consistent with C2-047 being the latest run, but is not itself a version-specific status response. No later run/push is recorded in this workflow.

## 2026-10-24 17:00 UTC: latest-run recheck

- `kernels list --mine` still reports `lastRunTime=2026-10-24T16:03:47`; slug-level `kernels status` remains `KernelWorkerStatus.RUNNING`; filtered benchmark/summary/log output remains absent. This is the latest run consistent with C2-047's 16:04 UTC version-14 push; the CLI status API is not version-specific.
- Official-score target remains a new Kaggle `publicScore > 23.86` (submission 57577905); no official submission or rerun was made.

## 2026-10-24 17:05:36 UTC: run still active

- Latest `kernels list --mine` observation remains `lastRunTime=2026-10-24T16:03:47`; slug-level `kernels status` is still `KernelWorkerStatus.RUNNING` (about 61m49s since that start time). No result files are present locally. A non-quiet `kernels output` call produced no downloaded file and no error beyond the Kaggle CLI version notice.
- This is an active run, not terminal evidence. No restart, push, or official submission was made; result review remains pending.

## 2026-10-24 17:06:10 UTC: continuation readiness check

The local notebook and kernel-metadata SHA-256 values for C2-047, C2-048, and C2-049 all match their candidate manifests. C2-048 and C2-049 remain local-only; the C2-047 latest run is still RUNNING, so no next GPU run has been started.

## 2026-10-24 17:08-17:11 UTC: live-log diagnostic (provisional)

`kernels logs --follow` exposed live benchmark diagnostics that ordinary `kernels logs` omitted while the run was active. The latest diagnostic said `ended: in progress`, 3 games, 3 runs, 0 wins, mean score 1.19, median 0.00, 165 actions and 368,611 tokens. Per-game entries were still intermediate; these values are not a final scorecard or Kaggle competition score. At 17:11:05 UTC the slug-level status remained `KernelWorkerStatus.RUNNING`, `lastRunTime` remained `2026-10-24T16:03:47`, and no result files were available locally.

The live log also showed rolling-summary attempts that tried to call `python`: one had 0 chars of text and was skipped; a response with 7,980 chars was kept while the tool call was dropped. Static inspection of the candidate notebook confirms `_maybe_append_rolling_summary` passes the full turn `tools` list into `_chat_completion`, even though this summary request runs outside the turn loop and those calls cannot execute. This is a concrete candidate defect to address after reviewing the terminal C2-047 result. No restart, push, or official submission was made.

## 2026-10-24 17:15:53 UTC: status recheck

The same latest kernel run remains `KernelWorkerStatus.RUNNING`; `lastRunTime` is unchanged and no output artifact has appeared. The 17:08 live metrics remain provisional. No new run was started.

## 2026-10-24 17:18:32 UTC: status recheck

The same slug-level run remains `KernelWorkerStatus.RUNNING`; output directory still contains no downloadable result files. `kernels logs --follow` returned the same latest benchmark snapshot as at 17:08 and no new summary/terminal line during this observation window. Continue treating mean 1.19 as provisional.

## 2026-10-24 17:19-17:20 UTC: terminal result and paired rescore

Kaggle slug-level status was `KernelWorkerStatus.COMPLETE` at 17:20:39 UTC; the run benchmark ended 17:19:15 UTC. The saved summary reports three games, one pass, zero wins, 211 actions, 489,628 generated tokens and 1h00m02s duration. The official local `EnvironmentScoreCalculator` rescoring helper returns C2-047 mean 5.95238095 (per game: m0r0 14.28571429 at 2/6 levels; sk48 0 at 0/8; tn36 3.57142857 at 1/7).

Paired against C2-046 slim on the exact same three game keys, identical base-action arrays/level counts and matching initial event fields (board, board_ascii, score, state, level, run_status, action_num, action_display, reward) for 3/3: C2-046 slim mean 19.30915594; C2-047 mean 5.95238095; delta -13.35677499. All three game scores and completed-level counts regressed. This rejects C2-047 as an improvement candidate; its local pilot score is not a Kaggle competition score.

Next experiment selected: C2-048, which starts from the stronger C2-046 slim baseline and changes only cross-level memory retention/revision. C2-050 remains a deferred local candidate for repairing summary tool access.
