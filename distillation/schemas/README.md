# Schema boundary

`source_profile.schema.json` is the minimal strict schema required by
`PH-D01A`. It fixes the permitted profile, split, answer-visibility,
development-usage, contamination, materialization, access-policy, and selector
states. Unknown fields and unknown enum values fail closed.

No `SourceContentManifest`, acquisition, environment, Causal IR, evidence, HDS
state, approval, or promotion schema is defined yet. Those schemas remain in
their ordered later phases.
