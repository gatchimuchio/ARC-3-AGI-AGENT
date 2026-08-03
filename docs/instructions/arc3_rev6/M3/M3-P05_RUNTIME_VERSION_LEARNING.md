# M3-P05 — Runtime Learning／Version Learning

- Point ID: `M3-P05_RUNTIME_VERSION_LEARNING`
- Depends on: M3-P04 PASS
- Next: `M3-P06_CONFORMANCE_REGRESSION`

## 目的

実行中M更新と、安定能力の次版P／J0／M0再コンパイルを分離して成立させる。

## Runtime Learning

```text
experience
→ M ADD／REVISE／INVALIDATE
→ later behavior changes within run
```

## Version Learning

```text
multiple runs + counterexamples + regression
→ ACTIVE_DEV candidate
→ compiled next initial state
→ restart uses acquired stable capability
```

## 必須作業

1. 一回の成功がreleaseへ直行しないことを確認する。
2. false learningをrollback／invalidateする。
3. stable capabilityをnext initial-state candidateへcompileする。
4. fresh restartで能力を利用する。
5. PとMの役割を混同しない。

## Hard Exit

```text
runtime_M_update_before_version_compile = true
single_run_release_promotion_count = 0
false_learning_rollback_observed = true
stable_capability_restart_use_observed = true
P_M_role_violation_count = 0
```

## 禁止

- current Mをそのままrelease M0化
- live human decisionをcompiled initial stateへ混入
- restart不能な「学習」

## Failure Routing

二つのloopが分離できなければM3-P05を閉じない。
