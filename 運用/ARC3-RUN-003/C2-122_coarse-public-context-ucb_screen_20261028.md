# C2-122 — coarse public-context UCB screen

Observed: `2026-10-28T01:45:30Z`.

## Candidate and paired screen

C2-106's exact-board contextual UCB only had 3/15 action-trace divergences and no score effect. C2-122 pooled action-visit counts by a compact set of generic public descriptors within each episode: completed levels, legal action set, color-count band, majority-occupancy band, board-area band, and board-aspect band. It added a contextual UCB bonus to discrete actions; ACTION6 kept its existing coordinate exploration. The policy resets for each game. No game identifier, fixed action sequence, hidden state, or evaluator data is used for action selection.

The candidate was compared against C2-111's matched seed-7 baseline on five public starts, with up to 80 actions including legal resets per episode and the same exploration/HDS settings.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0 |
| Matched starts | 5/5 | — | — |
| Positive / negative / tied pairs | — | 0 / 0 / 5 | — |
| Completed levels | 1 | 1 | 0 |
| Wins | 0 | 0 | 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 11 | +2 |
| GAME_OVER events | 6 | 6 | 0 |
| Contextual bonus applications | — | 676 | — |
| Context keys observed (summed per episode) | — | 6 | — |
| Illegal actions | — | 0 | — |

The `+0.01` RHAE gate failed. **Reject at screen; do not expand to 15 pairs or promote.** The candidate changed the no-op count by two but did not improve any paired score. The score result is local evidence only; it does not establish an official score or learning effect. The result JSON does not retain full candidate action traces, so the exact divergence positions were not measured.

## Official read-only checkpoint

Pinned local Kaggle CLI 2.2.5 history and limits were read between `2026-10-28T01:44:57Z` and `2026-10-28T01:45:09Z`. Submission `57688735` remains `COMPLETE`, public `28.07`, private score not provided; its description identifies legacy C2-046 v13 but gives no exact Notebook slug/version. Submission `57577905` remains `COMPLETE` at `23.86`. Limits returned `numTotal=8`, `numAllowedNow=1`; no submission is dated today, so daily use is `0/1`. Accelerator quota is GPU `30.13h used / 0.00h remaining`, TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No official submission, Competition Rerun, kernel push, or quota use occurred.

## Reproduction and evidence

- Runner: `検証/ARC3C2-122_coarse-public-context-ucb-screen.py` (SHA-256 `51fa2ba4b83ace999245770cf0f11b72b3859f3ee704c703befeb41ab8f30bfb`).
- Result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-122-coarse-public-context-ucb-result-20261028T014530Z.json` (SHA-256 `a9929a99c51f77dc008e31fc05924111d16c3aa5f5e2fa0c6a305cbcab46b06b`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Baseline runner: `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13c18ddba7c5777c3e6c5038cc2a0ad00f5b16498e9ae08a0abfb3862ab76cd1`).
- Screen evidence and official quota snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-122-coarse-public-context-ucb-evidence-20261028T014530Z.json`.
- Runtime: `87.584` seconds; all five starts matched; 676 contextual bonus applications; illegal actions 0.
- Validation: `ruff check` and `py_compile` passed using the locked temporary v6 environment.
- Before this work, the current v6 common/ARC3 three-point set, `AGENTS.md`, and `制御/現在状態.json` hashes were rechecked and matched the recorded values.
