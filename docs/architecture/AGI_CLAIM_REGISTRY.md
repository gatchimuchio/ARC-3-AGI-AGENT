# AGI最小三構成 Claim Registry

- current phase: `P5_JUDGMENT_SUBJECT_J`
- last completed phase: `P4_COMPUTE_SUBJECT_C`
- rule: 実装path、実行test、除去証人が揃わないclaimを`SUPPORTED`にしない

| Claim ID | 主張 | 状態 | primary evidence | 反証・不足 | 次phase |
|---|---|---|---|---|---|
| `CLAIM_P0_FOUNDATION` | typed IR、schema、verifier、checkpoint、authority foundationが存在する | `SUPPORTED` | `tests/unit/test_arc3_agi_foundation.py` | AGI三主体完成は含まない | 保持 |
| `CLAIM_P1_EXECUTION_MECHANISM` | 六L0責任、HDS authority、受動M暫定経路、OFFLINE action/re-observationが動く | `SUPPORTED` | `tests/integration/test_offline_sample_runner.py` | P、standalone J/M、G4は含まない | 回帰 |
| `CLAIM_L0_SIX_RESPONSIBILITIES` | 六責任がcallableで各single-removalが固有FAILになる | `SUPPORTED` | `test_each_single_role_removal_has_unique_functional_loss`, `test_full_p4_removal_audit_covers_l0_p_and_c` | P/J/M全体完成は含まない | 回帰 |
| `CLAIM_HDS_INTEGRATED_AUTHORITY` | integrated cycleでcommand/decision/write/emit/finalizeをHDSだけが承認する | `SUPPORTED` | `TrinityAuthorityTests`のcommand/directive/result攻撃試験群 | standalone J成立を含まない | P5 |
| `CLAIM_OFFLINE_ENVIRONMENT_BOUNDARY` | non-OFFLINE、未承認step、network経路を拒否する | `SUPPORTED` | `test_offline_sample_runner.py`, `test_offline_sample_runtime.py` | 全level攻略を含まない | P10 |
| `CLAIM_M_PASSIVE_PATH` | 未承認mutationを拒否し、承認済みADD-like更新を保持する | `SUPPORTED` | `test_memory_is_passive_and_rejects_unapproved_write` | full G3ではない | P6 |
| `CLAIM_P2_ROOT_AUDIT` | 全設計要素、claim、test、gap、順序がaccountingされる | `SUPPORTED` | `test_agi_minimum_three_audit.py` | runtime能力増加のclaimではない | P3 |
| `CLAIM_P3_EVIDENCE_COMPILER` | 全730 sourceをaccountingし、identity-free C/J/M fixture、provenance、holdoutを決定的に生成する | `SUPPORTED` | `test_evidence_compiler.py`, `test_p3_evidence_dataset.py` | P0/J0/M0、P-A/P-B、汎化性能は含まない | 回帰 |
| `CLAIM_P_IMPLEMENTED` | executable instruction body Pが存在する | `SUPPORTED` | `test_instruction_body_compiler.py` | P-A/P-Bの性能・P0 release固定は含まない | P11 |
| `CLAIM_C_COMPLETE` | `C=Execute(L0,P)`がG1を単独で満たす | `SUPPORTED` | `test_compute_subject_p4.py` | G2/G3/G4、sample攻略、汎化は含まない | 回帰 |
| `CLAIM_J_STANDALONE` | C/MなしでHDS FrameからG2を満たす | `UNSUPPORTED` | なし | standalone Frame API/fixture suiteなし | P5 |
| `CLAIM_M_STANDALONE` | C/Jなしで全memory operationを満たす | `UNSUPPORTED` | なし | operation semantics、conflict、rollback、archive不足 | P6 |
| `CLAIM_PAIRWISE_INSUFFICIENCY` | 三pairが固有witnessでAGI義務を閉じない | `UNSUPPORTED` | なし | pair harnessなし | P7 |
| `CLAIM_TWO_CYCLE_CAUSALITY` | cycle 1のM更新がcycle 2のC/Jを変える | `UNSUPPORTED` | なし | M-only controlled causal testなし | P8 |
| `CLAIM_CAUSAL_ATTRIBUTION` | P-only/J-only/M-only変更の効果を個別帰属できる | `UNSUPPORTED` | なし | causal isolation harnessなし | P8 |
| `CLAIM_MINIMUM_THREE` | 全8 subsetでfull setのみPASSする | `UNSUPPORTED` | なし | executable subset certificateなし | P9 |
| `CLAIM_SAMPLE_COMPLETE` | 全sample game/all levelを完全攻略する | `UNSUPPORTED` | なし | 現在は25 game各1 action経路だけ | P10 |
| `CLAIM_GENERALIZATION` | identity-free holdoutで未知構造へ汎化する | `UNSUPPORTED` | なし | P-B holdout BCEは退行なしだが、未知sample構造の攻略証明ではない | P10 |
| `CLAIM_RELEASE_STATE_FIXED` | P0/J0/M0/code/dependency/environmentから再現できる | `UNSUPPORTED` | なし | release manifestとfull regressionなし | P11 |
| `CLAIM_OFFICIAL_READY` | COMPETITION/Kaggleへ進める | `REJECTED` | なし | P9〜P11未完、current request外 | P12以降 |

## 禁止claim

次の表現は、対応claimが`SUPPORTED`になるまで使用しない。

- AGI完成
- 最小三構成を証明済み
- C/J/Mが単独成立済み
- 二周期学習成立済み
- 全sample攻略済み
- 汎化済み
- 公式提出可能
