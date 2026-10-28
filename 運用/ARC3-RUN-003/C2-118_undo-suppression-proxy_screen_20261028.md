# C2-118 — ACTION7 suppression proxy screen

Observed: `2026-10-28T00:46:42.523Z`.

## Candidate and comparison

This is an evaluation-only proxy for the unrun C2-114 Undo exposure change: while the observation is `NOT_FINISHED`, remove legal ACTION7 from the policy-visible action set before HDS ranking and UCB selection, then restore the original observation for validating the returned action. The SDK still considers ACTION7 legal; this policy simply does not select it. This does **not** reproduce the exact notebook `EXPOSE_UNDO` edit, and it is not evidence about that exact candidate. No game ID or hidden state is used.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0 |
| Matched starts | 5 | 5 | 5/5 |
| Positive / negative / tied pairs | — | — | 0 / 0 / 5 |
| Levels / wins | — | — | 0 / 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 10 | +1 |
| GAME_OVER | 6 | 6 | 0 |
| Illegal actions | — | 0 | — |
| ACTION7-filtered observations / candidate ACTION7 selections | — | 78 / 0 | — |

All five starts matched. The predeclared `+0.01` mean-RHAE screen gate failed, and candidate no-ops increased by one. **Reject this local proxy without expansion or promotion.** The aggregate control file does not retain baseline ACTION7 counts, so this report does not compare those counts. The exact C2-114 `EXPOSE_UNDO=off` Notebook candidate remains unrun pending GPU quota; the proxy result does not reject that exact candidate. No production agent, HDS, memory, or Notebook was changed. No Kaggle kernel push or official submission occurred.

The first harness invocation failed before evaluation with `NameError: name 'ComponentPruningPolicy' is not defined`. After correcting the stale class name, the second invocation failed before evaluation because `_HDSRankingPolicy.選ぶ()` does not accept the `HDS優先作用番号群` keyword. The override was corrected to match its one-argument signature; only the third invocation produced the result above.

## Reproduction and evidence

Runner: `検証/ARC3C2-118_undo-suppression-proxy-screen.py` (SHA-256 `103A311DCCDBE192C3D27B814CD4798315930AC078D9B15DD8A48DEB7528F630`). It uses `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13C18DDBA7C5777C3E6C5038CC2A0AD00F5B16498E9AE08A0ABFB3862AB76CD1`) and the frozen C2-111 control evidence.

Full paired result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-118-undo-suppression-proxy-result-20261028T004642Z.json` (SHA-256 `1B9D7720D16FD28A52E71B3B2A86B253EA23362C879F1D14D9E8F499EF7E1655`). Screen evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-118-undo-suppression-proxy-screen-20261028T004642Z.json` (SHA-256 `938EA6296B4261621B6E7E7B8F948A1875A969F359F121B70F94D889B24DF9AD`).

The v6 common and ARC3-specific three-point set, `AGENTS.md`, and `制御/現在状態.json` were rechecked before this work item. Their hashes are in the screen evidence; protected files remain unchanged.