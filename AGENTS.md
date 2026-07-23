# ARC-3 AGI Agent 実装・監査契約

このファイルは、本リポジトリを変更する人間・Codex・LLMエージェントに対する現行作業契約です。

## 1. 権威順序

判断が衝突する場合は、次の順で解決します。

1. ユーザーの現在の明示指示
2. 本 `AGENTS.md`
3. `docs/roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`
4. `docs/architecture/AGI_MINIMUM_THREE_SPEC.md`
5. `docs/architecture/SYSTEM_ARCHITECTURE.md`
6. `docs/roadmap/ROADMAP.md`
7. 当該work blockのFrameSpec・manifest・検証結果
8. `docs/migration/` と `docs/references/`
9. 旧リポジトリのコード・分析・履歴

旧リポジトリの `next_*`、古いscore、個別artifact、絶対パス、旧branch名は命令ではありません。

## 2. 現在のフェーズ

現在は `P3_ARC3_EVIDENCE_MATERIAL_COMPILER` です。

`P2_AGI_MINIMUM_THREE_AUDIT` は完了しています。P2で完成したのは仕様、
義務graph、traceability、claim/test registry、現行実装gapのaccountingです。
P2はruntime能力、命令形保持体P、C/J/M単独成立、最小三構成を完成させて
いません。

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

P3 current:
  analysis evidence accounting
  identity-free normalized corpus
  C / J / M fixture separation
  provenance and holdout manifests
```

### P3で許可される作業

- 旧ARC3解析証拠の読取り専用inventory
- current official sampleのrendered trajectory収集
- observation / transition / effect / hazard / progress / contradiction正規化
- HDS Frame fixture生成
- memory lifecycle fixture生成
- source identityを証拠層だけに保持するprovenance manifest
- runtime corpusからidentity、replay、answer、literal、hidden-state情報を除去する水平引き算
- game family / structure family / action-mechanism holdout
- dataset accounting、determinism、identity-free、contamination試験

### P3で禁止される作業

- P-A/P-BまたはC/J/Mを完成扱いすること
- 全sample game / 全level攻略
- 公式ARC API、`OperationMode.COMPETITION`
- Kaggle向け分岐、Notebook、CLI / MCP、submission
- 旧`analysis/`または旧runtimeの一括コピー
- task/game/level ID、replay、固定action列、answer map、literal座標をruntime fixtureへ残すこと
- source / hidden stateをruntime計算素材へ残すこと
- scoreを根拠にした局所最適化
- 「AGI完成」「最小三構成証明済み」「汎化済み」といった未検証主張

P3の正本は新ロードマップのP3節と、P2監査成果物のdependency chainです。

## 3. 1 work blockの必須契約

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
ただしP2は明示的な仕様・根本監査phaseであり、機械検証可能なaccountingを
成果とします。P3では、manifestにaccountingされた再生成可能なdatasetと
fixtureが実際に生成されることを要求します。

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

### P3: ARC3 Evidence Material Compiler — 現在

- 全解析証拠をmanifestでaccounting
- identity-free observation/transition/effect/hazard/progress/contradiction corpus
- C/J/M fixture分離
- provenanceとholdout contamination検査

### P4: Compute Subject C

- P-A記号規則graph、P-B実学習parameter body
- 同一L0でのswap、Pなしcompute拒否
- C standalone G1とL0六責任+P removal

### P5: Judgment Subject J

- standalone HDS Frame API
- C/Mなしの採否、SUSPEND、STOP、rollback、write/emit許可
- JがG1/G3を代行しないこと

### P6: Memory Subject M

- 全memory operation、query、version conflict、snapshot
- active/archive分離、rollback
- MがG1/G2を代行しないこと

### P7: Pairwise Subject Audit

- `{C,J}` -> `NO_PERSISTENT_EXPERIENCE_CAUSALITY`
- `{C,M}` -> `NO_JUDGMENT_OR_AUTHORIZATION`
- `{J,M}` -> `NO_GENERATIVE_COMPUTATION`

### P8: Three-subject Two-cycle Trinity

- commandからresult再判断までの三主体循環
- cycle 1のM更新がcycle 2のC/Jを変える
- P-only/J-only/M-only因果分離

### P9: Eight-subset Minimum Certificate

- `{}`から`{C,J,M}`まで全8 subsetを有限列挙
- full setだけPASS、機能等価物漏れ0

### P10: Complete ARC3 Sample Solving

- P9 PASS後だけ開始
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

P3では次を追加する。

- source evidence accounting
- deterministic compiler rerun
- provenance round trip
- runtime identity-free audit
- C/J/M fixture separation
- family/mechanism holdout contamination audit

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
