# ARC3を実証基盤とするAGI最小三構成 実装・証明ロードマップ

## 0. 最上位目的

ARC3の全タスク解析データ、公式sample環境、実行ログを素材として、次の機能構造を実装する。

```text
計算主体 C
判断主体 J
記憶主体 M

AGI Kernel = Trinity(C, J, M)
```

計算主体内部は次とする。

```text
C = Execute(L0, P)
```

* `L0`：計算、参照、状態条件付け、変換、出力案生成を行う機能機構
* `P`：知識、能力、関係、変換規則、パラメータを保持する命令形情報体
* `J`：HDSフレームに基づく判断主体
* `M`：経験、現行仮説、証拠、失敗、判断根拠を保持する記憶主体

目標は、単に三部品を接続することではない。

次を実行証明する。

```text
1. C、J、Mがそれぞれ単独で固有機能を果たす
2. 各主体が他主体の責任を代行しない
3. 二主体の組合せではAGI義務が閉じない
4. C＋J＋Mで初めて全義務が閉じる
5. cycle 1の経験がcycle 2の計算または判断を変える
6. 全8部分集合を有限列挙し、full setだけがPASSする
```

これにより、定義した機能的AGIクラスに対する、

> AGI最小三構成の機能必然性および構成充足性

を実行可能証明書付きで示す。

---

## 1. 定理の定義域

本ロードマップで扱う機能的AGIは、最低限次の義務を持つシステムと定義する。

### G1：計算義務

現在観測から、内容依存で次を生成できる。

* 表現
* 関係
* 仮説
* 反対仮説
* 予測
* 候補
* 更新案
* 出力案

### G2：判断義務

目的、観測範囲、証拠、リスク、未閉包項目に基づいて次を決定できる。

* 採用
* 拒否
* 再観測
* `SUSPEND`
* `STOP`
* rollback
* 記憶更新許可
* 外部出力許可

### G3：保持義務

経験、仮説、反証、失敗、判断根拠を保持し、必要に応じて次を実行できる。

* 追加
* 修正
* 統合
* 分割
* 置換
* 無効化
* 削除
* 再索引
* rollback
* archive

### G4：時間因果義務

過去経験による記憶更新が、将来の計算または判断を実際に変える。

```text
cycle 1
→ 経験
→ M更新
→ cycle 2の入力変更
→ Cの計算またはJの判断変更
```

### G5：閉ループ義務

計算、判断、行動、結果観測、記憶更新、再判断が閉じる。

---

## 2. ARC3全タスク解析データの役割

ARC3全タスク解析データは、三主体に共通する実証素材として使う。

ただし、用途を分離する。

### C用素材

* before / after observation
* action
* rendered effect
* progress
* hazard
* terminal
* action availability
* object / relation / structure
* positive / negative contrast
* counterfactual contrast
* delayed effect
* no-effect
* contradiction

これを`P`の生成・訓練素材にする。

### J用素材

解析結果から、HDS単体試験用のFrame fixtureを生成する。

* 目的
* 対象`X`
* 関係・候補・予測`R`
* 判断・停止条件`Mc`
* 候補
* 証拠
* 反証
* リスク
* hazard
* budget
* 未閉包項目

J単体試験では、これらを直接入力し、CもMも呼ばない。

### M用素材

解析ログ・失敗ログから、記憶操作fixtureを生成する。

* 仮説追加
* 支持証拠追加
* 反証追加
* confidence更新
* contradiction蓄積
* 仮説分割
* 旧仮説無効化
* rollback
* archive
* version conflict
* provenance追跡

### provenance境界

task、game、levelの識別情報は解析証拠層には保持してよい。

ただし、runtimeのselector、候補選択、action決定には使用しない。

```text
解析層
= source identityを保持可能

実行情報体P
= identity-free

実行記憶M
= identity-freeな判断根拠

runtime policy
= task/game/level ID非依存
```

---

# フェーズ構成

## P0 — Clean Restart Foundation

状態：完了

保持するもの：

* protocol
* typed IR
* schema
* verifier
* checkpoint
* authority boundary
* migration inventory

P0は設計・責任境界の基礎として保持する。

---

## P1 — Execution Mechanism Foundation

状態：完了・再分類

P1が証明したもの：

```text
Layer-0実行責任
＋ HDS権限制御
＋ 受動memoryの暫定経路
＋ OFFLINE sample action / re-observation
```

P1が証明していないもの：

```text
C = Execute(L0, P)

HDS単独成立

記憶主体の全機能成立

AGI最小三構成

三主体の独立性

二周期因果学習
```

したがって、P1をAGI実装完了とは扱わない。

既存コードは根本監査の被監査対象および実行mechanism素材とする。

---

## P2 — AGI最小三構成仕様・根本監査

### 目的

設計上必要な全要素と、現在実装されているコード・試験を一対一で対応付ける。

### 成果物

```text
AGI_MINIMUM_THREE_SPEC.md
AGI_OBLIGATION_GRAPH.json
AGI_TRACEABILITY_MATRIX.md
AGI_CLAIM_REGISTRY.md
AGI_TEST_MATRIX.md
AGI_CURRENT_IMPLEMENTATION_AUDIT.md
```

### Traceability項目

各要素について以下を記録する。

```text
定義
必要性
入力
出力
内部状態
状態所有者
更新者
権限
実装path
呼出経路
単体試験
除去証人
代行可能性
未実装
過剰主張
```

### 監査対象

* `L0`
* `P`
* `C`
* `J`
* `M`
* environment boundary
* learning compiler
* `P0 / J0 / M0`
* external emission
* memory write
* HDS Frame
* cycle transition
* stopping
* rollback

### 完了ゲート

* 設計要素の未対応項目が全件列挙されている
* 実装されていない要素を「完成」と呼んでいない
* 主張と試験証拠が一対一で対応する
* P3以降の実装順序が監査結果から確定する

---

## P3 — ARC3実証素材コンパイラ

### 目的

全タスク解析データを、C・J・Mの単体試験および情報体生成に使える正規化素材へ変換する。

### 生成物

```text
datasets/
  observations/
  transitions/
  effects/
  hazards/
  progress/
  contradictions/
  hds_frames/
  memory_lifecycles/
  holdout_families/

manifests/
  dataset_manifest.json
  provenance_manifest.json
  identity_free_audit.json
```

### 水平引き算

次を情報体・runtime素材から除去する。

* game ID
* task ID
* level ID
* replay index
* answer map
* 固定action列
* literal座標表
* task名
* source内部状態
* ファイル名依存
* 単一ゲームだけで成立するラベル

### 分割方法

ランダム行分割だけを使用しない。

* game family holdout
* structure family holdout
* action-mechanism holdout
* layout perturbation
* color perturbation
* position perturbation

を使用する。

### 完了ゲート

* 全解析データがmanifestでaccountingされる
* identity-free corpusが生成される
* C用、J用、M用fixtureが分離される
* provenanceから元解析データへ追跡できる
* holdoutが同一問題の重複で汚染されていない

---

## P4 — 計算主体Cの単独実装

## P4-A：命令形保持体Pの形成

同一契約で交換できる二種類を作る。

### P-A：記号・規則グラフ型

保持対象：

* object
* role
* feature
* relation
* action
* effect
* transition
* precondition
* goal relevance
* hazard condition
* falsifier
* support
* contradiction
* confidence
* composition rule
* applicability selector

### P-B：パラメトリック／ニューラル型

ARC3 trajectoryから実際に学習する。

最低出力：

* action-conditioned effect prediction
* progress likelihood
* hazard likelihood
* information-gain estimate
* uncertainty
* candidate prior

候補構成：

* embedding＋MLP
* recurrent state model
* small attention
* trainable transition tensor
* rule graphとのhybrid

固定乱数、手書き重み、固定順位表は不可。

### P共通契約

```text
validate
query
digest
version
provenance
serialize
load
compile
```

### P除去・交換監査

* Pなしでcomputeを拒否
* P-AとP-Bを交換して計算結果が変わる
* L0コードを変更せず交換できる
* 同一P・同一入力で決定的
* 異なるP versionを混同しない
* PがMへ自律書込みしない

---

## P4-B：C単独試験

### 入力

* Observation
* bounded Context
* P
* compute request
* 任意の空memory view

Mは必須にしない。

Jも呼ばない。

### 出力

* hypotheses
* counter-hypotheses
* predictions
* candidates
* memory update proposals
* output proposals
* uncertainty
* provenance

### 禁止

* 候補採用
* memory確定更新
* external emit
* 自分の出力の真認定
* HDS decision生成

### 完了ゲート

* CがJ・Mなしで単独計算できる
* `C = Execute(L0, P)`のtraceが残る
* P queryが計算結果へ因果を持つ
* Cを除去すると計算義務G1が失われる
* C単独ではG2・G3・G4を満たさない
* L0六責任＋Pの除去監査が通る

---

## P5 — HDS判断主体Jの単独実装

### 目的

HDSフレームに基づき、C・Mなしで判断主体として機能することを示す。

### 入力

ARC3解析データから生成したHDS Frame fixtureを直接与える。

```text
purpose
X
R
Mc
observation boundary
candidates
predicted outcomes
evidence
counter-evidence
risk
hazard
budget
unknowns
stopping conditions
```

### 出力

* compute request
* candidate acceptance
* rejection
* reobserve
* `SUSPEND`
* `STOP`
* rollback
* memory-write authorization
* external-emit authorization

### 禁止

* 仮説生成
* candidate生成
* 記憶実書込み
* external action実行
* P参照
* M参照の必須化

### 必須試験

* `X`欠落で`SUSPEND`
* `R`欠落で`SUSPEND`
* `Mc`欠落で`SUSPEND`
* hazardでveto
* evidence不足で再観測
* budget枯渇でSTOP
* contradictionでreject
* rollback条件成立
* 同一Frameで同一判断
* Jを除去すると採否・停止・許可が不能

### 完了ゲート

* HDSがC・Mなしで単独判断できる
* HDSフレーム仕様に対する適合試験が通る
* JがCの計算を代行しない
* JがMの保持を代行しない
* J単独ではG1・G3・G4を満たさない

---

## P6 — 記憶主体Mの単独実装

### 目的

判断・計算を行わず、保持装置として必要な全機能を単独で実装する。

### 内部storage機能

* ADD
* REVISE
* MERGE
* SPLIT
* REPLACE
* INVALIDATE
* DELETE
* REINDEX
* ROLLBACK
* ARCHIVE
* READ
* QUERY
* VERSION
* SNAPSHOT
* PROVENANCE

### 保持項目

* current purpose
* current state
* hypothesis
* support
* contradiction
* failure
* evidence
* lifecycle
* unresolved item
* provenance
* version
* rollback reference

### 二種類の試験

#### storage単体試験

テストハーネスから低水準操作を直接実行し、記憶機能自体を確認する。

#### runtime権限試験

HDS許可のないmutation要求を拒否する。

### 禁止

* 自律仮説生成
* 自律判断
* 自律更新開始
* external emit
* 候補採用
* 追記専用設計

### 完了ゲート

* 全memory operationが単独で機能する
* version conflictを検出する
* rollbackで指定版へ戻る
* current stateとarchiveを分離する
* 同一queryで同一結果
* Mを除去すると周期間の経験因果が失われる
* M単独ではG1・G2・G4を満たさない

---

## P7 — 二主体接続監査

## C＋J、Mなし

成立：

* 計算
* 候補生成
* 採否
* 一周期のaction許可

不成立：

* 経験の持続
* 次周期への判断根拠継承
* 学習因果

固定failure witness：

```text
NO_PERSISTENT_EXPERIENCE_CAUSALITY
```

## C＋M、Jなし

成立：

* 計算
* memory read
* 更新案生成
* 保持機構

不成立：

* 採否
* 停止
* write許可
* emit許可

固定failure witness：

```text
NO_JUDGMENT_OR_AUTHORIZATION
```

更新案は生成できても、確定writeは拒否する。

## J＋M、Cなし

成立：

* 外部から与えられた候補への判断
* 記憶更新許可
* 判断根拠保持

不成立：

* 未知観測からの新規計算
* 仮説生成
* 候補生成
* 出力案生成

固定failure witness：

```text
NO_GENERATIVE_COMPUTATION
```

### 完了ゲート

* 三つの二者構成が固有の理由でAGI義務を満たさない
* 欠落主体を他の主体が代行しない
* pairごとのfailure witnessが重複しない

---

## P8 — 三主体Trinity循環

### 一周期試験

```text
Jがcompute commandを発行
→ CがPとObservationを計算
→ Cが仮説・候補・更新案を返す
→ Jが採否
→ JがMEMORY_WRITEまたはEXTERNAL_EMITを許可
→ Cの実行面が許可済み操作を実行
→ Mまたはenvironmentが結果を保持・返却
→ Jが結果を再評価
```

### 二周期因果試験

```text
cycle 1
→ action result
→ JがM更新を許可
→ CがMへ書込み
→ cycle 2
→ 更新済みMを引用
→ Cの仮説・候補が変化
または
→ Jの採否・停止判断が変化
```

### 因果分離試験

#### Mだけ変更

PとJ条件を固定し、Mだけ変更する。

期待：

* Cのmemory-dependent計算またはJ判断が変わる

#### Pだけ変更

JとMを固定し、P-A／P-BまたはP versionだけ変更する。

期待：

* Cの仮説・予測・候補が変わる

#### Jだけ変更

PとMを固定し、HDS Frameの目的・境界・停止条件だけ変更する。

期待：

* 採否・停止・許可が変わる

### 完了ゲート

* 三主体が固有責任を維持して循環する
* cycle 1がcycle 2へ因果を持つ
* hidden global stateで差を捏造していない
* P、J、Mの影響を個別帰属できる
* writeとemitの権限越境がない

---

## P9 — AGI最小三構成 全8部分集合監査

検査対象：

```text
{}
{C}
{J}
{M}
{C,J}
{C,M}
{J,M}
{C,J,M}
```

### 期待結果

| 構成        | 計算G1 | 判断G2 | 保持G3 | 時間因果G4 |  閉ループG5 | 総合   |
| --------- | ---: | ---: | ---: | -----: | ------: | ---- |
| `{}`      | FAIL | FAIL | FAIL |   FAIL |    FAIL | FAIL |
| `{C}`     | PASS | FAIL | FAIL |   FAIL |    FAIL | FAIL |
| `{J}`     | FAIL | PASS | FAIL |   FAIL |    FAIL | FAIL |
| `{M}`     | FAIL | FAIL | PASS |   FAIL |    FAIL | FAIL |
| `{C,J}`   | PASS | PASS | FAIL |   FAIL | PARTIAL | FAIL |
| `{C,M}`   | PASS | FAIL | PASS |   FAIL |    FAIL | FAIL |
| `{J,M}`   | FAIL | PASS | PASS |   FAIL |    FAIL | FAIL |
| `{C,J,M}` | PASS | PASS | PASS |   PASS |    PASS | PASS |

### 機能等価物監査

単にclassを`None`へするだけでは不足する。

* 他主体に同じ責任が残っていない
* fallbackが存在しない
* global functionが代行しない
* fixtureが答えを内包しない
* hidden callbackが代行しない
* metadata削除だけでFAILさせていない

ことを確認する。

### 成果物

```text
agi_minimum_three_certificate.json
agi_subset_enumeration.json
agi_removal_witnesses.json
agi_obligation_graph.json
agi_conformance_report.md
```

### 定理成立条件

```text
full_set_pass = true
proper_subset_pass_count = 0
single_removal_fail_count = 3
pair_subset_fail_count = 3
two_cycle_causality_pass = true
functional_equivalent_leak_count = 0
```

この段階で初めて、

> 定義された機能的AGIクラスは、C・J・Mまたはその機能等価物を必要とし、三主体の接続によって全義務を満たす

と主張できる。

---

## P10 — ARC3全sample完全攻略

開始条件：

* P9のAGI最小三構成証明がPASS
* C、J、Mの単体試験がPASS
* 二者接続試験がPASS
* 二周期因果試験がPASS

実施：

* ARC3全タスク解析データをP初期構成へcompile
* M初期状態をidentity-freeに構成
* HDS FrameをARC3目的へ設定
* P-A、P-B、hybridを比較
* 全sample game / 全levelを攻略
* failureをMへ蓄積
* 安定した経験を明示的compilerで次版Pへ反映

完了条件：

* 全sample level完了
* errorなし
* GAME_OVER等を解消
* 同一条件で再現
* ID・replay・answer map非依存
* M更新が未来判断へ反映
* P version更新が明示的
* 全実行traceを保存

---

## P11 — 完成状態固定

固定対象：

* code commit
* dependency
* Python version
* P format / version / digest
* J初期状態
* M初期状態 / version
* dataset manifest
* compiler version
* seed
* action budget
* regression suite
* 全sample完了証拠

```text
Release State
= P0 + J0 + M0 + code + dependency + environment
```

---

## P12 — 公式ARC環境接続

開始条件：

* P10完全攻略
* P11再現性固定

ここで初めて`COMPETITION`環境との差分を導入する。

基本AGI設計は変更しない。

---

## P13 — Kaggle提出経路

* Kaggle CLI
* Kaggle公式MCP
* 同一Notebook version
* 同一output
* 同一submission message
* secret非保存
* ユーザー明示許可前の実提出禁止

---

## P14 — 実提出・公式結果最適化

全gate完了後に実提出する。

公式評価結果は、責任構造の正否ではなく、能力・効率・汎化の追加評価として使用する。

---

# 最終順序

```text
現行実装の根本監査
↓
ARC3解析データの実証素材化
↓
C単独実装
↓
J単独実装
↓
M単独実装
↓
二主体接続監査
↓
三主体二周期循環
↓
全8部分集合監査
↓
AGI最小三構成 実行証明
↓
ARC3全sample完全攻略
↓
再現性固定
↓
公式接続
↓
Kaggle提出経路
↓
実提出
```

# 固定結論

ARC3全タスク解析データは、攻略用answer mapとして使うのではない。

```text
Cを形成する計算素材
Jを検証する判断fixture
Mを検証する記憶履歴
三主体循環を検証する環境
AGI最小三構成を証明する実証基盤
```

として使用する。

単体成立を確認せず統合しない。

二者構成の不足を確認せず三者構成を完成と呼ばない。

二周期因果を確認せず学習と呼ばない。

全8部分集合を検査せず最小三構成と主張しない。
