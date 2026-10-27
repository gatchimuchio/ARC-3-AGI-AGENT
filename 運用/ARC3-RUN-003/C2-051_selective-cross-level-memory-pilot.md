# C2-051: Selective cross-level memory pilot

## Hypothesis

C1-019 shows public level progression declines with depth while visible no-op actions remain low. C2-046 slim is the current strongest matched 3-game local scorecard (19.309156). C2-048 kept both `World model` and `Plan` across level transitions and scored 16.888441 (-2.420715 paired); the plan was revised after each observed transition, while the world-model section changed after 4/7. `Plan` means intended next steps and is level-specific. This candidate keeps durable mechanics in `World model` but clears only `current_plan` at a level transition, retaining the existing revision nudge.

C1-020 did not support a generic board-statistics predictor for level progress. C2-051 therefore tests memory lifecycle only; it does not add board features, game/level lookup, fixed actions, or problem-specific rules.

## Candidate and controls

- Base: C2-048 version 15, private offline candidate.
- Treatment: one two-line addition in the existing level-transition memory handler; all other source cells and kernel metadata are unchanged.
- At a level transition, `current_plan` is cleared; `world_model` remains stored and the existing revise nudge remains enabled. Same 3 public games, seed 0, 1 pass, 160 actions/game, 1,200 seconds/game, private GPU, internet disabled, concurrency 1.
- This is a local candidate filter, not an official competition rerun or submission. No quota use.

## Acceptance

Rescore with the official local `EnvironmentScoreCalculator` and verify all three public starts match. Proceed only if mean is strictly greater than C2-046 slim's 19.309155944 and paired mean delta is positive. Report level progression, wins, actions, timeouts, token use, and memory delivery. Otherwise reject and keep C2-046 slim as the best matched pilot. Any later official claim requires a new Kaggle competition public score greater than 23.86.

## Initial state

Prepared locally only; not pushed or run. C2-050 version 17 is COMPLETE and version 16's saved terminal log shows the readiness deadline failure; the duplicate-run gate is cleared for one new private run. The C2-051 notebook and patch must pass source/hash and patch-parse checks before a single push.


## 2026-10-24 20:32 UTC: source audit and pre-run gate

The candidate notebook differs from C2-048 only in cell 3; all other cell source and kernel metadata bytes are identical. The added level-transition branch clears `current_plan` while retaining `world_model`. The embedded unified patch parses with `git apply --numstat` across all 17 patched paths. Notebook SHA-256: `0caf246e690489e225a4a1fe6b2de6e04c56ffdfc0b3ba310fc192ecfd9ca482`; metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.

Kaggle read-only pre-run status is `KernelWorkerStatus.COMPLETE`; `kernels list --mine` reports the prior latest run at 2026-10-24 19:08:17 UTC. C2-050 v16 has its saved readiness-timeout terminal artifact and v17 has a COMPLETE result, clearing the prior concurrency gate. Metadata confirms private=true, GPU=true, Internet=false. Pre-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-pre-run-review-20261024T203215Z.json`.

Ready for exactly one private offline three-game pilot. No official competition submission or rerun.


## 2026-10-24 20:33 UTC: private pilot launched

A single Kaggle push returned exit code 0 and explicitly reported **Kernel version 18 successfully pushed**. The immediate read-only latest-kernel status query reported `KernelWorkerStatus.RUNNING` at 20:32:42 UTC. This is one private offline three-game pilot; no official competition submission or rerun and no submission quota use. Push evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-push-20261024T203313Z.json`. Do not retry the push; follow this run to its terminal result.


## 2026-10-24 20:38 UTC: pilot still running

The configured `.venv` Kaggle CLI reports the latest run for the single pushed version 18 as `KernelWorkerStatus.RUNNING` (exit code 0). No repeat push, official submission, or competition rerun. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-running-20261024T203829Z.json`.


## 2026-10-24 20:41 UTC: startup progress only

Live read-only Kaggle logs for v18 show the embedded patch being checked and model weight precaching active through the 420-second marker. At 20:40:09 UTC the latest-status API still reported `KernelWorkerStatus.RUNNING`. The benchmark had not started and no score was available at this observation. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-startup-20261024T204103Z.json`.


## 2026-10-24 20:52 UTC: extended startup watch

The single v18 run remains `KernelWorkerStatus.RUNNING` (latest status at 20:50:11 UTC). Live logs have advanced through elapsed markers 990, 1020, 1050, and 1080 seconds without an inference-ready or benchmark-start event. For comparison, the completed v17 run began its benchmark 578.12 seconds after kernel start. The declared 1,800-second readiness deadline has not expired; no retry or duplicate push. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-startup-watch-20261024T205222Z.json`.

## 2026-10-24 20:53 UTC: version 18 still running

Read-only status check still reports Kaggle kernel version 18 as RUNNING. No repeat push, official rerun, or competition submission was made. Status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-status-20261024T205303Z.json`.
## 2026-10-24 20:58 UTC: version 18 still running

Pinned external ARC3 operation environment now reports Kaggle CLI 2.2.5 and kagglesdk 0.1.38. The read-only status remains RUNNING; no repeat push or official competition submission was made. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-status-20261024T205821Z.json`.
## 2026-10-24 21:03 UTC: version 18 still running

The lock-synced ARC3 operation environment reports kernel version 18 RUNNING. No repeat push, official rerun, or competition submission was made. Status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-status-20261024T210334Z.json`.

## 2026-10-24 21:05 UTC: version 18 terminal startup failure (no score)

Kaggle latest status reached `KernelWorkerStatus.ERROR` at 21:04:09 UTC. Captured output contains only `arc3-model-guided-c2-025.log` (27,598 bytes, SHA-256 `29100d175ae614e698878958c56cfe48400d46a9e66c9b95815726de3e1e30a1`) and `serve.log` (29,048 bytes, SHA-256 `45d30c3681a6454a27df3c146319a63ec0f6bf82f77c03c5a5131c0bf1b17222`); no `benchmark.json` or `summary.txt` was produced. The kernel log records weight precaching of 185.40 GB in 1718.07 seconds, then `DEADLINE after 1800s from server launch; server inference readiness was not confirmed`, followed by `RuntimeError: SGLang inference readiness was not confirmed; offline benchmark not started`. Therefore this is an infrastructure startup failure; C2-051 has no game score and neither pass nor fail evidence. Terminal evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-terminal-startup-error-20261024T210540Z.json`.

One recovery attempt is planned with the same C2-051 gameplay treatment and the same three-game conditions, changing only startup/readiness timeouts from 1800 to 2400 seconds. The prior version is terminal, so no runs overlap. No official submission or competition rerun.


## 2026-10-24 21:06 UTC: attempt 2 source and gate review

The first attempt is confirmed terminal ERROR and produced no benchmark. A recovery bundle is prepared under `出力/ARC3-RUN-003-local/C2-051-retry/`. Parsed notebook comparison confirms only runner timeout values changed: cell 5 startup deadline 1800→2400 seconds and cell 13 SGLang watchdog 1800→2400 seconds. The two-line gameplay treatment, model, source patch, metadata, seed 0, three-game list, action/time budgets, concurrency=1, and private/GPU/Internet-off settings are unchanged. Candidate SHA-256 `021bc357fb2ad7205165fe740894dd27380360faffb04b56780c769369def55d`; metadata SHA-256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.

The `.venv` Kaggle latest-run status was rechecked at 21:06:58 UTC and remains `KernelWorkerStatus.ERROR`, confirming no active run before one recovery push. Retry pre-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-attempt2-pre-run-review-20261024T210658Z.json`. This retry tests the same score hypothesis; it is not another candidate treatment. No official submission or competition rerun.


## 2026-10-24 21:07 UTC: attempt 2 launched

One recovery push returned exit code 0 and explicitly reported **Kernel version 19 successfully pushed**. The immediate read-only latest-run status at 21:07:23 UTC was `KernelWorkerStatus.RUNNING`. This is attempt 2 of the same C2-051 private offline three-game pilot, with only startup/watchdog timeout extended to 2400 seconds. Do not push again; follow version 19 to terminal. No official submission, competition rerun, or submission quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-push-20261024T210723Z.json`.

## 2026-10-24 21:08 UTC: version 18 still running

The single version 18 remains RUNNING in the lock-synced ARC3 operation environment. No repeat push, official rerun, or competition submission was made. Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v18-status-20261024T210843Z.json.
## 2026-10-24 21:12 UTC: version 19 status and attribution correction

The lock-synced Kaggle CLI read-only status query at 21:12:40 UTC reports the latest kernel run as `KernelWorkerStatus.RUNNING`; the latest pushed version is 19. Version 18 had reached terminal startup `ERROR` at 21:04:09 UTC, with no benchmark score. The 21:08:43 record labeled “version 18 still running” was a bookkeeping attribution error: `kaggle kernels status` reports only the latest run, and version 19 had already been pushed at 21:07:23 UTC. Its raw evidence is preserved; the correction is append-only in the work ledger. Status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-status-20261024T211240Z.json`. Next check: 21:17:40 UTC. Do not push another version or submit officially while v19 is running.

## 2026-10-24 21:14 UTC: version 19 startup progress

The single version 19 retry remains `KernelWorkerStatus.RUNNING`; live logs have advanced through the 330-second startup marker while model precaching continues. The extended 2400-second startup/watchdog guard is active; the offline benchmark has not started and no score is available yet. No duplicate push or official rerun. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-startup-20261024T211409Z.json`.

## 2026-10-24 21:29 UTC: version 19 startup log follow-up

The exact-version-19 read-only live log advanced through the 1260-second marker. Weight precaching remains active; inference readiness and benchmark start are not confirmed. The 2400-second startup/watchdog limit is unchanged. The local log-follow command was stopped after capturing the sample; the remote kernel remains running. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-startup-watch-20261024T212935Z.json`. Next check: 21:33:40 UTC.
## 2026-10-24 21:34 UTC: version 19 startup still precaching

The exact-version-19 status remained `KernelWorkerStatus.RUNNING` at 21:33:40 UTC. Read-only live logs advanced through the 1530-second marker; weight precaching continues, with inference readiness and benchmark start still unconfirmed. The retry's 2400-second timeout remains active. No score is available and no additional push or official rerun was performed. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-status-20261024T213340Z.json` and `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-startup-watch-20261024T213408Z.json`. Next check: 21:38:40 UTC.
## 2026-10-24 21:39 UTC: version 19 passed prior startup duration, still precaching

The exact-version-19 read-only status remained RUNNING at 21:38:40 UTC. Live logs advanced through 1830 seconds and still show weight precaching; inference readiness and benchmark start remain unconfirmed. This is past v18's 1800-second readiness window, but remains within v19's declared 2400-second limit. No score is available. No further push or official rerun was performed. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-status-20261024T213840Z.json` and `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-startup-watch-20261024T213911Z.json`. Next check: 21:43:40 UTC.

## 2026-10-24 21:47 UTC: version 19 model precache complete

At 21:47:28 UTC, the latest status was still `KernelWorkerStatus.RUNNING`. Live logs report 62 model files / 185.40 GB precached in 2214.69 seconds; the latest elapsed marker was 2310 seconds. A server-ready marker and benchmark start were not yet observed, with the configured 2400-second readiness deadline approaching. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-precache-complete-20261024T214728Z.json`.

## 2026-10-24 21:49 UTC: version 19 terminal startup failure (no score)

At 21:49:16 UTC, read-only Kaggle status reported `KernelWorkerStatus.ERROR` for exact version 19. Its logs reached 2473 seconds and report `RuntimeError: SGLang inference readiness was not confirmed; offline benchmark not started` after 62 model files / 185.40 GB were precached. No readiness marker, benchmark, or game score was produced. This is an infrastructure startup failure, not a gameplay-hypothesis score. The single planned recovery attempt is exhausted; no further push or official rerun is authorized by this gate. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-terminal-startup-error-20261024T214916Z.json` (SHA-256 `f8493918692b079ae08f9a8b573580a15ffb23ab446b6aac41ab811df29d7eca`).

The exact-version output query at 21:53:25 UTC returned the kernel log only (28,887 bytes, SHA-256 `4b017beed41114d03e90e68c2833a3c9dcec396100be77acf8c5237700efd1d1`). No `benchmark.json` or `summary.txt` score artifacts were returned. Output-check evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-output-check-20261024T215325Z.json` (SHA-256 `554240866bad9eb1fbf500f6fa4ba2f6d1dab616a8be01c87ee152c4bb766b0d`).


## 2026-10-24 21:50 UTC: version 19 terminal startup failure (no score)

The configured `.venv` status is `KernelWorkerStatus.ERROR` (observed 21:49:26 UTC). Retrieved output contains only `arc3-model-guided-c2-025.log` (28,887 bytes, SHA-256 `4b017beed41114d03e90e68c2833a3c9dcec396100be77acf8c5237700efd1d1`) and `serve.log` (29,752 bytes, SHA-256 `ba1b8d81fd684806871df8c7c907cb382c2381668f61839b05bb820b2c90f808`); there is no benchmark summary or score. The model files finished precaching in 2214.69 seconds, but at the 2400-second server-readiness deadline the SGLang log remained in CUDA graph capture at `0/7 [02:05]`; Kaggle recorded `SGLang inference readiness was not confirmed; offline benchmark not started`. This is another runner startup failure; the selective-memory treatment remains unevaluated. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v19-terminal-startup-error-20261024T215027Z.json`.

The recovered v17 log shows the same graph-capture stage at `0/7 [02:03]`, TileLang compilation at 02:06, and server readiness at 19:17:53. One final same-treatment retry is prepared with both startup/watchdog timeouts at 2700 seconds, giving the capture stage the extra five minutes it did not get under 2400 seconds. No official submission or competition rerun.


## 2026-10-24 21:51 UTC: attempt 3 source and gate review

Attempt 2 is confirmed `KernelWorkerStatus.ERROR` with no benchmark output. Attempt 3 is prepared at `出力/ARC3-RUN-003-local/C2-051-retry3/`; relative to attempt 2, only cell 5 `SERVER_STARTUP_TIMEOUT` and cell 13 SGLang watchdog change from 2400 to 2700 seconds. The selective memory treatment and all game/model/seed/action/time/concurrency/privacy controls remain unchanged. The latest status was rechecked as terminal ERROR at 21:51:12 UTC, with no active run. Pre-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-attempt3-pre-run-review-20261024T215112Z.json`. This bounded five-minute increase is based on v17 completing the same graph-capture stage after the v19 2400-second cutoff. One push only; no official submission or competition rerun.


## 2026-10-24 21:51 UTC: attempt 3 launched

A single push returned exit code 0 and explicitly reported **Kernel version 20 successfully pushed**. The immediate read-only latest status at 21:51:39 UTC is `KernelWorkerStatus.RUNNING`. Attempt 3 retains the same C2-051 gameplay change and all evaluation controls; only startup/watchdog timeouts are 2700 seconds. Do not push again; track v20 to terminal. No official submission, Competition Rerun, or submission quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-push-20261024T215139Z.json`.


## 2026-10-24 22:08 UTC: version 20 startup progress

The single v20 attempt remains `KernelWorkerStatus.RUNNING` (CLI exit code 0). Live logs have reached the 930-second marker; model precaching remains active, and the benchmark has not started. The 2700-second startup/watchdog settings are in effect. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-startup-20261024T220857Z.json`.


## 2026-10-24 22:28 UTC: version 20 extended startup watch

At 22:28 UTC the latest status remains `KernelWorkerStatus.RUNNING`; live logs have reached 2100 seconds, with model precaching still active and no benchmark start. The 2700-second startup/watchdog deadline remains in force. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-startup-20261024T222800Z.json`.


## 2026-10-24 22:34 UTC: version 20 model precache complete

The latest status remains `KernelWorkerStatus.RUNNING`. The model preload reports 62 files / 185.40 GB complete in 2434.59 seconds; the live server timer reached 2490 seconds. The 2700-second readiness deadline leaves roughly 210 seconds; server readiness and benchmark start have not yet appeared. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-precache-complete-20261024T223435Z.json`.


## 2026-10-24 22:37 UTC: version 20 benchmark started

Live logs show `Starting benchmark...` immediately after the 2670-second marker. At 22:37:39 UTC the latest status remains `KernelWorkerStatus.RUNNING`. The server became ready within the 2700-second startup allowance and entered the planned private offline run: 3 public games, seed 0, 1 pass, concurrency 1, 160 actions and 1200 seconds per game. No score is available yet. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-benchmark-start-20261024T223739Z.json`.


## 2026-10-24 22:48 UTC: nonterminal interim diagnostic

The live kernel log printed `mean score: 0.00`, while the latest status remains `KernelWorkerStatus.RUNNING`. No per-game rows or terminal benchmark artifact are available; this transient diagnostic is not used for candidate acceptance or rejection. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-interim-20261024T224832Z.json`.


## 2026-10-24 22:58 UTC: nonterminal interim diagnostic

The live log now prints `mean score: 0.65`; latest status remains `KernelWorkerStatus.RUNNING`, and no per-game rows or terminal output are available. This interim value does not decide the pilot. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-interim-20261024T225820Z.json`.


## 2026-10-24 23:08 UTC: nonterminal interim diagnostic

The live log printed `mean score: 1.84`; latest status remains `KernelWorkerStatus.RUNNING`, with no per-game rows or terminal scorecard. This interim value does not decide the pilot. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-interim-20261024T230806Z.json`.


## 2026-10-24 23:28 UTC: nonterminal interim diagnostic

The live log printed `mean score: 6.60`; latest status remains `KernelWorkerStatus.RUNNING`, with no per-game rows or terminal scorecard. No candidate decision is made from this intermediate output. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-interim-20261024T232839Z.json`.


## 2026-10-24 23:31 UTC: nonterminal interim diagnostic

The live log printed `mean score: 11.36`; latest status remains `KernelWorkerStatus.RUNNING`. Per-game rows and terminal scorecard are not yet available; this update does not decide the candidate. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-interim-20261024T233144Z.json`.


## 2026-10-24 23:32 UTC: version 20 terminal scorecard and rejection

Kaggle version 20 is `KernelWorkerStatus.COMPLETE`. The benchmark was rescored with the official local `EnvironmentScoreCalculator`; recomputed scores match all three saved `final_score` values. C2-051 mean is **11.360817966185**, versus C2-046 slim **19.309155943771** (paired mean delta **-7.948337977587**) and C2-048 **16.888440683895** (delta **-5.527622717710**). All three matched environments regressed versus C2-046 slim. Initial visible board hashes match 3/3. Per-game values and artifact hashes are in `運用/証拠/ARC26-UNIFIED/ARC3-C2-051-v20-terminal-scorecard-20261024T234025Z.json`.

**Decision: reject C2-051.** This treatment does not improve the current matched pilot; retain C2-046 slim as the local reference and continue with a separate hypothesis. The private run did not submit to the competition, invoke a competition rerun, or consume submission quota.
