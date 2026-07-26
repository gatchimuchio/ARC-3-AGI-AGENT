from __future__ import annotations

import unittest
from typing import Any

import numpy as np
from arcengine import FrameDataRaw, GameState

from arc3_agi_agent.teacher.s2_role_selector import (
    S2RoleSelectorError,
    compile_role_relative_selector,
    resolve_role_relative_selector,
    validate_role_relative_selector,
)


def _frame(grid: list[list[int]]) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="s2-selector-test",
        state=GameState.NOT_FINISHED,
        levels_completed=0,
        win_levels=1,
        available_actions=[],
    )
    result.frame = [np.asarray(grid, dtype=np.int8)]
    return result


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        output = set(value)
        for item in value.values():
            output.update(_keys(item))
        return output
    if isinstance(value, list):
        output: set[str] = set()
        for item in value:
            output.update(_keys(item))
        return output
    return set()


class TeacherS2RoleSelectorTests(unittest.TestCase):
    def test_selector_resolves_rendered_role_without_absolute_payload(
        self,
    ) -> None:
        frame = _frame(
            [
                [0, 0, 0, 0, 0],
                [0, 2, 2, 0, 0],
                [0, 2, 3, 0, 0],
                [0, 0, 0, 0, 0],
            ]
        )
        selector = compile_role_relative_selector(
            frame=frame,
            target_horizontal_index=2,
            target_vertical_index=2,
        )
        resolved = resolve_role_relative_selector(
            selector=selector,
            frame=frame,
        )

        self.assertEqual(resolved.horizontal_index, 2)
        self.assertEqual(resolved.vertical_index, 2)
        self.assertFalse(selector["absolute_target_stored"])
        self.assertEqual(
            _keys(selector).intersection(
                {
                    "action_data",
                    "column",
                    "coordinate",
                    "literal_coordinate",
                    "row",
                    "x",
                    "y",
                }
            ),
            set(),
        )

    def test_selector_transfers_with_translated_rendered_role(self) -> None:
        source = _frame(
            [
                [0, 0, 0, 0, 0, 0],
                [0, 2, 3, 0, 0, 0],
                [0, 2, 2, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
            ]
        )
        translated = _frame(
            [
                [0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
                [0, 0, 2, 3, 0, 0],
                [0, 0, 2, 2, 0, 0],
                [0, 0, 0, 0, 0, 0],
            ]
        )
        selector = compile_role_relative_selector(
            frame=source,
            target_horizontal_index=2,
            target_vertical_index=1,
        )
        self.assertEqual(selector["boundary_constraint_count"], 0)

        resolved = resolve_role_relative_selector(
            selector=selector,
            frame=translated,
        )
        self.assertEqual(resolved.horizontal_index, 3)
        self.assertEqual(resolved.vertical_index, 2)

    def test_uniform_frame_uses_relations_to_frame_boundary(self) -> None:
        frame = _frame([[0] * 5 for _ in range(4)])
        selector = compile_role_relative_selector(
            frame=frame,
            target_horizontal_index=3,
            target_vertical_index=1,
        )
        resolved = resolve_role_relative_selector(
            selector=selector,
            frame=frame,
        )

        self.assertGreater(selector["boundary_constraint_count"], 0)
        self.assertEqual(resolved.horizontal_index, 3)
        self.assertEqual(resolved.vertical_index, 1)

    def test_tampered_selector_is_rejected(self) -> None:
        frame = _frame(
            [
                [0, 0, 0],
                [0, 4, 0],
                [0, 0, 0],
            ]
        )
        selector: dict[str, Any] = compile_role_relative_selector(
            frame=frame,
            target_horizontal_index=1,
            target_vertical_index=1,
        )
        selector["center_palette"] = 8

        with self.assertRaisesRegex(
            ValueError,
            "S2_ROLE_SELECTOR_DIGEST_INVALID",
        ):
            validate_role_relative_selector(selector)

    def test_outside_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            S2RoleSelectorError,
            "S2_TARGET_OUTSIDE_RENDERED_FRAME",
        ):
            compile_role_relative_selector(
                frame=_frame([[0, 0], [0, 0]]),
                target_horizontal_index=2,
                target_vertical_index=0,
            )


if __name__ == "__main__":
    unittest.main()
