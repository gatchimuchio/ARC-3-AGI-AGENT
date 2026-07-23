"""Deterministic, identity-free exploration over rendered ARC-3 frames.

The explorer intentionally knows nothing about game or level identifiers.  It
derives a finite action surface from the current rendered grid, records visible
transition outcomes, and uses the learned transition graph to return to an
unexplored frontier.  Serialization is explicit so the state can be retained by
the passive memory subject rather than hidden in the planner.
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from .schema import digest_object, forbidden_runtime_paths

Grid = tuple[tuple[int, ...], ...]
Point = tuple[int, int]
Outcome = Literal["NO_CHANGE", "TRANSITION", "HAZARD"]

_OFFSETS4: tuple[Point, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
_NEUTRAL_COLORS = frozenset({0, 1, 2, 3, 4, 5})
_MASK_VALUE = 0


def _payload_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def normalized_grid(value: object) -> Grid:
    """Return a rectangular integer grid or an empty tuple."""

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = tolist()
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return ()
    rows: list[tuple[int, ...]] = []
    width: int | None = None
    for raw_row in value:
        if not isinstance(raw_row, Sequence) or isinstance(
            raw_row, (str, bytes, bytearray)
        ):
            return ()
        row: list[int] = []
        for cell in raw_row:
            if isinstance(cell, bool):
                return ()
            try:
                converted = int(cell)
            except (TypeError, ValueError, OverflowError):
                return ()
            row.append(converted)
        if not row:
            return ()
        if width is None:
            width = len(row)
        elif len(row) != width:
            return ()
        rows.append(tuple(row))
    return tuple(rows)


def last_rendered_grid(layers: object) -> Grid:
    """Select the last non-empty rendered layer without consulting identity."""

    if not isinstance(layers, Sequence) or isinstance(
        layers, (str, bytes, bytearray)
    ):
        return ()
    grids = tuple(normalized_grid(layer) for layer in layers)
    return next((grid for grid in reversed(grids) if grid), ())


@dataclass(frozen=True, slots=True)
class VisualComponent:
    color: int
    pixels: tuple[Point, ...]
    bbox: tuple[int, int, int, int]
    area: int
    rectangular: bool
    twin_count: int = 0

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0] + 1

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1] + 1

    @property
    def click_point(self) -> Point:
        """Pick the component pixel nearest its geometric centre."""

        center_x2 = self.bbox[0] + self.bbox[2]
        center_y2 = self.bbox[1] + self.bbox[3]
        return min(
            self.pixels,
            key=lambda point: (
                abs((2 * point[0]) - center_x2)
                + abs((2 * point[1]) - center_y2),
                point[1],
                point[0],
            ),
        )


def connected_components(
    grid: Grid,
    *,
    excluded: frozenset[Point] = frozenset(),
) -> tuple[VisualComponent, ...]:
    """Segment same-colour four-connected components in scan order."""

    if not grid:
        return ()
    height = len(grid)
    width = len(grid[0])
    visited: set[Point] = set(excluded)
    raw: list[VisualComponent] = []
    for y in range(height):
        for x in range(width):
            point = (x, y)
            if point in visited:
                continue
            color = grid[y][x]
            queue: deque[Point] = deque((point,))
            visited.add(point)
            pixels: list[Point] = []
            min_x = max_x = x
            min_y = max_y = y
            while queue:
                current_x, current_y = queue.popleft()
                pixels.append((current_x, current_y))
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                for dx, dy in _OFFSETS4:
                    next_x = current_x + dx
                    next_y = current_y + dy
                    next_point = (next_x, next_y)
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and next_point not in visited
                        and grid[next_y][next_x] == color
                    ):
                        visited.add(next_point)
                        queue.append(next_point)
            bbox = (min_x, min_y, max_x, max_y)
            area = len(pixels)
            raw.append(
                VisualComponent(
                    color=color,
                    pixels=tuple(pixels),
                    bbox=bbox,
                    area=area,
                    rectangular=area
                    == ((max_x - min_x + 1) * (max_y - min_y + 1)),
                )
            )

    descriptors = Counter(
        (component.color, component.area, component.rectangular)
        for component in raw
    )
    return tuple(
        VisualComponent(
            color=component.color,
            pixels=component.pixels,
            bbox=component.bbox,
            area=component.area,
            rectangular=component.rectangular,
            twin_count=descriptors[
                (
                    component.color,
                    component.area,
                    component.rectangular,
                )
            ]
            - 1,
        )
        for component in raw
    )


def _edge_sides(
    component: VisualComponent,
    *,
    width: int,
    height: int,
    distance: int,
) -> tuple[str, ...]:
    min_x, min_y, max_x, max_y = component.bbox
    sides: list[str] = []
    if max_x < distance:
        sides.append("left")
    if min_x >= width - distance:
        sides.append("right")
    if max_y < distance:
        sides.append("top")
    if min_y >= height - distance:
        sides.append("bottom")
    return tuple(sides)


def status_mask(
    grid: Grid,
    *,
    edge_distance: int = 3,
    ratio_threshold: float = 5.0,
    twin_threshold: int = 3,
) -> frozenset[Point]:
    """Infer likely edge status indicators from rendered geometry only."""

    if not grid:
        return frozenset()
    height = len(grid)
    width = len(grid[0])
    components = connected_components(grid)
    mask: set[Point] = set()
    by_descriptor: dict[tuple[int, int, bool], list[VisualComponent]] = {}
    for component in components:
        by_descriptor.setdefault(
            (component.color, component.area, component.rectangular),
            [],
        ).append(component)

    for component in components:
        sides = _edge_sides(
            component,
            width=width,
            height=height,
            distance=edge_distance,
        )
        if not sides:
            continue
        horizontal_edge = any(side in {"top", "bottom"} for side in sides)
        vertical_edge = any(side in {"left", "right"} for side in sides)
        horizontal_bar = (
            horizontal_edge
            and component.width / max(1, component.height) >= ratio_threshold
        )
        vertical_bar = (
            vertical_edge
            and component.height / max(1, component.width) >= ratio_threshold
        )
        descriptor = (
            component.color,
            component.area,
            component.rectangular,
        )
        same_edge_twins = sum(
            bool(
                set(sides)
                & set(
                    _edge_sides(
                        other,
                        width=width,
                        height=height,
                        distance=edge_distance,
                    )
                )
            )
            for other in by_descriptor[descriptor]
        )
        repeated_edge_indicator = same_edge_twins >= twin_threshold
        if horizontal_bar or vertical_bar or repeated_edge_indicator:
            mask.update(component.pixels)
    return frozenset(mask)


def masked_grid(grid: Grid, mask: frozenset[Point]) -> Grid:
    if not grid:
        return ()
    return tuple(
        tuple(
            _MASK_VALUE if (x, y) in mask else value
            for x, value in enumerate(row)
        )
        for y, row in enumerate(grid)
    )


@dataclass(frozen=True, slots=True)
class VisualAction:
    """One observation-derived action candidate."""

    key: str
    action_id: int
    group: int
    x: int | None = None
    y: int | None = None
    evidence: tuple[str, ...] = ()

    def step(self) -> dict[str, int]:
        step = {"action_id": self.action_id}
        if self.action_id == 6:
            if self.x is None or self.y is None:
                raise ValueError("click candidate requires coordinates")
            step.update({"x": self.x, "y": self.y})
        return step


@dataclass(frozen=True, slots=True)
class VisualScene:
    signature: str
    grid_digest: str
    structural_digest: str
    width: int
    height: int
    status_mask: frozenset[Point]
    components: tuple[VisualComponent, ...]
    candidates: tuple[VisualAction, ...]


def _click_group(
    component: VisualComponent,
    *,
    background: tuple[int, int],
) -> int:
    compact = 2 <= component.width <= 32 and 2 <= component.height <= 32
    salient = component.color not in _NEUTRAL_COLORS
    is_background = (component.color, component.area) == background
    if salient and compact:
        return 0
    if compact and not is_background:
        return 1
    if salient and not is_background:
        return 2
    if not is_background:
        return 3
    return 4


def analyze_scene(
    grid: Grid,
    available_actions: tuple[int, ...],
    *,
    fixed_status_mask: frozenset[Point] | None = None,
    max_click_candidates: int = 512,
) -> VisualScene:
    """Build a deterministic action surface from a rendered grid."""

    if not grid:
        raise ValueError("rendered grid is required")
    height = len(grid)
    width = len(grid[0])
    mask = status_mask(grid) if fixed_status_mask is None else fixed_status_mask
    normalized = masked_grid(grid, mask)
    components = connected_components(normalized)
    component_counts = Counter(
        value for row in normalized for value in row
    )
    background_color, background_area = max(
        component_counts.items(),
        key=lambda item: (item[1], -item[0]),
    )
    candidates: list[VisualAction] = []
    if 6 in available_actions:
        click_components = sorted(
            components,
            key=lambda component: (
                _click_group(
                    component,
                    background=(background_color, background_area),
                ),
                component.bbox[1],
                component.bbox[0],
                component.color,
                component.area,
                component.bbox,
            ),
        )[:max_click_candidates]
        for component in click_components:
            x, y = component.click_point
            group = _click_group(
                component,
                background=(background_color, background_area),
            )
            key = "click:" + digest_object(
                {
                    "color": component.color,
                    "area": component.area,
                    "bbox": component.bbox,
                    "point": (x, y),
                }
            )[:20]
            candidates.append(
                VisualAction(
                    key=key,
                    action_id=6,
                    group=group,
                    x=x,
                    y=y,
                    evidence=(
                        "rendered-connected-component",
                        f"component-group:{group}",
                    ),
                )
            )
    for action_id in available_actions:
        if action_id == 6 or not 1 <= action_id <= 7:
            continue
        candidates.append(
            VisualAction(
                key=f"simple:{action_id}",
                action_id=action_id,
                group=0 if action_id <= 5 else 3,
                evidence=("available-action-surface",),
            )
        )
    ordered = tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.group,
                0 if candidate.action_id != 6 else 1,
                candidate.action_id,
                candidate.y if candidate.y is not None else -1,
                candidate.x if candidate.x is not None else -1,
                candidate.key,
            ),
        )
    )
    # State identity must cover the complete rendered evidence.  The inferred
    # status mask is only an object-extraction aid: dropping it from identity
    # aliases visibly different states and can erase a real phase signal.
    grid_digest = digest_object(grid)
    structural_digest = digest_object(normalized)
    return VisualScene(
        signature="visual-state:" + grid_digest[:24],
        grid_digest=grid_digest,
        structural_digest=structural_digest,
        width=width,
        height=height,
        status_mask=mask,
        components=components,
        candidates=ordered,
    )


@dataclass(slots=True)
class _Node:
    actions: dict[str, VisualAction]
    order: tuple[str, ...]
    outcomes: dict[str, Outcome] = field(default_factory=dict)
    targets: dict[str, str] = field(default_factory=dict)

    def untested(self) -> tuple[VisualAction, ...]:
        return tuple(
            self.actions[key] for key in self.order if key not in self.outcomes
        )


@dataclass(frozen=True, slots=True)
class ExplorerDecision:
    action: VisualAction | None
    reason: str
    memory_influenced: bool
    frontier_distance: int | None


@dataclass(slots=True)
class DeterministicVisualExplorer:
    """Learn a rendered transition graph and select the next safe frontier."""

    nodes: dict[str, _Node] = field(default_factory=dict)
    initial_signature: str = ""
    status_mask: frozenset[Point] = frozenset()
    previous_signature: str = ""
    previous_action_key: str = ""
    level_epoch: int = 0
    transition_count: int = 0
    failure_count: int = 0
    memory_read_count: int = 0

    def reset_level(self, scene: VisualScene) -> None:
        self.nodes.clear()
        self.initial_signature = scene.signature
        self.status_mask = scene.status_mask
        self.previous_signature = ""
        self.previous_action_key = ""
        self.level_epoch += 1
        self._ensure_node(scene)

    def _ensure_node(self, scene: VisualScene) -> _Node:
        node = self.nodes.get(scene.signature)
        action_map = {candidate.key: candidate for candidate in scene.candidates}
        order = tuple(candidate.key for candidate in scene.candidates)
        if node is None:
            node = _Node(actions=action_map, order=order)
            self.nodes[scene.signature] = node
            return node
        for key, action in action_map.items():
            node.actions.setdefault(key, action)
        node.order = tuple(
            dict.fromkeys((*node.order, *order))
        )
        return node

    def observe(
        self,
        scene: VisualScene,
        *,
        terminal_state: str,
        level_progress: bool,
    ) -> None:
        """Commit the pending action's visible outcome to passive state."""

        if level_progress:
            self.reset_level(scene)
            return
        if not self.initial_signature:
            self.reset_level(scene)
            return

        self._ensure_node(scene)
        if not self.previous_signature or not self.previous_action_key:
            return
        source = self.nodes.get(self.previous_signature)
        if source is None:
            raise ValueError("previous visual state missing")
        if terminal_state == "GAME_OVER":
            source.outcomes[self.previous_action_key] = "HAZARD"
            source.targets.pop(self.previous_action_key, None)
            self.failure_count += 1
        elif scene.signature == self.previous_signature:
            source.outcomes[self.previous_action_key] = "NO_CHANGE"
            source.targets.pop(self.previous_action_key, None)
        else:
            source.outcomes[self.previous_action_key] = "TRANSITION"
            source.targets[self.previous_action_key] = scene.signature
            self.transition_count += 1
        self.previous_signature = ""
        self.previous_action_key = ""

    def record_hazard(
        self,
        source_signature: str,
        action: VisualAction,
    ) -> None:
        """Retain a signed failure even when the action result was rejected."""

        if not source_signature:
            raise ValueError("hazard source signature is required")
        node = self.nodes.get(source_signature)
        if node is None:
            node = _Node(
                actions={action.key: action},
                order=(action.key,),
            )
            self.nodes[source_signature] = node
        else:
            node.actions.setdefault(action.key, action)
            node.order = tuple(dict.fromkeys((*node.order, action.key)))
        if node.outcomes.get(action.key) != "HAZARD":
            self.failure_count += 1
        node.outcomes[action.key] = "HAZARD"
        node.targets.pop(action.key, None)
        if not self.initial_signature:
            self.initial_signature = source_signature
        self.previous_signature = ""
        self.previous_action_key = ""

    def known_outcome(
        self,
        source_signature: str,
        action_key: str,
    ) -> Outcome | None:
        node = self.nodes.get(source_signature)
        return None if node is None else node.outcomes.get(action_key)

    def stage_action(
        self,
        scene: VisualScene,
        action: VisualAction,
    ) -> bool:
        """Record a semantic proposal as pending without selecting authority."""

        node = self._ensure_node(scene)
        if node.outcomes.get(action.key) in {"NO_CHANGE", "HAZARD"}:
            return False
        node.actions.setdefault(action.key, action)
        node.order = tuple(dict.fromkeys((*node.order, action.key)))
        self.previous_signature = scene.signature
        self.previous_action_key = action.key
        return True

    def _frontier_action(
        self,
        signature: str,
    ) -> tuple[VisualAction | None, int | None]:
        node = self.nodes[signature]
        untested = node.untested()
        if untested:
            return untested[0], 0

        queue: deque[tuple[str, int]] = deque(((signature, 0),))
        visited = {signature}
        first_action: dict[str, VisualAction] = {}
        while queue:
            current, distance = queue.popleft()
            current_node = self.nodes[current]
            if distance > 0 and current_node.untested():
                return first_action[current], distance
            for key in current_node.order:
                if current_node.outcomes.get(key) != "TRANSITION":
                    continue
                target = current_node.targets.get(key)
                action = current_node.actions.get(key)
                if (
                    target is None
                    or action is None
                    or target not in self.nodes
                    or target in visited
                ):
                    continue
                visited.add(target)
                first_action[target] = (
                    action if distance == 0 else first_action[current]
                )
                queue.append((target, distance + 1))
        return None, None

    def reset_frontier_available(self, current_signature: str) -> bool:
        """Return whether RESET can expose a disconnected untested frontier."""

        if (
            not self.initial_signature
            or self.initial_signature not in self.nodes
            or current_signature == self.initial_signature
        ):
            return False
        action, _distance = self._frontier_action(self.initial_signature)
        return action is not None

    def decide(self, scene: VisualScene) -> ExplorerDecision:
        """Choose one candidate; prior observations change future selection."""

        node = self._ensure_node(scene)
        del node
        action, distance = self._frontier_action(scene.signature)
        memory_influenced = bool(
            self.transition_count
            or self.failure_count
            or any(item.outcomes for item in self.nodes.values())
        )
        if memory_influenced:
            self.memory_read_count += 1
        if action is None:
            reset_frontier = self.reset_frontier_available(scene.signature)
            return ExplorerDecision(
                action=None,
                reason=(
                    "VISUAL_BRANCH_EXHAUSTED_RESET_REQUIRED"
                    if reset_frontier
                    else "VISUAL_FRONTIER_EXHAUSTED"
                ),
                memory_influenced=memory_influenced,
                frontier_distance=None,
            )
        self.previous_signature = scene.signature
        self.previous_action_key = action.key
        return ExplorerDecision(
            action=action,
            reason=(
                "VISUAL_UNTESTED_CANDIDATE"
                if distance == 0
                else "VISUAL_TRANSITION_GRAPH_ROUTE"
            ),
            memory_influenced=memory_influenced,
            frontier_distance=distance,
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": "arc3-visual-explorer-v1",
            "initial_signature": self.initial_signature,
            "status_mask": [list(point) for point in sorted(self.status_mask)],
            "previous_signature": self.previous_signature,
            "previous_action_key": self.previous_action_key,
            "level_epoch": self.level_epoch,
            "transition_count": self.transition_count,
            "failure_count": self.failure_count,
            "memory_read_count": self.memory_read_count,
            "nodes": {
                signature: {
                    "order": list(node.order),
                    "actions": {
                        key: {
                            "key": action.key,
                            "action_id": action.action_id,
                            "group": action.group,
                            "x": action.x,
                            "y": action.y,
                            "evidence": list(action.evidence),
                        }
                        for key, action in sorted(node.actions.items())
                    },
                    "outcomes": dict(sorted(node.outcomes.items())),
                    "targets": dict(sorted(node.targets.items())),
                }
                for signature, node in sorted(self.nodes.items())
            },
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "VISUAL_EXPLORER_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        value: Mapping[str, object],
    ) -> DeterministicVisualExplorer:
        if value.get("format") != "arc3-visual-explorer-v1":
            raise ValueError("visual explorer payload format invalid")
        mask_value = value.get("status_mask", ())
        if not isinstance(mask_value, Sequence) or isinstance(
            mask_value, (str, bytes, bytearray)
        ):
            raise ValueError("visual explorer status mask invalid")
        mask: set[Point] = set()
        for item in mask_value:
            if (
                not isinstance(item, Sequence)
                or isinstance(item, (str, bytes, bytearray))
                or len(item) != 2
            ):
                raise ValueError("visual explorer status point invalid")
            mask.add(
                (
                    _payload_int(item[0], "status_mask.x"),
                    _payload_int(item[1], "status_mask.y"),
                )
            )

        explorer = cls(
            initial_signature=str(value.get("initial_signature", "")),
            status_mask=frozenset(mask),
            previous_signature=str(value.get("previous_signature", "")),
            previous_action_key=str(value.get("previous_action_key", "")),
            level_epoch=_payload_int(
                value.get("level_epoch", 0),
                "level_epoch",
            ),
            transition_count=_payload_int(
                value.get("transition_count", 0),
                "transition_count",
            ),
            failure_count=_payload_int(
                value.get("failure_count", 0),
                "failure_count",
            ),
            memory_read_count=_payload_int(
                value.get("memory_read_count", 0),
                "memory_read_count",
            ),
        )
        raw_nodes = value.get("nodes", {})
        if not isinstance(raw_nodes, Mapping):
            raise ValueError("visual explorer nodes invalid")
        for raw_signature, raw_node in raw_nodes.items():
            if not isinstance(raw_node, Mapping):
                raise ValueError("visual explorer node invalid")
            raw_actions = raw_node.get("actions", {})
            if not isinstance(raw_actions, Mapping):
                raise ValueError("visual explorer actions invalid")
            actions: dict[str, VisualAction] = {}
            for raw_key, raw_action in raw_actions.items():
                if not isinstance(raw_action, Mapping):
                    raise ValueError("visual explorer action invalid")
                evidence = raw_action.get("evidence", ())
                if not isinstance(evidence, Sequence) or isinstance(
                    evidence, (str, bytes, bytearray)
                ):
                    raise ValueError("visual explorer action evidence invalid")
                key = str(raw_key)
                actions[key] = VisualAction(
                    key=str(raw_action.get("key", key)),
                    action_id=_payload_int(
                        raw_action.get("action_id"),
                        "action_id",
                    ),
                    group=_payload_int(
                        raw_action.get("group"),
                        "group",
                    ),
                    x=(
                        None
                        if raw_action.get("x") is None
                        else _payload_int(raw_action.get("x"), "x")
                    ),
                    y=(
                        None
                        if raw_action.get("y") is None
                        else _payload_int(raw_action.get("y"), "y")
                    ),
                    evidence=tuple(str(item) for item in evidence),
                )
            raw_order = raw_node.get("order", ())
            raw_outcomes = raw_node.get("outcomes", {})
            raw_targets = raw_node.get("targets", {})
            if (
                not isinstance(raw_order, Sequence)
                or isinstance(raw_order, (str, bytes, bytearray))
                or not isinstance(raw_outcomes, Mapping)
                or not isinstance(raw_targets, Mapping)
            ):
                raise ValueError("visual explorer node fields invalid")
            outcomes: dict[str, Outcome] = {}
            for key, outcome in raw_outcomes.items():
                normalized = str(outcome)
                if normalized not in {"NO_CHANGE", "TRANSITION", "HAZARD"}:
                    raise ValueError("visual explorer outcome invalid")
                outcomes[str(key)] = normalized  # type: ignore[assignment]
            explorer.nodes[str(raw_signature)] = _Node(
                actions=actions,
                order=tuple(str(item) for item in raw_order),
                outcomes=outcomes,
                targets={
                    str(key): str(target)
                    for key, target in raw_targets.items()
                },
            )
        return explorer

    @property
    def digest(self) -> str:
        return digest_object(self.to_payload())


__all__ = [
    "DeterministicVisualExplorer",
    "ExplorerDecision",
    "Grid",
    "Outcome",
    "Point",
    "VisualAction",
    "VisualComponent",
    "VisualScene",
    "analyze_scene",
    "connected_components",
    "last_rendered_grid",
    "masked_grid",
    "normalized_grid",
    "status_mask",
]
