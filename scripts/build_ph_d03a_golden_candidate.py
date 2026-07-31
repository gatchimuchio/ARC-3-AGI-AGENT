#!/usr/bin/env python3
"""Build the deterministic, non-authoritative PH-D03A Golden candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.golden_corpus import (  # noqa: E402
    write_phase_d03a_candidate_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="repository root receiving the four checked candidate artifacts",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    digests = write_phase_d03a_candidate_artifacts(root)
    print(
        json.dumps(
            {
                "artifact_count": len(digests),
                "candidate_state": "PROPOSED_PENDING_OWNER_APPROVAL",
                "digests": digests,
                "golden_freeze_started": False,
                "owner_approval_generated": False,
                "phase_id": "PH-D03A",
                "sealed_corpus_started": False,
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
