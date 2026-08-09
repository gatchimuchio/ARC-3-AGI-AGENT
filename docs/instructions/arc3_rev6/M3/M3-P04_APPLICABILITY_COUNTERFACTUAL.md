# M3-P04 — Applicability Counterfactual

- Point ID: `M3-P04_APPLICABILITY_COUNTERFACTUAL`
- Depends on: M3-P03 PASS
- Next: `M3-P05_RUNTIME_VERSION_LEARNING`

## 目的

MechanismSpecが表面identityではなく成立条件によって選択されることを確認する。

## 必須試験

各mandatory familyについて:

```text
condition-preserving perturbation
→ same mechanism family remains applicable
→ parameter binding changes as needed

condition-breaking perturbation
→ mechanism becomes non-applicable
→ alternative／probe／SUSPEND
```

## Perturbation Axis

```text
color／label
translation／rotation／reflection
object count
relation structure
legal action surface
precondition removal
goal/hazard change
temporal order
```

## 必須作業

1. Applicability Predicateを明示する。
2. positive、negative、boundary perturbationを作る。
3. selectionとaction principleを比較する。
4. surface identity依存を修正する。
5. representative official regressionを行う。

## Hard Exit

```text
mandatory_family_counterfactual_coverage = 100%
condition_preserving_failures = 0
condition_breaking_false_applications = 0
identity_feature_usage = 0
M2_regression = PASS
```

## 禁止

- synthetic PASSだけでofficial regression省略
- family IDの固定選択
- perturbationに答えを埋め込む

## Failure Routing

境界不成立familyはPROBATIONへ降格し、M1-P03へ戻す。
