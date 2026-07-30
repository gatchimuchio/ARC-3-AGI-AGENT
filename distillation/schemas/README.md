# Schema boundary

`source_profile.schema.json` fixes the `PH-D01A` admission contract.
`PH-D01B` adds four strict and separate contracts:

- `source_content_manifest.schema.json`: logical path, file byte identity,
  size, Merkle root, upstream identity, data role, and contamination;
- `acquisition_record.schema.json`: local path, acquisition time, mtime,
  actor, transport, and notes;
- `environment_manifest.schema.json`: all 50 ARC3 environment files, both
  runtime wheels, exact interpreter/OS/dependency lock, seed/reset, and
  isolation binding;
- `run_manifest.schema.json`: command, working directory, input/environment
  digests, tool digest, times, exit status, stream hashes, and network scope.

Every schema rejects unknown fields. Acquisition and run metadata are not
members of `SourceContentManifest.content_digest`. No Causal IR, hypothesis,
Rule, approval, Bridge, runtime, locked-final, official, or submission schema
is introduced by this phase.

`PH-D02A` intentionally adds no member of the later 38-schema inventory.
Instead, `../input/canonicalization_contract.json` and
`hds_distill.canonical` define the common byte, ID, digest, ZIP, NPY, NPZ, and
trajectory-digest representation that PH-D02B schemas must use. The checked
vectors are under `../artifacts/test_vectors/`.

`PH-D02B` now fixes that complete inventory. The machine-readable source of
truth is `../input/schema_contract.json`; it maps each authority name to one
snake_case schema filename, schema version, primary ID field, logical digest
namespace, explicit digest exclusions, typed references, and semantic rules.
The directory contains exactly 38 `*.schema.json` files:

- the five PH-D01A/B documents above remain byte-identical;
- the other 33 documents are deterministic, closed top-level schemas;
- new records use PH-D02A content-derived IDs and logical digests;
- prior-phase records retain their prior ID and digest algorithms rather than
  being silently reinterpreted.

`hds_distill.schema_registry` validates the supported JSON Schema subset,
record identity, duplicate/dangling/wrong-kind/wrong-target references, and
cross-record evidence, decision, approval, promotion, coverage, completion,
audit, and frozen-manifest invariants. Its checked examples are under
`../artifacts/test_vectors/schema_examples/`, and its report is
`../artifacts/reports/schema_conformance.json`.

The ApprovalRecord example is deliberately `SCHEMA_TEMPLATE`,
`authoritative=false`, and `decision=SUSPEND`. It is not an Owner approval.
No schema file is an executable Causal IR, interpreter, Rule promotion,
runtime, official connector, or submission contract.
