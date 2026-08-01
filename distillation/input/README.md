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

The Owner-approved post-audit `PH-D03A` adds
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

The checked Owner review request itself contains no decision. The separate,
content-specific PH-D03A OwnerDecisionCapture and ApprovalRecord approve the
exact sixteen-target bundle without mutating these candidate artifacts.
Approved expectations cannot be auto-updated.

The Owner-approved `PH-D03B` adds `sealed_audit_contract.json` and the versioned
sealed namespace under `../frozen/sealed_audit/ph_d03b_v1/`. The contract is
bound to the exact PH-D03A evidence, sixteen-target bundle, decision,
ApprovalRecord, current WorkBlockFrame, preinventory, and transition. It
fixes:

- exactly sixteen unlabeled expected-artifact digest commitments;
- zero expected-artifact plaintext and zero fixture identifiers in sealed
  artifacts;
- exact source byte hashes and bound digests without copying mutable Golden
  content;
- canonical manifest and runner-contract references;
- exact status-only `PASS\n` or `FAIL\n` disclosure;
- logical-digest recomputation instead of trusting declared digests;
- atomic consume-on-first-attempt state in a mutable ledger outside the
  repository;
- fail-closed source drift, bundle drift, malformed submission, ledger
  placement, and reuse behavior;
- DG-06 and DG-14 evidence with zero real-source normalization, promotion,
  Bridge, Runtime, official, and Kaggle activity.

The audit path raw-hashes the bound Golden source files but does not parse
their expected plaintext. PH-D05 was not started by this contract.

The Owner-approved `PH-D05` adds
`arc3_teacher_trajectory_normalization_contract.json`. The contract binds the
exact PH-D03B evidence and entry decision, pinned dataset revision, source and
environment manifests, acquisition report, strict OFFLINE replay-x3 report,
canonical manifest/report digests, deterministic rebuild evidence, action and
frame invariants, five required gates, and zero downstream activity. Raw
recording bytes and replay captures remain outside the repository.

This contract authorizes lossless trajectory normalization only. It does not
authorize candidate selection, causal claims, intervention, Rule promotion,
Bridge, Runtime, official access, or Kaggle mutation.

The current `PH-D06` adds
`arc3_hypothesis_candidate_generation_contract.json`. It binds the exact
PH-D05 evidence and entry approval, canonical teacher manifest, current
WorkBlockFrame, preinventory, transition, source-blind execution report,
candidate manifest, deterministic rebuild evidence, and no-LLM capture. It
requires 18 candidates per each of 25 cases, including 16 executable typed IR
alternatives and two privilege adversaries rejected before execution.

The contract also pins source-blind execution to the external, non-Git Python
3.12.13 runtime archive SHA-256
`7ceaf4360f4b4ab44f31d8217cfdc70df8e12b61d9561b4900ee7af87176e50d`,
the extracted 4,522-entry runtime-tree digest, and the exact interpreter
executable digest. Candidate generation has no network acquisition path; all
three isolated processes must report the same verified runtime evidence.

This contract authorizes bounded candidate generation only. Every candidate
remains unselected and unevaluated for fit; PH-D07A owns fit evaluation and
PH-D07B owns interventions. It authorizes no causal assertion, Rule promotion,
Bridge, Runtime, official access, or Kaggle mutation.

`historical_pre_audit/PH-D03A/` preserves the four pre-audit checked
candidate artifacts plus the corresponding source and test bytes from commit
`70722de7df8278c866de0734c97206c9952d731d`. The snapshot is
non-authoritative and cannot satisfy a current Golden gate.
