"""Rendered role-relative target selectors for privileged S2 execution.

S2 removes stored absolute pointer payloads.  A compiler may observe an S1
target during development, but the emitted selector retains only palette and
target-centred spatial relations.  The executor scans the current rendered
frame and resolves exactly one target before constructing the transient
environment API payload.

The selector deliberately does not contain an absolute horizontal or vertical
index.  Relative displacements are structural relations to rendered content
or, only when needed, to the frame boundary.  Identity and source/hidden state
remain separate S2 privileges and are removed by later stages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from arcengine import FrameDataRaw

from ..schema import digest_object

S2_ROLE_SELECTOR_SCHEMA_VERSION = "arc3-teacher-s2-role-selector-v1"
S2_ROLE_SELECTOR_DIGEST_PREFIX = "arc3_teacher_s2_role_selector:"

_PALETTE_KIND = "PALETTE"
_BOUNDARY_KIND = "FRAME_BOUNDARY"
_FORBIDDEN_ABSOLUTE_KEYS = frozenset(
    {
        "action_data",
        "column",
        "coordinate",
        "literal_coordinate",
        "row",
        "x",
        "y",
    }
)


class S2RoleSelectorError(RuntimeError):
    """Raised when a role-relative selector is invalid or ambiguous."""


@dataclass(frozen=True)
class ResolvedRenderedTarget:
    """Ephemeral target resolved from the current rendered frame."""

    horizontal_index: int
    vertical_index: int


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _all_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        mapping_output = {str(key) for key in value}
        for item in value.values():
            mapping_output.update(_all_keys(item))
        return mapping_output
    if isinstance(value, list):
        list_output: set[str] = set()
        for item in value:
            list_output.update(_all_keys(item))
        return list_output
    return set()


def final_render_grid(frame: FrameDataRaw) -> tuple[tuple[int, ...], ...]:
    """Return the final animation frame as a validated rectangular grid."""

    if not isinstance(frame, FrameDataRaw):
        raise TypeError("S2_FRAME_REQUIRED")
    raw_frames = list(frame.frame)
    if not raw_frames:
        raise S2RoleSelectorError("S2_RENDER_FRAME_MISSING")
    raw_grid = raw_frames[-1]
    value = raw_grid.tolist() if hasattr(raw_grid, "tolist") else raw_grid
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError("S2_RENDER_GRID_INVALID")
    rows: list[tuple[int, ...]] = []
    expected_width: int | None = None
    for raw_row in value:
        if not isinstance(raw_row, Sequence) or isinstance(
            raw_row,
            (str, bytes, bytearray),
        ):
            raise TypeError("S2_RENDER_ROW_INVALID")
        row = tuple(
            _integer(item, "render_palette") for item in raw_row
        )
        if expected_width is None:
            expected_width = len(row)
        if not row or len(row) != expected_width:
            raise S2RoleSelectorError("S2_RENDER_GRID_NOT_RECTANGULAR")
        rows.append(row)
    if not rows:
        raise S2RoleSelectorError("S2_RENDER_GRID_EMPTY")
    return tuple(rows)


def _relation_token(
    grid: tuple[tuple[int, ...], ...],
    *,
    horizontal_index: int,
    vertical_index: int,
    horizontal_delta: int,
    vertical_delta: int,
) -> tuple[str, int | None]:
    height = len(grid)
    width = len(grid[0])
    target_horizontal = horizontal_index + horizontal_delta
    target_vertical = vertical_index + vertical_delta
    if (
        target_horizontal < 0
        or target_horizontal >= width
        or target_vertical < 0
        or target_vertical >= height
    ):
        return (_BOUNDARY_KIND, None)
    return (
        _PALETTE_KIND,
        grid[target_vertical][target_horizontal],
    )


@lru_cache(maxsize=16)
def _offset_order(
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, int], ...]:
    """Order relations for compact, deterministic target separation."""

    cardinal: list[tuple[int, int]] = []
    for distance in range(1, max(width, height) + 1):
        if distance <= width:
            cardinal.extend(((-distance, 0), (distance, 0)))
        if distance <= height:
            cardinal.extend(((0, -distance), (0, distance)))

    diagonal: list[tuple[int, int]] = []
    for distance in range(1, max(width, height) + 1):
        if distance <= width and distance <= height:
            diagonal.extend(
                (
                    (-distance, -distance),
                    (distance, -distance),
                    (-distance, distance),
                    (distance, distance),
                )
            )

    selected = set(cardinal)
    selected.update(diagonal)
    remaining = [
        (horizontal_delta, vertical_delta)
        for vertical_delta in range(-height, height + 1)
        for horizontal_delta in range(-width, width + 1)
        if (horizontal_delta, vertical_delta) != (0, 0)
        and (horizontal_delta, vertical_delta) not in selected
    ]
    remaining.sort(
        key=lambda item: (
            max(abs(item[0]), abs(item[1])),
            abs(item[0]) + abs(item[1]),
            item[1],
            item[0],
        )
    )
    return tuple([*cardinal, *diagonal, *remaining])


def _constraint(
    *,
    horizontal_delta: int,
    vertical_delta: int,
    token: tuple[str, int | None],
) -> dict[str, object]:
    kind, value = token
    expected: dict[str, object] = {"kind": kind}
    if kind == _PALETTE_KIND:
        if value is None:
            raise S2RoleSelectorError("S2_PALETTE_TOKEN_MISSING")
        expected["value"] = value
    elif kind != _BOUNDARY_KIND:
        raise S2RoleSelectorError("S2_RELATION_TOKEN_INVALID")
    return {
        "horizontal_delta": horizontal_delta,
        "vertical_delta": vertical_delta,
        "expected": expected,
    }


def _constraint_token(
    raw_constraint: Mapping[str, Any],
) -> tuple[int, int, tuple[str, int | None]]:
    horizontal_delta = _integer(
        raw_constraint.get("horizontal_delta"),
        "horizontal_delta",
    )
    vertical_delta = _integer(
        raw_constraint.get("vertical_delta"),
        "vertical_delta",
    )
    raw_expected = raw_constraint.get("expected")
    if not isinstance(raw_expected, Mapping):
        raise TypeError("S2_SELECTOR_EXPECTED_TOKEN_INVALID")
    kind = str(raw_expected.get("kind", ""))
    if kind == _PALETTE_KIND:
        token: tuple[str, int | None] = (
            kind,
            _integer(raw_expected.get("value"), "expected.value"),
        )
    elif kind == _BOUNDARY_KIND:
        if "value" in raw_expected:
            raise S2RoleSelectorError(
                "S2_BOUNDARY_TOKEN_VALUE_FORBIDDEN"
            )
        token = (kind, None)
    else:
        raise S2RoleSelectorError("S2_SELECTOR_TOKEN_KIND_INVALID")
    return horizontal_delta, vertical_delta, token


def compile_role_relative_selector(
    *,
    frame: FrameDataRaw,
    target_horizontal_index: int,
    target_vertical_index: int,
) -> dict[str, Any]:
    """Compile one absolute development target into rendered relations."""

    grid = final_render_grid(frame)
    height = len(grid)
    width = len(grid[0])
    if (
        target_horizontal_index < 0
        or target_horizontal_index >= width
        or target_vertical_index < 0
        or target_vertical_index >= height
    ):
        raise S2RoleSelectorError("S2_TARGET_OUTSIDE_RENDERED_FRAME")
    center_palette = grid[target_vertical_index][
        target_horizontal_index
    ]
    candidates = [
        ResolvedRenderedTarget(
            horizontal_index=horizontal_index,
            vertical_index=vertical_index,
        )
        for vertical_index, row in enumerate(grid)
        for horizontal_index, value in enumerate(row)
        if value == center_palette
    ]
    candidate_count_before = len(candidates)
    constraints: list[dict[str, object]] = []
    boundary_constraint_count = 0
    for horizontal_delta, vertical_delta in _offset_order(
        width=width,
        height=height,
    ):
        if len(candidates) == 1:
            break
        target_token = _relation_token(
            grid,
            horizontal_index=target_horizontal_index,
            vertical_index=target_vertical_index,
            horizontal_delta=horizontal_delta,
            vertical_delta=vertical_delta,
        )
        retained = [
            candidate
            for candidate in candidates
            if _relation_token(
                grid,
                horizontal_index=candidate.horizontal_index,
                vertical_index=candidate.vertical_index,
                horizontal_delta=horizontal_delta,
                vertical_delta=vertical_delta,
            )
            == target_token
        ]
        if len(retained) == len(candidates):
            continue
        constraints.append(
            _constraint(
                horizontal_delta=horizontal_delta,
                vertical_delta=vertical_delta,
                token=target_token,
            )
        )
        boundary_constraint_count += int(
            target_token[0] == _BOUNDARY_KIND
        )
        candidates = retained
    if len(candidates) != 1:
        raise S2RoleSelectorError(
            f"S2_TARGET_ROLE_NOT_UNIQUE:{len(candidates)}"
        )
    resolved = candidates[0]
    if (
        resolved.horizontal_index != target_horizontal_index
        or resolved.vertical_index != target_vertical_index
    ):
        raise S2RoleSelectorError("S2_TARGET_ROLE_RESOLVED_WRONG")

    body: dict[str, Any] = {
        "schema_version": S2_ROLE_SELECTOR_SCHEMA_VERSION,
        "selector_class": "TARGET_CENTERED_RENDER_RELATIONS",
        "absolute_target_stored": False,
        "center_palette": center_palette,
        "candidate_count_before": candidate_count_before,
        "candidate_count_after": 1,
        "relative_constraint_count": len(constraints),
        "boundary_constraint_count": boundary_constraint_count,
        "relative_constraints": constraints,
    }
    selector = {
        **body,
        "content_digest": (
            S2_ROLE_SELECTOR_DIGEST_PREFIX + digest_object(body)
        ),
    }
    validate_role_relative_selector(selector)
    return selector


def validate_role_relative_selector(
    selector: Mapping[str, Any],
) -> None:
    """Fail closed on absolute payloads or malformed selector evidence."""

    body = dict(selector)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if (
        claimed
        != S2_ROLE_SELECTOR_DIGEST_PREFIX + digest_object(body)
    ):
        failures.append("S2_ROLE_SELECTOR_DIGEST_INVALID")
    if selector.get("schema_version") != S2_ROLE_SELECTOR_SCHEMA_VERSION:
        failures.append("S2_ROLE_SELECTOR_SCHEMA_INVALID")
    if selector.get("selector_class") != (
        "TARGET_CENTERED_RENDER_RELATIONS"
    ):
        failures.append("S2_ROLE_SELECTOR_CLASS_INVALID")
    if selector.get("absolute_target_stored") is not False:
        failures.append("S2_ROLE_SELECTOR_ABSOLUTE_TARGET_PRESENT")
    if _all_keys(selector).intersection(_FORBIDDEN_ABSOLUTE_KEYS):
        failures.append("S2_ROLE_SELECTOR_ABSOLUTE_KEY_PRESENT")
    raw_constraints = selector.get("relative_constraints")
    if not isinstance(raw_constraints, list):
        failures.append("S2_ROLE_SELECTOR_CONSTRAINTS_INVALID")
        raw_constraints = []
    if (
        selector.get("candidate_count_before") != 1
        and not raw_constraints
    ):
        failures.append("S2_ROLE_SELECTOR_CONSTRAINTS_INVALID")
    for raw_constraint in raw_constraints:
        if not isinstance(raw_constraint, Mapping):
            failures.append("S2_ROLE_SELECTOR_CONSTRAINT_INVALID")
            continue
        try:
            _constraint_token(raw_constraint)
        except (TypeError, ValueError, S2RoleSelectorError):
            failures.append("S2_ROLE_SELECTOR_CONSTRAINT_INVALID")
    if selector.get("candidate_count_after") != 1:
        failures.append("S2_ROLE_SELECTOR_NOT_UNIQUE")
    if selector.get("relative_constraint_count") != len(
        raw_constraints
    ):
        failures.append("S2_ROLE_SELECTOR_CONSTRAINT_COUNT_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))


def resolve_role_relative_selector(
    *,
    selector: Mapping[str, Any],
    frame: FrameDataRaw,
) -> ResolvedRenderedTarget:
    """Resolve exactly one transient target from current rendered content."""

    validate_role_relative_selector(selector)
    grid = final_render_grid(frame)
    center_palette = _integer(
        selector.get("center_palette"),
        "center_palette",
    )
    candidates = [
        ResolvedRenderedTarget(
            horizontal_index=horizontal_index,
            vertical_index=vertical_index,
        )
        for vertical_index, row in enumerate(grid)
        for horizontal_index, value in enumerate(row)
        if value == center_palette
    ]
    if len(candidates) != selector.get("candidate_count_before"):
        raise S2RoleSelectorError(
            "S2_SELECTOR_CANDIDATE_DOMAIN_DIVERGED:"
            f"{len(candidates)}/"
            f"{selector.get('candidate_count_before')}"
        )
    raw_constraints = selector.get("relative_constraints")
    if not isinstance(raw_constraints, list):
        raise TypeError("S2_SELECTOR_CONSTRAINTS_INVALID")
    for raw_constraint in raw_constraints:
        if not isinstance(raw_constraint, Mapping):
            raise TypeError("S2_SELECTOR_CONSTRAINT_INVALID")
        (
            horizontal_delta,
            vertical_delta,
            expected_token,
        ) = _constraint_token(raw_constraint)
        candidates = [
            candidate
            for candidate in candidates
            if _relation_token(
                grid,
                horizontal_index=candidate.horizontal_index,
                vertical_index=candidate.vertical_index,
                horizontal_delta=horizontal_delta,
                vertical_delta=vertical_delta,
            )
            == expected_token
        ]
    if len(candidates) != 1:
        raise S2RoleSelectorError(
            f"S2_SELECTOR_RESOLUTION_NOT_UNIQUE:{len(candidates)}"
        )
    return candidates[0]


__all__ = [
    "ResolvedRenderedTarget",
    "S2RoleSelectorError",
    "S2_ROLE_SELECTOR_DIGEST_PREFIX",
    "S2_ROLE_SELECTOR_SCHEMA_VERSION",
    "compile_role_relative_selector",
    "final_render_grid",
    "resolve_role_relative_selector",
    "validate_role_relative_selector",
]
