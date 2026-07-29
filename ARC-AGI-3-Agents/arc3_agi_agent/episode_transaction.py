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
        level_handle_digest = "level-handle:" + digest_object(
            {
                "episode_control_scope": "ACTIVE",
                "base_version": memory.version,
                "base_active_digest": _active_digest(memory),
            }
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
            receipt.final_active_digest
            != self.base_session_global_digest
            or final_digest != self.base_session_global_digest
            or receipt.promoted
        ):
            self.state = "FAILED_CLOSED"
            raise RuntimeError("EPISODE_TRANSACTION_GLOBAL_DIGEST_LEAK")
        if succeeded and not self.consolidation_enabled and (
            receipt.final_active_digest
            != self.base_session_global_digest
            or final_digest != self.base_session_global_digest
            or receipt.promoted
        ):
            self.state = "FAILED_CLOSED"
            raise RuntimeError("EPISODE_TRANSACTION_GLOBAL_DIGEST_LEAK")
        if succeeded and self.consolidation_enabled and (
            receipt.final_active_digest != final_digest
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
