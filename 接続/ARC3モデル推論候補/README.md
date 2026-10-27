# ARC3 model-guided candidate (C2-025)

This is a separate Kaggle notebook candidate for a bounded execution and public-environment comparison of a generic model-guided policy. It does not replace the observation-driven v4 candidate or modify HDS.

## Source and scope

- Upstream Kaggle notebook: [Daniel Franzen, ARC-AGI-3 Milestone 2 Solution](https://www.kaggle.com/code/dfranzen/arc-agi-3-milestone-2-solution), downloaded 2026-10-23. Downloaded notebook SHA-256: `88A379F17C3A4BA8C98715FC23155346CCD6EB289BDAFEBADFC61A3178F9D9BD`.
- Upstream source repository: [da-fr/arc-agi-3-solution](https://github.com/da-fr/arc-agi-3-solution), inspected at commit `10882e332d883af3e61616df8c8a17d03a328a75`. It is Apache-2.0; a copy of that license is in this folder. Original author and Tufa Labs attribution stays in the notebook.
- The selected Qwen3.8-Flash-Next and quantized model inputs carry Qwen Community License 1.0, as shown in the [official Qwen model repository](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) and the [Albucino derivative model card](https://huggingface.co/albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE). The notebook does not redistribute model weights.
- Kaggle resources and the upstream Python 3.12 Docker image digest are pinned in `kernel-metadata.json`; GPU is RTX PRO 6000 and internet access is disabled.

The notebook clears inherited output cells, adds this scope note, and bounds interactive offline runs to the first `ARC3_DEV_GAME_LIMIT` environments in one pass, one worker, and at most 80 Action events per game. C2-027 temporarily sets the offline-only default to 25 and retains a 1,200-second per-game wall-clock cap. Private runs v2/v3 confirmed the model-server runtime path but neither completed a level. C2-026 version 4 compared three public starts against the same local v4 starts: the candidate completed 3 levels versus 1 for the local baseline (+2), with no game wins. This supports a bounded 25-environment pilot, not promotion or an official performance claim. The live competition path keeps the original generic policy and has no per-game cap. No game ID, filename, or board-hash answer branching was found in the notebook's code cells.

## Run and interpretation

`submission.ipynb` and `kernel-metadata.json` are the source for the private Kaggle kernel `tecchannn/arc3-model-guided-c2-025`. Offline runs are ordinary private kernel executions, not official competition scores. The official Competition Rerun path is separate; no new competition submission has been made for this candidate.

The upstream author reported a public leaderboard score in the write-up. That figure is an external reference, not a measurement for this candidate or a promise of improvement over v4.

## C2-027 current status

At 2026-10-23 17:19 UTC, private kernel version 5 (first 25 public environments, one pass, one worker, 80 Action events/game, 1,200 seconds/game) was still running. It is a normal private kernel run, not a Competition Rerun or official score. The local v4 baseline has 25 public starts and 3 total completed levels; direct candidate-vs-baseline start-board matching is pending output retrieval. The official submission history was rechecked at 15:43 UTC and remains unchanged. See `運用/ARC3-RUN-002/C2-027_汎用モデル候補の公開25環境pilot.md`.

## C2-027 completed

Private kernel version 5 completed. On 25 exactly matched public starts, the model-guided candidate completed 47 levels in 1,906 Action events versus 3 levels in the 2,000-Action local v4 baseline (+44; 22 improved, 2 tied, 1 regressed). All 25 candidate runs ended `gave_up` with no wins, and four reached the 1,200-second per-game limit. This is a bounded private development result, not an official score or promotion decision. Full per-game comparison, runtime and telemetry caveats, and output hashes are in [`C2-027`](../../運用/ARC3-RUN-002/C2-027_汎用モデル候補の公開25環境pilot.md) and `出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5/C2-027-comparison.json`. The next scoped diagnostic is [`C2-028`](../../運用/ARC3-RUN-002/C2-028_25環境pilotの失敗分布と実行上限診断.md).

## C2-028 diagnosis and C2-029 horizon test

C2-028 confirmed 25/25 exact starts, 22 improved games, two ties, one regression, 68/1,906 visible no-op actions versus baseline 137/2,000, and seven GAME_OVER events versus baseline 15. Twenty-one runs reached the 80-Action cap; four hit 1,200 seconds. Timeout transcripts and incomplete token telemetry are recorded. No WIN occurred, so the diagnostic does not promote the candidate. See [`C2-028`](../../運用/ARC3-RUN-002/C2-028_25環境pilotの失敗分布と実行上限診断.md).

On 2026-10-23 19:52 UTC, offline guard changes for C2-029 were pushed as private kernel version 6. The run uses the same first three starts, 160 Action cap, 1,200 seconds/game, one pass, one worker, GPU, and Internet disabled. Kaggle status is `RUNNING`; no Competition Rerun or submission was made. Notebook SHA-256: `fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a`.

## 2026-10-23 21:13 UTC C2-029 horizon検査・C2-030計測監査

- model-guided private kernel version 6はCOMPLETE。最初3公開開始状態の初期board/state/levelは3/3一致。version 5からのlevel差はsk48 +1、tn36 +3、m0r0 -2、合計2→4（+2）だが、全てgave_up/WIN 0。Action上限拡大の因果改善とは判定せず不採用。時間上限1件、Action上限2件。詳細は[C2-029](../../運用/ARC3-RUN-002/C2-029_80Action打切りと勝利未達のhorizon検査.md)。
- C2-030の監査で、benchmark時刻差はv5 15,657.695秒/v6 3,200.794秒。一方summary total wallclockは累積per-game timer合計（228,187.620秒/6,673.737秒）と一致し、全体時間として誤読されることを確認。今後job全体はstart/end差、per-gameは累積timerの隣接差で集計する。history token合計はsummaryと一致したが、solver_noteとの差はv5 +28,229、v6 +31,679。全final_generated_tokens欄は0で不採用。hash監査164/164・32/32一致。
- 監査ツール[benchmark_telemetry_audit.py](../../道具/benchmark_telemetry_audit.py)、targeted test3件PASS。audit JSONは出力/ARC3-RUN-002-local/C2-030-telemetry-audit/。
- Kaggle read-only照会: private model-guided kernel COMPLETE、公式latest ref 57541830/public 0.25と57527856/public 0.00。提出残り0件。新規Competition Rerun/公式提出/採点なし。次は[C2-031](../../運用/ARC3-RUN-002/C2-031_sk48-runtime-cap-analyzer待ち時間監査.md)で既存artifactのruntime/request時系列を監査する。
## 2026-10-23 21:21 UTC C2-031 cold-start診断・C2-032 private run開始

- C2-031でv6 sk48のruntime cap 1,200.173秒、action42直前のread timeout 36.05秒1件、transcript turn-token yields 7件を確認。requestログ全体は191 request/190 responseで、timestamp/game ID不足のため個々の待ち時間はjoin不可。Notebookの/health gateと過去の8m32s cold-load comment、server precache 876.95秒が、first-game timer内のmodel loadと整合する。timeout単独原因説は支持しない。
- C2-032でreadiness probeを/health_generateへ変更し、offline deadlineをserver起動後12分で測定するprivate 1-game検査を開始。version 7 push成功、status RUNNING。v6 backup SHA fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a、candidate Notebook SHA d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922。最終結果待ち。C2-032の詳細は[こちら](../../運用/ARC3-RUN-002/C2-032_SGLang推論ready前のgame-timer消費を避けるprivate-pilot.md)。
## 2026-10-23 21:37 UTC C2-032結果・C2-033 private run開始

- C2-032 private kernel version 7は`ERROR`。SGLang 0.5.19+gd00d88efc8d6で38 shard中34 shard（89%）を11分15秒時点まで読み込んだが、server起動後720秒のready deadlineに達し、offline benchmark開始前に停止した。`/health_generate`のHTTP 200は未観測であり、endpoint自体の成否は不明。v6 sk48（41 Action、1 level、1,200.173秒）に対するcurrent/deltaはN/A。
- version指定の保存ログ: `出力/ARC3-RUN-002-local/C2-032-kaggle-output/v7/`。kernel log SHA256 `24ae6a54f64977729d5b074e58fa9562fe44bce53bd8ecc49742bd098165a6af`、serve.log SHA256 `e2b578339fd168e08b6c1bdebf197990124dc65f8f3bb0504272b8ff21762d40`。benchmark/summaryは出力されず。詳細は[C2-032](../../運用/ARC3-RUN-002/C2-032_SGLang推論ready前のgame-timer消費を避けるprivate-pilot.md)。
- C2-033はdeadlineだけを12分から18分に延長し、`/health_generate`とfail-closed、1ゲーム/160 Action/1,200秒、solver/model/promptを保持。変更cellは5と18。version 7 backupは`出力/ARC3-RUN-002-local/C2-033-source/v7-submission.ipynb`（SHA256 `d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922`）。Notebook SHA256 `449b57c9eca8f24a6338b5eb6f68d231a2fab4185073293a79c00581f85a5a05`、format/metadata/outputs監査PASS。
- private kernel version 8 push成功、直後status `RUNNING`。これはcold-start pilotでありCompetition Rerun・公式提出・採点ではない。公式candidateの昇格なし。
