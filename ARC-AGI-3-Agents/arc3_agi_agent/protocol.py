"""Executable authority contracts for the ARC-3 restart foundation.

Adapted from the legacy repository's ``agent/trinity_protocol.py`` at
commit ``0970dc6a56addf2f2ca494efbf80ef919e2e3a12``. This module is an
isolated protocol seam. It does not implement a planner, a policy, persistent
memory, or an environment adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

PROTOCOL_VERSION = "arc3-restart-protocol-v2"

LAYER0_ROOTS = (
    "SYMBOL_SPACE",
    "CONTEXT_STATE",
    "TRANSFORM_OR_WORLD_MODEL",
    "CANDIDATE_SURFACE",
    "FITTING_OR_SUCCESS_CRITERION",
    "EMISSION_INTERFACE",
)

COMPUTE_OPERATIONS = frozenset({"INPUT_READ", "MEMORY_READ", "LLM_COMPUTE"})
DECISION_STATUSES = frozenset(
    {"PASS", "EMIT", "PROBE", "HOLD", "SUSPEND", "REJECT", "STOP", "ROLLBACK"}
)
MEMORY_OPERATIONS = frozenset(
    {
        "ADD",
        "REVISE",
        "MERGE",
        "SPLIT",
        "REPLACE",
        "INVALIDATE",
        "DELETE",
        "REINDEX",
        "ROLLBACK",
        "ARCHIVE",
    }
)
MEMORY_LIFECYCLES = frozenset(
    {
        "PROPOSED",
        "PROBATION",
        "ACTIVE",
        "SUSPENDED",
        "SUPERSEDED",
        "REJECTED",
        "ARCHIVED",
        "SEALED",
    }
)

_HDS_AUTHORIZATION_CAPABILITY = object()


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class AuthorityViolation(PermissionError):
    """Raised when computation, mutation, or emission crosses the HDS boundary."""


@dataclass(slots=True)
class _SingleUseAuthorization:
    """Mutable one-shot grant embedded in an otherwise immutable directive."""

    purpose: str
    consumed: bool = False
    _receipt: object = field(default_factory=object, repr=False)
    _receipt_digest: str = field(default="", repr=False)
    _owner: object | None = field(default=None, repr=False)

    def bind_owner(self, owner: object) -> None:
        if self._owner is not None:
            raise AuthorityViolation(f"{self.purpose}_DIRECTIVE_OWNER_ALREADY_BOUND")
        self._owner = owner

    def is_owned_by(self, owner: object) -> bool:
        return self._owner is owner

    def consume(self, owner: object) -> object:
        if not self.is_owned_by(owner):
            raise AuthorityViolation(f"{self.purpose}_DIRECTIVE_NOT_OWNED")
        if self.consumed:
            raise AuthorityViolation(f"{self.purpose}_DIRECTIVE_ALREADY_CONSUMED")
        self.consumed = True
        return self._receipt

    def bind_receipt(
        self,
        owner: object,
        receipt: object,
        content_digest: str,
    ) -> None:
        if not self.is_owned_by(owner):
            raise AuthorityViolation(f"{self.purpose}_DIRECTIVE_NOT_OWNED")
        if not self.consumed or receipt is not self._receipt:
            raise AuthorityViolation(f"{self.purpose}_RECEIPT_NOT_OWNED")
        if self._receipt_digest:
            raise AuthorityViolation(f"{self.purpose}_RECEIPT_ALREADY_BOUND")
        if not content_digest.strip():
            raise AuthorityViolation(f"{self.purpose}_RECEIPT_DIGEST_MISSING")
        self._receipt_digest = content_digest

    def owns_receipt(
        self,
        owner: object,
        receipt: object | None,
        content_digest: str,
    ) -> bool:
        return (
            self.is_owned_by(owner)
            and self.consumed
            and receipt is self._receipt
            and bool(self._receipt_digest)
            and content_digest == self._receipt_digest
        )


@dataclass(frozen=True, slots=True)
class InstructionBodyContract:
    """Immutable execution contract; mutable judgment memory is not this body."""

    version: str = PROTOCOL_VERSION
    layer0_roots: tuple[str, ...] = LAYER0_ROOTS
    pure_llm_authority: str = "compute-and-propose-only"
    hds_authority: str = (
        "command-judge-accept-reject-suspend-rollback-stop-and-authorize"
    )
    memory_authority: str = "passive-state-hds-authorized-write-only"
    removal_witnesses: tuple[str, ...] = (
        "without-symbol-space-no-reusable-input-alphabet",
        "without-context-state-no-cross-observation-conditioning",
        "without-transform-no-bounded-transition-hypothesis",
        "without-candidate-surface-no-comparable-proposals",
        "without-success-criterion-no-verifiable-closure",
        "without-emission-interface-no-external-action-boundary",
    )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _is_nonempty_text(self.version):
            failures.append("PROTOCOL_VERSION_MISSING")
        if self.layer0_roots != LAYER0_ROOTS:
            failures.append("LAYER0_ROOT_SET_INVALID")
        if len(self.removal_witnesses) != len(LAYER0_ROOTS):
            failures.append("LAYER0_REMOVAL_WITNESS_COUNT_INVALID")
        if self.pure_llm_authority != "compute-and-propose-only":
            failures.append("PURE_LLM_AUTHORITY_INVALID")
        if self.hds_authority != (
            "command-judge-accept-reject-suspend-rollback-stop-and-authorize"
        ):
            failures.append("HDS_AUTHORITY_INVALID")
        if self.memory_authority != "passive-state-hds-authorized-write-only":
            failures.append("MEMORY_AUTHORITY_INVALID")
        return tuple(sorted(set(failures)))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "layer0_roots": list(self.layer0_roots),
            "pure_llm_authority": self.pure_llm_authority,
            "hds_authority": self.hds_authority,
            "memory_authority": self.memory_authority,
            "removal_witnesses": list(self.removal_witnesses),
        }


@dataclass(frozen=True, slots=True)
class ComputeRequest:
    """Single-use HDS command passed to the subordinate computation surface."""

    command_id: str
    operation: str
    observation_signature: str
    context_signature: str = ""
    memory_signature: str = ""
    contract_version: str = PROTOCOL_VERSION
    feature_tokens: tuple[str, ...] = ()
    authority: str = "hds-only"

    def validate(self, contract: InstructionBodyContract) -> tuple[str, ...]:
        failures: list[str] = []
        if not _is_nonempty_text(self.command_id):
            failures.append("COMMAND_ID_MISSING")
        if (
            not isinstance(self.operation, str)
            or self.operation not in COMPUTE_OPERATIONS
        ):
            failures.append("COMPUTE_OPERATION_INVALID")
        if not _is_nonempty_text(self.observation_signature):
            failures.append("OBSERVATION_SIGNATURE_MISSING")
        if not _is_nonempty_text(self.context_signature):
            failures.append("CONTEXT_SIGNATURE_MISSING")
        if not _is_nonempty_text(self.memory_signature):
            failures.append("MEMORY_SIGNATURE_MISSING")
        if self.contract_version != contract.version:
            failures.append("CONTRACT_VERSION_MISMATCH")
        if self.authority != "hds-only":
            failures.append("COMPUTE_REQUEST_AUTHORITY_INVALID")
        if not isinstance(self.feature_tokens, tuple) or any(
            not _is_nonempty_text(token) for token in self.feature_tokens
        ):
            failures.append("FEATURE_TOKEN_EMPTY")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class ComputeResult:
    """Pure-LLM result. A result is a proposal, never a new authority grant."""

    command_id: str
    executor: str
    status: str
    result: object | None = None

    def validate(self, request: ComputeRequest) -> tuple[str, ...]:
        failures: list[str] = []
        if self.command_id != request.command_id:
            failures.append("RESULT_COMMAND_MISMATCH")
        if self.executor != "pure-llm":
            failures.append("PURE_LLM_EXECUTOR_REQUIRED")
        if (
            not isinstance(self.status, str)
            or self.status not in {"COMPUTED", "EXECUTED", "REJECTED"}
        ):
            failures.append("COMPUTE_RESULT_STATUS_INVALID")
        return tuple(sorted(set(failures)))

    @classmethod
    def from_mapping(
        cls,
        command_id: str,
        value: Mapping[str, object],
        *,
        status: str = "COMPUTED",
    ) -> "ComputeResult":
        return cls(
            command_id=command_id,
            executor=str(value.get("executor", "")),
            status=status,
            result=dict(value),
        )


@dataclass(frozen=True, slots=True)
class HDSDecision:
    """Typed HDS judgment; proposal generation does not grant authority."""

    command_id: str
    decision_id: str
    status: str = "SUSPEND"
    reason_codes: tuple[str, ...] = ()
    candidate_id: str | None = None
    closure_signature: str = ""
    allow_memory_write: bool = False
    allow_external_emit: bool = False
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def is_hds_authorized(self) -> bool:
        return self._capability is _HDS_AUTHORIZATION_CAPABILITY

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _is_nonempty_text(self.command_id):
            failures.append("HDS_COMMAND_ID_MISSING")
        if not _is_nonempty_text(self.decision_id):
            failures.append("HDS_DECISION_ID_MISSING")
        if (
            not isinstance(self.status, str)
            or self.status not in DECISION_STATUSES
        ):
            failures.append("HDS_DECISION_STATUS_INVALID")
        if self.authority != "hds-only":
            failures.append("HDS_DECISION_AUTHORITY_INVALID")
        if not self.is_hds_authorized():
            failures.append("HDS_DECISION_NOT_ISSUED_BY_HDS")
        if not isinstance(self.reason_codes, tuple) or any(
            not _is_nonempty_text(code) for code in self.reason_codes
        ):
            failures.append("HDS_REASON_CODE_EMPTY")
        if not isinstance(self.allow_memory_write, bool):
            failures.append("MEMORY_WRITE_FLAG_INVALID")
        if not isinstance(self.allow_external_emit, bool):
            failures.append("EXTERNAL_EMIT_FLAG_INVALID")
        if (
            self.allow_external_emit is True
            and self.status not in {"PASS", "EMIT", "PROBE"}
        ):
            failures.append("EXTERNAL_EMIT_NOT_COMPATIBLE_WITH_STATUS")
        if self.allow_external_emit is True and not _is_nonempty_text(
            self.candidate_id
        ):
            failures.append("EXTERNAL_EMIT_CANDIDATE_MISSING")
        if self.allow_external_emit is True and not _is_nonempty_text(
            self.closure_signature
        ):
            failures.append("EXTERNAL_EMIT_CLOSURE_MISSING")
        if (
            self.allow_memory_write is True
            and self.status in {"REJECT", "STOP"}
        ):
            failures.append("MEMORY_WRITE_NOT_COMPATIBLE_WITH_STATUS")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class MemoryDirective:
    """HDS-issued memory mutation directive executed by the compute surface."""

    command_id: str
    decision_id: str
    operation: str
    target: str
    lifecycle: str
    evidence_signature: str
    payload_digest: str = ""
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _authorization: _SingleUseAuthorization | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(self, decision: HDSDecision) -> tuple[str, ...]:
        failures: list[str] = []
        if decision.validate():
            failures.append("HDS_DECISION_INVALID")
        if not _is_nonempty_text(self.command_id):
            failures.append("MEMORY_COMMAND_ID_MISSING")
        if self.command_id != decision.command_id:
            failures.append("MEMORY_COMMAND_MISMATCH")
        if self.decision_id != decision.decision_id:
            failures.append("MEMORY_DECISION_MISMATCH")
        if (
            not isinstance(self.operation, str)
            or self.operation not in MEMORY_OPERATIONS
        ):
            failures.append("MEMORY_OPERATION_INVALID")
        if not _is_nonempty_text(self.target):
            failures.append("MEMORY_TARGET_MISSING")
        if (
            not isinstance(self.lifecycle, str)
            or self.lifecycle not in MEMORY_LIFECYCLES
        ):
            failures.append("MEMORY_LIFECYCLE_INVALID")
        if not _is_nonempty_text(self.evidence_signature):
            failures.append("MEMORY_EVIDENCE_MISSING")
        if not _is_nonempty_text(self.payload_digest):
            failures.append("MEMORY_PAYLOAD_DIGEST_MISSING")
        if self.authority != "hds-only":
            failures.append("MEMORY_DIRECTIVE_AUTHORITY_INVALID")
        if self._capability is not _HDS_AUTHORIZATION_CAPABILITY:
            failures.append("MEMORY_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if (
            not isinstance(self._authorization, _SingleUseAuthorization)
            or self._authorization.purpose != "MEMORY_WRITE"
        ):
            failures.append("MEMORY_DIRECTIVE_AUTHORIZATION_INVALID")
        elif not self._authorization.is_owned_by(self):
            failures.append("MEMORY_WRITE_DIRECTIVE_NOT_OWNED")
        elif self._authorization.consumed:
            failures.append("MEMORY_WRITE_DIRECTIVE_ALREADY_CONSUMED")
        if not decision.allow_memory_write:
            failures.append("MEMORY_WRITE_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))

    def consume(self, decision: HDSDecision) -> object:
        failures = self.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        if not isinstance(self._authorization, _SingleUseAuthorization):
            raise AuthorityViolation("MEMORY_DIRECTIVE_AUTHORIZATION_INVALID")
        return self._authorization.consume(self)

    def bind_owner(self) -> None:
        if not isinstance(self._authorization, _SingleUseAuthorization):
            raise AuthorityViolation("MEMORY_DIRECTIVE_AUTHORIZATION_INVALID")
        self._authorization.bind_owner(self)

    @property
    def is_consumed(self) -> bool:
        return (
            isinstance(self._authorization, _SingleUseAuthorization)
            and self._authorization.consumed
        )


@dataclass(frozen=True, slots=True)
class EmissionDirective:
    """HDS-issued external action authorization."""

    command_id: str
    decision_id: str
    action_id: int
    reasoning_digest: str
    candidate_id: str = ""
    closure_signature: str = ""
    observation_signature: str = ""
    authority: str = "hds-only"
    _capability: object | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _authorization: _SingleUseAuthorization | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(self, decision: HDSDecision) -> tuple[str, ...]:
        failures: list[str] = []
        if decision.validate():
            failures.append("HDS_DECISION_INVALID")
        if self.command_id != decision.command_id:
            failures.append("EMISSION_COMMAND_MISMATCH")
        if self.decision_id != decision.decision_id:
            failures.append("EMISSION_DECISION_MISMATCH")
        if (
            isinstance(self.action_id, bool)
            or not isinstance(self.action_id, int)
            or not 1 <= self.action_id <= 7
        ):
            failures.append("EMISSION_ACTION_INVALID")
        if not _is_nonempty_text(self.reasoning_digest):
            failures.append("EMISSION_REASONING_DIGEST_MISSING")
        if not _is_nonempty_text(self.candidate_id):
            failures.append("EMISSION_CANDIDATE_MISSING")
        elif self.candidate_id != decision.candidate_id:
            failures.append("EMISSION_CANDIDATE_MISMATCH")
        if not _is_nonempty_text(self.closure_signature):
            failures.append("EMISSION_CLOSURE_MISSING")
        elif self.closure_signature != decision.closure_signature:
            failures.append("EMISSION_CLOSURE_MISMATCH")
        if not _is_nonempty_text(self.observation_signature):
            failures.append("EMISSION_OBSERVATION_SIGNATURE_MISSING")
        if self.authority != "hds-only":
            failures.append("EMISSION_DIRECTIVE_AUTHORITY_INVALID")
        if self._capability is not _HDS_AUTHORIZATION_CAPABILITY:
            failures.append("EMISSION_DIRECTIVE_NOT_ISSUED_BY_HDS")
        if (
            not isinstance(self._authorization, _SingleUseAuthorization)
            or self._authorization.purpose != "EXTERNAL_EMIT"
        ):
            failures.append("EMISSION_DIRECTIVE_AUTHORIZATION_INVALID")
        elif not self._authorization.is_owned_by(self):
            failures.append("EXTERNAL_EMIT_DIRECTIVE_NOT_OWNED")
        elif self._authorization.consumed:
            failures.append("EXTERNAL_EMIT_DIRECTIVE_ALREADY_CONSUMED")
        if not decision.allow_external_emit:
            failures.append("EXTERNAL_EMIT_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))

    def consume(self, decision: HDSDecision) -> object:
        failures = self.validate(decision)
        if failures:
            raise AuthorityViolation(";".join(failures))
        if not isinstance(self._authorization, _SingleUseAuthorization):
            raise AuthorityViolation("EMISSION_DIRECTIVE_AUTHORIZATION_INVALID")
        return self._authorization.consume(self)

    def bind_owner(self) -> None:
        if not isinstance(self._authorization, _SingleUseAuthorization):
            raise AuthorityViolation("EMISSION_DIRECTIVE_AUTHORIZATION_INVALID")
        self._authorization.bind_owner(self)

    def bind_receipt(self, receipt: object, content_digest: str) -> None:
        if not isinstance(self._authorization, _SingleUseAuthorization):
            raise AuthorityViolation("EMISSION_DIRECTIVE_AUTHORIZATION_INVALID")
        self._authorization.bind_receipt(self, receipt, content_digest)

    def owns_receipt(
        self,
        receipt: object | None,
        content_digest: str,
    ) -> bool:
        return (
            isinstance(self._authorization, _SingleUseAuthorization)
            and self._authorization.owns_receipt(
                self,
                receipt,
                content_digest,
            )
        )


TRINITY_STAGES = (
    "BOOT",
    "SELF_CHECK",
    "FRAME",
    "RETRIEVE",
    "COMPUTE",
    "JUDGE",
    "SUSPEND",
    "STOP",
    "RECOMPUTE",
    "ACT",
    "OBSERVE_RESULT",
    "UPDATE_MEMORY",
    "REFRAME",
)

_STAGE_TRANSITIONS = {
    "BOOT": {"SELF_CHECK"},
    "SELF_CHECK": {"FRAME", "STOP"},
    "FRAME": {"RETRIEVE", "STOP"},
    "RETRIEVE": {"COMPUTE", "SUSPEND", "STOP"},
    "COMPUTE": {"JUDGE", "RECOMPUTE", "SUSPEND", "STOP"},
    "JUDGE": {"SUSPEND", "STOP", "RECOMPUTE", "ACT", "UPDATE_MEMORY"},
    "SUSPEND": {"RECOMPUTE", "STOP", "REFRAME"},
    "STOP": set(),
    "RECOMPUTE": {"COMPUTE", "SUSPEND", "STOP"},
    "ACT": {"OBSERVE_RESULT", "STOP"},
    "OBSERVE_RESULT": {"UPDATE_MEMORY", "REFRAME", "STOP"},
    "UPDATE_MEMORY": {"REFRAME", "STOP"},
    "REFRAME": {"RETRIEVE", "COMPUTE", "STOP"},
}


@dataclass(slots=True)
class TrinityLifecycle:
    """Bounded state machine for one HDS-compute-memory control cycle."""

    stage: str = "BOOT"

    def __post_init__(self) -> None:
        normalized = str(self.stage).upper().strip()
        if normalized not in TRINITY_STAGES:
            raise ValueError(f"unknown initial Trinity stage: {self.stage}")
        self.stage = normalized

    def transition(self, target: str) -> str:
        normalized = str(target).upper().strip()
        if normalized not in TRINITY_STAGES:
            raise ValueError(f"unknown Trinity stage: {target}")
        if normalized not in _STAGE_TRANSITIONS.get(self.stage, set()):
            raise ValueError(f"invalid Trinity transition: {self.stage}->{normalized}")
        self.stage = normalized
        return self.stage


DEFAULT_INSTRUCTION_BODY_CONTRACT = InstructionBodyContract()

__all__ = [
    "COMPUTE_OPERATIONS",
    "DECISION_STATUSES",
    "DEFAULT_INSTRUCTION_BODY_CONTRACT",
    "AuthorityViolation",
    "EmissionDirective",
    "ComputeRequest",
    "ComputeResult",
    "HDSDecision",
    "InstructionBodyContract",
    "LAYER0_ROOTS",
    "MEMORY_LIFECYCLES",
    "MEMORY_OPERATIONS",
    "MemoryDirective",
    "PROTOCOL_VERSION",
    "TRINITY_STAGES",
    "TrinityLifecycle",
]
