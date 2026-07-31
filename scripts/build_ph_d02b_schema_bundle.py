#!/usr/bin/env python3
"""Build deterministic post-audit PH-D02B schema and bundle artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation/src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.post_audit_schema_bundle import (  # noqa: E402
    write_post_audit_artifacts,
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
    paths = write_post_audit_artifacts(root)
    for path in paths:
        print(path.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
