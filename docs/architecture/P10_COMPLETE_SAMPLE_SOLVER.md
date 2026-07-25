# P10 ARC3全sample攻略・実装監査

- phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- state: `IN_PROGRESS`
- predecessor: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`
- successor: `P11_RELEASE_STATE_FREEZE`
- operation mode: `OFFLINE` only
- HDS judgment: `HOLD`

## 1. Work-block FrameSpec

```text
X:
  保持済み25 sample / 183 levelのrendered observation、available action、
  bounded context、identity-free P、受動M、HDS Frame、OFFLINE adapter

R:
  HDS command
  -> Cがrendered sceneとHDS承認済みMを計算
  -> Jが候補を採否
  -> capability-bound external emit
  -> result再観測
  -> J再判断
  -> 許可済みM更新またはrollback
  -> 次cycleの計算・判断変更

Mc:
  183/183、error 0、GAME_OVER 0、timeout 0、無限loop 0、
  max-action停止0、同一条件再実行一致、runtime identity leak 0、
  M因果あり、明示的P version更新、全trace保存でPASS

non-goals:
  公式API、COMPETITION、Kaggle、submission、P11凍結

evidence boundary:
  sourceは解析・反証専用
  runtimeはrendered observation、available action、action/effect history、
  identity-free P/Mだけを使用

falsification:
  ID/replay/fixed action/answer/literal coordinate/source/hidden-state routing、
  capabilityなしRESET、失敗握り潰し、未完了を全攻略と表記

regression:
  P0〜P9 unit / integration / certificate、strict mypy、ruff、compileall
```

## 1.1 現行三層開発境界

P10の現行開発単位は、個別level operatorではなくcapability clusterである。

```text
A Legacy Evidence
  705 analysis JSONをpath / SHA-256 / revisionで凍結
  identity、level関係、source参照を開発証拠として保持

B Development Analysis Memory
  25 game / 183 levelをmechanics、state、effect、failure、
  capability、blocker、current statusで検索可能に保持

C Runtime P
  COMPOSABLEまで反証された能力だけをidentity-freeへcompile
```

四正本は[`analysis/development`](../../analysis/development)に置く。すべて
`development_only`かつ`runtime_use: FORBIDDEN`であり、active runtimeから
importしない。詳細は
[`P10全タスク能力cluster補正`](../roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md)
を参照する。

現行active evidenceとの再照合は次である。

| status | count |
|---|---:|
| `CONFIRMED` | 26 |
| `PARTIALLY_CONFIRMED` | 1 |
| `CONTRADICTED` | 0 |
| `STALE` | 9 |
| `UNOBSERVED` | 147 |

35 completionは維持するが、旧bounded-suspendのまま現行で完了した9行は、
旧field再検証まで`STALE`とする。

## 2. 現在の実装ブロック

`arc3_agi_agent/visual_explorer.py`は、rendered gridから同色連結成分、
status候補、単純action、観測由来click候補を形成し、遷移・無変化・hazardを
versioned payloadへ直列化する。game/task/level IDを入力に取らない。

`arc3_agi_agent/p10_compute.py`はP1 kernelを変更せず、HDS commandの配下で
最新の承認済みMを読み、P10候補とM更新案を生成する。cycle 1のMにより
cycle 2の候補actionが変わることを単体試験で固定している。

`arc3_agi_agent/p10_instruction_compiler.py`は、P4 predecessorからP-A、
P-B、hybridをseed 0で決定論的にcompileする。意味演算子のdetector、
transform、parameter、precondition、falsifierはP-A/hybridだけに入り、
P-Bからは除去される。P交換時はinstruction digestを照合し、旧P由来queue、
transition model、constraint stateを無効化する。

`arc3_agi_agent/semantic_operators.py`は、rendered relation tile latticeを
GF(2)または循環差分で解く演算子と、rendered target/controlの作用対応を
一手再観測、transition graph、coordinate descent、permutation modelで
学習する演算子を持つ。`arc3_agi_agent/selectable_push.py`は、paired
border object、enclosing target ring、intervening barrierを現在のrendered
gridから検出し、selection pointと方向別移動回数をgeometryから導出する。
曖昧なrole、非整列delta、必要action欠落時はplanを返さない。

`arc3_agi_agent/symbolic_rewrite.py`はbordered symbol、connector、source/
output row、selectorをrenderから検出する。fixed rewriteを直接適用し、
editable ruleは各visible nodeのcycleを観測した後、有界constraintとして
解く。三演算子ともgame/task/level ID、source、hidden state、固定座標を
受け取らず、内部stateはversioned passive M payloadへ直列化される。

`arc3_agi_agent/fruit_merge.py`は、rendered interfaceから要求rank/actor、
playfieldからfruit/actor/targetを再検出する。要求対象へのroute、同rankの
接近・merge、actor回避を一手ごとに再観測し、surface消失時はHDS経路の
undo候補と失敗clickを受動Mへ保持する。固定route、level番号、既知座標は
入力に取らない。この能力はv14で9 / 9の同条件再現と既存20 level非回帰を
経てactive化された。

`arc3_agi_agent/recovery.py`とOFFLINE adapterは、観測済みGAME_OVERに対して
HDSがrollback Frameを判断し、single-use capabilityを発行した場合だけ、
Pure-LLM executorによるM rollback、failure保持、RESET、再観測を許す。
偽造directiveと二重RESETは拒否する。

`arc3_agi_agent/search_reset.py`はGAME_OVER recoveryと分離されている。
現在branchから未試行frontierへ到達できず、初期rendered state側にだけ
frontierが残ることをCが証拠化し、HDSがFrameを閉じた場合だけ、Mを保持して
環境RESETを1回実行する。RESETごとに新しいsingle-use capabilityを要求する。

`agents/templates/p10_sample_agent.py`と`p10_main.py`は、通常actionとRESETの
双方を上記権限境界だけから実行し、full trace、P digest、M version、
rollback decision、完了数をreportする。

`arc3_agi_agent/p10_batch_checkpoint.py`はmax-actions、P variant/lifecycle、
active manifest digest、environment code/metadata inventory、P10 runtime
source inventory、Python、ARC Toolkit version、game集合を一つのcondition
digestへ束縛する。各gameを独立scorecardで実行してatomic checkpointを閉じ、
完全一致した条件だけをresumeし、local oracle互換scorecardへ集約する。

`arc3_agi_agent/cross_cutting_transition.py`はC2/C3の横断候補である。rendered
pre/post stateを、no-change、local/regional/global redraw、component
motion/appear/disappear、action-surface change、progress、hazardへ分類し、
commit/hazard/transition-only/no-visible-commitを分離する。現時点では
`LOCAL_PROBE`のshadow telemetryであり、action選択、M write、external emit、
P promotionへ一切影響しない。

作業Mは同一targetへ毎cycle追加しない。初回はHDSが`ADD`、後続は観測時の
active targetを確認して`REPLACE`を許可する。version/historyは維持しつつ、
current snapshotの重複増大を防ぎ、各cycleのtraceはreport側へ残す。

## 3. 現在の実測境界

P10実行経路の関連unit、strict mypy、ruff gateは通過している。現行hybrid
`p10-hybrid-v26`、instruction compiler
`arc3-p10-instruction-compiler-v26`、semantic planner
`arc3-semantic-planner-v11`、visual operator
`arc3-p10-visual-operator-v13`、OFFLINE、seed 0のstable regression実測は
次のとおりである。

| rendered mechanism | 完了 | actions | M影響cycle | recovery | reset | 終端 |
|---|---:|---:|---:|---:|---:|---|
| relation-toggle | 6 / 6 | 75 | 69 | 0 | 0 | `WIN` |
| object-target control | 8 / 8 | 235 | 188 | 0 | 0 | `WIN` |
| symbolic rewrite | 6 / 6 | 308 | 284 | 0 | 0 | `WIN` |
| goal-aware equal-rank merge | 9 / 9 | 175 | 証拠内 | 0 | 0 | `WIN` |
| selectable-object target push | 1 / 7 | 64 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |
| selectable multi-object route | 2 / 7 | 96 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |
| marker shape-target push | 3 / 7 | 192 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |
| multi-actor shape-target push | 4 / 7 | 192 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |
| occluded-target route | 5 / 7 | 192 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |
| directional-force multi-obligation route | 6 / 7 | 200 | 証拠内 | 0 | 0 | `MAX_ACTION_STOP` |

最初の四blockはerror 0、GAME_OVER 0、max-action停止なしである。
v16 selectable-object target pushは、previous stableの0 / 7に対してcandidateが
1 / 7を同条件で二回再現し、既存29 levelを同じactionsで維持した。v17では
marker-centered object表現、released-marker位相、bounded push-route search、
queued-action再観測を合成し、previous activeの1 / 7に対してcandidateが
2 / 7を96 actionsで二回再現した。既存29 levelの完了数とactionsは不変だった。
HDSは全十promotion gateを確認して`p10-hybrid-v22`をACTIVEへ昇格した。
v18ではclosed-outline interior、filled-shape family、bounded actor-mediated
impulse push、dynamic footer除外、transient queue advancementを合成して
target 2→3を再現し、`p10-hybrid-v23`へ昇格した。v19ではmultiple marker
actor、selected index、観測由来click、recursive actor-mediated pushを合成し、
target 3→4を二回再現して`p10-hybrid-v24`へ昇格した。v20では三つの
intact sideと外側occluderに覆われた一つのmissing runからtargetを再構成し、
occluder normalへ垂直に進入するbounded routeと、一時的なtarget edge
unavailabilityで既emit actionを一つだけ進めるqueue検証を合成した。target
4→5を二回再現して`p10-hybrid-v25`へ昇格した。v21ではrendered charge band
から方向と位相を復元し、通常移動regionとforce portal、shape/actorの二義務を
段階化したbounded routeを構成した。未選択marker roleを早期fail-closeし、
search-state上限を2,000へ固定した上でtarget 5→6を二回再現して
`p10-hybrid-v26`へ昇格した。各更新は既存29 levelを維持し、
post-promotion v21 active runは6 / 7、200 actions、error 0だった。
`MAX_ACTION_STOP`で残り1 target levelは未閉包である。現時点の
HDS採用済み境界は`35 / 183`、残りは`148 level`。これは十の
意味演算子blockの限定証拠で、
全sample攻略証拠またはfull local-oracle scoreではない。

previous stable PでのSU15 bounded runは、4 / 9 levelを160 actionsまでに
完了した後、level 5で`MAX_ACTION_STOP`となった。この失敗は
[`su15_hybrid_active_failure_compact.json`](../../evidence/p10/su15_hybrid_active_failure_compact.json)
へ保持した。v14ではrendered goal、required actor type、actor-fruit距離だけ
からterminal actor protectionを再導出し、fruit placement前にactorを安全な
anchorへ移動して四遷移を再観測する。game/task/level ID、固定座標、replayは
runtime入力に使わない。

canonical条件`OFFLINE / hybrid ACTIVE / 450 actions per game`で全25 gameを
逐次実行したが、外部commandの7200秒timeoutへ到達し、最終reportは生成
されなかった。これはagentのmax-action停止とは別の検証環境失敗であり、
部分値をfull scoreとして扱わない。次のrunはgame単位checkpointとresumeを
備えた経路で採取し、25 game / 183 levelが一つの検証済みreportへ集約される
までP10全体のHDS判断は`HOLD`、P11開始は禁止である。

checkpoint/resume実装後、`OFFLINE / hybrid ACTIVE / max-actions 1`で25 gameを
分割実行した。25/25 report、error 0、checkpoint 25件、resume時の再実行0を
確認した。C2/C3 shadow probeは25 transitionを記録し、visible transition
22、no-visible-change 3、action選択影響0だった。これは計測経路と
`LOCAL_PROBE`の証拠であり、level completion、local score、CLUSTER_STABLE、
Runtime P promotionの証拠ではない。正本は
[`C2_C3_LOCAL_PROBE_AUDIT.json`](../../evidence/p10/development/c2_c3_local_probe_all25_max1/C2_C3_LOCAL_PROBE_AUDIT.json)
である。

v15では、既知のstate-changing actionより未観測prototypeを優先する
candidate policyを五つのbounded structureで比較した。action分布は変化したが
完了levelは全て0のままだったため、semantic commit能力ではないと
`REJECT`しactive Pへ入れていない。v16では現在rendered geometryだけから
selectable object / target / barrier roleを閉じるoperatorをcandidate compileし、
target 0→1、既存29 level非回帰、同条件再実行一致を確認してHDS昇格した。
v17では、touching same-color objectをconnected componentとして扱う直接拡張を
`REJECT`し、target dimensionから導くmarker-centered templateでobjectを分離した。
selection、push可能route search、予測state付きqueue、最大8 transient frameの
再観測を一つのP演算子へcompileし、target 1→2を再現してHDS昇格した。
v18ではsingle controlled actorとfilled movable shapeを別roleとして表し、
closed outline interiorとのshape-family assignmentとbounded impulse pushを
compileした。v19ではsingle-actor detectorの直接緩和を`REJECT`し、multiple
marker actorのselected state、rendered center click、actor-to-actor /
actor-to-shape recursive pushを一つのbounded operatorへcompileした。

FT09、action budget 256、seed 0、OFFLINEの同一条件比較:

| P variant | P version | 完了 | actions | 終端 |
|---|---|---:|---:|---|
| P-A | `p10-p-a-symbolic-v2` | 6 / 6 | 75 | `WIN` |
| P-B | `p10-p-b-parametric-v2` | 0 / 6 | 256 | `MAX_ACTION_STOP` |
| hybrid | `p10-hybrid-v1` | 6 / 6 | 75 | `WIN` |

全variantでruntime errorは0だった。P-Bではsemantic operator instructionが
0件であり、CコードとM内queueを同じままにしても能力が消失した。これは
当該能力がPの明示内容へ依存することのP10実行証拠である。

初期relation-toggleの全cycle traceを含むscorecard非依存の安定射影は
[`ft09_variant_comparison.json`](../../evidence/p10/ft09_variant_comparison.json)
へ保存した。content digestは
`8d17b068a757ececded6c4f2a7669a57319a12e3194e5c8ca1d9c956f213f473`
である。game IDは実行結果を同定するevidence fieldにだけ存在し、P、C、
M、runtime selectorへは入らない。

v14以前のstable実行は、各cycleのtrace digest、trace-event root、実emit、
provenance、level transition、P digest、M version、rollback/reset欄を保持する
compact evidenceへ固定した。

- [`ft09_hybrid_active_compact.json`](../../evidence/p10/ft09_hybrid_active_compact.json):
  `6680518299ed6952bcd99cb300f8118e02a96045f22acea4acde7339f8e54ab0`
- [`lp85_hybrid_compact.json`](../../evidence/p10/lp85_hybrid_compact.json):
  `834907e467bc0ae1fb0130a3c9a06da2cefeb7ae8a700cbc9e090ce8cbb248d4`
- [`tr87_hybrid_compact.json`](../../evidence/p10/tr87_hybrid_compact.json):
  `fd2ea2dd39f378228446b4cb3847c8f97741e5b9105203081e693784dda5f9e4`
- [`su15_hybrid_active_failure_compact.json`](../../evidence/p10/su15_hybrid_active_failure_compact.json):
  `10442999cd46639c281cc717bb937166dc3c1a9d5ab1c167b0a8307b03b2bec2`

compact evidenceは省略したtrace event本体を`trace_events_digest`へ束縛する。
raw reportはlocal実行証拠であり、非決定的scorecard identityをrelease
artifactへ持ち込まない。

一方、rendered transition graphだけによる探索は全sample攻略を閉じない。
G50T level 1の診断では188 action、1 reset、25 visible nodeでfrontierが
尽き、進捗は0だった。status候補をstate signatureから除外しない診断は
状態空間が急増し、300秒以内に進捗を得なかった。

これはP10完了証拠ではなく、履歴位相・役割・目標・commit条件を持つ
identity-free演算子が残りの構造にも必要であるという反証である。したがって
現時点のHDS判断は`HOLD`とし、P11へ進めない。

## 4. 実行入口

```bash
cd ARC-AGI-3-Agents
python -m arc3_agi_agent.p10_instruction_compiler \
  --base-bundle-dir arc3_agi_agent/bundles \
  --output-dir arc3_agi_agent/bundles
python p10_main.py --game FT09 --instruction-variant hybrid \
  --max-actions 4096
python p10_main.py --all-samples --max-actions 4096 \
  --instruction-variant hybrid \
  --report ../evidence/p10/run.json

python -m arc3_agi_agent.local_score_oracle \
  --sample-zip /path/to/arc-prize-2026-arc-agi-3.zip \
  --p10-report ../evidence/p10/run.json \
  --output ../evidence/p10/arc3_local_score_oracle_latest.json \
  --markdown ../evidence/p10/arc3_local_score_oracle_latest.md
```

`p10_main.py`は全選択gameが`WIN`でない限り終了code 1を返す。
`local_score_oracle`は旧repo
`scripts/generate_arc3_local_score_oracle.py`のRHAE数式だけを個別ADAPTし、
P10 reportのagent traceとlocal scorecardから25 game分のlevel action数を
fail-closedで射影する。採点器は環境やagentを実行せず、公式APIにも接続しない。
RHAE scoreは同一条件回帰指標であり、183/183、identity-free、M因果、全traceの
P10完了gateを代替しない。現時点では移植機能だけを検証しており、現行agentの
全25 game score artifactはまだ生成していない。

## 5. 次の採否gate

追加する演算子は、現在frameと許可されたhistoryから適用条件を再導出し、
同一構造へ再利用できなければならない。旧資産のID router、level counter
router、replay、固定列、literal座標は移植しない。

各演算子は次を満たした場合だけactive Pへcompileする。

1. identity-free detectorとplannerを別々に試験する
2. 現行Pとの同一条件比較で完了levelを減らさない
3. failureがMへ保持され次判断を変える
4. source/hidden-state runtime参照が0
5. 全traceでHDSが最終採否主体である
