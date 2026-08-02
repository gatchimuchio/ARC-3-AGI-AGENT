# ARC3 Completion AGI Agent 製品開発ロードマップ rev4

- Roadmap ID: `ARC3_COMPLETION_AGENT_PRODUCT_ROADMAP_REV4`
- 製品: `ARC3CompletionAgent`
- 上位仕様: `docs/strategy/ARC3_AGIエージェント_製品仕様書_rev4.md`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 日付: `2026-08-02`
- 状態: `OWNER_PRODUCT_DIRECTIVE_INSTALLED`
- 現在milestone: `M5_PRODUCT_CLOSURE_AND_PACKAGING`

---

## 0. エンドポイントからの逆算

```text
DONE
25/25 official sample games = WIN
183/183 levels = COMPLETE
one ARC3CompletionAgent artifact
        ↑
M5 Product Closure / Packaging
        ↑
M4 Full-Sample Repair Loop
        ↑
M3 Integrated AGI Capability
        ↑
M2 Product Capability Bundle
        ↑
M1 Official Product Runtime
        ↑
M0 Current Product Baseline / Blocking Defects
```

HDS分析、教師軌道分解、構造抽出、P生成はM2〜M4で使う能力構築workstreamであり、独立した最終endpointではない。

各milestoneは必ず実行可能なagent artifactと、公式サンプル上の実測結果を出す。

---

# M0 — PRODUCT BASELINE AND BLOCKER CLOSURE

## 目的

現在の`GenericAGIAgent`／`GenericAGIRuntime`を製品候補として公式サンプルへ接続し、能力以前の完遂不能条件を除去する。

## 現状確認済み

```text
official sample games       = 25
official sample levels      = 183
teacher canonical actions   = 11,574
max known actions per game  = 1,519
legacy generic budget       = 128
current product budget      = 4096
teacher max no-progress run = 644
product no-progress limit   = 650
current competition P       = HybridRelationalInstructionBody()
default P-IR                = compatibility_p_ir_program()
```

## 実装

1. `ARC3CompletionAgent`を製品entrypointとして固定する。
   - 現行`GenericAGIAgent`を継承・改名・統合してよい。
   - 開発と公式packageで同じproduct pathを使う。
2. 公式サンプル25 gameを実行するblocking acceptance runnerを作る。
3. action budgetを開発時4096へ変更し、設定可能にする。
4. HDS `resource_budget`／`stop_after_no_progress`とproduct budgetを整合させる。
5. 1 game failureで全scorecard／全batchを失わないreportを維持する。
6. 現行agentを全25 gameへ実行し、baselineを保存する。
7. failureを製品責任へ分類する。

## Primary Output

```text
ARC-AGI-3-Agents/agents/templates/arc3_completion_agent.py
ARC-AGI-3-Agents/arc3_agi_agent/product_runner.py
analysis/product/rev4/current_product_baseline.json
```

## Blocking Acceptance

```text
25 games started
25 games produce a terminal or bounded product report
0 budget-impossible games
0 adapter crashes
0 scorecard lifecycle leaks
one product path
```

このmilestoneでは25/25 WINを要求しない。製品を正しく測定でき、能力差分が結果へ反映される状態を作る。

## Exit

`PRODUCT_BASELINE_EXECUTABLE`

---

# M1 — OFFICIAL PRODUCT RUNTIME

## 目的

公式FrameData／GameActionを、AGIが必要な情報を失わずC／J／Mへ接続する。

## 実装

### Observation Model

- 一手内の全camera render frame
- action完了時の最終composited view
- action frame間のtemporal relation
- temporal frame history
- animation／complete-action区別
- progress／terminal／full reset
- legal action surface／payload schema
- UI／board／background候補

### Action Model

- RESET
- ACTION1〜ACTION5
- ACTION6の一般座標候補
- ACTION7
- one HDS-authorized external action per cycle

### Session Model

- one CognitiveSession per product run
- one episode per game
- level境界の明示
- episode M／game M／cross-game Mの責任分離
- product traceとfailure log

## Product Increment

```text
ARC3CompletionAgent v0.2
```

全25 gameで観測・候補生成・J authorization・一手実行・再観測が成立する。複数action frameを持つ初期観測を含め、情報縮退を起こさない。

## Acceptance

- all 25 initial frames parse
- all observed action-frame counts preserved
- all legal actions represented
- ACTION6 candidate space includes objects, cells, regions, boundaries, paths, UI candidates
- terminal／level progress transitions correct
- every action passes J authority

## Exit

`OFFICIAL_RUNTIME_SURFACE_COMPLETE`

実測証拠: `analysis/product/rev4/m1_official_runtime_surface.json`

```text
25 / 25 initial frames inspected
183 total win-level contract
normal actions 1..7 and RESET control 0 represented
ACTION6 seven spatial affordance categories represented
25 / 25 selected emissions consumed J authorization
25 / 25 external actions executed and reobserved
identity / descriptor failure 0
```

---

# M2 — PRODUCT CAPABILITY BUNDLE

## 目的

PH-D05教師素材とHDS解析を、製品が直接実行する`P／J0／M0`へ変換する。

## Workstream A — HDS Task Interpretation

成功軌道とframe差分を、次へ解釈する。

```text
purpose
entity / role / relation
state
precondition
operation
effect / delayed effect
goal / hazard
order / composition
probe / rollback
applicability boundary
```

これはanalysis完成を目的としない。Product Bundleへコンパイルするために必要な粒度だけ作る。

## Workstream B — P Compilation

次の命令能力をPへ実装する。

- temporal action-frame／final-composite representation
- task/mechanism hypothesis generation
- counter-hypothesis generation
- action-effect prediction
- goal/hazard prediction
- subgoal／plan generation
- probe selection
- effect verification
- failure update

現行`HybridRelationalInstructionBody`と`compatibility_p_ir_program()`を製品bundleへ置換する。

## Workstream C — J0

ARC3 HDS Domain Profileを構築する。

- reversible probe
- delayed effect wait
- game-over veto
- no-effect handling
- level reset
- unresolved next question
- resource／loop control

## Workstream D — M0

- action semantics
- transferable structure families
- known failure signatures
- probe patterns
- evidence requirements
- boundaries

answer map／fixed trajectoryは格納しない。

## Product Increment

```text
ARC3CompletionAgent v0.3
+ ARC3ProductBundle v1
```

## Acceptance

- product loads compiled P/J0/M0
- P removal materially reduces capability
- product behavior differs from generic exploration baseline
- teacher-derived structure is cited in C output
- no game-ID action router
- no trajectory playback path
- at least one official game completes end-to-end through the product AGI loop

## Exit

`PRODUCT_CAPABILITY_BUNDLE_ACTIVE`

実績（2026-08-02）:

- `ARC3ProductBundle v1`を製品entrypointへruntime identity付きで結合
- FT09を75 action、6/6 level、`WIN`で完遂
- 同一J0／M0・128 actionのP除去対照は0/6、`NOT_FINISHED`
- M2受入14 gate PASS、証拠は`analysis/product/rev4/m2_product_capability_bundle.json`

---

# M3 — INTEGRATED AGI CAPABILITY

## 目的

静的能力bundleだけでなく、未知の現在状態に対してAGI三主体がオンライン同定・計画・更新する製品を完成させる。

## 実装

### C

- multiple representations
- mechanism hypotheses
- counter-hypotheses
- state transition predictions
- bounded multi-step plans
- probe plans
- target／coordinate bindings

### J

- purpose／closure frame
- model competition
- evidence／risk／resource gates
- execute／probe／recompute／wait／rollback／reset／stop
- memory update decision
- next question generation

### M

- support／refutation
- current mechanism replacement
- delayed effect attribution
- failed plan invalidation
- successful subplan retention
- level／game consolidation
- cross-game transfer with applicability

## Product Increment

```text
ARC3CompletionAgent v0.4
```

## Acceptance

- relevant M mutation changes future candidate／plan／action
- irrelevant M mutation leaves action invariant
- failed hypothesis is not repeated indefinitely
- product generates its own next probe／question
- rollback／reset produces a revised plan
- C/J/M/P deletion tests fail as predicted
- official sample completed game／level count improves over v0.3

## Exit

`AGI_CLOSED_LOOP_CAPABILITY_ACTIVE`

実績（2026-08-03）:

- 全actionへの複数representation・競合仮説・subgoal・4-step plan結合
- 10,733/10,733 actionでC planとJ commitが一致
- 失敗帰属12、rollback plan 42、失敗仮説無効化478、rollback後replan 42
- relevant M causality／irrelevant M invariance／C-J-M-P deletion回帰PASS

---

# M4 — FULL-SAMPLE REPAIR LOOP

## 目的

同一製品を全25 game／183 levelへ繰り返し実行し、残存failureをHDSで責任分解して最小修正する。

## 循環

```text
RUN PRODUCT
→ observe product failure
→ HDS classify responsibility
→ patch C / J / M / P / Adapter / Resource
→ run regression
→ run full sample again
```

## Failure Classes

```text
ADAPTER_ERROR
RESOURCE_ERROR
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
```

## 修正原則

- failureを新しい管理phaseで包まない
- 最小責任部品を修正する
- 既に完遂したgame／levelのregressionを守る
- game固有parameterは観測からbindingする
- fixed answer replayへ退行しない

## Product Increment

```text
ARC3CompletionAgent v0.5 ... v1.0
```

## Progressive Gates

```text
G1  25/25 games start, no product crash
G2  first complete game
G3  all action-surface families complete at least one level
G4  50% levels complete
G5  90% levels complete
G6  183/183 levels complete
G7  25/25 games WIN
```

## Exit

`OFFICIAL_SAMPLE_PRODUCT_COMPLETE`

実績（2026-08-03）:

```text
25 / 25 games WIN
183 / 183 levels complete
10,733 actions
runtime failure signature 0
adapter / lifecycle failure 0
one shared CognitiveSession
```

正本証拠: `analysis/product/rev4/m4_full_sample_product.json`

---

# M5 — PRODUCT CLOSURE AND PACKAGING

## 目的

M4で全数完遂した同一製品artifactを再現可能にpackageし、公式実行経路へ載せる。

## 実装

- freeze ARC3ProductBundle
- freeze code／dependencies／resource config
- build wheel／package
- local clean-environment install
- official sample rerun
- Kaggle Notebook／entrypoint
- placeholder／output contract
- sequential scorecard lifecycle
- submission transport

## Acceptance

```text
same product artifact
clean install PASS
25/25 sample WIN after clean install
183/183 complete after clean install
package digest reproducible
normal Kaggle run complete
submission accepted or platform failure isolated
```

公式platform failureは製品failureと分離する。ただし製品完成claimはclean-environment公式サンプル全数完遂を必要とする。

## Exit

`ARC3_COMPLETION_AGENT_PRODUCT_RELEASED`

Local closure実績（2026-08-03）:

- implementation commit `9e7657281bc31ee4dd97a09bde7e96b567631166`
- wheel SHA-256 `0557c3cbc1fbaf295a25351aad62c9349cdcfdb5fdc5bce669edffdfc4de55de`
- 別clean archive間でwheel／MANIFEST byte一致
- fresh Python 3.12.13 venvへ通常install、`pip check` PASS
- installed wheelで25/25 `WIN`、183/183、10,733 action
- M4とclean-install runの25行機能結果が完全一致
- P／J0／M0 logical identity一致
- Kaggle Notebook local validation 25/25 PASS、secret 0、submission API call 0

正本証拠:

- `analysis/product/rev4/m5_clean_install_product.json`
- `analysis/product/rev4/m5_product_release.json`

外部Kaggle normal runは未実行であり、Ownerの現在の明示授権まで`ARC3_COMPLETION_AGENT_PRODUCT_RELEASED`はclaimしない。

---

## 1. 現在作業

```text
M5_PRODUCT_CLOSURE_AND_PACKAGING
```

ローカルproduct closureは完了した。現在の作業境界は、Ownerの現在の明示授権を得た後の外部Kaggle normal runのみである。授権なしにNotebook upload、run、submissionを実行しない。

---

## 2. 運用規則

- 新repositoryを作らない。
- 全作業は本repositoryの製品pathへ統合する。
- 全milestoneはrunnable productを出す。
- reportだけ、schemaだけ、evidenceだけのmilestoneを作らない。
- Owner承認は製品仕様変更、product bundle freeze、公式提出に限定する。
- 内部実装・試験・修正は連続実行する。
- 進捗はcompleted games／levelsとfailure減少で評価する。
