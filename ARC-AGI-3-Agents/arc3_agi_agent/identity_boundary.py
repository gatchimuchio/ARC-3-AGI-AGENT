"""Typed separation between orchestration metadata and decision inputs."""

from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Generic, TypeVar

from .generic_types import GenericObservation
from .schema import (
    FORBIDDEN_RUNTIME_KEY_TOKENS,
    canonical_json,
)

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
    environment_handle: Tainted[object] = field(metadata={"serialize": False})


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


@lru_cache(maxsize=2_048)
def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _inspect_value(
    value: object,
    *,
    path: str,
    runtime_paths: list[str],
    orchestration_paths: list[str],
) -> bool:
    """Inspect one immutable decision value in a single fail-closed walk."""

    if isinstance(value, (Tainted, OrchestrationMetadata)):
        return True
    if value is None or isinstance(value, (str, bool, int)):
        return False
    if isinstance(value, float):
        if math.isfinite(value):
            return False
        canonical_json(value)
        return False
    tainted = False
    if dataclasses.is_dataclass(value):
        for item in dataclasses.fields(value):
            if not item.metadata.get("serialize", True):
                continue
            child_path = f"{path}.{item.name}"
            normalized = _normalized_key(item.name)
            if normalized in FORBIDDEN_RUNTIME_KEY_TOKENS:
                runtime_paths.append(child_path)
            if normalized in _FORBIDDEN_DECISION_KEYS:
                orchestration_paths.append(child_path)
            tainted = (
                _inspect_value(
                    getattr(value, item.name),
                    path=child_path,
                    runtime_paths=runtime_paths,
                    orchestration_paths=orchestration_paths,
                )
                or tainted
            )
        return tainted
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.<key>"
            if not isinstance(key, (str, int, float, bool)) and key is not None:
                tainted = (
                    _inspect_value(
                        key,
                        path=key_path,
                        runtime_paths=runtime_paths,
                        orchestration_paths=orchestration_paths,
                    )
                    or tainted
                )
            child_path = f"{path}.{key}"
            normalized = _normalized_key(str(key))
            if normalized in FORBIDDEN_RUNTIME_KEY_TOKENS:
                runtime_paths.append(child_path)
            if normalized in _FORBIDDEN_DECISION_KEYS:
                orchestration_paths.append(child_path)
            tainted = (
                _inspect_value(
                    item,
                    path=child_path,
                    runtime_paths=runtime_paths,
                    orchestration_paths=orchestration_paths,
                )
                or tainted
            )
        return tainted
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            tainted = (
                _inspect_value(
                    item,
                    path=f"{path}[{index}]",
                    runtime_paths=runtime_paths,
                    orchestration_paths=orchestration_paths,
                )
                or tainted
            )
        return tainted
    if isinstance(value, Mapping):
        return _inspect_value(
            dict(value.items()),
            path=path,
            runtime_paths=runtime_paths,
            orchestration_paths=orchestration_paths,
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return _inspect_value(
            tuple(value),
            path=path,
            runtime_paths=runtime_paths,
            orchestration_paths=orchestration_paths,
        )
    # Preserve the former canonical serializer's fail-closed behavior for
    # unsupported leaves and non-finite numbers.
    canonical_json(value)
    return False


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
            runtime_paths: list[str] = []
            orchestration_paths: list[str] = []
            if _inspect_value(
                value,
                path="$",
                runtime_paths=runtime_paths,
                orchestration_paths=orchestration_paths,
            ):
                failures.append(f"$[{index}]:TAINTED_VALUE")
                continue
            failures.extend(
                f"$[{index}]{path[1:]}:FORBIDDEN_KEY" for path in runtime_paths
            )
            failures.extend(
                f"$[{index}]{path[1:]}:ORCHESTRATION_KEY"
                for path in orchestration_paths
            )
        return tuple(sorted(set(failures)))

    def require_decision_context(self, *values: object) -> None:
        failures = self.inspect_decision_context(*values)
        if failures:
            raise PermissionError("IDENTITY_BOUNDARY_VIOLATION:" + ",".join(failures))


__all__ = [
    "IDENTITY_BOUNDARY_VERSION",
    "IdentityBoundary",
    "OrchestrationMetadata",
    "Tainted",
]
