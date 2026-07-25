# P10 C2/C3 transition evidence — all 25, max-actions 450, v2

This directory persists the reviewable evidence for the bounded C2/C3
transition run. It is development-only and must not be imported or consulted
by Runtime P.

## Frozen execution conditions

- execution source commit: `d1891a1`
- runtime source inventory digest:
  `2fe055f44870a6916700102d81cdf034f2aa621a583c9ee337837e0ec882eecd`
- active manifest digest:
  `6b67437d771d2a31f4c93303dee858f5151120412c2b7cf3ce55061b987aa2e1`
- checkpoint conditions digest:
  `f64f05f732c50117e9b57ee2ba9d3e30c8484ab5b972da25ddeaed72647b19f9`
- operation mode: `OFFLINE`
- lifecycle / variant: `active / hybrid`
- action budget: `450`
- Python: `3.14.4`
- ARC Toolkit: `0.9.8`
- sample ZIP SHA-256:
  `c72400a32db5e48da9014baf893b48016b300e9a6a77bd5d505de2b1ec61d645`

The ZIP is an external static oracle input and is not copied into Git.

## Result

- games represented: `25 / 25`
- levels represented: `183 / 183`
- completed levels: `35 / 183`
- complete games: `4 / 25`
- runtime errors: `0`
- completion rate: `19.125683%`
- local standard-oracle RHAE: `18.821945363%`
- score digest:
  `9f214c1825f8ee0f52b1ef6a323b778971ce03e03a3733338d2323a9b0ebb238`
- resume: `25` checkpoints reused, `0` games executed

This run is a measurement and resource-regression checkpoint. It does not
claim score progress.

## Resource result

- all 25 worker exits: `0`
- all 25 measured worker swaps: `0`
- maximum worker RSS: `143852 KB` (`KA59`)
- retained `SB26` behavior projection: exactly equal to the pre-fix baseline
- retained `SB26` maximum RSS: `1666868 KB -> 110792 KB`
- observed host-wide residual swap: `279 MB`

The host-wide residual value is informational; no measured worker swapped.

## Capability judgment

- C2 post-action visible-effect observer: `CLUSTER_STABLE / PASS`
- C3 non-circular boundary predictor: `LOCAL_PROBE / HOLD`
- C2+C3 work block: `HOLD`
- C10 materially new one-step visible-context probe: `LOCAL_PROBE / PASS`
- C10 cluster stability and composability: `HOLD`
- Runtime P compile / promotion: not authorized

The stored transition field named `predicted_boundary` is recomputed from the
same post-action evidence as the observed label. The v2 predictive audit gives
it no predictive credit. C3 is evaluated from pre-action source structure and
action information with leave-one-game-out and prequential controls.

## Persistence policy

The full raw report and all 25 full checkpoint payloads remain in ignored
operator-local `scratch/p10-c2-c3-cluster-v2-all25-max450/`. They are not
duplicated into Git because the previous evidence set already demonstrated
that this pattern adds more than 150 MB per run.

Git retains:

- compact evidence with all emissions, transition contrasts, and trace roots;
- the content-bound checkpoint index;
- all worker and resource logs;
- the full `SB26` checkpoint required by the retention/removal audit;
- local-oracle, standard-budget, C2/C3, C10, and retention judgments.

Raw report SHA-256:
`4da99e99398371e5d28d61fc804eddbec1d87aae8dc30548bf3d773bbff1ed8c`.
Compact evidence SHA-256:
`4704259a42f80dec8caa708227038a7084b8b51141e2da18bad96c4c133cd2d0`.
