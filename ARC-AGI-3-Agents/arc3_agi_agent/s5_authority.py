"""Dedicated HDS capabilities for S5 outcome retention and policy RESET."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from arcengine import FrameDataRaw

from .judgment import (
    HDSR,
    HDSX,
    HDSFrame,
    HDSJudgmentSubject,
    HDSMc,
    JudgmentCandidate,
)
from .memory import (
    MemoryMutationResult,
    MemoryOperation,
    PassiveMemory,
)
from .protocol import AuthorityViolation
from .s5_policy import S5PolicyDecision
from .schema import digest_object, forbidden_runtime_paths

S5_OUTCOME_RETENTION_REASON = "OBSERVED_OUTCOME_RETENTION_CLOSED"
S5_POLICY_RESET_REASON = "RENDERED_POLICY_COMPATIBILITY_RESET_REQUIRED"
_S5_RETENTION_CAPABILITY = object()
_S5_RESET_CAPABILITY = object()


def _payload_failures(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        f"S5_MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
        for path in forbidden_runtime_paths(payload)
    )


def _write_memory(
    *,
    memory: PassiveMemory,
    target: str,
    payload: Mapping[str, object],
    evidence_signature: str,
    provenance: tuple[str, ...],
) -> MemoryMutationResult:
    operation = (
        "REPLACE"
        if target in {entry.target for entry in memory.view().entries}
        else "ADD"
    )
    result = memory.execute_storage(
        MemoryOperation(
            operation=operation,
            target=target,
            expected_version=memory.version,
            lifecycle="ACTIVE",
            evidence_signature=evidence_signature,
            payload_items=tuple(sorted(dict(payload).items())),
            provenance=provenance,
        )
    )
    if not isinstance(result, MemoryMutationResult):
        raise AuthorityViolation("S5_MEMORY_RESULT_INVALID")
    return result


@dataclass(frozen=True, slots=True)
class S5OutcomeRetentionDecision:
    decision_id: str
    observation_signature: str
    result_signature: str
    candidate_digest: str
    memory_version: int
    status: str = "ACCEPT"
    allow_memory_write: bool = True
    allow_external_emit: bool = False
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.decision_id:
            failures.append("S5_RETENTION_DECISION_ID_MISSING")
        if not self.observation_signature:
            failures.append("S5_RETENTION_OBSERVATION_MISSING")
        if not self.result_signature:
            failures.append("S5_RETENTION_RESULT_MISSING")
        if not self.candidate_digest:
            failures.append("S5_RETENTION_CANDIDATE_MISSING")
        if self.memory_version < 0:
            failures.append("S5_RETENTION_MEMORY_VERSION_INVALID")
        if self.status != "ACCEPT":
            failures.append("S5_RETENTION_STATUS_INVALID")
        if self.allow_memory_write is not True:
            failures.append("S5_RETENTION_MEMORY_WRITE_REQUIRED")
        if self.allow_external_emit is not False:
            failures.append("S5_RETENTION_EXTERNAL_EMIT_FORBIDDEN")
        if self.authority != "hds-only":
            failures.append("S5_RETENTION_AUTHORITY_INVALID")
        if self._capability is not _S5_RETENTION_CAPABILITY:
            failures.append("S5_RETENTION_NOT_ISSUED_BY_HDS")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class S5OutcomeRetentionDirective:
    decision_id: str
    expected_memory_version: int
    memory_target: str
    memory_payload_digest: str
    _capability: object | None = field(default=None, repr=False)
    _consumed: bool = field(default=False, init=False, repr=False)

    def consume(self, decision: S5OutcomeRetentionDecision) -> None:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("S5_RETENTION_DIRECTIVE_DECISION_MISMATCH")
        if self.expected_memory_version != decision.memory_version:
            failures.append("S5_RETENTION_DIRECTIVE_MEMORY_VERSION_MISMATCH")
        if not self.memory_target or not self.memory_payload_digest:
            failures.append("S5_RETENTION_DIRECTIVE_PAYLOAD_MISSING")
        if self._capability is not _S5_RETENTION_CAPABILITY:
            failures.append("S5_RETENTION_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if self._consumed:
            failures.append("S5_RETENTION_DIRECTIVE_ALREADY_CONSUMED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._consumed = True


@dataclass(slots=True)
class HDSOutcomeRetentionController:
    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    _decisions: dict[str, S5OutcomeRetentionDecision] = field(
        default_factory=dict,
        init=False,
    )
    _directives: set[str] = field(default_factory=set, init=False)

    def judge(
        self,
        *,
        observation_signature: str,
        result_signature: str,
        candidate_digest: str,
        memory_version: int,
    ) -> S5OutcomeRetentionDecision:
        if (
            not observation_signature
            or not result_signature
            or not candidate_digest
        ):
            raise AuthorityViolation("S5_RETENTION_EVIDENCE_MISSING")
        if memory_version < 0:
            raise AuthorityViolation("S5_RETENTION_MEMORY_VERSION_INVALID")
        candidate_id = "candidate:s5-retain:" + digest_object(
            {
                "observation": observation_signature,
                "result": result_signature,
                "candidate": candidate_digest,
                "memory_version": memory_version,
            }
        )[:24]
        frame = HDSFrame(
            frame_id="s5-retention-frame:" + digest_object(candidate_id)[:24],
            purpose="retain-observed-rendered-outcome",
            x=HDSX(
                targets=("passive-memory", "observed-action-outcome"),
                candidate_ids=(candidate_id,),
                observation_scope=(
                    "rendered-observation",
                    "authorized-emission-result",
                    "bounded-action-effect-history",
                ),
            ),
            r=HDSR(
                relations=(
                    "authorized-result-precedes-factual-memory-retention",
                ),
                evidence_links=(result_signature, candidate_digest),
                counter_evidence_links=(),
            ),
            mc=HDSMc(
                identity="s5-retention-closure:"
                + digest_object((result_signature, candidate_digest))[:24],
                boundary="rendered-observation-only",
                acceptance_criteria=(S5_OUTCOME_RETENTION_REASON,),
                rejection_criteria=("result-not-hds-observed",),
                stop_on=("retention-complete",),
                allow_memory_write=True,
                allow_external_emit=False,
            ),
            observation_boundary="rendered-observation-only",
            candidates=(
                JudgmentCandidate(
                    candidate_id=candidate_id,
                    predicted_outcomes=("factual-outcome-retained",),
                    evidence_refs=(result_signature, candidate_digest),
                    counter_evidence_refs=(),
                    preconditions=("authorized-result-observed",),
                    falsification_conditions=("result-binding-mismatch",),
                    score=1.0,
                    risk=0.0,
                    admissible=True,
                    reason_codes=(S5_OUTCOME_RETENTION_REASON,),
                ),
            ),
            evidence=(result_signature, candidate_digest),
            counter_evidence=(),
            risk=0.0,
            hazard=False,
            budget=1,
            unknowns=(),
            stopping_conditions=(),
            observation_available=True,
        )
        standalone = self.judgment_subject.judge(frame)
        if (
            standalone.status != "ACCEPT"
            or standalone.selected_candidate_id != candidate_id
            or standalone.allow_memory_write is not True
            or standalone.allow_external_emit is not False
        ):
            raise AuthorityViolation("HDS_S5_RETENTION_NOT_AUTHORIZED")
        decision = S5OutcomeRetentionDecision(
            decision_id="s5-retention-decision:"
            + digest_object(
                {
                    "frame": frame.digest,
                    "judgment": standalone.digest,
                }
            )[:24],
            observation_signature=observation_signature,
            result_signature=result_signature,
            candidate_digest=candidate_digest,
            memory_version=memory_version,
            _capability=_S5_RETENTION_CAPABILITY,
        )
        failures = decision.validate()
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._decisions[decision.decision_id] = decision
        return decision

    def directive(
        self,
        decision: S5OutcomeRetentionDecision,
        *,
        memory_target: str,
        memory_payload: Mapping[str, object],
    ) -> S5OutcomeRetentionDirective:
        if self._decisions.get(decision.decision_id) is not decision:
            raise AuthorityViolation("S5_RETENTION_DECISION_NOT_OWNED")
        if decision.decision_id in self._directives:
            raise AuthorityViolation("S5_RETENTION_DIRECTIVE_ALREADY_ISSUED")
        failures = _payload_failures(memory_payload)
        if failures:
            raise AuthorityViolation(";".join(failures))
        directive = S5OutcomeRetentionDirective(
            decision_id=decision.decision_id,
            expected_memory_version=decision.memory_version,
            memory_target=memory_target,
            memory_payload_digest=digest_object(dict(memory_payload)),
            _capability=_S5_RETENTION_CAPABILITY,
        )
        self._directives.add(decision.decision_id)
        return directive


@dataclass(frozen=True, slots=True)
class PureLLMOutcomeRetentionExecutor:
    executor: str = "pure-llm"

    def execute(
        self,
        directive: S5OutcomeRetentionDirective,
        decision: S5OutcomeRetentionDecision,
        memory_payload: Mapping[str, object],
        memory: PassiveMemory,
    ) -> MemoryMutationResult:
        failures = list(decision.validate())
        if self.executor != "pure-llm":
            failures.append("S5_RETENTION_EXECUTOR_NOT_PURE_LLM")
        if memory.version != directive.expected_memory_version:
            failures.append("S5_RETENTION_MEMORY_VERSION_CONFLICT")
        if directive.memory_payload_digest != digest_object(
            dict(memory_payload)
        ):
            failures.append("S5_RETENTION_PAYLOAD_MISMATCH")
        failures.extend(_payload_failures(memory_payload))
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        directive.consume(decision)
        return _write_memory(
            memory=memory,
            target=directive.memory_target,
            payload=memory_payload,
            evidence_signature=decision.result_signature,
            provenance=(
                "hds-s5-outcome-retention",
                decision.decision_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class S5PolicyResetDecision:
    decision_id: str
    observation_signature: str
    policy_digest: str
    query_digest: str
    feature_digest: str
    memory_version: int
    reset_reference: str
    terminal_state: str
    status: str = "ROLLBACK"
    allow_memory_write: bool = True
    allow_environment_reset: bool = True
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.decision_id:
            failures.append("S5_RESET_DECISION_ID_MISSING")
        for name, value in (
            ("OBSERVATION", self.observation_signature),
            ("POLICY", self.policy_digest),
            ("QUERY", self.query_digest),
            ("FEATURE", self.feature_digest),
            ("REFERENCE", self.reset_reference),
        ):
            if not value:
                failures.append(f"S5_RESET_{name}_MISSING")
        if self.memory_version < 0:
            failures.append("S5_RESET_MEMORY_VERSION_INVALID")
        if self.terminal_state not in {"GAME_OVER", "NOT_FINISHED"}:
            failures.append("S5_RESET_TERMINAL_STATE_INVALID")
        if self.status != "ROLLBACK":
            failures.append("S5_RESET_STATUS_INVALID")
        if self.allow_memory_write is not True:
            failures.append("S5_RESET_MEMORY_WRITE_REQUIRED")
        if self.allow_environment_reset is not True:
            failures.append("S5_RESET_ENVIRONMENT_NOT_AUTHORIZED")
        if self.authority != "hds-only":
            failures.append("S5_RESET_AUTHORITY_INVALID")
        if self._capability is not _S5_RESET_CAPABILITY:
            failures.append("S5_RESET_NOT_ISSUED_BY_HDS")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class S5PolicyResetDirective:
    decision_id: str
    observation_signature: str
    expected_memory_version: int
    memory_target: str
    memory_payload_digest: str
    _capability: object | None = field(default=None, repr=False)
    _memory_consumed: bool = field(default=False, init=False, repr=False)
    _reset_consumed: bool = field(default=False, init=False, repr=False)

    def consume_memory(self, decision: S5PolicyResetDecision) -> None:
        failures = self._failures(decision)
        if self._memory_consumed:
            failures.append("S5_RESET_MEMORY_ALREADY_CONSUMED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._memory_consumed = True

    def consume_reset(self, decision: S5PolicyResetDecision) -> None:
        failures = self._failures(decision)
        if not self._memory_consumed:
            failures.append("S5_RESET_MEMORY_NOT_RETAINED")
        if self._reset_consumed:
            failures.append("S5_RESET_ALREADY_CONSUMED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._reset_consumed = True

    def _failures(
        self,
        decision: S5PolicyResetDecision,
    ) -> list[str]:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("S5_RESET_DIRECTIVE_DECISION_MISMATCH")
        if self.observation_signature != decision.observation_signature:
            failures.append("S5_RESET_DIRECTIVE_OBSERVATION_MISMATCH")
        if self.expected_memory_version != decision.memory_version:
            failures.append("S5_RESET_DIRECTIVE_MEMORY_VERSION_MISMATCH")
        if not self.memory_target or not self.memory_payload_digest:
            failures.append("S5_RESET_DIRECTIVE_PAYLOAD_MISSING")
        if self._capability is not _S5_RESET_CAPABILITY:
            failures.append("S5_RESET_DIRECTIVE_NOT_ISSUED_BY_HDS")
        return failures


@dataclass(slots=True)
class HDSPolicyResetController:
    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    _decisions: dict[str, S5PolicyResetDecision] = field(
        default_factory=dict,
        init=False,
    )
    _directives: set[str] = field(default_factory=set, init=False)

    def judge(
        self,
        *,
        observation_signature: str,
        terminal_state: str,
        policy_digest: str,
        query_digest: str,
        policy_decision: S5PolicyDecision,
        memory_version: int,
    ) -> S5PolicyResetDecision:
        if (
            policy_decision.action_id != 0
            or policy_decision.compatibility_reset is not True
        ):
            raise AuthorityViolation("S5_RESET_POLICY_DECISION_REQUIRED")
        if policy_decision.action_margin <= 0.0:
            raise AuthorityViolation("S5_RESET_POLICY_MARGIN_INVALID")
        if terminal_state not in {"GAME_OVER", "NOT_FINISHED"}:
            raise AuthorityViolation("S5_RESET_TERMINAL_STATE_INVALID")
        if not observation_signature or not policy_digest or not query_digest:
            raise AuthorityViolation("S5_RESET_RENDERED_EVIDENCE_MISSING")
        reset_reference = "s5-rendered-reset:" + digest_object(
            {
                "observation": observation_signature,
                "policy": policy_digest,
                "query": query_digest,
                "feature": policy_decision.feature_digest,
            }
        )[:24]
        frame = HDSFrame(
            frame_id="s5-reset-frame:" + digest_object(reset_reference)[:24],
            purpose="execute-rendered-policy-compatibility-reset",
            x=HDSX(
                targets=("rendered-state", "passive-memory", "environment"),
                candidate_ids=(),
                observation_scope=(
                    "rendered-observation",
                    "available-actions",
                    "bounded-action-effect-history",
                    "compiled-policy-output",
                ),
            ),
            r=HDSR(
                relations=(
                    "compiled-policy-selects-compatibility-reset",
                    "memory-retention-precedes-reset",
                ),
                evidence_links=(
                    policy_digest,
                    query_digest,
                    policy_decision.feature_digest,
                ),
                counter_evidence_links=(),
            ),
            mc=HDSMc(
                identity="s5-reset-closure:"
                + digest_object(
                    (
                        policy_digest,
                        query_digest,
                        policy_decision.feature_digest,
                    )
                )[:24],
                boundary="rendered-observation-only",
                acceptance_criteria=(S5_POLICY_RESET_REASON,),
                rejection_criteria=("policy-does-not-select-reset",),
                stop_on=("compatibility-reset-complete",),
                allow_memory_write=False,
                allow_external_emit=False,
            ),
            observation_boundary="rendered-observation-only",
            candidates=(),
            evidence=(
                policy_digest,
                query_digest,
                policy_decision.feature_digest,
            ),
            counter_evidence=(),
            risk=0.0,
            hazard=False,
            budget=1,
            unknowns=(),
            stopping_conditions=(),
            rollback_condition="rendered-policy-reset-selected",
            rollback_reference=reset_reference,
            observation_available=True,
        )
        standalone = self.judgment_subject.judge(frame)
        if (
            standalone.status != "ROLLBACK"
            or standalone.rollback_reference != reset_reference
        ):
            raise AuthorityViolation("HDS_S5_RESET_NOT_AUTHORIZED")
        decision = S5PolicyResetDecision(
            decision_id="s5-reset-decision:"
            + digest_object(
                {
                    "frame": frame.digest,
                    "judgment": standalone.digest,
                }
            )[:24],
            observation_signature=observation_signature,
            policy_digest=policy_digest,
            query_digest=query_digest,
            feature_digest=policy_decision.feature_digest,
            memory_version=memory_version,
            reset_reference=reset_reference,
            terminal_state=terminal_state,
            _capability=_S5_RESET_CAPABILITY,
        )
        failures = decision.validate()
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._decisions[decision.decision_id] = decision
        return decision

    def directive(
        self,
        decision: S5PolicyResetDecision,
        *,
        memory_target: str,
        memory_payload: Mapping[str, object],
    ) -> S5PolicyResetDirective:
        if self._decisions.get(decision.decision_id) is not decision:
            raise AuthorityViolation("S5_RESET_DECISION_NOT_OWNED")
        if decision.decision_id in self._directives:
            raise AuthorityViolation("S5_RESET_DIRECTIVE_ALREADY_ISSUED")
        failures = _payload_failures(memory_payload)
        if failures:
            raise AuthorityViolation(";".join(failures))
        directive = S5PolicyResetDirective(
            decision_id=decision.decision_id,
            observation_signature=decision.observation_signature,
            expected_memory_version=decision.memory_version,
            memory_target=memory_target,
            memory_payload_digest=digest_object(dict(memory_payload)),
            _capability=_S5_RESET_CAPABILITY,
        )
        self._directives.add(decision.decision_id)
        return directive


@dataclass(frozen=True, slots=True)
class S5PolicyResetExecution:
    reset_frame: FrameDataRaw
    memory_result: MemoryMutationResult
    memory_version_before: int
    memory_version_after: int


@dataclass(frozen=True, slots=True)
class PureLLMPolicyResetExecutor:
    executor: str = "pure-llm"

    def execute(
        self,
        directive: S5PolicyResetDirective,
        decision: S5PolicyResetDecision,
        memory_payload: Mapping[str, object],
        memory: PassiveMemory,
        reset_boundary: object,
    ) -> S5PolicyResetExecution:
        failures = list(decision.validate())
        if self.executor != "pure-llm":
            failures.append("S5_RESET_EXECUTOR_NOT_PURE_LLM")
        if memory.version != directive.expected_memory_version:
            failures.append("S5_RESET_MEMORY_VERSION_CONFLICT")
        if directive.memory_payload_digest != digest_object(
            dict(memory_payload)
        ):
            failures.append("S5_RESET_MEMORY_PAYLOAD_MISMATCH")
        reset = getattr(reset_boundary, "s5_policy_reset", None)
        if not callable(reset):
            failures.append("S5_RESET_BOUNDARY_MISSING")
        failures.extend(_payload_failures(memory_payload))
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        directive.consume_memory(decision)
        before = memory.version
        memory_result = _write_memory(
            memory=memory,
            target=directive.memory_target,
            payload=memory_payload,
            evidence_signature=decision.feature_digest,
            provenance=("hds-s5-policy-reset", decision.decision_id),
        )
        reset_call = cast(Callable[..., object], reset)
        reset_frame = reset_call(
            directive,
            decision,
            executor=self.executor,
        )
        if not isinstance(reset_frame, FrameDataRaw):
            raise AuthorityViolation("S5_RESET_REOBSERVATION_MISSING")
        return S5PolicyResetExecution(
            reset_frame=reset_frame,
            memory_result=memory_result,
            memory_version_before=before,
            memory_version_after=memory.version,
        )


def require_s5_policy_reset_directive(
    directive: S5PolicyResetDirective,
    decision: S5PolicyResetDecision,
    *,
    executor: str,
) -> None:
    failures = list(decision.validate())
    if executor != "pure-llm":
        failures.append("S5_RESET_EXECUTOR_NOT_PURE_LLM")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))
    directive.consume_reset(decision)


__all__ = [
    "HDSOutcomeRetentionController",
    "HDSPolicyResetController",
    "PureLLMOutcomeRetentionExecutor",
    "PureLLMPolicyResetExecutor",
    "S5_OUTCOME_RETENTION_REASON",
    "S5_POLICY_RESET_REASON",
    "S5OutcomeRetentionDecision",
    "S5OutcomeRetentionDirective",
    "S5PolicyResetDecision",
    "S5PolicyResetDirective",
    "S5PolicyResetExecution",
    "require_s5_policy_reset_directive",
]
