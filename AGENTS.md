# ARC3 Completion Agent 製品開発契約 rev4

このrepositoryの最終成果物は、ARC3公式環境を同一AGI構造で自律完遂する実行可能製品`ARC3CompletionAgent`である。公式サンプル25 game／183 levelは必須の既知サンプル回帰であり、それだけをAGI完成扱いしない。

HDS分析、教師軌道分解、構造データ、命令形P、J設定、M0、試験reportは製品を成立させる素材・手段・内部部品であり、それ自体を開発endpointとしない。

## Authority

1. Ownerの現在の明示指示
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/architecture/工学的AGI実装仕様書_v0_2.md`
5. `docs/strategy/ARC3_AGIエージェント_製品仕様書_rev4.md`
6. `docs/roadmap/ARC3_AGIエージェント_製品開発ロードマップ_rev4.md`
7. `control/rev4/CURRENT_TASK.json`
8. 旧rev3／P0〜P22／S0〜S6は履歴・再利用資産

上位のAGI／HDS正本を、ARC3製品仕様、roadmap、current taskが上書きしてはならない。規範権威と作業順序を分離し、`control/rev4/CURRENT_TASK.json`は作業対象を選択するだけとする。

現在selectorは`control/rev4/CURRENT_TASK.json`の一つだけである。`control/rev3/REV3_CURRENT_SELECTOR.json`というlegacy filenameは履歴snapshotとして保持するが、現在phase、runtime activation、作業許可を与えない。分類正本は`control/rev4/LEGACY_REV3_CLASSIFICATION.json`とする。

## Product Endpoint

```text
ARC3CompletionAgent
→ official EnvironmentWrapper
→ observe FrameDataRaw
→ C = Execute(L0, P)
→ J_hds judges
→ M updates
→ emit one legal GameAction
→ repeat
→ known sample 25/25 WIN and 183/183 complete
→ same active artifact genericity and unused locked evaluation
→ official full completion
```

既知サンプル回帰条件:

```text
one runnable product artifact
one active C/J/M/P runtime
25 / 25 official sample games WIN
183 / 183 levels complete
no manual per-step intervention
no fixed trajectory playback
```

製品完成条件は上記に加え、同一active artifactによる汎用性、未使用locked evaluator完遂、package identity、公式output bytes／score／full scope完遂を全て要求する。別artifactの成果合算は禁止する。

## Current Work

```text
M3_INTEGRATED_AGI_CAPABILITY
```

M4／M5証拠は25/25 `WIN`、183/183 level、10,733 action、runtime failure signature 0の既知サンプル／package回帰として保持する。active product P／J0／M0は七つのdevelopment transformation worldを7/7完遂した。一方、現行active Pは全teacher parameterを継承し、CVは25 holdout中完遂0、sealed証拠はactive Pとdigest不一致である。したがってM3を継続し、汎用性と同一artifact評価を修正する。

現在の機械検証gateは次である。

```text
python scripts/validate_rev4_product_governance.py
python scripts/build_product_completion_audit.py --check
```

旧`validate_rev3_governance.py`はrev3履歴snapshotの整合だけを検査し、current selectorを決定しない。

現在実装・検証する。

1. active productと同じmodel family／resource contractによるCV
2. semantic transformed-environment completion
3. 同一frozen P／J0／M0による未使用locked evaluator完遂
4. 既知25/25／183/183回帰の維持
5. 汎用性成立後のwheel／clean install／Notebook再固定
6. 外部Kaggle実行はOwnerの現在の明示授権後のみ実行

## Verified Product Gaps

```text
B-01 legacy generic path budget 128; product path closed at 4096
B-02 closed in M2: teacher-derived compiled product P is runtime-bound
B-03 closed in M2: non-compatibility product P-IR is runtime-bound
B-04 closed in M1: all temporal action frames, final composite and history represented
B-05 closed in M1: ACTION6 covers seven bounded spatial affordance classes
B-06 reopened in M3: online trace exists, unknown-state capability is unproven
B-07 known-sample regression: 25/25 WIN, 183/183, 10,733 actions
B-08 external Kaggle write requires current Owner authorization
B-09 open: active transformation 7/7、CV 0/25、sealed active-P mismatch
```

## Product Architecture

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
Product = Official Adapter + AGI Kernel + Product Runtime + Product Bundle
```

- C: representation、hypothesis、counter-hypothesis、prediction、candidate、probe、plan
- J: HDS purpose、frame、gate、selection、action、rollback、memory update、next question、stop
- M: active judgment grounds, revised by experience
- P: Layer-0が実行するARC3能力本体
- Adapter: official I/O conversion only; not a subject

Cは最終採否・外部action・active memory commitを行わない。J以外の外部action経路を禁止する。

## HDS Usage

HDSは開発成果物ではなく、製品Jと開発時failure分解の方法である。

```text
F   observe/frame
Md  model alternatives, counter-hypotheses, candidates
Cm  compare, gate, decide
U   attribute result, revise P/J/M or product component
```

教師素材のHDS解釈は、P／J0／M0へコンパイルされ製品で使われる範囲だけ実施する。

## Product-First Milestones

```text
M0 Product baseline / blockers
M1 Official product runtime
M2 Product capability bundle P/J0/M0
M3 Integrated AGI capability
M4 Full-sample repair loop
M5 Product closure / packaging
```

全milestoneでrunnable `ARC3CompletionAgent`を保持する。reportだけ、schemaだけ、evidenceだけ、approvalだけのmilestoneを作らない。

## Allowed

- 既知回答・成功軌道・raw recording・canonical trajectoryの能力構築利用
- environment sourceを開発時の機構確認へ利用
- 最大情報から構造を抽出し、製品runtimeでidentity／replay依存を減算
- PH-D05 corpus、P16〜P21 substrate、P-IR、C/J/M、official adapterの再利用
- 製品code、bundle、tests、runner、failure repairの連続実行
- failureからC／J／M／P／Adapter／Resourceへ戻ること

## Forbidden

- 新repository作成
- HDS蒸留／構造抽出を最終製品扱いすること
- productへ接続しない大量analysis artifact
- governance-only phase
- action ID／game ID／level IDによる完成trajectory routing
- fixed answer playbackをAGI能力と数えること
- current product baseline測定前の抽象的な完成claim
- 128 action固定の維持
- Jを迂回する外部action

## Progress Metrics

```text
games started
games WIN
levels completed
failure classes
actions used
resource stop count
memory-caused behavior change
regressions
```

test数、schema数、commit数、digest数を製品進捗と数えない。

## Artifact Rule

新artifactは次のいずれかの場合だけ作る。

```text
product runtimeが直接読む
product acceptanceが直接読む
product failure repairに直接使う
official packageに必要
```

## Owner Boundary

Ownerは製品定義、戦略変更、Product Bundle freeze、公式提出を決定する。内部実装・試験・修正は、明示停止または重大な仕様衝突まで継続する。
