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

`P1_SAMPLE_EXECUTION_KERNEL`は完了しています。P2は未開始です。
ユーザーが次フェーズを明示するまでは、P1境界の監査・回帰修正だけを行います。

許可される作業:

- 六つのARC-native責任をcallableにするkernel
- HDS command、候補採否、SUSPEND、STOP、write、emit境界
- bounded context、受動memory、in-memory / OFFLINE sample emission adapter
- 決定論的なfull-set試験、除去試験、権限拒否試験
- 保持済み公式sampleを`OperationMode.OFFLINE`だけで実行するP1監査
- sample observationから再観測、context、memory、次判断までの有界循環

禁止される作業:

- P2の全sample game / 全level攻略
- 公式ARC API接続、`OperationMode.COMPETITION`
- Kaggle向け分岐、Notebook、CLI / MCP提出
- 旧runtimeの一括コピー
- task/game/level別ルータの再導入
- replay、固定action列、answer map、literal座標の汎用能力化
- scoreを根拠にした閾値調整・局所最適化
- 新しいbenchmark値を同一条件証拠なしで正本化
- 「AGI完成」「満点対応」「汎化済み」といった未検証主張

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

文書追加だけでruntime能力が変わらない場合は、実装前進と記録しません。P0の文書・型・試験は閉じた基盤であり、P1ではcallableな循環と機能除去証拠を要求します。

## 4. 非対称権限

```text
HDS command
  -> Pure-LLM computation / proposal
  -> HDS judgment
  -> authorized MEMORY_WRITE or EXTERNAL_EMIT
  -> result observation
  -> HDS reevaluation
```

- Pure-LLM計算面: 計算・候補提案・許可済み操作の実行のみ
- HDS: 命令、採否、SUSPEND、停止、rollback、記憶更新許可、外部放出許可
- Memory: 受動保持。自律的に計算・書換え・放出しない
- Environment adapter: HDS許可済みemission以外から直接操作しない

この境界がコード上で拒否可能になっていない場合、適合とは認めず `SUSPEND` します。

## 5. ARC実行時の禁止入力

標準solver coreは次へ依存してはいけません。

- game/task/level IDによるaction選択
- replay index lookup
- 固定action sequence、固定keyboard script
- answer map、literal coordinate table
- source state、hidden state、evaluator内部状態
- ファイル名・task名による暗黙routing
- 外部API、internet、secret、実行時LLM呼出し

公式環境ソースや既知解答を解析時に読む場合も、runtimeへ移せるのは現在観測・action/effect履歴・再利用可能な遷移・verifier・rollback条件から再導出できる構造だけです。

## 6. 移植規則

旧資産は次の4分類で扱います。

- `ADAPT`: 小さく独立し、責任境界と試験を保てるもの
- `REFERENCE`: 設計・証拠として読むが、active runtimeへ直接入れないもの
- `QUARANTINE`: 比較・失敗解析専用。標準経路から隔離するもの
- `REJECT`: 旧前提、重複、汚染、非再現、禁止入力を含むもの

一括ディレクトリコピーは禁止します。各移植には元path、元commit、変更点、試験、残存リスクを記録します。

## 7. 段階ゲート

### P0: Foundation

- 型、契約、権限、停止、引用元が固定される
- 単体試験が決定論的に通る
- benchmark改善は要求しない

### P1: Sample Execution Kernel

- 六つのARC-native責任がcallableになる
- 各責任に除去証人がある
- HDS未承認の計算・write・emitが拒否される
- 保持済みsampleを`OFFLINE`で実行し、結果を再観測する
- 状態更新が次のHDS判断へ入力される
- 標準online runner、公式API、Kaggle経路を変更しない

### P2: Complete Sample Solving

- 全sample game / 全levelを完了する
- GAME_OVER、timeout、無限loop、max-action停止を解消する
- ID、replay、answer mapへ依存せず、同一条件で再現する
- 実行log、失敗signature、判断根拠、状態更新を保存する

### P3: Freeze and Regression Audit

- P2完了状態の依存、Python、command、初期状態、budgetを固定する
- 成功判定、log、packaging、determinism、regressionを固定する
- 公式接続差分を導入する前にlocal完成状態へ戻せるようにする

### P4: Official ARC Connection

- P2とP3の完了後だけ開始する
- `OFFLINE`との差分を列挙し、Kaggle相当REST環境をlocal再現する
- session、cookie、scorecard、reset、single-make制約を検証する
- 基本エージェント設計を作り直さず`COMPETITION`へ接続する

### P5: Kaggle Submission Paths

- Kaggle CLIとKaggle公式MCPの二経路を構築する
- 同一Notebook version、output、messageを照合する
- secretをGitへ保存しない
- ユーザーの明示許可なしに実提出しない

### P6: Actual Submission

- P2〜P5の全gateとユーザーの明示指示を満たした場合だけ実行する
- 同一Notebook versionを重複提出しない
- submission、score、error、commit、package digestを保存する

### P7: Official-result Optimization

- P6の公式評価結果を用いる
- leaderboard scoreだけで責任境界を削除しない
- ユーザーの明示的phase切替後だけ開始する

## 8. 検証規約

最低限:

```bash
cd ARC-AGI-3-Agents
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests/unit
ruff check arc3_agi_agent agents/__init__.py agents/recorder.py tests/conftest.py tests/unit
```

runtime接続以後は、対象試験に加えてoffline、deterministic、禁止入力、secret、rollback、emission gate、同一条件benchmarkを検査します。

P1のsample実行gate:

```bash
cd ARC-AGI-3-Agents
python -m unittest discover -s tests/integration \
  -p "test_offline_sample_runner.py" -v
python sample_main.py --all-samples --max-actions 1
```

この1-action smokeはP1の実行経路証拠であり、P2のlevel攻略数へ加算しません。

未実行の検証を `PASS` と書いてはいけません。環境不足、依存不足、credential不足、製品回帰を区別します。

## 9. Git境界

- 無関係な既存変更をstage・削除・整形しない
- `reset --hard`、`clean -fd`、force pushを行わない
- 1 PRは1つの段階目的に限定する
- migration PRでは旧runtimeの機能追加やscore調整を混ぜない
