"""Identity-free observation adapter for local ARC-AGI-3 sample frames."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

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
    state = frame.state.value.upper()
    return state if state in _SUPPORTED_TERMINAL_STATES else "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SampleFrameProjection:
    """One immutable, identity-free projection of a rendered frame."""

    layers: tuple[tuple[tuple[int, ...], ...], ...]
    signature: str
    dimensions: tuple[int, int] | None
    available_actions: tuple[int, ...]
    terminal_state: str


@dataclass(frozen=True, slots=True)
class SampleFrameAdapter:
    """Convert rendered sample state without exposing game or level identity."""

    def project(self, frame: FrameDataRaw) -> SampleFrameProjection:
        """Materialize expensive rendered facts exactly once per frame use."""

        layers = _layers(frame)
        dimensions: tuple[int, int] | None = None
        for layer in layers:
            if not layer:
                continue
            widths = {len(row) for row in layer}
            if len(widths) == 1 and next(iter(widths), 0) > 0:
                dimensions = (len(layer), next(iter(widths)))
                break
        available_actions = tuple(
            sorted(
                {
                    int(action)
                    for action in frame.available_actions
                    if isinstance(action, int)
                    and not isinstance(action, bool)
                    and 1 <= action <= 7
                }
            )
        )
        return SampleFrameProjection(
            layers=layers,
            signature="frame:" + digest_object(layers)[:20],
            dimensions=dimensions,
            available_actions=available_actions,
            terminal_state=_terminal_state(frame),
        )

    def signature(
        self,
        frame: FrameDataRaw,
        *,
        projection: SampleFrameProjection | None = None,
    ) -> str:
        return (projection or self.project(frame)).signature

    def dimensions(
        self,
        frame: FrameDataRaw,
        *,
        projection: SampleFrameProjection | None = None,
    ) -> tuple[int, int] | None:
        return (projection or self.project(frame)).dimensions

    def visible_effects(
        self,
        current: FrameDataRaw,
        previous: FrameDataRaw | None,
        *,
        current_projection: SampleFrameProjection | None = None,
        previous_projection: SampleFrameProjection | None = None,
    ) -> tuple[str, ...]:
        if previous is None:
            return ()

        current_view = current_projection or self.project(current)
        previous_view = previous_projection or self.project(previous)
        effects: set[str] = set()
        if current_view.signature == previous_view.signature:
            effects.add("NO_VISIBLE_CHANGE")
        else:
            effects.add("VISIBLE_STATE_CHANGE")
        if current.levels_completed > previous.levels_completed:
            effects.add("LEVEL_PROGRESS")
        if current.full_reset:
            effects.add("FULL_RESET")
        terminal_state = current_view.terminal_state
        if terminal_state == "WIN":
            effects.update(("LEVEL_PROGRESS", "WIN_TERMINAL"))
        elif terminal_state == "GAME_OVER":
            effects.add("IRREVERSIBLE_FAILURE")
        if (
            current_view.available_actions
            != previous_view.available_actions
        ):
            effects.add("ACTION_SURFACE_CHANGE")
        return tuple(sorted(effects))

    def runtime_observation(
        self,
        current: FrameDataRaw,
        previous: FrameDataRaw | None = None,
        *,
        current_projection: SampleFrameProjection | None = None,
        previous_projection: SampleFrameProjection | None = None,
    ) -> dict[str, object]:
        current_view = current_projection or self.project(current)
        previous_view = (
            None
            if previous is None
            else previous_projection or self.project(previous)
        )
        layers = current_view.layers
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
        available_actions = current_view.available_actions
        terminal_state = current_view.terminal_state
        return {
            "frame": layers,
            "frame_signature": current_view.signature,
            "dimensions": current_view.dimensions,
            "available_actions": available_actions,
            "effects": self.visible_effects(
                current,
                previous,
                current_projection=current_view,
                previous_projection=previous_view,
            ),
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
        current_projection: SampleFrameProjection | None = None,
        previous_projection: SampleFrameProjection | None = None,
    ) -> RenderedObservation:
        current_view = current_projection or self.project(current)
        previous_view = (
            None
            if previous is None
            else previous_projection or self.project(previous)
        )
        effects = self.visible_effects(
            current,
            previous,
            current_projection=current_view,
            previous_projection=previous_view,
        )
        terminal_state = current_view.terminal_state
        return RenderedObservation(
            signature=current_view.signature,
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
            available_actions=current_view.available_actions,
            action_count=action_count,
            max_actions=max_actions,
        )


__all__ = ["SampleFrameAdapter", "SampleFrameProjection"]
