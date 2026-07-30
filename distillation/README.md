# HDS Distillation Project

This project is the isolated `PH-D00B` distillation namespace. Its authority
and behavioral boundary is the repository-root `SCOPE_LOCK.md`.

Current contents are deliberately limited to:

- an empty input boundary;
- a schema boundary reserved for later ordered phases;
- trusted static scope markers;
- a deterministic Scope Guard;
- dedicated tests;
- canonical scope-audit evidence.

It does not process ARC data and does not implement Causal IR, candidate
generation, a Bridge, an agent, a runtime, networking, or submission output.

Use exactly Python 3.12.13. From the repository root:

```text
PYTHONPATH=distillation/src python -m pytest distillation/tests
PYTHONPATH=distillation/src python -m ruff check \
  distillation/src distillation/tests
PYTHONPATH=distillation/src python -m mypy --strict \
  distillation/src distillation/tests
python distillation/src/hds_distill/scope_guard.py \
  --project-root distillation \
  --repository-root . \
  --verify-report distillation/artifacts/reports/distillation_scope_audit.json
```

On this checkout, validation uses
`ARC-AGI-3-Agents/.venv/Scripts/python.exe` because that interpreter is the
existing exact Python 3.12.13 environment. The distillation package does not
import or depend on the historical ARC package in that environment.
