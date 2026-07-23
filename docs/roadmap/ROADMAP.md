# ARC-3 AGI Agent ロードマップ

## 固定原則

- 最終目的: 未知ARC3タスクへ転用可能な汎用エージェント
- 現在の作業: 命令形保持体 `P` の形成とLayer-0への接続
- score最適化: sample完全攻略とアーキテクチャ固定後、ユーザーの明示切替後のみ
- 旧資産: 証拠として保持し、active runtimeへは選別移植
- 絶対順序: sample内完成 → 再現性固定 → 公式接続 → Kaggle提出経路 → 実提出

## 最小設計式

```text
C = Execute(L0, P)

AGI Kernel = Trinity(C, J, M)
```

- `L0`: 計算・参照・状態条件付け・変換・放出の機能機構
- `P`: 知識、能力、関係、変換規則、パラメータを保持する命令形情報体
- `J`: HDS判断主体
- `M`: HDSが引用する現行判断根拠の受動記憶

`L0`の機能実装だけでは計算主体`C`は成立しない。`P`を独立形成し、実際の計算で使用する必要がある。

---

## P0 — Restart Foundation（完了）

目的:

- 旧前提を切断し、正本・責任・停止・移植境界を固定する

成果物:

- root README / AGENTS
- system architecture / roadmap
- legacy inventory / migration manifest / source map
- protocol / typed IR / schema / rendered verifier / checkpoint
- pure-stdlib unit tests

完了ゲート:

- 全成果物が相互矛盾しない
- 新coreが旧task routerへ依存しない
- unit testsがPASS
- score主張を行わない

---

## P1 — Sample Execution Mechanism（完了）

目的:

- 保持済み公式sampleのlocal実行経路で、六つのLayer-0責任、HDS権限、受動memory、OFFLINE action / re-observationを動作させる

実装済み:

1. `SYMBOL_SPACE`: rendered frameとdeltaのidentity-free正規化
2. `CONTEXT_STATE`: bounded episode state
3. `TRANSFORM_OR_WORLD_MODEL`: 固定規則による暫定仮説生成
4. `CANDIDATE_SURFACE`: 固定規則による暫定候補生成
5. `FITTING_OR_SUCCESS_CRITERION`: `W=(X,R,Mc)`と評価軸
6. `EMISSION_INTERFACE`: HDS gate、action availability、OFFLINE step、feedback
7. action後のrendered再観測、transition verification、次cycleへの状態反映

完了証拠:

- full setと六つのsingle-callable removal
- HDS commandなしcompute、未承認write / emit、direct stepを拒否
- `OperationMode.OFFLINE`固定
- 保持済み25ゲームすべてで1 actionのHDS循環と再観測
- no-network、compile、unit、integration、lint、package gate

現行入口:

```bash
cd ARC-AGI-3-Agents
python sample_main.py --all-samples --max-actions 1
```

### P1の再分類

P1は次を証明した。

```text
Layer-0 execution mechanism
+ HDS / Memory authority loop
+ OFFLINE environment path
```

P1は次をまだ証明していない。

```text
C = Execute(L0, P)
```

現行 `roles.py` の手書き仮説、固定confidence、固定候補評価値は、独立した命令形保持体 `P` ではなく、コードへ埋め込まれた暫定seedである。

---

## P2 — Instruction Body Formation（現在）

目的:

- sampleから、Layer-0が参照・選択・合成・実行する命令形保持体 `P` を形成する
- `P`と判断根拠記憶`M`を分離する
- 同一Layer-0へ異なる情報体を交換できることを証明する

正本:

- `docs/architecture/P2_INSTRUCTION_BODY_FORMATION.md`

### 実装対象

1. `InstructionBody` interfaceと拡張contract
2. P-A: 記号・規則グラフ型
3. P-B: 小型パラメトリック／ニューラル型
4. sample trajectory collector
5. identity-free transition dataset
6. rule compiler / parameter trainer
7. P version bundle、digest、provenance
8. `PureLLMCompute`へのP必須接続
9. `roles.py`固定知識・固定候補値のPへの移動
10. P-A / P-B swap audit
11. 六責任 + P removal audit

### P-A

保持対象:

- object / role / relation
- action / effect / transition primitive
- precondition / goal / hazard
- support / contradiction / confidence
- falsifier / applicability / composition

### P-B

最低出力:

- action-conditioned effect prediction
- progress likelihood
- hazard likelihood
- information-gain estimate
- uncertainty
- candidate prior

sample trajectoryから実際に重み・パラメータを生成し、保存・再読込・digest照合できること。

### P2完了ゲート

- P-A / P-Bが同一契約で動く
- Layer-0コードを変更せずPを交換できる
- Pなしcomputeを拒否する
- 仮説・候補がP内容に依存する
- P / Mのversion・更新経路が分離される
- explicit compiler実行時だけP versionが変わる
- identity-free training-data auditが通る
- OFFLINE sample traceでP queryが記録される
- 六責任 + Pの除去監査が通る

P2では全sample攻略、公式接続、Kaggle提出を行わない。

---

## P3 — Complete Sample Solving（未開始）

開始条件:

- P2完了

目的:

- P-A / P-Bまたはそのhybridを使用し、全sample game / 全levelを完全攻略する

完了ゲート:

- 全sample levelを完了する
- 全gameでerrorがない
- `GAME_OVER`、timeout、無限loop、max-action停止を解消する
- 固定ID、replay暗記、answer mapだけへ依存しない
- 同一条件で再現できる
- 実行log、失敗signature、判断根拠を保存できる
- M更新が次判断へ反映される
- 安定した経験を次版Pへ明示的にcompileできる

P3完了前に公式環境へ接続しない。

---

## P4 — Freeze and Reproducibility Audit

目的:

- sample完全攻略状態をrelease candidateとして固定する

固定項目:

- dependencyとPython version
- 実行command、初期状態、設定値、action budget
- P format / version / digest / provenance
- HDS initial state
- M initial state / version
- 成功判定、log形式、packaging形式
- deterministic条件、regression suite
- 全sample完了証拠

完了ゲート:

- 公式環境との差分導入後もlocal完成状態へ戻せる
- 同一条件regressionが再現可能
- P / J0 / M0の初期状態bundleを再構築できる

---

## P5 — Official ARC Runtime Connection

開始条件:

- P3とP4が完了

実施順:

1. sample完成版を凍結
2. ARC Toolkit versionを固定
3. `OperationMode.OFFLINE`との差分を列挙
4. `listen_and_serve(competition_mode=True)`でKaggle相当REST環境をlocal再現
5. session、cookie、scorecard、reset、single-make制約を検証
6. `OperationMode.COMPETITION`へ接続
7. 全game一回作成制約で確認
8. 公式接続差分によるfailureだけを抽出

P5で基本agent設計、P、HDS、Mを作り直さない。

---

## P6 — Kaggle Submission Paths

目的:

- 同一Notebook version、同一output、同一messageを使う二経路を構築する

### 経路A — Kaggle CLI

```bash
kaggle --version
kaggle auth login
kaggle competitions list --group entered
kaggle competitions submit \
  <COMPETITION_SLUG> \
  -k <KAGGLE_USERNAME>/<NOTEBOOK_SLUG> \
  -v <NOTEBOOK_VERSION> \
  -f <OUTPUT_FILE> \
  -m "<SUBMISSION_MESSAGE>"
kaggle competitions submissions <COMPETITION_SLUG> -v
```

### 経路B — Kaggle公式MCP

```toml
[mcp_servers.kaggle]
url = "https://www.kaggle.com/mcp"
bearer_token_env_var = "KAGGLE_API_TOKEN"
required = true
default_tools_approval_mode = "writes"
tool_timeout_sec = 120
```

規則:

- 接続時のtool schemaを正本にする
- Notebook version、output、messageをCLIとMCPで照合
- secretをGitへ保存しない
- ユーザーの明示許可なしに実提出しない

完了ゲート:

- 認証、competition参加、rules受諾
- Notebook update / buildと必須output生成
- CLI commandとMCP toolが同一対象を指す
- submission status取得経路がある

---

## P7 — Actual Kaggle Submission

開始条件:

- sample完全攻略と回帰PASS
- 公式接続PASS
- Notebook buildとoutput検証PASS
- CLI / MCP両経路PASS
- ユーザーの実提出明示指示

規則:

- CLIまたはMCPを主経路、他方を代替経路
- 同一Notebook versionを重複提出しない
- competition / Notebook slug、version、output、message、timestamp、status、public score、error、経路、Git SHA、package digestを保存

---

## P8 — Official-result Optimization

開始条件:

- P7の公式評価結果がある
- ユーザーがphase切替を明示

対象:

- search budget、candidate ordering、threshold
- action efficiency、memory retrieval、runtime performance
- P compiler / parameter trainingの改善

禁止:

- task ID patch、replay暗記、benchmark leakage
- leaderboard scoreだけを根拠とした責任境界の削除

---

## P2 / P3共通禁止

- 公式API接続、`OperationMode.COMPETITION`
- Kaggle向けcode分岐、Notebook都合による設計変更
- Kaggle CLI / MCP提出
- leaderboard scoreによる採否
- sample未完状態での公式評価
- game/task/level IDをPへ埋め込むこと
- runtime中の無監査P自己更新

P5〜P7の工程を本書へ記録することは、工程の前倒し実行を意味しない。
