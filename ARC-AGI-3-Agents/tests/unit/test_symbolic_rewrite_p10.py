from __future__ import annotations

import unittest

import arc3_agi_agent.symbolic_rewrite as rewrite
from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.symbolic_rewrite import (
    SYMBOLIC_REWRITE_OPERATOR,
    SymbolicRewriteState,
)

PATTERN_A = (
    "00100",
    "01110",
    "00100",
    "00100",
    "11111",
)
PATTERN_B = (
    "10000",
    "11110",
    "10010",
    "10010",
    "11111",
)
PATTERN_C = (
    "11111",
    "10100",
    "10000",
    "10100",
    "11111",
)


def instruction(
    *,
    maximum_output_tokens: int = 32,
) -> SemanticOperatorInstruction:
    parameters: dict[str, object] = {
        "tile_size": 7,
        "symbol_color": 5,
        "connector_color": 3,
        "selector_color": 0,
        "cycle_size": 7,
        "decrement_action": 1,
        "increment_action": 2,
        "previous_action": 3,
        "next_action": 4,
        "minimum_border_count": 23,
        "maximum_rewrite_depth": 2,
        "maximum_intermediate_candidates": 128,
        "maximum_output_tokens": maximum_output_tokens,
    }
    return SemanticOperatorInstruction(
        operator_id=SYMBOLIC_REWRITE_OPERATOR,
        action_id=2,
        detector="rendered bordered symbols and connectors",
        transform="bounded visible rewrite",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("DIRECTIONAL_ACTIONS_AVAILABLE",),
        falsification_conditions=("rewrite detector does not close",),
        provenance=("compiled-visible-rewrite-evidence",),
    )


def fixed_rewrite_grid(
    *,
    output_pattern: tuple[str, ...],
) -> tuple[tuple[int, ...], ...]:
    rows = [[2] * 64 for _ in range(64)]

    def tile(
        x: int,
        y: int,
        background: int,
        pattern: tuple[str, ...],
    ) -> None:
        for dy in range(7):
            for dx in range(7):
                rows[y + dy][x + dx] = background
        for dy, pattern_row in enumerate(pattern, start=1):
            for dx, value in enumerate(pattern_row, start=1):
                if value == "1":
                    rows[y + dy][x + dx] = 5

    tile(10, 10, 10, PATTERN_A)
    tile(20, 10, 7, PATTERN_B)
    for x in range(17, 20):
        rows[13][x] = 3
    tile(10, 40, 10, PATTERN_A)
    tile(10, 51, 7, output_pattern)
    for x in range(10, 17):
        rows[47][x] = 0
        rows[62][x] = 0
    return tuple(tuple(row) for row in rows)


class P10SymbolicRewriteTests(unittest.TestCase):
    def test_fixed_rules_derive_target_and_cycle_visible_output(self) -> None:
        state = SymbolicRewriteState()

        mismatch = state.decide(
            fixed_rewrite_grid(output_pattern=PATTERN_C),
            (1, 2, 3, 4),
            instruction(),
        )
        matched = state.decide(
            fixed_rewrite_grid(output_pattern=PATTERN_B),
            (1, 2, 3, 4),
            instruction(),
        )

        self.assertIsNotNone(mismatch.action)
        self.assertIsNotNone(matched.action)
        assert mismatch.action is not None
        assert matched.action is not None
        self.assertEqual(mismatch.action.step(), {"action_id": 2})
        self.assertEqual(matched.action.step(), {"action_id": 1})
        self.assertIn("output-cycle", mismatch.reason)
        self.assertIn("submit-arm", matched.reason)

    def test_instruction_change_invalidates_passive_rewrite_state(
        self,
    ) -> None:
        state = SymbolicRewriteState()
        state.decide(
            fixed_rewrite_grid(output_pattern=PATTERN_B),
            (1, 2, 3, 4),
            instruction(),
        )
        original_digest = state.instruction_digest
        self.assertEqual(state.submit_count, 1)

        state.decide(
            fixed_rewrite_grid(output_pattern=PATTERN_C),
            (1, 2, 3, 4),
            instruction(maximum_output_tokens=31),
        )

        self.assertNotEqual(state.instruction_digest, original_digest)
        self.assertEqual(state.submit_count, 0)
        self.assertEqual(state.observation_count, 1)

    def test_editable_constraint_solver_selects_observed_offsets(
        self,
    ) -> None:
        parameters = rewrite._RewriteParameters.from_instruction(
            instruction()
        )
        assert parameters is not None
        nodes = (
            rewrite._RewriteNode(
                key="rule:0:left",
                labels=("10:a0",),
                bbox=(0, 0, 6, 6),
            ),
            rewrite._RewriteNode(
                key="rule:0:right",
                labels=("7:b0",),
                bbox=(10, 0, 16, 6),
            ),
        )
        surface = rewrite._RewriteSurface(
            signature="surface:test",
            mode="editable-rules",
            rules=(
                rewrite._RewriteRule(
                    index=0,
                    left_key="rule:0:left",
                    right_key="rule:0:right",
                ),
            ),
            nodes=nodes,
            source=("10:a1",),
            output=("7:b2",),
            selected_index=0,
            fixed_target=(),
            fixed_depth=0,
            parameters=parameters,
        )
        state = SymbolicRewriteState(
            surface_signature=surface.signature,
            mode=surface.mode,
            phase="solve",
            node_order=surface.node_order,
            candidate_states={
                "rule:0:left": [("10:a0",), ("10:a1",)],
                "rule:0:right": [
                    ("7:b0",),
                    ("7:b1",),
                    ("7:b2",),
                ],
            },
        )

        offsets = rewrite._solve_editable_offsets(surface, state)
        restored = SymbolicRewriteState.from_payload(state.to_payload())

        self.assertEqual(offsets, (1, 2))
        self.assertEqual(
            restored.candidate_states,
            state.candidate_states,
        )


if __name__ == "__main__":
    unittest.main()
