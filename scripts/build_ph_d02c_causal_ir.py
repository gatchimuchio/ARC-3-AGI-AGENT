#!/usr/bin/env python3
"""Build deterministic post-audit PH-D02C Typed Causal IR artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation/src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.verification import (  # noqa: E402
    write_phase_d02c_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
    )
    args = parser.parse_args()
    root = args.repository_root.resolve()
    digests = write_phase_d02c_artifacts(root)
    for path, digest in sorted(digests.items()):
        print(f"{digest}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
