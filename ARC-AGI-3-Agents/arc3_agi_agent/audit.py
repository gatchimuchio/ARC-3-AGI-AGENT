"""Functional removal audits for Layer-0, instruction body P, and compute C."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .instruction_body import INSTRUCTION_BODY_REMOVAL_WITNESS
from .kernel import (
    COMPUTE_SUBJECT_REMOVAL_WITNESS,
    Layer0Components,
    Layer0Kernel,
)
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
        expected = (
            INSTRUCTION_BODY_REMOVAL_WITNESS
            if self.removed_role == "INSTRUCTION_BODY"
            else COMPUTE_SUBJECT_REMOVAL_WITNESS
            if self.removed_role == "COMPUTE_SUBJECT"
            else ROLE_FAILURE_REASONS[self.removed_role]
        )
        return (
            self.status == "FAIL"
            and self.failure_reason == expected
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


@dataclass(frozen=True, slots=True)
class ComputeSubjectRemovalAuditReport:
    full_set_status: str
    full_trace_digest: str
    cases: tuple[RemovalAuditCase, ...]

    @property
    def failure_witnesses(self) -> tuple[str, ...]:
        return tuple(case.failure_reason for case in self.cases)

    @property
    def passed(self) -> bool:
        expected_count = len(LAYER0_ROOTS) + 2
        return (
            self.full_set_status == "PASS"
            and len(self.cases) == expected_count
            and all(case.passed for case in self.cases)
            and len(set(self.failure_witnesses)) == expected_count
        )


def run_required_removal_audit(
    raw_observation: Mapping[str, object],
) -> RemovalAuditReport:
    """Run the full set and each actual single-callable removal."""

    full_result = Layer0Kernel().run_cycle(raw_observation)
    cases: list[RemovalAuditCase] = []

    for role in LAYER0_ROOTS:
        field_name = _COMPONENT_FIELDS[role]
        components = Layer0Components()
        setattr(components, field_name, None)
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


def run_compute_subject_removal_audit(
    raw_observation: Mapping[str, object],
) -> ComputeSubjectRemovalAuditReport:
    """Audit the six L0 responsibilities plus executable P and compute C."""

    full_result = Layer0Kernel().run_cycle(raw_observation)
    cases: list[RemovalAuditCase] = []
    targets = (*LAYER0_ROOTS, "INSTRUCTION_BODY", "COMPUTE_SUBJECT")
    fields = {
        **_COMPONENT_FIELDS,
        "INSTRUCTION_BODY": "instruction_body",
        "COMPUTE_SUBJECT": "compute",
    }
    for role in targets:
        components = Layer0Components()
        setattr(components, fields[role], None)
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
    return ComputeSubjectRemovalAuditReport(
        full_set_status=full_result.status,
        full_trace_digest=full_result.trace_digest,
        cases=tuple(cases),
    )


__all__ = [
    "ComputeSubjectRemovalAuditReport",
    "RemovalAuditCase",
    "RemovalAuditReport",
    "run_compute_subject_removal_audit",
    "run_required_removal_audit",
]
