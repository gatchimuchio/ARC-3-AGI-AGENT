# P10 完全閉包先行・水平減算戦略

- phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- strategy: `COMPLETE_CLOSURE_FIRST_HORIZONTAL_SUBTRACTION`
- state: `IN_PROGRESS`
- operation mode: `OFFLINE` only
- Teacher boundary: `DEVELOPMENT_ONLY`
- Runtime Student boundary: `RENDERED_ONLY`
- successor: `P11_RELEASE_STATE_FREEZE`

## 1. 最上位順序

P10の現行順序は次で固定する。

```text
全情報を使うTeacherで完全閉包
  -> 各成功を解法グラフへ変換
  -> 同一ゲーム内のlevel差分を抽出
  -> 全ゲーム横断の構造文法へ因数分解
  -> 固定action、座標、ID、source/hiddenを水平に一段ずつ削除
  -> rendered-only Studentで183/183
  -> 摂動下の汎化測定
```

過学習防止は入口制約ではない。ある特権を削除してscoreまたは完了数が落ちた
場合、その特権が保持していた構造をまだPへコンパイルできていないと判定する。

## 2. Teacher / Runtime Student境界

### Teacher

Teacherは開発専用であり、次を使用できる。

- task/game/level identity
- source code、hidden state
- 正解、成功trajectory、replay
- 固定action列、literal座標
- 全タスク解析、過去の成功・失敗ログ
- level間依存関係

Teacher成果物はすべて`development_only: true`かつ
`runtime_use: FORBIDDEN`とする。

### Runtime Student

Runtime Studentが使用できるのは次だけである。

- rendered observation
- available actions
- action/effect history
- HDS承認済み受動M
- identity-free P

`arc3_agi_agent.teacher`、`analysis/teacher`、TeacherのID、replay、固定action、
literal座標、source/hidden stateをRuntimeからimportまたは参照してはならない。

## 3. 減算stage

| stage | 使用条件 | 必須結果 | 現状 |
|---|---|---:|---|
| S0 | 全特権を許可 | 183/183 | `PASS` |
| S1 | 固定action列を禁止 | 183/183 | `PASS` |
| S2 | literal座標も禁止 | 183/183 | `NOT_RUN` |
| S3 | task/game/level ID routingも禁止 | 183/183 | `NOT_RUN` |
| S4 | source/hidden stateも禁止 | 183/183 | `NOT_RUN` |
| S5 | rendered observationと履歴のみ | 183/183 | `NOT_RUN` |
| S6 | 色・回転・反転・配置・個数・順序・未観測合成を摂動 | 汎化測定 | `NOT_RUN` |

一つ前のstageが183/183でなければ次stageへ進まない。

## 4. P10-R0〜R6

### P10-R0 現行固定 — 完了

- 旧active Runtime Student 35/183を比較基準として凍結
- KA59 7/7 candidateを未採用証拠として保持
- C2/C3、negative-only probe、個別operator追加を現行selectorから除外

R0の35/183とRHAE 18.821945363%は旧Runtime Studentの回帰値であり、
後述の特権Teacher値と混同しない。

### P10-R1 Teacher 183閉包 — 完了

2026-07-26に次を同一OFFLINE runで確認した。

| 指標 | 結果 |
|---|---:|
| game | 25/25 |
| level | 183/183 |
| executable action | 11,574 |
| error | 0 |
| GAME_OVER | 0 |
| max-action stop | 0 |
| available-action mismatch | 0 |
| level-reset compatibility event | 64 |
| source frame digest mismatch | 542 |
| local completion | 100% |
| privileged Teacher RHAE | 99.446886157% |
| S1 state graph | 11,387 node / 11,383 edge |
| S1 executable action | 10,733 |
| S1 privileged Teacher RHAE | 99.619936696% |
| S1 RHAE delta vs S0 | +0.173050539 percentage point |
| S1 fixed-action decision dependency | 0 |

Public human trajectory inventoryは25 game、183 level、11,648 recorded action。
FT09の公開trajectoryは保持サンプルの旧revisionを対象としていたため、既存の
content-bound local success evidence 75 actionを現行環境で再実行し、6/6を
確認して一件だけ監査付きoverrideした。

R11Lを含む`RESET`はrecorded `full_reset: false`を保持するため、当該action中
だけlevel-reset互換scopeを適用し、環境変数をaction後に必ず復元する。

542件のsource frame digest差分があるため、source frameのbyte同一性は主張
しない。全11,574 actionの実環境状態遷移、level進捗、available action、
最終WINは一致している。

正本:

- `analysis/teacher/FULL_SOLUTION_CORPUS.json`
- `analysis/teacher/TEACHER_S0_CLOSURE_REPORT.json`
- `analysis/teacher/TEACHER_S0_LOCAL_SCORE_ORACLE.json`

### P10-R2 解法グラフ生成 — 完了

183 level全てについて、次を持つS0 graphを生成済み。

- observation model
- objects、roles
- state variables、hidden-variable slot
- goal/progress/hazard/commit predicates
- action transition model
- successful solution trajectory
- recorded reset/recovery contrast
- necessary/sufficient conditions
- privilege dependencies

2026-07-26に、保持中の25 environment sourceを直接AST解析し、全183 graphへ
次をcontent-boundで付与した。

- 25 source fileのSHA-256と183 `Level(...)`定義
- levelごとのsource object family、data、transform
- `step`から到達可能なaction control-flow
- 25 `next_level()` goal witness
- 43 `lose()` hazard witness
- 20 custom hidden-state exportと5 explicit-none boundary
- source state、actor/manipuland候補集合、goal/hazard参加状態
- 実行済み成功trajectoryとsource hazard pathの因果contrast

結果は`causal_semantic_complete_count: 183`、
`success_failure_contrast_complete_count: 183`である。

sourceは難読化されているため、旧解析のhuman-readable mechanic名をsource fact
とは扱わない。名称・effect class・semantic state名は
`DEVELOPMENT_HYPOTHESIS`として直接source evidenceへ束縛し、Runtime ruleには
採用していない。また、実行していないnegative action列をfailure replayとして
捏造せず、sourceが定義する`lose()` control pathと実行済み成功pathのcontrast
だけを主張する。

正本:

- `analysis/teacher/LEVEL_SOLUTION_GRAPH_LEDGER.json`

### P10-R3 構造文法抽出 — 完了

25 game内のlevel N→N+1差分158 edgeについて、action primitiveに加え、
source object family、causal role、level data、semantic state、goal/hazardの
差分を抽出した。全158 edgeがsource-causal graphへ束縛されている。

game/level ID・literal座標を含まないcross-game primitive grammarには、
183 graphのsource-causal role registryと開発仮説のeffect class分布を分離して
保持した。

grammarは183 S0 graphから因数分解した構造候補である。固定actionなしの
S1実行証拠はR4で別に束縛する。

正本:

- `analysis/teacher/INTRA_GAME_PROGRESSION_GRAPH.json`
- `analysis/teacher/CROSS_GAME_STRUCTURAL_GRAMMAR.json`

### P10-R4 構造実行器 — 完了

S0 compilerだけが`FULL_SOLUTION_CORPUS`を読み、11,574成功遷移を
11,387 current-state node、11,383 action edgeへ変換した。S1 executorは
corpusをimportせず、次だけでedgeを選ぶ。

- 現在のrendered frame digest
- available action、level完了数、terminal state
- S1でまだ許可されるsource/hidden state digest
- action/effect履歴の固定長4 suffix
- WINからのreverse-BFS距離

同一状態に複数edgeがある場合も、全観測targetでWIN距離が厳密に減少する
actionだけを採用する。`step`、cursor、replay index、action ordinalはgraph
schemaで禁止し、executor sourceはcorpus依存を持たない。

work block契約:

- `X`: S0成功遷移、保持OFFLINE環境、S1 Teacher packageだけを観測し、
  state graph、executor、S1証拠だけを変更する。
- `R`: current-state conditionからgraph nodeを引き、選択edge実行後に再観測し、
  WIN距離の厳密減少とlevel commitを検証する。
- `Mc`: 25/25 game、183/183 level、error 0、node miss 0、unexpected target 0、
  全actionで距離減少の場合だけS1を`PASS`とする。
- 非目的: literal座標、ID routing、source/hidden state、answer/replay graphの
  除去、およびRuntime Student Pへの採用。
- 証拠境界: S1は開発用Teacher証拠でありrendered-only能力ではない。
- 反証条件: position key、corpus import、距離非減少、未知node/target、
  `GAME_OVER`、未完levelのいずれか。
- 回帰線: S0 183/183を維持し、同じOFFLINE sampleでS1も183/183。

結果:

- source transition witness: 11,574
- state node: 11,387
- action edge: 11,383
- branch node: 20
- merged state node: 110
- nondeterministic same-action target: 0
- S1 executable action: 10,733
- fixed action sequence / replay position / action ordinal decision: 0
- same-sample local oracle: RHAE 99.619936696%
- S0 local-oracle delta: +0.173050539 percentage point
- full graph rerun: byte-identical
  (`sha256:d3f5685c52fbbc644d47f10c7124cec93950dd5b40c9b30a0f3df4ef88b98223`)
- full closure rerun: byte-identical
  (`sha256:7f09a63e7014720bf5b0822a97de6152b76cae8074ce0357409e2498ad60ac90`)

正本:

- `analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json`
- `analysis/teacher/TEACHER_S1_CLOSURE_REPORT.json`

### P10-R5 水平減算 — S2待機

S1は完了した。次はliteral座標を除去するS2であり、S3以降へ先行しない。

正本:

- `analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json`
- `analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json`

現状のRuntime P reportは`BLOCKED_BY_S2_LITERAL_COORDINATES`であり、
Runtime P変更・rule採用・graph採用はいずれも0である。

### P10-R6 汎化試験 — 未開始

S5が183/183になるまで開始しない。

## 5. 現行停止対象

次はR0のhistorical evidenceとして保持するが、現行work selectorにはしない。

- 正例なしの能力cluster探索
- 大量shadow probe
- predictor accuracy単独の改善
- visible changeを進歩とする判定
- level専用operator追加
- 早期identity除去
- negative-only監査の反復
- `WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER`

C2 observer、C3 predictor、C10 composition等の過去結果は削除しないが、
R1以降の採否を決める正本ではない。

## 6. 正本成果物

```text
analysis/teacher/FULL_SOLUTION_CORPUS.json
analysis/teacher/LEVEL_SOLUTION_GRAPH_LEDGER.json
analysis/teacher/INTRA_GAME_PROGRESSION_GRAPH.json
analysis/teacher/CROSS_GAME_STRUCTURAL_GRAMMAR.json
analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json
analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json
```

補助証拠:

```text
analysis/teacher/HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json
analysis/teacher/LOCAL_SOLUTION_OVERRIDE_MANIFEST.json
analysis/teacher/TEACHER_S0_CLOSURE_REPORT.json
analysis/teacher/TEACHER_S0_ORACLE_ADAPTER_REPORT.json
analysis/teacher/TEACHER_S0_LOCAL_SCORE_ORACLE.json
analysis/teacher/TEACHER_S0_LOCAL_SCORE_ORACLE.md
analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json
analysis/teacher/TEACHER_S1_CLOSURE_REPORT.json
analysis/teacher/TEACHER_S1_ORACLE_ADAPTER_REPORT.json
analysis/teacher/TEACHER_S1_LOCAL_SCORE_ORACLE.json
analysis/teacher/TEACHER_S1_LOCAL_SCORE_ORACLE.md
```

## 7. 再生成・検証

```bash
cd ARC-AGI-3-Agents

python -m arc3_agi_agent.teacher.human_replay_corpus validate \
  --corpus ../analysis/teacher/FULL_SOLUTION_CORPUS.json

python -m arc3_agi_agent.teacher.replay_runner \
  --environments-dir ../environment_files \
  --corpus ../analysis/teacher/FULL_SOLUTION_CORPUS.json \
  --output ../analysis/teacher/TEACHER_S0_CLOSURE_REPORT.json

python -m arc3_agi_agent.teacher.s1_graph_compiler \
  --environments-dir ../environment_files \
  --corpus ../analysis/teacher/FULL_SOLUTION_CORPUS.json \
  --output \
    ../analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json

python -m arc3_agi_agent.teacher.s1_graph_executor \
  --environments-dir ../environment_files \
  --policy-graph \
    ../analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json \
  --output ../analysis/teacher/TEACHER_S1_CLOSURE_REPORT.json

python -m arc3_agi_agent.teacher.solution_graph_compiler \
  --corpus ../analysis/teacher/FULL_SOLUTION_CORPUS.json \
  --closure-report ../analysis/teacher/TEACHER_S0_CLOSURE_REPORT.json \
  --environments-dir ../environment_files \
  --development-level-ledger \
    ../analysis/development/LEGACY_LEVEL_ANALYSIS_LEDGER.json \
  --s1-policy-graph \
    ../analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json \
  --s1-closure-report \
    ../analysis/teacher/TEACHER_S1_CLOSURE_REPORT.json \
  --output-dir ../analysis/teacher

python -m pytest -q \
  tests/unit/test_teacher_complete_closure.py \
  tests/integration/test_teacher_s0_replay.py \
  tests/integration/test_teacher_s1_graph.py
```

## 8. 次work block

```text
WB-S2-LITERAL-COORDINATE-SUBTRACTION
```

R1〜R4とS1は閉じた。次はS1 graphのpointer targetをrole-relative selectorへ
変換し、literal x/yを一切読まずにS2を183/183へ閉じる。S2が183/183に
なる前にS3以降へ進まない。
