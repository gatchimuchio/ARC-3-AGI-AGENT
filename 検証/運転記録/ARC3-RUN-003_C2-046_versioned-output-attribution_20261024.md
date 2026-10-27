# ARC3 C2-046 versioned output attribution correction

Observed 2026-10-24 17:39 UTC. Kaggle CLI 2.2.4 ignored the `/version` suffix for kernel output and returned the latest session. The exact downloads were repeated with Kaggle CLI 2.2.5, whose version-specific behavior is recorded in the official Kaggle CLI changelog.

## Exact matched results

| Run | Mean score | Levels | Actions | Difference vs off v11 |
|---|---:|---:|---:|---:|
| off control v11 | 12.735567 | 6/21 | 480 | baseline |
| slim v12 | 15.848342 | 6/21 | 363 | score +3.112775; levels 0; actions -117 |
| slim v13 | 19.309156 | 7/21 | 389 | score +6.573589; levels +1; actions -91 |

All three runs use the same three public initial states. Both exact v12 and v13 notebook cell sources match the local C2-046 slim candidate after normalization. Each treatment is one pass over three games, and neither run won a game. Keep the candidate at HOLD; this pilot is too small to promote.

The earlier saved `slim` output with benchmark SHA `6535b524…369a72e` is version 13, not version 12. The exact v12 output is SHA `02b10aac…fd7e04`.

Kernel v14 has a different source (one changed cell) and its completed run is not part of C2-046. Kernel v15 also has a different source and remains RUNNING; its output was not read.

No competition submission or rerun was performed. No hidden solution or answer map was read or used.

Evidence JSON: `運用/証拠/ARC26-UNIFIED/ARC3-C2-046-versioned-output-attribution-20261024T1739Z.json`
