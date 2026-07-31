# HDS Distillation Project

This project is the isolated distillation namespace. Its authority
and behavioral boundary is the repository-root `SCOPE_LOCK.md`.

## Current authority status

`PH-D01B` is the only active phase. PH-D01A is Owner-approved against exact
post-audit implementation and evidence commits. Existing PH-D01A through
PH-D03A phase records originated before the rev3 audit correction; colliding
PH-D01B control artifacts are preserved under
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D01B/` and are not current phase-pass,
promotion, or completion evidence.

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

The current `PH-D01B` rebind freezes the admitted byte identities and their
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

`PH-D02A` adds the common deterministic representation layer used by later
distillation schemas:

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

`PH-D02B` adds the static schema and HDS record boundary:

- exactly 38 authority-named Draft 2020-12 schemas, with the five PH-D01A/B
  schema files preserved byte-for-byte and 33 closed schemas added;
- a content-bound schema contract with one primary ID, digest policy, and
  typed reference declaration per record type;
- seven independent HDS state axes and explicit RawObservation,
  DeterministicDerivation, and InterpretationHypothesis separation;
- a standard-library-only structural, content-identity, typed-reference, and
  cross-record semantic validator;
- one mutually resolvable synthetic example per schema, a two-model
  MULTI_CAUSAL fixture, a no-selection SUSPEND fixture, and deterministic
  adversarial bundles with stable failure codes;
- fail-closed Owner approval and promotion boundaries: checked fixtures contain
  only a non-authoritative `SCHEMA_TEMPLATE`, never an Owner decision;
- deterministic schema conformance evidence for DG-00, DG-01, DG-02, and the
  schema-only portion of DG-14.

`PH-D02C` adds the synthetic-only executable Causal IR boundary:

- exactly 18 canonical JSON-native common types, 33 ARC2 opcodes, and 18 ARC3
  opcodes;
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

`PH-D03A` adds a non-authoritative Golden conformance candidate layer:

- exactly eight authority-listed ARC2 categories and eight authority-listed
  ARC3 categories, represented by 16 deterministic synthetic cases;
- RawObservation, DeterministicDerivation, InterpretationHypothesis, at least
  two typed HypothesisIR alternatives, exact-fit accounting, a pre-result
  frozen bounded intervention, InterventionResult, HDSCausalRecord,
  FailureSignature, GateResult, and ApprovalRecord schema template per case;
- complete behavioral coverage of DG-00 through DG-15, including explicit
  resource suspension, unsupported-opcode failure, pending-Owner suspension,
  and rejection of unapproved commit or promotion;
- a content-bound candidate set, gate-coverage report, and Owner review
  request reconstructed byte-identically in three independent processes;
- only non-authoritative `SCHEMA_TEMPLATE` approvals with `SUSPEND`; no
  content-specific Owner decision and no Golden expected-artifact freeze.

The compiler hashes source bytes but does not semantically parse, import,
execute, or replay them. The only network evidence is the already frozen,
revision-checked, read-only Dataset Viewer capture. Manifest compilation itself
does not access a network.

PH-D03A executes only checked synthetic typed conformance candidates. It does
not normalize a real trajectory, read teacher/source payloads, freeze Golden
expectations, create the Sealed corpus, generate or rank general candidates,
establish a real causal mechanism, promote Rules, create or simulate Owner
approval, create a Bridge, agent, or runtime, access locked-final or official
data, or create submission output. Historical runtime canonical helpers are
not imported into the isolated distillation package.

Use exactly Python 3.12.13. From the repository root:

```text
PYTHONPATH=distillation/src python -m pytest distillation/tests
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_canonical.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_schema_registry.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_causal_ir.py
PYTHONPATH=distillation/src python -m pytest \
  distillation/tests/unit/test_golden_corpus.py
PYTHONPATH=distillation/src python -m ruff check \
  distillation/src distillation/tests
PYTHONPATH=distillation/src python -m mypy --strict \
  distillation/src distillation/tests
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.schema_registry import build_phase_d02b_artifacts; expected=build_phase_d02b_artifacts(Path('.')); assert all((Path('.') / path).read_bytes() == payload for path, payload in expected.items())"
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.verification import build_phase_d02c_artifacts; expected=build_phase_d02c_artifacts(Path('.')); assert all((Path('.') / path).read_bytes() == payload for path, payload in expected.items())"
PYTHONPATH=distillation/src python -c \
  "from pathlib import Path; from hds_distill.golden_corpus import build_phase_d03a_candidate_artifacts; expected=build_phase_d03a_candidate_artifacts(Path('.')); assert all((Path('.') / path).read_bytes() == payload for path, payload in expected.items())"
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
