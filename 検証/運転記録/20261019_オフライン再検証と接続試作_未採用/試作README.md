# 目標相対再始動_v1: offline contract harness (NOT ADOPTED)

## Result and scope

The new source is an isolated one-action, injected/mock connection owner. It is not a goal solver, learner, production launcher, replacement historical wrapper, or adopted native connection. `native起動` always raises HOLD. No HDS/SDK import, restore, Query, Teach, live Action, Git write, or core/authority/state edit occurred.

45 pure tests pass in `reports/run04`; 34 negative/subtest records are retained. Independent review found three additional boundary failures after run02: mutable output state read after persistence, a query following save-triggered reentrant HOLD, and provenance deepcopy outside the acquired-lock try/finally. The pre-fix run02 source/runner are retained. All three have regression tests; additional factory-reentry, input-boundary mutation, and action-return retention probes are included. The first run had one test-fixture error and is preserved with its exact source/runner in `reports/run01`. Counts are contract checks, not capability. Earlier original suites remain 38 baseline / 63 combined (38+25), not 101 distinct tests. They were not rerun or overwritten by this unit.

Historical serialized state remains counters 6647 / 183 experiences / 16 principles, not natively restored here. Historical ability 1/183 remains unremeasured. No learning, goal-policy acquisition, transfer, or performance gain is established.

## Reproduce

From this directory, with a NEW result leaf each time:

    ulimit -v 524288
    PYTHONDONTWRITEBYTECODE=1 python -B verify_manifest.py
    PYTHONDONTWRITEBYTECODE=1 python -B tests/test_connection.py reports/NEW_LEAF

The two exact pure public dependencies are copied under `dependencies/`. No install, network, SDK extraction, native import, or path monkeypatch is needed. The test runner prepends only these new local dependency/source directories; dependency hashes must pass first. The module itself is not a hardened malicious-plugin sandbox. Callbacks are trusted test doubles; production callbacks are out of scope.

## Implemented call graph

1. Constructor explicitly requires pure-test mode; claims exclusive object-identity ownership of injected machine/environment/writer and the creating thread. Claims are retained for this bounded process; there is no release/recovery route.
2. `一手`: validate public observation with unchanged `ARC3境界.観測する`; retain full frames and provenance; use unchanged `図式観測.成分群` for purely visible component facts.
3. Exhaustively enumerate every public legal action; ACTION6 covers all 4096 coordinates, including outside the visible frame dimensions. This is legality enumeration, not structural semantic inference or an assertion that all coordinates work. No top-k or pruning.
4. Persist before-query evidence. Construct the exact existing `外部入力` shape, operation mapping boundary `公開列図式:観測された解答作業と行動ID`, and `{'解答作業': operation}`. Only three existing operations are admitted. IDs, files, hashes, teacher evidence and provenance are not query features.
5. Invoke only injected `照会する`; retain exact returned object plus detached full public output and trace. Persist its receipt. Validate public HOLD/conflict fields, every relevant prediction's exact integer type and support reference. Classify and retain every legal candidate. A unique number-to-action match is required. ACTION6 cannot be uniquely bound by this small operation-ID harness and HOLDs with all candidates retained.
6. Build `HDS確定作用` internally from that returned prediction and persisted output receipt, never from a caller-provided confirmed flag. Persist before action; call unchanged `作用を排出する` with injected mock GameAction/environment.
7. Persist entire after-response before parsing; retain complete after observation and full frames, visible/status/availability/level/reset/run changes, exposed reward, success/failure, explicit unknown hidden delta, and unproven temporal causality. Persist completion. One-shot HOLD then prevents all subsequent calls.
8. Any failure latches HOLD, retains the original exception object, current record, pending persistence payload and completed receipts. No query, action, save retry, automatic recovery or next observation is attempted. The test controller writes failure evidence separately after unwinding; durable emergency failure capture is a native gate, not claimed here.

## Existing capability inspected first

`candidate_query_v5.semantic_entry` already supplies the meaningful public-frame → fixed-family scene → learned roles → complete goal pool → complete structural candidates path. `candidate_preservation_v1` already binds 4px target centers (+2) with action mapping, goal-relative effect and preservation queries. It retains unsupported classes and leaves execution disabled. `candidate_goalset_v2` extends nonempty multi-goal semantics, delegating unique/empty cases; `goalset_common_v4` pins old absolute dependency paths and derives a pure fixed enumeration from existing source.

These establish existing semantic/coordinate assets. Their coordinates are not absent HDS capability. This harness does not replace, flatten or certify those assets. The precise gap is an independently pinned new runtime binding to those semantics, current observation identity, exact HDS returns, applicability/effect/preservation proofs and persistence; plus native verification. Old wrappers are not imported or rewritten. No missing historical bytes are fabricated.

The fixed column assumptions (4px symbols, 6px spacing, 10px containers, row-ordered target, finite/productive repeated columns) are conditional priors, never universal learned rules. This unit applies none of them at runtime. Its operation is a fixture assumption, visibly marked as such; goal/precondition/delta semantics remain unknown. An ID-permutation test verifies only provenance separation, not transfer.

## Persistence boundaries and limits

`証拠保存` is a new owned JSON evidence writer, not a native codec or state saver. It uses exclusive create, file and directory fsync, exact full readback, digest/length receipts, and full directory byte accounting before and after writes. The offline cap is 96 MiB with a 256 KiB reserved margin. It records peak RSS and current AS limits; the launch command enforces 512 MiB AS. These numbers describe this small offline workload, not lowered production thresholds. The root must already be a trusted single-owner directory. It rejects root/descendant symlinks but does not claim adversarial race-free ancestor confinement. No concurrent external filesystem mutator is supported.

Failure stops this writer permanently and keeps pending bytes and completed receipts. It does not use the earlier `SaveCapture` adapter, whose exact-method/clock/standard-codec contract does not apply to this simpler writer. Thus the prior capture tests are not claimed as certification of these new methods. Native-state serialization, normal-codec roundtrip, timer-interruption and emergency durable capture remain untested and blocked.

## Native pilot gates (separate authorization/scope required)

1. Independently review source/dependency manifest and pure tests. Re-read Owner originals/AGENTS/authority/state and pin current main before the next unit. Preserve fixed v0.4.2 and authority unchanged.
2. Build a separately named, exact dependency closure for the existing semantic entry/candidate/preservation/goalset functions. Do not revive historical absolute paths, monkeypatch modules or infer equivalence to fresh043. Verify whole public response and terminal phase, current identity and all frames; unsupported family must HOLD.
3. Preserve the exact existing input/output contracts, every mapping/effect/preservation query and candidate, returned HDS objects/support evidence, and current observation → target/coordinates → exact action binding. Confirm preconditions and preservation against all candidates; ambiguity/unknown/contradiction HOLD. No arbitrary first candidate, unexplained clipping or assumed universal safety.
4. Specify the actual bounded native workload, complete worst-case disk/RAM/time budgets, durable failure reserve and outer latch. Verify native codec/restore/save byte/type/order roundtrip and interruptions with the exact new writer/binding. Do not reuse offline 96MiB as a native budget without measurement. Preserve incomplete writes and primary exceptions.
5. Only then run a separately scoped restore/read-only Query pilot against the exact frozen core and state; require native call tracing, exact state before/after and paired-counter-only change for Query. No SDK/live Action in that pilot.
6. Audit actual public teacher source provenance, target/role/relation/goal predicates and runtime feature separation. Only a subsequent explicitly bounded Teach pilot can establish learning; retain exact input, native judgement, supporting and contradicting experiences, applicability and state/principle delta, then later Query.
7. Live one-action/fresh pilot requires a separately verified official SDK contract and exact semantic decision binding plus all above gates. Reobserve every response and preserve hidden unknowns, failures, HOLD and unprocessed candidates. Transfer claims require same-condition previous/current/delta, all prior-success regression, fresh instances and eligible surface/level/game changes without identity routing.

Historical fresh043 and the missing 358669-byte analysis prevent exact old-run reproduction only. They are not a reason to wait indefinitely or to invent a new policy. This small harness is one verified connection infrastructure unit; actual semantic/native integration remains open.

## Concrete next implementation unit

Rehost the already inspected semantic path as explicitly named derivatives under this new connection: retain the bodies/return schemas of family perception, role/goal enumeration, candidate-preservation and goalset predicates; replace only historical absolute-path loader plumbing with explicit pinned local dependencies and an injected existing 外部入力 constructor. Do not import candidate_query_v5 or goalset wrappers as launchers, execute their top-level loaders, or monkeypatch historical globals. Keep semantic_entry's whole pool, all candidate/effect/preservation queries, unsupported classes and fixed-prior applicability. Compare derivatives to exact old pure function bodies and schema fixtures before native execution. Any unavoidable semantic difference requires a separate documented test and HOLD, not a quiet policy change.

Then replace this harness's fixture-provided operation with that existing semantic result, binding each candidate's exact mapping/effect/preservation return and current target coordinates to the saved observation. Do not use this harness's number-only ambiguity handling as a substitute for the established structural candidate path. The purpose is to reach bounded restore/Query and subsequently real Teach validation, not add another solver or another permanent harness layer.
