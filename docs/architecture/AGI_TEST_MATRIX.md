# AGI最小三構成 Test Matrix

- phase: `P2_AGI_MINIMUM_THREE_AUDIT`
- current executable gate: `test_agi_minimum_three_audit.py`

## 現行証拠

| Test ID | Primary claim | 実行対象 | 受入条件 | 現在 |
|---|---|---|---|---|
| `T-P0-FOUNDATION` | `CLAIM_P0_FOUNDATION` | `test_arc3_agi_foundation.py` | protocol/schema/verifier/checkpointが決定論的 | 実装済み |
| `T-P1-L0-REMOVAL` | `CLAIM_L0_SIX_RESPONSIBILITIES` | `test_each_single_role_removal_has_unique_functional_loss` | full set PASS、六single removalが固有FAIL | 実装済み |
| `T-P1-HDS-AUTHORITY` | `CLAIM_HDS_INTEGRATED_AUTHORITY` | `TrinityAuthorityTests` | forged/copied/replayed command/directive/resultを拒否 | 実装済み |
| `T-P1-M-PASSIVE` | `CLAIM_M_PASSIVE_PATH` | unauthorized/payload/single-use memory tests | HDS許可なしのmutationが不能 | 実装済み |
| `T-P1-OFFLINE` | `CLAIM_OFFLINE_ENVIRONMENT_BOUNDARY` | integration + sample runtime tests | OFFLINE限定、no-network、結果再観測 | 実装済み |
| `T-P2-AUDIT-GRAPH` | `CLAIM_P2_ROOT_AUDIT` | `test_agi_minimum_three_audit.py` | G1〜G5、全要素、全8 subset、claim証拠がaccountingされる | 本phaseで追加 |

## 後続phaseの固定試験

| Test ID | Primary claim | Phase | 必須反証条件 |
|---|---|---|---|
| `T-P3-DATASET-ACCOUNTING` | identity-free evidence corpus | P3 | source recordの欠落、重複、provenance断絶でFAIL |
| `T-P3-HOLDOUT-CONTAMINATION` | holdout分離 | P3 | 同一source/trajectory familyのtrain/holdout混入でFAIL |
| `T-P4-P-SCHEMA` | `CLAIM_P_IMPLEMENTED` | P4 | schema/version/digest/provenance/identity違反で拒否 |
| `T-P4-P-SWAP` | P-A/P-B交換 | P4 | L0変更、同一結果、authority変化でFAIL |
| `T-P4-C-STANDALONE` | `CLAIM_C_COMPLETE` | P4 | J/M呼出し、採否、write、emitがあればFAIL |
| `T-P4-L0-P-REMOVAL` | C必要性 | P4 | L0六責任またはP除去後もG1が残ればFAIL |
| `T-P5-J-STANDALONE` | `CLAIM_J_STANDALONE` | P5 | C/P/M参照、仮説/候補生成、実write/emitでFAIL |
| `T-P5-HDS-FRAME` | HDS適合 | P5 | X/R/Mc欠落非SUSPEND、hazard非veto、budget非STOPでFAIL |
| `T-P6-M-OPERATIONS` | `CLAIM_M_STANDALONE` | P6 | 必須operationいずれかの意味論欠落でFAIL |
| `T-P6-M-VERSION` | M version/rollback/archive | P6 | stale version受理、rollback不一致、archive混入でFAIL |
| `T-P7-PAIR-CJ` | `CLAIM_PAIRWISE_INSUFFICIENCY` | P7 | witnessが`NO_PERSISTENT_EXPERIENCE_CAUSALITY`以外ならFAIL |
| `T-P7-PAIR-CM` | `CLAIM_PAIRWISE_INSUFFICIENCY` | P7 | witnessが`NO_JUDGMENT_OR_AUTHORIZATION`以外ならFAIL |
| `T-P7-PAIR-JM` | `CLAIM_PAIRWISE_INSUFFICIENCY` | P7 | witnessが`NO_GENERATIVE_COMPUTATION`以外ならFAIL |
| `T-P8-TWO-CYCLE` | `CLAIM_TWO_CYCLE_CAUSALITY` | P8 | M update除去後もcycle 2差が残ればFAIL |
| `T-P8-PJM-ISOLATION` | `CLAIM_CAUSAL_ATTRIBUTION` | P8 | hidden global state、複数変数同時変更でFAIL |
| `T-P9-EIGHT-SUBSETS` | `CLAIM_MINIMUM_THREE` | P9 | proper subset PASSまたはfull set FAILでFAIL |
| `T-P9-EQUIVALENT-LEAK` | no functional equivalent | P9 | fallback/global callback/answer fixture代行でFAIL |
| `T-P10-ALL-SAMPLES` | `CLAIM_SAMPLE_COMPLETE` | P10 | 未完level、error、GAME_OVER、timeout、max-action停止でFAIL |
| `T-P10-DETERMINISM` | sample reproducibility | P10 | 同一release stateでtrace/result差があればFAIL |
| `T-P11-REBUILD` | `CLAIM_RELEASE_STATE_FIXED` | P11 | P0/J0/M0/dataset/compiler/package digest差でFAIL |

## claim昇格規則

1. Primary testが実行済みである。
2. 対応するnegative/removal testが実行済みである。
3. 実装path、入力、出力、state owner、authorityがtraceへ残る。
4. 禁止入力・機能等価物の漏れが0件である。
5. 未実行testをPASSとして記録しない。
