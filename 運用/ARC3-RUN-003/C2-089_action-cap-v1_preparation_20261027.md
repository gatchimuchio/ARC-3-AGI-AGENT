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
