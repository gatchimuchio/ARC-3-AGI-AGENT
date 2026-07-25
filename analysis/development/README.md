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
| `CAPABILITY_COVERAGE_MATRIX.json` | `5b4d9ddee8f973898b9bd70a81996afc65026644e83b8d15dab2ee2a34f167c1` |
| `CAPABILITY_BUILD_QUEUE.json` | `45f85adda59b3a3f3b42f5f68591594f987cd4bd60c5d6f2c69800c342e00735` |

Current reconciliation totals:

```text
CONFIRMED                26
PARTIALLY_CONFIRMED       1
CONTRADICTED              0
STALE                     9
UNOBSERVED              147
TOTAL                   183
```

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
