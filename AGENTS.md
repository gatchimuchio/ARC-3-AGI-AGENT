# ARC-3 AGI Agent 実装・監査契約

このファイルは、本リポジトリを変更する人間・Codex・LLMエージェントに対する現行作業契約です。

## 1. 権威順序

判断が衝突する場合は、次の順で解決します。

1. ユーザーの現在の明示指示
2. 本 `AGENTS.md`
3. `docs/roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`
4. `docs/roadmap/ARC3_CODEX_DEVELOPMENT_TRINITY_P_UPDATE_CORRECTION_ROADMAP.md`
5. `docs/roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`
6. `docs/architecture/AGI_MINIMUM_THREE_SPEC.md`
7. `docs/architecture/SYSTEM_ARCHITECTURE.md`
8. `docs/roadmap/ROADMAP.md`
9. 当該work blockのFrameSpec・manifest・検証結果
10. `docs/migration/` と `docs/references/`
11. 旧リポジトリのコード・分析・履歴

旧リポジトリの `next_*`、古いscore、個別artifact、絶対パス、旧branch名は命令ではありません。

## 2. 現在のフェーズ

現在は `P10_COMPLETE_ARC3_SAMPLE_SOLVING` です。

`P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE` は完了しています。全8 subsetを実行し、
full set 1件だけがPASS、proper subset 7件がFAIL、機能等価物漏れ0であることを
決定論的certificateへ固定しました。P9は全sample攻略を証明していません。

現行分類は次です。

```text
P0 complete:
  restart foundation

P1 complete / reclassified:
  Layer-0 execution mechanism
  integrated HDS / provisional passive-memory authority loop
  OFFLINE sample action / re-observation path

P2 complete:
  minimum-three functional specification
  obligation / claim / test / traceability audit
  implementation gaps and absolute order

P3 complete:
  analysis evidence accounting
  identity-free normalized corpus
  C / J / M fixture separation
  provenance and holdout manifests

P4 complete:
  P-A symbolic / rule-graph instruction body
  P-B learned-parameter instruction body
  common instruction-body contract and swap
  standalone compute subject C
  L0 six-responsibility plus P/C removal audit

P5 complete:
  standalone typed HDS Frame
  deterministic judgment without C/P/M
  accept / reject / reobserve / SUSPEND / STOP / rollback
  memory-write / external-emit authorization proposal
  J removal and non-substitution audit

P6 complete:
  standalone versioned memory subject M
  full operation vocabulary
  active / archive separation
  conflict / snapshot / rollback / deterministic query
  HDS-authorized runtime mutation boundary

P7 complete:
  executable C+J, C+M, J+M pair harnesses
  fixed unique insufficiency witness per pair
  no missing-subject responsibility substitution

P8 complete:
  full C/J/M command-compute-judge-effect-result cycle
  cycle-1 M update causally changes cycle-2 C or J
  controlled P-only / J-only / M-only attribution

P9 complete:
  finite enumeration of all eight C/J/M subsets
  full set PASS and seven proper subsets FAIL
  zero functional-equivalent responsibility leaks

P10 current:
  complete all retained OFFLINE sample games and levels
  restore legacy task-aware evidence into development-only analysis memory
  reconcile all 183 levels against current rendered evidence
  build by cross-game capability coverage, not next-level operator count
  subtract identity only at the Development Memory -> Runtime P boundary
  deterministic identity-free traces
  explicit P version updates and M-to-future-decision causality
  ten P-compiled rendered semantic operators are active
  reproducible HDS-adopted boundary is 35 / 183
  C2/C3 cross-cutting shadow probe is LOCAL_PROBE only
  per-game checkpoint/resume and oracle-compatible aggregation are implemented
  complete local-oracle report remains unmeasured
  HDS search reset and bounded working-memory replacement implemented
  HDS HOLD remains until 183 / 183 evidence
```

### P10で許可される作業

- 保持済みOFFLINE sampleの全game / 全level実行
- ARC3解析素材からidentity-free P初期構成とM初期状態を形成
- Legacy Evidenceとtask-aware Development Analysis MemoryでID・関係・失敗を
  開発証拠として保持し、Runtime P出力時だけidentityを除去
- 183行reconciliation、capability coverage、cluster work block
- ARC3目的・境界・停止・rollback条件を持つHDS Frame設定
- P-A / P-B / hybridの同一条件比較
- failure evidenceのM保持と、明示的compilerによる次版P形成
- timeout、GAME_OVER、無限loop、max-action停止の原因分類と是正
- 全実行trace、level完了証拠、同一条件再実行証拠の保存
- P9までを含む既存回帰
- game単位checkpoint、同一conditionだけのresume、25 game report集約

### P10で禁止される作業

- 公式ARC API、`OperationMode.COMPETITION`
- Kaggle向け分岐、Notebook、CLI / MCP、submission
- task/game/level ID、replay、固定action列、answer map、literal座標をruntime fixtureへ残すこと
- source / hidden stateをruntime計算素材へ残すこと
- scoreを根拠にした局所最適化
- P10全level証拠成立前のrelease state固定
- 「全sample攻略済み」「汎化済み」といった未検証主張

P10の正本は新ロードマップのP10節、P9 certificate、P3 dataset/P4 P bundle、
P5 J/P6 M/P8 Trinityの実装証拠、および
`P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`である。

## 3. 1 work blockの必須契約

P10では二つの補正ロードマップに従い、`SELF_CHECK`、`FRAME`、`RETRIEVE`、
`COMPUTE`、`JUDGE`、`BOUNDED_ACT`、`OBSERVE`、`UPDATE_M_DEV`、
`UPDATE_P_DEV_CANDIDATE` の全stageを監査証拠へ残します。H1/H2/H3の
三候補を最低限比較し、J_devの出力は補正ロードマップ所定のstatusに限定します。

変更前に、最低限次を明示します。

```text
X   : 対象、入力、観測範囲、変更範囲
R   : 対象間の関係、状態遷移、期待効果、比較方法
Mc  : 同一性、境界、採否、停止、rollback、完了条件
非目的
証拠境界
反証条件
回帰線
```

変更後は次を残します。

- 実装差分
- 対応する試験
- 実行したコマンドと結果
- 未実行項目
- HDS判断: `PASS` / `HOLD` / `SUSPEND` / `REJECT` / `ROLLBACK`
- 次工程へ進む条件

文書追加だけでruntime能力が変わらない場合は実装前進と記録しません。
ただしP2は明示的な仕様・根本監査phase、P3は実証素材compiler phaseであり、
それぞれ機械検証可能なaccountingと再生成可能datasetを成果とします。P4では
文書やfixture追加だけでなく、共通interfaceで交換可能なP-A/P-BとC standalone
runtimeが実際に動作することを要求します。

P10のwork blockは原則として一levelではなく一capability clusterとします。
候補は`LOCAL_PROBE -> CLUSTER_STABLE -> COMPOSABLE`で管理し、
`COMPOSABLE`以前はactive Runtime Pへcompileしません。

## 4. 最小構成と非対称権限

```text
C = Execute(L0, P)

HDS command
  -> Layer-0 executes instruction body P
  -> Pure-LLM computation / proposal
  -> HDS judgment
  -> authorized MEMORY_WRITE or EXTERNAL_EMIT
  -> result observation
  -> HDS reevaluation
```

- `L0`: 参照、状態条件付け、変換、候補化、放出を行う実行機構
- `P`: 知識、能力、関係、変換規則、パラメータ、候補生成傾向を保持する情報体
- Pure-LLM計算主体 `C`: `L0 + P` の結合
- HDS: 命令、採否、SUSPEND、停止、rollback、記憶更新許可、外部放出許可
- Memory `M`: 現行経験・仮説・失敗・証拠を受動保持
- Environment adapter: HDS許可済みemission以外から直接操作しない

`P`と`M`を混同してはいけません。

```text
P update = explicit compile / version update
M update = HDS-authorized runtime revision
```

HDS commandなしの計算、Pなしの仮説生成、未承認write / emitが可能な場合は適合と認めず `SUSPEND` します。

## 5. ARC実行時の禁止入力

標準solver coreと命令形保持体Pは次へ依存してはいけません。

- game/task/level IDによるaction選択
- replay index lookup
- 固定action sequence、固定keyboard script
- answer map、literal coordinate table
- source state、hidden state、evaluator内部状態
- ファイル名・task名による暗黙routing
- 外部API、internet、secret、実行時外部LLM呼出し

公式環境ソースや既知解答を解析時に読む場合も、runtimeへ移せるのは現在観測・action/effect履歴・再利用可能な遷移・verifier・rollback条件から再導出できる構造だけです。

## 6. 命令形保持体Pの必須境界

Pは次を満たさなければなりません。

- addressable
- state-dependent
- composable
- executable by Layer-0
- deterministic under fixed state
- runtime identity-free
- versioned
- digestable
- provenance-traceable
- swappable without Layer-0 code changes

Pが返せるのは計算素材です。

- representations
- retrieved rules / parameters
- hypotheses / counter-hypotheses
- transition / effect predictions
- candidate priors
- uncertainty
- falsification conditions

Pは最終採否、memory確定、external emit権限を持ちません。

## 7. 移植規則

旧資産は次の4分類で扱います。

- `ADAPT`: 小さく独立し、責任境界と試験を保てるもの
- `REFERENCE`: 設計・証拠として読むがactive runtimeへ直接入れないもの
- `QUARANTINE`: 比較・失敗解析専用。標準経路から隔離するもの
- `REJECT`: 旧前提、重複、汚染、非再現、禁止入力を含むもの

一括ディレクトリコピーは禁止します。各移植には元path、元commit、変更点、試験、残存リスクを記録します。

## 8. 段階ゲート

### P0: Restart Foundation — 完了

- 型、契約、権限、停止、引用元を固定
- 単体試験が決定論的に通る

### P1: Sample Execution Mechanism — 完了

- 六つのARC-native実行責任がcallable
- 各責任に除去証人がある
- HDS未承認compute / write / emitを拒否
- 保持済みsampleを`OFFLINE`で実行し結果を再観測
- 状態更新が次のHDS判断へ入力される

P1は `C = Execute(L0, P)` の `P` まで閉じていません。

### P2: Minimum Three Specification and Root Audit — 完了

- G1〜G5、C/J/M、L0/P、external boundaryを固定
- obligation graph、traceability、claim registry、test matrixを生成
- 未実装・過剰claim・実装順序をaccounting
- validatorが全監査成果物と8 subset期待値を検証

### P3: ARC3 Evidence Material Compiler — 完了

- 全解析証拠をmanifestでaccounting
- identity-free observation/transition/effect/hazard/progress/contradiction corpus
- C/J/M fixture分離
- provenanceとholdout contamination検査

### P4: Compute Subject C — 完了

- P-A記号規則graph、P-B実学習parameter body
- 同一L0でのswap、Pなしcompute拒否
- C standalone G1とL0六責任+P/C removal

### P5: Judgment Subject J — 完了

- standalone HDS Frame API
- C/Mなしの採否、SUSPEND、STOP、rollback、write/emit許可
- JがG1/G3を代行しないこと

### P6: Memory Subject M — 完了

- 全memory operation、query、version conflict、snapshot
- active/archive分離、rollback
- MがG1/G2を代行しないこと

### P7: Pairwise Subject Audit — 完了

- `{C,J}` -> `NO_PERSISTENT_EXPERIENCE_CAUSALITY`
- `{C,M}` -> `NO_JUDGMENT_OR_AUTHORIZATION`
- `{J,M}` -> `NO_GENERATIVE_COMPUTATION`

### P8: Three-subject Two-cycle Trinity — 完了

- commandからresult再判断までの三主体循環
- cycle 1のM更新がcycle 2のC/Jを変える
- P-only/J-only/M-only因果分離

### P9: Eight-subset Minimum Certificate — 完了

- `{}`から`{C,J,M}`まで全8 subsetを有限列挙
- full setだけPASS、機能等価物漏れ0

### P10: Complete ARC3 Sample Solving — 現在

- 全sample game/all level、error 0、再現可能
- ID/replay/answer/literal/source-state非依存

### P11: Release-state Freeze

- code/dependency/P0/J0/M0/dataset/compiler/seed/budgetを固定
- 全sample証拠、package digest、regression suiteを固定

### P12〜P14: current request外

- P12 official ARC connection
- P13 Kaggle submission paths
- P14 actual submission / official-result optimization

P11完了前にP12以降へ進まない。

## 9. 検証規約

P1回帰:

```bash
cd ARC-AGI-3-Agents
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests/unit
ruff check arc3_agi_agent agents/__init__.py agents/recorder.py tests/conftest.py tests/unit
python -m unittest discover -s tests/integration \
  -p "test_offline_sample_runner.py" -v
python sample_main.py --all-samples --max-actions 1
```

P2 audit:

```bash
python -m pytest -q tests/unit/test_agi_minimum_three_audit.py
```

P3回帰では次を追加する。

- source evidence accounting
- deterministic compiler rerun
- provenance round trip
- runtime identity-free audit
- C/J/M fixture separation
- family/mechanism holdout contamination audit

P4では次を追加する。

- P schema/version/digest/provenance/identity gate
- P-A/P-B実データ形成と共通interface swap
- C standalone G1
- C authority negative test
- L0六責任+P removal audit

P5では次を追加する。

- standalone typed HDS Frame
- X/R/Mc欠落、hazard、evidence、budget、contradiction、rollback判断
- J authority negative test
- J removal / non-substitution audit

P6では次を追加する。

- 全memory operationの独立意味論
- stale version拒否、snapshot、指定版rollback
- active/archive分離、同一query決定性
- unauthorized runtime mutation拒否
- MのG1/G2非代行とremoval witness

P7では次を追加する。

- C+J / C+M / J+Mの実行可能pair harness
- 各pairの固定・固有failure witness
- 欠落主体の責任非代行とfunctional-equivalent leak検査

P8では次を追加する。

- full C/J/M一周期authority trace
- M updateを介した二周期behavioral delta
- P-only / J-only / M-only controlled causal isolation
- hidden-global-state不在とwrite/emit越境negative test

P9では次を追加する。

- 全8 subsetの有限・重複なし列挙
- full setだけPASSするmachine-readable certificate
- single/pair removal witnessとG1〜G5実測の整合
- functional-equivalent leak 0とcertificate deterministic rebuild

P4以降の固定test IDと反証条件は
`docs/architecture/AGI_TEST_MATRIX.md`を正本とする。

未実行の検証を `PASS` と書いてはいけません。環境不足、依存不足、credential不足、製品回帰を区別します。

## 10. Git境界

- ローカル・リモートの継続branchは`main`だけとする
- ユーザーが明示的に方針を変更しない限り、作業branchとPRを作成しない
- branch操作やpushの前に`origin/main`を取得し、local/remote差分を確認する
- 関連gateを通し、ユーザーがcommit / pushを許可した場合だけ`main`へ直接反映する
- main-only運用を、無関係な変更の混入や検証省略の理由にしない
- 無関係な既存変更をstage・削除・整形しない
- `reset --hard`、`clean -fd`、force pushを行わない
