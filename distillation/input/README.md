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

`PH-D02B` adds `schema_contract.json`. It is canonical JSON without a trailing
newline and fixes:

- the exact 38-name/38-file schema inventory;
- every schema version, primary ID field, digest field and exclusion policy;
- every typed ID or digest reference and its allowed target schemas;
- the seven independent HDS state axes;
- structural and semantic fail-closed policies;
- the DG-00, DG-01, DG-02, and DG-14 schema boundary;
- explicit zero counts for PH-D02C execution, real trajectory normalization,
  Rule promotion, runtime, locked-final, official, and Kaggle activity.

The schema contract consumes only prior checked metadata and synthetic
fixtures. It grants no approval, promotion, completion acceptance, or phase
transition.
