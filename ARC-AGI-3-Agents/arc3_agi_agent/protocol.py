"""Executable authority contracts for the ARC-3 restart foundation.

Adapted from the legacy repository's ``agent/trinity_protocol.py`` at
commit ``0970dc6a56addf2f2ca494efbf80ef919e2e3a12``. This module is an
isolated protocol seam. It does not implement a planner, a policy, persistent
memory, or an environment adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

PROTOCOL_VERSION = "arc3-restart-protocol-v1"

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
        if not self.version.strip():
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
    contract_version: str = PROTOCOL_VERSION
    feature_tokens: tuple[str, ...] = ()
    authority: str = "hds-only"

    def validate(self, contract: InstructionBodyContract) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.command_id.strip():
            failures.append("COMMAND_ID_MISSING")
        if self.operation not in COMPUTE_OPERATIONS:
            failures.append("COMPUTE_OPERATION_INVALID")
        if not self.observation_signature.strip():
            failures.append("OBSERVATION_SIGNATURE_MISSING")
        if self.contract_version != contract.version:
            failures.append("CONTRACT_VERSION_MISMATCH")
        if self.authority != "hds-only":
            failures.append("COMPUTE_REQUEST_AUTHORITY_INVALID")
        if any(not str(token).strip() for token in self.feature_tokens):
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
        if self.status not in {"COMPUTED", "EXECUTED", "REJECTED"}:
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

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.command_id.strip():
            failures.append("HDS_COMMAND_ID_MISSING")
        if not self.decision_id.strip():
            failures.append("HDS_DECISION_ID_MISSING")
        if self.status not in DECISION_STATUSES:
            failures.append("HDS_DECISION_STATUS_INVALID")
        if self.authority != "hds-only":
            failures.append("HDS_DECISION_AUTHORITY_INVALID")
        if any(not str(code).strip() for code in self.reason_codes):
            failures.append("HDS_REASON_CODE_EMPTY")
        if self.allow_external_emit and self.status not in {"PASS", "EMIT", "PROBE"}:
            failures.append("EXTERNAL_EMIT_NOT_COMPATIBLE_WITH_STATUS")
        if self.allow_memory_write and self.status in {"REJECT", "STOP"}:
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
    authority: str = "hds-only"

    def validate(self, decision: HDSDecision) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.command_id.strip():
            failures.append("MEMORY_COMMAND_ID_MISSING")
        if self.command_id != decision.command_id:
            failures.append("MEMORY_COMMAND_MISMATCH")
        if self.decision_id != decision.decision_id:
            failures.append("MEMORY_DECISION_MISMATCH")
        if self.operation not in MEMORY_OPERATIONS:
            failures.append("MEMORY_OPERATION_INVALID")
        if not self.target.strip():
            failures.append("MEMORY_TARGET_MISSING")
        if self.lifecycle not in MEMORY_LIFECYCLES:
            failures.append("MEMORY_LIFECYCLE_INVALID")
        if not self.evidence_signature.strip():
            failures.append("MEMORY_EVIDENCE_MISSING")
        if self.authority != "hds-only":
            failures.append("MEMORY_DIRECTIVE_AUTHORITY_INVALID")
        if not decision.allow_memory_write:
            failures.append("MEMORY_WRITE_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class EmissionDirective:
    """HDS-issued external action authorization."""

    command_id: str
    decision_id: str
    action_id: int
    reasoning_digest: str
    authority: str = "hds-only"

    def validate(self, decision: HDSDecision) -> tuple[str, ...]:
        failures: list[str] = []
        if self.command_id != decision.command_id:
            failures.append("EMISSION_COMMAND_MISMATCH")
        if self.decision_id != decision.decision_id:
            failures.append("EMISSION_DECISION_MISMATCH")
        if self.action_id < 1 or self.action_id > 7:
            failures.append("EMISSION_ACTION_INVALID")
        if not self.reasoning_digest.strip():
            failures.append("EMISSION_REASONING_DIGEST_MISSING")
        if self.authority != "hds-only":
            failures.append("EMISSION_DIRECTIVE_AUTHORITY_INVALID")
        if not decision.allow_external_emit:
            failures.append("EXTERNAL_EMIT_NOT_AUTHORIZED")
        return tuple(sorted(set(failures)))


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
    "STOP": {"REFRAME"},
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
