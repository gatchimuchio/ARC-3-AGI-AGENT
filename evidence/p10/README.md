# P10 execution evidence

このdirectoryは、保持済みOFFLINE sampleをP10 runtimeで実行した結果を
保存する。sample/game識別子は結果を同定する監査metadataに限り許可し、
P bundle、C selector、M payload、runtime routingには使用しない。

## Development capability evidence

`development/c2_c3_local_probe_all25_max1/`は、C2 Visible effect transition
modelとC3 Commit boundary predictorのshadow-only `LOCAL_PROBE`証拠である。

- mode: `OFFLINE`
- lifecycle: `ACTIVE`
- max-actions: 1
- game report: 25 / 25
- error: 0
- checkpoint: 25
- exact-condition resume: 25 reused / 0 executed
- transition observation: 25
- visible transition: 22
- no-visible commit: 3
- action-selection influence: 0
- shadow probe fault: 0
- Runtime P promotion: `HOLD`
- condition digest:
  `6e85e433f42f992b20705968c30a1594a60a91ab7068e69ce187253e7102e296`

| artifact | SHA-256 |
|---|---|
| raw report | `e5859d50efd090e23a795fff51d32e7d7b2ad72a402043de4167f874aa62f1c7` |
| compact evidence | `1c4c3062d1a5654b7dd0792f31b14e49aff6254f4e5720669ae421d98fac5de5` |
| LOCAL_PROBE audit | `9d3000ba55228c17fe07bf2b34a308e5eed590354a0caaf0688a4a55b08071d2` |
| resume index | `fbd9e627c3f93fc9c29112b45581e3a538e2992b1c2c678c14d5291be2b5d5f4` |

`p10_all25_active_max1_raw.json`はscorecardを含む原report、
`p10_all25_active_max1_compact.json`はscorecard identityを除くcontent-bound
射影、`C2_C3_LOCAL_PROBE_AUDIT.json`はHDS境界を含む監査正本である。
`checkpoints/`はgame単位のresume証拠である。

max-actions 1のためcompleted levelは0である。このdirectoryを35/183更新、
full local score、CLUSTER_STABLE、COMPOSABLE、全sample攻略の証拠に使わない。

### visual operator v14での再取得

`development/c2_c3_local_probe_all25_max1_v14/`は、有界memory/
visual-explorer実装後にruntime source inventoryを取り直した現行正本である。
旧directoryはv13時点の履歴証拠として保持し、現行checkpointへ再利用しない。

- condition digest:
  `1cb23c290b76719cea2047fcef038c0f75ffd7a2429df2c147d585a0bc717966`
- runtime source inventory:
  `8ade5406134a6ff077934da8dc44eae979d9046dcfb1ca1e33a329c5acbd259b`
- report: 25 / 25
- error / probe fault: 0 / 0
- visible / no-visible: 22 / 3
- action-selection influence: 0
- resume: 25 reused / 0 executed
- HDS: `LOCAL_PROBE PASS`、`CLUSTER_STABLE HOLD`、`COMPOSABLE HOLD`

| artifact | SHA-256 |
|---|---|
| raw report | `95b9cfcfe34a4b4d849dd92e6cfca36743afdab7487dd102841aa5c3472daf0c` |
| compact evidence | `5bcbf15c2c034937ef8e3d03d5ee2b3a665391b148039d6a673305f00210700f` |
| LOCAL_PROBE audit | `37013f4cc797094c3a6eed71f0f972a4ce54bfd28c14c125a253d1a084046058` |
| resume index | `f616efb9761ee5000dc982af4422a32bdab1ee3a4b0697f577739be9ceab8094` |

max-actions-oneはscore証拠ではない。v14のBP35 450-action診断は6分41秒、
最大RSS約430 MB、swap 0でreportを生成し、旧workerの35分超・約1.37 GB
未完了を解消した。一方で0 / 9、`MAX_ACTION_STOP`、error 0であり、
能力境界は改善していない。機械可読な比較正本は
[`development/P10_BOUNDED_RUNTIME_MEMORY_V14_AUDIT.json`](development/P10_BOUNDED_RUNTIME_MEMORY_V14_AUDIT.json)
で、content digestは
`arc3_p10_bounded_runtime_memory_audit:f1d6ceba849ecb96c1372369940b69e6254a4afff9131217fd93c70bdb8e3179`
である。

### visual operator v14標準budgetと回帰

`OFFLINE / hybrid ACTIVE / max-actions 450`のcheckpoint aggregateは、
25 / 25 report、35 / 183 completed level、4 complete game、10,243 actions、
error/probe fault 0である。exact-condition resumeは25 reused / 0 executed。
添付ZIPの25 game / 183 levelへ束縛したローカル標準オラクルは
RHAE `18.821945363%`を返した。

| artifact | content digest |
|---|---|
| all-25 standard-budget audit | `arc3_p10_standard_budget_all25_audit:ae1c4f59ff59e7b79a66ee817b45b6581a230c30829fc1802220ba2e143a9c2b` |
| stable-regression audit | `arc3_p10_stable_regression_audit:e6953818cff613854f347ae3907cbe4ae1b34d653ee269a241e5b8267055a55a` |
| local score result SHA-256 | `40f7983afcdb2bb76884238375abd322b020ba0da085eeeec560fd17205340c9` |

standard-budget監査は
[`development/P10_ACTIVE_ALL25_MAX450_V14_AUDIT.json`](development/P10_ACTIVE_ALL25_MAX450_V14_AUDIT.json)、
回帰監査は
[`development/P10_V14_STABLE_REGRESSION_AUDIT.json`](development/P10_V14_STABLE_REGRESSION_AUDIT.json)、
score正本は
[`arc3_local_score_oracle_latest.json`](arc3_local_score_oracle_latest.json)
である。FT09、LP85、TR87、SU15、KA59の行動射影は旧HDS採用証拠と5/5一致した。
標準budgetの76 MB raw reportと82 MB checkpoint payloadはローカル保持し、
tracked compact/index/auditへSHA-256で束縛する。stable regressionのraw
reportも`scratch/`へ保持し、tracked compact証拠を比較正本とする。

SB26 workerは最大RSS 1,666,868 KB、並列計測peak swapは283 MBだったため、
worker completionは`PASS`でもresource headroomは`FAIL_HIGH_WATER`である。
このbaselineはscore・能力改善を示さず、Runtime Pは未変更、P10/P11は
`HOLD / GATED`のままである。

## `ft09_variant_comparison.json`

- schema: `arc3-p10-execution-evidence-v1`
- condition: OFFLINE、action budget 256、同一sample、seed 0
- variants: P-A / P-B / hybrid
- P-A: 6 / 6、75 actions、WIN
- P-B: 0 / 6、256 actions、MAX_ACTION_STOP
- hybrid: 6 / 6、75 actions、WIN
- error: 全variant 0
- content digest:
  `8d17b068a757ececded6c4f2a7669a57319a12e3194e5c8ca1d9c956f213f473`

各stable runはagent reportの全`trace_events`、trace digest、P format/version/
digest、M operation/version、HDS decision/verification、rollback/search-reset
証拠を保持する。local scorecard IDのような非決定的metadataだけを除外した。

この証拠はPの有無による能力差とFT09の6 level完了だけを示す。
全25 game / 183 level完了、未知構造への一般汎化、P11 release stateを
証明しない。

## 現行hybrid compact evidence

compact evidenceは、全cycleのtrace digest、trace event root、実emit、
provenance、level transition、P digest、M version、rollback/reset欄を保持する。
local scorecard identityと重複するtrace event本体は除外し、event本体全体を
`trace_events_digest`へ束縛する。

| file | 完了 | actions | 終端 | content digest |
|---|---:|---:|---|---|
| `ft09_hybrid_active_compact.json` | 6 / 6 | 75 | `WIN` | `6680518299ed6952bcd99cb300f8118e02a96045f22acea4acde7339f8e54ab0` |
| `lp85_hybrid_compact.json` | 8 / 8 | 235 | `WIN` | `834907e467bc0ae1fb0130a3c9a06da2cefeb7ae8a700cbc9e090ce8cbb248d4` |
| `tr87_hybrid_compact.json` | 6 / 6 | 308 | `WIN` | `fd2ea2dd39f378228446b4cb3847c8f97741e5b9105203081e693784dda5f9e4` |
| `su15_hybrid_active_failure_compact.json` | 4 / 9 | 160 | `MAX_ACTION_STOP` | `10442999cd46639c281cc717bb937166dc3c1a9d5ab1c167b0a8307b03b2bec2` |

上記四fileはv14以前のbaseline証拠として保持する。現行active Pは
`p10-hybrid-v26`であり、HDS採用済みの再現可能なlevel境界は
35 / 183へ更新された。

## P update v14 promotion evidence

`p_update/iteration_14_regression/`をv14の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | HDS-approved MからのP-B学習、同一入力C差分、stable/target二回回帰 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout比較、attribution |
| `p10_active_post_promotion_su15.json` | ACTIVE昇格後の9 / 9、175 actions、reset 0 |

候補はstable 20 / 20を維持し、targetをprevious stableの7 / 9から9 / 9へ
改善した。同条件二回のselected-field digestは一致し、HDSの全十promotion
gateがPASSした。中間iterationのraw reportとsuperseded bundleは正本へ
含めず、`M_dev`の無制限追記を避ける。

全25 gameのcanonical 450-action逐次runは外部commandの7200秒timeoutに達し、
完了reportを生成できなかった。この失敗はP10 agentのmax-action停止と分離し、
full scoreおよび183 / 183の証拠には使用しない。P10全体は`HOLD`である。

## P update v16 promotion evidence

`p_update/iteration_16_regression/`をv16の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 level回帰、target 0→1、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout比較、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の1 / 7、64 actions、error 0 |

候補は既存29 levelを同じactionsで維持し、bounded targetをprevious stableの
0 / 7から1 / 7へ改善した。同条件二回のtarget run digestは一致し、HDSの
全十promotion gateがPASSした。active manifest digestは
`4e19e461a7f0d65573782be5e2bddc873ba62d5bfe76ef2f1e42293ac2dd32cc`。
ただしtargetは`MAX_ACTION_STOP`で残り6 levelが未完了であり、完全な
25 game / 183 level reportも存在しない。したがって30 / 183は採用済み
level境界であって、ローカルオラクルのfull scoreではない。

## P update v17 promotion evidence

`p_update/iteration_17_regression/`をv17の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 stable level回帰、target 1→2、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout gate、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の2 / 7、96 actions、error 0 |

候補は既存29 levelの完了数とactionsを維持し、bounded targetをprevious
activeの1 / 7から2 / 7へ改善した。同条件二回のtarget selected-field
digestは一致し、HDSの全十promotion gateがPASSした。active Pは
`p10-p-a-symbolic-v23`、`p10-p-b-parametric-v23`、
`p10-hybrid-v22`、active manifest digestは
`8db83a354c334811870bca13f72ea49b329dd35fb11fd77cb3cc92a07d400da3`。

post-promotion targetは`MAX_ACTION_STOP`で残り5 levelが未完了であり、
完全な25 game / 183 level reportも存在しない。したがって31 / 183は
HDS採用済みlevel境界であって、ローカルオラクルのfull scoreではない。

## P update v18 promotion evidence

`p_update/iteration_18_queue_regression/`をv18の正本promotion証拠directory
とする。`p_update/iteration_18_regression/`はtarget 2→2でHOLDされた
先行候補の反証証拠として保持する。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 stable level回帰、target 2→3、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout gate、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の3 / 7、192 actions、error 0 |

closed-outline interiorとfilled-shape family、bounded actor-mediated impulse
push、dynamic footer除外、transient queue advancementを候補に限定して導入した。
候補は既存29 levelを維持し、targetを2 / 7から3 / 7へ二回同一に改善した。
HDS昇格後のactive Pは`p10-p-a-symbolic-v24`、
`p10-p-b-parametric-v24`、`p10-hybrid-v23`、active manifest digestは
`9beb81c420fff3b4bc453edc960300eb5912035a4efe871b57498adabf8d9584`。

## P update v19 promotion evidence

`p_update/iteration_19_regression/`をv19の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 stable level回帰、target 3→4、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout gate、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の4 / 7、192 actions、error 0 |

候補は複数marker actor、selected actor index、観測由来click point、
interchangeable shape family、recursive actor-mediated pushを明示状態として
追加した。既存29 levelはactive/candidateで同じ完了数を維持し、targetは
3 / 7から4 / 7へ改善した。candidate二回のcompact reportは完全一致し、
HDSの全十promotion gateがPASSした。active Pは
`p10-p-a-symbolic-v25`、`p10-p-b-parametric-v25`、
`p10-hybrid-v24`、active manifest digestは
`ed005422ea68a7cc42bad99a10817ba7b6b7ab337bdb8993a750d781fba21c2c`。

post-promotion targetは`MAX_ACTION_STOP`で残り3 levelが未完了であり、
完全な25 game / 183 level reportも存在しない。したがって33 / 183は
HDS採用済みlevel境界であって、ローカルオラクルのfull scoreではない。
P10は継続、P11は未開始である。

## P update v20 promotion evidence

`p_update/iteration_20_regression/`をv20の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 stable level回帰、target 4→5、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout gate、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の5 / 7、192 actions、error 0 |

候補はrendered geometryだけから三辺がintactで一辺のmissing runが外側occluder
に覆われたtargetを一意に再構成する。occluder normalへ垂直に進入するbounded
routeと、移動objectがtarget edgeを一時的に隠す間だけ既emit actionを一つ進める
queue検証を追加した。open outline、複数候補、incoherent occlusion、blocked
routeはfail closedする。既存29 levelは二回とも同じ完了数とactionsを維持し、
targetは4 / 7から5 / 7へ二回同一に改善した。HDSの全十promotion gateがPASSし、
active Pは`p10-p-a-symbolic-v26`、`p10-p-b-parametric-v26`、
`p10-hybrid-v25`、active manifest digestは
`66ab43152ef7eb4512679ca4a683a3c4963a2bb8147daaa743fe70f9f9b5ceba`。

post-promotion targetは`MAX_ACTION_STOP`で残り2 levelが未完了であり、
完全な25 game / 183 level reportも存在しない。したがって34 / 183は
HDS採用済みlevel境界であって、ローカルオラクルのfull scoreではない。
P10は継続、P11は未開始である。

## P update v21 promotion evidence

`p_update/iteration_21_regression/`をv21の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 stable level回帰、target 5→6、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout gate、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の6 / 7、200 actions、error 0 |

候補はrendered selected marker actor、filled shapeと各target obligation、
hazardで分断された通常移動region、方向別charge band、force portalを現在観測
だけから構成する。shape配置、transit復帰、actor配置を独立したbounded stage
として探索し、各queued actionを次のrendered grid digestで再検証する。
未選択marker roleが存在する次構造は早期fail-closeし、search-state上限は
原形・反転・90度回転fixtureを閉じる丸め済み安全値2,000へ固定した。

既存29 levelは二回とも同じ完了数を維持し、targetは5 / 7から6 / 7へ
二回同一に改善した。HDSの全十promotion gateがPASSし、active Pは
`p10-p-a-symbolic-v27`、`p10-p-b-parametric-v27`、
`p10-hybrid-v26`、active manifest digestは
`6b67437d771d2a31f4c93303dee858f5151120412c2b7cf3ce55061b987aa2e1`。

post-promotion targetは`MAX_ACTION_STOP`で残り1 levelが未完了であり、
完全な25 game / 183 level reportも存在しない。したがって35 / 183は
HDS採用済みlevel境界であって、ローカルオラクルのfull scoreではない。
P10は継続、P11は未開始である。

## C7 negative-only移植とdirectional-settle反証

P3 provenanceで凍結済みのC7 harnessを
[`c7_target_contact_closed_negative_v1`](development/c7_target_contact_closed_negative_v1)
へ移植した。sourceはmanifest記録のSHA-256
`cf52951e7bc4c85aa29a2bff217f298b558fc5d3dad6312c3bde1c8575883032`
および2,232,464 bytesと一致する。7 target、288 probe、228 visible change、
63 contact gainに対し、progress/hazard/promotion separatorは全て0だった。
legacy contract-spec mismatchは明示quarantineし、同じtarget-contact surfaceを
繰り返さないための負の証拠にだけ採用する。HDSは
`REJECT / CLOSED_NEGATIVE`、Runtime P compile/promotion/score claimは不許可。

KA59 remaining-boundary compositionでは、既存multi-actor、
directional-force、obligation capabilityへ、進捗後の旧actionを最大8回だけ
再観測する候補を合成した。FT09は6/6を維持したが、KA59はactive/candidate
とも6/7、220 actionsでdelta 0だった。candidateはaction 194–201で旧actionを
8回再送した後、action 202でgeneric fallbackへ戻ったため、候補発火不足ではなく
因果仮説の反証である。HDSは`REJECT / CLOSED_NEGATIVE`、active manifest不変、
candidate slot復元、all-sample regression不許可とした。正本は
[`directional_settle_composition_v1`](development/directional_settle_composition_v1)
に置く。

capability queueではC7を`LOCAL_PROBE / CLOSED_NEGATIVE`、C5の
bounded-old-action-replay軸を`LOCAL_PROBE / CLOSED_NEGATIVE_AXIS`とし、
KA59の同一軸を再試行する場合は、旧action replayではなく新しいvisible
successor obligation stateが必要である。

## C12 layout-mode二surfaceのnegative-only閉包

P3 provenanceで凍結済みのprimary C12 harnessとauxiliary layout-mode harnessを
[`c12_layout_mode_closed_negative_v1`](development/c12_layout_mode_closed_negative_v1)
へbyte-exactで保持した。primaryは1,700,713 bytes、SHA-256
`3ca11339393f4c4410974e676cf163099a2da36030d869dd10c45d5c4364df40`、
auxiliaryは185,866 bytes、SHA-256
`bb9ce326f52709ad9395c1a7db959c520f8b634750265f735db5edda827479fd`
である。

primaryは5 target / 212 probe / 140 visible change /
104 layout-mode change、auxiliaryは5 target / 176 probe /
86 visible changeだった。合計388 probeに対してprogress 0、GAME_OVER 0、
progress/hazard/promotion separator 0、positive pre-action variable 0である。
primary contract-spec mismatch、auxiliary public replay bootstrap、stale score
fieldをquarantineした。HDSは`REJECT / CLOSED_NEGATIVE`、same-surface retry、
Runtime P compile/promotion、score claimをすべて不許可とした。

capability queueではC12を`LOCAL_PROBE / CLOSED_NEGATIVE`として閉じ、次の
未埋込high-support work blockを
`WB-C1_rendered_affordance_objectizer`へ進める。active scoreは変更しておらず、
35/183、RHAE 18.821945363%のままである。
