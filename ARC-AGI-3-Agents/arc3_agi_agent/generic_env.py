"""Identity-free environment adapters and executable generic micro-worlds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

from arc_agi import EnvironmentWrapper  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw, GameAction

from .generic_types import GenericObservation
from .sample_observation import SampleFrameAdapter, SampleFrameProjection
from .schema import digest_object

GENERIC_ENV_VERSION = "arc3-generic-environments-v1"
TRANSFORMATION_FAMILIES = (
    "COLOR",
    "ROTATION",
    "REFLECTION",
    "LAYOUT",
    "OBJECT_COUNT",
    "ORDER",
    "UNSEEN_COMPOSITION",
)
_OBSERVATION_HISTORY_LIMIT = 16


def _last_action_surface(
    frame: FrameDataRaw,
) -> tuple[int, tuple[tuple[str, int], ...]]:
    """Project only the legal action payload, never opaque reasoning data."""

    action_input = frame.action_input
    raw_action = getattr(action_input, "id", 0)
    raw_action = getattr(raw_action, "value", raw_action)
    action_id = (
        raw_action
        if isinstance(raw_action, int) and not isinstance(raw_action, bool)
        else 0
    )
    raw_payload = getattr(action_input, "data", {})
    payload: list[tuple[str, int]] = []
    if action_id == 6 and isinstance(raw_payload, Mapping):
        for key in ("x", "y"):
            value = raw_payload.get(key)
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            payload.append((key, value))
    return action_id, tuple(sorted(payload))


def _rotate(
    matrix: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(matrix[len(matrix) - 1 - row][column] for row in range(len(matrix)))
        for column in range(len(matrix[0]))
    )


def _reflect(
    matrix: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(reversed(row)) for row in matrix)


def _translate(
    matrix: tuple[tuple[int, ...], ...],
    *,
    dy: int,
    dx: int,
) -> tuple[tuple[int, ...], ...]:
    height = len(matrix)
    width = len(matrix[0])
    output = [[0 for _ in range(width)] for _ in range(height)]
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            output[(y + dy) % height][(x + dx) % width] = value
    return tuple(tuple(row) for row in output)


@dataclass(slots=True)
class MechanismWorld:
    """Closed rendered world with hidden action-effect semantics.

    The runtime sees only GenericObservation. The hidden winning ordinals are
    evaluator state, not task identity or an answer map exposed to C/J/M/P.
    """

    available_actions: tuple[int, ...]
    winning_ordinals: tuple[int, ...]
    required_progress: int = 3
    transformation: str = "BASE"
    failure_ordinals: tuple[int, ...] = ()
    max_turns: int = 64
    seed: int = 0
    _progress: int = field(default=0, init=False)
    _turn: int = field(default=0, init=False)
    _state: str = field(default="NOT_FINISHED", init=False)
    _last_effects: tuple[str, ...] = field(default=(), init=False)
    _seen_request_ids: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if not self.available_actions or self.available_actions != tuple(
            sorted(set(self.available_actions))
        ):
            raise ValueError("MECHANISM_WORLD_ACTION_SURFACE_INVALID")
        if not self.winning_ordinals or any(
            item < 0 or item >= len(self.available_actions)
            for item in self.winning_ordinals
        ):
            raise ValueError("MECHANISM_WORLD_WINNING_ORDINAL_INVALID")
        if self.transformation not in {"BASE", *TRANSFORMATION_FAMILIES}:
            raise ValueError("MECHANISM_WORLD_TRANSFORMATION_INVALID")

    def _base_matrix(self) -> tuple[tuple[int, ...], ...]:
        size = 9
        matrix = [[0 for _ in range(size)] for _ in range(size)]
        objects = [
            (1, 1, 2),
            (1, 6, 3),
            (6, 1, 4),
            (6, 6, 5),
        ]
        if self.transformation == "OBJECT_COUNT":
            objects.extend(((4, 2, 6), (2, 4, 7)))
        if self.transformation == "ORDER":
            objects = list(reversed(objects))
        for index, (y, x, value) in enumerate(objects):
            offset = (self.seed + index) % 2
            matrix[y][x] = value
            if y + offset + 1 < size:
                matrix[y + offset + 1][x] = value
        for x in range(1, 1 + min(self._progress, size - 2)):
            matrix[4][x] = 8
        output = tuple(tuple(row) for row in matrix)
        if self.transformation == "COLOR":
            output = tuple(
                tuple(0 if value == 0 else ((value * 5 + 3) % 15) + 1 for value in row)
                for row in output
            )
        elif self.transformation == "ROTATION":
            output = _rotate(output)
        elif self.transformation == "REFLECTION":
            output = _reflect(output)
        elif self.transformation == "LAYOUT":
            output = _translate(output, dy=2, dx=3)
        elif self.transformation == "UNSEEN_COMPOSITION":
            output = _reflect(_rotate(_translate(output, dy=1, dx=2)))
        return output

    def observe(self) -> GenericObservation:
        matrix = self._base_matrix()
        return GenericObservation(
            signature="mechanism-frame:"
            + digest_object(
                {
                    "matrix": matrix,
                    "progress": self._progress,
                    "state": self._state,
                    "actions": self.available_actions,
                }
            )[:24],
            available_actions=self.available_actions,
            rendered_layers=(matrix,),
            terminal_state=self._state,
            progress_count=self._progress,
            visible_effects=self._last_effects,
        )

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        del payload
        if request_id in self._seen_request_ids:
            raise RuntimeError("MECHANISM_WORLD_DUPLICATE_REQUEST")
        self._seen_request_ids.add(request_id)
        if self._state != "NOT_FINISHED":
            raise RuntimeError("MECHANISM_WORLD_TERMINAL_STEP")
        if action_id not in self.available_actions:
            raise ValueError("MECHANISM_WORLD_ACTION_INVALID")
        ordinal = self.available_actions.index(action_id)
        self._turn += 1
        if ordinal in self.failure_ordinals:
            self._state = "GAME_OVER"
            self._last_effects = ("IRREVERSIBLE_FAILURE",)
            return self.observe()
        expected = self.winning_ordinals[self._progress % len(self.winning_ordinals)]
        if ordinal == expected:
            self._progress += 1
            self._last_effects = ("LEVEL_PROGRESS", "VISIBLE_STATE_CHANGE")
            if self._progress >= self.required_progress:
                self._state = "WIN"
                self._last_effects = (
                    "LEVEL_PROGRESS",
                    "VISIBLE_STATE_CHANGE",
                    "WIN_TERMINAL",
                )
        else:
            self._last_effects = ("NO_VISIBLE_CHANGE",)
        if self._turn >= self.max_turns and self._state == "NOT_FINISHED":
            self._last_effects = ("NO_VISIBLE_CHANGE", "RESOURCE_PRESSURE")
        return self.observe()

    def reset_level(self, *, request_id: str) -> GenericObservation:
        if request_id in self._seen_request_ids:
            raise RuntimeError("MECHANISM_WORLD_DUPLICATE_REQUEST")
        self._seen_request_ids.add(request_id)
        if self._state != "GAME_OVER":
            raise RuntimeError("MECHANISM_WORLD_RESET_WITHOUT_FAILURE")
        self._state = "NOT_FINISHED"
        self._last_effects = ("LEVEL_RESET",)
        return self.observe()


@dataclass(slots=True)
class OfflineGenericEnvironment:
    """Local sample adapter that never exposes its orchestration identity."""

    _boundary: ClassVar[str] = "GENERIC_OFFLINE"
    environment: Any
    frame_adapter: SampleFrameAdapter = field(default_factory=SampleFrameAdapter)
    _current: FrameDataRaw = field(init=False, repr=False)
    _previous: FrameDataRaw | None = field(default=None, init=False, repr=False)
    _current_projection: SampleFrameProjection = field(init=False, repr=False)
    _previous_projection: SampleFrameProjection | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _seen_request_ids: set[str] = field(default_factory=set, init=False)
    _observation_history: tuple[str, ...] = field(
        default=(),
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.environment, LocalEnvironmentWrapper):
            raise TypeError(f"{self._boundary}_LOCAL_WRAPPER_REQUIRED")
        current = self.environment.observation_space
        if not isinstance(current, FrameDataRaw):
            raise TypeError(f"{self._boundary}_INITIAL_FRAME_REQUIRED")
        self._initialize_current(current)

    def _initialize_current(self, current: FrameDataRaw) -> None:
        self._current = current
        self._current_projection = self.frame_adapter.project(current)
        self._observation_history = (self._current_projection.signature,)

    def _advance(self, raw: FrameDataRaw) -> None:
        self._previous = self._current
        self._previous_projection = self._current_projection
        self._current = raw
        self._current_projection = self.frame_adapter.project(raw)
        self._observation_history = (
            *self._observation_history,
            self._current_projection.signature,
        )[-_OBSERVATION_HISTORY_LIMIT:]

    def _observation(self) -> GenericObservation:
        projection = self._current_projection
        effects = self.frame_adapter.visible_effects(
            self._current,
            self._previous,
            current_projection=projection,
            previous_projection=self._previous_projection,
        )
        payload_schema: tuple[tuple[int, tuple[str, ...]], ...] = ()
        if 6 in projection.available_actions:
            payload_schema = ((6, ("x", "y")),)
        last_action_id, last_action_payload_items = _last_action_surface(self._current)
        return GenericObservation(
            signature=projection.signature,
            available_actions=projection.available_actions,
            rendered_layers=projection.layers,
            terminal_state=projection.terminal_state,
            progress_count=int(self._current.levels_completed),
            visible_effects=effects,
            action_payload_schema=payload_schema,
            control_actions=(0,),
            win_level_count=int(self._current.win_levels),
            full_reset=bool(self._current.full_reset),
            last_action_id=last_action_id,
            last_action_payload_items=last_action_payload_items,
            observation_history=self._observation_history,
            action_complete=True,
        )

    def observe(self) -> GenericObservation:
        return self._observation()

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        if request_id in self._seen_request_ids:
            raise RuntimeError(f"{self._boundary}_DUPLICATE_REQUEST")
        self._seen_request_ids.add(request_id)
        observation = self._observation()
        if action_id not in observation.available_actions:
            raise ValueError(f"{self._boundary}_ACTION_UNAVAILABLE")
        action = GameAction.from_id(action_id)
        data: dict[str, int] = {}
        if action_id == 6:
            if set(payload) != {"x", "y"}:
                raise ValueError(f"{self._boundary}_POINTER_PAYLOAD_REQUIRED")
            data = {"x": int(payload["x"]), "y": int(payload["y"])}
        raw = self.environment.step(
            action,
            data=data,
            reasoning={
                "authority": "HDS",
                "runtime": "GenericAGIRuntime",
                "request_id": request_id,
            },
        )
        if not isinstance(raw, FrameDataRaw):
            raise RuntimeError(f"{self._boundary}_STEP_FAILED")
        self._advance(raw)
        return self._observation()

    def reset_level(self, *, request_id: str) -> GenericObservation:
        if request_id in self._seen_request_ids:
            raise RuntimeError(f"{self._boundary}_DUPLICATE_REQUEST")
        self._seen_request_ids.add(request_id)
        raw = self.environment.step(
            GameAction.RESET,
            data={},
            reasoning={
                "authority": "HDS",
                "runtime": "GenericAGIRuntime",
                "request_id": request_id,
                "scope": "level",
            },
        )
        if not isinstance(raw, FrameDataRaw):
            raise RuntimeError(f"{self._boundary}_RESET_FAILED")
        self._advance(raw)
        return self._observation()


class CompetitionGenericEnvironment(OfflineGenericEnvironment):
    """Official remote-wrapper adapter with the same identity-free projection."""

    __slots__ = ()
    _boundary: ClassVar[str] = "GENERIC_COMPETITION"

    def __post_init__(self) -> None:
        if not isinstance(self.environment, EnvironmentWrapper) or isinstance(
            self.environment, LocalEnvironmentWrapper
        ):
            raise TypeError("GENERIC_COMPETITION_REMOTE_WRAPPER_REQUIRED")
        current = self.environment.observation_space
        if not isinstance(current, FrameDataRaw):
            raise TypeError("GENERIC_COMPETITION_INITIAL_FRAME_REQUIRED")
        self._initialize_current(current)


def transformed_worlds(
    *,
    seed: int = 0,
) -> tuple[tuple[str, MechanismWorld], ...]:
    """Return seven executable worlds, one per mandated transformation."""

    return tuple(
        (
            family,
            MechanismWorld(
                available_actions=(11, 29, 47),
                winning_ordinals=(1,),
                required_progress=2,
                transformation=family,
                failure_ordinals=(2,)
                if family in {"ORDER", "UNSEEN_COMPOSITION"}
                else (),
                seed=seed + index,
            ),
        )
        for index, family in enumerate(TRANSFORMATION_FAMILIES)
    )


__all__ = [
    "GENERIC_ENV_VERSION",
    "TRANSFORMATION_FAMILIES",
    "CompetitionGenericEnvironment",
    "MechanismWorld",
    "OfflineGenericEnvironment",
    "transformed_worlds",
]
