# ARC3 AGI Claim Registry rev2

- last completed phase: `P21_GOVERNED_DEVELOPMENT_LOOP_JOINT_OPTIMIZATION`
- current work block: `P22_A_PUBLIC_CV_TRANSFORMATION_STRESS`（進行中）
- active runtime: `GenericAGIRuntime` 一件
- historical boundary: P0〜P15。P11/S5、P12、Kaggle preflightを現行完成claimへ合算しない
- current authority: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- rule: 実装path、実行test、除去証人、scope、RuntimeIdentityが揃わないclaimを
  `SUPPORTED`にしない。progress、response retention、crash 0をcompletionと呼ばない

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
| `CLAIM_SAMPLE_COMPLETE` | 全sample game/all levelを完全攻略し全cycle traceを保存する | `SUPPORTED` | `S5_RENDERED_ONLY_CLOSURE_REPORT.json`, `S5_FULL_EXECUTION_TRACE_MANIFEST.json`, `S5_SHORTCUT_AND_AUTHORITY_AUDIT.json` | 保持OFFLINE sample 25 game・183 levelの範囲。未知task汎化は含まない | 回帰 |
| `CLAIM_GENERALIZATION` | identity-free holdoutで未知構造へ汎化する | `UNSUPPORTED` | `S6_PERTURBATION_MEASUREMENT.json`: 七摂動14,336 responseを測定 | semantic ground truthとtransformed environment完了証拠がなく、結論は`MEASURED_NOT_PROVEN` | P12 |
| `CLAIM_MINIMUM_THREE_STRUCTURAL_CERTIFICATE` | 全8 subsetでfull setのみPASSする構造証明 | `SUPPORTED` | `test_minimum_three_certificate_p9.py`, `certificates/p9/` | fixture/synthetic定義域の構成最小性。S5 operational conformance、sample攻略、未知汎化を含まない | 回帰 |
| `CLAIM_KNOWN_SAMPLE_CLOSURE` | frozen S5が保持OFFLINE 25 game / 183 levelを閉包し全cycle traceを保存する | `SUPPORTED` | `S5_RENDERED_ONLY_CLOSURE_REPORT.json`, `S5_FULL_EXECUTION_TRACE_MANIFEST.json`, `S5_SHORTCUT_AND_AUTHORITY_AUDIT.json` | known sampleだけ。未知task、AGI完成、公式readyを含まない | 回帰 |
| `CLAIM_S5_OPERATIONAL_AGI_CONFORMANCE` | frozen S5 pathがTrinity/HDS/L0/Mのoperational受入を満たす | `SUSPEND` | `S5_OPERATIONAL_CONFORMANCE_REPORT.json` | frozen known-sample path自体には複数model/candidate、J独立採否、semantic M、L0因果ablationがない | 保持 |
| `CLAIM_GENERIC_OPERATIONAL_CONFORMANCE` | separate `GenericAGIRuntime`がrev1のL0/C/J/M/Trinity/learning/observability受入を満たした | `HISTORICAL_ONLY` | `GENERIC_OPERATIONAL_CONFORMANCE_REPORT.json`, `test_generic_runtime_p12.py`, `test_generic_memory_p12.py` | rev2のcandidate binding、shared session、atomic M、P-IR、未知game完了を含まない | P17〜P22 |
| `CLAIM_GENERICITY` | whole-game/mechanism/transformation/sealed holdoutで未知構造へ適応する | `HISTORICAL_ONLY` | 25/25 whole-gameで全5 fold progress各1、holdout完了0、旧変換/sealed progress | progressだけでcompletionをPASSにしていたrev1 claim。rev2 generic completion証拠には使わない | P22 |
| `CLAIM_RELEASE_STATE_FIXED` | P0/J0/M0/code/dependency/environmentから再現できる | `SUPPORTED` | `P11_RELEASE_STATE.json`, `P11_REGRESSION_REPORT.json`, `test_p11_release_state.py` | code `823c51b68d7f...`、OFFLINE sample releaseの範囲 | 回帰 |
| `CLAIM_COMPETITION_MOCK_CONTRACT` | rev1 Competition adapter契約を公式接続なしのmockで満たした | `HISTORICAL_ONLY` | `COMPETITION_CONTRACT_DRY_RUN.json`: `OFF-001`〜`OFF-008` PASS | P23のshared session、exact artifact、資源、official lifecycleを含まない | P23 |
| `CLAIM_OFFICIAL_COMPATIBILITY` | 公式Competition contractに実接続で適合する | `NOT_EVALUATED` | mock dry-runはPASS、official connection performedはfalse | actualはP13かつP12全blocking PASS後のみ | P13 |
| `CLAIM_OFFICIAL_SCORE` | 公式scoreを取得済み | `NOT_EVALUATED` | なし | 公式接続・提出未実施 | P15 |
| `CLAIM_PRE_OFFICIAL_AGI_READY` | rev1 P13公式接続の前提gateを満たした | `HISTORICAL_ONLY` | `PRE_OFFICIAL_AGI_RELEASE_STATE.json`: 57/57 PASS、failed ID 0 | rev2 blocking registryを満たさず、現行phase selectorではない | 参照のみ |
| `STRUCTURAL_READY` | rev2 C/J/M/P、権限、traceが実装済み | `SUPPORTED` | P17-A〜P21 phase state、architecture docs、unit tests | completion・汎化・official readinessを含まない | P22 |
| `KNOWN_PUBLIC_REGRESSION` | active generic runtimeだけで公開25 game・183 levelを完遂 | `NOT_EVALUATED` | focused `ft09-0d8bbf25`は6/6 level・75/75 action・failure 0 | 残り24 gameと全数artifact未実行 | P22-A |
| `MEMORY_CAUSAL` | candidate-bound Mだけの差で未来の計算・判断・行動が変化 | `SUPPORTED` | `test_p22a_compiled_autonomous_policy.py`: 同一renderでbounded Mだけを変えaction 6→3、runtime HDS-authorized append | public全数ablationは未完了 | P22-A |
| `P_VERSION_LEARNING_CAUSAL` | ExperienceからP-IR候補を昇格し再起動利用 | `SUPPORTED` | P20-B compiler/bundle/restart、P21 governed loop/lineage tests | locked-final成果を含まない | P22/P23 |
| `CV_PROCEDURE_EVIDENCE` | 分離したfold artifactで開発手順を補助評価 | `NOT_EVALUATED` | rev1 CVはhistorical | rev2 role/access/identityで未実行 | P22-A |
| `TRANSFORMATION_STRESS_PASS` | 七変換environmentをactive runtimeが完遂 | `NOT_EVALUATED` | rev1 progress測定はhistorical | environment completion証拠なし | P22-A |
| `SEALED_SINGLE_ARTIFACT_COMPLETE` | 一つの固定artifactが未使用locked evaluatorを一回で完遂 | `NOT_EVALUATED` | rev1 sealedはcontent/result開示済み | rev2 LOCKED_FINAL未作成 | P22-B |
| `COMPETITION_READY` | exact P22-B artifactが公式lifecycle・資源・package gateを満たす | `NOT_ESTABLISHED` | Notebook通常実行はpreflightのみ | P23未実施 | P23 |
| `OFFICIAL_RUN_ACCEPTED` | exact artifactの公式runがbytesとscoreを返した | `NOT_OBSERVED` | baseline提出はscoreなし・bytes 0 | accepted official resultなし | P24 |
| `OFFICIAL_PUBLIC_COMPLETE` | exact artifactのPublic scopeが100% | `NOT_OBSERVED` | なし | official Public scoreなし | P24 |
| `OFFICIAL_PRIVATE_COMPLETE` | 同一exact artifactのPrivate scopeが100% | `NOT_OBSERVED` | なし | official Private scoreなし | P24 |
| `OFFICIAL_FULL_COMPLETE` | 同一artifactのPublic/Private両scopeまたはFULL_110が100% | `NOT_OBSERVED` | なし | full official scoreなし | P24 |

## 禁止claim

次の表現は、対応claimが`SUPPORTED`になるまで使用しない。

- AGI完成
- ARC3閉包
- rev2 memory causality成立済み
- 汎用自律完遂済み
- 公式提出可能
- PRE_OFFICIAL_AGI_READY
- COMPETITION_READY
- OFFICIAL_FULL_COMPLETE
