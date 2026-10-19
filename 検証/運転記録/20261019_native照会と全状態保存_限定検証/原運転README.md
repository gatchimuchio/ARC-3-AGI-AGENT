# Native HDS Query/save pilot: bounded PASS, independent review pending

The corrected serialized Query/save run passed after two preserved admission failures. This is connection/persistence evidence only. No Teach, SDK, Action, adoption, ability gain or core change.

## Final corrected run

- query_retry02/supervisor.json: return code 0, wall 1.7920s, child CPU 1.7272s, peak RSS 88,452 KiB under 512 MiB AS.
- Existing reviewed semantic route: 13 actual native Queries, 24 assignments examined, one goal pool, five structural candidates. The original enumeration retains rejection counts but not each rejected assignment/HOLD detail; this run did not capture those individually. Native boundary counts: two role, two goal relation, five action mapping, four preparation-effect queries. No repair or preservation Query is implied: this exact packet has no selected inventory/filled slots requiring those branches, and the returned full semantic result retains their original applicability/absence information. Four candidates report effect support; submission remains UNKNOWN. All nine execution-permission flags recursively inspected are false.
- 40 durable native-codec records (13 exact inputs, 13 outputs, 13 post-call inputs, one whole semantic result). Each has fsynced bytes, offset/length/hash receipt and full readback. The ledger reserves 16 MiB and uses 251,453 bytes; trailing unused zeros are not evidence. evidence_index.json gives exact record slices. verify_results.py checks every slice and native codec reconstruction.
- Normal restore→save exactly equals baseline bytes before Query. Full decoded native type/value/order comparison after Query passes except the paired counters 6647→6660. An additional serialized-tree check found exactly those two numeric changes. All 183 observations, 16 principle entries and all other ledger/state/history contents are unchanged. No native learning took place.
- A newly authorized parent resource adjustment increased the aggregate owned-directory ceiling from 96 MiB to 112 MiB (+16 MiB), solely to preserve original failures alongside complete new allocation. Source, AS, query count, compute/finalization limits and HOLD semantics remain unchanged. budget_change.json records authorization and free-space measurement; supervisor rechecks >=1 GiB free and conservative full remaining allocation before launch. Nothing was overwritten/reused in earlier reserves.
- Peak sampled directory size 94,294,341 bytes. Original profile and failed child plus corrected retry consume about 4.01s total measured native-child CPU, below the 120s aggregate budget. The corrected supervisor subtracts earlier measured CPU before setting the retry limit. Finalization remains separately alarm-bounded at 120s.

## Review and limits

Independent review identified an important completeness limit: the original goal enumeration records all-assignment count and aggregate rejection counts, but not each rejected assignment or its individual HOLD/rejection detail. Therefore the original native run is not a complete per-assignment failure trace. A deterministic pure retrospective audit of all 24 assignments from the saved scene/native roles is being prepared separately by the reviewer; it is retrospective evidence, not original native instrumentation. Before future teacher/action adoption, an explicitly reviewed inline per-assignment recorder must capture every assignment and reason without pruning, altering core logic, or mislabeling retrospective reconstruction as original execution evidence.

Read trace_summary.json, query_retry02/result.json, all three supervisor results, budget_change.json, correction_tests.json, and exact runner snapshots. Current result awaits independent review. Guard tests are fixtures; only this one complete saved packet has been exercised with real HDS. The existing permissive role/goal evidence rules remain unmodified, so the diagnostic goal pool/candidates authorize no action. The new serialized owner/persistence wrapper is unadopted.

No hidden state, live legality, public reward or transfer was observed. Native queries do not show learning or better capability. Historical 1/183 is unchanged and unremeasured. A teacher pilot still requires separately audited complete public causal witness/contrast joins, explicit generic predicates, teacher/state/evidence growth admission, real Teach before/after queries and regression, independent review, and no automatic action transition.

## Preserved earlier admission history

The following account was written at the earlier HOLD and is retained for exact failure history; its stopping statements are superseded only by the corrected run above. Exact earlier README and gate report are also retained in query_retry01/.

# Native HDS restore/save profile and retained Query-admission failure

Status: HOLD before first Query. No Teach, SDK, live Action, adoption, or core change.

## Verified results

- Start main fixed at 06961ee02d43329aee746d763cf19d651f97bcaa, independently read back by the sole Git writer and supplied by parent. This worker made no Git writes.
- Re-read the three Owner originals, AGENTS, hierarchy and current state. Exact frozen v0.4.2 closure comprises 12 Python modules, README and pyproject, each checked against baseline archive/member pins. Static import inventory finds only relative package or Python standard-library dependencies. Historical launchers were never imported.
- Copied complete selected public packet (6627 bytes, SHA-256 ce4c2950ac1d3fd1abbd67bb84196397777d080f2f0c6258245be8241b25cdab). All frames were decoded and validated, including frame hash, dimensions, data type, ordinal, byte count and existing ARC3 observation boundary. Explicit observation sequence 0, sole terminal phase 0, four inventory tokens/four slots. This is saved diagnostic evidence, never current-environment authority.
- Separately admitted no-query native codec/save profile: process return code 0; recursive native type/value/dictionary-order/sequence-order equality passed. Native decode/encode reproduces the original exact bytes. Normal HDS API restore→save reproduces all 5,355,957 bytes, fsynced file and directory. Saved counters are 6647/6647, observations 183, principle ledger entries 16, principle histories 15.
- Profile wall 1.1726s, child CPU 1.1205s, peak RSS 70,024 KiB, AS ceiling 512 MiB.
- Query attempt repeats codec and normal restore/save gates successfully, validates the public observation, then fails allocating evidence before guard construction/admission and before any Query. Process return code 1; OSError 27 File too large. Wall 1.1771s, child CPU 1.1604s, peak RSS 70,204 KiB. All files are retained, including the zero-length partial evidence.bin and preallocated failure.reserve. The entire semantic route remains unprocessed.

## Exact failure and attribution

The outer supervisor sets an 8 MiB RLIMIT_FSIZE to protect state artifacts. The worker subsequently attempts to preallocate one 16 MiB evidence file. That incompatible wrapper configuration produces the admission failure. The existing native HDS core did not cause it. There were zero native Query entries and no native post-Query state. Both normal_roundtrip.json artifacts equal the baseline bytes. No candidate/native reply trace exists because execution never reached Query.

The complete raw exception is query/failure.json and stderr.log; process results and resource samples are in each supervisor.json. Profile runner snapshots are preserved in profile/. Current worker.py is the attempted query runner. The preallocated reserve contains a supervisor status prefix and trailing zero padding; it is not a JSON document. Do not parse the complete padded file as JSON.

## Limits of this attempt

The reserved evidence partition was never successfully allocated, so admission.json, guard fixture tests and native route execution were never reached. guard.py is proposed, unvalidated native binding code. The wrapper's no-follow-on-call behavior at this allocation failure is observed; its mutation/reentry/callback-failure handling is not validated by this run. No native role/goal/mapping/effect/preservation behavior or full post-Query state equality is claimed. Existing permissive unsupported-role/UNKNOWN-goal issues remain diagnostic-only limitations.

The supervisor samples aggregate file size and enforces AS/CPU/per-file limits; sampling alone is not a race-free total-directory hard quota. A correction should establish a deterministic full allocation ledger before execution, test the exact combined guard with failures/reentry/mutation, and distinguish state-file from evidence-file limits without raising the agreed 96 MiB total ceiling. Existing failed artifacts consume part of that ceiling and must not be removed. Do not rerun supervise.py in existing profile/query leaves: creation is exclusive and intentionally fails.

## Next bounded correction and subsequent teacher conditions

1. Independently review this failure first. A separately named attempt can split the complete 16 MiB evidence reserve into <=8 MiB chunks, with exact append offsets and complete cross-chunk readback, while preserving every prior file. Calculate the remaining 96 MiB directory capacity including new failure reserve and all saves; if insufficient, ask for a separately admitted directory/budget. Do not truncate evidence or prune queries.
2. Retest recorder/native-codec reconstruction, source pinning, exclusive ownership, reentry, mutation, failures and no-follow-on-calls. Reserve failure/suffix capture before running Query. Enforce the total native compute ceiling cumulatively, with separate finalization timing. Run every admitted semantic call through the exact guard and retain all outputs/HOLDs.
3. Only after successful Query/save and independent full-state comparison may a teacher pilot be admitted. Audit exact public before/after witness joins, target/coordinates, roles/relations, goal/precondition, visible/status/legal-action/level delta and public reward/success/failure, preserving unknown hidden deltas and contrasts. Freeze teacher count/bytes and complete state/evidence growth bounds. Run real processing API on a separate state descendant, with before/after queries and complete ledger/history-prefix checks. No automatic Teach or Action transition.

Native queries are not ability gains. Historical 1/183 is unchanged and unremeasured; no learning, transfer, additional solved level or improved capability is established.

## Authorized correction and second admission gate

The parent authorized correcting the contradictory per-file limits within the unchanged aggregate ceiling. Pure isolated boundary tests passed: 16 MiB evidence allocation permitted, 16 MiB+1 writes refused, separate 8 MiB state-file limit refused an oversized state write. guard.py fixture probes passed normal detached return, input/output recorder failure, mutation, native exception, reentry and stopped subsequent calls. These are wrapper fixture checks, not native semantic behavior.

Before launching a corrected child, the retained supervisor calculated a full conservative remaining allocation: two <=8 MiB state artifacts, 16 MiB evidence, 16 MiB emergency, and 1 MiB metadata/logs. It exceeded the authorized 96 MiB aggregate by approximately 0.66 MiB. query_retry01/admission_failure.json preserves this second, pre-child-launch HOLD. There was no corrected native child, no further restore, and still zero native Query calls.

The parent permitted reusing an existing emergency reserve only if entirely blank and containing no evidence. Both existing reserve files contain original supervisor status prefixes, so reuse was rejected. Their whole hashes, allocated sizes and blank-tail extents are retained in final_gate_report.json; no original failure evidence was changed. This is a verified allocation blocker requiring a separately approved partition or budget. The native retry remains unexecuted. Current worker/supervisor are proposed corrected sources; exact original attempted sources are frozen in query/.
