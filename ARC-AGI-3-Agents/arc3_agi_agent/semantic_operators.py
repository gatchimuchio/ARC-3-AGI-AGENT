"""Identity-free semantic operators and their passive planner state.

Operators are selected only from rendered structure and the available action
surface.  They return observation-derived action plans; they do not judge,
write memory, emit, inspect source state, or accept task identity.
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import gcd

from .fruit_merge import (
    FRUIT_MERGE_CANDIDATE_OPERATOR,
    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
    FRUIT_MERGE_OPERATOR,
    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
    FruitMergeState,
)
from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object, forbidden_runtime_paths
from .symbolic_rewrite import (
    SYMBOLIC_REWRITE_OPERATOR,
    SymbolicRewriteState,
)
from .visual_explorer import (
    Grid,
    Point,
    VisualAction,
    VisualComponent,
    connected_components,
)

SEMANTIC_PLANNER_FORMAT = "arc3-semantic-planner-v6"
RELATION_TOGGLE_OPERATOR = "relation-constrained-toggle-gf2-v1"
OBJECT_TARGET_CONTROL_OPERATOR = "object-target-cycle-control-v1"


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


@dataclass(frozen=True, slots=True)
class _ObjectTargetParameters:
    left_control_color: int
    right_control_color: int
    state_excluded_colors: frozenset[int]
    minimum_control_area: int
    maximum_control_area: int
    goal_to_corner_width_ratio: int
    target_corner_stride_ratio: int
    paired_far_tolerance_in_corner_widths: int
    near_tolerance_in_corner_widths: int
    far_tolerance_in_corner_widths: int
    vertical_far_tolerance_in_corner_widths: int
    minimum_guided_cost_per_goal: int
    maximum_search_states: int
    maximum_control_cycle_steps: int
    minimum_model_observations_per_action: int
    maximum_model_plan_depth: int
    maximum_mechanism_slots: int
    minimum_dense_model_slots: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _ObjectTargetParameters | None:
        if (
            instruction.operator_id != OBJECT_TARGET_CONTROL_OPERATOR
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

        left_control_color = integer("left_control_color")
        right_control_color = integer("right_control_color")
        state_excluded_colors = colors("state_excluded_colors")
        minimum_control_area = integer("minimum_control_area")
        maximum_control_area = integer("maximum_control_area")
        goal_to_corner_width_ratio = integer(
            "goal_to_corner_width_ratio"
        )
        target_corner_stride_ratio = integer(
            "target_corner_stride_ratio"
        )
        paired_far_tolerance = integer(
            "paired_far_tolerance_in_corner_widths"
        )
        near_tolerance = integer("near_tolerance_in_corner_widths")
        far_tolerance = integer("far_tolerance_in_corner_widths")
        vertical_far_tolerance = integer(
            "vertical_far_tolerance_in_corner_widths"
        )
        minimum_guided_cost_per_goal = integer(
            "minimum_guided_cost_per_goal"
        )
        maximum_search_states = integer("maximum_search_states")
        maximum_control_cycle_steps = integer(
            "maximum_control_cycle_steps"
        )
        minimum_model_observations = integer(
            "minimum_model_observations_per_action"
        )
        maximum_model_plan_depth = integer(
            "maximum_model_plan_depth"
        )
        maximum_mechanism_slots = integer("maximum_mechanism_slots")
        minimum_dense_model_slots = integer(
            "minimum_dense_model_slots"
        )
        if (
            left_control_color is None
            or right_control_color is None
            or left_control_color == right_control_color
            or state_excluded_colors is None
            or left_control_color in state_excluded_colors
            or right_control_color in state_excluded_colors
            or minimum_control_area is None
            or minimum_control_area < 1
            or maximum_control_area is None
            or maximum_control_area < minimum_control_area
            or goal_to_corner_width_ratio is None
            or goal_to_corner_width_ratio < 2
            or target_corner_stride_ratio is None
            or target_corner_stride_ratio <= goal_to_corner_width_ratio
            or paired_far_tolerance is None
            or paired_far_tolerance < 1
            or near_tolerance is None
            or near_tolerance < 1
            or far_tolerance is None
            or far_tolerance <= near_tolerance
            or vertical_far_tolerance is None
            or vertical_far_tolerance <= far_tolerance
            or minimum_guided_cost_per_goal is None
            or minimum_guided_cost_per_goal < 1
            or maximum_search_states is None
            or not 64 <= maximum_search_states <= 16_384
            or maximum_control_cycle_steps is None
            or not 2 <= maximum_control_cycle_steps <= 256
            or minimum_model_observations is None
            or not 1 <= minimum_model_observations <= 64
            or maximum_model_plan_depth is None
            or not 1 <= maximum_model_plan_depth <= 32
            or maximum_mechanism_slots is None
            or not 2 <= maximum_mechanism_slots <= 128
            or minimum_dense_model_slots is None
            or not 2
            <= minimum_dense_model_slots
            <= maximum_mechanism_slots
        ):
            return None
        return cls(
            left_control_color=left_control_color,
            right_control_color=right_control_color,
            state_excluded_colors=state_excluded_colors,
            minimum_control_area=minimum_control_area,
            maximum_control_area=maximum_control_area,
            goal_to_corner_width_ratio=goal_to_corner_width_ratio,
            target_corner_stride_ratio=target_corner_stride_ratio,
            paired_far_tolerance_in_corner_widths=(
                paired_far_tolerance
            ),
            near_tolerance_in_corner_widths=near_tolerance,
            far_tolerance_in_corner_widths=far_tolerance,
            vertical_far_tolerance_in_corner_widths=(
                vertical_far_tolerance
            ),
            minimum_guided_cost_per_goal=(
                minimum_guided_cost_per_goal
            ),
            maximum_search_states=maximum_search_states,
            maximum_control_cycle_steps=maximum_control_cycle_steps,
            minimum_model_observations_per_action=(
                minimum_model_observations
            ),
            maximum_model_plan_depth=maximum_model_plan_depth,
            maximum_mechanism_slots=maximum_mechanism_slots,
            minimum_dense_model_slots=minimum_dense_model_slots,
        )


@dataclass(frozen=True, slots=True)
class _TargetMarker:
    color: int
    center_x2: int
    center_y2: int
    corner_width: int
    corner_height: int
    corner_components: tuple[VisualComponent, ...]


@dataclass(frozen=True, slots=True)
class _TargetRole:
    color: int
    goal_centers_x2_y2: tuple[Point, ...]
    markers: tuple[_TargetMarker, ...]


def _component_center_x2_y2(component: VisualComponent) -> Point:
    return (
        component.bbox[0] + component.bbox[2],
        component.bbox[1] + component.bbox[3],
    )


def _target_markers(
    components: tuple[VisualComponent, ...],
    parameters: _ObjectTargetParameters,
) -> tuple[_TargetMarker, ...]:
    """Find four-corner target glyphs without literal positions."""

    by_descriptor: dict[
        tuple[int, int, int, int],
        list[VisualComponent],
    ] = {}
    for component in components:
        if (
            not component.rectangular
            or component.width != component.height
            or component.width > 8
        ):
            continue
        by_descriptor.setdefault(
            (
                component.color,
                component.width,
                component.height,
                component.area,
            ),
            [],
        ).append(component)

    markers: list[_TargetMarker] = []
    for (
        color,
        corner_width,
        corner_height,
        _area,
    ), candidates in sorted(by_descriptor.items()):
        by_top_left = {
            (component.bbox[0], component.bbox[1]): component
            for component in candidates
        }
        starts_x = sorted({component.bbox[0] for component in candidates})
        starts_y = sorted({component.bbox[1] for component in candidates})
        candidates_for_descriptor: list[_TargetMarker] = []
        for left_x in starts_x:
            for right_x in starts_x:
                if (
                    right_x - left_x
                    != corner_width
                    * parameters.target_corner_stride_ratio
                ):
                    continue
                for top_y in starts_y:
                    for bottom_y in starts_y:
                        if (
                            bottom_y - top_y
                            != corner_height
                            * parameters.target_corner_stride_ratio
                        ):
                            continue
                        points = (
                            (left_x, top_y),
                            (right_x, top_y),
                            (left_x, bottom_y),
                            (right_x, bottom_y),
                        )
                        if any(point not in by_top_left for point in points):
                            continue
                        marker_components = tuple(
                            by_top_left[point] for point in points
                        )
                        candidates_for_descriptor.append(
                            _TargetMarker(
                                color=color,
                                center_x2=(
                                    marker_components[0].bbox[0]
                                    + marker_components[1].bbox[2]
                                ),
                                center_y2=(
                                    marker_components[0].bbox[1]
                                    + marker_components[2].bbox[3]
                                ),
                                corner_width=corner_width,
                                corner_height=corner_height,
                                corner_components=marker_components,
                            )
                        )
        ordered_candidates = tuple(
            sorted(
                candidates_for_descriptor,
                key=lambda marker: (
                    marker.center_y2,
                    marker.center_x2,
                ),
            )
        )
        best: tuple[_TargetMarker, ...] = ()

        def select_disjoint(
            index: int,
            used: frozenset[VisualComponent],
            selected: tuple[_TargetMarker, ...],
        ) -> None:
            nonlocal best
            if len(selected) + len(ordered_candidates) - index < len(best):
                return
            if index == len(ordered_candidates):
                selected_key = tuple(
                    (marker.center_y2, marker.center_x2)
                    for marker in selected
                )
                best_key = tuple(
                    (marker.center_y2, marker.center_x2)
                    for marker in best
                )
                if len(selected) > len(best) or (
                    len(selected) == len(best)
                    and selected_key < best_key
                ):
                    best = selected
                return
            candidate = ordered_candidates[index]
            candidate_components = frozenset(
                candidate.corner_components
            )
            if candidate_components.isdisjoint(used):
                select_disjoint(
                    index + 1,
                    used | candidate_components,
                    (*selected, candidate),
                )
            select_disjoint(index + 1, used, selected)

        select_disjoint(0, frozenset(), ())
        markers.extend(best)
    return tuple(
        sorted(
            markers,
            key=lambda item: (
                item.color,
                item.center_y2,
                item.center_x2,
            ),
        )
    )


def _target_roles(
    components: tuple[VisualComponent, ...],
    parameters: _ObjectTargetParameters,
) -> tuple[_TargetRole, ...]:
    markers = _target_markers(components, parameters)
    roles: list[_TargetRole] = []
    for color in sorted({marker.color for marker in markers}):
        color_markers = tuple(
            marker for marker in markers if marker.color == color
        )
        marker_components = {
            component
            for marker in color_markers
            for component in marker.corner_components
        }
        expected_widths = {
            marker.corner_width
            * parameters.goal_to_corner_width_ratio
            for marker in color_markers
        }
        expected_heights = {
            marker.corner_height
            * parameters.goal_to_corner_width_ratio
            for marker in color_markers
        }
        goals = tuple(
            component
            for component in components
            if (
                component.color == color
                and component not in marker_components
                and component.rectangular
                and component.width in expected_widths
                and component.height in expected_heights
            )
        )
        if len(goals) != len(color_markers) or not goals:
            continue
        roles.append(
            _TargetRole(
                color=color,
                goal_centers_x2_y2=tuple(
                    sorted(
                        (
                            _component_center_x2_y2(component)
                            for component in goals
                        ),
                        key=lambda point: (point[1], point[0]),
                    )
                ),
                markers=tuple(
                    sorted(
                        color_markers,
                        key=lambda marker: (
                            marker.center_y2,
                            marker.center_x2,
                        ),
                    )
                ),
            )
        )
    return tuple(roles)


def _control_components(
    components: tuple[VisualComponent, ...],
    parameters: _ObjectTargetParameters,
) -> tuple[
    tuple[VisualComponent, ...],
    tuple[VisualComponent, ...],
]:
    """Select compact non-rectangular controls by P-provided role colors."""

    maximum_scale = 8

    def eligible(
        component: VisualComponent,
        expected_color: int,
    ) -> bool:
        scale = gcd(component.width, component.height)
        normalized_area = component.area // max(1, scale * scale)
        return (
            component.color == expected_color
            and not component.rectangular
            and parameters.minimum_control_area
            <= normalized_area
            <= parameters.maximum_control_area
            and 1 <= scale <= maximum_scale
            and max(component.width, component.height)
            <= 8 * scale
        )

    left = tuple(
        sorted(
            (
                component
                for component in components
                if eligible(component, parameters.left_control_color)
            ),
            key=lambda item: (item.bbox[1], item.bbox[0]),
        )
    )
    right = tuple(
        sorted(
            (
                component
                for component in components
                if eligible(component, parameters.right_control_color)
            ),
            key=lambda item: (item.bbox[1], item.bbox[0]),
        )
    )
    return left, right


def _row_pairs(
    left: tuple[VisualComponent, ...],
    right: tuple[VisualComponent, ...],
) -> tuple[tuple[VisualComponent, VisualComponent], ...]:
    pairs: list[tuple[VisualComponent, VisualComponent]] = []
    remaining = list(right)
    for left_control in left:
        left_y2 = left_control.bbox[1] + left_control.bbox[3]
        compatible = sorted(
            remaining,
            key=lambda right_control: (
                abs(
                    left_y2
                    - right_control.bbox[1]
                    - right_control.bbox[3]
                ),
                right_control.bbox[0],
            ),
        )
        if not compatible:
            continue
        right_control = compatible[0]
        right_y2 = right_control.bbox[1] + right_control.bbox[3]
        tolerance = max(
            left_control.height,
            right_control.height,
        )
        if abs(left_y2 - right_y2) > tolerance:
            continue
        remaining.remove(right_control)
        pairs.append((left_control, right_control))
    return tuple(
        sorted(
            pairs,
            key=lambda pair: (
                pair[0].bbox[1] + pair[0].bbox[3],
                pair[0].bbox[0],
            ),
        )
    )


def _single_role_horizontal_control(
    role: _TargetRole,
    left: tuple[VisualComponent, ...],
    right: tuple[VisualComponent, ...],
) -> VisualComponent | None:
    if (
        len(role.goal_centers_x2_y2) != 1
        or len(role.markers) != 1
        or len(left) != 1
        or len(right) != 1
    ):
        return None
    goal_x2, goal_y2 = role.goal_centers_x2_y2[0]
    marker = role.markers[0]
    vertical_tolerance = 2 * marker.corner_height
    if abs(goal_y2 - marker.center_y2) > vertical_tolerance:
        return None
    if goal_x2 > marker.center_x2:
        return left[0]
    if goal_x2 < marker.center_x2:
        return right[0]
    return None


def _paired_role_control(
    role: _TargetRole,
    pairs: tuple[tuple[VisualComponent, VisualComponent], ...],
    parameters: _ObjectTargetParameters,
) -> VisualComponent | None:
    """Choose one current-frame action for a two-object row controller."""

    if (
        len(role.goal_centers_x2_y2) != 2
        or len(role.markers) != 2
        or len(pairs) != 3
    ):
        return None
    upper_goal, lower_goal = role.goal_centers_x2_y2
    marker_x2 = round(
        sum(marker.center_x2 for marker in role.markers)
        / len(role.markers)
    )
    marker_ys2 = sorted(marker.center_y2 for marker in role.markers)
    upper_marker_y2 = marker_ys2[0]
    corner_width = min(
        marker.corner_width for marker in role.markers
    )
    far = (
        2
        * parameters.paired_far_tolerance_in_corner_widths
        * corner_width
    )

    if upper_goal[0] < marker_x2:
        return pairs[0][1]
    if (
        upper_goal[1] < upper_marker_y2
        and lower_goal[0] <= marker_x2 - far
    ):
        return pairs[2][1]
    if upper_goal[1] < upper_marker_y2:
        return pairs[0][1]
    if lower_goal[0] < marker_x2:
        return pairs[2][1]
    return None


def _dual_role_control(
    roles: tuple[_TargetRole, ...],
    left: tuple[VisualComponent, ...],
    right: tuple[VisualComponent, ...],
    parameters: _ObjectTargetParameters,
) -> VisualComponent | None:
    """Choose one state-dependent control for two distinct target roles."""

    if (
        len(roles) != 2
        or any(
            len(role.goal_centers_x2_y2) != 1
            or len(role.markers) != 1
            for role in roles
        )
    ):
        return None
    ordered_roles = sorted(roles, key=lambda role: role.color)
    first, second = ordered_roles
    first_goal = first.goal_centers_x2_y2[0]
    first_marker = first.markers[0]
    second_goal = second.goal_centers_x2_y2[0]
    second_marker = second.markers[0]
    dx_first = first_marker.center_x2 - first_goal[0]
    dy_first = first_marker.center_y2 - first_goal[1]
    dx_second = second_marker.center_x2 - second_goal[0]
    dy_second = second_marker.center_y2 - second_goal[1]
    corner_width = min(
        first_marker.corner_width,
        second_marker.corner_width,
    )
    near = (
        2
        * parameters.near_tolerance_in_corner_widths
        * corner_width
    )
    far = (
        2
        * parameters.far_tolerance_in_corner_widths
        * corner_width
    )
    vertical_far = (
        2
        * parameters.vertical_far_tolerance_in_corner_widths
        * corner_width
    )

    if len(left) == 2 and len(right) == 2:
        controls = (*left, *right)
        center_ys2 = tuple(
            component.bbox[1] + component.bbox[3]
            for component in controls
        )
        if max(center_ys2) - min(center_ys2) > max(
            component.height for component in controls
        ):
            return None
        low_left, high_left = sorted(left, key=lambda item: item.bbox[0])
        if -dx_first > far:
            return high_left
        if -dx_first > near or dx_second > far:
            return low_left
        if abs(dx_second) + abs(dy_second) > 0:
            return high_left
        return low_left

    if len(left) < 4 or len(right) < 4:
        return None
    horizontal_pairs = _row_pairs(left, right)
    if not horizontal_pairs:
        return None
    top_y = min(pair[0].bbox[1] for pair in horizontal_pairs)
    top_row = sorted(
        (
            pair
            for pair in horizontal_pairs
            if pair[0].bbox[1] == top_y
        ),
        key=lambda pair: pair[0].bbox[0],
    )
    if not top_row:
        return None
    top_right = top_row[0][1]
    below = sorted(
        (
            component
            for component in right
            if component.bbox[1] > top_y
        ),
        key=lambda component: (
            component.bbox[0],
            component.bbox[1],
        ),
    )
    if not below:
        return None
    align_second = below[0]
    paired_left = sorted(
        (
            component
            for component in left
            if component.bbox[0] == align_second.bbox[0]
            and component.bbox[1] < align_second.bbox[1]
        ),
        key=lambda component: component.bbox[1],
        reverse=True,
    )
    if not paired_left:
        return None
    lower_first = paired_left[0]
    if dx_first > near:
        return top_right
    if dy_second < 0 and dx_second > 0:
        return align_second
    if dx_first > 0:
        return top_right
    if dx_second > 0:
        if dy_first > vertical_far:
            return lower_first
        return top_right
    if dy_first > 0:
        return lower_first
    return None


def _object_target_action(
    component: VisualComponent,
    instruction: SemanticOperatorInstruction,
) -> VisualAction:
    x, y = component.click_point
    return VisualAction(
        key="semantic-object-target:"
        + digest_object(
            {
                "operator": OBJECT_TARGET_CONTROL_OPERATOR,
                "component": {
                    "color": component.color,
                    "bbox": component.bbox,
                    "area": component.area,
                },
            }
        )[:20],
        action_id=instruction.action_id,
        group=0,
        x=x,
        y=y,
        evidence=(
            OBJECT_TARGET_CONTROL_OPERATOR,
            f"operator-prototype:{OBJECT_TARGET_CONTROL_OPERATOR}",
            "rendered-target-marker",
            "rendered-goal-displacement",
            "single-step-reobservation-required",
            *instruction.provenance,
        ),
    )


def _object_target_parts(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[
    _ObjectTargetParameters,
    tuple[VisualComponent, ...],
    tuple[_TargetRole, ...],
    tuple[VisualComponent, ...],
    tuple[VisualComponent, ...],
] | None:
    parameters = _ObjectTargetParameters.from_instruction(instruction)
    if parameters is None or instruction.action_id not in available_actions:
        return None
    components = connected_components(grid)
    roles = _target_roles(components, parameters)
    left, right = _control_components(components, parameters)
    if not roles or not (left or right):
        return None
    return parameters, components, roles, left, right


@dataclass(frozen=True, slots=True)
class _TargetSearchSurface:
    state_signature: str
    target_cost: int
    cost_guidance_enabled: bool
    actions: tuple[VisualAction, ...]
    maximum_states: int
    coordinate_descent_enabled: bool
    maximum_control_cycle_steps: int
    mechanism_positions: tuple[Point, ...]
    mechanism_colors: tuple[int, ...]
    target_requirements: tuple[tuple[int, int], ...]
    minimum_model_observations_per_action: int
    maximum_model_plan_depth: int
    minimum_dense_model_slots: int


def _target_search_surface(
    parts: tuple[
        _ObjectTargetParameters,
        tuple[VisualComponent, ...],
        tuple[_TargetRole, ...],
        tuple[VisualComponent, ...],
        tuple[VisualComponent, ...],
    ],
    instruction: SemanticOperatorInstruction,
) -> _TargetSearchSurface | None:
    parameters, _components, roles, left, right = parts
    controls = frozenset((*left, *right))
    descriptors: list[tuple[object, ...]] = []
    target_cost = 0
    target_count = 0
    for role in roles:
        if (
            role.color in parameters.state_excluded_colors
            or not role.markers
        ):
            continue
        scale = max(
            1,
            min(
                min(marker.corner_width, marker.corner_height)
                for marker in role.markers
            ),
        )
        anchor_x2 = min(marker.center_x2 for marker in role.markers)
        anchor_y2 = min(marker.center_y2 for marker in role.markers)
        marker_positions = tuple(
            sorted(
                (
                    (marker.center_x2 - anchor_x2) // scale,
                    (marker.center_y2 - anchor_y2) // scale,
                )
                for marker in role.markers
            )
        )
        goal_positions = tuple(
            sorted(
                (
                    (goal_x2 - anchor_x2) // scale,
                    (goal_y2 - anchor_y2) // scale,
                )
                for goal_x2, goal_y2 in role.goal_centers_x2_y2
            )
        )
        descriptors.append(
            (
                len(marker_positions),
                len(goal_positions),
                marker_positions,
                goal_positions,
            )
        )
        costs = tuple(
            tuple(
                abs(goal_x - marker_x) + abs(goal_y - marker_y)
                for marker_x, marker_y in marker_positions
            )
            for goal_x, goal_y in goal_positions
        )
        matching_costs: dict[int, int] = {0: 0}
        for goal_costs in costs:
            next_costs: dict[int, int] = {}
            for used_mask, accumulated in matching_costs.items():
                for marker_index, cost in enumerate(goal_costs):
                    marker_bit = 1 << marker_index
                    if used_mask & marker_bit:
                        continue
                    next_mask = used_mask | marker_bit
                    candidate = accumulated + cost
                    previous = next_costs.get(next_mask)
                    if previous is None or candidate < previous:
                        next_costs[next_mask] = candidate
            matching_costs = next_costs
        complete_mask = (1 << len(marker_positions)) - 1
        role_cost = matching_costs.get(complete_mask)
        if role_cost is None:
            return None
        target_cost += role_cost
        target_count += len(goal_positions)
    normalized_role_descriptors = tuple(sorted(descriptors))
    if not normalized_role_descriptors:
        return None
    global_scale = max(
        1,
        min(
            min(marker.corner_width, marker.corner_height)
            for role in roles
            for marker in role.markers
        ),
    )
    global_anchor_x2 = min(
        marker.center_x2
        for role in roles
        for marker in role.markers
    )
    global_anchor_y2 = min(
        marker.center_y2
        for role in roles
        for marker in role.markers
    )
    phase_descriptors = tuple(
        sorted(
            (
                component.color,
                component.area // max(1, global_scale * global_scale),
                (component.bbox[0] + component.bbox[2] - global_anchor_x2)
                // global_scale,
                (component.bbox[1] + component.bbox[3] - global_anchor_y2)
                // global_scale,
                component.width // global_scale,
                component.height // global_scale,
            )
            for component in _components
            if (
                component not in controls
                and component.color
                not in {
                    parameters.left_control_color,
                    parameters.right_control_color,
                }
                and component.color
                not in parameters.state_excluded_colors
                and component.rectangular
                and component.width == component.height
                and component.area <= 144
                and component.width <= 12
                and component.height <= 12
            )
        )
    )
    if not phase_descriptors:
        return None
    state_descriptors = (
        ("roles", normalized_role_descriptors),
        ("phase", phase_descriptors),
    )
    mechanism_by_position: dict[Point, int] = {}
    mechanism_valid = True
    for component in _components:
        if (
            component in controls
            or component.color
            in {
                parameters.left_control_color,
                parameters.right_control_color,
                *parameters.state_excluded_colors,
            }
            or not component.rectangular
            or component.width != 2 * global_scale
            or component.height != 2 * global_scale
            or component.area != 4 * global_scale * global_scale
        ):
            continue
        position = (
            (
                component.bbox[0]
                + component.bbox[2]
                - global_anchor_x2
            )
            // global_scale,
            (
                component.bbox[1]
                + component.bbox[3]
                - global_anchor_y2
            )
            // global_scale,
        )
        if position in mechanism_by_position:
            mechanism_valid = False
            break
        mechanism_by_position[position] = component.color
    mechanism_positions = tuple(sorted(mechanism_by_position))
    requirement_by_position = {
        (
            (marker.center_x2 - global_anchor_x2) // global_scale,
            (marker.center_y2 - global_anchor_y2) // global_scale,
        ): role.color
        for role in roles
        for marker in role.markers
    }
    if (
        not mechanism_valid
        or not requirement_by_position
        or any(
            position not in mechanism_by_position
            for position in requirement_by_position
        )
        or not 2
        <= len(mechanism_positions)
        <= parameters.maximum_mechanism_slots
    ):
        mechanism_positions = ()
        mechanism_colors: tuple[int, ...] = ()
        target_requirements: tuple[tuple[int, int], ...] = ()
    else:
        mechanism_colors = tuple(
            mechanism_by_position[position]
            for position in mechanism_positions
        )
        position_index = {
            position: index
            for index, position in enumerate(mechanism_positions)
        }
        target_requirements = tuple(
            sorted(
                (
                    position_index[position],
                    color,
                )
                for position, color in requirement_by_position.items()
            )
        )
    actions = tuple(
        _object_target_action(component, instruction)
        for component in sorted(
            controls,
            key=lambda item: (
                item.bbox[1],
                item.bbox[0],
                item.color,
                item.area,
            ),
        )
    )
    if not actions:
        return None
    return _TargetSearchSurface(
        state_signature="target-control-state:"
        + digest_object(state_descriptors)[:24],
        target_cost=target_cost,
        cost_guidance_enabled=(
            target_cost
            >= parameters.minimum_guided_cost_per_goal
            * max(1, target_count)
        ),
        actions=actions,
        maximum_states=parameters.maximum_search_states,
        coordinate_descent_enabled=bool(left) != bool(right),
        maximum_control_cycle_steps=(
            parameters.maximum_control_cycle_steps
        ),
        mechanism_positions=mechanism_positions,
        mechanism_colors=mechanism_colors,
        target_requirements=target_requirements,
        minimum_model_observations_per_action=(
            parameters.minimum_model_observations_per_action
        ),
        maximum_model_plan_depth=(
            parameters.maximum_model_plan_depth
        ),
        minimum_dense_model_slots=parameters.minimum_dense_model_slots,
    )


def object_target_control_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Return one observation-derived control action, never a fixed route."""

    parts = _object_target_parts(
        grid,
        available_actions,
        instruction,
    )
    if parts is None:
        return ()
    parameters, _components, roles, left, right = parts

    selected: VisualComponent | None = None
    if len(roles) == 1 and left and right:
        selected = _single_role_horizontal_control(
            roles[0],
            left,
            right,
        )
        if selected is None:
            selected = _paired_role_control(
                roles[0],
                _row_pairs(left, right),
                parameters,
            )
    if selected is None:
        selected = _dual_role_control(
            roles,
            left,
            right,
            parameters,
        )
    if selected is None:
        return ()
    return (_object_target_action(selected, instruction),)


def _minimum_geometric_permutation(
    positions: tuple[Point, ...],
    candidates: tuple[tuple[int, ...], ...],
) -> tuple[int, ...] | None:
    """Resolve one deterministic minimum-distance perfect matching."""

    size = len(positions)
    if (
        size == 0
        or len(candidates) != size
        or any(
            not row
            or any(source < 0 or source >= size for source in row)
            for row in candidates
        )
    ):
        return None
    forbidden_cost = 10**9
    costs = tuple(
        tuple(
            (
                abs(positions[destination][0] - positions[source][0])
                + abs(
                    positions[destination][1]
                    - positions[source][1]
                )
                if source in candidates[destination]
                else forbidden_cost
            )
            for source in range(size)
        )
        for destination in range(size)
    )

    # Hungarian assignment. Rows are destination slots; columns are sources.
    row_potential = [0] * (size + 1)
    column_potential = [0] * (size + 1)
    matched_row = [0] * (size + 1)
    predecessor = [0] * (size + 1)
    for row in range(1, size + 1):
        matched_row[0] = row
        column = 0
        minimum = [forbidden_cost] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[column] = True
            active_row = matched_row[column]
            delta = forbidden_cost
            next_column = 0
            for candidate_column in range(1, size + 1):
                if used[candidate_column]:
                    continue
                reduced = (
                    costs[active_row - 1][candidate_column - 1]
                    - row_potential[active_row]
                    - column_potential[candidate_column]
                )
                if reduced < minimum[candidate_column]:
                    minimum[candidate_column] = reduced
                    predecessor[candidate_column] = column
                if minimum[candidate_column] < delta:
                    delta = minimum[candidate_column]
                    next_column = candidate_column
            if delta >= forbidden_cost:
                return None
            for candidate_column in range(size + 1):
                if used[candidate_column]:
                    row_potential[matched_row[candidate_column]] += delta
                    column_potential[candidate_column] -= delta
                else:
                    minimum[candidate_column] -= delta
            column = next_column
            if matched_row[column] == 0:
                break
        while True:
            previous_column = predecessor[column]
            matched_row[column] = matched_row[previous_column]
            column = previous_column
            if column == 0:
                break
    permutation = [0] * size
    for source_column in range(1, size + 1):
        destination_row = matched_row[source_column]
        if destination_row:
            permutation[destination_row - 1] = source_column - 1
    if any(
        source not in candidates[destination]
        for destination, source in enumerate(permutation)
    ):
        return None
    return tuple(permutation)


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
                    f"operator-prototype:{RELATION_TOGGLE_OPERATOR}",
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
    target_initial_state: str = ""
    target_pending_state: str = ""
    target_pending_action: str = ""
    target_cost_guidance_enabled: bool = False
    target_transitions: dict[str, dict[str, str]] = field(
        default_factory=dict
    )
    target_state_costs: dict[str, int] = field(default_factory=dict)
    target_safe_actions: set[str] = field(default_factory=set)
    target_hazards: dict[str, set[str]] = field(default_factory=dict)
    target_observation_count: int = 0
    target_route_count: int = 0
    target_coordinate_phase: str = ""
    target_coordinate_action_order: tuple[str, ...] = ()
    target_coordinate_action_index: int = 0
    target_coordinate_pass_start_cost: int = 0
    target_coordinate_base_state: str = ""
    target_coordinate_base_cost: int = 0
    target_coordinate_probe_step: int = 0
    target_coordinate_best_step: int = 0
    target_coordinate_best_cost: int = 0
    target_coordinate_commit_remaining: int = 0
    target_coordinate_completed_passes: int = 0
    target_coordinate_abandoned: bool = False
    target_model_positions: tuple[Point, ...] = ()
    target_model_requirements: tuple[tuple[int, int], ...] = ()
    target_pending_mechanism: tuple[int, ...] = ()
    target_permutation_candidates: dict[
        str,
        tuple[tuple[int, ...], ...],
    ] = field(default_factory=dict)
    target_permutation_observations: dict[str, int] = field(
        default_factory=dict
    )
    target_model_plan: list[str] = field(default_factory=list)
    target_model_expected_colors: tuple[int, ...] = ()
    target_model_plan_count: int = 0
    target_model_mismatch_count: int = 0
    target_model_abandoned: bool = False
    fruit_merge: FruitMergeState = field(
        default_factory=FruitMergeState
    )
    symbolic_rewrite: SymbolicRewriteState = field(
        default_factory=SymbolicRewriteState
    )

    def _clear_active_plan(self) -> None:
        self.queue.clear()
        self.active_operator = ""
        self.active_instruction_digest = ""
        self.active_plan_signature = ""
        self.source_signature = ""

    def _reset_target_coordinate(
        self,
        *,
        abandoned: bool = False,
    ) -> None:
        self.target_coordinate_phase = ""
        self.target_coordinate_action_order = ()
        self.target_coordinate_action_index = 0
        self.target_coordinate_pass_start_cost = 0
        self.target_coordinate_base_state = ""
        self.target_coordinate_base_cost = 0
        self.target_coordinate_probe_step = 0
        self.target_coordinate_best_step = 0
        self.target_coordinate_best_cost = 0
        self.target_coordinate_commit_remaining = 0
        self.target_coordinate_completed_passes = 0
        self.target_coordinate_abandoned = abandoned

    def _reset_target_model(self) -> None:
        self.target_model_positions = ()
        self.target_model_requirements = ()
        self.target_pending_mechanism = ()
        self.target_permutation_candidates.clear()
        self.target_permutation_observations.clear()
        self.target_model_plan.clear()
        self.target_model_expected_colors = ()
        self.target_model_plan_count = 0
        self.target_model_mismatch_count = 0
        self.target_model_abandoned = False

    def reset_after_progress(self) -> None:
        self._clear_active_plan()
        self.target_initial_state = ""
        self.target_pending_state = ""
        self.target_pending_action = ""
        self.target_cost_guidance_enabled = False
        self.target_transitions.clear()
        self.target_state_costs.clear()
        self.target_safe_actions.clear()
        self.target_hazards.clear()
        self.target_observation_count = 0
        self.target_route_count = 0
        self._reset_target_coordinate()
        self._reset_target_model()
        self.fruit_merge.reset()
        self.symbolic_rewrite.reset()

    def record_target_hazard(self) -> bool | None:
        """Retain a failed pending edge without granting judgment authority."""

        classified: bool | None = None
        if self.target_pending_state and self.target_pending_action:
            classified = (
                self.target_pending_action not in self.target_safe_actions
            )
            if classified:
                self.target_hazards.setdefault(
                    self.target_pending_state,
                    set(),
                ).add(self.target_pending_action)
        self.target_pending_state = ""
        self.target_pending_action = ""
        self.target_pending_mechanism = ()
        self.target_model_plan.clear()
        self.target_model_expected_colors = ()
        if classified:
            self.target_model_abandoned = True
        self._reset_target_coordinate(abandoned=classified is True)
        return classified

    def invalidate_active_plan(self, *, block: bool = True) -> None:
        if block and self.active_plan_signature:
            self.blocked_plan_signatures.add(self.active_plan_signature)
        self._clear_active_plan()
        self.target_pending_state = ""
        self.target_pending_action = ""
        self.target_pending_mechanism = ()
        self.target_model_plan.clear()
        self.target_model_expected_colors = ()

    def _observe_target_surface(
        self,
        surface: _TargetSearchSurface,
    ) -> bool:
        self.target_state_costs[surface.state_signature] = (
            surface.target_cost
        )
        if not self.target_initial_state:
            self.target_initial_state = surface.state_signature
            self.target_cost_guidance_enabled = (
                surface.cost_guidance_enabled
            )
        self._bind_target_model_surface(surface)
        if not self.target_pending_state or not self.target_pending_action:
            return False
        self.target_transitions.setdefault(
            self.target_pending_state,
            {},
        )[self.target_pending_action] = surface.state_signature
        self.target_safe_actions.add(self.target_pending_action)
        self._observe_target_model(
            surface,
            pending_action=self.target_pending_action,
        )
        self._observe_target_coordinate(
            surface,
            self.target_pending_action,
        )
        self.target_pending_state = ""
        self.target_pending_action = ""
        self.target_observation_count += 1
        return True

    def _bind_target_model_surface(
        self,
        surface: _TargetSearchSurface,
    ) -> None:
        if (
            self.target_model_abandoned
            or not surface.mechanism_positions
            or not surface.mechanism_colors
            or not surface.target_requirements
        ):
            return
        if not self.target_model_positions:
            self.target_model_positions = surface.mechanism_positions
            self.target_model_requirements = (
                surface.target_requirements
            )
            return
        if (
            surface.mechanism_positions != self.target_model_positions
            or surface.target_requirements
            != self.target_model_requirements
        ):
            self.target_model_plan.clear()
            self.target_model_expected_colors = ()
            self.target_model_abandoned = True

    def _observe_target_model(
        self,
        surface: _TargetSearchSurface,
        *,
        pending_action: str,
    ) -> None:
        if (
            self.target_model_abandoned
            or not self.target_model_positions
            or surface.mechanism_positions != self.target_model_positions
            or len(self.target_pending_mechanism)
            != len(surface.mechanism_colors)
        ):
            self.target_pending_mechanism = ()
            self.target_model_expected_colors = ()
            return
        if (
            self.target_model_expected_colors
            and surface.mechanism_colors
            != self.target_model_expected_colors
        ):
            self.target_model_mismatch_count += 1
            self.target_model_plan.clear()
        self.target_model_expected_colors = ()

        slot_count = len(surface.mechanism_colors)
        previous = self.target_permutation_candidates.get(
            pending_action,
            tuple(
                tuple(range(slot_count))
                for _destination in range(slot_count)
            ),
        )
        if len(previous) != slot_count:
            self.target_model_abandoned = True
            self.target_pending_mechanism = ()
            self.target_model_plan.clear()
            return
        refined = tuple(
            tuple(
                source
                for source in previous[destination]
                if self.target_pending_mechanism[source]
                == surface.mechanism_colors[destination]
            )
            for destination in range(slot_count)
        )
        if (
            _minimum_geometric_permutation(
                self.target_model_positions,
                refined,
            )
            is None
        ):
            self.target_model_abandoned = True
            self.target_pending_mechanism = ()
            self.target_model_plan.clear()
            return
        self.target_permutation_candidates[pending_action] = refined
        self.target_permutation_observations[pending_action] = (
            self.target_permutation_observations.get(
                pending_action,
                0,
            )
            + 1
        )
        self.target_model_plan.clear()
        self.target_pending_mechanism = ()

    def _target_model_permutations(
        self,
        surface: _TargetSearchSurface,
    ) -> dict[str, tuple[int, ...]] | None:
        if (
            self.target_model_abandoned
            or surface.coordinate_descent_enabled
            or not self.target_model_positions
            or surface.mechanism_positions != self.target_model_positions
            or (
                self.target_cost_guidance_enabled
                and len(surface.mechanism_positions)
                < surface.minimum_dense_model_slots
            )
        ):
            return None
        permutations: dict[str, tuple[int, ...]] = {}
        for action in surface.actions:
            if (
                self.target_permutation_observations.get(action.key, 0)
                < surface.minimum_model_observations_per_action
            ):
                return None
            candidates = self.target_permutation_candidates.get(
                action.key
            )
            if candidates is None:
                return None
            permutation = _minimum_geometric_permutation(
                self.target_model_positions,
                candidates,
            )
            if permutation is None:
                return None
            permutations[action.key] = permutation
        return permutations

    def _target_model_goal(
        self,
        colors: tuple[int, ...],
    ) -> bool:
        return bool(self.target_model_requirements) and all(
            0 <= index < len(colors) and colors[index] == color
            for index, color in self.target_model_requirements
        )

    @staticmethod
    def _apply_target_permutation(
        colors: tuple[int, ...],
        permutation: tuple[int, ...],
    ) -> tuple[int, ...]:
        return tuple(colors[source] for source in permutation)

    def _compile_target_model_plan(
        self,
        surface: _TargetSearchSurface,
        permutations: Mapping[str, tuple[int, ...]],
    ) -> tuple[str, ...]:
        initial = surface.mechanism_colors
        if not initial or self._target_model_goal(initial):
            return ()
        ordered_keys = tuple(
            action.key
            for action in sorted(
                surface.actions,
                key=lambda action: (
                    -(action.y if action.y is not None else -1),
                    -(action.x if action.x is not None else -1),
                    action.key,
                ),
            )
        )
        queue: deque[tuple[tuple[int, ...], tuple[str, ...]]] = deque(
            ((initial, ()),)
        )
        visited = {initial}
        while queue and len(visited) <= surface.maximum_states:
            colors, path = queue.popleft()
            if len(path) >= surface.maximum_model_plan_depth:
                continue
            for key in ordered_keys:
                next_colors = self._apply_target_permutation(
                    colors,
                    permutations[key],
                )
                if next_colors in visited:
                    continue
                next_path = (*path, key)
                if self._target_model_goal(next_colors):
                    return next_path
                visited.add(next_colors)
                if len(visited) > surface.maximum_states:
                    break
                queue.append((next_colors, next_path))
        return ()

    def _target_model_action(
        self,
        surface: _TargetSearchSurface,
    ) -> VisualAction | None:
        permutations = self._target_model_permutations(surface)
        if permutations is None:
            return None
        if not self.target_model_plan:
            self.target_model_plan = list(
                self._compile_target_model_plan(
                    surface,
                    permutations,
                )
            )
            if self.target_model_plan:
                self.target_model_plan_count += 1
        if not self.target_model_plan:
            return None
        action_by_key = {
            action.key: action for action in surface.actions
        }
        action_key = self.target_model_plan.pop(0)
        action = action_by_key.get(action_key)
        if action is None:
            self.target_model_plan.clear()
            return None
        self.target_model_expected_colors = (
            self._apply_target_permutation(
                surface.mechanism_colors,
                permutations[action_key],
            )
        )
        return action

    def _target_model_probe_action(
        self,
        surface: _TargetSearchSurface,
    ) -> VisualAction | None:
        if (
            self.target_model_abandoned
            or surface.coordinate_descent_enabled
            or not self.target_model_positions
            or surface.mechanism_positions != self.target_model_positions
            or (
                self.target_cost_guidance_enabled
                and len(surface.mechanism_positions)
                < surface.minimum_dense_model_slots
            )
        ):
            return None
        observation_count = sum(
            self.target_permutation_observations.values()
        )
        if not surface.actions:
            return None
        return min(
            surface.actions,
            key=lambda action: (
                self.target_permutation_observations.get(
                    action.key,
                    0,
                ),
                digest_object(
                    {
                        "state": surface.state_signature,
                        "observations": observation_count,
                        "action": action.key,
                    }
                ),
                action.key,
            ),
        )

    def _start_target_coordinate_probe(
        self,
        surface: _TargetSearchSurface,
        *,
        action_index: int,
    ) -> None:
        self.target_coordinate_phase = "probe"
        self.target_coordinate_action_index = action_index
        self.target_coordinate_base_state = surface.state_signature
        self.target_coordinate_base_cost = surface.target_cost
        self.target_coordinate_probe_step = 0
        self.target_coordinate_best_step = 0
        self.target_coordinate_best_cost = surface.target_cost
        self.target_coordinate_commit_remaining = 0

    def _begin_target_coordinate_descent(
        self,
        surface: _TargetSearchSurface,
    ) -> None:
        self.target_coordinate_action_order = tuple(
            action.key for action in surface.actions
        )
        self.target_coordinate_pass_start_cost = surface.target_cost
        self.target_coordinate_completed_passes = 0
        self.target_coordinate_abandoned = False
        self._start_target_coordinate_probe(surface, action_index=0)

    def _advance_target_coordinate_control(
        self,
        surface: _TargetSearchSurface,
    ) -> None:
        next_index = self.target_coordinate_action_index + 1
        if next_index < len(self.target_coordinate_action_order):
            self._start_target_coordinate_probe(
                surface,
                action_index=next_index,
            )
            return
        self.target_coordinate_completed_passes += 1
        if surface.target_cost < self.target_coordinate_pass_start_cost:
            self.target_coordinate_pass_start_cost = surface.target_cost
            self._start_target_coordinate_probe(
                surface,
                action_index=0,
            )
            return
        self.target_coordinate_phase = "done"

    def _observe_target_coordinate(
        self,
        surface: _TargetSearchSurface,
        pending_action: str,
    ) -> None:
        if (
            not surface.coordinate_descent_enabled
            or self.target_coordinate_abandoned
            or self.target_coordinate_phase not in {"probe", "commit"}
            or not self.target_coordinate_action_order
            or self.target_coordinate_action_index
            >= len(self.target_coordinate_action_order)
            or pending_action
            != self.target_coordinate_action_order[
                self.target_coordinate_action_index
            ]
        ):
            return
        current_order = tuple(action.key for action in surface.actions)
        if current_order != self.target_coordinate_action_order:
            self.target_coordinate_phase = "done"
            self.target_coordinate_abandoned = True
            return
        if self.target_coordinate_phase == "commit":
            self.target_coordinate_commit_remaining -= 1
            if self.target_coordinate_commit_remaining <= 0:
                self._advance_target_coordinate_control(surface)
            return

        self.target_coordinate_probe_step += 1
        if surface.target_cost < self.target_coordinate_best_cost:
            self.target_coordinate_best_cost = surface.target_cost
            self.target_coordinate_best_step = (
                self.target_coordinate_probe_step
            )
        if surface.state_signature == self.target_coordinate_base_state:
            if self.target_coordinate_best_step:
                self.target_coordinate_phase = "commit"
                self.target_coordinate_commit_remaining = (
                    self.target_coordinate_best_step
                )
            else:
                self._advance_target_coordinate_control(surface)
            return
        if (
            self.target_coordinate_probe_step
            >= surface.maximum_control_cycle_steps
        ):
            self.target_coordinate_phase = "done"
            self.target_coordinate_abandoned = True

    def _target_coordinate_action(
        self,
        surface: _TargetSearchSurface,
    ) -> VisualAction | None:
        if (
            not surface.coordinate_descent_enabled
            or self.target_coordinate_abandoned
            or self.target_coordinate_phase == "done"
        ):
            return None
        if not self.target_coordinate_phase:
            self._begin_target_coordinate_descent(surface)
        current_order = tuple(action.key for action in surface.actions)
        if current_order != self.target_coordinate_action_order:
            self.target_coordinate_phase = "done"
            self.target_coordinate_abandoned = True
            return None
        if self.target_coordinate_action_index >= len(current_order):
            self.target_coordinate_phase = "done"
            self.target_coordinate_abandoned = True
            return None
        selected_key = current_order[self.target_coordinate_action_index]
        return next(
            action
            for action in surface.actions
            if action.key == selected_key
        )

    def _target_frontier_action(
        self,
        surface: _TargetSearchSurface,
    ) -> tuple[VisualAction | None, int | None]:
        action_by_key = {action.key: action for action in surface.actions}
        ordered_keys = tuple(
            action.key
            for action in sorted(
                surface.actions,
                key=lambda action: (
                    -(action.y if action.y is not None else -1),
                    -(action.x if action.x is not None else -1),
                    action.key,
                ),
            )
        )
        known_states = {
            surface.state_signature,
            *self.target_transitions,
            *(
                target
                for edges in self.target_transitions.values()
                for target in edges.values()
            ),
        }
        if len(known_states) > surface.maximum_states:
            return None, None
        current_cost = self.target_state_costs.get(
            surface.state_signature,
            surface.target_cost,
        )
        order_index = {
            key: index for index, key in enumerate(ordered_keys)
        }
        transitions = self.target_transitions.get(
            surface.state_signature,
            {},
        )
        improving = tuple(
            sorted(
                (
                    self.target_state_costs[target],
                    order_index[key],
                    key,
                )
                for key, target in transitions.items()
                if (
                    key in action_by_key
                    and target in self.target_state_costs
                    and self.target_state_costs[target] < current_cost
                    and key
                    not in self.target_hazards.get(
                        surface.state_signature,
                        set(),
                    )
                )
            )
        )
        if improving and self.target_cost_guidance_enabled:
            self.target_route_count += 1
            return action_by_key[improving[0][2]], 1

        def frontier_action_key(state: str) -> str | None:
            transitions = self.target_transitions.get(state, {})
            hazards = self.target_hazards.get(state, set())
            return next(
                (
                    key
                    for key in ordered_keys
                    if key not in transitions and key not in hazards
                ),
                None,
            )

        immediate = frontier_action_key(surface.state_signature)
        if immediate is not None and not self.target_cost_guidance_enabled:
            return action_by_key[immediate], 0

        queue: deque[tuple[str, int]] = deque(
            ((surface.state_signature, 0),)
        )
        visited = {surface.state_signature}
        first_action: dict[str, str] = {}
        guided_frontiers: list[tuple[int, int, str, str]] = []
        while queue:
            state, distance = queue.popleft()
            frontier = frontier_action_key(state)
            if frontier is not None:
                route_key = (
                    frontier if distance == 0 else first_action[state]
                )
                if self.target_cost_guidance_enabled:
                    guided_frontiers.append(
                        (
                            self.target_state_costs.get(
                                state,
                                current_cost,
                            ),
                            distance,
                            state,
                            route_key,
                        )
                    )
                elif distance > 0:
                    action = action_by_key.get(route_key)
                    if action is not None:
                        self.target_route_count += 1
                        return action, distance
            for key in ordered_keys:
                target = self.target_transitions.get(state, {}).get(key)
                if (
                    target is None
                    or target in visited
                    or key not in action_by_key
                ):
                    continue
                visited.add(target)
                first_action[target] = (
                    key if distance == 0 else first_action[state]
                )
                queue.append((target, distance + 1))
        if guided_frontiers:
            _cost, distance, _state, key = min(guided_frontiers)
            action = action_by_key.get(key)
            if action is not None:
                self.target_route_count += 1
                return action, distance
        return None, None

    def _stage_target_action(
        self,
        surface: _TargetSearchSurface,
        action: VisualAction,
    ) -> None:
        self.target_transitions.setdefault(surface.state_signature, {})
        self.target_pending_state = surface.state_signature
        self.target_pending_action = action.key
        self.target_pending_mechanism = (
            surface.mechanism_colors
            if (
                not self.target_model_abandoned
                and surface.mechanism_positions
                == self.target_model_positions
            )
            else ()
        )

    def decide(
        self,
        grid: Grid,
        available_actions: tuple[int, ...],
        operator_instructions: tuple[SemanticOperatorInstruction, ...],
        *,
        source_signature: str,
    ) -> SemanticPlannerDecision:
        if self.active_operator:
            active_instruction = next(
                (
                    instruction
                    for instruction in operator_instructions
                    if instruction.operator_id == self.active_operator
                ),
                None,
            )
            if (
                active_instruction is None
                or digest_object(active_instruction)
                != self.active_instruction_digest
            ):
                self.reset_after_progress()
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
            target_surface: _TargetSearchSurface | None = None
            decision_reason = instruction.operator_id
            memory_influenced = False
            if instruction.operator_id == RELATION_TOGGLE_OPERATOR:
                plan = relation_toggle_plan(
                    grid,
                    available_actions,
                    instruction,
                )
            elif instruction.operator_id == OBJECT_TARGET_CONTROL_OPERATOR:
                parts = _object_target_parts(
                    grid,
                    available_actions,
                    instruction,
                )
                if parts is None:
                    continue
                target_surface = _target_search_surface(
                    parts,
                    instruction,
                )
                if target_surface is not None:
                    self._observe_target_surface(target_surface)
                plan = object_target_control_plan(
                    grid,
                    available_actions,
                    instruction,
                )
                if not plan and target_surface is not None:
                    target_action = self._target_model_action(
                        target_surface
                    )
                    if target_action is not None:
                        plan = (target_action,)
                        decision_reason = (
                            f"{instruction.operator_id}:learned-permutation"
                        )
                        memory_influenced = True
                    else:
                        target_action = self._target_model_probe_action(
                            target_surface
                        )
                        if target_action is not None:
                            plan = (target_action,)
                            decision_reason = (
                                f"{instruction.operator_id}:"
                                "permutation-probe"
                            )
                            memory_influenced = bool(
                                self.target_observation_count
                            )
                        else:
                            target_action = (
                                self._target_coordinate_action(
                                    target_surface
                                )
                            )
                            if target_action is not None:
                                plan = (target_action,)
                                decision_reason = (
                                    f"{instruction.operator_id}:"
                                    "coordinate-descent"
                                )
                                memory_influenced = bool(
                                    self.target_observation_count
                                    or self.target_coordinate_probe_step
                                    or (
                                        self
                                        .target_coordinate_completed_passes
                                    )
                                )
                            else:
                                target_action, distance = (
                                    self._target_frontier_action(
                                        target_surface
                                    )
                                )
                                if target_action is not None:
                                    plan = (target_action,)
                                    decision_reason = (
                                        f"{instruction.operator_id}:"
                                        "state-graph"
                                    )
                                    memory_influenced = bool(
                                        self.target_observation_count
                                        or self.target_hazards
                                        or (
                                            distance is not None
                                            and distance > 0
                                        )
                                    )
            elif instruction.operator_id in {
                FRUIT_MERGE_OPERATOR,
                FRUIT_MERGE_CANDIDATE_OPERATOR,
                FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
                FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
            }:
                fruit_decision = self.fruit_merge.decide(
                    grid,
                    available_actions,
                    instruction,
                )
                plan = (
                    ()
                    if fruit_decision.action is None
                    else (fruit_decision.action,)
                )
                decision_reason = fruit_decision.reason
                memory_influenced = fruit_decision.memory_influenced
            elif instruction.operator_id == SYMBOLIC_REWRITE_OPERATOR:
                rewrite_decision = self.symbolic_rewrite.decide(
                    grid,
                    available_actions,
                    instruction,
                )
                plan = (
                    ()
                    if rewrite_decision.action is None
                    else (rewrite_decision.action,)
                )
                decision_reason = rewrite_decision.reason
                memory_influenced = (
                    rewrite_decision.memory_influenced
                )
            else:
                continue
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
            if target_surface is not None:
                self._stage_target_action(target_surface, action)
            if memory_influenced:
                self.memory_read_count += 1
            return SemanticPlannerDecision(
                action=action,
                reason=decision_reason,
                memory_influenced=memory_influenced,
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
            "target_initial_state": self.target_initial_state,
            "target_pending_state": self.target_pending_state,
            "target_pending_action": self.target_pending_action,
            "target_cost_guidance_enabled": (
                self.target_cost_guidance_enabled
            ),
            "target_transitions": {
                state: dict(sorted(edges.items()))
                for state, edges in sorted(
                    self.target_transitions.items()
                )
            },
            "target_state_costs": dict(
                sorted(self.target_state_costs.items())
            ),
            "target_safe_actions": sorted(self.target_safe_actions),
            "target_hazards": {
                state: sorted(actions)
                for state, actions in sorted(self.target_hazards.items())
            },
            "target_observation_count": self.target_observation_count,
            "target_route_count": self.target_route_count,
            "target_coordinate_phase": self.target_coordinate_phase,
            "target_coordinate_action_order": list(
                self.target_coordinate_action_order
            ),
            "target_coordinate_action_index": (
                self.target_coordinate_action_index
            ),
            "target_coordinate_pass_start_cost": (
                self.target_coordinate_pass_start_cost
            ),
            "target_coordinate_base_state": (
                self.target_coordinate_base_state
            ),
            "target_coordinate_base_cost": (
                self.target_coordinate_base_cost
            ),
            "target_coordinate_probe_step": (
                self.target_coordinate_probe_step
            ),
            "target_coordinate_best_step": (
                self.target_coordinate_best_step
            ),
            "target_coordinate_best_cost": (
                self.target_coordinate_best_cost
            ),
            "target_coordinate_commit_remaining": (
                self.target_coordinate_commit_remaining
            ),
            "target_coordinate_completed_passes": (
                self.target_coordinate_completed_passes
            ),
            "target_coordinate_abandoned": (
                self.target_coordinate_abandoned
            ),
            "target_model_positions": [
                list(position) for position in self.target_model_positions
            ],
            "target_model_requirements": [
                list(requirement)
                for requirement in self.target_model_requirements
            ],
            "target_pending_mechanism": list(
                self.target_pending_mechanism
            ),
            "target_permutation_candidates": {
                action: [list(row) for row in candidates]
                for action, candidates in sorted(
                    self.target_permutation_candidates.items()
                )
            },
            "target_permutation_observations": dict(
                sorted(self.target_permutation_observations.items())
            ),
            "target_model_plan": list(self.target_model_plan),
            "target_model_expected_colors": list(
                self.target_model_expected_colors
            ),
            "target_model_plan_count": self.target_model_plan_count,
            "target_model_mismatch_count": (
                self.target_model_mismatch_count
            ),
            "target_model_abandoned": self.target_model_abandoned,
            "fruit_merge": self.fruit_merge.to_payload(),
            "symbolic_rewrite": self.symbolic_rewrite.to_payload(),
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
        raw_target_transitions = value.get("target_transitions", {})
        raw_target_state_costs = value.get("target_state_costs", {})
        raw_target_safe_actions = value.get("target_safe_actions", ())
        raw_target_hazards = value.get("target_hazards", {})
        raw_target_coordinate_order = value.get(
            "target_coordinate_action_order",
            (),
        )
        raw_target_model_positions = value.get(
            "target_model_positions",
            (),
        )
        raw_target_model_requirements = value.get(
            "target_model_requirements",
            (),
        )
        raw_target_pending_mechanism = value.get(
            "target_pending_mechanism",
            (),
        )
        raw_target_permutation_candidates = value.get(
            "target_permutation_candidates",
            {},
        )
        raw_target_permutation_observations = value.get(
            "target_permutation_observations",
            {},
        )
        raw_target_model_plan = value.get("target_model_plan", ())
        raw_target_model_expected_colors = value.get(
            "target_model_expected_colors",
            (),
        )
        raw_fruit_merge = value.get("fruit_merge")
        raw_symbolic_rewrite = value.get("symbolic_rewrite")
        if (
            not isinstance(raw_queue, Sequence)
            or isinstance(raw_queue, (str, bytes, bytearray))
            or not isinstance(raw_blocked, Sequence)
            or isinstance(raw_blocked, (str, bytes, bytearray))
            or not isinstance(raw_target_transitions, Mapping)
            or not isinstance(raw_target_state_costs, Mapping)
            or not isinstance(raw_target_safe_actions, Sequence)
            or isinstance(
                raw_target_safe_actions,
                (str, bytes, bytearray),
            )
            or not isinstance(raw_target_hazards, Mapping)
            or not isinstance(raw_target_coordinate_order, Sequence)
            or isinstance(
                raw_target_coordinate_order,
                (str, bytes, bytearray),
            )
            or not isinstance(raw_target_model_positions, Sequence)
            or isinstance(
                raw_target_model_positions,
                (str, bytes, bytearray),
            )
            or not isinstance(
                raw_target_model_requirements,
                Sequence,
            )
            or isinstance(
                raw_target_model_requirements,
                (str, bytes, bytearray),
            )
            or not isinstance(
                raw_target_pending_mechanism,
                Sequence,
            )
            or isinstance(
                raw_target_pending_mechanism,
                (str, bytes, bytearray),
            )
            or not isinstance(
                raw_target_permutation_candidates,
                Mapping,
            )
            or not isinstance(
                raw_target_permutation_observations,
                Mapping,
            )
            or not isinstance(raw_target_model_plan, Sequence)
            or isinstance(
                raw_target_model_plan,
                (str, bytes, bytearray),
            )
            or not isinstance(
                raw_target_model_expected_colors,
                Sequence,
            )
            or isinstance(
                raw_target_model_expected_colors,
                (str, bytes, bytearray),
            )
            or not isinstance(raw_fruit_merge, Mapping)
            or not isinstance(raw_symbolic_rewrite, Mapping)
        ):
            raise ValueError("semantic planner sequence invalid")
        target_coordinate_phase = str(
            value.get("target_coordinate_phase", "")
        )
        if target_coordinate_phase not in {"", "probe", "commit", "done"}:
            raise ValueError("semantic planner coordinate phase invalid")
        target_coordinate_abandoned = value.get(
            "target_coordinate_abandoned",
            False,
        )
        if not isinstance(target_coordinate_abandoned, bool):
            raise ValueError(
                "semantic planner coordinate abandoned flag invalid"
            )
        target_cost_guidance_enabled = value.get(
            "target_cost_guidance_enabled",
            False,
        )
        if not isinstance(target_cost_guidance_enabled, bool):
            raise ValueError(
                "semantic planner target guidance flag invalid"
            )
        target_model_abandoned = value.get(
            "target_model_abandoned",
            False,
        )
        if not isinstance(target_model_abandoned, bool):
            raise ValueError(
                "semantic planner target model abandoned flag invalid"
            )

        def integer_sequence(
            raw: object,
            field_name: str,
        ) -> tuple[int, ...]:
            if not isinstance(raw, Sequence) or isinstance(
                raw,
                (str, bytes, bytearray),
            ):
                raise ValueError(f"{field_name} invalid")
            return tuple(
                _payload_int(item, field_name) for item in raw
            )

        def integer_pairs(
            raw: object,
            field_name: str,
        ) -> tuple[tuple[int, int], ...]:
            if not isinstance(raw, Sequence) or isinstance(
                raw,
                (str, bytes, bytearray),
            ):
                raise ValueError(f"{field_name} invalid")
            pairs: list[tuple[int, int]] = []
            for item in raw:
                converted = integer_sequence(item, field_name)
                if len(converted) != 2:
                    raise ValueError(f"{field_name} pair invalid")
                pairs.append((converted[0], converted[1]))
            return tuple(pairs)

        target_model_positions = integer_pairs(
            raw_target_model_positions,
            "target_model_positions",
        )
        target_model_requirements = integer_pairs(
            raw_target_model_requirements,
            "target_model_requirements",
        )
        target_pending_mechanism = integer_sequence(
            raw_target_pending_mechanism,
            "target_pending_mechanism",
        )
        target_model_expected_colors = integer_sequence(
            raw_target_model_expected_colors,
            "target_model_expected_colors",
        )
        target_permutation_candidates: dict[
            str,
            tuple[tuple[int, ...], ...],
        ] = {}
        for raw_action, raw_rows in (
            raw_target_permutation_candidates.items()
        ):
            if not isinstance(raw_rows, Sequence) or isinstance(
                raw_rows,
                (str, bytes, bytearray),
            ):
                raise ValueError(
                    "target_permutation_candidates invalid"
                )
            target_permutation_candidates[str(raw_action)] = tuple(
                integer_sequence(
                    row,
                    "target_permutation_candidate",
                )
                for row in raw_rows
            )
        target_permutation_observations = {
            str(action): _payload_int(
                count,
                "target_permutation_observation",
            )
            for action, count in (
                raw_target_permutation_observations.items()
            )
        }
        target_transitions: dict[str, dict[str, str]] = {}
        for raw_state, raw_edges in raw_target_transitions.items():
            if not isinstance(raw_edges, Mapping):
                raise ValueError(
                    "semantic planner target transition invalid"
                )
            target_transitions[str(raw_state)] = {
                str(action): str(target)
                for action, target in raw_edges.items()
            }
        target_hazards: dict[str, set[str]] = {}
        for raw_state, raw_actions in raw_target_hazards.items():
            if (
                not isinstance(raw_actions, Sequence)
                or isinstance(raw_actions, (str, bytes, bytearray))
            ):
                raise ValueError(
                    "semantic planner target hazard invalid"
                )
            target_hazards[str(raw_state)] = {
                str(action) for action in raw_actions
            }
        target_state_costs = {
            str(state): _payload_int(cost, "target_state_cost")
            for state, cost in raw_target_state_costs.items()
        }
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
            target_initial_state=str(
                value.get("target_initial_state", "")
            ),
            target_pending_state=str(
                value.get("target_pending_state", "")
            ),
            target_pending_action=str(
                value.get("target_pending_action", "")
            ),
            target_cost_guidance_enabled=(
                target_cost_guidance_enabled
            ),
            target_transitions=target_transitions,
            target_state_costs=target_state_costs,
            target_safe_actions={
                str(action) for action in raw_target_safe_actions
            },
            target_hazards=target_hazards,
            target_observation_count=_payload_int(
                value.get("target_observation_count", 0),
                "target_observation_count",
            ),
            target_route_count=_payload_int(
                value.get("target_route_count", 0),
                "target_route_count",
            ),
            target_coordinate_phase=target_coordinate_phase,
            target_coordinate_action_order=tuple(
                str(action) for action in raw_target_coordinate_order
            ),
            target_coordinate_action_index=_payload_int(
                value.get("target_coordinate_action_index", 0),
                "target_coordinate_action_index",
            ),
            target_coordinate_pass_start_cost=_payload_int(
                value.get("target_coordinate_pass_start_cost", 0),
                "target_coordinate_pass_start_cost",
            ),
            target_coordinate_base_state=str(
                value.get("target_coordinate_base_state", "")
            ),
            target_coordinate_base_cost=_payload_int(
                value.get("target_coordinate_base_cost", 0),
                "target_coordinate_base_cost",
            ),
            target_coordinate_probe_step=_payload_int(
                value.get("target_coordinate_probe_step", 0),
                "target_coordinate_probe_step",
            ),
            target_coordinate_best_step=_payload_int(
                value.get("target_coordinate_best_step", 0),
                "target_coordinate_best_step",
            ),
            target_coordinate_best_cost=_payload_int(
                value.get("target_coordinate_best_cost", 0),
                "target_coordinate_best_cost",
            ),
            target_coordinate_commit_remaining=_payload_int(
                value.get("target_coordinate_commit_remaining", 0),
                "target_coordinate_commit_remaining",
            ),
            target_coordinate_completed_passes=_payload_int(
                value.get("target_coordinate_completed_passes", 0),
                "target_coordinate_completed_passes",
            ),
            target_coordinate_abandoned=target_coordinate_abandoned,
            target_model_positions=target_model_positions,
            target_model_requirements=target_model_requirements,
            target_pending_mechanism=target_pending_mechanism,
            target_permutation_candidates=(
                target_permutation_candidates
            ),
            target_permutation_observations=(
                target_permutation_observations
            ),
            target_model_plan=[
                str(action) for action in raw_target_model_plan
            ],
            target_model_expected_colors=(
                target_model_expected_colors
            ),
            target_model_plan_count=_payload_int(
                value.get("target_model_plan_count", 0),
                "target_model_plan_count",
            ),
            target_model_mismatch_count=_payload_int(
                value.get("target_model_mismatch_count", 0),
                "target_model_mismatch_count",
            ),
            target_model_abandoned=target_model_abandoned,
            fruit_merge=FruitMergeState.from_payload(raw_fruit_merge),
            symbolic_rewrite=SymbolicRewriteState.from_payload(
                raw_symbolic_rewrite
            ),
        )

    @property
    def digest(self) -> str:
        return digest_object(self.to_payload())


__all__ = [
    "FRUIT_MERGE_OPERATOR",
    "FRUIT_MERGE_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR",
    "FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR",
    "OBJECT_TARGET_CONTROL_OPERATOR",
    "RELATION_TOGGLE_OPERATOR",
    "SYMBOLIC_REWRITE_OPERATOR",
    "SEMANTIC_PLANNER_FORMAT",
    "SemanticPlannerDecision",
    "SemanticPlannerState",
    "object_target_control_plan",
    "relation_toggle_plan",
]
