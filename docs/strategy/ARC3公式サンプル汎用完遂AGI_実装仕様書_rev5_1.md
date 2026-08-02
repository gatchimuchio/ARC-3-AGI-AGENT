# ARC3公式サンプル汎用完遂AGI 実装仕様書 rev5.1

- 仕様ID: `ARC3_OFFICIAL_SAMPLE_GENERIC_COMPLETION_AGI_SPEC_REV5_1`
- 製品名: `ARC3CompletionAgent`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 対象環境: ARC Prize 2026 / ARC-AGI-3公式サンプル
- 最終成果物: 公式サンプル25 game／183 levelを同一構造で自律完遂する統合AGIエージェント
- 基底理論:
  - `HDSフレーム rev3.1a（仮）内部用統合仕様`
  - `AGI三主体統合設計図 v0.1`
- 下位正本:
  - `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev5_1.md`
  - `docs/instructions/ARC3公式サンプル汎用完遂AGI_ロードマップ準拠指示書_rev5_1.md`
- 旧rev4製品案: `HISTORICAL_SUPERSEDED`
- 状態: `OWNER_DIRECTIVE_CANDIDATE`

---

## 0. 固定結論

本開発の完成品は、仕様書、ロードマップ、分析資料、構造データ、PBundle、runner、shellではない。

完成品は次である。

```text
ARC3CompletionAgent
=
公式ARC3環境を観測し
現在の目的・状態・機構を解釈し
仮説・反対仮説・probe・計画を生成し
HDS判断主体が一手を採否し
結果を可変記憶へ反映し
次の計算と判断を更新しながら
人間の逐次指示なしに
公式サンプル25 game／183 levelを完遂する
統合AGIエージェント
```

HDS解析、成功軌道、回答、環境ソース、構造抽出、命令形P、J初期状態、M初期状態は、上記製品能力を構築する素材・手段・内部部品である。

次は単独では開発完了ではない。

```text
HDS解析完了
構造抽出完了
P生成完了
AGI骨格実装完了
agent class作成
runner作成
試験PASS
一部game完遂
```

開発完了は、統合製品が本仕様の完成式を実測で満たした時点だけに成立する。

---

## 1. 最上位目的と完成式

### 1.1 Terminal Purpose

```text
公式サンプル25 game／183 levelを
同一のARC3CompletionAgent製品で
汎用的かつ自律的に完全攻略する
```

### 1.2 完成式

```text
ARC3_PRODUCT_COMPLETE
=
ONE_PRODUCT_ARTIFACT
AND ONE_ACTIVE_PRODUCT_BUNDLE
AND C_EQUALS_EXECUTE_L0_P
AND CLOSED_TRINITY_C_J_M
AND J_AUTHORIZES_EVERY_EXTERNAL_ACTION
AND M_CHANGES_FUTURE_COMPUTATION_OR_JUDGEMENT
AND NO_MANUAL_STEP_INTERVENTION
AND NO_FIXED_TRAJECTORY_PLAYBACK
AND NO_IDENTITY_ACTION_ROUTER
AND OFFICIAL_SAMPLE_25_OF_25_WIN
AND OFFICIAL_SAMPLE_183_OF_183_COMPLETE
AND CLEAN_STATE_REPEAT_PASS
```

### 1.3 未完成条件

次のいずれかが存在する場合、製品は未完成である。

- 未完遂gameまたはlevelがある
- 人間がgame途中のaction、対象、順序、probe、resetを指定する
- 成功軌道をそのまま再生する
- `game_id`、`level_id`、frame完全hashから答えを選択する
- Jを迂回してC、Adapter、runnerが外部actionを確定する
- M更新後も未来の候補・計画・判断が変化しない
- Pを除去・交換してもARC3能力が変化しない
- C／J／M責任が混線する

---

## 2. エンドポイントからの逆算

```text
E0  25/25 WIN・183/183 COMPLETE
↑
E1  同一AGIエージェントが全gameを自律攻略できる
↑
E2  C/J/M/Pが閉ループで機構同定・計画・学習できる
↑
E3  ARC3攻略能力を持つP/J0/M0が製品へ統合されている
↑
E4  game／levelの目的、機構、状態遷移、失敗構造がHDSで解釈されている
↑
E5  成功軌道、回答、観測、環境ソース、既存解析資産が利用可能である
```

実装作業はE5からE0へ進むが、作業の採否は常にE0から逆算して決定する。

すべての作業に対し、次を問う。

```text
この作業は、
1. ARC3タスクの機構理解を進めるか
2. P/J0/M0の攻略能力を増やすか
3. C/J/Mのオンライン循環を強化するか
4. 完遂game数または完遂level数を増やすか
5. 観測済みの製品阻害要因を直接除去するか
```

すべてNOなら、その作業は現在実施しない。

---

## 3. 公式環境契約

### 3.1 入力

製品は毎cycle、公式`EnvironmentWrapper`から`FrameDataRaw`を受け取る。

```text
FrameDataRaw:
  frame[]
  state
  levels_completed
  win_levels
  action_input
  full_reset
  available_actions
```

`frame[]`は複数layerを持ち得る。最終layerだけへ縮退してはならない。

### 3.2 出力

製品は一cycleにつき一つの合法な`GameAction`を出力する。

```text
RESET   = 0
ACTION1 = 1
ACTION2 = 2
ACTION3 = 3
ACTION4 = 4
ACTION5 = 5
ACTION6 = 6, payload = {x, y}
ACTION7 = 7
```

ACTION6の座標は現在観測から生成する。固定座標表または成功軌道lookupを使用しない。

### 3.3 終端

```text
NOT_FINISHED
WIN
GAME_OVER
```

`GAME_OVER`は原因帰属、rollback、RESET、計画更新の対象になり得る。

### 3.4 自律境界

人間が与えるのは高位目的だけである。

```text
公式サンプルを完遂せよ
```

以後の観測、問い、仮説、probe、行動、待機、rollback、reset、停止は製品内部で決定する。

---

## 4. 「汎用的完遂」の運用定義

本仕様の汎用性は、未知宇宙全体に対する全称命題ではない。

公式サンプルに対して次を満たすことを意味する。

### 4.1 同一構造

- 同じ`ARC3CompletionAgent`
- 同じC／J／M責任分離
- 同じLayer-0契約
- 同じP／J0／M0形式
- 同じRuntime Loop
- 同じHDS Gate体系

### 4.2 禁止される個別化

```text
game_id → 完成行動列
level_id → 完成行動列
frame完全hash → 次の正解action
trajectory index → playback
hidden answer map
```

### 4.3 許可される個別化

- 現在観測から抽出したentity、role、relation、state
- 現在観測から推定したtask／mechanism
- パラメータ化した汎用構造
- 同一構造への異なる対象、座標、順序、goalのbinding
- 答え列ではなく宣言的機構として保持されたDomain-Local Residue
- 実行中にMへ獲得した現在gameの機構モデル

### 4.4 Applicability Predicate

各MechanismSpecは、現在観測だけから評価できる適用条件を持つ。

```yaml
ApplicabilityPredicate:
  required_entities:
  required_relations:
  required_state_pattern:
  required_action_surface:
  temporal_conditions:
  negative_conditions:
  falsification_condition:
```

禁止feature:

```text
game_id
level_id
recording_id
trajectory_id
full-frame exact hash
successful action index
```

---

## 5. AGI製品アーキテクチャ

### 5.1 基本式

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
ARC3CompletionAgent = Official Adapter + AGI Kernel + Product Runtime
```

### 5.2 C：計算主体

Cは次を生成する。

- 複数表現
- entity／role／relation
- state候補
- goal候補
- mechanism hypothesis
- counter-hypothesis
- transition prediction
- action／probe候補
- subgoal
- bounded multi-step plan
- expected effect
- hazard
- open term

Cは最終採否、外部action、ACTIVE M確定更新、最上位目的変更を行わない。

### 5.3 J：HDS判断主体

Jは製品の主幹制御主体である。

Jは次を所有する。

```text
Purpose / Value / Risk
W := (X, R, Mc)
F / Md / Cm / U
ModelSet採否
Gate判定
次のComputeRequest
外部action承認
MemoryDirective承認
SUSPEND / WAIT / ROLLBACK / RESET / STOP
```

全外部actionはJの一意な承認を必要とする。

### 5.4 M：可変記憶主体

Mは現在の判断根拠を保持・改訂する。

必須操作:

```text
ADD
REVISE
MERGE
SPLIT
REPLACE
INVALIDATE
DELETE
REINDEX
ROLLBACK
ARCHIVE
```

保持対象:

- 現在game／levelの目的候補
- entity／role binding
- action-effect evidence
- precondition
- goal／hazard
- failed hypothesis／plan
- successful subplan
- delayed effect attribution
- phase transition
- open term／next question
- cross-level／cross-game structure

### 5.5 P：命令形保持体

Pは説明文または解析reportではない。Layer-0が実行する攻略能力本体である。

```text
OBSERVE
REPRESENT
COMPARE
FORM_HYPOTHESIS
FORM_COUNTER_HYPOTHESIS
PREDICT
PLAN
PROBE
BIND_ACTION
VERIFY_EFFECT
ATTRIBUTE_DELAY
REQUEST_MEMORY
CONTINUE
WAIT
ROLLBACK
RESET
STOP
```

### 5.6 Adapter

Adapterは公式I/Oと内部型を変換する非主体である。目的、採否、記憶更新を所有しない。

---

## 6. HDS実装契約

### 6.1 HDSの位置づけ

HDSは製品Jの判断原理であり、開発時には製品failureを能力変更へ変換する方法である。

HDS自体を最終製品または独立した蒸留工場へ変えてはならない。

### 6.2 HDS Run

一つのCaseに対するRunは次を持つ。

```yaml
HDSCase:
  run_id:
  target:
  scope:
  purpose:
  W:
    X:
    R:
    Mc:
  observations:
  constraints:
  resources:
  model_set:
  gates:
  decision:
  outcome:
  update:
```

### 6.3 F／Md／Cm／U

```text
F:
  観測、目的、境界、状態、関係、未閉包を固定する

Md:
  baseline、alternative、counter-hypothesis、予測、plan、probeを生成する

Cm:
  GateResultを統合し、採用、保留、棄却、実行、待機、停止を決める

U:
  結果帰属、model revision、Failure Signature、memory update、版更新候補を作る
```

### 6.4 必須Gate

最低限、次を使用する。

```text
G01 Open-Term
G02 Closure
G03 Impossibility
G06 Evidence
G07 Validity / Soundness / Coherence
G09 Projection
G10 Reversibility
G11 Temporal Attribution
G12 Resource
G13 Shadow / Principle
G14 Authority / Control Ownership
G15 Commit
```

### 6.5 Update非自動性

一回の成功を一般則またはrelease初期状態へ直接昇格させない。

```text
実行経験
→ Runtime M / LOCAL_M
→ 複数Run・反証・削除試験
→ PROBATION_DEV
→ 独立Case・反例・regression
→ ACTIVE_DEV
→ 全数完遂・AGI適合監査
→ RELEASE_FROZEN P/J0/M0
```

能力資産の状態:

```text
LOCAL_M
PROBATION_DEV
ACTIVE_DEV
RELEASE_FROZEN
REJECTED
ARCHIVED
```

---

## 7. 解析粒度と圧縮

PH-D05教師素材は25 game、183 level、10,942 canonical frame、11,574 canonical successful actionを含む。

全raw actionへの対応は必要だが、全一手に重いHDS文書を作ってはならない。

### 7.1 階層

```text
Game
└ Level
   └ Phase
      └ Mechanism Segment
         └ Action Macro
            └ raw step span
```

### 7.2 フルHDS解析地点

- 目的／subgoalが変わる
- mechanism hypothesisが変わる
- action semanticsが変わる
- state transition
- progress／terminal
- failure／rollback
- phase change
- delayed effect attribution
- applicability boundary

### 7.3 同型反復の圧縮

```text
REPEAT action UNTIL predicate
MOVE along path
CLICK each entity matching predicate
WAIT until transition
APPLY operation TO all matching roles
```

全raw actionは必ずどれかのsegmentへ所属する。解析artifact量そのものを成果にしない。

---

## 8. 必須攻略能力

### 8.1 観測・表現

- 全render layerとcomposited view
- layer間relation
- 時系列frame差分
- animation／UI／board／background分離
- entity／region／path／boundary／empty space
- shape／color／count／orientation／topology
- containment／adjacency／alignment／order
- action surface／payload schema
- progress／terminal／reset

### 8.2 Goal／Mechanism Induction

- terminal goal候補
- subgoal
- state variable
- precondition
- immediate／delayed effect
- phase change
- level間継承／変更
- goal／hazard
- order／loop／composition

### 8.3 仮説競合

最低限:

```text
baseline
alternative
counter-hypothesis
null / no-op
observation error
delayed effect
different goal
wrong target
wrong order
```

### 8.4 探索・計画

- reversible probe
- information-gain probe
- hypothesis discrimination
- bounded plan search
- subgoal planning
- effect verification
- no-effect recovery
- hazard veto
- rollback／reset
- resource-aware continuation

### 8.5 ACTION6空間

候補をconnected-component中心に限定しない。

```text
object center / interior / edge
empty cell
region center / boundary
path node / destination
intersection
aligned position
symmetry counterpart
UI control
highlighted cell
candidate placement
relation-derived coordinate
```

### 8.6 結果帰属

```text
action_effect
delayed_effect
time_passage
exogenous_change
observation_error
redraw_or_stale_state
interface_only_change
no_effect
multi_causal
unknown
```

### 8.7 学習

学習とは経験によって未来の計算または判断が変わることである。

次は学習と数えない。

```text
ログ保存のみ
archive増加のみ
読まれないmemory追加
同じloop反復
更新後も行動不変
```

---

## 9. Runtime深度制御

HDSは複数仮説を要求するが、確立済み機構を毎一手ゼロから再生成しない。

```text
既知状態・ACTIVE_DEV mechanism
→ 現行modelを再利用
→ effect verification

新規状態
証拠矛盾
no-effect
failure
phase change
適用境界外
→ ModelSet再生成
→ alternative／counter-hypothesis展開
```

深いHDS再解析はイベント駆動、通常cycleはactive modelの実行・検証とする。

---

## 10. Product Capability Asset

### 10.1 TaskMechanismRecord

```yaml
TaskMechanismRecord:
  case_id:
  purpose_tree:
  state_schema:
  entities:
  roles:
  relations:
  action_semantics:
  preconditions:
  transitions:
  immediate_effects:
  delayed_effects:
  goals:
  hazards:
  order_constraints:
  loops:
  phases:
  subgoals:
  probes:
  rollback_rules:
  failure_signatures:
  applicability:
  counterexamples:
  raw_step_spans:
  product_mapping:
    runtime_M:
    P_dev:
    J_dev:
    M_dev:
```

`product_mapping`が空の解析物をprimary成果物としない。

### 10.2 GenericMechanismFamily

同型Caseを水平引き算して作る。

```yaml
GenericMechanismFamily:
  family_id:
  purpose_class:
  required_observation:
  state_schema:
  role_schema:
  relation_schema:
  precondition_pattern:
  operation_pattern:
  transition_pattern:
  goal_pattern:
  hazard_pattern:
  order_pattern:
  planning_pattern:
  parameter_schema:
  applicability_predicate:
  positive_cases:
  negative_cases:
  failure_signatures:
  asset_state:
  product_mapping:
```

### 10.3 ARC3ProductBundle

```text
ARC3ProductBundle
├ PBundle
├ JDomainProfile
├ M0
├ type/operator registry
├ mechanism-family registry
├ planner configuration
├ resource contract
└ official adapter configuration
```

---

## 11. Work Unit契約

すべての実装作業は`CapabilityClosureUnit`として実施する。

```yaml
CapabilityClosureUnit:
  unit_id:
  product_gap:
  affected_games:
  affected_levels:
  raw_trace_spans:
  HDS_frame:
  model_set:
  selected_mechanism:
  counterexamples:
  asset_state_before:
  responsible_component:
  product_change:
  expected_behavior_delta:
  execution_result:
  game_delta:
  level_delta:
  regression:
  asset_state_after:
  remaining_open_terms:
```

Work Unitは必ず次で閉じる。

```text
product failure / missing capability
→ HDS F/Md/Cm/U
→ product capability change
→ integrated agent execution
→ behavior delta
→ regression
```

分析report、schema、shell、runner、testだけで終了してはならない。

---

## 12. 既存資産の扱い

### 12.1 再利用対象

- 公式Environment Adapter
- `GenericAGIRuntime`
- `CognitiveSession`
- `GenericHDSJudgementSubject`
- `SemanticMemory`
- authority router／event ledger／rollback
- P-IR／interpreter／compiler
- PH-D05教師corpus／成功軌道
- 既存C／J／M責任分離

### 12.2 置換対象

- `HybridRelationalInstructionBody`を最終能力とする経路
- `compatibility_p_ir_program()`を最終Pとする経路
- 最終layer中心の表現
- component anchor中心だけのACTION6候補
- 未観測action probeとprogress scorerだけのpolicy

### 12.3 作成禁止

```text
新repository
空の製品shell
能力を増やさないagent subclass
能力を増やさないrunner
監査専用phase
承認専用phase
digest専用phase
schema専用phase
製品が読まないanalysis artifact
```

---

## 13. 製品受入試験

### 13.1 完遂

```text
25 games attempted
25 games WIN
183 levels complete
```

### 13.2 三主体削除

| 除去 | 期待破損 |
|---|---|
| C | 新しい表現・仮説・計画を生成できない |
| J | 外部actionとACTIVE M更新が不能 |
| M | 経験が未来へ残らず同じ失敗を反復 |
| P | ARC3攻略能力が消失 |
| L0 | Pを計算できない |

### 13.3 記憶因果

```text
same observation + relevant M revision
→ candidate / plan / action changes

same observation + irrelevant M
→ action unchanged
```

### 13.4 Identity／Replay

- game／level IDをtaint扱い
- frame完全hash routeなし
- trajectory indexなし
- successful action sequenceなし

### 13.5 Applicability Counterfactual

```text
成立条件を保つ摂動
→ MechanismSpec適用維持

成立条件を壊す摂動
→ 非適用またはSUSPEND
```

### 13.6 Clean Repeat

同一artifact、同一ProductBundleをclean stateから再実行し、25/25・183/183を再現する。

---

## 14. 開発終了条件

```text
ARC3_PRODUCT_COMPLETE
=
ARC3CompletionAgent artifact exists
AND one ARC3ProductBundle is active
AND C/J/M/P loop is active
AND J authorizes every external action
AND M changes future behavior
AND no fixed trajectory playback exists
AND no identity action router exists
AND 25/25 games WIN
AND 183/183 levels complete
AND clean-state repeat PASS
```

上式が成立するまで、本開発は未完了である。
