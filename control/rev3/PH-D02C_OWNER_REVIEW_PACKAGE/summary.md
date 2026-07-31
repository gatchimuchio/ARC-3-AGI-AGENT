# PH-D02C Typed Causal IR Evidence

- Phase: `PH-D02C`
- Decision: `CODEX_SELF_AUDIT_PASS`
- Implementation commit: `09525862e3f503f6ae4b7e63ad048b1726d4f958`
- Implementation tree: `4ffc030f7be0b0063b72c3cb13b2646867a149cc`
- Evidence payload digest: `sha256:cb5c07dd9295ee47fa5f114ba9aff5d9f10106da2c6d2412adbea42080fe4a04`
- Derived schema set: `45 / 45 PASS` (`43 unchanged + 2 refined`)
- Common type system: `18 / 18 PASS`
- Domain opcodes: `51 / 51 PASS` (`33 ARC2 + 18 ARC3`)
- Positive synthetic vectors: `51 / 51 PASS`
- Negative rejection vectors: `15 / 15 PASS`
- Full distillation: `311 / 311 PASS`
- Full unit: `736 / 736 PASS`
- Full integration: `8 / 8 PASS`
- Governance validator: `64 / 64 PASS`
- Rebuild determinism: `3 / 3 BYTE_IDENTICAL` for 69 artifacts
- Historical control migration: `13 / 13 BYTE_IDENTICAL`
- Historical IR snapshot: `12 / 12 BYTE_IDENTICAL`
- Scope Guard findings: `0`
- Failed requirements: `0`
- Runtime activation: `SUSPEND`
- PH-D03A started: `false`

The exact typed causal IR schema, 18-type system, 51-opcode registries, pure
offline interpreter, linter, resource model, ABI, vectors, and conformance
report are bound to the implementation commit and tree. Unknown types and
opcodes, ABI and version drift, type and cardinality mismatch, forward
references, malformed parameters, failed preconditions, privileged routing,
answer copying, fixed successful actions, and causal overclaim fail closed.
Resource overflow returns `SUSPEND_RESOURCE` with `HOLD` and `INCONCLUSIVE`.

The dormant PH-D03A Golden builder remains regression-compatible through the
post-audit schema adapter, while its historical checked artifacts remain
byte-identical to the PH-D02C entry base and are not promoted or rewritten.
No real teacher trajectory was parsed or normalized, no real intervention was
executed, and no Golden or Sealed freeze, candidate generation, Rule
promotion, Bridge, Runtime capability, locked-final access, official access,
Kaggle mutation, or submission was performed.
