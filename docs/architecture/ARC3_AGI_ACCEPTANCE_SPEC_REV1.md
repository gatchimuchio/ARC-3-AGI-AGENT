# ARC3 AGI 受入仕様 rev1

> status: `HISTORICAL_NON_BLOCKING`
>
> P16以降の現行受入は
> `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`を正本とする。
> 本書の57項目PASSはrev1定義域の歴史的証拠であり、rev2のphase gate、
> generic completion、sealed single-artifact、official completionを成立させない。

- specification: `ARC3_AGI_ACCEPTANCE_SPEC_REV1`
- statuses: `PASS | HOLD | SUSPEND | FAIL | NOT_EVALUATED`
- blocking rule: 一件でも`PASS`以外なら公式接続を禁止する
- source authority: `ARC3_AGI_監査修正パッケージ_rev1.zip`

## 1. Runtime separation

```text
KnownSampleStudent
  = frozen S5 rendered-history MLP
  = known-sample regression baseline

GenericAGIRuntime
  = active pre-official generic path
  = no KnownSampleStudent / Teacher / game-specific fallback
```

## 2. Blocking requirement registry

### Claim

| ID | Requirement |
|---|---|
| `CLAIM-001` | 183/183をknown-sample closureとしてのみ表記する |
| `CLAIM-002` | structural、known-sample、operational、genericity、official compatibility、official scoreを分離する |
| `CLAIM-003` | P11 artifact、score、trace、digestを変更しない |

### Layer-0 and C

| ID | Requirement |
|---|---|
| `L0-001` | relation/goal-conditioned selective retrievalを実行し、除去で固有劣化する |
| `L0-002` | 非線形parameter Pを同一L0で交換でき、出力が変化する |
| `L0-003` | `represent→retrieve→model→predict→candidate`の有効直列深度をtraceする |
| `C-001` | baseline、alternative、counter/null等の独立仮説を最低2件生成する |
| `C-002` | 複数合法action時に意味的に異なる候補を最低2件生成する |
| `C-003` | Cは最終採否、external emit、active M commitを行わない |
| `C-004` | P除去・invalid化で固有witness付きFAILとなる |

### P

| ID | Requirement |
|---|---|
| `P-001` | addressable/state-dependent/composable/executable/versioned/digestable/provenance/deterministic/identity-free/swappable |
| `P-002` | Pはfinal authorityを持たず、J-only変更で決定が変わる |
| `P-003` | 25 gameを5-fold whole-game holdoutし、各gameを一度完全除外する |
| `P-004` | mechanism familyを完全holdoutし未知rule acquisitionを実行評価する |
| `P-005` | 未学習の合法available-actions surfaceを例外なく処理する |
| `P-006` | 七appearance/composition変換をenvironment completionで測る |
| `P-007` | frame/position/identity/contrast/removal/transformationの暗黙replay監査を行う |

### J_hds

| ID | Requirement |
|---|---|
| `J-001` | 継続状態、目的、採否、next question、action/update authorization、SUSPEND/stopを所有する |
| `J-002` | purpose/value/risk、X/R/Mc、evidence/resource/authority/open/stopを毎cycle保持する |
| `J-003` | ModelSetと適用可能なG00〜G15を実行する |
| `J-004` | C/P/M固定時にpurpose/risk/Mc/evidenceのJ-only変更で挙動が変わる |
| `J-005` | P高priorでも危険・未閉包・証拠不足をvetoできる |
| `J-006` | next question/observation/information/probe/stopを毎cycle生成する |
| `J-007` | Purpose/Mc/Counter/Suspend/Evidence/FailureUpdate/Projectionの各ablationが固有に壊れる |

### M_mem

| ID | Requirement |
|---|---|
| `M-001` | hypothesis/counter/contradiction/failure/procedure/rationale/open/rollbackを意味記憶として保持する |
| `M-002` | active/working/archive/sealedを分離しarchiveを自動引用しない |
| `M-003` | environment runでREVISE/REPLACE/INVALIDATE/MERGE/ROLLBACK/ARCHIVE/QUERYを観測する |
| `M-004` | action history固定・semantic Mのみ変更でC/Jが変わる |
| `M-005` | read/write ablationで改善が消え、rollbackで旧判断が戻る |
| `M-006` | old/new version、両証拠、scope、falsifier、authority、rollback pointerを記録する |

### Trinity and learning

| ID | Requirement |
|---|---|
| `TRI-001` | J commandからaction、attribution、M revision、next questionまで同一traceで閉じる |
| `TRI-002` | 上位目的だけで問い、計算、観測、行動、更新、停止を内部生成する |
| `LEARN-001` | M更新に帰属可能なfuture Frame/ModelSet/Commit/Stop変化を示す |
| `LEARN-002` | evidence→proposal→HDS compile→candidate P→blind holdout→promotion/rollbackを実行する |
| `LEARN-003` | P/J0/M0再起動後に獲得能力を初期状態から利用する |
| `LEARN-004` | logging/archive/unused/fixed-loop/behavior-invariant changeをlearningから除外する |

### Genericity

| ID | Requirement |
|---|---|
| `GEN-001` | 5-fold全てでcrash/leak/unknown-surface例外0かつ真のholdout progressを測る |
| `GEN-002` | mechanism holdoutでrandom固定policy超のprogressとhypothesis/probe/update traceを示す |
| `GEN-003` | COLOR/ROTATION/REFLECTION/LAYOUT/OBJECT_COUNT/ORDER/UNSEEN_COMPOSITIONを実environmentで実行する |
| `GEN-004` | freeze後、別processのsealed 3 gameでsource非参照・valid action・full trace・progressを示す |
| `GEN-005` | Generic失敗時もS5、Teacher、game-specific operatorへfallbackしない |

### Competition dry-run

| ID | Requirement |
|---|---|
| `OFF-001` | Competition adapterはremote/APIだけを使用しlocal sourceを読まない |
| `OFF-002` | runごとにscorecardを一件だけ開く |
| `OFF-003` | environmentごとにmakeを一回だけ行う |
| `OFF-004` | inflight scoreをruntime判断へ渡さない |
| `OFF-005` | RESETをlevel resetとして扱い`ONLY_RESET_LEVELS`に依存しない |
| `OFF-006` | 400分類、429 backoff、5xx/network bounded retry、exactly-once/dedupを実行する |
| `OFF-007` | game IDを作成adapter外のC/P/J/Mへ渡さない |
| `OFF-008` | OFF-001〜007のmock/staging content-bound reportを公式接続前に生成する |

### Resource, package, security, observability, regression

| ID | Requirement |
|---|---|
| `RES-001` | cold start/RSS/load/action p50-p95/total/package sizeを測る |
| `RES-002` | budget超過をbounded SUSPEND/STOPにする |
| `PKG-001` | reproducible runtime packageからtraining/Teacher/sealed sourceを除外する |
| `SEC-001` | secret/source-access/network-egress auditを通す |
| `OBS-001` | 全cycleのC/J/M/emission/result/attributionを追跡可能にする |
| `REG-001` | frozen P11証拠を変更しない |
| `REG-002` | KnownSampleStudent 183/183、RHAE、error/authority/leakを回帰する |
| `REG-003` | P/J/M変更ごとに変更対象外責任の非回帰を報告する |

## 3. Artifact contract

各machine-readable reportは最低限次を持つ。

```text
schema_version
code.commit
code.tree
input_artifact_digest
environment_manifest
seed
budget
command
status
failed_requirement_ids
content_digest
raw_evidence_pointers
```

`content_digest`は当該fieldを除くcanonical contentから計算する。文書、件数、
parameter数、単一happy path、scoreだけでは`PASS`にしない。

## 4. Final gate

```text
PRE_OFFICIAL_AGI_READY =
  CLAIM
  AND L0/C
  AND P
  AND J
  AND M
  AND TRI/LEARN
  AND GEN
  AND OFF_DRY_RUN
  AND RES/PKG/SEC/OBS
  AND REG
```

一件でも`FAIL`、`SUSPEND`、blocking `NOT_EVALUATED`、leak疑義、
unknown-action exception、J/M ablation無影響、P holdout非改善、P11回帰が
あれば、最終HDS出力は`SUSPEND`とし公式接続しない。
