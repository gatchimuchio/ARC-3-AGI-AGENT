# P10 全タスク解析復元・能力clusterコンパイル補正

- status: `ACTIVE_AUTHORITY`
- phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- source attachment SHA-256:
  `113ac0516e500679792e57fbc73f21ad078d19929ae39c11ff185ac1f9a353ef`
- predecessor:
  `ARC3_CODEX_DEVELOPMENT_TRINITY_P_UPDATE_CORRECTION_ROADMAP.md`
- successor: P10の`183 / 183`閉包後に限りP11

## 1. 補正する開発単位

P10の開発単位を、未攻略levelごとの専用演算子から、旧全タスク解析で
抽出済みの構造・失敗signature・必要能力clusterへ切り替える。

```text
旧方式:
  未攻略levelを観測
  -> 専用Python演算子
  -> 1 level前進

現行方式:
  旧全タスク解析を関係構造付きで復元
  -> 現行rendered traceと再照合
  -> failure / mechanics / capabilityで横断集約
  -> 複数levelを閉じ得る能力候補
  -> 複数構造で反証
  -> 最後にidentity-free Runtime Pへコンパイル
```

旧成果の183行は解答集ではない。76件のlegacy boundary closure、21件の
current frontier、86件のblocked inheritance、状態変数、effect class、
失敗signature、必要能力、blockerを持つ問題空間地図である。

## 2. 三層の固定境界

### A. Legacy Evidence

P3でaccounting済みの705 analysis JSONをsource revision、path、byte数、
SHA-256で凍結する。task/game/level identity、source relation、literal座標、
過去routeは開発証拠として原資料に保持してよい。

禁止事項:

- Runtime P、runtime selector、runtime Mへ直接渡さない
- stale score、旧promotion、旧`next_*`を現行命令にしない
- replay、固定action列、source/hidden stateをruntimeへ流さない

### B. Development Analysis Memory

全183 levelを一行ずつ次の必須fieldで保持する。

```yaml
game_id:
level:
frontier:
mechanics_id:
operation_type:
state_variables:
local_effect_classes:
failure_signature:
required_capabilities:
recommended_components:
progress_blocker:
hazard_blocker:
promotion_blocker:
evidence_refs:
legacy_confidence:
current_validation_status:
```

この層はtask-awareである。IDを失う前に、同じmechanics、失敗、必要能力、
blocked inheritance、期待coverageを検索・比較できなければならない。

### C. Runtime P

B層で複数構造に成立した能力だけを次の形へ水平変換する。

- task/game/level IDなし
- 固定座標・literal座標表なし
- replay・固定action列なし
- source/hidden stateなし
- rendered observationとaction/effect historyから再導出可能
- addressable、state-dependent、composable、versioned、digestable
- HDSの採否・write・emit・promotion権限を代行しない

水平引き算は入口ではなく、このB→Cの出力境界で行う。

## 3. field単位のサルベージ規則

| field | disposition |
|---|---|
| stale score | authorityとして廃棄 |
| task/game/level identity | A/Bだけに保持 |
| replay・固定action列 | 原資料参照として隔離 |
| literal座標 | 開発証拠だけに保持 |
| mechanics ID | Bへ採用 |
| state variables | Bへ採用 |
| effect class | Bへ採用 |
| failure signature | Bへ採用 |
| required capability | Bへ採用 |
| component候補 | Bへ採用 |
| progress/hazard/promotion blocker | Bへ採用 |
| evidence reference | Bへ採用 |

stale fieldが一つあることを理由に、JSON全体の意味情報を捨ててはならない。
ただしsource drift、parse error、provenance不一致はfail closedとする。

## 4. 四つの正本

`analysis/development/`の次をP10開発分析の正本とする。

1. `LEGACY_LEVEL_ANALYSIS_LEDGER.json`
2. `ANALYSIS_RECONCILIATION_MATRIX.json`
3. `CAPABILITY_COVERAGE_MATRIX.json`
4. `CAPABILITY_BUILD_QUEUE.json`

全artifactは`development_only: true`、`runtime_use: FORBIDDEN`、
content digestを持つ。runtime moduleからのimport、lookup、routingは禁止する。

## 5. 現行再照合境界

現在保持しているactive rendered evidenceだけで183行を分類した結果:

| status | level |
|---|---:|
| `CONFIRMED` | 26 |
| `PARTIALLY_CONFIRMED` | 1 |
| `CONTRADICTED` | 0 |
| `STALE` | 9 |
| `UNOBSERVED` | 147 |
| 合計 | 183 |

`CONFIRMED`は、legacy boundary closureと現行completionが一致した範囲だけを
意味する。現行active PのHDS採用済みcompletionは35であり、legacy
`BOUNDED_SUSPEND`のまま現行で完了した9行は、旧field再検証が済むまで
`STALE`とする。旧解析の全183行を現行確認済みとは呼ばない。

## 6. coverage優先順位

能力linkは重複するため加算しない。最初のbuild queueは次で固定する。

| capability | frontier | blocked | total links |
|---|---:|---:|---:|
| C2 Visible effect transition model | 21 | 86 | 107 |
| C3 Commit boundary predictor | 19 | 78 | 97 |
| C10 Phase timer unlock model | 9 | 35 | 44 |

C2とC3のoverlapは97、unionは107 levelである。したがって最初のwork blockは
`WB-C2-C3-VISIBLE-EFFECT-COMMIT`とする。

必要な共通契約:

- rendered pre/post state abstraction
- visible local-effect classification
- positive/negative transition contrast
- progress/commit/hazard boundary prediction
- wait/reobserve/rollback obligation
- identity-free cross-context reuse

## 7. 能力候補の三段階

```text
LOCAL_PROBE
  一つまたは少数contextで機構が成立。
  action選択、active P、score採否へ影響させない。

CLUSTER_STABLE
  複数game・複数構造でpositive/negative contrastが再現。
  candidate Pの候補にできる。

COMPOSABLE
  他能力との合成、回帰、除去監査、identity-free監査が成立。
  HDSがcompileを許可できる。
```

LOCAL_PROBEやCLUSTER_STABLEをactive Pへ直接追加してはならない。
Runtime Pのcompile、promotion、rollbackは既存HDS single-use gateに従う。

## 8. 実行phase

### Phase A: 現行成果と計測基盤

- active P manifest digestを固定
- HDS採用済み35/183を固定
- game単位で独立scorecardを閉じる
- 各game完了後にatomic checkpoint
- condition digest一致時だけresume
- 25 gameをoracle互換reportへ集約

max-action、variant、lifecycle、active manifest、environment code/metadata
inventory、P10 runtime source inventory、Python、ARC Toolkit version、game集合の
いずれかが変わったcheckpointは再利用しない。

### Phase B: 旧解析復元

P3 provenanceで705 sourceを照合し、四正本を決定論的に生成する。

### Phase C: 現行agentとの突合

全183行を`CONFIRMED / PARTIALLY_CONFIRMED / CONTRADICTED / STALE /
UNOBSERVED`へ再分類する。再解析ではなく、current rendered traceによる
再検証とする。

### Phase D: 能力cluster攻略

level単位ではなくcapability cluster単位で、最低H1/H2/H3を比較する。
最初はC2+C3、その次はC10を既定優先とする。coverageだけでpromotionせず、
positive/negative contrast、hazard separator、reobserve条件を要求する。

### Phase E: Runtime P compile

COMPOSABLEだけをidentity-free candidate Pへcompileし、同一条件回帰、
除去監査、HDS promotion gateを通す。採用後は全183へ再適用する。

## 9. KA59

KA59の残り1 levelは、新しい専用operatorの開発対象にしない。

```text
multi-actor capability
+ directional-force capability
+ obligation composition
```

の合成試験とする。成立しない場合は旧KA59のstate variables、
target contact、selection delta、bottom tick、required capabilityとの差分だけを
再検証する。

## 10. 中止する作業

- 未攻略levelごとの専用Python追加
- 旧解析を匿名断片だけへ早期圧縮
- stale scoreを理由に意味fieldまで廃棄
- KA59だけの継続的深掘り
- 35/183だけの回帰
- operator数、code量、test数を能力進歩とすること
- LOCAL_PROBEをscore改善またはP promotionと呼ぶこと

## 11. 現在の実装・HDS判断

- 四正本: 実装・生成済み
- 183行再照合: 実装済み
- per-game checkpoint/resume/集約: 実装済み
- all-25 standard-budget probe: 25/25、183 level、error/fault 0
- exact-condition resume: 25 reused / 0 executed
- C2 post-action visible-effect observer: `CLUSTER_STABLE`
- C3 non-circular boundary predictor: `LOCAL_PROBE / HOLD`
- C3 leave-one-game-out: coverage 1000/1000、accuracy 748/1000
- C3 leave-one-game-out recall:
  COMMIT 0/1000、HAZARD 47/1000、TRANSITION 945/1000、
  NO_VISIBLE 0/1000
- C10 one-step visible causal-context predictor: `CLUSTER_STABLE`
- C10同一frame/actionのoutcome ambiguity: 3 game、81 group
- C10一段context separator: 80 / 81 group
- C10非循環prequential ambiguous accuracy: 291→658 / 1000
- C2 coarse outcome除去control: 658→581 / 1000
- C2+C10 composition: `COMPOSABLE`
- candidate P-A intervention:
  stable 29→29、discovery/held-out 0→0、二巡一致、error 0
- candidate P-A HDS decision: `REJECT`
- action selection influence: 0
- worker resource: 25/25 exit 0、swap 0、最大RSS 143852 KB
- local standard oracle: 35 / 183、RHAE 18.821945363%
- Runtime P変更: なし
- active P version変更: なし
- HDS:
  - LOCAL_PROBE: `PASS`
  - C2 observer CLUSTER_STABLE: `PASS`
  - C3 predictor CLUSTER_STABLE: `HOLD`
  - C2+C3 work block CLUSTER_STABLE: `HOLD`
  - C10 CLUSTER_STABLE: `PASS`
  - C2+C10 COMPOSABLE: `PASS`
  - C2+C10 Runtime intervention: `REJECT`
  - Runtime P promotion: `HOLD`
  - P10全体: `HOLD`
  - P11開始: 禁止

post-action effect、terminal、progressから再計算したboundaryはC3の予測証拠へ
数えない。C3はheld-out action前に利用可能なsource structure、action
prototype、action classだけで評価する。C10のcluster/composition PASSは
再利用可能な観測・予測契約の証拠であり、completion delta 0でREJECTされた
runtime policyの採用、score進歩、全sample攻略の証拠ではない。
