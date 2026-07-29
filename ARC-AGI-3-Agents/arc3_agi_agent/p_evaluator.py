"""Development-validation-only evaluator for isolated PBundle candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .p_bundle import PBundle
from .schema import digest_object

P_EVALUATOR_VERSION: Final = "arc3-p-evaluator-v1"


@dataclass(frozen=True, slots=True)
class PVersionMetric:
    completed_environments: int
    completed_levels: int
    true_progress: int
    crashes: int
    invalid_actions: int
    identity_leaks: int
    actions: int
    memory_cost: int
    resource_cost: int

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in (
            "completed_environments",
            "completed_levels",
            "true_progress",
            "crashes",
            "invalid_actions",
            "identity_leaks",
            "actions",
            "memory_cost",
            "resource_cost",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                failures.append("P_EVALUATOR_METRIC_INVALID:" + name)
        return tuple(sorted(set(failures)))

    def utility(self) -> tuple[int, ...]:
        return (
            self.completed_environments,
            self.completed_levels,
            self.true_progress,
            -self.crashes,
            -self.invalid_actions,
            -self.identity_leaks,
            -self.actions,
            -self.memory_cost,
            -self.resource_cost,
        )


@dataclass(frozen=True, slots=True)
class PBundleEvaluation:
    evaluation_id: str
    evaluator_version: str
    dataset_role: str
    baseline_logical_digest: str
    candidate_logical_digest: str
    baseline: PVersionMetric
    candidate: PVersionMetric
    known_regression_non_degrading: bool
    dev_validation_improved: bool
    abi_compatible: bool
    deterministic: bool
    rollback_target_present: bool
    identity_leak_count: int
    invalid_action_count: int
    crash_count: int

    def digest(self) -> str:
        return "p-evaluation:" + digest_object(self)

    def passed(self) -> bool:
        return (
            self.dataset_role == "DEVELOPMENT_VALIDATION"
            and self.known_regression_non_degrading
            and self.dev_validation_improved
            and self.abi_compatible
            and self.deterministic
            and self.rollback_target_present
            and self.identity_leak_count == 0
            and self.invalid_action_count == 0
            and self.crash_count == 0
        )


@dataclass(frozen=True, slots=True)
class IsolatedPBundleEvaluator:
    evaluator_version: str = P_EVALUATOR_VERSION

    def evaluate(
        self,
        *,
        baseline_bundle: PBundle,
        candidate_bundle: PBundle,
        baseline_metric: PVersionMetric,
        candidate_metric: PVersionMetric,
        dataset_role: str,
        known_regression_non_degrading: bool,
        deterministic: bool = True,
    ) -> PBundleEvaluation:
        if dataset_role != "DEVELOPMENT_VALIDATION":
            raise PermissionError("P_EVALUATOR_ROLE_FORBIDDEN")
        baseline_failures = baseline_bundle.validate()
        candidate_failures = candidate_bundle.validate()
        metric_failures = (
            *baseline_metric.validate(),
            *candidate_metric.validate(),
        )
        failures = (
            *baseline_failures,
            *candidate_failures,
            *metric_failures,
        )
        if failures:
            raise ValueError(";".join(failures))
        if candidate_bundle.manifest.lifecycle != "CANDIDATE":
            raise ValueError("P_EVALUATOR_CANDIDATE_LIFECYCLE_REQUIRED")
        if (
            candidate_bundle.manifest.parent_logical_digest
            != baseline_bundle.logical_digest()
        ):
            raise PermissionError("P_EVALUATOR_PARENT_BINDING_INVALID")
        abi_compatible = (
            baseline_bundle.manifest.l0_abi_version
            == candidate_bundle.manifest.l0_abi_version
        )
        improved = candidate_metric.utility() > baseline_metric.utility()
        return PBundleEvaluation(
            evaluation_id="p-evaluation:"
            + digest_object(
                {
                    "baseline": baseline_bundle.logical_digest(),
                    "candidate": candidate_bundle.logical_digest(),
                    "baseline_metric": baseline_metric,
                    "candidate_metric": candidate_metric,
                    "role": dataset_role,
                }
            )[:32],
            evaluator_version=self.evaluator_version,
            dataset_role=dataset_role,
            baseline_logical_digest=baseline_bundle.logical_digest(),
            candidate_logical_digest=candidate_bundle.logical_digest(),
            baseline=baseline_metric,
            candidate=candidate_metric,
            known_regression_non_degrading=known_regression_non_degrading,
            dev_validation_improved=improved,
            abi_compatible=abi_compatible,
            deterministic=deterministic,
            rollback_target_present=bool(
                candidate_bundle.manifest.parent_logical_digest
            ),
            identity_leak_count=candidate_metric.identity_leaks,
            invalid_action_count=candidate_metric.invalid_actions,
            crash_count=candidate_metric.crashes,
        )


__all__ = [
    "P_EVALUATOR_VERSION",
    "IsolatedPBundleEvaluator",
    "PBundleEvaluation",
    "PVersionMetric",
]
