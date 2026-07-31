#!/usr/bin/env python3
"""Build the deterministic PH-D03B commitment-only sealed audit corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.sealed_audit import (  # noqa: E402
    write_phase_d03b_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="repository root receiving the five checked sealed artifacts",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    digests = write_phase_d03b_artifacts(root)
    print(
        json.dumps(
            {
                "actual_audit_consumption_count": 0,
                "artifact_count": len(digests),
                "digests": digests,
                "expected_plaintext_stored_count": 0,
                "freeze_status": (
                    "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
                ),
                "phase_id": "PH-D03B",
                "status": "PASS",
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
