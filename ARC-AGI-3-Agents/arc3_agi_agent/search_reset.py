"""HDS-authorized RESET for a visibly exhausted exploration branch.

This boundary is intentionally separate from irreversible-failure recovery.
It preserves the learned transition graph, performs no memory rollback, and
permits RESET only when the current rendered branch cannot reach a remaining
frontier that is still reachable from the initial rendered state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from arcengine import FrameDataRaw

from .judgment import HDSR, HDSX, HDSFrame, HDSJudgmentSubject, HDSMc
from .memory import MemoryMutationResult, MemoryOperation, PassiveMemory
from .protocol import AuthorityViolation
from .schema import digest_object, forbidden_runtime_paths

SEARCH_RESET_REASON = "VISUAL_BRANCH_EXHAUSTED_RESET_REQUIRED"
_SEARCH_RESET_CAPABILITY = object()


@dataclass(frozen=True, slots=True)
class HDSSearchResetDecision:
    """HDS-owned decision to preserve M and reset the current environment."""

    decision_id: str
    observation_signature: str
    evidence_signature: str
    memory_version: int
    reset_reference: str
    status: str = "ROLLBACK"
    allow_memory_retention: bool = True
    allow_memory_rollback: bool = False
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
            failures.append("SEARCH_RESET_DECISION_ID_MISSING")
        if not self.observation_signature:
            failures.append("SEARCH_RESET_OBSERVATION_MISSING")
        if not self.evidence_signature:
            failures.append("SEARCH_RESET_EVIDENCE_MISSING")
        if (
            isinstance(self.memory_version, bool)
            or not isinstance(self.memory_version, int)
            or self.memory_version < 0
        ):
            failures.append("SEARCH_RESET_MEMORY_VERSION_INVALID")
        if not self.reset_reference:
            failures.append("SEARCH_RESET_REFERENCE_MISSING")
        if self.status != "ROLLBACK":
            failures.append("SEARCH_RESET_STATUS_INVALID")
        if self.authority != "hds-only":
            failures.append("SEARCH_RESET_AUTHORITY_INVALID")
        if self._capability is not _SEARCH_RESET_CAPABILITY:
            failures.append("SEARCH_RESET_DECISION_NOT_ISSUED_BY_HDS")
        if self.allow_memory_retention is not True:
            failures.append("SEARCH_RESET_MEMORY_RETENTION_NOT_AUTHORIZED")
        if self.allow_memory_rollback is not False:
            failures.append("SEARCH_RESET_MEMORY_ROLLBACK_FORBIDDEN")
        if self.allow_environment_reset is not True:
            failures.append("SEARCH_RESET_ENVIRONMENT_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class SearchResetDirective:
    """Single-use capability for one M retention and one environment RESET."""

    decision_id: str
    observation_signature: str
    expected_memory_version: int
    memory_target: str
    memory_payload_digest: str
    _capability: object | None = field(default=None, repr=False)
    _consumed: bool = field(default=False, init=False, repr=False)
    _reset_consumed: bool = field(default=False, init=False, repr=False)

    def validate(
        self,
        decision: HDSSearchResetDecision,
    ) -> tuple[str, ...]:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("SEARCH_RESET_DIRECTIVE_DECISION_MISMATCH")
        if self.observation_signature != decision.observation_signature:
            failures.append("SEARCH_RESET_DIRECTIVE_OBSERVATION_MISMATCH")
        if self.expected_memory_version != decision.memory_version:
            failures.append("SEARCH_RESET_DIRECTIVE_MEMORY_VERSION_MISMATCH")
        if not self.memory_target:
            failures.append("SEARCH_RESET_MEMORY_TARGET_MISSING")
        if not self.memory_payload_digest:
            failures.append("SEARCH_RESET_MEMORY_PAYLOAD_DIGEST_MISSING")
        if self._capability is not _SEARCH_RESET_CAPABILITY:
            failures.append("SEARCH_RESET_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if self._consumed:
            failures.append("SEARCH_RESET_DIRECTIVE_ALREADY_CONSUMED")
        return tuple(sorted(set(failures)))

    def consume(self, decision: HDSSearchResetDecision) -> None:
        failures = self.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._consumed = True

    def consume_reset(self, decision: HDSSearchResetDecision) -> None:
        failures = list(decision.validate())
        if self.decision_id != decision.decision_id:
            failures.append("SEARCH_RESET_DIRECTIVE_DECISION_MISMATCH")
        if self.observation_signature != decision.observation_signature:
            failures.append("SEARCH_RESET_DIRECTIVE_OBSERVATION_MISMATCH")
        if self._capability is not _SEARCH_RESET_CAPABILITY:
            failures.append("SEARCH_RESET_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if not self._consumed:
            failures.append("SEARCH_RESET_EXECUTION_NOT_STARTED")
        if self._reset_consumed:
            failures.append("SEARCH_RESET_ALREADY_CONSUMED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._reset_consumed = True


@dataclass(slots=True)
class HDSSearchResetController:
    """Close the search-reset Frame and retain capability ownership."""

    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    _decisions: dict[str, HDSSearchResetDecision] = field(
        default_factory=dict,
        init=False,
    )
    _directives: dict[str, SearchResetDirective] = field(
        default_factory=dict,
        init=False,
    )

    def judge(
        self,
        *,
        observation_signature: str,
        reason: str,
        action_count: int,
        memory_version: int,
        evidence_signature: str,
    ) -> HDSSearchResetDecision:
        if reason != SEARCH_RESET_REASON:
            raise AuthorityViolation("SEARCH_RESET_REQUIRES_DISCONNECTED_FRONTIER")
        if (
            isinstance(action_count, bool)
            or not isinstance(action_count, int)
            or action_count < 1
        ):
            raise AuthorityViolation("SEARCH_RESET_REQUIRES_PRIOR_ACTION")
        if (
            isinstance(memory_version, bool)
            or not isinstance(memory_version, int)
            or memory_version < 0
        ):
            raise AuthorityViolation("SEARCH_RESET_MEMORY_VERSION_INVALID")
        if not observation_signature or not evidence_signature:
            raise AuthorityViolation("SEARCH_RESET_RENDERED_EVIDENCE_MISSING")

        reset_reference = "initial-rendered-state:" + digest_object(
            (observation_signature, evidence_signature)
        )[:24]
        frame = HDSFrame(
            frame_id="search-reset-frame:"
            + digest_object(
                {
                    "observation": observation_signature,
                    "evidence": evidence_signature,
                    "action_count": action_count,
                    "memory_version": memory_version,
                }
            )[:24],
            purpose="reopen-disconnected-rendered-frontier",
            x=HDSX(
                targets=("rendered-branch", "passive-memory", "environment"),
                candidate_ids=(),
                observation_scope=(
                    "rendered-observation",
                    "transition-graph",
                    "bounded-action-count",
                ),
            ),
            r=HDSR(
                relations=(
                    "current-branch-has-no-reachable-frontier",
                    "initial-state-retains-untested-frontier",
                    "memory-retention-precedes-reset",
                ),
                evidence_links=(evidence_signature,),
                counter_evidence_links=(),
            ),
            mc=HDSMc(
                identity="search-reset-closure:"
                + digest_object((evidence_signature, reset_reference))[:24],
                boundary="rendered-observation-only",
                acceptance_criteria=("disconnected-frontier-observed",),
                rejection_criteria=("frontier-not-proven",),
                stop_on=("search-reset-complete",),
                allow_memory_write=False,
                allow_external_emit=False,
            ),
            observation_boundary="rendered-observation-only",
            candidates=(),
            evidence=(evidence_signature,),
            counter_evidence=(),
            risk=0.0,
            hazard=False,
            budget=1,
            unknowns=(),
            stopping_conditions=(),
            rollback_condition="rendered-branch-exhausted",
            rollback_reference=reset_reference,
            observation_available=True,
        )
        standalone = self.judgment_subject.judge(frame)
        if (
            standalone.status != "ROLLBACK"
            or standalone.rollback_reference != reset_reference
        ):
            raise AuthorityViolation("HDS_SEARCH_RESET_NOT_AUTHORIZED")
        decision = HDSSearchResetDecision(
            decision_id="search-reset-decision:"
            + digest_object(
                {
                    "frame": frame.digest,
                    "standalone": standalone.digest,
                }
            )[:24],
            observation_signature=observation_signature,
            evidence_signature=evidence_signature,
            memory_version=memory_version,
            reset_reference=reset_reference,
            _capability=_SEARCH_RESET_CAPABILITY,
        )
        failures = decision.validate()
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._decisions[decision.decision_id] = decision
        return decision

    def directive(
        self,
        decision: HDSSearchResetDecision,
        *,
        memory_target: str,
        memory_payload: Mapping[str, object],
    ) -> SearchResetDirective:
        if self._decisions.get(decision.decision_id) is not decision:
            raise AuthorityViolation("SEARCH_RESET_DECISION_NOT_OWNED")
        if decision.decision_id in self._directives:
            raise AuthorityViolation("SEARCH_RESET_DIRECTIVE_ALREADY_ISSUED")
        if forbidden_runtime_paths(memory_payload):
            raise AuthorityViolation("SEARCH_RESET_MEMORY_IDENTITY_FORBIDDEN")
        directive = SearchResetDirective(
            decision_id=decision.decision_id,
            observation_signature=decision.observation_signature,
            expected_memory_version=decision.memory_version,
            memory_target=memory_target,
            memory_payload_digest=digest_object(dict(memory_payload)),
            _capability=_SEARCH_RESET_CAPABILITY,
        )
        failures = directive.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._directives[decision.decision_id] = directive
        return directive


@dataclass(frozen=True, slots=True)
class SearchResetExecutionResult:
    reset_frame: FrameDataRaw
    memory_result: MemoryMutationResult
    memory_version_before: int
    memory_version_after: int


@dataclass(frozen=True, slots=True)
class PureLLMSearchResetExecutor:
    """Retain HDS-approved M and execute one capability-bound RESET."""

    executor: str = "pure-llm"

    def execute(
        self,
        directive: SearchResetDirective,
        decision: HDSSearchResetDecision,
        memory_payload: Mapping[str, object],
        memory: PassiveMemory,
        reset_boundary: object,
    ) -> SearchResetExecutionResult:
        failures = list(directive.validate(decision))
        if self.executor != "pure-llm":
            failures.append("SEARCH_RESET_EXECUTOR_NOT_PURE_LLM")
        if directive.memory_payload_digest != digest_object(dict(memory_payload)):
            failures.append("SEARCH_RESET_MEMORY_PAYLOAD_MISMATCH")
        if memory.version != directive.expected_memory_version:
            failures.append("SEARCH_RESET_MEMORY_VERSION_CONFLICT")
        search_reset = getattr(reset_boundary, "search_reset", None)
        if not callable(search_reset):
            failures.append("SEARCH_RESET_BOUNDARY_MISSING")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        directive.consume(decision)

        before = memory.version
        raw_memory = memory.execute_storage(
            MemoryOperation(
                operation="ADD",
                target=directive.memory_target,
                expected_version=memory.version,
                lifecycle="ACTIVE",
                evidence_signature=decision.evidence_signature,
                payload_items=tuple(sorted(dict(memory_payload).items())),
                provenance=(
                    f"hds-search-reset:{decision.decision_id}",
                    decision.evidence_signature,
                ),
            )
        )
        if not isinstance(raw_memory, MemoryMutationResult):
            raise AuthorityViolation("SEARCH_RESET_MEMORY_RESULT_INVALID")
        reset_call = cast(Callable[..., object], search_reset)
        reset_frame = reset_call(
            directive,
            decision,
            executor=self.executor,
        )
        if not isinstance(reset_frame, FrameDataRaw):
            raise AuthorityViolation("SEARCH_RESET_REOBSERVATION_MISSING")
        return SearchResetExecutionResult(
            reset_frame=reset_frame,
            memory_result=raw_memory,
            memory_version_before=before,
            memory_version_after=memory.version,
        )


def require_search_reset_directive(
    directive: SearchResetDirective,
    decision: HDSSearchResetDecision,
    *,
    executor: str,
) -> None:
    failures = list(decision.validate())
    if executor != "pure-llm":
        failures.append("SEARCH_RESET_EXECUTOR_NOT_PURE_LLM")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))
    directive.consume_reset(decision)


__all__ = [
    "HDSSearchResetController",
    "HDSSearchResetDecision",
    "PureLLMSearchResetExecutor",
    "SEARCH_RESET_REASON",
    "SearchResetDirective",
    "SearchResetExecutionResult",
    "require_search_reset_directive",
]
