from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.adapters.in_memory import (
    EmissionResult,
    InMemoryEmissionInterface,
    emission_result_signature,
    validate_authorized_emission,
)
from arc3_agi_agent.audit import run_required_removal_audit
from arc3_agi_agent.context import BoundedContextState
from arc3_agi_agent.ir import CandidateIR, ObservationIR
from arc3_agi_agent.kernel import (
    Layer0Components,
    Layer0Kernel,
    MemoryProposal,
)
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


def authorized_cycle() -> tuple[object, ...]:
    components = Layer0Components()
    observation = components.symbol_space.encode(valid_raw_observation())
    context = components.context_state.ingest(observation)
    memory = components.memory.view()
    command = components.hds.issue_compute(observation, context, memory)
    proposal = components.compute.compute(
        command,
        components.hds,
        observation,
        context,
        memory,
        components.world_model,
        components.candidate_surface,
        components.instruction_body,
    )
    context = components.context_state.condition(proposal.hypotheses)
    closures = components.success_criterion.evaluate(
        observation,
        context,
        proposal.hypotheses,
        proposal.candidates,
    )
    decision = components.hds.judge(
        command,
        proposal,
        closures,
        observation,
        context,
    )
    selected = next(
        item
        for item in proposal.candidates
        if item.candidate_id == decision.candidate_id
    )
    return (
        components,
        observation,
        context,
        command,
        proposal,
        closures,
        decision,
        selected,
    )


class HazardousInMemoryEmissionInterface(InMemoryEmissionInterface):
    def emit(
        self,
        directive: EmissionDirective,
        decision: HDSDecision,
        selected: CandidateIR,
        observation: ObservationIR,
        *,
        executor: str,
    ) -> EmissionResult:
        action_id, receipt = validate_authorized_emission(
            directive,
            decision,
            selected,
            observation,
            executor=executor,
        )
        directive_signature = digest_object(directive)
        result_signature = emission_result_signature(
            candidate_id=selected.candidate_id,
            action_id=action_id,
            status="EMITTED_IN_MEMORY",
            command_id=directive.command_id,
            decision_id=directive.decision_id,
            closure_signature=directive.closure_signature,
            observation_signature=directive.observation_signature,
            result_observation_signature=directive.observation_signature,
            directive_signature=directive_signature,
            visible_effects=("HAZARD",),
            terminal_state="GAME_OVER",
            levels_completed=0,
        )
        directive.bind_receipt(receipt, result_signature)
        return EmissionResult(
            candidate_id=selected.candidate_id,
            action_id=action_id,
            status="EMITTED_IN_MEMORY",
            result_signature=result_signature,
            command_id=directive.command_id,
            decision_id=directive.decision_id,
            closure_signature=directive.closure_signature,
            observation_signature=directive.observation_signature,
            result_observation_signature=directive.observation_signature,
            directive_signature=directive_signature,
            visible_effects=("HAZARD",),
            terminal_state="GAME_OVER",
            _authorization_receipt=receipt,
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
                components.instruction_body,
            )

        command = components.hds.issue_compute(observation, context, memory)
        copied_command = replace(command)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_NOT_OWNED_BY_CONTROLLER",
        ):
            components.compute.compute(
                copied_command,
                components.hds,
                observation,
                context,
                memory,
                components.world_model,
                components.candidate_surface,
                components.instruction_body,
            )
        changed_raw = valid_raw_observation()
        changed_raw["frame"] = [[1, 1], [1, 0]]
        changed_observation = components.symbol_space.encode(changed_raw)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_OBSERVATION_MISMATCH",
        ):
            components.compute.compute(
                command,
                components.hds,
                changed_observation,
                context,
                memory,
                components.world_model,
                components.candidate_surface,
                components.instruction_body,
            )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_CONTEXT_MISMATCH",
        ):
            components.compute.compute(
                command,
                components.hds,
                observation,
                replace(context, version=context.version + 1),
                memory,
                components.world_model,
                components.candidate_surface,
                components.instruction_body,
            )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_MEMORY_MISMATCH",
        ):
            components.compute.compute(
                command,
                components.hds,
                observation,
                context,
                replace(memory, version=memory.version + 1),
                components.world_model,
                components.candidate_surface,
                components.instruction_body,
            )
        components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
            components.instruction_body,
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
                components.instruction_body,
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
        bool_action = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=True,
            reasoning_digest="reason:1",
            candidate_id=decision.candidate_id or "",
            closure_signature=decision.closure_signature,
            observation_signature="frame:1",
        )
        self.assertIn(
            "EMISSION_ACTION_INVALID",
            bool_action.validate(decision),
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
        memory = components.memory.view()
        command = components.hds.issue_compute(observation, context, memory)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
            components.instruction_body,
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
        memory = components.memory.view()
        command = components.hds.issue_compute(observation, context, memory)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
            components.instruction_body,
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

    def test_hds_rejects_boolean_action_ids_as_non_actions(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        context = components.context_state.ingest(observation)
        memory = components.memory.view()
        command = components.hds.issue_compute(observation, context, memory)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
            components.instruction_body,
        )
        original = next(
            item
            for item in proposal.candidates
            if item.mode in {"ACTION", "BOUNDED_PROBE"}
        )
        boolean_action = replace(
            original,
            steps=({"action_id": True},),
            preconditions=("ACTIONTrue_AVAILABLE",),
        )
        proposal = replace(
            proposal,
            candidates=tuple(
                boolean_action if item is original else item
                for item in proposal.candidates
            ),
        )
        context = components.context_state.condition(proposal.hypotheses)
        closures = components.success_criterion.evaluate(
            observation,
            context,
            proposal.hypotheses,
            proposal.candidates,
        )
        target_closure = next(
            item
            for item in closures
            if item.candidate_id == boolean_action.candidate_id
        )
        self.assertEqual(target_closure.status, "REJECT")
        self.assertIn("ACTION_NOT_AVAILABLE", target_closure.reason_codes)
        decision = components.hds.judge(
            command,
            proposal,
            closures,
            observation,
            context,
        )
        self.assertEqual(decision.status, "EMIT")
        self.assertNotEqual(decision.candidate_id, boolean_action.candidate_id)

    def test_hds_judgment_rejects_substituted_observation_or_context(self) -> None:
        components = Layer0Components()
        observation = components.symbol_space.encode(valid_raw_observation())
        context = components.context_state.ingest(observation)
        memory = components.memory.view()
        command = components.hds.issue_compute(observation, context, memory)
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            memory,
            components.world_model,
            components.candidate_surface,
            components.instruction_body,
        )
        conditioned = components.context_state.condition(proposal.hypotheses)
        closures = components.success_criterion.evaluate(
            observation,
            conditioned,
            proposal.hypotheses,
            proposal.candidates,
        )

        changed_raw = valid_raw_observation()
        changed_raw["frame"] = [[1, 1], [1, 0]]
        changed_observation = components.symbol_space.encode(changed_raw)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_JUDGMENT_OBSERVATION_MISMATCH",
        ):
            components.hds.judge(
                command,
                proposal,
                closures,
                changed_observation,
                conditioned,
            )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_JUDGMENT_CONTEXT_MISMATCH",
        ):
            components.hds.judge(
                command,
                proposal,
                closures,
                observation,
                replace(
                    conditioned,
                    actions_used=conditioned.actions_used + 1,
                ),
            )
        decision = components.hds.judge(
            command,
            proposal,
            closures,
            observation,
            conditioned,
        )
        self.assertEqual(decision.status, "EMIT")

    def test_hds_issues_only_one_decision_per_compute_command(self) -> None:
        (
            components,
            observation,
            context,
            command,
            proposal,
            closures,
            _decision,
            _selected,
        ) = authorized_cycle()
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_COMMAND_ALREADY_JUDGED",
        ):
            components.hds.judge(
                command,
                proposal,
                closures,
                observation,
                context,
            )

    def test_emission_directive_and_result_provenance_are_single_use(self) -> None:
        (
            components,
            observation,
            _context,
            _command,
            _proposal,
            _closures,
            decision,
            selected,
        ) = authorized_cycle()
        directive = components.hds.emission_directive(decision, selected)
        forged_result = EmissionResult(
            candidate_id=selected.candidate_id,
            action_id=directive.action_id,
            status="EMITTED_IN_MEMORY",
            result_signature="forged-result",
            command_id=directive.command_id,
            decision_id=directive.decision_id,
            closure_signature=directive.closure_signature,
            observation_signature=directive.observation_signature,
            directive_signature=digest_object(directive),
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EMISSION_RESULT_AUTHORIZATION_RECEIPT_INVALID",
        ):
            components.hds.observe_emission_result(
                decision,
                directive,
                selected,
                observation,
                forged_result,
            )

        result = components.compute.execute_emission(
            directive,
            decision,
            selected,
            observation,
            components.emission_interface,
        )
        tampered_effects = ("HAZARD",)
        tampered = replace(
            result,
            result_signature=emission_result_signature(
                candidate_id=result.candidate_id,
                action_id=result.action_id,
                status=result.status,
                command_id=result.command_id,
                decision_id=result.decision_id,
                closure_signature=result.closure_signature,
                observation_signature=result.observation_signature,
                result_observation_signature=result.result_observation_signature,
                directive_signature=result.directive_signature,
                visible_effects=tampered_effects,
                terminal_state="GAME_OVER",
                levels_completed=result.levels_completed,
            ),
            visible_effects=tampered_effects,
            terminal_state="GAME_OVER",
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EMISSION_RESULT_AUTHORIZATION_RECEIPT_INVALID",
        ):
            components.hds.observe_emission_result(
                decision,
                directive,
                selected,
                observation,
                tampered,
            )
        self.assertTrue(
            components.hds.observe_emission_result(
                decision,
                directive,
                selected,
                observation,
                result,
            ).startswith("hds-observation:")
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_EMISSION_RESULT_ALREADY_OBSERVED",
        ):
            components.hds.observe_emission_result(
                decision,
                directive,
                selected,
                observation,
                result,
            )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EXTERNAL_EMIT_DIRECTIVE_ALREADY_CONSUMED",
        ):
            components.compute.execute_emission(
                directive,
                decision,
                selected,
                observation,
                components.emission_interface,
            )

    def test_directive_copies_cannot_consume_hds_grants(self) -> None:
        (
            components,
            observation,
            _context,
            _command,
            proposal,
            _closures,
            decision,
            selected,
        ) = authorized_cycle()
        emission_directive = components.hds.emission_directive(
            decision,
            selected,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EXTERNAL_EMIT_DIRECTIVE_NOT_OWNED",
        ):
            components.compute.execute_emission(
                replace(emission_directive),
                decision,
                selected,
                observation,
                components.emission_interface,
            )
        emission_result = components.compute.execute_emission(
            emission_directive,
            decision,
            selected,
            observation,
            components.emission_interface,
        )
        components.hds.observe_emission_result(
            decision,
            emission_directive,
            selected,
            observation,
            emission_result,
        )
        self.assertEqual(
            components.hds.judge_emission_result(decision, emission_result),
            "PASS",
        )

        memory_directive = components.hds.memory_directive(
            decision,
            proposal.memory_proposal,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_WRITE_DIRECTIVE_NOT_OWNED",
        ):
            components.compute.execute_memory(
                replace(memory_directive),
                decision,
                proposal.memory_proposal,
                components.memory,
            )
        result = components.compute.execute_memory(
            memory_directive,
            decision,
            proposal.memory_proposal,
            components.memory,
        )
        self.assertEqual(result.version, 1)

    def test_memory_directive_is_observation_gated_payload_bound_and_single_use(
        self,
    ) -> None:
        (
            components,
            observation,
            _context,
            _command,
            proposal,
            _closures,
            decision,
            selected,
        ) = authorized_cycle()
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_WRITE_REQUIRES_EMISSION_OBSERVATION",
        ):
            components.hds.memory_directive(decision, proposal.memory_proposal)

        emission_directive = components.hds.emission_directive(decision, selected)
        emission_result = components.compute.execute_emission(
            emission_directive,
            decision,
            selected,
            observation,
            components.emission_interface,
        )
        components.hds.observe_emission_result(
            decision,
            emission_directive,
            selected,
            observation,
            emission_result,
        )
        self.assertEqual(
            components.hds.judge_emission_result(
                decision,
                emission_result,
            ),
            "PASS",
        )

        altered = MemoryProposal(
            target=proposal.memory_proposal.target,
            payload_items=(("claim", "not-the-judged-proposal"),),
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_PROPOSAL_PAYLOAD_MISMATCH",
        ):
            components.hds.memory_directive(decision, altered)

        directive = components.hds.memory_directive(
            decision,
            proposal.memory_proposal,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_PAYLOAD_MISMATCH",
        ):
            components.compute.execute_memory(
                directive,
                decision,
                altered,
                components.memory,
            )
        first = components.compute.execute_memory(
            directive,
            decision,
            proposal.memory_proposal,
            components.memory,
        )
        self.assertEqual(first.version, 1)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_WRITE_DIRECTIVE_ALREADY_CONSUMED",
        ):
            components.compute.execute_memory(
                directive,
                decision,
                proposal.memory_proposal,
                components.memory,
            )
        self.assertEqual(components.memory.view().version, 1)

    def test_hds_rejects_selected_candidate_content_substitution(self) -> None:
        (
            components,
            _observation,
            _context,
            _command,
            _proposal,
            _closures,
            decision,
            selected,
        ) = authorized_cycle()
        substituted = replace(
            selected,
            expected_progress=selected.expected_progress + 0.01,
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_SELECTED_CANDIDATE_CONTENT_MISMATCH",
        ):
            components.hds.emission_directive(decision, substituted)

    def test_emission_rejects_an_observation_other_than_the_judged_frame(
        self,
    ) -> None:
        (
            components,
            observation,
            _context,
            _command,
            _proposal,
            _closures,
            decision,
            selected,
        ) = authorized_cycle()
        directive = components.hds.emission_directive(decision, selected)
        changed = valid_raw_observation()
        changed["frame"] = [[1, 1], [1, 0]]
        stale_observation = components.symbol_space.encode(changed)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "EMISSION_OBSERVATION_MISMATCH",
        ):
            components.compute.execute_emission(
                directive,
                decision,
                selected,
                stale_observation,
                components.emission_interface,
            )
        result = components.compute.execute_emission(
            directive,
            decision,
            selected,
            observation,
            components.emission_interface,
        )
        self.assertEqual(result.observation_signature, observation.frame_signature)

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
        kernel = Layer0Kernel()
        result = kernel.run_cycle(valid_raw_observation())
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
        self.assertIn("CYCLE_FINALIZED", operations)
        observed = next(
            event
            for event in result.trace
            if event.operation == "EMISSION_RESULT_OBSERVED"
        )
        self.assertTrue(dict(observed.details)["result"].startswith("hds-observation:"))
        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_CYCLE_ALREADY_FINALIZED",
        ):
            kernel.components.hds.finalize_cycle(
                result.decision,
                result.emission_result,
                result.memory_result,
                kernel.components.context_state.snapshot(),
                kernel.components.memory.view(),
            )

    def test_hazard_veto_precedes_unknown_state_and_exhausted_budget(self) -> None:
        unknown_hazard = valid_raw_observation()
        unknown_hazard["terminal_state"] = "UNKNOWN"
        unknown_hazard["effects"] = ["HAZARD"]
        unknown_result = Layer0Kernel().run_cycle(unknown_hazard)
        self.assertEqual(unknown_result.decision.status, "REJECT")
        self.assertEqual(
            unknown_result.decision.reason_codes,
            ("HAZARD_ACTION_VETO",),
        )

        components = Layer0Components(
            context_state=BoundedContextState(action_budget=1)
        )
        kernel = Layer0Kernel(components)
        self.assertEqual(kernel.run_cycle(valid_raw_observation()).status, "PASS")
        exhausted_hazard = valid_raw_observation()
        exhausted_hazard["terminal_state"] = "GAME_OVER"
        exhausted_hazard["effects"] = ["HAZARD"]
        exhausted_result = kernel.run_cycle(exhausted_hazard)
        self.assertEqual(exhausted_result.decision.status, "REJECT")
        self.assertEqual(
            exhausted_result.decision.reason_codes,
            ("HAZARD_ACTION_VETO",),
        )

    def test_hds_rejects_hazardous_emission_result_before_memory_write(
        self,
    ) -> None:
        components = Layer0Components(
            emission_interface=HazardousInMemoryEmissionInterface()
        )
        kernel = Layer0Kernel(components)
        result = kernel.run_cycle(valid_raw_observation())
        self.assertEqual(result.decision.status, "EMIT")
        self.assertEqual(result.status, "REJECT")
        self.assertIsNone(result.memory_result)
        self.assertEqual(components.memory.view().version, 0)
        context = components.context_state.snapshot()
        self.assertEqual(context.actions_used, 1)
        self.assertEqual(context.effect_history[-1], ("HAZARD",))
        operations = tuple(item.operation for item in result.trace)
        self.assertIn("EMISSION_RESULT_JUDGED", operations)
        self.assertNotIn("AUTHORIZED_MEMORY_WRITE_EXECUTED", operations)

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
        memory = self.components.memory.view()
        command = self.components.hds.issue_compute(
            self.observation,
            self.context,
            memory,
        )
        proposal = self.components.compute.compute(
            command,
            self.components.hds,
            self.observation,
            self.context,
            memory,
            self.components.world_model,
            self.components.candidate_surface,
            self.components.instruction_body,
        )
        self.hypotheses = proposal.hypotheses
        self.candidates = proposal.candidates
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
    def test_boolean_available_actions_are_not_normalized_as_action_one(
        self,
    ) -> None:
        raw = valid_raw_observation()
        raw["available_actions"] = [True]
        observation = Layer0Components().symbol_space.encode(raw)
        self.assertEqual(observation.available_actions, ())

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
