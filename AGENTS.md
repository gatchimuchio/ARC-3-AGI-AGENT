# ARC3公式サンプル汎用完遂AGI 開発実行契約 rev5.1

このrepositoryの当該開発endpointは、ARC3公式サンプル25 game／183 levelを同一のC／J／M／P構造で自律完遂する実行可能製品`ARC3CompletionAgent`である。

HDS解析、成功軌道、構造、P/J0/M0、試験、reportは、製品能力を構築する素材・手段・内部部品であり、それ自体を開発endpointとしない。

## Authority

1. Ownerの現在の明示指示
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/architecture/工学的AGI実装仕様書_v0_2.md`
5. `docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev5_1.md`
6. `docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev5_1.md`
7. `docs/instructions/ARC3公式サンプル汎用完遂AGI_ロードマップ準拠指示書_rev5_1.md`
8. `control/rev5_1/CURRENT_TASK.json`
9. 旧rev4／rev3／P0〜P22／S0〜S6は履歴・再利用資産

上位AGI／HDS正本をARC3仕様が上書きしてはならない。仕様書、ロードマップ、指示書は三点一組であり、ロードマップPoint IDと指示書の指示IDが一致しない作業を開始してはならない。

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
→ 25/25 WIN and 183/183 complete
```

当該開発の終了条件:

```text
one runnable product artifact
one active ARC3ProductBundle
closed Trinity(C,J,M)
J authorizes every external action
M changes future computation or judgement
25 / 25 official sample games WIN
183 / 183 levels complete
no manual per-step intervention
no fixed trajectory playback
no identity action router
clean-state repeat PASS
```

## Current Point

```text
M0-P02_CAPABILITY_COVERAGE_MATRIX
```

M0-P01は既存substrateで充足済みであり、新しいshell、runner、agent subclass、packageを作ってはならない。

現在Pointでは、公式25 gameを浅く一巡し、次の能力面を一つの`CapabilityCoverageMatrix`へ記録する。

```text
input modality
action surface
RESET
ACTION6
ACTION7
render layer count
temporal / animation
delayed effect
phase change
long-horizon action count
rollback requirement
planning depth
spatial binding type
goal structure
```

深層HDS解析、全game構造抽出、P/J/M実装はM0-P03 basis選定前に開始しない。

## Fixed Architecture

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J, M)
Product = Official Adapter + AGI Kernel + Product Runtime
```

- C: representation、hypothesis、counter-hypothesis、prediction、candidate、probe、plan
- J: HDS purpose、W=(X,R,Mc)、gate、selection、action、rollback、memory update、next question、stop
- M: active judgment grounds, revised by experience
- P: Layer-0が実行するARC3能力本体
- Adapter: official I/O conversion only; not a subject

Cは最終採否、外部action、ACTIVE M commitを行わない。J以外の外部action経路を禁止する。

## HDS Run Contract

```text
F   observation / purpose / boundary / open terms
Md  baseline / alternatives / counter-hypotheses / predictions / plans
Cm  gates / selection / suspend / execute / stop
U   attribution / model revision / Failure Signature / memory update
```

一回の成功をrelease P/J0/M0へ直接昇格させない。

```text
Runtime M / LOCAL_M
→ PROBATION_DEV
→ ACTIVE_DEV
→ RELEASE_FROZEN
```

## Roadmap Discipline

各Pointは対応する指示書だけで実行する。

```text
M0 Capability basis + first AGI closure
M1 Capability-family expansion
M2 Full-sample product closure
M3 Generic / AGI conformance
M4 Product freeze and release
```

各CapabilityClosureUnitは次で閉じる。

```text
product failure / missing capability
→ HDS F/Md/Cm/U
→ product capability change
→ integrated agent execution
→ behavior delta
→ regression
```

分析report、schema、shell、runner、testだけで終了してはならない。

## Allowed

- 既知回答・成功軌道・raw recording・canonical trajectoryの能力構築利用
- environment sourceを開発時のmechanism確認へ利用
- 最大情報から構造を抽出し、製品runtimeでidentity／replay依存を減算
- PH-D05 corpus、既存C/J/M、P-IR、official adapterの再利用
- roadmap Point内での製品code、P/J/M、tests、failure repair
- failureから責任componentへ戻ること

## Forbidden

- 新repository
- 新しい空shell／agent subclass
- parallel runner／package path
- HDS解析・構造抽出・P生成を最終製品扱いすること
- Point外の先行実装
- 製品へ接続しない大量analysis artifact
- governance-only phase
- game／level ID、frame hash、trajectory indexによる答え選択
- fixed successful trajectory playback
- J bypass
- test数、schema数、commit数、digest数を進捗扱いすること

## Progress Metrics

```text
games WIN
levels completed
Failure Signature reduction
ACTIVE_DEV CapabilityFamily count
P/J/M capability delta
memory-caused behavior change
regressions
```

## Artifact Rule

新artifactは次のいずれかの場合だけ作る。

```text
次Pointが直接読む
product runtimeが直接読む
product acceptanceが直接読む
product failure repairに直接使う
official packageに必要
```

## Reporting

各Point終了時は、対応指示書の`PointReport`形式だけで報告する。

Ownerは製品定義、戦略変更、release ProductBundle freeze、公式提出を決定する。内部実装・試験・修正は、明示停止または重大な仕様衝突までロードマップ順で継続する。
