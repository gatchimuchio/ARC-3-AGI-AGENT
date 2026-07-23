"""Functional removal audit for the six callable Layer-0 responsibilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from .kernel import Layer0Components, Layer0Kernel
from .protocol import LAYER0_ROOTS
from .roles import ROLE_FAILURE_REASONS, Layer0FunctionalLoss

_COMPONENT_FIELDS = {
    "SYMBOL_SPACE": "symbol_space",
    "CONTEXT_STATE": "context_state",
    "TRANSFORM_OR_WORLD_MODEL": "world_model",
    "CANDIDATE_SURFACE": "candidate_surface",
    "FITTING_OR_SUCCESS_CRITERION": "success_criterion",
    "EMISSION_INTERFACE": "emission_interface",
}


@dataclass(frozen=True, slots=True)
class RemovalAuditCase:
    removed_role: str
    status: str
    failure_reason: str
    observed_stage: str
    callable_removed: bool
    substitution_observed: bool

    @property
    def passed(self) -> bool:
        return (
            self.status == "FAIL"
            and self.failure_reason == ROLE_FAILURE_REASONS[self.removed_role]
            and self.callable_removed
            and not self.substitution_observed
        )


@dataclass(frozen=True, slots=True)
class RemovalAuditReport:
    full_set_status: str
    full_trace_digest: str
    cases: tuple[RemovalAuditCase, ...]

    @property
    def failure_witnesses(self) -> tuple[str, ...]:
        return tuple(case.failure_reason for case in self.cases)

    @property
    def passed(self) -> bool:
        return (
            self.full_set_status == "PASS"
            and len(self.cases) == len(LAYER0_ROOTS)
            and all(case.passed for case in self.cases)
            and len(set(self.failure_witnesses)) == len(LAYER0_ROOTS)
        )


def run_required_removal_audit(
    raw_observation: Mapping[str, object],
) -> RemovalAuditReport:
    """Run the full set and each actual single-callable removal."""

    full_result = Layer0Kernel().run_cycle(raw_observation)
    cases: list[RemovalAuditCase] = []

    for role in LAYER0_ROOTS:
        field_name = _COMPONENT_FIELDS[role]
        components = replace(Layer0Components(), **{field_name: None})
        try:
            Layer0Kernel(components).run_cycle(raw_observation)
        except Layer0FunctionalLoss as exc:
            cases.append(
                RemovalAuditCase(
                    removed_role=role,
                    status="FAIL",
                    failure_reason=exc.reason,
                    observed_stage=exc.stage,
                    callable_removed=exc.removed and exc.role == role,
                    substitution_observed=exc.role != role,
                )
            )
        else:
            cases.append(
                RemovalAuditCase(
                    removed_role=role,
                    status="UNEXPECTED_PASS",
                    failure_reason="FUNCTIONAL_EQUIVALENT_OR_FALLBACK_REMAINED",
                    observed_stage="UNKNOWN",
                    callable_removed=True,
                    substitution_observed=True,
                )
            )

    return RemovalAuditReport(
        full_set_status=full_result.status,
        full_trace_digest=full_result.trace_digest,
        cases=tuple(cases),
    )


__all__ = [
    "RemovalAuditCase",
    "RemovalAuditReport",
    "run_required_removal_audit",
]
