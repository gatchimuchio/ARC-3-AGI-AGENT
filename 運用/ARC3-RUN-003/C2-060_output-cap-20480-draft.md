# C2-060 draft — output reserve 20,480 with 118,272 input allowance

Status: **C2-060 private version 29 is COMPLETE and rejected by the predeclared paired-score gate; it is not an official competition submission.** This candidate tests whether two 16,384-token `finish_reason=length` responses seen in the partial C2-058 transcript matter for performance. It raises `LOCAL_ANALYZER_MAX_OUTPUT` from 16,384 to 20,480 and raises context from 135,168 to 139,264 so the effective input allowance remains 118,272. The context setting reaches the observed server limit, so startup feasibility must be rechecked before any future push.

Score v28 against the predeclared C2-046 gate first. Do not push C2-060 while v28 runs. Private, GPU-enabled, Internet-disabled; no official submission or quota use.

- Notebook: `出力/ARC3-RUN-003-local/C2-060-outputcap-20480-context139264/source/cap20k-context139264/submission.ipynb` (SHA256 `d610d79e44e0974cf18f3f29c9521c7407e4c6fa047d38456f1a9a67f8a65e26`).
- Metadata: `出力/ARC3-RUN-003-local/C2-060-outputcap-20480-context139264/source/cap20k-context139264/kernel-metadata.json` (SHA256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`).
- Preflight: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-preflight-draft-20261025T144038Z.json` (SHA256 `10b3060869951f6ed3503b9ad15fff362dbaa628808b84b2a06c1eb5bd7e99b2`).
- Delta: cell 5 only; context 135168→139264 and output reserve 16384→20480.
- Gate: mean > C2-046 `19.309155943771326` and positive paired mean delta on the same three starts.


## Matched request-budget evidence (2026-10-25T14:42:00Z)

The complete C2-046 control transcript has one output terminated at its 12,288-token cap. The partial C2-058 transcript has two outputs terminated at its 16,384-token cap. This supports an output-headroom experiment but does not predict a score gain. The different actions and trajectories prevent a direct behavioral comparison; output-cap hits are diagnostic only. C2-058 logs still do not establish that input pruning occurred.

- Cross-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-output-cap-evidence-comparison-20261025T144200Z.json` (SHA256 `02d3421e8fe649b277a0db2f9f43f1dd380b71f1014c5090ef79a2a2a6c3ee02`).


## Output-cap sequence interpretation (2026-10-25T14:55:24Z)

The action-79 / step-24 sequence shows two 16,384-token length terminations, followed by a tool-call response and then action 88. The cap therefore caused extra reasoning continuations in this trace but did not permanently block actions. C2-060 may reduce repeated calls; it is not assumed to improve score. Judge it with paired score, level progress, actions, and token totals.

- Sanitized sequence evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-cap-sequence-diagnostic-20261025T145524Z.json` (SHA256 `faeaebf859d0d8d1ba3776226a0f45c7e714c247c32d63fac82c1e33baa218d1`); prompt and board content were not saved.


## Next-pilot ordering update (2026-10-25T14:58:43Z)

A clean C2-061 `slim`→`off` memory ablation is now prepared from the C2-059 candidate with only cell 5 changed. The historical v5→C2-046 comparison shows this setting differed on the official 23.86 Notebook and current local baseline, but the versions have other differences; that is motivation only. After v28 terminates, prioritize deciding on C2-061 before C2-060 because it isolates one persistent-memory setting without moving the output/context budget to the server limit. C2-060 remains a later hypothesis, not a simultaneous push.

- C2-061 notebook: `出力/ARC3-RUN-003-local/C2-061-memory-sections-off/source/context135168-cap16k-memoryoff/submission.ipynb`.
- C2-061 report: `運用/ARC3-RUN-003/C2-061-memory-sections-off-draft.md`.
- C2-061 preflight: `運用/証拠/ARC26-UNIFIED/ARC3-C2-061-preflight-draft-20261025T145742Z.json`.


## Sequencing refinement after prior memory-mode evidence (2026-10-25T15:04:50Z)

C2-061 is held based on the prior matched `off`/`slim` ablation. C2-060 remains a conditional candidate after exact v28 completion. A read-only version-28 `.log` output query returned no files while the kernel remained RUNNING. Before any C2-060 push, require v28 prompt sizes to fit the 118,272-token input allowance, confirm server context/startup/readiness/resource support at 139,264 tokens, and verify repeated 16,384-token cap hits. A cap hypothesis alone is not a score claim. No push or quota use.

- Sequencing evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-sequencing-refinement-20261025T150450Z.json` (SHA256 `d47baceb84c0e5232ca06219bdfeaa64a2bc667daa0aa25eddcb2655fff6952b`).


## Updated readiness after C2-059 version 28 completed (2026-10-27T04:44:47.991112+00:00)

C2-059 was rejected by the fixed paired score gate. Its complete request log contains 393 JSON lines (0 invalid), 196 responses, and one `finish_reason=length` at action 43 / analysis step 22 with completion 16,384. Maximum observed prompt was 118276 tokens. The candidate server log reports `context_length=139264`. C2-060 tests the remaining output-cap hypothesis (16,384→20,480) at the same measured server context; it does not repeat the rejected context-only change. At the observed maximum prompt, prompt plus 20,480 output is 138756, 508 below that reported context. The observed prompt exceeds the proposed 118,272 effective input budget by 4 tokens, so this remains a one-pilot hypothesis with a narrow measured margin; changed trajectories may use longer prompts.

C2-060 local Notebook hash `d610d79e44e0974cf18f3f29c9521c7407e4c6fa047d38456f1a9a67f8a65e26` remains a one-cell source delta from C2-059 (`cell 5` only); its metadata hash is `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`. Its declared context is 139,264, output cap 20,480, and memory mode remains `slim`. Current read-only Kaggle statuses show C2-087 A and C2-088 version 1 both QUEUED; C2-087 B has no remote kernel (status query 404). No free batch session is confirmed, and an earlier B push was rejected at the two-session cap. Therefore C2-060 remains a local draft and is **not pushed**. Before its one private pilot, recheck the GPU session slot, exact source/config diff, prompt budget, and run budget.

Readiness evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-post-v28-readiness-20261027T044447Z.json`.


## 2026-10-27T10:42:23Z: private version 29 launched and source verified

- The first `.venv` CLI push returned `Expecting value: line 1 column 1 (char 0)`. A remote status/list check showed no version after that response. One direct call to the same pinned Kaggle SDK then returned HTTP 200 and created kernel version 29 (`kernel_id=140391884`). The first CLI error's cause is unresolved; no duplicate version was created.
- This later launch supersedes the 04:44 UTC readiness note that described C2-060 as an unpushed local draft.
- Exact version 29 was pulled read-only. Its 25 ordered cell sources match the candidate exactly, and all checked execution metadata fields match. Local notebook SHA-256: `d610d79e44e0974cf18f3f29c9521c7407e4c6fa047d38456f1a9a67f8a65e26`; remote raw Notebook SHA-256 differs because Kaggle serializes it.
- Exact version 29 status was `RUNNING` at 2026-10-27T10:41:34Z. It is a private GPU run with Internet disabled; 3 public offline games, seed 0, 160 actions/game, 1,200 seconds/game. No Competition Rerun, official submission, or submission-quota use occurred.
- The official history read at 10:42 UTC still shows submission `57688735` PENDING with no scores; `numToday=1`, `numTotal=8`. The confirmed official best remains submission `57577905`, public 23.86.
- Do not push again. On terminal completion, retrieve exact version 29 output and score it against C2-046 slim using the same three public starts and the predeclared gate (>19.309155944 and positive paired mean delta).
- Push/source/status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-v29-push-20261027T104223Z.json`.


## 2026-10-27T11:55Z: private version 29 terminal paired scorecard

Exact kernel `tecchannn/arc3-model-guided-c2-025/29` reported `KernelWorkerStatus.COMPLETE` at 2026-10-27T11:55:20.961696+00:00. Kaggle output is retained under `出力/ARC3-RUN-003-local/C2-060-outputcap-20480-context139264/remote-v29/output`; the completed manifest contains 31 files / 151225601 bytes and matches the scorecard SHA-256 `68d9a4541b34b0748a157518ca9b00fab1e681f3b2e63abe74cd623978e74dba`. `benchmark.json` is complete; `requests.jsonl.kaggle-partial` marks the request transcript incomplete, so the score uses the complete benchmark, recomputed official ARC SDK scorecard, and paired initial event records.

The same three public starts (seed 0, 160-action cap, 1,200 seconds/game) were checked field-by-field against both references. The official `EnvironmentScoreCalculator` recomputation matches each saved per-game score.

- C2-060 v29 mean: **6.793535827960**; C2-046 slim mean: **19.309155943771**; paired delta: **-12.515620115812**. All three games regressed against C2-046; completed levels were 4 versus 7 with the same 389 total actions.
- Against C2-058 v27, mean was **12.471062097130**, delta **-5.677526269171**; two games improved and one regressed.
- Compared with the prior C2-059 v28 mean of 5.351788828051, v29 rose by **1.441746999909**, but remains 12.515620115812 below C2-046 and fails the declared acceptance gate (`mean > 19.309155943771326` and positive paired delta). **Decision: REJECT C2-060; do not promote this version as a higher-scoring candidate.**

The official submission `57688735` is still `SubmissionStatus.PENDING` with public/private scores blank at 2026-10-27T11:58:31.571410+00:00. Its description identifies the earlier C2-046 v13 fallback, not this private v29 run. Kaggle reports `numToday=1`, `numTotal=8`, `remainingToday=0`. The confirmed official best remains submission `57577905`, public **23.86**. No Competition Rerun, new official submission, or quota use occurred for C2-060.

- Scorecard script: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-v29-scorecard.py` (SHA-256 `3c14602e206ffcdee4efda77d281713f235db84b2e5d2d2835e001b1de9b6cd8`).
- Scorecard result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-v29-terminal-scorecard.json` (SHA-256 `19a45df2dc0e55a5bb5140b718a12941b3218edbd939c7e48388aa61cf3d59cb`).
- Terminal-status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-v29-terminal-status-20261027T115520Z.json` (SHA-256 `c59d3b7ecb61da4e5ae7347cb5fc6ee2883178118a457d0147f2b9eb6a64dabc`).
- Official history/quota evidence: `運用/証拠/ARC26-UNIFIED/official-cli-observation-20261027T115831Z.json` (SHA-256 `13bd5cfd8c426759397dd73bfd2bb5a2d60250e41b2d2af737774efcdf291a0a`).
