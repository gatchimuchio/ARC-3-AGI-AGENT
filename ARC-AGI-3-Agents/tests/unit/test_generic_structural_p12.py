from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from arc3_agi_agent.generic_compute import HybridRelationalInstructionBody
from arc3_agi_agent.generic_runtime import (
    GenericAGIRuntime,
    GenericRuntimeConfiguration,
)
from arc3_agi_agent.generic_structural import (
    infer_relational_rewrite_state,
)
from arc3_agi_agent.generic_types import GenericObservation
from arc3_agi_agent.schema import digest_object

_SHAPES = (
    ("..#..", "..#..", "#####", "..#..", "..#.."),
    ("#....", "#....", "#....", "#....", "#####"),
    ("#####", "..#..", "..#..", "..#..", "..#.."),
    ("#####", "#...#", "#...#", "#...#", "#####"),
    ("#....", "##...", ".##..", "..##.", "...##"),
    ("#...#", "#...#", "#...#", "#...#", "#####"),
)
_SOURCE = (3, 4, 0, 1, 2)
_DESIRED = tuple((value + 1) % len(_SHAPES) for value in _SOURCE)


def _draw_shape(
    matrix: list[list[int]],
    *,
    center_x: int,
    center_y: int,
    shape_index: int,
    color: int = 5,
) -> None:
    for dy, row in enumerate(_SHAPES[shape_index]):
        for dx, value in enumerate(row):
            if value == "#":
                matrix[center_y - 2 + dy][center_x - 2 + dx] = color


def _rewrite_frame(
    outputs: tuple[int, ...],
    selected: int,
) -> tuple[tuple[int, ...], ...]:
    matrix = [
        [2 if y < 34 else 3 for _ in range(64)]
        for y in range(64)
    ]
    matrix[-1] = [1 for _ in range(64)]
    for row_index, center_y in enumerate((7, 16, 25)):
        first_source = row_index * 2
        for center_x, shape_index in (
            (12, first_source),
            (22, (first_source + 1) % len(_SHAPES)),
            (38, first_source + 1),
            (48, (first_source + 2) % len(_SHAPES)),
        ):
            _draw_shape(
                matrix,
                center_x=center_x,
                center_y=center_y,
                shape_index=shape_index,
            )
    for index, shape_index in enumerate(_SOURCE):
        _draw_shape(
            matrix,
            center_x=12 + index * 10,
            center_y=43,
            shape_index=shape_index,
        )
    for index, shape_index in enumerate(outputs):
        center_x = 12 + index * 10
        _draw_shape(
            matrix,
            center_x=center_x,
            center_y=54,
            shape_index=shape_index,
        )
        if index == selected:
            for x in range(center_x - 2, center_x + 3):
                matrix[48][x] = 0
                matrix[60][x] = 0
    return tuple(tuple(row) for row in matrix)


@dataclass(slots=True)
class _RenderedRewriteWorld:
    outputs: tuple[int, ...] = (0, 0, 0, 0, 0)
    selected: int = 0
    progress: int = 0
    state: str = "NOT_FINISHED"
    effects: tuple[str, ...] = ()
    request_ids: set[str] = field(default_factory=set)

    def observe(self) -> GenericObservation:
        frame = _rewrite_frame(self.outputs, self.selected)
        return GenericObservation(
            signature="rewrite-world:"
            + digest_object(
                (self.outputs, self.selected, self.progress, self.state)
            ),
            available_actions=(1, 2, 3, 4),
            rendered_layers=(frame,),
            terminal_state=self.state,
            progress_count=self.progress,
            visible_effects=self.effects,
        )

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        assert not payload
        assert request_id not in self.request_ids
        self.request_ids.add(request_id)
        if action_id == 1:
            next_outputs = list(self.outputs)
            next_outputs[self.selected] = (
                next_outputs[self.selected] - 1
            ) % len(_SHAPES)
            self.outputs = tuple(next_outputs)
        elif action_id == 2:
            next_outputs = list(self.outputs)
            next_outputs[self.selected] = (
                next_outputs[self.selected] + 1
            ) % len(_SHAPES)
            self.outputs = tuple(next_outputs)
        elif action_id == 3:
            self.selected = (self.selected - 1) % len(self.outputs)
        elif action_id == 4:
            self.selected = (self.selected + 1) % len(self.outputs)
        else:
            raise ValueError("REWRITE_WORLD_ACTION_INVALID")
        self.effects = ("VISIBLE_STATE_CHANGE",)
        if self.outputs == _DESIRED:
            self.progress = 1
            self.state = "WIN"
            self.effects = ("LEVEL_PROGRESS", "VISIBLE_STATE_CHANGE")
        return self.observe()

    def reset_level(self, *, request_id: str) -> GenericObservation:
        del request_id
        raise RuntimeError("REWRITE_WORLD_RESET_UNAVAILABLE")


def test_rendered_rewrite_inference_and_effect_learned_control() -> None:
    world = _RenderedRewriteWorld()
    inferred = infer_relational_rewrite_state(
        world.observe().rendered_layers[-1]
    )

    assert inferred is not None
    assert inferred.sequence_length == 5
    assert inferred.selected_index == 0
    assert inferred.selected_matches is False
    assert inferred.all_matches is False

    report = GenericAGIRuntime(
        environment=world,
        instruction_body=HybridRelationalInstructionBody(),
        configuration=GenericRuntimeConfiguration(max_cycles=64),
    ).run()

    assert report.final_state == "WIN"
    assert report.progress_count == 1
    assert report.actions_executed <= 40
    observed_effects = {
        effect
        for cycle in report.cycles
        if cycle.attribution is not None
        for effect in cycle.attribution.visible_effects
    }
    assert "STRUCTURAL_SELECTION_CHANGE" in observed_effects
    assert "STRUCTURAL_VALUE_CHANGE" in observed_effects
