# ARC3公式サンプル汎用完遂AGI 実装仕様書 rev6

- 仕様ID: `ARC3_OFFICIAL_SAMPLE_GENERIC_COMPLETION_AGI_SPEC_REV6`
- 製品: `ARC3CompletionAgent`
- 対象: ARC Prize 2026 / ARC-AGI-3公式サンプル
- 最終成果物: 同一のC／J／M／P構造で公式25 game／183 levelを自律完遂する実行可能AGIエージェント
- ロードマップ: `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev6.md`
- Point別指示書: `docs/instructions/arc3_rev6/INDEX.md`
- 機械可読正本: `control/rev6/ROADMAP_MANIFEST.json`
- 状態: `OWNER_REDESIGN_CANDIDATE`

---

## 0. rev5.1の失効

rev5.1は製品endpointを宣言したが、実行拘束として成立しなかった。

確認済み矛盾:

```text
rev5.1 product_status = ARC3_COMPLETION_AGENT_PRODUCT_RELEASED
official public score = 0.06
required endpoint = 25/25 WIN and 183/183 complete
```

加えて、M2 Clean Run Aの参照ファイルは空であり、Full Mapping Closureには`replay-guard actions`、`public-exact-replay`、`keyboard replay signature`等の記述が残る一方、zero replayを自己申告していた。

したがってrev5.1のM2〜M4完了、`RELEASE_FROZEN`、`ARC3_COMPLETION_AGENT_PRODUCT_RELEASED`は、製品完成証拠として失効する。旧artifactは削除せず、失敗履歴としてのみ保存する。

失効正本:

`analysis/product/rev6/REV5_1_INVALIDATION.json`

---

## 1. 製品endpoint

```text
ARC3CompletionAgent
=
Official Adapter
+ C = Execute(L0, P)
+ J_hds
+ M
+ Product Runtime
+ ARC3ProductBundle
```

完成式:

```text
ARC3_PRODUCT_COMPLETE
=
ONE_PRODUCT_ARTIFACT
AND ONE_ACTIVE_PRODUCT_BUNDLE
AND CLOSED_TRINITY_C_J_M
AND J_AUTHORIZES_EVERY_EXTERNAL_ACTION
AND M_CHANGES_FUTURE_BEHAVIOR
AND NO_MANUAL_STEP_INTERVENTION
AND NO_FIXED_TRAJECTORY_PLAYBACK
AND NO_IDENTITY_ACTION_ROUTER
AND OFFICIAL_SAMPLE_25_OF_25_WIN
AND OFFICIAL_SAMPLE_183_OF_183_COMPLETE
AND CLEAN_STATE_REPEAT_PASS
```

低い公式score、Notebook実行成功、package生成、mock run、teacher replay、source-assisted local successは、上式の代替証拠にならない。

---

## 2. 作業採否原則

すべての作業は、次の少なくとも一つを直接増加させなければならない。

```text
ARC3機構理解
Pの攻略能力
Jの判断能力
Mの判断根拠
C/J/Mオンライン循環
完遂game数
完遂level数
Failure Signatureの閉包
```

次を進捗と数えない。

```text
shell
runner
class名
schema数
test数
artifact数
commit数
自己申告PASS
```

---

## 3. 固定アーキテクチャ

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
Product = Official Adapter + AGI Kernel + Product Runtime
```

### C

- 全layer表現
- entity／role／relation
- goal／mechanism hypothesis
- counter-hypothesis
- transition／effect prediction
- probe／subgoal／plan
- action／ACTION6 binding

Cは最終採否、外部action、ACTIVE M確定更新を行わない。

### J

- Purpose／Value／Risk
- `W := (X, R, Mc)`
- F／Md／Cm／U
- Gate判定
- compute request
- action／rollback／reset／memory update承認
- next question／SUSPEND／STOP

J以外の外部action経路を禁止する。

### M

- 現在のgoal／mechanism model
- entity／role binding
- support／refutation
- failed hypothesis／plan
- delayed effect attribution
- successful subplan
- level／game transfer
- open term／next question

必須操作:

`ADD / REVISE / MERGE / SPLIT / REPLACE / INVALIDATE / DELETE / ROLLBACK / ARCHIVE`

### P

Pは説明文ではなくLayer-0が実行する能力本体である。

`OBSERVE / REPRESENT / FORM_HYPOTHESIS / FORM_COUNTER_HYPOTHESIS / PREDICT / PLAN / PROBE / BIND_ACTION / VERIFY_EFFECT / ATTRIBUTE_DELAY / REQUEST_MEMORY / WAIT / ROLLBACK / RESET / STOP`

---

## 4. HDS実装契約

各Capability Closure Unitは次で閉じる。

```text
product failure or missing capability
→ F: frame／purpose／boundary
→ Md: models／counter-models／plans／probes
→ Cm: gates／selection／commit
→ product code or P/J/M capability change
→ official sample execution
→ U: attribution／M update／Failure Signature
→ result delta and regression
```

分析だけ、構造だけ、P生成だけ、testだけでUnitを終了してはならない。

必須Gate:

`G01 Open-Term / G02 Closure / G03 Impossibility / G06 Evidence / G07 Validity / G09 Projection / G10 Reversibility / G11 Temporal Attribution / G12 Resource / G14 Authority / G15 Commit`

---

## 5. 能力資産状態

一回の成功をrelease能力へ直接昇格させない。

```text
Runtime M / LOCAL_M
→ PROBATION_DEV
→ ACTIVE_DEV
→ RELEASE_FROZEN
```

- `LOCAL_M`: 単一Runの現行仮説
- `PROBATION_DEV`: 対象Caseで製品差分を出した候補
- `ACTIVE_DEV`: 独立Case、反例、回帰を通過した開発能力
- `RELEASE_FROZEN`: 全数完遂とM3適合試験を通過したrelease初期状態

---

## 6. 解析粒度

全11,574 actionへ対応するが、全一手に重い文書を作らない。

```text
Game
└ Level
   └ Phase
      └ Mechanism Segment
         └ Action Macro
            └ raw step span
```

フルHDS解析地点:

- purpose／subgoal変更
- mechanism変更
- progress／terminal
- failure／rollback
- delayed effect
- phase change
- applicability boundary

同型反復は`REPEAT / MOVE ALONG / CLICK EACH / WAIT UNTIL`へ圧縮する。

---

## 7. 汎用性境界

禁止:

```text
game_id → action sequence
level_id → action sequence
exact frame hash → next action
trajectory index → playback
successful action table
hidden answer map
```

許可:

- 現観測から抽出したentity／relation／state
- 観測条件で選択されるMechanismSpec
- parameterized mechanism
- Runtime Mで同定したcurrent game model

各MechanismSpecは`ApplicabilityPredicate`、negative condition、falsification conditionを持つ。

---

## 8. Hard Evidence Gate

### Inventory／selection Point

実装前観測を許可するが、指定された次Point入力を一つだけ作る。

### Capability analysis Point

TaskMechanismRecordと製品mappingが必要。mappingなしのanalysis artifactはprimary成果物にならない。

### Capability implementation Point

実際のproduct runtimeが能力をloadし、C／J／Mのいずれかが使用したtraceを要求する。

### Capability closure Point

公式サンプル環境で次のいずれかを要求する。

```text
game WIN delta > 0
level completion delta > 0
target Failure Signature count decreases
same failed hypothesis is no longer repeated
```

mock、synthetic world、teacher replayだけではExit不可。

### Full-sample Point

fresh process、fresh session、one bundle、25 official gamesの連続実行を要求する。

### Release Point

M2 full-sample closureとM3 conformanceを両方要求する。公式scoreがendpoint未達なら`PRODUCT_RELEASED`を宣言しない。

---

## 9. Point遷移規則

- Current Pointは`control/CURRENT_SELECTOR.json`で一意に指定する。
- 各Pointは独立指示書一ファイルを持つ。
- Point完了は対応指示書のHard Exitをすべて満たす場合だけ。
- artifact存在、digest一致、test PASSだけでは自動遷移しない。
- 一回の出力で複数Pointをまとめて完了しない。
- `auto_advance_allowed = false`。

---

## 10. 開発終了条件

本開発は、同一artifactがclean stateから公式25 game／183 levelを完遂し、C／J／M／P削除試験、記憶因果、identity／replay監査を通過した時点だけに終了する。
