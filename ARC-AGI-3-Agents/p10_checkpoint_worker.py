"""Run one P10 sample under the condition digest for the complete sample set.

This development-only worker permits process-level parallel measurement while
retaining one shared all-sample condition digest.  The selected game identity
is used only by the outer OFFLINE harness; it is never provided to Runtime P.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from arc3_agi_agent.p10_batch_checkpoint import (
    build_batch_conditions,
    checkpoint_path,
    load_game_checkpoint,
    write_game_checkpoint,
)
from arc3_agi_agent.p10_instruction_compiler import (
    active_p10_manifest_digest,
)
from arc3_agi_agent.p10_runtime import P10InstructionVariant
from p10_main import (
    _resolve_p10_batch_game_ids,
    run_p10_offline_samples,
)
from sample_main import _default_environments_dir


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def run_p10_checkpoint_worker(
    *,
    environments_dir: Path,
    checkpoint_dir: Path,
    game_id: str,
    max_actions: int = 450,
    instruction_variant: P10InstructionVariant = "hybrid",
    resume: bool = False,
) -> dict[str, object]:
    """Execute or reuse one worker bound to the full sample inventory."""

    environments_dir = environments_dir.resolve()
    checkpoint_dir = checkpoint_dir.resolve()
    game_ids = _resolve_p10_batch_game_ids(
        environments_dir=environments_dir,
        requested_games=None,
        all_samples=True,
        recordings_dir=None,
    )
    if game_id not in game_ids:
        raise ValueError(f"P10_WORKER_GAME_NOT_IN_SAMPLE_SET:{game_id}")
    bundle_dir = Path(__file__).resolve().parent / "arc3_agi_agent" / "bundles"
    conditions = build_batch_conditions(
        environments_dir=environments_dir,
        game_ids=game_ids,
        max_actions=max_actions,
        instruction_variant=instruction_variant,
        instruction_lifecycle="active",
        active_manifest_digest=active_p10_manifest_digest(bundle_dir),
    )
    existing = load_game_checkpoint(
        checkpoint_dir=checkpoint_dir,
        conditions=conditions,
        game_id=game_id,
    )
    status = "REUSED"
    if existing is None:
        result = run_p10_offline_samples(
            environments_dir=environments_dir,
            requested_games=[game_id],
            max_actions=max_actions,
            instruction_variant=instruction_variant,
            instruction_lifecycle="active",
        )
        path = write_game_checkpoint(
            checkpoint_dir=checkpoint_dir,
            conditions=conditions,
            game_id=game_id,
            result=result,
        )
        status = "EXECUTED"
    else:
        if not resume:
            raise FileExistsError(
                "P10_CHECKPOINT_EXISTS_USE_RESUME:"
                + str(checkpoint_path(checkpoint_dir, game_id))
            )
        raw_result = existing.get("single_game_report")
        if not isinstance(raw_result, Mapping):
            raise TypeError("P10_WORKER_CHECKPOINT_REPORT_MISSING")
        result = dict(raw_result)
        path = checkpoint_path(checkpoint_dir, game_id)

    reports = result.get("reports")
    if not isinstance(reports, list):
        raise TypeError("P10_WORKER_REPORTS_INVALID")
    report: Mapping[str, Any] = {}
    if reports:
        first = reports[0]
        if not isinstance(first, Mapping):
            raise TypeError("P10_WORKER_GAME_REPORT_INVALID")
        report = first
    return {
        "status": status,
        "game_id": game_id,
        "checkpoint": str(path),
        "conditions_digest": str(conditions["conditions_digest"]),
        "runtime_source_inventory_digest": str(
            conditions["runtime_source_inventory_digest"]
        ),
        "completed_count": _integer(
            result.get("completed_count"),
            "completed_count",
        ),
        "error_count": _integer(
            result.get("error_count"),
            "error_count",
        ),
        "actions": _integer(report.get("actions", 0), "actions"),
        "levels_completed": _integer(
            report.get("levels_completed", 0),
            "levels_completed",
        ),
        "win_levels": _integer(
            report.get("win_levels", 0),
            "win_levels",
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one OFFLINE P10 game under the complete-sample condition "
            "digest and write its atomic checkpoint."
        )
    )
    parser.add_argument("--game", required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--max-actions", type=int, default=450)
    parser.add_argument(
        "--instruction-variant",
        choices=("P-A", "P-B", "hybrid"),
        default="hybrid",
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_p10_checkpoint_worker(
        environments_dir=args.environments_dir,
        checkpoint_dir=args.checkpoint_dir,
        game_id=args.game,
        max_actions=args.max_actions,
        instruction_variant=cast(
            P10InstructionVariant,
            args.instruction_variant,
        ),
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
