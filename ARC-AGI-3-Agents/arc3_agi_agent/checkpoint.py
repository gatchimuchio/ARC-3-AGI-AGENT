"""Bounded evidence checkpoints.

A checkpoint is a retained observation record.  It is not a guarantee that the
environment can be restored to the corresponding state.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field

from .verification import RenderedObservation


@dataclass(frozen=True, slots=True)
class Checkpoint:
    checkpoint_id: str
    observation: RenderedObservation
    authority: str = "evidence-only"


@dataclass(slots=True)
class CheckpointManager:
    max_checkpoints: int = 32
    checkpoints: deque[Checkpoint] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_checkpoints < 1:
            raise ValueError("max_checkpoints must be positive")

    def save(self, observation: RenderedObservation) -> Checkpoint:
        failures = observation.validate()
        if failures:
            raise ValueError(f"invalid observation: {','.join(failures)}")
        payload = {
            "signature": observation.signature,
            "levels_completed": observation.levels_completed,
            "terminal_state": observation.terminal_state,
            "visible_progress": observation.visible_progress,
            "visible_effects": observation.visible_effects,
            "available_actions": observation.available_actions,
            "action_count": observation.action_count,
            "max_actions": observation.max_actions,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        checkpoint = Checkpoint(f"checkpoint:{digest}", observation)
        self.checkpoints.append(checkpoint)
        while len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.popleft()
        return checkpoint

    def latest(self) -> Checkpoint | None:
        return self.checkpoints[-1] if self.checkpoints else None

    def evidence(self) -> tuple[Checkpoint, ...]:
        return tuple(self.checkpoints)


__all__ = ["Checkpoint", "CheckpointManager"]
