"""Identity-free semantic operators and their passive planner state.

Operators are selected only from rendered structure and the available action
surface.  They return observation-derived action plans; they do not judge,
write memory, emit, inspect source state, or accept task identity.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object, forbidden_runtime_paths
from .visual_explorer import Grid, Point, VisualAction

SEMANTIC_PLANNER_FORMAT = "arc3-semantic-planner-v1"
RELATION_TOGGLE_OPERATOR = "relation-constrained-toggle-gf2-v1"


def _payload_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class SemanticPlannerDecision:
    action: VisualAction | None
    reason: str
    memory_influenced: bool
    plan_signature: str = ""


@dataclass(frozen=True, slots=True)
class _ToggleCell:
    x: int
    y: int
    color: int
    mask: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class _ToggleConstraint:
    x: int
    y: int
    target: int
    pattern: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class _ToggleParameters:
    tile_size: int
    neighbor_stride: int
    mask_color: int
    equality_relation_color: int
    excluded_colors: frozenset[int]
    relation_colors: frozenset[int]
    status_scan_width: int
    status_scan_height: int
    max_camera_scale: int
    minimum_cell_count: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _ToggleParameters | None:
        if (
            instruction.operator_id != RELATION_TOGGLE_OPERATOR
            or instruction.action_id != 6
        ):
            return None
        raw = instruction.parameters()

        def integer(name: str) -> int | None:
            value = raw.get(name)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else None
            )

        def colors(name: str) -> frozenset[int] | None:
            value = raw.get(name)
            if not isinstance(value, Sequence) or isinstance(
                value,
                (str, bytes, bytearray),
            ):
                return None
            converted = frozenset(
                item
                for item in value
                if isinstance(item, int) and not isinstance(item, bool)
            )
            return converted if len(converted) == len(value) else None

        tile_size = integer("tile_size")
        neighbor_stride = integer("neighbor_stride")
        mask_color = integer("mask_color")
        equality_relation_color = integer("equality_relation_color")
        excluded_colors = colors("excluded_colors")
        relation_colors = colors("relation_colors")
        status_scan_width = integer("status_scan_width")
        status_scan_height = integer("status_scan_height")
        max_camera_scale = integer("max_camera_scale")
        minimum_cell_count = integer("minimum_cell_count")
        if (
            tile_size != 3
            or neighbor_stride is None
            or neighbor_stride < tile_size
            or mask_color is None
            or equality_relation_color is None
            or excluded_colors is None
            or relation_colors is None
            or equality_relation_color not in relation_colors
            or status_scan_width is None
            or status_scan_width < 1
            or status_scan_height is None
            or status_scan_height < 1
            or max_camera_scale is None
            or not 1 <= max_camera_scale <= 8
            or minimum_cell_count is None
            or minimum_cell_count < 2
        ):
            return None
        return cls(
            tile_size=tile_size,
            neighbor_stride=neighbor_stride,
            mask_color=mask_color,
            equality_relation_color=equality_relation_color,
            excluded_colors=excluded_colors,
            relation_colors=relation_colors,
            status_scan_width=status_scan_width,
            status_scan_height=status_scan_height,
            max_camera_scale=max_camera_scale,
            minimum_cell_count=minimum_cell_count,
        )


def _uniform_block_scale(
    grid: Grid,
    *,
    max_camera_scale: int,
) -> tuple[Grid, int, int]:
    """Infer camera pixel replication without task or layout identity."""

    if not grid:
        return (), 1, 1
    height = len(grid)
    width = len(grid[0])
    for scale in range(
        min(max_camera_scale, height, width),
        1,
        -1,
    ):
        if height % scale or width % scale:
            continue
        blocks = tuple(
            tuple(
                grid[y + dy][x + dx]
                for dy in range(scale)
                for dx in range(scale)
            )
            for y in range(0, height, scale)
            for x in range(0, width, scale)
        )
        uniform_ratio = sum(
            len(set(block)) == 1 for block in blocks
        ) / len(blocks)
        if uniform_ratio >= 0.95:
            reduced = tuple(
                tuple(
                    Counter(
                        grid[y + dy][x + dx]
                        for dy in range(scale)
                        for dx in range(scale)
                    ).most_common(1)[0][0]
                    for x in range(0, width, scale)
                )
                for y in range(0, height, scale)
            )
            return reduced, scale, scale
    return grid, 1, 1


def _toggle_status_colors(
    grid: Grid,
    parameters: _ToggleParameters,
) -> list[int]:
    if not grid:
        return []
    colors: list[int] = []
    seen: set[int] = set()
    start_x = max(0, len(grid[0]) - parameters.status_scan_width)
    for y in range(min(parameters.status_scan_height, len(grid))):
        for x in range(start_x, len(grid[0])):
            color = grid[y][x]
            if (
                color in parameters.excluded_colors
                or color == parameters.mask_color
                or color in seen
            ):
                continue
            seen.add(color)
            colors.append(color)
    return colors


def _parse_toggle_grid(
    grid: Grid,
    parameters: _ToggleParameters,
) -> tuple[
    tuple[_ToggleCell, ...],
    tuple[_ToggleConstraint, ...],
    tuple[int, ...],
]:
    if not grid:
        return (), (), ()
    height = len(grid)
    width = len(grid[0])
    tile_size = parameters.tile_size
    half = tile_size // 2
    minimum_visible = (tile_size * tile_size) // 2 + 1
    candidates: list[tuple[int, int, int, tuple[Point, ...], int]] = []
    for y in range(0, height - tile_size + 1):
        for x in range(0, width - tile_size + 1):
            values = tuple(
                grid[y + dy][x + dx]
                for dy in range(tile_size)
                for dx in range(tile_size)
            )
            visible = tuple(
                value
                for value in values
                if value != parameters.mask_color
            )
            if (
                len(visible) < minimum_visible
                or len(set(visible)) != 1
            ):
                continue
            color = visible[0]
            if color in parameters.excluded_colors:
                continue
            if any(
                value not in (color, parameters.mask_color)
                for value in values
            ):
                continue
            visible_mask = tuple(
                (dx - half, dy - half)
                for dy in range(tile_size)
                for dx in range(tile_size)
                if grid[y + dy][x + dx] == parameters.mask_color
            )
            effect_mask = tuple(sorted({(0, 0), *visible_mask}))
            candidates.append(
                (x, y, color, effect_mask, len(visible))
            )

    occupied: set[Point] = set()
    cells: list[_ToggleCell] = []
    for x, y, color, effect_mask, score in sorted(
        candidates,
        key=lambda item: (-item[4], item[1], item[0]),
    ):
        points = {
            (x + dx, y + dy)
            for dy in range(tile_size)
            for dx in range(tile_size)
        }
        if points & occupied:
            continue
        occupied.update(points)
        cells.append(
            _ToggleCell(
                x=x,
                y=y,
                color=color,
                mask=effect_mask,
            )
        )
    cells.sort(key=lambda item: (item.y, item.x))

    cell_positions = {(cell.x, cell.y) for cell in cells}
    constraints: list[_ToggleConstraint] = []
    seen_constraints: set[Point] = set()
    for y in range(0, height - tile_size + 1):
        for x in range(0, width - tile_size + 1):
            pattern = tuple(
                tuple(
                    grid[y + dy][x + dx]
                    for dx in range(tile_size)
                )
                for dy in range(tile_size)
            )
            center = pattern[half][half]
            if (
                center in parameters.excluded_colors
                or center == parameters.mask_color
            ):
                continue
            surrounds = tuple(
                pattern[dy][dx]
                for dy in range(tile_size)
                for dx in range(tile_size)
                if (dx, dy) != (half, half)
            )
            if any(
                value not in parameters.relation_colors
                for value in surrounds
            ):
                continue
            has_neighbor = any(
                (
                    x + dx * parameters.neighbor_stride,
                    y + dy * parameters.neighbor_stride,
                )
                in cell_positions
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if (dx, dy) != (0, 0)
            )
            if not has_neighbor or (x, y) in seen_constraints:
                continue
            seen_constraints.add((x, y))
            constraints.append(
                _ToggleConstraint(
                    x=x,
                    y=y,
                    target=center,
                    pattern=pattern,
                )
            )
    constraints.sort(key=lambda item: (item.y, item.x))

    colors = _toggle_status_colors(grid, parameters)
    for color in sorted(
        {cell.color for cell in cells}
        | {constraint.target for constraint in constraints}
    ):
        if color not in colors:
            colors.append(color)
    return tuple(cells), tuple(constraints), tuple(colors)


def _toggle_cell_options(
    cells: tuple[_ToggleCell, ...],
    constraints: tuple[_ToggleConstraint, ...],
    colors: tuple[int, ...],
    parameters: _ToggleParameters,
) -> tuple[frozenset[int], ...]:
    cell_index = {
        (cell.x, cell.y): index for index, cell in enumerate(cells)
    }
    options = [set(colors) for _ in cells]
    offsets = range(
        -(parameters.tile_size // 2),
        (parameters.tile_size // 2) + 1,
    )
    for constraint in constraints:
        for pattern_y, dy in enumerate(offsets):
            for pattern_x, dx in enumerate(offsets):
                if (dx, dy) == (0, 0):
                    continue
                position = (
                    constraint.x + dx * parameters.neighbor_stride,
                    constraint.y + dy * parameters.neighbor_stride,
                )
                index = cell_index.get(position)
                if index is None:
                    continue
                if (
                    constraint.pattern[pattern_y][pattern_x]
                    == parameters.equality_relation_color
                ):
                    options[index].intersection_update({constraint.target})
                else:
                    options[index].discard(constraint.target)
    return tuple(frozenset(option) for option in options)


def _toggle_effects(
    cells: tuple[_ToggleCell, ...],
    parameters: _ToggleParameters,
) -> tuple[tuple[int, ...], ...]:
    cell_index = {
        (cell.x, cell.y): index for index, cell in enumerate(cells)
    }
    effects: list[tuple[int, ...]] = []
    for cell in cells:
        affected = {
            cell_index[position]
            for dx, dy in cell.mask
            if (
                position := (
                    cell.x + dx * parameters.neighbor_stride,
                    cell.y + dy * parameters.neighbor_stride,
                )
            )
            in cell_index
        }
        if not affected:
            affected.add(cell_index[(cell.x, cell.y)])
        effects.append(tuple(sorted(affected)))
    return tuple(effects)


def _gf2_solve(
    matrix: list[list[int]],
    target: list[int],
) -> list[int] | None:
    if not matrix:
        return []
    row_count = len(matrix)
    column_count = len(matrix[0])
    rows = [
        matrix[index][:] + [target[index] & 1]
        for index in range(row_count)
    ]
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        selected = next(
            (
                row
                for row in range(pivot_row, row_count)
                if rows[row][column] & 1
            ),
            None,
        )
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        for row in range(row_count):
            if row != pivot_row and rows[row][column] & 1:
                rows[row] = [
                    left ^ right
                    for left, right in zip(
                        rows[row],
                        rows[pivot_row],
                        strict=True,
                    )
                ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    if any(
        not any(row[:column_count]) and row[column_count] & 1
        for row in rows
    ):
        return None
    solution = [0] * column_count
    for row, column in enumerate(pivots):
        solution[column] = rows[row][column_count] & 1
    return solution


def _first_allowed_color(
    allowed: frozenset[int],
    colors: tuple[int, ...],
) -> int:
    return next(
        (color for color in colors if color in allowed),
        min(allowed),
    )


def _binary_toggle_plan(
    cells: tuple[_ToggleCell, ...],
    constraints: tuple[_ToggleConstraint, ...],
    colors: tuple[int, ...],
    parameters: _ToggleParameters,
) -> tuple[Point, ...]:
    options = _toggle_cell_options(
        cells,
        constraints,
        colors,
        parameters,
    )
    if any(not allowed for allowed in options):
        return ()
    desired = tuple(
        cell.color
        if cell.color in allowed
        else _first_allowed_color(allowed, colors)
        for cell, allowed in zip(cells, options, strict=True)
    )
    base = colors[0]
    current_bits = [0 if cell.color == base else 1 for cell in cells]
    desired_bits = [0 if color == base else 1 for color in desired]
    effects = _toggle_effects(cells, parameters)
    matrix: list[list[int]] = []
    target: list[int] = []
    for cell_index in range(len(cells)):
        matrix.append(
            [
                int(cell_index in affected)
                for affected in effects
            ]
        )
        target.append(current_bits[cell_index] ^ desired_bits[cell_index])
    solution = _gf2_solve(matrix, target)
    if solution is None:
        return ()
    return tuple(
        (cells[index].x, cells[index].y)
        for index, enabled in enumerate(solution)
        if enabled
    )


def _ternary_toggle_plan(
    cells: tuple[_ToggleCell, ...],
    constraints: tuple[_ToggleConstraint, ...],
    colors: tuple[int, ...],
    parameters: _ToggleParameters,
) -> tuple[Point, ...]:
    if any(cell.mask != ((0, 0),) for cell in cells):
        return ()
    options = _toggle_cell_options(
        cells,
        constraints,
        colors,
        parameters,
    )
    if any(not allowed for allowed in options):
        return ()
    order = {color: index for index, color in enumerate(colors)}
    if len(order) != 3:
        return ()
    plan: list[Point] = []
    for cell, allowed in zip(cells, options, strict=True):
        if cell.color not in order:
            return ()
        click_count = min(
            (order[color] - order[cell.color]) % 3
            for color in allowed
        )
        plan.extend([(cell.x, cell.y)] * click_count)
    return tuple(plan)


def relation_toggle_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Compile a full rendered relation-grid plan, or reject applicability."""

    parameters = _ToggleParameters.from_instruction(instruction)
    if parameters is None or instruction.action_id not in available_actions:
        return ()
    reduced, scale_x, scale_y = _uniform_block_scale(
        grid,
        max_camera_scale=parameters.max_camera_scale,
    )
    cells, constraints, colors = _parse_toggle_grid(reduced, parameters)
    if (
        len(cells) < parameters.minimum_cell_count
        or not constraints
        or len(colors) not in {2, 3}
    ):
        return ()
    logical_plan = (
        _binary_toggle_plan(cells, constraints, colors, parameters)
        if len(colors) == 2
        else _ternary_toggle_plan(
            cells,
            constraints,
            colors,
            parameters,
        )
    )
    actions: list[VisualAction] = []
    for logical_x, logical_y in logical_plan:
        center_offset = parameters.tile_size // 2
        x = min(63, (logical_x + center_offset) * scale_x)
        y = min(63, (logical_y + center_offset) * scale_y)
        actions.append(
            VisualAction(
                key="semantic-toggle:"
                + digest_object(
                    {
                        "operator": RELATION_TOGGLE_OPERATOR,
                        "point": (x, y),
                    }
                )[:20],
                action_id=instruction.action_id,
                group=0,
                x=x,
                y=y,
                evidence=(
                    RELATION_TOGGLE_OPERATOR,
                    "rendered-relation-grid",
                    "dynamic-gf2-plan",
                    *instruction.provenance,
                ),
            )
        )
    return tuple(actions)


@dataclass(slots=True)
class SemanticPlannerState:
    """Serializable queue state owned by passive M, not by the operator."""

    queue: list[VisualAction] = field(default_factory=list)
    active_operator: str = ""
    active_instruction_digest: str = ""
    active_plan_signature: str = ""
    source_signature: str = ""
    blocked_plan_signatures: set[str] = field(default_factory=set)
    plan_count: int = 0
    memory_read_count: int = 0

    def reset_after_progress(self) -> None:
        self.queue.clear()
        self.active_operator = ""
        self.active_instruction_digest = ""
        self.active_plan_signature = ""
        self.source_signature = ""

    def invalidate_active_plan(self) -> None:
        if self.active_plan_signature:
            self.blocked_plan_signatures.add(self.active_plan_signature)
        self.reset_after_progress()

    def decide(
        self,
        grid: Grid,
        available_actions: tuple[int, ...],
        operator_instructions: tuple[SemanticOperatorInstruction, ...],
        *,
        source_signature: str,
    ) -> SemanticPlannerDecision:
        if self.queue:
            current_instruction = next(
                (
                    instruction
                    for instruction in operator_instructions
                    if instruction.operator_id == self.active_operator
                ),
                None,
            )
            if (
                current_instruction is None
                or digest_object(current_instruction)
                != self.active_instruction_digest
            ):
                self.invalidate_active_plan()
            else:
                action = self.queue.pop(0)
                if action.action_id not in available_actions:
                    self.invalidate_active_plan()
                else:
                    self.memory_read_count += 1
                    return SemanticPlannerDecision(
                        action=action,
                        reason=self.active_operator,
                        memory_influenced=True,
                        plan_signature=self.active_plan_signature,
                    )

        for instruction in sorted(
            operator_instructions,
            key=lambda item: item.operator_id,
        ):
            if instruction.operator_id != RELATION_TOGGLE_OPERATOR:
                continue
            plan = relation_toggle_plan(
                grid,
                available_actions,
                instruction,
            )
            if not plan:
                continue
            operator_id = instruction.operator_id
            plan_signature = "semantic-plan:" + digest_object(
                {
                    "operator": operator_id,
                    "instruction": instruction,
                    "source": source_signature,
                    "steps": tuple(action.step() for action in plan),
                }
            )
            if plan_signature in self.blocked_plan_signatures:
                continue
            self.active_operator = operator_id
            self.active_instruction_digest = digest_object(instruction)
            self.active_plan_signature = plan_signature
            self.source_signature = source_signature
            self.plan_count += 1
            action = plan[0]
            self.queue = list(plan[1:])
            return SemanticPlannerDecision(
                action=action,
                reason=operator_id,
                memory_influenced=False,
                plan_signature=plan_signature,
            )
        return SemanticPlannerDecision(
            action=None,
            reason="NO_SEMANTIC_OPERATOR_APPLICABLE",
            memory_influenced=bool(
                self.queue
                or self.blocked_plan_signatures
                or self.memory_read_count
            ),
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": SEMANTIC_PLANNER_FORMAT,
            "queue": [
                {
                    "key": action.key,
                    "action_id": action.action_id,
                    "group": action.group,
                    "x": action.x,
                    "y": action.y,
                    "evidence": list(action.evidence),
                }
                for action in self.queue
            ],
            "active_operator": self.active_operator,
            "active_instruction_digest": self.active_instruction_digest,
            "active_plan_signature": self.active_plan_signature,
            "source_signature": self.source_signature,
            "blocked_plan_signatures": sorted(
                self.blocked_plan_signatures
            )[-64:],
            "plan_count": self.plan_count,
            "memory_read_count": self.memory_read_count,
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "SEMANTIC_PLANNER_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        value: Mapping[str, object],
    ) -> SemanticPlannerState:
        if value.get("format") != SEMANTIC_PLANNER_FORMAT:
            raise ValueError("semantic planner payload format invalid")
        raw_queue = value.get("queue", ())
        raw_blocked = value.get("blocked_plan_signatures", ())
        if (
            not isinstance(raw_queue, Sequence)
            or isinstance(raw_queue, (str, bytes, bytearray))
            or not isinstance(raw_blocked, Sequence)
            or isinstance(raw_blocked, (str, bytes, bytearray))
        ):
            raise ValueError("semantic planner sequence invalid")
        queue: list[VisualAction] = []
        for raw_action in raw_queue:
            if not isinstance(raw_action, Mapping):
                raise ValueError("semantic planner action invalid")
            raw_evidence = raw_action.get("evidence", ())
            if (
                not isinstance(raw_evidence, Sequence)
                or isinstance(raw_evidence, (str, bytes, bytearray))
            ):
                raise ValueError("semantic planner evidence invalid")
            queue.append(
                VisualAction(
                    key=str(raw_action.get("key", "")),
                    action_id=_payload_int(
                        raw_action.get("action_id"),
                        "action_id",
                    ),
                    group=_payload_int(raw_action.get("group"), "group"),
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
                    evidence=tuple(str(item) for item in raw_evidence),
                )
            )
        return cls(
            queue=queue,
            active_operator=str(value.get("active_operator", "")),
            active_instruction_digest=str(
                value.get("active_instruction_digest", "")
            ),
            active_plan_signature=str(
                value.get("active_plan_signature", "")
            ),
            source_signature=str(value.get("source_signature", "")),
            blocked_plan_signatures={
                str(item) for item in raw_blocked if str(item)
            },
            plan_count=_payload_int(value.get("plan_count", 0), "plan_count"),
            memory_read_count=_payload_int(
                value.get("memory_read_count", 0),
                "memory_read_count",
            ),
        )

    @property
    def digest(self) -> str:
        return digest_object(self.to_payload())


__all__ = [
    "RELATION_TOGGLE_OPERATOR",
    "SEMANTIC_PLANNER_FORMAT",
    "SemanticPlannerDecision",
    "SemanticPlannerState",
    "relation_toggle_plan",
]
