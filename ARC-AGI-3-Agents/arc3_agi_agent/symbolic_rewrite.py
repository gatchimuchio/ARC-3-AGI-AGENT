"""Rendered symbolic-rewrite operator with passive, serializable learning.

The detector consumes only the current rendered grid and a compiled,
identity-free instruction.  It recognizes bordered symbol tiles, visible
rewrite connectors, source/output rows, and a rendered selector.  Fixed-rule
surfaces are solved directly.  Editable-rule surfaces are learned by cycling
each visible selector node once, retaining the observed alternatives in
passive state, and solving the resulting bounded rewrite constraints.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object, forbidden_runtime_paths
from .visual_explorer import Grid, Point, VisualAction

SYMBOLIC_REWRITE_OPERATOR = "rendered-symbolic-rewrite-v1"
SYMBOLIC_REWRITE_STATE_FORMAT = "arc3-symbolic-rewrite-state-v2"


def _payload_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class _RewriteParameters:
    tile_size: int
    symbol_color: int
    connector_color: int
    selector_color: int
    cycle_size: int
    decrement_action: int
    increment_action: int
    previous_action: int
    next_action: int
    minimum_border_count: int
    maximum_rewrite_depth: int
    maximum_intermediate_candidates: int
    maximum_output_tokens: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _RewriteParameters | None:
        if instruction.operator_id != SYMBOLIC_REWRITE_OPERATOR:
            return None
        raw = instruction.parameters()

        def integer(name: str) -> int | None:
            value = raw.get(name)
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else None
            )

        values = {
            name: integer(name)
            for name in (
                "tile_size",
                "symbol_color",
                "connector_color",
                "selector_color",
                "cycle_size",
                "decrement_action",
                "increment_action",
                "previous_action",
                "next_action",
                "minimum_border_count",
                "maximum_rewrite_depth",
                "maximum_intermediate_candidates",
                "maximum_output_tokens",
            )
        }
        if any(value is None for value in values.values()):
            return None

        def required(name: str) -> int:
            value = values[name]
            if value is None:
                raise AssertionError("validated rewrite parameter missing")
            return value

        parameters = cls(
            tile_size=required("tile_size"),
            symbol_color=required("symbol_color"),
            connector_color=required("connector_color"),
            selector_color=required("selector_color"),
            cycle_size=required("cycle_size"),
            decrement_action=required("decrement_action"),
            increment_action=required("increment_action"),
            previous_action=required("previous_action"),
            next_action=required("next_action"),
            minimum_border_count=required("minimum_border_count"),
            maximum_rewrite_depth=required("maximum_rewrite_depth"),
            maximum_intermediate_candidates=required(
                "maximum_intermediate_candidates"
            ),
            maximum_output_tokens=required("maximum_output_tokens"),
        )
        actions = {
            parameters.decrement_action,
            parameters.increment_action,
            parameters.previous_action,
            parameters.next_action,
        }
        border_cells = 4 * parameters.tile_size - 4
        if (
            not 5 <= parameters.tile_size <= 11
            or not 0 <= parameters.symbol_color <= 15
            or not 0 <= parameters.connector_color <= 15
            or not 0 <= parameters.selector_color <= 15
            or len(
                {
                    parameters.symbol_color,
                    parameters.connector_color,
                    parameters.selector_color,
                }
            )
            != 3
            or not 2 <= parameters.cycle_size <= 16
            or len(actions) != 4
            or any(not 1 <= action <= 7 for action in actions)
            or not parameters.tile_size
            <= parameters.minimum_border_count
            <= border_cells
            or not 1 <= parameters.maximum_rewrite_depth <= 3
            or not 64
            <= parameters.maximum_intermediate_candidates
            <= 16_384
            or not 4 <= parameters.maximum_output_tokens <= 128
        ):
            return None
        return parameters


@dataclass(frozen=True, slots=True)
class _RewriteTile:
    x: int
    y: int
    background: int
    pattern: str
    score: int

    @property
    def label(self) -> str:
        return f"{self.background}:{self.pattern}"


@dataclass(frozen=True, slots=True)
class _RewriteRow:
    y: int
    tiles: tuple[_RewriteTile, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(tile.label for tile in self.tiles)


@dataclass(frozen=True, slots=True)
class _RewriteNode:
    key: str
    labels: tuple[str, ...]
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _RewriteRule:
    index: int
    left_key: str
    right_key: str


@dataclass(frozen=True, slots=True)
class _RewriteSurface:
    signature: str
    mode: str
    rules: tuple[_RewriteRule, ...]
    nodes: tuple[_RewriteNode, ...]
    source: tuple[str, ...]
    output: tuple[str, ...]
    selected_index: int
    fixed_target: tuple[str, ...]
    fixed_depth: int
    parameters: _RewriteParameters

    @property
    def node_order(self) -> tuple[str, ...]:
        return tuple(node.key for node in self.nodes)

    def node(self, key: str) -> _RewriteNode:
        return next(node for node in self.nodes if node.key == key)


@dataclass(frozen=True, slots=True)
class SymbolicRewriteDecision:
    action: VisualAction | None
    reason: str
    memory_influenced: bool


def _rotate_clockwise(rows: tuple[str, ...]) -> tuple[str, ...]:
    size = len(rows)
    return tuple(
        "".join(rows[size - 1 - y][x] for y in range(size))
        for x in range(size)
    )


def _canonical_pattern(pattern: str) -> str:
    rows = tuple(pattern.split("/"))
    rotations: list[str] = []
    current = rows
    for _ in range(4):
        rotations.append("/".join(current))
        current = _rotate_clockwise(current)
    return min(rotations)


def _raw_tile_candidates(
    grid: Grid,
    parameters: _RewriteParameters,
) -> tuple[_RewriteTile, ...]:
    size = parameters.tile_size
    height = len(grid)
    width = len(grid[0]) if height else 0
    candidates: list[_RewriteTile] = []
    for y in range(0, height - size + 1):
        for x in range(0, width - size + 1):
            border = (
                tuple(grid[y][xx] for xx in range(x, x + size))
                + tuple(
                    grid[y + size - 1][xx]
                    for xx in range(x, x + size)
                )
                + tuple(
                    grid[yy][x] for yy in range(y + 1, y + size - 1)
                )
                + tuple(
                    grid[yy][x + size - 1]
                    for yy in range(y + 1, y + size - 1)
                )
            )
            background, border_count = Counter(border).most_common(1)[0]
            if (
                background
                in {
                    parameters.symbol_color,
                    parameters.connector_color,
                    parameters.selector_color,
                }
                or border_count < parameters.minimum_border_count
            ):
                continue
            corners = (
                grid[y][x],
                grid[y][x + size - 1],
                grid[y + size - 1][x],
                grid[y + size - 1][x + size - 1],
            )
            if any(value != background for value in corners):
                continue
            interior = tuple(
                grid[yy][xx]
                for yy in range(y + 1, y + size - 1)
                for xx in range(x + 1, x + size - 1)
            )
            if (
                parameters.symbol_color not in interior
                or any(
                    value not in {parameters.symbol_color, background}
                    for value in interior
                )
            ):
                continue
            pattern = "/".join(
                "".join(
                    (
                        "1"
                        if grid[yy][xx] == parameters.symbol_color
                        else "0"
                    )
                    for xx in range(x + 1, x + size - 1)
                )
                for yy in range(y + 1, y + size - 1)
            )
            candidates.append(
                _RewriteTile(
                    x=x,
                    y=y,
                    background=background,
                    pattern=_canonical_pattern(pattern),
                    score=border_count * 10
                    + sum(
                        value == parameters.symbol_color
                        for value in interior
                    ),
                )
            )
    return tuple(candidates)


def _select_non_overlapping(
    candidates: Sequence[_RewriteTile],
    *,
    tile_size: int,
) -> tuple[_RewriteTile, ...]:
    best_by_origin: dict[Point, _RewriteTile] = {}
    for candidate in candidates:
        key = (candidate.x, candidate.y)
        previous = best_by_origin.get(key)
        if previous is None or (
            candidate.score,
            -candidate.x,
            -candidate.y,
        ) > (
            previous.score,
            -previous.x,
            -previous.y,
        ):
            best_by_origin[key] = candidate
    items = sorted(
        best_by_origin.values(),
        key=lambda item: (item.x, -item.score),
    )
    previous_indexes: list[int] = []
    for index, item in enumerate(items):
        previous_index = -1
        for candidate_index in range(index - 1, -1, -1):
            if (
                items[candidate_index].x + tile_size
                <= item.x
            ):
                previous_index = candidate_index
                break
        previous_indexes.append(previous_index)
    dynamic: list[tuple[tuple[int, int, int], tuple[int, ...]]] = [
        ((0, 0, 0), ()) for _ in range(len(items) + 1)
    ]
    for index, item in enumerate(items, start=1):
        skip_key, skip_indexes = dynamic[index - 1]
        base_key, base_indexes = dynamic[
            previous_indexes[index - 1] + 1
        ]
        take_indexes = (*base_indexes, index - 1)
        take_key = (
            base_key[0] + 1,
            base_key[1] + item.score,
            -sum(items[item_index].x for item_index in take_indexes),
        )
        dynamic[index] = (
            (take_key, take_indexes)
            if take_key > skip_key
            else (skip_key, skip_indexes)
        )
    return tuple(items[index] for index in dynamic[-1][1])


def _parse_rows(
    grid: Grid,
    parameters: _RewriteParameters,
) -> tuple[_RewriteRow, ...]:
    candidates = sorted(
        _raw_tile_candidates(grid, parameters),
        key=lambda item: (item.y, item.x),
    )
    clusters: list[list[_RewriteTile]] = []
    for candidate in candidates:
        if not clusters:
            clusters.append([candidate])
            continue
        y_values = sorted(item.y for item in clusters[-1])
        current_y = y_values[len(y_values) // 2]
        if candidate.y - current_y <= 2:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])
    rows: list[_RewriteRow] = []
    for cluster in clusters:
        selected = _select_non_overlapping(
            cluster,
            tile_size=parameters.tile_size,
        )
        if not selected:
            continue
        y_values = sorted(item.y for item in selected)
        rows.append(
            _RewriteRow(
                y=y_values[len(y_values) // 2],
                tiles=tuple(
                    sorted(selected, key=lambda item: (item.x, item.y))
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.y, row.tiles[0].x)))


def _connector_present(
    grid: Grid,
    *,
    left: _RewriteTile,
    right: _RewriteTile,
    parameters: _RewriteParameters,
) -> bool:
    start = left.x + parameters.tile_size
    end = right.x
    if not start < end:
        return False
    center_y = left.y + parameters.tile_size // 2
    values = tuple(grid[center_y][x] for x in range(start, end))
    return bool(values) and (
        sum(value == parameters.connector_color for value in values)
        * 4
        >= len(values) * 3
    )


def _parse_rule_nodes(
    grid: Grid,
    rows: tuple[_RewriteRow, ...],
    parameters: _RewriteParameters,
) -> tuple[tuple[_RewriteRule, ...], tuple[_RewriteNode, ...]]:
    if len(rows) < 3:
        return (), ()
    rules: list[tuple[_RewriteRow, int, int, int]] = []
    for row in rows[:-2]:
        for left_index, (left, right) in enumerate(
            zip(row.tiles, row.tiles[1:])
        ):
            if not _connector_present(
                grid,
                left=left,
                right=right,
                parameters=parameters,
            ):
                continue
            left_start = left_index
            while (
                left_start > 0
                and row.tiles[left_start].x
                - row.tiles[left_start - 1].x
                == parameters.tile_size
            ):
                left_start -= 1
            right_end = left_index + 1
            while (
                right_end + 1 < len(row.tiles)
                and row.tiles[right_end + 1].x
                - row.tiles[right_end].x
                == parameters.tile_size
            ):
                right_end += 1
            rules.append((row, left_start, left_index, right_end))
    rules.sort(
        key=lambda item: (
            item[0].y,
            item[0].tiles[item[1]].x,
            item[0].tiles[item[2] + 1].x,
        )
    )
    parsed_rules: list[_RewriteRule] = []
    nodes: list[_RewriteNode] = []
    for rule_index, (row, left_start, left_end, right_end) in enumerate(
        rules
    ):
        left_tiles = row.tiles[left_start : left_end + 1]
        right_tiles = row.tiles[left_end + 1 : right_end + 1]
        if not left_tiles or not right_tiles:
            continue
        left_key = f"rule:{rule_index}:left"
        right_key = f"rule:{rule_index}:right"
        nodes.extend(
            (
                _RewriteNode(
                    key=left_key,
                    labels=tuple(tile.label for tile in left_tiles),
                    bbox=(
                        left_tiles[0].x,
                        min(tile.y for tile in left_tiles),
                        left_tiles[-1].x + parameters.tile_size - 1,
                        max(tile.y for tile in left_tiles)
                        + parameters.tile_size
                        - 1,
                    ),
                ),
                _RewriteNode(
                    key=right_key,
                    labels=tuple(tile.label for tile in right_tiles),
                    bbox=(
                        right_tiles[0].x,
                        min(tile.y for tile in right_tiles),
                        right_tiles[-1].x
                        + parameters.tile_size
                        - 1,
                        max(tile.y for tile in right_tiles)
                        + parameters.tile_size
                        - 1,
                    ),
                ),
            )
        )
        parsed_rules.append(
            _RewriteRule(
                index=rule_index,
                left_key=left_key,
                right_key=right_key,
            )
        )
    return tuple(parsed_rules), tuple(nodes)


def _selector_score(
    grid: Grid,
    node: _RewriteNode,
    parameters: _RewriteParameters,
) -> int:
    x0, y0, x1, y1 = node.bbox
    width = len(grid[0]) if grid else 0
    height = len(grid)
    score = 0
    for y in range(max(0, y0 - 6), min(height, y1 + 7)):
        if y0 <= y <= y1:
            continue
        for x in range(max(0, x0 - 1), min(width, x1 + 2)):
            if grid[y][x] == parameters.selector_color:
                score += 1
    return score


def _apply_fixed_rules(
    source: tuple[str, ...],
    rules: tuple[_RewriteRule, ...],
    node_by_key: Mapping[str, _RewriteNode],
) -> tuple[str, ...] | None:
    output: list[str] = []
    position = 0
    while position < len(source):
        matched = False
        for rule in rules:
            left = node_by_key[rule.left_key].labels
            if source[position : position + len(left)] != left:
                continue
            output.extend(node_by_key[rule.right_key].labels)
            position += len(left)
            matched = True
            break
        if not matched:
            return None
    return tuple(output)


def _fixed_target(
    source: tuple[str, ...],
    output_backgrounds: tuple[int, ...],
    rules: tuple[_RewriteRule, ...],
    nodes: tuple[_RewriteNode, ...],
    parameters: _RewriteParameters,
) -> tuple[tuple[str, ...], int]:
    node_by_key = {node.key: node for node in nodes}
    current: tuple[str, ...] | None = source
    for depth in range(1, parameters.maximum_rewrite_depth + 1):
        if current is None:
            break
        current = _apply_fixed_rules(current, rules, node_by_key)
        if (
            current is not None
            and len(current) == len(output_backgrounds)
            and tuple(
                int(label.split(":", 1)[0]) for label in current
            )
            == output_backgrounds
        ):
            return current, depth
    return (), 0


def _surface_from_grid(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> _RewriteSurface | None:
    parameters = _RewriteParameters.from_instruction(instruction)
    if parameters is None:
        return None
    required_actions = {
        parameters.decrement_action,
        parameters.increment_action,
        parameters.previous_action,
        parameters.next_action,
    }
    if not required_actions.issubset(available_actions):
        return None
    rows = _parse_rows(grid, parameters)
    if len(rows) < 3:
        return None
    rules, rule_nodes = _parse_rule_nodes(grid, rows, parameters)
    if not rules or len(rule_nodes) != 2 * len(rules):
        return None
    source_row, output_row = rows[-2:]
    if (
        not source_row.tiles
        or not output_row.tiles
        or len(source_row.tiles) > parameters.maximum_output_tokens
        or len(output_row.tiles) > parameters.maximum_output_tokens
    ):
        return None
    output_nodes = tuple(
        _RewriteNode(
            key=f"output:{index}",
            labels=(tile.label,),
            bbox=(
                tile.x,
                tile.y,
                tile.x + parameters.tile_size - 1,
                tile.y + parameters.tile_size - 1,
            ),
        )
        for index, tile in enumerate(output_row.tiles)
    )
    rule_scores = tuple(
        _selector_score(grid, node, parameters) for node in rule_nodes
    )
    output_scores = tuple(
        _selector_score(grid, node, parameters) for node in output_nodes
    )
    best_rule_score = max(rule_scores, default=0)
    best_output_score = max(output_scores, default=0)
    if max(best_rule_score, best_output_score) < 2:
        return None
    if best_rule_score > best_output_score:
        mode = "editable-rules"
        nodes = rule_nodes
        selected_index = min(
            (
                index
                for index, score in enumerate(rule_scores)
                if score == best_rule_score
            ),
            default=-1,
        )
        fixed_target: tuple[str, ...] = ()
        fixed_depth = 0
    else:
        mode = "fixed-rules"
        nodes = output_nodes
        selected_index = min(
            (
                index
                for index, score in enumerate(output_scores)
                if score == best_output_score
            ),
            default=-1,
        )
        fixed_target, fixed_depth = _fixed_target(
            source_row.labels,
            tuple(tile.background for tile in output_row.tiles),
            rules,
            rule_nodes,
            parameters,
        )
        if not fixed_target:
            return None
    if not 0 <= selected_index < len(nodes):
        return None
    signature = "symbolic-rewrite-surface:" + digest_object(
        {
            "mode": mode,
            "rule_arities": tuple(
                (
                    len(next(node.labels for node in rule_nodes
                             if node.key == rule.left_key)),
                    len(next(node.labels for node in rule_nodes
                             if node.key == rule.right_key)),
                )
                for rule in rules
            ),
            "node_boxes": tuple(node.bbox for node in nodes),
            "source_length": len(source_row.labels),
            "output_length": len(output_row.labels),
        }
    )[:24]
    return _RewriteSurface(
        signature=signature,
        mode=mode,
        rules=rules,
        nodes=nodes,
        source=source_row.labels,
        output=output_row.labels,
        selected_index=selected_index,
        fixed_target=fixed_target,
        fixed_depth=fixed_depth,
        parameters=parameters,
    )


def _semantic_action(
    action_id: int,
    instruction: SemanticOperatorInstruction,
    *,
    reason: str,
) -> VisualAction:
    return VisualAction(
        key=f"semantic-rewrite-action:{action_id}",
        action_id=action_id,
        group=0,
        evidence=(
            SYMBOLIC_REWRITE_OPERATOR,
            f"operator-prototype:{SYMBOLIC_REWRITE_OPERATOR}",
            "rendered-symbol-tile-rules",
            reason,
            "single-step-reobservation-required",
            *instruction.provenance,
        ),
    )


def _selector_navigation_action(
    selected: int,
    target: int,
    count: int,
    parameters: _RewriteParameters,
) -> int:
    forward = (target - selected) % count
    backward = (selected - target) % count
    return (
        parameters.next_action
        if forward <= backward
        else parameters.previous_action
    )


def _node_candidates(
    state: SymbolicRewriteState,
    key: str,
) -> tuple[tuple[str, ...], ...]:
    return tuple(state.candidate_states.get(key, ()))


def _assigned_rules(
    surface: _RewriteSurface,
    state: SymbolicRewriteState,
    assignments: Mapping[str, int],
) -> tuple[
    tuple[
        tuple[str, ...],
        tuple[str, ...],
    ],
    ...,
] | None:
    output: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for rule in surface.rules:
        left_candidates = _node_candidates(state, rule.left_key)
        right_candidates = _node_candidates(state, rule.right_key)
        left_index = assignments.get(rule.left_key, 0)
        right_index = assignments.get(rule.right_key, 0)
        if (
            not 0 <= left_index < len(left_candidates)
            or not 0 <= right_index < len(right_candidates)
        ):
            return None
        output.append(
            (
                left_candidates[left_index],
                right_candidates[right_index],
            )
        )
    return tuple(output)


def _apply_assigned_rules(
    source: tuple[str, ...],
    assigned_rules: tuple[
        tuple[tuple[str, ...], tuple[str, ...]],
        ...,
    ],
    *,
    maximum_output_tokens: int,
) -> tuple[str, ...] | None:
    output: list[str] = []
    position = 0
    while position < len(source):
        for left, right in assigned_rules:
            if source[position : position + len(left)] != left:
                continue
            output.extend(right)
            if len(output) > maximum_output_tokens:
                return None
            position += len(left)
            break
        else:
            return None
    return tuple(output)


def _enumerate_rewrite_pass(
    source: tuple[str, ...],
    target: tuple[str, ...] | None,
    surface: _RewriteSurface,
    state: SymbolicRewriteState,
    base_assignments: Mapping[str, int],
    *,
    limit: int,
) -> tuple[tuple[tuple[str, ...], dict[str, int]], ...]:
    results: list[tuple[tuple[str, ...], dict[str, int]]] = []

    def visit(
        source_position: int,
        output: tuple[str, ...],
        assignments: dict[str, int],
    ) -> None:
        if len(results) >= limit:
            return
        if source_position == len(source):
            if target is None or output == target:
                results.append((output, dict(assignments)))
            return
        if len(output) > surface.parameters.maximum_output_tokens:
            return
        for rule in surface.rules:
            left_options = _node_candidates(state, rule.left_key)
            right_options = _node_candidates(state, rule.right_key)
            required_left = assignments.get(rule.left_key)
            required_right = assignments.get(rule.right_key)
            left_indexes = (
                (required_left,)
                if required_left is not None
                else tuple(range(len(left_options)))
            )
            right_indexes = (
                (required_right,)
                if required_right is not None
                else tuple(range(len(right_options)))
            )
            for left_index in left_indexes:
                left = left_options[left_index]
                if (
                    source[
                        source_position : source_position + len(left)
                    ]
                    != left
                ):
                    continue
                for right_index in right_indexes:
                    right = right_options[right_index]
                    next_output = (*output, *right)
                    if (
                        target is not None
                        and target[: len(next_output)] != next_output
                    ):
                        continue
                    next_assignments = dict(assignments)
                    next_assignments[rule.left_key] = left_index
                    next_assignments[rule.right_key] = right_index
                    visit(
                        source_position + len(left),
                        next_output,
                        next_assignments,
                    )

    visit(0, (), dict(base_assignments))
    deduplicated: dict[
        tuple[tuple[str, ...], tuple[tuple[str, int], ...]],
        tuple[tuple[str, ...], dict[str, int]],
    ] = {}
    for output, assignments in results:
        key = (output, tuple(sorted(assignments.items())))
        deduplicated[key] = (output, assignments)
    return tuple(deduplicated.values())


def _validate_solution(
    surface: _RewriteSurface,
    state: SymbolicRewriteState,
    assignments: Mapping[str, int],
    *,
    depth: int,
) -> bool:
    assigned = _assigned_rules(surface, state, assignments)
    if assigned is None:
        return False
    current: tuple[str, ...] | None = surface.source
    for _ in range(depth):
        if current is None:
            return False
        current = _apply_assigned_rules(
            current,
            assigned,
            maximum_output_tokens=(
                surface.parameters.maximum_output_tokens
            ),
        )
    return current == surface.output


def _solve_editable_offsets(
    surface: _RewriteSurface,
    state: SymbolicRewriteState,
) -> tuple[int, ...]:
    limit = surface.parameters.maximum_intermediate_candidates
    solutions: list[tuple[int, ...]] = []
    for depth in range(1, surface.parameters.maximum_rewrite_depth + 1):
        if depth == 1:
            final_paths = _enumerate_rewrite_pass(
                surface.source,
                surface.output,
                surface,
                state,
                {},
                limit=limit,
            )
        else:
            frontiers: tuple[
                tuple[tuple[str, ...], dict[str, int]],
                ...,
            ] = ((surface.source, {}),)
            for _pass_index in range(depth - 1):
                next_frontiers: list[
                    tuple[tuple[str, ...], dict[str, int]]
                ] = []
                for tokens, assignments in frontiers:
                    remaining = max(0, limit - len(next_frontiers))
                    if not remaining:
                        break
                    next_frontiers.extend(
                        _enumerate_rewrite_pass(
                            tokens,
                            None,
                            surface,
                            state,
                            assignments,
                            limit=remaining,
                        )
                    )
                frontiers = tuple(next_frontiers)
                if not frontiers:
                    break
            final_list: list[
                tuple[tuple[str, ...], dict[str, int]]
            ] = []
            for tokens, assignments in frontiers:
                remaining = max(0, limit - len(final_list))
                if not remaining:
                    break
                final_list.extend(
                    _enumerate_rewrite_pass(
                        tokens,
                        surface.output,
                        surface,
                        state,
                        assignments,
                        limit=remaining,
                    )
                )
            final_paths = tuple(final_list)
        for _output, assignments in final_paths:
            complete = {
                key: assignments.get(key, 0)
                for key in surface.node_order
            }
            if not _validate_solution(
                surface,
                state,
                complete,
                depth=depth,
            ):
                continue
            solutions.append(
                tuple(complete[key] for key in surface.node_order)
            )
        if solutions:
            break
    if not solutions:
        return ()
    return min(
        set(solutions),
        key=lambda offsets: (sum(offsets), offsets),
    )


@dataclass(slots=True)
class SymbolicRewriteState:
    """Passive state for one rendered symbolic-rewrite surface."""

    instruction_digest: str = ""
    surface_signature: str = ""
    mode: str = ""
    phase: str = ""
    node_order: tuple[str, ...] = ()
    candidate_states: dict[
        str,
        list[tuple[str, ...]],
    ] = field(default_factory=dict)
    probe_index: int = 0
    target_offsets: tuple[int, ...] = ()
    execution_index: int = 0
    observation_count: int = 0
    plan_count: int = 0
    submit_count: int = 0
    abandoned: bool = False

    def reset(self) -> None:
        self.instruction_digest = ""
        self.surface_signature = ""
        self.mode = ""
        self.phase = ""
        self.node_order = ()
        self.candidate_states.clear()
        self.probe_index = 0
        self.target_offsets = ()
        self.execution_index = 0
        self.observation_count = 0
        self.plan_count = 0
        self.submit_count = 0
        self.abandoned = False

    def _bind(
        self,
        surface: _RewriteSurface,
        instruction: SemanticOperatorInstruction,
    ) -> None:
        instruction_digest = digest_object(instruction)
        if (
            self.instruction_digest == instruction_digest
            and self.surface_signature == surface.signature
            and self.mode == surface.mode
            and self.node_order == surface.node_order
        ):
            return
        self.reset()
        self.instruction_digest = instruction_digest
        self.surface_signature = surface.signature
        self.mode = surface.mode
        self.node_order = surface.node_order
        self.phase = (
            "fixed"
            if surface.mode == "fixed-rules"
            else "probe"
        )
        self.candidate_states = {
            key: [] for key in surface.node_order
        }

    def _fixed_decision(
        self,
        surface: _RewriteSurface,
        instruction: SemanticOperatorInstruction,
    ) -> SymbolicRewriteDecision:
        target = surface.fixed_target
        if len(target) != len(surface.output):
            self.abandoned = True
            return SymbolicRewriteDecision(
                action=None,
                reason="SYMBOLIC_REWRITE_TARGET_UNAVAILABLE",
                memory_influenced=False,
            )
        mismatches = tuple(
            index
            for index, (current, desired) in enumerate(
                zip(surface.output, target)
            )
            if current != desired
        )
        if mismatches:
            target_index = mismatches[0]
            if surface.selected_index != target_index:
                action_id = _selector_navigation_action(
                    surface.selected_index,
                    target_index,
                    len(surface.nodes),
                    surface.parameters,
                )
                return SymbolicRewriteDecision(
                    action=_semantic_action(
                        action_id,
                        instruction,
                        reason="rendered-selector-navigation",
                    ),
                    reason=(
                        f"{SYMBOLIC_REWRITE_OPERATOR}:selector-navigation"
                    ),
                    memory_influenced=self.observation_count > 0,
                )
            self.observation_count += 1
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    surface.parameters.increment_action,
                    instruction,
                    reason="rendered-output-symbol-mismatch",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:output-cycle",
                memory_influenced=self.observation_count > 1,
            )
        self.submit_count += 1
        return SymbolicRewriteDecision(
            action=_semantic_action(
                surface.parameters.decrement_action,
                instruction,
                reason="verified-output-submit-arm",
            ),
            reason=f"{SYMBOLIC_REWRITE_OPERATOR}:submit-arm",
            memory_influenced=True,
        )

    def _probe_decision(
        self,
        surface: _RewriteSurface,
        instruction: SemanticOperatorInstruction,
    ) -> SymbolicRewriteDecision:
        if self.probe_index >= len(self.node_order):
            self.phase = "solve"
            return self._solve_decision(surface, instruction)
        target_key = self.node_order[self.probe_index]
        target_index = self.probe_index
        if surface.selected_index != target_index:
            action_id = _selector_navigation_action(
                surface.selected_index,
                target_index,
                len(surface.nodes),
                surface.parameters,
            )
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    action_id,
                    instruction,
                    reason="rendered-rule-node-navigation",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:probe-navigation",
                memory_influenced=bool(self.observation_count),
            )
        observed = surface.nodes[target_index].labels
        candidates = self.candidate_states[target_key]
        if observed not in candidates:
            candidates.append(observed)
            self.observation_count += 1
        if len(candidates) < surface.parameters.cycle_size:
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    surface.parameters.increment_action,
                    instruction,
                    reason="bounded-rule-node-cycle-probe",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:cycle-probe",
                memory_influenced=len(candidates) > 1,
            )
        if observed != candidates[0]:
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    surface.parameters.increment_action,
                    instruction,
                    reason="restore-probed-rule-node",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:probe-restore",
                memory_influenced=True,
            )
        self.probe_index += 1
        if self.probe_index >= len(self.node_order):
            self.phase = "solve"
            return self._solve_decision(surface, instruction)
        return SymbolicRewriteDecision(
            action=_semantic_action(
                surface.parameters.next_action,
                instruction,
                reason="advance-to-unobserved-rule-node",
            ),
            reason=f"{SYMBOLIC_REWRITE_OPERATOR}:probe-advance",
            memory_influenced=True,
        )

    def _solve_decision(
        self,
        surface: _RewriteSurface,
        instruction: SemanticOperatorInstruction,
    ) -> SymbolicRewriteDecision:
        if not self.target_offsets:
            self.target_offsets = _solve_editable_offsets(surface, self)
            if not self.target_offsets:
                self.abandoned = True
                self.phase = "done"
                return SymbolicRewriteDecision(
                    action=None,
                    reason="SYMBOLIC_REWRITE_CONSTRAINTS_UNCLOSED",
                    memory_influenced=True,
                )
            self.plan_count += 1
        self.phase = "execute"
        self.execution_index = 0
        return self._execute_decision(surface, instruction)

    def _execute_decision(
        self,
        surface: _RewriteSurface,
        instruction: SemanticOperatorInstruction,
    ) -> SymbolicRewriteDecision:
        if len(self.target_offsets) != len(self.node_order):
            self.abandoned = True
            self.phase = "done"
            return SymbolicRewriteDecision(
                action=None,
                reason="SYMBOLIC_REWRITE_PLAN_INVALID",
                memory_influenced=True,
            )
        target_index = min(
            self.execution_index,
            len(self.node_order) - 1,
        )
        if surface.selected_index != target_index:
            action_id = _selector_navigation_action(
                surface.selected_index,
                target_index,
                len(surface.nodes),
                surface.parameters,
            )
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    action_id,
                    instruction,
                    reason="compiled-rule-plan-navigation",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:plan-navigation",
                memory_influenced=True,
            )
        key = self.node_order[target_index]
        candidates = _node_candidates(self, key)
        target_offset = self.target_offsets[target_index]
        if not 0 <= target_offset < len(candidates):
            self.abandoned = True
            self.phase = "done"
            return SymbolicRewriteDecision(
                action=None,
                reason="SYMBOLIC_REWRITE_OFFSET_INVALID",
                memory_influenced=True,
            )
        current = surface.nodes[target_index].labels
        if current != candidates[target_offset]:
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    surface.parameters.increment_action,
                    instruction,
                    reason="execute-compiled-rule-offset",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:plan-cycle",
                memory_influenced=True,
            )
        if target_index + 1 < len(self.node_order):
            self.execution_index = target_index + 1
            return SymbolicRewriteDecision(
                action=_semantic_action(
                    surface.parameters.next_action,
                    instruction,
                    reason="advance-compiled-rule-plan",
                ),
                reason=f"{SYMBOLIC_REWRITE_OPERATOR}:plan-advance",
                memory_influenced=True,
            )
        self.submit_count += 1
        return SymbolicRewriteDecision(
            action=_semantic_action(
                surface.parameters.decrement_action,
                instruction,
                reason="verified-rule-plan-submit-arm",
            ),
            reason=f"{SYMBOLIC_REWRITE_OPERATOR}:submit-arm",
            memory_influenced=True,
        )

    def decide(
        self,
        grid: Grid,
        available_actions: tuple[int, ...],
        instruction: SemanticOperatorInstruction,
    ) -> SymbolicRewriteDecision:
        surface = _surface_from_grid(
            grid,
            available_actions,
            instruction,
        )
        if surface is None:
            return SymbolicRewriteDecision(
                action=None,
                reason="NO_RENDERED_SYMBOLIC_REWRITE_SURFACE",
                memory_influenced=bool(self.observation_count),
            )
        self._bind(surface, instruction)
        if self.abandoned:
            return SymbolicRewriteDecision(
                action=None,
                reason="SYMBOLIC_REWRITE_STATE_ABANDONED",
                memory_influenced=True,
            )
        if self.phase == "fixed":
            return self._fixed_decision(surface, instruction)
        if self.phase == "probe":
            return self._probe_decision(surface, instruction)
        if self.phase == "solve":
            return self._solve_decision(surface, instruction)
        if self.phase == "execute":
            return self._execute_decision(surface, instruction)
        return SymbolicRewriteDecision(
            action=None,
            reason="SYMBOLIC_REWRITE_PHASE_CLOSED",
            memory_influenced=True,
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": SYMBOLIC_REWRITE_STATE_FORMAT,
            "instruction_digest": self.instruction_digest,
            "surface_signature": self.surface_signature,
            "mode": self.mode,
            "phase": self.phase,
            "node_order": list(self.node_order),
            "candidate_states": {
                key: [list(labels) for labels in candidates]
                for key, candidates in sorted(
                    self.candidate_states.items()
                )
            },
            "probe_index": self.probe_index,
            "target_offsets": list(self.target_offsets),
            "execution_index": self.execution_index,
            "observation_count": self.observation_count,
            "plan_count": self.plan_count,
            "submit_count": self.submit_count,
            "abandoned": self.abandoned,
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "SYMBOLIC_REWRITE_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        value: Mapping[str, object],
    ) -> SymbolicRewriteState:
        if value.get("format") != SYMBOLIC_REWRITE_STATE_FORMAT:
            raise ValueError("symbolic rewrite payload format invalid")
        raw_node_order = value.get("node_order", ())
        raw_candidates = value.get("candidate_states", {})
        raw_offsets = value.get("target_offsets", ())
        abandoned = value.get("abandoned", False)
        if (
            not isinstance(raw_node_order, Sequence)
            or isinstance(raw_node_order, (str, bytes, bytearray))
            or not isinstance(raw_candidates, Mapping)
            or not isinstance(raw_offsets, Sequence)
            or isinstance(raw_offsets, (str, bytes, bytearray))
            or not isinstance(abandoned, bool)
        ):
            raise ValueError("symbolic rewrite payload sequence invalid")
        candidate_states: dict[str, list[tuple[str, ...]]] = {}
        for raw_key, raw_states in raw_candidates.items():
            if (
                not isinstance(raw_states, Sequence)
                or isinstance(raw_states, (str, bytes, bytearray))
            ):
                raise ValueError(
                    "symbolic rewrite candidate states invalid"
                )
            converted: list[tuple[str, ...]] = []
            for raw_state in raw_states:
                if (
                    not isinstance(raw_state, Sequence)
                    or isinstance(raw_state, (str, bytes, bytearray))
                ):
                    raise ValueError(
                        "symbolic rewrite candidate state invalid"
                    )
                converted.append(tuple(str(item) for item in raw_state))
            candidate_states[str(raw_key)] = converted
        phase = str(value.get("phase", ""))
        if phase not in {
            "",
            "fixed",
            "probe",
            "solve",
            "execute",
            "done",
        }:
            raise ValueError("symbolic rewrite phase invalid")
        mode = str(value.get("mode", ""))
        if mode not in {"", "fixed-rules", "editable-rules"}:
            raise ValueError("symbolic rewrite mode invalid")
        return cls(
            instruction_digest=str(
                value.get("instruction_digest", "")
            ),
            surface_signature=str(
                value.get("surface_signature", "")
            ),
            mode=mode,
            phase=phase,
            node_order=tuple(str(item) for item in raw_node_order),
            candidate_states=candidate_states,
            probe_index=_payload_int(
                value.get("probe_index", 0),
                "probe_index",
            ),
            target_offsets=tuple(
                _payload_int(item, "target_offset")
                for item in raw_offsets
            ),
            execution_index=_payload_int(
                value.get("execution_index", 0),
                "execution_index",
            ),
            observation_count=_payload_int(
                value.get("observation_count", 0),
                "observation_count",
            ),
            plan_count=_payload_int(
                value.get("plan_count", 0),
                "plan_count",
            ),
            submit_count=_payload_int(
                value.get("submit_count", 0),
                "submit_count",
            ),
            abandoned=abandoned,
        )


__all__ = [
    "SYMBOLIC_REWRITE_OPERATOR",
    "SYMBOLIC_REWRITE_STATE_FORMAT",
    "SymbolicRewriteDecision",
    "SymbolicRewriteState",
]
