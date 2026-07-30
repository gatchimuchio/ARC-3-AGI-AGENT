# Input metadata boundary

`PH-D01A` admits source locator and contamination metadata only through
`source_inventory_plan.json` and the content-bound documents under
`../profiles/source/`.

The plan defines the complete candidate roots, exact admitted paths, external
archive members, raw-recording locators, exclusions, and expected accounting.
It is not a `SourceContentManifest`, `AcquisitionRecord`, or
`EnvironmentManifest`. No source payload is copied or processed here.

PH-D01B must separately bind content, acquisition, environment, wheels, seed,
and read-only source state before any downstream processing.
