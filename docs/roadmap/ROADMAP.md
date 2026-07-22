# ARC-3 AGI Agent ロードマップ

## 固定原則

- 最終目的: 未知ARC3タスクへ転用可能な汎用エージェント
- 現在の作業: アーキテクチャ基盤の再構築
- score最適化: アーキテクチャ完成後、ユーザーの明示切替後のみ
- 旧資産: 証拠として保持し、active runtimeへは選別移植

## P0 — Restart Foundation（現在）

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

## P1 — Executable Kernel

目的:

- 六つのARC-native Layer-0責任をcallableな最小kernelとして閉じる

実装:

1. `SYMBOL_SPACE`: raw frameとdeltaの正規化
2. `CONTEXT_STATE`: bounded state store
3. `TRANSFORM_OR_WORLD_MODEL`: 複数仮説・反証更新
4. `CANDIDATE_SURFACE`: 複数候補とprovenance
5. `FITTING_OR_SUCCESS_CRITERION`: progress/risk/information/uncertainty
6. `EMISSION_INTERFACE`: available action・HDS gate・feedback

必須試験:

- 六役割full-set trace
- 各single-role removal witness
- HDS commandなしcompute拒否
- 未承認memory write / external emit拒否
- invalid lifecycle transition拒否

完了ゲート:

- `kernel_complete=true`
- role labelではなく機能喪失を観測できる
- offline / deterministic

## P2 — HDS–Compute–Memory Closed Loop

目的:

- 非対称三主体を一つの実行traceで閉じる

実装:

- HDS command envelope
- observation/memory view制限
- proposal、counter-hypothesis、closure decision
- versioned memory directive
- reobserve / recompute / suspend / stop / rollback
- external emit authorization

必須試験:

- stale observation
- version conflict
- contradiction accumulation
- budget exhaustion
- candidate rejection
- reobservation
- rollback boundary
- final emission veto

完了ゲート:

- commandから結果再観測まで一貫したtraceが残る
- 権限越境が機械的に拒否される

## P3 — Generic Solver Integration

目的:

- 独立kernelを公式 `ARC-AGI-3-Agents` runnerのprimary汎用coreへ接続する

統合順:

1. environment adapter
2. observation normalization
3. context / passive memory
4. hypothesis/world-model ensemble
5. candidate generation
6. closure/verifier/rollback
7. emission and feedback

隔離:

- task-specific policy
- replay
- literal action sequence
- source-assisted route

完了ゲート:

- task/game/level IDなしで起動・停止・再観測できる
- 複数候補をHDSが比較・拒否できる
- 汎用coreを外して旧routerへ暗黙fallbackしない

## P4 — Architecture Completion Audit

必須監査:

- six-role functional removal
- HDS authority / Trinity independence
- no autonomous memory / no autonomous output
- runtime identity / replay / literal dependency
- candidate / verifier / rollback / emission integration
- deterministic / offline / packaging
- evidence provenance and SUSPEND behavior

完了ゲート:

- `maximum_agent_complete=true`
- 未閉包項目がbounded `SUSPEND`として列挙される
- task-specific経路が標準coreから除去またはquarantineされる

## P5 — Benchmark Re-establishment

目的:

- 新リポジトリの同一条件baselineを確立する

固定項目:

- code commit
- dependency lock
- dataset/environment digest
- seed
- action budget
- memory initial state
- evaluation command
- machine/runtime条件

報告:

- completed levels
- score formulaとscore
- errors
- GAME_OVER
- maxed-out
- NOT_FINISHED
- elapsed time / action count
- artifact digest

過去の `46/183`、`97/183`、`6/183` は新baselineへ自動継承しません。

## P6 — Capability Expansion

優先順:

- 観測・object permanence
- delayed visibility / stale frame
- spatial/topological model
- symbolic/relational model
- phase/timer/resource model
- multi-step bounded planning
- counterfactual probes
- failure compression and reopen conditions
- cross-task memory compilation

各能力は少なくとも二つの異なるtask familyで転用可能性を検証します。

## P7 — Optimization

開始条件:

- P4完了
- P5 baseline固定
- ユーザーの明示許可

対象:

- search budget
- candidate ordering
- thresholds
- action efficiency
- memory retrieval
- runtime performance

禁止:

- task ID patch
- replay memorization
- benchmark leakage
- scoreだけを根拠とした責任境界の削除
