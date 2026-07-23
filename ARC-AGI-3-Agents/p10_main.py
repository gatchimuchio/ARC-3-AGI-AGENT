"""Deterministic P10 runner for retained ARC-AGI-3 OFFLINE samples."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from agents.templates.p10_sample_agent import P10SampleAgent
from arc3_agi_agent.p10_runtime import P10InstructionVariant
from arc3_agi_agent.protocol import AuthorityViolation
from sample_main import _default_environments_dir, _resolve_game_ids


def run_p10_offline_samples(
    *,
    environments_dir: Path,
    requested_games: list[str] | None = None,
    all_samples: bool = False,
    max_actions: int = 4096,
    instruction_variant: P10InstructionVariant = "hybrid",
    record: bool = False,
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Run P10 without constructing any online or competition boundary."""

    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_ENV_FORBIDDEN_DURING_P10")

    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else environments_dir.parent / "recordings"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")

    game_ids = _resolve_game_ids(
        arcade,
        requested_games,
        all_samples=all_samples,
    )
    if not game_ids:
        raise ValueError("select --all-samples or at least one --game")

    card_id = arcade.open_scorecard(tags=["p10", "offline-sample"])
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    scorecard: dict[str, Any] | None = None
    try:
        for game_id in game_ids:
            try:
                environment = arcade.make(
                    game_id,
                    scorecard_id=card_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("OFFLINE_SAMPLE_ENVIRONMENT_LOAD_FAILED")
                previous_recordings_dir = os.environ.get("RECORDINGS_DIR")
                try:
                    if record:
                        os.environ["RECORDINGS_DIR"] = str(output_dir)
                    agent = P10SampleAgent(
                        card_id=card_id,
                        game_id=game_id,
                        agent_name="p10sample",
                        ROOT_URL="",
                        record=record,
                        arc_env=environment,
                        tags=["p10", "offline-sample"],
                        operation_mode=arcade.operation_mode,
                        max_actions=max_actions,
                        instruction_variant=instruction_variant,
                    )
                    agent.main()
                    reports.append(dataclasses.asdict(agent.report()))
                finally:
                    if record:
                        if previous_recordings_dir is None:
                            os.environ.pop("RECORDINGS_DIR", None)
                        else:
                            os.environ["RECORDINGS_DIR"] = (
                                previous_recordings_dir
                            )
            except Exception as error:
                errors.append(
                    {
                        "game_id": game_id,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
    finally:
        closed = arcade.close_scorecard(card_id)
        if closed is not None:
            scorecard = closed.model_dump(mode="json")

    completed_levels = sum(
        int(report["levels_completed"]) for report in reports
    )
    total_levels = sum(int(report["win_levels"]) for report in reports)
    complete_games = sum(bool(report["complete"]) for report in reports)
    return {
        "phase": "P10",
        "operation_mode": arcade.operation_mode.value,
        "environment_count": len(game_ids),
        "completed_count": len(reports),
        "complete_game_count": complete_games,
        "completed_levels": completed_levels,
        "total_levels": total_levels,
        "all_complete": (
            not errors
            and len(reports) == len(game_ids)
            and complete_games == len(game_ids)
        ),
        "error_count": len(errors),
        "max_actions": max_actions,
        "instruction_variant": instruction_variant,
        "reports": reports,
        "errors": errors,
        "local_scorecard": scorecard,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the P10 Trinity agent against retained samples using only "
            "OperationMode.OFFLINE."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all-samples", action="store_true")
    selection.add_argument("--game", action="append", dest="games")
    parser.add_argument("--max-actions", type=int, default=4096)
    parser.add_argument(
        "--instruction-variant",
        choices=("P-A", "P-B", "hybrid"),
        default="hybrid",
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_p10_offline_samples(
        environments_dir=args.environments_dir,
        requested_games=args.games,
        all_samples=args.all_samples,
        max_actions=args.max_actions,
        instruction_variant=args.instruction_variant,
        record=args.record,
        recordings_dir=args.recordings_dir,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    return 0 if result["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
