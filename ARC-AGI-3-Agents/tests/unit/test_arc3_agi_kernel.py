from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.adapters.in_memory import InMemoryEmissionInterface
from arc3_agi_agent.audit import run_required_removal_audit
from arc3_agi_agent.context import BoundedContextState
from arc3_agi_agent.ir import CandidateIR
from arc3_agi_agent.kernel import Layer0Components, Layer0Kernel
from arc3_agi_agent.memory import PassiveMemory
from arc3_agi_agent.protocol import (
    LAYER0_ROOTS,
    AuthorityViolation,
    EmissionDirective,
    HDSDecision,
    MemoryDirective,
)
from arc3_agi_agent.roles import (
    CANDIDATE_MODES,
    ROLE_FAILURE_REASONS,
    DeterministicSuccessCriterion,
    Layer0FunctionalLoss,
)
from arc3_agi_agent.schema import digest_object, forbidden_runtime_paths
from arc3_agi_agent.verification import (
    RenderedObservation,
    verify_rendered_transition,
)


def valid_raw_observation() -> dict[str, object]:
    return {
        "frame": [[0, 1], [1, 0]],
        "dimensions": [2, 2],
        "available_actions": [2, 1],
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


def allowed_decision() -> HDSDecision:
    return HDSDecision(
        command_id="command:1",
        decision_id="decision:1",
        status="EMIT",
        candidate_id="candidate:1",
        closure_signature="closure:1",
        allow_memory_write=True,
        allow_external_emit=True,
    )


def candidate(action_id: int = 1) -> CandidateIR:
    return CandidateIR(
        candidate_id="candidate:1",
        mode="ACTION",
        steps=({"action_id": action_id},),
        preconditions=(f"ACTION{action_id}_AVAILABLE",),
        expected_effects_by_hypothesis={"hypothesis:1": ("VISIBLE_STATE_CHANGE",)},
        provenance=("current-observation",),
        falsification_conditions=("unexpected rendered effect",),
    )


class TrinityAuthorityTests(unittest.TestCase):
    def test_compute_requires_consumable_hds_command(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        context = components.context_state.ingest(observation)
        memory = components.memory.view()

        with self.assertRaisesRegex(AuthorityViolation, "HDS_COMMAND_REQUIRED"):
            components.compute.compute(
                None,
                components.hds,
                observation,
                context,
                memory,
                components.world_model,
                components.candidate_surface,
            )

        command = components.hds.issue_compute(observation, context)
        components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_ALREADY_CONSUMED",
        ):
            components.compute.compute(
                command,
                components.hds,
                observation,
                context,
                memory,
                components.world_model,
                components.candidate_surface,
            )

    def test_memory_is_passive_and_rejects_unapproved_write(self) -> None:
        memory = PassiveMemory()
        before = memory.view()
        denied = HDSDecision(
            command_id="command:1",
            decision_id="decision:1",
            status="SUSPEND",
        )
        directive = MemoryDirective(
            command_id="command:1",
            decision_id="decision:1",
            operation="ADD",
            target="hypothesis:1",
            lifecycle="PROPOSED",
            evidence_signature="evidence:1",
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_WRITE_NOT_AUTHORIZED",
        ):
            memory.apply_authorized(
                directive,
                denied,
                {"claim": "bounded proposal"},
                executor="pure-llm",
            )
        self.assertEqual(memory.view(), before)

    def test_external_emit_rejects_missing_approval(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        denied = HDSDecision(
            command_id="command:1",
            decision_id="decision:1",
            status="SUSPEND",
        )
        directive = EmissionDirective(
            command_id="command:1",
            decision_id="decision:1",
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id="candidate:1",
            closure_signature="closure:1",
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EXTERNAL_EMIT_NOT_AUTHORIZED",
        ):
            InMemoryEmissionInterface().emit(
                directive,
                denied,
                candidate(),
                observation,
                executor="pure-llm",
            )

    def test_forged_hds_labels_do_not_authorize_write_or_emit(self) -> None:
        decision = allowed_decision()
        memory_directive = MemoryDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            operation="ADD",
            target="hypothesis:1",
            lifecycle="PROPOSED",
            evidence_signature=decision.closure_signature,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_DECISION_INVALID",
        ):
            PassiveMemory().apply_authorized(
                memory_directive,
                decision,
                {"claim": "forged-label"},
                executor="pure-llm",
            )

        emission_directive = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id=decision.candidate_id or "",
            closure_signature=decision.closure_signature,
        )
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_DECISION_INVALID",
        ):
            InMemoryEmissionInterface().emit(
                emission_directive,
                decision,
                candidate(),
                observation,
                executor="pure-llm",
            )

    def test_emit_rejects_candidate_and_closure_mismatch(self) -> None:
        decision = allowed_decision()
        wrong_candidate = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id="candidate:other",
            closure_signature=decision.closure_signature,
        )
        self.assertIn(
            "EMISSION_CANDIDATE_MISMATCH",
            wrong_candidate.validate(decision),
        )

        missing_closure = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id=decision.candidate_id or "",
        )
        self.assertIn(
            "EMISSION_CLOSURE_MISSING",
            missing_closure.validate(decision),
        )

    def test_emit_rejects_action_not_currently_available(self) -> None:
        components = Layer0Components()
        raw = valid_raw_observation()
        raw["available_actions"] = [2]
        observation = components.symbol_space.encode(raw)
        decision = allowed_decision()
        directive = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id=decision.candidate_id or "",
            closure_signature=decision.closure_signature,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EMISSION_ACTION_NOT_AVAILABLE",
        ):
            InMemoryEmissionInterface().emit(
                directive,
                decision,
                candidate(),
                observation,
                executor="pure-llm",
            )

    def test_invalid_hds_decision_cannot_write_or_emit(self) -> None:
        invalid = HDSDecision(
            command_id="command:1",
            decision_id="decision:1",
            status="INVALID",
            candidate_id="candidate:1",
            closure_signature="closure:1",
            allow_memory_write=True,
            allow_external_emit=True,
        )
        memory_directive = MemoryDirective(
            command_id="command:1",
            decision_id="decision:1",
            operation="ADD",
            target="hypothesis:1",
            lifecycle="PROPOSED",
            evidence_signature="evidence:1",
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_DECISION_INVALID",
        ):
            PassiveMemory().apply_authorized(
                memory_directive,
                invalid,
                {"claim": "proposal"},
                executor="pure-llm",
            )

        emission_directive = EmissionDirective(
            command_id="command:1",
            decision_id="decision:1",
            action_id=1,
            reasoning_digest="reason:1",
            candidate_id="candidate:1",
            closure_signature="closure:1",
        )
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_DECISION_INVALID",
        ):
            InMemoryEmissionInterface().emit(
                emission_directive,
                invalid,
                candidate(),
                observation,
                executor="pure-llm",
            )

    def test_hds_revalidates_closure_instead_of_trusting_pass_label(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        context = components.context_state.ingest(observation)
        command = components.hds.issue_compute(observation, context)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            components.memory.view(),
            components.world_model,
            components.candidate_surface,
        )
        context = components.context_state.condition(proposal.hypotheses)
        closures = components.success_criterion.evaluate(
            observation,
            context,
            proposal.hypotheses,
            proposal.candidates,
        )
        modes = {
            item.candidate_id: item.mode for item in proposal.candidates
        }
        tampered = tuple(
            replace(item, mc={})
            if modes[item.candidate_id] in {"ACTION", "BOUNDED_PROBE"}
            else item
            for item in closures
        )
        decision = components.hds.judge(
            command,
            proposal,
            tampered,
            observation,
            context,
        )
        self.assertEqual(decision.status, "SUSPEND")
        self.assertIn(
            "HDS_CLOSURE_REVALIDATION_FAILED",
            decision.reason_codes,
        )

    def test_hds_rejects_forged_complete_closure_score(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        context = components.context_state.ingest(observation)
        command = components.hds.issue_compute(observation, context)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            components.memory.view(),
            components.world_model,
            components.candidate_surface,
        )
        context = components.context_state.condition(proposal.hypotheses)
        closures = components.success_criterion.evaluate(
            observation,
            context,
            proposal.hypotheses,
            proposal.candidates,
        )
        modes = {
            item.candidate_id: item.mode for item in proposal.candidates
        }
        tampered = tuple(
            replace(
                item,
                mc={**item.mc, "fit_score": 999.0},
            )
            if modes[item.candidate_id] in {"ACTION", "BOUNDED_PROBE"}
            else item
            for item in closures
        )
        decision = components.hds.judge(
            command,
            proposal,
            tampered,
            observation,
            context,
        )
        self.assertEqual(decision.status, "SUSPEND")
        self.assertFalse(decision.allow_external_emit)
        self.assertIn(
            "HDS_CLOSURE_REVALIDATION_FAILED",
            decision.reason_codes,
        )

    def test_stop_is_terminal_for_kernel(self) -> None:
        raw = valid_raw_observation()
        raw["terminal_state"] = "WIN"
        kernel = Layer0Kernel()
        result = kernel.run_cycle(raw)
        self.assertEqual(result.status, "STOP")
        self.assertEqual(result.decision.status, "STOP")
        with self.assertRaisesRegex(AuthorityViolation, "KERNEL_STOPPED"):
            kernel.run_cycle(valid_raw_observation())


class Layer0FunctionalTests(unittest.TestCase):
    def test_full_set_establishes_one_authorized_cycle(self) -> None:
        result = Layer0Kernel().run_cycle(valid_raw_observation())
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.decision.status, "EMIT")
        self.assertEqual(result.decision.validate(), ())
        self.assertIsNotNone(result.emission_result)
        self.assertIsNotNone(result.memory_result)
        self.assertEqual(len(result.hypotheses), 2)
        self.assertGreaterEqual(len(result.candidates), 2)
        self.assertEqual(
            {item.mode for item in result.candidates},
            set(CANDIDATE_MODES),
        )
        action_closures = tuple(
            closure
            for closure in result.closures
            if closure.mc["mode"] in {"ACTION", "BOUNDED_PROBE"}
        )
        self.assertTrue(action_closures)
        self.assertEqual(
            set(action_closures[0].r["evaluation_axes"]),
            {
                "progress",
                "goal_relevance",
                "hazard",
                "terminal_state",
                "expected_effect_consistency",
                "information_gain",
                "uncertainty",
                "repetition_cost",
                "rollback_cost",
                "action_budget_remaining",
            },
        )
        operations = tuple(event.operation for event in result.trace)
        self.assertIn("COMPUTE_COMMAND_ISSUED", operations)
        self.assertIn("AUTHORIZED_EXTERNAL_EMIT_EXECUTED", operations)
        self.assertIn("AUTHORIZED_MEMORY_WRITE_EXECUTED", operations)
        self.assertIn("EMISSION_RESULT_OBSERVED", operations)
        observed = next(
            event
            for event in result.trace
            if event.operation == "EMISSION_RESULT_OBSERVED"
        )
        self.assertTrue(dict(observed.details)["result"].startswith("hds-observation:"))

    def test_context_history_is_bounded_without_resetting_budget(self) -> None:
        store = BoundedContextState(max_history=1, action_budget=3)
        store.record_emission(1, ("ONE",))
        store.record_emission(2, ("TWO",))
        store.record_emission(3, ("THREE",))
        snapshot = store.snapshot()
        self.assertEqual(snapshot.action_history, (3,))
        self.assertEqual(snapshot.actions_used, 3)
        self.assertEqual(snapshot.remaining_actions, 0)

    def test_each_single_role_removal_has_unique_functional_loss(self) -> None:
        report = run_required_removal_audit(valid_raw_observation())
        self.assertTrue(report.passed)
        self.assertEqual(
            tuple(case.removed_role for case in report.cases),
            LAYER0_ROOTS,
        )
        self.assertEqual(
            tuple(case.failure_reason for case in report.cases),
            tuple(ROLE_FAILURE_REASONS[role] for role in LAYER0_ROOTS),
        )
        self.assertEqual(len(set(report.failure_witnesses)), 6)
        self.assertTrue(all(not case.substitution_observed for case in report.cases))

    def test_role_label_with_no_callable_is_rejected(self) -> None:
        components = Layer0Components(symbol_space=object())
        with self.assertRaises(Layer0FunctionalLoss) as caught:
            Layer0Kernel(components).run_cycle(valid_raw_observation())
        self.assertEqual(caught.exception.role, "SYMBOL_SPACE")
        self.assertEqual(
            caught.exception.reason,
            "SYMBOL_SPACE_CALLABLE_MISSING",
        )
        self.assertFalse(caught.exception.removed)


class ClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.components = Layer0Components()
        self.observation = self.components.symbol_space.encode(valid_raw_observation())
        self.context_store = BoundedContextState()
        self.context = self.context_store.ingest(self.observation)
        self.hypotheses = self.components.world_model.transform(
            self.observation,
            self.context,
            self.components.memory.view(),
        )
        self.candidates = self.components.candidate_surface.generate(
            self.observation,
            self.context,
            self.hypotheses,
        )
        self.criterion = DeterministicSuccessCriterion()

    def test_missing_x_r_or_mc_suspends(self) -> None:
        missing_x_observation = replace(
            self.observation,
            frame_signature="",
            structural_signature="",
        )
        missing_x = self.criterion.evaluate(
            missing_x_observation,
            self.context,
            self.hypotheses,
            (self.candidates[0],),
        )[0]
        self.assertEqual(missing_x.status, "SUSPEND")
        self.assertIn("X", missing_x.missing_terms)

        missing_r_candidate = replace(
            self.candidates[0],
            preconditions=(),
            expected_effects_by_hypothesis={},
            falsification_conditions=(),
        )
        missing_r = self.criterion.evaluate(
            self.observation,
            self.context,
            self.hypotheses,
            (missing_r_candidate,),
        )[0]
        self.assertEqual(missing_r.status, "SUSPEND")
        self.assertEqual(missing_r.missing_terms, ("R",))

        missing_mc_candidate = replace(self.candidates[0], provenance=())
        missing_mc = self.criterion.evaluate(
            self.observation,
            self.context,
            self.hypotheses,
            (missing_mc_candidate,),
        )[0]
        self.assertEqual(missing_mc.status, "SUSPEND")
        self.assertEqual(missing_mc.missing_terms, ("Mc",))

    def test_unobserved_terminal_suspends(self) -> None:
        raw = valid_raw_observation()
        raw["terminal_state"] = "UNKNOWN"
        result = Layer0Kernel().run_cycle(raw)
        self.assertEqual(result.status, "SUSPEND")
        self.assertEqual(result.decision.status, "SUSPEND")
        self.assertIsNone(result.emission_result)

    def test_invalid_terminal_is_normalized_to_unobserved(self) -> None:
        raw = valid_raw_observation()
        raw["terminal_state"] = "UNTRUSTED_VALUE"
        result = Layer0Kernel().run_cycle(raw)
        self.assertEqual(result.observation.terminal_state, "UNKNOWN")
        self.assertEqual(result.status, "SUSPEND")

    def test_hazard_vetoes_action(self) -> None:
        raw = valid_raw_observation()
        raw["effects"] = ["HAZARD"]
        result = Layer0Kernel().run_cycle(raw)
        self.assertEqual(result.status, "REJECT")
        self.assertEqual(result.decision.status, "REJECT")
        self.assertIn("HAZARD_ACTION_VETO", result.decision.reason_codes)
        self.assertIsNone(result.emission_result)

    def test_expected_effect_mismatch_does_not_pass(self) -> None:
        before = RenderedObservation(
            signature="before",
            levels_completed=0,
            terminal_state="RUNNING",
            visible_progress=False,
            visible_effects=(),
            available_actions=(1,),
            action_count=0,
            max_actions=8,
        )
        after = replace(
            before,
            signature="after",
            visible_effects=("UNEXPECTED_EFFECT",),
            action_count=1,
        )
        result = verify_rendered_transition(before, after, 1, ("MOVED",))
        self.assertNotEqual(result.status, "PASS")
        self.assertEqual(result.commitment_status, "FAIL")


class GenericityAndDeterminismTests(unittest.TestCase):
    def test_runtime_identity_variants_are_rejected(self) -> None:
        forbidden_bases = (
            "game_id",
            "task_id",
            "level_id",
            "replay_index",
            "answer_map",
            "fixed_action_sequence",
            "literal_coordinate_table",
            "source_state",
            "hidden_state",
        )
        for base in forbidden_bases:
            parts = base.split("_")
            variants = (
                base,
                parts[0] + "".join(part.title() for part in parts[1:]),
                "".join(part.title() for part in parts),
            )
            for key in variants:
                with self.subTest(key=key):
                    value = {"runtime": {key: "forbidden"}}
                    self.assertTrue(forbidden_runtime_paths(value))
                    raw = valid_raw_observation()
                    raw["metadata"] = value
                    with self.assertRaisesRegex(
                        ValueError,
                        "FORBIDDEN_RUNTIME_IDENTITY",
                    ):
                        Layer0Kernel().run_cycle(raw)

    def test_same_initial_state_has_same_candidates_closure_and_trace(self) -> None:
        first = Layer0Kernel().run_cycle(valid_raw_observation())
        second = Layer0Kernel().run_cycle(valid_raw_observation())
        self.assertEqual(
            tuple(item.candidate_id for item in first.candidates),
            tuple(item.candidate_id for item in second.candidates),
        )
        self.assertEqual(first.closures, second.closures)
        self.assertEqual(
            digest_object(first.closures),
            digest_object(second.closures),
        )
        self.assertEqual(first.trace, second.trace)
        self.assertEqual(first.trace_digest, second.trace_digest)


if __name__ == "__main__":
    unittest.main()
