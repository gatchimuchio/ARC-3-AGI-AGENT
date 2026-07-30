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
