# C2-061 draft — ablate slim world-model memory

Status: **draft only; not pushed**. C2-059 version 28 remains active. This changes only `ARC3_MEMORY_SECTIONS` from `slim` to `off`; context 135,168, output reserve 16,384, seed 0, and other runtime metadata remain fixed. Current patched prompt logic explicitly supports `off`, so the ablation removes the persistent world-model block and its prompt guidance without retaining the stale instructions present in the historical v5 code.

Official v5 (public 23.86) also used `off`, but its Notebook has other code differences and its official output/input provenance is incomplete. Treat that only as motivation, not as evidence this setting caused the score. This candidate is a private ablation; it does not claim HDS prior-memory v0.4 is loaded or used and cannot be promoted without the v4 connection and reproducibility gates.

- Notebook: `出力/ARC3-RUN-003-local/C2-061-memory-sections-off/source/context135168-cap16k-memoryoff/submission.ipynb` (SHA256 `0e080dfeca3539e3d8dfa0a3766c8f997ae9f7756d21e3fb60f8fb722eeddedf`).
- Metadata: `出力/ARC3-RUN-003-local/C2-061-memory-sections-off/source/context135168-cap16k-memoryoff/kernel-metadata.json` (SHA256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`).
- Preflight: `運用/証拠/ARC26-UNIFIED/ARC3-C2-061-preflight-draft-20261025T145742Z.json` (SHA256 `73df7e27411c3323e859ae5d4b8d0df73c38cdccc866235b23e2cea63f5b51b1`).
- Gate: mean > C2-046 `19.309155943771326` and positive paired mean delta on the same three starts.
- Do not push while v28 runs; score v28 first.


## Historical score clue audit (2026-10-25T14:59:39Z)

The official v5 23.86 Notebook uses `ARC3_MEMORY_SECTIONS=off`; C2-046 local control uses `slim` and `LOCAL_ANALYZER_SEED=0`. They are not causal controls: ordered cell-source differences also include startup timeout, model-loader/readiness behavior, and offline action limits. C2-061 isolates only the mode change on current code, including the current prompt path for `off`; this remains a private ablation, with no claim about HDS prior-memory v0.4 use.

- Source audit: `運用/証拠/ARC26-UNIFIED/ARC3-C2-061-memory-mode-source-audit-20261025T145939Z.json` (SHA256 `58a902a7342e2ff69e404b0e18924a407efabf09c58fcc0fbf1da63f249a217c`).


## Prior controlled memory-mode evidence and sequencing correction (2026-10-25T15:02:17Z)

A previous C2-046 private/offline comparison already isolated `ARC3_MEMORY_SECTIONS`: the `off` and `slim` notebooks differ only in cell 5, their metadata and three public starts match, and the versioned output audit confirms the results. `off` scored 12.735567; two `slim` runs scored 15.848342 and 19.309156 (paired deltas +3.112775 and +6.573589 versus off). No arm won a game, so this is pilot evidence, not promotion.

C2-061 would repeat the mode comparison on a later 132 KiB context / 16 KiB output configuration (C2-046 used 128 KiB / 12 KiB). There is no evidence yet that this context/output change reverses the mode effect. Therefore C2-061 is **held and de-prioritized**; after C2-059 v28, inspect whether the 16,384-token output cap is still hit before choosing C2-060. No push or quota use.

- Audit: `運用/証拠/ARC26-UNIFIED/ARC3-C2-061-prior-ablation-review-20261025T150217Z.json` (SHA256 `70bf95862de115009805614212eb4f7fd8c8a2f5ebc49bb340e6f22747e42f98`).
- Source output attribution: `運用/証拠/ARC26-UNIFIED/ARC3-C2-046-versioned-output-attribution-20261024T1739Z.json` (SHA256 `8185542aee9e0d5f32b417b53d131792313d54c4e90a850ea37dc0919909672f`).
