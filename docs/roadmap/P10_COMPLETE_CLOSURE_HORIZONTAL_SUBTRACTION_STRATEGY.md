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
| S1 | 固定action列を禁止 | 183/183 | `NOT_RUN` |
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

### P10-R2 解法グラフ生成 — 進行中

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

現状は全183 graphが成功trajectoryと実行結果へ束縛されている。一方、source
からのmechanic名、actor/object role、hidden variable、失敗因果の意味付けは
未完了である。したがって`causal_semantic_complete_count`は0とし、
R2全体を完了扱いしない。

正本:

- `analysis/teacher/LEVEL_SOLUTION_GRAPH_LEDGER.json`

### P10-R3 構造文法抽出 — 進行中

25 game内のlevel N→N+1差分158 edgeと、game/level ID・literal座標を含まない
cross-game primitive grammarを生成済み。

grammarは183 S0 graphから因数分解した構造候補であり、固定actionなしの実行
能力はまだ証明していない。

正本:

- `analysis/teacher/INTRA_GAME_PROGRESSION_GRAPH.json`
- `analysis/teacher/CROSS_GAME_STRUCTURAL_GRAMMAR.json`

### P10-R4 構造実行器 — 未開始

完了条件:

- graphから観測条件付きplanを生成する
- 固定action列を読まない
- 全183 levelを同一条件で完了する
- S1を183/183で閉じる

### P10-R5 水平減算 — 未開始

S1、S2、S3、S4、S5を絶対順序で実行する。

正本:

- `analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json`
- `analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json`

現状のRuntime P reportは`BLOCKED_BY_UNSUBTRACTED_S0_PRIVILEGES`であり、
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

python -m arc3_agi_agent.teacher.solution_graph_compiler \
  --corpus ../analysis/teacher/FULL_SOLUTION_CORPUS.json \
  --closure-report ../analysis/teacher/TEACHER_S0_CLOSURE_REPORT.json \
  --output-dir ../analysis/teacher

python -m pytest -q \
  tests/unit/test_teacher_complete_closure.py \
  tests/integration/test_teacher_s0_replay.py
```

## 8. 次work block

```text
WB-SOLUTION-GROUNDED-183-CLOSURE-AND-GRAPH-COMPILATION
```

このblockの残作業は、183 graphへsource-grounded object/role/state/goal/hazard
因果を付与し、成功/失敗contrastを閉じることである。その後だけ
`WB-S1-FIXED-ACTION-SUBTRACTION-EXECUTOR`へ進む。
