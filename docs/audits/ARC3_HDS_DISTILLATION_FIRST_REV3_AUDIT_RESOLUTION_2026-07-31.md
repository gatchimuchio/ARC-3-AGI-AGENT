# ARC3 HDS蒸留先行 rev3 監査是正記録

- Audit date: `2026-07-31`
- Source report: `ARC3_HDS蒸留先行_戦略改定パッケージ_rev3_監査報告.md`
- Source report SHA-256: `8536f4644fdc56cc71fa5a43699b43894c8f5d2c007ff772d68c29cc4546c1c1`
- Audit verdict: `MAJOR_REVISION_REQUIRED`
- Correction work class: `REV3_DOCUMENT_CORRECTION_ONLY`
- Strategy status: `PROPOSED_PENDING_OWNER_APPROVAL`
- Installation status: `NOT_INSTALLED`
- `PH-R00`: `SUSPEND`
- Owner approval represented by this record: `NONE`

この記録は監査報告の判断を変更しない。監査findingをどの是正契約へ反映したかを追跡するためのCodex作成記録であり、Owner ApprovalRecordではない。

## Finding resolution matrix

| Finding | 是正 | 正本 |
|---|---|---|
| F-01 | 規範権威と実行制御を分離 | `AUTHORITY_ORDER.md`、root `AGENTS.md`、spec 2.4、INDEX |
| F-02 | Implementation／Evidence／Attestation／Approvalを分離し自己参照を禁止 | root `AGENTS.md` 5/6/12、spec 11.1、roadmap Phase State |
| F-03 | Primary Source／Derived Evidence／Governance Artifactsを分離 | spec 4.1、governance contract |
| F-04 | Relevant-M causal witnessとIrrelevant-M invarianceを分離 | spec 9.2/9.4、roadmap PH-B05/PH-A01 |
| F-05 | 一primary class＋複数typed projection＋重複加点禁止 | spec 5.3/7.3、roadmap PH-B01 |
| F-06 | familyごとのsource splitからRuntimeIdentityまでのend-to-end CV | spec 12.3、roadmap PH-E01、CV contract |
| F-07 | category別hard minimumを持つbuild-ready profile | spec 6.1、roadmap PH-D14、build-ready profile |
| F-08 | manifest、record、digest、reference、migration、unknown/partial rejection | spec 5.1、bundle contract |
| F-09 | `J_CORE_OWNER_FROZEN`と`J_DOMAIN_PROFILE_DISTILLED`を分離 | spec 7.2、roadmap PH-B03/PH-A02 |
| F-10 | Replay Maintainer／Distillation Executor／Auditorを別process・checkoutへ分離 | root `AGENTS.md` 7、spec 4.4 |
| F-11 | D01、D02、D03、D07、D09〜D11を個別Phaseへ分割 | roadmap Track D |
| F-12 | Owner判断の機械転記schemaを追加 | root `AGENTS.md` 5、spec 11.2、OwnerDecisionCapture schema |
| F-13 | 未導入状態、PH-R-1、PH-R00 SUSPENDを固定 | 全rev3正本 |
| F-14 | internal stateとexternal claim IDのmappingを固定 | spec 13、Claim Registry |
| F-15 | Authority／Custodian／Token Issuer／Consumption Ledgerを分離 | root `AGENTS.md` 10、spec 12.4、roadmap PH-E02 |
| F-16 | legality maskを許可し、action tuple routerを禁止 | root `AGENTS.md` 10、spec 7.4、roadmap PH-B04 |
| F-17 | ASCII-safe entry、`MANIFEST.json`、`SHA256SUMS`、deterministic ZIP | `scripts/package_rev3_strategy.py`と生成package |

## Historical evidence disposition

監査前に生成された次の資産は削除しない。

- `control/rev3/R00_PHASE_STATE.json`
- `control/rev3/D00A_PHASE_STATE.json`〜`D02C_PHASE_STATE.json`
- `control/rev3/D03A_CANDIDATE_STATE.json`
- `control/rev3/OWNER_APPROVAL_RECORDS/PH-R00.json`
- `control/rev3/PHASE_TRANSITIONS/*`
- 対応するOwner Review Package
- `docs/strategy/REV3_STRATEGY_REBASELINE.md`
- `docs/strategy/REV3_AUTHORITY_INPUT_MANIFEST.json`
- `artifacts/source_content_manifests/hds_dependencies.json`
- `artifacts/reports/dependency_audit.json`
- `scripts/audit_hds_dependencies.py`

分類は一律、

```text
HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE
```

である。これらは当時の実装履歴として保持するが、是正後strategyのcurrent phase、phase pass、activation、Rule/Bundle approvalへ使用しない。

## Remaining gate

Codexの是正実装と自己監査が合格しても、次は成立しない。

```text
OWNER_APPROVED_REV3_CORRECTION
STRATEGY_INSTALLATION_COMPLETE
PH-R00_STARTED
```

Ownerが是正artifact digest、evidence commit、許可遷移を明示した判断だけを、`OwnerDecisionCapture`として後続commitへ機械転記できる。その後の最初のPhaseは`PH-R-1`であり、PH-R00ではない。
