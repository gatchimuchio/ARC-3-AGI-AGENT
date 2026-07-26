# P10 完全閉包先行・水平減算戦略

- phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- strategy: `COMPLETE_CLOSURE_FIRST_HORIZONTAL_SUBTRACTION`
- state: `COMPLETE`
- operation mode: `OFFLINE` only
- Teacher boundary: `DEVELOPMENT_ONLY`
- Runtime Student boundary: `RENDERED_ONLY`
- successor: `P11_RELEASE_STATE_FREEZE`
- successor state: `COMPLETE`

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
| S2 | literal座標も禁止 | 183/183 | `PASS` |
| S3 | task/game/level ID routingも禁止 | 183/183 | `PASS` |
| S4 | source/hidden stateも禁止 | 183/183 | `PASS` |
| S5 | rendered observationと履歴のみ | 183/183 | `PASS` |
| S6 | 色・回転・反転・配置・個数・順序・未観測合成を摂動 | 汎化測定 | `MEASURED_NOT_PROVEN` |

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
| S2 role-relative graph | 10,758 node / 10,733 edge |
| S2 executable action | 10,733 |
| S2 rendered role resolution | 3,112 |
| S2 relative relation constraint | 26,623 |
| S2 stored absolute pointer payload | 0 |
| S2 selector failure / error | 0 / 0 |
| S2 privileged Teacher RHAE | 99.619936696% |
| S2 RHAE delta vs S1 | 0 percentage point |
| S3 global policy partition | 1 |
| S3 identity key / literal / decision | 0 / 0 / 0 |
| S3 global state graph | 10,758 node / 10,733 edge |
| S3 branch / nondeterministic action | 0 / 0 |
| S3 executable action | 10,733 |
| S3 privileged Teacher RHAE | 99.619936696% |
| S3 RHAE delta vs S2 | 0 percentage point |
| S4 target source/hidden read / decision | 0 / 0 |
| S4 global state graph | 10,758 node / 10,733 edge |
| S4 branch / merge / nondeterministic action | 0 / 0 / 0 |
| S4 executable action | 10,733 |
| S4 privileged Teacher RHAE | 99.619936696% |
| S4 RHAE delta vs S3 | 0 percentage point |

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

### P10-R5 水平減算 — 完了

S2 compilerだけがS1 graphのpointer targetを観測し、absolute targetを
target-centred rendered relationへ変換する。S2 graphとexecutorは
`action_data`、absolute x/y、row/column、coordinate、replay position、
action ordinalを保持しない。環境APIがpointer payloadを要求する時だけ、
current renderから一意解決したtargetをtransient payloadとして生成する。

work block契約:

- `X`: S1 graph、保持OFFLINE環境、S2 Teacher packageだけを観測し、
  role selector、S2 graph/executor、S2証拠だけを変更する。
- `R`: current-state nodeを引き、pointer actionならtarget-centred palette
  relationをcurrent renderへ照合して一意targetを得て、一手後に再観測する。
- `Mc`: 25/25 game、183/183 level、error 0、selector failure 0、
  absolute payload保存0、全actionでWIN距離減少の場合だけS2を`PASS`とする。
- 非目的: ID routing、source/hidden state、answer/replay graphの除去、
  Runtime Student Pへの採用。
- 証拠境界: S2は開発用Teacher証拠でありidentity-freeまたは
  rendered-only能力ではない。
- 反証条件: graph内absolute target key、selector曖昧/不一致、未知node/target、
  距離非減少、`GAME_OVER`、未完levelのいずれか。
- 回帰線: 同じOFFLINE sampleとlocal oracleでS1の183/183・RHAEを維持する。

結果:

- source transition witness / executable action: 10,733
- state node / action edge: 10,758 / 10,733
- branch / merged / nondeterministic action: 0 / 0 / 0
- rendered role selector resolution: 3,112
- boundary relationを必要としたselector: 204
- relative relation constraint: 26,623
- stored absolute pointer payload: 0
- selector failure / node miss / unexpected target / error: 0 / 0 / 0 / 0
- same-sample local oracle: RHAE 99.619936696%
- S1 local-oracle delta: 0 percentage point
- full graph rerun: byte-identical
  (`sha256:082e8b33cb104286ad2f5706fc582e01dd564e2373427d9e0436dc62ee7d1956`)
- full closure rerun: byte-identical
  (`sha256:389ead42c459333a2302f180ff9d2fa99d3af51378fdd1ffa102e8dff3c8ff80`)

正本:

- `analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json`
- `analysis/teacher/TEACHER_S2_CLOSURE_REPORT.json`

S3 compilerだけがS2のgame別partitionとIDを開発入力として観測し、全成功遷移を
一つのglobal state/action graphへ統合する。S3 graphはtask/game/level ID、
game class、level progress counter、game別partition、具体的sample ID literalを
保持しない。executorのaction選択関数は環境IDを受け取らず、評価harnessだけが
OFFLINE環境の作成と結果帰属にIDを使用する。

work block契約:

- `X`: S2 graph、保持OFFLINE環境、S3 Teacher packageだけを観測し、
  global graph/state/executor、S3証拠だけを変更する。
- `R`: identity-routing-freeなcurrent-state署名をglobal indexから一意に引き、
  WIN距離を厳密に減らすedgeを選び、一手後に再観測する。
- `Mc`: 25/25 game、183/183 level、error 0、identity routing decision 0、
  policy partition 1、graph内identity key/literal 0、全actionでWIN距離減少の
  場合だけS3を`PASS`とする。
- 非目的: source/hidden state、answer/replay graphの除去、Runtime Student P採用。
- 証拠境界: S3は開発用Teacherの明示ID-routing除去証拠であり、
  source-state-free、rendered-only、汎化能力の証拠ではない。
- 反証条件: action選択への環境ID入力、game別graph lookup、identity key/literal、
  未知node/target、距離非減少、`GAME_OVER`、未完levelのいずれか。
- 回帰線: 同じOFFLINE sampleとlocal oracleでS2の183/183・RHAEを維持する。

結果:

- source transition witness / executable action: 10,733
- global state node / action edge: 10,758 / 10,733
- branch / merged / cross-environment merged: 0 / 0 / 0
- nondeterministic action: 0
- policy partition: 1
- identity routing key / explicit ID literal / decision: 0 / 0 / 0
- action selectionへのenvironment identity入力: false
- level progress counter decision: false
- rendered role selector resolution: 3,112
- selector failure / node miss / unexpected target / error: 0 / 0 / 0 / 0
- same-sample local oracle: RHAE 99.619936696%
- S2 local-oracle delta: 0 percentage point
- full graph rerun: byte-identical
  (`sha256:b9e733ec99982359eecb92b06f78ded6bbefd1c41d724d823f454fb7300166a6`)
- full closure rerun: byte-identical
  (`sha256:297c171685d5754a6ee3907fea18548e03072eb0eb18a6478462bf48b61f422f`)

正本:

- `analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json`
- `analysis/teacher/TEACHER_S3_CLOSURE_REPORT.json`

S4 compilerは、使い捨てS3 mirrorから既証明のanswer trajectoryだけを回収し、
別に生成したfresh target環境へ同じ構造actionを適用する。target側の状態署名は
render、available action、terminal、固定長4の観測action/effect履歴だけから
生成し、environment wrapper、source object、hidden state、identityを
action selectorへ渡さない。S3 mirrorのconditionはS4 graphへ保存しない。

S3 graphから`source_state_digest`だけを機械的に削除する初期案は棄却した。
`ls20._get_hidden_state()`がrender制御値を書き換える副作用を持ち、
hidden読取を除去した正しいS4実行とS3収集時のrenderが367 action目で分岐した
ためである。fresh target再収集に是正後、`ls20`は7/7 level、472 actionで
再現した。

work block契約:

- `X`: S3 global graph、保持OFFLINE環境、S4 Teacher packageだけを観測し、
  source/hidden未読target graph/executor、S4証拠だけを変更する。
- `R`: disposable mirrorはanswer trajectory回収だけを行い、fresh targetの
  render/history状態をglobal indexへ登録する。runtime action選択はその
  observation-only署名からWIN距離を厳密に減らすedgeを選ぶ。
- `Mc`: 25/25 game、183/183 level、error 0、target source/hidden read 0、
  source/hidden decision 0、policy partition 1、全actionでWIN距離減少の場合だけ
  S4を`PASS`とする。
- 非目的: answer/replay由来exact graphの除去、Runtime Student P採用、S5、
  perturbation汎化。
- 証拠境界: S4はsource/hidden runtime依存除去の開発用Teacher証拠であり、
  rendered-only Runtime Studentまたは汎化能力の証拠ではない。
- 反証条件: targetでのsource/hidden getter呼出し、graphへのsource key保持、
  未知node/target、距離非減少、`GAME_OVER`、未完levelのいずれか。
- 回帰線: 同じOFFLINE sampleとlocal oracleでS3の183/183・RHAEを維持する。

結果:

- source transition witness / executable action: 10,733
- global state node / action edge: 10,758 / 10,733
- branch / merge / nondeterministic action: 0 / 0 / 0
- policy partition: 1
- identity routing key / source-hidden decision key: 0 / 0
- target environment source/hidden read: 0
- action selectionへのenvironment wrapper/source/hidden入力: false
- rendered role selector resolution: 3,112
- selector failure / node miss / unexpected target / error: 0 / 0 / 0 / 0
- same-sample local oracle: RHAE 99.619936696%
- S3 local-oracle delta: 0 percentage point
- full graph rerun: byte-identical
  (`sha256:09fbd408ce7ee34d7598a67f8d8cc8951d60c3a280e80107058db339313954c8`)
- full closure rerun: byte-identical
  (`sha256:5b75363a82a1565db79a0369bcabcfe653aa4d77623d06321a92b236489e04f0`)

正本:

- `analysis/teacher/S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json`
- `analysis/teacher/TEACHER_S4_CLOSURE_REPORT.json`
- `analysis/teacher/TEACHER_S4_ORACLE_ADAPTER_REPORT.json`
- `analysis/teacher/TEACHER_S4_LOCAL_SCORE_ORACLE.json`
- `analysis/teacher/TEACHER_S4_LOCAL_SCORE_ORACLE.md`
- `analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json`
- `analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json`

S5ではS4成功trajectoryからdevelopment-only training corpusを作り、
rendered observation、available action、最大16件のaction/effect履歴だけを
入力とするMLP parameter bodyへコンパイルした。Runtime artifactにはtraining
frame、label、game ordinal、level progress、answer/replay graphを含めない。
Runtime側はTeacher package、`analysis/teacher`、environment identity、
source/hidden stateをimport・参照しない。

結果:

- game / level: 25/25 / 183/183
- action / error: 10,733 / 0
- deterministic seed: 0
- HDS compute command: 10,733
- HDS-authorized external emission: 10,691
- HDS-authorized policy reset: 42
- GAME_OVER observation / factual retention: 12 / 12
- pointer payload: 3,112
- Mが判断へ影響したaction: 10,708
- Runtime P parameter: 4,269,485 float16
- Teacher-forced / quantized error: 0 / 0
- runtime policy digest:
  `sha256:87408c43b6dad4f82111f1b06b19fdf028f32a832ec9259694bcde7ee4d9c464`
- local oracle: completion 100%、RHAE 99.619936696%、error 0
- full S5 rerun SHA-256:
  `3d28de66699b07a95ef7c8c5872d7158c338fd230ce10039ccddc80445b93c2b`
- two full S5 reports: byte-identical

`S5_SHORTCUT_AND_AUTHORITY_AUDIT.json`はshortcut、identity、Teacher import、
HDS command/write/reset/emit境界を検査し`PASS`である。一方、observable
action surfaceがgame分布のproxyになり得ること、同一renderだけではactionが
一意でない190 conflict groupがありhistoryが必要なことを残存リスクとして
保持する。same-sample 183/183は未知構造への汎化証明ではない。

### P10-R6 汎化試験 — 測定完了・汎化未証明

全25 game・183 levelを覆う固定2,048 corpus recordに対し、S5 Pを変更せず
七摂動、合計14,336 responseを測定した。transformed environmentは実行せず、
semantic ground truthは利用できないため、指標は元Teacher actionに対する
response retentionでありcorrectnessではない。

| family | action retention |
|---|---:|
| COLOR | 1,019 / 2,048 = 49.755859375% |
| ROTATION | 1,173 / 2,048 = 57.275390625% |
| REFLECTION | 1,275 / 2,048 = 62.255859375% |
| LAYOUT | 1,271 / 2,048 = 62.060546875% |
| OBJECT_COUNT | 2,010 / 2,048 = 98.14453125% |
| ORDER | 1,337 / 2,048 = 65.283203125% |
| UNSEEN_COMPOSITION | 950 / 2,048 = 46.38671875% |

baseline action/pointer error、unknown action surface、unavailable action、
exceptionはいずれも0。二回のS6 reportはSHA-256
`66e71375b02812e3e03a1f5af045f4c69cfd3a6e3db54f234d0c6a649304151d`
でbyte-identicalである。HDS結論は
`S6_MEASURED_HOLD_GENERALIZATION_CLAIM`、claimは
`MEASURED_NOT_PROVEN`に固定する。

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
analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json
analysis/teacher/TEACHER_S2_CLOSURE_REPORT.json
analysis/teacher/TEACHER_S2_ORACLE_ADAPTER_REPORT.json
analysis/teacher/TEACHER_S2_LOCAL_SCORE_ORACLE.json
analysis/teacher/TEACHER_S2_LOCAL_SCORE_ORACLE.md
analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json
analysis/teacher/TEACHER_S3_CLOSURE_REPORT.json
analysis/teacher/TEACHER_S3_ORACLE_ADAPTER_REPORT.json
analysis/teacher/TEACHER_S3_LOCAL_SCORE_ORACLE.json
analysis/teacher/TEACHER_S3_LOCAL_SCORE_ORACLE.md
analysis/teacher/S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json
analysis/teacher/TEACHER_S4_CLOSURE_REPORT.json
analysis/teacher/TEACHER_S4_ORACLE_ADAPTER_REPORT.json
analysis/teacher/TEACHER_S4_LOCAL_SCORE_ORACLE.json
analysis/teacher/TEACHER_S4_LOCAL_SCORE_ORACLE.md
analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json
analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.npz
analysis/teacher/S5_RUNTIME_P_COMPILATION_REPORT.json
analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json
analysis/runtime/S5_FULL_EXECUTION_TRACE.jsonl.gz
analysis/runtime/S5_FULL_EXECUTION_TRACE_MANIFEST.json
analysis/runtime/S5_SHORTCUT_AND_AUTHORITY_AUDIT.json
analysis/runtime/S5_ORACLE_ADAPTER_REPORT.json
analysis/runtime/S5_LOCAL_SCORE_ORACLE.json
analysis/runtime/S5_LOCAL_SCORE_ORACLE.md
analysis/runtime/S6_PERTURBATION_MEASUREMENT.json
analysis/release/P10_REPRODUCIBILITY_AUDIT.json
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

python -m arc3_agi_agent.teacher.s2_graph_compiler \
  --environments-dir ../environment_files \
  --s1-policy-graph \
    ../analysis/teacher/S1_STATE_CONDITIONED_POLICY_GRAPH.json \
  --output ../analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json

python -m arc3_agi_agent.teacher.s2_graph_executor \
  --environments-dir ../environment_files \
  --policy-graph \
    ../analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json \
  --output ../analysis/teacher/TEACHER_S2_CLOSURE_REPORT.json

python -m arc3_agi_agent.teacher.s3_graph_compiler \
  --environments-dir ../environment_files \
  --s2-policy-graph \
    ../analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json \
  --output \
    ../analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json

python -m arc3_agi_agent.teacher.s3_graph_executor \
  --environments-dir ../environment_files \
  --policy-graph \
    ../analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json \
  --output ../analysis/teacher/TEACHER_S3_CLOSURE_REPORT.json

python -m arc3_agi_agent.teacher.s4_graph_compiler \
  --environments-dir ../environment_files \
  --s3-policy-graph \
    ../analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json \
  --output \
    ../analysis/teacher/S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json

python -m arc3_agi_agent.teacher.s4_graph_executor \
  --environments-dir ../environment_files \
  --policy-graph \
    ../analysis/teacher/S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json \
  --output ../analysis/teacher/TEACHER_S4_CLOSURE_REPORT.json

python -m arc3_agi_agent.s5_runner \
  --environments-dir ../environment_files \
  --seed 0 --max-actions 4096 \
  --trace-jsonl \
    ../analysis/runtime/S5_FULL_EXECUTION_TRACE.jsonl.gz \
  --trace-manifest \
    ../analysis/runtime/S5_FULL_EXECUTION_TRACE_MANIFEST.json \
  --output ../analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json

python -m arc3_agi_agent.teacher.s5_runtime_audit \
  --package-dir arc3_agi_agent \
  --manifest arc3_agi_agent/bundles/s5_rendered_policy_v1.json \
  --weights arc3_agi_agent/bundles/s5_rendered_policy_v1.npz \
  --closure-report \
    ../analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json \
  --policy-compilation-report \
    ../analysis/teacher/S5_RUNTIME_P_COMPILATION_REPORT.json \
  --training-corpus \
    ../analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.npz \
  --output ../analysis/runtime/S5_SHORTCUT_AND_AUTHORITY_AUDIT.json

python -m arc3_agi_agent.teacher.s6_generalization \
  --corpus \
    ../analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.npz \
  --corpus-manifest \
    ../analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json \
  --output ../analysis/runtime/S6_PERTURBATION_MEASUREMENT.json

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
  --s2-policy-graph \
    ../analysis/teacher/S2_ROLE_RELATIVE_POLICY_GRAPH.json \
  --s2-closure-report \
    ../analysis/teacher/TEACHER_S2_CLOSURE_REPORT.json \
  --s3-policy-graph \
    ../analysis/teacher/S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json \
  --s3-closure-report \
    ../analysis/teacher/TEACHER_S3_CLOSURE_REPORT.json \
  --s4-policy-graph \
    ../analysis/teacher/S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json \
  --s4-closure-report \
    ../analysis/teacher/TEACHER_S4_CLOSURE_REPORT.json \
  --s5-closure-report \
    ../analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json \
  --s5-policy-compilation-report \
    ../analysis/teacher/S5_RUNTIME_P_COMPILATION_REPORT.json \
  --s5-runtime-audit \
    ../analysis/runtime/S5_SHORTCUT_AND_AUTHORITY_AUDIT.json \
  --s6-generalization-report \
    ../analysis/runtime/S6_PERTURBATION_MEASUREMENT.json \
  --output-dir ../analysis/teacher

python -m pytest -q \
  tests/unit/test_s5_execution_trace.py \
  tests/unit/test_teacher_complete_closure.py \
  tests/integration/test_teacher_s0_replay.py \
  tests/integration/test_teacher_s1_graph.py \
  tests/unit/test_teacher_s2_role_selector.py \
  tests/integration/test_teacher_s2_graph.py \
  tests/unit/test_teacher_s3_state.py \
  tests/integration/test_teacher_s3_graph.py \
  tests/unit/test_teacher_s4_state.py \
  tests/integration/test_teacher_s4_graph.py
```

## 8. 後続状態

```text
P11_RELEASE_STATE_FREEZE = COMPLETE
P12_PRE_OFFICIAL_AGI_CONFORMANCE_AND_GENERICITY = ACTIVE
```

P10-R0〜R6は順序通り閉じた。P11はpolicyやscoreを変更せず、code、
dependency、Python、P0/J0/M0、dataset、compiler、seed、budget、全sample
証拠、regression suite、reproducible package digestをrelease stateへ固定して
完了した。P12ではP11をknown-sample baselineとして凍結し、separate
GenericAGIRuntimeのoperational conformanceとgenericityを反証する。
公式接続はP13以降である。
