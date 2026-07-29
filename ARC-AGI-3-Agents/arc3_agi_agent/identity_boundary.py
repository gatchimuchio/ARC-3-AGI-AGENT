"""Typed separation between orchestration metadata and decision inputs."""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from .generic_types import GenericObservation
from .schema import canonical_json, forbidden_runtime_paths

IDENTITY_BOUNDARY_VERSION = "arc3-identity-boundary-v1"

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class Tainted(Generic[_T]):
    """A value that is legal for orchestration and illegal for cognition."""

    value: _T = field(metadata={"serialize": False})


@dataclass(frozen=True, slots=True)
class OrchestrationMetadata:
    """Metadata retained only at the runner/framework boundary."""

    scorecard_id: Tainted[str] = field(metadata={"serialize": False})
    game_id: Tainted[str] = field(metadata={"serialize": False})
    game_index: Tainted[int] = field(metadata={"serialize": False})
    environment_handle: Tainted[object] = field(
        metadata={"serialize": False}
    )


_FORBIDDEN_DECISION_KEYS = frozenset(
    {
        "scorecardid",
        "gameid",
        "gameindex",
        "taskid",
        "levelid",
        "environmenthandle",
        "episodehandle",
        "replayindex",
        "answermap",
        "sourcestate",
        "hiddenstate",
        "fixedactionsequence",
        "literalcoordinatetable",
    }
)


def _contains_taint(value: object) -> bool:
    if isinstance(value, (Tainted, OrchestrationMetadata)):
        return True
    if dataclasses.is_dataclass(value):
        return any(
            _contains_taint(getattr(value, item.name))
            for item in dataclasses.fields(value)
            if item.metadata.get("serialize", True)
        )
    if isinstance(value, Mapping):
        return any(
            _contains_taint(key) or _contains_taint(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return any(_contains_taint(item) for item in value)
    return False


def _forbidden_keys(value: object, path: str = "$") -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            child_path = f"{path}.{key}"
            if normalized in _FORBIDDEN_DECISION_KEYS:
                failures.append(child_path)
            failures.extend(_forbidden_keys(item, child_path))
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for index, item in enumerate(value):
            failures.extend(_forbidden_keys(item, f"{path}[{index}]"))
    return failures


@dataclass(frozen=True, slots=True)
class IdentityBoundary:
    """Fail closed when tainted orchestration data reaches cognition."""

    boundary_version: str = IDENTITY_BOUNDARY_VERSION

    def inspect_decision_context(
        self,
        *values: object,
    ) -> tuple[str, ...]:
        failures: list[str] = []
        for index, value in enumerate(values):
            if isinstance(value, GenericObservation):
                observation_failures = value.validate()
                if observation_failures:
                    failures.extend(
                        f"$[{index}]:TYPED_CONTRACT_INVALID:{failure}"
                        for failure in observation_failures
                    )
                    continue
                value = {
                    "typed_contract": "GenericObservation",
                    "signature": value.signature,
                    "available_actions": value.available_actions,
                    "terminal_state": value.terminal_state,
                    "progress_count": value.progress_count,
                    "visible_effects": value.visible_effects,
                    "action_payload_schema": value.action_payload_schema,
                    "rendered_content_digest": value.digest(),
                }
            if _contains_taint(value):
                failures.append(f"$[{index}]:TAINTED_VALUE")
                continue
            serialized = json.loads(canonical_json(value))
            failures.extend(
                f"$[{index}]{path[1:]}:FORBIDDEN_KEY"
                for path in forbidden_runtime_paths(serialized)
            )
            failures.extend(
                f"$[{index}]{path[1:]}:ORCHESTRATION_KEY"
                for path in _forbidden_keys(serialized)
            )
        return tuple(sorted(set(failures)))

    def require_decision_context(self, *values: object) -> None:
        failures = self.inspect_decision_context(*values)
        if failures:
            raise PermissionError(
                "IDENTITY_BOUNDARY_VIOLATION:" + ",".join(failures)
            )


__all__ = [
    "IDENTITY_BOUNDARY_VERSION",
    "IdentityBoundary",
    "OrchestrationMetadata",
    "Tainted",
]
