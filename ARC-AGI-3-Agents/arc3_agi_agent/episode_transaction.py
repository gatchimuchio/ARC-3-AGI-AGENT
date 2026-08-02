"""Safe episode/level transaction facade for P17-B."""

from __future__ import annotations

from dataclasses import dataclass, field

from .control_state import ControlState
from .generic_memory import SemanticMemory
from .memory_overlay import EpisodeOverlayReceipt, MemoryOverlay
from .schema import digest_object

EPISODE_TRANSACTION_VERSION = "arc3-episode-transaction-v1"
EPISODE_TRANSACTION_STATES = frozenset(
    {"ACTIVE", "COMMITTED_LOCAL", "ROLLED_BACK", "FAILED_CLOSED"}
)


def _active_digest(memory: SemanticMemory) -> str:
    return "episode-active:" + digest_object(memory.view().active)


@dataclass(slots=True)
class EpisodeTransaction:
    """Bind one opaque handle to a rollback-verified memory base."""

    memory: SemanticMemory = field(repr=False)
    control: ControlState = field(repr=False)
    overlay: MemoryOverlay = field(repr=False)
    episode_handle_digest: str = field(
        repr=False,
        metadata={"serialize": False},
    )
    level_handle_digest: str = field(
        repr=False,
        metadata={"serialize": False},
    )
    base_version: int
    base_session_global_digest: str
    consolidation_enabled: bool = False
    state: str = field(default="ACTIVE", init=False)
    level_transition_ordinal: int = field(default=0, init=False)

    @staticmethod
    def _level_handle(
        *,
        episode_handle_digest: str,
        previous_level_handle_digest: str,
        transition_ordinal: int,
        boundary_ordinal: int,
        memory: SemanticMemory,
    ) -> str:
        return "level-handle:" + digest_object(
            {
                "episode_handle_digest": episode_handle_digest,
                "previous_level_handle_digest": previous_level_handle_digest,
                "transition_ordinal": transition_ordinal,
                "boundary_ordinal": boundary_ordinal,
                "base_version": memory.version,
                "base_active_digest": _active_digest(memory),
            }
        )

    @classmethod
    def begin(
        cls,
        *,
        memory: SemanticMemory,
        control: ControlState,
        overlay: MemoryOverlay,
        episode_handle_digest: str,
        action_budget: int,
        time_budget_seconds: float | None,
    ) -> EpisodeTransaction:
        control.begin_episode(
            episode_handle_digest,
            action_budget=action_budget,
            time_budget_seconds=time_budget_seconds,
        )
        try:
            overlay.begin_episode(episode_handle_digest)
        except Exception:
            control.end_episode(episode_handle_digest)
            raise
        level_handle_digest = cls._level_handle(
            episode_handle_digest=episode_handle_digest,
            previous_level_handle_digest="",
            transition_ordinal=0,
            boundary_ordinal=0,
            memory=memory,
        )
        try:
            control.begin_level(level_handle_digest)
            overlay.begin_level(level_handle_digest)
        except Exception:
            if control.current_level_handle_digest == level_handle_digest:
                control.end_level(level_handle_digest)
            control.end_episode(episode_handle_digest)
            raise
        return cls(
            memory=memory,
            control=control,
            overlay=overlay,
            episode_handle_digest=episode_handle_digest,
            level_handle_digest=level_handle_digest,
            base_version=memory.version,
            base_session_global_digest=_active_digest(memory),
            consolidation_enabled=overlay.promotion_enabled,
        )

    def require_active(self, episode_handle_digest: str) -> None:
        if (
            self.state != "ACTIVE"
            or self.episode_handle_digest != episode_handle_digest
        ):
            raise PermissionError("EPISODE_TRANSACTION_HANDLE_INVALID")
        self.control.require_episode(episode_handle_digest)
        self.overlay.require_episode(episode_handle_digest)

    def transition_level(
        self,
        *,
        episode_handle_digest: str,
        preserve_causal_memory: bool,
        boundary_ordinal: int,
    ) -> tuple[str, str]:
        """Close one level-attempt scope and open the next opaque scope.

        Active semantic records are HDS-authorized, post-outcome causal
        evidence.  A failed environment attempt may therefore preserve them
        for the retry while working memory is still cleared at the boundary.
        Episode close remains the authority that prevents failed-game leakage.
        """

        self.require_active(episode_handle_digest)
        if (
            isinstance(boundary_ordinal, bool)
            or not isinstance(boundary_ordinal, int)
            or boundary_ordinal < 0
        ):
            raise ValueError("EPISODE_TRANSACTION_LEVEL_BOUNDARY_INVALID")
        closed_handle = self.level_handle_digest
        self.overlay.end_level(
            closed_handle,
            succeeded=preserve_causal_memory,
        )
        self.control.end_level(closed_handle)
        self.level_transition_ordinal += 1
        next_handle = self._level_handle(
            episode_handle_digest=episode_handle_digest,
            previous_level_handle_digest=closed_handle,
            transition_ordinal=self.level_transition_ordinal,
            boundary_ordinal=boundary_ordinal,
            memory=self.memory,
        )
        try:
            self.control.begin_level(next_handle)
            self.overlay.begin_level(next_handle)
        except Exception:
            if self.control.current_level_handle_digest == next_handle:
                self.control.end_level(next_handle)
            self.state = "FAILED_CLOSED"
            raise
        self.level_handle_digest = next_handle
        return closed_handle, next_handle

    def close(
        self,
        *,
        episode_handle_digest: str,
        succeeded: bool,
        reason: str,
    ) -> EpisodeOverlayReceipt:
        self.require_active(episode_handle_digest)
        if not reason:
            raise ValueError("EPISODE_TRANSACTION_REASON_REQUIRED")
        self.overlay.end_level(
            self.level_handle_digest,
            succeeded=succeeded,
        )
        self.control.end_level(self.level_handle_digest)
        try:
            receipt = self.overlay.end_episode(
                episode_handle_digest,
                succeeded=succeeded,
                reason=reason,
            )
        except Exception:
            self.state = "FAILED_CLOSED"
            self.control.end_episode(episode_handle_digest)
            raise
        self.control.end_episode(episode_handle_digest)
        final_digest = _active_digest(self.memory)
        if not succeeded and (
            receipt.final_active_digest != self.base_session_global_digest
            or final_digest != self.base_session_global_digest
            or receipt.promoted
        ):
            self.state = "FAILED_CLOSED"
            raise RuntimeError("EPISODE_TRANSACTION_GLOBAL_DIGEST_LEAK")
        if (
            succeeded
            and not self.consolidation_enabled
            and (
                receipt.final_active_digest != self.base_session_global_digest
                or final_digest != self.base_session_global_digest
                or receipt.promoted
            )
        ):
            self.state = "FAILED_CLOSED"
            raise RuntimeError("EPISODE_TRANSACTION_GLOBAL_DIGEST_LEAK")
        if (
            succeeded
            and self.consolidation_enabled
            and (receipt.final_active_digest != final_digest)
        ):
            self.state = "FAILED_CLOSED"
            raise RuntimeError("EPISODE_TRANSACTION_PROMOTION_DIGEST_MISMATCH")
        self.state = "COMMITTED_LOCAL" if succeeded else "ROLLED_BACK"
        return receipt


__all__ = [
    "EPISODE_TRANSACTION_STATES",
    "EPISODE_TRANSACTION_VERSION",
    "EpisodeTransaction",
]
