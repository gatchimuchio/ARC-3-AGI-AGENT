# PH-D00A HDS Dependency Lock

- phase: `PH-D00A`
- lock state: `DEPENDENCY_LOCK_PASS`
- gates: `DG-00`, `DG-14`
- final selector / promotion authority: `大平鉄兵 / OWNER_ONLY`
- dependency manifest:
  `hds-dependency-lock:df90909100a5d3e8b7b89a7224d1c65f4100bfde3824d9eb98066e0ebf87f695`
- dependency audit:
  `hds-dependency-audit-report:dfc1fb138f1bc6c4830ef63987bfe1810c6d08fa0390d634077add0f5a64e9a1`
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
| ARC3 rev3 specification | `docs/strategy/ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md` | `feea0ac2319e0776b8c34101379608a69ac6e59aefbf4f8943ee453a660ff29f` | 23083 |
| ARC3 rev3 roadmap | `docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md` | `b210be684fd43c9f7a1f431e01c3cd5145e7c36301f2c55b9b2fcffc548652b2` | 17209 |

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
  `dfe6fb43564c2aa1ee1cb83cb00861397a466f57a853cbc20a90981719d9e03c`
- Owner approval record:
  `control/rev3/OWNER_APPROVAL_RECORDS/PH-R00.json`
- record SHA-256:
  `e34e21bfb72172dda3c43b922119bee962a9aca899c9d4850402f90c5c7f04f7`
- approval artifact digest:
  `owner-approval-record:a7df8aa233f07c3bb3831f24eb462db0be5dc0fe6885a6da42bb5dce7c5693c0`

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
