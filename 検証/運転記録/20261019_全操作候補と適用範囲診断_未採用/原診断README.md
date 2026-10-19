# Goal6 action bridge: pure diagnostic, fail-closed

## Finding

The existing adapters do NOT provide an action-authorizing closure from goal6. `予測.py`, `手順.py`, and `応答.py` explicitly keep 実行許可=False. They additionally require COPY, MASK, TURN, device geometry and coordinate-support evidence. Goal6 learned only a fixed-mask-condition-pair → public endpoint-progress correspondence. It does not supply those prerequisites.

A minimal pure diagnostic bridge is implemented in bridge.py, reusing only exact whitelisted pure own-source definitions through AST extraction. No historical module import, native HDS, Query, SDK, Action, or Git mutation. All original sources are pinned under origins/; no source is overwritten. Fixed grammar assignment values are read with ast.literal_eval, never executed. This is diagnostic source reuse, not native-module equivalence or runtime adoption.

## Complete comparison and retained evidence

All12 saved whole public rows,112 phases checked against the existing teacher material.35 measured observations reproduce exactly;77 unknown phases remain unknown. All459312 public legal candidates were exhaustively enumerated (112×4101: Action1–5 plus4096 Action6 coordinates). No pruning/top-k/replay selection. Each is retained in all_legal_candidates.jsonl.gz, linked to complete phase records in all_phases.json. Every candidate is HOLD, execution_permission=False.21 phase-local Action5 query proposals are emitted, not executed. Intermediate response phases are diagnostic evidence, never current action authority.

Six teacher before-state tuples match exactly. Terminal status, malformed frame and duplicate availability negative tests retained in test_bridge.py. test_result.json and test_run01.log contain exact execution results. PeakRSS36556KiB under512MiB AS; directory about3MiB under96MiB. No test failure occurred. Tool inspection errors outside code were read-only (an inventory root was not a list); no failed native or hidden execution was concealed.

## Structural scope, not identity scope

Input to phase(frame,status,available) has no game/level/source/hash/replay key. The fixed parser requires64×64, unique background, the existing color4 reference-frame/palette grammar, a10×10 public reference and target, a red instrument and nonzero direction. Existing exact relative device-role pixels are checked against the12 fixed visible templates. These are structural prior applicability checks, not proof that another visually matching environment has the same action semantics.

The existing parser chooses the largest red component as instrument, then classifies Action1–4 as direction and Action5 as wide-paint by fixed action-number mapping. Those are prior assumptions, not learned causal evidence. Therefore even a structural match cannot be promoted to action permission. Unknown phases never get invented roles. Known phases retain role_hypothesis, not certified roles. All unsupported clicks remain present as HOLD, including coordinates inside visually similar rectangles without demonstrated click equivalence.

The bridge's mask derives depth=dx(2x−n+1)+dy(2y−n+1), wide mask depth≥0. It records every100 target coordinates, public goal color, current color, candidate membership and predicted color. It maps all-repair/all-preserve to the exact learned string tuple API. This is the same hypothesis that generated the teachers, not a learned mask or unique true success condition.

## Existing assets inspected and limits

- goal6 archive own-source perception, relation vocabulary, prediction, all-candidates, planning, response gate and12device-template grammar recovered intact.
- The recovered goal6 native states concern the endpoint relation only; current lineage has column boundaries plus goal6. No COPY/MASK/TURN principle was demonstrated installed by this work.
- The available baseline prior-memory files were searched for the exact COPY/MASK/TURN boundaries; none contains them. This limited negative search is not a claim that no historical learned state exists. A verified archive location has been requested from the publication worker. Recover such a state and its support witnesses before creating replacement learning machinery.
- Existing response gate already refuses unexplained phases, action-argument mismatch, changed problem binding, reset/progress, and lack of supported terminal prediction. Reuse that contract; do not weaken it to make goal6 succeed.

## Useful public causal evidence now established

mask_endpoint_checks.json compares the prior mask prediction to every measured post phase. For all6 actions, old-problem phases13/14 exactly match fixed half-plane overwrite with unchanged tool color/direction. For5 cases, early phases0/1 do not yet match the predicted endpoint. Case3 already matches early. All six have11 uninterpreted intermediate phases. Positive cases4/5 have phase15 with a changed reference binding, and tool/direction may change. Those are boundaries requiring problem-history separation, not permitted evidence that the old goal persisted.

This can support an explicitly old-problem ENDPOINT overwrite relation with complete raw-phase uncertainty retained. It cannot support all-phase preservation. Pixels already equal to tool color are observationally non-identifying: unchanged color does not establish whether overwrite occurred. Do not count100 correlated pixels as100 independent Action experiments.

## Minimum practical pre-Action gates

1. Observe a complete fresh public packet, status NOT_FINISHED, exact legal-action set and sequence. The historical112 phases do not authorize a current environment action.
2. Structurally parse current terminal frame, reject ambiguity in reference/target/tool/palette/device roles. A largest-component heuristic alone is insufficient causal role confirmation.
3. Establish observed action-role mapping in the relevant structural scope, including actual action arguments. In particular Action5→wide-paint is not inferred solely from its number.
4. Use verified applicable COPY/MASK/TURN and target-click support, or explicitly HOLD missing mappings. Do not use goal6 as their substitute.
5. Form every legal candidate, including all click coordinates. Record all unresolved alternatives; no selected ID/hash/source branch.
6. Establish public reference/goal predicate, mask prerequisites and preservation/repair independently enough for the learned goal6 boundary to apply. Query the real HDS only in a separately admitted unit. Positive endpoint progress prediction does not imply action safety/permission.
7. Require separate action target permission and fail-closed response contract: whole phases retained, actual action echo bound, expected visible deltas/status/availability/reward checked, hidden delta unknown, no unexplained intermediates silently ignored, old problem reset on progress/structural change.
8. Only after those gates and separate authorization/admission may a one-action fresh pilot be considered. No plan replay or future action based on stale predicted frames.

## Reuse-first teacher plan to close the causal chain

Read TEACHER_PLAN.md. It names precise existing relation targets, evidence needed, ambiguity negatives, and a bounded endpoint-first option. No new mechanism or native learning is proposed as already established. The absence of action-role and all-phase support is a genuine gate; this diagnostic bridge does not bypass it.

### Historical state search result

Publication worker confirmed no verified wide-paint native-state pointer: historical Color3/Query3/Color12/Query1 and native29489/fixture18870 closures remain unresolved. The listed goalset4/prepsave/CP3/recovery archives must not be described as containing that missing state without inspection. This package therefore leaves COPY/MASK/TURN historical-principle reuse unverified, rather than claiming absence or manufacturing new support.

## Superseding scope fix and attribution (v2)

Review found the v1 reusable candidate helper could emit a diagnostic goal6 Query proposal for Action5 absent from availability or carrying malformed arguments. It still returned HOLD/no execution permission, but Query scope was not fail-closed. Exact pre-fix sources, corpus outputs, result, manifest and reproduction probes are preserved in pre_fix_v1/. v2 requires exact action{id,data}, strict available integer ID, valid unique availability list, empty arguments for non-click actions, and exact integer x/y within0..63 for clicks. Unknown fields, bool coordinates, missing keys and unavailable actions yield no Query proposal.

All112 existing phase outputs are byte-identical and all459312 decompressed candidate records are byte-identical after the fix. Fifteen invalid-scope probes and repeated-call purity checks pass; see scope_regression_v2.json. No reentrancy state or native calls are introduced. Old MANIFEST.json is retained; MANIFEST_v2.json identifies supersession.

Full all6×100 target attribution, with every post phase, is in all6_full_attribution_v2.json. Endpoints13/14 classify210 observable changes to tool color,240 preserved prior colors,150 unidentifiable prior=tool pixels. Counts by case are retained. Case3 has100/100 prior=tool and therefore supplies NO independent positive evidence of overwrite versus no-op. Its endpoint fit is observationally non-identifying. Case2 has10 and case5 has40 similarly ambiguous pixels. Do not discard these negatives/ambiguities or treat pixels/phases as independent Actions. Public outcome-level experience remains a valid historical observation, but a MASK causal teacher must explicitly require observable identification and keep ambiguous cells unlabelled. No native teacher payload was manufactured from mere fit.

### v3 red-role guard

A further fixed-prior guard inspects every red component, rejects equal largest components and multiple plausible single-color instrument components, and requires the sole plausible component to match the parsed instrument rectangle. It never certifies the role merely by selecting the largest. Multiple plausible instrument probe is retained in ambiguous_instrument_probe_v3.json; it yields no Query proposal. Existing all112 phase and459312 candidate outputs remain byte-identical. Unique grammar remains a fixed prior, not causal proof.

The reviewer’s full600 audited attribution rows are copied intact as reviewer_pixel_attribution.json and joined to the independently retained full-phase attribution: all600 old/new/tool/membership values agree. reviewer_attribution_join.json pins that source. Use these reviewed rows in the teacher plan rather than counting the independent recomputation as evidence. pre_red_guard_v2/ preserves the preceding source/configuration. MANIFEST_v3.json is the new additive manifest.
