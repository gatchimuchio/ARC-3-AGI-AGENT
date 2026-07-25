from __future__ import annotations

import unittest

import numpy as np
from arcengine import FrameDataRaw, GameState

from arc3_agi_agent.memory import MemoryOperation, PassiveMemory
from arc3_agi_agent.p10_compute import (
    VISUAL_EXPLORER_MEMORY_FORMAT,
    VISUAL_OPERATOR_VERSION,
    prepare_visual_search_reset,
)
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.search_reset import (
    SEARCH_RESET_REASON,
    HDSSearchResetController,
    PureLLMSearchResetExecutor,
    SearchResetDirective,
    require_search_reset_directive,
)
from arc3_agi_agent.visual_explorer import (
    DeterministicVisualExplorer,
    analyze_scene,
)


def frame(values: list[list[int]]) -> FrameDataRaw:
    result = FrameDataRaw(
        state=GameState.NOT_FINISHED,
        levels_completed=0,
        win_levels=1,
        available_actions=[1, 2],
    )
    result.frame = [np.asarray(values, dtype=np.int8)]
    return result


class SearchResetBoundary:
    def __init__(self, reset_frame: FrameDataRaw) -> None:
        self.reset_frame = reset_frame
        self.calls = 0

    def search_reset(
        self,
        directive: SearchResetDirective,
        decision: object,
        *,
        executor: str,
    ) -> FrameDataRaw:
        require_search_reset_directive(
            directive,
            decision,  # type: ignore[arg-type]
            executor=executor,
        )
        self.calls += 1
        return self.reset_frame


class P10SearchResetTests(unittest.TestCase):
    def test_preparation_requires_disconnected_initial_frontier(self) -> None:
        initial_grid = (
            (0, 0, 0),
            (0, 8, 0),
            (0, 0, 0),
        )
        dead_grid = (
            (0, 0, 0),
            (0, 9, 0),
            (0, 0, 0),
        )
        initial = analyze_scene(initial_grid, (1, 2))
        dead = analyze_scene(dead_grid, (1,))
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(initial)
        explorer.observe(
            dead,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(dead)

        memory = PassiveMemory()
        memory.execute_storage(
            MemoryOperation(
                operation="ADD",
                target="visual-cycle:pending-branch",
                expected_version=0,
                lifecycle="ACTIVE",
                evidence_signature="rendered-transition:pending-branch",
                payload_items=tuple(
                    sorted(
                        {
                            "format": VISUAL_EXPLORER_MEMORY_FORMAT,
                            "operator_version": VISUAL_OPERATOR_VERSION,
                            "visual_explorer": explorer.to_payload(),
                        }.items()
                    )
                ),
                provenance=("rendered-transition",),
            )
        )

        prepared = prepare_visual_search_reset(
            memory.view(),
            dead_grid,
            (1,),
            terminal_state="NOT_FINISHED",
        )

        self.assertIsNotNone(prepared)
        assert prepared is not None
        self.assertEqual(prepared.reason, SEARCH_RESET_REASON)
        self.assertEqual(
            prepared.memory_payload["search_reset_reason"],
            SEARCH_RESET_REASON,
        )
        self.assertNotIn("game_id", repr(prepared.memory_payload))
        self.assertNotIn("level_id", repr(prepared.memory_payload))

    def test_preparation_preserves_candidate_causal_context_mode(
        self,
    ) -> None:
        initial_grid = (
            (0, 0, 0),
            (0, 8, 0),
            (0, 0, 0),
        )
        dead_grid = (
            (0, 0, 0),
            (0, 9, 0),
            (0, 0, 0),
        )
        initial = analyze_scene(initial_grid, (1, 2))
        dead = analyze_scene(dead_grid, (1,))
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(
            initial,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(
            initial,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            dead,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(
            dead,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            dead,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(
            dead,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            dead,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        stalled = explorer.decide(
            dead,
            causal_context_mode="one-step-visible",
        )
        self.assertEqual(stalled.reason, SEARCH_RESET_REASON)

        memory = PassiveMemory()
        memory.execute_storage(
            MemoryOperation(
                operation="ADD",
                target="visual-cycle:causal-context-branch",
                expected_version=0,
                lifecycle="ACTIVE",
                evidence_signature="rendered-transition:causal-context",
                payload_items=tuple(
                    sorted(
                        {
                            "format": VISUAL_EXPLORER_MEMORY_FORMAT,
                            "operator_version": VISUAL_OPERATOR_VERSION,
                            "visual_explorer": explorer.to_payload(),
                        }.items()
                    )
                ),
                provenance=("rendered-transition",),
            )
        )

        prepared = prepare_visual_search_reset(
            memory.view(),
            dead_grid,
            (1,),
            terminal_state="NOT_FINISHED",
        )

        self.assertIsNotNone(prepared)
        assert prepared is not None
        retained = prepared.memory_payload["visual_explorer"]
        assert isinstance(retained, dict)
        self.assertEqual(
            retained["causal_context_extension_format"],
            "arc3-one-step-visible-causal-context-v1",
        )

    def test_controller_executor_retains_memory_without_rollback(self) -> None:
        memory = PassiveMemory()
        controller = HDSSearchResetController()
        payload = {
            "format": VISUAL_EXPLORER_MEMORY_FORMAT,
            "operator_version": VISUAL_OPERATOR_VERSION,
            "search_reset_reason": SEARCH_RESET_REASON,
        }
        decision = controller.judge(
            observation_signature="frame:rendered-branch",
            reason=SEARCH_RESET_REASON,
            action_count=3,
            memory_version=0,
            evidence_signature="search-frontier:observed",
        )
        directive = controller.directive(
            decision,
            memory_target="visual-search-reset:observed",
            memory_payload=payload,
        )
        boundary = SearchResetBoundary(frame([[0, 0], [0, 1]]))

        execution = PureLLMSearchResetExecutor().execute(
            directive,
            decision,
            payload,
            memory,
            boundary,
        )

        self.assertEqual(boundary.calls, 1)
        self.assertEqual(execution.memory_version_before, 0)
        self.assertEqual(execution.memory_version_after, 1)
        self.assertEqual(memory.view().entries[-1].lifecycle, "ACTIVE")
        self.assertFalse(decision.allow_memory_rollback)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "SEARCH_RESET_DIRECTIVE_ALREADY_CONSUMED",
        ):
            PureLLMSearchResetExecutor().execute(
                directive,
                decision,
                payload,
                memory,
                boundary,
            )
        self.assertEqual(boundary.calls, 1)

    def test_forged_or_unproven_reset_is_rejected(self) -> None:
        controller = HDSSearchResetController()
        with self.assertRaisesRegex(
            AuthorityViolation,
            "SEARCH_RESET_REQUIRES_DISCONNECTED_FRONTIER",
        ):
            controller.judge(
                observation_signature="frame:rendered-branch",
                reason="VISUAL_FRONTIER_EXHAUSTED",
                action_count=3,
                memory_version=0,
                evidence_signature="search-frontier:exhausted",
            )

        decision = controller.judge(
            observation_signature="frame:rendered-branch",
            reason=SEARCH_RESET_REASON,
            action_count=3,
            memory_version=0,
            evidence_signature="search-frontier:observed",
        )
        forged = SearchResetDirective(
            decision_id=decision.decision_id,
            observation_signature=decision.observation_signature,
            expected_memory_version=0,
            memory_target="visual-search-reset:forged",
            memory_payload_digest="forged",
        )
        boundary = SearchResetBoundary(frame([[0, 0], [0, 1]]))
        with self.assertRaisesRegex(
            AuthorityViolation,
            "SEARCH_RESET_DIRECTIVE_NOT_ISSUED_BY_HDS",
        ):
            PureLLMSearchResetExecutor().execute(
                forged,
                decision,
                {"format": "forged"},
                PassiveMemory(),
                boundary,
            )
        self.assertEqual(boundary.calls, 0)


if __name__ == "__main__":
    unittest.main()
