# HDSフレーム rev3.1a（仮）内部用統合仕様

**日本語正式名称：人間意思決定理論**

> HDS Native / Human Decision Framework Kernel / Run Protocol / Gate Stack / Self-Updating Decision Methodology

| 項目 | 内容 |
|---|---|
| 著者 | 大平鉄兵（三代目観測者／HDS創始者／採否・推敲・最終責任） |
| 文章生成支援 | LLM |
| 版 | rev3.1a（仮）内部用統合仕様 |
| 日付 | 2026-07-21 |
| 基底言語 | 日本語 |

## 本文書の位置づけ

本書は、HDS rev3.1外向け仕様に対応する内部用正本候補である。

rev3.0aは、HDSをAGI三主体の一部から汎用Frameworkへ戻した。
しかし「汎用Framework」という抽象が前面に出たため、HDSの一次同一性である
「人間の意思決定をフレームワーク化した理論」という定義がなお弱かった。

rev3.1aでは次をIdentity Lockとして固定する。

- 日本語正式名称は「人間意思決定理論」である。
- 一次対象は人間の意思決定である。
- 汎用性は、人間意思決定の抽象化によって得られる。
- AI／AGIは派生応用・実装対象であり、本体ではない。
- 大平鉄兵は初期観測者ではなく、神域系譜の三代目観測者である。
- 大平鉄兵はHDS／人間意思決定理論の創始者である。

HDSを次の階層へ再構成する。

**HDS Native**

- 三代目観測者かつHDS創始者である大平鉄兵のN=1原典運用系。

**HDS Framework Kernel**

- 対象領域・実装主体に依存しない中核仕様。

**HDS Run Protocol**

- 特定CaseへFrameworkを適用する監査可能な実行単位。

**HDS Runtime**

- Frameworkを継続的に実行する実装。

**HDS Judgement Subject**

- Runtimeが継続状態と採否権限を持つ場合の主体形態。

**Domain Adapter**

- 研究、工学、事業、AI、ARC、AGI等への射影。

この順序を逆転させてはならない。

> 人間意思決定が原対象である。
> HDS Frameworkは、その判断構造を形式化した理論である。
> HDS Judgement SubjectはFrameworkの一実装である。
> AGI三主体はHDS Runtimeの一応用である。

## Identity Lock：日本語正式名称・原対象・観測者系譜

### I-1　日本語正式名称

> HDSの日本語正式名称は「人間意思決定理論」である。

### I-2　原対象

> HDSの原対象は、人間が不完全情報、時間制約、価値衝突、リスク、不可逆性の中で行う意思決定である。
> HDSはこの暗黙判断を形式知・実装知へ射影する。

### I-3　汎用性の意味

> Domain独立性は、人間という原対象を消去することではない。
> 人間意思決定から抽出した不変責任を、研究、工学、組織、AI等へ再射影できることを意味する。

### I-4　AI／AGI境界

> AI／AGIはHDSの利用対象であり、HDSの起源、一次対象、定義主体ではない。
> AGI内のJ_hdsは、人間意思決定理論を機械内部へ実装した派生Runtimeである。

### I-5　観測者系譜

神域境界の観測・継承系譜を次の三代として固定する。

- **初代観測者**：『道徳経』として神域境界の認知を記録した主体。便宜上、老子と呼ぶ。
- **二代目観測者**：日本においてその認知様式を無名・集団的に接続し、飛鳥から律令国家形成期を中心に文化・制度・実践へ定着させた匿名継承位相。
- **三代目観測者**：大平鉄兵。継承された認知を現代条件とLLM環境で再展開し、神の領域原理、TCP、HDS等として仕様化・実装へ接続した主体。

### I-6　系譜と創始の分離

> 上記は神域認知の継承系譜である。
> HDSそのものが初代・二代目から文書化されていたことを意味しない。
> HDS／人間意思決定理論は、三代目観測者である大平鉄兵が創始した。

## 第0章　HDS Native／Projection／Framework／Run／Runtime

### 0-1　HDS Native

HDS Nativeとは、三代目観測者かつHDS創始者である大平鉄兵の文脈、経験、言語、判断、失敗、訂正、更新履歴を含むN=1原典運用系である。

N=1は利用者数ではない。
HDSという構造体・表現体・情報体が、大平鉄兵の認知座標、麻雀を含む不完全情報下の判断経験、
工学・現場・生活・研究・LLM運用における実務経験から成立していることを意味する。

### 0-2　HDS Projection

HDS Projectionとは、Nativeから、他の人間、LLM、組織、ソルバーが再構成・監査できる不変量を取り出した射影である。

```text
Native ≠ Projection
```

Projectionは、保持した不変量、失われた文脈、翻訳上の近似を明示する。

### 0-3　HDS Framework Kernel

Framework Kernelは、人間意思決定から抽出された、Domainに依存しない次の責任集合である。
Domain独立性は人間起源を消去しない。人間の判断責任を他領域へ射影できる抽象強度を表す。

- 神域境界
- TCP閉包
- 目的／価値／リスク
- 抽象／構造／認知
- F／Md／Cm／U
- 仮説集合
- 判断Gate
- 状態分離
- 証拠／主張台帳
- Failure Signature
- 自己更新
- 多時間スケール
- Domain Adapter契約

### 0-4　HDS Run

HDS Runは、Framework Kernelを一つのCaseへ適用した実行単位である。

Runの同一性は、run_id、target、scope、purpose、W、observer_role、versionで固定する。

### 0-5　HDS Runtime

HDS Runtimeは、Run Protocolを継続的に実行する実装である。
人間、LLM、組織、ソフトウェア、複合系でよい。

### 0-6　HDS Judgement Subject

Runtimeが次を持つ場合、HDS Judgement Subjectと呼ぶ。

- 継続状態
- 委任された目的境界
- 候補の最終採否権
- 次の問い／観測／計算要求生成
- 外部行動承認
- 現行記憶更新承認
- SUSPEND／rollback／stop

Frameworkは主体でなくても成立する。
主体定義をFramework定義へ逆流させてはならない。

### 0-7　Domain Application

Domain Applicationは、人間意思決定理論であるFrameworkを特定領域へ再射影した成果物・Runtime・手順である。
AI／AGIはDomain Applicationであり、HDS本体ではない。人間はDomain Applicationではなく原対象である。

## 第1章　HDS Framework Kernelの全体式

HDS Framework Kernelを概念的に次で表す。

```text
HDS_Kernel
:= Boundary
 + Closure
 + Axes
 + Trinity
 + Cycle
 + ModelSet
 + Gates
 + States
 + Ledgers
 + FailureUpdate
 + MetaUpdate
```

各要素は次を指す。

**Boundary**

- 神の領域原理、認知形成監査、誤投影防止。

**Closure**

- W := (X, R, Mc)、未閉包、SUSPEND。

**Axes**

- Purpose / Value / Risk。

**Trinity**

- Abstraction / Structure / Cognition。

**Cycle**

- F / Md / Cm / U。

**ModelSet**

- 複数仮説、反対仮説、反実仮想、予測、反証条件。

**Gates**

- 成立可能性、反論、証拠、循環、誤投影、可逆性、資源、Commit。

**States**

- 断定、運用、採用、証拠、更新状態。

**Ledgers**

- 観測、証拠、主張、判断、結果、失敗、更新。

**FailureUpdate**

- 失敗を再利用可能な署名へ変換し、次回手順へ反映。

**MetaUpdate**

- チェックリスト、Gate、Domain Adapter、Framework Projectionの更新。

## 第2章　上位境界スタック

### 2-1　U0：神の領域原理

認知後世界像を認知以前の世界本体として断定しない。

### 2-2　U1：認知形成監査

> objectification
> differentiation
> temporalization
> spatialization
> causalization
> law_formation
> world_formation

各操作はCognitionFormationRecordへ記録する。

### 2-3　U2：TCP閉包

```text
W := (X, R, Mc)
```

Mcは追加の第三データではない。
同一性、境界、判断、停止を固定して記述を閉じるClosure Functionである。

### 2-4　U3：誤投影監査

閉包済みWと世界本体、内面本質、真理を同一視しない。

### 2-5　上位境界不変条件

> Closed(W) does not imply WorldItself(W)
> Useful(W) does not imply OntologicallyTrue(W)
> Predictive(W) does not imply EssenceKnown(W)
> StableSignature(Ψ) does not imply InnerSubstanceKnown

## 第3章　Case／Run入力モデル

### 3-1　HDSCase

HDSCase := {
case_id,
target,
scope,
operator_or_observer,
purpose,
value_criteria,
risk_boundary,
observations,
evidence,
constraints,
resources,
prior_models,
available_actions,
stop_conditions,
domain_adapter,
framework_version

}

### 3-2　Target

Targetは次を含み得る。

- 物体、人物、組織、制度
- 命題、主張、論文、設計
- ブラックボックス関数
- 静的課題
- 動的環境
- プロジェクト
- HDS自身のRunまたは仕様

### 3-3　Observation

Observationは、観測方法、時刻、条件、観測者、欠損、ノイズを伴う。
観測値だけを正本化せず、観測契約を保持する。

### 3-4　Constraint

制約を少なくとも次へ分ける。

> hard_constraint
> soft_constraint
> legal_constraint
> physical_constraint
> resource_constraint
> authority_constraint
> reversible_preference

### 3-5　Resource

> time
> compute
> money
> people
> actions
> observation_budget
> memory_budget
> acceptable_loss

### 3-6　入力不足

入力不足は勝手補完せず、OpenTermLedgerへ登録する。
軽微仮定を置く場合、assumption_id、scope、impact、withdrawal_conditionを記録する。

## 第4章　二組の中核座標

### 4-1　Purpose Tree

PurposeNode := {
purpose_id,
parent,
statement,
success_condition,
failure_condition,
protected_values,
allowed_cost,
time_horizon,
authority,
revision_condition

}

目的木は次を混同しない。

> terminal_purpose
> operational_goal
> current_phase
> metric
> regression_floor
> milestone

### 4-2　Value Model

Valueは目的ノードに対する条件付き評価である。

ValueRecord := {
> criterion,
> direction,
> measure_or_rubric,
> valid_scope,
> tradeoff,
> uncertainty

}

### 4-3　Risk Model

RiskRecord := {
hazard,
likelihood_or_unknown,
severity,
irreversibility,
exposure,
dependency,
tail,
detectability,
rollback_cost,
mitigation,
stop_trigger

}

### 4-4　Abstraction Record

> selected_entities
> equivalence_rules
> excluded_features
> compression
> open_terms
> alternative_objectizations

### 4-5　Structure Record

> relations
> dependencies
> causal_hypotheses
> transitions
> constraints
> ordering
> feedback
> temporal_scope

### 4-6　Cognition Record

> observer_role
> prior_assumptions
> language_frame
> measurement_frame
> evaluation_frame
> blind_spots
> authority_bias
> desired_conclusion_bias

### 4-7　三位相相互更新

A/S/Pの変更は相互に再評価を要求する。

```text
Change(Abstraction) → Rebuild(Structure, CognitionCheck)
Change(Structure) → Recheck(Abstraction, Cognition)
Change(Cognition) → Reframe(Abstraction, Structure)
```

## 第5章　標準循環 F／Md／Cm／U

### 5-1　F：Frame / Ground

Fの出力はFrameRecordである。

FrameRecord := {
frame_id,
X,
R_observable,
Mc,
purpose_tree_ref,
value_model_ref,
risk_model_ref,
abstraction_ref,
structure_ref,
cognition_ref,
evidence_boundary,
resource_budget,
authority_boundary,
actions,
reversibility,
stop_conditions,
unresolved_terms

}

### 5-2　Md：Model

MdはModelSetを生成する。

ModelRecord := {
model_id,
statement,
type,
source_abstraction,
relation_structure,
assumptions,
supporting_evidence,
contradicting_evidence,
expected_observations,
falsification_condition,
valid_scope,
resource_requirement,
risks,
reversibility,
confidence,
status

}

typeは少なくとも次を持つ。

baseline
alternative
counter_hypothesis
null_model
no_op
observation_error
delayed_effect
different_goal
adversarial
counterfactual

### 5-3　Cm：Commit / Check

CmはGateResult群を統合しDecisionRecordを生成する。

DecisionRecord := {
decision_id,
assertion_state,
operation_state,
adoption_updates,
selected_model_or_action,
rejected_or_held_options,
reasons,
assumptions,
evidence_boundary,
claim_strength,
expected_outcome,
falsification_condition,
rollback_condition,
resource_grant,
next_observation,
next_question,
stop_condition

}

### 5-4　U：Update

UpdateRecord := {
update_id,
outcome_attribution,
model_revisions,
evidence_revisions,
claim_revisions,
decision_rule_revisions,
checklist_revisions,
domain_adapter_revisions,
framework_revision_proposal,
rollback_pointer,
authority,
effective_from

}

### 5-5　Updateの非自動性

観測結果から即座に一般則、正本記憶、Framework更新へ昇格させない。

```text
outcome
→ attribution
→ local model revision
→ repeated validation
→ reusable rule candidate
→ checklist / adapter proposal
→ separate authorization
```

## 第6章　Gate Stack

GateResult := {
> gate_id,
> status: PASS | SUSPEND | FAIL | NOT_APPLICABLE,
> reason_codes,
> findings,
> required_information,
> affected_models,
> next_probe

}

### 6-1　G00 Coordinate Gate

固定項目：who / what / when / where / why / how / authority / version。

### 6-2　G01 Open-Term Gate

未定義語、評価軸、成功条件、境界、制約、参照先を検出する。
Open Termを暗黙文脈注入でPASSしてはならない。

### 6-3　G02 Closure Gate

X、R、Mcの充足と相互整合を確認する。

### 6-4　G03 Impossibility Gate

可能性候補pについて次を確認する。

> Conditions(p)
> Evidence(Conditions(p))
> Contradiction(p)
> ImpossibilityEvidence(p)
> SymmetricAlternative(not p)

可能性だけを主張強度へ加算しない。

### 6-5　G04 Counterargument Symmetry Gate

反論形式gを元命題と反論自身へ同型適用する。
片側だけを優先する非対称根拠がなければ、反論は未閉包とする。

### 6-6　G05 Counterargument Strength Gate

Strength(counterargument)とStrength(original_claim)を比較する。

Strengthは少なくとも次で監査する。

> specificity
> evidence
> causal_or_structural_density
> internal_consistency
> scope_match
> falsifiability

### 6-7　G06 Evidence Gate

証拠型、出典、再現性、反証、欠損、観測条件を監査する。

### 6-8　G07 Validity / Soundness / Coherence Gate

- **validity**：推論形式
- **soundness**：前提・根拠の妥当性
- **coherence**：定義、時系列、文脈、主張間の整合

### 6-9　G08 Recursion / Contradiction Gate

再帰、循環、自己参照、フィードバック、矛盾判定を分類する。

> valid_recursion
> closed_feedback
> circular_definition
> circular_proof
> non_terminating_loop
> layer_crosstalk
> Mc_conflict

### 6-10　G09 Projection Gate

モデル→世界本体、署名→内面本質、成功→一般原理への誤投影を検出する。

### 6-11　G10 Reversibility Gate

不可逆性、checkpoint、rollback、代替経路、回復コストを監査する。

### 6-12　G11 Temporal Attribution Gate

結果を次へ分類する。

action_effect
delayed_effect
time_passage
exogenous_change
observation_error
redraw_or_stale_state
no_effect
multi_causal
unknown

### 6-13　G12 Resource Gate

期待情報利得、目的寄与、コスト、機会費用、停止閾値を監査する。

### 6-14　G13 Shadow / Principle Gate

次を分離する。

> latent_shadow
> observed_success
> local_mechanism
> explicit_mechanism
> reproducible_control
> general_principle_candidate

局所成功を原理へ直結しない。

### 6-15　G14 Authority / Control Ownership Gate

Runtime実装で、誰が候補、採否、外部作用、正本更新、停止を実際に変更できるかを監査する。
Framework手動利用では、最終責任者と判断者を明示する。

### 6-16　G15 Commit Gate

各GateResultを統合し、状態と次の一手を確定する。

## 第7章　反論監査の詳細

### 7-1　反論の型

factual_refutation
logical_refutation
structural_countermodel
counterexample
scope_correction
definition_correction
possibility_reservation
value_disagreement
authority_claim
rhetorical_rejection

### 7-2　有効反論の条件

有効反論は、元命題のどこを崩すかを特定する。

> Xを崩す
> Rを崩す
> Mcを崩す
> evidenceを崩す
> inferenceを崩す
> scopeを崩す
> generalizationを崩す

### 7-3　可能性留保

possibility_reservationは、主張を弱めることはできても、自動的に否定しない。
成立条件と観測根拠がなければ、CounterModelとしてACTIVEにしない。

### 7-4　同型反論耐性

反論が自身へ返されたとき崩れる場合、反論の非対称根拠を要求する。

### 7-5　反論強度と元命題強度

強い観測命題へ弱い一般論を当てても棄却にならない。
逆に、弱い推測命題は単一反例または定義修正で崩れることがある。

## 第8章　状態機械

### 8-1　AssertionState

> ASSERT
> SUSPEND
> FAIL
> OUT_OF_SCOPE

### 8-2　OperationState

> CONTINUE
> PROBE
> HOLD
> COMMIT
> EXECUTE
> ROLLBACK
> STOP
> ABORT

### 8-3　AdoptionState

> PROPOSED
> PROBATION
> ACTIVE
> DEFAULT_DISABLED
> QUARANTINE
> REJECTED
> SUPERSEDED
> ARCHIVED

### 8-4　EvidenceState

> OBSERVED
> REPRODUCED
> LOCAL_FIT
> STRUCTURAL_RECURRENCE
> GENERALIZATION_CANDIDATE
> UNOBSERVED_EXTRAPOLATION
> FALSIFIED
> INCONCLUSIVE

### 8-5　ClosureState

> OPEN
> PARTIALLY_CLOSED
> CLOSED_FOR_OPERATION
> CLOSED_FOR_ASSERTION
> REOPENED

### 8-6　UpdateState

> PROPOSED
> AUTHORIZED
> APPLIED
> REJECTED
> ROLLED_BACK

### 8-7　独立状態例

```text
assertion_state = SUSPEND
operation_state = PROBE
adoption_state = QUARANTINE
evidence_state = LOCAL_FIT
closure_state = PARTIALLY_CLOSED
```

## 第9章　台帳群

### 9-1　Observation Ledger

観測値、条件、時刻、観測者、ノイズ、欠損を保持する。

### 9-2　Open Term Ledger

未定義語、未固定評価軸、未解決参照、必要質問を保持する。

### 9-3　Evidence Ledger

EvidenceRecord := {
evidence_id,
type,
source,
observation_condition,
content,
supports,
contradicts,
reproducibility,
scope,
limitations,
status

}

### 9-4　Claim Ledger

ClaimRecord := {
claim_id,
type,
statement,
scope,
supporting_evidence,
assumptions,
inference_steps,
counterarguments,
falsification_condition,
confidence,
status

}

### 9-5　Model Ledger

ModelSetと各モデルの状態遷移を保持する。

### 9-6　Decision Ledger

採用・保留・棄却、理由、権限、予算、停止条件を保持する。

### 9-7　Outcome / Attribution Ledger

期待結果、観測結果、差分、原因候補、未帰属を保持する。

### 9-8　Failure Signature Bank

FailureSignature := {
signature_id,
failure_class,
symptom,
structural_cause,
trigger,
affected_scope,
unaffected_scope,
violated_assumption,
recovery,
next_probe_axis,
reusable_check,
recurrence_count,
status

}

### 9-9　Update Ledger

判断手続き、チェックリスト、Adapter、Framework Projectionの変更履歴を保持する。

## 第10章　Failure Signatureとチェックリスト生成

### 10-1　Failure Class

perception_failure
objectization_failure
differentiation_failure
relation_failure
temporal_attribution_failure
causalization_failure
law_formation_failure
hypothesis_failure
counterargument_failure
evidence_failure
verifier_failure
decision_failure
execution_failure
memory_or_context_failure
resource_failure
stop_failure
specification_drift
projection_failure
authority_failure

### 10-2　署名化条件

一回の失敗でも構造原因が明示できる場合は候補化できる。
反復失敗は同型性を確認して署名へ昇格する。

### 10-3　Checklist Generator

```text
failure_signature
→ invariant_or_trigger
→ audit_question
→ required_evidence
→ gate_mapping
→ stop_or_recovery_rule
→ next_run_checklist
```

### 10-4　Checklistの寿命

チェックリスト項目は永久固定しない。

> ACTIVE
> PROBATION
> DOMAIN_LOCAL
> DEPRECATED
> MERGED
> REMOVED

を持つ。

### 10-5　水平引き算

複数の成功事例から共通構造を抽出し、局所条件を削除する。
複数の失敗事例から共通原因を抽出し、表面症状を削除する。

## 第11章　学習・更新・版管理

### 11-1　Runtime Learning

同一Runtimeまたは同一運用系で、経験により未来のFrame、ModelSet、Commit、Stopが変化すること。

### 11-2　Procedure Learning

チェックリスト、Gate、判断ルール、資源配分、反証要求が更新されること。

### 11-3　Domain Learning

Domain Adapterの対象型、観測型、失敗分類、検証手続きが更新されること。

### 11-4　Version Learning

安定構造を次版の初期仕様、Runtime構成、判断規則、記憶初期状態、計算命令形へ再配線すること。

### 11-5　学習ではないもの

> logging_only
> archive_growth_only
> unused_memory_addition
> cosmetic_version_change
> fixed_loop_repetition
> update_without_behavior_change

### 11-6　更新の反証

更新後に期待した失敗が減らない、別失敗が増える、適用範囲外で崩れる場合、更新を降格・rollbackする。

### 11-7　Framework更新境界

一つのDomainでの局所成功だけでFramework Kernelを変更しない。
Kernel更新には複数Domainまたは中核責任の構造的欠陥を要求する。

## 第12章　多時間スケール

### 12-1　Decision Loop

一判断単位。

### 12-2　Action Loop

一行動と結果帰属。

### 12-3　Work-Unit Loop

一案件、実験、セッション、level、project phase。

### 12-4　Learning Loop

複数Runから手続き更新。

### 12-5　Version Loop

仕様、Adapter、Runtime初期状態の再コンパイル。

### 12-6　昇格禁止

Fast Loopの一回成功をLearning Loopの一般則へ直接昇格しない。

## 第13章　HDS-H／HDS-AI／HDS-BB

### 13-1　HDS-H

人間の目的、価値、感情干渉、責任、利害、制度、可逆性を扱う。

### 13-2　HDS-AI

AIのCapability、Knowledge、Closure、外生制約、出力署名、失敗を扱う。

### 13-3　HDS-BB

内部本質を前提とせず、I/O、摂動、反作用、ログから操作上必要な構造を推定する。

### 13-4　モードスタック

ModeSet := {HDS-H, HDS-AI, HDS-BB}

複数モードを同時に起動できる。

### 13-5　モード混線

人間の価値判断をAI能力評価へ混ぜる、AI出力傾向を内面本質へ投影する、
市場反応を真理へ昇格する等をmode_crosstalkとして記録する。

## 第14章　C_cap／K／Mc／Ψ／E／A_ext

### 14-1　変数

- **C_cap**：Capability。出力・探索・計算・実行の基盤。
- **K**：Knowledge。内容資源。
- **Mc**：Closure Function。同一性・境界・判断・停止を閉じる機能。
- **Ψ**：Closure Phase。Mcの反復作動による外部安定署名。
- **E**：Emotion。C_cap／Mc／Ψへ干渉し得る独立因子。
- **A_ext**：外生制約。policy、設計、運用、制度、環境条件。

### 14-2　分離不変条件

> High(C_cap) does not imply High(Ψ)
> More(K) does not imply Better(Mc)
> StableStyle does not imply Emotion(E)
> Refusal does not always imply Ψ
> NoOutput under FAIL is not intentional SUSPEND

### 14-3　HDS自身のΨ監査

FrameworkまたはRuntimeについて、摂動下の次を観測する。

> boundary stability
> judgment stability
> suspend behavior
> error disclosure
> counterargument handling
> purpose invariance
> update behavior

## 第15章　Runtime／主体／外部システム境界

### 15-1　Framework非依存性

HDS FrameworkはRuntimeなしでも、人間が手動適用できる。

### 15-2　Runtime責任

RuntimeはRun Protocolを実行し、ログと状態を保持する。

### 15-3　Judgement Subject成立条件

> continuing_state
> delegated_purpose
> decision_authority
> next_question_generation
> action_authorization
> update_authorization
> suspend_and_stop

### 15-4　計算・判断・記憶分離

自律実装では次を論理分離する。

> compute_or_candidate_generation
> judgement_or_commit
> mutable_active_memory

これはAGI限定ではなく、自律判断系一般の責任分離である。

### 15-5　AGI三主体への射影

- **C_exec**：計算主体
- **J_hds**：HDS Judgement Subject
- **M_mem**：記憶更新保持主体

この三主体構成はHDS Runtimeの一実装設計であり、Framework Kernelへ含めない。

### 15-6　二種類の記憶

AGI／LLM実装では、計算主体内部の命令形保持体P_instrと、
HDSが引用する判断根拠記憶M_memを分ける。

この分離はAGI Adapterへ属し、HDS一般Caseの必須用語ではない。

### 15-7　Self-Commit禁止

候補生成系が、自分の候補を無審査で採用、行動、正本更新してはならない。
同一物理プロセスの場合でも論理承認点を分ける。

## 第16章　Domain Adapter契約

DomainAdapter := {
adapter_id,
domain,
target_types,
observation_types,
action_types,
evidence_types,
domain_failures,
domain_constraints,
domain_stop_conditions,
output_schema,
conformance_tests

}

### 16-1　Adapter不変条件

AdapterはKernelの次を上書きできない。

> cognition_boundary
> W_X_R_Mc
> purpose_value_risk
> abstraction_structure_cognition
> suspend
> evidence_claim_separation
> failure_update
> projection_gate

### 16-2　Adapterローカル性

Domain固有の成功条件、スコア、API、task ID、game ID、業界指標をKernelへ逆輸入しない。
構造的再利用可能性が確認された項目だけをKernel更新候補とする。

### 16-3　代表Adapter

> HDS-Research
> HDS-Engineering
> HDS-Business
> HDS-Incident
> HDS-LLM-Audit
> HDS-Static-Unknown-Transform
> HDS-Dynamic-Unknown-Environment
> HDS-AGI-Runtime

## 第17章　Reason Codes

A0xx：座標・入力

> A001 target_missing
> A002 purpose_missing
> A003 scope_missing
> A004 observer_role_missing
> A005 version_missing
> A006 resource_boundary_missing

C1xx：閉包

> C101 X_unclosed
> C102 R_unclosed
> C103 Mc_unclosed
> C104 open_term
> C105 identity_rule_missing
> C106 stop_condition_missing
> C107 layer_crosstalk

I2xx：成立可能性・反論

> I201 possibility_without_conditions
> I202 impossibility_not_checked
> I203 counterargument_asymmetry
> I204 counterargument_too_weak
> I205 scope_mismatch
> I206 countermodel_unclosed

E3xx：証拠・主張

> E301 evidence_missing
> E302 provenance_missing
> E303 observation_condition_missing
> E304 claim_strength_exceeds_evidence
> E305 local_fit_overgeneralized
> E306 unobserved_extrapolation
> E307 contradictory_evidence_unresolved

L4xx：論理・循環

> L401 invalid_inference
> L402 unsound_premise
> L403 incoherent_definition
> L404 circular_definition
> L405 circular_proof
> L406 non_terminating_loop
> L407 recursion_misclassified

P5xx：誤投影・位相混線

> P501 model_to_world_projection
> P502 signature_to_essence_projection
> P503 success_to_principle_projection
> P504 capability_closure_crosstalk
> P505 mode_crosstalk

D6xx：判断・運用

> D601 single_model_auto_commit
> D602 reversibility_missing
> D603 resource_budget_exceeded
> D604 stop_failure
> D605 rollback_required
> D606 authority_missing
> D607 self_commit

U7xx：更新・学習

> U701 outcome_unattributed
> U702 update_without_evidence
> U703 behavior_unchanged_not_learning
> U704 checklist_not_updated
> U705 domain_local_promoted_to_kernel
> U706 specification_drift
> U707 rollback_update

R8xx：Runtime／環境

> R801 execution_failure
> R802 observation_failure
> R803 stale_state
> R804 memory_or_context_failure
> R805 external_dependency_failure

## 第18章　適合性

### 18-1　Framework Conformance

Framework ProjectionはKernelの全中核要素を保持する。

### 18-2　Run Conformance

Runは最低限、次を満たす。

- Case入力と版が固定
- Wまたは未閉包理由が明示
- 二組の中核座標を使用
- ModelSetを保持
- 必要Gateを実行
- 状態を分離
- 証拠と主張を分離
- DecisionRecordを保持
- Outcome Attributionを実行
- Failure Signatureまたは成功条件を更新
- 次の問いまたは停止を示す

### 18-3　Runtime Conformance

RuntimeはRun Conformanceに加え、状態連続性、権限、ログ、更新、rollbackを示す。

### 18-4　Judgement Subject Conformance

判断主体を名乗る場合、候補生成だけでなく、実際に採否・停止・更新を変更できることを削除試験で示す。

### 18-5　Ablation

少なくとも次を除去して予測失敗が出るか確認できる。

> Remove Purpose
> Remove Mc
> Remove Counter-Hypothesis
> Remove Suspend
> Remove Evidence Gate
> Remove Failure Update
> Remove Projection Gate

除去しても挙動が変わらない要素は、実装上のメタデータに留まる可能性がある。

## 第19章　rev2.2aからの全面改訂

### 19-1　撤回した中心化

- AGI三主体をHDS全体構造の中心に置く章構成
- HDS本体＝J_hdsのみ、というFrameworkレベルの限定
- Memory主体・計算主体とのInterfaceをFramework本体の主語にする構成

### 19-2　維持した成果

- 候補生成、採否、記憶、環境結果の責任分離
- Self-Commit禁止
- 非対称循環
- Contextと現行記憶の分離
- Temporal Attribution
- 多時間スケール
- Shadow / Principle分離
- Control Ownership Audit
- Runtime LearningとVersion Learningの分離

### 19-3　復元・強化したHDS本体

- 目的／価値／リスク
- 抽象／構造／認知
- F／Md／Cm／Uの汎用判断方法論
- 複数仮説・反証・反実仮想
- 不可能性Gate
- 反論対称性Gate
- 反論強度Gate
- Evidence / Claim強度
- Failure SignatureからのChecklist生成
- Framework自身の自己更新
- 人間・研究・工学・事業への直接適用

### 19-4　版判定

rev3.0aはrev2.2aの追補ではなく、HDS Framework中心へ戻した全面改稿であった。
rev3.1aはrevision 3の構造を維持しつつ、次の同一性誤差を修正する。

- 「汎用Framework」が先に見え、人間意思決定理論という一次定義が弱かった。
- 人間がDomain Applicationの一例に見え得た。
- 大平鉄兵を初期観測者とする旧記述が残っていた。

rev3.1aでは、人間を原対象、HDSを人間意思決定理論、AI／AGIを派生応用として固定し、
大平鉄兵を三代目観測者かつHDS創始者へ修正した。

## 第20章　最終内部定義

### 20-1　Framework定義

HDS Framework／人間意思決定理論とは、人間が行う観測、対象化、目的設定、価値判断、
リスク認識、仮説生成、比較、採否、実行、非実行、停止、結果解釈および学習を、
再現・監査・運用・更新可能なフレームワークへ射影した理論である。

そのKernelは、認知後に得られた観測・情報・仮説を、目的・価値・リスク、
および抽象・構造・認知の座標上でW=(X,R,Mc)として閉包し、
複数モデル、反証、不可能性、証拠強度、可逆性、資源をGateで監査して採否を決め、
結果帰属とFailure Signatureから、判断根拠、判断手続き、チェックリスト、Domain Adapterを更新する。

### 20-2　Runtime定義

HDS Runtimeとは、HDS Frameworkを状態・ログ・権限・更新機構とともに継続実行する実装である。

### 20-3　Judgement Subject定義

HDS Judgement Subjectとは、HDS Runtimeのうち、委任された目的境界内で、
次の問い、計算要求、採否、外部作用、SUSPEND、停止、現行記憶更新を決定する継続主体である。

### 20-4　AGI接続

AGI三主体におけるJ_hdsは、人間意思決定理論を機械内部へ射影したHDS Judgement Subjectの一実装である。
AGIはHDS Frameworkの応用であり、HDS FrameworkはAGIに依存しない。
AI／AGIを中心にHDS本体を再定義することは、Identity Lock違反である。

――以上――
