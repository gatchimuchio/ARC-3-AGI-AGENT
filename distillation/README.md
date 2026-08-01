# HDS Distillation Project

This project is the isolated distillation namespace. Its authority
and behavioral boundary is the repository-root `SCOPE_LOCK.md`.

## Current authority status

`PH-D06` is the only active phase. PH-D05 is Owner-approved against exact
canonical teacher-corpus implementation, replay, deterministic rebuild,
evidence, and content-specific decision/approval commits. Existing pre-audit PH-D01A
through PH-D03A phase records remain historical; colliding PH-D01B, PH-D02A,
PH-D02B, PH-D02C, and PH-D03A control artifacts are preserved under
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D01B/` and
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D02A/` and
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D02B/` and
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D02C/` and
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D03A/`. They are not current
phase-pass, promotion, or completion evidence.

The Owner-approved `PH-D01A` rebind validates and hardens:

- a declarative source-admission plan;
- eight strict ARC2/ARC3 SourceProfile documents;
- metadata-only source and contamination inventory;
- deterministic inventory validation and evidence;
- explicit metadata-only provenance from all 25 raw recordings and 183
  covered levels to FULL and both S5 canonical corpus representations;
- strict raw-manifest game, row, split, level, action, filename, and pinned
  trajectory-hash accounting;
- explicit zero admission for policy weights, Derived Distillation Evidence,
  and Governance Artifacts;
- trusted static scope markers;
- a deterministic Scope Guard;
- dedicated tests;
- canonical scope-audit evidence.

The Owner-approved `PH-D01B` rebind freezes the admitted byte identities and their
execution context:

- eight `SourceContentManifest` documents covering all 83 admitted sources;
- eight separate `AcquisitionRecord` documents;
- one complete ARC3 replay `EnvironmentManifest`;
- one revision-pinned raw-recording verification `RunManifest`;
- domain-separated file/path/size Merkle roots;
- exact ARC2 members, 50 ARC3 archive aliases, two ARC3 wheels, Python
  3.12.13, Windows/AMD64, installed distributions, seed/reset, and source
  non-mutation;
- deterministic freeze and isolation reports.
- separate process identities and checkout projections for the replay harness
  maintainer, distillation executor, and distillation auditor;
- Linux bubblewrap mount and network namespace evidence proving that the
  executor and auditor do not receive the environment source tree or original
  repository root.
- an exact downstream invalidation report for three pre-audit PH-D02B
  artifacts whose embedded environment/run bindings are now stale; their
  checked bytes remain preserved and PH-D02B rebuild stays suspended until
  PH-D02A and then PH-D02B are entered in roadmap order.

The Owner-approved `PH-D02A` rebind revalidates and hardens the common deterministic
representation layer used by later distillation schemas:

- strict canonical UTF-8 JSON with Unicode NFC and explicit unordered-array
  pointers;
- integer `confidence_ppm`, content-derived IDs, and explicit top-level
  digest-exclusion categories;
- domain-separated logical-content, physical-package, raw-trajectory, and
  canonical-trajectory digests;
- canonical `ZIP_STORED` bytes with fixed metadata and member order;
- dependency-free canonical NPY v1 and NPZ encoding with fixed dtype,
  little endian, C-order shape, member order, and non-finite rejection;
- committed JSON/ZIP/NPZ test vectors and three-process reproducibility tests.

PH-D02A uses synthetic vectors only. It did not read or normalize real
teacher trajectories, generate HDS hypotheses, or implement Bridge/Runtime
capability.

The Owner-approved post-audit `PH-D02B` rebind adds the static schema and bundle
record boundary:

- exactly 38 authority-named HDS rev2 schemas plus exactly 7
  HDSStructureBundle schemas under `schema_sets/ph_d02b_v1/`;
- a content-bound 45-schema contract with one primary identity and digest
  policy per record type;
- an exact one-to-one mapping from all 38 HDS rev2 schemas to the 7 canonical
  bundle record projections without duplicate evidence scoring;
- seven independent HDS state axes and explicit RawObservation,
  DeterministicDerivation, and InterpretationHypothesis separation;
- a standard-library-only structural, content-identity, typed cross-file
  reference, dependency-lock, version, and package-inventory validator;
- one mutually resolvable synthetic example per all 45 schemas, a two-model
  MULTI_CAUSAL fixture, a no-selection SUSPEND fixture, and deterministic
  adversarial cases with stable failure codes;
- fail-closed rejection for duplicate/dangling/wrong-kind/wrong-target
  references, partial bundles, unknown files, unknown versions, and
  dependency-lock drift;
- fail-closed Owner approval and promotion boundaries: checked fixtures contain
  only a non-authoritative `SCHEMA_TEMPLATE`, never an Owner decision;
- deterministic schema conformance evidence for DG-00, DG-01, DG-02, and the
  schema-only portion of DG-14.

The Owner-approved post-audit `PH-D02C` rebind derives a synthetic-only executable
Causal IR boundary from the approved PH-D02B schema set:

- exactly 18 canonical JSON-native common types, 33 ARC2 opcodes, and 18 ARC3
  opcodes;
- exactly 45 derived schemas, with 43 byte-identical to PH-D02B and explicit
  version migrations only for HypothesisIR and OperatorRegistry;
- complete, content-bound ARC2/ARC3 operator registries with explicit input,
  output, parameter, precondition, execution, invalid-operation,
  cardinality, resource, commutativity, and test-vector metadata;
- closed executable `HypothesisIR` nodes and a Code/IR ABI binding the
  interpreter contract, refined schema contract, registries, type system,
  resource model, and canonical serialization;
- a dependency-free type checker and pure declared-order interpreter with
  canonical trace/result digests;
- stable fail-closed errors for malformed types, unknown/version-mismatched
  opcodes, references, preconditions, invalid operations, cardinality, ABI,
  identity routing, answer copying, and causal overclaim;
- `SUSPEND_RESOURCE` with `SUSPEND`/`HOLD`/`INCONCLUSIVE` rather than hidden
  failure when the declared step budget is exhausted;
- one checked synthetic vector for every opcode, 15 adversarial programs, an
  exact comparator, and a bounded synthetic intervention runner that emits no
  causal claim;
- deterministic conformance evidence for DG-03, DG-08, DG-09, and DG-12.

The 12 pre-audit schema/generated-IR candidates are preserved byte-identically
under `input/historical_pre_audit/PH-D02C/`. They are revalidated input only,
not current evidence. Current artifacts bind the approved PH-D02B evidence,
the PH-D02C entry approval, and the current WorkBlockFrame.

The Owner-approved post-audit `PH-D03A` rebind adds a Golden
implementation-conformance candidate layer:

- exactly eight authority-listed ARC2 categories and eight authority-listed
  ARC3 categories, represented by 16 deterministic synthetic cases;
- RawObservation, DeterministicDerivation, InterpretationHypothesis, at least
  two typed HypothesisIR alternatives, exact-fit accounting, a pre-result
  frozen bounded intervention, InterventionResult, HDSCausalRecord,
  FailureSignature, GateResult, and ApprovalRecord schema template per case;
- complete behaviorally recomputed coverage of DG-00 through DG-15. Coverage
  is derived from case structure, IR re-execution, exact-fit reconstruction,
  and negative probes rather than trusting each declared GateResult;
- explicit resource suspension, unsupported-opcode accounting,
  pending-Owner suspension, recursive privileged-route rejection, authority
  fabrication rejection, and rejection of unapproved commit or promotion;
- a content-bound candidate set, gate-coverage report, and Owner review
  request reconstructed byte-identically in three independent processes;
- only non-authoritative in-candidate `SCHEMA_TEMPLATE` approvals with
  `SUSPEND`; the later exact target bundle and external OwnerDecisionCapture
  approve all sixteen expectation digests without mutating candidate bytes.

The Owner-approved `PH-D03B` work block freezes those sixteen exact approved
expectation digests as an immutable commitment-only sealed audit input:

- exactly sixteen unique, lexicographically ordered commitments with no
  fixture IDs, labels, or expected-artifact plaintext;
- exact raw-byte and bound-digest records for the Golden source artifacts,
  target bundle, PH-D03A evidence attestation, OwnerDecisionCapture, and
  ApprovalRecord;
- a canonical manifest, runner contract, and freeze report for
  `DISTILLATION_CONFORMANCE_CORPUS_FROZEN`;
- an audit-only runner that recomputes submitted logical digests and emits
  exact `PASS\n` or `FAIL\n` bytes;
- atomic consume-on-first-attempt state in a caller-supplied mutable ledger
  outside the repository, with reuse returning `FAIL`;
- behaviorally checked DG-06 and DG-14 boundaries and zero real-source,
  normalization, promotion, Bridge, Runtime, official, or Kaggle activity.

The compiler hashes source bytes but does not semantically parse, import,
execute, or replay them. The only network evidence is the already frozen,
revision-checked, read-only Dataset Viewer capture. Manifest compilation itself
does not access a network.

PH-D03B reads the approved PH-D03A Golden files semantically only while
building the commitment set. At audit time it parses only the sealed contract,
commitments, manifest, runner contract, and submitted artifact values; Golden
source files are raw-hash checked without expected-plaintext parsing. It does
not normalize a real trajectory, execute source or replay, generate or rank
general candidates, establish a real causal mechanism, promote Rules, create
a Bridge, agent, or runtime, access locked-final or official data, or create
submission output. Historical runtime canonical helpers are not imported into
the isolated distillation package.

The checked pre-audit artifacts, source, and tests remain byte-identical under
`input/historical_pre_audit/PH-D03A/` and are ineligible for current
activation. The four checked PH-D03A artifacts remain byte-identical and are
bound by the external exact target bundle and Owner approval. PH-D03B never
rewrites those Golden artifacts.

The Owner-approved `PH-D05` work block normalizes every one of the 25 pinned ARC3
public winning recordings into a deterministic canonical teacher corpus:

- all 25 raw payloads are acquired only at the pinned dataset revision,
  size/SHA-256 checked, and retained in an external cache rather than Git;
- all 183 levels, 11,648 recorded actions, and the 11,574-action validated
  successful corpus are bound without treating raw and canonical trajectories
  as the same object;
- RESET and ACTION1 through ACTION7 remain numeric action surfaces, ACTION6
  requires complete integer x/y, and routing metadata is excluded from the
  semantic action payload;
- every transition binds before/action/after, available actions, terminal
  state, level progress, raw-frame provenance, a lossless canonical frame, and
  an invertible visible diff;
- the one validated local solution override is explicit and preserves its
  distinct 149-action raw source projection beside the 75-action canonical
  replay;
- three secret-scrubbed, network-denied, fixed-seed OFFLINE replay processes
  complete 25 games and 183 levels with zero canonical frame, action,
  availability, terminal, or progress mismatch;
- three independent canonical builds produce byte-identical manifest,
  25 package files, and normalization report;
- DG-00, DG-06, DG-10, DG-11, and DG-12 are recomputed while hypothesis,
  causal assertion, intervention, promotion, Bridge, Runtime, official, and
  Kaggle counts remain zero.

The current `PH-D06` work block consumes that canonical corpus through three
source-blind, network-isolated executor processes and deterministically emits:

- exactly 18 candidates for each of 25 teacher cases;
- exactly 16 typed executable IR candidates and two fail-closed privilege
  adversaries per case;
- selector-family and operator/ordering alternatives sufficient for the
  Alternative Adequacy gate;
- explicit `IR_ANSWER_COPY_FORBIDDEN` and
  `IR_IDENTITY_ROUTING_FORBIDDEN` rejection evidence;
- byte-identical manifest and 25 package files across three independent
  builds;
- zero automatic adoption, fit execution, causal assertion, intervention,
  promotion, Bridge, Runtime, official access, or Kaggle mutation.

The resulting multi-hypothesis corpus is evidence input for PH-D07A teacher
fit. It does not select a hypothesis, establish a causal model, approve a
Rule, create a StructureBundle, or add runtime capability.

PH-D06 additionally pins the source-blind interpreter itself. The external
runtime archive must be the official
`cpython-3.12.13+20260728-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`
asset with SHA-256
`7ceaf4360f4b4ab44f31d8217cfdc70df8e12b61d9561b4900ee7af87176e50d`.
Its extracted 4,522-entry tree digest must be
`hds-ph-d06-python-runtime-tree:bb0341f8ca64f9830163873839b08ba8a0cb1f6abb9a56cc9762fb5ce9196d7f`,
and `bin/python3` must have SHA-256
`1e4461092175d186c4bcdb19ee2849a45d6e4d8d1f6a871e45f63418d52a4e35`.
The archive and extracted runtime remain outside Git. The build performs no
network acquisition and rejects a missing, modified, writable-in-namespace,
or version-mismatched runtime before candidate generation.

Use exactly Python 3.12.13. From the repository root, set the two paths to a
content-verified external cache before the PH-D06 build:

```text
export ARC3_PH_D06_PYTHON_RUNTIME_ARCHIVE=<external-cache>/cpython-3.12.13+20260728-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
export ARC3_PH_D06_PYTHON_RUNTIME_ROOT=<external-cache>/cpython-3.12.13+20260728-x86_64-unknown-linux-gnu-frozen
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=distillation/src "$ARC3_PH_D06_PYTHON_RUNTIME_ROOT/bin/python3" \
  scripts/build_ph_d06_hypothesis_candidates.py --write
PYTHONPATH=distillation/src "$ARC3_PH_D06_PYTHON_RUNTIME_ROOT/bin/python3" \
  scripts/build_ph_d06_hypothesis_candidates.py --verify
PYTHONPATH=distillation/src python -m pytest distillation/tests
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_canonical.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_post_audit_schema_bundle.py
python scripts/build_ph_d02b_schema_bundle.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_post_audit_causal_ir_schema.py \
  distillation/tests/unit/test_causal_ir.py
python scripts/build_ph_d02c_causal_ir.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_golden_corpus.py
python scripts/build_ph_d03a_golden_candidate.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_sealed_audit.py
python scripts/build_ph_d03b_sealed_audit.py
python scripts/run_ph_d03b_sealed_audit.py \
  --submission <canonical-submission.json> \
  --ledger <outside-repository-ledger.json>
python scripts/acquire_ph_d05_teacher_recordings.py \
  --output-dir <external-content-verified-cache>
python scripts/run_ph_d05_replay_x3.py \
  --output-root <external-replay-cache>
python scripts/build_ph_d05_teacher_trajectories.py \
  --raw-recordings-dir <external-content-verified-cache> \
  --replay-capture-dir <external-replay-cache>/run-1/captures
python scripts/build_ph_d05_teacher_trajectories.py \
  --verify-rebuild-root <independent-build-2> \
  --verify-rebuild-root <independent-build-3>
PYTHONPATH=distillation/src python -m ruff check \
  distillation/src distillation/tests
PYTHONPATH=distillation/src python -m mypy --strict \
  distillation/src distillation/tests
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.schema_registry import build_phase_d02b_artifacts; expected=build_phase_d02b_artifacts(Path('.')); assert all((Path('.') / path).read_bytes() == payload for path, payload in expected.items())"
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.verification import build_phase_d02c_artifacts; expected=build_phase_d02c_artifacts(Path('.')); assert all((Path('.') / path).read_bytes() == payload for path, payload in expected.items())"
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_golden_corpus.py::test_pre_audit_artifacts_are_snapshotted_and_current_bytes_are_rebuilt
python distillation/src/hds_distill/scope_guard.py \
  --project-root distillation \
  --repository-root . \
  --verify-report distillation/artifacts/reports/distillation_scope_audit.json
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.source_inventory import verify_source_inventory_report; verify_source_inventory_report(Path('distillation/artifacts/reports/source_inventory.json'), Path('distillation'), repository_root=Path('.'))"
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.source_inventory import verify_primary_source_provenance_report; verify_primary_source_provenance_report(Path('distillation/artifacts/reports/primary_source_provenance.json'), Path('distillation'), repository_root=Path('.'))"
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.manifest_freeze import verify_manifest_freeze_artifacts; verify_manifest_freeze_artifacts(Path('distillation'), repository_root=Path('.'), distribution_paths={'arc-prize-2026-arc-agi-2.zip': Path('../Downloads/arc-prize-2026-arc-agi-2.zip'), 'arc-prize-2026-arc-agi-3.zip': Path('../Downloads/arc-prize-2026-arc-agi-3.zip')})"
python scripts/verify_source_blind_execution.py --verify-report
```

On this checkout, validation uses
`ARC-AGI-3-Agents/.venv/Scripts/python.exe` because that interpreter is the
existing exact Python 3.12.13 environment. The distillation package does not
import or depend on the historical ARC package in that environment.
