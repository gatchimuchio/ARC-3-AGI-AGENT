# ARC3公式サンプル汎用完遂AGI ロードマップ準拠指示書 rev5.1

- 指示書ID: `ARC3_GENERIC_COMPLETION_AGI_ROADMAP_INSTRUCTIONS_REV5_1`
- 上位仕様: `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev5_1.md`
- 対応ロードマップ: `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev5_1.md`
- 適用対象: Codex／実装LLM／開発実行主体
- 原則: ロードマップPoint IDと本書の指示IDを一対一対応させる
- 旧rev4指示: `HISTORICAL_SUPERSEDED`

---

## 0. 全Point共通契約

以下はすべてのPointに常時適用する。

```text
最終成果物は、公式サンプル25 game／183 levelを完遂する
統合AGIエージェント ARC3CompletionAgent である。

C = Execute(L0, P)
AGI Kernel = Trinity(C, J_hds, M)

HDS解析、成功軌道、回答、構造、P/J0/M0は
製品能力を作る素材・手段・内部部品であり、単独のendpointではない。
```

### 共通実行規則

1. 作業開始時に、現在Point ID、目的、入力、Exitを明示する。
2. ロードマップで許可されたPoint以外へ進まない。
3. 新しいshell、空agent class、parallel runner、管理専用phaseを作らない。
4. 既存公式Adapter、C/J/M Runtime、P-IR、memoryを原則再利用する。
5. 解析は必ずRuntime M、P_dev、J_dev、M_devまたは製品コードへ接続する。
6. 一回の成功をrelease P/J0/M0へ直接昇格しない。
7. 外部actionはすべてJの承認を通す。
8. `game_id`、`level_id`、frame完全hash、trajectory indexで答えを選ばない。
9. Work Unitは`HDS解析→製品変更→統合実行→結果差分→回帰`まで閉じる。
10. 報告は能力差分、game／level差分、Failure Signature、次Pointだけに限定する。

### 共通作業採否Gate

```text
この作業は、
- ARC3機構理解を増やすか
- P/J/M能力を増やすか
- 三主体オンライン循環を強化するか
- 完遂game/levelを増やすか
- 観測済みblocking failureを直接除去するか
```

すべてNOなら実行しない。

### 共通報告形式

```yaml
PointReport:
  point_id:
  product_gap:
  HDS_finding:
  product_change:
  asset_state_change:
  games_before_after:
  levels_before_after:
  failure_signature_change:
  regression:
  exit_status:
  next_point:
```

---

# M0 — CAPABILITY BASIS + FIRST AGI CLOSURE

## 指示 M0-P01 — EXISTING PRODUCT PATH BINDING

```text
現在PointはM0-P01である。
既存repositoryから、公式Environment Adapter、GenericAGIRuntime、CognitiveSession、
GenericHDSJudgementSubject、SemanticMemory、P-IR/interpreter、rollback、authority経路を確認せよ。
新しいagent shell、runner、entrypoint、packageを作るな。
現在のPとP-IRの置換点、C/J/Mの能力追加点、公式入力から外部actionまでの唯一の経路を一枚に固定せよ。
出力は既存substrateへの参照と変更点だけとし、平行実装を0にせよ。
Exitはone product substrate、parallel shell 0、P/P-IR replacement point確定である。
```

---

## 指示 M0-P02 — CAPABILITY COVERAGE MATRIX

```text
現在PointはM0-P02である。
公式サンプル25 game／183 level、metadata、PH-D05 manifest、必要最小限の環境ソースを確認し、
各gameについてinput modality、action surface、RESET、ACTION6、ACTION7、layer数、temporal/animation、
delayed effect、phase change、長期手数、rollback、planning depth、spatial binding、goal構造を一行で記録せよ。
深層HDS解析は行うな。全gameの能力面と未被覆面を比較できるCapabilityCoverageMatrix一つだけを作れ。
次Pointのbasis選定へ直接使えない項目は追加するな。
Exitは25 game、183 level accounting、coverage gap明示、basis選定入力完成である。
```

---

## 指示 M0-P03 — BASIS SET SELECTION

```text
現在PointはM0-P03である。
M0-P02のCapabilityCoverageMatrixだけを入力に、keyboard-only、ACTION6-only、mixed action、RESET、ACTION7、
multi-layer/temporal complexity、long-horizon resourceを覆うbasis setを選定せよ。
短いgameだけ、同一mechanism familyだけ、回答が簡単なgameだけに偏らせるな。
各選定gameについて、どの能力面を閉じるために必要か、代替候補より優先する理由を記録せよ。
Exitはmandatory surface全coverage、basis順序固定、未被覆能力0または明示的追加条件である。
```

---

## 指示 M0-P04 — BASIS CASE DEEP HDS ANALYSIS

```text
現在PointはM0-P04である。
選定basis gameを一件ずつ、Game→Level→Phase→Mechanism Segment→Action Macro→raw step spanへ分解せよ。
各機構変化点についてPurpose Tree、W=(X,R,Mc)、entity/role/relation、state、action semantics、precondition、
immediate/delayed effect、goal/hazard、order/loop/phase、subgoal、probe、rollback、Failure Signature、applicabilityをHDSのF/Md/Cm/Uで確定せよ。
一手ごとの重い文書を作るな。同型反復はREPEAT、MOVE、CLICK EACH、WAIT UNTIL等へ圧縮せよ。
全raw actionをsegmentへ対応づけ、open termとproduct mapping候補を残せ。
Exitは全basis raw actionのsegment所属、全segmentの目的・条件・操作・効果・終了条件成立である。
```

---

## 指示 M0-P05 — LOCAL CAPABILITY IMPLEMENTATION

```text
現在PointはM0-P05である。
M0-P04のTaskMechanismRecordをreportで終わらせず、最初はRuntime M/LOCAL_Mへ、
再利用候補はP_dev/J_dev/M_devのPROBATION_DEVへ実装せよ。
必要なmulti-layer representation、goal/mechanism hypothesis、counter-hypothesis、action binding、effect prediction、
probe/plan、J risk/wait/rollback、M support/refutation/invalidationを既存C/J/M Runtimeへ追加せよ。
release P/J0/M0へ直接固定するな。game ID selector、固定軌道、frame hash lookupを入れるな。
Exitは製品runtimeが能力をloadし、Cが引用し、Jが採否し、Mが修正・無効化できることである。
```

---

## 指示 M0-P06 — FIRST ONLINE TRINITY CLOSURE

```text
現在PointはM0-P06である。
M0-P05の能力を既存製品経路へloadし、最初のbasis gameを人間の一手指示なしで実行せよ。
各重要状態でCは複数model/planを生成し、Jはexecute/probe/wait/rollback/reset/suspendを採否し、
結果をG11 Temporal Attributionで帰属し、MをADD/REVISE/INVALIDATE/REPLACEせよ。
relevant M更新後に次のcandidate/plan/actionが変わることを実測せよ。
同じ失敗仮説を無限反復した場合はFailure Signature化し、別modelまたはnext questionへ切り替えよ。
Exitは全action J承認、記憶因果成立、agent自律probe生成、最初のbasis game WINである。
```

---

## 指示 M0-P07 — BASIS SET WIN CLOSURE

```text
現在PointはM0-P07である。
M0-P06で成立した同じC/J/M/P構造をbasis setの各gameへ適用せよ。
各gameでHDS分析→capability delta→統合→実行→failure classification→最小修正→WINを同一Work Unit内で閉じよ。
新しい個別solver shellを作るな。game固有差は観測依存ApplicabilityPredicateとparameter bindingで表現せよ。
完遂済みbasis gameの回帰を各変更後に実行せよ。
Exitは全basis game WIN、全basis level complete、mandatory action/observation/resource surface実証である。
```

---

## 指示 M0-P08 — INITIAL HORIZONTAL SUBTRACTION

```text
現在PointはM0-P08である。
basis gameのTaskMechanismRecordをpurpose、input責任、precondition、operation、transition、goal、hazard、orderで比較せよ。
色、座標、対象名、action literalをparameterへ分離し、positive/negative/boundary CaseとApplicabilityPredicateを持つGenericMechanismFamilyを作れ。
独立Case support、反例、regression、identity/replay finding 0を満たすものだけACTIVE_DEVへ昇格せよ。
満たさないものはPROBATION_DEVまたはDomain-Local Residueに留めよ。
Exitはcross-game ACTIVE_DEV能力1件以上、全basis WIN維持、game-ID選択0である。
```

---

# M1 — CAPABILITY-FAMILY EXPANSION

## 指示 M1-P01 — FULL-SAMPLE FAILURE / CAPABILITY INVENTORY

```text
現在PointはM1-P01である。
現行ACTIVE_DEV ProductBundleで公式25 gameを実行し、全game/level結果を構造原因で分類せよ。
表面症状ではなく、OBSERVATION、REPRESENTATION、GOAL、MECHANISM、PRECONDITION、ACTION_BINDING、EFFECT、DELAY、PLAN、PROBE、J、M、ROLLBACK、TRANSFER、RESOURCEへclusterせよ。
各clusterにaffected game/level数、blocking severity、再利用可能性、依存関係を付け、最大leverage gapを明示せよ。
新しい能力実装は次Pointで行う。Exitは25 game attempted、failure cluster ranking、次gap一意化である。
```

---

## 指示 M1-P02 — CAPABILITY CLOSURE UNIT SELECTION

```text
現在PointはM1-P02である。
M1-P01のclusterから、affected game数、level数、再利用性、blocking severity、依存、regression riskを比較し、次に閉じるCapabilityClosureUnitを一つ選べ。
選定unitについてproduct gap、対象CaseSet、期待完遂delta、責任候補、必要HDS観測、禁止される代理解を固定せよ。
複数unitを同時に開始するな。Exitは一つのCapabilityClosureUnitが実装可能な粒度で固定されることである。
```

---

## 指示 M1-P03 — HDS CASESET ANALYSIS

```text
現在PointはM1-P03である。
選定CapabilityClosureUnitのaffected CaseSetをHDSで比較せよ。
共通Frameと差分条件を分け、baseline、alternative、counter-hypothesis、null/no-op、observation error、wrong target/order等を生成せよ。
positive、negative、near-miss、failure CaseからApplicabilityPredicateとfalsification conditionを確定し、水平引き算候補を作れ。
単一Caseの成功だけで一般化するな。ExitはCaseSetを説明するmechanism、反例、責任component固定である。
```

---

## 指示 M1-P04 — PRODUCT CAPABILITY IMPLEMENTATION

```text
現在PointはM1-P04である。
M1-P03で確定した機構をP_dev/J_dev/M_dev/C/J/M/Adapterの最小責任箇所へ実装せよ。
製品runtimeが直接読むtyped capabilityとし、asset state、source Case、ApplicabilityPredicate、Failure Signature、expected behavior deltaを保持せよ。
parallel product path、identity feature、trajectory replayを追加するな。
単体挙動で期待差分を確認し、直後にaffected game実行へ進め。
Exitはcapability executable、behavior delta観測、外装増加0である。
```

---

## 指示 M1-P05 — AFFECTED GAME CLOSURE

```text
現在PointはM1-P05である。
M1-P04の能力を使い、affected game/levelを再実行せよ。
選択したFailure Signatureの減少、完遂level/game delta、resource、回帰を測定せよ。
failureが消えなければHDS FrameまたはModelSetを更新し、同じunit内で最小修正を繰り返せ。
failureが別責任へ移動した場合は新Failure Signatureを作り、現在unitを閉じてM1-P02へ戻せ。
Exitはtarget failure減少または消失、完遂delta増加、basis regression PASSである。
```

---

## 指示 M1-P06 — CONTINUOUS HORIZONTAL SUBTRACTION / PROMOTION

```text
現在PointはM1-P06である。
M1-P03〜P05で得た能力を既存Caseと比較し、重複構造を水平引き算せよ。
独立Case support、negative/boundary Case、regression、identity/replay finding 0、behavior deltaを満たす場合だけACTIVE_DEVへ昇格せよ。
期待failureが減らない、別failureが増える、適用範囲外で誤作動する、identity proxyがある場合は降格またはrollbackせよ。
Exitはasset state、適用範囲、次のFailure Signatureが確定することである。
```

---

## 指示 M1-P07 — FULL MAPPING CLOSURE

```text
現在PointはM1-P07である。
M1-P01〜P06を反復し、全25 game／183 levelを少なくとも一度完遂せよ。
全raw actionをMechanism Segmentへ所属させ、全segmentをCapabilityFamilyまたは明示的Domain-Local Residueへ対応づけよ。
全primary解析物にRuntime M、P_dev、J_dev、M_devまたは製品componentへのmappingを持たせ、未使用解析artifactを0にせよ。
Exitは25 game individually WIN、183 level individually complete、one ACTIVE_DEV ProductBundleである。
```

---

# M2 — FULL-SAMPLE PRODUCT CLOSURE

## 指示 M2-P01 — CLEAN RUN A / OFFICIAL ORDER

```text
現在PointはM2-P01である。
fresh process、fresh CognitiveSession、fresh M、one ACTIVE_DEV ProductBundleで公式順序の25 gameを連続実行せよ。
各gameのWIN、levels、actions、stop reason、Failure Signature、M promotion、resourceを記録せよ。
途中で人間修正を入れるな。全数PASSならM2-P04へ、failureがあればM2-P02へ進め。
Exitはfull-run failure setまたは25/25 PASS結果である。
```

---

## 指示 M2-P02 — FULL-RUN FAILURE REPAIR

```text
現在PointはM2-P02である。
M2-P01でのみ発生したstale memory、negative transfer、resource、game-order、session lifecycle、Applicability誤適用をHDSで責任分解せよ。
最小責任箇所を修正し、局所回帰とfull-run前提回帰を行え。
新しい管理層やrunnerで包むな。Exitは対象full-run failure閉包または明示的CapabilityClosureUnit化である。
```

---

## 指示 M2-P03 — CLEAN RERUN UNTIL PASS

```text
現在PointはM2-P03である。
M2-P01とM2-P02を反復し、公式順序clean runで25/25 WIN・183/183 completeを成立させよ。
各修正後にfresh stateから再実行し、過去完遂gameのregressionを確認せよ。
ExitはRun A 25/25、183/183、product crash 0、manual intervention 0である。
```

---

## 指示 M2-P04 — SHUFFLED ORDER RUNS

```text
現在PointはM2-P04である。
同一artifact、同一ProductBundle、fresh stateでgame順序を二種類shuffleしてRun B／Cを実行せよ。
順序依存のM contamination、暗黙identity、negative transfer、resource driftを監査せよ。
順序依存が能力上のblocking failureなら修正し、再度B／Cを実行せよ。
Exitは順序非依存PASSまたは許容可能な明示境界確定である。
```

---

## 指示 M2-P05 — FULL-SAMPLE PRODUCT CLOSURE

```text
現在PointはM2-P05である。
Run A/B/C、全回帰、identity/replay preliminary scanを統合し、one agent architecture、one ACTIVE_DEV ProductBundle、clean state、25/25 WIN、183/183 completeを確認せよ。
不足が一つでもあればM2を閉じるな。
ExitはM2_COMPLETEのみである。
```

---

# M3 — GENERIC / AGI CONFORMANCE

## 指示 M3-P01 — C / J / M / P ABLATION

```text
現在PointはM3-P01である。
同一入力と代表CaseでC、J、M、Pを個別に除去または機能停止せよ。
C除去で新規表現・仮説・計画、J除去で外部action/ACTIVE M commit、M除去で学習差、P除去でARC3能力が失われることを確認せよ。
削除しても能力が残る場合、機能等価物漏れまたは責任混線を修正せよ。
Exitは全ablationが設計予測と一致することである。
```

---

## 指示 M3-P02 — MEMORY CAUSALITY

```text
現在PointはM3-P02である。
same observationに対し、relevant Mを追加・修正・無効化し、candidate/plan/actionが変化することを確認せよ。
次にirrelevant/stale/out-of-scope Mを追加し、action不変を確認せよ。
差が出ない場合はretrieval、binding、J citation、memory update経路を修正せよ。
Exitはrelevant causalityとirrelevant invarianceの両方PASSである。
```

---

## 指示 M3-P03 — IDENTITY / REPLAY AUDIT

```text
現在PointはM3-P03である。
product code、PBundle、JDomainProfile、M0、Domain-Local Residue、selectorを対象にgame_id、level_id、recording_id、trajectory_id、exact frame hash、successful action sequence、action indexを検索・追跡せよ。
orchestration metadataはtaintとしてdecision inputへ流入させるな。
発見した経路は現在観測のApplicabilityPredicateとparameter bindingへ置換し、全数回帰せよ。
Exitはidentity action router 0、fixed trajectory playback 0である。
```

---

## 指示 M3-P04 — APPLICABILITY COUNTERFACTUAL

```text
現在PointはM3-P04である。
代表MechanismSpecごとに、成立条件を保つ摂動と壊す摂動を作れ。
条件保持摂動では適用と行動原理が維持され、条件破壊摂動では非適用、alternative選択、SUSPENDのいずれかになることを確認せよ。
表面identityで選択される場合はApplicabilityPredicateを修正せよ。
Exitは全mandatory familyのcounterfactual境界PASSである。
```

---

## 指示 M3-P05 — RUNTIME / VERSION LEARNING

```text
現在PointはM3-P05である。
実行経験がまずRuntime Mを更新し、複数Run、反証、削除試験、回帰を通過した安定構造だけがrelease候補P/J0/M0へ再コンパイルされることを確認せよ。
false learningをINVALIDATE/ROLLBACKでき、restart後にcompiled initial stateから獲得能力を利用できることを示せ。
一回の成功からrelease固定する経路を禁止せよ。
ExitはRuntime LearningとVersion Learningの分離成立である。
```

---

## 指示 M3-P06 — CONFORMANCE FULL REGRESSION

```text
現在PointはM3-P06である。
M3-P01〜P05の全試験後、同一ACTIVE_DEV ProductBundleでclean full sampleを再実行せよ。
25/25 WIN・183/183を維持できなければM3を閉じるな。
Exitは全conformance PASSと全数完遂維持である。
```

---

# M4 — PRODUCT FREEZE AND RELEASE

## 指示 M4-P01 — RELEASE BUNDLE COMPILATION

```text
現在PointはM4-P01である。
M3を通過したACTIVE_DEV P_dev/J_dev/M_devだけを入力に、RELEASE_FROZEN P/J0/M0へ再コンパイルせよ。
PROBATION、LOCAL_M、未閉包、identity/replay contaminated assetをreleaseへ入れるな。
一つのARC3ProductBundle、provenance、type/operator registry、resource contractを生成せよ。
Exitはone release bundleである。
```

---

## 指示 M4-P02 — CODE / DEPENDENCY / RESOURCE FREEZE

```text
現在PointはM4-P02である。
M4-P01のbundleを使うcode、dependency、resource、adapter、entrypointを一意に固定せよ。
能力変更を混ぜるな。変更が必要ならM3以前へ戻れ。
Exitは再構築可能なfreeze manifestと一意な実行経路である。
```

---

## 指示 M4-P03 — CLEAN INSTALL

```text
現在PointはM4-P03である。
fresh environmentへ同一artifactをinstallし、外部cache、開発tree、secret、未固定assetなしで起動せよ。
import、bundle load、official adapter、C/J/M/P self-checkを確認せよ。
Exitはclean install／boot PASSである。
```

---

## 指示 M4-P04 — CLEAN FULL-SAMPLE RERUN

```text
現在PointはM4-P04である。
M4-P03のclean install環境で同一release artifactを公式サンプル全数へ実行せよ。
25/25 WIN・183/183 completeを再現できなければreleaseを破棄し、原因Pointへ戻れ。
Exitはsame artifact full-sample PASSである。
```

---

## 指示 M4-P05 — KAGGLE PACKAGE / NORMAL RUN

```text
現在PointはM4-P05である。
M4-P04でPASSした同一artifactをKaggle Notebook／entrypointへ配置し、dependency install、公式I/O、placeholder/output contract、sequential scorecard lifecycle、normal runを確認せよ。
このPointで能力を変更するな。ExitはKaggle normal run completeである。
```

---

## 指示 M4-P06 — SUBMISSION / PLATFORM SEPARATION

```text
現在PointはM4-P06である。
M4-P05の同一artifactを提出し、product failure、transport failure、Kaggle platform failureを分離して記録せよ。
platform failureを能力failureへ誤帰属せず、製品failureをplatform failureへ隠すな。
提出結果とrelease artifact identityを固定し、ExitをARC3_COMPLETION_AGENT_PRODUCT_RELEASEDとせよ。
```

---

# CapabilityClosureUnit 共通テンプレート

```yaml
CapabilityClosureUnit:
  unit_id:
  roadmap_point:
  product_gap:
  affected_games:
  affected_levels:
  raw_trace_spans:
  HDS:
    F:
    Md:
    Cm:
    U:
  selected_mechanism:
  counter_hypotheses:
  applicability:
  falsification_condition:
  responsible_component:
  asset_state_before:
  product_change:
  expected_behavior_delta:
  execution_result:
  game_delta:
  level_delta:
  failure_signature_change:
  regression:
  asset_state_after:
  remaining_open_terms:
```

終了条件:

```text
target failureが減少・消失
または
原因が別責任へ移動したことを実測
AND
製品能力変更が実行結果へ現れた
```

---

# 現在Point投入指示

```text
現在PointはM0-P02_CAPABILITY_COVERAGE_MATRIXである。
上位仕様rev5.1、ロードマップrev5.1、本指示書の共通契約を正本として使用せよ。
新しいshell、runner、agent subclass、packageを作るな。
公式25 gameを浅く一巡し、CapabilityCoverageMatrix一つを作成し、M0-P03 basis set選定へ直接接続せよ。
深層HDS解析、全game構造抽出、P/J/M実装はまだ開始するな。
Exit条件を満たしたら、同じ報告内でM0-P03に必要なcoverage gapとbasis候補だけを提示せよ。
```
