# P10 C2+C10 candidate intervention — v1

This directory stores the development-only, HDS-controlled intervention for
the identity-free C2 observer plus C10 one-step visible causal-context
candidate. It is evidence, not Runtime P input.

## Conditions

- operation mode: `OFFLINE`
- instruction variant: `P-A`
- active conditions: four stable, one discovery, two held-out
- candidate conditions: the same seven conditions
- repetitions: two complete ordered passes per lifecycle
- action budget: `450` per condition
- total runs: `28`

## Result

- active reproducible: `true`
- candidate reproducible: `true`
- active/candidate error count: `0 / 0`
- stable completion: `29 -> 29`
- discovery/held-out completion: `0 -> 0`
- target completion delta: `0`
- active manifest changed: `false`
- HDS decision: `REJECT`
- all-sample candidate regression authorized: `false`
- Runtime P promotion authorized: `false`
- score-progress claim authorized: `false`

The candidate changed no adopted level boundary. HDS restored the prior
candidate slot byte-for-byte and removed the working candidate body. The
compiled body and candidate manifest are retained only under
`candidate_archive/` so the rejected intervention remains auditable.

The authoritative content-bound result is
`C2_C10_CANDIDATE_INTERVENTION_AUDIT.json`.
