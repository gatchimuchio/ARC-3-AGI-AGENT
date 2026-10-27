# C2-114 — Undo exposure diagnostic draft

Status: **prepared locally; not run, not pushed to Kaggle, and no score is claimed.**

## Finding

In the exact C2-060 version 29 trace, sk48 issued 17 consecutive ACTION7 (UNDO) actions at actions 44–60. None produced a reward or completed a level. The first level completion came at action 64; the matched C2-046 v13 trace completed its first level at action 43 and used no Undo. Neither tn36 nor m0r0 used Undo in either trace. This is a bounded, observed failure pattern; it does not explain the full v29 score loss.

C2-060 v29 scored **6.7935 mean** against **19.3092** for the matched C2-046 slim control (paired delta **−12.5156**, all three starts regressed). The exact scorecard is 運用/証拠/ARC26-UNIFIED/ARC3-C2-060-v29-terminal-scorecard.json (SHA-256 19a45df2dc0e55a5bb5140b718a12941b3218edbd939c7e48388aa61cf3d59cb).

## Candidate

C2-114 changes only EXPOSE_UNDO from on to off in cell 5 of the exact v29 candidate. Context (139,264), output reserve (20,480), and the 118,272-token effective input allowance remain fixed. The notebook has 25 ordered cells and cell 5 is the only source cell changed.

- Candidate notebook: 出力/ARC3-RUN-003-local/C2-114-expose-undo-off/source/undo-off/submission.ipynb (SHA-256 5e5d92994533303de46f11145ebc07a62cc36d26ff9dab6aa191446668b8b539)
- Metadata copied unchanged: 出力/ARC3-RUN-003-local/C2-114-expose-undo-off/source/undo-off/kernel-metadata.json (SHA-256 e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372)
- Reproducible one-line patch: 検証/ARC3C2-114_EXPOSE_UNDO_off.patch (SHA-256 548e00b52768c955a154b0e4c7cef0707127e59ff963b353584b69a7c3d747e1)

## Gate and execution

If a private pilot becomes available, compare the same three public starts to v29 for the Undo effect. Promotion still requires beating the C2-046 mean **19.3091559438** with a positive paired mean delta and verified matched starts. The candidate is not run and cannot be promoted from this trace audit.

The last recorded private GPU push rejection is C2-105 at 2026-10-27T20:48:49Z, rejected at the weekly GPU quota. There is no fresh capacity evidence, so C2-114 was not pushed. No official submission or competition quota was used. The last read-only official history check showed submission 57688735 COMPLETE, public score **28.07** (legacy C2-046 v13).

## Three-point set and protected-file check

The v6.0 three-point set was rechecked for this work item. All six hashes and the protected AGENTS.md / 制御/現在状態.json hashes are recorded in the evidence JSON. None were modified.

Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-114-undo-streak-diagnostic-20261027T233055Z.json (SHA-256 5e9f86f06f501110d54ca1a93746ea56c6f4ec0e59f398391ce6562884cb8848).

## 2026-10-27T23:43:16Z capacity and output retrieval checkpoint

The pinned Kaggle CLI `kaggle quota` read returned GPU 30.13h used / 0.00h remaining / 30.00h total, refreshing at `2026-10-31T00:00:00Z`. TPU remains 20.00h, but C2-114 uses the existing GPU model path, so it remains unrun and unpushed pending GPU refresh. No official submission quota was used.

To keep future private output collection within the available local disk, exact kernel version 29 was queried with `--file-pattern '^benchmark\.json$'`. The CLI returned `benchmark.json` (99,849 bytes, SHA-256 `9619e3f916b66e807b2f71bb7c62fe1d0559fe98ede2eb26f4c2c2d16b037e2c`) and its 44,119-byte run log; it did not download the full output bundle or use compute quota.

Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-114-capacity-and-selective-output-20261027T234316Z.json` (SHA-256 `9d357655a27d895aECB7c8af8c90bb7c3398dd9d21b9596bacf2c6e5711c00a5`).
