# ARC3 HDS蒸留先行 戦略改定資料 INDEX

- Package status: `OWNER_APPROVED`
- Installation status: `INSTALLED`
- PH-R-1 status: `OWNER_APPROVED_PASS`
- Current work class: `PH-D01B_SOURCE_CONTENT_ACQUISITION_ENVIRONMENT_RUN_AND_SOURCE_BLIND_REBIND`
- Active phase: `PH-D01B`
- `PH-D01B`: `IN_PROGRESS`
- `PH-D01A`: `OWNER_APPROVED_PASS`
- `PH-D00B`: `OWNER_APPROVED_PASS`
- `PH-D00A`: `OWNER_APPROVED_PASS`
- `PH-R00`: `OWNER_APPROVED_PASS`
- Audit: `docs/audits/ARC3_HDS_DISTILLATION_FIRST_REV3_AUDIT_RESOLUTION_2026-07-31.md`
- Installation approval: `control/rev3/OWNER_APPROVAL_RECORDS/REV3_DOC_FIX_TO_PH-R-1_20260731.json`
- Current authority manifest: `docs/strategy/REV3_CURRENT_AUTHORITY_MANIFEST.json`

## 規範権威

上位文書は下位文書の意味を制約する。実行制御文書はこの順序を変更できない。

1. Ownerの現在の明示指示
2. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
3. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
4. `docs/architecture/工学的AGI実装仕様書_v0_2.md`
5. `docs/strategy/ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md`
6. `docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md`
7. `docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md`
8. `docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md`

## 実行制御

実行制御は作業対象・順序・停止点だけを決め、規範権威を変更しない。

1. Ownerの現在の明示指示
2. root `AGENTS.md`
3. Ownerの明示判断を`OwnerDecisionCapture`で転記した、Owner承認済みPhase State
4. current `WorkBlockFrame`
5. committed evidence

過去のphase state、ApprovalRecord、transition、artifact-local `next_*`は履歴証拠であり、current selectorではない。

## 導入順序

```text
REV3文書・契約の監査是正
→ Ownerによる是正内容の明示承認
→ PH-R-1 Strategy Installation
→ PH-R00 Current HEAD Infrastructure Freeze
→ Source-blind HDS Distillation
→ Schema-bound HDSStructureBundle
→ Evidence-thresholded Build-Ready Gate
→ Canonical Record + Multi-Projection Bridge
→ Owner-frozen J Core + Distilled Domain Profile
→ P₀ / JDomain₀ / M₀ / ProbeCatalog
→ Distilled Runtime
→ Relevant-M Causal Witness + Irrelevant-M Invariance
→ End-to-End Mechanism-Family CV
→ Independent Locked Final
→ Official
```

## 現行資産

```text
P16-P21 = 基盤候補としてfreeze
S5/P22 compiled policy = historical/quarantine
監査前rev3 phase evidence = historical/pre-audit/non-authoritative
```

既存成果物は削除しない。監査是正後のOwner承認とStrategy Installationは成立したが、監査前成果物を現在のPhase通過証拠またはactive selectorとして使用しない。

## 機械可読契約

- `control/rev3/REV3_CURRENT_SELECTOR.json`
- `docs/strategy/contracts/REV3_GOVERNANCE_CONTRACT_V1.json`
- `docs/strategy/contracts/HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json`
- `docs/strategy/contracts/AGI_BUILD_READY_PROFILE_V1.json`
- `docs/strategy/contracts/MECHANISM_FAMILY_CV_CONTRACT_V1.json`
- `docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V1.json`
- `docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V2.json`
- `docs/strategy/contracts/OWNER_STANDING_AUTHORIZATION_SCHEMA_V1.json`
- `docs/strategy/contracts/APPROVAL_RECORD_SCHEMA_V1.json`
- `docs/strategy/contracts/PHASE_STATE_SCHEMA_V2.json`
- `docs/strategy/contracts/EVIDENCE_COMMIT_ATTESTATION_SCHEMA_V1.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V3.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V4.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V5.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V6.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V7.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V8.json`
- `docs/strategy/contracts/CLAIM_REGISTRY_REV3.json`

## Codex

```text
Codex = Development Meta-C
Owner = Meta-J
Repository = Meta-M
```

CodexはOwner判断の内容を生成しない。Ownerの明示判断を`OwnerDecisionCapture`として機械的に転記できるだけであり、Owner Approval、phase promotion、Rule promotion、completion claimを自ら行わない。
