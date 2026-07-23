# AGI最小三構成 P9 Conformance Report

- schema: `agi-minimum-three-certificate-v1`
- audit digest: `6885c1c0a64471a656e5a557a6344d1287d3bcdb3eff7df3b1650921559fbc4f`
- full set pass: `true`
- proper subset pass count: `0`
- single removal fail count: `3`
- pair subset fail count: `3`
- two-cycle causality pass: `true`
- functional-equivalent leak count: `0`

| subset | G1 | G2 | G3 | G4 | G5 | overall | witness |
|---|---|---|---|---|---|---|---|
| {} | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | `NO_COMPUTE_JUDGMENT_OR_MEMORY` |
| {C} | PASS | FAIL | FAIL | FAIL | FAIL | FAIL | `NO_JUDGMENT_OR_MEMORY` |
| {J} | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION_OR_MEMORY` |
| {M} | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION_OR_JUDGMENT` |
| {C,J} | PASS | PASS | FAIL | FAIL | PARTIAL | FAIL | `NO_PERSISTENT_EXPERIENCE_CAUSALITY` |
| {C,M} | PASS | FAIL | PASS | FAIL | FAIL | FAIL | `NO_JUDGMENT_OR_AUTHORIZATION` |
| {J,M} | FAIL | PASS | PASS | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION` |
| {C,J,M} | PASS | PASS | PASS | PASS | PASS | PASS | `-` |

## Conformance conclusion

定義された機能的AGIクラスでは、C・J・Mのfull setだけがG1〜G5を満たす。
proper subset 7件はすべて実行後に固有の不足でFAILし、欠落主体の機能等価物漏れは0件である。

このcertificateは定義済み機能義務と固定fixture上の構成最小性を証明する。
未知ARC taskの汎化、全sample攻略、公式評価性能を証明しない。
