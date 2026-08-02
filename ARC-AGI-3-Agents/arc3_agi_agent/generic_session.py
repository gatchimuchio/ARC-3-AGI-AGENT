"""Scorecard/run-scoped cognitive subject container for GenericAGIRuntime."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from .authority_state import AuthorityState
from .control_state import ControlState
from .episode_transaction import EpisodeTransaction
from .experience_ledger import EventSourcedExperienceLedger
from .generic_compute import GenericComputeSubject, GenericInstructionBody
from .generic_hds import (
    ActionAuthorizationExecutor,
    ControlRollbackAuthorizationExecutor,
    GenericHDSJudgementSubject,
    HDSConfiguration,
    RollbackAuthorizationExecutor,
)
from .generic_memory import (
    ActionHistoryAuthorization,
    ActionHistoryEvent,
    BoundedActionEffectMemory,
    MemoryMutationProposal,
    MemoryMutationReceipt,
    SemanticMemory,
    SemanticRecord,
    semantic_record,
)
from .generic_types import ActionEffectRecord
from .identity_boundary import IdentityBoundary
from .memory_backend import InMemoryBackend, MemoryBackend
from .memory_consolidation import MemoryConsolidator
from .memory_overlay import EpisodeOverlayReceipt, MemoryOverlay
from .p_ir import compatibility_p_ir_program, p_ir_program_logical_digest
from .p_ir_types import PIRProgram
from .runtime_identity import RuntimeIdentity, build_runtime_identity
from .schema import digest_object

GENERIC_SESSION_VERSION = "arc3-cognitive-session-v1"
RUNTIME_MODES = frozenset({"DEVELOPMENT", "VALIDATION", "LOCKED_FINAL", "COMPETITION"})


@dataclass(frozen=True, slots=True)
class ResourceContract:
    action_budget_per_episode: int = 256
    max_memory_updates_per_cycle: int = 8
    time_budget_seconds: float | None = None

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            isinstance(self.action_budget_per_episode, bool)
            or not isinstance(self.action_budget_per_episode, int)
            or not 1 <= self.action_budget_per_episode <= 100_000
        ):
            failures.append("RESOURCE_ACTION_BUDGET_INVALID")
        if (
            isinstance(self.max_memory_updates_per_cycle, bool)
            or not isinstance(self.max_memory_updates_per_cycle, int)
            or not 1 <= self.max_memory_updates_per_cycle <= 64
        ):
            failures.append("RESOURCE_MEMORY_UPDATE_BUDGET_INVALID")
        if self.time_budget_seconds is not None and (
            isinstance(self.time_budget_seconds, bool)
            or not isinstance(self.time_budget_seconds, (int, float))
            or self.time_budget_seconds <= 0
        ):
            failures.append("RESOURCE_TIME_BUDGET_INVALID")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
class FrozenPReference:
    body: GenericInstructionBody = field(repr=False)
    logical_digest: str
    program: PIRProgram = field(repr=False)
    program_logical_digest: str

    def require_unchanged(self) -> None:
        if self.body.digest() != self.logical_digest:
            raise RuntimeError("COGNITIVE_SESSION_P_REFERENCE_CHANGED")
        if p_ir_program_logical_digest(self.program) != self.program_logical_digest:
            raise RuntimeError("COGNITIVE_SESSION_P_IR_REFERENCE_CHANGED")


@dataclass(frozen=True, slots=True)
class EpisodeHandle:
    handle_digest: str = field(metadata={"serialize": False})
    session_lineage_digest: str = field(metadata={"serialize": False})
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _evidence_nonce: str = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


class ExperienceLedger(Protocol):
    """Append-only raw experience interface owned by the cognitive session."""

    def append(
        self,
        event_type: str,
        payload: Mapping[str, object],
    ) -> str: ...


@dataclass(slots=True)
class GenericSideEffectExecutor:
    """Mechanical executor wired to the session-owned AuthorityState."""

    authority_state: AuthorityState = field(repr=False)
    action_executor: ActionAuthorizationExecutor = field(init=False)
    rollback_executor: RollbackAuthorizationExecutor = field(init=False)
    control_rollback_executor: ControlRollbackAuthorizationExecutor = field(init=False)

    def __post_init__(self) -> None:
        self.action_executor = ActionAuthorizationExecutor(self.authority_state)
        self.rollback_executor = RollbackAuthorizationExecutor(self.authority_state)
        self.control_rollback_executor = ControlRollbackAuthorizationExecutor(
            self.authority_state
        )

    @property
    def authority_token(self) -> object:
        return self.authority_state.live_token

    def execute_memory(
        self,
        memory: SemanticMemory,
        proposal: MemoryMutationProposal,
        authorization: object,
    ) -> MemoryMutationReceipt:
        from .generic_memory import MemoryAuthorization

        if not isinstance(authorization, MemoryAuthorization):
            raise TypeError("GENERIC_MEMORY_AUTHORIZATION_REQUIRED")
        return memory.apply_authorized(proposal, authorization)

    def execute_memory_batch(
        self,
        memory: SemanticMemory,
        proposals: tuple[MemoryMutationProposal, ...],
        authorizations: tuple[object, ...],
        *,
        idempotency_key: str,
    ) -> tuple[MemoryMutationReceipt, ...]:
        from .generic_memory import MemoryAuthorization

        if not all(isinstance(item, MemoryAuthorization) for item in authorizations):
            raise TypeError("GENERIC_MEMORY_AUTHORIZATION_REQUIRED")
        return memory.apply_authorized_batch(
            proposals,
            authorizations,  # type: ignore[arg-type]
            idempotency_key=idempotency_key,
            mandatory=True,
        )

    def execute_action_history(
        self,
        memory: BoundedActionEffectMemory,
        record: ActionEffectRecord,
        authorization: ActionHistoryAuthorization,
    ) -> ActionHistoryEvent:
        return memory.append_authorized(record, authorization)


@dataclass(slots=True)
class CognitiveSession:
    """One cognitive subject lineage for exactly one scorecard/run."""

    session_id: str
    mode: str
    runtime_identity: RuntimeIdentity
    authority: AuthorityState
    control: ControlState
    memory: SemanticMemory
    action_history: BoundedActionEffectMemory
    ledger: ExperienceLedger
    p_bundle: FrozenPReference
    hds_config: HDSConfiguration
    resource_contract: ResourceContract
    identity_boundary: IdentityBoundary
    compute: GenericComputeSubject
    hds: GenericHDSJudgementSubject
    executor: GenericSideEffectExecutor
    overlay: MemoryOverlay
    lineage_digest: str
    _active_episode: EpisodeHandle | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _active_transaction: EpisodeTransaction | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _episode_ordinal: int = field(
        default=0,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _poisoned_reason: str | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _level_progress: int | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )

    @property
    def instruction_body(self) -> GenericInstructionBody:
        self.p_bundle.require_unchanged()
        return self.p_bundle.body

    @property
    def p_ir_program(self) -> PIRProgram:
        self.p_bundle.require_unchanged()
        return self.p_bundle.program

    @property
    def active_episode(self) -> EpisodeHandle | None:
        return self._active_episode

    @property
    def cross_game_semantic_promotion_enabled(self) -> bool:
        return self.overlay.promotion_enabled

    def state_owner_violations(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.authority.session_id != self.session_id:
            failures.append("AUTHORITY_OWNER_MISMATCH")
        if self.control.session_id != self.session_id:
            failures.append("CONTROL_OWNER_MISMATCH")
        if self.memory.authority_state is not self.authority:
            failures.append("MEMORY_AUTHORITY_OWNER_MISMATCH")
        if self.action_history.authority_state is not self.authority:
            failures.append("ACTION_HISTORY_AUTHORITY_OWNER_MISMATCH")
        if self.compute.authority_state is not self.authority:
            failures.append("COMPUTE_AUTHORITY_OWNER_MISMATCH")
        if self.hds.authority_state is not self.authority:
            failures.append("HDS_AUTHORITY_OWNER_MISMATCH")
        if self.hds.control_state is not self.control:
            failures.append("HDS_CONTROL_OWNER_MISMATCH")
        if self.executor.authority_state is not self.authority:
            failures.append("EXECUTOR_AUTHORITY_OWNER_MISMATCH")
        if self.overlay.memory is not self.memory:
            failures.append("OVERLAY_MEMORY_OWNER_MISMATCH")
        if self.overlay.hds is not self.hds:
            failures.append("OVERLAY_HDS_OWNER_MISMATCH")
        if self.overlay.executor is not self.executor:
            failures.append("OVERLAY_EXECUTOR_OWNER_MISMATCH")
        return tuple(sorted(set(failures)))

    def _require_handle(self, handle: EpisodeHandle) -> None:
        self.authority.require_live_token(
            handle._authority_token,
            error="COGNITIVE_SESSION_EPISODE_AUTHORITY_INVALID",
        )
        if (
            handle.session_lineage_digest != self.lineage_digest
            or self._active_episode != handle
        ):
            raise PermissionError("COGNITIVE_SESSION_EPISODE_HANDLE_INVALID")
        if self._active_transaction is None:
            raise PermissionError("COGNITIVE_SESSION_TRANSACTION_MISSING")
        self._active_transaction.require_active(handle.handle_digest)
        self.control.require_episode(handle.handle_digest)
        self.overlay.require_episode(handle.handle_digest)

    def begin_episode(self) -> EpisodeHandle:
        if self._poisoned_reason is not None:
            raise RuntimeError("COGNITIVE_SESSION_POISONED:" + self._poisoned_reason)
        if self._active_episode is not None:
            raise RuntimeError("COGNITIVE_SESSION_EPISODE_ALREADY_ACTIVE")
        self.p_bundle.require_unchanged()
        nonce = secrets.token_hex(24)
        handle = EpisodeHandle(
            handle_digest="episode-handle:"
            + digest_object(
                {
                    "session_lineage": self.lineage_digest,
                    "nonce": nonce,
                    "ordinal": self._episode_ordinal,
                }
            ),
            session_lineage_digest=self.lineage_digest,
            _authority_token=self.authority.live_token,
            _evidence_nonce="evidence-episode:" + secrets.token_hex(24),
        )
        self._episode_ordinal += 1
        transaction = EpisodeTransaction.begin(
            memory=self.memory,
            control=self.control,
            overlay=self.overlay,
            episode_handle_digest=handle.handle_digest,
            action_budget=self.resource_contract.action_budget_per_episode,
            time_budget_seconds=self.resource_contract.time_budget_seconds,
        )
        self.action_history.begin_episode()
        self._active_episode = handle
        self._active_transaction = transaction
        self._level_progress = None
        self.ledger.append(
            "EPISODE_BEGIN",
            {
                "episode_handle_digest": handle.handle_digest,
                "session_lineage_digest": self.lineage_digest,
                "memory_version": self.memory.version,
            },
        )
        return handle

    def require_episode(self, handle: EpisodeHandle) -> None:
        self._require_handle(handle)

    def evidence_nonce(self, handle: EpisodeHandle) -> str:
        """Return the non-search independence nonce for the active episode."""

        self._require_handle(handle)
        return handle._evidence_nonce

    def bind_level_scope(
        self,
        handle: EpisodeHandle,
        *,
        progress_count: int,
        observation_digest: str,
    ) -> str:
        """Bind the initial explicit level-local M scope to rendered state."""

        self._require_handle(handle)
        if self._level_progress is not None:
            raise RuntimeError("COGNITIVE_SESSION_LEVEL_SCOPE_ALREADY_BOUND")
        if (
            isinstance(progress_count, bool)
            or not isinstance(progress_count, int)
            or progress_count < 0
        ):
            raise ValueError("COGNITIVE_SESSION_LEVEL_PROGRESS_INVALID")
        if not isinstance(observation_digest, str) or not observation_digest:
            raise ValueError("COGNITIVE_SESSION_LEVEL_OBSERVATION_REQUIRED")
        transaction = self._active_transaction
        if transaction is None:
            raise RuntimeError("COGNITIVE_SESSION_TRANSACTION_MISSING")
        self._level_progress = progress_count
        return self.ledger.append(
            "LEVEL_SCOPE_BEGIN",
            {
                "episode_handle_digest": handle.handle_digest,
                "level_handle_digest": transaction.level_handle_digest,
                "progress_count": progress_count,
                "observation_digest": observation_digest,
                "memory_version": self.memory.version,
            },
        )

    def record_level_transition(
        self,
        handle: EpisodeHandle,
        *,
        before_progress: int,
        after_progress: int,
        observation_digest: str,
        cycle_index: int,
    ) -> str:
        """Close successful level M and open the next game-local level M."""

        self._require_handle(handle)
        if (
            self._level_progress != before_progress
            or isinstance(after_progress, bool)
            or not isinstance(after_progress, int)
            or after_progress <= before_progress
        ):
            raise ValueError("COGNITIVE_SESSION_LEVEL_TRANSITION_INVALID")
        if (
            isinstance(cycle_index, bool)
            or not isinstance(cycle_index, int)
            or cycle_index < 0
        ):
            raise ValueError("COGNITIVE_SESSION_LEVEL_CYCLE_INVALID")
        if not isinstance(observation_digest, str) or not observation_digest:
            raise ValueError("COGNITIVE_SESSION_LEVEL_OBSERVATION_REQUIRED")
        transaction = self._active_transaction
        if transaction is None:
            raise RuntimeError("COGNITIVE_SESSION_TRANSACTION_MISSING")
        closed_handle, opened_handle = transaction.transition_level(
            episode_handle_digest=handle.handle_digest,
            preserve_causal_memory=True,
            boundary_ordinal=after_progress,
        )
        self._level_progress = after_progress
        return self.ledger.append(
            "LEVEL_SCOPE_TRANSITION",
            {
                "episode_handle_digest": handle.handle_digest,
                "closed_level_handle_digest": closed_handle,
                "opened_level_handle_digest": opened_handle,
                "before_progress": before_progress,
                "after_progress": after_progress,
                "progress_delta": after_progress - before_progress,
                "observation_digest": observation_digest,
                "cycle_index": cycle_index,
                "memory_version": self.memory.version,
            },
        )

    def record_level_reset(
        self,
        handle: EpisodeHandle,
        *,
        progress_count: int,
        observation_digest: str,
        cycle_index: int,
        reason: str,
    ) -> str:
        """Rotate retry scope while retaining HDS-attributed causal evidence.

        A GAME_OVER invalidates the attempted environment state, not the
        observed action/effect evidence.  Working memory is cleared by the
        level boundary, while causal semantic M remains game-local and is
        discarded at episode close if the game never succeeds.
        """

        self._require_handle(handle)
        if self._level_progress != progress_count:
            raise ValueError("COGNITIVE_SESSION_LEVEL_RESET_PROGRESS_INVALID")
        if (
            isinstance(cycle_index, bool)
            or not isinstance(cycle_index, int)
            or cycle_index < 0
        ):
            raise ValueError("COGNITIVE_SESSION_LEVEL_CYCLE_INVALID")
        if not isinstance(observation_digest, str) or not observation_digest:
            raise ValueError("COGNITIVE_SESSION_LEVEL_OBSERVATION_REQUIRED")
        if not isinstance(reason, str) or not reason:
            raise ValueError("COGNITIVE_SESSION_LEVEL_RESET_REASON_REQUIRED")
        transaction = self._active_transaction
        if transaction is None:
            raise RuntimeError("COGNITIVE_SESSION_TRANSACTION_MISSING")
        closed_handle, opened_handle = transaction.transition_level(
            episode_handle_digest=handle.handle_digest,
            preserve_causal_memory=True,
            boundary_ordinal=progress_count,
        )
        return self.ledger.append(
            "LEVEL_SCOPE_RESET",
            {
                "episode_handle_digest": handle.handle_digest,
                "closed_level_handle_digest": closed_handle,
                "opened_level_handle_digest": opened_handle,
                "progress_count": progress_count,
                "observation_digest": observation_digest,
                "cycle_index": cycle_index,
                "reason_digest": digest_object(reason),
                "attempt_succeeded": False,
                "causal_memory_preserved": True,
                "working_memory_cleared": True,
                "memory_version": self.memory.version,
            },
        )

    def end_episode(
        self,
        handle: EpisodeHandle,
        *,
        succeeded: bool,
        reason: str,
    ) -> EpisodeOverlayReceipt:
        self._require_handle(handle)
        if not isinstance(reason, str) or not reason:
            raise ValueError("COGNITIVE_SESSION_EPISODE_REASON_REQUIRED")
        transaction = self._active_transaction
        if transaction is None:
            raise RuntimeError("COGNITIVE_SESSION_TRANSACTION_MISSING")
        try:
            receipt = transaction.close(
                episode_handle_digest=handle.handle_digest,
                succeeded=succeeded,
                reason=reason,
            )
        except Exception as error:
            self._poisoned_reason = type(error).__name__
            self.action_history.end_episode()
            self._active_episode = None
            self._active_transaction = None
            self._level_progress = None
            raise
        self.action_history.end_episode()
        self._active_episode = None
        self._active_transaction = None
        self._level_progress = None
        self.ledger.append(
            "EPISODE_END",
            {
                "episode_handle_digest": handle.handle_digest,
                "outcome": receipt.outcome,
                "reason_digest": digest_object(reason),
                "memory_version": receipt.final_version,
                "promoted": receipt.promoted,
                "discarded": receipt.discarded,
            },
        )
        return receipt


def create_cognitive_session(
    *,
    p_bundle: GenericInstructionBody,
    p_ir_program: PIRProgram | None = None,
    mode: str = "VALIDATION",
    hds_configuration: HDSConfiguration | None = None,
    initial_memory_records: tuple[SemanticRecord, ...] = (),
    resource_contract: ResourceContract | None = None,
    runtime_identity: RuntimeIdentity | None = None,
    ledger: ExperienceLedger | None = None,
    memory_backend: MemoryBackend | None = None,
    enable_cross_game_promotion: bool = True,
) -> CognitiveSession:
    """Create all mutable subjects once, before any per-game runtime exists."""

    if mode not in RUNTIME_MODES:
        raise ValueError("COGNITIVE_SESSION_MODE_INVALID")
    if not isinstance(enable_cross_game_promotion, bool):
        raise TypeError("COGNITIVE_SESSION_PROMOTION_FLAG_INVALID")
    body_failures = p_bundle.validate()
    if body_failures:
        raise ValueError(";".join(body_failures))
    selected_program = p_ir_program or compatibility_p_ir_program()
    selected_program_digest = p_ir_program_logical_digest(selected_program)
    selected_resources = resource_contract or ResourceContract()
    resource_failures = selected_resources.validate()
    if resource_failures:
        raise ValueError(";".join(resource_failures))
    selected_hds = hds_configuration or HDSConfiguration(
        resource_budget=selected_resources.action_budget_per_episode,
        stop_after_no_progress=selected_resources.action_budget_per_episode,
    )
    hds_failures = selected_hds.validate()
    if hds_failures:
        raise ValueError(";".join(hds_failures))
    selected_identity = runtime_identity or build_runtime_identity(
        p_bundle=p_bundle,
        p_ir_program=selected_program,
        hds_configuration=selected_hds,
        initial_memory_records=initial_memory_records,
    )
    identity_failures = selected_identity.validate()
    if identity_failures:
        raise ValueError(";".join(identity_failures))

    session_id = "cognitive-session:" + secrets.token_hex(24)
    lineage_digest = "cognitive-lineage:" + digest_object(
        {
            "session_id": session_id,
            "runtime_identity": selected_identity.digest(),
        }
    )
    authority = AuthorityState(session_id)
    control = ControlState(session_id)
    memory = SemanticMemory(
        authority,
        backend=memory_backend or InMemoryBackend(),
    )
    action_history = BoundedActionEffectMemory(authority)
    memory.seed_sealed(
        (
            semantic_record(
                memory_id="constitution:authority",
                kind="PURPOSE_BOUNDARY",
                statement=(
                    "HDS alone commits actions and active-memory updates; "
                    "models are not the world."
                ),
                semantic_tokens=(
                    "boundary:authority",
                    "boundary:reversible",
                    "goal:progress",
                ),
                evidence=("AGI_Trinity_Blueprint_v0_1",),
                falsification_condition=(
                    "a non-HDS path can commit an action or active-memory write"
                ),
                state="SEALED",
            ),
        )
    )
    memory.seed_active(initial_memory_records)
    compute = GenericComputeSubject(authority)
    hds = GenericHDSJudgementSubject(
        authority_state=authority,
        control_state=control,
        configuration=selected_hds,
        run_id=lineage_digest,
    )
    executor = GenericSideEffectExecutor(authority)
    overlay = MemoryOverlay(
        memory=memory,
        hds=hds,
        executor=executor,
        promotion_enabled=enable_cross_game_promotion,
        consolidator=MemoryConsolidator(
            policy=selected_hds.evidence_policy(),
        ),
    )
    session = CognitiveSession(
        session_id=session_id,
        mode=mode,
        runtime_identity=selected_identity,
        authority=authority,
        control=control,
        memory=memory,
        action_history=action_history,
        ledger=ledger or EventSourcedExperienceLedger(),
        p_bundle=FrozenPReference(
            body=p_bundle,
            logical_digest=p_bundle.digest(),
            program=selected_program,
            program_logical_digest=selected_program_digest,
        ),
        hds_config=selected_hds,
        resource_contract=selected_resources,
        identity_boundary=IdentityBoundary(),
        compute=compute,
        hds=hds,
        executor=executor,
        overlay=overlay,
        lineage_digest=lineage_digest,
    )
    violations = session.state_owner_violations()
    if violations:
        raise RuntimeError(";".join(violations))
    return session


__all__ = [
    "GENERIC_SESSION_VERSION",
    "RUNTIME_MODES",
    "CognitiveSession",
    "EpisodeHandle",
    "ExperienceLedger",
    "FrozenPReference",
    "GenericSideEffectExecutor",
    "ResourceContract",
    "create_cognitive_session",
]
