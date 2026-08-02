# ARC3CompletionAgent v1.0

This directory contains the deterministic local release candidate built from
implementation commit `9e7657281bc31ee4dd97a09bde7e96b567631166`.

## Verify

```bash
cd release/ARC3CompletionAgent-v1.0
sha256sum -c SHA256SUMS
```

Expected wheel SHA-256:

```text
0557c3cbc1fbaf295a25351aad62c9349cdcfdb5fdc5bce669edffdfc4de55de
```

## Install

Use a fresh Python 3.12 environment.

```bash
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps arc3_completion_agent-1.0.0-py3-none-any.whl
python -m pip check
arc3-completion-product --help
```

The recorded acceptance run also exercised a normal dependency-resolving
installation of the wheel before this resolved lock was written.

## Run the bundled official samples

The official sample environment directory is development input and is not
embedded in the wheel.

```bash
OPERATION_MODE=offline arc3-completion-product \
  --mode offline \
  --environments-dir /path/to/environment_files \
  --action-budget 4096 \
  --report /path/to/product-report.json
```

The endpoint is complete only when the report records 25/25 games as `WIN`,
183/183 completed levels, zero endpoint failures, and a closed scorecard.

External Kaggle Notebook execution or submission is not performed by this
release artifact and requires a separate current Owner authorization.
