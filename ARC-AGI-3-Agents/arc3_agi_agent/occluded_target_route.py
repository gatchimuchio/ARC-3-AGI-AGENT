"""Rendered routing to a uniquely occluded target without environment identity."""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass
from typing import Literal

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object
from .visual_explorer import Grid, VisualAction

OCCLUDED_TARGET_ROUTE_OPERATOR = (
    "occluded-selectable-object-target-route-v5"
)

Position = tuple[int, int]
RouteObservationStatus = Literal["MATCH", "UNAVAILABLE", "MISMATCH"]


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
    minimum_object_side: int
    maximum_object_side: int
    maximum_missing_border_cells: int
    maximum_search_states: int
    maximum_plan_actions: int
    maximum_transition_observations: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _Parameters | None:
        if instruction.operator_id != OCCLUDED_TARGET_ROUTE_OPERATOR:
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
            "minimum_object_side",
            "maximum_object_side",
            "maximum_missing_border_cells",
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
            or parsed["minimum_object_side"] < 3
            or parsed["maximum_object_side"]
            < parsed["minimum_object_side"]
            or parsed["maximum_missing_border_cells"] < 1
            or parsed["maximum_search_states"] < 1
            or parsed["maximum_plan_actions"] < 1
            or parsed["maximum_transition_observations"] < 1
        ):
            return None
        return cls(**parsed)

    @property
    def marker_colors(self) -> frozenset[int]:
        return frozenset(
            {
                self.selected_marker_color,
                self.unselected_marker_color,
                self.released_marker_color,
            }
        )

    @property
    def action_deltas(self) -> tuple[tuple[int, Position], ...]:
        return (
            (self.up_action, (0, -1)),
            (self.down_action, (0, 1)),
            (self.left_action, (-1, 0)),
            (self.right_action, (1, 0)),
        )


@dataclass(frozen=True, slots=True)
class _Target:
    color: int
    bbox: tuple[int, int, int, int]
    missing_side: str
    missing_border: tuple[Position, ...]
    walkable_color: int
    object_width: int
    object_height: int
    goal: Position


@dataclass(frozen=True, slots=True)
class _RouteObject:
    color: int
    width: int
    height: int
    position: Position
    marker_color: int


@dataclass(frozen=True, slots=True)
class _Model:
    width: int
    height: int
    terrain: Grid
    object: _RouteObject
    target: _Target
    stride: int
    parameters: _Parameters

    @property
    def initial_position(self) -> Position:
        return self.object.position

    @property
    def goal(self) -> Position:
        return self.target.goal


def _maximal_runs(
    values: tuple[int, ...],
) -> tuple[tuple[int, int, int], ...]:
    if not values:
        return ()
    runs: list[tuple[int, int, int]] = []
    start = 0
    color = values[0]
    for index, value in enumerate(values[1:], start=1):
        if value == color:
            continue
        runs.append((color, start, index - 1))
        color = value
        start = index
    runs.append((color, start, len(values) - 1))
    return tuple(runs)


def _contiguous(points: tuple[Position, ...], *, axis: int) -> bool:
    coordinates = sorted(point[axis] for point in points)
    return coordinates == list(
        range(coordinates[0], coordinates[-1] + 1)
    )


def _occluder_extends_outside(
    grid: Grid,
    *,
    color: int,
    walkable_color: int,
    missing_side: str,
    missing: tuple[Position, ...],
) -> bool:
    delta = {
        "left": (-1, 0),
        "right": (1, 0),
        "top": (0, -1),
        "bottom": (0, 1),
    }.get(missing_side)
    if delta is None:
        return False
    height = len(grid)
    width = len(grid[0])
    missing_values: set[int] = set()
    outside_values: set[int] = set()
    for x, y in missing:
        value = grid[y][x]
        outside_x = x + delta[0]
        outside_y = y + delta[1]
        if (
            value in {color, walkable_color}
            or not 0 <= outside_x < width
            or not 0 <= outside_y < height
            or grid[outside_y][outside_x]
            in {color, walkable_color}
        ):
            return False
        missing_values.add(value)
        outside_values.add(grid[outside_y][outside_x])
    if len(missing_values) != 1 or len(outside_values) != 1:
        return False
    return True


def _target_from_bbox(
    grid: Grid,
    parameters: _Parameters,
    *,
    color: int,
    bbox: tuple[int, int, int, int],
    complete_axis: str,
) -> _Target | None:
    x0, y0, x1, y1 = bbox
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    object_width = width - 2 * parameters.target_inset
    object_height = height - 2 * parameters.target_inset
    if (
        not parameters.minimum_object_side
        <= object_width
        <= parameters.maximum_object_side
        or not parameters.minimum_object_side
        <= object_height
        <= parameters.maximum_object_side
    ):
        return None
    interior = tuple(
        grid[y][x]
        for y in range(
            y0 + parameters.target_inset,
            y1 - parameters.target_inset + 1,
        )
        for x in range(
            x0 + parameters.target_inset,
            x1 - parameters.target_inset + 1,
        )
    )
    if not interior or len(set(interior)) != 1:
        return None
    walkable_color = interior[0]
    if walkable_color == color:
        return None

    top = tuple((x, y0) for x in range(x0, x1 + 1))
    bottom = tuple((x, y1) for x in range(x0, x1 + 1))
    left = tuple((x0, y) for y in range(y0, y1 + 1))
    right = tuple((x1, y) for y in range(y0, y1 + 1))
    borders = {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
    }
    if complete_axis == "horizontal":
        complete_sides = ("top", "bottom")
        candidate_sides = ("left", "right")
        contiguous_axis = 1
    elif complete_axis == "vertical":
        complete_sides = ("left", "right")
        candidate_sides = ("top", "bottom")
        contiguous_axis = 0
    else:
        return None
    if any(
        any(grid[y][x] != color for x, y in borders[side])
        for side in complete_sides
    ):
        return None
    missing_by_side = {
        side: tuple(
            (x, y)
            for x, y in borders[side][1:-1]
            if grid[y][x] != color
        )
        for side in candidate_sides
    }
    incomplete = tuple(
        side for side in candidate_sides if missing_by_side[side]
    )
    if len(incomplete) != 1:
        return None
    missing_side = incomplete[0]
    intact_side = next(
        side for side in candidate_sides if side != missing_side
    )
    if any(
        grid[y][x] != color
        for x, y in borders[intact_side]
    ):
        return None
    missing = missing_by_side[missing_side]
    if (
        len(missing) > parameters.maximum_missing_border_cells
        or not _contiguous(missing, axis=contiguous_axis)
        or not _occluder_extends_outside(
            grid,
            color=color,
            walkable_color=walkable_color,
            missing_side=missing_side,
            missing=missing,
        )
    ):
        return None
    return _Target(
        color=color,
        bbox=bbox,
        missing_side=missing_side,
        missing_border=missing,
        walkable_color=walkable_color,
        object_width=object_width,
        object_height=object_height,
        goal=(
            x0 + parameters.target_inset,
            y0 + parameters.target_inset,
        ),
    )


def _targets(
    grid: Grid,
    parameters: _Parameters,
) -> tuple[_Target, ...]:
    if not grid or not grid[0]:
        return ()
    height = len(grid)
    width = len(grid[0])
    maximum_target_side = (
        parameters.maximum_object_side
        + 2 * parameters.target_inset
    )
    minimum_target_side = (
        parameters.minimum_object_side
        + 2 * parameters.target_inset
    )
    candidates: dict[
        tuple[int, tuple[int, int, int, int], str],
        _Target,
    ] = {}

    horizontal: dict[tuple[int, int, int], list[int]] = {}
    for y, row in enumerate(grid):
        for color, x0, x1 in _maximal_runs(row):
            side = x1 - x0 + 1
            if minimum_target_side <= side <= maximum_target_side:
                horizontal.setdefault((color, x0, x1), []).append(y)
    for (color, x0, x1), rows in horizontal.items():
        for first_index, y0 in enumerate(rows):
            for y1 in rows[first_index + 1 :]:
                if not minimum_target_side <= y1 - y0 + 1 <= (
                    maximum_target_side
                ):
                    continue
                target = _target_from_bbox(
                    grid,
                    parameters,
                    color=color,
                    bbox=(x0, y0, x1, y1),
                    complete_axis="horizontal",
                )
                if target is not None:
                    candidates[
                        (target.color, target.bbox, target.missing_side)
                    ] = target

    vertical: dict[tuple[int, int, int], list[int]] = {}
    for x in range(width):
        column = tuple(grid[y][x] for y in range(height))
        for color, y0, y1 in _maximal_runs(column):
            side = y1 - y0 + 1
            if minimum_target_side <= side <= maximum_target_side:
                vertical.setdefault((color, y0, y1), []).append(x)
    for (color, y0, y1), columns in vertical.items():
        for first_index, x0 in enumerate(columns):
            for x1 in columns[first_index + 1 :]:
                if not minimum_target_side <= x1 - x0 + 1 <= (
                    maximum_target_side
                ):
                    continue
                target = _target_from_bbox(
                    grid,
                    parameters,
                    color=color,
                    bbox=(x0, y0, x1, y1),
                    complete_axis="vertical",
                )
                if target is not None:
                    candidates[
                        (target.color, target.bbox, target.missing_side)
                    ] = target
    return tuple(
        sorted(
            candidates.values(),
            key=lambda target: (
                target.color,
                target.bbox,
                target.missing_side,
            ),
        )
    )


def _object_at(
    grid: Grid,
    parameters: _Parameters,
    *,
    x0: int,
    y0: int,
    width: int,
    height: int,
) -> _RouteObject | None:
    divisor = parameters.marker_divisor
    if width % divisor or height % divisor:
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
    if (
        len(marker_values) != 1
        or not marker_values <= parameters.marker_colors
    ):
        return None
    marker_color = next(iter(marker_values))
    object_values = {
        grid[y][x]
        for y in range(y0, y0 + height)
        for x in range(x0, x0 + width)
        if not (
            marker_x0 <= x < marker_x0 + marker_width
            and marker_y0 <= y < marker_y0 + marker_height
        )
        and grid[y][x] not in parameters.marker_colors
    }
    if len(object_values) != 1:
        return None
    object_color = next(iter(object_values))
    if object_color in parameters.marker_colors:
        return None
    for y in range(y0, y0 + height):
        for x in range(x0, x0 + width):
            if (
                marker_x0 <= x < marker_x0 + marker_width
                and marker_y0 <= y < marker_y0 + marker_height
            ):
                continue
            value = grid[y][x]
            if value == object_color:
                continue
            if (
                marker_color == parameters.selected_marker_color
                and value == parameters.selected_marker_color
                and (
                    x in {x0, x0 + width - 1}
                    or y in {y0, y0 + height - 1}
                )
            ):
                continue
            return None
    return _RouteObject(
        color=object_color,
        width=width,
        height=height,
        position=(x0, y0),
        marker_color=marker_color,
    )


def _objects_for_target(
    grid: Grid,
    target: _Target,
    parameters: _Parameters,
) -> tuple[_RouteObject, ...]:
    width = target.object_width
    height = target.object_height
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
            )
        )
        is not None
    )
    if len(matches) != 1:
        return ()
    return matches


def _playable_height(
    grid: Grid,
    *,
    walkable_color: int,
) -> int:
    height = len(grid)
    for y in range(max(1, height - 4), height - 1):
        if len(set(grid[y])) == 1 and grid[y][0] != walkable_color:
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
) -> _Model | None:
    candidates: list[tuple[_Target, _RouteObject]] = []
    for target in _targets(grid, parameters):
        objects = _objects_for_target(grid, target, parameters)
        if (
            len(objects) == 1
            and objects[0].marker_color
            == parameters.selected_marker_color
        ):
            candidates.append((target, objects[0]))
    if len(candidates) != 1:
        return None
    target, route_object = candidates[0]
    stride = math.gcd(route_object.width, route_object.height)
    if (
        stride < 1
        or (target.goal[0] - route_object.position[0]) % stride
        or (target.goal[1] - route_object.position[1]) % stride
    ):
        return None
    height = _playable_height(
        grid,
        walkable_color=target.walkable_color,
    )
    terrain = [list(row) for row in grid[:height]]
    x0, y0 = route_object.position
    if y0 + route_object.height > height:
        return None
    for y in range(y0, y0 + route_object.height):
        for x in range(x0, x0 + route_object.width):
            terrain[y][x] = target.walkable_color
    return _Model(
        width=len(grid[0]),
        height=height,
        terrain=tuple(tuple(row) for row in terrain),
        object=route_object,
        target=target,
        stride=stride,
        parameters=parameters,
    )


def _passable(model: _Model, position: Position) -> bool:
    x0, y0 = position
    if (
        x0 < 0
        or y0 < 0
        or x0 + model.object.width > model.width
        or y0 + model.object.height > model.height
    ):
        return False
    passable_colors = {
        model.target.walkable_color,
        model.target.color,
    }
    if not all(
        model.terrain[y][x] in passable_colors
        for y in range(y0, y0 + model.object.height)
        for x in range(x0, x0 + model.object.width)
    ):
        return False
    if position == model.goal:
        return True
    goal_x, goal_y = model.goal
    horizontal_overlap = (
        x0 < goal_x + model.object.width
        and goal_x < x0 + model.object.width
    )
    vertical_overlap = (
        y0 < goal_y + model.object.height
        and goal_y < y0 + model.object.height
    )
    if (
        model.target.missing_side in {"left", "right"}
        and vertical_overlap
    ):
        return False
    if (
        model.target.missing_side in {"top", "bottom"}
        and horizontal_overlap
    ):
        return False
    return True


def _transition(
    model: _Model,
    position: Position,
    action_id: int,
) -> Position:
    delta = next(
        (
            delta
            for candidate, delta in model.parameters.action_deltas
            if candidate == action_id
        ),
        None,
    )
    if delta is None:
        return position
    candidate = (
        position[0] + delta[0] * model.stride,
        position[1] + delta[1] * model.stride,
    )
    return candidate if _passable(model, candidate) else position


def _heuristic(model: _Model, position: Position) -> int:
    return (
        abs(position[0] - model.goal[0])
        + abs(position[1] - model.goal[1])
    ) // model.stride


def _search(model: _Model) -> tuple[int, ...]:
    initial = model.initial_position
    if initial == model.goal:
        return ()
    frontier: list[tuple[int, int, int, Position]] = [
        (_heuristic(model, initial), 0, 0, initial)
    ]
    best = {initial: 0}
    predecessor: dict[Position, tuple[Position, int]] = {}
    order = 0
    visited = 0
    while frontier:
        _estimate, cost, _order, position = heapq.heappop(frontier)
        if cost != best.get(position):
            continue
        visited += 1
        if visited > model.parameters.maximum_search_states:
            return ()
        if position == model.goal:
            actions: list[int] = []
            current = position
            while current != initial:
                previous, action_id = predecessor[current]
                actions.append(action_id)
                current = previous
            plan = tuple(reversed(actions))
            return (
                plan
                if len(plan) <= model.parameters.maximum_plan_actions
                else ()
            )
        for action_id, _delta in model.parameters.action_deltas:
            candidate = _transition(model, position, action_id)
            if candidate == position:
                continue
            candidate_cost = cost + 1
            if candidate_cost >= best.get(candidate, 2**31):
                continue
            best[candidate] = candidate_cost
            predecessor[candidate] = (position, action_id)
            order += 1
            heapq.heappush(
                frontier,
                (
                    candidate_cost + _heuristic(model, candidate),
                    candidate_cost,
                    order,
                    candidate,
                ),
            )
    return ()


def _state_signature(model: _Model, position: Position) -> str:
    return "occluded-route-state:" + digest_object(
        {
            "operator": OCCLUDED_TARGET_ROUTE_OPERATOR,
            "object_color": model.object.color,
            "object_size": (
                model.object.width,
                model.object.height,
            ),
            "position": position,
            "goal": model.goal,
            "stride": model.stride,
            "target_color": model.target.color,
            "target_bbox": model.target.bbox,
            "missing_side": model.target.missing_side,
            "walkable_color": model.target.walkable_color,
        }
    )


def _observation_evidence(model: _Model, position: Position) -> str:
    payload = {
        "object_color": model.object.color,
        "object_size": (model.object.width, model.object.height),
        "position": position,
        "goal": model.goal,
        "stride": model.stride,
        "target_color": model.target.color,
        "target_bbox": model.target.bbox,
        "missing_side": model.target.missing_side,
        "walkable_color": model.target.walkable_color,
    }
    return "occluded-route-observation:" + json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


def _visual_action(
    model: _Model,
    instruction: SemanticOperatorInstruction,
    action_id: int,
    *,
    index: int,
    position: Position,
) -> VisualAction:
    payload = {
        "operator": instruction.operator_id,
        "index": index,
        "action": action_id,
        "position": position,
        "goal": model.goal,
    }
    return VisualAction(
        key="semantic-occluded-route:"
        + digest_object(payload)[:20],
        action_id=action_id,
        group=0,
        evidence=(
            instruction.operator_id,
            f"operator-prototype:{instruction.operator_id}",
            "rendered-partially-occluded-target-relation",
            "observation-derived-border-completion",
            "observation-derived-bounded-route-search",
            _state_signature(model, position),
            _observation_evidence(model, position),
            *instruction.provenance,
        ),
    )


def occluded_target_route_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Plan after a rendered occluder exposes a bounded route to its target."""

    parameters = _Parameters.from_instruction(instruction)
    if parameters is None:
        return ()
    required_actions = {
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
    plan = _search(model)
    if not plan:
        return ()
    actions: list[VisualAction] = []
    position = model.initial_position
    for index, action_id in enumerate(plan):
        actions.append(
            _visual_action(
                model,
                instruction,
                action_id,
                index=index,
                position=position,
            )
        )
        position = _transition(model, position, action_id)
    if position != model.goal:
        return ()
    return tuple(actions)


def _pair(value: object) -> tuple[int, int] | None:
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


def _bbox(value: object) -> tuple[int, int, int, int] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in value
        )
    ):
        return None
    return value[0], value[1], value[2], value[3]


def occluded_target_route_observation_status(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> RouteObservationStatus:
    """Compare one queued route action with a fresh rendered observation."""

    expected_states = tuple(
        item
        for item in action.evidence
        if item.startswith("occluded-route-state:")
    )
    observations = tuple(
        item.removeprefix("occluded-route-observation:")
        for item in action.evidence
        if item.startswith("occluded-route-observation:")
    )
    if len(expected_states) != 1 or len(observations) != 1:
        return "MISMATCH"
    parameters = _Parameters.from_instruction(instruction)
    if parameters is None:
        return "MISMATCH"
    try:
        raw = json.loads(observations[0])
    except json.JSONDecodeError:
        return "MISMATCH"
    if not isinstance(raw, dict):
        return "MISMATCH"
    object_size = _pair(raw.get("object_size"))
    position = _pair(raw.get("position"))
    goal = _pair(raw.get("goal"))
    target_bbox = _bbox(raw.get("target_bbox"))
    integer_names = (
        "object_color",
        "stride",
        "target_color",
        "walkable_color",
    )
    integers = {name: raw.get(name) for name in integer_names}
    missing_side = raw.get("missing_side")
    if (
        object_size is None
        or position is None
        or goal is None
        or target_bbox is None
        or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in integers.values()
        )
        or missing_side not in {"left", "right", "top", "bottom"}
    ):
        return "MISMATCH"
    model = _model(grid, parameters)
    if model is None:
        return "UNAVAILABLE"
    actual = {
        "object_color": model.object.color,
        "object_size": (model.object.width, model.object.height),
        "position": model.object.position,
        "goal": model.goal,
        "stride": model.stride,
        "target_color": model.target.color,
        "target_bbox": model.target.bbox,
        "missing_side": model.target.missing_side,
        "walkable_color": model.target.walkable_color,
    }
    expected = {
        "object_color": integers["object_color"],
        "object_size": object_size,
        "position": position,
        "goal": goal,
        "stride": integers["stride"],
        "target_color": integers["target_color"],
        "target_bbox": target_bbox,
        "missing_side": missing_side,
        "walkable_color": integers["walkable_color"],
    }
    return "MATCH" if actual == expected else "MISMATCH"


def occluded_target_route_action_matches_state(
    grid: Grid,
    instruction: SemanticOperatorInstruction,
    action: VisualAction,
) -> bool:
    """Return whether one queued action is valid for the rendered state."""

    return (
        occluded_target_route_observation_status(
            grid,
            instruction,
            action,
        )
        == "MATCH"
    )


def occluded_target_route_transition_observation_limit(
    instruction: SemanticOperatorInstruction,
) -> int:
    """Return the instruction-bounded transient observation allowance."""

    parameters = _Parameters.from_instruction(instruction)
    return (
        0
        if parameters is None
        else parameters.maximum_transition_observations
    )


__all__ = [
    "OCCLUDED_TARGET_ROUTE_OPERATOR",
    "occluded_target_route_action_matches_state",
    "occluded_target_route_observation_status",
    "occluded_target_route_plan",
    "occluded_target_route_transition_observation_limit",
]
