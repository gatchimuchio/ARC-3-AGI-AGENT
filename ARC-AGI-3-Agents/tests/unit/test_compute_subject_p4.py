from __future__ import annotations

import unittest

from arc3_agi_agent.audit import run_compute_subject_removal_audit
from arc3_agi_agent.context import BoundedContextState, ContextSnapshot
from arc3_agi_agent.instruction_body import (
    INSTRUCTION_BODY_REMOVAL_WITNESS,
    InstructionBody,
    load_default_parametric_instruction_body,
    load_default_symbolic_instruction_body,
)
from arc3_agi_agent.ir import ObservationIR, OutputProposalIR
from arc3_agi_agent.kernel import (
    COMPUTE_SUBJECT_REMOVAL_WITNESS,
    ComputeProposal,
    Layer0Components,
    Layer0Kernel,
    PureLLMCompute,
)
from arc3_agi_agent.memory import MemorySnapshot
from arc3_agi_agent.protocol import ComputeRequest, HDSDecision
from arc3_agi_agent.roles import (
    DeterministicCandidateSurface,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
    Layer0FunctionalLoss,
)


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


def compute_fixture() -> tuple[
    ObservationIR,
    ContextSnapshot,
    MemorySnapshot,
]:
    observation = DeterministicSymbolSpace().encode(raw_observation())
    context = BoundedContextState().ingest(observation)
    return observation, context, MemorySnapshot(version=0, entries=())


def request_for(
    body: InstructionBody,
    observation: ObservationIR,
    context: ContextSnapshot,
    memory: MemorySnapshot,
) -> ComputeRequest:
    return ComputeRequest(
        command_id="standalone:p4-proof",
        operation="LLM_COMPUTE",
        observation_signature=observation.frame_signature,
        context_signature=context.digest,
        memory_signature=memory.digest,
        contract_version=body.contract.version,
        feature_tokens=observation.feature_tokens,
    )


def standalone(
    body: InstructionBody,
    observation: ObservationIR,
    context: ContextSnapshot,
    memory: MemorySnapshot,
) -> ComputeProposal:
    return PureLLMCompute().compute_standalone(
        request_for(body, observation, context, memory),
        observation,
        context,
        body,
        DeterministicWorldModel(),
        DeterministicCandidateSurface(),
        memory,
    )


class ComputeSubjectP4Tests(unittest.TestCase):
    def test_symbolic_and_parametric_bodies_are_swappable_and_deterministic(
        self,
    ) -> None:
        observation, context, memory = compute_fixture()
        symbolic = load_default_symbolic_instruction_body()
        parametric = load_default_parametric_instruction_body()

        symbolic_first = standalone(symbolic, observation, context, memory)
        symbolic_second = standalone(symbolic, observation, context, memory)
        parametric_first = standalone(parametric, observation, context, memory)
        parametric_second = standalone(parametric, observation, context, memory)

        self.assertEqual(symbolic_first, symbolic_second)
        self.assertEqual(parametric_first, parametric_second)
        self.assertNotEqual(symbolic_first.digest, parametric_first.digest)
        self.assertNotEqual(
            symbolic_first.instruction_body_format,
            parametric_first.instruction_body_format,
        )
        self.assertNotEqual(
            symbolic_first.predictions,
            parametric_first.predictions,
        )

    def test_compute_standalone_satisfies_g1_without_authority_effects(self) -> None:
        observation, context, memory = compute_fixture()
        proposal = standalone(
            load_default_symbolic_instruction_body(),
            observation,
            context,
            memory,
        )

        self.assertGreaterEqual(len(proposal.hypotheses), 2)
        self.assertIn(
            "counter-hypothesis",
            {item.hypothesis_type for item in proposal.hypotheses},
        )
        self.assertEqual(
            {item.action_id for item in proposal.predictions},
            set(observation.available_actions),
        )
        self.assertGreaterEqual(len(proposal.candidates), 2)
        self.assertEqual(len(proposal.output_proposals), len(proposal.predictions))
        self.assertTrue(proposal.memory_proposal.payload())
        self.assertTrue(proposal.provenance)
        self.assertTrue(0.0 <= proposal.uncertainty <= 1.0)
        self.assertFalse(
            any(
                isinstance(value, HDSDecision)
                for value in (
                    *proposal.hypotheses,
                    *proposal.candidates,
                    *proposal.output_proposals,
                )
            )
        )
        self.assertEqual(memory, MemorySnapshot(version=0, entries=()))
        self.assertTrue(
            all(isinstance(item, OutputProposalIR) for item in proposal.output_proposals)
        )
        self.assertTrue(
            all(not hasattr(item, "emit") for item in proposal.output_proposals)
        )

    def test_instruction_query_changes_with_state_without_mutating_body(
        self,
    ) -> None:
        observation, context, memory = compute_fixture()
        body = load_default_symbolic_instruction_body()
        initial_digest = body.digest()
        first = body.query(
            request_for(body, observation, context, memory),
            observation,
            context,
            memory,
        )
        state = BoundedContextState()
        state.ingest(observation)
        changed_context = state.record_emission(1, ("NO_VISIBLE_CHANGE",))
        second = body.query(
            request_for(body, observation, changed_context, memory),
            observation,
            changed_context,
            memory,
        )

        self.assertNotEqual(first.query_digest, second.query_digest)
        self.assertNotEqual(first.predictions, second.predictions)
        self.assertEqual(body.digest(), initial_digest)

    def test_kernel_binds_p_and_updates_m_without_updating_p(self) -> None:
        components = Layer0Components()
        body = components.instruction_body
        self.assertIsInstance(body, InstructionBody)
        assert isinstance(body, InstructionBody)
        initial_digest = body.digest()
        initial_version = body.body_version

        result = Layer0Kernel(components).run_cycle(raw_observation())

        self.assertEqual(result.status, "PASS")
        self.assertIsNotNone(result.memory_result)
        self.assertEqual(components.memory.view().version, 1)
        self.assertEqual(body.digest(), initial_digest)
        self.assertEqual(body.body_version, initial_version)
        operations = {event.operation for event in result.trace}
        self.assertIn("INSTRUCTION_BODY_BOUND", operations)
        self.assertIn("INSTRUCTION_BODY_QUERY_EXECUTED", operations)
        self.assertEqual(result.instruction_body_digest, initial_digest)

    def test_p_and_c_removal_have_fixed_non_substituted_witnesses(self) -> None:
        cases = (
            (
                Layer0Components(instruction_body=None),
                "INSTRUCTION_BODY",
                INSTRUCTION_BODY_REMOVAL_WITNESS,
            ),
            (
                Layer0Components(compute=None),
                "COMPUTE_SUBJECT",
                COMPUTE_SUBJECT_REMOVAL_WITNESS,
            ),
        )
        for components, role, witness in cases:
            with self.subTest(role=role):
                with self.assertRaises(Layer0FunctionalLoss) as raised:
                    Layer0Kernel(components).run_cycle(raw_observation())
                self.assertEqual(raised.exception.role, role)
                self.assertEqual(raised.exception.reason, witness)
                self.assertTrue(raised.exception.removed)

    def test_full_p4_removal_audit_covers_l0_p_and_c(self) -> None:
        report = run_compute_subject_removal_audit(raw_observation())

        self.assertTrue(report.passed)
        self.assertEqual(len(report.cases), 8)
        self.assertEqual(
            {case.removed_role for case in report.cases},
            {
                "SYMBOL_SPACE",
                "CONTEXT_STATE",
                "TRANSFORM_OR_WORLD_MODEL",
                "CANDIDATE_SURFACE",
                "FITTING_OR_SUCCESS_CRITERION",
                "EMISSION_INTERFACE",
                "INSTRUCTION_BODY",
                "COMPUTE_SUBJECT",
            },
        )
        self.assertEqual(len(set(report.failure_witnesses)), 8)
        self.assertFalse(any(case.substitution_observed for case in report.cases))


if __name__ == "__main__":
    unittest.main()
