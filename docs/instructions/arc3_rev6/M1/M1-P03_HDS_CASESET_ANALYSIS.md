# M1-P03 — HDS CaseSet比較解析

- Point ID: `M1-P03_HDS_CASESET_ANALYSIS`
- Depends on: M1-P02 PASS
- Next: `M1-P04_CAPABILITY_IMPLEMENTATION`

## 目的

同じFailure Signatureを持つ複数Caseを比較し、共通機構と適用境界を確定する。

## HDS Frame

```text
F:
  common purpose／boundary
  shared observations
  differing conditions
  open terms

Md:
  baseline
  alternative
  counter-hypothesis
  null/no-op
  observation error
  wrong target/order/goal

Cm:
  evidence／impossibility／projection／reversibility／resource

U:
  selected local mechanism
  falsification condition
  product responsibility hypothesis
```

## 必須作業

1. positive、negative、near-miss、failure Caseを含める。
2. 共通部分とCase固有parameterを分離する。
3. Applicability Predicateを定義する。
4. 反例で過剰一般化を削る。
5. P／J／M／C／Adapterの責任候補を比較する。
6. raw trace spanへの参照を保持する。

## 出力

`analysis/product/rev6/m1/units/<unit_id>/hds_caseset_analysis.json`

## Hard Exit

```text
baseline_and_counter_models_present = true
positive_case_count >= 1
negative_or_boundary_case_count >= 1
applicability_predicate_defined = true
falsification_condition_defined = true
responsible_component_selected = true
product_mapping_defined = true
```

## 禁止

- 単一成功Caseから一般則確定
- game IDによる共通性
- action literal一致だけでfamily化
- product mappingなしの解析完了

## Failure Routing

反例で機構が崩れる場合はModelSetを更新する。責任部品が確定しない限りM1-P04へ進まない。
