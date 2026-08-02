"""Identity-free observation adapter for local ARC-AGI-3 sample frames."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from arcengine import FrameDataRaw

from .schema import digest_object
from .verification import RenderedObservation

_SUPPORTED_TERMINAL_STATES = frozenset({"NOT_FINISHED", "WIN", "GAME_OVER"})


def _matrix(value: object) -> tuple[tuple[int, ...], ...]:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = tolist()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
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
    """One immutable projection of an action-complete frame response.

    The official ``FrameDataRaw.frame`` list contains temporal camera renders
    collected while one external action completes.  ``layers`` remains the
    compatibility attribute name; callers should use the semantic properties
    below for new product code.
    """

    layers: tuple[tuple[tuple[int, ...], ...], ...]
    signature: str
    dimensions: tuple[int, int] | None
    available_actions: tuple[int, ...]
    terminal_state: str

    @property
    def action_frames(self) -> tuple[tuple[tuple[int, ...], ...], ...]:
        return self.layers

    @property
    def composited_view(self) -> tuple[tuple[int, ...], ...]:
        return self.layers[-1] if self.layers else ()

    @property
    def action_frame_signatures(self) -> tuple[str, ...]:
        return tuple(
            "action-frame:" + digest_object(action_frame)[:20]
            for action_frame in self.layers
        )

    @property
    def frame_relations(self) -> tuple[str, ...]:
        return tuple(
            f"action-frame:{index - 1}:precedes:action-frame:{index}"
            for index in range(1, len(self.layers))
        )


@dataclass(frozen=True, slots=True)
class SampleFrameAdapter:
    """Convert rendered sample state without exposing game or level identity."""

    def project(self, frame: FrameDataRaw) -> SampleFrameProjection:
        """Materialize expensive rendered facts exactly once per frame use."""

        layers = _layers(frame)
        dimensions: tuple[int, int] | None = None
        for action_frame in reversed(layers):
            if not action_frame:
                continue
            widths = {len(row) for row in action_frame}
            if len(widths) == 1 and next(iter(widths), 0) > 0:
                dimensions = (len(action_frame), next(iter(widths)))
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
        current_view = current_projection or self.project(current)
        effects: set[str] = {"ACTION_COMPLETE"}
        if len(current_view.action_frames) > 1:
            effects.add("ANIMATION_OBSERVED")
        if current.full_reset:
            effects.add("FULL_RESET")
        if previous is None:
            effects.add("INITIAL_OBSERVATION")
            terminal_state = current_view.terminal_state
            if terminal_state == "WIN":
                effects.update(("LEVEL_PROGRESS", "WIN_TERMINAL"))
            elif terminal_state == "GAME_OVER":
                effects.add("IRREVERSIBLE_FAILURE")
            return tuple(sorted(effects))

        previous_view = previous_projection or self.project(previous)
        current_render = current_view.composited_view
        previous_render = previous_view.composited_view
        temporal_path = (previous_render, *current_view.action_frames)
        temporal_change = any(
            left != right for left, right in zip(temporal_path, temporal_path[1:])
        )
        if current_render == previous_render:
            effects.add("NO_VISIBLE_CHANGE")
            if temporal_change:
                effects.add("TRANSIENT_ANIMATION_CHANGE")
        else:
            same_shape = (
                len(current_render) == len(previous_render)
                and bool(current_render)
                and all(
                    len(current_row) == len(previous_row)
                    for current_row, previous_row in zip(
                        current_render,
                        previous_render,
                    )
                )
            )
            changed_cells = (
                tuple(
                    (vertical, horizontal)
                    for vertical, (current_row, previous_row) in enumerate(
                        zip(current_render, previous_render)
                    )
                    for horizontal, (current_cell, previous_cell) in enumerate(
                        zip(current_row, previous_row)
                    )
                    if current_cell != previous_cell
                )
                if same_shape
                else ()
            )
            height = len(current_render)
            width = len(current_render[0]) if current_render else 0
            interface_only = bool(changed_cells) and all(
                vertical in {0, height - 1} or horizontal in {0, width - 1}
                for vertical, horizontal in changed_cells
            )
            if interface_only:
                effects.update(("INTERFACE_ONLY_CHANGE", "NO_VISIBLE_CHANGE"))
            else:
                effects.add("VISIBLE_STATE_CHANGE")
        if current.levels_completed > previous.levels_completed:
            effects.add("LEVEL_PROGRESS")
        terminal_state = current_view.terminal_state
        if terminal_state == "WIN":
            effects.update(("LEVEL_PROGRESS", "WIN_TERMINAL"))
        elif terminal_state == "GAME_OVER":
            effects.add("IRREVERSIBLE_FAILURE")
        if current_view.available_actions != previous_view.available_actions:
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
            None if previous is None else previous_projection or self.project(previous)
        )
        layers = current_view.action_frames
        composited_view = current_view.composited_view
        palette = Counter(cell for layer in layers for row in layer for cell in row)
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
        relations = current_view.frame_relations
        available_actions = current_view.available_actions
        terminal_state = current_view.terminal_state
        return {
            "frame": layers,
            "composited_view": composited_view,
            "frame_signature": current_view.signature,
            "action_frame_signatures": (current_view.action_frame_signatures),
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
                f"action-frame-count:{len(layers)}",
            ),
            "phase_hypotheses": (
                "terminal" if terminal_state in {"WIN", "GAME_OVER"} else "active",
            ),
            "feature_tokens": (
                f"terminal:{terminal_state.casefold()}",
                f"action-frame-count:{len(layers)}",
                f"visible-palette-size:{len(palette)}",
                "action-complete:true",
                f"animation-observed:{str(len(layers) > 1).casefold()}",
            ),
            "terminal_state": terminal_state,
            "full_reset": bool(current.full_reset),
            "action_complete": True,
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
            None if previous is None else previous_projection or self.project(previous)
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
