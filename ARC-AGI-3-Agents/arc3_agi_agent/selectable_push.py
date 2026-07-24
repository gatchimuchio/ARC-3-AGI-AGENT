"""Rendered selectable-object push planning without environment identity."""

from __future__ import annotations

from dataclasses import dataclass

from .instruction_body import SemanticOperatorInstruction
from .schema import digest_object
from .visual_explorer import (
    Grid,
    Point,
    VisualAction,
    VisualComponent,
    connected_components,
)

SELECTABLE_PUSH_TARGET_OPERATOR = "selectable-object-target-push-v1"


@dataclass(frozen=True, slots=True)
class _PushParameters:
    click_action: int
    up_action: int
    down_action: int
    left_action: int
    right_action: int
    required_pair_count: int
    target_inset: int
    minimum_block_side: int
    maximum_block_side: int
    minimum_barrier_area_ratio: int

    @classmethod
    def from_instruction(
        cls,
        instruction: SemanticOperatorInstruction,
    ) -> _PushParameters | None:
        if instruction.operator_id != SELECTABLE_PUSH_TARGET_OPERATOR:
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
                "click_action",
                "up_action",
                "down_action",
                "left_action",
                "right_action",
                "required_pair_count",
                "target_inset",
                "minimum_block_side",
                "maximum_block_side",
                "minimum_barrier_area_ratio",
            )
        }
        if any(value is None for value in values.values()):
            return None
        parsed = {
            name: value
            for name, value in values.items()
            if value is not None
        }
        if (
            instruction.action_id != parsed["click_action"]
            or len(
                {
                    parsed["up_action"],
                    parsed["down_action"],
                    parsed["left_action"],
                    parsed["right_action"],
                }
            )
            != 4
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
            or parsed["required_pair_count"] < 2
            or not 1 <= parsed["target_inset"] <= 4
            or parsed["minimum_block_side"] < 2
            or parsed["maximum_block_side"]
            < parsed["minimum_block_side"]
            or parsed["minimum_barrier_area_ratio"] < 2
        ):
            return None
        return cls(**parsed)


@dataclass(frozen=True, slots=True)
class _Ring:
    component: VisualComponent

    @property
    def center(self) -> Point:
        return (
            (self.component.bbox[0] + self.component.bbox[2]) // 2,
            (self.component.bbox[1] + self.component.bbox[3]) // 2,
        )


def _is_border_ring(component: VisualComponent) -> bool:
    if (
        component.rectangular
        or component.width < 3
        or component.height < 3
    ):
        return False
    border = {
        (x, y)
        for y in range(component.bbox[1], component.bbox[3] + 1)
        for x in range(component.bbox[0], component.bbox[2] + 1)
        if x in {component.bbox[0], component.bbox[2]}
        or y in {component.bbox[1], component.bbox[3]}
    }
    return set(component.pixels) == border


def _ring_families(
    components: tuple[VisualComponent, ...],
) -> dict[tuple[int, int, int], tuple[_Ring, ...]]:
    grouped: dict[tuple[int, int, int], list[_Ring]] = {}
    for component in components:
        if not _is_border_ring(component):
            continue
        grouped.setdefault(
            (component.color, component.width, component.height),
            [],
        ).append(_Ring(component))
    return {
        key: tuple(
            sorted(
                rings,
                key=lambda ring: (ring.center[1], ring.center[0]),
            )
        )
        for key, rings in grouped.items()
    }


def _touches_edge(
    component: VisualComponent,
    *,
    width: int,
    height: int,
) -> bool:
    x0, y0, x1, y1 = component.bbox
    return x0 == 0 or y0 == 0 or x1 == width - 1 or y1 == height - 1


def _structural_roles(
    grid: Grid,
    parameters: _PushParameters,
) -> tuple[
    tuple[_Ring, ...],
    tuple[_Ring, ...],
    VisualComponent,
] | None:
    if not grid:
        return None
    height = len(grid)
    width = len(grid[0])
    components = connected_components(grid)
    families = _ring_families(components)
    candidates: list[
        tuple[
            tuple[int, int, int, int],
            tuple[_Ring, ...],
            tuple[_Ring, ...],
            VisualComponent,
        ]
    ] = []
    for (
        block_color,
        block_width,
        block_height,
    ), blocks in families.items():
        if (
            len(blocks) != parameters.required_pair_count
            or not parameters.minimum_block_side
            <= min(block_width, block_height)
            <= max(block_width, block_height)
            <= parameters.maximum_block_side
        ):
            continue
        target_width = block_width + 2 * parameters.target_inset
        target_height = block_height + 2 * parameters.target_inset
        for (
            target_color,
            family_width,
            family_height,
        ), targets in families.items():
            if (
                target_color == block_color
                or family_width != target_width
                or family_height != target_height
                or len(targets) != len(blocks)
            ):
                continue
            ordered_blocks = tuple(
                sorted(blocks, key=lambda ring: ring.center[0])
            )
            ordered_targets = tuple(
                sorted(targets, key=lambda ring: ring.center[0])
            )
            if len({ring.center[1] for ring in ordered_blocks}) != 1:
                continue
            right_block_x = ordered_blocks[-1].center[0]
            right_target_x = ordered_targets[-1].center[0]
            if right_target_x <= right_block_x:
                continue
            minimum_barrier_area = (
                block_width
                * block_height
                * parameters.minimum_barrier_area_ratio
            )
            barriers = tuple(
                component
                for component in components
                if (
                    component.rectangular
                    and component.area >= minimum_barrier_area
                    and not _touches_edge(
                        component,
                        width=width,
                        height=height,
                    )
                    and right_block_x
                    < component.bbox[0]
                    < right_target_x
                )
            )
            if not barriers:
                continue
            barrier = max(
                barriers,
                key=lambda component: (
                    component.area,
                    component.height,
                    -component.bbox[0],
                ),
            )
            relation_key = (
                block_width,
                block_height,
                target_width,
                barrier.bbox[0] - right_block_x,
            )
            candidates.append(
                (
                    relation_key,
                    ordered_blocks,
                    ordered_targets,
                    barrier,
                )
            )
    if len(candidates) != 1:
        return None
    _key, blocks, targets, barrier = candidates[0]
    return blocks, targets, barrier


def _axis_actions(
    delta: int,
    *,
    negative_action: int,
    positive_action: int,
    step: int,
) -> tuple[int, ...] | None:
    if delta % step:
        return None
    action = positive_action if delta > 0 else negative_action
    return (action,) * (abs(delta) // step)


def _simple_action(
    action_id: int,
    *,
    instruction: SemanticOperatorInstruction,
    index: int,
) -> VisualAction:
    return VisualAction(
        key="semantic-selectable-push:"
        + digest_object(
            {
                "operator": instruction.operator_id,
                "index": index,
                "action_id": action_id,
            }
        )[:20],
        action_id=action_id,
        group=0,
        evidence=(
            instruction.operator_id,
            f"operator-prototype:{instruction.operator_id}",
            "rendered-selectable-object-target-relation",
            *instruction.provenance,
        ),
    )


def _click_action(
    point: Point,
    *,
    instruction: SemanticOperatorInstruction,
    index: int,
) -> VisualAction:
    return VisualAction(
        key="semantic-selectable-push:"
        + digest_object(
            {
                "operator": instruction.operator_id,
                "index": index,
                "point": point,
            }
        )[:20],
        action_id=instruction.action_id,
        group=0,
        x=point[0],
        y=point[1],
        evidence=(
            instruction.operator_id,
            f"operator-prototype:{instruction.operator_id}",
            "rendered-selectable-object-target-relation",
            "observation-derived-selection-point",
            *instruction.provenance,
        ),
    )


def selectable_push_target_plan(
    grid: Grid,
    available_actions: tuple[int, ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[VisualAction, ...]:
    """Compile a geometry-derived two-object crossing and placement plan."""

    parameters = _PushParameters.from_instruction(instruction)
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
    roles = _structural_roles(grid, parameters)
    if roles is None:
        return ()
    blocks, targets, barrier = roles
    left_block, right_block = blocks
    left_target, right_target = targets
    step = left_block.component.width
    if (
        right_block.component.width != step
        or left_block.component.height != right_block.component.height
    ):
        return ()
    left_x, base_y = left_block.center
    right_x, right_y = right_block.center
    left_target_x, left_target_y = left_target.center
    right_target_x, right_target_y = right_target.center
    if right_y != base_y:
        return ()
    right_shoves = max(
        1,
        ((barrier.bbox[0] - right_x + step - 1) // step) + 1,
    )
    left_stage = (left_x + step, base_y)
    right_stage = (right_target_x - step, base_y)
    right_vertical = _axis_actions(
        right_target_y - base_y,
        negative_action=parameters.up_action,
        positive_action=parameters.down_action,
        step=step,
    )
    right_horizontal = _axis_actions(
        right_target_x - right_stage[0],
        negative_action=parameters.left_action,
        positive_action=parameters.right_action,
        step=step,
    )
    left_horizontal = _axis_actions(
        left_target_x - left_stage[0],
        negative_action=parameters.left_action,
        positive_action=parameters.right_action,
        step=step,
    )
    left_vertical = _axis_actions(
        left_target_y - base_y,
        negative_action=parameters.up_action,
        positive_action=parameters.down_action,
        step=step,
    )
    if (
        right_vertical is None
        or right_horizontal is None
        or left_horizontal is None
        or left_vertical is None
    ):
        return ()
    action_specs: list[int | Point] = [
        *([parameters.right_action] * right_shoves),
        parameters.left_action,
        right_stage,
        *right_vertical,
        *right_horizontal,
        left_stage,
        *left_horizontal,
        *left_vertical,
    ]
    return tuple(
        (
            _click_action(spec, instruction=instruction, index=index)
            if isinstance(spec, tuple)
            else _simple_action(
                spec,
                instruction=instruction,
                index=index,
            )
        )
        for index, spec in enumerate(action_specs)
    )


__all__ = [
    "SELECTABLE_PUSH_TARGET_OPERATOR",
    "selectable_push_target_plan",
]
