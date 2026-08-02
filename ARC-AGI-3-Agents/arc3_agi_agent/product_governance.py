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
    """Measured known-sample endpoint; never sufficient for AGI completion."""

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
        action_values = [
            value
            for row in valid_rows
            if (value := _integer(row.get("actions_executed"))) is not None
            and value >= 0
        ]
        plan_metric_names = (
            "executed_plan_count",
            "hds_plan_commit_count",
            "initial_plan_count",
            "revised_plan_count",
            "rollback_plan_count",
            "failed_hypothesis_invalidation_count",
            "post_rollback_replan_count",
            "memory_bound_plan_count",
            "competing_hypothesis_plan_count",
            "multi_representation_plan_count",
            "subgoal_plan_count",
            "max_plan_step_count",
            "failure_attribution_count",
        )
        plan_metric_values = {
            name: tuple(
                value
                for row in valid_rows
                if (value := _integer(row.get(name))) is not None
                and value >= 0
            )
            for name in plan_metric_names
        }
        plan_metric_totals = {
            name: (
                max(values, default=0)
                if name == "max_plan_step_count"
                else sum(values)
            )
            for name, values in plan_metric_values.items()
        }
        plan_integrity_rows: list[dict[str, object]] = []
        runtime_failure_signature_row_count = 0
        for row in valid_rows:
            raw_failure_signatures = row.get("failure_signatures")
            if not isinstance(raw_failure_signatures, (list, tuple)) or any(
                not isinstance(item, str) or not item
                for item in raw_failure_signatures
            ):
                runtime_failure_signature_row_count += 1
            elif raw_failure_signatures:
                runtime_failure_signature_row_count += 1
            actions = _integer(row.get("actions_executed"))
            metrics: dict[str, int] = {}
            for name in plan_metric_names:
                value = _integer(row.get(name))
                metrics[name] = -1 if value is None else value
            if (
                actions is not None
                and actions > 0
                and all(value >= 0 for value in metrics.values())
                and metrics["executed_plan_count"] == actions
                and metrics["hds_plan_commit_count"] == actions
                and metrics["initial_plan_count"] == 1
                and metrics["revised_plan_count"] >= actions - 1
                and metrics["memory_bound_plan_count"] >= actions - 1
                and metrics["competing_hypothesis_plan_count"] == actions
                and metrics["multi_representation_plan_count"] == actions
                and metrics["subgoal_plan_count"] == actions
                and metrics["max_plan_step_count"] == 4
            ):
                plan_integrity_rows.append(row)
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
        if runtime_failure_signature_row_count:
            endpoint_failures.append("PRODUCT_RUNTIME_FAILURE_SIGNATURE_PRESENT")
        if len(plan_integrity_rows) != self.game_target:
            endpoint_failures.append("PRODUCT_PLAN_EVIDENCE_COVERAGE_MISMATCH")
        if plan_metric_totals["initial_plan_count"] != self.game_target:
            endpoint_failures.append("PRODUCT_INITIAL_PLAN_COVERAGE_MISMATCH")
        if plan_metric_totals["failure_attribution_count"] <= 0:
            endpoint_failures.append("PRODUCT_FAILURE_ATTRIBUTION_MISSING")
        if plan_metric_totals["rollback_plan_count"] <= 0:
            endpoint_failures.append("PRODUCT_ROLLBACK_PLAN_EVIDENCE_MISSING")
        if plan_metric_totals["failed_hypothesis_invalidation_count"] <= 0:
            endpoint_failures.append("PRODUCT_HYPOTHESIS_INVALIDATION_MISSING")
        if plan_metric_totals["post_rollback_replan_count"] <= 0:
            endpoint_failures.append("PRODUCT_POST_ROLLBACK_REPLAN_MISSING")
        if plan_metric_totals["max_plan_step_count"] != 4:
            endpoint_failures.append("PRODUCT_PLAN_DEPTH_MISMATCH")
        normalized_endpoint_failures = tuple(sorted(set(endpoint_failures)))
        known_sample_complete = not normalized_endpoint_failures
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
            "product_total_action_count": sum(action_values),
            "product_plan_integrity_row_count": len(plan_integrity_rows),
            "product_runtime_failure_signature_row_count": (
                runtime_failure_signature_row_count
            ),
            **{
                f"product_{name}": value
                for name, value in plan_metric_totals.items()
            },
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
            "known_sample_regression_established": known_sample_complete,
            "known_sample_regression_status": (
                "KNOWN_SAMPLE_REGRESSION_COMPLETE"
                if known_sample_complete
                else "KNOWN_SAMPLE_REGRESSION_INCOMPLETE"
            ),
            # Higher AGI authority requires genericity, locked-evaluator, and
            # official-full evidence. This endpoint sees none of those gates.
            "product_completion_established": False,
            "product_status": (
                "GENERICITY_NOT_ESTABLISHED"
                if known_sample_complete
                else "KNOWN_SAMPLE_REGRESSION_INCOMPLETE"
            ),
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
