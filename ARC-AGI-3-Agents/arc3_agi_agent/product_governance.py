"""Fail-closed product endpoint contract for ARC3CompletionAgent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ARC3_PRODUCT_ID: Final = "ARC3CompletionAgent"
ARC3_PRODUCT_ACTIVE_MILESTONE: Final = "M3_INTEGRATED_AGI_CAPABILITY"
ARC3_OFFICIAL_SAMPLE_GAME_TARGET: Final = 25
ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET: Final = 183
ARC3_KNOWN_SUCCESS_ACTION_CEILING: Final = 1519
ARC3_DEVELOPMENT_ACTION_BUDGET: Final = 4096
ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING: Final = 644
ARC3_PRODUCT_NO_PROGRESS_LIMIT: Final = 650
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
    known_success_no_progress_ceiling: int = ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING
    no_progress_limit: int = ARC3_PRODUCT_NO_PROGRESS_LIMIT

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
        if self.no_progress_limit < self.known_success_no_progress_ceiling:
            failures.append("PRODUCT_NO_PROGRESS_LIMIT_IMPOSSIBLE")
        if self.no_progress_limit > self.action_budget:
            failures.append("PRODUCT_NO_PROGRESS_LIMIT_UNBOUNDED")
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
        bounded_rows = [
            row
            for row in valid_rows
            if (actions := _integer(row.get("actions_executed"))) is not None
            and actions >= 0
            and (progress := _integer(row.get("progress_count"))) is not None
            and progress >= 0
            and isinstance(row.get("final_state"), str)
            and bool(row.get("final_state"))
            and isinstance(row.get("stop_reason"), str)
            and bool(row.get("stop_reason"))
        ]
        progress_values = [
            value
            for row in valid_rows
            if (value := _integer(row.get("progress_count"))) is not None and value >= 0
        ]
        game_win_count = sum(1 for row in valid_rows if row.get("final_state") == "WIN")
        level_completion_count = sum(progress_values)
        advertised = _integer(report.get("advertised_game_count"))
        started = _integer(report.get("started_game_count"))
        completed = _integer(report.get("completed_game_count"))
        failed = _integer(report.get("failed_game_count"))
        lifecycle_failed = _integer(report.get("lifecycle_failure_count"))
        scorecard_open_count = _integer(report.get("scorecard_open_count"))
        scorecard_close_count = _integer(report.get("scorecard_close_count"))
        active_agent_peak = _integer(report.get("active_agent_peak"))
        actual_action_budget = _integer(
            report.get("resource_action_budget_per_episode")
        )
        actual_no_progress_limit = _integer(report.get("hds_stop_after_no_progress"))
        shared_session_count = _integer(report.get("shared_session_count"))
        state_owner_violation_count = _integer(
            report.get("state_owner_violation_count")
        )
        expected_indexes = list(range(self.game_target))
        raw_orchestration_index = report.get("orchestration_game_index")
        orchestration_index = (
            raw_orchestration_index if isinstance(raw_orchestration_index, list) else []
        )
        orchestration_indexes = [
            index
            for row in orchestration_index
            if isinstance(row, dict)
            and (index := _integer(row.get("game_index"))) is not None
            and isinstance(row.get("game_id"), str)
            and bool(row.get("game_id"))
        ]
        orchestration_game_ids = [
            str(row["game_id"])
            for row in orchestration_index
            if isinstance(row, dict)
            and isinstance(row.get("game_id"), str)
            and bool(row.get("game_id"))
        ]
        baseline_failures = list(self.validate())
        if advertised != self.game_target:
            baseline_failures.append("PRODUCT_ADVERTISED_GAME_COUNT_MISMATCH")
        if started != self.game_target:
            baseline_failures.append("PRODUCT_STARTED_GAME_COUNT_MISMATCH")
        if completed != self.game_target:
            baseline_failures.append("PRODUCT_COMPLETED_GAME_COUNT_MISMATCH")
        if len(valid_rows) != self.game_target:
            baseline_failures.append("PRODUCT_RESULT_COUNT_MISMATCH")
        if len(bounded_rows) != self.game_target:
            baseline_failures.append("PRODUCT_BOUNDED_REPORT_COUNT_MISMATCH")
        if sorted(game_indexes) != expected_indexes:
            baseline_failures.append("PRODUCT_GAME_INDEX_COVERAGE_MISMATCH")
        if len(progress_values) != self.game_target:
            baseline_failures.append("PRODUCT_PROGRESS_COVERAGE_MISMATCH")
        if (
            sorted(orchestration_indexes) != expected_indexes
            or len(orchestration_game_ids) != self.game_target
            or len(set(orchestration_game_ids)) != self.game_target
        ):
            baseline_failures.append("PRODUCT_ORCHESTRATION_GAME_COVERAGE_MISMATCH")
        if failed != 0:
            baseline_failures.append("PRODUCT_GAME_FAILURE_PRESENT")
        if lifecycle_failed != 0:
            baseline_failures.append("PRODUCT_LIFECYCLE_FAILURE_PRESENT")
        if report.get("scorecard_closed") is not True:
            baseline_failures.append("PRODUCT_SCORECARD_NOT_CLOSED")
        if scorecard_open_count != 1 or scorecard_close_count != 1:
            baseline_failures.append("PRODUCT_SCORECARD_LIFECYCLE_MISMATCH")
        if active_agent_peak != 1:
            baseline_failures.append("PRODUCT_ACTIVE_AGENT_PEAK_MISMATCH")
        if shared_session_count != 1:
            baseline_failures.append("PRODUCT_SHARED_SESSION_COUNT_MISMATCH")
        if state_owner_violation_count != 0:
            baseline_failures.append("PRODUCT_STATE_OWNER_VIOLATION")
        if report.get("identity_boundary") != "PASS":
            baseline_failures.append("PRODUCT_IDENTITY_BOUNDARY_FAILURE")
        if report.get("runtime_policy_changed") is not False:
            baseline_failures.append("PRODUCT_RUNTIME_POLICY_CHANGED")
        if (
            actual_action_budget is None
            or actual_action_budget < self.known_success_action_ceiling
        ):
            baseline_failures.append("PRODUCT_OBSERVED_ACTION_BUDGET_IMPOSSIBLE")
        if actual_action_budget != self.action_budget:
            baseline_failures.append("PRODUCT_OBSERVED_ACTION_BUDGET_MISMATCH")
        if (
            actual_no_progress_limit is None
            or actual_no_progress_limit < self.known_success_no_progress_ceiling
        ):
            baseline_failures.append("PRODUCT_OBSERVED_NO_PROGRESS_LIMIT_IMPOSSIBLE")
        if actual_no_progress_limit != self.no_progress_limit:
            baseline_failures.append("PRODUCT_OBSERVED_NO_PROGRESS_LIMIT_MISMATCH")
        normalized_baseline_failures = tuple(sorted(set(baseline_failures)))
        baseline_executable = not normalized_baseline_failures
        endpoint_failures = list(normalized_baseline_failures)
        if game_win_count != self.game_target:
            endpoint_failures.append("PRODUCT_GAME_WIN_COUNT_MISMATCH")
        if level_completion_count != self.level_target:
            endpoint_failures.append("PRODUCT_LEVEL_COMPLETION_COUNT_MISMATCH")
        normalized_endpoint_failures = tuple(sorted(set(endpoint_failures)))
        complete = not normalized_endpoint_failures
        observed_budget_impossible = (
            actual_action_budget is None
            or actual_action_budget < self.known_success_action_ceiling
        )
        return {
            "product_id": ARC3_PRODUCT_ID,
            "product_active_milestone": ARC3_PRODUCT_ACTIVE_MILESTONE,
            "product_action_budget_per_game": actual_action_budget or 0,
            "required_product_action_budget_per_game": self.action_budget,
            "known_success_action_ceiling": self.known_success_action_ceiling,
            "known_success_no_progress_ceiling": (
                self.known_success_no_progress_ceiling
            ),
            "product_no_progress_limit": actual_no_progress_limit or 0,
            "required_product_no_progress_limit": self.no_progress_limit,
            "known_budget_impossibility": observed_budget_impossible,
            "budget_impossible_game_count": (
                self.game_target if observed_budget_impossible else 0
            ),
            "official_sample_game_target": self.game_target,
            "official_sample_level_target": self.level_target,
            "product_advertised_game_count": advertised or 0,
            "product_game_started_count": started or 0,
            "product_result_count": len(valid_rows),
            "product_bounded_report_count": len(bounded_rows),
            "product_game_win_count": game_win_count,
            "product_level_completion_count": level_completion_count,
            "adapter_crash_count": failed if failed is not None else self.game_target,
            "scorecard_lifecycle_leak_count": (
                0
                if report.get("scorecard_closed") is True
                and scorecard_open_count == 1
                and scorecard_close_count == 1
                else 1
            ),
            "active_product_path_count": shared_session_count or 0,
            "product_baseline_failure_count": len(normalized_baseline_failures),
            "product_baseline_failures": normalized_baseline_failures,
            "baseline_report_complete": baseline_executable,
            "product_baseline_executable": baseline_executable,
            "product_baseline_status": (
                "PRODUCT_BASELINE_EXECUTABLE" if baseline_executable else "INCOMPLETE"
            ),
            "product_endpoint_failure_count": len(normalized_endpoint_failures),
            "product_endpoint_failures": normalized_endpoint_failures,
            "product_completion_established": complete,
            "product_status": "COMPLETE" if complete else "INCOMPLETE",
        }


ARC3_PRODUCT_ENDPOINT: Final = ProductEndpointContract()


__all__ = [
    "ARC3_CURRENT_SELECTOR_PATH",
    "ARC3_DEVELOPMENT_ACTION_BUDGET",
    "ARC3_KNOWN_SUCCESS_ACTION_CEILING",
    "ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING",
    "ARC3_LEGACY_REV3_IS_CURRENT",
    "ARC3_OFFICIAL_SAMPLE_GAME_TARGET",
    "ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET",
    "ARC3_PRODUCT_ACTIVE_MILESTONE",
    "ARC3_PRODUCT_ENDPOINT",
    "ARC3_PRODUCT_ID",
    "ARC3_PRODUCT_NO_PROGRESS_LIMIT",
    "ProductEndpointContract",
]
