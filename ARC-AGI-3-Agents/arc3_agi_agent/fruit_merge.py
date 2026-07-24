"""Rendered goal-aware fruit merge and actor-placement operator.

The operator consumes only a rendered grid, available actions, a compiled
identity-free instruction, and passive serializable state.  It reads required
entity glyphs from the rendered interface, recognizes same-rank square
entities and target zones, and emits one re-observation-gated click at a time.
No game, task, level, source, or hidden-state identity is accepted.
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object, forbidden_runtime_paths
from .visual_explorer import Grid, Point, VisualAction

FRUIT_MERGE_OPERATOR = "rendered-goal-aware-fruit-merge-v2"
FRUIT_MERGE_CANDIDATE_OPERATOR = "rendered-goal-aware-fruit-merge-v3"
FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v4"
)
FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v5"
)
FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v6"
)
FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v7"
)
FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v8"
)
FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v9"
)
FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v10"
)
FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v11"
)
FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v12"
)
FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v13"
)
FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR = (
    "rendered-goal-aware-fruit-merge-v14"
)
FRUIT_MERGE_STATE_FORMAT = "arc3-fruit-merge-state-v2"

_OFFSETS4: tuple[Point, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _payload_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class _RankSpec:
    rank: int
    color: int
    side: int


@dataclass(frozen=True, slots=True)
class _ActorSpec:
    kind: str
    color: int
    width: int
    height: int
    mask: frozenset[Point]


@dataclass(frozen=True, slots=True)
class _FruitParameters:
    click_action: int
    undo_action: int
    click_x_origin: int
    click_y_origin: int
    click_step: int
    click_radius: int
    fruit_move_step: int
    actor_move_distance: int
    actor_chase_risk_distance: int
    actor_divert_interval: int
    actor_fruit_rank_delta: int
    maximum_transition_observations: int
    interface_max_y: int
    playfield_min_y: int
    playfield_max_y: int
    target_color: int
    target_min_side: int
    target_max_side: int
    target_min_area: int
    target_max_area: int
    rank_specs: tuple[_RankSpec, ...]
    actor_specs: tuple[_ActorSpec, ...]
    actor_merge_chain: tuple[str, ...]

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _FruitParameters | None:
        if instruction.operator_id not in {
            FRUIT_MERGE_OPERATOR,
            FRUIT_MERGE_CANDIDATE_OPERATOR,
            FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
            FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
            FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
            FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
            FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
            FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
        }:
            return None
        raw = instruction.parameters()

        def integer(name: str) -> int | None:
            value = raw.get(name)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else None
            )

        integer_names = (
            "click_action",
            "undo_action",
            "click_x_origin",
            "click_y_origin",
            "click_step",
            "click_radius",
            "fruit_move_step",
            "actor_move_distance",
            "actor_chase_risk_distance",
            "actor_divert_interval",
            "actor_fruit_rank_delta",
            "interface_max_y",
            "playfield_min_y",
            "playfield_max_y",
            "target_color",
            "target_min_side",
            "target_max_side",
            "target_min_area",
            "target_max_area",
        )
        values = {name: integer(name) for name in integer_names}
        if any(value is None for value in values.values()):
            return None
        maximum_transition_observations = integer(
            "maximum_transition_observations"
        )
        if (
            instruction.operator_id
            in {
                FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
            }
            and maximum_transition_observations is None
        ):
            return None
        if maximum_transition_observations is None:
            maximum_transition_observations = 0

        def required(name: str) -> int:
            value = values[name]
            if value is None:
                raise AssertionError("validated fruit parameter missing")
            return value

        raw_rank_specs = raw.get("rank_specs")
        raw_actor_specs = raw.get("actor_specs")
        raw_actor_merge_chain = raw.get("actor_merge_chain")
        if (
            not isinstance(raw_rank_specs, Sequence)
            or isinstance(raw_rank_specs, (str, bytes, bytearray))
            or not isinstance(raw_actor_specs, Sequence)
            or isinstance(raw_actor_specs, (str, bytes, bytearray))
            or not isinstance(raw_actor_merge_chain, Sequence)
            or isinstance(
                raw_actor_merge_chain,
                (str, bytes, bytearray),
            )
        ):
            return None
        rank_specs: list[_RankSpec] = []
        for item in raw_rank_specs:
            if not isinstance(item, Mapping):
                return None
            try:
                spec = _RankSpec(
                    rank=_payload_int(item.get("rank"), "rank"),
                    color=_payload_int(item.get("color"), "rank color"),
                    side=_payload_int(item.get("side"), "rank side"),
                )
            except ValueError:
                return None
            if (
                not 0 <= spec.rank <= 15
                or not 0 <= spec.color <= 15
                or not 1 <= spec.side <= 16
            ):
                return None
            rank_specs.append(spec)
        if (
            not rank_specs
            or len({spec.rank for spec in rank_specs}) != len(rank_specs)
            or len({(spec.color, spec.side) for spec in rank_specs})
            != len(rank_specs)
        ):
            return None

        actor_specs: list[_ActorSpec] = []
        for item in raw_actor_specs:
            if not isinstance(item, Mapping):
                return None
            raw_mask = item.get("mask")
            if (
                not isinstance(raw_mask, Sequence)
                or isinstance(raw_mask, (str, bytes, bytearray))
            ):
                return None
            try:
                width = _payload_int(item.get("width"), "actor width")
                height = _payload_int(item.get("height"), "actor height")
                color = _payload_int(item.get("color"), "actor color")
                mask = frozenset(
                    (
                        _payload_int(point[0], "actor mask x"),
                        _payload_int(point[1], "actor mask y"),
                    )
                    for point in raw_mask
                    if isinstance(point, Sequence)
                    and not isinstance(point, (str, bytes, bytearray))
                    and len(point) == 2
                )
            except (IndexError, ValueError):
                return None
            kind = str(item.get("kind", "")).strip()
            if (
                not kind
                or not 1 <= width <= 16
                or not 1 <= height <= 16
                or not 0 <= color <= 15
                or not mask
                or any(
                    not 0 <= x < width or not 0 <= y < height
                    for x, y in mask
                )
                or len(mask) != len(raw_mask)
            ):
                return None
            actor_specs.append(
                _ActorSpec(
                    kind=kind,
                    color=color,
                    width=width,
                    height=height,
                    mask=mask,
                )
            )
        if len({spec.kind for spec in actor_specs}) != len(actor_specs):
            return None
        actor_merge_chain = tuple(
            str(kind).strip() for kind in raw_actor_merge_chain
        )
        actor_kinds = {spec.kind for spec in actor_specs}
        if (
            not actor_merge_chain
            or len(set(actor_merge_chain)) != len(actor_merge_chain)
            or any(
                not kind or kind not in actor_kinds
                for kind in actor_merge_chain
            )
        ):
            return None

        parameters = cls(
            click_action=required("click_action"),
            undo_action=required("undo_action"),
            click_x_origin=required("click_x_origin"),
            click_y_origin=required("click_y_origin"),
            click_step=required("click_step"),
            click_radius=required("click_radius"),
            fruit_move_step=required("fruit_move_step"),
            actor_move_distance=required("actor_move_distance"),
            actor_chase_risk_distance=required(
                "actor_chase_risk_distance"
            ),
            actor_divert_interval=required("actor_divert_interval"),
            actor_fruit_rank_delta=required("actor_fruit_rank_delta"),
            maximum_transition_observations=(
                maximum_transition_observations
            ),
            interface_max_y=required("interface_max_y"),
            playfield_min_y=required("playfield_min_y"),
            playfield_max_y=required("playfield_max_y"),
            target_color=required("target_color"),
            target_min_side=required("target_min_side"),
            target_max_side=required("target_max_side"),
            target_min_area=required("target_min_area"),
            target_max_area=required("target_max_area"),
            rank_specs=tuple(sorted(rank_specs, key=lambda item: item.rank)),
            actor_specs=tuple(sorted(actor_specs, key=lambda item: item.kind)),
            actor_merge_chain=actor_merge_chain,
        )
        if (
            parameters.click_action == parameters.undo_action
            or not 1 <= parameters.click_action <= 7
            or not 1 <= parameters.undo_action <= 7
            or not 0 <= parameters.click_x_origin <= 63
            or not 0 <= parameters.click_y_origin <= 63
            or not 1 <= parameters.click_step <= 16
            or not 1 <= parameters.click_radius <= 32
            or not 1 <= parameters.fruit_move_step <= 16
            or not 1 <= parameters.actor_move_distance <= 32
            or not 1 <= parameters.actor_chase_risk_distance <= 64
            or not 1 <= parameters.actor_divert_interval <= 32
            or not -8 <= parameters.actor_fruit_rank_delta <= -1
            or (
                instruction.operator_id
                in {
                    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                }
                and not 1
                <= parameters.maximum_transition_observations
                <= 32
            )
            or (
                instruction.operator_id
                not in {
                    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                }
                and parameters.maximum_transition_observations != 0
            )
            or not 0 <= parameters.interface_max_y
            < parameters.playfield_min_y
            <= parameters.playfield_max_y
            <= 63
            or not 0 <= parameters.target_color <= 15
            or not 2
            <= parameters.target_min_side
            <= parameters.target_max_side
            <= 32
            or not 1
            <= parameters.target_min_area
            <= parameters.target_max_area
            <= 1024
        ):
            return None
        return parameters


@dataclass(frozen=True, slots=True)
class _Component:
    color: int
    area: int
    bbox: tuple[int, int, int, int]
    rectangular: bool

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0] + 1

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1] + 1

    @property
    def center(self) -> Point:
        return (
            (self.bbox[0] + self.bbox[2]) // 2,
            (self.bbox[1] + self.bbox[3]) // 2,
        )


@dataclass(frozen=True, slots=True)
class _Fruit:
    rank: int
    center: Point
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _Actor:
    kind: str
    center: Point
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _Target:
    center: Point
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _FruitSurface:
    signature: str
    fruits: tuple[_Fruit, ...]
    actors: tuple[_Actor, ...]
    targets: tuple[_Target, ...]
    required_ranks: tuple[tuple[int, int], ...]
    required_actors: tuple[tuple[str, int], ...]
    parameters: _FruitParameters
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FruitMergeDecision:
    action: VisualAction | None
    reason: str
    memory_influenced: bool


def _components(grid: Grid) -> tuple[_Component, ...]:
    if not grid:
        return ()
    height = len(grid)
    width = len(grid[0])
    visited: set[Point] = set()
    result: list[_Component] = []
    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue
            color = grid[y][x]
            queue: deque[Point] = deque(((x, y),))
            visited.add((x, y))
            points: list[Point] = []
            while queue:
                px, py = queue.popleft()
                points.append((px, py))
                for dx, dy in _OFFSETS4:
                    nx = px + dx
                    ny = py + dy
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and (nx, ny) not in visited
                        and grid[ny][nx] == color
                    ):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            xs = tuple(point[0] for point in points)
            ys = tuple(point[1] for point in points)
            bbox = (min(xs), min(ys), max(xs), max(ys))
            area = len(points)
            result.append(
                _Component(
                    color=color,
                    area=area,
                    bbox=bbox,
                    rectangular=area
                    == (
                        (bbox[2] - bbox[0] + 1)
                        * (bbox[3] - bbox[1] + 1)
                    ),
                )
            )
    return tuple(result)


def _actor_at(
    grid: Grid,
    x: int,
    y: int,
    spec: _ActorSpec,
) -> bool:
    for dy in range(spec.height):
        for dx in range(spec.width):
            if ((dx, dy) in spec.mask) != (
                grid[y + dy][x + dx] == spec.color
            ):
                return False
    return True


def _actors(
    grid: Grid,
    parameters: _FruitParameters,
    *,
    interface: bool,
) -> tuple[_Actor, ...]:
    if not grid:
        return ()
    height = len(grid)
    width = len(grid[0])
    found: list[_Actor] = []
    occupied: set[Point] = set()
    for spec in parameters.actor_specs:
        min_y = 0 if interface else parameters.playfield_min_y
        max_y = (
            parameters.interface_max_y
            if interface
            else min(parameters.playfield_max_y, height - 1)
        )
        for y in range(min_y, max_y - spec.height + 2):
            for x in range(0, width - spec.width + 1):
                points = {
                    (x + dx, y + dy) for dx, dy in spec.mask
                }
                if points & occupied or not _actor_at(grid, x, y, spec):
                    continue
                occupied.update(points)
                found.append(
                    _Actor(
                        kind=spec.kind,
                        center=(
                            x + spec.width // 2,
                            y + spec.height // 2,
                        ),
                        bbox=(
                            x,
                            y,
                            x + spec.width - 1,
                            y + spec.height - 1,
                        ),
                    )
                )
    return tuple(
        sorted(found, key=lambda item: (item.kind, item.center))
    )


def _strictly_encloses(
    outer: tuple[int, int, int, int],
    inner: tuple[int, int, int, int],
) -> bool:
    return (
        outer[0] < inner[0]
        and outer[1] < inner[1]
        and outer[2] > inner[2]
        and outer[3] > inner[3]
    )


def _surface_from_grid(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> _FruitSurface | None:
    parameters = _FruitParameters.from_instruction(instruction)
    if (
        parameters is None
        or parameters.click_action not in available_actions
        or parameters.undo_action not in available_actions
        or not grid
    ):
        return None
    height = len(grid)
    width = len(grid[0])
    rank_lookup = {
        (spec.color, spec.side): spec.rank
        for spec in parameters.rank_specs
    }
    fruits: list[_Fruit] = []
    required_ranks: Counter[int] = Counter()
    targets: list[_Target] = []
    components = _components(grid)
    interface_containers = tuple(
        component
        for component in components
        if (
            not component.rectangular
            and component.bbox[3] <= parameters.interface_max_y
            and component.width <= max(4, width // 2)
        )
    )
    for component in components:
        rank = rank_lookup.get((component.color, component.width))
        if (
            rank is not None
            and component.width == component.height
            and component.rectangular
        ):
            if component.bbox[3] <= parameters.interface_max_y:
                if any(
                    container.color != component.color
                    and container.area > component.area
                    and _strictly_encloses(
                        container.bbox,
                        component.bbox,
                    )
                    for container in interface_containers
                ):
                    continue
                required_ranks[rank] += 1
            elif (
                component.bbox[1] >= parameters.playfield_min_y
                and component.bbox[3] <= parameters.playfield_max_y
            ):
                fruits.append(
                    _Fruit(
                        rank=rank,
                        center=component.center,
                        bbox=component.bbox,
                    )
                )
            continue
        if (
            component.color == parameters.target_color
            and not component.rectangular
            and parameters.target_min_side
            <= component.width
            <= parameters.target_max_side
            and parameters.target_min_side
            <= component.height
            <= parameters.target_max_side
            and parameters.target_min_area
            <= component.area
            <= parameters.target_max_area
            and component.bbox[1] >= parameters.playfield_min_y
            and component.bbox[3] <= parameters.playfield_max_y
        ):
            targets.append(
                _Target(
                    center=component.center,
                    bbox=component.bbox,
                )
            )
    actors = _actors(grid, parameters, interface=False)
    required_actors = Counter(
        actor.kind for actor in _actors(grid, parameters, interface=True)
    )
    if (
        not targets
        or not (required_ranks or required_actors)
        or not (fruits or actors)
        or sum(required_ranks.values())
        + sum(required_actors.values())
        > len(targets)
    ):
        return None
    ordered_targets = tuple(
        sorted(targets, key=lambda item: item.center)
    )
    signature = "fruit-merge-surface:" + digest_object(
        {
            "dimensions": (width, height),
            "targets": tuple(target.bbox for target in ordered_targets),
            "required_ranks": tuple(sorted(required_ranks.items())),
            "required_actors": tuple(sorted(required_actors.items())),
            "click_lattice": (
                parameters.click_x_origin,
                parameters.click_y_origin,
                parameters.click_step,
            ),
        }
    )[:24]
    return _FruitSurface(
        signature=signature,
        fruits=tuple(
            sorted(fruits, key=lambda item: (item.rank, item.center))
        ),
        actors=actors,
        targets=ordered_targets,
        required_ranks=tuple(sorted(required_ranks.items())),
        required_actors=tuple(sorted(required_actors.items())),
        parameters=parameters,
        width=width,
        height=height,
    )


def _inside(point: Point, bbox: tuple[int, int, int, int]) -> bool:
    return (
        bbox[0] <= point[0] <= bbox[2]
        and bbox[1] <= point[1] <= bbox[3]
    )


def _distance_sq(first: Point, second: Point) -> int:
    return (
        (first[0] - second[0]) ** 2
        + (first[1] - second[1]) ** 2
    )


def _bbox_distance_sq(
    bbox: tuple[int, int, int, int],
    point: Point,
) -> int:
    nearest_x = min(max(point[0], bbox[0]), bbox[2])
    nearest_y = min(max(point[1], bbox[1]), bbox[3])
    return (
        (point[0] - nearest_x) ** 2
        + (point[1] - nearest_y) ** 2
    )


def _valid_clicks(surface: _FruitSurface) -> tuple[Point, ...]:
    parameters = surface.parameters
    return tuple(
        (x, y)
        for x in range(
            parameters.click_x_origin,
            surface.width,
            parameters.click_step,
        )
        for y in range(
            parameters.click_y_origin,
            min(surface.height - 1, parameters.playfield_max_y) + 1,
            parameters.click_step,
        )
    )


def _affected_fruits(
    surface: _FruitSurface,
    click: Point,
) -> tuple[int, ...]:
    radius_sq = surface.parameters.click_radius**2
    return tuple(
        index
        for index, fruit in enumerate(surface.fruits)
        if _bbox_distance_sq(fruit.bbox, click) <= radius_sq
    )


def _affected_actors(
    surface: _FruitSurface,
    click: Point,
) -> tuple[int, ...]:
    radius_sq = surface.parameters.click_radius**2
    return tuple(
        index
        for index, actor in enumerate(surface.actors)
        if _bbox_distance_sq(actor.bbox, click) <= radius_sq
    )


def _transition_observation_click(
    surface: _FruitSurface,
) -> Point | None:
    """Choose a rendered-lattice click outside every semantic object."""

    semantic_boxes = tuple(
        (
            *(fruit.bbox for fruit in surface.fruits),
            *(actor.bbox for actor in surface.actors),
            *(target.bbox for target in surface.targets),
        )
    )
    radius_sq = surface.parameters.click_radius**2
    candidates: list[tuple[int, int, int, Point]] = []
    for click in _valid_clicks(surface):
        if (
            _affected_fruits(surface, click)
            or _affected_actors(surface, click)
            or any(
                _bbox_distance_sq(box, click) <= radius_sq
                for box in (target.bbox for target in surface.targets)
            )
        ):
            continue
        minimum_clearance = min(
            (
                _bbox_distance_sq(box, click)
                for box in semantic_boxes
            ),
            default=surface.width * surface.width
            + surface.height * surface.height,
        )
        candidates.append(
            (
                minimum_clearance,
                -click[1],
                -click[0],
                click,
            )
        )
    return None if not candidates else max(candidates)[-1]


def _interface_observation_click(
    grid: Grid,
    surface: _FruitSurface,
) -> Point | None:
    """Choose a rendered interface-background point with maximal clearance."""

    interface_height = min(
        len(grid),
        surface.parameters.interface_max_y + 1,
    )
    if interface_height < 1 or not grid or not grid[0]:
        return None
    width = min(surface.width, len(grid[0]))
    colors = Counter(
        grid[y][x]
        for y in range(interface_height)
        for x in range(width)
    )
    if not colors:
        return None
    background = min(
        colors,
        key=lambda color: (-colors[color], color),
    )
    foreground = tuple(
        (x, y)
        for y in range(interface_height)
        for x in range(width)
        if grid[y][x] != background
    )
    candidates: list[tuple[int, int, int, Point]] = []
    for y in range(interface_height):
        for x in range(width):
            if grid[y][x] != background:
                continue
            clearance = min(
                (
                    _distance_sq((x, y), point)
                    for point in foreground
                ),
                default=width * width + interface_height * interface_height,
            )
            candidates.append((clearance, x, y, (x, y)))
    return None if not candidates else max(candidates)[-1]


def _moved_fruit_center(
    fruit: _Fruit,
    click: Point,
    step: int,
) -> Point:
    return (
        fruit.center[0] + max(-step, min(step, click[0] - fruit.center[0])),
        fruit.center[1] + max(-step, min(step, click[1] - fruit.center[1])),
    )


def _bbox_at(
    bbox: tuple[int, int, int, int],
    center: Point,
) -> tuple[int, int, int, int]:
    width = bbox[2] - bbox[0] + 1
    height = bbox[3] - bbox[1] + 1
    left = center[0] - width // 2
    top = center[1] - height // 2
    return (left, top, left + width - 1, top + height - 1)


def _overlap(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def _safe_fruit_move(
    surface: _FruitSurface,
    source_index: int,
    click: Point,
) -> bool:
    source = surface.fruits[source_index]
    predicted = _bbox_at(
        source.bbox,
        _moved_fruit_center(
            source,
            click,
            surface.parameters.fruit_move_step,
        ),
    )
    return all(
        index == source_index
        or fruit.rank == source.rank
        or not _overlap(predicted, fruit.bbox)
        for index, fruit in enumerate(surface.fruits)
    )


def _target_occupancy(
    surface: _FruitSurface,
) -> tuple[
    Counter[int],
    Counter[str],
    tuple[int, ...],
]:
    rank_counts: Counter[int] = Counter()
    actor_counts: Counter[str] = Counter()
    occupied: set[int] = set()
    for index, target in enumerate(surface.targets):
        for fruit in surface.fruits:
            if _inside(fruit.center, target.bbox):
                rank_counts[fruit.rank] += 1
                occupied.add(index)
                break
        if index in occupied:
            continue
        for actor in surface.actors:
            if _inside(actor.center, target.bbox):
                actor_counts[actor.kind] += 1
                occupied.add(index)
                break
    return rank_counts, actor_counts, tuple(sorted(occupied))


def _missing_requirements(
    surface: _FruitSurface,
) -> tuple[Counter[int], Counter[str], tuple[int, ...]]:
    present_ranks, present_actors, occupied = _target_occupancy(surface)
    missing_ranks = Counter(
        {
            rank: max(0, count - present_ranks.get(rank, 0))
            for rank, count in surface.required_ranks
        }
    )
    missing_actors = Counter(
        {
            kind: max(0, count - present_actors.get(kind, 0))
            for kind, count in surface.required_actors
        }
    )
    return (
        +missing_ranks,
        +missing_actors,
        occupied,
    )


def _rank_requirements_materialized(
    surface: _FruitSurface,
    missing: Counter[int],
) -> bool:
    available: Counter[int] = Counter(
        fruit.rank
        for fruit in surface.fruits
        if not any(
            _inside(fruit.center, target.bbox)
            for target in surface.targets
        )
    )
    return all(
        available.get(rank, 0) >= count
        for rank, count in missing.items()
        if count > 0
    )


def _actor_requirements_materialized(
    surface: _FruitSurface,
    missing: Counter[str],
) -> bool:
    available: Counter[str] = Counter(
        actor.kind
        for actor in surface.actors
        if not any(
            _inside(actor.center, target.bbox)
            for target in surface.targets
        )
    )
    return all(
        available.get(kind, 0) >= count
        for kind, count in missing.items()
        if count > 0
    )


def _empty_targets(
    surface: _FruitSurface,
    occupied: tuple[int, ...],
) -> tuple[_Target, ...]:
    occupied_set = set(occupied)
    return tuple(
        target
        for index, target in enumerate(surface.targets)
        if index not in occupied_set
    )


def _route_required_fruit(
    surface: _FruitSurface,
    missing: Counter[int],
    targets: tuple[_Target, ...],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    desired = {
        rank for rank, count in missing.items() if count > 0
    }
    candidates: list[tuple[int, int, int, int, int, Point]] = []
    for source_index, fruit in enumerate(surface.fruits):
        if fruit.rank not in desired or any(
            _inside(fruit.center, target.bbox)
            for target in surface.targets
        ):
            continue
        for target in targets:
            before = _distance_sq(fruit.center, target.center)
            for click in _valid_clicks(surface):
                if (
                    click in blocked_clicks
                    or _affected_fruits(surface, click)
                    != (source_index,)
                    or _affected_actors(surface, click)
                    or not _safe_fruit_move(surface, source_index, click)
                ):
                    continue
                predicted = _moved_fruit_center(
                    fruit,
                    click,
                    surface.parameters.fruit_move_step,
                )
                after = _distance_sq(predicted, target.center)
                if after >= before:
                    continue
                candidates.append(
                    (
                        -fruit.rank,
                        after,
                        before,
                        click[1],
                        click[0],
                        click,
                    )
                )
    return None if not candidates else min(candidates)[-1]


def _merge_candidate(
    surface: _FruitSurface,
    missing: Counter[int],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    desired = tuple(rank for rank, count in missing.items() if count > 0)
    if not desired:
        return None
    candidates: list[tuple[int, int, int, int, Point]] = []
    for click in _valid_clicks(surface):
        if click in blocked_clicks:
            continue
        affected = _affected_fruits(surface, click)
        if len(affected) != 2 or _affected_actors(surface, click):
            continue
        ranks = {surface.fruits[index].rank for index in affected}
        if len(ranks) != 1:
            continue
        rank = next(iter(ranks))
        if not any(rank < target_rank for target_rank in desired):
            continue
        midpoint = (
            sum(surface.fruits[index].center[0] for index in affected) // 2,
            sum(surface.fruits[index].center[1] for index in affected) // 2,
        )
        target_distance = min(
            _distance_sq(midpoint, target.center)
            for target in surface.targets
        )
        candidates.append(
            (-rank, target_distance, click[1], click[0], click)
        )
    return None if not candidates else min(candidates)[-1]


def _approach_candidate(
    surface: _FruitSurface,
    missing: Counter[int],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    desired = tuple(rank for rank, count in missing.items() if count > 0)
    if not desired:
        return None
    candidates: list[tuple[int, int, int, int, int, Point]] = []
    for source_index, source in enumerate(surface.fruits):
        if not any(source.rank < target_rank for target_rank in desired):
            continue
        for destination_index, destination in enumerate(surface.fruits):
            if (
                source_index == destination_index
                or source.rank != destination.rank
            ):
                continue
            before = _distance_sq(source.center, destination.center)
            for click in _valid_clicks(surface):
                if (
                    click in blocked_clicks
                    or _affected_fruits(surface, click)
                    != (source_index,)
                    or _affected_actors(surface, click)
                    or not _safe_fruit_move(surface, source_index, click)
                ):
                    continue
                predicted = _moved_fruit_center(
                    source,
                    click,
                    surface.parameters.fruit_move_step,
                )
                after = _distance_sq(predicted, destination.center)
                if after >= before:
                    continue
                candidates.append(
                    (
                        -source.rank,
                        after,
                        before,
                        click[1],
                        click[0],
                        click,
                    )
                )
    return None if not candidates else min(candidates)[-1]


def _moved_actor_center(
    actor: _Actor,
    click: Point,
    distance: int,
    surface: _FruitSurface,
) -> Point:
    dx = click[0] - actor.center[0]
    dy = click[1] - actor.center[1]
    distance_sq = dx * dx + dy * dy
    if distance_sq == 0:
        return actor.center
    scale = distance / (distance_sq**0.5)
    width = actor.bbox[2] - actor.bbox[0] + 1
    height = actor.bbox[3] - actor.bbox[1] + 1
    return (
        max(
            width // 2,
            min(
                surface.width - 1 - width // 2,
                int(round(actor.center[0] + dx * scale)),
            ),
        ),
        max(
            surface.parameters.playfield_min_y + height // 2,
            min(
                surface.parameters.playfield_max_y - height // 2,
                int(round(actor.center[1] + dy * scale)),
            ),
        ),
    )


def _route_required_actor(
    surface: _FruitSurface,
    missing: Counter[str],
    targets: tuple[_Target, ...],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    desired = {
        kind for kind, count in missing.items() if count > 0
    }
    candidates: list[tuple[int, int, int, int, Point]] = []
    for actor_index, actor in enumerate(surface.actors):
        if actor.kind not in desired or any(
            _inside(actor.center, target.bbox)
            for target in surface.targets
        ):
            continue
        for target in targets:
            before = _distance_sq(actor.center, target.center)
            for click in _valid_clicks(surface):
                if (
                    click in blocked_clicks
                    or _affected_actors(surface, click)
                    != (actor_index,)
                    or _affected_fruits(surface, click)
                ):
                    continue
                predicted = _moved_actor_center(
                    actor,
                    click,
                    surface.parameters.actor_move_distance,
                    surface,
                )
                after = _distance_sq(predicted, target.center)
                if after >= before:
                    continue
                candidates.append(
                    (after, before, click[1], click[0], click)
                )
    return None if not candidates else min(candidates)[-1]


def _merge_actor_candidate(
    surface: _FruitSurface,
    missing: Counter[str],
    blocked_clicks: frozenset[Point],
) -> tuple[Point, str] | None:
    chain = surface.parameters.actor_merge_chain
    chain_index = {kind: index for index, kind in enumerate(chain)}
    desired_indices = tuple(
        chain_index[kind]
        for kind, count in missing.items()
        if count > 0 and kind in chain_index
    )
    if not desired_indices:
        return None

    def gap(kind: str) -> int | None:
        source_index = chain_index.get(kind)
        if source_index is None:
            return None
        gaps = tuple(
            desired_index - source_index
            for desired_index in desired_indices
            if desired_index > source_index
        )
        return None if not gaps else min(gaps)

    direct: list[tuple[int, int, int, Point]] = []
    for click in _valid_clicks(surface):
        if click in blocked_clicks or _affected_fruits(surface, click):
            continue
        affected = _affected_actors(surface, click)
        if len(affected) != 2:
            continue
        first = surface.actors[affected[0]]
        second = surface.actors[affected[1]]
        source_gap = gap(first.kind)
        if source_gap is None or first.kind != second.kind:
            continue
        direct.append((source_gap, click[1], click[0], click))
    if direct:
        return min(direct)[-1], "rendered-equal-kind-actor-merge"

    approach: list[tuple[int, int, int, int, int, Point]] = []
    for source_index, source in enumerate(surface.actors):
        source_gap = gap(source.kind)
        if source_gap is None:
            continue
        for destination_index, destination in enumerate(surface.actors):
            if (
                source_index == destination_index
                or source.kind != destination.kind
            ):
                continue
            before = _distance_sq(source.center, destination.center)
            for click in _valid_clicks(surface):
                if (
                    click in blocked_clicks
                    or _affected_actors(surface, click)
                    != (source_index,)
                    or _affected_fruits(surface, click)
                ):
                    continue
                predicted = _moved_actor_center(
                    source,
                    click,
                    surface.parameters.actor_move_distance,
                    surface,
                )
                if any(
                    _overlap(
                        _bbox_at(source.bbox, predicted),
                        fruit.bbox,
                    )
                    for fruit in surface.fruits
                ):
                    continue
                after = _distance_sq(predicted, destination.center)
                if after >= before:
                    continue
                approach.append(
                    (
                        source_gap,
                        after,
                        before,
                        click[1],
                        click[0],
                        click,
                    )
                )
    if not approach:
        return None
    return min(approach)[-1], "rendered-equal-kind-actor-approach"


def _route_actor_rank_reduction(
    surface: _FruitSurface,
    missing: Counter[int],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    delta = surface.parameters.actor_fruit_rank_delta
    desired = tuple(rank for rank, count in missing.items() if count > 0)
    candidates: list[tuple[int, int, int, int, int, int, Point]] = []
    for actor_index, actor in enumerate(surface.actors):
        for fruit in surface.fruits:
            reachable = tuple(
                rank
                for rank in desired
                if fruit.rank > rank
                and (fruit.rank - rank) % abs(delta) == 0
            )
            if not reachable:
                continue
            target_rank = max(reachable)
            before = _distance_sq(actor.center, fruit.center)
            for click in _valid_clicks(surface):
                if (
                    click in blocked_clicks
                    or _affected_actors(surface, click) != (actor_index,)
                    or _affected_fruits(surface, click)
                ):
                    continue
                predicted = _moved_actor_center(
                    actor,
                    click,
                    surface.parameters.actor_move_distance,
                    surface,
                )
                after = _distance_sq(predicted, fruit.center)
                if after >= before:
                    continue
                candidates.append(
                    (
                        fruit.rank - target_rank,
                        after,
                        before,
                        click[1],
                        click[0],
                        actor_index,
                        click,
                    )
                )
    return None if not candidates else min(candidates)[-1]


def _wait_for_actor_rank_reduction(
    surface: _FruitSurface,
    missing: Counter[int],
    blocked_clicks: frozenset[Point],
) -> Point | None:
    delta = surface.parameters.actor_fruit_rank_delta
    desired = tuple(rank for rank, count in missing.items() if count > 0)
    pair_distances = tuple(
        _distance_sq(actor.center, fruit.center)
        for actor in surface.actors
        for fruit in surface.fruits
        if any(
            fruit.rank > rank
            and (fruit.rank - rank) % abs(delta) == 0
            for rank in desired
        )
    )
    if (
        not pair_distances
        or min(pair_distances)
        > surface.parameters.actor_chase_risk_distance**2
    ):
        return None
    entity_boxes = tuple(
        fruit.bbox for fruit in surface.fruits
    ) + tuple(actor.bbox for actor in surface.actors)
    candidates: list[tuple[int, int, int, Point]] = []
    for click in _valid_clicks(surface):
        if (
            click in blocked_clicks
            or _affected_fruits(surface, click)
            or _affected_actors(surface, click)
        ):
            continue
        clearance = min(
            (_bbox_distance_sq(bbox, click) for bbox in entity_boxes),
            default=0,
        )
        candidates.append((-clearance, click[1], click[0], click))
    return None if not candidates else min(candidates)[-1]


def _actor_risk(surface: _FruitSurface, actor: _Actor) -> int:
    if not surface.fruits:
        return 1 << 30
    return min(
        _distance_sq(actor.center, fruit.center)
        for fruit in surface.fruits
    )


def _terminal_required_actor_at_risk(
    surface: _FruitSurface,
    missing: Counter[str],
) -> bool:
    """Detect a visible required terminal actor close enough to chase fruit."""

    if not surface.parameters.actor_merge_chain:
        return False
    terminal_kind = surface.parameters.actor_merge_chain[-1]
    if missing.get(terminal_kind, 0) <= 0:
        return False
    risk_limit = surface.parameters.actor_chase_risk_distance**2
    return any(
        actor.kind == terminal_kind
        and not any(
            _inside(actor.center, target.bbox)
            for target in surface.targets
        )
        and _actor_risk(surface, actor) <= risk_limit
        for actor in surface.actors
    )


def _target_actor_anchor_click(
    surface: _FruitSurface,
) -> Point | None:
    """Anchor a required terminal actor already occupying a target."""

    if not surface.parameters.actor_merge_chain:
        return None
    terminal_kind = surface.parameters.actor_merge_chain[-1]
    required = Counter(dict(surface.required_actors))
    if required.get(terminal_kind, 0) <= 0:
        return None
    candidates: list[tuple[int, int, Point]] = []
    for actor in surface.actors:
        if (
            actor.kind != terminal_kind
            or not any(
                _inside(actor.center, target.bbox)
                for target in surface.targets
            )
            or _affected_fruits(surface, actor.center)
        ):
            continue
        candidates.append((actor.center[1], actor.center[0], actor.center))
    return None if not candidates else min(candidates)[-1]


def _protect_required_terminal_actor(
    surface: _FruitSurface,
    blocked_clicks: frozenset[Point],
) -> Point | None:
    """Move only the rendered required terminal actor away from fruit."""

    if not surface.parameters.actor_merge_chain:
        return None
    terminal_kind = surface.parameters.actor_merge_chain[-1]
    required = Counter(dict(surface.required_actors))
    if required.get(terminal_kind, 0) <= 0:
        return None
    excluded = Counter(
        {
            actor.kind: 1
            for actor in surface.actors
            if actor.kind != terminal_kind
        }
    )
    return _divert_actor(
        surface,
        excluded,
        blocked_clicks,
        force=False,
    )


def _divert_actor(
    surface: _FruitSurface,
    required_actors: Counter[str],
    blocked_clicks: frozenset[Point],
    *,
    force: bool,
) -> Point | None:
    risk_limit = surface.parameters.actor_chase_risk_distance**2
    candidates: list[tuple[int, int, int, int, int, Point]] = []
    for actor_index, actor in enumerate(surface.actors):
        if required_actors.get(actor.kind, 0) > 0:
            continue
        current_risk = _actor_risk(surface, actor)
        if not force and current_risk > risk_limit:
            continue
        for click in _valid_clicks(surface):
            if (
                click in blocked_clicks
                or _affected_actors(surface, click) != (actor_index,)
                or _affected_fruits(surface, click)
            ):
                continue
            predicted = _moved_actor_center(
                actor,
                click,
                surface.parameters.actor_move_distance,
                surface,
            )
            predicted_risk = min(
                (
                    _distance_sq(predicted, fruit.center)
                    for fruit in surface.fruits
                ),
                default=1 << 30,
            )
            if predicted_risk <= current_risk:
                continue
            candidates.append(
                (
                    current_risk,
                    -predicted_risk,
                    _distance_sq(
                        predicted,
                        (surface.width - 2, surface.parameters.playfield_min_y),
                    ),
                    click[1],
                    click[0],
                    click,
                )
            )
    return None if not candidates else min(candidates)[-1]


def _route_actor_protection_click(
    surface: _FruitSurface,
    blocked_clicks: frozenset[Point],
) -> Point | None:
    """Move any actor beyond one chase step plus the normal risk margin."""

    protection_distance = (
        surface.parameters.actor_chase_risk_distance
        + surface.parameters.actor_move_distance
    )
    if all(
        _actor_risk(surface, actor) > protection_distance**2
        for actor in surface.actors
    ):
        return None
    return _divert_actor(
        surface,
        Counter(),
        blocked_clicks,
        force=True,
    )


def _semantic_action(
    surface: _FruitSurface,
    instruction: SemanticOperatorInstruction,
    click: Point,
    *,
    reason: str,
) -> VisualAction:
    operator_id = instruction.operator_id
    return VisualAction(
        key="semantic-fruit-merge:"
        + digest_object(
            {
                "operator": operator_id,
                "surface": surface.signature,
                "click": click,
                "reason": reason,
            }
        )[:20],
        action_id=surface.parameters.click_action,
        group=0,
        x=click[0],
        y=click[1],
        evidence=(
            operator_id,
            f"operator-prototype:{operator_id}",
            reason,
            *instruction.provenance,
        ),
    )


def _semantic_undo_action(
    instruction: SemanticOperatorInstruction,
    *,
    surface_signature: str,
    undo_action: int,
    reason: str = "rendered-fruit-surface-loss-undo",
) -> VisualAction:
    operator_id = instruction.operator_id
    return VisualAction(
        key="semantic-fruit-undo:"
        + digest_object(
            {
                "operator": operator_id,
                "surface": surface_signature,
                "reason": reason,
            }
        )[:20],
        action_id=undo_action,
        group=0,
        evidence=(
            operator_id,
            f"operator-prototype:{operator_id}",
            reason,
            *instruction.provenance,
        ),
    )


def _semantic_transition_observation_action(
    instruction: SemanticOperatorInstruction,
    *,
    surface_signature: str,
    observation_index: int,
    observation_action: int,
    observation_click: Point | None = None,
) -> VisualAction:
    reason = "rendered-semantic-effect-observation"
    operator_id = instruction.operator_id
    key_payload: dict[str, object] = {
        "operator": operator_id,
        "surface": surface_signature,
        "observation_index": observation_index,
        "reason": reason,
    }
    if observation_click is not None:
        key_payload["observation_click"] = observation_click
    return VisualAction(
        key="semantic-fruit-observe:"
        + digest_object(key_payload)[:20],
        action_id=observation_action,
        group=0,
        x=(
            None
            if observation_click is None
            else observation_click[0]
        ),
        y=(
            None
            if observation_click is None
            else observation_click[1]
        ),
        evidence=(
            operator_id,
            f"operator-prototype:{operator_id}",
            reason,
            *instruction.provenance,
        ),
    )


@dataclass(slots=True)
class FruitMergeState:
    """Passive state for a rendered fruit/actor target surface."""

    instruction_digest: str = ""
    surface_signature: str = ""
    previous_grid_digest: str = ""
    last_action_kind: str = ""
    observation_count: int = 0
    decision_count: int = 0
    fruit_action_streak: int = 0
    actor_action_count: int = 0
    last_click: Point | None = None
    blocked_clicks: list[Point] = field(default_factory=list)
    undo_pending: bool = False
    abandoned: bool = False
    pending_effect_click: Point | None = None
    pending_effect_kind: str = ""
    pending_effect_observations: int = 0
    pending_effect_observation_click: Point | None = None

    def reset(self) -> None:
        self.instruction_digest = ""
        self.surface_signature = ""
        self.previous_grid_digest = ""
        self.last_action_kind = ""
        self.observation_count = 0
        self.decision_count = 0
        self.fruit_action_streak = 0
        self.actor_action_count = 0
        self.last_click = None
        self.blocked_clicks.clear()
        self.undo_pending = False
        self.abandoned = False
        self.pending_effect_click = None
        self.pending_effect_kind = ""
        self.pending_effect_observations = 0
        self.pending_effect_observation_click = None

    def _bind(
        self,
        surface: _FruitSurface,
        instruction: SemanticOperatorInstruction,
    ) -> None:
        instruction_digest = digest_object(instruction)
        if (
            self.instruction_digest == instruction_digest
            and self.surface_signature == surface.signature
        ):
            return
        self.reset()
        self.instruction_digest = instruction_digest
        self.surface_signature = surface.signature

    def _record_observation(self, grid: Grid) -> bool:
        current = digest_object(grid)
        influenced = bool(
            self.previous_grid_digest
            and self.previous_grid_digest != current
        )
        if influenced:
            self.observation_count += 1
        self.previous_grid_digest = current
        return influenced

    def _clear_pending_effect(self) -> None:
        self.pending_effect_click = None
        self.pending_effect_kind = ""
        self.pending_effect_observations = 0
        self.pending_effect_observation_click = None

    def _stage_pending_effect(
        self,
        surface: _FruitSurface,
        grid: Grid,
        click: Point,
        action_kind: str,
        reason: str,
        instruction: SemanticOperatorInstruction,
    ) -> None:
        self.pending_effect_click = click
        self.pending_effect_kind = action_kind
        self.pending_effect_observations = 0
        self.pending_effect_observation_click = (
            _transition_observation_click(surface)
            if (
                instruction.operator_id
                == FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR
                or (
                    instruction.operator_id
                    == FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR
                    and reason == "rendered-required-fruit-route"
                )
            )
            else (
                click
                if (
                    instruction.operator_id
                    == FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR
                )
                or (
                    instruction.operator_id
                    == FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR
                    and reason == "rendered-required-fruit-route"
                )
                or (
                    instruction.operator_id
                    == FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR
                )
                else None
            )
        )
        if (
            instruction.operator_id
            == FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR
        ):
            self.pending_effect_observation_click = (
                _interface_observation_click(grid, surface)
            )
        if (
            instruction.operator_id
            == FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR
            and reason == "rendered-required-fruit-route"
        ):
            self.pending_effect_observation_click = (
                _transition_observation_click(surface)
            )
        if (
            instruction.operator_id
            == FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR
            and reason == "rendered-required-fruit-route"
        ):
            self.pending_effect_observation_click = (
                _target_actor_anchor_click(surface)
            )

    def _observe_pending_effect(
        self,
        instruction: SemanticOperatorInstruction,
        parameters: _FruitParameters,
    ) -> FruitMergeDecision | None:
        if (
            instruction.operator_id
            not in {
                FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
            }
            or self.pending_effect_click is None
            or self.pending_effect_observations
            >= parameters.maximum_transition_observations
            or (
                instruction.operator_id
                in {
                    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                }
                and self.pending_effect_observation_click is None
            )
        ):
            return None
        self.pending_effect_observations += 1
        self.decision_count += 1
        click_observation = (
            instruction.operator_id
            in {
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
            }
        )
        return FruitMergeDecision(
            action=_semantic_transition_observation_action(
                instruction,
                surface_signature=self.surface_signature,
                observation_index=self.pending_effect_observations,
                observation_action=(
                    parameters.click_action
                    if click_observation
                    else parameters.undo_action
                ),
                observation_click=(
                    self.pending_effect_observation_click
                    if click_observation
                    else None
                ),
            ),
            reason=(
                f"{instruction.operator_id}:"
                "rendered-semantic-effect-observation"
            ),
            memory_influenced=True,
        )

    def _rollback_pending_effect(
        self,
        instruction: SemanticOperatorInstruction,
        parameters: _FruitParameters,
        *,
        reason: str,
    ) -> FruitMergeDecision:
        failed_click = self.pending_effect_click or self.last_click
        failed_kind = self.pending_effect_kind or self.last_action_kind
        if (
            failed_click is not None
            and failed_click not in self.blocked_clicks
        ):
            self.blocked_clicks.append(failed_click)
            self.blocked_clicks = self.blocked_clicks[-64:]
        self._clear_pending_effect()
        self.undo_pending = True
        self.last_action_kind = "undo"
        self.fruit_action_streak = (
            parameters.actor_divert_interval
            if failed_kind == "fruit"
            else 0
        )
        self.decision_count += 1
        return FruitMergeDecision(
            action=_semantic_undo_action(
                instruction,
                surface_signature=self.surface_signature,
                undo_action=parameters.undo_action,
                reason=reason,
            ),
            reason=f"{instruction.operator_id}:{reason}",
            memory_influenced=True,
        )

    def decide(
        self,
        grid: Grid,
        available_actions: tuple[int, ...],
        instruction: SemanticOperatorInstruction,
    ) -> FruitMergeDecision:
        surface = _surface_from_grid(
            grid,
            available_actions,
            instruction,
        )
        if surface is None:
            parameters = _FruitParameters.from_instruction(instruction)
            if (
                parameters is not None
                and instruction.operator_id
                in {
                    FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                }
                and self.pending_effect_click is not None
                and parameters.undo_action in available_actions
            ):
                return self._rollback_pending_effect(
                    instruction,
                    parameters,
                    reason="rendered-fruit-surface-loss-undo",
                )
            if (
                parameters is not None
                and instruction.operator_id
                in {
                    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                }
                and self.pending_effect_click is not None
                and (
                    parameters.click_action
                    if (
                        instruction.operator_id
                        in {
                            FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                            FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                        }
                    )
                    else parameters.undo_action
                )
                in available_actions
            ):
                observation = self._observe_pending_effect(
                    instruction,
                    parameters,
                )
                if observation is not None:
                    return observation
                return self._rollback_pending_effect(
                    instruction,
                    parameters,
                    reason="rendered-effect-observation-limit-undo",
                )
            if (
                parameters is not None
                and parameters.undo_action in available_actions
                and self.surface_signature
                and self.last_click is not None
                and not self.undo_pending
                and self.instruction_digest == digest_object(instruction)
            ):
                hazard_action_kind = self.last_action_kind
                if self.last_click not in self.blocked_clicks:
                    self.blocked_clicks.append(self.last_click)
                    self.blocked_clicks = self.blocked_clicks[-64:]
                self.undo_pending = True
                self.last_action_kind = "undo"
                self.fruit_action_streak = (
                    parameters.actor_divert_interval
                    if hazard_action_kind == "fruit"
                    else 0
                )
                self.decision_count += 1
                return FruitMergeDecision(
                    action=_semantic_undo_action(
                        instruction,
                        surface_signature=self.surface_signature,
                        undo_action=parameters.undo_action,
                    ),
                    reason=(
                        f"{instruction.operator_id}:"
                        "rendered-fruit-surface-loss-undo"
                    ),
                    memory_influenced=True,
                )
            return FruitMergeDecision(
                action=None,
                reason="NO_RENDERED_FRUIT_MERGE_SURFACE",
                memory_influenced=bool(self.observation_count),
            )
        self._bind(surface, instruction)
        self.undo_pending = False
        influenced = self._record_observation(grid)
        if self.abandoned:
            return FruitMergeDecision(
                action=None,
                reason="FRUIT_MERGE_STATE_ABANDONED",
                memory_influenced=True,
            )

        missing_ranks, missing_actors, occupied = _missing_requirements(
            surface
        )
        blocked_clicks = frozenset(self.blocked_clicks)
        empty_targets = _empty_targets(surface, occupied)
        ranks_materialized = _rank_requirements_materialized(
            surface,
            missing_ranks,
        )
        actors_materialized = _actor_requirements_materialized(
            surface,
            missing_actors,
        )
        goals_materialized = (
            ranks_materialized and actors_materialized
        )
        place_mobile_actor_last = (
            instruction.operator_id
            in {
                FRUIT_MERGE_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
            }
        )
        if (
            instruction.operator_id
            in {
                FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
            }
            and _terminal_required_actor_at_risk(surface, missing_actors)
        ):
            place_mobile_actor_last = False
        click: Point | None = None
        reason = ""
        action_kind = "fruit"
        if (
            goals_materialized
            and (not place_mobile_actor_last or not missing_ranks)
            and missing_actors
            and surface.actors
        ):
            click = _divert_actor(
                surface,
                Counter(dict(surface.required_actors)),
                blocked_clicks,
                force=False,
            )
            if click is not None:
                reason = "rendered-actor-hazard-divert"
                action_kind = "actor"
        if (
            click is None
            and goals_materialized
            and (not place_mobile_actor_last or not missing_ranks)
        ):
            click = _route_required_actor(
                surface,
                missing_actors,
                empty_targets,
                blocked_clicks,
            )
            reason = "rendered-required-actor-route"
            if click is not None:
                action_kind = "actor"
        if click is None and not ranks_materialized:
            construction_click = _merge_candidate(
                surface,
                missing_ranks,
                blocked_clicks,
            )
            construction_reason = "rendered-equal-rank-merge"
            if construction_click is None:
                construction_click = _approach_candidate(
                    surface,
                    missing_ranks,
                    blocked_clicks,
                )
                construction_reason = "rendered-equal-rank-approach"
            if (
                construction_click is not None
                and surface.actors
                and self.fruit_action_streak
                >= surface.parameters.actor_divert_interval
            ):
                click = _divert_actor(
                    surface,
                    Counter(dict(surface.required_actors)),
                    blocked_clicks,
                    force=True,
                )
                if click is not None:
                    reason = "rendered-actor-hazard-divert"
                    action_kind = "actor"
            if click is None and construction_click is not None:
                click = construction_click
                reason = construction_reason
        if click is None and not ranks_materialized:
            click = _route_actor_rank_reduction(
                surface,
                missing_ranks,
                blocked_clicks,
            )
            reason = "rendered-actor-fruit-rank-reduction"
            action_kind = "actor"
        if click is None and not ranks_materialized:
            click = _wait_for_actor_rank_reduction(
                surface,
                missing_ranks,
                blocked_clicks,
            )
            reason = "rendered-actor-chase-rank-reduction"
            action_kind = "actor"
        if click is None and ranks_materialized and not actors_materialized:
            actor_merge = _merge_actor_candidate(
                surface,
                missing_actors,
                blocked_clicks,
            )
            if actor_merge is not None:
                click, reason = actor_merge
                action_kind = "actor"
        if (
            click is None
            and goals_materialized
            and surface.actors
            and self.last_action_kind != "actor"
        ):
            click = _divert_actor(
                surface,
                Counter(dict(surface.required_actors)),
                blocked_clicks,
                force=False,
            )
            if (
                click is None
                and self.fruit_action_streak
                >= surface.parameters.actor_divert_interval
            ):
                click = _divert_actor(
                    surface,
                    Counter(dict(surface.required_actors)),
                    blocked_clicks,
                    force=True,
                )
            if click is not None:
                reason = "rendered-actor-hazard-divert"
                action_kind = "actor"
        if click is None and goals_materialized:
            if (
                instruction.operator_id
                == FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR
                and missing_ranks
                and surface.actors
            ):
                click = _route_actor_protection_click(
                    surface,
                    blocked_clicks,
                )
                if click is not None:
                    reason = "rendered-actor-hazard-divert"
                    action_kind = "actor"
        if click is None and goals_materialized:
            if (
                instruction.operator_id
                == FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR
                and missing_ranks
                and surface.actors
            ):
                click = _protect_required_terminal_actor(
                    surface,
                    blocked_clicks,
                )
                if click is not None:
                    reason = "rendered-actor-hazard-divert"
                    action_kind = "actor"
        if click is None and goals_materialized:
            click = _route_required_fruit(
                surface,
                missing_ranks,
                empty_targets,
                blocked_clicks,
            )
            reason = "rendered-required-fruit-route"
            action_kind = "fruit"
        if click is None and surface.actors and actors_materialized:
            click = _divert_actor(
                surface,
                Counter(dict(surface.required_actors)),
                blocked_clicks,
                force=False,
            )
            reason = "rendered-actor-hazard-divert"
            action_kind = "actor"
        if click is None:
            if (
                instruction.operator_id
                in {
                    FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                }
                and self.pending_effect_click is not None
            ):
                return self._rollback_pending_effect(
                    instruction,
                    surface.parameters,
                    reason="rendered-goal-plan-unavailable-undo",
                )
            if (
                instruction.operator_id
                in {
                    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                }
                and self.pending_effect_click is not None
            ):
                observation = self._observe_pending_effect(
                    instruction,
                    surface.parameters,
                )
                if observation is not None:
                    return observation
                return self._rollback_pending_effect(
                    instruction,
                    surface.parameters,
                    reason="rendered-effect-observation-limit-undo",
                )
            return FruitMergeDecision(
                action=None,
                reason="FRUIT_MERGE_GOAL_PLAN_UNAVAILABLE",
                memory_influenced=(
                    influenced
                    or bool(self.observation_count)
                    or bool(self.decision_count)
                ),
            )

        self.decision_count += 1
        self.last_action_kind = action_kind
        self.last_click = click
        if action_kind == "actor":
            self.actor_action_count += 1
            self.fruit_action_streak = 0
        else:
            self.fruit_action_streak += 1
        if (
            instruction.operator_id
            in {
                FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
            }
        ):
            self._stage_pending_effect(
                surface,
                grid,
                click,
                action_kind,
                reason,
                instruction,
            )
        return FruitMergeDecision(
            action=_semantic_action(
                surface,
                instruction,
                click,
                reason=reason,
            ),
            reason=f"{instruction.operator_id}:{reason}",
            memory_influenced=(
                influenced
                or self.observation_count > 0
                or self.decision_count > 1
            ),
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": FRUIT_MERGE_STATE_FORMAT,
            "instruction_digest": self.instruction_digest,
            "surface_signature": self.surface_signature,
            "previous_grid_digest": self.previous_grid_digest,
            "last_action_kind": self.last_action_kind,
            "observation_count": self.observation_count,
            "decision_count": self.decision_count,
            "fruit_action_streak": self.fruit_action_streak,
            "actor_action_count": self.actor_action_count,
            "last_click": (
                None
                if self.last_click is None
                else list(self.last_click)
            ),
            "blocked_clicks": [
                list(click) for click in self.blocked_clicks[-64:]
            ],
            "undo_pending": self.undo_pending,
            "abandoned": self.abandoned,
        }
        if self.pending_effect_click is not None:
            if (
                self.pending_effect_kind not in {"fruit", "actor"}
                or not 0 <= self.pending_effect_observations <= 32
            ):
                raise ValueError("fruit merge pending effect state invalid")
            pending_effect: dict[str, object] = {
                "click": list(self.pending_effect_click),
                "kind": self.pending_effect_kind,
                "observations": self.pending_effect_observations,
            }
            if self.pending_effect_observation_click is not None:
                pending_effect["observation_click"] = list(
                    self.pending_effect_observation_click
                )
            payload["pending_effect"] = pending_effect
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "FRUIT_MERGE_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        value: Mapping[str, object],
    ) -> FruitMergeState:
        if value.get("format") != FRUIT_MERGE_STATE_FORMAT:
            raise ValueError("fruit merge payload format invalid")
        abandoned = value.get("abandoned", False)
        if not isinstance(abandoned, bool):
            raise ValueError("fruit merge abandoned flag invalid")
        undo_pending = value.get("undo_pending", False)
        if not isinstance(undo_pending, bool):
            raise ValueError("fruit merge undo pending flag invalid")
        last_action_kind = str(value.get("last_action_kind", ""))
        if last_action_kind not in {"", "fruit", "actor", "undo"}:
            raise ValueError("fruit merge action kind invalid")
        raw_last_click = value.get("last_click")
        raw_blocked_clicks = value.get("blocked_clicks", ())
        raw_pending_effect = value.get("pending_effect")
        last_click: Point | None = None
        if raw_last_click is not None:
            if (
                not isinstance(raw_last_click, Sequence)
                or isinstance(
                    raw_last_click,
                    (str, bytes, bytearray),
                )
                or len(raw_last_click) != 2
            ):
                raise ValueError("fruit merge last click invalid")
            last_click = (
                _payload_int(raw_last_click[0], "last_click x"),
                _payload_int(raw_last_click[1], "last_click y"),
            )
        if (
            not isinstance(raw_blocked_clicks, Sequence)
            or isinstance(
                raw_blocked_clicks,
                (str, bytes, bytearray),
            )
            or len(raw_blocked_clicks) > 64
        ):
            raise ValueError("fruit merge blocked clicks invalid")
        blocked_clicks: list[Point] = []
        for raw_click in raw_blocked_clicks:
            if (
                not isinstance(raw_click, Sequence)
                or isinstance(raw_click, (str, bytes, bytearray))
                or len(raw_click) != 2
            ):
                raise ValueError("fruit merge blocked click invalid")
            click = (
                _payload_int(raw_click[0], "blocked click x"),
                _payload_int(raw_click[1], "blocked click y"),
            )
            if click not in blocked_clicks:
                blocked_clicks.append(click)
        pending_effect_click: Point | None = None
        pending_effect_kind = ""
        pending_effect_observations = 0
        pending_effect_observation_click: Point | None = None
        if raw_pending_effect is not None:
            if not isinstance(raw_pending_effect, Mapping):
                raise ValueError("fruit merge pending effect invalid")
            raw_pending_click = raw_pending_effect.get("click")
            if (
                not isinstance(raw_pending_click, Sequence)
                or isinstance(
                    raw_pending_click,
                    (str, bytes, bytearray),
                )
                or len(raw_pending_click) != 2
            ):
                raise ValueError("fruit merge pending effect click invalid")
            pending_effect_click = (
                _payload_int(
                    raw_pending_click[0],
                    "pending_effect click x",
                ),
                _payload_int(
                    raw_pending_click[1],
                    "pending_effect click y",
                ),
            )
            pending_effect_kind = str(raw_pending_effect.get("kind", ""))
            if pending_effect_kind not in {"fruit", "actor"}:
                raise ValueError("fruit merge pending effect kind invalid")
            pending_effect_observations = _payload_int(
                raw_pending_effect.get("observations", 0),
                "pending_effect observations",
            )
            if not 0 <= pending_effect_observations <= 32:
                raise ValueError(
                    "fruit merge pending effect observations invalid"
                )
            raw_observation_click = raw_pending_effect.get(
                "observation_click"
            )
            if raw_observation_click is not None:
                if (
                    not isinstance(raw_observation_click, Sequence)
                    or isinstance(
                        raw_observation_click,
                        (str, bytes, bytearray),
                    )
                    or len(raw_observation_click) != 2
                ):
                    raise ValueError(
                        "fruit merge effect observation click invalid"
                    )
                pending_effect_observation_click = (
                    _payload_int(
                        raw_observation_click[0],
                        "effect observation click x",
                    ),
                    _payload_int(
                        raw_observation_click[1],
                        "effect observation click y",
                    ),
                )
        return cls(
            instruction_digest=str(
                value.get("instruction_digest", "")
            ),
            surface_signature=str(
                value.get("surface_signature", "")
            ),
            previous_grid_digest=str(
                value.get("previous_grid_digest", "")
            ),
            last_action_kind=last_action_kind,
            observation_count=_payload_int(
                value.get("observation_count", 0),
                "observation_count",
            ),
            decision_count=_payload_int(
                value.get("decision_count", 0),
                "decision_count",
            ),
            fruit_action_streak=_payload_int(
                value.get("fruit_action_streak", 0),
                "fruit_action_streak",
            ),
            actor_action_count=_payload_int(
                value.get("actor_action_count", 0),
                "actor_action_count",
            ),
            last_click=last_click,
            blocked_clicks=blocked_clicks,
            undo_pending=undo_pending,
            abandoned=abandoned,
            pending_effect_click=pending_effect_click,
            pending_effect_kind=pending_effect_kind,
            pending_effect_observations=pending_effect_observations,
            pending_effect_observation_click=(
                pending_effect_observation_click
            ),
        )


__all__ = [
    "FRUIT_MERGE_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_OPERATOR",
    "FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_STATE_FORMAT",
    "FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR",
    "FruitMergeDecision",
    "FruitMergeState",
]
