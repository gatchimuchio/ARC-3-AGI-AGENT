# P10 Development Analysis Memory

This directory is development-only evidence for the P10 capability-cluster
workflow. Every JSON artifact declares:

- `development_only: true`
- `runtime_use: "FORBIDDEN"`
- a content digest over its semantic body

Task, game, and level identity is intentionally retained here so mechanics,
failure signatures, blockers, and required capabilities can be compared before
Runtime P compilation. Runtime code must not import, load, or route on these
artifacts.

## Canonical artifacts

| Artifact | SHA-256 |
|---|---|
| `LEGACY_LEVEL_ANALYSIS_LEDGER.json` | `8b9c7ba1874cf3599fea0e945760674caac4a1cfcef1de8ce377cb7fb0028877` |
| `ANALYSIS_RECONCILIATION_MATRIX.json` | `91718f62d700b4deccc8e426096429df37b74db081cdf3170e62277ce66a7ec2` |
| `CAPABILITY_COVERAGE_MATRIX.json` | `546892e74ff5f287ff0f010896601e4456553dc3173dae19e34f597e771a0ba9` |
| `CAPABILITY_BUILD_QUEUE.json` | `6a0d11ce3664627f603f0c872389c659c5918faa2a3fcdc445a88d2f5f49c91e` |

Current reconciliation totals:

```text
CONFIRMED                26
PARTIALLY_CONFIRMED       1
CONTRADICTED              0
STALE                     9
UNOBSERVED              147
TOTAL                   183
```

Current queue decisions:

- C2: `CLUSTER_STABLE`
- C3: `LOCAL_PROBE / HOLD`
- C10: `COMPOSABLE`, Runtime P intervention `REJECT`
- C7: `LOCAL_PROBE / CLOSED_NEGATIVE`
- C12: `LOCAL_PROBE / CLOSED_NEGATIVE`
- C1: `LOCAL_PROBE / CLOSED_NEGATIVE`
- C14, C8, C4, C6, C9, C11, C13:
  `LOCAL_PROBE / CLOSED_NEGATIVE / NEGATIVE_ONLY`
- C5 bounded-old-action-replay axis:
  `LOCAL_PROBE / CLOSED_NEGATIVE_AXIS`
- next unembedded work block:
  `WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER`

The seven newly closed frozen surfaces contain 21 targets and 2,199 probes:
565 visible changes, zero progress, and five raw `GAME_OVER` observations.
The raw hazard observations do not form a reusable hazard separator. See
`evidence/p10/development/remaining_frozen_negative_surfaces_v1/`.

All closed-negative conclusions are development accounting only. They do not
authorize Runtime P compilation, promotion, score progress, or P11 entry.

## Deterministic rebuild

The compiler requires the read-only legacy repository because the P3
provenance manifest binds all 705 selected source paths, byte counts, and
SHA-256 digests.

From `ARC-AGI-3-Agents/`:

```bash
arc3-compile-development-analysis \
  --legacy-repository-root \
  /mnt/c/Users/mzcum/ARC-Layer-0-Functional-Compliance-main \
  --repository-root .. \
  --output-dir ../analysis/development
```

Any missing source, digest drift, parse error, or row-count mismatch fails
closed. The old repository is an input only and must not be edited.

The authoritative workflow and promotion tiers are defined in
`docs/roadmap/P10_ALL_TASK_CAPABILITY_COMPILATION_CORRECTION.md`.
