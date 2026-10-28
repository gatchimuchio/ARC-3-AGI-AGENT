# C2-119 — same-state no-op avoidance screen

Observed: `2026-10-28T01:01:48Z`.

## Candidate and matched evaluation

The evaluation-only candidate enabled the existing generic policy flag that suppresses a previously no-op discrete action only when the exact same public board recurs and another legal action exists. ACTION6 remains exempt. The candidate used no game-ID branch, fixed action sequence, hidden state, or evaluator internals; production code, HDS, memory, and Notebook were not changed.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0.000000000 |
| Matched starts | 5/5 | — | — |
| Positive / negative / tied pairs | — | 0 / 0 / 5 | — |
| Levels / wins | — | 0 / 0 | — |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 9 | 0 |
| GAME_OVER | 6 | 6 | 0 |
| Illegal actions | — | 0 | — |
| Filter opportunities | — | 8 | — |

All five public starts matched. The predeclared `+0.01` mean-RHAE screen gate failed; all pairs tied, and no-op/action counts were unchanged. **Reject the candidate without 15-pair expansion or promotion.** This local screen does not establish a Kaggle score or learning effect.

## Official read-only checkpoint

The pinned local Kaggle CLI 2.2.5 history at `2026-10-28T01:01:48Z` reports submission `57688735` still `COMPLETE` at public `28.07` (private score not provided), with the description identifying legacy C2-046 v13; no exact Notebook slug/version is available. Submission `57577905` remains `COMPLETE` at `23.86`. `submission-limits --json` returned `numTotal=8`, `numAllowedNow=1`; the visible history has no submission dated today, so daily use is `0/1`. `kaggle quota` returned GPU `30.13h used / 0.00h remaining` and TPU `0.00h used / 20.00h remaining`, refresh `2026-10-31T00:00:00Z`. No submission, Competition Rerun, kernel push, or accelerator quota use occurred.

## Reproduction and evidence

- Runner: `検証/ARC3C2-119_same-state-noop-avoidance-screen.py` (SHA-256 `f5a38d2100dd9ccb924358ef0328d906a30831687fb4ed89a61330b4029f7488`).
- Control: `運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json` (SHA-256 `f9af6f91668055a49e9d9da164b70b5373b32c954b661a743e62adbe6ee97d61`).
- Full result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-119-same-state-noop-avoidance-result-20261028T010148Z.json` (SHA-256 `1ce8c1faa31c09cdfb7f77c2cf26c21e0501211a74af640b2f931536c5e5ee4d`).
- Screen evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-119-same-state-noop-avoidance-screen-20261028T010148Z.json`.
- Paired local screen runtime: `107.871` seconds.
- The v6 common and ARC3-specific three-point set, `AGENTS.md`, and `制御/現在状態.json` were rechecked before this work item; their hashes are recorded in screen evidence.
