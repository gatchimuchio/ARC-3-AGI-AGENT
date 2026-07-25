# ARC3 Codex開発Trinity・命令形保持体P更新

# 統合運用指示書兼P10補正ロードマップ

## 0. 最上位目的

本指示書の目的は、次の二つを同時に閉じることである。

```text
A. ARC3 AGI内部の学習循環
B. ARC3 AGIを開発するCodex自身の認知・改善循環
```

内側のAGI構造：

```text
C_runtime = Execute(L0, P_runtime)

AGI_runtime
= Trinity(C_runtime, J_runtime, M_runtime)
```

外側の開発構造：

```text
C_dev = Codexの検索・分析・実装・試験能力
J_dev = 開発用HDS判断
M_dev = 開発判断根拠・仮説・失敗・証拠の保持
P_dev = Codexが従うARC3開発方法論

Development System
= Trinity(C_dev, J_dev, M_dev)
```

外側のTrinityが、内側のTrinityを実装・監査・更新する。

## 0.1 P10現行補正

P10の攻略単位と水平引き算境界は、
[`P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`](P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md)
を正本とする。

```text
Legacy Evidence
-> task-aware Development Analysis Memory
-> capability cluster candidate
-> LOCAL_PROBE
-> CLUSTER_STABLE
-> COMPOSABLE
-> identity-free Runtime P
```

旧解析のidentity・関係を入口で捨てず、Runtime Pへの出力時だけ除去する。
未攻略levelごとの専用Python追加と、operator数を進歩とする運用を停止する。

---

# 1. 固定された主体分離

## 1.1 Runtime側

### `P_runtime`

計算主体が使用する情報体。

保持対象：

* 知識
* 能力
* 関係
* 規則
* semantic operator
* weight
* parameter
* candidate prior
* transform
* applicability
* falsification condition

### `M_runtime`

現在の経験と判断根拠を保持する。

保持対象：

* 現在状態
* 仮説
* 支持
* 反証
* failure
* unresolved item
* transition evidence
* rollback reference
* lifecycle
* provenance

```text
M_runtimeの更新
≠
P_runtimeの更新
```

一回の経験は原則としてMへ入れる。

複数の証拠によって安定した能力・規則・parameterだけを、明示的compilerによって次版Pへ昇格する。

---

## 1.2 Codex開発側

### `M_dev`

Codexが作業中に保持する判断根拠。

* 現在の最上位目的
* 現在phase
* 成立済み能力
* 未成立能力
* active仮説
* rejected仮説
* failure signature
* 実験結果
* 既知の禁止経路
* unresolved構造
* 再開条件
* evidence path
* commit／artifact digest

### `P_dev`

Codex自身が従う開発方法論。

* HDS運用手順
* Trinity運用手順
* 情報選別規則
* 仮説生成規則
* 仮説比較軸
* bounded experimentの作り方
* failure圧縮方法
* 汎用能力と局所patchの判別方法
* 記憶更新方法
* 方法論昇格条件
* rollback条件
* phase遷移条件

一回の成功や失敗を、直ちに`P_dev`へ追加してはならない。

```text
一回の経験
→ M_dev

複数条件で再現した方法
→ P_dev候補

監査・反証試験を通過
→ P_dev次版
```

---

# 2. Codexの必須開発循環

Codexは、単なる「実装要求→コード→テスト」の直線処理を禁止する。

すべてのwork blockで次を実行する。

## Stage 1：SELF_CHECK

開始時に確認する。

```text
現在のユーザー指示
現在phase
現在HEAD
dirty差分
現行P_runtime
現行J_runtime
現行M_runtime
成立済み能力
未成立能力
直近failure
禁止入力
停止条件
```

不整合があれば実装せず`SUSPEND`する。

---

## Stage 2：FRAME

今回の作業を次で固定する。

```text
X:
  観測対象
  変更対象
  使用する証拠
  使用しない証拠

R:
  仮説
  予測
  比較対象
  期待する状態遷移
  反証関係

Mc:
  同一性
  境界
  採用条件
  停止条件
  rollback条件
  完了条件
```

加えて必ず固定する。

```text
非目的
証拠境界
反証条件
回帰線
最大作業範囲
```

---

## Stage 3：RETRIEVE

`M_dev`および既存解析資産から、今回に関係する情報だけを抽出する。

最低限取得するもの：

* 同型failure
* 既存仮説
* 棄却済み仮説
* 関連task family
* 関連semantic operator
* 既存Pの適用範囲
* regression対象
* 未閉包証拠

関連しない解析ファイルを大量に読むことを、深い調査と見なしてはならない。

---

## Stage 4：COMPUTE

Codexは最低三種類の候補を生成する。

```text
H1: 直接的な能力追加
H2: 観測・表現・モデルの修正
H3: 既存能力の再構成・合成
```

必要に応じて追加する。

```text
H4: 現在仮説の反対仮説
H5: 実装せず追加観測する案
H6: SUSPEND／ROLLBACK
```

各候補に必ず付与する。

* 予測される効果
* 適用範囲
* 必要証拠
* falsifier
* 実装費用
* rollback費用
* 汎用性
* 情報利得
* contamination risk
* 既存能力への回帰risk

---

## Stage 5：JUDGE

`J_dev`は次の順序で候補を評価する。

```text
1. 最上位目的への接続
2. 証拠の強度
3. 汎用性
4. 情報利得
5. 可逆性
6. 回帰risk
7. 実装費用
8. 局所patch化risk
```

出力は次のいずれかに限定する。

```text
PASS
PROBE
HOLD
SUSPEND
REJECT
ROLLBACK
STOP
```

候補が一つしかないことを理由に採用してはならない。

---

## Stage 6：BOUNDED ACT

採択した仮説に対し、最小の反証可能実験を実装する。

原則：

* 変更範囲を限定する
* 既存Pを直接破壊しない
* candidate Pまたは隔離componentとして作る
* 同一条件baselineを残す
* failureを握り潰さない
* 新しいfallbackを暗黙追加しない
* task ID／replay／固定列を使用しない

---

## Stage 7：OBSERVE

予測と実測を比較する。

```text
予測した変化
実際の変化
変化しなかったもの
新たに壊れたもの
未観測のもの
```

スコア上昇だけで仮説を採用しない。

実装量、テスト数、commit数を能力向上の代理にしない。

---

## Stage 8：UPDATE M_dev

work block終了時、必ず次を更新する。

```text
採用仮説
棄却仮説
failure signature
得られた証拠
残った反証条件
次の再開条件
関連artifact
適用範囲
非適用範囲
```

`M_dev`は無制限追記ログにしない。

古い仮説は、

```text
ACTIVE
SUSPENDED
SUPERSEDED
REJECTED
ARCHIVED
```

へ状態遷移させる。

---

## Stage 9：UPDATE P_dev CANDIDATE

同じ方法論が複数の異なる構造で有効だった場合だけ、`P_dev`更新候補を生成する。

昇格条件：

* 異なるtask familyで再現
* 同一failure signatureへ複数回有効
* 適用条件が言語化可能
* falsifierが存在
* 旧方法より明確に優位
* 既存方法と責任重複しない
* regressionを増やさない

満たさない場合は`M_dev`に留める。

---

# 3. Runtime P更新ライフサイクル

## 3.1 P更新の基本循環

```text
P_t
↓
C_runtimeが計算
↓
J_runtimeが採否
↓
環境結果
↓
J_runtimeがM更新を許可
↓
M_{t+1}へ経験・反証・failureを保持
↓
C_runtimeまたはcompilerがΔP候補を生成
↓
J_runtimeがP更新候補の作成を許可
↓
P_candidate_{t+1}をcompile / train
↓
新旧Pを同一条件比較
↓
J_runtimeがPROMOTE / HOLD / REJECT / ROLLBACK
↓
P_{t+1}をactive化
```

Pをその場で破壊的更新しない。

常に、

```text
active P
candidate P
previous stable P
```

を分離する。

---

## 3.2 必須データ型

最低限、次を実装する。

```text
PUpdateProposal
PUpdateEvidenceSet
PUpdateDecision
InstructionBodyCompileDirective
CandidatePBundle
PRegressionReport
PPromotionDirective
PPromotionReceipt
PRollbackDirective
```

### `PUpdateProposal`

保持対象：

* source P version
* target component
* update type
* evidence refs
* expected effect
* expected affected capabilities
* expected unaffected capabilities
* falsifier
* rollback target
* provenance

### `PUpdateDecision`

HDSだけが生成する。

状態：

```text
PROBE
COMPILE
HOLD
REJECT
PROMOTE
ROLLBACK
```

---

## 3.3 P-A更新

更新対象：

* rule
* relation
* semantic operator
* applicability
* confidence
* support
* contradiction
* composition
* candidate prior

必要条件：

* 現在frameから適用条件を再導出できる
* task IDに依存しない
* operator単体試験がある
* 同型構造で再利用できる
* falsifierがある
* 旧Pとの比較がある

---

## 3.4 P-B更新

P-Bはversion番号だけを変えてはならない。

実際に次を更新する。

* weight
* bias
* embedding
* transition parameter
* feature mapping
* head parameter

必須証拠：

```text
parameter_digest(P_t)
!= parameter_digest(P_{t+1})
```

さらに、

```text
C(P_t, same_input)
!= C(P_{t+1}, same_input)
```

となり、差が更新対象に帰属しなければならない。

P-B更新用datasetは、

* Mから抽出した承認済み経験
* failure
* contradiction
* positive／negative contrast
* holdout
* replay禁止監査

から作る。

---

## 3.5 P昇格gate

candidate Pは次をすべて通過した場合だけactive化する。

1. schema／digest／provenance PASS
2. identity-free PASS
3. deterministic rebuild PASS
4. target能力の改善
5. 既存安定能力の非回帰
6. holdoutでbaseline未満に悪化しない
7. catastrophic forgettingが許容範囲内
8. HDS権限境界を迂回しない
9. 同一条件で再現
10. rollback可能

一項目でも未閉包なら`HOLD`または`REJECT`。

---

# 4. P更新とM更新の時間軸

## 即時適応

一つのepisode内の変化は原則としてMに保持する。

```text
M_working_t
→ M_working_{t+1}
```

対象：

* current-world transition
* failure location
* temporary prior
* current plan
* current hazard
* unresolved relation

## 安定学習

複数episode・複数構造で成立した経験をPへcompileする。

```text
P_stable_vN
→ P_candidate_vN+1
→ regression
→ HDS PROMOTE
→ P_stable_vN+1
```

MをPの代用にしてはならない。

Pを毎action無条件更新してはならない。

---

# 5. Codex用の管理成果物

Codexは最低限、次の論理成果物を管理する。

```text
CURRENT_FRAME
ACTIVE_HYPOTHESES
REJECTED_HYPOTHESES
CAPABILITY_REGISTRY
FAILURE_SIGNATURE_REGISTRY
EXPERIMENT_REGISTRY
DEV_MEMORY
DEV_METHOD_BODY
P_UPDATE_REGISTRY
DECISION_LOG
```

推奨内容：

## `CURRENT_FRAME`

今回の`X / R / Mc`と停止条件。

## `ACTIVE_HYPOTHESES`

競合仮説、予測、falsifier、状態。

## `CAPABILITY_REGISTRY`

* 実装済み能力
* active P version
* 適用構造
* 非適用構造
* removal witness
* regression対象

## `FAILURE_SIGNATURE_REGISTRY`

failureをゲーム名ではなく構造で記録する。

例：

```text
rendered relation incomplete
history phase missing
goal identity unresolved
action effect underdetermined
hazard recovery unavailable
candidate surface collapsed
```

## `DEV_METHOD_BODY`

複数条件で再現したCodex運用方法だけを保持する。

---

# 6. P10補正ロードマップ

## P10-A：現行baseline固定

* 現行active P
* M初期状態
* HDS Frame
* stable完了level
* failure evidence
* regression command
* artifact digest
* game単位checkpoint
* exact-condition resume
* oracle互換25 game report集約

を固定する。

---

## P10-B：Codex開発Trinity導入

Codexの全work blockへ、

```text
FRAME
RETRIEVE
COMPUTE
JUDGE
BOUNDED ACT
OBSERVE
UPDATE M_dev
P_dev昇格判定
```

を導入する。

完了条件：

* 仮説が最低三案存在
* 採否理由が残る
* failureが再利用可能なsignatureになる
* 次work blockが最大情報利得から決まる
* 同じ棄却経路を無目的に再試行しない

---

## P10-C：Runtime P更新契約

* PUpdateProposal
* PUpdateDecision
* compile directive
* promotion
* rollback

を実装する。

HDSに次の明示権限を追加する。

```text
allow_p_compile
allow_p_promote
allow_p_rollback
```

---

## P10-D：P-B再学習経路

Mから承認済み経験datasetを生成し、P-B weightを再学習する。

完了条件：

* parameter digestが変化
* target能力が変化
* holdout非悪化
* deterministic rebuild
* predecessor追跡
* previous stable Pへrollback可能

---

## P10-E：P-A／hybrid更新経路

semantic operatorを、直接コードへ追加して終わらせない。

```text
evidence
→ operator candidate
→ isolated implementation
→ regression
→ P bundle compile
→ HDS promotion
```

としてactive Pへ入れる。

---

## P10-F：閉ループP更新実証

最低一つの未攻略構造について、

```text
failure
→ M更新
→ ΔP生成
→ HDS compile許可
→ candidate P
→ regression
→ HDS promotion
→ 次回攻略結果変化
```

を一貫したtraceで証明する。

---

## P10-G：反復攻略

各未攻略levelではなく、coverage順の能力clusterについて次を繰り返す。

```text
全183再照合
→ mechanics / failure / required capabilityの横断cluster
→ coverage queue
→ 競合仮説
→ LOCAL_PROBE
→ 複数gameでCLUSTER_STABLE反証
→ 他能力とのCOMPOSABLE試験
→ identity-free candidate P
→ HDS昇格／棄却
→ 全183 regression
```

183/183まで、局所patchではなく能力単位で閉じる。

---

# 7. 絶対禁止

Codexは次を行ってはならない。

* 最初の実装案を自動採用する
* 一つの仮説だけで作業する
* task ID patchを能力と呼ぶ
* failureを単なるerror logへ落とす
* Mを無制限追記する
* P versionだけ変えて更新と呼ぶ
* weightが同一のP-Bを学習済み次版と呼ぶ
* 手書きoperator追加だけを自律学習と呼ぶ
* HDS承認なしにactive Pを変更する
* candidate Pの失敗時に旧Pを上書きする
* テスト未実行をPASSとする
* score上昇だけで汎用能力と認定する
* ユーザー指示なしにphaseを進める
* ユーザー指示なしにGit操作を行う

---

# 8. Codexの終了報告形式

各work block終了時、次を報告する。

```text
1. 現在Frame
2. 取得したM_dev
3. 生成した仮説一覧
4. J_devの採否
5. 実行したbounded experiment
6. 予測と実測
7. 更新したM_dev
8. P_dev更新候補の有無
9. P_runtime更新候補の有無
10. regression結果
11. HDS判断
12. 次の最大情報利得点
13. Git状態
```

---

# 9. 完了定義

本補正が完了したと言えるのは、次をすべて満たした場合だけである。

```text
Codex自身がHDS／Trinityフローで作業する

Codexの経験がM_devへ保持される

再現した方法だけがP_devへ昇格する

runtime経験がM_runtimeへ保持される

M_runtimeからP更新候補が作られる

HDSがP更新・昇格・rollbackを制御する

P-Bのparameterが実際に更新される

P更新が未来のC計算を変える

既存能力の非回帰が確認される

P更新失敗時に旧安定版へ戻れる
```

この状態で初めて、

```text
開発主体も学習循環する
かつ
実装対象AGIも学習循環する
```

という二重Trinityが成立する。
