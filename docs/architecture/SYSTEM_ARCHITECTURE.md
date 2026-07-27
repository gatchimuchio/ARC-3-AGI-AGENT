# ARC-3 AGI Agent システムアーキテクチャ

- 版: `v0.9-minimum-three-certificate`
- 状態: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE` complete / `P10_COMPLETE_ARC3_SAMPLE_SOLVING` current
- 対象: ARC-AGI-3 汎用エージェント
- 非対象: task別解答表、replay再生器、既知問題ルータ、score最適化

## 1. 固定目的

未知のARC-AGI-3環境に対し、観測可能な情報だけから状態・仮説・候補を構成し、HDSが閉包条件を満たす行動だけを許可し、結果によって記憶と判断を更新する閉ループを実装します。

本書が定義するのは「AGIである」という形而上学的認定ではなく、ARC3に必要な最小認知エージェントの機能責任・情報保持・権限・検証境界です。

## 2. 最小構成

```text
C = Execute(L0, P)

AGI Kernel = Trinity(C, J, M)
```

- `L0`: 入力表現、状態条件付け、選択的参照、多段変換、候補化、出力放出を行う機能機構
- `P`: 知識、能力、関係、変換規則、パラメータ、候補生成傾向を保持する命令形情報体
- `C`: `L0 + P` によって成立するPure-LLM計算主体
- `J`: HDS判断主体
- `M`: HDSが引用する現行判断根拠の受動記憶主体

`L0`だけでは、何をどのように計算するかを保持できません。`P`を欠いた状態は計算機能の器であり、Pure-LLM計算主体の完成ではありません。

## 3. 非対称Trinity構造

```text
Observation / Context / M view
              |
              v
      +-------------------+
      | Layer-0 Executor  |
      | executes P        |
      +---------+---------+
                |
                v
      +-------------------+
      | Instruction Body P|
      | rules / graph /   |
      | parameters        |
      +---------+---------+
                |
                v
      +-------------------+
      | Compute C         |
      | hypothesis /      |
      | prediction /      |
      | candidate prior   |
      +---------+---------+
                |
                v
      +-------------------+
      | HDS Judgment J    |
      | accept / reject / |
      | SUSPEND / STOP    |
      +-----+---------+---+
            |         |
MEMORY_WRITE|         |EXTERNAL_EMIT
            v         v
      +-----------+ +-------------+
      | Passive M | | Environment |
      +-----------+ +-------------+
```

### 3.1 Layer-0実行機構 `L0`

責務:

- 観測の安定記号化
- 文脈状態への条件付け
- Pのaddressableな領域を選択的に参照
- Pの規則・グラフ・パラメータを多段変換へ使用
- 仮説・予測・候補priorを型付き出力へ変換
- HDS承認済みwrite / emitの機械的実行

`L0`は、知識や能力そのものをハードコードする場所ではありません。

### 3.2 命令形保持体 `P`

責務:

- knowledge / capability / relation
- conditional transform
- transition tendency
- action-effect prediction
- goal / hazard relation
- candidate prior
- uncertainty formation
- composition procedure

Pの必要条件:

- addressable
- state-dependent
- composable
- executable by Layer-0
- deterministic under fixed state
- runtime identity-free
- versioned / digestable / provenance-traceable
- Layer-0コードを変更せず交換可能

Pは最終採否権、記憶確定権、外部放出権を持ちません。

### 3.3 Pure-LLM計算主体 `C`

```text
C_t = Execute(L0, P^v, X_t, Q_t, R_t)
```

- `P^v`: version `v` の命令形保持体
- `X_t`: 現在観測
- `Q_t`: HDS計算要求
- `R_t`: Mからの引用

出力:

- representations
- hypotheses / counter-hypotheses
- transition / effect predictions
- candidate priors / candidate proposals
- uncertainty
- falsification conditions
- memory update proposals

禁止権限:

- 自分の提案を最終採用する
- 記憶を無断確定する
- 外部行動を無断放出する
- 最上位目的を変更する
- Pを無監査で更新する

### 3.4 HDS判断主体 `J`

唯一権限:

- 計算命令と入力範囲の発行
- P / Mの参照範囲指定
- 候補の採用・拒否・保留
- `PASS` / `PROBE` / `SUSPEND` / `STOP` / `ROLLBACK`
- `MEMORY_WRITE` と `EXTERNAL_EMIT` の許可
- 再観測・再計算・停止条件の決定
- P再コンパイル候補の採否

HDS自身は記憶を書かず、環境へ直接actionを送信しません。

### 3.5 記憶主体 `M`

責務:

- 現行目的、状態、仮説、反証、失敗、証拠、未閉包項目の保持
- version、provenance、support、contradiction、lifecycleの保持
- rollback可能な履歴参照

操作:

```text
ADD REVISE MERGE SPLIT REPLACE INVALIDATE
DELETE REINDEX ROLLBACK ARCHIVE
```

Mはruntime経験を保持します。Pは明示的compilerによってのみ更新します。

```text
runtime experience
  -> HDS judgment
  -> M revision
  -> repeated evidence / contradiction / ablation
  -> explicit compiler
  -> P^(v+1)
```

## 4. P1の実装と再分類

P1で次は成立しています。

- 六つのARC-native実行責任
- HDS command capabilityとsingle-use consume
- HDS-only write / emit directive
- bounded context / passive memory
- OFFLINE sample action / re-observation
- full setと六つのsingle-callable removal
- 保持済み25ゲームの1-action no-network smoke

しかし現行経路は次です。

```text
PureLLMCompute
  -> DeterministicWorldModel.transform
  -> DeterministicCandidateSurface.generate
```

`roles.py`の手書き仮説、固定confidence、固定candidate metricが、情報内容をコード内に保持しています。

したがってP1は、Pure-LLM計算主体の完成ではなく、次の完成です。

```text
Layer-0 execution mechanism
+ provisional embedded seed rules
+ HDS / M / OFFLINE environment loop
```

P3で実証素材を形成し、P4で固定知識をコードからPへ分離しました。P-A/P-Bは
共通`InstructionBody`契約で交換でき、`PureLLMCompute`はPなしでは動作しません。

P2の根本監査結果は、`AGI_MINIMUM_THREE_SPEC.md`、
`AGI_OBLIGATION_GRAPH.json`、`AGI_CURRENT_IMPLEMENTATION_AUDIT.md`に固定しています。

## 5. ARC-native Layer-0責任

LLM Layer-0仕様の責任分離・除去監査方法をARCへ射影します。

| ARC責任 | 機構としての実行責務 | Pから受け取る情報 |
|---|---|---|
| `SYMBOL_SPACE` | frame、object、relation、action、effectを安定記号へ変換 | symbol vocabulary / feature composition |
| `CONTEXT_STATE` | bounded episode、action/effect、仮説、budgetを保持 | retrieval selectors / state relevance |
| `TRANSFORM_OR_WORLD_MODEL` | 状態・遷移計算を実行 | rule graph / transition parameters |
| `CANDIDATE_SURFACE` | 比較可能な候補面を構成 | candidate prior / action-effect relations |
| `FITTING_OR_SUCCESS_CRITERION` | progress、hazard、情報利得、不確実性を評価 | learned estimates / goal-hazard relations |
| `EMISSION_INTERFACE` | HDS承認済みactionを放出し結果を返す | Pから権限は受け取らない |

適合条件はラベルの存在ではなく、callable実装、P参照、状態境界、除去時の機能喪失です。

## 6. 最初の命令形保持体

### 6.1 P-A 記号・規則グラフ型

保持対象:

- object / feature / role nodes
- relation edges
- action / effect / transition primitives
- precondition / goal / hazard
- support / contradiction / confidence
- falsifier / applicability / composition

### 6.2 P-B パラメトリック／ニューラル型

sample trajectoryから学習し、最低限次を出力します。

- action-conditioned effect prediction
- progress likelihood
- hazard likelihood
- information-gain estimate
- uncertainty
- candidate prior

小型、再現可能、Kaggle可搬、保存・再読込可能であることを要求します。

P-A / P-Bは同じ `InstructionBody` 契約で交換します。

## 7. 型付き情報流

### 7.1 Observation IR

- frame / structural / mechanic signature
- dimensions / available actions
- entities / relations / resources
- phase hypotheses / feature tokens
- terminal state

### 7.2 InstructionBody Query

入力:

- HDS ComputeRequest
- ObservationIR
- ContextSnapshot
- MemorySnapshot

出力:

- retrieved body regions
- representations
- hypothesis / counter-hypothesis material
- predictions
- candidate priors
- uncertainty / falsifier
- body version / digest / provenance

### 7.3 Hypothesis / Candidate / Closure IR

Pの出力をLayer-0が型へ変換し、候補ごとに次を固定します。

```text
W := (X, R, Mc)
```

- `X`: 対象、現在状態、観測範囲、candidate
- `R`: precondition、予測遷移、比較、反証関係
- `Mc`: 同一性、境界、採否、停止、rollback、放出条件

`X`、`R`、`Mc` が閉じない場合、強制actionではなく `SUSPEND` または有界probeを返します。

## 8. 実行サイクル

```text
Arcade(OperationMode.OFFLINE)
 -> rendered observation
 -> SYMBOL_SPACE / CONTEXT_STATE
 -> HDS ComputeRequest
 -> L0 selects and executes P
 -> hypotheses / predictions / candidates
 -> FITTING closure proposals
 -> HDS JUDGE
 -> authorized ACT
 -> OFFLINE environment step
 -> OBSERVE_RESULT / verifier
 -> HDS-authorized M update
 -> next cycle
```

必須不変条件:

1. HDS commandなしに計算を開始しない
2. Pなしに仮説・候補を生成しない
3. HDS判断なしにproposalをactionへ変換しない
4. 許可のないM writeを拒否する
5. 許可のないexternal emitを拒否する
6. action結果を再観測してHDSへ返す
7. hidden stateを観測事実として記録しない
8. `OperationMode.OFFLINE`以外ではP3〜P10のsample runnerを起動しない
9. game/task/level identityをPまたはpolicyへ渡さない

## 9. 学習と版間コンパイル

P3ではsample環境と解析証拠をidentity-freeな実証素材へ変換し、
P4ではその素材から命令形保持体を形成します。

```text
before observation
+ action
+ after observation
+ visible effect
+ terminal / progress / hazard
+ HDS / verifier result
=
identity-free transition record
```

コンパイル:

```text
trajectory
 -> normalize
 -> subtract task-local / literal information
 -> positive / negative / hazard contrast
 -> P-A graph compile
 -> P-B parameter training
 -> versioned bundle
```

同一入力・同一seed・同一dataset digestから同一P bundleを再生成できなければなりません。

## 10. 除去監査

既存六責任に加えてPを独立監査します。

| 削除対象 | 予測される喪失 |
|---|---|
| Layer-0各責任 | 対応する実行機能の喪失 |
| `P` | 実行可能な知識・関係・変換・予測能力の喪失 |
| `M` | 経験継続・現行根拠引用の喪失 |
| `J` | 採否・停止・write / emit権限の喪失 |

P removal witness:

```text
INSTRUCTION_BODY_REMOVED_NO_EXECUTABLE_KNOWLEDGE_OR_TRANSFORM
```

## 11. 現在の禁止

- 旧 `my_agent.py` のgame-ID router
- replayや既知解答のPへの混入
- task / game / level identityによるselector
- source / hidden stateのruntime使用
- Pのruntime無監査自己更新
- HDSを迂回したP更新・action放出
- 学習データ件数・parameter数を能力証明にすること
- sample完全攻略前の公式接続
- Kaggle提出経路の前倒し実行

## 12. フェーズ境界

- P0: 基盤・契約 — 完了
- P1: Layer-0実行機構・OFFLINE経路 — 完了・再分類
- P2: AGI最小三構成仕様・根本監査 — 完了
- P3: ARC3実証素材compiler — 完了
- P4: 計算主体C・P-A/P-B — 完了
- P5: 判断主体J — 完了
- P6: 記憶主体M — 完了
- P7: 二主体接続監査 — 完了
- P8: 三主体二周期循環 — 完了
- P9: 全8部分集合証明 — 完了
- P10: 全sample完全攻略 — 完了
- P11: release state固定 — 完了
- P12: pre-official AGI conformance / genericity — 完了
- P13: 公式ARC接続 — 未開始・Owner明示許可待ち
- P14〜P15: 未開始

現行順序は
`docs/roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`、
P4〜P9の完了証拠は各phase実装文書を参照します。P10/P11の凍結証拠と
P12の57/57受入証拠は各phase正本を参照します。P13以降はOwnerの
明示的phase開始指示なしに進めません。
