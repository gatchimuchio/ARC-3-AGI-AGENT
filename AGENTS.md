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

`P1_EXECUTABLE_KERNEL`は完了しています。P2は未開始です。
ユーザーが次フェーズを明示するまでは、P1境界の監査・回帰修正だけを行います。

許可される作業:

- 六つのARC-native責任をcallableにする独立kernel
- HDS command、候補採否、SUSPEND、STOP、write、emit境界
- bounded context、受動memory、in-memory emission adapter
- 決定論的なfull-set試験、除去試験、権限拒否試験
- 公式runnerを変更しないP1監査

禁止される作業:

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

### P1: Executable Kernel

- 六つのARC-native責任がcallableになる
- 各責任に除去証人がある
- HDS未承認の計算・write・emitが拒否される

### P2: HDS–Compute–Memory Closed Loop

- 複数循環のcommand、再観測、再計算、SUSPEND、STOPを閉じる
- stale observation、version conflict、rollback境界を機械検証する
- P1の非対称権限を維持する

### P3: Generic Integration

- 公式runnerで汎用coreがprimary candidate sourceになる
- task/replay/ID依存なしで起動・停止・再観測できる
- 同一条件の回帰評価を行う

### P4: Architecture Completion Audit

- six-role removal、Trinity独立性、禁止入力、rollback、emissionを再監査する
- 未閉包項目をbounded `SUSPEND`として列挙する

### P5: Benchmark Re-establishment

- 評価条件、seed、budget、初期状態、artifact digestを固定する
- previous/current/deltaと全副作用を報告する
- scoreだけでアーキテクチャ適合を証明しない

### Post-P5: Optimization

アーキテクチャ完成監査後、ユーザーが明示的にphaseを切り替えた場合だけ
開始します。

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

未実行の検証を `PASS` と書いてはいけません。環境不足、依存不足、credential不足、製品回帰を区別します。

## 9. Git境界

- 無関係な既存変更をstage・削除・整形しない
- `reset --hard`、`clean -fd`、force pushを行わない
- 1 PRは1つの段階目的に限定する
- migration PRでは旧runtimeの機能追加やscore調整を混ぜない
