# ARC3-RUN-003 C2-048: cross-level memory retention

## 2026-10-24: local candidate prepared; not pushed

- Baseline: C2-046 slim v12. Treatment config adds `ARC3_WM_WIPE_ON_LEVEL=0` and `ARC3_WM_REVISE_NUDGES=True`; summary compaction remains disabled.
- Notebook SHA256: `ba2977ced60f1a37e1a795c8c872afa81a7b2644f16069f45615bbe499403aad`; metadata SHA256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.
- The kernel metadata remains private/GPU-enabled/Internet-disabled. No official competition rerun, submission, or quota use.
- Push is deferred until the already-running C2-047 version 14 is terminal and its official-local-scorecard result is reviewed.
- Hypothesis, paired score gate, state checks, and memory-boundary audit: `運用/ARC3-RUN-003/C2-048_cross-level-memory-retention-pilot.md`.

## 2026-10-24 16:22 UTC: pre-push source audit

- Notebook source diff against C2-046 slim is limited to cell 5 with the two declared environment settings; metadata bytes and hash match. Candidate hashes match the manifest.
- C2-047 version 14 exact status at 2026-10-24 16:22 UTC remains `KernelWorkerStatus.RUNNING`; C2-048 stays local-only and is not pushed.

## 2026-10-24 16:24 UTC: baseline score decomposition

- Official evaluator-weighted mean contribution per game, off→slim: level 1 1.828→3.882; level 2 5.474→4.316; level 3 5.433→4.762; level 4 0→6.349; levels 5-7 zero. Exact contributions include the evaluator score cap and sum to means 12.735567/19.309156 within rounding. C2-048 will specifically inspect later-level efficiency/progression; this small-sample decomposition is diagnostic, not causal attribution.

## 2026-10-24 16:26 UTC: 25-environment depth target verified

- Recomputed the v5 benchmark depth curve from 25 saved runs: level 1 22/25, level 2 14/22, level 3 7/14, level 4 3/7, level 5 1/3, level 6 0/1; scorecard mean 11.523217.
- C2-048 remains a 3-run pilot. If it passes its paired score gate, the next required step is a matched 25-public-environment control/treatment comparison with fixed starts/seed/loader/budgets and the same official local scorecard. The 3-run result cannot close the score objective.

## C2-046 stalled-level trace diagnosis (2026-10-24 UTC)

The saved public local event traces show that stalled level-2 runs rarely revisit an exact board state: `off` sk48 99 actions/92 unique boards and tn36 108/107; `slim` sk48 57/54 and tn36 104/103. There were no board states repeated four or more times in these traces, and unchanged-board actions were 0-1 per run in these level-2 segments. This does not support a simple repeated-state/no-op loop as the main failure mode. The next experiment therefore targets retained and revisable memory across level transitions; causal benefit remains unverified until C2-048 is run and compared.

## Candidate wiring audit (2026-10-24 UTC)

Re-read the saved notebooks and embedded patch. C2-048 differs from C2-046 slim only in cell 5 and adds `ARC3_WM_WIPE_ON_LEVEL=0` plus `ARC3_WM_REVISE_NUDGES=True`. The embedded transition handler reads the wipe value at call time and routes a retained level transition into `revise_reason="level"`; the revision nudge helper reads the second flag. This confirms the intended setting path, not a score effect; C2-048 remains unrun.

## 2026-10-24 17:20 UTC: C2-047 review and decision

C2-047 completed. Its re-scored three-game mean is 5.95238095 versus C2-046 slim 19.30915594 (paired delta -13.35677499), with regressions on all 3 matched games. Initial board/state/level event fields and public action baselines match for 3/3. The summary-compaction branch is rejected as the current best candidate. C2-048 is selected next because it isolates cross-level memory retention/revision on the stronger C2-046 slim base; this is still only a public three-game pilot, not evidence of an official competition-score increase.

## 2026-10-24 17:27 UTC: private pilot launched

- Before push, the local notebook and metadata hashes matched the candidate manifest; metadata confirms private kernel, GPU enabled, Internet disabled.
- Kaggle CLI accepted C2-048 and reported `Kernel version 15 successfully pushed` at 17:26 UTC. `kernels list` reports `lastRunTime=2026-10-24T17:27:05`; slug-level status at 17:27:09 is `KernelWorkerStatus.RUNNING`, consistent with version 15 being the latest run.
- Scope: 3 public games, one pass, concurrency 1, seed 0, 160 actions/game and 1200 seconds/game. No official competition submission or rerun.
- Next: wait for this run to reach terminal status, fetch benchmark/log artifacts, and rescore against C2-046 slim.

## 2026-10-24 17:29:23 UTC: startup check

Slug-level kernel status remains `KernelWorkerStatus.RUNNING`. The live log exposes the SGLang model-server launch command; no benchmark summary or error is present yet. This is startup-stage evidence only, not a benchmark result.

## 2026-10-24 17:30:43 UTC: status recheck

Using the configured ARC2 `.venv` via `python -m kaggle` (the target repository's former `Scripts\kaggle.exe` path is absent), the C2-048 slug-level status remains `KernelWorkerStatus.RUNNING`; no benchmark output is available yet. The run was not restarted or modified.

## 2026-10-24 17:34:41 UTC: model-startup progress

Kaggle live logs now show precaching progress: 211 files (6.70 GB) in 24.44s, then 62 files (185.40 GB) in 278.38s. At 17:34:41 UTC the slug-level status remains `KernelWorkerStatus.RUNNING`. No benchmark summary is available yet; these are startup/model-load messages, not score evidence.

## 2026-10-24 17:37:06 UTC: benchmark started

Filtered Kaggle live logs now show the benchmark harness starting and the 3-game, 1-pass, 160-action/1200-second-per-game run entering `Starting benchmark...`. The harness still prints the copied baseline label `C2-046 loader/memory pilot`; this is a stale descriptive label, while the pushed version 15 candidate manifest and run configuration identify C2-048. Slug status remains `KernelWorkerStatus.RUNNING`. No score/output artifact has been fetched yet.

## 2026-10-24 17:39:23 UTC: official baseline and quota recheck

ARC3-specific read-only evidence confirms submission 57577905 is `COMPLETE`, public score 23.86, private score not provided. Limits are 1 submission today, 6 total, and 0 remaining today. This is unchanged from the baseline C2-048 must eventually beat. No official submission or rerun was performed. Evidence: `運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T173923Z.json`.

Operational note: `接続/Kaggle操作.py 提出可否確認` defaults to `arc-prize-2026-arc-agi-2`; that query's ARC2 response was excluded from this ARC3 quota record.

## 2026-10-24 17:43:20 UTC: candidate integrity recheck

The local C2-048 notebook and kernel metadata SHA-256 values still match the pushed-version-15 manifest. Kaggle status remains `KernelWorkerStatus.RUNNING`; the output directory has not appeared yet. No source edits or reruns were made.

## 2026-10-24 17:46 UTC: prompt-level audit method confirmed

The prior completed pilot's `requests.jsonl` contains 346 request records with full `messages`. C2-048's configured level nudge has the marker `LEVEL CHANGED - your memory sections were KEPT, not wiped.` Once C2-048 output is available, inspect requests after each level transition for that delivered marker, the following `World model:`/`Plan:` revisions, and any rejected memory updates. This checks actual prompt delivery and stale level-specific carryover, beyond confirming environment settings.

## 2026-10-24 17:47:35 UTC: interim benchmark log

The live log printed `benchmark: regenerated diagnostics in /kaggle/working in 0.52s`, then `mean score: 0.93` and the per-game heading. The captured stream did not include per-game rows. At 17:48:12 UTC the kernel still reported `KernelWorkerStatus.RUNNING`, so 0.93 is recorded as interim only and is not used for candidate acceptance or rejection. Await terminal status and the complete output bundle.


## 2026-10-24 17:55:41 UTC: official score gate refresh

ARC3 CLI history still reports submission 57577905 `COMPLETE`, public score 23.86, private score not provided; limits remain 1 today, 6 total, 0 remaining today. C2-048 remains a candidate filter, not an official score change. No submission or rerun was performed.

## 2026-10-24 17:57:31 UTC: in-progress output availability check

Read-only `kernels output` probe requested only the summary, benchmark JSON, and kernel log while the slug remained running; Kaggle returned no files. The empty probe directory was removed. No output is locally available yet; no rerun or submission was made.

## 2026-10-24 17:58:32 UTC: analyzer timeouts during active run

Live log repeated twice: `analyzer request timed out at action 54; yielding with 0 tool call(s) preserved`, with local SGLang HTTP read timeout `44.42050213099992` seconds. The log still prints an interim mean of 0.93 without per-game rows. Kaggle remained `KernelWorkerStatus.RUNNING` at 17:58:32 UTC and no output files were available. No restart or duplicate run; await terminal outcome.

## 2026-10-24 18:05:14 UTC: timeout comparison with completed pilots

Structured line review found two distinct timeout events in each completed comparison: C2-046 slim at actions 100 and 131; C2-047 at actions 73 and 71. Each event was emitted twice in the captured runtime log. C2-048 has one distinct event so far (action 54), also duplicated in the stream. Thus timeout frequency observed to date is not elevated versus those completed pilots; the interim 0.93 cannot be attributed to a higher timeout count. C2-048 remains nonterminal.

## 2026-10-24 18:07:44 UTC: interim diagnostic update

Filtered live logs regenerated diagnostics in 0.33s and printed an interim mean score of 1.33, up from the previously observed 0.93. The per-game section still has no rows in the captured stream, and Kaggle status remains `KernelWorkerStatus.RUNNING`; this is progress evidence only, not a final scorecard.

## 2026-10-24 18:08 UTC: exact version 15 source-cell attribution

Downloaded Kaggle kernel version 15 source (not its output) and compared it to the local C2-048 candidate. All 25 notebook cell source strings match exactly, and shared execution metadata matches across the 13 compared fields. Raw notebook SHA-256 differs due Kaggle serialization (`19cce0304bdd71fb72cfea66906574182ca832276ab7e41b23be255a55e14636` remote vs `ba2977ced60f1a37e1a795c8c872afa81a7b2644f16069f45615bbe499403aad` local); metadata adds server fields and renames `code_file`. Exact evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-048-v15-source-cell-verification-20261024T1808Z.json`. Kernel status remains RUNNING; no outputs were read and no rerun/submission occurred.

## 2026-10-24 18:17:38 UTC: interim diagnostic update

Filtered live logs regenerated diagnostics in 0.47s and printed an interim mean score of 7.36, up from 1.33 at 18:07:44 UTC. The captured per-game section still has no rows. Kaggle status remains `KernelWorkerStatus.RUNNING`; this is not the terminal scorecard or an official competition score.

## 2026-10-24 18:27:31 UTC: interim diagnostic update

Filtered live logs regenerated diagnostics in 0.35s and printed an interim mean score of 12.13, up from 7.36 at 18:17:38 UTC. The captured per-game section still has no rows. Kaggle status remains `KernelWorkerStatus.RUNNING` after approximately 60 minutes from the manifest start time; this is not the terminal scorecard or an official competition score.

## 2026-10-24 18:28 UTC: prompt-trace evidence gate

The completed version-14 remote output contract contains only the log, `benchmark.json`, and `summary.txt`; it has no `requests.jsonl`. Its benchmark and log contain no `LEVEL CHANGED`, `World model:`, or `Plan:` marker content. Therefore, if version 15 output lacks an equivalent request trace, the C2-048 prompt-delivery and stale-memory audit remains unverified and cannot be waived. Exact inventory and hashes: `運用/証拠/ARC26-UNIFIED/ARC3-C2-048-output-telemetry-readiness-20261024T1828Z.json`. Version 15 was still RUNNING at observation; no output was pulled.

## 2026-10-24 18:36:14 UTC: interim diagnostic and timeout update

The live log recorded an analyzer request timeout at action 158 (HTTP read timeout 49.116s; duplicate log emission), then regenerated diagnostics in 0.92s and printed interim mean score 16.89, up from 12.13 at 18:27:31 UTC. This is C2-048's second distinct timeout event; the prior action-54 event was also duplicated, so the distinct-event count matches C2-046/C2-047's two events each. Kaggle status remains `KernelWorkerStatus.RUNNING`; the printed score is nonterminal and still below C2-046 slim's 19.30915594 pilot mean and the official 23.86 baseline.


## 2026-10-24 19:03 UTC: C2-048 v15 terminal paired score and prompt audit

The private Kaggle kernel version 15 completed. The local candidate and remote notebook have matching source text in all 25 cells, and their shared execution metadata matches. This was not an official competition submission.

Using EnvironmentScoreCalculator on the same three public games, v15 averaged 16.888441. C2-046 v13 remains the best matched baseline at 19.309156, so v15 is lower by 2.420715. Paired deltas were -19.047619, 0, and +11.785473; completed-level deltas were -1, 0, and +1. All three runs ended gave_up / NOT_FINISHED; there were no wins. The candidate fails both the mean and all-games-positive gates. It is not adopted, and the 25-game expansion is not run.

The exact remote requests.jsonl was streamed read-only: HTTP 200, 120,184,640 bytes, SHA-256 7e4bdced063f342c93d458781b3f50db27034051f48a76211c63ff38ce1f4e0c, 412 valid JSONL records. After all seven observed level transitions, the configured marker appeared within the next three requests; World model: and Plan: were present after every transition. The Plan section hash changed after 7/7 transitions and the World model hash after 4/7. No memory-update rejection was recorded in user, assistant, or tool message text. The trace contains 207 request records and 205 response records, so the two unpaired requests limit the negative rejection finding. The full trace was not saved locally; the prior local CLI copy remains explicitly incomplete.

C2-048 is closed as a failed pilot. C2-050's dependency on the C2-048 terminal result is now cleared for offline review; this record does not authorize or claim a C2-050 push/run.
