# ARC3-RUN-003 C2-046 実行記録

## 2026-10-24 JST: 準備

- 候補作成: C2-035 v10 controlと未push v11 slimを複製し、`出力/ARC3-RUN-003-local/C2-046/source/{off,slim}`へ保存。
- Notebook nbformat 4を確認。各armはC2-035からcell 13（SGLang weight-loader config）とcell 18（run label）だけが変更。off/slim間はcell 5の`ARC3_MEMORY_SECTIONS`だけが異なる。GPU/private/Internet metadataは維持。
- control SHA256: `b5a77e0e01906c52fd706ff31b3f73473fdf62f8e719af3d54747f3d90fbd828`; treatment SHA256: `453231dd960b2be929d15f1eaad43d856cc64faa12c699d34e088f6b16a7925e`; shared metadata SHA256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.
- Loader: `enable_multithread_load=true,num_threads=8`; prefetch setting and all model/prompt/solver parameters are held fixed. C2-035のstartup limit 1800秒は変更なし。
- Protected file hashes remain `AGENTS.md=dff057d8f6ac88c688ec1d950640dc88b706d5ed9184119deda226d0109a8d42`, `制御/現在状態.json=0e4b29319d727896e244fe32f9726f0933f63fe007f59480272e76d46508c93c`.
- Kaggle Phase A/private runのみ。Competition Rerun、公式提出、提出枠消費は行わない。Control成功後に限りslim treatmentを行う。

## 実行結果

Control run開始前。

## 2026-10-24 12:52 UTC: control version 11 開始

- Kaggle read-only status直前値: 既存latest kernel version 10は`ERROR`。
- `tecchannn/arc3-model-guided-c2-025`へC2-046 off control version 11を一度だけpush。Kaggle応答は`Kernel version 11 successfully pushed`、12:52 UTCのstatusは`RUNNING`。
- 使用Notebook SHA256 `b5a77e0e01906c52fd706ff31b3f73473fdf62f8e719af3d54747f3d90fbd828`。private run only。
- 次のgate: /health_generate readinessとoffline benchmark開始を確認。1800秒期限内に開始しない場合は追加実行せず閉じる。slim versionは未push。

## 2026-10-24 13:51 UTC status follow-up

- Version 11 read-only status remains `KernelWorkerStatus.RUNNING`; no terminal log or artifact is available yet. Exact-version status query only. No treatment push, official rerun, or submission.

## 2026-10-24 UTC: version 11 readiness gate passed

- Kaggle log reports `INFERENCE READY after 1675s` at kernel elapsed 1769.203s; `Starting benchmark...` follows at elapsed 1771.601s. Server launch was at kernel elapsed 94.038s, so readiness was confirmed before the unchanged 1800-second server deadline.
- Control uses SGLang loader `enable_multithread_load=true,num_threads=8`; status remains `RUNNING` while the 3-game offline benchmark executes.
- This is loader feasibility evidence only. Level/WIN delta and treatment readiness are not yet available. Version 12 slim is not pushed until control completes and its artifact/start-state evidence is checked.

## 2026-10-24 14:24 UTC: control version 11 完了

- Kaggle exact-version status: `tecchannn/arc3-model-guided-c2-025/11` = `KernelWorkerStatus.COMPLETE`（14:19 UTCに観測）。Notebook SHA256は準備時記録どおり。Kaggle logに`TRUE_SUBMISSION=False`を確認。
- Loader feasibility: `INFERENCE READY after 1675s`、benchmark開始はkernel elapsed 1771.601s。startup deadline 1800秒内。
- 3件のoffline benchmark: `gave_up` 3/3、WIN 0、level完了 6/21、Action 480（各run 160上限）、generated tokens合計 468,142、benchmark経過 3,255.914秒。個別環境識別子や盤面・action列は記録しない。
- 初期状態artifact: 3/3が`NOT_FINISHED`、level完了0、盤面shape 64x64。公開初期board/state/levelを正規化したaggregate fingerprint SHA256 `1f66dfa622cbbacf417db9fb2a65faffc6574f3daa1f7cb11418310cbb3567c7`。この値は状態一致確認用であり、action選択条件には使用しない。
- Output root: `出力/ARC3-RUN-003-local/C2-046/kaggle-output/off/`。Artifact SHA256: `benchmark.json=9ee4b8b85fe6afdb58cf702acca576947be52c808cabcccb3f75188e3ba4da64`; `summary.txt=acb01827589084f6bfe107029a0bd282f7f557dda76c1855a13cdc1336f3676f`; `serve.log=329dc43e490f495d8410d130da21d9f3000775cb1d6edbaaa2762a6b300510b2`; `intermediate_states.pkl=cc85cf97faa062b1942f53bfb77e0150508e7ac90c462ecb7fee45b91267741d`; run log `arc3-model-guided-c2-025.log=e66523248e67c1907376dd0667582e477d6557dac78369ba3adbc6fe8a789fc5`.
- Control is feasible but weak on this 3-run pilot; it does not establish memory treatment effect. Proceeding with the predeclared `slim` arm once, with same seed/environment/action budget. No official rerun/submission or score access.

## 2026-10-24 14:25 UTC: slim treatment version 12 開始

- Pre-push source audit: treatment Notebook SHA256 `453231dd960b2be929d15f1eaad43d856cc64faa12c699d34e088f6b16a7925e`; off/slim source diff is only memory setting cell 5. Shared metadata SHA256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`; private=true, GPU=true, Internet=false; shared loader config is `enable_multithread_load=true,num_threads=8` with checkpoint prefetch retained.
- Kaggle push completed once: `tecchannn/arc3-model-guided-c2-025` version 12. Read-only exact-version status at 14:25 UTC: `KernelWorkerStatus.RUNNING`.
- Same public offline benchmark protocol as control: seed 0, 3 games, 1 pass, 160 actions/game, 1200 seconds/game; only `ARC3_MEMORY_SECTIONS=slim` differs. Official competition rerun/submission and quota use remain zero.
- Next gates: confirm readiness/benchmark start, collect artifacts on completion, verify memory update/reinjection and match all three public start states against control, then record off/slim/delta and accept/reject.

## 2026-10-24 14:29 UTC: control no-op / legality supplement

- Public no-op definition for this audit: adjacent snapshots have identical visible board (`frame[-1]`), state, and completed-level count. Result: 6/480 transitions.
- Legality audit: 478 non-RESET actions checked against the preceding snapshot's `available_actions` (the serialized `GameAction.ACTIONn` name maps to action number n); illegal non-RESET actions: 0. Two RESET transitions are reported separately and excluded from the available-action mask check. All 480 actions are accounted for.
- Version 12 read-only status at 14:29 UTC remains `KernelWorkerStatus.RUNNING`; no live logs were available.

## 2026-10-24 14:36 UTC: control state summary

- Across 483 snapshots: 482 `NOT_FINISHED`, 1 `GAME_OVER`; level-win flags total 6 (per-run count histogram: one run at 1, one at 2, one at 3); no full-reset snapshots. Final benchmark statuses remain 3/3 `gave_up` at the 160-action cap. No run reached its 1200-second per-game limit.
- Version 12 read-only status at 14:36 UTC remains `KernelWorkerStatus.RUNNING`.

## 2026-10-24 14:58 UTC: version 12 status follow-up

- Read-only exact-version status remains `KernelWorkerStatus.RUNNING`; `kaggle kernels logs` returns no live output. No terminal result/artifacts yet. No repeat push, competition rerun, or submission.

## 2026-10-24 15:00 UTC: live output lookup

- Exact version 12 remains `KernelWorkerStatus.RUNNING`. `kernels logs` is empty and exact-version `kernels output` found no live matching log artifact. Monitoring remains read-only; no restart or duplicate push.

## 2026-10-24 15:12 UTC: version 12 delayed status follow-up

- Exact-version status remains `KernelWorkerStatus.RUNNING` about 47 minutes after push. `kernels logs` remains empty; no live output files. This differs from C2-046 v11's roughly 30-minute readiness evidence, but without logs it is not possible to distinguish slow startup from active benchmark. No restart/re-push.

## 2026-10-24 15:15 UTC: version 12 output recheck

- Exact-version status at 15:14 UTC remains `KernelWorkerStatus.RUNNING`. A second read-only, log-only `kernels output` fetch returned no files, consistent with logs being withheld until terminal completion.

## 2026-10-24 15:22 UTC: version 12 status follow-up

- Exact-version status remains `KernelWorkerStatus.RUNNING` about 57 minutes after push. Logs and live artifact lookup remain empty. No conclusion on readiness or memory effect yet.

## 2026-10-24 15:27 UTC: version 12 status follow-up

- At about 62 minutes after push, exact-version status is still `KernelWorkerStatus.RUNNING`; live logs/artifacts remain unavailable. The v11 run required about 87 minutes end-to-end, so this remains within that observed duration.

## 2026-10-24 15:34 UTC: version 12 status follow-up

- Exact-version status remains `KernelWorkerStatus.RUNNING` about 69 minutes after push. `kernels logs` and live output lookup remain empty. No restart/re-push; still within v11's roughly 87-minute end-to-end reference.

## 2026-10-24 15:40 UTC: version 12 status follow-up

- Exact-version status remains `KernelWorkerStatus.RUNNING` about 75 minutes after push. No log/artifact is available while running.

## 2026-10-24 15:48 UTC: slim treatment version 12 completed

- Kaggle exact-version status: `KernelWorkerStatus.COMPLETE` observed 15:48:49 UTC. This was a private offline benchmark; kernel log confirms `TRUE_SUBMISSION=False`. No official score/submission/quota was involved.
- Readiness gate passed: `INFERENCE READY after 1510s` at kernel elapsed 1567.017s; benchmark began at elapsed 1568.937s. No traceback in the saved main log. Total kernel log elapsed 4763.833s.
- Same 3 paired public starts: all 3/3 match on full public frame, state, completed level, and available-action mask. Initial state count 3 `NOT_FINISHED`, level 0, one 64x64 frame each. Matching used internal keys only; none are recorded here.
- Aggregate result, off -> slim: levels 6/21 -> 7/21 (+1); WIN 0 -> 0; final benchmark states `gave_up` 3/3 in both arms. Paired level delta distribution: two starts +1 level, one start -1. This is a small positive directional result, not a capability claim.
- Efficiency/trade-off: actions 480 -> 389 (-91); control all 3 runs reached 160 actions, while slim had 99/130/160 actions and 2/3 runs reached the 1200s per-game limit. Benchmark elapsed 3255.914s -> 3187.865s (-68.049s). Generated tokens 468142 -> 439748 (-28394). Public-state no-op transitions 6/480 -> 10/389; illegal non-RESET actions 0/478 -> 0/387; GAME_OVER snapshots 1 -> 1.
- Memory evidence: slim run request history contains assistant World model/Plan section headers and repeated later request contexts; all 3 transcript artifacts contain memory headers, no degenerate-update rejection appears in run logs, and at least one recorded level-change marker is followed by both World model and Plan headers. This establishes update/reinjection evidence for the pilot, not for every transition.
- Model request telemetry: response events 210 -> 247 (+37); mean prompt tokens/response remained about 69.9k in both arms, while total prompt tokens rose 14684991 -> 17277615 and completion tokens fell 468142 -> 439748. This points to more model calls rather than a large per-call prompt increase; causal attribution is not established.
- Paired start/action audit and run artifacts are under `出力/ARC3-RUN-003-local/C2-046/kaggle-output/{off,slim}/`. Slim SHA256: `benchmark.json=6535b5240dd5160eaa0b3d0afec3d6d2660cb7e12915bb487ab206167369a72e`; `summary.txt=38642abd77bb0cbc42a3dac9e7e7cac0393a84e995be39997d05a5394be2812d`; `serve.log=3d05a2eb138bdc0f228a824b4b83d481117982f0d1fdbbc59e31c9029d24c3f1`; `intermediate_states.pkl=8370d9588544bdbfd5e0926635e5e6412911407107b6ebadc0b528a56baa7c54`; `requests.jsonl=041c2aeee7dc283fd8324eff6932cea0938c63917ffa6173e706933c8c2c026f`; main log `ec065670b56a21de12263cc2f0d96cb8c8b0fc3cc42f8e8fbb1dc21691f55ebd`.
- Decision: retain `slim` as a validation candidate, do not promote it to an official submission candidate. The positive paired level delta meets the pilot's progress gate, but one regression, two timeouts, and n=3 require a larger matched confirmation and a follow-up focused on memory-driven request overhead.

## C2-046 pair audit clarification

- The paired state/action legality audit was computed inline from the saved run artifacts; a separate pair-audit file was not created. The earlier path reference points to the run artifacts and aggregate findings recorded above.

## Cross-level memory scope clarification

- Source audit of the prepared C2-046 slim notebook shows it did not override `ARC3_WM_WIPE_ON_LEVEL`; the runtime default is 1, which clears stored sections at each level transition. The observed post-transition World model/Plan headers establish rebuild/reinjection after the transition, not preservation of the prior level's sections. Reclassify C2-046 as a within-level memory comparison; cross-level retention remains untested. The saved paired scorecard result is unaffected.
