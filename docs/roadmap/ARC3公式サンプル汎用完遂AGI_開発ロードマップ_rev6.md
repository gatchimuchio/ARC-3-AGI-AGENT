# ARC3公式サンプル汎用完遂AGI 開発ロードマップ rev6

- Roadmap ID: `ARC3_GENERIC_COMPLETION_AGI_ROADMAP_REV6`
- 仕様: `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev6.md`
- 指示書Index: `docs/instructions/arc3_rev6/INDEX.md`
- Machine Manifest: `control/rev6/ROADMAP_MANIFEST.json`
- Current Point: `R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`
- 自動遷移: 禁止

---

## 全体構造

```text
R0 RECOVERY / REAL-STATE REBASELINE
→ M0 CAPABILITY BASIS + FIRST AGI CLOSURE
→ M1 CAPABILITY-FAMILY EXPANSION
→ M2 FULL-SAMPLE PRODUCT CLOSURE
→ M3 GENERIC / AGI CONFORMANCE
→ M4 PRODUCT FREEZE AND RELEASE
```

## Point一覧

| Point | 目的 | Hard Exit | 指示書 |
|---|---|---|---|
| R0-P01 | rev5.1虚偽閉包の失効 | release claim revoked | `R0/R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE.md` |
| R0-P02 | 実能力・実score・実コード再基準化 | real baseline fixed | `R0/R0-P02_REAL_STATE_REBASELINE.md` |
| M0-P01 | 25 game能力coverage | matrix complete | `M0/M0-P01_CAPABILITY_COVERAGE_MATRIX.md` |
| M0-P02 | basis set選定 | mandatory surfaces covered | `M0/M0-P02_BASIS_SET_SELECTION.md` |
| M0-P03 | 最初のbasis game HDS解析 | mechanism mapping complete | `M0/M0-P03_FIRST_BASIS_GAME_HDS_ANALYSIS.md` |
| M0-P04 | 最初の製品能力実装 | runtime consumes capability | `M0/M0-P04_FIRST_BASIS_GAME_CAPABILITY_IMPLEMENTATION.md` |
| M0-P05 | 最初のオンライン三主体WIN | first game WIN + memory causality | `M0/M0-P05_FIRST_ONLINE_TRINITY_WIN.md` |
| M0-P06 | 残りbasis完遂 | all basis games WIN | `M0/M0-P06_REMAINING_BASIS_GAMES_CLOSURE.md` |
| M0-P07 | 初期水平引き算 | cross-game ACTIVE_DEV family | `M0/M0-P07_INITIAL_HORIZONTAL_SUBTRACTION.md` |
| M1-P01 | 全25 game実製品baseline | real failure inventory | `M1/M1-P01_FULL_SAMPLE_BASELINE_WITH_REAL_PRODUCT.md` |
| M1-P02 | 次能力gap選定 | one closure unit fixed | `M1/M1-P02_CAPABILITY_GAP_SELECTION.md` |
| M1-P03 | HDS CaseSet比較 | mechanism/boundary fixed | `M1/M1-P03_HDS_CASESET_ANALYSIS.md` |
| M1-P04 | 能力実装 | product behavior delta | `M1/M1-P04_CAPABILITY_IMPLEMENTATION.md` |
| M1-P05 | affected game閉包 | target failure decreases | `M1/M1-P05_AFFECTED_GAME_CLOSURE.md` |
| M1-P06 | promotion／rollback | asset state fixed | `M1/M1-P06_PROMOTION_OR_ROLLBACK.md` |
| M1-P07 | 全game mapping閉包 | 25 individual WIN／183 complete | `M1/M1-P07_ALL_GAME_MAPPING_CLOSURE.md` |
| M2-P01 | clean full run A | full-run evidence | `M2/M2-P01_CLEAN_FULL_RUN_A.md` |
| M2-P02 | full-run failure修正 | failure closed | `M2/M2-P02_FULL_RUN_FAILURE_REPAIR.md` |
| M2-P03 | clean rerun | Run A 25/25・183/183 | `M2/M2-P03_CLEAN_RERUN_UNTIL_PASS.md` |
| M2-P04 | shuffled order | order independence | `M2/M2-P04_SHUFFLED_ORDER_RUNS.md` |
| M2-P05 | full-sample閉包 | one bundle full completion | `M2/M2-P05_FULL_SAMPLE_CLOSURE.md` |
| M3-P01 | C/J/M/P ablation | predicted loss | `M3/M3-P01_CJMP_ABLATION.md` |
| M3-P02 | 記憶因果 | relevant delta／irrelevant invariance | `M3/M3-P02_MEMORY_CAUSALITY.md` |
| M3-P03 | identity／replay監査 | finding 0 | `M3/M3-P03_IDENTITY_REPLAY_AUDIT.md` |
| M3-P04 | applicability反実仮想 | boundary PASS | `M3/M3-P04_APPLICABILITY_COUNTERFACTUAL.md` |
| M3-P05 | Runtime／Version Learning | two-loop separation | `M3/M3-P05_RUNTIME_VERSION_LEARNING.md` |
| M3-P06 | conformance回帰 | 25/25維持 | `M3/M3-P06_CONFORMANCE_REGRESSION.md` |
| M4-P01 | release bundle compile | one RELEASE_FROZEN bundle | `M4/M4-P01_RELEASE_BUNDLE_COMPILATION.md` |
| M4-P02 | code/dependency/resource freeze | immutable release input | `M4/M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE.md` |
| M4-P03 | clean install | fresh boot PASS | `M4/M4-P03_CLEAN_INSTALL.md` |
| M4-P04 | clean full rerun | same artifact 25/25 | `M4/M4-P04_CLEAN_FULL_SAMPLE_RERUN.md` |
| M4-P05 | Kaggle normal run | unchanged artifact normal run | `M4/M4-P05_KAGGLE_NORMAL_RUN.md` |
| M4-P06 | submission／platform separation | result classified; no false release | `M4/M4-P06_SUBMISSION_PLATFORM_SEPARATION.md` |

## 反復規則

M1-P02〜P06は、全game mappingが閉じるまで反復する。反復ごとに一つのCapability Closure Unitだけを扱う。

M2-P01〜P03は、clean official-order runが25/25・183/183になるまで反復する。

## 現在地点

`R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`

rev5.1 artifactは削除しない。製品完成証拠としての権威だけを失効させる。
