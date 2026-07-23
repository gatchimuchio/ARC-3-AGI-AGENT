"""Identity-free observation adapter for local ARC-AGI-3 sample frames."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from arcengine import FrameDataRaw

from .schema import digest_object
from .verification import RenderedObservation

_SUPPORTED_TERMINAL_STATES = frozenset(
    {"NOT_FINISHED", "WIN", "GAME_OVER"}
)


def _matrix(value: object) -> tuple[tuple[int, ...], ...]:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = tolist()
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return ()

    rows: list[tuple[int, ...]] = []
    for raw_row in value:
        if not isinstance(raw_row, Sequence) or isinstance(
            raw_row, (str, bytes, bytearray)
        ):
            return ()
        row: list[int] = []
        for raw_cell in raw_row:
            if isinstance(raw_cell, bool):
                return ()
            try:
                row.append(int(raw_cell))
            except (TypeError, ValueError, OverflowError):
                return ()
        rows.append(tuple(row))
    return tuple(rows)


def _layers(frame: FrameDataRaw) -> tuple[tuple[tuple[int, ...], ...], ...]:
    return tuple(_matrix(layer) for layer in frame.frame)


def _terminal_state(frame: FrameDataRaw) -> str:
    state = cast(str, frame.state.value).upper()
    return state if state in _SUPPORTED_TERMINAL_STATES else "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SampleFrameAdapter:
    """Convert rendered sample state without exposing game or level identity."""

    def signature(self, frame: FrameDataRaw) -> str:
        return "frame:" + digest_object(_layers(frame))[:20]

    def dimensions(self, frame: FrameDataRaw) -> tuple[int, int] | None:
        for layer in _layers(frame):
            if not layer:
                continue
            widths = {len(row) for row in layer}
            if len(widths) == 1 and next(iter(widths), 0) > 0:
                return (len(layer), next(iter(widths)))
        return None

    def visible_effects(
        self,
        current: FrameDataRaw,
        previous: FrameDataRaw | None,
    ) -> tuple[str, ...]:
        if previous is None:
            return ()

        effects: set[str] = set()
        if self.signature(current) == self.signature(previous):
            effects.add("NO_VISIBLE_CHANGE")
        else:
            effects.add("VISIBLE_STATE_CHANGE")
        if current.levels_completed > previous.levels_completed:
            effects.add("LEVEL_PROGRESS")
        if current.full_reset:
            effects.add("FULL_RESET")
        terminal_state = _terminal_state(current)
        if terminal_state == "WIN":
            effects.update(("LEVEL_PROGRESS", "WIN_TERMINAL"))
        elif terminal_state == "GAME_OVER":
            effects.add("IRREVERSIBLE_FAILURE")
        if tuple(current.available_actions) != tuple(previous.available_actions):
            effects.add("ACTION_SURFACE_CHANGE")
        return tuple(sorted(effects))

    def runtime_observation(
        self,
        current: FrameDataRaw,
        previous: FrameDataRaw | None = None,
    ) -> dict[str, object]:
        layers = _layers(current)
        palette = Counter(
            cell for layer in layers for row in layer for cell in row
        )
        objects = tuple(
            {
                "entity_id": f"palette:{value}",
                "features": (
                    f"visible-count:{count}",
                    "most-frequent"
                    if count == max(palette.values(), default=0)
                    else "visible",
                ),
            }
            for value, count in sorted(palette.items())
        )
        relations = tuple(
            f"layer:{index - 1}:precedes:layer:{index}"
            for index in range(1, len(layers))
        )
        available_actions = tuple(
            sorted(
                {
                    int(action)
                    for action in current.available_actions
                    if isinstance(action, int)
                    and not isinstance(action, bool)
                    and 1 <= action <= 7
                }
            )
        )
        terminal_state = _terminal_state(current)
        dimensions = self.dimensions(current)
        return {
            "frame": layers,
            "frame_signature": self.signature(current),
            "dimensions": dimensions,
            "available_actions": available_actions,
            "effects": self.visible_effects(current, previous),
            "objects": objects,
            "relations": relations,
            "resources": (
                f"available-action-count:{len(available_actions)}",
                f"visible-layer-count:{len(layers)}",
            ),
            "phase_hypotheses": (
                "terminal"
                if terminal_state in {"WIN", "GAME_OVER"}
                else "active",
            ),
            "feature_tokens": (
                f"terminal:{terminal_state.casefold()}",
                f"visible-layer-count:{len(layers)}",
                f"visible-palette-size:{len(palette)}",
            ),
            "terminal_state": terminal_state,
        }

    def rendered_observation(
        self,
        current: FrameDataRaw,
        previous: FrameDataRaw | None,
        *,
        action_count: int,
        max_actions: int,
    ) -> RenderedObservation:
        effects = self.visible_effects(current, previous)
        terminal_state = _terminal_state(current)
        return RenderedObservation(
            signature=self.signature(current),
            levels_completed=current.levels_completed,
            terminal_state=terminal_state,
            visible_progress=(
                previous is not None
                and (
                    current.levels_completed > previous.levels_completed
                    or terminal_state == "WIN"
                )
            ),
            visible_effects=effects,
            available_actions=tuple(
                sorted(
                    {
                        int(action)
                        for action in current.available_actions
                        if isinstance(action, int)
                        and not isinstance(action, bool)
                        and 1 <= action <= 7
                    }
                )
            ),
            action_count=action_count,
            max_actions=max_actions,
        )


__all__ = ["SampleFrameAdapter"]
