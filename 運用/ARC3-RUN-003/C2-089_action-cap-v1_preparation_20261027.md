# C2-089 action tranche cap v1 — local preparation

Recorded 2026-10-27T13:58:06Z for ARC3 optimization under the current v6 instruction set.

## Hypothesis

C2-088 B-v2 contained long open-loop Python snippets. In the exact trace, 6 of 10 analysis steps had more than four MOUSE actions; 45 MOUSE actions were after the first four in those steps, and the largest group contained 37 actions (step 6). This is an action-sequence counterfactual, not a predicted score improvement. The cap tests whether returning to observation after at most four executed actions helps gameplay.

## Candidate

A generic runtime control limits each Python tool snippet to four actually executed game actions. It is applied across games without game or level ID branching. Oversized batches are truncated to the remaining allowance; subsequent calls in the same snippet return an explicit python_tool_action_limit reason. The cap counts executed actions, includes model-requested RESET actions, and defaults off when unset. HDS payload cell 6 is unchanged.

- Candidate kernel slug: tecchannn/arc3-v6-action-tranche-c2-089
- Local candidate Notebook SHA-256: 16cb7b2f291a0f964a7e4bec0df901594a07b09f473a8b6efba10344fa368df7
- Metadata SHA-256: 9aff09ff942d321b87a913015435080a653ba45d43bbf0883462cf0daf63e17d
- Incremental patch SHA-256: 810dd3e53cfd47d9a43b4dbcd9378de1ac49642c2611bed83aecf5269f4afff3
- Candidate manifest SHA-256: c631c66524e966afc04558a6ffefa1509ae4bba9cba7d093f16c8329afa5a3b0
- Changed Notebook cells: [3, 5]

## Local validation

The combined patch applies to the v5 raw source and produces the candidate postimage; Python compilation passed. Synthetic checks passed for four executed calls with remaining calls blocked, a six-action oversized batch truncated to four while retaining requested count, and the default-unset behavior executing all six unchanged.

## Current disposition and limits

PREPARED_LOCAL_NOT_UPLOADED. No Kaggle kernel was uploaded, no official submission/rerun was performed, and no quota was used. Score effect is NOT MEASURED. The candidate remains local until matched A-v3 completes: B-v3's offline scorecard is invalid for acceptance because it exceeded the runtime grace and the frozen comparator does not accept the new boundary-only outcome label. A-v3 was still RUNNING at 2026-10-27T13:51:54Z. The B-v3/A-v3 overlap also creates a runtime/GPU contention confound.

The full candidate Notebook embeds the private HDS source bundle and is excluded from the public repo. The reviewable incremental patch is at 検証/ARC3-RUN-003/C2-089-action-cap-v1.patch.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-action-cap-v1-prepared-20261027T135806Z.json (SHA-256 6f0108672bab603c441ec1b922213165c519dedf674646d6fbaf7ac16513ae4c).

## C2-089 exact Python-call boundary audit — 2026-10-27T14:26Z

This resolves the earlier limitation that the candidate rationale grouped actions by analysis step rather than verified Python tool-call boundaries. The exact B-v2 transcript and event trace confirm three completed Python calls that each executed more than four game actions: 37 actions (action numbers 20–56), 8 (63–70), and 8 (73–80). For these three calls, cap=4 would have allowed 12 of the 53 actions in their original snippets and blocked 41 from those snippets. The model could then re-observe and issue different calls; this counterfactual is not a score prediction. The full trace may contain other oversized calls; this audit reports only these three directly confirmed examples.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-python-call-boundary-relevance-20261027T142642Z.json (SHA-256 d562a2f4f2c405be09d82ada69d24fb72181662d0255bb85630bddc5d5e0ca73); source trace SHA-256 08a41222b770c9bd284527dc3ff95acbd448a8446a5567bd02bfe98f51c4f413.

The earlier preparation record's “45 actions after first four per analysis step” remains a per-step counterfactual, not a call-level measurement; do not use it as the exact expected treatment count. The direct trace now supports testing the generic action cap. However, C2-089 inherits B-v3's unsupported boundary-only outcome label, whose frozen comparator currently marks integration invalid. Before using a C2-089 run for accepted score comparison, repair and re-evaluate that compatibility and establish a sequential valid parent baseline. A private normal kernel run may be used for diagnosis only; no official Competition Rerun/quota, and no gain claim until the gates pass.

## Parent-v5 reproduction gate — 2026-10-27T16:09:10Z

B-v3 version 4 now has an exact COMPLETE output scored by the extended-outcome adapter with gameplay and integration validity true. The same-package version 5 reproduction is running. C2-089 remains unpushed until version 5 is retrieved, scored with that adapter, and compared to version 4 on the same public games and limits. The candidate package hashes still match its prepared manifest; the action-cap score effect remains unmeasured. Today's official quota is treated as exhausted based on the current CLI history and Kaggle Staff's one-per-day statement.

Gate evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-action-cap-v1-parent-v5-preflight-20261027T160910Z.json.

## Parent v4/v5 comparison — 2026-10-27T16:26:19Z

The parent comparison is complete but not reproducible: identical initial public frames and first prompts produced different first actions in two games. The public offline mean RHAE moved from 2.206345 to 5.952381, with the same 3/21 levels and 240 actions but a substantially different per-game distribution. A private C2-089 run can now serve only as a diagnostic against this noisy reference. Do not label one run an improvement; require a repeated candidate result and interpret it against both parent observations. No Competition Rerun or quota was used.

Comparison evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-088-B-v3-sequential-v4-v5-reproducibility-audit-20261027T162619Z.json.

## Private diagnostic launch preflight — 2026-10-27T16:31:39Z

The exact C2-089 candidate hashes still match its prepared manifest. Kaggle status checks found the five known ARC3 v6 kernels in terminal COMPLETE state, with no running ARC3 v6 kernel observed. The parent v5 exact output is complete and scored, but its same-package result differs materially from v4; baseline reproducibility remains NOT_ESTABLISHED. A single private C2-089 run is therefore authorized only as a diagnostic of the generic four-actions-per-Python-call cap. Its output must be compared per game against both parent runs, and no gain may be claimed without a repeated candidate result. No Competition Rerun or official quota is used.

Preflight evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-action-cap-v1-private-diagnostic-preflight-20261027T163139Z.json.

## Capacity-status correction — 2026-10-27T16:36:29Z

Before launching C2-089, the read-only status refresh showed that `tecchannn/arc3-v6-learning-online-c2-087-r3` is `KernelWorkerStatus.ERROR`, not COMPLETE as stated in the preflight. This is terminal and not running; the remaining four checked ARC3 v6 kernels are COMPLETE. No candidate launch had occurred when this correction was recorded. The preflight is retained unchanged and this correction supersedes only that status field.

Correction evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-action-cap-v1-capacity-status-correction-20261027T163629Z.json.

## Private kernel push rejected by weekly GPU quota — 2026-10-27T16:38:26Z

The private C2-089 push was rejected with the exact CLI output `Kernel push error: Maximum weekly GPU quota of 30.00 hours reached.` The CLI created no kernel version, a subsequent read-only kernel list still did not contain the candidate slug, and no retry was performed. The reset time was not provided, so the candidate remains NOT_STARTED and its score effect NOT_MEASURED. This did not attempt a Competition Rerun or use official submission quota.

The read-only official history still shows submission 57688735 COMPLETE with public score 28.07 and no private score; it was submitted 2026-10-27T04:20:12.220000 UTC. The current UTC date already has one submission in history, so no official submission was attempted.

Rejection evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-action-cap-v1-kernel-push-rejection-20261027T163826Z.json.

## Exact v5 parent action-batch audit — 2026-10-27T17:16:56Z

The first 80 transitions per game were compared on the same three public starting boards. Grouping action events by analysis_step, C2-088 v5 has 55 action-bearing steps and 92 actions beyond the first four per step; C2-046 v13 has 80 steps and 66 such actions. Visible-board no-change counts are 13 for v5 versus 5 for v13. At action 80, v5 completed 3 levels and v13 completed 4.

| Game | v13 steps / over-cap actions / no-change | v5 steps / over-cap actions / no-change |
|---|---:|---:|
| sk48-d8078629 | 35 / 8 / 3 | 15 / 38 / 10 |
| tn36-ef4dde99 | 30 / 12 / 0 | 26 / 11 / 0 |
| m0r0-492f87ba | 15 / 46 / 2 | 14 / 43 / 3 |

The excess-action count is not a score prediction: cap4 would return to observation sooner and change later model outputs. v13 also contains 66 over-cap actions, so these data justify only a bounded diagnostic, not promotion. Keep the prepared C2-089 cap4 candidate blocked until Kaggle weekly GPU quota permits a private run; do not retry the rejected push before then. Compare per game against both v4 and v5, and repeat before claiming a gain.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-088-v5-analysis-batch-cap4-parent-audit-20261027T171656Z.json (SHA-256 b21635862a94a489146330b0bb8f694041372c85d3991859a0f5fc14c4c9ab70).

## Tail-action outcome check — 2026-10-27T17:20:59Z

Within action-batches longer than four, neither v5 nor v13 had a visible no-change action in the first four actions. In the remaining tails, v5 had 10 visible no-change actions and one level transition; v13 had one no-change action and two level transitions. This strengthens the rationale to test earlier observation on v5, but also shows cap4 may interrupt successful action sequences on v13. It remains an experiment, not a score claim.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-088-v5-cap4-tail-outcome-audit-20261027T172059Z.json (SHA-256 313d1a437edd7ad85072cf3b124aade449c7a15dae5e8275e7b3c4208123570a).

## Cap-threshold sensitivity on the matched trace prefix — 2026-10-27T17:28:01Z

| Reference | Cap | Long batches | Actions returned for later observation | Visible no-change actions in tails | Level transitions in tails |
|---|---:|---:|---:|---:|---:|
| v13 | 4 | 10 | 66 | 1 | 2 |
| v13 | 8 | 6 | 33 | 1 | 2 |
| v13 | 12 | 2 | 18 | 1 | 1 |
| v5 | 4 | 17 | 92 | 10 | 1 |
| v5 | 8 | 7 | 49 | 8 | 1 |
| v5 | 12 | 6 | 24 | 7 | 0 |

v5 cap12 retains every observed level transition within the first 80 actions while still returning 24 actions from long batches to later observation and covering 7 of 13 visible no-change actions. Cap4 returns 92 actions and crosses one observed level transition; cap8 returns 49 and also crosses one. The C2-046 v13 reference shows a different tradeoff, so this is not a score forecast.

Decision: prefer cap12 for the first private diagnostic if the cap can be isolated to one setting; keep cap4 as the prepared alternative. No private kernel push is allowed until weekly GPU quota is available, and no score improvement is claimed.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-088-v5-cap-threshold-sensitivity-20261027T172801Z.json (SHA-256 763ee44f7ce6dd5a71cf8a89a3ad66f6f88ae5faf1d6e84e48a2d22ed93bc6e0).

## Cap12 local candidate prepared — 2026-10-27T17:31:04Z

The prior cap4 Notebook was copied to 出力/ARC3-RUN-003-local/C2-089/action-cap-v2/submission.ipynb; only cell 5’s ARC3_MAX_ACTIONS_PER_PYTHON_CALL value changed from 4 to 12. Candidate SHA-256: 86bd236528fa0172ef33b14f73156fbd5821e0420fac8c629858b6adebd870a0. The generic patch and HDS payload are unchanged. The notebook JSON parses and the config diff contains exactly one changed value.

This candidate has not received synthetic runtime validation, has no Kaggle kernel version, has no score, and used no private or official quota. It is prepared for one private diagnostic after quota recovery and after the C2-088 v5 official result is terminal. No gain is claimed.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-089-cap12-candidate-prepared-20261027T173104Z.json (SHA-256 495d07767adce077b51142f52d3733145fceb41fb5fcde6a70cf0ee5a5c5d041).
