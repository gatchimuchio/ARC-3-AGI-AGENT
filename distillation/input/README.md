# Input metadata boundary

`PH-D01A` admits source locator and contamination metadata through
`source_inventory_plan.json` and the content-bound documents under
`../profiles/source/`.

`PH-D01B` then consumes two additional checked inputs:

- `manifest_freeze_plan.json` separates profile/upstream bindings,
  acquisitions, environment identity, the selected run record, resource
  limits, accounting, and phase boundaries;
- `raw_recording_content_capture.json` retains only identity fields, row
  bindings, trajectory byte sizes, and SHA-256 values for the 25 pinned
  recordings. It does not retain trajectory payloads.

The remote capture first verifies that the dataset is at
`455b7c58eaa9d5ea05f91cd1b5b603121599e758`, reads each selected Dataset
Viewer row, verifies game/row/guid/win/level/action/trajectory bindings, and
then verifies the dataset SHA again. Only the acquisition subobject changes
between equivalent captures; it is excluded from the capture content digest.

Local archive paths and timestamps remain acquisition-only metadata. External
archives and raw payloads are not copied into the repository.

`PH-D02A` adds `canonicalization_contract.json`. It is canonical JSON without
a trailing newline and fixes:

- Unicode, number, confidence, set, ordered-array, and explicitly unordered
  array behavior;
- repository-relative POSIX paths;
- content-ID and logical/physical digest domains and exclusions;
- ZIP, NPY, and NPZ physical representation;
- raw/canonical trajectory digest separation;
- the committed synthetic test-vector paths and x3 rebuild contract.

The contract consumes only frozen manifest metadata and synthetic fixtures.
It does not read a source payload or normalize a real trajectory.

The Owner-approved post-audit `PH-D02B` adds
`post_audit_schema_bundle_contract.json`. It is canonical JSON with the
PH-D02A document boundary and fixes:

- the exact 38 HDS rev2 plus 7 HDSStructureBundle schema inventory;
- every schema version, primary ID field, digest field and exclusion policy;
- every typed cross-file reference and its allowed target schemas;
- one-to-one projection of all 38 HDS rev2 schemas across the 7 canonical
  bundle record types;
- exact dependency-lock and 34-file bundle inventory behavior;
- the seven independent HDS state axes;
- structural and semantic fail-closed policies;
- the DG-00, DG-01, DG-02, and schema-only DG-14 boundary;
- explicit zero PH-D02C execution, real trajectory normalization, Rule
  promotion, runtime, locked-final, official, and Kaggle activity.

The schema contract consumes only prior checked metadata and synthetic
fixtures. It grants no approval, promotion, completion acceptance, or phase
transition.

`historical_pre_audit/PH-D02B/` is a byte-accounted snapshot extracted from
implementation commit `108c5462c2c73bdd95953e9e9b0cbbce68ac5d02`.
It is non-authoritative input only. The checked `schema_contract.json`
contains later pre-audit PH-D02C refinements and is not the current D02B
contract.

The current post-audit `PH-D02C` adds
`post_audit_causal_ir_schema_contract.json` and rebuilds
`causal_ir_contract.json`. The first derives exactly 45 schemas from the
approved PH-D02B set, changes exactly HypothesisIR and OperatorRegistry, and
records both version migrations. The second binds the 18 common types, both
exact opcode inventories, the type/registry/resource/ABI digests, stable error
codes, and zero downstream activity. Its executable scope is restricted to
synthetic typed programs; it is not teacher-data evidence or a causal
mechanism assertion.

`historical_pre_audit/PH-D02C/` preserves the 12 pre-audit schema and generated
IR candidates byte-identically under a content-bound snapshot manifest. Those
bytes are candidate input only and are not eligible for current activation.

The current post-audit `PH-D03A` adds
`golden_conformance_contract.json`. It is bound to the exact approved
PH-D02C phase-state hash, evidence payload, entry ApprovalRecord, post-audit
schema contract, executable IR contract, current WorkBlockFrame, and phase
transition. It fixes:

- the exact eight ARC2 and eight ARC3 synthetic conformance categories;
- the eleven required human-auditable artifact classes per case;
- at least two typed HypothesisIR alternatives per case;
- complete DG-00 through DG-15 behavioral coverage recomputed from case
  structure, executable results, bounded interventions, and negative probes;
- stable candidate-corpus validation errors;
- `PROPOSED_PENDING_OWNER_APPROVAL` as the only allowed candidate state;
- non-authoritative `SCHEMA_TEMPLATE` / `SUSPEND` ApprovalRecord semantics;
- zero Golden freeze, Sealed corpus, source/teacher reads, real intervention,
  causal establishment, general candidate generation, promotion, Bridge,
  runtime, official, and Kaggle activity.

The contract authorizes deterministic candidate construction and validation
only. The checked Owner review request contains no decision. A new trusted,
content-specific Owner ApprovalRecord is required before any provisional
expectation can be frozen, and approved expectations cannot be auto-updated.

`historical_pre_audit/PH-D03A/` preserves the four pre-audit checked
candidate artifacts plus the corresponding source and test bytes from commit
`70722de7df8278c866de0734c97206c9952d731d`. The snapshot is
non-authoritative and cannot satisfy a current Golden gate.
