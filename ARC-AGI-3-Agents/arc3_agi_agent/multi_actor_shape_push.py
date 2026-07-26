"""Rendered multi-actor selection and shape-target push routing.

The operator derives every actor, movable shape, target, selection point,
movement step, and transition expectation from the current rendered grid.
It neither accepts runtime identity nor owns judgment, memory mutation, or
external-emission authority.
"""

from __future__ import annotations

import heapq
import itertools
import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from typing import Literal, TypeAlias

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object
from .visual_explorer import (
    Grid,
    Point,
    VisualAction,
    VisualComponent,
    connected_components,
)

MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR = (
    "multi-actor-shape-target-route-v4"
)

Position: TypeAlias = tuple[int, int]
Mask: TypeAlias = tuple[Point, ...]
MultiShapeState: TypeAlias = tuple[tuple[Position, ...], int]
SearchAction: TypeAlias = tuple[Literal["move", "select"], int]
MultiShapeObservationStatus: TypeAlias = Literal[
    "MATCH",
    "MISMATCH",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class _Parameters:
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
    minimum_actor_count: int
    maximum_actor_count: int
    minimum_entity_count: int
    maximum_entity_count: int
    minimum_target_side: int
    maximum_target_side: int
    minimum_push_steps: int
    maximum_push_steps: int
    push_through_color: int
    maximum_search_states: int
    maximum_plan_actions: int
    maximum_transition_observations: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _Parameters | None:
        if (
            instruction.operator_id
            != MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR
        ):
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
            "minimum_actor_count",
            "maximum_actor_count",
            "minimum_entity_count",
            "maximum_entity_count",
            "minimum_target_side",
            "maximum_target_side",
            "minimum_push_steps",
            "maximum_push_steps",
            "push_through_color",
            "maximum_search_states",
            "maximum_plan_actions",
            "maximum_transition_observations",
        )
        parsed: dict[str, int] = {}
        for name in names:
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                return None
            parsed[name] = value
        movement_actions = {
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
        if (
            instruction.action_id != parsed["click_action"]
            or len(movement_actions) != 4
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
            or parsed["marker_divisor"] < 2
            or parsed["target_inset"] < 1
            or parsed["minimum_actor_count"] < 2
            or parsed["maximum_actor_count"]
            < parsed["minimum_actor_count"]
            or parsed["minimum_entity_count"]
            < parsed["minimum_actor_count"] + 1
            or parsed["maximum_entity_count"]
            < parsed["minimum_entity_count"]
            or parsed["maximum_entity_count"]
            < parsed["maximum_actor_count"]
            or parsed["minimum_target_side"] < 3
            or parsed["maximum_target_side"]
            < parsed["minimum_target_side"]
            or parsed["minimum_push_steps"] < 1
            or parsed["maximum_push_steps"]
            < parsed["minimum_push_steps"]
            or parsed["maximum_search_states"] < 1
            or parsed["maximum_plan_actions"] < 1
            or parsed["maximum_transition_observations"] < 1
        ):
            return None
        return cls(**parsed)


@dataclass(frozen=True, slots=True)
class _Target:
    color: int
    goal_position: Position
    width: int
    height: int
    mask: Mask

    @property
    def family(self) -> tuple[int, int, Mask]:
        return self.width, self.height, self.mask


@dataclass(frozen=True, slots=True)
class _Entity:
    selectable: bool
    color: int
    position: Position
    width: int
    height: int
    mask: Mask
    marker_color: int | None = None

    @property
    def family(self) -> tuple[int, int, Mask]:
        return self.width, self.height, self.mask

    @property
    def canonical_family(
        self,
    ) -> tuple[bool, int, int, int, Mask]:
        return (
            self.selectable,
            self.color,
            self.width,
            self.height,
            self.mask,
        )


@dataclass(frozen=True, slots=True)
class _Model:
    width: int
    height: int
    terrain: Grid
    entities: tuple[_Entity, ...]
    selected_index: int
    goal_families: tuple[
        tuple[tuple[int, ...], tuple[Position, ...]],
        ...,
    ]
    stride: int
    walkable_color: int
    target_colors: frozenset[int]
    parameters: _Parameters

    @property
    def initial_positions(self) -> tuple[Position, ...]:
        return tuple(entity.position for entity in self.entities)

    @property
    def selectable_indices(self) -> tuple[int, ...]:
        return tuple(
            index
            for index, entity in enumerate(self.entities)
            if entity.selectable
        )

    @property
    def canonical_groups(self) -> tuple[tuple[int, ...], ...]:
        grouped: dict[
            tuple[bool, int, int, int, Mask],
            list[int],
        ] = {}
        for index, entity in enumerate(self.entities):
            grouped.setdefault(entity.canonical_family, []).append(index)
        return tuple(
            tuple(indices)
            for _family, indices in sorted(grouped.items())
            if len(indices) > 1
        )


def _neighbors4(point: Point) -> tuple[Point, ...]:
    x, y = point
    return (
        (x - 1, y),
        (x + 1, y),
        (x, y - 1),
        (x, y + 1),
    )


def _connected(mask: set[Point]) -> bool:
    if not mask:
        return False
    remaining = set(mask)
    frontier = [remaining.pop()]
    while frontier:
        point = frontier.pop()
        for neighbor in _neighbors4(point):
            if neighbor in remaining:
                remaining.remove(neighbor)
                frontier.append(neighbor)
    return not remaining


def _enclosed_target(
    component: VisualComponent,
    parameters: _Parameters,
) -> _Target | None:
    if (
        component.width < parameters.minimum_target_side
        or component.height < parameters.minimum_target_side
        or component.width > parameters.maximum_target_side
        or component.height > parameters.maximum_target_side
    ):
        return None
    x0, y0, x1, y1 = component.bbox
    walls = set(component.pixels)
    rectangle = {
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
    }
    exterior: set[Point] = set()
    frontier: deque[Point] = deque()
    for point in rectangle:
        x, y = point
        if (
            point not in walls
            and (x in {x0, x1} or y in {y0, y1})
        ):
            exterior.add(point)
            frontier.append(point)
    while frontier:
        point = frontier.popleft()
        for neighbor in _neighbors4(point):
            if (
                neighbor in rectangle
                and neighbor not in walls
                and neighbor not in exterior
            ):
                exterior.add(neighbor)
                frontier.append(neighbor)
    enclosed = rectangle - walls - exterior
    if not enclosed or not _connected(enclosed):
        return None
    enclosed_x0 = min(x for x, _y in enclosed)
    enclosed_y0 = min(y for _x, y in enclosed)
    enclosed_x1 = max(x for x, _y in enclosed)
    enclosed_y1 = max(y for _x, y in enclosed)
    inset = parameters.target_inset
    if (
        enclosed_x0 != x0 + inset
        or enclosed_y0 != y0 + inset
        or enclosed_x1 != x1 - inset
        or enclosed_y1 != y1 - inset
    ):
        return None
    width = enclosed_x1 - enclosed_x0 + 1
    height = enclosed_y1 - enclosed_y0 + 1
    mask = tuple(
        sorted(
            (x - enclosed_x0, y - enclosed_y0)
            for x, y in enclosed
        )
    )
    return _Target(
        color=int(component.color),
        goal_position=(enclosed_x0, enclosed_y0),
        width=width,
        height=height,
        mask=mask,
    )


def _targets(
    grid: Grid,
    parameters: _Parameters,
) -> tuple[_Target, ...]:
    enclosed = tuple(
        target
        for component in connected_components(grid)
        if (
            target := _enclosed_target(component, parameters)
        )
        is not None
    )
    grouped: dict[int, list[_Target]] = {}
    for target in enclosed:
        grouped.setdefault(target.color, []).append(target)
    candidates = tuple(
        tuple(targets)
        for _color, targets in sorted(grouped.items())
        if (
            parameters.minimum_entity_count
            <= len(targets)
            <= parameters.maximum_entity_count
        )
    )
    if len(candidates) != 1:
        return ()
    return tuple(
        sorted(
            candidates[0],
            key=lambda item: (
                item.width,
                item.height,
                item.mask,
                item.goal_position[1],
                item.goal_position[0],
            ),
        )
    )


def _full_rectangle(width: int, height: int) -> Mask:
    return tuple(
        sorted(
            (x, y)
            for y in range(height)
            for x in range(width)
        )
    )


def _actor_at(
    grid: Grid,
    parameters: _Parameters,
    *,
    x0: int,
    y0: int,
    width: int,
    height: int,
) -> _Entity | None:
    divisor = parameters.marker_divisor
    if (
        width % divisor
        or height % divisor
        or width < divisor
        or height < divisor
    ):
        return None
    marker_width = width // divisor
    marker_height = height // divisor
    marker_x0 = x0 + (width - marker_width) // 2
    marker_y0 = y0 + (height - marker_height) // 2
    marker_values = {
        grid[y][x]
        for y in range(marker_y0, marker_y0 + marker_height)
        for x in range(marker_x0, marker_x0 + marker_width)
    }
    allowed_markers = {
        parameters.selected_marker_color,
        parameters.unselected_marker_color,
        parameters.released_marker_color,
    }
    if len(marker_values) != 1 or not marker_values <= allowed_markers:
        return None
    marker = int(next(iter(marker_values)))
    object_values = {
        grid[y][x]
        for y in range(y0, y0 + height)
        for x in range(x0, x0 + width)
        if not (
            marker_x0 <= x < marker_x0 + marker_width
            and marker_y0 <= y < marker_y0 + marker_height
        )
        and grid[y][x] not in allowed_markers
    }
    if len(object_values) != 1:
        return None
    object_color = int(next(iter(object_values)))
    if object_color in allowed_markers:
        return None
    for y in range(y0, y0 + height):
        for x in range(x0, x0 + width):
            if (
                marker_x0 <= x < marker_x0 + marker_width
                and marker_y0 <= y < marker_y0 + marker_height
            ):
                continue
            value = grid[y][x]
            border = (
                x in {x0, x0 + width - 1}
                or y in {y0, y0 + height - 1}
            )
            if value == object_color:
                continue
            if (
                border
                and marker == parameters.selected_marker_color
                and value == parameters.selected_marker_color
            ):
                continue
            return None
    return _Entity(
        selectable=True,
        color=object_color,
        position=(x0, y0),
        width=width,
        height=height,
        mask=_full_rectangle(width, height),
        marker_color=marker,
    )


def _actors(
    grid: Grid,
    targets: tuple[_Target, ...],
    parameters: _Parameters,
) -> tuple[_Entity, ...]:
    rectangle_sizes = tuple(
        sorted(
            {
                (target.width, target.height)
                for target in targets
                if target.mask
                == _full_rectangle(target.width, target.height)
            }
        )
    )
    found: dict[tuple[int, int, int, int, int], _Entity] = {}
    for width, height in rectangle_sizes:
        for y0 in range(len(grid) - height + 1):
            for x0 in range(len(grid[0]) - width + 1):
                actor = _actor_at(
                    grid,
                    parameters,
                    x0=x0,
                    y0=y0,
                    width=width,
                    height=height,
                )
                if actor is None:
                    continue
                found[
                    (
                        actor.position[0],
                        actor.position[1],
                        actor.width,
                        actor.height,
                        actor.color,
                    )
                ] = actor
    actors = tuple(
        sorted(
            found.values(),
            key=lambda item: (
                item.canonical_family,
                item.position[1],
                item.position[0],
            ),
        )
    )
    if (
        not parameters.minimum_actor_count
        <= len(actors)
        <= parameters.maximum_actor_count
        or sum(
            actor.marker_color == parameters.selected_marker_color
            for actor in actors
        )
        != 1
    ):
        return ()
    target_counts = Counter(target.family for target in targets)
    actor_counts = Counter(actor.family for actor in actors)
    if any(
        actor_counts[family] > target_counts[family]
        for family in actor_counts
    ):
        return ()
    return actors


def _normalized_component_mask(
    component: VisualComponent,
) -> Mask:
    x0, y0, _x1, _y1 = component.bbox
    return tuple(
        sorted((x - x0, y - y0) for x, y in component.pixels)
    )


def _entities(
    grid: Grid,
    targets: tuple[_Target, ...],
    actors: tuple[_Entity, ...],
    walkable_color: int,
    parameters: _Parameters,
) -> tuple[_Entity, ...]:
    target_groups: dict[
        tuple[int, int, Mask],
        list[_Target],
    ] = {}
    for target in targets:
        target_groups.setdefault(target.family, []).append(target)
    actor_counts = Counter(actor.family for actor in actors)
    components = connected_components(grid)
    excluded_colors = {
        target.color for target in targets
    } | {
        parameters.selected_marker_color,
        parameters.unselected_marker_color,
        parameters.released_marker_color,
        walkable_color,
    }
    pushables: list[_Entity] = []
    for family, family_targets in sorted(target_groups.items()):
        width, height, mask = family
        required = len(family_targets) - actor_counts[family]
        if required < 0:
            return ()
        matches = tuple(
            component
            for component in components
            if (
                component.color not in excluded_colors
                and component.width == width
                and component.height == height
                and _normalized_component_mask(component) == mask
            )
        )
        if len(matches) != required:
            return ()
        for component in sorted(
            matches,
            key=lambda item: (
                item.color,
                item.bbox[1],
                item.bbox[0],
            ),
        ):
            pushables.append(
                _Entity(
                    selectable=False,
                    color=int(component.color),
                    position=(component.bbox[0], component.bbox[1]),
                    width=width,
                    height=height,
                    mask=mask,
                )
            )
    entities = tuple(
        sorted(
            (*actors, *pushables),
            key=lambda item: (
                item.canonical_family,
                item.position[1],
                item.position[0],
            ),
        )
    )
    if not (
        parameters.minimum_entity_count
        <= len(entities)
        <= parameters.maximum_entity_count
        and len(entities) == len(targets)
        and len(entities) > len(actors)
    ):
        return ()
    return entities


def _walkable_color(
    grid: Grid,
    targets: tuple[_Target, ...],
    entities: tuple[_Entity, ...],
) -> int | None:
    excluded = {
        entity.color for entity in entities
    } | {
        entity.marker_color
        for entity in entities
        if entity.marker_color is not None
    } | {
        target.color for target in targets
    }
    values = [
        grid[target.goal_position[1] + dy][
            target.goal_position[0] + dx
        ]
        for target in targets
        for dx, dy in target.mask
        if (
            grid[target.goal_position[1] + dy][
                target.goal_position[0] + dx
            ]
            not in excluded
        )
    ]
    if not values:
        return None
    counts = Counter(values)
    maximum = max(counts.values())
    winners = tuple(
        color
        for color, count in sorted(counts.items())
        if count == maximum
    )
    return int(winners[0]) if len(winners) == 1 else None


def _playable_height(
    grid: Grid,
    *,
    walkable_color: int,
) -> int:
    height = len(grid)
    for y in range(max(1, height - 4), height - 1):
        if (
            len(set(grid[y])) == 1
            and grid[y][0] != walkable_color
        ):
            return y
    if (
        height > 1
        and len(set(grid[-1])) == 1
        and grid[-1][0] != walkable_color
    ):
        return height - 1
    return height


def _model(
    grid: Grid,
    parameters: _Parameters,
    *,
    walkable_hint: int | None = None,
    playable_height_hint: int | None = None,
) -> _Model | None:
    if not grid or not grid[0]:
        return None
    targets = _targets(grid, parameters)
    actors = _actors(grid, targets, parameters)
    if not actors:
        return None
    inferred_walkable = _walkable_color(
        grid,
        targets,
        actors,
    )
    if walkable_hint is None:
        if inferred_walkable is None:
            return None
        walkable = inferred_walkable
    else:
        excluded_colors = {
            *(target.color for target in targets),
            *(entity.color for entity in actors),
            *(
                entity.marker_color
                for entity in actors
                if entity.marker_color is not None
            ),
        }
        if (
            isinstance(walkable_hint, bool)
            or walkable_hint in excluded_colors
            or not any(walkable_hint in row for row in grid)
        ):
            return None
        walkable = walkable_hint
    preliminary = _entities(
        grid,
        targets,
        actors,
        walkable,
        parameters,
    )
    if not preliminary:
        return None
    if _walkable_color(grid, targets, preliminary) != walkable:
        return None
    entities = preliminary
    selected = tuple(
        index
        for index, entity in enumerate(entities)
        if (
            entity.selectable
            and entity.marker_color
            == parameters.selected_marker_color
        )
    )
    if len(selected) != 1:
        return None
    entity_groups: dict[
        tuple[int, int, Mask],
        list[int],
    ] = {}
    target_groups: dict[
        tuple[int, int, Mask],
        list[Position],
    ] = {}
    for index, entity in enumerate(entities):
        entity_groups.setdefault(entity.family, []).append(index)
    for target in targets:
        target_groups.setdefault(target.family, []).append(
            target.goal_position
        )
    if set(entity_groups) != set(target_groups):
        return None
    goal_families: list[
        tuple[tuple[int, ...], tuple[Position, ...]]
    ] = []
    for family in sorted(entity_groups):
        indices = tuple(entity_groups[family])
        goals = tuple(sorted(target_groups[family]))
        if len(indices) != len(goals):
            return None
        goal_families.append((indices, goals))
    stride = math.gcd(
        *(
            dimension
            for entity in entities
            if entity.selectable
            for dimension in (entity.width, entity.height)
        )
    )
    if stride < 1:
        return None
    for indices, goals in goal_families:
        positions = tuple(entities[index].position for index in indices)
        if any(
            (position[0] - goal[0]) % stride
            or (position[1] - goal[1]) % stride
            for position in positions
            for goal in goals
        ):
            return None
    if playable_height_hint is None:
        height = _playable_height(
            grid,
            walkable_color=walkable,
        )
    else:
        if (
            isinstance(playable_height_hint, bool)
            or not 1 <= playable_height_hint <= len(grid)
        ):
            return None
        height = playable_height_hint
    if any(
        y >= height
        for entity in entities
        for _x, y in _absolute_pixels(entity.position, entity.mask)
    ):
        return None
    terrain = [
        [int(value) for value in row]
        for row in grid[:height]
    ]
    for entity in entities:
        for x, y in _absolute_pixels(entity.position, entity.mask):
            terrain[y][x] = walkable
    model = _Model(
        width=len(grid[0]),
        height=height,
        terrain=tuple(tuple(row) for row in terrain),
        entities=entities,
        selected_index=selected[0],
        goal_families=tuple(goal_families),
        stride=stride,
        walkable_color=walkable,
        target_colors=frozenset(target.color for target in targets),
        parameters=parameters,
    )
    positions, canonical_selected = _canonical_state(
        model,
        model.initial_positions,
        model.selected_index,
    )
    if (
        positions != model.initial_positions
        or canonical_selected != model.selected_index
    ):
        return None
    return model


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
    model: _Model,
    positions: tuple[Position, ...],
    selected_index: int,
) -> MultiShapeState:
    if (
        len(positions) != len(model.entities)
        or selected_index not in model.selectable_indices
    ):
        raise ValueError("multi-shape state is incompatible with model")
    canonical = list(positions)
    selected_position = positions[selected_index]
    remapped_selected = selected_index
    for indices in model.canonical_groups:
        ordered = sorted(
            (positions[index] for index in indices),
            key=lambda position: (position[1], position[0]),
        )
        for index, position in zip(indices, ordered, strict=True):
            canonical[index] = position
        if selected_index in indices:
            remapped_selected = indices[
                ordered.index(selected_position)
            ]
    return tuple(canonical), remapped_selected


def _terrain_passable(
    model: _Model,
    position: Position,
    mask: Mask,
    *,
    pushed: bool,
) -> bool:
    passable = {
        model.walkable_color,
        *model.target_colors,
    }
    if pushed:
        passable.add(model.parameters.push_through_color)
    for x, y in _absolute_pixels(position, mask):
        if (
            x < 0
            or y < 0
            or x >= model.width
            or y >= model.height
            or model.terrain[y][x] not in passable
        ):
            return False
    return True


def _on_push_through(
    model: _Model,
    position: Position,
    mask: Mask,
) -> bool:
    return any(
        model.terrain[y][x]
        == model.parameters.push_through_color
        for x, y in _absolute_pixels(position, mask)
        if 0 <= x < model.width and 0 <= y < model.height
    )


def _move_entity_once(
    model: _Model,
    positions: list[Position],
    index: int,
    delta: Point,
    protected: frozenset[int],
) -> bool:
    if index in protected:
        return False
    next_position = (
        positions[index][0] + delta[0],
        positions[index][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        next_position,
        model.entities[index].mask,
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
                model.entities[index].mask,
                position,
                model.entities[other].mask,
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
            model.entities[index].mask,
            position,
            model.entities[other].mask,
        )
        for other, position in enumerate(working)
    ):
        return False
    working[index] = next_position
    positions[:] = working
    return True


def _movement_deltas(
    model: _Model,
) -> tuple[tuple[int, Point], ...]:
    stride = model.stride
    return (
        (model.parameters.up_action, (0, -stride)),
        (model.parameters.down_action, (0, stride)),
        (model.parameters.left_action, (-stride, 0)),
        (model.parameters.right_action, (stride, 0)),
    )


def _transition(
    model: _Model,
    state: MultiShapeState,
    action: SearchAction,
) -> MultiShapeState:
    positions, selected = state
    kind, value = action
    if kind == "select":
        if value not in model.selectable_indices:
            return state
        return _canonical_state(model, positions, value)
    delta = dict(_movement_deltas(model)).get(value)
    if delta is None:
        return state
    actor_next = (
        positions[selected][0] + delta[0],
        positions[selected][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        actor_next,
        model.entities[selected].mask,
        pushed=False,
    ):
        return state
    collided = tuple(
        index
        for index, position in enumerate(positions)
        if (
            index != selected
            and _collides(
                actor_next,
                model.entities[selected].mask,
                position,
                model.entities[index].mask,
            )
        )
    )
    mutable = list(positions)
    if not collided:
        mutable[selected] = actor_next
        return _canonical_state(model, tuple(mutable), selected)
    for push_step in range(model.parameters.maximum_push_steps):
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
            push_step + 1 >= model.parameters.minimum_push_steps
            and all(
                not _on_push_through(
                    model,
                    mutable[index],
                    model.entities[index].mask,
                )
                for index in collided
            )
        ):
            break
    return _canonical_state(model, tuple(mutable), selected)


def _family_assignment_cost(
    positions: tuple[Position, ...],
    goals: tuple[Position, ...],
    stride: int,
) -> int:
    size = len(positions)
    if size != len(goals):
        return 2**30
    costs: dict[tuple[int, int], int] = {(0, 0): 0}
    for index, position in enumerate(positions):
        next_costs: dict[tuple[int, int], int] = {}
        for (_done, mask), cost in costs.items():
            for goal_index, goal in enumerate(goals):
                if mask & (1 << goal_index):
                    continue
                value = cost + (
                    abs(position[0] - goal[0])
                    + abs(position[1] - goal[1])
                ) // stride
                key = (index + 1, mask | (1 << goal_index))
                next_costs[key] = min(
                    value,
                    next_costs.get(key, 2**30),
                )
        costs = next_costs
    return costs.get((size, (1 << size) - 1), 2**30)


def _is_goal(
    model: _Model,
    state: MultiShapeState,
) -> bool:
    positions, _selected = state
    return all(
        tuple(sorted(positions[index] for index in indices))
        == tuple(sorted(goals))
        for indices, goals in model.goal_families
    )


def _heuristic(
    model: _Model,
    state: MultiShapeState,
) -> int:
    positions, _selected = state
    return sum(
        _family_assignment_cost(
            tuple(positions[index] for index in indices),
            goals,
            model.stride,
        )
        for indices, goals in model.goal_families
    )


def _search(
    model: _Model,
) -> tuple[SearchAction, ...]:
    start = _canonical_state(
        model,
        model.initial_positions,
        model.selected_index,
    )
    if _is_goal(model, start):
        return ()
    serial = itertools.count()
    frontier: list[
        tuple[int, int, int, MultiShapeState]
    ] = [(_heuristic(model, start), 0, next(serial), start)]
    best = {start: 0}
    parent: dict[
        MultiShapeState,
        tuple[MultiShapeState, SearchAction],
    ] = {}
    found: MultiShapeState | None = None
    movement_actions: tuple[SearchAction, ...] = tuple(
        ("move", action_id)
        for action_id, _delta in _movement_deltas(model)
    )
    while frontier:
        _priority, cost, _order, state = heapq.heappop(frontier)
        if cost != best[state]:
            continue
        if _is_goal(model, state):
            found = state
            break
        selection_actions: tuple[SearchAction, ...] = tuple(
            ("select", index)
            for index in model.selectable_indices
            if index != state[1]
        )
        for action in (*movement_actions, *selection_actions):
            if len(best) >= model.parameters.maximum_search_states:
                break
            next_state = _transition(model, state, action)
            if next_state == state:
                continue
            next_cost = cost + 1
            if next_cost >= best.get(next_state, 2**31):
                continue
            best[next_state] = next_cost
            parent[next_state] = (state, action)
            heapq.heappush(
                frontier,
                (
                    next_cost + _heuristic(model, next_state),
                    next_cost,
                    next(serial),
                    next_state,
                ),
            )
    if found is None:
        return ()
    reversed_actions: list[SearchAction] = []
    cursor = found
    while cursor != start:
        previous, action = parent[cursor]
        reversed_actions.append(action)
        cursor = previous
    plan = tuple(reversed(reversed_actions))
    if len(plan) > model.parameters.maximum_plan_actions:
        return ()
    return plan


def _model_payload(
    model: _Model,
    state: MultiShapeState,
) -> dict[str, object]:
    positions, selected = state
    return {
        "entities": [
            {
                "selectable": entity.selectable,
                "color": entity.color,
                "width": entity.width,
                "height": entity.height,
                "mask": entity.mask,
                "position": positions[index],
            }
            for index, entity in enumerate(model.entities)
        ],
        "selected": selected,
        "goal_families": [
            {
                "indices": indices,
                "goals": goals,
            }
            for indices, goals in model.goal_families
        ],
        "height": model.height,
        "stride": model.stride,
        "target_colors": sorted(model.target_colors),
        "walkable_color": model.walkable_color,
        "width": model.width,
    }


def _state_signature(
    model: _Model,
    state: MultiShapeState,
) -> str:
    return "multi-shape-state:" + digest_object(
        {
            "operator": MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
            "model": _model_payload(model, state),
        }
    )


def _observation_evidence(
    model: _Model,
    state: MultiShapeState,
) -> str:
    return "multi-shape-observation:" + json.dumps(
        _model_payload(model, state),
        separators=(",", ":"),
        sort_keys=True,
    )


def _transition_terrain_digest(
    model: _Model,
    predecessor: MultiShapeState,
    expected: MultiShapeState,
) -> str:
    before_positions, before_selected = predecessor
    after_positions, after_selected = expected
    if not (
        len(before_positions)
        == len(after_positions)
        == len(model.entities)
    ):
        return ""
    terrain = [list(row) for row in model.terrain]
    for index, (start, end) in enumerate(
        zip(before_positions, after_positions, strict=True)
    ):
        difference = (end[0] - start[0], end[1] - start[1])
        if (
            (difference[0] and difference[1])
            or difference[0] % model.stride
            or difference[1] % model.stride
        ):
            return ""
        step = (
            (difference[0] > 0) - (difference[0] < 0),
            (difference[1] > 0) - (difference[1] < 0),
        )
        count = (
            max(abs(difference[0]), abs(difference[1]))
            // model.stride
        )
        for offset in range(count + 1):
            position = (
                start[0] + step[0] * model.stride * offset,
                start[1] + step[1] * model.stride * offset,
            )
            for x, y in _absolute_pixels(
                position,
                model.entities[index].mask,
            ):
                if 0 <= x < model.width and 0 <= y < model.height:
                    terrain[y][x] = -1
    return digest_object(
        {
            "terrain": tuple(tuple(row) for row in terrain),
            "selected_before": before_selected,
            "selected_after": after_selected,
        }
    )


def _visual_action(
    model: _Model,
    instruction: SemanticOperatorInstruction,
    action: SearchAction,
    *,
    index: int,
    state: MultiShapeState,
    predecessor_state: MultiShapeState | None,
    predecessor_action: SearchAction | None,
) -> VisualAction:
    kind, value = action
    payload = {
        "operator": instruction.operator_id,
        "index": index,
        "action": action,
        "state": state,
    }
    predecessor_evidence: tuple[str, ...] = ()
    if predecessor_state is not None and predecessor_action is not None:
        predecessor_evidence = (
            "multi-shape-predecessor:"
            + json.dumps(
                _model_payload(model, predecessor_state),
                separators=(",", ":"),
                sort_keys=True,
            ),
            "multi-shape-predecessor-action:"
            + json.dumps(
                predecessor_action,
                separators=(",", ":"),
            ),
            "multi-shape-transition-terrain:"
            + _transition_terrain_digest(
                model,
                predecessor_state,
                state,
            ),
        )
    evidence = (
        instruction.operator_id,
        f"operator-prototype:{instruction.operator_id}",
        "rendered-multi-actor-shape-target-relation",
        "observation-derived-selection-point",
        "observation-derived-outline-interior-mask",
        "observation-derived-bounded-impulse-search",
        "multi-shape-plan-terrain:" + digest_object(model.terrain),
        "multi-shape-current-action:"
        + json.dumps(action, separators=(",", ":")),
        _state_signature(model, state),
        _observation_evidence(model, state),
        *predecessor_evidence,
        *instruction.provenance,
    )
    if kind == "move":
        return VisualAction(
            key="semantic-multi-shape-push:"
            + digest_object(payload)[:20],
            action_id=value,
            group=0,
            evidence=evidence,
        )
    entity = model.entities[value]
    position = state[0][value]
    point = (
        position[0] + entity.width // 2,
        position[1] + entity.height // 2,
    )
    return VisualAction(
        key="semantic-multi-shape-push:"
        + digest_object({**payload, "point": point})[:20],
        action_id=instruction.action_id,
        group=0,
        x=point[0],
        y=point[1],
        evidence=evidence,
    )


def multi_actor_shape_push_target_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Derive a complete multi-actor shape-placement plan."""

    parameters = _Parameters.from_instruction(instruction)
    if parameters is None:
        return ()
    required_actions = {
        parameters.click_action,
        parameters.up_action,
        parameters.down_action,
        parameters.left_action,
        parameters.right_action,
    }
    if not required_actions.issubset(available_actions):
        return ()
    model = _model(grid, parameters)
    if model is None:
        return ()
    search_plan = _search(model)
    if not search_plan:
        return ()
    state = _canonical_state(
        model,
        model.initial_positions,
        model.selected_index,
    )
    actions: list[VisualAction] = []
    predecessor_state: MultiShapeState | None = None
    predecessor_action: SearchAction | None = None
    for index, action in enumerate(search_plan):
        actions.append(
            _visual_action(
                model,
                instruction,
                action,
                index=index,
                state=state,
                predecessor_state=predecessor_state,
                predecessor_action=predecessor_action,
            )
        )
        predecessor_state = state
        predecessor_action = action
        state = _transition(model, state, action)
    return tuple(actions)


def _pair(value: object) -> Position | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in value
        )
    ):
        return None
    return value[0], value[1]


def _payload_state(
    payload: dict[str, object],
) -> MultiShapeState | None:
    raw_entities = payload.get("entities")
    selected = payload.get("selected")
    if (
        not isinstance(raw_entities, list)
        or isinstance(selected, bool)
        or not isinstance(selected, int)
    ):
        return None
    positions = tuple(
        _pair(entity.get("position"))
        if isinstance(entity, dict)
        else None
        for entity in raw_entities
    )
    if (
        any(position is None for position in positions)
        or not 0 <= selected < len(positions)
    ):
        return None
    return (
        tuple(
            position
            for position in positions
            if position is not None
        ),
        selected,
    )


def _static_payload(
    payload: dict[str, object],
) -> dict[str, object] | None:
    raw_entities = payload.get("entities")
    if not isinstance(raw_entities, list):
        return None
    entities: list[dict[str, object]] = []
    for raw_entity in raw_entities:
        if not isinstance(raw_entity, dict):
            return None
        entity = dict(raw_entity)
        entity.pop("position", None)
        entities.append(entity)
    static = dict(payload)
    static["entities"] = entities
    static.pop("selected", None)
    return static


def _position_between_transition(
    predecessor: Position,
    expected: Position,
    actual: Position,
    *,
    stride: int,
) -> bool:
    if predecessor == expected:
        return actual == expected
    if predecessor[0] == expected[0]:
        return (
            actual[0] == predecessor[0]
            and min(predecessor[1], expected[1])
            <= actual[1]
            <= max(predecessor[1], expected[1])
            and (actual[1] - predecessor[1]) % stride == 0
        )
    if predecessor[1] == expected[1]:
        return (
            actual[1] == predecessor[1]
            and min(predecessor[0], expected[0])
            <= actual[0]
            <= max(predecessor[0], expected[0])
            and (actual[0] - predecessor[0]) % stride == 0
        )
    return False


def _positions_between_transition(
    predecessor: MultiShapeState,
    expected: MultiShapeState,
    actual: MultiShapeState,
    *,
    stride: int,
) -> bool:
    before_positions, before_selected = predecessor
    expected_positions, expected_selected = expected
    actual_positions, actual_selected = actual
    return (
        stride > 0
        and len(before_positions)
        == len(expected_positions)
        == len(actual_positions)
        and actual != expected
        and before_selected
        == expected_selected
        == actual_selected
        and all(
            _position_between_transition(
                before,
                after,
                observed,
                stride=stride,
            )
            for before, after, observed in zip(
                before_positions,
                expected_positions,
                actual_positions,
                strict=True,
            )
        )
    )


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


def multi_actor_shape_push_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> MultiShapeObservationStatus:
    """Classify a queued action against a rendered multi-actor state."""

    expected_signatures = tuple(
        item
        for item in action.evidence
        if item.startswith("multi-shape-state:")
    )
    current_actions = tuple(
        item.removeprefix("multi-shape-current-action:")
        for item in action.evidence
        if item.startswith("multi-shape-current-action:")
    )
    observations = tuple(
        item.removeprefix("multi-shape-observation:")
        for item in action.evidence
        if item.startswith("multi-shape-observation:")
    )
    predecessors = tuple(
        item.removeprefix("multi-shape-predecessor:")
        for item in action.evidence
        if item.startswith("multi-shape-predecessor:")
    )
    predecessor_actions = tuple(
        item.removeprefix("multi-shape-predecessor-action:")
        for item in action.evidence
        if item.startswith("multi-shape-predecessor-action:")
    )
    transition_terrains = tuple(
        item.removeprefix("multi-shape-transition-terrain:")
        for item in action.evidence
        if item.startswith("multi-shape-transition-terrain:")
    )
    if (
        len(expected_signatures) != 1
        or len(current_actions) != 1
        or len(observations) != 1
        or len(predecessors) != 1
        or len(predecessor_actions) != 1
        or len(transition_terrains) != 1
    ):
        return "MISMATCH"
    parameters = _Parameters.from_instruction(instruction)
    if parameters is None:
        return "MISMATCH"
    try:
        raw = json.loads(observations[0])
        predecessor = json.loads(predecessors[0])
        raw_predecessor_action = json.loads(predecessor_actions[0])
        raw_current_action = json.loads(current_actions[0])
    except json.JSONDecodeError:
        return "MISMATCH"
    predecessor_action = _search_action(raw_predecessor_action)
    current_action = _search_action(raw_current_action)
    if (
        not isinstance(raw, dict)
        or not isinstance(predecessor, dict)
        or predecessor_action is None
        or current_action is None
    ):
        return "MISMATCH"
    kind, value = current_action
    if (
        (kind == "move" and action.action_id != value)
        or (kind == "select" and action.action_id != parameters.click_action)
    ):
        return "MISMATCH"
    expected_signature = "multi-shape-state:" + digest_object(
        {
            "operator": MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
            "model": raw,
        }
    )
    if expected_signatures[0] != expected_signature:
        return "MISMATCH"
    walkable_hint = raw.get("walkable_color")
    if (
        isinstance(walkable_hint, bool)
        or not isinstance(walkable_hint, int)
    ):
        return "MISMATCH"
    model = _model(
        grid,
        parameters,
        walkable_hint=walkable_hint,
    )
    if model is None:
        return "UNAVAILABLE"
    actual_state = _canonical_state(
        model,
        model.initial_positions,
        model.selected_index,
    )
    actual = json.loads(
        json.dumps(
            _model_payload(model, actual_state),
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    expected_static = _static_payload(raw)
    predecessor_static = _static_payload(predecessor)
    actual_static = _static_payload(actual)
    if (
        expected_static is None
        or predecessor_static is None
        or actual_static is None
        or expected_static != predecessor_static
        or expected_static != actual_static
    ):
        return "MISMATCH"
    expected_state = _payload_state(raw)
    predecessor_state = _payload_state(predecessor)
    if (
        expected_state is None
        or predecessor_state is None
        or _transition(
            model,
            predecessor_state,
            predecessor_action,
        )
        != expected_state
        or _transition_terrain_digest(
            model,
            predecessor_state,
            expected_state,
        )
        != transition_terrains[0]
    ):
        return "MISMATCH"
    if actual == raw:
        return "MATCH"
    return (
        "UNAVAILABLE"
        if _positions_between_transition(
            predecessor_state,
            expected_state,
            actual_state,
            stride=model.stride,
        )
        else "MISMATCH"
    )


def multi_actor_shape_push_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the P-bounded transient observation limit."""

    parameters = _Parameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


__all__ = [
    "MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR",
    "multi_actor_shape_push_observation_status",
    "multi_actor_shape_push_target_plan",
    "multi_actor_shape_push_transition_observation_limit",
]
