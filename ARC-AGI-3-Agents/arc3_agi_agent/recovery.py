"""HDS-authorized P10 recovery after an observed irreversible failure."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from arcengine import FrameDataRaw

from .adapters.in_memory import EmissionResult
from .ir import CandidateIR
from .judgment import (
    HDSR,
    HDSX,
    HDSFrame,
    HDSJudgmentSubject,
    HDSMc,
)
from .memory import (
    MemoryMutationResult,
    MemoryOperation,
    PassiveMemory,
)
from .protocol import AuthorityViolation
from .schema import digest_object, forbidden_runtime_paths

_RECOVERY_CAPABILITY = object()


@dataclass(frozen=True, slots=True)
class HDSRecoveryDecision:
    """A rollback decision owned by the recovery controller."""

    decision_id: str
    result_signature: str
    rollback_version: int
    rollback_reference: str
    status: str = "ROLLBACK"
    allow_memory_recovery: bool = True
    allow_environment_reset: bool = True
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.decision_id:
            failures.append("RECOVERY_DECISION_ID_MISSING")
        if not self.result_signature:
            failures.append("RECOVERY_RESULT_SIGNATURE_MISSING")
        if (
            isinstance(self.rollback_version, bool)
            or not isinstance(self.rollback_version, int)
            or self.rollback_version < 0
        ):
            failures.append("RECOVERY_ROLLBACK_VERSION_INVALID")
        if not self.rollback_reference:
            failures.append("RECOVERY_ROLLBACK_REFERENCE_MISSING")
        if self.status != "ROLLBACK":
            failures.append("RECOVERY_STATUS_INVALID")
        if self.authority != "hds-only":
            failures.append("RECOVERY_AUTHORITY_INVALID")
        if self._capability is not _RECOVERY_CAPABILITY:
            failures.append("RECOVERY_DECISION_NOT_ISSUED_BY_HDS")
        if self.allow_memory_recovery is not True:
            failures.append("RECOVERY_MEMORY_NOT_AUTHORIZED")
        if self.allow_environment_reset is not True:
            failures.append("RECOVERY_RESET_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class RecoveryDirective:
    """Single-use capability for rollback, failure retention, and RESET."""

    decision_id: str
    result_signature: str
    rollback_version: int
    expected_memory_version: int
    failure_target: str
    failure_payload_digest: str
    _capability: object | None = field(default=None, repr=False)
    _consumed: bool = field(default=False, init=False, repr=False)
    _reset_consumed: bool = field(default=False, init=False, repr=False)

    def validate(
        self,
        decision: HDSRecoveryDecision,
    ) -> tuple[str, ...]:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("RECOVERY_DIRECTIVE_DECISION_MISMATCH")
        if self.result_signature != decision.result_signature:
            failures.append("RECOVERY_DIRECTIVE_RESULT_MISMATCH")
        if self.rollback_version != decision.rollback_version:
            failures.append("RECOVERY_DIRECTIVE_VERSION_MISMATCH")
        if (
            isinstance(self.expected_memory_version, bool)
            or not isinstance(self.expected_memory_version, int)
            or self.expected_memory_version < self.rollback_version
        ):
            failures.append("RECOVERY_EXPECTED_MEMORY_VERSION_INVALID")
        if not self.failure_target:
            failures.append("RECOVERY_FAILURE_TARGET_MISSING")
        if not self.failure_payload_digest:
            failures.append("RECOVERY_FAILURE_PAYLOAD_DIGEST_MISSING")
        if self._capability is not _RECOVERY_CAPABILITY:
            failures.append("RECOVERY_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if self._consumed:
            failures.append("RECOVERY_DIRECTIVE_ALREADY_CONSUMED")
        return tuple(sorted(set(failures)))

    def consume(self, decision: HDSRecoveryDecision) -> None:
        failures = self.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._consumed = True

    def consume_reset(self, decision: HDSRecoveryDecision) -> None:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("RECOVERY_DIRECTIVE_DECISION_MISMATCH")
        if self.result_signature != decision.result_signature:
            failures.append("RECOVERY_DIRECTIVE_RESULT_MISMATCH")
        if self._capability is not _RECOVERY_CAPABILITY:
            failures.append("RECOVERY_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if not self._consumed:
            failures.append("RECOVERY_EXECUTION_NOT_STARTED")
        if self._reset_consumed:
            failures.append("RECOVERY_RESET_ALREADY_CONSUMED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._reset_consumed = True


@dataclass(slots=True)
class HDSRecoveryController:
    """Create a rollback Frame and retain ownership of issued capabilities."""

    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    _decisions: dict[str, HDSRecoveryDecision] = field(
        default_factory=dict,
        init=False,
    )
    _directives: dict[str, RecoveryDirective] = field(
        default_factory=dict,
        init=False,
    )

    def judge(
        self,
        result: EmissionResult,
        candidate: CandidateIR,
        *,
        rollback_version: int,
        memory_version: int,
    ) -> HDSRecoveryDecision:
        if result.terminal_state != "GAME_OVER" and (
            "IRREVERSIBLE_FAILURE" not in result.visible_effects
        ):
            raise AuthorityViolation("RECOVERY_REQUIRES_OBSERVED_FAILURE")
        if (
            isinstance(rollback_version, bool)
            or not isinstance(rollback_version, int)
            or rollback_version < 0
            or rollback_version > memory_version
        ):
            raise AuthorityViolation("RECOVERY_ROLLBACK_VERSION_INVALID")
        rollback_reference = f"memory-version:{rollback_version}"
        frame = HDSFrame(
            frame_id="recovery-frame:"
            + digest_object(
                {
                    "result": result.result_signature,
                    "candidate": candidate.candidate_id,
                    "memory_version": memory_version,
                    "rollback_version": rollback_version,
                }
            )[:24],
            purpose="restore-last-safe-state-after-observed-failure",
            x=HDSX(
                targets=("observed-failure", "passive-memory", "environment"),
                candidate_ids=(),
                observation_scope=(
                    "rendered-result",
                    "authorized-emission-receipt",
                    "memory-version",
                ),
            ),
            r=HDSR(
                relations=(
                    "authorized-action-produced-observed-failure",
                    "rollback-reference-precedes-reset",
                ),
                evidence_links=(result.result_signature,),
                counter_evidence_links=(),
            ),
            mc=HDSMc(
                identity="recovery-closure:"
                + digest_object(
                    (result.result_signature, rollback_reference)
                )[:24],
                boundary="rendered-observation-only",
                acceptance_criteria=("failure-observed",),
                rejection_criteria=("failure-not-observed",),
                stop_on=("recovery-complete",),
                allow_memory_write=False,
                allow_external_emit=False,
            ),
            observation_boundary="rendered-observation-only",
            candidates=(),
            evidence=(result.result_signature,),
            counter_evidence=(),
            risk=1.0,
            hazard=False,
            budget=1,
            unknowns=(),
            stopping_conditions=(),
            rollback_condition="observed-irreversible-failure",
            rollback_reference=rollback_reference,
            observation_available=True,
        )
        standalone = self.judgment_subject.judge(frame)
        if (
            standalone.status != "ROLLBACK"
            or standalone.rollback_reference != rollback_reference
        ):
            raise AuthorityViolation("HDS_RECOVERY_ROLLBACK_NOT_AUTHORIZED")
        decision = HDSRecoveryDecision(
            decision_id="recovery-decision:"
            + digest_object(
                {
                    "frame": frame.digest,
                    "standalone": standalone.digest,
                }
            )[:24],
            result_signature=result.result_signature,
            rollback_version=rollback_version,
            rollback_reference=rollback_reference,
            _capability=_RECOVERY_CAPABILITY,
        )
        failures = decision.validate()
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._decisions[decision.decision_id] = decision
        return decision

    def directive(
        self,
        decision: HDSRecoveryDecision,
        *,
        memory_version: int,
        failure_target: str,
        failure_payload: Mapping[str, object],
    ) -> RecoveryDirective:
        if self._decisions.get(decision.decision_id) is not decision:
            raise AuthorityViolation("RECOVERY_DECISION_NOT_OWNED")
        if decision.decision_id in self._directives:
            raise AuthorityViolation("RECOVERY_DIRECTIVE_ALREADY_ISSUED")
        if forbidden_runtime_paths(failure_payload):
            raise AuthorityViolation("RECOVERY_FAILURE_PAYLOAD_IDENTITY_FORBIDDEN")
        directive = RecoveryDirective(
            decision_id=decision.decision_id,
            result_signature=decision.result_signature,
            rollback_version=decision.rollback_version,
            expected_memory_version=memory_version,
            failure_target=failure_target,
            failure_payload_digest=digest_object(dict(failure_payload)),
            _capability=_RECOVERY_CAPABILITY,
        )
        failures = directive.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._directives[decision.decision_id] = directive
        return directive


@dataclass(frozen=True, slots=True)
class RecoveryExecutionResult:
    reset_frame: FrameDataRaw
    rollback_result: MemoryMutationResult | None
    failure_memory_result: MemoryMutationResult
    memory_version_before: int
    memory_version_after: int


@dataclass(frozen=True, slots=True)
class PureLLMRecoveryExecutor:
    """Execute only a controller-owned recovery directive."""

    executor: str = "pure-llm"

    def execute(
        self,
        directive: RecoveryDirective,
        decision: HDSRecoveryDecision,
        failure_payload: Mapping[str, object],
        memory: PassiveMemory,
        recovery_boundary: object,
    ) -> RecoveryExecutionResult:
        failures = list(directive.validate(decision))
        if self.executor != "pure-llm":
            failures.append("RECOVERY_EXECUTOR_NOT_PURE_LLM")
        if directive.failure_payload_digest != digest_object(
            dict(failure_payload)
        ):
            failures.append("RECOVERY_FAILURE_PAYLOAD_MISMATCH")
        if memory.version != directive.expected_memory_version:
            failures.append("RECOVERY_MEMORY_VERSION_CONFLICT")
        recover = getattr(recovery_boundary, "recover", None)
        if not callable(recover):
            failures.append("RECOVERY_BOUNDARY_MISSING")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        directive.consume(decision)

        before = memory.version
        rollback_result: MemoryMutationResult | None = None
        if directive.rollback_version < memory.version:
            raw_rollback = memory.execute_storage(
                MemoryOperation(
                    operation="ROLLBACK",
                    target="visual-explorer-state",
                    expected_version=memory.version,
                    lifecycle="PROPOSED",
                    evidence_signature=directive.result_signature,
                    rollback_version=directive.rollback_version,
                    provenance=(
                        f"hds-recovery:{decision.decision_id}",
                        directive.result_signature,
                    ),
                )
            )
            if not isinstance(raw_rollback, MemoryMutationResult):
                raise AuthorityViolation("RECOVERY_MEMORY_ROLLBACK_RESULT_INVALID")
            rollback_result = raw_rollback

        raw_failure = memory.execute_storage(
            MemoryOperation(
                operation="ADD",
                target=directive.failure_target,
                expected_version=memory.version,
                lifecycle="REJECTED",
                evidence_signature=directive.result_signature,
                payload_items=tuple(sorted(dict(failure_payload).items())),
                provenance=(
                    f"hds-recovery:{decision.decision_id}",
                    directive.result_signature,
                ),
            )
        )
        if not isinstance(raw_failure, MemoryMutationResult):
            raise AuthorityViolation("RECOVERY_FAILURE_MEMORY_RESULT_INVALID")
        recover_call = cast(Callable[..., object], recover)
        reset_frame = recover_call(
            directive,
            decision,
            executor=self.executor,
        )
        if not isinstance(reset_frame, FrameDataRaw):
            raise AuthorityViolation("RECOVERY_RESET_REOBSERVATION_MISSING")
        return RecoveryExecutionResult(
            reset_frame=reset_frame,
            rollback_result=rollback_result,
            failure_memory_result=raw_failure,
            memory_version_before=before,
            memory_version_after=memory.version,
        )


def require_recovery_directive(
    directive: RecoveryDirective,
    decision: HDSRecoveryDecision,
    *,
    executor: str,
) -> None:
    failures = list(decision.validate())
    if executor != "pure-llm":
        failures.append("RECOVERY_EXECUTOR_NOT_PURE_LLM")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))
    directive.consume_reset(decision)


__all__ = [
    "HDSRecoveryController",
    "HDSRecoveryDecision",
    "PureLLMRecoveryExecutor",
    "RecoveryDirective",
    "RecoveryExecutionResult",
    "require_recovery_directive",
]
