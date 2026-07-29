"""Taint-free typed input envelope for C/P/J decision work."""

from __future__ import annotations

from dataclasses import dataclass, field

from .generic_types import GenericObservation
from .identity_boundary import IdentityBoundary
from .schema import digest_object

DECISION_CONTEXT_VERSION = "arc3-decision-context-v1"


@dataclass(frozen=True, slots=True)
class DecisionObservation:
    rendered_layers: tuple[tuple[tuple[int, ...], ...], ...]
    available_actions: tuple[int, ...]
    action_payload_schema: tuple[tuple[int, tuple[str, ...]], ...]
    terminal_state: str
    progress_count: int
    visible_effects: tuple[str, ...]
    episode_local_observation_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.episode_local_observation_digest.startswith(
            "generic-observation:"
        ):
            failures.append("DECISION_OBSERVATION_DIGEST_INVALID")
        if (
            not self.available_actions
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.available_actions
            )
        ):
            failures.append("DECISION_OBSERVATION_ACTIONS_INVALID")
        if any(
            isinstance(cell, bool) or not isinstance(cell, int)
            for layer in self.rendered_layers
            for row in layer
            for cell in row
        ):
            failures.append("DECISION_OBSERVATION_RENDER_INVALID")
        return tuple(sorted(set(failures)))

    @classmethod
    def from_observation(
        cls,
        observation: GenericObservation,
    ) -> DecisionObservation:
        failures = observation.validate()
        if failures:
            raise ValueError(";".join(failures))
        return cls(
            rendered_layers=observation.rendered_layers,
            available_actions=observation.available_actions,
            action_payload_schema=observation.action_payload_schema,
            terminal_state=observation.terminal_state,
            progress_count=observation.progress_count,
            visible_effects=observation.visible_effects,
            episode_local_observation_digest=observation.digest(),
        )


@dataclass(frozen=True, slots=True)
class DecisionContext:
    observation: DecisionObservation
    memory_version: int
    cycle_index: int
    purpose_tokens: tuple[str, ...]
    bounded_history_digests: tuple[str, ...] = ()
    _validation_cache: tuple[str, ...] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _digest_cache: str | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(self) -> tuple[str, ...]:
        if self._validation_cache is not None:
            return self._validation_cache
        failures: list[str] = []
        failures.extend(self.observation.validate())
        if (
            isinstance(self.memory_version, bool)
            or not isinstance(self.memory_version, int)
            or self.memory_version < 0
        ):
            failures.append("DECISION_CONTEXT_MEMORY_VERSION_INVALID")
        if (
            isinstance(self.cycle_index, bool)
            or not isinstance(self.cycle_index, int)
            or self.cycle_index < 0
        ):
            failures.append("DECISION_CONTEXT_CYCLE_INVALID")
        for name in ("purpose_tokens", "bounded_history_digests"):
            values = getattr(self, name)
            if (
                any(not isinstance(item, str) or not item for item in values)
                or values != tuple(sorted(set(values)))
            ):
                failures.append("DECISION_CONTEXT_SEQUENCE_INVALID:" + name)
        boundary_failures = IdentityBoundary().inspect_decision_context(
            {
                "observation_digest": (
                    self.observation.episode_local_observation_digest
                ),
                "available_actions": self.observation.available_actions,
                "action_payload_schema": (
                    self.observation.action_payload_schema
                ),
                "terminal_state": self.observation.terminal_state,
                "progress_count": self.observation.progress_count,
                "visible_effects": self.observation.visible_effects,
                "memory_version": self.memory_version,
                "cycle_index": self.cycle_index,
                "purpose_tokens": self.purpose_tokens,
                "bounded_history_digests": self.bounded_history_digests,
            }
        )
        failures.extend(
            "DECISION_CONTEXT_TAINT:" + item
            for item in boundary_failures
        )
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def digest(self) -> str:
        cached = self._digest_cache
        if cached is None:
            failures = self.validate()
            if failures:
                raise ValueError(";".join(failures))
            cached = "decision-context:" + digest_object(
                {
                    "observation_digest": (
                        self.observation.episode_local_observation_digest
                    ),
                    "memory_version": self.memory_version,
                    "cycle_index": self.cycle_index,
                    "purpose_tokens": self.purpose_tokens,
                    "bounded_history_digests": (
                        self.bounded_history_digests
                    ),
                }
            )
            object.__setattr__(
                self,
                "_digest_cache",
                cached,
            )
        return cached


__all__ = [
    "DECISION_CONTEXT_VERSION",
    "DecisionContext",
    "DecisionObservation",
]
