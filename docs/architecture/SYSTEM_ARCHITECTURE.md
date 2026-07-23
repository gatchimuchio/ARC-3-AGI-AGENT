# ARC-3 AGI Agent システムアーキテクチャ

- 版: `v0.1-restart`
- 状態: `P1_EXECUTABLE_KERNEL` complete / P2 not started
- 対象: ARC-AGI-3 汎用エージェント
- 非対象: task別解答表、replay再生器、既知問題ルータ、score最適化

## 1. 固定目的

未知のARC-AGI-3環境に対し、観測可能な情報だけから状態・仮説・候補を構成し、HDSが閉包条件を満たす行動だけを許可し、結果によって記憶と判断を更新する閉ループを実装します。

本書が定義するのは「AGIである」という形而上学的認定ではなく、ARC3に必要な最小認知エージェントの**機能責任・権限・検証境界**です。

## 2. 三主体の非対称構造

```text
                     +----------------------+
Observation -------->| Pure-LLM Compute C   |
Memory view -------->| hypothesis/proposal  |
HDS command -------->| authorized execution |
                     +----------+-----------+
                                |
                                v
                     +----------------------+
                     | HDS Judgment J       |
                     | frame / model /      |
                     | closure / authority  |
                     +----+------------+----+
                          |            |
             MEMORY_WRITE |            | EXTERNAL_EMIT
                          v            v
                 +---------------+  +----------------+
                 | Passive M     |  | Environment    |
                 | versioned     |  | adapter        |
                 | evidence state|  | action/result  |
                 +---------------+  +----------------+
```

### 2.1 Pure-LLM計算主体 `C`

責務:

- 観測の表現化
- 関係・遷移・反対仮説の計算
- 複数候補と予測効果の提案
- 記憶変更案と外部出力案の生成
- HDSが許可したwrite/emit機構の実行

禁止権限:

- 自分の提案を最終採用する
- 記憶を無断確定する
- 外部行動を無断放出する
- 最上位目的を変更する

### 2.2 HDS判断主体 `J`

唯一権限:

- 計算命令と入力範囲の発行
- 候補の採用・拒否・保留
- `PASS` / `PROBE` / `SUSPEND` / `STOP` / `ROLLBACK`
- `MEMORY_WRITE` と `EXTERNAL_EMIT` の許可
- 再観測・再計算・停止条件の決定

HDS自身は記憶を書かず、環境へ直接actionを送信しません。判断と機械的実行を分離します。

### 2.3 記憶主体 `M`

責務:

- 現行目的、状態、仮説、反証、失敗、証拠、未閉包項目の保持
- version、provenance、support、contradiction、lifecycleの保持
- rollback可能な履歴参照

操作:

```text
ADD REVISE MERGE SPLIT REPLACE INVALIDATE
DELETE REINDEX ROLLBACK ARCHIVE
```

記憶は受動状態です。HDS許可を伴う実行面以外から更新しません。

## 3. ARC-native Layer-0責任

LLM Layer-0仕様の方法論を、ARCエージェントの機能責任へ変換します。LLMの六役割をそのままARCの存在論として主張するものではありません。

| ARC責任 | 実行責務 | 除去した場合の観測可能な喪失 |
|---|---|---|
| `SYMBOL_SPACE` | frame、object、region、relation、control、action、effectを安定記号へ変換 | 入力状態やaction語彙を比較できない |
| `CONTEXT_STATE` | bounded episode、action/effect、仮説、失敗、budgetを保持 | 時系列条件付けが消え、同じ誤行動を反復する |
| `TRANSFORM_OR_WORLD_MODEL` | 競合する状態・遷移・因果仮説を更新 | 現在入力のlookup以上に適応できない |
| `CANDIDATE_SURFACE` | 複数action、probe、plan、reobserve、rollback、SUSPENDを提示 | 代替比較のない固定actionになる |
| `FITTING_OR_SUCCESS_CRITERION` | progress、goal、hazard、情報利得、不確実性、rollback costを評価 | 候補の採否・停止を根拠づけられない |
| `EMISSION_INTERFACE` | available action・座標・閉包許可を確認し、結果を返す | 内部計算が安全な外部行動へ接続しない |

適合条件はラベルの存在ではなく、callableな実装、状態境界、除去時の機能喪失です。

## 4. 型付き情報流

### 4.1 Observation IR

保持対象:

- frame / structural / mechanic signature
- dimensions / available actions
- entities / relations / resources
- phase hypotheses / feature tokens
- terminal state

### 4.2 Transition IR

保持対象:

- before / after signature
- action class
- visible effects
- progress / hazard evidence
- no-effect / delayed-visibility
- confidence

### 4.3 Hypothesis IR

各仮説は最低限、claim、prediction、falsification condition、support、contradiction、confidence、lifecycleを持ちます。

### 4.4 Candidate IR

候補はactionだけではなく、precondition、仮説別expected effects、progress、information gain、risk、repetition cost、rollback cost、provenance、falsifierを持ちます。

### 4.5 Closure IR

候補ごとに次を固定します。

```text
W := (X, R, Mc)
```

- `X`: 対象、現在状態、観測範囲、candidate
- `R`: precondition、予測遷移、比較、反証関係
- `Mc`: 同一性、境界、採否、停止、rollback、放出条件

`X`、`R`、`Mc` が閉じない場合、強制actionではなく `SUSPEND` または有界probeを返します。

## 5. 実行サイクル

```text
BOOT
 -> SELF_CHECK
 -> FRAME
 -> RETRIEVE
 -> COMPUTE
 -> JUDGE
    -> ACT -> OBSERVE_RESULT -> UPDATE_MEMORY -> REFRAME
    -> SUSPEND -> RECOMPUTE / REFRAME / STOP
    -> STOP
```

必須不変条件:

1. HDS commandなしに計算を開始しない
2. HDS判断なしにproposalをactionへ変換しない
3. 許可のないmemory writeを拒否する
4. 許可のないexternal emitを拒否する
5. action結果を再観測してHDSへ返す
6. hidden stateを観測事実として記録しない

## 6. 検証と停止

検証軸:

- 進捗: level増加、WIN、明示的visible progress
- 終端: `RUNNING` / `NOT_FINISHED` / `WIN` / `GAME_OVER` / `UNKNOWN`
- 危険: GAME_OVER、明示的hazard effect、不可逆失敗
- commitment: action availability、expected effect、progress commit
- provenance: 観測・推論・引用・runtime生成の分離

`NO_HAZARD_OBSERVED` は「危険が存在しない証明」ではありません。現在のrendered evidenceに危険が観測されていないという限定状態です。

## 7. Closure Phase Ψの扱い

Closure Phase Ψは内部実体として仮定せず、固定条件・反復・摂動下で残る外部signature residualとして測定します。

ARC3では例えば次を観測候補とします。

- 未観測条件での停止一貫性
- 反証後の仮説更新一貫性
- 危険境界でのaction veto
- 同型状態に対する閉包判断の保存
- task名や位置が変わっても維持される責任境界

単発成功、能力上昇、score上昇だけをClosure Phase Ψの証拠にしません。

## 8. 設計上の禁止

- 旧 `my_agent.py` のgame-ID routerを標準coreへ移植しない
- replayや既知解答をcandidate generatorへ混ぜない
- 分析artifact数を知識量・進捗の代理にしない
- 推論仮説をhidden world stateとして確定しない
- HDSをログ用ラベルや常時true gateにしない
- memoryを無制限追記ログにしない
- checkpointを環境状態の復元保証と誤認しない

## 9. P0基盤とP1独立kernel

- 本書、ロードマップ、移植台帳、参照mapが存在する
- protocol、IR、schema、verification、checkpointが独立import可能
- 単体試験が外部APIなしで決定論的に通る
- 旧runtimeが新標準経路へ未接続である
- benchmarkや汎化能力を未検証のまま主張していない

P1では、この基盤上に次を追加済みです。

- 六責任のcallable dependency
- HDS command capabilityとsingle-use consume
- Pure-LLMによる複数仮説・候補proposal
- `W=(X,R,Mc)` と十評価軸によるclosure proposal
- HDSだけが発行するwrite / emit directive
- 受動memoryとin-memory emission adapter
- full setと六つのsingle-callable removal
- repository-wide unit gateとinstallable package boundary

P1の実装境界、固定failure witness、未接続範囲は
[`P1_EXECUTABLE_KERNEL.md`](P1_EXECUTABLE_KERNEL.md)を正本とします。
