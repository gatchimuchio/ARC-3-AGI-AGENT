# AGI最小三構成 Claim Registry

- current phase: none (`P12_NOT_STARTED_CURRENT_REQUEST_OUT_OF_SCOPE`)
- last completed phase: `P11_RELEASE_STATE_FREEZE`
- rule: 実装path、実行test、除去証人が揃わないclaimを`SUPPORTED`にしない

| Claim ID | 主張 | 状態 | primary evidence | 反証・不足 | 次phase |
|---|---|---|---|---|---|
| `CLAIM_P0_FOUNDATION` | typed IR、schema、verifier、checkpoint、authority foundationが存在する | `SUPPORTED` | `tests/unit/test_arc3_agi_foundation.py` | AGI三主体完成は含まない | 保持 |
| `CLAIM_P1_EXECUTION_MECHANISM` | 六L0責任、HDS authority、受動M暫定経路、OFFLINE action/re-observationが動く | `SUPPORTED` | `tests/integration/test_offline_sample_runner.py` | P、standalone J/M、G4は含まない | 回帰 |
| `CLAIM_L0_SIX_RESPONSIBILITIES` | 六責任がcallableで各single-removalが固有FAILになる | `SUPPORTED` | `test_each_single_role_removal_has_unique_functional_loss`, `test_full_p4_removal_audit_covers_l0_p_and_c` | P/J/M全体完成は含まない | 回帰 |
| `CLAIM_HDS_INTEGRATED_AUTHORITY` | integrated cycleでcommand/decision/write/emit/finalizeをHDSだけが承認する | `SUPPORTED` | `TrinityAuthorityTests`と`test_integrated_kernel_uses_standalone_judgment_result` | full M/Trinity成立を含まない | 回帰 |
| `CLAIM_OFFLINE_ENVIRONMENT_BOUNDARY` | non-OFFLINE、未承認step、network経路を拒否する | `SUPPORTED` | `test_offline_sample_runner.py`, `test_offline_sample_runtime.py` | 全level攻略を含まない | P10 |
| `CLAIM_M_PASSIVE_PATH` | 未承認mutationを拒否し、承認済みmutationを保持する | `SUPPORTED` | `test_memory_is_passive_and_rejects_unapproved_write`, `test_memory_subject_p6.py` | G4やpair/Trinityは含まない | 回帰 |
| `CLAIM_P2_ROOT_AUDIT` | 全設計要素、claim、test、gap、順序がaccountingされる | `SUPPORTED` | `test_agi_minimum_three_audit.py` | runtime能力増加のclaimではない | P3 |
| `CLAIM_P3_EVIDENCE_COMPILER` | 全730 sourceをaccountingし、identity-free C/J/M fixture、provenance、holdoutを決定的に生成する | `SUPPORTED` | `test_evidence_compiler.py`, `test_p3_evidence_dataset.py` | P0/J0/M0、P-A/P-B、汎化性能は含まない | 回帰 |
| `CLAIM_P_IMPLEMENTED` | executable instruction body Pが存在する | `SUPPORTED` | `test_instruction_body_compiler.py` | 未知task汎化は含まない | 回帰 |
| `CLAIM_C_COMPLETE` | `C=Execute(L0,P)`がG1を単独で満たす | `SUPPORTED` | `test_compute_subject_p4.py` | G2/G3/G4、sample攻略、汎化は含まない | 回帰 |
| `CLAIM_J_STANDALONE` | C/P/MなしでHDS FrameからG2を満たす | `SUPPORTED` | `test_judgment_subject_p5.py` | G1/G3/G4、effect実行、sample攻略は含まない | 回帰 |
| `CLAIM_M_STANDALONE` | C/Jなしで全memory operationを満たす | `SUPPORTED` | `test_memory_subject_p6.py` | G1/G2/G4、pair、sample攻略は含まない | 回帰 |
| `CLAIM_PAIRWISE_INSUFFICIENCY` | 三pairが固有witnessでAGI義務を閉じない | `SUPPORTED` | `test_pairwise_subject_p7.py` | full Trinity・G4・全8 subsetは含まない | 回帰 |
| `CLAIM_TWO_CYCLE_CAUSALITY` | cycle 1のM更新がcycle 2のC/Jを変える | `SUPPORTED` | `test_trinity_two_cycle_p8.py` | 全8 subset・sample攻略は含まない | 回帰 |
| `CLAIM_CAUSAL_ATTRIBUTION` | P-only/J-only/M-only変更の効果を個別帰属できる | `SUPPORTED` | `test_trinity_two_cycle_p8.py` | 観測済みP-A/P-Bとsynthetic Frame条件の範囲 | 回帰 |
| `CLAIM_MINIMUM_THREE` | 全8 subsetでfull setのみPASSする | `SUPPORTED` | `test_minimum_three_certificate_p9.py`, `certificates/p9/` | G1〜G5定義域内の構成最小性。sample攻略・未知task汎化は含まない | 回帰 |
| `CLAIM_SAMPLE_COMPLETE` | 全sample game/all levelを完全攻略し全cycle traceを保存する | `SUPPORTED` | `S5_RENDERED_ONLY_CLOSURE_REPORT.json`, `S5_FULL_EXECUTION_TRACE_MANIFEST.json`, `S5_SHORTCUT_AND_AUTHORITY_AUDIT.json`, `test_s5_execution_trace.py`, `test_s5_rendered_policy.py`, `test_s5_rendered_runtime.py` | 保持OFFLINE sample 25 game・183 levelの範囲。未知task汎化は含まない | 回帰 |
| `CLAIM_GENERALIZATION` | identity-free holdoutで未知構造へ汎化する | `UNSUPPORTED` | `S6_PERTURBATION_MEASUREMENT.json`: 七摂動14,336 responseを測定 | semantic ground truthとtransformed environment完了証拠がなく、結論は`MEASURED_NOT_PROVEN` | 後続研究 |
| `CLAIM_RELEASE_STATE_FIXED` | P0/J0/M0/code/dependency/environmentから再現できる | `SUPPORTED` | `P11_RELEASE_STATE.json`, `P11_REGRESSION_REPORT.json`, `test_p11_release_state.py` | code `823c51b68d7f...`、OFFLINE sample releaseの範囲 | 回帰 |
| `CLAIM_OFFICIAL_READY` | COMPETITION/Kaggleへ進める | `REJECTED` | なし | 未評価、P12以降、current request外 | P12以降 |

## 禁止claim

次の表現は、対応claimが`SUPPORTED`になるまで使用しない。

- AGI完成
- 二周期学習成立済み
- 汎化済み
- 公式提出可能
