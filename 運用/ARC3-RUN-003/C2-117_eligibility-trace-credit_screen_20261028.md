# C2-117 — short eligibility trace for level-progress reward

Observed: `2026-10-28T00:37:15.226Z`.

## Candidate and comparison

The evaluation-only policy keeps an eligibility trace of the previous three actions within a level. When public state reports level progress, it adds half-scale credit from the level-progress reward to those actions, decaying by `0.5` for each action of distance. The trace clears on level progress or terminal state. This tests delayed credit assignment for sparse progress feedback without using game IDs or hidden state.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0 |
| Matched starts | 5 | 5 | 5/5 |
| Positive / negative / tied pairs | — | — | 0 / 0 / 5 |
| Levels / wins | — | — | 0 / 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 9 | 0 |
| GAME_OVER | 6 | 6 | 0 |
| Illegal actions | — | 0 | — |
| Progress events / credited prior actions | — | 1 / 3 | — |
| Propagated reward | — | 1.75 | — |

All five starts matched. The predeclared `+0.01` mean-RHAE screen gate failed; observed action traces and score were unchanged. **Reject after screen; do not expand to 15 pairs or promote.** Learning benefit remains unmeasured. The production agent, HDS, memory, and Notebook were not changed. No Kaggle kernel push or official submission occurred.

The first harness invocation failed before evaluation with `NameError: name 'ComponentPruningPolicy' is not defined` because the copied runner retained a stale class return name. The runner was corrected to return `EligibilityTracePolicy`; the completed second invocation is the only result included in the table.

## Reproduction and evidence

Runner: `検証/ARC3C2-117_eligibility-trace-credit-screen.py` (SHA-256 `E0BB858D81FBD2AB218A7BBEB6BB77E61969905FD4F3C69F0019307CF6C6C71A`). It uses `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13C18DDBA7C5777C3E6C5038CC2A0AD00F5B16498E9AE08A0ABFB3862AB76CD1`) and the frozen C2-111 control evidence.

Full paired result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-117-eligibility-trace-credit-result-20261028T003715Z.json` (SHA-256 `03B86508E909E174ACCE9C06340E60DB0AF9334D1844A80900DAE2E5E47E5A05`). Screen evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-117-eligibility-trace-credit-screen-20261028T003715Z.json` (SHA-256 `EBADC7BF4C54F3CA458175ED5422D700ED8DC7A4E1DB484663CADDADA586B5FF`).

The v6 common and ARC3-specific three-point set, `AGENTS.md`, and `制御/現在状態.json` were rechecked before this work item. Their hashes are in the screen evidence; protected files remain unchanged.