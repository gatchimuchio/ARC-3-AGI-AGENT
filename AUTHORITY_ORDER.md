# ARC3 rev3 Authority Planes

- strategy: `ARC3_HDS_DISTILLATION_FIRST_AUTONOMOUS_COMPLETION_SPEC_REV3`
- strategy status: `PROPOSED_PENDING_OWNER_APPROVAL`
- installation status: `NOT_INSTALLED`
- current work class: `REV3_DOCUMENT_CORRECTION_ONLY`
- active phase: `NONE`
- `PH-R00`: `SUSPEND`
- final selector / Meta-J: `大平鉄兵`
- implementation role / Meta-C: `Codex`

この文書は規範権威と実行制御を分離する。実行制御、code、tests、tools、generated content、memory、historical artifactsは規範権威の意味を変更できない。

## Normative Authority

1. Current explicit instruction from Owner 大平鉄兵
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/architecture/工学的AGI実装仕様書_v0_2.md`
5. `docs/strategy/ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md`
6. `docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md`
7. `docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md`
8. `docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`

## Execution Control

1. Current explicit instruction from Owner 大平鉄兵
2. root `AGENTS.md`
3. Owner-approved active phase state backed by `OwnerDecisionCapture`
4. Current Work Block Frame
5. Committed evidence

Past phase states, ApprovalRecords, transitions, artifact-local `next_*`, and P0-P22 artifacts are evidence only and are not current selectors.

## HDS dependency order

Within an Owner-approved Track D Work Block, after applying Normative Authority:

1. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
2. `docs/references/HDSフレーム_rev3_1_外向け仕様.md`
3. `docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md`
4. `docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`
5. Owner decision captured for the exact target artifact
6. Phase Frame, Manifest, and Run Report
7. `gatchimuchio/HDS-BlackBox-Translator` at the locked commit
8. rev1 documents
9. Implementer inference

`docs/references/HDS_SelfContained_Prompt_v1_2_utf8bom.txt` is a locked prompt dependency. It does not outrank the internal or external HDS specifications.

## Historical pre-audit evidence

The following record and its downstream PH-D00A evidence are preserved but classified as:

```text
HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE
```

- `control/rev3/OWNER_APPROVAL_RECORDS/PH-R00.json`
- `artifacts/source_content_manifests/hds_dependencies.json`
- `artifacts/reports/dependency_audit.json`
- `control/rev3/D00A_PHASE_STATE.json`

The earlier interpretation of generic “continue” instructions as PH-R00 acceptance or continuous phase approval is not valid activation evidence under the corrected contract.

## Current gate

```text
REV3 correction evidence
→ Owner explicit approval for the exact correction artifact
→ PH-R-1 Strategy Installation
→ Owner authorization for PH-R00
```

Until these transitions are captured, all PH-R00 and downstream work remains suspended. Missing or mismatched authority is visible failure; it is not repaired by lowering a gate or reusing historical approval.
