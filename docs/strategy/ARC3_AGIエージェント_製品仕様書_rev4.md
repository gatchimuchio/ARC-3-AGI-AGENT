# ARC3 Completion AGI Agent 製品仕様書 rev4

- 製品ID: `ARC3_COMPLETION_AGI_AGENT_PRODUCT_REV4`
- 製品名: `ARC3CompletionAgent`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 対象環境: ARC Prize 2026 / ARC-AGI-3公式サンプル
- 日付: `2026-08-02`
- 状態: `OWNER_PRODUCT_DIRECTIVE_INSTALLED`
- 開発ロードマップ: `docs/roadmap/ARC3_AGIエージェント_製品開発ロードマップ_rev4.md`

---

## 0. 製品定義

本開発の最終成果物は、HDS分析結果、構造データ、命令形P、仕様書、評価reportではない。

最終成果物は次の実行可能製品である。

```text
ARC3CompletionAgent
=
公式ARC3環境を観測し
一手ずつ自律的に判断・実行し
結果を記憶へ反映し
公式サンプル25 game／183 levelを
同一のAGI構造で完遂するエージェント
```

HDS、成功軌道、回答、解析データ、構造抽出、命令形P、J設定、初期記憶は、製品能力を構築するための素材・手段・内部部品である。

公式サンプル完遂は必須の既知サンプル回帰である。開発完了は、統合された同一artifactが未知環境評価と公式full scopeまで完遂した時点で判定する。

---

## 1. 製品エンドポイント

### 1.1 公式入出力契約

製品は公式`EnvironmentWrapper`へ接続し、各cycleで次を行う。

```text
INPUT
  FrameDataRaw
    frame[]
    state
    levels_completed
    win_levels
    available_actions
    full_reset
    action_input

PROCESS
  OBSERVE
  → FRAME
  → RETRIEVE
  → COMPUTE
  → JUDGE
  → ACT / PROBE / WAIT / ROLLBACK / RESET / STOP
  → OBSERVE_RESULT
  → UPDATE_MEMORY
  → REFRAME

OUTPUT
  legal GameAction exactly one per external cycle
  ACTION6の場合は現在観測から生成したx/y payload
```

製品は`WIN`または`GAME_OVER`まで自己循環する。人間はgame途中のaction、対象、順序、probe、resetを指示しない。

### 1.2 公式サンプル回帰受入

```text
one packaged agent artifact
one active runtime architecture
25 / 25 games final state = WIN
183 / 183 levels completed
all legal action surfaces supported
ACTION6 pointer payload supported
no crash
no uncaught exception
no manual per-step intervention
no fixed successful-trajectory playback
```

公式サンプル全数完遂を、本repositoryの必須回帰条件とする。

これは未知分布への汎用性または製品完成を単独では証明しない。製品完成には、同一active artifact、CVとsingle-artifact証拠の分離、semantic transformed-environment完遂、未使用locked evaluator完遂、公式output bytes／score／full scope完遂を追加で要求する。別runtimeの証拠合算は禁止する。

### 1.3 完成claim gate

```text
KNOWN_SAMPLE_REGRESSION
+ MEMORY_CAUSAL
+ P_VERSION_LEARNING_CAUSAL
+ SEALED_SINGLE_ARTIFACT_COMPLETE
+ COMPETITION_READY
+ OFFICIAL_FULL_COMPLETE
= ARC3実証上の製品完成
```

機械正本は`analysis/product/rev4/product_completion_audit.json`とし、一件でもblocking gateが`PASS`以外なら完成claimを禁止する。

### 1.4 資源契約

現行のcompetition pathは1ゲーム128 actionで停止するが、保持済み教師成功軌道は最大1,519 actionを必要とする。

したがって、128 action固定は製品契約に不適合である。

開発時の公式サンプル受入runnerは次を満たす。

```text
per-game action budget >= 4096
budget is configurable
actual actions are measured
known successful max no-level-progress streak = 644
development no-progress stop = 650
no-progress stop is mechanism-aware and separate from action budget
unbounded loop is forbidden
```

最終packageでは実測結果から安全な上限へ圧縮する。能力成立前に低い固定上限で製品を停止させない。

---

## 2. 製品アーキテクチャ

### 2.1 AGI Kernel

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
ARC3CompletionAgent = Adapter + Trinity(C, J, M) + Product Runtime
```

- `L0`: 型付き計算・実行基盤
- `P`: ARC3を解くための実行可能な命令形保持体
- `C`: 表現、仮説、反対仮説、予測、候補、probe、planを生成する計算主体
- `J`: HDSにより目的、観測要求、計算要求、採否、行動、rollback、記憶更新、停止を決定する判断主体
- `M`: 現在の判断根拠を追加・修正・統合・無効化・削除・rollbackする可変記憶主体
- `Adapter`: 公式FrameData／GameActionと内部型を変換する非主体

### 2.2 三主体の製品責任

#### C — 計算主体

```text
current observation
+ P
+ Jからの計算要求
+ Mから引用された根拠
→ representations
→ task/mechanism hypotheses
→ counter-hypotheses
→ predictions
→ action/probe/plan candidates
```

Cは最終採否、外部action、active memory commitを行わない。

#### J — HDS判断主体

Jは製品runtimeの主幹制御層である。

```text
Purpose
Boundary
Closure
F / Md / Cm / U
ModelSet
Gates
SUSPEND / ROLLBACK / STOP
Action Authorization
Memory Update Authorization
Next Question
```

Jは全外部actionを一意に承認する。Cまたはadapterからの直接action経路を禁止する。

#### M — 可変記憶主体

Mは次を保持・改訂する。

```text
episode state
level mechanism hypotheses
entity/role bindings
action-effect evidence
goal/hazard models
failed attempts
successful subplans
delayed-effect attribution
cross-level common structures
cross-game transferable structures
```

経験は次cycle以降のCとJを実際に変更しなければならない。

### 2.3 標準状態機械

```text
BOOT
→ SELF_CHECK
→ OBSERVE
→ FRAME
→ RETRIEVE
→ COMPUTE
→ JUDGE
   ├─ RECOMPUTE
   ├─ PROBE
   ├─ ACT
   ├─ WAIT
   ├─ ROLLBACK / RESET
   ├─ SUSPEND
   └─ STOP
→ OBSERVE_RESULT
→ ATTRIBUTE_OUTCOME
→ UPDATE_MEMORY
→ REFRAME
→ ...
```

---

## 3. 製品能力

ARC3CompletionAgentは、単なる合法action探索器ではなく、少なくとも次の能力を統合する。

### 3.1 観測・表現

- 一手内の全camera render frameの保持と時系列関係
- action完了時の最終composited view
- 時系列frame差分
- entity／object／region／interfaceの分離
- role、shape、color、count、position、orientation、topology
- relation、containment、alignment、adjacency、path、order
- current action surfaceとpayload schema
- level progress、terminal、reset、failure
- animation／delayed effect／action completionの区別

最終composited viewだけへ縮退してはならない。公式`FrameDataRaw.frame[]`は空間layerではなく、一回の外部actionが完了するまでにcameraが生成した時系列render列である。途中frameにだけ現れるanimation／delayed effectも保持する。

### 3.2 タスク・機構同定

- 現levelの目的候補
- precondition
- action-effect
- state transition
- delayed effect
- goal／hazard
- operation order
- repetition／loop
- subgoal decomposition
- phase change
- level間のルール継承と変更

### 3.3 探索・計画

- reversible probe
- information-gain exploration
- hypothesis discrimination
- bounded plan search
- subgoal planning
- effect verification
- no-effect recovery
- hazard veto
- rollback／level reset
- resource-aware continuation

### 3.4 学習・更新

- action-effect support／refutation
- false hypothesis invalidation
- current mechanism model replacement
- relevant memory retrieval
- irrelevant memory isolation
- level終了時のconsolidation
- game間の共通構造転移

### 3.5 行動表面

公式サンプルの全actionを扱う。

```text
RESET
ACTION1
ACTION2
ACTION3
ACTION4
ACTION5
ACTION6(x, y)
ACTION7
```

ACTION6は単なるconnected-component中心候補だけでなく、セル、領域、境界、空間関係、UI、経路、候補位置を現在観測から生成できること。

---

## 4. 製品内能力資産

### 4.1 P — 命令形保持体

Pは解析reportではなく、Cが実行する能力本体である。

```text
OBSERVE <fields>
REPRESENT <objects/relations/state>
FORM <hypotheses and counter-hypotheses>
SELECT <applicable mechanism>
GENERATE <actions/probes/plans>
PREDICT <effect/hazard/progress>
VERIFY <observed outcome>
REQUEST <memory retrieval/update>
CONTINUE / WAIT / PROBE / ROLLBACK / RESET / STOP
```

Pは次を含む。

- representation operators
- task/mechanism induction operators
- action-effect operators
- goal/hazard operators
- order/composition operators
- probe/planning operators
- verification／failure-update operators
- resource-control operators

現行`HybridRelationalInstructionBody`の「未観測actionをprobeし、progressを再利用する」一般ヒューリスティックだけでは製品Pとして不足する。

### 4.2 J0 — ARC3 HDS Domain Profile

Jの上位目的と権限はHDS Kernelに置く。ARC3固有の判断補助をDomain Profileとして与える。

- progress／terminal優先
- reversible probe優先
- game-over hazard veto
- delayed effect待機
- action completion待機
- no-effect分類
- level reset条件
- resource／loop境界
- unresolved時の次質問

### 4.3 M0 — 初期判断根拠

M0は公式サンプルの答え表ではない。次をseedする。

- ARC3 action semantics
- generic visual／interaction primitives
- known structure families
- hazard／failure signatures
- probe patterns
- task decomposition patterns
- Pの適用境界

### 4.4 Product Bundle

```text
ARC3ProductBundle
  PBundle
  JDomainProfile
  M0
  type/operator registry
  resource contract
  runtime configuration
  official adapter configuration
```

このbundleを同一の製品artifactへ組み込む。

---

## 5. HDS解析・教師データの位置づけ

### 5.1 素材

保持済みPH-D05教師corpusは次を含む。

```text
25 games
183 levels
10,942 frames
11,574 canonical successful actions
all RESET / ACTION1..ACTION7 surfaces
```

これは製品そのものではなく、P／J0／M0を構築・検証するための能力素材である。

### 5.2 HDS開発解析

開発時HDSは、成功軌道を次へ分解・解釈する。

```text
purpose
environment state
entity / role / relation
precondition
operation
effect / delayed effect
progress contribution
goal / hazard
order / composition
failure alternative
applicability boundary
```

出力は、最終的に製品P／J0／M0へコンパイルされる場合だけprimary成果として扱う。

### 5.3 最大情報からの減算

```text
回答・成功軌道・解析データを最大限使用
→ 機構と命令形を抽出
→ game固有parameterを分離
→ replay／identity依存を減算
→ 製品runtimeへ統合
→ 公式サンプルで実行検証
```

抽出前にsource-blindやidentity-freeを要求して能力情報を失わせない。減算監査は製品P／runtimeに対して行う。

---

## 6. 現行repository資産と製品差分

### 6.1 再利用する製品部品

- `GenericAGIRuntime`: C／J／M循環
- `CognitiveSession`: scorecard単位の継続主体
- `GenericHDSJudgementSubject`: action／memory／rollback権限
- `SemanticMemory`／event ledger／overlay／consolidation
- `CompetitionGenericEnvironment`: 公式adapter
- `GenericAGIAgent`: 公式Agent shell
- `generic_competition_runner`: 25 game逐次runner
- typed P-IR／interpreter／compiler
- PH-D05 canonical teacher corpus
- P16〜P21のstate ownership／evidence／memory／runtime substrate

### 6.2 現行の製品阻害要因

#### B-01 Resource Contract不適合

```text
current competition action budget = 128
known successful max per game = 1519
```

現状のままでは能力に関係なく複数gameを完遂不能。

#### B-02 P能力不足

現行competition runnerは`HybridRelationalInstructionBody()`を直接使用する。これは一般探索scorerであり、PH-D05／HDSから得たARC3機構能力を搭載していない。

#### B-03 P-IRがcompatibility fixture

`create_cognitive_session()`は指定がなければ`compatibility_p_ir_program()`を使用する。これは製品能力bundleではない。

#### B-04 観測縮退 — M1 CLOSED

全action frame、最終composited view、frame間差分、action completion、外部cycle履歴を製品表現へ統合した。公式25環境でframe数保存とidentity境界を実測済みである。

#### B-05 ACTION6候補不足 — M1 CLOSED

ACTION6候補はobject、cell、region、boundary、path、UI、candidate-positionの7分類を、現観測由来・bounded・重複座標なしで生成する。

#### B-06 目的・機構・計画能力不足 — M3 CLOSED

同一製品runtimeに、複数representation、競合機構仮説、subgoal、4-step plan、probe、失敗仮説無効化、rollback後replanを統合した。M4正本runは10,733手すべてでC planとJ commitを一対一に記録し、M参照が次判断へ結合されたことを示す。

#### B-07 製品受入未接続 — M4 CLOSED

同一`ARC3CompletionAgent v1.0`を公式サンプル25 gameへ一セッションで逐次実行し、25/25 `WIN`、183/183 level、10,733 action、runtime failure signature 0、scorecard leak 0を実測した。正本証拠は`analysis/product/rev4/m4_full_sample_product.json`とする。

#### B-08 公式外部実行 — M5 GATE

wheel・clean install・同一サンプル全数回帰・依存lock・Kaggle Notebook静的検証はローカル閉包済みである。外部Kaggle Notebook実行と提出は、当該操作に対するOwnerの現在の明示授権がある場合に限る。

---

## 7. 製品構築順序 — エンドポイントからの逆算

```text
Endpoint E0
  25/25 game WIN, 183/183 level complete
      ↑ requires
Product E1
  official-compatible one-agent runtime
      ↑ requires
Runtime E2
  closed C/J/M/P loop with adequate resources
      ↑ requires
Capability E3
  representation + induction + planning + action + learning
      ↑ requires
Product Bundle E4
  P + J0 + M0 compiled and loaded
      ↑ requires
Capability Build E5
  HDS interpretation of teacher trajectories and failure logs
      ↑ requires
Materials E6
  PH-D05 corpus, recordings, source-assisted analysis, existing assets
```

開発はE0から不足条件を逆算し、E1→E5を製品へ追加する。E5やE6の完成を開発終了としない。

---

## 8. 製品開発原則

1. 全milestoneで実行可能な`ARC3CompletionAgent`を保持する。
2. milestoneの成果は、製品コード差分と公式サンプル実測差分で示す。
3. 構造／P／J0／M0は製品runtimeへloadされるまで未統合素材とする。
4. test数、schema数、artifact数、承認数を進捗指標にしない。
5. 進捗指標は次とする。

```text
started games
completed levels
completed games
failure class distribution
action/resource usage
memory-caused behavior change
regression count
```

6. 新repositoryを作らない。
7. 証拠・digest・approval専用phaseを作らない。
8. 旧known-sample replayを製品能力と数えない。
9. 製品阻害要因を優先順位順に除去する。
10. 製品完成まで、分析だけを継続してはならない。

---

## 9. 製品受入試験

### 9.1 公式I/O

- 全25 environmentをopen／closeできる
- 全action surfaceを送信できる
- ACTION6 payloadが有効範囲
- 一手内の全render frameと最終composited viewを失わない
- terminal／progressを正しく扱う

### 9.2 三主体

- C除去で候補生成能力を失う
- J除去で外部actionが不能
- M除去で同じ未学習挙動を反復
- P除去でARC3能力を失う
- CからのJ bypassが不可能

### 9.3 記憶因果

```text
same observation
+ relevant Mを追加／修正／無効化
→ candidate／plan／actionが変化

same observation
+ irrelevant M
→ action不変
```

### 9.4 自律

人間は高位目的「gameを完遂せよ」だけを与える。以後の観測、問い、仮説、probe、行動、reset、停止を三主体が生成する。

### 9.5 公式サンプル完成

```text
25 games attempted
25 games WIN
183 levels complete
0 product crashes
0 manual step interventions
0 fixed trajectory playback
```

---

## 10. 開発終了条件

本開発は次のすべてが成立した時点で終了する。

```text
ARC3CompletionAgent product artifact exists
AND product loads one ARC3ProductBundle
AND C/J/M/P loop is active
AND HDS authorizes every external action
AND M updates future behavior
AND official sample runner observes 25/25 WIN
AND official sample runner observes 183/183 complete
AND product package is reproducible and executable
```

HDS解析、構造抽出、P生成、AGI骨格構築のいずれか単体では終了しない。
