# P7 二主体接続監査・完了証拠

- phase: `P7_PAIRWISE_SUBJECT_AUDIT`
- state: `COMPLETE`
- predecessor: `P6_MEMORY_SUBJECT_M`
- successor: `P8_THREE_SUBJECT_TWO_CYCLE_TRINITY`
- runtime scope: identity-free executable proper-subset audit
- official / competition connection: prohibited
- HDS judgment: `PASS`

## 1. Work-block FrameSpec

```text
X:
  P4 standalone C
  P5 standalone J
  P6 standalone M
  fixed pair obligations and witnesses from P2

R:
  instantiate exactly two named subjects
    -> execute every responsibility available to that pair
    -> attempt to close G1..G5
    -> fail at the responsibility owned by the absent subject

Mc:
  C+J has no mutable/persistent M
  C+M has no J decision or capability issuer
  J+M has no hypothesis/candidate/output generator C
  each witness is fixed and unique
  missing-subject field/fallback/global callback is absent

non-goals:
  full Trinity, G4 two-cycle causality, all-eight-subset certificate,
  sample solving, release freeze
```

## 2. 実行結果

| Pair | 実行できた責任 | 不成立責任 | 固定witness |
|---|---|---|---|
| `{C,J}` | J compute request、C仮説/候補生成、J採否、一周期action許可判断 | G3、G4、persistent experience | `NO_PERSISTENT_EXPERIENCE_CAUSALITY` |
| `{C,M}` | M保持、C memory read、仮説/候補、memory update proposal | G2、write/emit許可 | `NO_JUDGMENT_OR_AUTHORIZATION` |
| `{J,M}` | M根拠保持、外部candidateへのJ判断、memory update許可判断 | G1、新規仮説/候補/output生成 | `NO_GENERATIVE_COMPUTATION` |

義務結果:

| 構成 | G1 | G2 | G3 | G4 | G5 | 総合 |
|---|---|---|---|---|---|---|
| `{C,J}` | PASS | PASS | FAIL | FAIL | PARTIAL | FAIL |
| `{C,M}` | PASS | FAIL | PASS | FAIL | FAIL | FAIL |
| `{J,M}` | FAIL | PASS | PASS | FAIL | FAIL | FAIL |

## 3. 非代行証拠

`ComputeJudgmentPair`は`memory_subject`を持たず、immutable empty viewだけで
一周期を計算する。writeや周期間carrierは存在しない。

`ComputeMemoryPair`は`judgment_subject`を持たない。low-level fixture seedを
読み、更新案を生成できるが、forged/denied runtime writeはMの実権限境界で
拒否され、version/digestは不変である。

`JudgmentMemoryPair`は`compute_subject`を持たない。candidateは外部から明示供給し、
generated candidate countとhypothesis countは0のままJが判断する。Jの
memory-write許可判断はeffect capabilityではなく、C不在では実行されない。

全pair harnessを同一instanceで二回実行してもevidenceは一致する。hidden mutable
global、task/game/level ID、replay、answer map、source pathは使用しない。

## 4. 検証

- P7 dedicated tests: 7 PASS
- compileall: PASS
- full unit suite: 173 PASS
- strict mypy: PASS
- ruff: PASS
- integration: 2 PASS
- 25 sample OFFLINE 1-action regression: 25/25 execution、error 0
- pair witness unique count: 3
- functional-equivalent leak count: 0

P7はproper pair不足だけを`SUPPORTED`とする。full Trinity、G4、全8 subset、
全sample level攻略、汎化、release固定は未成立。次phaseはP8。
