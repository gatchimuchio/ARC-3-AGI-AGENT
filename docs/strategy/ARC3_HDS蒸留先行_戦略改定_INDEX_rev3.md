# ARC3 HDS蒸留先行 戦略改定資料 INDEX

- Package status: `OWNER_APPROVED`
- Installation status: `INSTALLED`
- PH-R-1 status: `OWNER_APPROVED_PASS`
- Current work class: `PH-D06_MULTI_HYPOTHESIS_CANDIDATE_GENERATION`
- Active phase: `PH-D06`
- `PH-D06`: `IN_PROGRESS`
- `PH-D05`: `OWNER_APPROVED_PASS`
- `PH-D03B`: `OWNER_APPROVED_PASS`
- `PH-D03A`: `OWNER_APPROVED_PASS`
- `PH-D02C`: `OWNER_APPROVED_PASS`
- `PH-D02B`: `OWNER_APPROVED_PASS`
- `PH-D02A`: `OWNER_APPROVED_PASS`
- `PH-D01B`: `OWNER_APPROVED_PASS`
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

## PH-D05承認済み証拠とPH-D06現行境界

- source-blind三roleは別process・別mount projectionで固定し、Executor/Auditorのenvironment source mountとrepository-root visibilityを0件として検証する。
- 現行environment/run bindingにより監査前PH-D02B成果物3件が失効することを`distillation/artifacts/reports/ph_d01b_downstream_invalidation.json`へexact digest付きで記録する。
- PH-D02Aではsynthetic test vector上のcanonical JSON／JSONL、ID／digest、ZIP／NPY／NPZ、raw／canonical trajectory digest型を再検証し、exact evidenceへOwner承認を拘束済みである。
- 監査前PH-D02A control artifact 13件は`control/rev3/HISTORICAL_PRE_AUDIT/PH-D02A/`へbyte-identicalに保持し、現行phase pass証拠には使用しない。
- PH-D02Bでは38 HDS rev2 schemaと7 HDSStructureBundle schemaのexact 45-schema set、cross-file reference、dependency lock、bundle inventory、synthetic conformanceを実装・再検証し、exact evidenceへOwner承認を拘束済みである。
- 監査前PH-D02B control artifact 13件は`control/rev3/HISTORICAL_PRE_AUDIT/PH-D02B/`へbyte-identicalに保持し、監査前D02C-refined schema／interpreter候補とともに現行phase pass証拠へ使用しない。
- PH-D02Cでは承認済みPH-D02B schema setからversioned 45-schema setを派生し、Typed Causal IR、pure offline interpreter、verifier ABI、identity／answer-copy linter、resource suspension、synthetic conformanceを実装・再検証し、exact evidenceへOwner承認を拘束済みである。
- 監査前PH-D02C control artifact 13件と生成IR candidate 12件は明示的historical namespaceへbyte-identicalに保持し、現行phase pass証拠へ使用しない。
- PH-D03AではARC2 8カテゴリ／ARC3 8カテゴリのsynthetic Golden implementation-conformance candidateを生成し、DG-00〜DG-15をcase構造、IR再実行、bounded intervention、negative probeから再計算し、16件すべてのexpectation digestをcontent-specific Owner decisionへ拘束済みである。
- 監査前PH-D03A control artifact 15件、4 candidate artifact、source、test、preinventoryは明示的historical namespaceへbyte-identicalに保持し、現行phase pass証拠へ使用しない。
- PH-D03Bでは、承認された16件のexpected-artifact digestだけをlabelなしcommitment setへ固定し、Golden source、target bundle、decision、ApprovalRecord、evidenceのexact digestをsealed manifestへ拘束する。
- Sealed namespaceにはexpected artifact plaintextとfixture identifierを保存しない。runnerはsubmission digestを再計算し、出力をexact `PASS\n`／`FAIL\n`だけに限定し、repository外のmutable ledgerで最初のaudit attemptをconsumeする。
- PH-D03Bの`DISTILLATION_CONFORMANCE_CORPUS_FROZEN`はOwner承認済みである。
- PH-D05ではexact 25 raw recordingを外部cacheでbyte検証し、全25 game／183 level／11,574 canonical actionをlossless canonical trajectoryへ正規化し、exact evidenceへOwner承認を拘束済みである。
- strict OFFLINE replay x3はcanonical frame／action／availability／terminal／progress mismatch 0、source pre/post identity、network denial、secret scrub、write allowlist、fixed seedを必須とする。
- canonical manifest、25 package、normalization reportは独立3 processでbyte-identical rebuildする。
- PH-D06では25 teacher caseごとに18候補、合計450候補をsource-blind processで生成する。各caseは16 executable typed IRと、answer-copy／identity-routingを生成後に拒否した2 adversarial candidateを持つ。
- selector familyとoperator／ordering familyの異なる非strawman代替を保持し、candidate auto-adoption、teacher fit、因果主張、intervention、promotionをすべて0に固定する。
- candidate manifestと25 packageは独立3 processでbyte-identical rebuildし、Executorへのenvironment source mount、repository-root visibility、network、secret継承を0件として検証する。
- source-blind実行はGit外のexact Python 3.12.13 runtimeに固定し、archive SHA-256、4,522-entry tree digest、interpreter digestを3 processすべてで一致させる。build中のnetwork取得とruntimeのGit格納は認めない。
- 現行境界は`MULTI_HYPOTHESIS_CORPUS_COMPLETE`までである。PH-D07A teacher fit、PH-D07B intervention、Rule promotion、Bridge、Runtimeは開始しない。

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
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V9.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V10.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V11.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V12.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V13.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V14.json`
- `docs/strategy/contracts/REV3_CURRENT_SELECTOR_SCHEMA_V15.json`
- `docs/strategy/contracts/POST_AUDIT_CAUSAL_IR_CONTRACT_V1.json`
- `docs/strategy/contracts/CLAIM_REGISTRY_REV3.json`

## Codex

```text
Codex = Development Meta-C
Owner = Meta-J
Repository = Meta-M
```

CodexはOwner判断の内容を生成しない。Ownerの明示判断を`OwnerDecisionCapture`として機械的に転記できるだけであり、Owner Approval、phase promotion、Rule promotion、completion claimを自ら行わない。
