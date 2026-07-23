# AGI最小三構成 Test Matrix

- current phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- last completed phase: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`
- current executable regression gates:
  `test_agi_minimum_three_audit.py`,
  `test_evidence_compiler.py`,
  `test_p3_evidence_dataset.py`,
  `test_instruction_body_compiler.py`,
  `test_compute_subject_p4.py`,
  `test_judgment_subject_p5.py`,
  `test_memory_subject_p6.py`,
  `test_pairwise_subject_p7.py`,
  `test_trinity_two_cycle_p8.py`,
  `test_minimum_three_certificate_p9.py`

## 現行証拠

| Test ID | Primary claim | 実行対象 | 受入条件 | 現在 |
|---|---|---|---|---|
| `T-P0-FOUNDATION` | `CLAIM_P0_FOUNDATION` | `test_arc3_agi_foundation.py` | protocol/schema/verifier/checkpointが決定論的 | 実装済み |
| `T-P1-L0-REMOVAL` | `CLAIM_L0_SIX_RESPONSIBILITIES` | `test_each_single_role_removal_has_unique_functional_loss` | full set PASS、六single removalが固有FAIL | 実装済み |
| `T-P1-HDS-AUTHORITY` | `CLAIM_HDS_INTEGRATED_AUTHORITY` | `TrinityAuthorityTests` | forged/copied/replayed command/directive/resultを拒否 | 実装済み |
| `T-P1-M-PASSIVE` | `CLAIM_M_PASSIVE_PATH` | unauthorized/payload/single-use memory tests | HDS許可なしのmutationが不能 | 実装済み |
| `T-P1-OFFLINE` | `CLAIM_OFFLINE_ENVIRONMENT_BOUNDARY` | integration + sample runtime tests | OFFLINE限定、no-network、結果再観測 | 実装済み |
| `T-P2-AUDIT-GRAPH` | `CLAIM_P2_ROOT_AUDIT` | `test_agi_minimum_three_audit.py` | G1〜G5、全要素、全8 subset、claim証拠がaccountingされる | 本phaseで追加 |
| `T-P3-DATASET-ACCOUNTING` | `CLAIM_P3_EVIDENCE_COMPILER` | `test_p3_evidence_dataset.py` | 730/730 source、parse error 0、provenance往復、C/J/M fixture分離 | 実装・実行済み |
| `T-P3-HOLDOUT-CONTAMINATION` | `CLAIM_P3_EVIDENCE_COMPILER` | `test_p3_evidence_dataset.py` | family/structure/action-mechanism groupが単一splitだけへ属する | 実装・実行済み |
| `T-P3-COMPILER-DETERMINISM` | `CLAIM_P3_EVIDENCE_COMPILER` | `test_evidence_compiler.py` + full rebuild | seed 0で全12出力がbyte一致 | 実装・実行済み |
| `T-P4-P-SCHEMA` | `CLAIM_P_IMPLEMENTED` | `test_instruction_body_compiler.py` | schema/version/digest/provenance/identity違反を拒否 | 実装・実行済み |
| `T-P4-P-SWAP` | P-A/P-B交換 | `test_compute_subject_p4.py` | 同一L0で交換、各決定的、P差で結果差 | 実装・実行済み |
| `T-P4-C-STANDALONE` | `CLAIM_C_COMPLETE` | `test_compute_subject_p4.py` | G1出力を生成しJ/M/write/emitを行わない | 実装・実行済み |
| `T-P4-L0-P-REMOVAL` | C必要性 | `test_compute_subject_p4.py` | L0六責任/P/Cの8除去が固有FAIL | 実装・実行済み |
| `T-P5-J-STANDALONE` | `CLAIM_J_STANDALONE` | `test_judgment_subject_p5.py` | C/P/Mなしで全判断statusと非effect境界 | 実装・実行済み |
| `T-P5-HDS-FRAME` | HDS適合 | `test_judgment_subject_p5.py` | 676 fixture、X/R/Mc、hazard、budget、rollback、除去 | 実装・実行済み |
| `T-P6-M-OPERATIONS` | `CLAIM_M_STANDALONE` | `test_memory_subject_p6.py` | 全15操作、687 fixture、G1/G2非代行、M除去 | 実装・実行済み |
| `T-P6-M-VERSION` | M version/rollback/archive | `test_memory_subject_p6.py` | stale拒否、指定版rollback、active/archive分離、query決定性 | 実装・実行済み |
| `T-P7-PAIR-CJ` | `CLAIM_PAIRWISE_INSUFFICIENCY` | `test_pairwise_subject_p7.py` | C/J実機能後にM/G3/G4だけが固有witnessでFAIL | 実装・実行済み |
| `T-P7-PAIR-CM` | `CLAIM_PAIRWISE_INSUFFICIENCY` | `test_pairwise_subject_p7.py` | C/M実機能後にJ判断・許可が固有witnessでFAIL | 実装・実行済み |
| `T-P7-PAIR-JM` | `CLAIM_PAIRWISE_INSUFFICIENCY` | `test_pairwise_subject_p7.py` | J/M実機能後にC生成計算が固有witnessでFAIL | 実装・実行済み |
| `T-P8-TWO-CYCLE` | `CLAIM_TWO_CYCLE_CAUSALITY` | `test_trinity_two_cycle_p8.py` | cycle 1 post-Mをcycle 2が引用しbehavioral delta | 実装・実行済み |
| `T-P8-PJM-ISOLATION` | `CLAIM_CAUSAL_ATTRIBUTION` | `test_trinity_two_cycle_p8.py` | P/J/M一因子だけを変え、固有出力だけが変化 | 実装・実行済み |
| `T-P9-EIGHT-SUBSETS` | `CLAIM_MINIMUM_THREE` | `test_minimum_three_certificate_p9.py` | 8 subsetを重複なく実行しproper subset 7件FAIL、full set 1件PASS | 実装・実行済み |
| `T-P9-EQUIVALENT-LEAK` | no functional equivalent | `test_minimum_three_certificate_p9.py` | 欠落C/J/Mの生成・判断・保持出力、field、fallback代行が0 | 実装・実行済み |
| `T-P9-CERTIFICATE-REBUILD` | `CLAIM_MINIMUM_THREE` | `test_minimum_three_certificate_p9.py` | 5 artifactの内容・digest・再生成byteが一致 | 実装・実行済み |

## 後続phaseの固定試験

| Test ID | Primary claim | Phase | 必須反証条件 |
|---|---|---|---|
| `T-P10-ALL-SAMPLES` | `CLAIM_SAMPLE_COMPLETE` | P10 | 未完level、error、GAME_OVER、timeout、max-action停止でFAIL |
| `T-P10-DETERMINISM` | sample reproducibility | P10 | 同一release stateでtrace/result差があればFAIL |
| `T-P11-REBUILD` | `CLAIM_RELEASE_STATE_FIXED` | P11 | P0/J0/M0/dataset/compiler/package digest差でFAIL |

## claim昇格規則

1. Primary testが実行済みである。
2. 対応するnegative/removal testが実行済みである。
3. 実装path、入力、出力、state owner、authorityがtraceへ残る。
4. 禁止入力・機能等価物の漏れが0件である。
5. 未実行testをPASSとして記録しない。
