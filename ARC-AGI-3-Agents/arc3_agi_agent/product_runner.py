"""Blocking product runner for ARC3CompletionAgent acceptance."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from .generic_competition_runner import run_sequential_competition
from .generic_compute import HybridRelationalInstructionBody
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)

ARC3_PRODUCT_RUNNER_VERSION = "arc3-completion-product-runner-v0.1"
ARC3_PRODUCT_ID = "ARC3CompletionAgent"
ARC3_OFFICIAL_SAMPLE_GAME_TARGET = 25
ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET = 183
ARC3_KNOWN_SUCCESS_ACTION_CEILING = 1519
ARC3_DEVELOPMENT_ACTION_BUDGET = 4096

logger = logging.getLogger(__name__)


def create_product_session() -> CognitiveSession:
    """Create the current product session with a non-blocking action budget.

    The active P remains the current runtime baseline until M2 compiles and
    installs the ARC3 product capability bundle. M0 exists to measure this
    product path honestly, not to claim capability completion.
    """

    return create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        mode="COMPETITION",
        resource_contract=ResourceContract(
            action_budget_per_episode=ARC3_DEVELOPMENT_ACTION_BUDGET,
        ),
    )


def _product_metrics(report: dict[str, object]) -> dict[str, object]:
    raw_results = report.get("results", ())
    results = raw_results if isinstance(raw_results, list) else []
    game_win_count = sum(
        1
        for row in results
        if isinstance(row, dict) and row.get("final_state") == "WIN"
    )
    level_completion_count = sum(
        int(row.get("progress_count", 0))
        for row in results
        if isinstance(row, dict)
        and isinstance(row.get("progress_count", 0), int)
        and not isinstance(row.get("progress_count", 0), bool)
    )
    advertised = report.get("advertised_game_count", 0)
    game_count = advertised if isinstance(advertised, int) else 0
    product_complete = (
        game_count == ARC3_OFFICIAL_SAMPLE_GAME_TARGET
        and game_win_count == ARC3_OFFICIAL_SAMPLE_GAME_TARGET
        and level_completion_count == ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET
        and report.get("failed_game_count") == 0
        and report.get("lifecycle_failure_count") == 0
    )
    return {
        "product_id": ARC3_PRODUCT_ID,
        "product_runner_version": ARC3_PRODUCT_RUNNER_VERSION,
        "product_action_budget_per_game": ARC3_DEVELOPMENT_ACTION_BUDGET,
        "known_success_action_ceiling": ARC3_KNOWN_SUCCESS_ACTION_CEILING,
        "known_budget_impossibility": (
            ARC3_DEVELOPMENT_ACTION_BUDGET
            < ARC3_KNOWN_SUCCESS_ACTION_CEILING
        ),
        "official_sample_game_target": ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
        "official_sample_level_target": ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
        "product_game_win_count": game_win_count,
        "product_level_completion_count": level_completion_count,
        "product_completion_established": product_complete,
        "product_status": "COMPLETE" if product_complete else "INCOMPLETE",
    }


def run_arc3_completion_product(
    *,
    arcade: Any | None = None,
    agent_factory: Callable[..., Any] | None = None,
    session_factory: Callable[[], CognitiveSession] | None = None,
) -> dict[str, object]:
    """Run the one product path and evaluate the actual product endpoint."""

    if agent_factory is None:
        from agents.templates.arc3_completion_agent import ARC3CompletionAgent

        agent_factory = ARC3CompletionAgent
    report = run_sequential_competition(
        arcade=arcade,
        agent_factory=agent_factory,
        session_factory=session_factory or create_product_session,
    )
    report.update(_product_metrics(report))
    return report


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    report = run_arc3_completion_product()
    print(json.dumps(report, sort_keys=True))
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
    "run_arc3_completion_product",
]
