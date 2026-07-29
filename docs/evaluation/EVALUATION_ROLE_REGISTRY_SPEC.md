# ARC3 Evaluation Role Registry Specification

- registry specification ID: `ARC3_EVALUATION_ROLE_REGISTRY_REV2`
- phase introduced: `P16`
- machine registry: `control/p16/EVALUATION_ROLE_REGISTRY.json`
- status: `PASS`

## Roles

| Role | 開発入力 | promotion入力 | 完成claim |
|---|---:|---:|---:|
| `DEVELOPMENT_TRAIN` | 可 | 間接可 | 不可 |
| `DEVELOPMENT_VALIDATION` | 評価だけ | 可 | 不可 |
| `CV_HOLDOUT` | fold freeze後不可 | procedure評価だけ | `CV_PROCEDURE_EVIDENCE`だけ |
| `LOCKED_FINAL` | freeze前後とも不可 | 不可 | 一つの固定artifact・一回実行だけ |
| `OFFICIAL_PUBLIC` | 提出後は次版の開発信号に可 | 当該artifact変更不可 | Public scopeだけ |
| `OFFICIAL_PRIVATE` | 公開後は次版の開発信号に可 | 当該artifact変更不可 | Private scopeだけ |

## Registry invariants

1. 一つのevaluation executionは一つのroleだけを持つ。
2. 同じ公開assetをtrain/CVへ使う場合も、execution identityとartifactを分ける。
3. CV foldごとのPは別`RuntimeIdentity`であり、結果をsingle-artifact claimへ合算しない。
4. `LOCKED_FINAL`はcontent未参照、one execution、結果開示後`CONSUMED`。
5. `LOCKED_FINAL`結果を開発へ使った時点でfinal資格を失い、
   `DEVELOPMENT_VALIDATION`へ降格する。
6. progress、response retention、crash 0だけでcompletionをPASSにしない。
7. official Public/Privateはscope、raw score、normalized score、
   exact artifact digestを別々に保持する。

## Current asset classification

- 公開25 gameは既知development/regression assetであり、未知final証拠ではない。
- P12 whole-game CVは完了0であり、rev1 historical procedure evidenceに限る。
- P12 sealed custom evaluatorは内容と結果がrepoに存在するため
  `HISTORICAL_CONSUMED`であり、rev2 `LOCKED_FINAL`ではない。
- rev2 `LOCKED_FINAL`は未作成・未参照である。
- official Public/Private scoreは現行artifactについて`NOT_OBSERVED`である。

## Access-state transitions

```text
NOT_PROVISIONED
→ REGISTERED_UNACCESSED
→ FROZEN_UNACCESSED
→ EXECUTED_ONCE
→ CONSUMED
```

内容を開発側が見た場合:

```text
REGISTERED_UNACCESSED or FROZEN_UNACCESSED
→ DOWNGRADED_TO_DEVELOPMENT
```

## Blocking conditions

- role未登録のevaluation
- LOCKED_FINALの二回目実行
- LOCKED_FINALをpromotion triggerへ利用
- CV fold artifactの合算
- Publicだけをfull completionと表記
- scope不明scoreをPublic/Privateへ推定分類
