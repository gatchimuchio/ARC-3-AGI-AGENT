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
- `S2_ROLE_RELATIVE_POLICY_GRAPH.json`
- `TEACHER_S2_CLOSURE_REPORT.json`
- `TEACHER_S2_ORACLE_ADAPTER_REPORT.json`
- `TEACHER_S2_LOCAL_SCORE_ORACLE.json`
- `TEACHER_S2_LOCAL_SCORE_ORACLE.md`
- `S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json`
- `TEACHER_S3_CLOSURE_REPORT.json`
- `TEACHER_S3_ORACLE_ADAPTER_REPORT.json`
- `TEACHER_S3_LOCAL_SCORE_ORACLE.json`
- `TEACHER_S3_LOCAL_SCORE_ORACLE.md`
- `S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json`
- `TEACHER_S4_CLOSURE_REPORT.json`
- `TEACHER_S4_ORACLE_ADAPTER_REPORT.json`
- `TEACHER_S4_LOCAL_SCORE_ORACLE.json`
- `TEACHER_S4_LOCAL_SCORE_ORACLE.md`

現状はS0〜S4 Teacherが183/183です。S5〜S6およびrendered-only Runtime
Studentは未達です。S4は固定action列、literal target、明示的な
task/game/level ID routing、source/hidden runtime読取を除去しましたが、
answer/replay由来のexact graphへの依存を残します。

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

P10-R5/S2はS1成功経路を10,758 coordinate-free state node、10,733 edgeへ
変換しました。3,112 pointer actionはabsolute payloadを保存せず、現在renderの
target-centred palette relation 26,623件から一意targetを解決します。
183/183 level、10,733 action、selector failure 0、error 0で、標準local
oracleはS1と同じRHAE 99.619936696%です。全25 gameのgraph生成と
全183 levelのexecutor実行を新規環境で各2回行い、graphとclosure reportは
いずれもbyte-identicalでした。

P10-R5/S3は25個のS2 game partitionを一つのglobal policy indexへ統合し、
状態署名とaction選択からgame/task/level identity、level progress counter、
game別graph routingを除去しました。graph内identity key/literalは0、
policy partitionは1です。183/183 level、10,733 action、identity-routing
decision 0、error 0で、標準local oracleはS2と同じRHAE 99.619936696%です。
評価harnessだけが環境作成と結果帰属にgame IDを使用し、action選択関数は
受け取りません。このS3時点ではsource/hiddenとanswer-derived graphが
残存特権であり、前者をS4で除去しました。
全global graph生成と全183 levelのexecutor実行を新規環境で各2回行い、
graphとclosure reportはいずれもbyte-identicalでした。

P10-R5/S4は、S3 source/hidden読取の副作用をS4へ混入させないため、
使い捨てS3 mirrorでanswer trajectoryだけを回収し、別のfresh target環境を
source/hidden未読のまま再実行してgraphを収集します。`ls20`では
`_get_hidden_state()`がrender制御値を書き換える副作用を持つことを検出し、
S3 conditionからdigestだけを削る変換を棄却しました。S4 targetの
source/hidden readは0、graph/runtime decisionも0です。25/25 game、
183/183 level、10,733 action、error 0で、標準local oracleはS3と同じ
RHAE 99.619936696%です。graphは10,758 node、10,733 edgeで、
branch、merge、nondeterministic actionはいずれも0です。全graph再生成と
全183 level再実行をfresh条件で各2回行い、graphとclosure reportは
byte-identicalでした。S4 graphはanswer-derived exact graphなので、
rendered-only Runtime Student Pの成立証拠には使用しません。

再生成手順とclaim境界は
[`P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md`](../../docs/roadmap/P10_COMPLETE_CLOSURE_HORIZONTAL_SUBTRACTION_STRATEGY.md)
を参照してください。
