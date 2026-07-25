"""Rendered directional-force routing across separated goal regions.

The operator closes a rendered relation that the ordinary shape-push model
cannot represent: charged movable blocks propel rendered entities through a
normally impassable band.  Detection, stage selection, and bounded search use
only the current rendered grid and compiled instruction parameters.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass
from typing import Literal, TypeAlias

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object
from .shape_push import (
    Mask,
    Position,
    _absolute_pixels,
    _canonical_positions,
    _shape_push_model,
    _ShapePushModel,
    _ShapePushParameters,
)
from .visual_explorer import Grid, Point, VisualAction

DIRECTIONAL_FORCE_ROUTE_OPERATOR = (
    "directional-force-multi-obligation-route-v1"
)

RoutePositions: TypeAlias = tuple[Position, ...]
Direction: TypeAlias = tuple[int, int]
DirectionalForceObservationStatus: TypeAlias = Literal[
    "MATCH",
    "UNAVAILABLE",
    "MISMATCH",
]


@dataclass(frozen=True, slots=True)
class _DirectionalForceParameters:
    click_action: int
    up_action: int
    down_action: int
    left_action: int
    right_action: int
    selected_marker_color: int
    unselected_marker_color: int
    released_marker_color: int
    marker_divisor: int
    target_inset: int
    minimum_pushable_count: int
    maximum_pushable_count: int
    minimum_target_side: int
    maximum_target_side: int
    minimum_push_steps: int
    maximum_push_steps: int
    hazard_color: int
    force_charge_color: int
    force_idle_color: int
    minimum_force_side: int
    maximum_force_side: int
    minimum_force_count: int
    maximum_force_count: int
    force_expansion_steps: int
    maximum_search_states: int
    maximum_stage_actions: int
    maximum_transition_observations: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _DirectionalForceParameters | None:
        if instruction.operator_id != DIRECTIONAL_FORCE_ROUTE_OPERATOR:
            return None
        raw = instruction.parameters()
        names = (
            "click_action",
            "up_action",
            "down_action",
            "left_action",
            "right_action",
            "selected_marker_color",
            "unselected_marker_color",
            "released_marker_color",
            "marker_divisor",
            "target_inset",
            "minimum_pushable_count",
            "maximum_pushable_count",
            "minimum_target_side",
            "maximum_target_side",
            "minimum_push_steps",
            "maximum_push_steps",
            "hazard_color",
            "force_charge_color",
            "force_idle_color",
            "minimum_force_side",
            "maximum_force_side",
            "minimum_force_count",
            "maximum_force_count",
            "force_expansion_steps",
            "maximum_search_states",
            "maximum_stage_actions",
        )
        parsed: dict[str, int] = {}
        for name in names:
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                return None
            parsed[name] = value
        maximum_transition_observations = raw.get(
            "maximum_transition_observations",
            0,
        )
        if (
            isinstance(maximum_transition_observations, bool)
            or not isinstance(maximum_transition_observations, int)
        ):
            return None
        parsed["maximum_transition_observations"] = (
            maximum_transition_observations
        )
        actions = {
            parsed["up_action"],
            parsed["down_action"],
            parsed["left_action"],
            parsed["right_action"],
        }
        marker_colors = {
            parsed["selected_marker_color"],
            parsed["unselected_marker_color"],
            parsed["released_marker_color"],
        }
        dynamic_colors = {
            parsed["hazard_color"],
            parsed["force_charge_color"],
            parsed["force_idle_color"],
        }
        if (
            instruction.action_id != parsed["click_action"]
            or len(actions) != 4
            or any(
                not 1 <= parsed[name] <= 7
                for name in (
                    "click_action",
                    "up_action",
                    "down_action",
                    "left_action",
                    "right_action",
                )
            )
            or len(marker_colors) != 3
            or len(dynamic_colors) != 3
            or parsed["marker_divisor"] < 2
            or parsed["target_inset"] < 1
            or parsed["minimum_pushable_count"] != 1
            or parsed["maximum_pushable_count"] < 1
            or parsed["minimum_target_side"] < 3
            or parsed["maximum_target_side"]
            < parsed["minimum_target_side"]
            or parsed["minimum_push_steps"] < 1
            or parsed["maximum_push_steps"]
            < parsed["minimum_push_steps"]
            or parsed["minimum_force_side"] < 2
            or parsed["maximum_force_side"]
            < parsed["minimum_force_side"]
            or parsed["minimum_force_count"] < 2
            or parsed["maximum_force_count"]
            < parsed["minimum_force_count"]
            or parsed["force_expansion_steps"] < 1
            or parsed["maximum_search_states"] < 1
            or parsed["maximum_stage_actions"] < 1
            or not 0
            <= parsed["maximum_transition_observations"]
            <= 64
        ):
            return None
        return cls(**parsed)

    def shape_parameters(self) -> _ShapePushParameters:
        return _ShapePushParameters(
            click_action=self.click_action,
            up_action=self.up_action,
            down_action=self.down_action,
            left_action=self.left_action,
            right_action=self.right_action,
            selected_marker_color=self.selected_marker_color,
            unselected_marker_color=self.unselected_marker_color,
            released_marker_color=self.released_marker_color,
            marker_divisor=self.marker_divisor,
            target_inset=self.target_inset,
            minimum_pushable_count=self.minimum_pushable_count,
            maximum_pushable_count=self.maximum_pushable_count,
            minimum_target_side=self.minimum_target_side,
            maximum_target_side=self.maximum_target_side,
            minimum_push_steps=self.minimum_push_steps,
            maximum_push_steps=self.maximum_push_steps,
            push_through_color=self.hazard_color,
            maximum_search_states=self.maximum_search_states,
            maximum_plan_actions=self.maximum_stage_actions,
            maximum_transition_observations=1,
        )


@dataclass(frozen=True, slots=True)
class _ForceBlock:
    position: Position
    width: int
    height: int
    direction: Direction

    @property
    def mask(self) -> Mask:
        return tuple(
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
        )


@dataclass(frozen=True, slots=True)
class _ForceRouteState:
    positions: RoutePositions
    phase: int


@dataclass(frozen=True, slots=True)
class _ForceRouteModel:
    shape: _ShapePushModel
    terrain: Grid
    forces: tuple[_ForceBlock, ...]
    region_items: tuple[tuple[Position, int], ...]
    actor_goal_region: int
    shape_goal_region: int
    transit_region: int
    initial_state: _ForceRouteState
    parameters: _DirectionalForceParameters

    @property
    def region_map(self) -> dict[Position, int]:
        return dict(self.region_items)

    @property
    def entity_masks(self) -> tuple[Mask, ...]:
        return (
            *self.shape.masks,
            *(force.mask for force in self.forces),
        )


def _neighbors4(point: Point, stride: int) -> tuple[Point, ...]:
    x, y = point
    return (
        (x, y - stride),
        (x, y + stride),
        (x - stride, y),
        (x + stride, y),
    )


def _union_components(
    grid: Grid,
    colors: frozenset[int],
) -> tuple[frozenset[Point], ...]:
    remaining = {
        (x, y)
        for y, row in enumerate(grid)
        for x, color in enumerate(row)
        if color in colors
    }
    components: list[frozenset[Point]] = []
    while remaining:
        start = min(remaining, key=lambda point: (point[1], point[0]))
        remaining.remove(start)
        component = {start}
        frontier = [start]
        while frontier:
            x, y = frontier.pop()
            for point in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    frontier.append(point)
        components.append(frozenset(component))
    return tuple(components)


def _edge_band(
    values: tuple[tuple[int, ...], ...],
    *,
    charge_color: int,
    idle_color: int,
) -> tuple[int, Direction] | None:
    height = len(values)
    width = len(values[0])
    candidates: list[tuple[int, Direction]] = []

    def rows_match(count: int, *, leading: bool) -> bool:
        return all(
            color
            == (
                charge_color
                if (
                    y < count
                    if leading
                    else y >= height - count
                )
                else idle_color
            )
            for y, row in enumerate(values)
            for color in row
        )

    def columns_match(count: int, *, leading: bool) -> bool:
        return all(
            color
            == (
                charge_color
                if (
                    x < count
                    if leading
                    else x >= width - count
                )
                else idle_color
            )
            for row in values
            for x, color in enumerate(row)
        )

    for count in range(1, height):
        if rows_match(count, leading=True):
            candidates.append((count, (0, 1)))
        if rows_match(count, leading=False):
            candidates.append((count, (0, -1)))
    for count in range(1, width):
        if columns_match(count, leading=True):
            candidates.append((count, (1, 0)))
        if columns_match(count, leading=False):
            candidates.append((count, (-1, 0)))
    return candidates[0] if len(candidates) == 1 else None


def _nearest_hazard_direction(
    *,
    position: Position,
    width: int,
    height: int,
    hazard: frozenset[Point],
) -> Direction | None:
    x0, y0 = position
    x1 = x0 + width - 1
    y1 = y0 + height - 1
    distances: list[tuple[int, Direction]] = []
    for direction in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        dx, dy = direction
        possible: list[int] = []
        for x, y in hazard:
            if dx == 0 and x0 <= x <= x1:
                distance = y0 - y - 1 if dy < 0 else y - y1 - 1
            elif dy == 0 and y0 <= y <= y1:
                distance = x0 - x - 1 if dx < 0 else x - x1 - 1
            else:
                continue
            if distance >= 0:
                possible.append(distance)
        if possible:
            distances.append((min(possible), direction))
    if not distances:
        return None
    minimum = min(distance for distance, _direction in distances)
    winners = tuple(
        direction
        for distance, direction in distances
        if distance == minimum
    )
    return winners[0] if len(winners) == 1 else None


def _force_blocks(
    grid: Grid,
    parameters: _DirectionalForceParameters,
    *,
    height: int,
) -> tuple[tuple[_ForceBlock, ...], int] | None:
    colors = frozenset(
        {parameters.force_charge_color, parameters.force_idle_color}
    )
    hazard = frozenset(
        (x, y)
        for y, row in enumerate(grid[:height])
        for x, color in enumerate(row)
        if color == parameters.hazard_color
    )
    if not hazard:
        return None
    parsed: list[tuple[_ForceBlock, int]] = []
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
            direction = _nearest_hazard_direction(
                position=(x0, y0),
                width=width,
                height=block_height,
                hazard=hazard,
            )
        else:
            band = _edge_band(
                values,
                charge_color=parameters.force_charge_color,
                idle_color=parameters.force_idle_color,
            )
            if band is None:
                return None
            phase, direction = band
            toward_hazard = _nearest_hazard_direction(
                position=(x0, y0),
                width=width,
                height=block_height,
                hazard=hazard,
            )
            if toward_hazard != direction:
                return None
        if direction is None:
            return None
        parsed.append(
            (
                _ForceBlock(
                    position=(x0, y0),
                    width=width,
                    height=block_height,
                    direction=direction,
                ),
                phase,
            )
        )
    if not (
        parameters.minimum_force_count
        <= len(parsed)
        <= parameters.maximum_force_count
    ):
        return None
    phases = {phase for _force, phase in parsed}
    dimensions = {
        (force.width, force.height) for force, _phase in parsed
    }
    if len(phases) != 1 or len(dimensions) != 1:
        return None
    ordered = tuple(
        sorted(
            parsed,
            key=lambda item: (
                item[0].direction,
                item[0].position[1],
                item[0].position[0],
            ),
        )
    )
    return tuple(force for force, _phase in ordered), next(iter(phases))


def _terrain_passable(
    model: _ForceRouteModel,
    position: Position,
    mask: Mask,
    *,
    pushed: bool,
) -> bool:
    passable = {
        model.shape.walkable_color,
        *model.shape.target_colors,
    }
    if pushed:
        passable.add(model.parameters.hazard_color)
    for x, y in _absolute_pixels(position, mask):
        if (
            x < 0
            or y < 0
            or x >= model.shape.width
            or y >= model.shape.height
            or model.terrain[y][x] not in passable
        ):
            return False
    return True


def _region_items(
    shape: _ShapePushModel,
    terrain: Grid,
) -> tuple[tuple[Position, int], ...]:
    actor_mask = shape.entities[0].mask
    passable_colors = {
        shape.walkable_color,
        *shape.target_colors,
    }
    x_offset = shape.entities[0].position[0] % shape.stride
    y_offset = shape.entities[0].position[1] % shape.stride
    positions = {
        (x, y)
        for y in range(
            y_offset,
            shape.height - shape.entities[0].height + 1,
            shape.stride,
        )
        for x in range(
            x_offset,
            shape.width - shape.entities[0].width + 1,
            shape.stride,
        )
        if all(
            terrain[py][px] in passable_colors
            for px, py in _absolute_pixels((x, y), actor_mask)
        )
    }
    remaining = set(positions)
    assigned: list[tuple[Position, int]] = []
    region = 0
    while remaining:
        start = min(remaining, key=lambda point: (point[1], point[0]))
        remaining.remove(start)
        frontier = [start]
        component = {start}
        while frontier:
            current = frontier.pop()
            for neighbor in _neighbors4(current, shape.stride):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
        assigned.extend((position, region) for position in component)
        region += 1
    return tuple(sorted(assigned))


def _entity_overlap(
    first_position: Position,
    first_mask: Mask,
    second_position: Position,
    second_mask: Mask,
) -> bool:
    return not _absolute_pixels(first_position, first_mask).isdisjoint(
        _absolute_pixels(second_position, second_mask)
    )


def _move_entity_once(
    model: _ForceRouteModel,
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
            and _entity_overlap(
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
        and _entity_overlap(
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


def _on_hazard(
    model: _ForceRouteModel,
    position: Position,
    mask: Mask,
) -> bool:
    return any(
        model.terrain[y][x] == model.parameters.hazard_color
        for x, y in _absolute_pixels(position, mask)
        if 0 <= x < model.shape.width and 0 <= y < model.shape.height
    )


def _normal_move(
    model: _ForceRouteModel,
    positions: list[Position],
    delta: Direction,
) -> None:
    masks = model.entity_masks
    actor_next = (
        positions[0][0] + delta[0],
        positions[0][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        actor_next,
        masks[0],
        pushed=False,
    ):
        return
    collided = tuple(
        index
        for index, position in enumerate(positions)
        if (
            index != 0
            and _entity_overlap(
                actor_next,
                masks[0],
                position,
                masks[index],
            )
        )
    )
    if not collided:
        positions[0] = actor_next
        return
    moved = list(positions)
    for step in range(model.parameters.maximum_push_steps):
        working = list(moved)
        changed = False
        for index in collided:
            before = working[index]
            if not _move_entity_once(
                model,
                working,
                index,
                delta,
                frozenset({0}),
            ):
                changed = False
                break
            changed = changed or working[index] != before
        if not changed:
            break
        moved = working
        if (
            step + 1 >= model.parameters.minimum_push_steps
            and all(
                not _on_hazard(model, moved[index], masks[index])
                for index in collided
            )
        ):
            break
    positions[:] = moved


def _adjacent_on_force_side(
    *,
    entity_position: Position,
    entity_mask: Mask,
    force_position: Position,
    force_mask: Mask,
    direction: Direction,
) -> bool:
    entity_pixels = _absolute_pixels(entity_position, entity_mask)
    force_pixels = _absolute_pixels(force_position, force_mask)
    shifted_force_edge = {
        (x + direction[0], y + direction[1])
        for x, y in force_pixels
    }
    return not entity_pixels.isdisjoint(shifted_force_edge)


def _apply_forces(
    model: _ForceRouteModel,
    positions: list[Position],
) -> None:
    masks = model.entity_masks
    force_offset = len(model.shape.entities)
    stride = model.shape.stride
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
                moved_steps < model.parameters.force_expansion_steps
                or _on_hazard(model, positions[index], masks[index])
            ):
                if moved_steps >= model.parameters.maximum_push_steps:
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


def _movement_deltas(
    model: _ForceRouteModel,
) -> tuple[tuple[int, Direction], ...]:
    stride = model.shape.stride
    parameters = model.parameters
    return (
        (parameters.up_action, (0, -stride)),
        (parameters.down_action, (0, stride)),
        (parameters.left_action, (-stride, 0)),
        (parameters.right_action, (stride, 0)),
    )


def _transition(
    model: _ForceRouteModel,
    state: _ForceRouteState,
    action_id: int,
) -> _ForceRouteState:
    delta = dict(_movement_deltas(model)).get(action_id)
    if delta is None:
        return state
    positions = list(state.positions)
    _normal_move(model, positions, delta)
    phase = state.phase + 1
    force_period = model.forces[0].height
    if phase >= force_period:
        _apply_forces(model, positions)
        phase = 0
    shape_positions = _canonical_positions(
        model.shape,
        positions[: len(model.shape.entities)],
    )
    return _ForceRouteState(
        positions=(
            *shape_positions,
            *positions[len(model.shape.entities) :],
        ),
        phase=phase,
    )


def _force_staging_positions(
    shape: _ShapePushModel,
    force: _ForceBlock,
) -> tuple[Position, ...]:
    actor = shape.entities[0]
    stride = shape.stride
    dx, dy = force.direction
    values: list[Position] = []
    if dx == 0:
        y = (
            force.position[1] - actor.height
            if dy < 0
            else force.position[1] + force.height
        )
        for x in range(
            force.position[0] - actor.width + 1,
            force.position[0] + force.width,
        ):
            if (
                x % stride == actor.position[0] % stride
                and y % stride == actor.position[1] % stride
            ):
                values.append((x, y))
    else:
        x = (
            force.position[0] - actor.width
            if dx < 0
            else force.position[0] + force.width
        )
        for y in range(
            force.position[1] - actor.height + 1,
            force.position[1] + force.height,
        ):
            if (
                x % stride == actor.position[0] % stride
                and y % stride == actor.position[1] % stride
            ):
                values.append((x, y))
    return tuple(values)


def _portal_regions(
    model: _ForceRouteModel,
    force_index: int,
) -> tuple[tuple[int, int], ...]:
    region_map = model.region_map
    force = model.forces[force_index]
    absolute_index = len(model.shape.entities) + force_index
    pairs: set[tuple[int, int]] = set()
    for staging in _force_staging_positions(model.shape, force):
        start_region = region_map.get(staging)
        if start_region is None:
            continue
        positions = list(model.initial_state.positions)
        positions[0] = staging
        positions[absolute_index] = force.position
        _apply_forces(model, positions)
        end_region = region_map.get(positions[0])
        if end_region is not None and end_region != start_region:
            pairs.add((start_region, end_region))
    return tuple(sorted(pairs))


def _force_route_model(
    grid: Grid,
    parameters: _DirectionalForceParameters,
) -> _ForceRouteModel | None:
    if any(
        parameters.unselected_marker_color in row
        for row in grid
    ):
        return None
    shape_parameters = parameters.shape_parameters()
    shape = _shape_push_model(grid, shape_parameters)
    if shape is None:
        excluded = {
            parameters.selected_marker_color,
            parameters.unselected_marker_color,
            parameters.released_marker_color,
            parameters.hazard_color,
            parameters.force_charge_color,
            parameters.force_idle_color,
        }
        counts = Counter(
            color
            for row in grid
            for color in row
            if color not in excluded
        )
        for color, _count in counts.most_common(4):
            shape = _shape_push_model(
                grid,
                shape_parameters,
                walkable_hint=color,
            )
            if shape is not None:
                break
    if (
        shape is None
        or len(shape.entities) != 2
        or len(shape.push_goal_families) != 1
        or len(shape.push_goal_families[0][0]) != 1
        or len(shape.push_goal_families[0][1]) != 1
    ):
        return None
    parsed_forces = _force_blocks(
        grid,
        parameters,
        height=shape.height,
    )
    if parsed_forces is None:
        return None
    forces, phase = parsed_forces
    terrain = [list(row) for row in shape.terrain]
    for force in forces:
        for x, y in _absolute_pixels(force.position, force.mask):
            terrain[y][x] = shape.walkable_color
    terrain_grid = tuple(tuple(row) for row in terrain)
    regions = _region_items(shape, terrain_grid)
    region_map = dict(regions)
    actor_goal_region = region_map.get(shape.actor_goal)
    shape_goal = shape.push_goal_families[0][1][0]
    shape_goal_region = region_map.get(shape_goal)
    if (
        actor_goal_region is None
        or shape_goal_region is None
        or actor_goal_region == shape_goal_region
    ):
        return None
    initial = _ForceRouteState(
        positions=(
            *shape.initial_positions,
            *(force.position for force in forces),
        ),
        phase=phase,
    )
    provisional = _ForceRouteModel(
        shape=shape,
        terrain=terrain_grid,
        forces=forces,
        region_items=regions,
        actor_goal_region=actor_goal_region,
        shape_goal_region=shape_goal_region,
        transit_region=-1,
        initial_state=initial,
        parameters=parameters,
    )
    destination_counts: dict[int, set[int]] = {}
    for index in range(len(forces)):
        for start, destination in _portal_regions(provisional, index):
            if start in {actor_goal_region, shape_goal_region}:
                destination_counts.setdefault(destination, set()).add(start)
    transit_candidates = tuple(
        region
        for region, starts in destination_counts.items()
        if (
            region not in {actor_goal_region, shape_goal_region}
            and starts == {actor_goal_region, shape_goal_region}
        )
    )
    if len(transit_candidates) != 1:
        return None
    model = _ForceRouteModel(
        shape=shape,
        terrain=terrain_grid,
        forces=forces,
        region_items=regions,
        actor_goal_region=actor_goal_region,
        shape_goal_region=shape_goal_region,
        transit_region=transit_candidates[0],
        initial_state=initial,
        parameters=parameters,
    )
    actor_region = model.region_map.get(initial.positions[0])
    if actor_region not in {
        model.actor_goal_region,
        model.shape_goal_region,
        model.transit_region,
    }:
        return None
    return model


def _shape_solved(
    model: _ForceRouteModel,
    state: _ForceRouteState,
) -> bool:
    indices, goals = model.shape.push_goal_families[0]
    return tuple(sorted(state.positions[index] for index in indices)) == tuple(
        sorted(goals)
    )


def _visual_roles_separated(
    model: _ForceRouteModel,
    state: _ForceRouteState,
) -> bool:
    """Avoid states where opaque sprites hide another role's bounding box."""

    actor = model.shape.entities[0]
    actor_rectangle = tuple(
        (x, y)
        for y in range(actor.height)
        for x in range(actor.width)
    )
    for index, entity in enumerate(model.shape.entities[1:], start=1):
        entity_rectangle = tuple(
            (x, y)
            for y in range(entity.height)
            for x in range(entity.width)
        )
        if _entity_overlap(
            state.positions[0],
            actor_rectangle,
            state.positions[index],
            entity_rectangle,
        ):
            return False
    return True


def _stage(
    model: _ForceRouteModel,
    state: _ForceRouteState,
) -> str | None:
    region = model.region_map.get(state.positions[0])
    if region is None:
        return None
    if not _shape_solved(model, state):
        if region == model.shape_goal_region:
            return "place-shape"
        if region == model.transit_region:
            return "enter-shape-region"
        if region == model.actor_goal_region:
            return "return-to-transit"
        return None
    if region == model.actor_goal_region:
        return (
            None
            if state.positions[0] == model.shape.actor_goal
            else "place-actor"
        )
    if region == model.transit_region:
        return "enter-actor-region"
    if region == model.shape_goal_region:
        return "return-to-transit"
    return None


def _stage_complete(
    model: _ForceRouteModel,
    state: _ForceRouteState,
    stage: str,
) -> bool:
    region = model.region_map.get(state.positions[0])
    if stage == "place-shape":
        return _shape_solved(model, state)
    if stage == "enter-shape-region":
        return region == model.shape_goal_region
    if stage == "return-to-transit":
        return region == model.transit_region
    if stage == "enter-actor-region":
        return region == model.actor_goal_region
    if stage == "place-actor":
        return state.positions[0] == model.shape.actor_goal
    return False


def _search_stage(
    model: _ForceRouteModel,
    stage: str,
) -> tuple[int, ...]:
    start = model.initial_state
    if _stage_complete(model, start, stage):
        return ()
    preserve_shape = _shape_solved(model, start)
    frontier: deque[_ForceRouteState] = deque([start])
    depth = {start: 0}
    parent: dict[
        _ForceRouteState,
        tuple[_ForceRouteState, int],
    ] = {}
    found: _ForceRouteState | None = None
    actions = tuple(
        action_id for action_id, _delta in _movement_deltas(model)
    )
    while frontier and len(depth) < model.parameters.maximum_search_states:
        state = frontier.popleft()
        state_depth = depth[state]
        if state_depth >= model.parameters.maximum_stage_actions:
            continue
        for action_id in actions:
            next_state = _transition(model, state, action_id)
            if (
                next_state in depth
                or not _visual_roles_separated(model, next_state)
                or (preserve_shape and not _shape_solved(model, next_state))
            ):
                continue
            depth[next_state] = state_depth + 1
            parent[next_state] = (state, action_id)
            if _stage_complete(model, next_state, stage):
                found = next_state
                frontier.clear()
                break
            frontier.append(next_state)
    if found is None:
        return ()
    reverse: list[int] = []
    cursor = found
    while cursor != start:
        previous, action_id = parent[cursor]
        reverse.append(action_id)
        cursor = previous
    return tuple(reversed(reverse))


def _model_payload(
    model: _ForceRouteModel,
    state: _ForceRouteState,
    *,
    stage: str,
    stage_plan: tuple[int, ...],
) -> dict[str, object]:
    return {
        "actor_goal": model.shape.actor_goal,
        "actor_goal_region": model.actor_goal_region,
        "entity_masks": model.entity_masks,
        "force_directions": tuple(
            force.direction for force in model.forces
        ),
        "phase": state.phase,
        "positions": state.positions,
        "shape_goal_region": model.shape_goal_region,
        "stage": stage,
        "stage_plan_digest": digest_object(stage_plan),
        "stage_plan_length": len(stage_plan),
        "stride": model.shape.stride,
        "terrain_digest": digest_object(model.terrain),
        "transit_region": model.transit_region,
    }


def _observation_height(model: _ForceRouteModel) -> int:
    if not model.terrain:
        return 0
    footer_colors = {
        model.parameters.selected_marker_color,
        model.parameters.released_marker_color,
    }
    return (
        model.shape.height - 1
        if set(model.terrain[-1]) <= footer_colors
        else model.shape.height
    )


def _render_state(
    model: _ForceRouteModel,
    state: _ForceRouteState,
) -> Grid:
    grid = [list(row) for row in model.terrain]
    shape_count = len(model.shape.entities)
    for index, entity in enumerate(model.shape.entities):
        x0, y0 = state.positions[index]
        for dx, dy in entity.mask:
            grid[y0 + dy][x0 + dx] = entity.color
        if index == 0:
            marker_width = entity.width // model.parameters.marker_divisor
            marker_height = (
                entity.height // model.parameters.marker_divisor
            )
            marker_x0 = x0 + (entity.width - marker_width) // 2
            marker_y0 = y0 + (entity.height - marker_height) // 2
            for y in range(marker_y0, marker_y0 + marker_height):
                for x in range(marker_x0, marker_x0 + marker_width):
                    grid[y][x] = model.parameters.selected_marker_color
    for index, force in enumerate(model.forces, start=shape_count):
        x0, y0 = state.positions[index]
        for dy in range(force.height):
            for dx in range(force.width):
                charged = (
                    (force.direction == (0, 1) and dy < state.phase)
                    or (
                        force.direction == (0, -1)
                        and dy >= force.height - state.phase
                    )
                    or (force.direction == (1, 0) and dx < state.phase)
                    or (
                        force.direction == (-1, 0)
                        and dx >= force.width - state.phase
                    )
                )
                grid[y0 + dy][x0 + dx] = (
                    model.parameters.force_charge_color
                    if charged
                    else model.parameters.force_idle_color
                )
    return tuple(tuple(row) for row in grid)


def _visual_action(
    model: _ForceRouteModel,
    instruction: SemanticOperatorInstruction,
    *,
    state: _ForceRouteState,
    stage: str,
    stage_plan: tuple[int, ...],
    action_id: int,
    index: int,
) -> VisualAction:
    observation_height = _observation_height(model)
    payload = _model_payload(
        model,
        state,
        stage=stage,
        stage_plan=stage_plan,
    )
    successor_evidence: tuple[str, ...] = ()
    if model.parameters.maximum_transition_observations:
        successor = _transition(model, state, action_id)
        successor_evidence = (
            "directional-force-successor-grid:"
            + digest_object(
                _render_state(model, successor)[:observation_height]
            ),
        )
    return VisualAction(
        key="semantic-directional-force:"
        + digest_object(
            {
                "operator": instruction.operator_id,
                "payload": payload,
                "action": action_id,
                "index": index,
            }
        )[:20],
        action_id=action_id,
        group=0,
        evidence=(
            instruction.operator_id,
            f"operator-prototype:{instruction.operator_id}",
            "rendered-marker-shape-target-obligations",
            "rendered-directional-charge-band",
            "rendered-impassable-region-separation",
            "bounded-force-assisted-stage-search",
            f"directional-force-current-action:{action_id}",
            f"directional-force-height:{observation_height}",
            "directional-force-expected-grid:"
            + digest_object(
                _render_state(model, state)[:observation_height]
            ),
            "directional-force-state:"
            + json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            ),
            *successor_evidence,
            *instruction.provenance,
        ),
    )


def directional_force_route_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Return one re-observation-gated action from a bounded stage plan."""

    parameters = _DirectionalForceParameters.from_instruction(instruction)
    if parameters is None:
        return ()
    required = {
        parameters.click_action,
        parameters.up_action,
        parameters.down_action,
        parameters.left_action,
        parameters.right_action,
    }
    if not required.issubset(available_actions):
        return ()
    model = _force_route_model(grid, parameters)
    if model is None:
        return ()
    stage = _stage(model, model.initial_state)
    if stage is None:
        return ()
    stage_plan = _search_stage(model, stage)
    if not stage_plan:
        return ()
    state = model.initial_state
    actions: list[VisualAction] = []
    for index, action_id in enumerate(stage_plan):
        actions.append(
            _visual_action(
                model,
                instruction,
                state=state,
                stage=stage,
                stage_plan=stage_plan[index:],
                action_id=action_id,
                index=index,
            )
        )
        state = _transition(model, state, action_id)
    return tuple(actions)


def _directional_force_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
    *,
    digest_prefix: str,
) -> DirectionalForceObservationStatus:
    parameters = _DirectionalForceParameters.from_instruction(instruction)
    if parameters is None:
        return "MISMATCH"
    actions = tuple(
        item.removeprefix("directional-force-current-action:")
        for item in action.evidence
        if item.startswith("directional-force-current-action:")
    )
    heights = tuple(
        item.removeprefix("directional-force-height:")
        for item in action.evidence
        if item.startswith("directional-force-height:")
    )
    digests = tuple(
        item.removeprefix(digest_prefix)
        for item in action.evidence
        if item.startswith(digest_prefix)
    )
    if len(actions) != 1 or len(heights) != 1 or len(digests) != 1:
        return "MISMATCH"
    try:
        expected_action = int(actions[0])
        height = int(heights[0])
    except ValueError:
        return "MISMATCH"
    if expected_action != action.action_id or not 0 < height <= len(grid):
        return "MISMATCH"
    if digest_object(tuple(grid[:height])) == digests[0]:
        return "MATCH"
    return (
        "UNAVAILABLE"
        if _force_route_model(grid, parameters) is None
        else "MISMATCH"
    )


def directional_force_route_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> DirectionalForceObservationStatus:
    """Classify a queued action against its rendered expected state."""

    return _directional_force_observation_status(
        grid,
        instruction,
        action,
        digest_prefix="directional-force-expected-grid:",
    )


def directional_force_route_successor_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> DirectionalForceObservationStatus:
    """Classify the rendered state after one emitted force-route action."""

    return _directional_force_observation_status(
        grid,
        instruction,
        action,
        digest_prefix="directional-force-successor-grid:",
    )


def directional_force_route_observation_matches(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> bool:
    """Validate one queued action against its rendered expected state."""

    return (
        directional_force_route_observation_status(
            grid,
            instruction,
            action,
        )
        == "MATCH"
    )


def directional_force_route_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the P-bounded transient-frame observation limit."""

    parameters = _DirectionalForceParameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


__all__ = [
    "DIRECTIONAL_FORCE_ROUTE_OPERATOR",
    "directional_force_route_observation_matches",
    "directional_force_route_observation_status",
    "directional_force_route_plan",
    "directional_force_route_successor_observation_status",
    "directional_force_route_transition_observation_limit",
]
