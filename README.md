# ARC3公式サンプル汎用完遂AGI

ARC Prize 2026 / ARC-AGI-3公式サンプルを、**同一のC／J／M／P構造で自律完遂する製品`ARC3CompletionAgent`**を構築するrepositoryです。

## 当該開発の最終成果物

```text
ARC3CompletionAgent
=
official adapter
+ C = Execute(L0, P)
+ HDS judgement subject J
+ mutable memory subject M
+ product runtime
+ ARC3ProductBundle
```

当該開発の終了条件:

```text
25 / 25 official sample games = WIN
183 / 183 levels = COMPLETE
one product artifact
one active ProductBundle
no manual per-step intervention
no fixed successful-trajectory playback
no identity action router
clean-state repeat PASS
```

HDS解析、成功軌道、構造、P/J0/M0は製品能力を構築する素材・手段です。これらを作っただけでは開発完了ではありません。

## 現行正本 — 三点セット

1. [実装仕様書 rev5.1](docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev5_1.md)
2. [開発ロードマップ rev5.1](docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev5_1.md)
3. [ロードマップ準拠指示書 rev5.1](docs/instructions/ARC3公式サンプル汎用完遂AGI_ロードマップ準拠指示書_rev5_1.md)

補助正本:

- [開発実行契約](AGENTS.md)
- [Current Task](control/rev5_1/CURRENT_TASK.json)

ロードマップの全Pointには固有IDがあり、指示書の同一IDと一対一対応します。Point外作業、shell先行、runner先行、管理専用phaseを禁止します。

旧rev4／rev3、P0〜P22、S0〜S6は履歴・再利用資産であり、current selectorではありません。

## アーキテクチャ

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J_hds, M)
```

- `C`: 表現、仮説、反対仮説、予測、probe、計画、候補生成
- `J`: HDSによる目的、W=(X,R,Mc)、Gate、採否、action、rollback、M更新、停止
- `M`: 現行判断根拠の追加、修正、置換、無効化、rollback
- `P`: Layer-0が実行するARC3攻略能力

## ロードマップ

```text
M0 Capability basis + first AGI closure
→ M1 Capability-family expansion
→ M2 Full-sample product closure
→ M3 Generic / AGI conformance
→ M4 Product freeze and release
```

最初のbasis game攻略時点から、C／J／Mのオンライン循環、記憶因果、HDS承認actionを要求します。個別静的攻略を作った後でAGI化する順序は採用しません。

## 現在Point

```text
M0-P02_CAPABILITY_COVERAGE_MATRIX
```

M0-P01は既存substrateで充足済みです。新しいshell、runner、agent subclassは作りません。

現在は公式25 gameを浅く一巡し、basis set選定用の`CapabilityCoverageMatrix`一つを作成します。

観測項目:

```text
input modality
action surface
RESET / ACTION6 / ACTION7
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

## HDS更新順序

```text
実行経験
→ Runtime M / LOCAL_M
→ 複数Run・反証・削除試験
→ PROBATION_DEV
→ 独立Case・反例・regression
→ ACTIVE_DEV
→ 全数完遂・AGI適合監査
→ RELEASE_FROZEN P/J0/M0
```

一回の成功をrelease能力へ直接固定しません。

## Capability Closure Unit

全能力実装は次の単位で閉じます。

```text
product failure / missing capability
→ HDS F/Md/Cm/U
→ product capability change
→ integrated agent execution
→ behavior delta
→ regression
```

分析report、schema、shell、runner、testだけで終了しません。

## 保持済み素材

```text
official sample games             25
official sample levels            183
PH-D05 canonical frames            10,942
PH-D05 canonical success actions   11,574
action surface                     RESET, ACTION1..ACTION7
```

## 進捗指標

```text
games WIN
levels completed
Failure Signature reduction
ACTIVE_DEV CapabilityFamily count
P/J/M capability delta
memory-caused behavior change
regressions
```

test数、schema数、artifact数、commit数を製品進捗の代替にしません。
