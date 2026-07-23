"""Deterministic P1 runner for bundled ARC-AGI-3 samples in OFFLINE mode."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from agents.templates.layer0_sample_agent import Layer0SampleAgent
from arc3_agi_agent.protocol import AuthorityViolation


def _default_environments_dir() -> Path:
    candidates = (
        Path(__file__).resolve().parents[1] / "environment_files",
        Path.cwd() / "environment_files",
        Path.cwd().parent / "environment_files",
    )
    return next(
        (candidate for candidate in candidates if candidate.is_dir()),
        candidates[0],
    )


def _resolve_game_ids(
    arcade: Arcade,
    requested: list[str] | None,
    *,
    all_samples: bool,
) -> list[str]:
    environments = sorted(
        arcade.get_environments(),
        key=lambda item: item.game_id,
    )
    if all_samples:
        return [item.game_id for item in environments]

    by_id = {item.game_id.casefold(): item.game_id for item in environments}
    by_title = {item.title.casefold(): item.game_id for item in environments}
    resolved: list[str] = []
    for value in requested or []:
        key = value.casefold()
        game_id = by_id.get(key) or by_title.get(key)
        if game_id is None:
            raise ValueError(f"unknown local sample: {value}")
        if game_id not in resolved:
            resolved.append(game_id)
    return resolved


def run_offline_samples(
    *,
    environments_dir: Path,
    requested_games: list[str] | None = None,
    all_samples: bool = False,
    max_actions: int = 1,
    record: bool = False,
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Run selected bundled samples; never construct a non-OFFLINE Arcade."""

    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_ENV_FORBIDDEN_DURING_P1")

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

    card_id = arcade.open_scorecard(tags=["p1", "offline-sample"])
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
                    agent = Layer0SampleAgent(
                        card_id=card_id,
                        game_id=game_id,
                        agent_name="layer0sample",
                        ROOT_URL="",
                        record=record,
                        arc_env=environment,
                        tags=["p1", "offline-sample"],
                        operation_mode=arcade.operation_mode,
                        max_actions=max_actions,
                    )
                    agent.main()
                    reports.append(dataclasses.asdict(agent.report()))
                finally:
                    if record:
                        if previous_recordings_dir is None:
                            os.environ.pop("RECORDINGS_DIR", None)
                        else:
                            os.environ["RECORDINGS_DIR"] = previous_recordings_dir
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

    return {
        "phase": "P1",
        "operation_mode": arcade.operation_mode.value,
        "environment_count": len(game_ids),
        "completed_count": len(reports),
        "error_count": len(errors),
        "max_actions": max_actions,
        "reports": reports,
        "errors": errors,
        "local_scorecard": scorecard,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the HDS-controlled Layer-0 kernel against bundled samples "
            "using only OperationMode.OFFLINE."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--all-samples",
        action="store_true",
        help="run every bundled sample environment",
    )
    selection.add_argument(
        "--game",
        action="append",
        dest="games",
        help="local game ID or title; repeat for multiple samples",
    )
    parser.add_argument("--max-actions", type=int, default=1)
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
    result = run_offline_samples(
        environments_dir=args.environments_dir,
        requested_games=args.games,
        all_samples=args.all_samples,
        max_actions=args.max_actions,
        record=args.record,
        recordings_dir=args.recordings_dir,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    return 1 if result["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
