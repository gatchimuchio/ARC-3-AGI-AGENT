#!/usr/bin/env python3
"""Run one PH-D03B sealed audit and emit only PASS or FAIL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.sealed_audit import audit_sealed_submission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    arguments = parser.parse_args()
    status = audit_sealed_submission(
        arguments.root.resolve(),
        arguments.submission.resolve(),
        arguments.ledger,
    )
    sys.stdout.buffer.write(status.encode("ascii") + b"\n")
    sys.stdout.buffer.flush()
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
