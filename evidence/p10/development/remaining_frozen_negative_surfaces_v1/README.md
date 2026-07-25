# P10 Remaining Frozen Negative Surfaces

This directory binds seven exact provenance-frozen legacy capability harnesses
to development-only HDS negative judgments. The retained legacy JSON files are
byte-for-byte evidence inputs; they are not Runtime P input.

## Aggregate result

- newly closed capability surfaces: 7
- previously closed C5 axis represented in queue order: 1
- targets: 21
- probes: 2,199
- changed probes: 565
- progress: 0
- raw `GAME_OVER`: 5
- reusable hazard separators: 0
- Runtime P compile or promotion: forbidden
- score progress claim: forbidden

The five `GAME_OVER` observations belong to C11. They do not separate a
reusable hazard variable and therefore cannot be promoted as a verifier.

## Strict queue result

1. C14 symbolic relation commit model: `CLOSED_NEGATIVE`
2. C8 helper handoff state model: `CLOSED_NEGATIVE`
3. C4 hazard rollback verifier: `CLOSED_NEGATIVE`
4. C6 action channel emitter model: `CLOSED_NEGATIVE`
5. C5 bounded-old-action-replay axis: previously `CLOSED_NEGATIVE_AXIS`
6. C9 token slot submission verifier: `CLOSED_NEGATIVE`
7. C11 route terminal reachability verifier: `CLOSED_NEGATIVE`
8. C13 support bridge slider model: `CLOSED_NEGATIVE`

The next materially new development work block is
`WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER`. It must use rendered,
identity-free prospective relations and successor-obligation state. Retrying
the frozen surfaces or replaying predecessor actions is not authorized.

## Canonical catalog

`REMAINING_FROZEN_NEGATIVE_CATALOG.json`

Content digest:

```text
arc3_p10_remaining_frozen_negative_catalog:c05d9cba55cceb6db08fdac380c40f2cc0fd28bf73e767ae20524f005a17fbfd
```

## Deterministic rebuild

From `ARC-AGI-3-Agents/`:

```bash
PYTHONPATH=. python -m \
  arc3_agi_agent.p10_remaining_frozen_negative_audit \
  --provenance-manifest ../manifests/provenance_manifest.json \
  --retained-dir \
  ../evidence/p10/development/remaining_frozen_negative_surfaces_v1 \
  --output-dir \
  ../evidence/p10/development/remaining_frozen_negative_surfaces_v1
```

Any source byte or SHA drift, positive-progress mutation, separator mutation,
scope violation, or legacy decision mismatch fails closed.
