# Caller-side native guard repair: pure-tested derivative

Status: bounded pure-test pass, pending independent final review. No new native Query, Teach, native save/load, SDK, Action, live environment call, or Git operation was made. This is launcher preparation, not a new learned ability or permission to run Teach.

## Authority and immutable baseline

Owner directives, AGENTS.md, hierarchy and current state from the preservation recovery were reread. HDS v0.4.2 remains unchanged; full observation, all candidates and failures/HOLD remain required. The completed native Query pilot is immutable. `prechange_pins.json` records all 126 pilot files including successful and failed artifacts. The observer only changes copied family/route binding, never selection or enumeration.

## Existing assets first

The existing `resource_guard_v1.py` performs prospective category accounting and sampled filesystem/free-space checks. It is not an aggregate OS quota. Existing `SaveCapture` deliberately captures exact own-frame references and existing partial outputs and says it is not a second quota ledger. The prior native pilot already had an exclusive evidence file, codec and guard. This derivative tightens those caller-side concepts: fixed reserved regions, a shared metadata/log cap, separate child/parent failure ownership, and entry counters. It neither changes native persistence nor introduces a competing native codec. Record frames wrap the exact caller-supplied native bytes; pure fixture codec helpers exist only in tests.

## Total allocation and all known writes

Store admission measures existing files in its parent, rejects understated accounting, adds every reserved region, and rejects above 96 MiB before creating a new directory. It also checks free storage >=1 GiB plus all requested allocations. Default reservations total 44 MiB: evidence 16; metadata plus both logs 1; worker diagnostic 1; worker emergency 1; supervisor terminal 1; three native states 8 each. A fresh mode-0700 directory and exclusive region files prevent reuse of any prior evidence. All regions are preallocated before operations. Appends reserve/check the complete framed extent before materialization; failed/partial extents are never reused. Metadata and stdout/stderr cannot exceed their combined one-MiB region.

This is a conservative bound on reviewed known writers, NOT an OS aggregate hard quota and NOT a hostile-code sandbox. The child denies unadmitted Python path writes/mutations. Unreviewed writers, SDK/C extensions, subprocess writers, competing filesystem owners or direct use of unrelated writable descriptors are outside the admitted writer inventory. No such writer may be added on the strength of these tests. Path writing is allowed only during the exact native save window. Source hashes, loaded code, class/method identity, engine delegation, persistence function and codec delegation are checked; loaded frozen modules are inspected without invoking them.

Native persistence stays the exact API. Its fresh state region is single-use, with per-file RLIMIT_FSIZE <=8 MiB and inode identity checks. Native Path.write_text truncates its reserve: the logical maximum remains separately accounted, but its physical allocation does NOT survive truncation. Partial outputs are retained in place. Free-space admission does not guarantee survival of ENOSPC or other filesystem failure. No full-retention guarantee under arbitrary disk failure is claimed. External state growth, full failure retention, owned-path and writer-inventory admission remain mandatory before a bounded native unit; neither the small Query result nor these fixtures establish Teach growth.

## Failure and exact frontier

The guard increments at the native invocation boundary, recording entered, returned, and fully persisted counts independently. Caught mid-route failures report the exact entered prefix, incomplete entered ordinal, first unentered ordinal and remaining upper bound. The not-yet-enumerated dynamic suffix count is explicitly unknown, never falsely labeled an entirely untouched route. No automatic resume occurs.

Worker failure, worker emergency and supervisor terminal are physically disjoint regions. The parent never overwrites a child fallback after fork. A small UNKNOWN emergency frame is precomputed before work. The raw fallback uses that frame without JSON/traceback construction or new-file allocation. Exact caught-error progress is preferred when serialization succeeds. The failure path retains the primary exception even when diagnostics fail; partial native failure-state output stays in its owned region. Allocation/I/O failure can still prevent capture. SIGKILL, process death or exhausted capture resources cannot reveal an exact Python invocation frontier; supervisor reports UNKNOWN, not zero or a fabricated exact count. These limits are fundamental and explicitly retained.

## Inline full assignment trace

An optional keyword-only observer is wired through the family/route constructors. Every unique assignment is emitted inline with ordinal, full assignment, match, complete generated detail and rejection/HOLD reason. Observer data is detached; return values have no effect; observer failure propagates and halts subsequent calls. No pruning, top-k, beam, extra semantic rule, or outcome substitution exists. The integrated pure run reproduces all 13 recorded replies, 24 exact reference rows and the original complete semantic result byte-for-byte.

## Verification and remaining gates

Run `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v test_guard test_trace` here under a 512 MiB AS limit. Latest retained log: `pure_tests_attempt07.log`, 21 passing tests. All attempt logs remain. Attempt04 failed because the no-reuse test's old admission limit became too small after measuring existing bytes; the limit was corrected without changing production rejection, and subsequent tests pass. Independent review probes additionally cover preencoded capture after injected MemoryError and post-return persistence failure.

`launch_native` is the minimal integrated caller binding, without a native launch CLI or automatic transition. It requires explicit external witness, growth, failure-retention and writer-inventory admission. It applies 512 MiB AS, CPU/file limits, a wall supervisor, normal/post/failure native save binding, bounded logs, and full trace retention. Native save itself has not been executed in this repair. A freshly imported isolated frozen native closure, codec identity and all external witness/growth checks must be independently admitted before using it. Arbitrary native/SDK writers are not supported.
