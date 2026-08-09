# M3-P02 — Memory Causality

- Point ID: `M3-P02_MEMORY_CAUSALITY`
- Depends on: M3-P01 PASS
- Next: `M3-P03_IDENTITY_REPLAY_AUDIT`

## 目的

Mが保存装置ではなく、未来のC／Jを因果的に変える主体であることを確認する。

## 必須試験

### Relevant mutation

```text
same observation
+ relevant M ADD／REVISE／INVALIDATE
→ model／candidate／plan／actionの少なくとも一つが変化
```

### Irrelevant mutation

```text
same observation
+ irrelevant／stale／out-of-scope M
→ selected action不変
```

### Failed hypothesis

```text
failure evidence
→ hypothesis invalidated
→ same failed action pattern not repeated unboundedly
```

## 必須作業

1. controlled representative statesを固定する。
2. M mutation前後のretrieval、C output、J decisionを比較する。
3. citation／bindingを追跡する。
4. 差が出ない場合はretrieval／binding／J evidence gateを修正する。

## Hard Exit

```text
relevant_behavior_change_count > 0
irrelevant_action_change_count = 0
failed_hypothesis_invalidation_observed = true
memory_citation_path_complete = true
M2_full_run_regression = PASS
```

## 禁止

- random seed差をmemory因果扱い
- output logだけの変化
- irrelevant Mによるpolicy drift

## Failure Routing

M因果未成立はM3-P02内で修正し、次へ進まない。
