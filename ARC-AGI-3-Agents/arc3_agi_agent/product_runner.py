"""Blocking product runner for ARC3CompletionAgent acceptance."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from .generic_competition_runner import run_sequential_competition
from .generic_compute import HybridRelationalInstructionBody
from .generic_hds import HDSConfiguration
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from .product_governance import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
    ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
    ARC3_PRODUCT_ENDPOINT,
    ARC3_PRODUCT_ID,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)

ARC3_PRODUCT_RUNNER_VERSION = "arc3-completion-product-runner-v0.2"

logger = logging.getLogger(__name__)


def create_product_session(
    *,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
    mode: str = "COMPETITION",
) -> CognitiveSession:
    """Create the current product session with a non-blocking action budget.

    The active P remains the current runtime baseline until M2 compiles and
    installs the ARC3 product capability bundle. M0 exists to measure this
    product path honestly, not to claim capability completion.
    """

    return create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        mode=mode,
        hds_configuration=HDSConfiguration(
            resource_budget=action_budget,
            stop_after_no_progress=min(
                action_budget,
                ARC3_PRODUCT_NO_PROGRESS_LIMIT,
            ),
        ),
        resource_contract=ResourceContract(
            action_budget_per_episode=action_budget,
        ),
    )


def run_arc3_completion_product(
    *,
    arcade: Any | None = None,
    agent_factory: Callable[..., Any] | None = None,
    session_factory: Callable[[], CognitiveSession] | None = None,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
    session_mode: str = "COMPETITION",
) -> dict[str, object]:
    """Run the one product path and evaluate the actual product endpoint."""

    if agent_factory is None:
        from agents.templates.arc3_completion_agent import ARC3CompletionAgent

        agent_factory = ARC3CompletionAgent
    selected_session_factory = session_factory
    if selected_session_factory is None:

        def selected_session_factory() -> CognitiveSession:
            return create_product_session(
                action_budget=action_budget,
                mode=session_mode,
            )

    report = run_sequential_competition(
        arcade=arcade,
        agent_factory=agent_factory,
        session_factory=selected_session_factory,
    )
    report.update(ARC3_PRODUCT_ENDPOINT.metrics(report))
    report["product_runner_version"] = ARC3_PRODUCT_RUNNER_VERSION
    return report


def _default_environments_dir() -> Path:
    candidates = (
        Path(__file__).resolve().parents[2] / "environment_files",
        Path.cwd() / "environment_files",
        Path.cwd().parent / "environment_files",
    )
    return next(
        (candidate for candidate in candidates if candidate.is_dir()),
        candidates[0],
    )


def _selected_offline_environments(
    arcade: Arcade,
    requested_games: tuple[str, ...],
) -> tuple[Any, ...]:
    environments = tuple(
        sorted(arcade.get_environments(), key=lambda item: item.game_id)
    )
    if not requested_games:
        return environments
    by_id = {item.game_id.casefold(): item for item in environments}
    by_title = {item.title.casefold(): item for item in environments}
    selected: list[Any] = []
    selected_ids: set[str] = set()
    for requested in requested_games:
        key = requested.casefold()
        environment = by_id.get(key) or by_title.get(key)
        if environment is None:
            raise ValueError(f"ARC3_PRODUCT_UNKNOWN_OFFLINE_GAME:{requested}")
        if environment.game_id not in selected_ids:
            selected.append(environment)
            selected_ids.add(environment.game_id)
    return tuple(selected)


class _SelectedOfflineArcade:
    """Orchestration-only diagnostic selection over one official Arcade."""

    def __init__(self, arcade: Arcade, environments: tuple[Any, ...]) -> None:
        self._arcade = arcade
        self._environments = environments

    def get_environments(self) -> list[Any]:
        return list(self._environments)

    def open_scorecard(self, *, tags: list[str]) -> str:
        return cast(str, self._arcade.open_scorecard(tags=tags))

    def make(
        self,
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> object | None:
        return cast(
            object | None,
            self._arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=save_recording,
                include_frame_data=include_frame_data,
            ),
        )

    def close_scorecard(self, card_id: str) -> object | None:
        return cast(object | None, self._arcade.close_scorecard(card_id))


def run_arc3_completion_offline(
    *,
    environments_dir: Path,
    requested_games: tuple[str, ...] = (),
    recordings_dir: Path | None = None,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
) -> dict[str, object]:
    """Run the product C/J/M/P path against official bundled environments."""

    resolved_environments_dir = environments_dir.resolve()
    if not resolved_environments_dir.is_dir():
        raise FileNotFoundError(
            "ARC3_PRODUCT_ENVIRONMENT_DIRECTORY_MISSING:"
            + str(resolved_environments_dir)
        )
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise PermissionError("ARC3_PRODUCT_OFFLINE_COMPETITION_ENV_FORBIDDEN")
    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else resolved_environments_dir.parent / "recordings" / "product-rev4"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(resolved_environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise RuntimeError("ARC3_PRODUCT_OFFLINE_MODE_NOT_EFFECTIVE")
    available_count = len(arcade.get_environments())
    selected = _selected_offline_environments(arcade, requested_games)
    report = run_arc3_completion_product(
        arcade=_SelectedOfflineArcade(arcade, selected),
        action_budget=action_budget,
        session_mode="VALIDATION",
    )
    report.update(
        {
            "operation_mode": arcade.operation_mode.value,
            "offline_environment_available_count": available_count,
            "offline_environment_selected_count": len(selected),
            "offline_environment_source": "BUNDLED_OFFICIAL_SAMPLES",
        }
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the endpoint-driven ARC3CompletionAgent product."
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "competition"),
        default="offline",
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument(
        "--action-budget",
        type=int,
        default=ARC3_DEVELOPMENT_ACTION_BUDGET,
    )
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    arguments = _parser().parse_args()
    if arguments.mode == "offline":
        report = run_arc3_completion_offline(
            environments_dir=arguments.environments_dir,
            requested_games=tuple(arguments.game),
            recordings_dir=arguments.recordings_dir,
            action_budget=arguments.action_budget,
        )
    else:
        if arguments.game:
            raise ValueError("ARC3_PRODUCT_COMPETITION_GAME_FILTER_FORBIDDEN")
        report = run_arc3_completion_product(
            action_budget=arguments.action_budget,
        )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(encoded + "\n", encoding="utf-8")
    return 0 if report["product_completion_established"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARC3_DEVELOPMENT_ACTION_BUDGET",
    "ARC3_KNOWN_SUCCESS_ACTION_CEILING",
    "ARC3_OFFICIAL_SAMPLE_GAME_TARGET",
    "ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET",
    "ARC3_PRODUCT_ID",
    "ARC3_PRODUCT_RUNNER_VERSION",
    "create_product_session",
    "run_arc3_completion_offline",
    "run_arc3_completion_product",
]
