"""Rendered marker-controlled actor and shape-target push routing."""

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

MARKER_SHAPE_PUSH_TARGET_OPERATOR = (
    "marker-controlled-shape-target-route-v3"
)

Position: TypeAlias = tuple[int, int]
Mask: TypeAlias = tuple[Point, ...]
ShapePushState: TypeAlias = tuple[Position, ...]
ShapePushObservationStatus: TypeAlias = Literal[
    "MATCH",
    "MISMATCH",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class _ShapePushParameters:
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
    push_through_color: int
    maximum_search_states: int
    maximum_plan_actions: int
    maximum_transition_observations: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _ShapePushParameters | None:
        if instruction.operator_id != MARKER_SHAPE_PUSH_TARGET_OPERATOR:
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
            or parsed["minimum_pushable_count"] < 1
            or parsed["maximum_pushable_count"]
            < parsed["minimum_pushable_count"]
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
class _ShapeTarget:
    color: int
    component_position: Position
    goal_position: Position
    width: int
    height: int
    mask: Mask

    @property
    def family(self) -> tuple[int, int, Mask]:
        return self.width, self.height, self.mask


@dataclass(frozen=True, slots=True)
class _ShapeEntity:
    role: str
    color: int
    position: Position
    width: int
    height: int
    mask: Mask
    marker_color: int | None = None

    @property
    def family(self) -> tuple[str, int, int, int, Mask]:
        return (
            self.role,
            self.color,
            self.width,
            self.height,
            self.mask,
        )


@dataclass(frozen=True, slots=True)
class _ShapePushModel:
    width: int
    height: int
    terrain: Grid
    entities: tuple[_ShapeEntity, ...]
    actor_goal: Position
    push_goal_families: tuple[
        tuple[tuple[int, ...], tuple[Position, ...]],
        ...,
    ]
    stride: int
    walkable_color: int
    target_colors: frozenset[int]
    parameters: _ShapePushParameters

    @property
    def initial_positions(self) -> ShapePushState:
        return tuple(entity.position for entity in self.entities)

    @property
    def masks(self) -> tuple[Mask, ...]:
        return tuple(entity.mask for entity in self.entities)


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
    parameters: _ShapePushParameters,
) -> _ShapeTarget | None:
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
            (
                x - enclosed_x0,
                y - enclosed_y0,
            )
            for x, y in enclosed
        )
    )
    if not mask:
        return None
    return _ShapeTarget(
        color=component.color,
        component_position=(x0, y0),
        goal_position=(enclosed_x0, enclosed_y0),
        width=width,
        height=height,
        mask=mask,
    )


def _shape_targets(
    grid: Grid,
    parameters: _ShapePushParameters,
) -> tuple[_ShapeTarget, ...]:
    enclosed = tuple(
        target
        for component in connected_components(grid)
        if (
            target := _enclosed_target(component, parameters)
        )
        is not None
    )
    grouped: dict[int, list[_ShapeTarget]] = {}
    for target in enclosed:
        grouped.setdefault(target.color, []).append(target)
    families = tuple(
        tuple(targets)
        for _color, targets in sorted(grouped.items())
        if (
            parameters.minimum_pushable_count + 1
            <= len(targets)
            <= parameters.maximum_pushable_count + 1
        )
    )
    if len(families) != 1:
        return ()
    targets = families[0]
    return tuple(
        sorted(
            targets,
            key=lambda item: (
                item.color,
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
    parameters: _ShapePushParameters,
    *,
    x0: int,
    y0: int,
    width: int,
    height: int,
) -> _ShapeEntity | None:
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
    marker = next(iter(marker_values))
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
    object_color = next(iter(object_values))
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
    return _ShapeEntity(
        role="actor",
        color=object_color,
        position=(x0, y0),
        width=width,
        height=height,
        mask=_full_rectangle(width, height),
        marker_color=marker,
    )


def _actor_and_goal(
    grid: Grid,
    targets: tuple[_ShapeTarget, ...],
    parameters: _ShapePushParameters,
) -> tuple[_ShapeEntity, _ShapeTarget] | None:
    matches: dict[
        tuple[int, int, int, int, int],
        tuple[_ShapeEntity, list[_ShapeTarget]],
    ] = {}
    for target in targets:
        if target.mask != _full_rectangle(
            target.width,
            target.height,
        ):
            continue
        for y0 in range(len(grid) - target.height + 1):
            for x0 in range(len(grid[0]) - target.width + 1):
                actor = _actor_at(
                    grid,
                    parameters,
                    x0=x0,
                    y0=y0,
                    width=target.width,
                    height=target.height,
                )
                if actor is None:
                    continue
                key = (
                    actor.position[0],
                    actor.position[1],
                    actor.width,
                    actor.height,
                    actor.color,
                )
                if key not in matches:
                    matches[key] = (actor, [])
                matches[key][1].append(target)
    candidates = tuple(
        (actor, tuple(dict.fromkeys(goals)))
        for actor, goals in matches.values()
    )
    if len(candidates) != 1:
        return None
    actor, goals = candidates[0]
    if (
        actor.marker_color != parameters.selected_marker_color
        or len(goals) != 1
    ):
        return None
    return actor, goals[0]


def _normalized_component_mask(
    component: VisualComponent,
) -> Mask:
    x0, y0, _x1, _y1 = component.bbox
    return tuple(
        sorted((x - x0, y - y0) for x, y in component.pixels)
    )


def _pushable_entities(
    grid: Grid,
    targets: tuple[_ShapeTarget, ...],
    *,
    actor_target: _ShapeTarget,
    walkable_color: int,
    parameters: _ShapePushParameters,
) -> tuple[
    tuple[_ShapeEntity, ...],
    tuple[tuple[tuple[int, ...], tuple[Position, ...]], ...],
] | None:
    remaining_targets = tuple(
        target for target in targets if target is not actor_target
    )
    grouped_targets: dict[
        tuple[int, int, Mask],
        list[_ShapeTarget],
    ] = {}
    for target in remaining_targets:
        grouped_targets.setdefault(target.family, []).append(target)
    if not grouped_targets:
        return None
    target_colors = {target.color for target in targets}
    components = connected_components(grid)
    entities: list[_ShapeEntity] = []
    families: list[
        tuple[tuple[int, ...], tuple[Position, ...]]
    ] = []
    for family, family_targets in sorted(
        grouped_targets.items(),
        key=lambda item: item[0],
    ):
        width, height, mask = family
        matching_components = tuple(
            component
            for component in components
            if (
                component.color not in target_colors
                and component.color != walkable_color
                and component.width == width
                and component.height == height
                and _normalized_component_mask(component) == mask
            )
        )
        if len(matching_components) != len(family_targets):
            return None
        colors = {component.color for component in matching_components}
        if len(colors) != 1:
            return None
        start = len(entities) + 1
        for component in sorted(
            matching_components,
            key=lambda item: (
                item.bbox[1],
                item.bbox[0],
            ),
        ):
            entities.append(
                _ShapeEntity(
                    role="pushable",
                    color=component.color,
                    position=(component.bbox[0], component.bbox[1]),
                    width=width,
                    height=height,
                    mask=mask,
                )
            )
        indices = tuple(
            range(start, start + len(matching_components))
        )
        goals = tuple(
            sorted(target.goal_position for target in family_targets)
        )
        families.append((indices, goals))
    if (
        not parameters.minimum_pushable_count
        <= len(entities)
        <= parameters.maximum_pushable_count
    ):
        return None
    return tuple(entities), tuple(families)


def _walkable_color(
    grid: Grid,
    targets: tuple[_ShapeTarget, ...],
    entities: tuple[_ShapeEntity, ...],
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
    return winners[0] if len(winners) == 1 else None


def _playable_height(
    grid: Grid,
    *,
    walkable_color: int,
) -> int:
    """Exclude a rendered footer behind a near-bottom separator."""

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


def _shape_push_model(
    grid: Grid,
    parameters: _ShapePushParameters,
    *,
    walkable_hint: int | None = None,
) -> _ShapePushModel | None:
    if not grid or not grid[0]:
        return None
    targets = _shape_targets(grid, parameters)
    actor_pair = _actor_and_goal(grid, targets, parameters)
    if actor_pair is None:
        return None
    actor, actor_target = actor_pair
    if walkable_hint is None:
        walkable = _walkable_color(grid, targets, (actor,))
        if walkable is None:
            return None
    else:
        excluded_colors = {
            actor.color,
            actor.marker_color,
            *(target.color for target in targets),
        }
        if (
            isinstance(walkable_hint, bool)
            or walkable_hint in excluded_colors
            or not any(walkable_hint in row for row in grid)
        ):
            return None
        walkable = walkable_hint
    push_result = _pushable_entities(
        grid,
        targets,
        actor_target=actor_target,
        walkable_color=walkable,
        parameters=parameters,
    )
    if push_result is None:
        return None
    pushables, push_goal_families = push_result
    entities = (actor, *pushables)
    if walkable_hint is None:
        confirmed_walkable = _walkable_color(grid, targets, entities)
        if confirmed_walkable != walkable:
            return None
    stride = math.gcd(actor.width, actor.height)
    if stride < 1 or any(
        (goal[0] - actor.position[0]) % stride
        or (goal[1] - actor.position[1]) % stride
        for goal in (actor_target.goal_position,)
    ):
        return None
    for indices, goals in push_goal_families:
        positions = tuple(entities[index].position for index in indices)
        if any(
            (position[0] - goal[0]) % stride
            or (position[1] - goal[1]) % stride
            for position in positions
            for goal in goals
        ):
            return None
    height = _playable_height(
        grid,
        walkable_color=walkable,
    )
    terrain = [list(row) for row in grid[:height]]
    for entity in entities:
        x0, y0 = entity.position
        for dx, dy in entity.mask:
            terrain[y0 + dy][x0 + dx] = walkable
    return _ShapePushModel(
        width=len(grid[0]),
        height=height,
        terrain=tuple(tuple(row) for row in terrain),
        entities=entities,
        actor_goal=actor_target.goal_position,
        push_goal_families=push_goal_families,
        stride=stride,
        walkable_color=walkable,
        target_colors=frozenset(target.color for target in targets),
        parameters=parameters,
    )


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


def _terrain_passable(
    model: _ShapePushModel,
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
    model: _ShapePushModel,
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
    model: _ShapePushModel,
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


def _canonical_positions(
    model: _ShapePushModel,
    positions: list[Position],
) -> ShapePushState:
    canonical = list(positions)
    for indices, _goals in model.push_goal_families:
        ordered = sorted(canonical[index] for index in indices)
        for index, position in zip(indices, ordered, strict=True):
            canonical[index] = position
    return tuple(canonical)


def _movement_deltas(
    model: _ShapePushModel,
) -> tuple[tuple[int, Point], ...]:
    stride = model.stride
    return (
        (model.parameters.up_action, (0, -stride)),
        (model.parameters.down_action, (0, stride)),
        (model.parameters.left_action, (-stride, 0)),
        (model.parameters.right_action, (stride, 0)),
    )


def _transition(
    model: _ShapePushModel,
    state: ShapePushState,
    action_id: int,
) -> ShapePushState:
    delta = dict(_movement_deltas(model)).get(action_id)
    if delta is None:
        return state
    actor_next = (
        state[0][0] + delta[0],
        state[0][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        actor_next,
        model.entities[0].mask,
        pushed=False,
    ):
        return state
    collided = tuple(
        index
        for index, position in enumerate(state)
        if (
            index != 0
            and _collides(
                actor_next,
                model.entities[0].mask,
                position,
                model.entities[index].mask,
            )
        )
    )
    mutable = list(state)
    if not collided:
        mutable[0] = actor_next
        return _canonical_positions(model, mutable)
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
                frozenset({0}),
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
    return _canonical_positions(model, mutable)


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
    model: _ShapePushModel,
    state: ShapePushState,
) -> bool:
    if state[0] != model.actor_goal:
        return False
    return all(
        tuple(sorted(state[index] for index in indices))
        == tuple(sorted(goals))
        for indices, goals in model.push_goal_families
    )


def _heuristic(
    model: _ShapePushModel,
    state: ShapePushState,
) -> int:
    cost = (
        abs(state[0][0] - model.actor_goal[0])
        + abs(state[0][1] - model.actor_goal[1])
    ) // model.stride
    return cost + sum(
        _family_assignment_cost(
            tuple(state[index] for index in indices),
            goals,
            model.stride,
        )
        for indices, goals in model.push_goal_families
    )


def _search(
    model: _ShapePushModel,
) -> tuple[int, ...]:
    start = _canonical_positions(
        model,
        list(model.initial_positions),
    )
    if _is_goal(model, start):
        return ()
    serial = itertools.count()
    frontier: list[
        tuple[int, int, int, ShapePushState]
    ] = [(_heuristic(model, start), 0, next(serial), start)]
    best = {start: 0}
    parent: dict[
        ShapePushState,
        tuple[ShapePushState, int],
    ] = {}
    found: ShapePushState | None = None
    actions = tuple(
        action_id
        for action_id, _delta in _movement_deltas(model)
    )
    while frontier:
        _priority, cost, _order, state = heapq.heappop(frontier)
        if cost != best[state]:
            continue
        if _is_goal(model, state):
            found = state
            break
        for action_id in actions:
            if len(best) >= model.parameters.maximum_search_states:
                break
            next_state = _transition(model, state, action_id)
            if next_state == state:
                continue
            next_cost = cost + 1
            if next_cost >= best.get(next_state, 2**31):
                continue
            best[next_state] = next_cost
            parent[next_state] = (state, action_id)
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
    reversed_actions: list[int] = []
    cursor = found
    while cursor != start:
        previous, action_id = parent[cursor]
        reversed_actions.append(action_id)
        cursor = previous
    plan = tuple(reversed(reversed_actions))
    if len(plan) > model.parameters.maximum_plan_actions:
        return ()
    return plan


def _model_payload(
    model: _ShapePushModel,
    state: ShapePushState,
) -> dict[str, object]:
    return {
        "actor": {
            "color": model.entities[0].color,
            "goal": model.actor_goal,
            "mask": model.entities[0].mask,
            "position": state[0],
        },
        "pushables": [
            {
                "color": entity.color,
                "mask": entity.mask,
                "position": state[index],
            }
            for index, entity in enumerate(
                model.entities[1:],
                start=1,
            )
        ],
        "push_goal_families": [
            {
                "indices": indices,
                "goals": goals,
            }
            for indices, goals in model.push_goal_families
        ],
        "height": model.height,
        "stride": model.stride,
        "target_colors": sorted(model.target_colors),
        "walkable_color": model.walkable_color,
        "width": model.width,
    }


def _state_signature(
    model: _ShapePushModel,
    state: ShapePushState,
) -> str:
    return "shape-push-state:" + digest_object(
        {
            "operator": MARKER_SHAPE_PUSH_TARGET_OPERATOR,
            "model": _model_payload(model, state),
        }
    )


def _observation_evidence(
    model: _ShapePushModel,
    state: ShapePushState,
) -> str:
    return "shape-push-observation:" + json.dumps(
        _model_payload(model, state),
        separators=(",", ":"),
        sort_keys=True,
    )


def _transition_terrain_digest(
    model: _ShapePushModel,
    predecessor: ShapePushState,
    expected: ShapePushState,
) -> str:
    if not (
        len(predecessor) == len(expected) == len(model.entities)
    ):
        return ""
    terrain = [list(row) for row in model.terrain]
    for index, (start, end) in enumerate(
        zip(predecessor, expected, strict=True)
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
        count = max(abs(difference[0]), abs(difference[1])) // model.stride
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
    return digest_object(tuple(tuple(row) for row in terrain))


def _visual_action(
    model: _ShapePushModel,
    instruction: SemanticOperatorInstruction,
    action_id: int,
    *,
    index: int,
    state: ShapePushState,
    predecessor_state: ShapePushState | None,
    predecessor_action_id: int | None,
) -> VisualAction:
    payload = {
        "operator": instruction.operator_id,
        "index": index,
        "action": action_id,
        "state": state,
    }
    predecessor_evidence: tuple[str, ...] = ()
    if (
        predecessor_state is not None
        and predecessor_action_id is not None
    ):
        predecessor_evidence = (
            "shape-push-predecessor:"
            + json.dumps(
                _model_payload(model, predecessor_state),
                separators=(",", ":"),
                sort_keys=True,
            ),
            f"shape-push-predecessor-action:{predecessor_action_id}",
            "shape-push-transition-terrain:"
            + _transition_terrain_digest(
                model,
                predecessor_state,
                state,
            ),
        )
    return VisualAction(
        key="semantic-shape-push:"
        + digest_object(payload)[:20],
        action_id=action_id,
        group=0,
        evidence=(
            instruction.operator_id,
            f"operator-prototype:{instruction.operator_id}",
            "rendered-marker-actor-shape-target-relation",
            "observation-derived-outline-interior-mask",
            "observation-derived-bounded-impulse-search",
            "shape-push-plan-terrain:" + digest_object(model.terrain),
            f"shape-push-current-action:{action_id}",
            _state_signature(model, state),
            _observation_evidence(model, state),
            *predecessor_evidence,
            *instruction.provenance,
        ),
    )


def marker_shape_push_target_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Derive a bounded actor-mediated shape placement plan."""

    parameters = _ShapePushParameters.from_instruction(instruction)
    if parameters is None:
        return ()
    required_actions = {
        parameters.up_action,
        parameters.down_action,
        parameters.left_action,
        parameters.right_action,
        parameters.click_action,
    }
    if not required_actions.issubset(available_actions):
        return ()
    model = _shape_push_model(grid, parameters)
    if model is None:
        return ()
    search_plan = _search(model)
    if not search_plan:
        return ()
    state = _canonical_positions(
        model,
        list(model.initial_positions),
    )
    actions: list[VisualAction] = []
    predecessor_state: ShapePushState | None = None
    predecessor_action_id: int | None = None
    for index, action_id in enumerate(search_plan):
        actions.append(
            _visual_action(
                model,
                instruction,
                action_id,
                index=index,
                state=state,
                predecessor_state=predecessor_state,
                predecessor_action_id=predecessor_action_id,
            )
        )
        predecessor_state = state
        predecessor_action_id = action_id
        state = _transition(model, state, action_id)
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


def _payload_positions(
    payload: dict[str, object],
) -> ShapePushState | None:
    actor = payload.get("actor")
    pushables = payload.get("pushables")
    if not isinstance(actor, dict) or not isinstance(pushables, list):
        return None
    actor_position = _pair(actor.get("position"))
    pushable_positions = tuple(
        _pair(item.get("position")) if isinstance(item, dict) else None
        for item in pushables
    )
    if actor_position is None or any(
        position is None for position in pushable_positions
    ):
        return None
    return (
        actor_position,
        *(
            position
            for position in pushable_positions
            if position is not None
        ),
    )


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
    predecessor: ShapePushState,
    expected: ShapePushState,
    actual: ShapePushState,
    *,
    stride: int,
) -> bool:
    return (
        stride > 0
        and len(predecessor) == len(expected) == len(actual)
        and actual != expected
        and all(
            _position_between_transition(
                before,
                after,
                observed,
                stride=stride,
            )
            for before, after, observed in zip(
                predecessor,
                expected,
                actual,
                strict=True,
            )
        )
    )


def _static_payload(
    payload: dict[str, object],
) -> dict[str, object] | None:
    actor = payload.get("actor")
    pushables = payload.get("pushables")
    if not isinstance(actor, dict) or not isinstance(pushables, list):
        return None
    actor_static = dict(actor)
    actor_static.pop("position", None)
    pushable_static: list[dict[str, object]] = []
    for item in pushables:
        if not isinstance(item, dict):
            return None
        item_static = dict(item)
        item_static.pop("position", None)
        pushable_static.append(item_static)
    static = dict(payload)
    static["actor"] = actor_static
    static["pushables"] = pushable_static
    return static


def marker_shape_push_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> ShapePushObservationStatus:
    """Classify a queued action against one rendered shape-push state."""

    expected_signatures = tuple(
        item
        for item in action.evidence
        if item.startswith("shape-push-state:")
    )
    current_actions = tuple(
        item.removeprefix("shape-push-current-action:")
        for item in action.evidence
        if item.startswith("shape-push-current-action:")
    )
    observations = tuple(
        item.removeprefix("shape-push-observation:")
        for item in action.evidence
        if item.startswith("shape-push-observation:")
    )
    predecessors = tuple(
        item.removeprefix("shape-push-predecessor:")
        for item in action.evidence
        if item.startswith("shape-push-predecessor:")
    )
    predecessor_actions = tuple(
        item.removeprefix("shape-push-predecessor-action:")
        for item in action.evidence
        if item.startswith("shape-push-predecessor-action:")
    )
    transition_terrains = tuple(
        item.removeprefix("shape-push-transition-terrain:")
        for item in action.evidence
        if item.startswith("shape-push-transition-terrain:")
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
    parameters = _ShapePushParameters.from_instruction(instruction)
    if parameters is None:
        return "MISMATCH"
    try:
        raw = json.loads(observations[0])
        predecessor = json.loads(predecessors[0])
        predecessor_action_id = json.loads(predecessor_actions[0])
        current_action_id = json.loads(current_actions[0])
    except json.JSONDecodeError:
        return "MISMATCH"
    if (
        not isinstance(raw, dict)
        or not isinstance(predecessor, dict)
        or isinstance(predecessor_action_id, bool)
        or not isinstance(predecessor_action_id, int)
        or isinstance(current_action_id, bool)
        or not isinstance(current_action_id, int)
        or current_action_id != action.action_id
    ):
        return "MISMATCH"
    expected_signature = "shape-push-state:" + digest_object(
        {
            "operator": MARKER_SHAPE_PUSH_TARGET_OPERATOR,
            "model": raw,
        }
    )
    if expected_signatures[0] != expected_signature:
        return "MISMATCH"
    walkable_hint = raw.get("walkable_color")
    if isinstance(walkable_hint, bool) or not isinstance(
        walkable_hint,
        int,
    ):
        return "MISMATCH"
    model = _shape_push_model(
        grid,
        parameters,
        walkable_hint=walkable_hint,
    )
    if model is None:
        return "UNAVAILABLE"
    actual_state = _canonical_positions(
        model,
        list(model.initial_positions),
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
    ):
        return "MISMATCH"
    expected_positions = _payload_positions(raw)
    predecessor_positions = _payload_positions(predecessor)
    if (
        expected_positions is None
        or predecessor_positions is None
        or predecessor_action_id
        not in dict(_movement_deltas(model))
        or _transition(
            model,
            predecessor_positions,
            predecessor_action_id,
        )
        != expected_positions
        or _transition_terrain_digest(
            model,
            predecessor_positions,
            expected_positions,
        )
        != transition_terrains[0]
    ):
        return "MISMATCH"
    if actual == raw:
        return "MATCH"
    if expected_static != actual_static:
        return "MISMATCH"
    actual_positions = _payload_positions(actual)
    if actual_positions is None:
        return "MISMATCH"
    return (
        "UNAVAILABLE"
        if _positions_between_transition(
            predecessor_positions,
            expected_positions,
            actual_positions,
            stride=model.stride,
        )
        else "MISMATCH"
    )


def marker_shape_push_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the P-bounded transient-frame observation limit."""

    parameters = _ShapePushParameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


__all__ = [
    "MARKER_SHAPE_PUSH_TARGET_OPERATOR",
    "marker_shape_push_observation_status",
    "marker_shape_push_target_plan",
    "marker_shape_push_transition_observation_limit",
]
