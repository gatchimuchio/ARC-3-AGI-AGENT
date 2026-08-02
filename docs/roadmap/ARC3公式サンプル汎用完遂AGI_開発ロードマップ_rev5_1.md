# ARC3公式サンプル汎用完遂AGI 開発ロードマップ rev5.1

- Roadmap ID: `ARC3_GENERIC_COMPLETION_AGI_PRODUCT_ROADMAP_REV5_1`
- 製品: `ARC3CompletionAgent`
- 上位仕様: `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev5_1.md`
- 対応指示書: `docs/instructions/ARC3公式サンプル汎用完遂AGI_ロードマップ準拠指示書_rev5_1.md`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 状態: `OWNER_DIRECTIVE_CANDIDATE`
- 現在Point: `M0-P02_CAPABILITY_COVERAGE_MATRIX`
- 旧rev4 roadmap: `HISTORICAL_SUPERSEDED`

---

## 0. エンドポイントからの逆算

```text
DONE
25/25 official sample games = WIN
183/183 levels = COMPLETE
one ARC3CompletionAgent artifact
one ARC3ProductBundle
        ↑
M4 PRODUCT FREEZE AND RELEASE
        ↑
M3 GENERIC / AGI CONFORMANCE
        ↑
M2 FULL-SAMPLE PRODUCT CLOSURE
        ↑
M1 CAPABILITY-FAMILY EXPANSION
        ↑
M0 CAPABILITY BASIS + FIRST AGI CLOSURE
```

HDS分析、教師軌道分解、構造抽出、P生成は、各Pointで製品能力へ接続する作業であり、独立した最終endpointではない。

各Pointは必ず次を含む。

```text
HDS解析
→ product capability change
→ P/J/MまたはAdapterへの統合
→ integrated agent execution
→ behavior delta
→ regression
```

ただし、浅い全体棚卸し、basis選定、clean run、削除試験など、そのPoint固有の目的上、能力変更前の観測が必要な場合は、同じPoint内で次の能力変更または明示的な次Point入力まで閉じる。

---

## 1. 開発原則

### 1.1 進捗として数えるもの

```text
完遂game数
完遂level数
閉じたFailure Signature数
ACTIVE_DEVへ昇格したCapabilityFamily数
製品へ統合済みP/J/M能力数
同一artifactでのregression維持
```

### 1.2 進捗として数えないもの

```text
仕様書数
schema数
test数
commit数
digest数
shell完成
runner完成
空class作成
```

### 1.3 能力資産状態

```text
LOCAL_M
→ PROBATION_DEV
→ ACTIVE_DEV
→ RELEASE_FROZEN
```

一回の成功をrelease P/J0/M0へ直接固定しない。

### 1.4 水平引き算

水平引き算はM1後に初めて行うのではなく、M0から継続する。

```text
1 Case成功
→ LOCAL_M / PROBATION_DEV

2 Case以上で同型
→ GenericMechanismFamily候補

反例・境界Case
→ applicability確定

独立Case＋regression
→ ACTIVE_DEV
```

---

# M0 — CAPABILITY BASIS + FIRST AGI CLOSURE

## 目的

代表能力を覆うbasis game群で、HDS解析からP/J/M能力実装、オンライン三主体循環、実際のWINまでを閉じる。

M0終了時点で、AGI三主体閉ループは既に成立していなければならない。

---

## M0-P01 — EXISTING PRODUCT PATH BINDING

### 目的

既存repositoryの公式Adapter、C/J/M Runtime、P-IR、memory、rollback経路を、再利用する唯一のproduct substrateとして固定する。

### 実施

- 既存公式Adapterから`GenericAGIRuntime`までの実行経路を確認
- C／J／M／P責任を確認
- 既存shell、runner、agent subclassを追加しない
- 現行PとP-IRが能力不足であることを入力事実として固定
- M0以降の変更先を既存substrate上へ限定

### Exit

```text
one existing product substrate selected
parallel shell count = 0
new empty agent class count = 0
current P/P-IR replacement points identified
```

### 状態

`SATISFIED_BY_EXISTING_ASSETS_NO_FURTHER_SHELL_WORK`

---

## M0-P02 — CAPABILITY COVERAGE MATRIX

### 目的

全25 gameを浅く一巡し、初期basis setが覆うべき能力空間を把握する。

### 観測項目

```text
input modality
action surface
RESET
ACTION6
ACTION7
render layer count
temporal / animation
delayed effect
phase change
long-horizon action count
rollback requirement
planning depth
spatial binding type
goal structure
```

### Primary Output

`CapabilityCoverageMatrix`一つ。

### 禁止

- 全gameの深層HDS解析
- P/J/M未接続の大量artifact
- shell／runner／package作業

### Exit

```text
25 games inventoried
183 levels accounted
coverage gaps explicit
basis selection inputs complete
```

---

## M0-P03 — BASIS SET SELECTION

### 目的

最小のgame集合で主要能力面を覆うbasis setを選定する。

### 必須coverage

```text
keyboard-only
ACTION6-only
mixed action surface
RESET
ACTION7
multi-layer or temporal complexity
long-horizon resource case
```

### 選定原則

- 短いgameだけに偏らない
- 同じmechanism familyだけに偏らない
- 複雑actionと長期計画を含める
- 選定根拠を能力coverageで説明する

### Exit

```text
basis set covers all mandatory surfaces
basis selection does not use desired answer convenience only
basis order fixed for M0
```

---

## M0-P04 — BASIS CASE DEEP HDS ANALYSIS

### 目的

basis gameを一件ずつ、Game→Level→Phase→Mechanism Segment→Action Macroへ分解する。

### 必須解析

```text
Purpose Tree
W = (X, R, Mc)
entity / role / relation
state variables
action semantics
precondition
immediate / delayed effect
goal / hazard
order / loop / phase
subgoal
probe
rollback
failure signature
applicability boundary
raw step spans
```

### 粒度

フルHDS解析は機構変化点、progress、failure、phase change、delayed effect帰属へ限定する。同型反復はAction Macroへ圧縮する。

### Exit

```text
all basis raw actions mapped to mechanism segments
all segments have purpose/precondition/operation/effect/termination
open terms explicit
product mapping candidate identified
```

---

## M0-P05 — LOCAL CAPABILITY IMPLEMENTATION

### 目的

M0-P04の解析を、Runtime M、P_dev、J_dev、M_devの製品能力へ実装する。

### 実施順序

```text
first case observation
→ LOCAL_M
→ product behavior test
→ PROBATION_DEV capability
```

### 実装対象

- multi-layer representation
- goal/mechanism hypothesis
- counter-hypothesis
- action binding
- effect prediction
- probe／plan
- J risk／wait／rollback
- M support／refutation／invalidation

### 禁止

- release P/J0/M0への直接固定
- game ID selector
- successful trajectory playback
- reportだけで終了

### Exit

```text
capability loaded by actual product runtime
C output cites capability
J can accept/reject it
M can revise/invalidate it
```

---

## M0-P06 — FIRST ONLINE TRINITY CLOSURE

### 目的

最初のbasis gameで、C／J／Mがオンライン循環し、経験が次の行動を変えることを実証する。

### 必須循環

```text
OBSERVE
→ C generates multiple models/plans
→ J selects or probes
→ one action
→ attribution
→ M update
→ next candidate/plan/action changes
```

### Exit

```text
all external actions J-authorized
relevant M update changes future behavior
failed hypothesis is not repeated indefinitely
agent generates next probe/question
first basis game WIN
```

---

## M0-P07 — BASIS SET WIN CLOSURE

### 目的

M0-P06で成立した同じAGI構造をbasis set全体へ拡張し、全basis gameをWINさせる。

### 進行

各gameについて:

```text
HDS analysis
→ capability delta
→ product integration
→ run
→ failure classification
→ minimal repair
→ WIN
```

### Exit

```text
all basis games WIN
all basis levels complete
keyboard-only covered
ACTION6-only covered
mixed/RESET/ACTION7 covered
long-horizon case covered
```

---

## M0-P08 — INITIAL HORIZONTAL SUBTRACTION

### 目的

basis game間の同型構造をGenericMechanismFamilyへ統合し、PROBATION_DEVからACTIVE_DEVへ昇格できる能力を確定する。

### 必須

- logic／parameter分離
- positive／negative／boundary Case
- applicability predicate
- identity feature排除
- affected basis game regression

### Exit

```text
at least one cross-game ACTIVE_DEV capability
basis games remain WIN
no game-ID mechanism selection
M0_COMPLETE
```

---

# M1 — CAPABILITY-FAMILY EXPANSION

## 目的

残りgameを一件ずつ個別solver化せず、共通Failure Signatureと不足CapabilityFamily単位で閉じる。

---

## M1-P01 — FULL-SAMPLE FAILURE / CAPABILITY INVENTORY

### 目的

現行ACTIVE_DEV bundleで全25 gameを実行し、未完遂を構造原因でclusterする。

### Failure Class

```text
OBSERVATION_LOSS
REPRESENTATION_ERROR
ENTITY_ROLE_ERROR
RELATION_ERROR
GOAL_INDUCTION_ERROR
MECHANISM_INDUCTION_ERROR
PRECONDITION_ERROR
ACTION_BINDING_ERROR
EFFECT_PREDICTION_ERROR
DELAY_ATTRIBUTION_ERROR
PLAN_ERROR
PROBE_ERROR
JUDGEMENT_ERROR
MEMORY_RETRIEVAL_ERROR
MEMORY_UPDATE_ERROR
ROLLBACK_ERROR
LEVEL_TRANSFER_ERROR
GAME_TRANSFER_ERROR
RESOURCE_ERROR
```

### Exit

```text
25 games attempted
failure clusters ranked by affected games/levels
highest-leverage capability gap identified
```

---

## M1-P02 — CAPABILITY CLOSURE UNIT SELECTION

### 目的

次に閉じる能力不足を、最大共有Failure Signatureと完遂delta見込みから選ぶ。

### 選定軸

```text
affected game count
affected level count
reusability
blocking severity
implementation dependency
regression risk
```

### Exit

一つの`CapabilityClosureUnit`が固定される。

---

## M1-P03 — HDS CASESET ANALYSIS

### 目的

単一Caseでなく、同じfailure clusterを持つ複数CaseをHDSで比較する。

### 必須

- common frame
- differing conditions
- baseline／alternative／counter-hypothesis
- positive／negative／near-miss
- applicability boundary
- falsification condition
- horizontal subtraction candidate

### Exit

```text
selected mechanism explains affected CaseSet
counterexamples preserved
product component responsibility fixed
```

---

## M1-P04 — PRODUCT CAPABILITY IMPLEMENTATION

### 目的

M1-P03の結果を、P_dev／J_dev／M_dev／C／J／M／Adapterの最小責任箇所へ実装する。

### 必須

- product runtimeが直接読む
- capability asset stateを記録
- identity/replay featureを含まない
- expected behavior deltaを定義

### Exit

```text
capability executable in product
unit-level behavior delta observed
no parallel product path
```

---

## M1-P05 — AFFECTED GAME CLOSURE

### 目的

影響game／levelを再実行し、選択したFailure Signatureを閉じる。

### Exit

```text
target failure decreases or disappears
affected game/level completion increases
completed basis regression maintained
```

失敗が別責任へ移動した場合、新しいFailure SignatureとしてM1-P02へ戻る。

---

## M1-P06 — CONTINUOUS HORIZONTAL SUBTRACTION / PROMOTION

### 目的

複数Caseで成立した能力を統合し、PROBATION_DEVからACTIVE_DEVへ昇格または降格する。

### 昇格条件

- 独立Case support
- negative／boundary Case
- regression PASS
- identity/replay finding 0
- behavior delta

### 降格条件

- 期待failureが減らない
- 別failureを増やす
- applicability外で誤作動
- identity proxyが見つかる

### Exit

asset stateと次の適用範囲が確定する。

---

## M1-P07 — FULL MAPPING CLOSURE

### 目的

M1-P01〜P06を反復し、全25 game／183 levelを少なくとも一度完遂し、全raw actionをMechanism Segmentへ対応づける。

### Exit

```text
25 games individually WIN at least once
183 levels individually complete at least once
all raw actions mapped to segments
all segments mapped to CapabilityFamily or explicit Domain-Local Residue
unused primary analysis artifact = 0
one active development ProductBundle
M1_COMPLETE
```

---

# M2 — FULL-SAMPLE PRODUCT CLOSURE

## 目的

一つのACTIVE_DEV ProductBundleを使用し、clean stateから公式サンプル全体を連続完遂する。

---

## M2-P01 — CLEAN RUN A / OFFICIAL ORDER

### 目的

clean session、公式順序、同一bundleで25 gameを連続実行する。

### 記録

```text
game result
levels completed
actions
stop reason
failure signature
memory promotions
resource use
```

### Exit

full-run failure setが得られる。全数PASSならM2-P04へ進む。

---

## M2-P02 — FULL-RUN FAILURE REPAIR

### 目的

full-run特有のstale memory、negative transfer、resource、order dependencyをHDSで責任分解し、最小修正する。

### Exit

対象full-run failureが閉じるか、明確な次CapabilityClosureUnitへ変換される。

---

## M2-P03 — CLEAN RERUN UNTIL PASS

### 目的

M2-P01／P02を反復し、公式順序clean runで25/25・183/183を成立させる。

### Exit

```text
Run A = 25/25 WIN
Run A = 183/183 complete
zero product crash
zero manual intervention
```

---

## M2-P04 — SHUFFLED ORDER RUNS

### 目的

game順序に依存したmemory contaminationまたは暗黙routerを検出する。

### 実行

```text
Run B = shuffle order 1
Run C = shuffle order 2
```

### Exit

- 順序依存がなければPASS
- 順序依存があればblocking failureとして修正

---

## M2-P05 — FULL-SAMPLE PRODUCT CLOSURE

### Exit

```text
one agent architecture
one ACTIVE_DEV ProductBundle
clean state
25/25 WIN
183/183 complete
zero fixed replay
zero identity router
M2_COMPLETE
```

---

# M3 — GENERIC / AGI CONFORMANCE

## 目的

25/25という結果が、lookup、静的個別solver、shellではなく、三主体AGI構造によって成立したことを確認する。

---

## M3-P01 — C / J / M / P ABLATION

### 必須試験

```text
remove C → new representation/hypothesis/plan generation fails
remove J → external action and ACTIVE M commit fail
remove M → learning delta disappears and failure repeats
remove P → ARC3 capability disappears
```

### Exit

全削除結果が設計予測と一致する。

---

## M3-P02 — MEMORY CAUSALITY

### 必須試験

```text
same observation + relevant M revision
→ candidate / plan / action changes

same observation + irrelevant M
→ action unchanged
```

### Exit

記憶因果と無関連不変性が成立する。

---

## M3-P03 — IDENTITY / REPLAY AUDIT

### 必須

- `game_id`／`level_id` taint
- exact frame hash route scan
- trajectory index scan
- successful action sequence scan
- Domain-Local Residue selector audit

### Exit

```text
identity action router finding = 0
fixed trajectory playback finding = 0
```

---

## M3-P04 — APPLICABILITY COUNTERFACTUAL

### 目的

MechanismSpecが表面identityではなく成立条件で選択されることを確認する。

### Exit

```text
condition-preserving perturbation → applicability maintained
condition-breaking perturbation → non-applicable or SUSPEND
```

---

## M3-P05 — RUNTIME / VERSION LEARNING

### 目的

実行時M更新と、安定能力の次版P/J0/M0再コンパイルを分離して確認する。

### 必須

```text
runtime experience first updates M
stable multi-Run structure only promotes to release candidate
restart uses compiled initial state
false learning can be invalidated/rolled back
```

### Exit

Runtime LearningとVersion Learningが両方成立する。

---

## M3-P06 — CONFORMANCE FULL REGRESSION

### Exit

```text
all conformance tests PASS
25/25 WIN maintained
183/183 maintained
M3_COMPLETE
```

---

# M4 — PRODUCT FREEZE AND RELEASE

## 目的

ACTIVE_DEV能力をrelease初期状態へ再コンパイルし、全数完遂済み製品を再現可能なartifactへ固定する。

---

## M4-P01 — RELEASE BUNDLE COMPILATION

### 目的

```text
ACTIVE_DEV P_dev / J_dev / M_dev
→ RELEASE_FROZEN P / J0 / M0
```

### Exit

一つのrelease `ARC3ProductBundle`が生成される。

---

## M4-P02 — CODE / DEPENDENCY / RESOURCE FREEZE

### Exit

code、dependencies、resource config、adapter configが一意に固定される。

---

## M4-P03 — CLEAN INSTALL

### Exit

fresh environmentで同一artifactをinstall／起動できる。

---

## M4-P04 — CLEAN FULL-SAMPLE RERUN

### Exit

```text
same release artifact
25/25 WIN
183/183 complete
```

---

## M4-P05 — KAGGLE PACKAGE / NORMAL RUN

### Exit

Notebook／entrypoint／output contractを満たし、normal runが完了する。

---

## M4-P06 — SUBMISSION / PLATFORM SEPARATION

### 目的

製品failureとplatform failureを分離して提出結果を記録する。

### Exit

```text
ARC3_COMPLETION_AGENT_PRODUCT_RELEASED
```

---

## 2. 現在作業

```text
M0-P02_CAPABILITY_COVERAGE_MATRIX
```

M0-P01は既存substrateで充足済みとし、新しいshell、runner、agent subclassを作らない。

次に実施するのは、公式25 gameを浅く一巡したCapability Coverage Matrixの作成と、M0-P03 basis set選定である。

---

## 3. 逸脱停止条件

次を検出した場合、現在Pointを停止し、ロードマップへ戻る。

```text
shellを作っている
runnerを作っている
schema／evidence数を増やすことが目的化している
全game深層解析を先行している
P/J/Mへ接続されないartifactを作っている
完遂数または能力差分が変わらない作業を継続している
```
