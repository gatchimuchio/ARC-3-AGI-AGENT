# C2-124 — level-boundary action-value reset screen

Observed: `2026-10-28T02:15:23Z`.

## Candidate and paired screen

The online policy keeps action and coordinate-color reward counts across completed levels, although the public state has advanced. C2-124 tests a fresh bandit period after observed level progress: clear action visits/rewards, color visits/rewards, and the total-action UCB count. Keep tried-coordinate and board-novelty memory, and keep HDS memory. The reset uses only the public level-completion counter; it does not branch on game identity or use hidden state.

The evaluation-only candidate was compared against C2-111 on five matched public starts at seed 7, up to 80 actions including legal resets, using the same UCB/HDS settings.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0 |
| Matched starts | 5/5 | — | — |
| Positive / negative / tied pairs | — | 0 / 0 / 5 | — |
| Completed levels | 1 | 1 | 0 |
| Wins | 0 | 0 | 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 9 | 0 |
| GAME_OVER events | 6 | 6 | 0 |
| Level-boundary resets | — | 1 | — |
| Prior action observations cleared | — | 44 | — |
| Pairs with a changed action trace | — | 1/5 | — |
| Illegal actions | — | 0 | — |

The one level completion caused the first trace divergence at action index 44. The remaining pairs had no level-boundary reset. All scores and efficiency totals tied, so the predeclared `+0.01` score gate failed. **Reject at screen; do not expand or promote.** This local screen establishes neither an official score change nor a learning-transfer effect.

## Official read-only checkpoint

Pinned local Kaggle CLI 2.2.5 history, limits, and accelerator quota were read between `2026-10-28T02:11:58Z` and `2026-10-28T02:12:11Z`. Submission `57688735` remains `COMPLETE`, public `28.07`, private score not provided; its description identifies legacy C2-046 v13, with no exact Notebook slug/version. Submission `57577905` remains `COMPLETE` at `23.86`. Limits returned `numTotal=8`, `numAllowedNow=1`; no submission is dated today, so daily use is `0/1`. GPU quota is `30.13h used / 0.00h remaining`, TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No submission, Competition Rerun, kernel push, or quota use occurred.

## Reproduction and evidence

- Runner: `検証/ARC3C2-124_level-boundary-bandit-reset-screen.py` (SHA-256 `5f9aabb5ab94d53ecb4c087fd6c57500fd4b826420eed7ec13eed34669fccdbd`).
- Result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-124-level-boundary-bandit-reset-result-20261028T021523Z.json` (SHA-256 `90ae1423e4e69918a782ec2180dd560171565c2ec1fb2e0ff41101c483fa114c`).
- Baseline runner: `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13c18ddba7c5777c3e6c5038cc2a0ad00f5b16498e9ae08a0abfb3862ab76cd1`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Screen evidence and official quota snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-124-level-boundary-bandit-reset-evidence-20261028T021523Z.json`.
- Runtime: `85.525` seconds; five starts matched; illegal actions 0.
- Validation: `ruff check` and `py_compile` passed using the locked temporary v6 environment.
- Before this work, all six current v6 instruction documents, `AGENTS.md`, and `制御/現在状態.json` were hash-checked and unchanged.
