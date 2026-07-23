# P9 AGI最小三構成・全8部分集合証明

- phase: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`
- state: `COMPLETE`
- predecessor: `P8_THREE_SUBJECT_TWO_CYCLE_TRINITY`
- successor: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- definition scope: functional obligations `G1` through `G5`
- official / competition connection: prohibited
- HDS judgment: `PASS`

## 1. Work-block FrameSpec

```text
X:
  空集合、C/J/M single、C+J/C+M/J+M pair、C+J+M full set
  P4〜P8の実行主体と固定identity-free observation

R:
  各subsetを実行し、G1〜G5、overall、固有failure witness、
  欠落主体field、欠落主体固有出力を一対一対応する

Mc:
  8 subsetを有限・重複なしで列挙
  full setだけPASS
  proper subset 7件FAIL
  single removal 3件、pair failure 3件
  two-cycle causality PASS
  functional-equivalent leak 0
  5 artifactを同一入力からbyte一致で再生成

non-goals:
  全sample攻略、未知task汎化、公式評価、release state固定
```

## 2. 実行結果

| subset | G1 | G2 | G3 | G4 | G5 | overall | failure witness |
|---|---|---|---|---|---|---|---|
| `{}` | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | `NO_COMPUTE_JUDGMENT_OR_MEMORY` |
| `{C}` | PASS | FAIL | FAIL | FAIL | FAIL | FAIL | `NO_JUDGMENT_OR_MEMORY` |
| `{J}` | FAIL | PASS | FAIL | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION_OR_MEMORY` |
| `{M}` | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION_OR_JUDGMENT` |
| `{C,J}` | PASS | PASS | FAIL | FAIL | PARTIAL | FAIL | `NO_PERSISTENT_EXPERIENCE_CAUSALITY` |
| `{C,M}` | PASS | FAIL | PASS | FAIL | FAIL | FAIL | `NO_JUDGMENT_OR_AUTHORIZATION` |
| `{J,M}` | FAIL | PASS | PASS | FAIL | FAIL | FAIL | `NO_GENERATIVE_COMPUTATION` |
| `{C,J,M}` | PASS | PASS | PASS | PASS | PASS | PASS | - |

定理条件の実測値:

```text
full_set_pass = true
proper_subset_pass_count = 0
proper_subset_fail_count = 7
single_removal_fail_count = 3
pair_subset_fail_count = 3
two_cycle_causality_pass = true
functional_equivalent_leak_count = 0
```

audit digest:
`6885c1c0a64471a656e5a557a6344d1287d3bcdb3eff7df3b1650921559fbc4f`

## 3. 機能等価物監査

single harnessは、保持する主体に対応するfieldだけを持つ。各subset証拠は
field監査に加え、欠落主体の固有出力を検査する。

- C欠落時: hypothesis / generated candidateは0
- J欠落時: judgment statusは空
- M欠落時: memory version mutationは0
- J-onlyのcandidateは外部供給として明示し、生成計算へ数えない
- proper pairはP7の実行witnessと主体field監査を再利用する
- full setはP8の実二周期reportからhypothesis数、candidate数、J status、
  cycle 2 post-memory version、causalityを導出する

fixtureはgame/task/level ID、replay、固定action列、answer map、literal座標、
source/hidden stateを含まない。全reportのruntime identity検査は0件である。

## 4. 固定成果物

`certificates/p9/`の5件だけをP9 certificate setとする。

| artifact | SHA-256 |
|---|---|
| `agi_minimum_three_certificate.json` | `9b12bfd7054fddc48458d553565994a0046a5fbd594e385ba8613f2341773e68` |
| `agi_subset_enumeration.json` | `c35ef67e246022acdedec8d414e699cecf4b5a3e856b856ee9d8af7abf69c7fb` |
| `agi_removal_witnesses.json` | `4e2de0ac279be2be0942c21c6f39754d33476b3de7815bdd13931d4657cfe3d8` |
| `agi_obligation_graph.json` | `a897a9079832a86762382e9a7c24ae520ed68ea7717c5a5afcd53429ad11cb7f` |
| `agi_conformance_report.md` | `e08aa8029f6e824a09e7661bd7bfa384a7f13edf36291cafb57f7f9296703e87` |

生成入口:

```bash
arc3-build-minimum-certificate \
  --obligation-graph ../docs/architecture/AGI_OBLIGATION_GRAPH.json \
  --output-dir ../certificates/p9
```

certificateの`content_digest`は
`dd40f060b663ef7066c1e25fc41edc5aa2f4c6e678c3d5a61a139df0d8671425`
である。

## 5. 検証

- P9 dedicated tests: 9 PASS
- compileall: PASS
- full unit suite: 189 PASS
- strict mypy: PASS
- ruff: PASS
- integration: 2 PASS
- 25 sample OFFLINE 1-action regression: 25/25 execution、error 0

1-action回帰はP1〜P9の実行経路非回帰だけを示し、level完了証拠ではない。

## 6. 結論と境界

定義されたG1〜G5の機能クラスにおいて、C・J・Mまたはその機能等価物は共同で
必要であり、この実装ではfull setだけが全義務を満たす。これにより
`CLAIM_MINIMUM_THREE`を`SUPPORTED`へ昇格する。

このcertificateは全sample攻略、未知task汎化、公式評価性能、形而上学的な
汎用知能認定を証明しない。次phaseはP10である。
