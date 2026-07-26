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
- `S1_STATE_CONDITIONED_POLICY_GRAPH.json`
- `TEACHER_S1_CLOSURE_REPORT.json`
- `TEACHER_S1_ORACLE_ADAPTER_REPORT.json`
- `TEACHER_S1_LOCAL_SCORE_ORACLE.json`
- `TEACHER_S1_LOCAL_SCORE_ORACLE.md`

現状はS0とS1 Teacherが183/183です。S2〜S6およびrendered-only Runtime
Studentは未達です。S1は固定action列だけを除去しており、ID、source/hidden、
answer/replay graph、literal座標への依存を残します。

P10-R2の全183 graphは、保持中25 source fileのSHA-256、183 level定義、
object/state role、25 goal witness、43 hazard witness、hidden-state boundary、
実行済み成功pathとsource hazard pathのcontrastへ束縛済みです。
human-readable mechanic名はsource factではなく開発仮説として分離しています。
未実行のnegative action列はfailure replayとして主張していません。

P10-R3のgame内差分158/158とcross-game source-causal factorizationも完了して
います。

P10-R4/S1は11,574成功遷移を11,387 current-state node、11,383 edgeへ
変換しました。executorはcorpusをimportせず、現在観測、S1で許可される
source/hidden state、固定長4のaction/effect履歴、WIN距離だけでactionを
選択します。25/25 game、183/183 level、10,733 action、error 0で、
node miss、unexpected target、距離非減少はいずれも0です。
同一sample zipによる標準local oracleはRHAE 99.619936696%で、S0
99.446886157%に対して+0.173050539 percentage pointです。
全25 gameのgraph生成と全183 levelのexecutor実行を新規環境で各2回行い、
graphとclosure reportはいずれもbyte-identicalでした。

再生成手順とclaim境界は
[`P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md`](../../docs/roadmap/P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md)
を参照してください。
