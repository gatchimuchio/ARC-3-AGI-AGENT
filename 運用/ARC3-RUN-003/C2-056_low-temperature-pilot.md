# C2-056: low-temperature private pilot

## Hypothesis

C2-046 slim uses sampling temperature 0.7. Reducing it to 0.2 may make action selection more consistent across repeated decisions on the same game state. It may also suppress useful exploration. Prior C2-034 used temperature 0.6 but mixed that setting with a memory-mode comparison and failed before benchmark, so it does not establish a temperature effect. C2-056 isolates temperature from the C2-046 slim control.

## One-factor change

Only cell 5 changes `LOCAL_ANALYZER_TEMPERATURE` from `0.7` to `0.2`. Notebook cell sources differ only in cell 5; all 25 cells remain present. Kernel metadata is byte-identical to C2-046 and remains private, GPU-enabled, and Internet-disabled. Candidate notebook SHA-256: `e240d98eac956330e4f1daae8ec73ac05ba611934ce3af4c1c7f5e2f19a6c447`; metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.

## Acceptance and sequence

This candidate is prepared and unpushed. Queue it only after C2-054 version 23 has a terminal scorecard and C2-055 has completed or is explicitly rejected. Use the same three public starting games, seed, and limits; recompute with the official local `EnvironmentScoreCalculator`. Accept the pilot only if mean is strictly above 19.309155943771326 and paired mean delta versus C2-046 is positive. Compare matched starts, per-game score, levels, wins, actions, runtime, generated tokens, and terminal states. A passing pilot requires matched public-25 validation before promotion, with further score optimization continuing.

## Pre-run evidence

Source comparison confirms only cell 5 differs and metadata bytes match. This candidate has not been pushed, run, or submitted. No official competition quota has been used. Manifest: `出力/ARC3-RUN-003-local/C2-056-low-temperature/attempt-manifest.json`.

## Terminal result — version 25

Version 25 reached KernelWorkerStatus.COMPLETE; exact versioned output was recovered. Official EnvironmentScoreCalculator recomputation confirms candidate mean 13.949735 vs C2-046 slim 19.309156, paired mean delta −5.359420, with 1 improved / 1 unchanged / 1 regressed. Paired initial state checks passed 3/3. The candidate is **rejected**. No official submission or quota use occurred. Full scorecard: $scoreRel (SHA-256 $scoreHash).