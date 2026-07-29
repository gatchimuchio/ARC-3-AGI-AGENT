"""Level/episode overlays with rollback-first causal consolidation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from .generic_hds import GenericHDSJudgementSubject
from .generic_memory import (
    MemoryAuthorization,
    MemoryMutationProposal,
    MemoryMutationReceipt,
    SemanticMemory,
)
from .memory_consolidation import MemoryConsolidator
from .schema import digest_object

MEMORY_OVERLAY_VERSION = "arc3-memory-overlay-v1"


class AuthorizedMemoryExecutor(Protocol):
    def execute_memory(
        self,
        memory: SemanticMemory,
        proposal: MemoryMutationProposal,
        authorization: object,
    ) -> MemoryMutationReceipt: ...

    def execute_memory_batch(
        self,
        memory: SemanticMemory,
        proposals: tuple[MemoryMutationProposal, ...],
        authorizations: tuple[object, ...],
        *,
        idempotency_key: str,
    ) -> tuple[MemoryMutationReceipt, ...]: ...


@dataclass(frozen=True, slots=True)
class EpisodeOverlayReceipt:
    episode_handle_digest: str
    base_version: int
    final_version: int
    base_active_digest: str
    final_active_digest: str
    promoted: bool
    discarded: bool
    rollback_event_digest: str | None
    promotion_event_digest: str | None
    consolidation_plan_digest: str | None
    outcome: str


@dataclass(slots=True)
class MemoryOverlay:
    """Isolate game-local writes until later phases define consolidation."""

    memory: SemanticMemory
    hds: GenericHDSJudgementSubject
    executor: AuthorizedMemoryExecutor
    promotion_enabled: bool = False
    consolidator: MemoryConsolidator | None = None
    _episode_handle_digest: str | None = field(default=None, init=False)
    _episode_base_version: int | None = field(default=None, init=False)
    _episode_base_active_digest: str | None = field(
        default=None,
        init=False,
    )
    _level_handle_digest: str | None = field(default=None, init=False)
    _level_base_version: int | None = field(default=None, init=False)
    _level_base_active_digest: str | None = field(default=None, init=False)
    _episode_discarded_any: bool = field(default=False, init=False)
    _last_level_rollback_event_digest: str | None = field(
        default=None,
        init=False,
    )

    @property
    def episode_active(self) -> bool:
        return self._episode_handle_digest is not None

    @property
    def level_active(self) -> bool:
        return self._level_handle_digest is not None

    @staticmethod
    def _active_digest(memory: SemanticMemory) -> str:
        return "episode-active:" + digest_object(memory.view().active)

    def begin_episode(self, episode_handle_digest: str) -> None:
        if self.episode_active:
            raise RuntimeError("MEMORY_OVERLAY_EPISODE_ALREADY_ACTIVE")
        if self.promotion_enabled and self.consolidator is None:
            raise RuntimeError("MEMORY_CONSOLIDATOR_REQUIRED")
        if not isinstance(episode_handle_digest, str) or not episode_handle_digest:
            raise ValueError("MEMORY_OVERLAY_EPISODE_HANDLE_REQUIRED")
        self.memory.clear_working()
        self._episode_handle_digest = episode_handle_digest
        self._episode_base_version = self.memory.version
        self._episode_base_active_digest = self._active_digest(self.memory)
        self._episode_discarded_any = False
        self._last_level_rollback_event_digest = None

    def require_episode(self, episode_handle_digest: str) -> None:
        if (
            not self.episode_active
            or self._episode_handle_digest != episode_handle_digest
        ):
            raise PermissionError("MEMORY_OVERLAY_EPISODE_HANDLE_INVALID")

    def begin_level(self, level_handle_digest: str) -> None:
        if not self.episode_active:
            raise RuntimeError("MEMORY_OVERLAY_EPISODE_REQUIRED")
        if self.level_active:
            raise RuntimeError("MEMORY_OVERLAY_LEVEL_ALREADY_ACTIVE")
        if not isinstance(level_handle_digest, str) or not level_handle_digest:
            raise ValueError("MEMORY_OVERLAY_LEVEL_HANDLE_REQUIRED")
        self._level_handle_digest = level_handle_digest
        self._level_base_version = self.memory.version
        self._level_base_active_digest = self._active_digest(self.memory)

    def end_level(self, level_handle_digest: str, *, succeeded: bool) -> None:
        if self._level_handle_digest != level_handle_digest:
            raise PermissionError("MEMORY_OVERLAY_LEVEL_HANDLE_INVALID")
        base_version = self._level_base_version
        base_digest = self._level_base_active_digest
        if base_version is None or base_digest is None:
            raise RuntimeError("MEMORY_OVERLAY_LEVEL_BASE_MISSING")
        if not succeeded and self._active_digest(self.memory) != base_digest:
            proposal = self._rollback_proposal(
                target_id="level-overlay-discard",
                rollback_version=base_version,
                scope="level-overlay",
                reason="rollback failed level overlay to its safe base",
            )
            authorization = self.hds.authorize_overlay_discard(
                proposal,
                memory_version=self.memory.version,
            )
            receipt = self.executor.execute_memory(
                self.memory,
                proposal,
                authorization,
            )
            self._episode_discarded_any = True
            self._last_level_rollback_event_digest = receipt.event_digest
            if self._active_digest(self.memory) != base_digest:
                raise RuntimeError(
                    "MEMORY_OVERLAY_LEVEL_ROLLBACK_DIGEST_MISMATCH"
                )
        self.memory.clear_working()
        self._level_handle_digest = None
        self._level_base_version = None
        self._level_base_active_digest = None

    @staticmethod
    def _rollback_proposal(
        *,
        target_id: str,
        rollback_version: int,
        scope: str,
        reason: str,
    ) -> MemoryMutationProposal:
        return MemoryMutationProposal(
            operation="ROLLBACK",
            target_id=target_id,
            record=None,
            evidence=(f"{scope}-boundary-control-state",),
            counter_evidence=(),
            scope=(scope,),
            falsification_condition=(
                "the captured safe memory version is unavailable"
            ),
            reason=reason,
            rollback_version=rollback_version,
        )

    def _authorize_consolidation(
        self,
        proposals: Sequence[MemoryMutationProposal],
    ) -> tuple[MemoryAuthorization, ...]:
        memory_version = self.memory.version
        return tuple(
            self.hds.authorize_consolidation(
                proposal,
                memory_version=memory_version,
            )
            for proposal in proposals
        )

    def end_episode(
        self,
        episode_handle_digest: str,
        *,
        succeeded: bool,
        reason: str,
    ) -> EpisodeOverlayReceipt:
        """Rollback local writes, then atomically apply normalized promotion."""

        self.require_episode(episode_handle_digest)
        if self.level_active:
            raise RuntimeError("MEMORY_OVERLAY_LEVEL_STILL_ACTIVE")
        base_version = self._episode_base_version
        base_active_digest = self._episode_base_active_digest
        if base_version is None or base_active_digest is None:
            raise RuntimeError("MEMORY_OVERLAY_BASE_STATE_MISSING")

        episode_records = self.memory.view().active
        base_records = self.memory.snapshot(base_version)
        plan = (
            self.consolidator.plan(
                base_records=base_records,
                episode_records=episode_records,
                succeeded=succeeded,
            )
            if self.promotion_enabled and self.consolidator is not None
            else None
        )
        rollback_event_digest = self._last_level_rollback_event_digest
        current_active_digest = self._active_digest(self.memory)
        discarded = (
            self._episode_discarded_any
            or current_active_digest != base_active_digest
        )
        if current_active_digest != base_active_digest:
            proposal = self._rollback_proposal(
                target_id="episode-overlay-discard",
                rollback_version=base_version,
                scope="episode-overlay",
                reason=(
                    "rollback episode-local writes before optional "
                    "SESSION_GLOBAL consolidation"
                ),
            )
            authorization = self.hds.authorize_overlay_discard(
                proposal,
                memory_version=self.memory.version,
            )
            mutation_receipt = self.executor.execute_memory(
                self.memory,
                proposal,
                authorization,
            )
            rollback_event_digest = mutation_receipt.event_digest
        self.memory.clear_working()
        rolled_back_digest = self._active_digest(self.memory)
        if rolled_back_digest != base_active_digest:
            raise RuntimeError("MEMORY_OVERLAY_DISCARD_DIGEST_MISMATCH")
        promoted = False
        promotion_event_digest: str | None = None
        if (
            succeeded
            and self.promotion_enabled
            and plan is not None
            and plan.proposals
        ):
            authorizations = self._authorize_consolidation(plan.proposals)
            receipts = self.executor.execute_memory_batch(
                self.memory,
                plan.proposals,
                authorizations,
                idempotency_key="episode-consolidation:"
                + digest_object(
                    {
                        "episode": episode_handle_digest,
                        "plan": plan.plan_digest,
                        "base_version": base_version,
                    }
                ),
            )
            promoted = bool(receipts)
            if receipts:
                promotion_event_digest = receipts[-1].event_digest
        final_active_digest = self._active_digest(self.memory)
        overlay_receipt = EpisodeOverlayReceipt(
            episode_handle_digest=episode_handle_digest,
            base_version=base_version,
            final_version=self.memory.version,
            base_active_digest=base_active_digest,
            final_active_digest=final_active_digest,
            promoted=promoted,
            discarded=discarded,
            rollback_event_digest=rollback_event_digest,
            promotion_event_digest=promotion_event_digest,
            consolidation_plan_digest=(
                plan.plan_digest if plan is not None else None
            ),
            outcome="SUCCESS" if succeeded else "FAILURE",
        )
        self._episode_handle_digest = None
        self._episode_base_version = None
        self._episode_base_active_digest = None
        self._episode_discarded_any = False
        self._last_level_rollback_event_digest = None
        return overlay_receipt


__all__ = [
    "MEMORY_OVERLAY_VERSION",
    "AuthorizedMemoryExecutor",
    "EpisodeOverlayReceipt",
    "MemoryOverlay",
]
