# C2-121 — square-root weighted connected-component sampling

Observed: `2026-10-28T01:30:33Z`.

## Candidate and screen

C2-120's equal-probability component sampler had a positive 5-start seed-7 screen but failed the full 15-pair nonnegative-level gate. C2-121 tests a softer, generic weighting: select each visible 4-neighbor same-color component with probability proportional to the square root of its unseen-cell count, then choose an unseen cell uniformly within it. This interpolates between cell-uniform and component-uniform sampling without a game-ID branch, fixed action sequence, hidden state, or evaluator internals.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.000000000 | -0.238095238 |
| Matched starts | 5/5 | — | — |
| Positive / negative / tied pairs | — | 0 / 1 / 4 | — |
| Levels / wins | — | — | -1 / 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 17 | 8 |
| GAME_OVER | 6 | 5 | -1 |
| Component-selected unseen cells | — | 237 | — |
| Illegal actions | — | 0 | — |

All five starts matched. Mean RHAE regressed by `0.238095238`; one pair lost a level, no-ops rose by 8, and no pair improved. **Reject at screen; do not expand to 15 pairs or promote.** This is a local result, not an official Kaggle score or learning-effect result.

The first harness attempt failed before score execution with `NameError: name 'ComponentBalancedPolicy' is not defined`. The second invocation completed but read the prior experiment's stats key when computing only the aggregate selection count; its per-pair score rows were not used as the final result. After fixing the class return and metric key, the third invocation completed and is the result above.

## Official read-only checkpoint

Pinned Kaggle CLI 2.2.5 was read between `2026-10-28T01:30:24Z` and `2026-10-28T01:30:33Z`. Submission `57688735` remains `COMPLETE` at public `28.07`, private score not provided; the description identifies legacy C2-046 v13, with no exact Notebook slug/version. Submission `57577905` remains `COMPLETE` at `23.86`. Limits returned `numTotal=8`, `numAllowedNow=1`; history has no submission dated today, so daily use is `0/1`. Accelerator quota is GPU `30.13h used / 0.00h remaining`, TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No submission, Competition Rerun, kernel push, or quota use occurred.

## Reproduction and evidence

- Runner: `検証/ARC3C2-121_sqrt-component-weighted-coordinate-screen.py` (SHA-256 `23d284f136f3e89348619628389aa51131be0a86db7cd4645b4462f676e65de3`).
- Result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-121-sqrt-component-weighted-screen-result-20261028T013033Z.json` (SHA-256 `40613719f8dad3b196f7a5a36c0d7bce538b8967da2f8247d17efc439b3911d1`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Screen evidence and official quota snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-121-sqrt-component-weighted-screen-evidence-20261028T013033Z.json`.
- Runtime: `83.131` seconds; 5/5 starting observations matched; illegal actions 0.
- Before this work, the current v6 common/ARC3 three-point set, `AGENTS.md`, and `制御/現在状態.json` hashes were rechecked and matched the recorded values.
