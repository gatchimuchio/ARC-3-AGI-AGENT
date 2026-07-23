from __future__ import annotations

import unittest

from arc3_agi_agent.context import BoundedContextState
from arc3_agi_agent.kernel import Layer0Components, Layer0Kernel
from arc3_agi_agent.p10_compute import (
    VISUAL_EXPLORER_MEMORY_FORMAT,
    P10VisualCandidateSurface,
    P10VisualCompute,
)
from arc3_agi_agent.roles import DeterministicSymbolSpace


def rendered_observation() -> dict[str, object]:
    return {
        "frame": (
            (
                (0, 0, 0, 0),
                (0, 8, 8, 0),
                (0, 8, 8, 0),
                (0, 0, 0, 0),
            ),
        ),
        "dimensions": (4, 4),
        "available_actions": (1, 2, 6),
        "objects": (
            {
                "entity_id": "visible-component",
                "features": ("rendered",),
            },
        ),
        "relations": ("component:inside:frame",),
        "resources": ("bounded-action-budget",),
        "terminal_state": "NOT_FINISHED",
    }


class P10VisualComputeTests(unittest.TestCase):
    def test_rendered_layers_are_runtime_only(self) -> None:
        encoded = DeterministicSymbolSpace().encode(rendered_observation())
        self.assertTrue(encoded.rendered_layers)
        self.assertNotIn("rendered_layers", encoded.__repr__())

    def test_full_kernel_commits_explorer_to_authorized_memory(self) -> None:
        components = Layer0Components(
            context_state=BoundedContextState(action_budget=8),
            candidate_surface=P10VisualCandidateSurface(),
            compute=P10VisualCompute(),
        )
        result = Layer0Kernel(components).run_cycle(rendered_observation())
        self.assertEqual(result.status, "PASS")
        self.assertIsNotNone(result.emission_result)
        self.assertIsNotNone(result.memory_result)
        memory = components.memory
        assert memory is not None
        latest = memory.view().entries[-1].payload
        self.assertEqual(
            latest["format"],
            VISUAL_EXPLORER_MEMORY_FORMAT,
        )
        self.assertIn("visual_explorer", latest)

    def test_memory_from_cycle_one_changes_cycle_two_action(self) -> None:
        components = Layer0Components(
            context_state=BoundedContextState(action_budget=8),
            candidate_surface=P10VisualCandidateSurface(),
            compute=P10VisualCompute(),
        )
        kernel = Layer0Kernel(components)
        first = kernel.run_cycle(rendered_observation())
        second = kernel.run_cycle(rendered_observation())
        assert first.emission_result is not None
        assert second.emission_result is not None
        self.assertNotEqual(
            first.emission_result.candidate_id,
            second.emission_result.candidate_id,
        )
        self.assertNotEqual(
            first.emission_result.action_id,
            second.emission_result.action_id,
        )
        memory = components.memory
        assert memory is not None
        latest = memory.view().entries[-1].payload
        self.assertIs(latest["memory_influenced_decision"], True)
        self.assertEqual(second.compute_memory_version, 1)

    def test_generic_candidate_surface_cannot_substitute_visual_surface(
        self,
    ) -> None:
        components = Layer0Components(
            context_state=BoundedContextState(action_budget=8),
            compute=P10VisualCompute(),
        )
        with self.assertRaisesRegex(
            TypeError,
            "P10 visual candidate surface must be callable",
        ):
            Layer0Kernel(components).run_cycle(rendered_observation())


if __name__ == "__main__":
    unittest.main()
