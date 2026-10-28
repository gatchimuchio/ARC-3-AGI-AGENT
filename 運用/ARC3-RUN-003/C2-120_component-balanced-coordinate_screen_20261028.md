# C2-120 — connected-component-balanced coordinate sampling

Observed: `2026-10-28T01:18:49Z`.

## Hypothesis and intervention

The current ACTION6 policy chooses an unseen cell uniformly from all unseen cells of a selected color, so a large connected region receives probability in proportion to its number of cells. The evaluation-only candidate instead chooses uniformly among 4-neighbor same-color connected components that contain unseen cells, then uniformly within the selected component. It is a generic sampling rule using the visible board only; no game-ID branch, fixed action sequence, hidden state, or evaluator internals are used.

A five-start seed-7 screen passed the predeclared `+0.01` RHAE threshold: mean `0.238095238→0.871365559` (`Δ +0.633270321`), with 1 positive and 4 tied pairs, levels/wins unchanged, and no-ops `9→15`. Per protocol, the same candidate was expanded to the full 15 matched public-dev starts across seeds 7, 31, and 73.

## Full 15-pair result

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.240596656 | 0.473155298 | +0.232558642 |
| Matched starts | 15/15 | — | — |
| Positive / negative / tied score pairs | — | 2 / 1 / 12 | — |
| Levels completed | — | — | -1 |
| Wins | — | — | 0 |
| Actions | 1200 | 1200 | 0 |
| No-ops | 35 | 44 | 9 |
| GAME_OVER events | 18 | 16 | -2 |
| Illegal actions | — | 0 | — |

| Policy seed | Pairs | Mean RHAE delta | Positive / negative / tied | Level delta | No-op delta |
|---:|---:|---:|---:|---:|---:|
| 7 | 5 | 0.633270321 | 1/0/4 | 0 | +6 |
| 31 | 5 | 0.401112968 | 1/0/4 | 0 | +3 |
| 73 | 5 | -0.336707364 | 0/1/4 | -1 | +0 |

The mean RHAE delta is positive, but the full evaluation loses one completed level overall and has only 2 positive pairs, 1 negative pair, and 12 ties. No-op count also rises by 9. The predeclared nonnegative-level gate therefore fails. **Reject C2-120 without holdout or promotion.** The seed-7 screen signal did not generalize across the matched seed set; it is not a Kaggle score or evidence of learning effectiveness.

## Official read-only checkpoint

Pinned Kaggle CLI 2.2.5 history was read between `2026-10-28T01:18:40Z` and `2026-10-28T01:18:49Z`. Submission `57688735` remains `COMPLETE` at public `28.07`, private score not provided; the description identifies legacy C2-046 v13, with no exact Notebook slug/version. Submission `57577905` remains `COMPLETE` at `23.86`. Submission limits returned `numTotal=8`, `numAllowedNow=1`; history contains no submission dated today, so daily use is `0/1`. Accelerator quota is GPU `30.13h used / 0.00h remaining`, TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No submission, Competition Rerun, kernel push, or accelerator quota use occurred.

## Reproduction and evidence

- Screen runner: `検証/ARC3C2-120_component-balanced-coordinate-screen.py` (SHA-256 `e490f73a321c4800f3044d1e685f083e1a66dc0bc67dca82aa14e4661940f369`); result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-120-component-balanced-screen-result-20261028T011849Z.json` (SHA-256 `05b6219b1c770a5642f38ad15d59a209ff0ebd2ff15b0f352aa4d5da79b2df24`).
- Full evaluator: `検証/ARC3C2-120_component-balanced-coordinate-full-evaluation.py` (SHA-256 `1072ad61c513032c720e5326c897cd11b422ce4f2b81dcb0e98bb9489133ec5a`); result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-120-component-balanced-full15-result-20261028T011849Z.json` (SHA-256 `1b7acd12534cfc723970ec96a620a5351527f302254ba876a30e4889be422821`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Screen evidence and official quota snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-120-component-balanced-screen-evidence-20261028T011849Z.json`.
- Full evaluation runtime: `265.517` seconds; 15/15 starting observations matched; illegal actions 0.
- Before C2-120, the v6 common/ARC3 three-point set, `AGENTS.md`, and `制御/現在状態.json` were rechecked and matched their recorded SHA-256 values.
