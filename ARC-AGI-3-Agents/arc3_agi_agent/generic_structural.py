"""Identity-free structural state inference for rendered control problems."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Sequence

from .schema import digest_object

Matrix = tuple[tuple[int, ...], ...]
ShapeSignature = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class _ColorComponent:
    cells: tuple[tuple[int, int], ...]
    min_y: int
    min_x: int
    max_y: int
    max_x: int

    @property
    def center_y(self) -> int:
        return round((self.min_y + self.max_y) / 2.0)

    @property
    def center_x(self) -> int:
        return round((self.min_x + self.max_x) / 2.0)


@dataclass(frozen=True, slots=True)
class RelationalRewriteState:
    """A rendered example-to-sequence rewrite state with no task identity."""

    sequence_length: int
    selected_index: int
    selected_matches: bool
    all_matches: bool
    desired_shapes: tuple[ShapeSignature, ...]
    output_shapes: tuple[ShapeSignature, ...]
    structure_digest: str


def _components_for_color(
    matrix: Matrix,
    color: int,
) -> tuple[_ColorComponent, ...]:
    height = len(matrix)
    width = len(matrix[0]) if matrix else 0
    visited: set[tuple[int, int]] = set()
    components: list[_ColorComponent] = []
    for y in range(height):
        for x in range(width):
            if matrix[y][x] != color or (y, x) in visited:
                continue
            queue: deque[tuple[int, int]] = deque(((y, x),))
            visited.add((y, x))
            cells: list[tuple[int, int]] = []
            while queue:
                current_y, current_x = queue.popleft()
                cells.append((current_y, current_x))
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    next_y = current_y + dy
                    next_x = current_x + dx
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and (next_y, next_x) not in visited
                        and matrix[next_y][next_x] == color
                    ):
                        visited.add((next_y, next_x))
                        queue.append((next_y, next_x))
            ordered = tuple(sorted(cells))
            ys = tuple(item[0] for item in ordered)
            xs = tuple(item[1] for item in ordered)
            components.append(
                _ColorComponent(
                    cells=ordered,
                    min_y=min(ys),
                    min_x=min(xs),
                    max_y=max(ys),
                    max_x=max(xs),
                )
            )
    return tuple(components)


def _glyph_components(
    matrix: Matrix,
    color: int,
) -> tuple[_ColorComponent, ...]:
    height = len(matrix)
    width = len(matrix[0]) if matrix else 0
    maximum_extent = max(3, min(height, width) // 4)
    return tuple(
        component
        for component in _components_for_color(matrix, color)
        if (
            3 <= component.max_y - component.min_y + 1 <= maximum_extent
            and 3 <= component.max_x - component.min_x + 1
            <= maximum_extent
            and component.min_y > 0
            and component.min_x > 0
            and component.max_y < height - 1
            and component.max_x < width - 1
        )
    )


def _rows(
    components: Sequence[_ColorComponent],
) -> tuple[tuple[_ColorComponent, ...], ...]:
    grouped: dict[int, list[_ColorComponent]] = {}
    for component in components:
        grouped.setdefault(component.center_y, []).append(component)
    return tuple(
        tuple(sorted(grouped[center], key=lambda item: item.center_x))
        for center in sorted(grouped)
    )


def _rotate(shape: ShapeSignature) -> ShapeSignature:
    return tuple(
        tuple(shape[len(shape) - 1 - x][y] for x in range(len(shape)))
        for y in range(len(shape[0]))
    )


def _shape_signature(
    matrix: Matrix,
    component: _ColorComponent,
    color: int,
) -> ShapeSignature:
    shape = tuple(
        tuple(
            0 if matrix[y][x] == color else 1
            for x in range(component.min_x, component.max_x + 1)
        )
        for y in range(component.min_y, component.max_y + 1)
    )
    if not shape or len(shape) != len(shape[0]):
        return shape
    rotations: list[ShapeSignature] = []
    current = shape
    for _ in range(4):
        rotations.append(current)
        current = _rotate(current)
    return min(rotations)


def _occupied_shape_signature(
    matrix: Matrix,
    component: _ColorComponent,
    color: int,
) -> ShapeSignature:
    shape = tuple(
        tuple(
            1 if matrix[y][x] == color else 0
            for x in range(component.min_x, component.max_x + 1)
        )
        for y in range(component.min_y, component.max_y + 1)
    )
    if not shape or len(shape) != len(shape[0]):
        return shape
    rotations: list[ShapeSignature] = []
    current = shape
    for _ in range(4):
        rotations.append(current)
        current = _rotate(current)
    return min(rotations)


def _marker_index(
    matrix: Matrix,
    output_row: Sequence[_ColorComponent],
    *,
    output_color: int,
) -> int | None:
    if not output_row:
        return None
    center_y = output_row[0].center_y
    row_background = Counter(matrix[center_y]).most_common(1)[0][0]
    scores: list[int] = []
    for component in output_row:
        score = 0
        for y in range(
            max(0, component.min_y - 4),
            min(len(matrix), component.max_y + 5),
        ):
            for x in range(component.min_x, component.max_x + 1):
                inside = (
                    component.min_y <= y <= component.max_y
                    and component.min_x <= x <= component.max_x
                )
                value = matrix[y][x]
                if not inside and value not in {
                    row_background,
                    output_color,
                }:
                    score += 1
        scores.append(score)
    maximum = max(scores)
    if maximum <= 0 or scores.count(maximum) != 1:
        return None
    return scores.index(maximum)


def _infer_shared_symbol_rewrite(
    matrix: Matrix,
    colors: Sequence[int],
) -> RelationalRewriteState | None:
    inferred: list[tuple[int, RelationalRewriteState]] = []
    for color in colors:
        rows = _rows(_glyph_components(matrix, color))
        if len(rows) < 4:
            continue
        maximum_count = max(len(row) for row in rows)
        sequence_rows = tuple(
            row for row in rows if len(row) == maximum_count
        )
        if (
            maximum_count < 3
            or len(sequence_rows) != 2
            or sequence_rows[0][0].center_y
            >= sequence_rows[1][0].center_y
        ):
            continue
        source_row, output_row = sequence_rows
        mapping_rows = tuple(
            row
            for row in rows
            if (
                row[0].center_y < source_row[0].center_y
                and len(row) >= 4
                and len(row) % 2 == 0
            )
        )
        if len(mapping_rows) < 2:
            continue
        mapping: dict[ShapeSignature, ShapeSignature] = {}
        for mapping_row in mapping_rows:
            for index in range(0, len(mapping_row), 2):
                mapping[
                    _occupied_shape_signature(
                        matrix,
                        mapping_row[index],
                        color,
                    )
                ] = _occupied_shape_signature(
                    matrix,
                    mapping_row[index + 1],
                    color,
                )
        source_shapes = tuple(
            _occupied_shape_signature(matrix, component, color)
            for component in source_row
        )
        if any(shape not in mapping for shape in source_shapes):
            continue
        desired_shapes = tuple(mapping[shape] for shape in source_shapes)
        output_shapes = tuple(
            _occupied_shape_signature(matrix, component, color)
            for component in output_row
        )
        selected_index = _marker_index(
            matrix,
            output_row,
            output_color=color,
        )
        if selected_index is None:
            continue
        state = RelationalRewriteState(
            sequence_length=len(output_shapes),
            selected_index=selected_index,
            selected_matches=(
                output_shapes[selected_index]
                == desired_shapes[selected_index]
            ),
            all_matches=output_shapes == desired_shapes,
            desired_shapes=desired_shapes,
            output_shapes=output_shapes,
            structure_digest="relational-rewrite:"
            + digest_object(
                {
                    "mapping": mapping,
                    "source_shapes": source_shapes,
                    "desired_shapes": desired_shapes,
                    "output_shapes": output_shapes,
                    "selected_index": selected_index,
                }
            ),
        )
        inferred.append((len(mapping), state))
    if not inferred:
        return None
    inferred.sort(
        key=lambda item: (
            -item[0],
            item[1].structure_digest,
        )
    )
    return inferred[0][1]


def infer_relational_rewrite_state(
    matrix: Matrix,
) -> RelationalRewriteState | None:
    """Infer a visual example mapping and an editable output sequence."""

    if (
        len(matrix) < 12
        or not matrix[0]
        or any(len(row) != len(matrix[0]) for row in matrix)
    ):
        return None
    colors = tuple(
        color
        for color, _ in Counter(
            cell for row in matrix for cell in row
        ).most_common()
    )
    shared_symbol_state = _infer_shared_symbol_rewrite(matrix, colors)
    if shared_symbol_state is not None:
        return shared_symbol_state
    candidates: list[
        tuple[
            int,
            int,
            tuple[tuple[_ColorComponent, ...], ...],
            tuple[_ColorComponent, ...],
        ]
    ] = []
    for color in colors:
        rows = _rows(_glyph_components(matrix, color))
        sequence_rows = tuple(row for row in rows if len(row) >= 3)
        if len(sequence_rows) != 1:
            continue
        sequence_row = sequence_rows[0]
        mapping_rows = tuple(
            row
            for row in rows
            if row is not sequence_row
            and len(row) >= 2
            and row[0].center_y < sequence_row[0].center_y
        )
        if len(mapping_rows) < 2:
            continue
        candidates.append(
            (color, sequence_row[0].center_y, mapping_rows, sequence_row)
        )

    inferred: list[tuple[int, RelationalRewriteState]] = []
    for source in candidates:
        for output in candidates:
            if source[0] == output[0] or source[1] >= output[1]:
                continue
            source_mapping_by_y = {
                row[0].center_y: row for row in source[2]
            }
            output_mapping_by_y = {
                row[0].center_y: row for row in output[2]
            }
            shared_rows = tuple(
                sorted(
                    set(source_mapping_by_y).intersection(
                        output_mapping_by_y
                    )
                )
            )
            if len(shared_rows) < 2:
                continue
            mapping: dict[ShapeSignature, ShapeSignature] = {}
            for center_y in shared_rows:
                source_row = source_mapping_by_y[center_y]
                output_row = output_mapping_by_y[center_y]
                for source_component, output_component in zip(
                    source_row,
                    output_row,
                ):
                    mapping[
                        _shape_signature(
                            matrix,
                            source_component,
                            source[0],
                        )
                    ] = _shape_signature(
                        matrix,
                        output_component,
                        output[0],
                    )
            if len(source[3]) != len(output[3]) or len(source[3]) < 3:
                continue
            source_shapes = tuple(
                _shape_signature(matrix, component, source[0])
                for component in source[3]
            )
            if any(shape not in mapping for shape in source_shapes):
                continue
            desired_shapes = tuple(mapping[shape] for shape in source_shapes)
            output_shapes = tuple(
                _shape_signature(matrix, component, output[0])
                for component in output[3]
            )
            selected_index = _marker_index(
                matrix,
                output[3],
                output_color=output[0],
            )
            if selected_index is None:
                continue
            state = RelationalRewriteState(
                sequence_length=len(output_shapes),
                selected_index=selected_index,
                selected_matches=(
                    output_shapes[selected_index]
                    == desired_shapes[selected_index]
                ),
                all_matches=output_shapes == desired_shapes,
                desired_shapes=desired_shapes,
                output_shapes=output_shapes,
                structure_digest="relational-rewrite:"
                + digest_object(
                    {
                        "mapping": mapping,
                        "source_shapes": source_shapes,
                        "desired_shapes": desired_shapes,
                        "output_shapes": output_shapes,
                        "selected_index": selected_index,
                    }
                ),
            )
            inferred.append((len(mapping), state))
    if not inferred:
        return None
    inferred.sort(
        key=lambda item: (
            -item[0],
            item[1].structure_digest,
        )
    )
    return inferred[0][1]


__all__ = [
    "RelationalRewriteState",
    "infer_relational_rewrite_state",
]
