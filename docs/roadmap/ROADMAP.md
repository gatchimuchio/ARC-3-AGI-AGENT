# ARC-3 AGI Agent ロードマップ

## 固定原則

- 最終目的: 未知ARC3タスクへ転用可能な汎用エージェント
- 現在の作業: アーキテクチャ基盤の再構築
- score最適化: アーキテクチャ完成後、ユーザーの明示切替後のみ
- 旧資産: 証拠として保持し、active runtimeへは選別移植

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

## P1 — Sample Execution Kernel（完了）

目的:

- 保持済みARC-AGI-3公式sampleのlocal実行経路で、六つのLayer-0責任、
  HDS判断主体、Pure-LLM計算主体、受動memoryを実動agentとして閉じる

実装:

1. `SYMBOL_SPACE`: rendered frameとdeltaのidentity-free正規化
2. `CONTEXT_STATE`: bounded episode state
3. `TRANSFORM_OR_WORLD_MODEL`: 複数仮説と反証条件
4. `CANDIDATE_SURFACE`: action / probe / control候補とprovenance
5. `FITTING_OR_SUCCESS_CRITERION`: `W=(X,R,Mc)`と十評価軸
6. `EMISSION_INTERFACE`: HDS gate、action availability、OFFLINE step、feedback
7. action後のrendered再観測、transition verification、次cycleへの状態反映

完了ゲート:

- full setと六つのsingle-callable removalが固有証人を出す
- HDS commandなしcompute、未承認write / emit、direct stepを拒否する
- `OperationMode.OFFLINE`以外をP1入口で拒否する
- game/task/level ID、replay、固定列、answer map、literal座標表をpolicyへ渡さない
- 保持済み25ゲームすべてで1 actionのHDS循環と再観測が成立する
- network requestを発生させない
- compile、unit、integration、lint、package gateが通る

現行入口:

```bash
cd ARC-AGI-3-Agents
python sample_main.py --all-samples --max-actions 1
```

このsmokeは実行経路だけの証拠であり、level攻略数、完全攻略、汎化scoreではありません。
既存のHTTP / online runnerのaction-selectionは変更しません。

## P2 — Complete Sample Solving（未開始）

目的:

- P1実行核を使い、全sample game / 全levelを完全攻略する

完了ゲート:

- 全sample levelを完了する
- 全gameでerrorがない
- `GAME_OVER`、timeout、無限loop、max-action停止を解消する
- 固定ID、replay暗記、answer mapだけへ依存しない
- 同一条件で再現できる
- 実行log、失敗signature、判断根拠を保存できる
- 状態更新が次の判断へ実際に反映される

P2完了前に公式環境へ接続しません。

## P3 — Freeze and Reproducibility Audit

目的:

- sample完全攻略状態をrelease candidateとして固定する

固定項目:

- dependencyとPython version
- 実行command、初期状態、設定値、action budget
- 成功判定、log形式、packaging形式
- deterministic条件、regression suite
- 全sample完了証拠

完了ゲート:

- 公式環境との差分導入後もlocal完成状態へ戻せる
- 同一条件regressionが再現可能である

## P4 — Official ARC Runtime Connection

開始条件:

- P2とP3が完了している

実施順:

1. sample完成版を凍結する
2. ARC Toolkit versionを固定する
3. `OperationMode.OFFLINE`との差分を列挙する
4. `listen_and_serve(competition_mode=True)`でKaggle相当REST環境をlocal再現する
5. session、cookie、scorecard、reset、single-make制約を検証する
6. `OperationMode.COMPETITION`へ接続する
7. 全gameを一回だけ作成する制約で確認する
8. 公式接続差分によるfailureだけを抽出する

P4で基本agent設計を作り直しません。

## P5 — Kaggle Submission Paths

目的:

- 同一Notebook version、同一output、同一messageを使う二経路を構築する

経路A — Kaggle CLI:

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

経路B — Kaggle公式MCP:

```toml
[mcp_servers.kaggle]
url = "https://www.kaggle.com/mcp"
bearer_token_env_var = "KAGGLE_API_TOKEN"
required = true
default_tools_approval_mode = "writes"
tool_timeout_sec = 120
```

- 接続時のtool schemaを正本とする
- `save_notebook`と`create_code_competition_submission`の実在・引数を再取得する
- CLIとMCPのNotebook version、output、messageを照合する
- secretをGitへ保存しない
- ユーザーの明示許可なしに実提出しない

完了ゲート:

- 認証、competition参加、rules受諾が確認できる
- Notebook update / buildと必須output生成が成功する
- CLI commandとMCP toolが構成でき、同一対象を指す
- submission statusを取得できる

## P6 — Actual Kaggle Submission

開始条件:

- sample完全攻略と回帰がPASS
- 公式接続がPASS
- Notebook buildとoutput検証がPASS
- CLI / MCP両経路がPASS
- ユーザーが実提出を明示指示している

規則:

- CLIまたはMCPを主経路、他方を代替経路にする
- 同一Notebook versionを重複提出しない
- competition / Notebook slug、version、output、message、timestamp、status、
  public score、error、経路、Git SHA、package digestを保存する

## P7 — Official-result Optimization

開始条件:

- P6の公式評価結果がある
- ユーザーがphase切替を明示している

対象:

- search budget、candidate ordering、threshold
- action efficiency、memory retrieval、runtime performance

禁止:

- task ID patch、replay暗記、benchmark leakage
- leaderboard scoreだけを根拠とした責任境界の削除

## P1 / P2共通禁止

- 公式API接続、`OperationMode.COMPETITION`
- Kaggle向けcode分岐、Notebook都合による設計変更
- Kaggle CLI / MCP提出
- leaderboard scoreによる採否
- sample未完状態での公式評価

P4〜P6の工程を本書へ記録することは、工程の前倒し実行を意味しません。
