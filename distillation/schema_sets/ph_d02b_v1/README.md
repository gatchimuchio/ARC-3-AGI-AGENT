# Post-audit PH-D02B schema set

This directory is the current PH-D02B schema-set candidate. It is generated
deterministically by `scripts/build_ph_d02b_schema_bundle.py`.

The set contains exactly 45 `*.schema.json` files:

- 38 HDS rev2 schemas reconstructed from the byte-accounted historical
  snapshot under `distillation/input/historical_pre_audit/PH-D02B/`;
- 7 HDSStructureBundle schemas:
  `HDSStructureBundleManifest`, `OntologyTypeRecord`,
  `MechanismAssetRecord`, `ProbeObligationRecord`,
  `StructureCoverageProfile`, `BundleApprovalRecord`, and
  `StructureBundleMigrationRecord`.

The source of truth is
`distillation/input/post_audit_schema_bundle_contract.json`. Validation is
implemented by `hds_distill.post_audit_schema_bundle` and covers exact
inventory, content identities, typed cross-file references, dependency locks,
schema versions, and the required package file inventory.

The repository-root `distillation/schemas/` directory and
`hds_distill.schema_registry` contain a retained pre-audit PH-D02C-refined
candidate. They are not imported by this schema set and are not current
PH-D02B phase-pass evidence.

All examples are synthetic. `BundleApprovalRecord` is a structural fixture,
not an Owner decision. No file in this directory authorizes PH-D02C
execution, real trajectory normalization, Rule promotion, Bridge, Runtime,
official access, or Kaggle submission.
