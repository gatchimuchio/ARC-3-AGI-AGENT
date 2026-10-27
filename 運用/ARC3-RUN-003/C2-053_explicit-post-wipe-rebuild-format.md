# C2-053: explicit post-wipe rebuild format

## Evidence and hypothesis

C2-052 version 21 was rejected: the matched three-game mean was 6.334139442173 versus C2-046 slim 19.309155943771, paired delta -12.975016501599, with all three games regressing. Initial public boards and metadata matched 3/3, and saved scores matched the official local `EnvironmentScoreCalculator` 3/3.

The trace contained 4 level transitions and 56 user-prompt blocks carrying the post-wipe nudge. Across assistant responses there were 9 `World model:` update lines and 100 `Plan:` update lines; 52/56 nudged prompts were followed by a memory-section update. The current code clears the pending rebuild nudge only after an accepted World model update. This supports testing whether clearer output formatting helps the model restore the missing section.

## Single factor

Starting from C2-052 v21, keep the model, loader, slim memory sections, wipe behavior, nudge frequency, game set, seed, action/time limits, concurrency, GPU, and offline/private metadata fixed. Change only the nudge wording to ask for each fresh memory section on its own line with its exact label and a colon. This is a private three-game pilot. The candidate source changes only notebook cell 3; metadata is byte-identical. Notebook SHA-256: `292dbb5ede29e97c2111129e7eea49ea00ad84e148cc6a5cdbadb77daf0bd0a0`. Pre-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-053-pre-run-review-20261025T012828Z.json`.

## Acceptance

Recompute all game scores with the official local `EnvironmentScoreCalculator`, verify saved-score consistency and identical public starts, and inspect nudge/update/rejection traces. Accept only if mean is strictly above 19.309155943771 and paired mean delta is positive. If it passes, proceed to matched public-25 evaluation; a public-25-supported best version may proceed to at most one official Phase-B submission after fresh rules, eligibility, pending-status, and quota checks. Compare the numeric official score with 23.86, then continue optimizing. If it fails, reject it and choose another evidence-backed factor.

## Pre-run result

Static review passed: notebook schema valid, all 150 unified-diff hunk counts valid, only source cell 3 differs from C2-052, and metadata remains private/GPU-enabled/Internet-disabled. Previous exact kernel version 21 is COMPLETE. Ready for one private offline pilot; no official submission or quota use.

## Run update — 2026-10-25 01:31 UTC

Kaggle accepted one private, GPU-enabled, Internet-disabled pilot push as kernel version 22. Exact-version status was KernelWorkerStatus.RUNNING at 01:31:34 UTC. The preceding version 21 was COMPLETE, and a read-only pull of the latest kernel matched version 21 in every cell source and notebook metadata. Candidate notebook SHA-256: 292dbb5ede29e97c2111129e7eea49ea00ad84e148cc6a5cdbadb77daf0bd0a0. No official submission or competition quota was used. Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-053-v22-start-20261025T013134Z.json.

## Run update — 2026-10-25 01:47 UTC

Exact kernel version 22 remains KernelWorkerStatus.RUNNING at 01:47:19 UTC, approximately 16 minutes after push. No terminal scorecard is available, so no candidate decision has been made. No official submission or competition quota was used. Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-053-v22-status-20261025T014719Z.json.

## Run update — 2026-10-25 02:02 UTC

Exact kernel version 22 remains KernelWorkerStatus.RUNNING at 02:02:32 UTC, approximately 31 minutes after push. There is still no terminal scorecard. No candidate decision has been made; no official submission or competition quota was used. Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-053-v22-status-20261025T020232Z.json.

## Terminal scorecard — 2026-10-25 03:44 UTC

Kaggle version 22 is `KernelWorkerStatus.COMPLETE`. The benchmark ran 02:08:04–03:01:27 UTC (53m23s). Recomputed scores with `arc_agi.scorecard.EnvironmentScoreCalculator` match saved values 6/6. The three game IDs and initial board, ASCII board, level, title, run status, and score match C2-046 slim 3/3.

C2-053 mean is **10.247475**, median **2.170996**, versus C2-046 slim mean **19.309156**, paired delta **-9.061681**; 0 improved / 0 unchanged / 3 regressed. Per-game deltas: m0r0-492f87ba -19.047619, sk48-d8078629 -0.606782, tn36-ef4dde99 -7.530642. Candidate completed 4 levels versus control 7, used 384 actions versus 389, won 0 games, and all three ended `gave_up`. The candidate is +3.913335 mean versus C2-052 v21 on the same IDs (two improved, one regressed), but fails the C2-046 promotion gate. **Decision: reject for promotion; keep C2-046 as the local reference.**

Trace scan of the next assistant response after each rebuild nudge found parseable `World model` and `Plan` headings in 47/53 prompts, and exact bare headings in 3/53. This did not validate the wording change as a score improvement. No official submission or competition quota was used. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-053-v22-terminal-scorecard-20261025T034450Z.json`.
