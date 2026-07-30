# ARC3 rev3 Production Import Boundary

- phase: `PH-R00`
- boundary version: `arc3-rev3-production-import-boundary-v1`
- active production runtime: none
- capability claim: `NOT_ESTABLISHED`

## Purpose

PH-R00はAGI Runtimeを構築しない。将来のproduction completion pathが、
historical S5／P22資産をparent、active policy、fallbackとして選択できない境界だけを
固定する。

## Rev3 production entry condition

rev3 production selectionは次を全て必要とする。

```text
source_kind = DISTILLED_INITIAL_STATE_BUNDLE
structure_bundle_digest = content-bound
initial_state_bundle_digest = content-bound
owner_approval_digest = content-bound
runtime_artifact_digest = content-bound
fallback_source_kinds = empty
```

検証器:

```text
arc3_agi_agent.rev3_governance.require_rev3_production_selection
```

## Forbidden source kinds

```text
S5_RUNTIME
S5_COMPILED_POLICY
HISTORICAL_KNOWN_SAMPLE_STUDENT
P22_COMPILED_POLICY
P22_CV_ARTIFACT
REV1_GENERIC_RUNTIME
TEACHER_TRAJECTORY
```

## Forbidden production import roots

```text
compiled_policy
p22_evaluator
s5_authority
s5_compute
s5_policy
s5_runner
s5_runtime
s5_score_adapter
teacher
```

監査器:

```text
arc3_agi_agent.rev3_governance.audit_rev3_production_imports
```

## Historical namespace

既存のS5／P22 sourceとartifactは削除しない。用途を次へ限定する。

- historical regression
- failure analysis
- teacher compression baseline
- non-generalization witness

これらをimportする旧CLI／testはrev3 production entrypointではない。

## Infrastructure candidate finding

現行`p_bundle.py`はP22で追加されたcompiled-policy codecを直接importする。
したがって、現行generic packageをそのままrev3 production packageとして採用しない。
Track B/Aでdistilled ABIへ接続する前にcodec境界を再監査する。

PH-R00ではrev3 active runtimeを0とし、production selectionを上記guard以外から
成立させないことで、historical dependency countを0に保つ。

## Negative guarantees

- S5 fallbackを追加しない。
- compiled policyをdistilled assetと再分類しない。
- P22 scoreをPH-R00 acceptanceへ使用しない。
- Owner approvalをCodexが生成しない。
- missing digestをdefault値で補わない。

