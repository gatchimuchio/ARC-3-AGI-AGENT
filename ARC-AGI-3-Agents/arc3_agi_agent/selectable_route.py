"""Rendered multi-object selection, pushing, and target routing."""

from __future__ import annotations

import heapq
import itertools
import json
import math
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

SELECTABLE_ROUTE_TARGET_OPERATOR = "selectable-object-target-route-v2"

Position: TypeAlias = tuple[int, int]
RouteState: TypeAlias = tuple[tuple[Position, ...], int]
SearchAction: TypeAlias = tuple[Literal["move", "select"], int]
RouteObservationStatus: TypeAlias = Literal[
    "MATCH",
    "MISMATCH",
    "UNAVAILABLE",
]


@dataclass(frozen=True, slots=True)
class _RouteParameters:
    click_action: int
    up_action: int
    down_action: int
    left_action: int
    right_action: int
    selected_marker_color: int
    unselected_marker_color: int
    released_marker_color: int
    push_through_color: int
    target_inset: int
    minimum_object_count: int
    maximum_object_count: int
    minimum_push_steps: int
    maximum_push_steps: int
    maximum_search_states: int
    maximum_plan_actions: int
    maximum_transition_observations: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _RouteParameters | None:
        if instruction.operator_id != SELECTABLE_ROUTE_TARGET_OPERATOR:
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
            "push_through_color",
            "target_inset",
            "minimum_object_count",
            "maximum_object_count",
            "minimum_push_steps",
            "maximum_push_steps",
            "maximum_search_states",
            "maximum_plan_actions",
            "maximum_transition_observations",
        )
        parsed: dict[str, int] = {}
        for name in names:
            value = raw.get(name)
            if not isinstance(value, int) or isinstance(value, bool):
                return None
            parsed[name] = value
        movement_actions = {
            parsed["up_action"],
            parsed["down_action"],
            parsed["left_action"],
            parsed["right_action"],
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
            or len(
                {
                    parsed["selected_marker_color"],
                    parsed["unselected_marker_color"],
                    parsed["released_marker_color"],
                }
            )
            != 3
            or parsed["target_inset"] < 1
            or parsed["minimum_object_count"] < 3
            or parsed["maximum_object_count"]
            < parsed["minimum_object_count"]
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
class _RouteObject:
    color: int
    width: int
    height: int
    position: Position
    marker_color: int


@dataclass(frozen=True, slots=True)
class _RouteModel:
    width: int
    height: int
    terrain: Grid
    objects: tuple[_RouteObject, ...]
    goals: tuple[Position, ...]
    selected_index: int
    stride: int
    walkable_color: int
    target_color: int
    parameters: _RouteParameters

    @property
    def sizes(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (item.width, item.height) for item in self.objects
        )

    @property
    def initial_positions(self) -> tuple[Position, ...]:
        return tuple(item.position for item in self.objects)


def _is_border_ring(component: VisualComponent) -> bool:
    if (
        component.rectangular
        or component.width < 3
        or component.height < 3
    ):
        return False
    x0, y0, x1, y1 = component.bbox
    border = {
        (x, y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
        if x in {x0, x1} or y in {y0, y1}
    }
    return set(component.pixels) == border


def _target_families(
    components: tuple[VisualComponent, ...],
    parameters: _RouteParameters,
) -> tuple[tuple[VisualComponent, ...], ...]:
    grouped: dict[int, list[VisualComponent]] = {}
    for component in components:
        object_width = component.width - 2 * parameters.target_inset
        object_height = component.height - 2 * parameters.target_inset
        if (
            not _is_border_ring(component)
            or not 3 <= object_width <= 12
            or not 3 <= object_height <= 12
        ):
            continue
        grouped.setdefault(component.color, []).append(component)
    families: list[tuple[VisualComponent, ...]] = []
    for targets in grouped.values():
        sizes = {
            (
                target.width - 2 * parameters.target_inset,
                target.height - 2 * parameters.target_inset,
            )
            for target in targets
        }
        if (
            parameters.minimum_object_count
            <= len(targets)
            <= parameters.maximum_object_count
            and len(sizes) == len(targets)
        ):
            families.append(
                tuple(
                    sorted(
                        targets,
                        key=lambda item: (
                            item.width,
                            item.height,
                            item.bbox[1],
                            item.bbox[0],
                        ),
                    )
                )
            )
    return tuple(
        sorted(
            families,
            key=lambda family: (
                family[0].color,
                tuple(item.bbox for item in family),
            ),
        )
    )


def _object_at(
    grid: Grid,
    parameters: _RouteParameters,
    *,
    x0: int,
    y0: int,
    width: int,
    height: int,
    stride: int,
) -> _RouteObject | None:
    if width % stride or height % stride:
        return None
    marker_width = width // stride
    marker_height = height // stride
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
    return _RouteObject(
        color=object_color,
        width=width,
        height=height,
        position=(x0, y0),
        marker_color=marker,
    )


def _route_objects_from_sizes(
    grid: Grid,
    sizes: tuple[tuple[int, int], ...],
    parameters: _RouteParameters,
    *,
    stride: int,
) -> tuple[_RouteObject, ...]:
    if (
        stride < 1
        or not sizes
        or len(set(sizes)) != len(sizes)
        or any(
            width < 3
            or height < 3
            or width > 12
            or height > 12
            or width % stride
            or height % stride
            for width, height in sizes
        )
    ):
        return ()
    matches_by_size: list[tuple[_RouteObject, ...]] = []
    for width, height in sizes:
        matches = tuple(
            item
            for y0 in range(len(grid) - height + 1)
            for x0 in range(len(grid[0]) - width + 1)
            if (
                item := _object_at(
                    grid,
                    parameters,
                    x0=x0,
                    y0=y0,
                    width=width,
                    height=height,
                    stride=stride,
                )
            )
            is not None
        )
        if not matches or len(matches) > 32:
            return ()
        matches_by_size.append(matches)
    valid: list[tuple[_RouteObject, ...]] = []
    for combination_index, objects in enumerate(
        itertools.product(*matches_by_size),
        start=1,
    ):
        if combination_index > parameters.maximum_search_states:
            return ()
        if (
            len({item.position for item in objects}) == len(objects)
            and len({item.color for item in objects}) == 1
            and sum(
                item.marker_color == parameters.selected_marker_color
                for item in objects
            )
            == 1
            and not any(
                _overlaps(
                    first.position,
                    (first.width, first.height),
                    second.position,
                    (second.width, second.height),
                )
                for index, first in enumerate(objects)
                for second in objects[index + 1 :]
            )
        ):
            valid.append(objects)
            if len(valid) > 1:
                return ()
    if len(valid) != 1:
        return ()
    objects = valid[0]
    return tuple(
        sorted(
            objects,
            key=lambda item: (
                item.width,
                item.height,
                item.position[1],
                item.position[0],
            ),
        )
    )


def _route_objects_from_targets(
    grid: Grid,
    targets: tuple[VisualComponent, ...],
    parameters: _RouteParameters,
) -> tuple[_RouteObject, ...]:
    sizes = tuple(
        (
            target.width - 2 * parameters.target_inset,
            target.height - 2 * parameters.target_inset,
        )
        for target in targets
    )
    stride = math.gcd(
        *(dimension for size in sizes for dimension in size)
    )
    return _route_objects_from_sizes(
        grid,
        sizes,
        parameters,
        stride=stride,
    )


def _walkable_color(
    grid: Grid,
    targets: tuple[VisualComponent, ...],
) -> int | None:
    values = tuple(
        grid[y][x]
        for target in targets
        for y in range(target.bbox[1] + 1, target.bbox[3])
        for x in range(target.bbox[0] + 1, target.bbox[2])
    )
    if not values:
        return None
    counts = {
        value: values.count(value)
        for value in sorted(set(values))
    }
    maximum = max(counts.values())
    winners = tuple(
        value for value, count in counts.items() if count == maximum
    )
    return winners[0] if len(winners) == 1 else None


def _route_model(
    grid: Grid,
    parameters: _RouteParameters,
) -> _RouteModel | None:
    if not grid or not grid[0]:
        return None
    components = connected_components(grid)
    candidates: list[
        tuple[
            tuple[_RouteObject, ...],
            tuple[VisualComponent, ...],
        ]
    ] = []
    for targets in _target_families(components, parameters):
        objects = _route_objects_from_targets(
            grid,
            targets,
            parameters,
        )
        if len(objects) == len(targets):
            candidates.append((objects, targets))
    if len(candidates) != 1:
        return None
    objects, targets = candidates[0]
    selected = tuple(
        index
        for index, item in enumerate(objects)
        if item.marker_color == parameters.selected_marker_color
    )
    if len(selected) != 1:
        return None
    walkable = _walkable_color(grid, targets)
    if walkable is None:
        return None
    target_colors = {item.color for item in targets}
    if len(target_colors) != 1:
        return None
    target_color = next(iter(target_colors))
    goals: list[Position] = []
    for item in objects:
        matches = tuple(
            target
            for target in targets
            if (
                target.width
                == item.width + 2 * parameters.target_inset
                and target.height
                == item.height + 2 * parameters.target_inset
            )
        )
        if len(matches) != 1:
            return None
        target = matches[0]
        goals.append(
            (
                target.bbox[0] + parameters.target_inset,
                target.bbox[1] + parameters.target_inset,
            )
        )
    stride = math.gcd(
        *(
            dimension
            for item in objects
            for dimension in (item.width, item.height)
        )
    )
    if stride < 1 or any(
        (goal[0] - item.position[0]) % stride
        or (goal[1] - item.position[1]) % stride
        for item, goal in zip(objects, goals, strict=True)
    ):
        return None
    height = len(grid)
    if (
        height > 1
        and len(set(grid[-1])) == 1
        and grid[-1][0] != walkable
    ):
        height -= 1
    terrain = [list(row) for row in grid]
    for item in objects:
        x0, y0 = item.position
        for y in range(y0, y0 + item.height):
            for x in range(x0, x0 + item.width):
                terrain[y][x] = walkable
    return _RouteModel(
        width=len(grid[0]),
        height=height,
        terrain=tuple(tuple(row) for row in terrain),
        objects=objects,
        goals=tuple(goals),
        selected_index=selected[0],
        stride=stride,
        walkable_color=walkable,
        target_color=target_color,
        parameters=parameters,
    )


def _overlaps(
    first_position: Position,
    first_size: tuple[int, int],
    second_position: Position,
    second_size: tuple[int, int],
) -> bool:
    first_x, first_y = first_position
    first_width, first_height = first_size
    second_x, second_y = second_position
    second_width, second_height = second_size
    return (
        first_x < second_x + second_width
        and second_x < first_x + first_width
        and first_y < second_y + second_height
        and second_y < first_y + first_height
    )


def _terrain_passable(
    model: _RouteModel,
    position: Position,
    size: tuple[int, int],
    *,
    pushed: bool,
) -> bool:
    x0, y0 = position
    width, height = size
    if (
        x0 < 0
        or y0 < 0
        or x0 + width > model.width
        or y0 + height > model.height
    ):
        return False
    passable = {
        model.walkable_color,
        model.target_color,
    }
    if pushed:
        passable.add(model.parameters.push_through_color)
    return all(
        model.terrain[y][x] in passable
        for y in range(y0, y0 + height)
        for x in range(x0, x0 + width)
    )


def _on_push_through(
    model: _RouteModel,
    position: Position,
    size: tuple[int, int],
) -> bool:
    x0, y0 = position
    width, height = size
    return any(
        model.terrain[y][x] == model.parameters.push_through_color
        for y in range(y0, y0 + height)
        for x in range(x0, x0 + width)
    )


def _move_pushed_once(
    model: _RouteModel,
    positions: list[Position],
    index: int,
    delta: Point,
    protected: frozenset[int],
) -> bool:
    if index in protected:
        return False
    working = list(positions)
    next_position = (
        working[index][0] + delta[0],
        working[index][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        next_position,
        model.sizes[index],
        pushed=True,
    ):
        return False
    collided = tuple(
        other
        for other, position in enumerate(working)
        if (
            other != index
            and _overlaps(
                next_position,
                model.sizes[index],
                position,
                model.sizes[other],
            )
        )
    )
    for other in collided:
        if not _move_pushed_once(
            model,
            working,
            other,
            delta,
            protected | {index},
        ):
            return False
    if any(
        other != index
        and _overlaps(
            next_position,
            model.sizes[index],
            position,
            model.sizes[other],
        )
        for other, position in enumerate(working)
    ):
        return False
    working[index] = next_position
    positions[:] = working
    return True


def _movement_deltas(
    model: _RouteModel,
) -> tuple[tuple[int, Point], ...]:
    step = model.stride
    return (
        (model.parameters.up_action, (0, -step)),
        (model.parameters.down_action, (0, step)),
        (model.parameters.left_action, (-step, 0)),
        (model.parameters.right_action, (step, 0)),
    )


def _transition(
    model: _RouteModel,
    state: RouteState,
    action: SearchAction,
) -> RouteState:
    positions, selected = state
    kind, value = action
    if kind == "select":
        return positions, value
    delta = dict(_movement_deltas(model)).get(value)
    if delta is None:
        return state
    next_position = (
        positions[selected][0] + delta[0],
        positions[selected][1] + delta[1],
    )
    if not _terrain_passable(
        model,
        next_position,
        model.sizes[selected],
        pushed=False,
    ):
        return state
    collided = tuple(
        index
        for index, position in enumerate(positions)
        if (
            index != selected
            and _overlaps(
                next_position,
                model.sizes[selected],
                position,
                model.sizes[index],
            )
        )
    )
    mutable = list(positions)
    if not collided:
        mutable[selected] = next_position
        return tuple(mutable), selected
    for push_step in range(model.parameters.maximum_push_steps):
        working = list(mutable)
        moved = False
        for index in collided:
            before = working[index]
            if not _move_pushed_once(
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
                    model.sizes[index],
                )
                for index in collided
            )
        ):
            break
    return tuple(mutable), selected


def _heuristic(
    model: _RouteModel,
    positions: tuple[Position, ...],
) -> int:
    return sum(
        (
            abs(position[0] - goal[0])
            + abs(position[1] - goal[1])
        )
        // model.stride
        for position, goal in zip(positions, model.goals, strict=True)
    )


def _search(
    model: _RouteModel,
) -> tuple[SearchAction, ...]:
    start: RouteState = (
        model.initial_positions,
        model.selected_index,
    )
    if start[0] == model.goals:
        return ()
    serial = itertools.count()
    frontier: list[tuple[int, int, int, RouteState]] = [
        (_heuristic(model, start[0]), 0, next(serial), start)
    ]
    best = {start: 0}
    parent: dict[RouteState, tuple[RouteState, SearchAction]] = {}
    found: RouteState | None = None
    movement_actions: tuple[SearchAction, ...] = tuple(
        ("move", action_id)
        for action_id, _delta in _movement_deltas(model)
    )
    while frontier:
        _priority, cost, _order, state = heapq.heappop(frontier)
        if cost != best[state]:
            continue
        if state[0] == model.goals:
            found = state
            break
        selection_actions: tuple[SearchAction, ...] = tuple(
            ("select", index)
            for index in range(len(model.objects))
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
                    next_cost + _heuristic(model, next_state[0]),
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


def _state_signature(
    model: _RouteModel,
    state: RouteState,
) -> str:
    return "selectable-route-state:" + digest_object(
        {
            "operator": SELECTABLE_ROUTE_TARGET_OPERATOR,
            "sizes": model.sizes,
            "goals": model.goals,
            "positions": state[0],
            "selected": state[1],
            "stride": model.stride,
            "walkable_color": model.walkable_color,
            "target_color": model.target_color,
        }
    )


def _observation_evidence(
    model: _RouteModel,
    state: RouteState,
) -> str:
    payload = {
        "object_color": model.objects[0].color,
        "positions": state[0],
        "selected": state[1],
        "sizes": model.sizes,
        "stride": model.stride,
    }
    return "selectable-route-observation:" + json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


def _visual_action(
    model: _RouteModel,
    instruction: SemanticOperatorInstruction,
    action: SearchAction,
    *,
    index: int,
    state: RouteState,
) -> VisualAction:
    kind, value = action
    payload: dict[str, object] = {
        "operator": instruction.operator_id,
        "index": index,
        "kind": kind,
        "value": value,
        "positions": state[0],
        "selected": state[1],
    }
    evidence = (
        instruction.operator_id,
        f"operator-prototype:{instruction.operator_id}",
        "rendered-multi-object-target-route",
        "observation-derived-state-search",
        _state_signature(model, state),
        _observation_evidence(model, state),
        *instruction.provenance,
    )
    if kind == "move":
        return VisualAction(
            key="semantic-selectable-route:"
            + digest_object(payload)[:20],
            action_id=value,
            group=0,
            evidence=evidence,
        )
    position = state[0][value]
    size = model.sizes[value]
    point = (
        position[0] + size[0] // 2,
        position[1] + size[1] // 2,
    )
    return VisualAction(
        key="semantic-selectable-route:"
        + digest_object({**payload, "point": point})[:20],
        action_id=instruction.action_id,
        group=0,
        x=point[0],
        y=point[1],
        evidence=(
            *evidence,
            "observation-derived-selection-point",
        ),
    )


def selectable_route_target_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Derive one complete multi-object route from the rendered state."""

    parameters = _RouteParameters.from_instruction(instruction)
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
    model = _route_model(grid, parameters)
    if model is None:
        return ()
    search_plan = _search(model)
    if not search_plan:
        return ()
    state: RouteState = (
        model.initial_positions,
        model.selected_index,
    )
    actions: list[VisualAction] = []
    for index, action in enumerate(search_plan):
        actions.append(
            _visual_action(
                model,
                instruction,
                action,
                index=index,
                state=state,
            )
        )
        state = _transition(model, state, action)
    return tuple(actions)


def selectable_route_action_matches_state(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> bool:
    """Check a queued action against the newly rendered route state."""

    return (
        selectable_route_observation_status(
            grid,
            instruction,
            action,
        )
        == "MATCH"
    )


def selectable_route_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> RouteObservationStatus:
    """Classify a queued action against one rendered observation."""

    expected = tuple(
        item
        for item in action.evidence
        if item.startswith("selectable-route-state:")
    )
    if len(expected) != 1:
        return "MISMATCH"
    parameters = _RouteParameters.from_instruction(instruction)
    if parameters is None:
        return "MISMATCH"
    observations = tuple(
        item.removeprefix("selectable-route-observation:")
        for item in action.evidence
        if item.startswith("selectable-route-observation:")
    )
    if len(observations) != 1:
        return "MISMATCH"
    try:
        raw = json.loads(observations[0])
    except json.JSONDecodeError:
        return "MISMATCH"
    if not isinstance(raw, dict):
        return "MISMATCH"

    def pair(value: object) -> tuple[int, int] | None:
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

    raw_sizes = raw.get("sizes")
    raw_positions = raw.get("positions")
    raw_selected = raw.get("selected")
    raw_stride = raw.get("stride")
    raw_object_color = raw.get("object_color")
    if (
        not isinstance(raw_sizes, list)
        or not isinstance(raw_positions, list)
        or isinstance(raw_selected, bool)
        or not isinstance(raw_selected, int)
        or isinstance(raw_stride, bool)
        or not isinstance(raw_stride, int)
        or isinstance(raw_object_color, bool)
        or not isinstance(raw_object_color, int)
    ):
        return "MISMATCH"
    sizes = tuple(pair(value) for value in raw_sizes)
    positions = tuple(pair(value) for value in raw_positions)
    if (
        any(value is None for value in sizes)
        or any(value is None for value in positions)
        or len(sizes) != len(positions)
        or not parameters.minimum_object_count
        <= len(sizes)
        <= parameters.maximum_object_count
        or not 0 <= raw_selected < len(sizes)
    ):
        return "MISMATCH"
    expected_sizes = tuple(
        value for value in sizes if value is not None
    )
    expected_positions = tuple(
        value for value in positions if value is not None
    )
    objects = _route_objects_from_sizes(
        grid,
        expected_sizes,
        parameters,
        stride=raw_stride,
    )
    if len(objects) != len(expected_sizes):
        return "UNAVAILABLE"
    selected = tuple(
        index
        for index, item in enumerate(objects)
        if item.marker_color == parameters.selected_marker_color
    )
    if len(selected) != 1:
        return "UNAVAILABLE"
    actual = {
        "object_color": objects[0].color,
        "positions": tuple(item.position for item in objects),
        "selected": selected[0],
        "sizes": tuple((item.width, item.height) for item in objects),
        "stride": raw_stride,
    }
    expected_observation = {
        "object_color": raw_object_color,
        "positions": expected_positions,
        "selected": raw_selected,
        "sizes": expected_sizes,
        "stride": raw_stride,
    }
    return "MATCH" if actual == expected_observation else "MISMATCH"


def selectable_route_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the P-bounded transient-frame observation limit."""

    parameters = _RouteParameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


__all__ = [
    "SELECTABLE_ROUTE_TARGET_OPERATOR",
    "selectable_route_action_matches_state",
    "selectable_route_observation_status",
    "selectable_route_target_plan",
    "selectable_route_transition_observation_limit",
]
