"""Mutable execution-control state for one cognitive session."""

from __future__ import annotations

from dataclasses import dataclass, field

CONTROL_STATE_VERSION = "arc3-control-state-v1"
DEFAULT_NEXT_QUESTION = (
    "What current relation can safely advance the delegated goal?"
)


@dataclass(slots=True)
class ControlState:
    """Own cycle, budget, progress, and episode-local compatibility state."""

    session_id: str
    legacy_structural_compatibility: bool = True
    cycle_index: int = field(default=0, init=False)
    remaining_action_budget: int = field(default=0, init=False)
    remaining_time_seconds: float | None = field(default=None, init=False)
    no_progress_count: int = field(default=0, init=False)
    next_question: str = field(default=DEFAULT_NEXT_QUESTION, init=False)
    pending_probe: str = field(default="", init=False)
    stop_boundary: str = field(default="", init=False)
    current_episode_handle_digest: str | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    current_level_handle_digest: str | None = field(
        default=None,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("CONTROL_SESSION_ID_REQUIRED")

    @property
    def episode_active(self) -> bool:
        return self.current_episode_handle_digest is not None

    def begin_episode(
        self,
        episode_handle_digest: str,
        *,
        action_budget: int,
        time_budget_seconds: float | None,
    ) -> None:
        if self.episode_active:
            raise RuntimeError("CONTROL_EPISODE_ALREADY_ACTIVE")
        if not isinstance(episode_handle_digest, str) or not episode_handle_digest:
            raise ValueError("CONTROL_EPISODE_HANDLE_REQUIRED")
        if (
            isinstance(action_budget, bool)
            or not isinstance(action_budget, int)
            or action_budget <= 0
        ):
            raise ValueError("CONTROL_ACTION_BUDGET_INVALID")
        if (
            time_budget_seconds is not None
            and (
                isinstance(time_budget_seconds, bool)
                or not isinstance(time_budget_seconds, (int, float))
                or time_budget_seconds <= 0
            )
        ):
            raise ValueError("CONTROL_TIME_BUDGET_INVALID")
        self.current_episode_handle_digest = episode_handle_digest
        self.current_level_handle_digest = None
        self.cycle_index = 0
        self.remaining_action_budget = action_budget
        self.remaining_time_seconds = (
            float(time_budget_seconds)
            if time_budget_seconds is not None
            else None
        )
        self.no_progress_count = 0
        self.next_question = DEFAULT_NEXT_QUESTION
        self.pending_probe = ""
        self.stop_boundary = ""

    def require_episode(self, episode_handle_digest: str) -> None:
        if (
            not self.episode_active
            or self.current_episode_handle_digest != episode_handle_digest
        ):
            raise PermissionError("CONTROL_EPISODE_HANDLE_INVALID")

    def begin_level(self, level_handle_digest: str) -> None:
        if not self.episode_active:
            raise RuntimeError("CONTROL_EPISODE_REQUIRED")
        if self.current_level_handle_digest is not None:
            raise RuntimeError("CONTROL_LEVEL_ALREADY_ACTIVE")
        if not isinstance(level_handle_digest, str) or not level_handle_digest:
            raise ValueError("CONTROL_LEVEL_HANDLE_REQUIRED")
        self.current_level_handle_digest = level_handle_digest

    def end_level(self, level_handle_digest: str) -> None:
        if self.current_level_handle_digest != level_handle_digest:
            raise PermissionError("CONTROL_LEVEL_HANDLE_INVALID")
        self.current_level_handle_digest = None

    def set_remaining_budget(self, remaining: int) -> None:
        if (
            isinstance(remaining, bool)
            or not isinstance(remaining, int)
            or remaining < 0
        ):
            raise ValueError("CONTROL_REMAINING_BUDGET_INVALID")
        self.remaining_action_budget = remaining

    def record_decision(
        self,
        *,
        next_question: str,
        pending_probe: str,
        stop_boundary: str,
    ) -> None:
        self.next_question = next_question
        self.pending_probe = pending_probe
        self.stop_boundary = stop_boundary

    def observe_outcome(self, *, progress: bool) -> None:
        self.no_progress_count = 0 if progress else self.no_progress_count + 1
        self.cycle_index += 1
        self.remaining_action_budget = max(
            0,
            self.remaining_action_budget - 1,
        )
        self.next_question = (
            "Which current relation, revised memory, and legal probe should "
            "be evaluated next?"
        )

    def end_episode(self, episode_handle_digest: str) -> None:
        self.require_episode(episode_handle_digest)
        self.current_level_handle_digest = None
        self.current_episode_handle_digest = None
        self.remaining_action_budget = 0
        self.remaining_time_seconds = None
        self.pending_probe = ""
        self.stop_boundary = ""


__all__ = [
    "CONTROL_STATE_VERSION",
    "DEFAULT_NEXT_QUESTION",
    "ControlState",
]
