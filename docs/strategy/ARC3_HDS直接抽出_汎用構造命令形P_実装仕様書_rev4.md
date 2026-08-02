# ARC3 HDS直接抽出・汎用構造／命令形P 実装仕様書 rev4

- 仕様ID: `ARC3_HDS_DIRECT_STRUCTURE_AND_IMPERATIVE_P_SPEC_REV4`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 日付: `2026-08-02`
- 状態: `OWNER_DIRECTIVE_INSTALLED`
- 現行ロードマップ: `docs/roadmap/ARC3_HDS直接抽出_開発ロードマップ_rev4.md`
- 旧rev3: `HISTORICAL_SUPERSEDED`

---

## 0. 固定結論

本repositoryの最上位目的は、ARC Prize 2026 / ARC-AGI-3において、同一のARC3エージェントで全タスクを自律完遂することである。

現在必要なのは、HDSそのものを証明・形式化することではない。

```text
成功軌道・回答・観測記録
  ↓ HDSでタスク分解
状態・対象・関係・条件・操作・効果・終了を抽出
  ↓ 同型を統合
ARC3で再利用できる汎用構造
  ↓ Layer-0実行形式へ変換
命令形保持体 P
  ↓
ARC3エージェント C/J/Mへ接続
  ↓
全183 levelを実行し、失敗から構造とPを更新
```

本仕様の完成対象は次の五つである。

1. 全25 game／183 levelのHDSタスク分解記録
2. ARC3汎用構造ライブラリ
3. Layer-0が計算可能な命令形保持体P
4. Pを使用する同一ARC3エージェント
5. 全数実行・失敗更新・公式提出経路

---

## 1. 最上位目的と優先順位

### 1.1 完成式

```text
ARC3_AGENT_COMPLETE
=
ONE_AGENT
AND GENERIC_STRUCTURE_LIBRARY
AND IMPERATIVE_P
AND HDS_CONTROLLED_EXECUTION
AND UPDATEABLE_MEMORY
AND FULL_PUBLIC_EXECUTION
AND OFFICIAL_SUBMISSION_PATH
```

### 1.2 優先順位

```text
1. ARC3タスクを理解可能な単位へ分解する
2. 分解結果から再利用可能な構造を抜く
3. 構造を命令形Pへ変換する
4. エージェントへ接続する
5. 実行失敗から修正する
6. 最後に証拠・配布・公式提出を整える
```

検証、digest、schema、承認記録は成果物を守る補助手段である。成果物より上位へ置かない。

### 1.3 非目的

- HDS理論そのものの完全形式化
- HDS蒸留工場の構築
- schema数・test数・artifact数の増加
- 小工程ごとのEvidence Commit／Attestation／Owner Approval
- 抽出前のsource-blind証明
- 汎用構造完成前のAGI完成証明
- Runtime完成前の公式提出最適化

---

## 2. HDSの役割

HDSは本開発の成果物ではなく、ARC3を分解・採否・更新する判断方法である。

### 2.1 ARC3 HDS Run

各game／level／episodeを一つのHDS Runとして扱う。

```text
Purpose       何を成立させればlevelが進むか
Premise       現在観測できる状態と制約は何か
Axes          進捗・安全・可逆性・手数・情報利得
Alternatives  可能な対象・操作・順序・probe
Risk          失敗、不可逆、誤対象、誤順序、資源浪費
Reason        どの観測と関係から候補を支持したか
Tradeoff      進捗と探索、短期効果と遅延効果の比較
Decision      実行、観測、保留、rollback、reset、stop
Evidence      before/action/after、progress、terminal、failure
Closure       成立条件、未閉包、次の観測要求
```

### 2.2 標準循環

```text
F  : 観測を切り取り、状態・対象・関係・変化を抽出する
Md : 複数の構造仮説・反対仮説・操作候補を作る
Cm : HDS Gateで採否し、実行または保留を決める
U  : 結果を構造ライブラリ、P、M、Failure Signatureへ反映する
```

各Runは必ず、後続コードが直接読める機械可読成果物へ変換する。

---

## 3. 入力契約

### 3.1 使用する入力

抽出工程では、利用可能な教師情報を最大限使用する。

- 25 game／183 levelの成功軌道
- raw recording
- canonical teacher trajectory
- before／after frame
- action ID／payload
- available actions
- progress／terminal／reset／failure記録
- 既知の回答・正解行動列
- 既存のR1〜S5解析資産
- 既存のtyped IR／interpreter

回答・成功軌道の使用は許可する。目的は回答を隠すことではなく、回答を汎用構造へ変換することである。

### 3.2 使用境界

- game／level IDは開発時の照合キーとして使用できる。
- game／level IDだけでruntime行動を選ぶrouterへ変換してはならない。
- 成功行動列は構造抽出・回帰に使用できる。
- 成功行動列をruntime replay tableとして使用してはならない。
- environment sourceは構造仮説の検証補助に限定し、runtime入力へ持ち込まない。
- public 25 gameはblind評価ではなく、教師・開発・全数回帰対象として扱う。

### 3.3 最大情報からの減算

抽出前に情報を遮断しない。

```text
最大情報で構造を抽出
→ game固有値を分離
→ identity依存を減算
→ replay依存を減算
→ 汎用構造だけを残す
```

source-blind、identity-free、answer-copy禁止は抽出開始条件ではなく、最終P／runtimeの減算監査として実施する。

---

## 4. 必須成果物

### 4.1 TaskDecompositionRecord

全183 levelについて、一つ以上の分解記録を作る。

```text
case_id
purpose
initial_state
entities
relations
state_variables
action_surface
steps[]
  before_state
  selected_target
  preconditions
  action
  payload
  expected_effect
  observed_effect
  progress_delta
  delayed_effect
  failure_or_hazard
  next_state
terminal_condition
reset_condition
open_terms
source_refs
```

単なる軌道保存ではない。各stepについて「何を対象に、どの条件で、何をし、何が変わったか」を保持する。

### 4.2 StructureAtom

分解記録から次の型を抽出する。

```text
REPRESENTATION ENTITY RELATION STATE SELECTOR PRECONDITION
OPERATION EFFECT DELAYED_EFFECT GOAL HAZARD ORDER COMPOSITION
PROBE WAIT LOOP RESET ROLLBACK TERMINAL FAILURE
```

必須field:

```text
structure_id
structure_type
inputs
conditions
operation
expected_output_or_effect
scope
parameters
positive_examples
negative_examples
failure_signatures
source_cases
confidence_state
```

### 4.3 GenericStructureFamily

同型のStructureAtomを統合し、logicとparameterを分離する。

```text
logic:
  SELECT target WHERE predicate
  MOVE target TOWARD destination
  OBSERVE effect
  REPEAT UNTIL goal OR hazard

parameters:
  target role
  destination relation
  movement action
  goal predicate
  hazard predicate
```

統合条件:

- 同じ入力責任
- 同じ条件構造
- 同じ操作型
- 同じ効果型
- 差分をparameterとして表現可能

統合禁止:

- action ID一致だけ
- game ID一致だけ
- 座標列一致だけ
- 成功軌道全体の一致だけ
- 効果・目的が異なるものの強制統合

### 4.4 ImperativePRecord

汎用構造をLayer-0が実行できる命令形へ変換する。

```text
OBSERVE <required fields>
IF <precondition>
SELECT <target by relation/role>
EXECUTE <operation with parameters>
EXPECT <effect within horizon>
VERIFY <progress/terminal/hazard>
UPDATE_M <support/refute/failure>
REPEAT | WAIT | PROBE | ROLLBACK | RESET | STOP
```

必須field:

```text
p_id
applicability
required_observation
selector
precondition
operation
expected_effect
verification
hazard_veto
failure_update
next_control
source_structure_ids
```

Pは説明文ではない。runtimeが読み、候補生成・予測・実行へ使用できるtyped instructionでなければならない。

### 4.5 GameBinding

```text
generic P    = 再利用可能な命令構造
game binding = 対象、色、位置、action surface、goal等の観測依存parameter
```

GameBindingはruntimeの入力観測から構築する。固定game ID routerにしない。

### 4.6 最終静的資産

```text
ARC3StructureLibrary
  structure_families
  boundaries
  hazards
  failure_signatures
  probe_patterns

ARC3PBundle
  imperative_p_records
  type_registry
  operator_registry
  applicability_index
  provenance_index
```

---

## 5. エージェント接続

```text
C = Execute(L0, P)
Runtime = Trinity(C, J, M)
```

- `P`: 長期汎用構造・命令形
- `C`: 観測とMを使い、適用可能なP、候補、予測、probeを計算する
- `J`: HDSで候補を採否し、外部行動・停止・rollback・M更新を決める
- `M`: 現episodeで成立したbinding、仮説支持、反証、失敗、進捗を更新する

一cycle:

```text
OBSERVE
→ RETRIEVE applicable P
→ BIND observed entities/relations
→ GENERATE action/probe candidates
→ HDS JUDGEMENT
→ EXECUTE one action
→ REOBSERVE
→ ATTRIBUTE effect
→ UPDATE M
→ CONTINUE / WAIT / ROLLBACK / RESET / STOP
```

Runtime禁止:

- game／level IDによる完成行動列選択
- full state digestによる軌道lookup
- hidden answer map
- 固定座標列の再生
- HDSを通らない外部action
- 観測なしの複数action一括送信
- 失敗時の無制限探索

---

## 6. 抽出・統合・実行

### 6.1 Level分解

各成功軌道をstep列として読み、各stepで次を抽出する。

```text
before state
→ selected target
→ applicable condition
→ executed operation
→ visible/immediate effect
→ delayed effect
→ progress/terminal contribution
→ failure alternative
```

### 6.2 目的から逆算

```text
terminal
← goal predicate
← required state transition
← operation
← precondition
← selected entity/relation
← observation
```

これにより、action frequencyではなく、目的へ寄与する命令構造を得る。

### 6.3 反対候補

各構造に最低限次を付与する。

- wrong target
- wrong precondition
- wrong operation
- wrong order
- immediate／delayed effect alternative
- no-op／observation error
- overfit parameterization

反対候補はphaseを増やすためではなく、構造境界を決めるために使う。

### 6.4 同型統合とPコンパイル

対象名・色・座標・action IDをparameterへ持ち上げ、同じ責任を持つ構造をfamilyへ統合する。各familyをImperativePRecordへ変換し、typed interpreterで実行可能にする。

### 6.5 全数実行と修正

全183 levelを同一agentで実行する。失敗は次へ分類する。

```text
OBSERVATION_MISSING REPRESENTATION_ERROR ENTITY_ROLE_ERROR
RELATION_ERROR PRECONDITION_ERROR OPERATION_ERROR EFFECT_MODEL_ERROR
DELAY_ATTRIBUTION_ERROR GOAL_ERROR HAZARD_ERROR ORDER_ERROR
P_APPLICABILITY_ERROR BINDING_ERROR JUDGEMENT_ERROR MEMORY_ERROR
RESOURCE_ERROR
```

分類結果に応じ、TaskDecompositionRecord、StructureFamily、P、GameBinding、J、Mの必要箇所だけを修正する。

---

## 7. 完成条件

### 7.1 分解完成

```text
25 game covered
183 level covered
all successful steps represented
orphan action count = 0
terminal contribution unresolved count = 0 or explicitly OPEN
```

### 7.2 構造抽出完成

```text
all decomposition records mapped to StructureAtom
all StructureAtom assigned to family or explicit case-specific residue
logic/parameter separation complete
positive/negative/boundary examples attached
```

### 7.3 P完成

```text
all active structure families compiled to executable ImperativePRecord
all P type-check
all P have applicability, effect verification, hazard, failure update
identity router finding = 0
trajectory replay finding = 0
```

### 7.4 Agent接続完成

```text
one runtime artifact
one active PBundle
HDS judgement on every external action
relevant M changes future selection
irrelevant M does not change action
```

### 7.5 公開全数完成

```text
25/25 game complete
183/183 level complete
crash = 0
unbounded retry = 0
```

公開全数完成は既知教師群の実装閉包であり、未知汎化または公式private完遂と混同しない。

### 7.6 公式完成

```text
same artifact
official accepted
public complete
private complete
```

---

## 8. 工程制約

現行ロードマップは六つの実装phaseだけを持つ。

1. Task Decomposition
2. Generic Structure Extraction
3. Imperative P Compilation
4. Agent Integration
5. Full Execution Repair Loop
6. Official Packaging／Evaluation

文書、schema、evidence、approvalを独立phaseへ増殖させない。

新しいartifactを作る条件:

```text
次工程のコードが直接読む
OR 失敗修正に直接使う
OR 公式提出に必要
```

検証規則:

- testは各phase末尾で行う
- test専用phaseを作らない
- digestはreleaseまたは再現性が必要な成果物にだけ付ける
- Owner承認は戦略変更、PBundle freeze、公式提出に限定する
- 内部の連続開発は、失敗または仕様衝突まで継続する

---

## 9. 既存資産

直接再利用:

- PH-D05 canonical teacher trajectory
- raw recording／before-after／progress／terminal
- typed IR／interpreter／operator registry
- P16〜P21 Runtime substrate候補
- C／J／M／Trinity既存実装
- official lifecycle adapter

履歴・参考:

- rev3 D00A〜D14／B00〜B06／A00〜A08／E00〜E04
- PH-D06固定450候補
- source-blind x3証拠群
- S0〜S5既知軌道圧縮成果
- P22系CV成果

再利用禁止:

- fixed trajectory replay
- game-ID policy router
- answer map runtime
- S5 logitsを汎用構造とみなすこと
- 旧phase承認をrev4完成証拠へ流用すること

---

## 10. 主要ディレクトリ

既存repositoryを使用し、新repositoryを作らない。

```text
distillation/
  artifacts/decomposition/arc3/rev4/
  artifacts/structures/arc3/rev4/
  artifacts/p/arc3/rev4/
  src/hds_distill/arc3_task_decomposition.py
  src/hds_distill/arc3_structure_extraction.py
  src/hds_distill/arc3_p_compiler.py

ARC-AGI-3-Agents/
  arc3_agi_agent/structure_library.py
  arc3_agi_agent/p_bundle.py
  arc3_agi_agent/generic_agent.py
  tests/

control/rev4/
  CURRENT_TASK.json
  FAILURE_LOG.jsonl
  COMPLETION_STATUS.json
```

---

## 11. 最終判定

判断基準は工程の多さ、証拠の厚さ、test数ではない。

```text
教師軌道がHDSで分解されたか
汎用構造が抜けたか
命令形Pになったか
エージェントが実際に使ったか
全数実行で結果が出たか
失敗から更新できたか
```

以上を満たすためだけにrepositoryを更新する。
