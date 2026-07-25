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
| `CAPABILITY_COVERAGE_MATRIX.json` | `67cbdf9d98d8f70040565a312b7c2d64c6bbedb7c76d7ee16d4813011ba6baa9` |
| `CAPABILITY_BUILD_QUEUE.json` | `fa2f1a3340657c9f59fbf315b3e8aa8e608be1de293f58b58dee0d442539a692` |

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
- C5 bounded-old-action-replay axis:
  `LOCAL_PROBE / CLOSED_NEGATIVE_AXIS`
- next unembedded work block:
  `WB-C12_layout_mode_commit_discriminator`

C7 and C5 are negative-only development conclusions. They do not authorize
Runtime P compilation, promotion, score progress, or P11 entry.

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
