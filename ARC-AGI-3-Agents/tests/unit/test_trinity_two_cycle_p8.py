from __future__ import annotations

import dataclasses
import unittest
from dataclasses import replace
from typing import cast

from arc3_agi_agent.context import BoundedContextState
from arc3_agi_agent.instruction_body import InstructionBody
from arc3_agi_agent.judgment import HDSFramePolicy
from arc3_agi_agent.kernel import (
    HDSController,
    Layer0Components,
    Layer0Kernel,
)
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.roles import (
    DeterministicCandidateSurface,
    DeterministicSuccessCriterion,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
)
from arc3_agi_agent.schema import forbidden_runtime_paths
from arc3_agi_agent.trinity import run_trinity_two_cycle_audit


def raw_observation() -> dict[str, object]:
    return {
        "frame": [[0, 1], [1, 0]],
        "dimensions": [2, 2],
        "available_actions": [1, 2, 3],
        "objects": [
            {
                "entity_id": "actor",
                "features": ["controllable", "foreground"],
            }
        ],
        "relations": ["adjacent"],
        "resources": ["bounded-action-budget"],
        "terminal_state": "RUNNING",
    }


class TrinityTwoCycleTests(unittest.TestCase):
    def test_two_full_cycles_preserve_authority_order_and_memory_causality(
        self,
    ) -> None:
        report = run_trinity_two_cycle_audit(raw_observation())
        evidence = report.cycle_evidence

        self.assertTrue(report.passed)
        self.assertTrue(evidence.passed)
        self.assertEqual(evidence.cycle_1_status, "PASS")
        self.assertEqual(evidence.cycle_2_status, "PASS")
        self.assertEqual(evidence.cycle_1_compute_memory_version, 0)
        self.assertEqual(evidence.cycle_1_after_memory_version, 1)
        self.assertEqual(evidence.cycle_2_compute_memory_version, 1)
        self.assertEqual(evidence.cycle_2_after_memory_version, 2)
        self.assertEqual(
            evidence.cycle_2_compute_memory_digest,
            evidence.cycle_1_after_memory_digest,
        )
        self.assertTrue(evidence.behavior_changed)

    def test_m_only_change_alters_c_output_with_p_and_j_fixed(self) -> None:
        case = run_trinity_two_cycle_audit(raw_observation()).m_only

        self.assertTrue(case.passed)
        self.assertEqual(case.changed_inputs, ("M",))
        self.assertEqual(
            case.baseline.instruction_body_digest,
            case.variant.instruction_body_digest,
        )
        self.assertEqual(
            case.baseline.frame_policy_digest,
            case.variant.frame_policy_digest,
        )
        self.assertIn("predictions", case.changed_outputs)
        self.assertEqual(case.variant.cited_memory_version, 1)
        self.assertEqual(
            case.variant.cited_memory_digest,
            case.variant.memory_digest,
        )

    def test_p_only_change_alters_c_output_with_j_and_m_fixed(self) -> None:
        case = run_trinity_two_cycle_audit(raw_observation()).p_only

        self.assertTrue(case.passed)
        self.assertEqual(case.changed_inputs, ("P",))
        self.assertEqual(
            case.baseline.frame_policy_digest,
            case.variant.frame_policy_digest,
        )
        self.assertEqual(
            case.baseline.memory_digest,
            case.variant.memory_digest,
        )
        self.assertTrue(
            {"hypotheses", "predictions", "candidates"}
            & set(case.changed_outputs)
        )

    def test_j_only_change_alters_judgment_not_compute(self) -> None:
        case = run_trinity_two_cycle_audit(raw_observation()).j_only

        self.assertTrue(case.passed)
        self.assertEqual(case.changed_inputs, ("J",))
        self.assertEqual(case.baseline.proposal_digest, case.variant.proposal_digest)
        self.assertEqual(
            case.baseline.hypotheses_digest,
            case.variant.hypotheses_digest,
        )
        self.assertEqual(
            case.baseline.predictions_digest,
            case.variant.predictions_digest,
        )
        self.assertEqual(case.baseline.judgment_status, "ACCEPT")
        self.assertEqual(case.variant.judgment_status, "STOP")
        self.assertFalse(
            {"proposal", "hypotheses", "predictions", "candidates"}
            & set(case.changed_outputs)
        )
        self.assertTrue(
            {"judgment", "judgment_status", "authorization"}
            <= set(case.changed_outputs)
        )

    def test_report_is_deterministic_identity_free_and_has_no_hidden_delta(
        self,
    ) -> None:
        first = run_trinity_two_cycle_audit(raw_observation())
        second = run_trinity_two_cycle_audit(raw_observation())

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertTrue(first.deterministic_probe_replay)
        self.assertFalse(first.hidden_global_state_observed)
        self.assertFalse(first.authority_violation_observed)
        self.assertEqual(
            forbidden_runtime_paths(dataclasses.asdict(first)),
            (),
        )

    def test_invalid_j_frame_policy_fails_closed_before_effects(self) -> None:
        components = Layer0Components(
            hds=HDSController(
                frame_policy=HDSFramePolicy(purpose=""),
            )
        )
        memory = components.memory
        assert memory is not None
        before = memory.view()

        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_FRAME_POLICY_INVALID",
        ):
            Layer0Kernel(components).run_cycle(raw_observation())
        self.assertEqual(memory.view(), before)

    def test_hds_rejects_compute_memory_citation_substitution(self) -> None:
        components = Layer0Components()
        memory = components.memory
        compute = components.compute
        assert memory is not None
        assert compute is not None
        symbol_space = cast(
            DeterministicSymbolSpace,
            components.symbol_space,
        )
        context_state = cast(BoundedContextState, components.context_state)
        world_model = cast(
            DeterministicWorldModel,
            components.world_model,
        )
        candidate_surface = cast(
            DeterministicCandidateSurface,
            components.candidate_surface,
        )
        success_criterion = cast(
            DeterministicSuccessCriterion,
            components.success_criterion,
        )
        instruction_body = cast(InstructionBody, components.instruction_body)
        observation = symbol_space.encode(raw_observation())
        context = context_state.ingest(observation)
        memory_view = memory.view()
        command = components.hds.issue_compute(
            observation,
            context,
            memory_view,
        )
        proposal = compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory_view,
            world_model,
            candidate_surface,
            instruction_body,
        )
        conditioned = context_state.condition(proposal.hypotheses)
        closures = success_criterion.evaluate(
            observation,
            conditioned,
            proposal.hypotheses,
            proposal.candidates,
        )

        with self.assertRaisesRegex(
            AuthorityViolation,
            "PROPOSAL_MEMORY_CITATION_MISMATCH",
        ):
            components.hds.judge(
                command,
                replace(proposal, memory_view_digest="forged-memory-view"),
                closures,
                observation,
                conditioned,
            )
        self.assertEqual(memory.view(), memory_view)


if __name__ == "__main__":
    unittest.main()
