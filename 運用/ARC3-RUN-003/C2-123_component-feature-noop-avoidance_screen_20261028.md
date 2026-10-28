# C2-123 — component-feature no-op avoidance screen

Observed: `2026-10-28T01:58:49Z`.

## Candidate and paired screen

C2-119 suppressed an action only after it no-oped on the exact same board. C2-123 tests whether observed ACTION6 no-op feedback transfers across different boards through generic same-color component features. After an ACTION6 response with no visible cell change and no level progress, the episode-local policy marks the component context: component area band (`1`, `2–4`, `5–16`, `17+`), component share of its color's cells (`small`, `medium`, `large`), and board color-count band (`1`, `2`, `3+`). On later choices it skips unseen coordinates from marked contexts only when another unseen component of the selected color remains. If no alternative exists, it falls back to the existing coordinate selector. No game identifier, fixed action sequence, hidden state, or evaluator data is used.

The candidate was compared against C2-111's matched seed-7 baseline on five public starts, with up to 80 actions including legal resets per episode and the same exploration/HDS settings.

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
| Learned no-op contexts | — | 3 | — |
| No-op feedback events | — | 4 | — |
| Filter opportunities | — | 26 | — |
| Unseen cells suppressed | — | 234 | — |
| Illegal actions | — | 0 | — |

Despite 26 filter opportunities, no-op totals and RHAE did not change; every pair tied. The predeclared `+0.01` score gate failed. **Reject at screen; do not expand to 15 pairs or promote.** The full candidate action trace is not retained in this result, so exact divergence positions were not measured. This is local score evidence only and does not establish an official score or learning effect.

## Official read-only checkpoint

Pinned local Kaggle CLI 2.2.5 history, limits, and accelerator quota were read between `2026-10-28T01:58:36Z` and `2026-10-28T01:58:49Z`. Submission `57688735` remains `COMPLETE`, public `28.07`, private score not provided; the description identifies legacy C2-046 v13 but gives no exact Notebook slug/version. Submission `57577905` remains `COMPLETE` at `23.86`. Limits returned `numTotal=8`, `numAllowedNow=1`; no submission is dated today, so daily use is `0/1`. GPU quota is `30.13h used / 0.00h remaining`, TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No submission, Competition Rerun, kernel push, or quota use occurred.

## Reproduction and evidence

- Runner: `検証/ARC3C2-123_component-feature-noop-avoidance-screen.py` (SHA-256 `9942d990c95b12a064935ffb787c7a26b80f799af125840fbc6593e93765897a`).
- Result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-123-component-feature-noop-avoidance-result-20261028T015849Z.json` (SHA-256 `8b01c2df29e58997a946146a95cade62d3a7ae47be2e7715e502fda9c2227bb1`).
- Baseline runner: `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13c18ddba7c5777c3e6c5038cc2a0ad00f5b16498e9ae08a0abfb3862ab76cd1`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Screen evidence and official quota snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-123-component-feature-noop-avoidance-evidence-20261028T015849Z.json`.
- Runtime: `94.765` seconds; all five starts matched; illegal actions 0.
- Validation: `ruff check` and `py_compile` passed using the locked temporary v6 environment.
- Before this work, the current v6 common/ARC3 three-point set, `AGENTS.md`, and `制御/現在状態.json` hashes were rechecked and matched the recorded values.
