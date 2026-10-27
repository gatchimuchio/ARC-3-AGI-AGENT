# C2-059: preserve input budget with a 16k output reserve

## Status

Prepared locally only; not pushed. Wait for C2-058 version 27 to reach terminal status and for its matched score/trace review before deciding whether to run this candidate.

## Hypothesis

C2-058 raises `LOCAL_ANALYZER_MAX_OUTPUT` from 12,288 to 16,384 while leaving the 131,072 context window fixed. The output reserve and 512-token safety margin reduce the allowed input from 118,272 to 114,176 tokens. The C2-046 control trace had one prompt at 116,437 tokens. C2-059 keeps the 16,384 output reserve but raises the context window to 135,168, restoring the 118,272-token input budget within the 139,264-token server context.

## Candidate

Based on the C2-058 candidate. Only cell 5 changes relative to C2-058: `LOCAL_ANALYZER_CONTEXT_WINDOW` 131,072 -> 135,168. Cell 5 remains at output cap 16,384. Notebook has 25 cells; only cell 5 source differs. Candidate SHA-256: `627ce824f4e3f72d00303223c549d7d0dbbe311bc8b026351b7c186559daf0b2`; metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.

## Acceptance

Use the same three public starts as C2-046 and C2-058. Recompute with `arc_agi.scorecard.EnvironmentScoreCalculator`; require mean > 19.309155943771326 and positive paired delta versus C2-046. Also report paired delta versus C2-058, per-game scores, levels, wins, actions, runtime, generated tokens, terminal state, and start-state identity.

No official competition submission or quota use. Preflight evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-preflight-20261025T132113Z.json`.


## C2-058 terminal evidence and fresh v27 preflight

- C2-058 version 27 is COMPLETE. Its matched mean was 12.471062097 vs C2-046 19.309155944, paired delta -6.838093847; it is rejected. The output-budget pilot therefore needs the planned input-history restoration follow-up.
- Fresh exact version 27 source pull and status confirm the base Notebook is the completed C2-058 version. Compared with that remote source, C2-059 changes only cell 5: `LOCAL_ANALYZER_CONTEXT_WINDOW` from `(116+12)*1024` to `(132)*1024`; output remains `16*1024`. It is also a one-cell delta from the local C2-058 source.
- This restores effective input budget from 114,176 to 118,272. The 116,437-token baseline prompt then fits by 1,835 tokens; server context is 139,264. Metadata remains private, GPU enabled, Internet disabled.
- Preflight evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-preflight-20261025T142506Z.json` (SHA256 `79397624e01237bca203265f9d43323485172a762d142a10509a5b860fb911b9`). No official submission or quota use.
- Acceptance remains C2-046 mean > 19.309155943771326 and positive paired mean delta on the same three starts. Beating C2-058 alone is diagnostic and does not authorize promotion.


## Version 28 private pilot started

- Kaggle accepted one push as private kernel version 28. First read-only status at 2026-10-25 14:25:58 UTC was `KernelWorkerStatus.RUNNING`. No official competition submission or official quota use.
- Exact version 28 was pulled back read-only. Its 25 ordered cell sources (12 code cells) match candidate Notebook SHA256 `627ce824f4e3f72d00303223c549d7d0dbbe311bc8b026351b7c186559daf0b2`; stable runtime metadata matches the private/GPU/Internet-off configuration. Remote raw Notebook SHA256 `aeccaa17f8d00695252aeed956f3c9976bf26055dd858e1b14e29775b733b683` differs due Kaggle serialization.
- Push record: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-push-20261025T142630Z.json` (SHA256 `39a2b985bf70dc034c6ca79016df0c58bf5be7651e24f213007cfcc89aacef0d`). The only active experiment is version 28; do not create a duplicate. After COMPLETE, retrieve exact `/28` output and apply the predeclared paired gate against C2-046 and C2-058.


## Context-pruning hypothesis audit (2026-10-25T14:34:27Z)

The C2-046 control transcript contains a 116,437-token prompt, 2,261 tokens above C2-058's 114,176-token input budget. That makes earlier pruning plausible if the same prompt occurred in the candidate trajectory. However, the complete v27 `serve.log` records a maximum prefill of 112,384 tokens, 1,792 under that budget, and no explicit context overflow or truncation error. Actual pruning in v27 is therefore **not established**; the C2-059 preflight wording that it “had pruned” the prompt is too strong. Keep C2-059 as a controlled 4,096-token input-headroom experiment and retain the original score gate. Version 28 was still `KernelWorkerStatus.RUNNING` at the observation time.

- Audit evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-context-hypothesis-audit-20261025T143427Z.json` (SHA256 `2dc598eab50ce82e1465eb65efe453e740e64eb395a001804e64dc59a684b8fc`).


## Request-log diagnostic for the next optimization (2026-10-25T14:38:31Z)

The available `requests.jsonl` capture is partial (93,323,264 of 103,567,872 bytes; 368 valid JSON lines and one incomplete line). Within captured model usage, the largest prompt was 112,371 tokens, below the 114,176 input allowance; this cannot rule out an unseen request in the missing tail. Two responses at action 79 / analysis step 24 ended with `finish_reason=length` at exactly 16,384 completion tokens. This is a concrete output-cap binding signal, but not a score gain. If C2-059 fails its gate, a later private experiment can test 20,480 output tokens while retaining 118,272 input allowance at the observed 139,264 server context limit; verify startup feasibility first and wait for v28 to terminate before any push.

- Request-log audit: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-request-log-audit-20261025T143831Z.json` (SHA256 `429631b7774e6fa28400248518b0698254ba6b8c3ab37d148826909781e9042d`).


## C2-060 local draft prepared (2026-10-25T14:40:38Z)

Prepared a local-only output-reserve candidate at 20,480 while preserving the 118,272-token effective input allowance. It is motivated by two length-terminated 16,384-token responses in the partial v27 request transcript, not a performance claim. Context 139,264 equals the observed server limit, so feasibility must be rechecked after v28 completes. C2-060 is not pushed and must not be pushed while v28 runs.

- Draft report: `運用/ARC3-RUN-003/C2-060_output-cap-20480-draft.md`.
- Preflight: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-preflight-draft-20261025T144038Z.json` (SHA256 `10b3060869951f6ed3503b9ad15fff362dbaa628808b84b2a06c1eb5bd7e99b2`).
- Notebook SHA256: `d610d79e44e0974cf18f3f29c9521c7407e4c6fa047d38456f1a9a67f8a65e26`; metadata SHA256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.


## Matched request-budget evidence (2026-10-25T14:42:00Z)

The complete C2-046 control transcript has one output terminated at its 12,288-token cap. The partial C2-058 transcript has two outputs terminated at its 16,384-token cap. This supports an output-headroom experiment but does not predict a score gain. The different actions and trajectories prevent a direct behavioral comparison; output-cap hits are diagnostic only. C2-058 logs still do not establish that input pruning occurred.

- Cross-run evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-output-cap-evidence-comparison-20261025T144200Z.json` (SHA256 `02d3421e8fe649b277a0db2f9f43f1dd380b71f1014c5090ef79a2a2a6c3ee02`).


## Version 28 scorecard preparation

Prepared a scorecard script by adapting the validated C2-058 v3 scorer. It will require terminal `COMPLETE` for exact version 28, three matched game IDs, matching initial-state fields/level counts/baseline actions, recompute per-game scores with `EnvironmentScoreCalculator`, and apply the unchanged C2-046 mean/paired-delta gate. It has not been run because v28 remains RUNNING and its output is not available.

- Script: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-scorecard.py` (SHA256 `d19754a0e8df5aaeb73a5b763517bc4c5aa5a413fd4b08e8f11d0725f8e066ac`).


## Output-cap sequence interpretation (2026-10-25T14:55:24Z)

The action-79 / step-24 sequence shows two 16,384-token length terminations, followed by a tool-call response and then action 88. The cap therefore caused extra reasoning continuations in this trace but did not permanently block actions. C2-060 may reduce repeated calls; it is not assumed to improve score. Judge it with paired score, level progress, actions, and token totals.

- Sanitized sequence evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-cap-sequence-diagnostic-20261025T145524Z.json` (SHA256 `faeaebf859d0d8d1ba3776226a0f45c7e714c247c32d63fac82c1e33baa218d1`); prompt and board content were not saved.


## Exact version 28 terminal result and decision (rechecked 2026-10-27T04:44:47.991112+00:00)

- Read-only Kaggle recheck confirms exact kernel version 28 is COMPLETE. The versioned output bundle (31 files, 140,762,127 bytes) is already downloaded and hash-manifested; no duplicate retrieval was needed.
- On the same three public starts, the `EnvironmentScoreCalculator` scorecard is **5.351788828 mean**, versus C2-046 slim **19.309155944** (delta **−13.957367116**, paired 0 improved / 1 tied / 2 regressed; 4 vs 7 completed levels; 0 wins; all three runs `gave_up`). Total actions 366 vs 389; generated-token history sum 491,194 vs 439,748. The predeclared gate failed.
- Against C2-058 v27, C2-059 averaged **5.351788828 vs 12.471062097** (delta **−7.119273269**; 2 improved / 0 tied / 1 regressed). The largest paired regression was the `tn36` public-start row, −34.058720818. Initial public fields, level counts and baseline actions match 3/3. The C2-058 output retrieval was incomplete; its validated benchmark/scorecard and initial-event records are the comparison source.
- Earlier status text saying v28 was still RUNNING and its scorer had not run is superseded by the terminal status and scorecard artifacts below; the historical record is retained. The later note correction changes only the scorecard transcript-completeness note, not metrics.
- This is a private offline public-start scorecard, not a Kaggle competition score. It does not beat the historical official best 23.86 (submission 57577905); the current official submission 57688735 remained PENDING with blank public/private fields in the read-only history snapshot at 2026-10-27T04:44:47.991112+00:00.
- Candidate is **REJECT_C2-059**. The context-window increase alone is not a score-improving change and is not promoted. Exact evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-terminal-scorecard.json`, `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-vs-C2-058-scorecard.json`, `運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-terminal-status.json`. Consolidated next-candidate evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-060-post-v28-readiness-20261027T044447Z.json`.
