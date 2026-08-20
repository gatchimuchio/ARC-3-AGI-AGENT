# PH-D00A HDS Dependency Lock

- phase: `PH-D00A`
- lock state: `DEPENDENCY_LOCK_PASS`
- gates: `DG-00`, `DG-14`
- final selector / promotion authority: `大平鉄兵 / OWNER_ONLY`
- dependency manifest:
  `hds-dependency-lock:2f032a1b853e24624a2df9f176486978e7cf41537af951278996b0f1cf0b9b01`
- dependency audit:
  `hds-dependency-audit-report:7c1540a1c23d39e9d1db4b7156caeb5313283fa62ef0678d83ce383d2768770e`
- Open Term Ledger:
  `hds-open-term-ledger:92774b752cd68c17588c2d443707d6327f28df7e0d4a4960447299e1fe54e291`

The machine-readable source of truth is
`artifacts/source_content_manifests/hds_dependencies.json`.
Every path in that artifact is repository-relative POSIX. A changed byte,
size, path, Git object, authority record, schema boundary, or content digest is
a blocking failure, not an implicit upgrade.

## Local authority dependencies

| Role | Repository-relative path | SHA-256 | Bytes |
|---|---|---|---:|
| HDS internal canonical specification | `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md` | `6f55471c0bb3b2b54d434ac05ac09ee24ef69fda3f2f024e5f762696e822216c` | 32565 |
| HDS external specification | `docs/references/HDSフレーム_rev3_1_外向け仕様.md` | `d7cbbf4c981621509e124077ae66cc49bd29b2271fbf94194c6786d2a5a8724a` | 31229 |
| HDS self-contained prompt | `docs/references/HDS_SelfContained_Prompt_v1_2_utf8bom.txt` | `33b8a35176a0cc2f18502befb4a53cfbbf378b35e36b911888fa534a8b377b50` | 9876 |
| HDS distillation specification | `docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md` | `79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02d88fb6fc93` | 38926 |
| HDS distillation roadmap | `docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md` | `64640eff883f417baeb2d70716e1904c1fd765a3d1a5a5eacb8bba82e3500518` | 20818 |
| ARC3 rev3 specification | `docs/strategy/ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md` | `52c652ae734a41cd4116d4e15bca890c43c5e0aaf3f7f8d6f0627a540f7a9f63` | 36907 |
| ARC3 rev3 roadmap | `docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md` | `7c010c9c5becd89800ffb2fd9ba9a914dac3cd246a39891e88367ac5ae7753e5` | 26937 |

## HDS-BlackBox-Translator reference

- repository: `gatchimuchio/HDS-BlackBox-Translator`
- commit: `b501cc77c94048421af8efdb2e866c22b06f7208`
- tree: `de5e9e5907efd2d32d22c41d1ef9215867ce9ce5`
- README Git blob: `7f6f9f4b1e2a25a07e25688b5cde24a96bfd2335`
- README SHA-256:
  `a49d75aadce49fcd95576abf06106c03286b8ce38e010e4205cc5e0fc0708e99`
- capability boundary: `DETERMINISTIC_HDS_TRANSLATION_REFERENCE_ONLY`

This reference supports deterministic projection of supplied evidence,
candidates, policy, PV, and selection into an auditable HDS judgment
structure. It is not evidence of unknown-mechanism induction, executable
causal hypotheses, counterfactual intervention, unique internal recovery, or
automatic RuleAtom promotion.

## Authority lock

- order document: `AUTHORITY_ORDER.md`
- SHA-256:
  `055f4b8c14001193d525708799f31f457d22dc9815a9feb2a972515d9b705044`
- Owner approval record:
  `control/rev3/OWNER_APPROVAL_RECORDS/PH-R00_TO_PH-D00A_20260731.json`
- record SHA-256:
  `afc32e7ef47b7145e29a9c0baf682046ee5548cccd58b7428acbcd7e65df852c`
- approval artifact digest:
  `owner-approval-record:db4a8bc2a2f1fab0cafb51a64745e072857eea9e35cff6cd8cceb57c65e8e581`

The phase-continuation authorization does not approve Rule promotion,
HDSStructureBundle, DistilledInitialStateBundle, locked-final access, official
access, or Kaggle mutation/submission.

## Validation

Offline lock verification:

```bash
python scripts/audit_hds_dependencies.py \
  --verify-report artifacts/reports/dependency_audit.json
```

Optional exact upstream Git-object verification:

```bash
python scripts/audit_hds_dependencies.py \
  --translator-git-dir <bare-or-dot-git-directory> \
  --verify-report artifacts/reports/dependency_audit.json
```

The command exits non-zero on unknown or missing fields, malformed types,
non-canonical JSON, absolute/backslash/parent paths, local byte or size drift,
Translator object drift, authority drift, non-empty dependency Open Terms, or
content-digest mismatch.

## Scope boundary

This lock establishes only:

```text
hds_dependency_match = true
authority_defined = true
unresolved_dependency_count = 0
```

It does not establish HDS corpus processing, causal mechanism support, Rule
promotion, Bridge readiness, AGI capability, generalization, competition
readiness, or official score.
