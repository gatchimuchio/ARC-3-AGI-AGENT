# P4 計算主体C・命令形保持体P 実装指示書

- phase: `P4_COMPUTE_SUBJECT_IMPLEMENTATION`
- state: `COMPLETE`
- predecessor: `P3_ARC3_EVIDENCE_MATERIAL_COMPILER`
- predecessor gate: `PASS`
- runtime scope: bundled official ARC-AGI-3 samples / `OperationMode.OFFLINE`
- official / competition connection: prohibited until later phase
- successor: `P5_JUDGMENT_SUBJECT_J`
- benchmark claim: none

## 0. 現状監査

P1で次は実装済みである。

- 六つのARC-native Layer-0責任のcallable実装
- HDS command、採否、SUSPEND、STOP、memory write、external emitの非対称権限
- bounded context、受動memory、OFFLINE sample adapter
- 保持済み25ゲームの1-action実行、結果再観測、次判断への状態反映
- full setと六つのsingle-callable removal audit

ただし、現在の計算経路は次である。

```text
PureLLMCompute
  -> DeterministicWorldModel.transform()
  -> DeterministicCandidateSurface.generate()
```

`roles.py`に固定された仮説、予測、候補、評価値を直接実行しており、Layer-0が参照・選択・合成・実行する独立した命令形保持体 `P` は存在しない。

したがって、現在成立しているのは次である。

```text
Layer-0 execution mechanism
+ provisional rules embedded in code
+ HDS / Memory / OFFLINE environment loop
```

現在まだ成立していないものは次である。

```text
C = Execute(L0, P)
```

既存の `InstructionBodyContract` は責任ラベルと権限境界を検証する契約であり、知識・能力・関係・変換傾向・手続きを保持する実体 `P` ではない。

P1を「純粋LLM計算主体の完成」と扱ってはならない。P1は、`P`を実行できる機械側の基礎が成立した段階である。

---

## 1. P4の目的

公式sampleから、Layer-0が実際に計算へ使用する命令形保持体 `P` を形成し、次を実装証明する。

```text
L0 = 計算・参照・変換・放出の機能機構
P  = L0が計算する知識・能力・関係・規則・パラメータの情報体
C  = Execute(L0, P)
```

P4では、単なる設定ファイル、ログ置場、辞書、候補一覧を `P` と呼んではならない。

`P`は、現在入力・文脈・記憶引用に応じて、Layer-0が内容依存で参照・選択・合成し、仮説・予測・候補生成を変化させる実行可能な情報体でなければならない。

---

## 2. `P` と `M` の分離

命令形保持体 `P` と判断根拠記憶 `M` を混同しない。

| 対象 | 所属 | 役割 | 更新境界 |
|---|---|---|---|
| `P` | Pure-LLM計算主体内部 | 知識、能力、関係、変換規則、パラメータ、候補生成傾向を保持 | explicit compile / version update |
| `M` | 独立した受動記憶主体 | 現在目的、現行仮説、経験、失敗、証拠、未閉包項目を保持 | HDS承認済みruntime update |

原則:

```text
runtime experience
  -> HDS judgment
  -> M update
  -> repeated evidence / contradiction / ablation
  -> explicit compiler
  -> new P version
```

通常の1 actionごとに `P` を自律更新してはならない。

---

## 3. 命令形保持体契約

現行 `InstructionBodyContract` を、実体 `P` を検証できる契約へ拡張する。

最低限必要な属性:

```yaml
InstructionBodyContract:
  format_id: string
  schema_version: string
  body_version: string
  content_digest: string
  addressable: true
  state_dependent: true
  composable: true
  executable_by_layer0: true
  deterministic_under_fixed_state: true
  runtime_identity_free: true
  provenance_digest: string
  input_contract: object
  state_contract: object
  output_contract: object
  compile_contract: object
```

最低限必要な実行境界:

```python
class InstructionBody:
    def validate(self) -> tuple[str, ...]: ...
    def query(self, request, observation, context, memory_view): ...
    def digest(self) -> str: ...
```

`query`結果は最終判断ではなく、Pure-LLM計算主体がHDSへ返す計算素材である。

最低限の出力:

- addressable representations
- retrieved rules / parameters
- hypotheses
- counter-hypotheses
- transition / effect predictions
- candidate priors
- uncertainty
- falsification conditions
- evidence / provenance references

---

## 4. 最初に形成する二つの情報体

Layer-0と情報体を分離できたことを証明するため、同一契約で交換可能な二種類を実装する。

### P-A: 記号・規則グラフ型

保持対象:

- object / feature / role node
- relation edge
- action / effect / transition primitive
- precondition
- goal relevance
- hazard condition
- support / contradiction
- confidence
- falsification condition
- applicability selector
- composition rule

例:

```text
OBJECT(role=controllable)
  --ACTION1-->
EFFECT(relative_motion)

RULE:
  precondition = action_available AND controllable_observed
  predicts = rendered_delta
  falsifier = repeated_no_effect
  confidence = evidence-derived
```

必要条件:

- task / game / level IDをselectorにしない
- literal answer、replay、固定action列を保持しない
- position・color・名称の摂動に耐える構造表現を優先する
- source由来の内部状態をruntime規則へ昇格しない

### P-B: パラメトリック／ニューラル型

小型で再現可能な学習済み情報体を実装する。

目的は巨大モデルの構築ではなく、同じLayer-0契約へ、規則グラフ以外の情報保持方式を接続できることの証明である。

最低出力:

- action-conditioned effect prediction
- progress likelihood
- hazard likelihood
- information-gain estimate
- uncertainty
- candidate prior

入力はidentity-freeなObservation / Context / Memory viewから構成する。

初期実装は、依存・計算量・Kaggle可搬性を考慮し、次のいずれかの小型構成でよい。

- embedding + MLP
- recurrent state model
- small attention model
- trainable matrix / tensor transition model
- 上記と記号グラフのhybrid

ただし、単なる固定乱数、手書き重み、候補順位表を「ニューラル情報体」と呼んではならない。sample trajectoryから学習され、重み・接続・活性化・出力形成が保存されることを要求する。

---

## 5. sampleからの情報体生成

保持済み公式sampleを訓練・実証環境として使用する。

### 5.1 収集する観測レコード

```text
before observation
context snapshot
memory view digest
available actions
action
rendered after observation
visible effect
progress / terminal / hazard
verification result
HDS decision
```

### 5.2 データ生成

- successful transition
- no-effect transition
- hazard / GAME_OVER transition
- delayed visibility
- stale / redraw candidate
- alternative action contrast
- counterfactual pair
- rollback / recovery boundary
- terminal / progress boundary

既知sampleのgame IDを学習入力へ入れてはならない。

### 5.3 コンパイル

```text
raw trajectory
  -> identity-free normalized transition record
  -> duplicate / literal / task-local subtraction
  -> positive / negative / hazard contrast
  -> P-A rule graph compilation
  -> P-B parameter training
  -> version bundle + digest + provenance
```

---

## 6. 現行コードの修正境界

### 6.1 `PureLLMCompute`

現状の直接依存:

```text
world_model.transform
candidate_surface.generate
```

これを次へ変更する。

```text
HDS ComputeRequest
  -> Layer0 executor
  -> InstructionBody P query / execution
  -> representation / hypothesis / prediction / candidate prior
  -> world-model / candidate executors
  -> ComputeProposal
```

`PureLLMCompute`が `P` なしで仮説・候補を生成できてはならない。

### 6.2 `roles.py`

現行の手書き仮説、固定confidence、固定候補評価値は、機構本体から除去する。

扱い:

- P-Aのseed materialへ移す
- test fixtureへ隔離する
- 明示的なfallbackとして残さない

`DeterministicWorldModel`と`DeterministicCandidateSurface`は、情報体を実行するmechanismへ縮退させる。

### 6.3 `Layer0Components`

必須依存へ追加する。

```text
instruction_body: InstructionBody
```

`None`の場合は次の固定証人で失敗する。

```text
INSTRUCTION_BODY_REMOVED_NO_EXECUTABLE_KNOWLEDGE_OR_TRANSFORM
```

---

## 7. 必須試験

### 7.1 P存在試験

- `P`なしではcomputeを拒否する
- schema不適合の`P`を拒否する
- digest / version / provenance欠落を拒否する
- task identityを含む`P`を拒否する

### 7.2 swap試験

同じLayer-0、HDS、M、観測へP-AとP-Bを差し替える。

受入条件:

- Layer-0コードを変更しない
- 両方とも同じComputeRequest / ComputeResult契約で動く
- 情報体差により予測・候補priorが変化する
- HDS権限は変化しない

### 7.3 機能試験

- 同一P / 同一入力 / 同一状態で決定的結果
- Pの規則・重みが実際に計算結果へ寄与する
- Pの一部除去で対応能力が失われる
- Pを読まない実装を検出する
- PとMの内容・version・更新経路が分離される
- M更新だけではP digestが変化しない
- explicit compiler実行時だけP versionが変化する

### 7.4 学習試験

- sample trajectoryからP-Bの重みを生成できる
- 学習前後でtransition / effect predictionが変化する
- 変化を訓練レコードと重みdigestへ追跡できる
- held-out transitionで完全な退行がない
- training dataからgame/task/level identityが除去されている

### 7.5 ablation

既存六責任に加えて、`P`除去を独立監査する。

```text
remove L0 role -> corresponding execution function loss
remove P       -> executable knowledge / transformation loss
remove M       -> experience continuity loss
remove HDS     -> acceptance / authority / stopping loss
```

---

## 8. P4完了条件

以下をすべて満たすまでP4を完了としない。

- `InstructionBody`実体と拡張contractが存在する
- P-A記号・規則グラフ型がsampleから生成される
- P-Bパラメトリック／ニューラル型がsample trajectoryから学習される
- 同じLayer-0へP-A / P-Bを交換できる
- `PureLLMCompute`がPなしで動作しない
- 仮説・候補が固定コードではなくP内容に依存する
- P / Mの更新経路とversionが分離される
- P compilerが再現可能である
- P bundleがdigest / provenance / schemaを持つ
- runtime identity-free guardが通る
- 六責任 + Pの除去監査が通る
- 保持済みsampleのOFFLINE経路でPが実際に使用される
- official API / competition / Kaggleへ接続していない

P4完了後にのみ、P5のHDS判断主体J単独実装へ進む。全sample
game / 全level攻略はP9の全8部分集合証明後、P10で開始する。

---

## 9. 非目的・禁止

- P4中の全183 level攻略完了
- 公式ARC API接続
- `OperationMode.COMPETITION`
- Kaggle Notebook / CLI / MCP / submission
- task ID、replay、answer map、literal座標によるP形成
- source / hidden stateのruntime利用
- Pを無制限にruntime自己更新すること
- HDSを迂回したP更新・action放出
- 学習データ件数やparameter数を能力証明にすること
- 小型ニューラル体の存在だけでAGI完成を主張すること

---

## 10. 最終報告形式

```text
1. 現状分類
   - P1 execution mechanism complete
   - P4 instruction body state

2. P-A
   - schema
   - rule / graph count
   - provenance
   - digest

3. P-B
   - architecture
   - parameter count
   - training records
   - training / held-out metrics
   - weight digest

4. L0 / P / M分離
   - interface
   - state owner
   - update boundary
   - swap result

5. 実行trace
   - P query
   - hypothesis / prediction
   - candidate proposal
   - HDS judgment
   - sample emission / observation

6. ablation
   - six roles
   - P removal
   - HDS removal
   - M removal

7. validation
   - commands
   - PASS / FAIL / SUSPEND
   - unexecuted items

8. remaining gaps
   - sample solving
   - learning quality
   - portability
   - official connection
```

結果が不足する場合は、`P4 complete`と書かず、未完了または`SUSPEND`とする。

---

## 11. 完了証拠（2026-07-23）

HDS判断: `PASS`

### P-A

- format: `symbolic-rule-graph`
- version: `p-a-symbolic-v1`
- graph: 21 nodes / 7 edges / 7 action rules
- content digest:
  `sha256-decimal:061467752463442905112848972582770278545407933726140802225436193305820092171858`
- bundle SHA-256:
  `feca68b67e80f0325a79d5f35be0adbf2ce749066abd1c503ba1a619b112171f`

### P-B

- format: `parametric-sigmoid-matrix`
- version: `p-b-parametric-v1`
- architecture: 12 identity-free features × 6 sigmoid heads
- parameter: 72 / 72 non-zero trained weights
- examples: train 5,018 / validation 312 / holdout 405
- BCE: train `0.693147181 -> 0.220763586`
- BCE: validation `0.227625351`
- BCE: holdout `0.693147181 -> 0.238558444`
- content digest:
  `sha256-decimal:063748466360764868803781633776294754303076777578612338993158639053037752827320`
- bundle SHA-256:
  `5ecc09d9a23dc0fadb56d7fbcc7e8328b02157c34bd1f286fd3398541d2d43cd`

### 分離・実行証拠

- `InstructionBody`共通interfaceだけでP-A/P-Bを交換し、同一入力では各々決定的、
  P差によってprediction/proposalが変化した。
- `roles.py`はPが返した仮説・prediction・controlを実行するmechanismへ縮退し、
  固定仮説・固定candidate metric fallbackを除去した。
- standalone Cはhypothesis、counter-hypothesis、prediction、candidate、
  memory proposal、output proposal、uncertainty、provenanceを生成するが、採否、
  write、emitを行わない。
- M更新後もP version/digestは不変で、P更新はseed 0のexplicit compilerだけに
  分離した。
- L0六責任、P、Cの8 single-removalはすべて固有witnessでFAILし、代行0件。
- 25/25 OFFLINE sampleの全cycleにP-A body/query digestが存在し、error 0。

### 実行検証

- `compileall`: PASS
- `unittest discover tests/unit`: 89 PASS
- `pytest tests/unit`: 143 PASS
- strict mypy: 19 source PASS
- ruff: PASS
- integration: 2 PASS
- `sample_main.py --all-samples --max-actions 1`: 25/25 complete、error 0
- P compiler Windows/Linux改行差を除去し、3 bundle artifactのbyte rebuild: PASS

P4はsample攻略・汎化・standalone J/M・最小三構成を主張しない。次phaseはP5。
