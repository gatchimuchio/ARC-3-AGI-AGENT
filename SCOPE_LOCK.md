# PH-D00B Distillation Scope Lock

- Scope ID: `ARC3_HDS_DISTILLATION_SCOPE_D00B_V1`
- Phase: `PH-D00B`
- Work Block: `WB-PH-D00B-DISTILLATION-REPOSITORY-BOOTSTRAP-REBIND-20260731`
- Exit claim: `DISTILLATION_SCOPE_GUARD_PASS`
- Final promotion authority: 大平鉄兵

This is the post-audit current Work Block. Earlier PH-D00B phase state,
transitions, and review evidence are preserved under
`control/rev3/HISTORICAL_PRE_AUDIT/PH-D00B/` and are not current completion
evidence.

## Purpose

`distillation/` is an isolated development project for deriving auditable HDS
structure from explicitly labeled development evidence. It is not an ARC
solver, production agent, runtime, network client, or submission builder.

The D00B boundary is:

```text
distillation/  # executable static audit and future distillation-only code
bridge/        # semantically empty; `.gitkeep` only
runtime/       # documentation-only read-only reference
```

No module in `distillation/` may import or execute code from `bridge/`,
`runtime/`, `ARC-AGI-3-Agents/arc3_agi_agent/`, historical teacher/runtime
packages, official ARC packages, or Kaggle packages.

## Environment lock

The exact interpreter and development tools are:

```text
Python 3.12.13
ruff 0.12.7
mypy 1.17.1
pytest 8.4.1
```

`distillation/pyproject.toml` contains exact pins and has no runtime
dependencies. A different Python patch version is outside the D00B evidence
boundary. The WSL Python 3.14 interpreter is not eligible for D00B validation.

## Allowed behavior

- deterministic, offline static analysis
- deterministic local report generation
- labeled teacher replay
- an offline interpreter whose inputs are an explicit program/model and local
  interpreter state
- synthetic negative fixtures used only by Scope Guard tests

Public callables that receive task-like inputs are allowed only when the
callable imports the trusted `hds_distill.scope_contract.teacher_bound` marker
and also receives explicit teacher evidence such as an expected answer, label,
ground truth, or teacher trajectory. A locally defined marker with the same
name has no authority.

`offline_interpreter` marks a local interpreter boundary. It does not authorize
unknown-task solving, answer generation, networking, runtime imports, or
submission output.

## Forbidden behavior

- official ARC API imports, calls, or competition mode
- network-capable imports or calls
- dynamic imports or source execution
- process execution except the statically bounded read-only
  `git ls-files -- <root>` metadata inventory
- public callables that answer an unlabeled task
- trusted scope-marker rebinding or local marker spoofing
- task, game, level, or case identity routing
- answer maps, full-answer literals, or fixed action sequences
- submission-format artifact generation
- unknown `pyproject.toml` execution surfaces or executable/installable
  artifacts
- runtime, production, historical solver, agent, teacher, or Bridge dependency
- executable code in `bridge/` or `runtime/`
- undeclared or outside-`src/` production entrypoints
- ARC corpus processing before `PH-D01A`
- Rule or RuleAtom promotion
- locked-final, official, or Kaggle access

The guard analyzes AST behavior, resolved import provenance, declared
entrypoints, dependencies, and directory boundaries. It does not decide from a
filename. A valid offline file containing `solver` in its name must pass.

## Local gate

GitHub Actions are intentionally not used. The equivalent mandatory local gate
is:

```text
python distillation/src/hds_distill/scope_guard.py \
  --project-root distillation \
  --repository-root . \
  --verify-report distillation/artifacts/reports/distillation_scope_audit.json
```

Exit status `0` means the checked report matches a finding-free live audit.
Exit status `2` means a scope finding exists. Configuration, parse, or checked
report mismatch is a visible nonzero failure.

## Claim boundary

`DISTILLATION_SCOPE_GUARD_PASS` means only that the D00B repository and
behavior boundary is implemented and finding-free under the recorded audit.
It does not mean causal structure has been discovered, the corpus has been
processed, a Rule has been promoted, the Bridge or AGI Runtime is ready, or an
official submission is authorized.
