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
