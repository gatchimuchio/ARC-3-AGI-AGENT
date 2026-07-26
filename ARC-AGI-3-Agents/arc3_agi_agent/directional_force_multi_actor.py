"""Composed rendered multi-actor and directional-force planning.

This module does not define a new semantic operator.  It is a dormant,
instruction-gated execution path for the existing directional-force operator.
The path composes the already compiled multi-actor obligation model with the
already compiled directional-force transition model.  Detection, search,
selection points, transition checks, and all coordinates are derived from the
current rendered observation.
"""

from __future__ import annotations

import heapq
import itertools
import json
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, TypeAlias

from .directional_force_route import (
    DIRECTIONAL_FORCE_ROUTE_OPERATOR,
    _DirectionalForceParameters,
    _edge_band,
    _force_blocks,
    _ForceBlock,
    _union_components,
)
from .instruction_body import SemanticOperatorInstruction
from .multi_actor_shape_push import (
    MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
    Mask,
    MultiShapeState,
    Position,
    SearchAction,
)
from .multi_actor_shape_push import (
    _heuristic as _multi_heuristic,
)
from .multi_actor_shape_push import (
    _is_goal as _multi_is_goal,
)
from .multi_actor_shape_push import (
    _Model as _MultiModel,
)
from .multi_actor_shape_push import (
    _model as _multi_model,
)
from .multi_actor_shape_push import (
    _Parameters as _MultiParameters,
)
from .schema import digest_object
from .visual_explorer import Grid, Point, VisualAction

COMPOSITION_EVIDENCE = "directional-force-multi-actor-composition-v1"
DIRECTION_PROBE_EVIDENCE = (
    "directional-force-multi-actor-direction-probe-v1"
)

Direction: TypeAlias = tuple[int, int]
CompositionObservationStatus: TypeAlias = Literal[
    "MATCH",
    "UNAVAILABLE",
    "MISMATCH",
]


@dataclass(frozen=True, slots=True)
class _CompositionParameters:
    maximum_search_states: int
    maximum_navigation_states: int
    maximum_plan_actions: int
    maximum_transition_observations: int
    maximum_relation_candidates: int
    relation_heuristic_weight: int
    manipulator_retention_divisor: int
    direction_probe_enabled: int
    force_phase_advance_on_move: int
    force_phase_advance_on_select: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _CompositionParameters | None:
        if instruction.operator_id != DIRECTIONAL_FORCE_ROUTE_OPERATOR:
            return None
        raw = instruction.parameters()
        enabled = raw.get("multi_actor_composition_enabled", 0)
        if (
            isinstance(enabled, bool)
            or not isinstance(enabled, int)
            or enabled != 1
        ):
            return None
        names = (
            "maximum_composition_search_states",
            "maximum_composition_navigation_states",
            "maximum_composition_plan_actions",
            "maximum_composition_transition_observations",
            "maximum_composition_relation_candidates",
            "composition_relation_heuristic_weight",
            "composition_manipulator_retention_divisor",
            "composition_direction_probe_enabled",
            "force_phase_advance_on_move",
            "force_phase_advance_on_select",
        )
        parsed: dict[str, int] = {}
        for name in names:
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                return None
            parsed[name] = value
        if (
            parsed["maximum_composition_search_states"] < 1
            or parsed["maximum_composition_navigation_states"] < 1
            or parsed["maximum_composition_plan_actions"] < 1
            or not 1
            <= parsed["maximum_composition_transition_observations"]
            <= 64
            or parsed["maximum_composition_relation_candidates"] < 1
            or parsed["composition_relation_heuristic_weight"] < 1
            or parsed["composition_manipulator_retention_divisor"] < 1
            or parsed["composition_direction_probe_enabled"] not in {0, 1}
            or parsed["force_phase_advance_on_move"] not in {0, 1}
            or parsed["force_phase_advance_on_select"] not in {0, 1}
            or (
                parsed["force_phase_advance_on_move"] == 0
                and parsed["force_phase_advance_on_select"] == 0
            )
        ):
            return None
        return cls(
            maximum_search_states=parsed[
                "maximum_composition_search_states"
            ],
            maximum_navigation_states=parsed[
                "maximum_composition_navigation_states"
            ],
            maximum_plan_actions=parsed[
                "maximum_composition_plan_actions"
            ],
            maximum_transition_observations=parsed[
                "maximum_composition_transition_observations"
            ],
            maximum_relation_candidates=parsed[
                "maximum_composition_relation_candidates"
            ],
            relation_heuristic_weight=parsed[
                "composition_relation_heuristic_weight"
            ],
            manipulator_retention_divisor=parsed[
                "composition_manipulator_retention_divisor"
            ],
            direction_probe_enabled=parsed[
                "composition_direction_probe_enabled"
            ],
            force_phase_advance_on_move=parsed[
                "force_phase_advance_on_move"
            ],
            force_phase_advance_on_select=parsed[
                "force_phase_advance_on_select"
            ],
        )


@dataclass(frozen=True, slots=True)
class _ComposedState:
    positions: tuple[Position, ...]
    selected: int
    marker_colors: tuple[int | None, ...]
    phase: int


@dataclass(frozen=True, slots=True)
class _ComposedModel:
    multi: _MultiModel
    terrain: Grid
    observation_tail: Grid
    forces: tuple[_ForceBlock, ...]
    entity_masks: tuple[Mask, ...]
    canonical_groups: tuple[tuple[int, ...], ...]
    initial_state: _ComposedState
    directional_parameters: _DirectionalForceParameters
    composition_parameters: _CompositionParameters
    force_directions_observed: bool

    @property
    def multi_count(self) -> int:
        return len(self.multi.entities)

    @property
    def force_period(self) -> int:
        force = self.forces[0]
        return (
            force.height
            if force.direction[0] == 0
            else force.width
        )


@lru_cache(maxsize=131_072)
def _absolute_pixels(
    position: Position,
    mask: Mask,
) -> frozenset[Point]:
    return frozenset(
        (position[0] + dx, position[1] + dy)
        for dx, dy in mask
    )


def _collides(
    first_position: Position,
    first_mask: Mask,
    second_position: Position,
    second_mask: Mask,
) -> bool:
    return not _absolute_pixels(
        first_position,
        first_mask,
    ).isdisjoint(
        _absolute_pixels(second_position, second_mask)
    )


def _canonical_state(
    model: _ComposedModel,
    positions: tuple[Position, ...],
    selected: int,
    marker_colors: tuple[int | None, ...],
    phase: int,
) -> _ComposedState:
    multi_count = model.multi_count
    if (
        len(positions) != multi_count + len(model.forces)
        or len(marker_colors) != multi_count
        or not 0 <= phase < model.force_period
    ):
        raise ValueError("composed directional-force state invalid")
    multi_positions = positions[:multi_count]
    canonical_positions = list(multi_positions)
    canonical_selected = selected
    canonical_markers = list(marker_colors)
    for indices in model.canonical_groups:
        ordered = sorted(
            (
                multi_positions[index],
                marker_colors[index],
            )
            for index in indices
        )
        for index, (_position, marker) in zip(
            indices,
            ordered,
            strict=True,
        ):
            canonical_positions[index] = _position
            canonical_markers[index] = marker
        if selected in indices:
            selected_position = multi_positions[selected]
            canonical_selected = indices[
                tuple(position for position, _marker in ordered).index(
                    selected_position
                )
            ]
    return _ComposedState(
        positions=(
            *tuple(canonical_positions),
            *positions[multi_count:],
        ),
        selected=canonical_selected,
        marker_colors=tuple(canonical_markers),
        phase=phase,
    )


@dataclass(frozen=True, slots=True)
class _ForceGeometry:
    position: Position
    width: int
    height: int
    phase: int
    direction: Direction | None


def _composition_force_blocks(
    grid: Grid,
    parameters: _DirectionalForceParameters,
    *,
    height: int,
    direction_hints: tuple[Direction, ...] | None = None,
    position_hints: tuple[Position, ...] | None = None,
) -> tuple[tuple[_ForceBlock, ...], int, bool] | None:
    """Parse force geometry without treating nearby hazard as direction.

    A non-zero rendered charge band is the direction authority.  A fully
    idle block is intentionally marked unobserved; a deterministic placeholder
    is used only to choose a reversible observation action.  Queued actions
    may supply their prior rendered direction and expected position so an
    idle phase can be reconstructed without identity or hidden state.
    """

    if (direction_hints is None) != (position_hints is None):
        return None
    colors = frozenset(
        {parameters.force_charge_color, parameters.force_idle_color}
    )
    geometries: list[_ForceGeometry] = []
    for component in _union_components(grid[:height], colors):
        x0 = min(x for x, _y in component)
        y0 = min(y for _x, y in component)
        x1 = max(x for x, _y in component)
        y1 = max(y for _x, y in component)
        width = x1 - x0 + 1
        block_height = y1 - y0 + 1
        rectangle = {
            (x, y)
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
        }
        if (
            component != rectangle
            or not parameters.minimum_force_side
            <= min(width, block_height)
            or max(width, block_height)
            > parameters.maximum_force_side
        ):
            return None
        values = tuple(
            tuple(grid[y][x] for x in range(x0, x1 + 1))
            for y in range(y0, y1 + 1)
        )
        unique = {color for row in values for color in row}
        if unique == {parameters.force_idle_color}:
            phase = 0
            direction: Direction | None = None
        else:
            band = _edge_band(
                values,
                charge_color=parameters.force_charge_color,
                idle_color=parameters.force_idle_color,
            )
            if band is None:
                return None
            phase, direction = band
        geometries.append(
            _ForceGeometry(
                position=(x0, y0),
                width=width,
                height=block_height,
                phase=phase,
                direction=direction,
            )
        )
    if not (
        parameters.minimum_force_count
        <= len(geometries)
        <= parameters.maximum_force_count
    ):
        return None
    phases = {geometry.phase for geometry in geometries}
    dimensions = {
        (geometry.width, geometry.height)
        for geometry in geometries
    }
    if len(phases) != 1 or len(dimensions) != 1:
        return None
    phase = next(iter(phases))
    observed = all(
        geometry.direction is not None for geometry in geometries
    )

    ordered: list[tuple[_ForceGeometry, Direction]] = []
    if direction_hints is not None and position_hints is not None:
        if (
            len(direction_hints) != len(position_hints)
            or len(direction_hints) != len(geometries)
            or len(set(position_hints)) != len(position_hints)
        ):
            return None
        by_position = {
            geometry.position: geometry for geometry in geometries
        }
        for position, direction in zip(
            position_hints,
            direction_hints,
            strict=True,
        ):
            if direction not in {
                (0, -1),
                (0, 1),
                (-1, 0),
                (1, 0),
            }:
                return None
            geometry = by_position.get(position)
            if (
                geometry is None
                or (
                    geometry.direction is not None
                    and geometry.direction != direction
                )
            ):
                return None
            ordered.append((geometry, direction))
    elif observed:
        ordered = sorted(
            (
                (geometry, geometry.direction)
                for geometry in geometries
                if geometry.direction is not None
            ),
            key=lambda item: (
                item[1],
                item[0].position[1],
                item[0].position[0],
            ),
        )
    else:
        fallback = _force_blocks(
            grid,
            parameters,
            height=height,
        )
        fallback_directions = (
            {}
            if fallback is None
            else {
                force.position: force.direction
                for force in fallback[0]
            }
        )
        ordered = [
            (
                geometry,
                fallback_directions.get(
                    geometry.position,
                    (0, -1),
                ),
            )
            for geometry in sorted(
                geometries,
                key=lambda item: (
                    item.position[1],
                    item.position[0],
                ),
            )
        ]
    forces = tuple(
        _ForceBlock(
            position=geometry.position,
            width=geometry.width,
            height=geometry.height,
            direction=direction,
        )
        for geometry, direction in ordered
    )
    periods = {
        force.height if force.direction[0] == 0 else force.width
        for force in forces
    }
    if len(periods) != 1 or phase >= next(iter(periods)):
        return None
    return forces, phase, observed


def _composed_model(
    grid: Grid,
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
    *,
    force_direction_hints: tuple[Direction, ...] | None = None,
    force_position_hints: tuple[Position, ...] | None = None,
    playable_height_hint: int | None = None,
) -> _ComposedModel | None:
    directional_parameters = (
        _DirectionalForceParameters.from_instruction(
            directional_instruction
        )
    )
    composition_parameters = _CompositionParameters.from_instruction(
        directional_instruction
    )
    multi_parameters = _MultiParameters.from_instruction(multi_instruction)
    if (
        directional_parameters is None
        or composition_parameters is None
        or multi_parameters is None
        or directional_parameters.click_action
        != multi_parameters.click_action
        or directional_parameters.up_action != multi_parameters.up_action
        or directional_parameters.down_action != multi_parameters.down_action
        or directional_parameters.left_action
        != multi_parameters.left_action
        or directional_parameters.right_action
        != multi_parameters.right_action
        or directional_parameters.selected_marker_color
        != multi_parameters.selected_marker_color
        or directional_parameters.unselected_marker_color
        != multi_parameters.unselected_marker_color
        or directional_parameters.released_marker_color
        != multi_parameters.released_marker_color
        or directional_parameters.hazard_color
        != multi_parameters.push_through_color
        or directional_parameters.minimum_push_steps
        != multi_parameters.minimum_push_steps
        or directional_parameters.maximum_push_steps
        != multi_parameters.maximum_push_steps
    ):
        return None
    multi = _multi_model(
        grid,
        multi_parameters,
        playable_height_hint=playable_height_hint,
    )
    if multi is None:
        return None
    parsed_forces = _composition_force_blocks(
        grid,
        directional_parameters,
        height=multi.height,
        direction_hints=force_direction_hints,
        position_hints=force_position_hints,
    )
    if parsed_forces is None:
        return None
    forces, phase, force_directions_observed = parsed_forces
    terrain = [list(row) for row in multi.terrain]
    for force in forces:
        for x, y in _absolute_pixels(force.position, force.mask):
            if not 0 <= x < multi.width or not 0 <= y < multi.height:
                return None
            terrain[y][x] = multi.walkable_color
    initial = _ComposedState(
        positions=(
            *multi.initial_positions,
            *(force.position for force in forces),
        ),
        selected=multi.selected_index,
        marker_colors=tuple(
            (
                entity.marker_color
                if entity.selectable
                else None
            )
            for entity in multi.entities
        ),
        phase=phase,
    )
    provisional = _ComposedModel(
        multi=multi,
        terrain=tuple(tuple(row) for row in terrain),
        observation_tail=grid[multi.height :],
        forces=forces,
        entity_masks=(
            *(entity.mask for entity in multi.entities),
            *(force.mask for force in forces),
        ),
        canonical_groups=multi.canonical_groups,
        initial_state=initial,
        directional_parameters=directional_parameters,
        composition_parameters=composition_parameters,
        force_directions_observed=force_directions_observed,
    )
    try:
        canonical = _canonical_state(
            provisional,
            initial.positions,
            initial.selected,
            initial.marker_colors,
            initial.phase,
        )
    except ValueError:
        return None
    if canonical != initial:
        return None
    return provisional


def _terrain_passable(
    model: _ComposedModel,
    position: Position,
    mask: Mask,
    *,
    pushed: bool,
) -> bool:
    passable = {
        model.multi.walkable_color,
        *model.multi.target_colors,
    }
    if pushed:
        passable.add(model.directional_parameters.hazard_color)
    for x, y in _absolute_pixels(position, mask):
        if (
            x < 0
            or y < 0
            or x >= model.multi.width
            or y >= model.multi.height
            or model.terrain[y][x] not in passable
        ):
            return False
    return True


def _on_hazard(
    model: _ComposedModel,
    position: Position,
    mask: Mask,
) -> bool:
    return any(
        model.terrain[y][x]
        == model.directional_parameters.hazard_color
        for x, y in _absolute_pixels(position, mask)
        if 0 <= x < model.multi.width and 0 <= y < model.multi.height
    )


def _move_entity_once(
    model: _ComposedModel,
    positions: list[Position],
    index: int,
    delta: Direction,
    protected: frozenset[int],
) -> bool:
    if index in protected:
        return False
    masks = model.entity_masks
    next_position = (
        positions[index][0] + delta[0],
        positions[index][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        next_position,
        masks[index],
        pushed=True,
    ):
        return False
    collided = tuple(
        other
        for other, position in enumerate(positions)
        if (
            other != index
            and _collides(
                next_position,
                masks[index],
                position,
                masks[other],
            )
        )
    )
    working = list(positions)
    for other in collided:
        if not _move_entity_once(
            model,
            working,
            other,
            delta,
            protected | {index},
        ):
            return False
    if any(
        other != index
        and _collides(
            next_position,
            masks[index],
            position,
            masks[other],
        )
        for other, position in enumerate(working)
    ):
        return False
    working[index] = next_position
    positions[:] = working
    return True


def _movement_deltas(
    model: _ComposedModel,
) -> tuple[tuple[int, Direction], ...]:
    stride = model.multi.stride
    parameters = model.directional_parameters
    return (
        (parameters.up_action, (0, -stride)),
        (parameters.down_action, (0, stride)),
        (parameters.left_action, (-stride, 0)),
        (parameters.right_action, (stride, 0)),
    )


def _normal_move(
    model: _ComposedModel,
    state: _ComposedState,
    delta: Direction,
) -> tuple[Position, ...]:
    positions = state.positions
    selected = state.selected
    masks = model.entity_masks
    actor_next = (
        positions[selected][0] + delta[0],
        positions[selected][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        actor_next,
        masks[selected],
        pushed=False,
    ):
        return positions
    collided = tuple(
        index
        for index, position in enumerate(positions)
        if (
            index != selected
            and _collides(
                actor_next,
                masks[selected],
                position,
                masks[index],
            )
        )
    )
    mutable = list(positions)
    if not collided:
        mutable[selected] = actor_next
        return tuple(mutable)
    for push_step in range(
        model.directional_parameters.maximum_push_steps
    ):
        working = list(mutable)
        moved = False
        for index in collided:
            before = working[index]
            if not _move_entity_once(
                model,
                working,
                index,
                delta,
                frozenset({selected}),
            ):
                moved = False
                break
            moved = moved or before != working[index]
        if not moved:
            break
        mutable = working
        if (
            push_step + 1
            >= model.directional_parameters.minimum_push_steps
            and all(
                not _on_hazard(
                    model,
                    mutable[index],
                    masks[index],
                )
                for index in collided
            )
        ):
            break
    return tuple(mutable)


def _adjacent_on_force_side(
    *,
    entity_position: Position,
    entity_mask: Mask,
    force_position: Position,
    force_mask: Mask,
    direction: Direction,
) -> bool:
    entity_pixels = _absolute_pixels(entity_position, entity_mask)
    shifted_force_edge = {
        (x + direction[0], y + direction[1])
        for x, y in _absolute_pixels(force_position, force_mask)
    }
    return not entity_pixels.isdisjoint(shifted_force_edge)


def _apply_forces(
    model: _ComposedModel,
    positions: list[Position],
) -> None:
    masks = model.entity_masks
    force_offset = model.multi_count
    stride = model.multi.stride
    for local_index, force in enumerate(model.forces):
        force_index = force_offset + local_index
        direction = (
            force.direction[0] * stride,
            force.direction[1] * stride,
        )
        affected = tuple(
            index
            for index in range(len(positions))
            if (
                index != force_index
                and _adjacent_on_force_side(
                    entity_position=positions[index],
                    entity_mask=masks[index],
                    force_position=positions[force_index],
                    force_mask=masks[force_index],
                    direction=force.direction,
                )
            )
        )
        for index in affected:
            moved_steps = 0
            while (
                moved_steps
                < model.directional_parameters.force_expansion_steps
                or _on_hazard(
                    model,
                    positions[index],
                    masks[index],
                )
            ):
                if (
                    moved_steps
                    >= model.directional_parameters.maximum_push_steps
                ):
                    break
                if not _move_entity_once(
                    model,
                    positions,
                    index,
                    direction,
                    frozenset({force_index}),
                ):
                    break
                moved_steps += 1


def _advance_phase(
    model: _ComposedModel,
    positions: list[Position],
    phase: int,
    amount: int,
) -> int:
    next_phase = phase + amount
    if next_phase >= model.force_period:
        _apply_forces(model, positions)
        return 0
    return next_phase


def _transition(
    model: _ComposedModel,
    state: _ComposedState,
    action: SearchAction,
) -> _ComposedState:
    kind, value = action
    if kind == "move":
        return _movement_transition(model, state, value)[0]
    positions = list(state.positions)
    selected = state.selected
    markers = list(state.marker_colors)
    if value not in model.multi.selectable_indices:
        return state
    if value != selected:
        markers[selected] = (
            model.directional_parameters.released_marker_color
        )
        markers[value] = (
            model.directional_parameters.selected_marker_color
        )
        selected = value
    phase = _advance_phase(
        model,
        positions,
        state.phase,
        model.composition_parameters.force_phase_advance_on_select,
    )
    return _canonical_state(
        model,
        tuple(positions),
        selected,
        tuple(markers),
        phase,
    )


def _movement_transition(
    model: _ComposedModel,
    state: _ComposedState,
    action_id: int,
) -> tuple[_ComposedState, tuple[Position, ...]]:
    delta = dict(_movement_deltas(model)).get(action_id)
    if delta is None:
        return state, state.positions
    normal_positions = _normal_move(model, state, delta)
    positions = list(normal_positions)
    phase = _advance_phase(
        model,
        positions,
        state.phase,
        model.composition_parameters.force_phase_advance_on_move,
    )
    return (
        _canonical_state(
            model,
            tuple(positions),
            state.selected,
            state.marker_colors,
            phase,
        ),
        normal_positions,
    )


def _multi_state(
    model: _ComposedModel,
    state: _ComposedState,
) -> MultiShapeState:
    return (
        state.positions[: model.multi_count],
        state.selected,
    )


def _is_goal(
    model: _ComposedModel,
    state: _ComposedState,
) -> bool:
    return _multi_is_goal(model.multi, _multi_state(model, state))


def _heuristic(
    model: _ComposedModel,
    state: _ComposedState,
) -> int:
    distance = _multi_heuristic(
        model.multi,
        _multi_state(model, state),
    )
    return (
        distance
        + model.directional_parameters.force_expansion_steps
        - 1
    ) // model.directional_parameters.force_expansion_steps


def _goal_bits(
    model: _ComposedModel,
    state: _ComposedState,
) -> tuple[bool, ...]:
    positions = state.positions[: model.multi_count]
    bits = [False] * model.multi_count
    for indices, goals in model.multi.goal_families:
        remaining = list(goals)
        for index in indices:
            position = positions[index]
            if position in remaining:
                bits[index] = True
                remaining.remove(position)
    return tuple(bits)


@lru_cache(maxsize=4096)
def _mask_bounds(mask: Mask) -> tuple[int, int, int, int]:
    return (
        min(x for x, _y in mask),
        min(y for _x, y in mask),
        max(x for x, _y in mask),
        max(y for _x, y in mask),
    )


def _rectangle_gap(
    first_position: Position,
    first_mask: Mask,
    second_position: Position,
    second_mask: Mask,
) -> int:
    first_dx0, first_dy0, first_dx1, first_dy1 = _mask_bounds(
        first_mask
    )
    second_dx0, second_dy0, second_dx1, second_dy1 = _mask_bounds(
        second_mask
    )
    first_x0 = first_position[0] + first_dx0
    first_x1 = first_position[0] + first_dx1
    first_y0 = first_position[1] + first_dy0
    first_y1 = first_position[1] + first_dy1
    second_x0 = second_position[0] + second_dx0
    second_x1 = second_position[0] + second_dx1
    second_y0 = second_position[1] + second_dy0
    second_y1 = second_position[1] + second_dy1
    return (
        max(0, first_x0 - second_x1, second_x0 - first_x1)
        + max(0, first_y0 - second_y1, second_y0 - first_y1)
    )


def _relational_heuristic(
    model: _ComposedModel,
    state: _ComposedState,
) -> int:
    """Estimate obligation order without task identity or coordinates."""

    bits = _goal_bits(model, state)
    passive_indices = tuple(
        index
        for index, entity in enumerate(model.multi.entities)
        if not entity.selectable and not bits[index]
    )
    if not passive_indices:
        return _multi_heuristic(
            model.multi,
            _multi_state(model, state),
        )

    distance = 0
    for entity_index in passive_indices:
        goals = next(
            goals
            for indices, goals in model.multi.goal_families
            if entity_index in indices
        )
        position = state.positions[entity_index]
        distance += min(
            abs(position[0] - goal[0])
            + abs(position[1] - goal[1])
            for goal in goals
        ) // model.multi.stride

    settled_manipulators = sum(
        entity.selectable and bits[index]
        for index, entity in enumerate(model.multi.entities)
    )
    distance += (
        settled_manipulators
        * len(passive_indices)
        * max(
            1,
            model.multi.width
            // model.multi.stride
            // model.composition_parameters.manipulator_retention_divisor,
        )
    )

    force_offset = model.multi_count
    for entity_index in passive_indices:
        distance += min(
            _rectangle_gap(
                state.positions[entity_index],
                model.entity_masks[entity_index],
                state.positions[actor_index],
                model.entity_masks[actor_index],
            )
            // model.multi.stride
            for actor_index in model.multi.selectable_indices
        )
        goals = next(
            goals
            for indices, goals in model.multi.goal_families
            if entity_index in indices
        )
        force_gaps: list[int] = []
        for goal in goals:
            vector = (
                goal[0] - state.positions[entity_index][0],
                goal[1] - state.positions[entity_index][1],
            )
            for force_index, force in enumerate(model.forces):
                if (
                    vector[0] * force.direction[0]
                    + vector[1] * force.direction[1]
                    <= 0
                ):
                    continue
                force_position = state.positions[
                    force_offset + force_index
                ]
                shifted_position = (
                    force_position[0] + force.direction[0],
                    force_position[1] + force.direction[1],
                )
                force_gaps.append(
                    _rectangle_gap(
                        state.positions[entity_index],
                        model.entity_masks[entity_index],
                        shifted_position,
                        force.mask,
                    )
                    // model.multi.stride
                )
        if force_gaps:
            distance += min(force_gaps)
    return distance


def _contact_profile(
    model: _ComposedModel,
    state: _ComposedState,
    indices: tuple[int, ...],
) -> tuple[tuple[int, int, int], ...]:
    selected = state.selected
    selected_dx0, selected_dy0, selected_dx1, selected_dy1 = (
        _mask_bounds(model.entity_masks[selected])
    )
    selected_position = state.positions[selected]
    selected_x0 = selected_position[0] + selected_dx0
    selected_x1 = selected_position[0] + selected_dx1
    selected_y0 = selected_position[1] + selected_dy0
    selected_y1 = selected_position[1] + selected_dy1
    profile: list[tuple[int, int, int]] = []
    for index in indices:
        dx0, dy0, dx1, dy1 = _mask_bounds(model.entity_masks[index])
        position = state.positions[index]
        x0 = position[0] + dx0
        x1 = position[0] + dx1
        y0 = position[1] + dy0
        y1 = position[1] + dy1
        profile.append(
            (
                index,
                max(
                    0,
                    min(selected_x1, x1)
                    - max(selected_x0, x0)
                    + 1,
                ),
                max(
                    0,
                    min(selected_y1, y1)
                    - max(selected_y0, y0)
                    + 1,
                ),
            )
        )
    return tuple(profile)


def _event_signature(
    model: _ComposedModel,
    current: _ComposedState,
    successor: _ComposedState,
    normal: tuple[Position, ...],
    action_id: int,
) -> tuple[object, ...] | None:
    pushed = tuple(
        (
            index,
            normal[index][0] - current.positions[index][0],
            normal[index][1] - current.positions[index][1],
        )
        for index in range(len(normal))
        if (
            index != current.selected
            and normal[index] != current.positions[index]
        )
    )
    forced = tuple(
        (
            index,
            successor.positions[index][0] - normal[index][0],
            successor.positions[index][1] - normal[index][1],
        )
        for index in range(len(normal))
        if successor.positions[index] != normal[index]
    )
    goal_delta = tuple(
        (index, before, after)
        for index, (before, after) in enumerate(
            zip(
                _goal_bits(model, current),
                _goal_bits(model, successor),
                strict=True,
            )
        )
        if before != after
    )
    if not pushed and not forced and not goal_delta:
        return None
    affected = tuple(
        sorted(
            {
                index
                for index, _dx, _dy in (*pushed, *forced)
                if index != current.selected
            }
        )
    )
    return (
        current.selected,
        action_id,
        pushed,
        forced,
        goal_delta,
        successor.phase,
        _contact_profile(model, successor, affected),
    )


def _event_rank(
    model: _ComposedModel,
    state: _ComposedState,
    path: tuple[SearchAction, ...],
) -> tuple[object, ...]:
    return (
        -sum(_goal_bits(model, state)),
        _relational_heuristic(model, state),
        len(path),
        state.positions,
        state.selected,
        state.phase,
    )


def _macro_events(
    model: _ComposedModel,
    start: _ComposedState,
    remaining_actions: int,
) -> tuple[
    tuple[_ComposedState, tuple[SearchAction, ...]],
    ...,
]:
    movement: tuple[SearchAction, ...] = tuple(
        ("move", action_id)
        for action_id, _delta in _movement_deltas(model)
    )
    queue: deque[
        tuple[_ComposedState, tuple[SearchAction, ...]]
    ] = deque(((start, ()),))
    visited = {start}
    found: dict[
        tuple[object, ...],
        list[tuple[_ComposedState, tuple[SearchAction, ...]]],
    ] = {}
    while (
        queue
        and len(visited)
        < model.composition_parameters.maximum_navigation_states
    ):
        state, path = queue.popleft()
        if len(path) >= remaining_actions:
            continue
        for action in movement:
            successor, normal = _movement_transition(
                model,
                state,
                action[1],
            )
            if successor == state:
                continue
            next_path = (*path, action)
            signature = _event_signature(
                model,
                state,
                successor,
                normal,
                action[1],
            )
            if signature is not None:
                candidates = found.setdefault(signature, [])
                existing = next(
                    (
                        index
                        for index, candidate in enumerate(candidates)
                        if candidate[0] == successor
                    ),
                    None,
                )
                if existing is not None:
                    if len(next_path) >= len(candidates[existing][1]):
                        continue
                    candidates.pop(existing)
                candidates.append((successor, next_path))
                candidates.sort(
                    key=lambda item: _event_rank(
                        model,
                        item[0],
                        item[1],
                    )
                )
                del candidates[
                    model.composition_parameters.maximum_relation_candidates :
                ]
                continue
            if successor not in visited:
                visited.add(successor)
                queue.append((successor, next_path))
    return tuple(
        sorted(
            (
                candidate
                for candidates in found.values()
                for candidate in candidates
            ),
            key=lambda item: _event_rank(
                model,
                item[0],
                item[1],
            ),
        )
    )


def _search(
    model: _ComposedModel,
) -> tuple[SearchAction, ...]:
    start = model.initial_state
    if _is_goal(model, start):
        return ()
    serial = itertools.count()
    frontier: list[tuple[int, int, int, _ComposedState]] = [
        (
            model.composition_parameters.relation_heuristic_weight
            * _relational_heuristic(model, start),
            0,
            next(serial),
            start,
        )
    ]
    best = {start: 0}
    parent: dict[
        _ComposedState,
        tuple[_ComposedState, tuple[SearchAction, ...]],
    ] = {}
    event_cache: dict[
        tuple[_ComposedState, int],
        tuple[
            tuple[_ComposedState, tuple[SearchAction, ...]],
            ...,
        ],
    ] = {}
    found: _ComposedState | None = None
    while (
        frontier
        and len(best)
        < model.composition_parameters.maximum_search_states
    ):
        _priority, cost, _order, state = heapq.heappop(frontier)
        if cost != best[state]:
            continue
        if _is_goal(model, state):
            found = state
            break
        if cost >= model.composition_parameters.maximum_plan_actions:
            continue
        remaining = (
            model.composition_parameters.maximum_plan_actions - cost
        )
        edges: list[
            tuple[_ComposedState, tuple[SearchAction, ...]]
        ] = []
        for index in model.multi.selectable_indices:
            if index == state.selected:
                continue
            action: SearchAction = ("select", index)
            successor = _transition(model, state, action)
            if successor != state:
                edges.append((successor, (action,)))
        cache_key = (state, remaining)
        movement_edges = event_cache.get(cache_key)
        if movement_edges is None:
            movement_edges = _macro_events(
                model,
                state,
                remaining,
            )
            event_cache[cache_key] = movement_edges
        edges.extend(movement_edges)
        for next_state, path in edges:
            if (
                len(best)
                >= model.composition_parameters.maximum_search_states
            ):
                break
            next_cost = cost + len(path)
            if (
                next_cost
                > model.composition_parameters.maximum_plan_actions
                or next_cost >= best.get(next_state, 2**31)
            ):
                continue
            best[next_state] = next_cost
            parent[next_state] = (state, path)
            heapq.heappush(
                frontier,
                (
                    next_cost
                    + (
                        model.composition_parameters.relation_heuristic_weight
                        * _relational_heuristic(model, next_state)
                    ),
                    next_cost,
                    next(serial),
                    next_state,
                ),
            )
    if found is None:
        return ()
    reverse: list[tuple[SearchAction, ...]] = []
    cursor = found
    while cursor != start:
        previous, path = parent[cursor]
        reverse.append(path)
        cursor = previous
    return tuple(
        action
        for path in reversed(reverse)
        for action in path
    )


def _direction_probe_action(
    model: _ComposedModel,
) -> SearchAction | None:
    if (
        model.force_directions_observed
        or not model.composition_parameters.direction_probe_enabled
        or model.initial_state.phase != 0
    ):
        return None
    deltas = dict(_movement_deltas(model))
    actions_by_delta = {
        delta: action_id for action_id, delta in deltas.items()
    }
    candidates: list[
        tuple[int, int, int, _ComposedState, SearchAction]
    ] = []
    start = model.initial_state
    for action_id, delta in _movement_deltas(model):
        action: SearchAction = ("move", action_id)
        successor = _transition(model, start, action)
        if (
            successor == start
            or successor.phase != 1
            or any(
                successor.positions[index] != start.positions[index]
                for index in range(len(start.positions))
                if index != start.selected
            )
        ):
            continue
        opposite_action = actions_by_delta.get((-delta[0], -delta[1]))
        if opposite_action is None:
            continue
        reverse_positions = _normal_move(
            model,
            successor,
            deltas[opposite_action],
        )
        if reverse_positions != start.positions:
            continue
        successor_goal_bits = _goal_bits(model, successor)
        passive_gap = sum(
            _rectangle_gap(
                successor.positions[index],
                model.entity_masks[index],
                successor.positions[successor.selected],
                model.entity_masks[successor.selected],
            )
            for index, entity in enumerate(model.multi.entities)
            if not entity.selectable and not successor_goal_bits[index]
        )
        candidates.append(
            (
                _multi_heuristic(
                    model.multi,
                    _multi_state(model, successor),
                ),
                passive_gap,
                action_id,
                successor,
                action,
            )
        )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (item[0], item[1], item[2]),
    )[4]


def _static_payload(model: _ComposedModel) -> dict[str, object]:
    return {
        "width": model.multi.width,
        "height": model.multi.height,
        "stride": model.multi.stride,
        "walkable_color": model.multi.walkable_color,
        "target_colors": sorted(model.multi.target_colors),
        "entities": [
            {
                "selectable": entity.selectable,
                "color": entity.color,
                "width": entity.width,
                "height": entity.height,
                "mask": entity.mask,
            }
            for entity in model.multi.entities
        ],
        "goal_families": [
            {
                "indices": indices,
                "goals": goals,
            }
            for indices, goals in model.multi.goal_families
        ],
        "forces": [
            {
                "width": force.width,
                "height": force.height,
                "direction": force.direction,
                "mask": force.mask,
            }
            for force in model.forces
        ],
    }


def _state_payload(
    model: _ComposedModel,
    state: _ComposedState,
) -> dict[str, object]:
    return {
        "positions": state.positions,
        "selected": state.selected,
        "phase": state.phase,
        "multi_count": model.multi_count,
    }


def _projected_state(
    model: _ComposedModel,
    state: _ComposedState,
) -> tuple[tuple[Position, ...], int, int]:
    return state.positions, state.selected, state.phase


def _render_state(
    model: _ComposedModel,
    state: _ComposedState,
) -> Grid:
    """Render a model state for deterministic transition verification."""

    grid = [list(row) for row in model.terrain]
    for index, entity in enumerate(model.multi.entities):
        x0, y0 = state.positions[index]
        for dx, dy in entity.mask:
            grid[y0 + dy][x0 + dx] = entity.color
        marker = state.marker_colors[index]
        if marker is None:
            continue
        marker_width = (
            entity.width // model.directional_parameters.marker_divisor
        )
        marker_height = (
            entity.height // model.directional_parameters.marker_divisor
        )
        marker_x0 = x0 + (entity.width - marker_width) // 2
        marker_y0 = y0 + (entity.height - marker_height) // 2
        for y in range(marker_y0, marker_y0 + marker_height):
            for x in range(marker_x0, marker_x0 + marker_width):
                grid[y][x] = marker
    for local_index, force in enumerate(model.forces):
        position = state.positions[model.multi_count + local_index]
        for dy in range(force.height):
            for dx in range(force.width):
                charged = (
                    (
                        force.direction == (0, 1)
                        and dy < state.phase
                    )
                    or (
                        force.direction == (0, -1)
                        and dy >= force.height - state.phase
                    )
                    or (
                        force.direction == (1, 0)
                        and dx < state.phase
                    )
                    or (
                        force.direction == (-1, 0)
                        and dx >= force.width - state.phase
                    )
                )
                grid[position[1] + dy][position[0] + dx] = (
                    model.directional_parameters.force_charge_color
                    if charged
                    else model.directional_parameters.force_idle_color
                )
    return (
        *(tuple(row) for row in grid),
        *model.observation_tail,
    )


def _actor_normalization(
    model: _ComposedModel,
    state: _ComposedState,
) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        sorted(
            (
                state.positions[index][0] + dx,
                state.positions[index][1] + dy,
                entity.color,
            )
            for index, entity in enumerate(model.multi.entities)
            if entity.selectable
            for dx, dy in entity.mask
        )
    )


def _normalized_visible_digest(
    grid: Grid,
    *,
    playable_height: int,
    normalization: tuple[tuple[int, int, int], ...],
    parameters: _DirectionalForceParameters,
) -> str | None:
    if (
        isinstance(playable_height, bool)
        or not 1 <= playable_height <= len(grid)
        or not grid
        or not grid[0]
    ):
        return None
    width = len(grid[0])
    if any(len(row) != width for row in grid[:playable_height]):
        return None
    coordinates = tuple((x, y) for x, y, _color in normalization)
    if len(set(coordinates)) != len(coordinates):
        return None
    normalized = [
        [int(value) for value in row]
        for row in grid[:playable_height]
    ]
    marker_colors = {
        parameters.selected_marker_color,
        parameters.unselected_marker_color,
        parameters.released_marker_color,
    }
    for x, y, base_color in normalization:
        if not 0 <= x < width or not 0 <= y < playable_height:
            return None
        if normalized[y][x] in {*marker_colors, base_color}:
            normalized[y][x] = base_color
    return digest_object(tuple(tuple(row) for row in normalized))


def _transition_digest(
    *,
    static_digest: str,
    current: dict[str, object],
    action: SearchAction,
    successor: dict[str, object],
    current_visible_digest: str,
    successor_visible_digest: str,
    current_actor_normalization: tuple[tuple[int, int, int], ...],
    successor_actor_normalization: tuple[tuple[int, int, int], ...],
    force_directions: tuple[Direction, ...],
    playable_height: int,
) -> str:
    return digest_object(
        {
            "format": COMPOSITION_EVIDENCE,
            "static": static_digest,
            "current": current,
            "action": action,
            "successor": successor,
            "current_visible_digest": current_visible_digest,
            "successor_visible_digest": successor_visible_digest,
            "current_actor_normalization": current_actor_normalization,
            "successor_actor_normalization": (
                successor_actor_normalization
            ),
            "force_directions": force_directions,
            "playable_height": playable_height,
        }
    )


def _visual_action(
    model: _ComposedModel,
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
    *,
    state: _ComposedState,
    action: SearchAction,
    index: int,
    plan_digest: str,
    direction_probe: bool = False,
) -> VisualAction:
    successor = _transition(model, state, action)
    current_payload = _state_payload(model, state)
    successor_payload = _state_payload(model, successor)
    static_digest = digest_object(_static_payload(model))
    current_actor_normalization = _actor_normalization(model, state)
    successor_actor_normalization = _actor_normalization(
        model,
        successor,
    )
    current_visible_digest = _normalized_visible_digest(
        _render_state(model, state),
        playable_height=model.multi.height,
        normalization=current_actor_normalization,
        parameters=model.directional_parameters,
    )
    successor_visible_digest = _normalized_visible_digest(
        _render_state(model, successor),
        playable_height=model.multi.height,
        normalization=successor_actor_normalization,
        parameters=model.directional_parameters,
    )
    if current_visible_digest is None or successor_visible_digest is None:
        raise ValueError("composed visible projection invalid")
    transition_digest = _transition_digest(
        static_digest=static_digest,
        current=current_payload,
        action=action,
        successor=successor_payload,
        current_visible_digest=current_visible_digest,
        successor_visible_digest=successor_visible_digest,
        current_actor_normalization=current_actor_normalization,
        successor_actor_normalization=successor_actor_normalization,
        force_directions=tuple(
            force.direction for force in model.forces
        ),
        playable_height=model.multi.height,
    )
    evidence = (
        DIRECTIONAL_FORCE_ROUTE_OPERATOR,
        f"operator-prototype:{DIRECTIONAL_FORCE_ROUTE_OPERATOR}",
        COMPOSITION_EVIDENCE,
        MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
        "rendered-multi-actor-shape-target-relation",
        "rendered-directional-charge-band",
        "bounded-composed-obligation-search",
        "observation-derived-selection-point",
        "directional-force-composition-directional-instruction:"
        + digest_object(directional_instruction),
        "directional-force-composition-multi-instruction:"
        + digest_object(multi_instruction),
        "directional-force-composition-static:" + static_digest,
        "directional-force-composition-action:"
        + json.dumps(action, separators=(",", ":")),
        "directional-force-composition-current:"
        + json.dumps(
            current_payload,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "directional-force-composition-successor:"
        + json.dumps(
            successor_payload,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "directional-force-composition-transition:"
        + transition_digest,
        (
            "directional-force-composition-current-visible:"
            + current_visible_digest
        ),
        (
            "directional-force-composition-successor-visible:"
            + successor_visible_digest
        ),
        "directional-force-composition-current-actor-normalization:"
        + json.dumps(
            current_actor_normalization,
            separators=(",", ":"),
        ),
        "directional-force-composition-successor-actor-normalization:"
        + json.dumps(
            successor_actor_normalization,
            separators=(",", ":"),
        ),
        "directional-force-composition-directions:"
        + json.dumps(
            tuple(force.direction for force in model.forces),
            separators=(",", ":"),
        ),
        (
            "directional-force-composition-playable-height:"
            f"{model.multi.height}"
        ),
        "directional-force-composition-plan:" + plan_digest,
        f"directional-force-composition-index:{index}",
        *((DIRECTION_PROBE_EVIDENCE,) if direction_probe else ()),
        *directional_instruction.provenance,
        *multi_instruction.provenance,
    )
    kind, value = action
    payload = {
        "operator": DIRECTIONAL_FORCE_ROUTE_OPERATOR,
        "composition": COMPOSITION_EVIDENCE,
        "plan": plan_digest,
        "index": index,
        "state": current_payload,
        "action": action,
        "direction_probe": direction_probe,
    }
    if kind == "move":
        return VisualAction(
            key="semantic-directional-force-composed:"
            + digest_object(payload)[:20],
            action_id=value,
            group=0,
            evidence=evidence,
        )
    entity = model.multi.entities[value]
    position = state.positions[value]
    point = (
        position[0] + entity.width // 2,
        position[1] + entity.height // 2,
    )
    return VisualAction(
        key="semantic-directional-force-composed:"
        + digest_object({**payload, "point": point})[:20],
        action_id=directional_instruction.action_id,
        group=0,
        x=point[0],
        y=point[1],
        evidence=evidence,
    )


def directional_force_multi_actor_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Return a bounded plan from the composed rendered state model."""

    model = _composed_model(
        grid,
        directional_instruction,
        multi_instruction,
    )
    if model is None:
        return ()
    required = {
        model.directional_parameters.click_action,
        model.directional_parameters.up_action,
        model.directional_parameters.down_action,
        model.directional_parameters.left_action,
        model.directional_parameters.right_action,
    }
    if not required.issubset(available_actions):
        return ()
    probe_action = _direction_probe_action(model)
    if probe_action is not None:
        plan_digest = digest_object(
            {
                "operator": DIRECTIONAL_FORCE_ROUTE_OPERATOR,
                "composition": COMPOSITION_EVIDENCE,
                "kind": DIRECTION_PROBE_EVIDENCE,
                "static": _static_payload(model),
                "initial": _state_payload(model, model.initial_state),
                "action": probe_action,
            }
        )
        return (
            _visual_action(
                model,
                directional_instruction,
                multi_instruction,
                state=model.initial_state,
                action=probe_action,
                index=0,
                plan_digest=plan_digest,
                direction_probe=True,
            ),
        )
    if not model.force_directions_observed:
        return ()
    search_plan = _search(model)
    if not search_plan:
        return ()
    plan_digest = digest_object(
        {
            "operator": DIRECTIONAL_FORCE_ROUTE_OPERATOR,
            "composition": COMPOSITION_EVIDENCE,
            "static": _static_payload(model),
            "initial": _state_payload(model, model.initial_state),
            "actions": search_plan,
        }
    )
    state = model.initial_state
    actions: list[VisualAction] = []
    for index, action in enumerate(search_plan):
        actions.append(
            _visual_action(
                model,
                directional_instruction,
                multi_instruction,
                state=state,
                action=action,
                index=index,
                plan_digest=plan_digest,
            )
        )
        state = _transition(model, state, action)
    if not _is_goal(model, state):
        return ()
    return tuple(actions)


def is_directional_force_multi_actor_action(
    action: VisualAction,
) -> bool:
    """Return whether an action carries the composed-path evidence marker."""

    return COMPOSITION_EVIDENCE in action.evidence


def is_directional_force_multi_actor_probe_action(
    action: VisualAction,
) -> bool:
    """Return whether an action exists only to reveal idle force direction."""

    return DIRECTION_PROBE_EVIDENCE in action.evidence


def directional_force_multi_actor_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the candidate-only bound for a transient composed frame."""

    parameters = _CompositionParameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


def _single_evidence(
    action: VisualAction,
    prefix: str,
) -> str | None:
    values = tuple(
        item.removeprefix(prefix)
        for item in action.evidence
        if item.startswith(prefix)
    )
    return values[0] if len(values) == 1 else None


def _payload_projection(
    value: object,
) -> tuple[tuple[Position, ...], int, int, int] | None:
    if not isinstance(value, dict):
        return None
    raw_positions = value.get("positions")
    selected = value.get("selected")
    phase = value.get("phase")
    multi_count = value.get("multi_count")
    if (
        not isinstance(raw_positions, list)
        or isinstance(selected, bool)
        or not isinstance(selected, int)
        or isinstance(phase, bool)
        or not isinstance(phase, int)
        or isinstance(multi_count, bool)
        or not isinstance(multi_count, int)
    ):
        return None
    positions: list[Position] = []
    for raw_position in raw_positions:
        if (
            not isinstance(raw_position, list)
            or len(raw_position) != 2
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in raw_position
            )
        ):
            return None
        positions.append((raw_position[0], raw_position[1]))
    if (
        not 0 < multi_count <= len(positions)
        or not 0 <= selected < multi_count
        or phase < 0
    ):
        return None
    return tuple(positions), selected, phase, multi_count


def _search_action(value: object) -> SearchAction | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or value[0] not in {"move", "select"}
        or isinstance(value[1], bool)
        or not isinstance(value[1], int)
    ):
        return None
    return value[0], value[1]


def _direction_projection(value: object) -> tuple[Direction, ...] | None:
    if not isinstance(value, list):
        return None
    directions: list[Direction] = []
    for raw_direction in value:
        if (
            not isinstance(raw_direction, list)
            or len(raw_direction) != 2
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in raw_direction
            )
        ):
            return None
        direction = (raw_direction[0], raw_direction[1])
        if direction not in {
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        }:
            return None
        directions.append(direction)
    return tuple(directions)


def _normalization_projection(
    value: object,
) -> tuple[tuple[int, int, int], ...] | None:
    if not isinstance(value, list):
        return None
    normalization: list[tuple[int, int, int]] = []
    for raw_pixel in value:
        if (
            not isinstance(raw_pixel, list)
            or len(raw_pixel) != 3
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in raw_pixel
            )
        ):
            return None
        normalization.append(
            (raw_pixel[0], raw_pixel[1], raw_pixel[2])
        )
    if (
        normalization != sorted(normalization)
        or len({(x, y) for x, y, _color in normalization})
        != len(normalization)
    ):
        return None
    return tuple(normalization)


def _observation_status(
    grid: Grid,
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
    action: VisualAction,
    *,
    successor: bool,
) -> CompositionObservationStatus:
    if not is_directional_force_multi_actor_action(action):
        return "MISMATCH"
    directional_digest = _single_evidence(
        action,
        "directional-force-composition-directional-instruction:",
    )
    multi_digest = _single_evidence(
        action,
        "directional-force-composition-multi-instruction:",
    )
    static_digest = _single_evidence(
        action,
        "directional-force-composition-static:",
    )
    raw_action = _single_evidence(
        action,
        "directional-force-composition-action:",
    )
    raw_current = _single_evidence(
        action,
        "directional-force-composition-current:",
    )
    raw_successor = _single_evidence(
        action,
        "directional-force-composition-successor:",
    )
    transition_digest = _single_evidence(
        action,
        "directional-force-composition-transition:",
    )
    raw_directions = _single_evidence(
        action,
        "directional-force-composition-directions:",
    )
    raw_playable_height = _single_evidence(
        action,
        "directional-force-composition-playable-height:",
    )
    current_visible_digest = _single_evidence(
        action,
        "directional-force-composition-current-visible:",
    )
    successor_visible_digest = _single_evidence(
        action,
        "directional-force-composition-successor-visible:",
    )
    raw_current_normalization = _single_evidence(
        action,
        "directional-force-composition-current-actor-normalization:",
    )
    raw_successor_normalization = _single_evidence(
        action,
        "directional-force-composition-successor-actor-normalization:",
    )
    if None in {
        directional_digest,
        multi_digest,
        static_digest,
        raw_action,
        raw_current,
        raw_successor,
        transition_digest,
        raw_directions,
        raw_playable_height,
        current_visible_digest,
        successor_visible_digest,
        raw_current_normalization,
        raw_successor_normalization,
    }:
        return "MISMATCH"
    assert directional_digest is not None
    assert multi_digest is not None
    assert static_digest is not None
    assert raw_action is not None
    assert raw_current is not None
    assert raw_successor is not None
    assert transition_digest is not None
    assert raw_directions is not None
    assert raw_playable_height is not None
    assert current_visible_digest is not None
    assert successor_visible_digest is not None
    assert raw_current_normalization is not None
    assert raw_successor_normalization is not None
    if (
        directional_digest != digest_object(directional_instruction)
        or multi_digest != digest_object(multi_instruction)
    ):
        return "MISMATCH"
    try:
        action_value = json.loads(raw_action)
        current_value = json.loads(raw_current)
        successor_value = json.loads(raw_successor)
        direction_value = json.loads(raw_directions)
        current_normalization_value = json.loads(
            raw_current_normalization
        )
        successor_normalization_value = json.loads(
            raw_successor_normalization
        )
        playable_height = int(raw_playable_height)
    except (json.JSONDecodeError, ValueError):
        return "MISMATCH"
    search_action = _search_action(action_value)
    current_projection = _payload_projection(current_value)
    successor_projection = _payload_projection(successor_value)
    direction_projection = _direction_projection(direction_value)
    current_normalization = _normalization_projection(
        current_normalization_value
    )
    successor_normalization = _normalization_projection(
        successor_normalization_value
    )
    if (
        search_action is None
        or current_projection is None
        or successor_projection is None
        or direction_projection is None
        or current_normalization is None
        or successor_normalization is None
        or playable_height < 1
        or current_projection[3] != successor_projection[3]
        or _transition_digest(
            static_digest=static_digest,
            current=current_value,
            action=search_action,
            successor=successor_value,
            current_visible_digest=current_visible_digest,
            successor_visible_digest=successor_visible_digest,
            current_actor_normalization=current_normalization,
            successor_actor_normalization=successor_normalization,
            force_directions=direction_projection,
            playable_height=playable_height,
        )
        != transition_digest
    ):
        return "MISMATCH"
    kind, value = search_action
    if (
        (kind == "move" and action.action_id != value)
        or (
            kind == "select"
            and action.action_id != directional_instruction.action_id
        )
    ):
        return "MISMATCH"
    if (
        successor
        and is_directional_force_multi_actor_probe_action(action)
    ):
        return "MISMATCH"
    expected_visible_digest = (
        successor_visible_digest
        if successor
        else current_visible_digest
    )
    expected_normalization = (
        successor_normalization
        if successor
        else current_normalization
    )
    directional_parameters = (
        _DirectionalForceParameters.from_instruction(
            directional_instruction
        )
    )
    if directional_parameters is None:
        return "MISMATCH"
    observed_visible_digest = _normalized_visible_digest(
        grid,
        playable_height=playable_height,
        normalization=expected_normalization,
        parameters=directional_parameters,
    )
    if kind == "move" and observed_visible_digest == expected_visible_digest:
        return "MATCH"
    expected_projection = (
        successor_projection if successor else current_projection
    )
    multi_count = expected_projection[3]
    force_positions = expected_projection[0][multi_count:]
    if len(force_positions) != len(direction_projection):
        return "MISMATCH"
    model = _composed_model(
        grid,
        directional_instruction,
        multi_instruction,
        force_direction_hints=direction_projection,
        force_position_hints=force_positions,
        playable_height_hint=playable_height,
    )
    if model is None:
        return "UNAVAILABLE"
    if (
        digest_object(_static_payload(model)) != static_digest
        or current_projection[3] != model.multi_count
        or len(current_projection[0])
        != model.multi_count + len(model.forces)
        or current_projection[2] >= model.force_period
        or successor_projection[2] >= model.force_period
    ):
        return "MISMATCH"
    expected = expected_projection[:3]
    if _projected_state(model, model.initial_state) != expected:
        return "MISMATCH"
    if not successor:
        predicted = _transition(
            model,
            model.initial_state,
            search_action,
        )
        if _projected_state(model, predicted) != successor_projection[:3]:
            return "MISMATCH"
        if kind == "select":
            if (
                value not in model.multi.selectable_indices
                or action.x is None
                or action.y is None
            ):
                return "MISMATCH"
            entity = model.multi.entities[value]
            position = model.initial_state.positions[value]
            if (action.x, action.y) != (
                position[0] + entity.width // 2,
                position[1] + entity.height // 2,
            ):
                return "MISMATCH"
        elif action.x is not None or action.y is not None:
            return "MISMATCH"
    return "MATCH"


def directional_force_multi_actor_observation_status(
    grid: Grid,
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> CompositionObservationStatus:
    """Classify the stable rendered state before a queued composed action."""

    return _observation_status(
        grid,
        directional_instruction,
        multi_instruction,
        action,
        successor=False,
    )


def directional_force_multi_actor_successor_observation_status(
    grid: Grid,
    directional_instruction: SemanticOperatorInstruction,
    multi_instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> CompositionObservationStatus:
    """Classify the stable rendered state after one composed action."""

    return _observation_status(
        grid,
        directional_instruction,
        multi_instruction,
        action,
        successor=True,
    )


__all__ = [
    "COMPOSITION_EVIDENCE",
    "DIRECTION_PROBE_EVIDENCE",
    "directional_force_multi_actor_observation_status",
    "directional_force_multi_actor_plan",
    "directional_force_multi_actor_successor_observation_status",
    "directional_force_multi_actor_transition_observation_limit",
    "is_directional_force_multi_actor_action",
    "is_directional_force_multi_actor_probe_action",
]
