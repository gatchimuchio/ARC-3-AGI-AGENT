# S0 Teacher artifacts

このディレクトリはP10-R1以降の開発専用Teacher正本です。Runtime Studentから
参照・importしてはいけません。

## 入力固定

- `HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json`: 25 winning row、dataset
  repository SHA、各trajectory SHA-256
- `LOCAL_SOLUTION_OVERRIDE_MANIFEST.json`: 現行sample revisionと非互換な
  public trajectoryに対するcontent-bound local override

## 六正本

- `FULL_SOLUTION_CORPUS.json`
- `LEVEL_SOLUTION_GRAPH_LEDGER.json`
- `INTRA_GAME_PROGRESSION_GRAPH.json`
- `CROSS_GAME_STRUCTURAL_GRAMMAR.json`
- `PRIVILEGE_SUBTRACTION_MATRIX.json`
- `RUNTIME_P_COMPILATION_REPORT.json`

## 実行・score証拠

- `TEACHER_S0_CLOSURE_REPORT.json`
- `TEACHER_S0_ORACLE_ADAPTER_REPORT.json`
- `TEACHER_S0_LOCAL_SCORE_ORACLE.json`
- `TEACHER_S0_LOCAL_SCORE_ORACLE.md`

現状はS0 Teacherのみ183/183です。S1〜S6およびrendered-only Runtime
Studentは未達です。

再生成手順とclaim境界は
[`P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md`](../../docs/roadmap/P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md)
を参照してください。
