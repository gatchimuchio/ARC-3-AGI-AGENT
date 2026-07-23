# ARC-3 AGI Agent 実装・監査契約

このファイルは、本リポジトリを変更する人間・Codex・LLMエージェントに対する現行作業契約です。

## 1. 権威順序

判断が衝突する場合は、次の順で解決します。

1. ユーザーの現在の明示指示
2. 本 `AGENTS.md`
3. `docs/architecture/SYSTEM_ARCHITECTURE.md`
4. `docs/roadmap/ROADMAP.md`
5. 当該work blockのFrameSpec・manifest・検証結果
6. `docs/migration/` と `docs/references/`
7. 旧リポジトリのコード・分析・履歴

旧リポジトリの `next_*`、古いscore、個別artifact、絶対パス、旧branch名は命令ではありません。

## 2. 現在のフェーズ

現在は `P2_INSTRUCTION_BODY_FORMATION` です。

`P1_SAMPLE_EXECUTION_KERNEL` は完了しています。ただしP1で完成したのは、六つのLayer-0実行責任、HDS権限、受動memory、OFFLINE sample接続であり、純粋LLM計算主体全体ではありません。

現行 `PureLLMCompute` は、`roles.py` に埋め込まれた固定規則を直接実行しています。Layer-0が参照・選択・合成して計算する独立命令形保持体 `P` は未実装です。

したがって現行分類は次です。

```text
P1 complete:
  Layer-0 execution mechanism
  HDS / Memory authority loop
  OFFLINE sample action / re-observation path

P2 current:
  executable instruction body P
  sample-derived information body formation
  L0 / P / M separation
  P-A symbolic body / P-B parametric body swap
```

### P2で許可される作業

- `InstructionBody`実体と拡張contract
- sample trajectoryのidentity-free収集・正規化
- P-A記号・規則グラフ型情報体
- P-B小型パラメトリック／ニューラル型情報体
- information-body compiler、version、digest、provenance
- `PureLLMCompute`を `P` 必須にするrefactor
- `roles.py`内の固定知識・候補値をPへ移す作業
- 同一Layer-0へのP-A / P-B swap試験
- 六責任に加えたP除去監査
- 保持済みsampleの`OperationMode.OFFLINE`経路でPが使用されることの検証

### P2で禁止される作業

- 全sample game / 全levelの完全攻略を完了扱いすること
- 公式ARC API接続、`OperationMode.COMPETITION`
- Kaggle向け分岐、Notebook、CLI / MCP提出
- 旧runtimeの一括コピー
- task/game/level別ルータの再導入
- replay、固定action列、answer map、literal座標の情報体化
- source / hidden stateのruntime利用
- runtime中の無監査P自己更新
- scoreを根拠にした局所最適化
- parameter数、学習データ数、情報体の存在だけによる能力主張
- 「AGI完成」「満点対応」「汎化済み」といった未検証主張

詳細指示は `docs/architecture/P2_INSTRUCTION_BODY_FORMATION.md` を正本とします。

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

文書追加だけでruntime能力が変わらない場合は実装前進と記録しません。P2では、`P`が実際の計算結果を変え、OFFLINE sample経路で参照されることを要求します。

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

### P2: Instruction Body Formation — 現在

- InstructionBody contractと実体
- P-A記号・規則グラフ
- P-Bパラメトリック／ニューラル情報体
- sample trajectoryからの再現可能なcompile / training
- 同一Layer-0でのswap
- Pなしcompute拒否
- P / M分離
- 六責任 + Pの除去監査

### P3: Complete Sample Solving

- 全sample game / 全levelを完了
- GAME_OVER、timeout、無限loop、max-action停止を解消
- ID、replay、answer mapへ依存せず同一条件で再現
- 実行log、失敗signature、判断根拠、状態更新を保存

### P4: Freeze and Regression Audit

- P3完了状態の依存、Python、command、初期状態、P version、M initial state、budgetを固定
- 成功判定、log、packaging、determinism、regressionを固定
- 公式接続差分を導入する前にlocal完成状態へ戻せるようにする

### P5: Official ARC Connection

- P3とP4の完了後だけ開始
- `OFFLINE`との差分を列挙し、Kaggle相当REST環境をlocal再現
- session、cookie、scorecard、reset、single-make制約を検証
- 基本エージェント設計を作り直さず`COMPETITION`へ接続

### P6: Kaggle Submission Paths

- Kaggle CLIとKaggle公式MCPの二経路
- 同一Notebook version、output、messageを照合
- secretをGitへ保存しない
- ユーザーの明示許可なしに実提出しない

### P7: Actual Submission

- P3〜P6の全gateとユーザーの明示指示を満たした場合だけ実行
- 同一Notebook versionを重複提出しない
- submission、score、error、commit、package digestを保存

### P8: Official-result Optimization

- P7の公式評価結果を用いる
- leaderboard scoreだけで責任境界を削除しない
- ユーザーの明示的phase切替後だけ開始

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

P2では上記に加え、次を必須とします。

- P schema / digest / provenance validation
- P-A / P-B swap test
- P removal witness
- P / M update-boundary test
- training / compilation reproducibility
- identity-free training-data audit
- OFFLINE sample traceでP queryが記録されること

未実行の検証を `PASS` と書いてはいけません。環境不足、依存不足、credential不足、製品回帰を区別します。

## 10. Git境界

- ローカル・リモートの継続branchは`main`だけとする
- ユーザーが明示的に方針を変更しない限り、作業branchとPRを作成しない
- branch操作やpushの前に`origin/main`を取得し、local/remote差分を確認する
- 関連gateを通し、ユーザーがcommit / pushを許可した場合だけ`main`へ直接反映する
- main-only運用を、無関係な変更の混入や検証省略の理由にしない
- 無関係な既存変更をstage・削除・整形しない
- `reset --hard`、`clean -fd`、force pushを行わない
