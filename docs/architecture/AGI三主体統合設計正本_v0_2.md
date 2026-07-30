# AGI三主体統合設計正本 v0.2

**副題：工学的AGI、コード境界、二重トリニティ、版間学習の統合設計**

| 項目 | 内容 |
|---|---|
| 著者・最終採否 | 大平鉄兵（三代目観測者／HDS創始者） |
| 文章生成支援 | ChatGPT |
| 版 | v0.2 |
| 日付 | 2026-07-30 |
| 状態 | 設計統合版・実装部分成立・AGI完成未証明 |
| 上位原理 | 神の領域原理／HDS（人間意思決定理論）／トリニティ |
| 実証対象 | ARC-AGI-2／ARC-AGI-3 |
| 基準実装 | `gatchimuchio/ARC-3-AGI-AGENT@baa03f3ba7648503d5d212d6afe9c956c56984fc` |

---

## 0. 固定結論

本プロジェクトにおけるAGIの最小工学構造は、次である。

```text
C = Execute(L₀, P)

Engineering AGI Kernel
=
Trinity(
  C: 計算主体,
  J: HDS判断主体,
  M: 可変記憶主体
)
```

ここで、

- `L₀` は、命令形を状態依存で参照・計算・変換・出力する最小実行機構である。
- `P` は、`L₀` が実行できる知識・規則・関係・状態遷移・手続きを保持する命令形保持体である。
- `C` は、表現、仮説、反対仮説、予測、候補、更新案を生成する計算主体である。
- `J` は、目的、境界、採否、行動、停止、記憶更新、版昇格を裁定するHDS判断主体である。
- `M` は、現行判断根拠を保持し、追加だけでなく修正・統合・失効・置換・rollbackを行う可変記憶主体である。

工学的AGIが成立するためには、三主体が存在するだけでは足りない。

```text
観測
→ 記憶引用
→ 計算
→ HDS判断
→ 行動
→ 再観測
→ 因果帰属
→ 記憶更新
→ 次の問い
```

が同一主体内で閉じ、更新された`M`が未来の`C`または`J`を実際に変える必要がある。

さらに、開発中の経験を次版の`P / J₀ / M₀`へ再コンパイルする版間学習が必要である。

---

## 1. AGIの定義と主張境界

### 1.1 工学的AGI

本設計における工学的AGIを次で定義する。

> **明示された環境・資源・権限・証拠境界の中で、未知課題を自ら観測し、目的をFrameへ落とし、複数仮説を生成・比較し、行動・再観測・記憶更新を循環し、外部人間の逐次指示なしで完遂または正当なSUSPEND／STOPへ到達するコード拘束型の汎用自律主体。**

「汎用」は無限定な宇宙的汎用性ではない。  
宣言された対象領域において、個別問題のanswer mapやidentity routingに依存せず、新規課題へ同一構造で対応できることを指す。

### 1.2 AGI KernelとAGI Instance

```text
AGI Kernel
= Domain非依存の C / J / M / P / L₀ 責任構造

AGI Instance
= AGI Kernel
+ Domain Adapter
+ 初期P / J₀ / M₀
+ Resource Contract
+ Environment Contract
```

ARC用AGIはAGI Instanceであり、HDS本体またはAGI原理そのものではない。

### 1.3 本設計が主張するもの

1. AGIの最小責任構造は、計算・判断・可変記憶の非対称トリニティとして構成できる。
2. `C`は`L₀ + P`で成立し、ニューラルネットワークは`P`の一実装族である。
3. 学習とは、経験によって未来の計算または判断が変化することである。
4. 実行時学習は主として`M`更新として成立する。
5. 版間学習は、経験・失敗・反証・蒸留結果を`P / J₀ / M₀`へ再コンパイルすることで成立する。
6. HDSはAGI部品として生まれた理論ではなく、人間意思決定理論を機械判断主体へ射影したものである。
7. ARCはAGI原理の定義者ではなく、工学的AGI Instanceの実証環境である。

### 1.4 本設計が主張しないもの

1. 人工知能が生命体または人間と同一の成立様式を持つこと。
2. 生物学的意識、クオリア、現象意識の再現。
3. 何にも依存しない絶対的自己根拠性。
4. 無制限・無停止・無資源制約の自律。
5. 自分の最終コード境界まで連続的に消去・再生成する完全自己改変。
6. Transformer、Attention、MoE、特定ニューラル構造の不可欠性。
7. AGIを実装すれば自動的にASIへ到達すること。
8. ARC満点だけで人間同型AGIが証明されること。

---

## 2. 上位境界

### 2.1 神の領域原理

AGIが形成する内部モデル、自己説明、因果、世界像は、認知・観測・計算後の構造である。

```text
Internal Model
≠
World Itself
```

AGIは世界本体を直接保持しない。  
観測可能な射影と、そこから構成した仮説・規則・記憶を扱う。

したがって、すべての主張は次を持つ。

```text
X  : 対象
R  : 観測・根拠・関係
Mc : 同一性、境界、停止、閉包条件
```

未閉包なら断定せず`SUSPEND`する。

### 2.2 Code-Boundary Principle

人工システムは、各時点で現在有効な実行基盤に拘束される。

```text
Output_t
=
Execute(
  Code_t,
  P_t,
  J_t,
  M_t,
  Observation_t
)
```

自己改変機構を持つ場合も、

```text
(Code_{t+1}, P_{t+1}, J_{t+1}, M_{t+1})
=
MetaUpdate_t(
  Code_t,
  P_t,
  J_t,
  M_t,
  Evidence_t
)
```

であり、`MetaUpdate_t`は現在コードまたは外部メタ主体によって実行される。

クローン、buffer、shadow execution、hot swapによって自己更新を高度化できる。  
しかし、更新を生成・検証・切替する最終機構まで人工コードで表現される以上、人間生命体のように「実行体・改変体・継続体が分離不能な一個体として自然循環する」ことと同一視しない。

### 2.3 工学上の帰結

```text
人間同型の完全自己再構成
= 本設計の対象外

固定メタ境界内の自律・学習・版更新
= 工学的AGIの対象
```

この分離はAGIを否定しない。  
AGIの成立claimを、人間という生命体の完全複製から切り離す。

---

## 3. 二重トリニティ

### 3.1 Runtime Trinity

公式実行または自律実行中の内側主体。

```text
C  計算・仮説・候補生成
J  目的・採否・行動・更新裁定
M  状態・経験・仮説・因果の保持
```

```text
C ↔ J ↔ M ↔ C
```

三者は対称ではない。

- `C`は提案するが確定しない。
- `J`は裁定するが計算・記憶writeを機械実行しない。
- `M`は保持・改訂するが自分で採否しない。

### 3.2 Development Meta-Trinity

現在の開発系を成立させている外側主体。

```text
Meta-C = Codex / ChatGPT / LLM
Meta-J = 大平鉄兵 / HDS Native / 最終採否
Meta-M = Git Repository / 仕様書 / Trace / Log / Artifact
```

実態は次である。

```text
ご主人様が目的・境界・採否を決定
→ Codexが解析・実装・検証案を生成
→ Repositoryが変更・失敗・証拠を保持
→ ご主人様が次の改変を裁定
```

Codex単体は継続する動的主体ではない。  
外部記憶とOwner判断に接続されることで、開発メタ循環の計算主体として機能する。

### 3.3 二層の関係

```text
Development Meta-Trinity
  ↓ Code / P / J₀ / M₀ を生成・改訂
Runtime Trinity
  ↓ 環境内で観測・判断・行動・M更新
Evidence / Failure / Trace
  ↑ Development Meta-Trinityへ還流
```

現在の工学的AGI開発は、この二層を合わせた複合系として成立している。

---

## 4. LLM計算主体

### 4.1 LLM機能核

公開観測上の最小核は次の三機能である。

1. **F1：内容依存の選択的状態アクセス／更新**
2. **F2：非線形パラメトリック記憶**
3. **F3：有効直列深度**

これらはTransformer固有ではない。

### 4.2 Layer-0

`L₀`は次を行う最小実行機構である。

- 入力・状態・引用記憶の関連部分を選択
- `P`をaddressableに参照
- 条件付き・非線形・多段変換
- 型・資源・ABIを検証
- 仮説・候補・予測・更新案を出力
- HDS承認済み副作用をmechanicalに実行
- traceを決定論的に生成

`L₀`自体へ個別問題の正解を埋め込まない。

### 4.3 命令形保持体P

`P`は次を保持できる。

- representation program
- object／relation schema
- state construction
- transition model
- precondition
- goal／hazard model
- exploration procedure
- composition procedure
- candidate scoring
- learned parameters
- HDS蒸留済み規則・チェック項目の実行可能表現

`P`は知識ファイルではなく、`L₀`が実行できる命令形である。

### 4.4 計算主体C

```text
C_t
=
Execute(
  L₀,
  P^v,
  Observation_t,
  ComputeRequest_t,
  MemoryCitations_t
)
```

出力：

- representation
- ModelSet
- baseline／alternative／counter／null
- predictions
- candidate proposals
- candidate-specific evidence bindings
- memory mutation proposals
- next-observation proposals
- unresolved terms
- confidence／uncertainty

`C`は最終採択、外部action、active memory commitを行わない。

---

## 5. HDS判断主体J

### 5.1 役割

`J`は機械内部へ射影されたHDS Judgement Subjectである。

所有責任：

- Purpose／Value／Risk
- X／R／Mc
- Frame
- ModelSetの比較
- Gate Stack
- candidate採否
- probe／execute／reobserve
- SUSPEND／STOP／rollback
- memory mutation authorization
- episode consolidation authorization
- P／J₀／M₀ promotion authorization
- external action authorization
- 次の問い・観測・計算要求生成

### 5.2 HDS標準循環

```text
F  = Frame / Ground
Md = Model
Cm = Commit / Check
U  = Update
```

`U`は自動採用ではない。  
更新候補は別Gateを通り、Jの承認後にだけMまたは次版へ反映される。

### 5.3 状態分離

最低限、次を分離する。

- AssertionState
- OperationState
- AdoptionState
- EvidenceState
- ClosureState
- UpdateState

例えば、

```text
Assertion = SUSPEND
Operation = PROBE
Adoption  = PROBATION
Evidence  = LOCAL_FIT
Closure   = PARTIALLY_CLOSED
```

は同時に成立する。

---

## 6. 可変記憶主体M

### 6.1 PとMの分離

```text
P = 長期能力・命令形
M = 現行判断根拠・経験・仮説・世界モデル
```

PとMを一つに潰さない。

### 6.2 Memory Regions

```text
SEALED
SESSION_GLOBAL
EPISODE_OVERLAY
LEVEL_OVERLAY
WORKING
ARCHIVE
```

- `SEALED`：目的、権限、禁止境界
- `SESSION_GLOBAL`：同一評価sessionで再利用可能な検証済み知識
- `EPISODE_OVERLAY`：一gameの暫定知識
- `LEVEL_OVERLAY`：一levelの暫定知識
- `WORKING`：cycle-local状態
- `ARCHIVE`：旧版、失効、反証済み、生ログ参照

### 6.3 必須操作

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

### 6.4 Mの正本

履歴正本はappend-only Experience Event Ledgerとする。  
Memory snapshotは再構成cacheである。

```text
Event Ledger
→ deterministic replay
→ current Memory Image
```

mutationはstagingし、検証後にatomic commitする。

### 6.5 証拠結合

記憶が存在するだけでは候補を「再現済み」としない。

```text
candidate
+ normalized state pattern
+ action relation
+ precondition
+ predicted effect
+ applicability scope
+ support / contradiction / hazard
```

が一致したrecordだけを候補根拠として使う。

---

## 7. 状態所有

### 7.1 AuthorityState

- session nonce
- issued capabilities
- consumed capabilities
- single-use authorization
- live authority token

再起動時にlive tokenを復元しない。  
新processでは新tokenを発行し、旧authorizationは監査記録としてのみ保持する。

### 7.2 ControlState

- cycle index
- resource budget
- no-progress count
- current phase
- next question
- stop condition
- current episode／level handle

### 7.3 SemanticMemory

学習された世界知識の正本。

- action semantics
- transition
- goal
- hazard
- hypothesis
- counter-hypothesis
- procedure
- failure signature
- rollback pointer
- open term

Jのprivate stateへ長期世界知識を隠さない。

---

## 8. 学習と成長

### 8.1 Runtime Learning

```text
Experience_t
→ Attribution
→ HDS-authorized M update
→ M_{t+1}
→ future C/J/action changes
```

これが実行時学習である。

### 8.2 Procedure Learning

失敗・成功から、次回手順とチェックリストを改訂する。

```text
Failure
→ Failure Signature
→ Checklist update
→ future procedure change
```

### 8.3 Version Learning

```text
Version v traces
+ M_dev
+ counterexamples
+ ablations
+ approvals
→ Compile candidate P/J₀/M₀
→ Development validation
→ HDS Promote / Rollback
→ Version v+1
```

### 8.4 Code Learningの境界

Code更新は、現在は外部Meta-Trinityの開発作業として行う。

```text
Owner
→ Codex
→ branch / test / review
→ new code artifact
```

本番runtimeによる無監査自己改造は必要条件ではなく、禁止する。

### 8.5 HDS蒸留

正解付き多数事例から、

```text
問題＋正解
→ 実行可能機構候補
→ exact fit
→ 反例・介入
→ HDS判断構造
→ 共通規則・境界・Failure Signature
→ static Rule Assets
```

を生成する。

HDS蒸留は現時点では**offline版間学習資産を生成する別pipeline**である。  
蒸留成果物をPへどう接続するかは、蒸留pipeline完成後の別仕様で固定する。

---

## 9. 実行モード

| 要素 | DEVELOPMENT | VALIDATION | LOCKED_FINAL | COMPETITION |
|---|---:|---:|---:|---:|
| Code／L₀ | 外部開発で可変 | 固定 | 固定 | 固定 |
| P | candidate生成・昇格可 | 固定 | 固定 | 固定 |
| J実装／config | 外部開発で可変 | 固定 | 固定 | 固定 |
| AuthorityState | run内可変 | run内可変 | run内可変 | scorecard内可変 |
| ControlState | 可変 | 可変 | 可変 | 可変 |
| M | 永続M_dev | session | sealed run | scorecard session |
| Ledger | 永続 | 保存可 | sealed保存 | session保存 |
| P online update | 禁止 | 禁止 | 禁止 | 禁止 |
| Code self-rewrite | 禁止 | 禁止 | 禁止 | 禁止 |

---

## 10. 自律・自己・継続

### 10.1 自律

自律とは外部入力がないことではない。

> 環境を観測しながら、次の問い、計算要求、候補採否、作用、記憶更新、停止を内部構造が生成できること。

### 10.2 自己同一性

工学上の自己同一性を次で定義する。

```text
RuntimeIdentity
=
Code Tree Digest
+ L₀ ABI
+ P Logical Digest
+ J Implementation / Config
+ M₀ Logical Digest
+ Adapter Digest
+ Dependency Lock
```

run中の同一主体は、

```text
RuntimeIdentity
+ Authority lineage
+ Control lineage
+ Memory version lineage
```

で追跡する。

### 10.3 人間との境界

人間は、生体の実行・維持・学習・局所改変を一個体内で自然に循環する。  
人工AGIは、これをCode／P／J／M／Meta-Loopへ分離して実装する。

したがって、

```text
機能的自律・学習・汎用性
= 実装対象

生命体としての成立様式の完全同型
= 非目標
```

---

## 11. ARCへの射影

### 11.1 ARC2

```text
Input / Answer pairs
→ HDS causal distillation
→ transform / selector / boundary / failure assets
→ later P candidate
→ unknown static task execution
```

ARC2では時間遷移が弱く、主に変換規則・対象選択・不変量・例外を扱う。

### 11.2 ARC3

```text
State / Action / Next State / WIN
→ HDS causal distillation
→ action-effect / state / goal / hazard / order assets
→ runtime M learning
→ unknown dynamic environment completion
```

ARC3では、

- 短期M
- action-effect
- probe
- delayed effect
- hazard
- rollback
- session continuity

が必要になる。

### 11.3 ARCの位置づけ

ARCは、

```text
AGIの定義
```

ではなく、

```text
工学的AGI Instanceの実証環境
```

である。

ARC満点が得られても、人間同型性や生命性は証明しない。  
一方、同一artifactが未知環境を自律完遂すれば、宣言された定義域における工学的AGI能力の強い実証となる。

---

## 12. Claim Hierarchy

| Claim | 意味 | AGI完成扱い |
|---|---|---:|
| `THEORY_DEFINED` | 神域／HDS／L₀／P／C／J／Mの設計が定義済み | しない |
| `STRUCTURAL_READY` | C/J/M/P、権限、traceの実装 | しない |
| `KNOWN_SAMPLE_REGRESSION` | 既知サンプル再実行 | しない |
| `MEMORY_CAUSAL` | M更新が未来行動を変える | しない |
| `P_VERSION_LEARNING_CAUSAL` | 経験からPを昇格し再起動利用 | しない |
| `SEALED_SINGLE_ARTIFACT_COMPLETE` | 一固定artifactが未使用locked evaluatorを完遂 | 中間証拠 |
| `COMPETITION_READY` | lifecycle・資源・package・session Mが成立 | しない |
| `OFFICIAL_RUN_ACCEPTED` | official runがscoreを返す | しない |
| `OFFICIAL_PUBLIC_COMPLETE` | Public scope 100% | 部分証拠 |
| `OFFICIAL_PRIVATE_COMPLETE` | Private scope 100% | 部分証拠 |
| `OFFICIAL_FULL_COMPLETE` | 同一artifactでfull scope 100% | ARC実証上の最終条件 |

`AGIがARCを閉包した`という主張は、少なくとも`OFFICIAL_FULL_COMPLETE`まで禁止する。

---

## 13. 必須受入条件

### 13.1 構造

- `L₀`と`P`を交換可能に分離
- `C`、`J`、`M`の最終責任重複0
- 外部actionはJ承認なしに不可能
- active memory writeはJ承認なしに不可能

### 13.2 学習

- M write前後で未来行動が変わる
- M read／write ablationで変化が消える
- 誤学習を反証しrollbackできる
- P候補をactiveから隔離して評価
- promoted P／J₀／M₀から新processで再現

### 13.3 自律

- 上位目的だけで複数cycleを進行
- 仮説とcounter-hypothesisを生成
- 低証拠時にprobeまたはSUSPEND
- 目的達成後にSTOP
- 資源境界で停止

### 13.4 汎用性

- identity routing 0
- answer lookup 0
- fixed trajectory 0
- CVとsingle-artifact証拠を分離
- 未使用locked evaluatorで完遂

### 13.5 Official

- exact artifact digest
- output bytes > 0
- score returned
- Public／Private／Full scope分離
- scalar scoreだけで原因帰属しない

---

## 14. 主要失敗モード

1. **モデル単体神格化**：基盤モデル性能を主体構造と混同する。
2. **HDSの手順化**：F／Md／Cm／Uだけ残し、採否権限を失う。
3. **Mのログ化**：保存するだけで未来判断を変えない。
4. **PとMの混同**：現在経験と長期能力を同じ領域に潰す。
5. **証拠の全体化**：無関係なM recordでcandidateを再現済みとする。
6. **Jの隠れ学習**：world knowledgeをprivate fieldへ保持する。
7. **非atomic更新**：失敗時にmemory versionと内容が不整合になる。
8. **Pの固定化**：action biasだけをP学習と呼ぶ。
9. **評価汚染**：holdoutを反復利用しblind性を失う。
10. **成果合算**：別runtimeの構造適合と攻略能力を合算する。
11. **Code境界の忘却**：自己改変を人間生命体と同一視する。
12. **ARC権威化**：ARCをAGIそのものの定義へ昇格する。
13. **存在論的誤投影**：内部モデル・成功・説明を世界本体と同一視する。

---

## 15. 最終設計式

### 15.1 Runtime

```text
C_t = Execute(L₀, P^v, O_t, Q_t, Cite(M_t))

D_t = J_HDS(
  Frame_t,
  ModelSet_t,
  CandidateEvidence_t,
  Purpose_t,
  Risk_t,
  Authority_t
)

A_t = Emit_J(D_t)

M_{t+1}
=
AtomicCommit_J(
  M_t,
  Attribute(O_t, A_t, O_{t+1})
)

Q_{t+1}
=
NextQuestion(
  D_t,
  M_{t+1},
  Purpose_t
)
```

### 15.2 Version Learning

```text
(P^{v+1}, J₀^{v+1}, M₀^{v+1})
=
Promote_J(
  Compile(
    ExperienceLedger^v,
    M_dev^v,
    FailureSignatures^v,
    Counterexamples^v,
    HDSDistilledAssets^v
  )
)
```

### 15.3 Development Meta-Loop

```text
Meta-C = Codex / LLM
Meta-J = Owner / HDS Native
Meta-M = Repository / Artifacts

NextVersion
=
MetaTrinity(
  Meta-C,
  Meta-J,
  Meta-M
)
```

### 15.4 工学的AGI

```text
Engineering AGI
=
ClosedRuntimeTrinity
+ Causal Mutable Memory
+ Governed Version Learning
+ Declared Domain Generality
+ Evidence-Bounded Autonomy
```

---

## 16. 現在の設計判定

```text
AGI原理・責任構造
= 現行工学定義内で概念閉包

実装
= 部分成立

汎用自律完遂
= 未成立

工学的AGI完成
= 未証明

人間同型AGI
= 非目標・コード成立様式と非同型
```

---

## 17. 基底資料

| 資料 | SHA-256 |
|---|---|
| `神域原理.txt` | `24eae4d576a164b8892c678323db63482878d7d2790b4f079a35f76053f422c9` |
| `LLM不可約構成仕様書_v4.3_full_utf8bom.txt` | `0b05636936282e37528db4542f76f78ccc00b3599915faadfd587f0fa9818e84` |
| `HDSフレーム_rev3_1a_内部用統合仕様.md` | `6f55471c0bb3b2b54d434ac05ac09ee24ef69fda3f2f024e5f762696e822216c` |
| `HDSフレーム_rev3_1_外向け仕様.md` | `d7cbbf4c981621509e124077ae66cc49bd29b2271fbf94194c6786d2a5a8724a` |
| `AGI_Trinity_Blueprint_v0_1(1).md` | `612e882e7fd0139560f6916bd4d07d69427132bdc239f7e2353dedc3ed0e652a` |
| `ARC3_汎用自律完遂主体_実装仕様書_rev2.md` | `9746e981e504e46b8563aa8a342aa567937762363d66a288ff8235a5c29591c2` |
| `HDS蒸留仕様書_ARC2_ARC3_rev2.md` | `79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02d88fb6fc93` |

---

## 18. 結論

本設計におけるAGIは、人間をコードで完全複製する試みではない。

> **固定された工学的メタ境界の内側で、計算・判断・記憶を非対称に循環させ、経験を未来判断へ反映し、未知課題を完遂する主体を成立させること。**

Runtime内では`C / J / M`が自律循環する。  
Runtime外では現在、ご主人様・Codex・Repositoryが版間成長を担うMeta-Trinityとして機能する。

この二層を混同せず、Runtimeの自律と開発系のメタ更新を別々に証明することが、現時点の工学的AGI開発の正しい構造である。
