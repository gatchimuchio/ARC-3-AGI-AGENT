#!/usr/bin/env python3
"""Execute active ARC3 product P/J0/M0 semantic transformation checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.product_genericity import (  # noqa: E402
    PRODUCT_TRANSFORMATION_ACTION_BUDGET,
    run_active_product_transformation_evaluation,
)

DEFAULT_OUTPUT = Path(
    "analysis/product/rev4/m3_active_product_transformation.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--action-budget",
        type=int,
        default=PRODUCT_TRANSFORMATION_ACTION_BUDGET,
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output = arguments.output
    if not output.is_absolute():
        output = root / output
    report = run_active_product_transformation_evaluation(
        seed=int(arguments.seed),
        action_budget=int(arguments.action_budget),
        output_path=output,
    )
    print(
        json.dumps(
            {
                "active_p_body_digest": report["active_p_body_digest"],
                "completed": report["transformation_completion"]["completed"],
                "output": output.as_posix(),
                "required": report["transformation_completion"]["required"],
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
