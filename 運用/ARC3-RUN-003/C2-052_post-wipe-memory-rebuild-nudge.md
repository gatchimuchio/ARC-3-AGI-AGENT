# C2-052: post-wipe memory rebuild nudge

## 目的と仮説

C2-046 slim is the current strongest matched 3-game local reference (19.309155943771). It clears its carried slim sections (World model and Plan) on level transition by default and leaves the rebuild nudge off. C2-048 and C2-051 carried selected memory across transitions and both failed to beat C2-046 slim; C2-051's selective-plan treatment scored 11.360817966185 (delta -7.948337977587). C2-052 keeps the C2-046 wipe behavior for the slim sections and enables only the existing generic post-wipe rebuild nudge. The model must reconstruct fresh World model and Plan from the new visible level; no prior-level Plan is carried.

## 比較条件

- Control: C2-046 slim, 3 public games, seed 0, 1 pass.
- Treatment: same source/behavior except `ARC3_WM_REBUILD_NUDGE=True`; `ARC3_WM_WIPE_ON_LEVEL` remains default 1 and revise nudge remains default false.
- Fixed: model, loader, 3-game set, seed, action/time limits, concurrency, private GPU, Internet disabled. Startup/readiness timeout is raised to 3300 seconds on both runner and SGLang watchdog after C2-051 v20 became ready at 2670 seconds; this is infrastructure only.
- No official competition submission/rerun and no submission quota use.

## 採否

Before score acceptance, inspect request/memory traces to confirm the post-wipe `IMPORTANT: your memory sections were reset` nudge is injected on level transitions and fresh slim World model/Plan updates are carried into subsequent prompts; record update/rejection counts. Rescore with the official local `EnvironmentScoreCalculator`; verify the 3 public starting boards match C2-046 slim. Accept as a pilot candidate only if the mean is strictly greater than 19.309155943771 and paired mean delta is positive. If it passes, proceed to matched public-25 evaluation before promotion. A public-25-supported best version may proceed to one official Phase-B run only after fresh rule, eligibility, and quota checks; compare its official score with 23.86, then continue optimizing. Neither local gate is an endpoint.

## 初期証拠

- Source: `出力/ARC3-RUN-003-local/C2-052-post-wipe-rebuild-nudge/source/rebuild-nudge/submission.ipynb`; metadata is byte-identical to C2-046 slim. Changed cells: [5, 13]. Notebook SHA-256: `77f99e38bd8f674d05027d814348db6934f63ab9a0917fd702a406155128842b`.
- Candidate manifest: `出力/ARC3-RUN-003-local/C2-052-post-wipe-rebuild-nudge/attempt-manifest.json`.
- Pre-push review: passed; pre-run evidence and v21 push evidence are recorded below.


## 2026-10-24 23:40 UTC: pre-run gate passed

The base source hash matches C2-046 slim and the change review confirms only the rebuild-nudge setting plus startup/watchdog deadlines. Kernel metadata remains private, GPU-enabled, Internet-disabled; latest prior kernel status was COMPLETE. Ready for one private offline three-game pilot. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-052-pre-run-review-20261024T234025Z.json`.


## 2026-10-24 23:41 UTC: private pilot pushed

One push returned exit code 0 and reported **Kernel version 21 successfully pushed**. The read-only latest status at 23:41:12 UTC is `KernelWorkerStatus.RUNNING`. This is the planned private/offline three-public-game pilot; no official submission, competition rerun, or quota use. Do not push a duplicate. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-052-v21-push-20261024T234112Z.json`.


## 2026-10-25 00:37 UTC: version 21 remains nonterminal

At 00:37:07 UTC, exact-version Kaggle status remained `KernelWorkerStatus.RUNNING`. `kernels logs` and the exact-version output query returned no logs or files. Elapsed time since the 23:41:12 UTC push is about 56 minutes, but the SGLang readiness timer start cannot be confirmed from published logs. No game score is available; this is not classified as a startup failure. Continue read-only tracking of version 21; do not duplicate the push. No official submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-052-v21-status-20261025T003707Z.json`.


## 2026-10-25 01:25 UTC: version 21 terminal scorecard and rejection

Kaggle version 21 is `KernelWorkerStatus.COMPLETE`. The offline benchmark ran 2026-10-25 00:24:07–01:16:29 UTC (52m22s), with 3 public games, 480 actions, 4 completed levels, 0 wins, and 453,536 generated tokens. Recomputed with the official local `EnvironmentScoreCalculator`; saved scores match 3/3, control scores match 3/3, public metadata matches 3/3, and initial boards match 3/3. Candidate mean **6.334139442173** (median 3.571428571429) vs C2-046 slim **19.309155943771**; paired delta **-12.975016501599**, with 0 improved / 0 unchanged / 3 regressed.

Trace audit found 4 public level transitions. The rebuild nudge appeared in 56 transcript user-prompt blocks; each included both slim memory sections, and 52 were followed by an assistant World model or Plan update. The audited transcript contains 9 World model and 100 Plan update lines; exact update snippets appeared in later prompts 7 and 70 times, respectively. No explicit memory-update rejection markers were found. Rebuild behavior was inconsistent across the three runs, and the candidate failed the score gate. **Decision: reject C2-052; retain C2-046 slim as pilot reference and design a separate one-factor hypothesis.** No official competition submission/rerun or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-052-v21-terminal-scorecard-20261025T012518Z.json`.
