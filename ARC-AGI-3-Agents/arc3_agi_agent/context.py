"""Bounded episode context for the executable ARC-3 kernel."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .ir import HypothesisIR, ObservationIR
from .schema import digest_object


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Immutable view used by computation and HDS judgment."""

    current_observation: ObservationIR | None
    previous_observation: ObservationIR | None
    action_history: tuple[int, ...]
    effect_history: tuple[tuple[str, ...], ...]
    hypotheses: tuple[HypothesisIR, ...]
    failures: tuple[str, ...]
    action_budget: int
    actions_used: int
    open_items: tuple[str, ...]
    version: int

    @property
    def remaining_actions(self) -> int:
        return max(0, self.action_budget - self.actions_used)

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(slots=True)
class BoundedContextState:
    """Owns current execution context; it is not long-term memory."""

    max_observations: int = 4
    max_history: int = 16
    action_budget: int = 8
    _observations: deque[ObservationIR] = field(default_factory=deque, init=False)
    _action_history: deque[int] = field(default_factory=deque, init=False)
    _effect_history: deque[tuple[str, ...]] = field(
        default_factory=deque, init=False
    )
    _hypotheses: tuple[HypothesisIR, ...] = field(default=(), init=False)
    _failures: deque[str] = field(default_factory=deque, init=False)
    _open_items: tuple[str, ...] = field(default=(), init=False)
    _actions_used: int = field(default=0, init=False)
    _version: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_observations < 2:
            raise ValueError("max_observations must be at least two")
        if self.max_history < 1:
            raise ValueError("max_history must be positive")
        if self.action_budget < 1:
            raise ValueError("action_budget must be positive")

    def ingest(self, observation: ObservationIR) -> ContextSnapshot:
        if not isinstance(observation, ObservationIR):
            raise TypeError("CONTEXT_STATE requires ObservationIR")
        self._observations.append(observation)
        while len(self._observations) > self.max_observations:
            self._observations.popleft()
        self._version += 1
        return self.snapshot()

    def condition(
        self,
        hypotheses: tuple[HypothesisIR, ...],
        *,
        open_items: tuple[str, ...] = (),
    ) -> ContextSnapshot:
        self._hypotheses = tuple(hypotheses)
        self._open_items = tuple(sorted(set(open_items)))
        self._version += 1
        return self.snapshot()

    def record_emission(
        self,
        action_id: int,
        effects: tuple[str, ...],
    ) -> ContextSnapshot:
        self._action_history.append(int(action_id))
        self._effect_history.append(tuple(effects))
        self._actions_used += 1
        while len(self._action_history) > self.max_history:
            self._action_history.popleft()
        while len(self._effect_history) > self.max_history:
            self._effect_history.popleft()
        self._version += 1
        return self.snapshot()

    def record_failure(self, reason: str) -> ContextSnapshot:
        normalized = str(reason).strip()
        if not normalized:
            raise ValueError("failure reason must be non-empty")
        self._failures.append(normalized)
        while len(self._failures) > self.max_history:
            self._failures.popleft()
        self._version += 1
        return self.snapshot()

    def snapshot(self) -> ContextSnapshot:
        observations = tuple(self._observations)
        current = observations[-1] if observations else None
        previous = observations[-2] if len(observations) > 1 else None
        return ContextSnapshot(
            current_observation=current,
            previous_observation=previous,
            action_history=tuple(self._action_history),
            effect_history=tuple(self._effect_history),
            hypotheses=self._hypotheses,
            failures=tuple(self._failures),
            action_budget=self.action_budget,
            actions_used=self._actions_used,
            open_items=self._open_items,
            version=self._version,
        )


__all__ = ["BoundedContextState", "ContextSnapshot"]
