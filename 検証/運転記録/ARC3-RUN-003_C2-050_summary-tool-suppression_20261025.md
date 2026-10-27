# ARC3-RUN-003 C2-050: Rolling Summary Without Tools

## 2026-10-24 preparation record

- Candidate copied from C2-047 version 14 and prepared locally only; not pushed or run.
- Log evidence motivating this candidate: C2-047 live benchmark was still `in progress` with interim mean 1.19, and rolling-summary logs showed attempted `python` tool calls, including a zero-character response skipped and a 7,980-character summary retained while the tool call was discarded.
- Static source review located the cause: `_maybe_append_rolling_summary` passes `tools=tools` although it is called outside the turn loop. The prepared change passes `tools=None` only for the summary request. The unchanged `_request_tool_choice(None)` returns `None` and `_chat_completion` forwards `tools=None` to `build_chat_payload`.
- Notebook SHA-256: `c5ea749ff7048c448c8a20d8815137a734d6a8e29dffc8dc95677d3c55f3db86`; metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.
- Next action: wait for C2-047 terminal status, recover its outputs, evaluate its final scorecard, then choose between C2-048 cross-level retention, C2-049 summary turn-context, and this C2-050 fix. No official submission or rerun.

## 2026-10-24 17:15:53 UTC: static candidate audit

The C2-050 notebook JSON parses; byte comparison against the C2-047 candidate confirms exactly one source change: the summary request now passes `tools=None`. The candidate notebook and metadata hashes match the new manifest. The C2-047 Kaggle run is still `RUNNING`, so C2-050 remains unpushed and unrun.


## 2026-10-24 17:44 UTC: static candidate integrity recheck

C2-050 notebook and metadata hashes match its manifest. Parsed notebook comparison with C2-047 confirms exactly one source change in cell 3: `_maybe_append_rolling_summary` now passes `tools=None` instead of `tools=tools`. Candidate remains local-only pending the C2-048 version-15 terminal result; it has not been pushed or run.

## 2026-10-24 19:23 UTC: version 16 terminal error, version 17 still running

A fresh exact-version status query reports version 16 as ERROR and version 17 as RUNNING. Version 16 output was recovered into a separate directory. Its kernel log records the 1,800-second server-readiness deadline and says the offline benchmark did not start; repeated sitecustomize warnings report missing wrapt, but the logs do not establish that as the cause. The candidate change was not evaluated in version 16.

The concurrency=1 gate was already breached when both versions were RUNNING at 19:14 UTC. Both versions remain diagnostic only and are ineligible for candidate adoption. Since version 17 is now the only RUNNING version, it is left to reach terminal status. No new push, private run, official rerun, or competition submission is started.

Evidence: ARC3-C2-050-v16-terminal-error-20261024T192335Z.json; recovered logs are listed there by path and SHA-256. Next: track version 17 to terminal and retrieve its outputs separately.

## 2026-10-24 20:28 UTC: version 17 terminal paired scorecard

Kaggle's latest-run status endpoint reported `KernelWorkerStatus.COMPLETE` at 20:28:55 UTC. Version 17 is the latest pushed version for this slug. Its recovered output summary reports a private offline run from 19:17:56 to 20:18:00 UTC: 3 games, 1 pass, 0 wins, 243 actions, 453,182 generated tokens, and summary mean 4.91. Recalculation of all three runs with the official local `EnvironmentScoreCalculator` matched each saved `final_score` exactly; mean 4.909114956.

Paired on the same three public starts, C2-047 scored 5.952380952, so C2-050 v17 delta is -1.043265996. C2-046 slim scored 19.309155944, delta -14.400040988. This output is diagnostic only: versions 16 and 17 were concurrently RUNNING at 19:14:14 UTC, breaching the predeclared concurrency=1 gate. The evidence for v16 records an inference-readiness deadline failure and no benchmark. C2-050 is rejected and not adopted.

The kernel log contains one rolling-summary request timeout (read timeout 12.7518s); it contains no successful summary/replacement record. The request trace has 350 normal model request records, but does not include an identifiable rolling-summary request, so the intended `tools=None` effect is unverified. C2-050 does not support summary compaction as a score optimization.

Recovered output: `出力/ARC3-RUN-003-local/C2-050/kaggle-output/v17/`. Key SHA-256: `benchmark.json` 913e4bfa2b56c846a75d16bdacf05fd16797df89a75c78619fe1102d9d404e96; `summary.txt` 3f1c67d4cc64241d46b1aaa22d9b4734a1d01f8c84b24b899588773cf9c9d04e; `requests.jsonl` 9560923f9b97acb65202c479fc07a40904a1a159c7002499eab9458838ca460c; `arc3-model-guided-c2-025.log` 3f204177b6e3f0e25f8f22f1eac0aaedfe8407b6307ea3fe3e0437f590d8fb8e.

No official competition rerun, submission, or quota use. Next optimization candidate is a selective level-transition memory treatment: retain durable `World model`, clear the level-specific `Plan`, and compare against C2-046 slim and C2-048 on the same public starts. A single private pilot may proceed only after the v16 readiness-failure artifact and v17 COMPLETE status are retained in the ledger; no official submission is authorized by this record.
