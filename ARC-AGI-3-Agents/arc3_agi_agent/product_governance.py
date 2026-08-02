"""Fail-closed product endpoint contract for ARC3CompletionAgent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ARC3_PRODUCT_ID: Final = "ARC3CompletionAgent"
ARC3_PRODUCT_ACTIVE_MILESTONE: Final = "M0_PRODUCT_BASELINE_AND_BLOCKER_CLOSURE"
ARC3_OFFICIAL_SAMPLE_GAME_TARGET: Final = 25
ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET: Final = 183
ARC3_KNOWN_SUCCESS_ACTION_CEILING: Final = 1519
ARC3_DEVELOPMENT_ACTION_BUDGET: Final = 4096
ARC3_CURRENT_SELECTOR_PATH: Final = "control/rev4/CURRENT_TASK.json"
ARC3_LEGACY_REV3_IS_CURRENT: Final = False


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


@dataclass(frozen=True, slots=True)
class ProductEndpointContract:
    """Measured endpoint that must hold before product completion is claimed."""

    game_target: int = ARC3_OFFICIAL_SAMPLE_GAME_TARGET
    level_target: int = ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET
    known_success_action_ceiling: int = ARC3_KNOWN_SUCCESS_ACTION_CEILING

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.game_target != 25:
            failures.append("PRODUCT_GAME_TARGET_INVALID")
        if self.level_target != 183:
            failures.append("PRODUCT_LEVEL_TARGET_INVALID")
        if self.action_budget < self.known_success_action_ceiling:
            failures.append("PRODUCT_ACTION_BUDGET_IMPOSSIBLE")
        if self.action_budget > 100_000:
            failures.append("PRODUCT_ACTION_BUDGET_UNBOUNDED")
        return tuple(failures)

    def metrics(self, report: dict[str, object]) -> dict[str, object]:
        """Evaluate one runner report without accepting missing or coerced fields."""

        raw_results = report.get("results")
        results = raw_results if isinstance(raw_results, list) else []
        valid_rows = [row for row in results if isinstance(row, dict)]
        game_indexes = [
            value
            for row in valid_rows
            if (value := _integer(row.get("game_index"))) is not None
        ]
        progress_values = [
            value
            for row in valid_rows
            if (value := _integer(row.get("progress_count"))) is not None and value >= 0
        ]
        game_win_count = sum(1 for row in valid_rows if row.get("final_state") == "WIN")
        level_completion_count = sum(progress_values)
        advertised = _integer(report.get("advertised_game_count"))
        completed = _integer(report.get("completed_game_count"))
        failed = _integer(report.get("failed_game_count"))
        lifecycle_failed = _integer(report.get("lifecycle_failure_count"))
        scorecard_open_count = _integer(report.get("scorecard_open_count"))
        scorecard_close_count = _integer(report.get("scorecard_close_count"))
        active_agent_peak = _integer(report.get("active_agent_peak"))
        expected_indexes = list(range(self.game_target))
        endpoint_failures = list(self.validate())
        if advertised != self.game_target:
            endpoint_failures.append("PRODUCT_ADVERTISED_GAME_COUNT_MISMATCH")
        if completed != self.game_target:
            endpoint_failures.append("PRODUCT_COMPLETED_GAME_COUNT_MISMATCH")
        if len(valid_rows) != self.game_target:
            endpoint_failures.append("PRODUCT_RESULT_COUNT_MISMATCH")
        if sorted(game_indexes) != expected_indexes:
            endpoint_failures.append("PRODUCT_GAME_INDEX_COVERAGE_MISMATCH")
        if game_win_count != self.game_target:
            endpoint_failures.append("PRODUCT_GAME_WIN_COUNT_MISMATCH")
        if level_completion_count != self.level_target:
            endpoint_failures.append("PRODUCT_LEVEL_COMPLETION_COUNT_MISMATCH")
        if failed != 0:
            endpoint_failures.append("PRODUCT_GAME_FAILURE_PRESENT")
        if lifecycle_failed != 0:
            endpoint_failures.append("PRODUCT_LIFECYCLE_FAILURE_PRESENT")
        if report.get("scorecard_closed") is not True:
            endpoint_failures.append("PRODUCT_SCORECARD_NOT_CLOSED")
        if scorecard_open_count != 1 or scorecard_close_count != 1:
            endpoint_failures.append("PRODUCT_SCORECARD_LIFECYCLE_MISMATCH")
        if active_agent_peak != 1:
            endpoint_failures.append("PRODUCT_ACTIVE_AGENT_PEAK_MISMATCH")
        failures = tuple(sorted(set(endpoint_failures)))
        complete = not failures
        return {
            "product_id": ARC3_PRODUCT_ID,
            "product_active_milestone": ARC3_PRODUCT_ACTIVE_MILESTONE,
            "product_action_budget_per_game": self.action_budget,
            "known_success_action_ceiling": self.known_success_action_ceiling,
            "known_budget_impossibility": (
                self.action_budget < self.known_success_action_ceiling
            ),
            "official_sample_game_target": self.game_target,
            "official_sample_level_target": self.level_target,
            "product_game_started_count": advertised or 0,
            "product_result_count": len(valid_rows),
            "product_game_win_count": game_win_count,
            "product_level_completion_count": level_completion_count,
            "product_endpoint_failure_count": len(failures),
            "product_endpoint_failures": failures,
            "product_completion_established": complete,
            "product_status": "COMPLETE" if complete else "INCOMPLETE",
        }


ARC3_PRODUCT_ENDPOINT: Final = ProductEndpointContract()


__all__ = [
    "ARC3_CURRENT_SELECTOR_PATH",
    "ARC3_DEVELOPMENT_ACTION_BUDGET",
    "ARC3_KNOWN_SUCCESS_ACTION_CEILING",
    "ARC3_LEGACY_REV3_IS_CURRENT",
    "ARC3_OFFICIAL_SAMPLE_GAME_TARGET",
    "ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET",
    "ARC3_PRODUCT_ACTIVE_MILESTONE",
    "ARC3_PRODUCT_ENDPOINT",
    "ARC3_PRODUCT_ID",
    "ProductEndpointContract",
]
