"""Independent deterministic Layer-0 kernel with asymmetric Trinity control."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, cast

from .adapters.in_memory import EmissionResult, InMemoryEmissionInterface
from .context import BoundedContextState, ContextSnapshot
from .ir import CandidateIR, ClosureIR, HypothesisIR, ObservationIR
from .memory import MemoryMutationResult, MemorySnapshot, PassiveMemory
from .protocol import (
    _HDS_AUTHORIZATION_CAPABILITY,
    DEFAULT_INSTRUCTION_BODY_CONTRACT,
    AuthorityViolation,
    ComputeRequest,
    EmissionDirective,
    HDSDecision,
    MemoryDirective,
    TrinityLifecycle,
    _SingleUseAuthorization,
)
from .roles import (
    ACTION_MODES,
    ROLE_FAILURE_REASONS,
    DeterministicCandidateSurface,
    DeterministicSuccessCriterion,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
    Layer0FunctionalLoss,
)
from .schema import digest_object
from .verification import HAZARD_EFFECTS

_HDS_COMMAND_CAPABILITY = object()


@dataclass(frozen=True, slots=True)
class AuthorizedComputeCommand:
    """Capability-bearing command issued only by the HDS controller."""

    request: ComputeRequest
    _capability: object = field(repr=False, compare=False)

    def is_hds_authorized(self) -> bool:
        return self._capability is _HDS_COMMAND_CAPABILITY


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    target: str
    payload_items: tuple[tuple[str, object], ...]

    def payload(self) -> dict[str, object]:
        return dict(self.payload_items)


@dataclass(frozen=True, slots=True)
class ComputeProposal:
    command_id: str
    hypotheses: tuple[HypothesisIR, ...]
    candidates: tuple[CandidateIR, ...]
    memory_proposal: MemoryProposal

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class _ComputeBinding:
    observation: ObservationIR
    context: ContextSnapshot
    memory: MemorySnapshot


@dataclass(frozen=True, slots=True)
class _DecisionBinding:
    proposal_digest: str
    hypotheses_digest: str
    observation_signature: str
    memory_target: str
    memory_payload_digest: str
    candidate_digest: str | None = None


@dataclass(frozen=True, slots=True)
class KernelTraceEvent:
    index: int
    stage: str
    actor: str
    operation: str
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class KernelResult:
    status: str
    observation: ObservationIR
    hypotheses: tuple[HypothesisIR, ...]
    candidates: tuple[CandidateIR, ...]
    closures: tuple[ClosureIR, ...]
    decision: HDSDecision
    trace: tuple[KernelTraceEvent, ...]
    trace_digest: str
    memory_result: MemoryMutationResult | None
    emission_result: EmissionResult | None


@dataclass(slots=True)
class HDSController:
    """Sole command, judgment, stopping, write, and emission authority."""

    _issued: dict[str, bool] = field(default_factory=dict, init=False)
    _commands: dict[str, AuthorizedComputeCommand] = field(
        default_factory=dict,
        init=False,
    )
    _compute_bindings: dict[str, _ComputeBinding] = field(
        default_factory=dict,
        init=False,
    )
    _decisions: dict[str, HDSDecision] = field(default_factory=dict, init=False)
    _decision_bindings: dict[str, _DecisionBinding] = field(
        default_factory=dict,
        init=False,
    )
    _judged_commands: set[str] = field(default_factory=set, init=False)
    _memory_directives: dict[str, MemoryDirective] = field(
        default_factory=dict,
        init=False,
    )
    _emission_directives: dict[str, EmissionDirective] = field(
        default_factory=dict,
        init=False,
    )
    _observed_emissions: dict[str, EmissionResult] = field(
        default_factory=dict,
        init=False,
    )
    _emission_outcomes: dict[str, str] = field(
        default_factory=dict,
        init=False,
    )
    _finalized_decisions: set[str] = field(default_factory=set, init=False)
    _counter: int = field(default=0, init=False)

    def _issue_decision(
        self,
        *,
        command_id: str,
        decision_id: str,
        status: str,
        reason_codes: tuple[str, ...],
        candidate_id: str | None = None,
        closure_signature: str = "",
        allow_memory_write: bool = False,
        allow_external_emit: bool = False,
        binding: _DecisionBinding,
    ) -> HDSDecision:
        if command_id in self._judged_commands:
            raise AuthorityViolation("HDS_COMMAND_ALREADY_JUDGED")
        decision = HDSDecision(
            command_id=command_id,
            decision_id=decision_id,
            status=status,
            reason_codes=reason_codes,
            candidate_id=candidate_id,
            closure_signature=closure_signature,
            allow_memory_write=allow_memory_write,
            allow_external_emit=allow_external_emit,
            _capability=_HDS_AUTHORIZATION_CAPABILITY,
        )
        failures = decision.validate()
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._decisions[decision_id] = decision
        self._decision_bindings[decision_id] = binding
        self._judged_commands.add(command_id)
        return decision

    def _require_issued_decision(self, decision: HDSDecision) -> None:
        failures = list(decision.validate())
        if self._decisions.get(decision.decision_id) is not decision:
            failures.append("HDS_DECISION_NOT_OWNED_BY_CONTROLLER")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))

    def issue_compute(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> AuthorizedComputeCommand:
        self._counter += 1
        command_id = "command:" + digest_object(
            {
                "counter": self._counter,
                "observation": observation.frame_signature,
                "context": context.digest,
                "memory": memory.digest,
            }
        )[:20]
        request = ComputeRequest(
            command_id=command_id,
            operation="LLM_COMPUTE",
            observation_signature=observation.frame_signature,
            context_signature=context.digest,
            memory_signature=memory.digest,
            feature_tokens=observation.feature_tokens,
        )
        failures = request.validate(DEFAULT_INSTRUCTION_BODY_CONTRACT)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._issued[command_id] = False
        command = AuthorizedComputeCommand(request, _HDS_COMMAND_CAPABILITY)
        self._commands[command_id] = command
        self._compute_bindings[command_id] = _ComputeBinding(
            observation=observation,
            context=context,
            memory=memory,
        )
        return command

    def consume_compute(
        self,
        command: AuthorizedComputeCommand | None,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> ComputeRequest:
        if command is None or not isinstance(command, AuthorizedComputeCommand):
            raise AuthorityViolation("HDS_COMMAND_REQUIRED")
        if not command.is_hds_authorized():
            raise AuthorityViolation("HDS_COMMAND_CAPABILITY_INVALID")
        failures = command.request.validate(DEFAULT_INSTRUCTION_BODY_CONTRACT)
        if failures:
            raise AuthorityViolation(";".join(failures))
        command_id = command.request.command_id
        if command_id not in self._issued:
            raise AuthorityViolation("HDS_COMMAND_NOT_ISSUED")
        if self._commands.get(command_id) is not command:
            raise AuthorityViolation("HDS_COMMAND_NOT_OWNED_BY_CONTROLLER")
        if self._issued[command_id]:
            raise AuthorityViolation("HDS_COMMAND_ALREADY_CONSUMED")
        binding = self._compute_bindings[command_id]
        input_failures: list[str] = []
        if observation != binding.observation:
            input_failures.append("HDS_COMMAND_OBSERVATION_MISMATCH")
        if context != binding.context:
            input_failures.append("HDS_COMMAND_CONTEXT_MISMATCH")
        if memory != binding.memory:
            input_failures.append("HDS_COMMAND_MEMORY_MISMATCH")
        if input_failures:
            raise AuthorityViolation(";".join(input_failures))
        self._issued[command_id] = True
        return command.request

    @staticmethod
    def _closure_revalidated(
        candidate: CandidateIR,
        closure: ClosureIR,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
    ) -> bool:
        action_id: int | None = None
        if candidate.steps:
            value = candidate.steps[0].get("action_id")
            if isinstance(value, int) and not isinstance(value, bool):
                action_id = value
        if (
            candidate.mode not in ACTION_MODES
            or action_id not in observation.available_actions
            or not observation.frame_signature
            or not observation.structural_signature
            or not candidate.preconditions
            or f"ACTION{action_id}_AVAILABLE" not in candidate.preconditions
            or not candidate.falsification_conditions
            or not candidate.provenance
        ):
            return False
        if (
            candidate.mode == "BOUNDED_PROBE"
            and "ACTION_BUDGET_REMAINING" not in candidate.preconditions
        ):
            return False
        if action_id == 6:
            step = candidate.steps[0]
            if any(
                isinstance(step.get(axis), bool)
                or not isinstance(step.get(axis), int)
                or not 0 <= int(step[axis]) <= 63
                for axis in ("x", "y")
            ):
                return False

        bounded_metrics = (
            candidate.expected_progress,
            candidate.expected_information_gain,
            candidate.expected_risk,
            candidate.repetition_cost,
            candidate.rollback_cost,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
            for value in bounded_metrics
        ):
            return False

        hypothesis_ids = tuple(
            hypothesis.hypothesis_id for hypothesis in hypotheses
        )
        if (
            len(hypothesis_ids) < 2
            or len(set(hypothesis_ids)) != len(hypothesis_ids)
            or any(
                not hypothesis_id
                or isinstance(hypothesis.confidence, bool)
                or not isinstance(hypothesis.confidence, (int, float))
                or not isfinite(float(hypothesis.confidence))
                or not 0.0 <= float(hypothesis.confidence) <= 1.0
                for hypothesis_id, hypothesis in zip(
                    hypothesis_ids,
                    hypotheses,
                    strict=True,
                )
            )
        ):
            return False
        expected_effects = {
            key: tuple(values)
            for key, values in candidate.expected_effects_by_hypothesis.items()
        }
        if (
            not hypothesis_ids
            or set(expected_effects) != set(hypothesis_ids)
            or any(not values for values in expected_effects.values())
        ):
            return False

        uncertainty = 1.0 - max(
            (hypothesis.confidence for hypothesis in hypotheses),
            default=0.0,
        )
        fit_score = round(
            candidate.expected_progress
            + (0.5 * candidate.expected_information_gain)
            - candidate.expected_risk
            - candidate.repetition_cost
            - candidate.rollback_cost
            - (0.25 * uncertainty),
            6,
        )
        expected_x = {
            "observation_signature": observation.frame_signature,
            "structural_signature": observation.structural_signature,
            "terminal_state": observation.terminal_state,
            "candidate_id": candidate.candidate_id,
            "available_actions": observation.available_actions,
        }
        expected_r = {
            "preconditions": candidate.preconditions,
            "expected_effects_by_hypothesis": expected_effects,
            "falsification_conditions": candidate.falsification_conditions,
            "hypothesis_ids": hypothesis_ids,
            "evaluation_axes": {
                "progress": candidate.expected_progress,
                "goal_relevance": candidate.expected_progress,
                "hazard": "NOT_OBSERVED",
                "terminal_state": observation.terminal_state,
                "expected_effect_consistency": "PREDICTIONS_PRESENT",
                "information_gain": candidate.expected_information_gain,
                "uncertainty": round(uncertainty, 6),
                "repetition_cost": candidate.repetition_cost,
                "rollback_cost": candidate.rollback_cost,
                "action_budget_remaining": context.remaining_actions,
            },
        }
        expected_mc = {
            "identity": candidate.candidate_id,
            "boundary": "rendered-observation-only",
            "mode": candidate.mode,
            "provenance": candidate.provenance,
            "stop_on": ("hazard", "divergence", "budget-exhaustion"),
            "rollback_cost": candidate.rollback_cost,
            "fit_score": fit_score,
        }
        return (
            closure.status == "PASS"
            and closure.reason_codes == ("W_X_R_MC_CLOSED",)
            and not closure.missing_terms
            and closure.candidate_id == candidate.candidate_id
            and closure.x == expected_x
            and closure.r == expected_r
            and closure.mc == expected_mc
            and closure.confidence == 0.9
        )

    def judge(
        self,
        command: AuthorizedComputeCommand,
        proposal: ComputeProposal,
        closures: tuple[ClosureIR, ...],
        observation: ObservationIR,
        context: ContextSnapshot,
    ) -> HDSDecision:
        if (
            not isinstance(command, AuthorizedComputeCommand)
            or not command.is_hds_authorized()
        ):
            raise AuthorityViolation("HDS_COMMAND_CAPABILITY_INVALID")
        command_id = command.request.command_id
        if self._commands.get(command_id) is not command:
            raise AuthorityViolation("HDS_COMMAND_NOT_OWNED_BY_CONTROLLER")
        if not self._issued.get(command_id, False):
            raise AuthorityViolation("HDS_COMMAND_NOT_CONSUMED")
        if command_id in self._judged_commands:
            raise AuthorityViolation("HDS_COMMAND_ALREADY_JUDGED")
        if proposal.command_id != command_id:
            raise AuthorityViolation("PROPOSAL_COMMAND_MISMATCH")
        compute_binding = self._compute_bindings[command_id]
        if observation != compute_binding.observation:
            raise AuthorityViolation("HDS_JUDGMENT_OBSERVATION_MISMATCH")
        initial_context = compute_binding.context
        if (
            context.current_observation != observation
            or context.previous_observation != initial_context.previous_observation
            or context.action_history != initial_context.action_history
            or context.effect_history != initial_context.effect_history
            or context.failures != initial_context.failures
            or context.action_budget != initial_context.action_budget
            or context.actions_used != initial_context.actions_used
            or context.hypotheses != proposal.hypotheses
            or context.open_items
            or context.version != initial_context.version + 1
        ):
            raise AuthorityViolation("HDS_JUDGMENT_CONTEXT_MISMATCH")

        memory_payload = proposal.memory_proposal.payload()
        if len(memory_payload) != len(proposal.memory_proposal.payload_items):
            raise AuthorityViolation("MEMORY_PROPOSAL_DUPLICATE_KEYS")
        base_binding = _DecisionBinding(
            proposal_digest=proposal.digest,
            hypotheses_digest=digest_object(proposal.hypotheses),
            observation_signature=observation.frame_signature,
            memory_target=proposal.memory_proposal.target,
            memory_payload_digest=digest_object(memory_payload),
        )

        candidate_by_id = {
            candidate.candidate_id: candidate for candidate in proposal.candidates
        }
        decision_seed = {
            "command_id": command_id,
            "proposal": proposal.digest,
            "closures": closures,
            "context": context.digest,
        }
        decision_id = "decision:" + digest_object(decision_seed)[:20]

        if observation.terminal_state == "WIN":
            return self._issue_decision(
                command_id=command_id,
                decision_id=decision_id,
                status="STOP",
                reason_codes=("TERMINAL_WIN",),
                binding=base_binding,
            )
        hazard_observed = observation.terminal_state == "GAME_OVER" or any(
            effect in HAZARD_EFFECTS for effect in observation.visible_effects
        )
        if hazard_observed:
            return self._issue_decision(
                command_id=command_id,
                decision_id=decision_id,
                status="REJECT",
                reason_codes=("HAZARD_ACTION_VETO",),
                binding=base_binding,
            )
        if observation.terminal_state == "UNKNOWN":
            return self._issue_decision(
                command_id=command_id,
                decision_id=decision_id,
                status="SUSPEND",
                reason_codes=("TERMINAL_UNOBSERVED",),
                binding=base_binding,
            )
        if context.remaining_actions == 0:
            return self._issue_decision(
                command_id=command_id,
                decision_id=decision_id,
                status="STOP",
                reason_codes=("ACTION_BUDGET_EXHAUSTED",),
                binding=base_binding,
            )

        selectable: list[tuple[CandidateIR, ClosureIR]] = []
        for closure in closures:
            candidate = candidate_by_id.get(closure.candidate_id)
            if (
                candidate is not None
                and candidate.mode in ACTION_MODES
                and closure.status == "PASS"
                and self._closure_revalidated(
                    candidate,
                    closure,
                    observation,
                    context,
                    proposal.hypotheses,
                )
            ):
                selectable.append((candidate, closure))
        selected = (
            sorted(
                selectable,
                key=lambda item: (
                    -float(item[1].mc.get("fit_score", 0.0)),
                    item[0].candidate_id,
                ),
            )[0]
            if selectable
            else None
        )

        if selected is not None:
            candidate, closure = selected
            return self._issue_decision(
                command_id=command_id,
                decision_id=decision_id,
                status="EMIT",
                reason_codes=closure.reason_codes,
                candidate_id=candidate.candidate_id,
                closure_signature=digest_object(closure),
                allow_memory_write=True,
                allow_external_emit=True,
                binding=_DecisionBinding(
                    proposal_digest=base_binding.proposal_digest,
                    hypotheses_digest=base_binding.hypotheses_digest,
                    observation_signature=base_binding.observation_signature,
                    memory_target=base_binding.memory_target,
                    memory_payload_digest=base_binding.memory_payload_digest,
                    candidate_digest=digest_object(candidate),
                ),
            )

        action_closures = tuple(
            closure
            for closure in closures
            if candidate_by_id.get(closure.candidate_id) is not None
            and candidate_by_id[closure.candidate_id].mode in ACTION_MODES
        )
        rejected = any(closure.status == "REJECT" for closure in action_closures)
        reason_set = {
            reason
            for closure in action_closures
            for reason in closure.reason_codes
            if closure.status != "PASS"
        }
        if any(
                closure.status == "PASS"
                and (
                    (candidate := candidate_by_id.get(closure.candidate_id)) is None
                    or not self._closure_revalidated(
                        candidate,
                        closure,
                        observation,
                        context,
                        proposal.hypotheses,
                    )
                )
            for closure in action_closures
        ):
            reason_set.add("HDS_CLOSURE_REVALIDATION_FAILED")
        reasons = tuple(sorted(reason_set))
        return self._issue_decision(
            command_id=command_id,
            decision_id=decision_id,
            status="REJECT" if rejected else "SUSPEND",
            reason_codes=reasons or ("NO_CLOSED_ACTION_CANDIDATE",),
            binding=base_binding,
        )

    def memory_directive(
        self,
        decision: HDSDecision,
        proposal: MemoryProposal,
    ) -> MemoryDirective:
        self._require_issued_decision(decision)
        if not decision.allow_memory_write:
            raise AuthorityViolation("MEMORY_WRITE_NOT_AUTHORIZED")
        if (
            decision.allow_external_emit
            and decision.decision_id not in self._observed_emissions
        ):
            raise AuthorityViolation("MEMORY_WRITE_REQUIRES_EMISSION_OBSERVATION")
        if self._emission_outcomes.get(decision.decision_id) != "PASS":
            raise AuthorityViolation("MEMORY_WRITE_REQUIRES_HDS_RESULT_PASS")
        if decision.decision_id in self._memory_directives:
            raise AuthorityViolation("MEMORY_DIRECTIVE_ALREADY_ISSUED")
        binding = self._decision_bindings[decision.decision_id]
        payload = proposal.payload()
        payload_digest = digest_object(payload)
        if len(payload) != len(proposal.payload_items):
            raise AuthorityViolation("MEMORY_PROPOSAL_DUPLICATE_KEYS")
        if proposal.target != binding.memory_target:
            raise AuthorityViolation("MEMORY_PROPOSAL_TARGET_MISMATCH")
        if payload_digest != binding.memory_payload_digest:
            raise AuthorityViolation("MEMORY_PROPOSAL_PAYLOAD_MISMATCH")
        directive = MemoryDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            operation="ADD",
            target=proposal.target,
            lifecycle="PROPOSED",
            evidence_signature=decision.closure_signature,
            payload_digest=payload_digest,
            _capability=_HDS_AUTHORIZATION_CAPABILITY,
            _authorization=_SingleUseAuthorization("MEMORY_WRITE"),
        )
        directive.bind_owner()
        self._memory_directives[decision.decision_id] = directive
        return directive

    def emission_directive(
        self,
        decision: HDSDecision,
        candidate: CandidateIR,
    ) -> EmissionDirective:
        self._require_issued_decision(decision)
        if not decision.allow_external_emit:
            raise AuthorityViolation("EXTERNAL_EMIT_NOT_AUTHORIZED")
        if decision.decision_id in self._emission_directives:
            raise AuthorityViolation("EMISSION_DIRECTIVE_ALREADY_ISSUED")
        if candidate.candidate_id != decision.candidate_id:
            raise AuthorityViolation("HDS_SELECTED_CANDIDATE_MISMATCH")
        binding = self._decision_bindings[decision.decision_id]
        if digest_object(candidate) != binding.candidate_digest:
            raise AuthorityViolation("HDS_SELECTED_CANDIDATE_CONTENT_MISMATCH")
        if not candidate.steps or "action_id" not in candidate.steps[0]:
            raise AuthorityViolation("EMISSION_ACTION_MISSING")
        action_value = candidate.steps[0]["action_id"]
        if isinstance(action_value, bool) or not isinstance(action_value, int):
            raise AuthorityViolation("EMISSION_ACTION_INVALID")
        action_id = action_value
        directive = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=action_id,
            reasoning_digest=digest_object(
                {
                    "decision_id": decision.decision_id,
                    "candidate_id": candidate.candidate_id,
                }
            ),
            candidate_id=candidate.candidate_id,
            closure_signature=decision.closure_signature,
            observation_signature=binding.observation_signature,
            _capability=_HDS_AUTHORIZATION_CAPABILITY,
            _authorization=_SingleUseAuthorization("EXTERNAL_EMIT"),
        )
        directive.bind_owner()
        self._emission_directives[decision.decision_id] = directive
        return directive

    def observe_emission_result(
        self,
        decision: HDSDecision,
        directive: EmissionDirective,
        candidate: CandidateIR,
        observation: ObservationIR,
        result: EmissionResult,
    ) -> str:
        self._require_issued_decision(decision)
        failures: list[str] = []
        if not decision.allow_external_emit:
            failures.append("HDS_EMISSION_OBSERVATION_NOT_AUTHORIZED")
        if self._emission_directives.get(decision.decision_id) is not directive:
            failures.append("HDS_EMISSION_DIRECTIVE_NOT_OWNED")
        if decision.decision_id in self._observed_emissions:
            failures.append("HDS_EMISSION_RESULT_ALREADY_OBSERVED")
        binding = self._decision_bindings[decision.decision_id]
        if digest_object(candidate) != binding.candidate_digest:
            failures.append("HDS_EMISSION_RESULT_CANDIDATE_CONTENT_MISMATCH")
        failures.extend(result.validate(directive, decision, candidate, observation))
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._observed_emissions[decision.decision_id] = result
        return "hds-observation:" + digest_object(
            {
                "command_id": decision.command_id,
                "decision_id": decision.decision_id,
                "directive_signature": result.directive_signature,
                "result_signature": result.result_signature,
                "status": result.status,
            }
        )[:20]

    def judge_emission_result(
        self,
        decision: HDSDecision,
        result: EmissionResult,
    ) -> str:
        """Classify the observed effect before any memory write is allowed."""

        self._require_issued_decision(decision)
        if self._observed_emissions.get(decision.decision_id) is not result:
            raise AuthorityViolation("HDS_EMISSION_RESULT_NOT_OBSERVED")
        if decision.decision_id in self._emission_outcomes:
            raise AuthorityViolation("HDS_EMISSION_RESULT_ALREADY_JUDGED")
        hazard_observed = result.terminal_state == "GAME_OVER" or any(
            effect in HAZARD_EFFECTS for effect in result.visible_effects
        )
        if hazard_observed:
            outcome = "REJECT"
        elif result.terminal_state == "WIN":
            outcome = "STOP"
        else:
            outcome = "PASS"
        self._emission_outcomes[decision.decision_id] = outcome
        return outcome

    def finalize_cycle(
        self,
        decision: HDSDecision,
        emission_result: EmissionResult,
        memory_result: MemoryMutationResult | None,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> str:
        """Issue the final PASS only after authorized effects are observable."""

        self._require_issued_decision(decision)
        failures: list[str] = []
        if decision.decision_id in self._finalized_decisions:
            failures.append("HDS_CYCLE_ALREADY_FINALIZED")
        observed_result = self._observed_emissions.get(decision.decision_id)
        if observed_result is not emission_result:
            failures.append("HDS_EMISSION_RESULT_NOT_OBSERVED")
        outcome = self._emission_outcomes.get(decision.decision_id)
        if outcome is None:
            failures.append("HDS_EMISSION_RESULT_NOT_JUDGED")
            outcome = "REJECT"

        compute_binding = self._compute_bindings[decision.command_id]
        initial_context = compute_binding.context
        decision_binding = self._decision_bindings[decision.decision_id]
        expected_effects = emission_result.visible_effects or (
            "EMIT_PENDING_REOBSERVATION",
        )
        action_prefix = context.action_history[:-1]
        effect_prefix = context.effect_history[:-1]
        action_history_matches = (
            not action_prefix
            or action_prefix
            == initial_context.action_history[-len(action_prefix) :]
        )
        effect_history_matches = (
            not effect_prefix
            or effect_prefix
            == initial_context.effect_history[-len(effect_prefix) :]
        )
        if (
            context.current_observation != compute_binding.observation
            or context.previous_observation != initial_context.previous_observation
            or context.actions_used != initial_context.actions_used + 1
            or context.action_budget != initial_context.action_budget
            or not context.action_history
            or context.action_history[-1] != emission_result.action_id
            or not action_history_matches
            or not context.effect_history
            or context.effect_history[-1] != expected_effects
            or not effect_history_matches
            or context.failures != initial_context.failures
            or digest_object(context.hypotheses)
            != decision_binding.hypotheses_digest
            or context.open_items
            or context.version != initial_context.version + 2
        ):
            failures.append("HDS_CONTEXT_UPDATE_NOT_OBSERVED")

        if outcome == "PASS" and decision.allow_memory_write:
            directive = self._memory_directives.get(decision.decision_id)
            if directive is None:
                failures.append("HDS_MEMORY_DIRECTIVE_NOT_ISSUED")
            elif not directive.is_consumed:
                failures.append("HDS_MEMORY_DIRECTIVE_NOT_CONSUMED")
            if memory_result is None:
                failures.append("HDS_MEMORY_RESULT_REQUIRED")
            elif directive is not None:
                if (
                    memory_result.target != directive.target
                    or memory_result.operation != directive.operation
                    or memory_result.version != memory.version
                    or memory_result.snapshot_digest != memory.digest
                    or memory.version != compute_binding.memory.version + 1
                ):
                    failures.append("HDS_MEMORY_RESULT_MISMATCH")
        elif outcome == "PASS":
            if memory_result is not None:
                failures.append("HDS_MEMORY_RESULT_NOT_AUTHORIZED")
        else:
            if memory_result is not None:
                failures.append("HDS_MEMORY_RESULT_AFTER_REJECTION")
            if memory != compute_binding.memory:
                failures.append("HDS_MEMORY_CHANGED_AFTER_REJECTION")

        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._finalized_decisions.add(decision.decision_id)
        return outcome


@dataclass(frozen=True, slots=True)
class PureLLMCompute:
    """Subordinate calculator/executor with no independent authority."""

    executor: str = "pure-llm"

    def compute(
        self,
        command: AuthorizedComputeCommand | None,
        hds: HDSController,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
        world_model: object,
        candidate_surface: object,
    ) -> ComputeProposal:
        request = hds.consume_compute(
            command,
            observation,
            context,
            memory,
        )
        transform = getattr(world_model, "transform", None)
        generate = getattr(candidate_surface, "generate", None)
        if not callable(transform) or not callable(generate):
            raise TypeError("compute dependencies must be callable")

        hypotheses = transform(observation, context, memory)
        candidates = generate(observation, context, hypotheses)
        memory_target = "cycle:" + digest_object(
            {
                "command_id": request.command_id,
                "observation": observation.frame_signature,
            }
        )[:20]
        memory_proposal = MemoryProposal(
            target=memory_target,
            payload_items=(
                ("candidate_count", len(candidates)),
                ("command_id", request.command_id),
                ("hypothesis_count", len(hypotheses)),
                ("observation_signature", observation.frame_signature),
            ),
        )
        return ComputeProposal(
            command_id=request.command_id,
            hypotheses=hypotheses,
            candidates=candidates,
            memory_proposal=memory_proposal,
        )

    def execute_memory(
        self,
        directive: MemoryDirective,
        decision: HDSDecision,
        proposal: MemoryProposal,
        memory: PassiveMemory,
    ) -> MemoryMutationResult:
        return memory.apply_authorized(
            directive,
            decision,
            proposal.payload(),
            executor=self.executor,
        )

    def execute_emission(
        self,
        directive: EmissionDirective,
        decision: HDSDecision,
        candidate: CandidateIR,
        observation: ObservationIR,
        interface: object,
    ) -> EmissionResult:
        emit = getattr(interface, "emit", None)
        if not callable(emit):
            raise TypeError("emission interface must be callable")
        return cast(
            EmissionResult,
            emit(
                directive,
                decision,
                candidate,
                observation,
                executor=self.executor,
            ),
        )


@dataclass(slots=True)
class Layer0Components:
    symbol_space: object | None = field(default_factory=DeterministicSymbolSpace)
    context_state: object | None = field(default_factory=BoundedContextState)
    world_model: object | None = field(default_factory=DeterministicWorldModel)
    candidate_surface: object | None = field(
        default_factory=DeterministicCandidateSurface
    )
    success_criterion: object | None = field(
        default_factory=DeterministicSuccessCriterion
    )
    emission_interface: object | None = field(
        default_factory=InMemoryEmissionInterface
    )
    hds: HDSController = field(default_factory=HDSController)
    compute: PureLLMCompute = field(default_factory=PureLLMCompute)
    memory: PassiveMemory = field(default_factory=PassiveMemory)


class Layer0Kernel:
    """Orchestrate one HDS-controlled cycle without the official runner."""

    def __init__(self, components: Layer0Components | None = None) -> None:
        self.components = components or Layer0Components()
        self._stopped = False

    @staticmethod
    def _method(
        role: str,
        component: object | None,
        method_name: str,
        *,
        stage: str,
    ) -> Callable[..., Any]:
        if component is None:
            raise Layer0FunctionalLoss(
                role,
                ROLE_FAILURE_REASONS[role],
                stage=stage,
                removed=True,
            )
        method = getattr(component, method_name, None)
        if not callable(method):
            raise Layer0FunctionalLoss(
                role,
                f"{role}_CALLABLE_MISSING",
                stage=stage,
                removed=False,
            )
        return cast(Callable[..., Any], method)

    @staticmethod
    def _output_loss(role: str, stage: str) -> Layer0FunctionalLoss:
        return Layer0FunctionalLoss(
            role,
            f"{role}_OUTPUT_INVALID",
            stage=stage,
            removed=False,
        )

    def run_cycle(self, raw_observation: Mapping[str, object]) -> KernelResult:
        if self._stopped:
            raise AuthorityViolation("KERNEL_STOPPED")

        lifecycle = TrinityLifecycle()
        events: list[KernelTraceEvent] = []

        def record(
            stage: str,
            actor: str,
            operation: str,
            **details: object,
        ) -> None:
            events.append(
                KernelTraceEvent(
                    index=len(events),
                    stage=stage,
                    actor=actor,
                    operation=operation,
                    details=tuple(
                        sorted((key, str(value)) for key, value in details.items())
                    ),
                )
            )

        lifecycle.transition("SELF_CHECK")
        record(lifecycle.stage, "HDS", "KERNEL_SELF_CHECK")
        lifecycle.transition("FRAME")
        record(lifecycle.stage, "HDS", "OBSERVATION_ACCEPTED")

        encode = self._method(
            "SYMBOL_SPACE",
            self.components.symbol_space,
            "encode",
            stage="FRAME",
        )
        observation = encode(raw_observation)
        if not isinstance(observation, ObservationIR):
            raise self._output_loss("SYMBOL_SPACE", "FRAME")
        record(
            lifecycle.stage,
            "SYMBOL_SPACE",
            "OBSERVATION_SYMBOLIZED",
            observation=observation.frame_signature,
        )

        ingest = self._method(
            "CONTEXT_STATE",
            self.components.context_state,
            "ingest",
            stage="FRAME",
        )
        context = ingest(observation)
        if not isinstance(context, ContextSnapshot):
            raise self._output_loss("CONTEXT_STATE", "FRAME")
        record(
            lifecycle.stage,
            "CONTEXT_STATE",
            "EPISODE_CONTEXT_UPDATED",
            context=context.digest,
        )

        lifecycle.transition("RETRIEVE")
        memory_view = self.components.memory.view()
        record(
            lifecycle.stage,
            "MEMORY",
            "PASSIVE_MEMORY_READ",
            memory=memory_view.digest,
        )
        lifecycle.transition("COMPUTE")
        command = self.components.hds.issue_compute(
            observation,
            context,
            memory_view,
        )
        record(
            lifecycle.stage,
            "HDS",
            "COMPUTE_COMMAND_ISSUED",
            command=command.request.command_id,
        )

        world_method = self._method(
            "TRANSFORM_OR_WORLD_MODEL",
            self.components.world_model,
            "transform",
            stage="COMPUTE",
        )
        candidate_method = self._method(
            "CANDIDATE_SURFACE",
            self.components.candidate_surface,
            "generate",
            stage="COMPUTE",
        )
        del world_method, candidate_method
        proposal = self.components.compute.compute(
            command,
            self.components.hds,
            observation,
            context,
            memory_view,
            self.components.world_model,
            self.components.candidate_surface,
        )
        if (
            not isinstance(proposal.hypotheses, tuple)
            or len(proposal.hypotheses) < 2
            or not all(
                isinstance(hypothesis, HypothesisIR)
                for hypothesis in proposal.hypotheses
            )
        ):
            raise self._output_loss("TRANSFORM_OR_WORLD_MODEL", "COMPUTE")
        if (
            not isinstance(proposal.candidates, tuple)
            or len(proposal.candidates) < 2
            or not all(
                isinstance(candidate, CandidateIR)
                for candidate in proposal.candidates
            )
            or len({item.candidate_id for item in proposal.candidates})
            != len(proposal.candidates)
        ):
            raise self._output_loss("CANDIDATE_SURFACE", "COMPUTE")
        record(
            lifecycle.stage,
            "PURE_LLM",
            "HYPOTHESES_AND_CANDIDATES_PROPOSED",
            candidates=len(proposal.candidates),
            hypotheses=len(proposal.hypotheses),
            proposal=proposal.digest,
        )

        condition = self._method(
            "CONTEXT_STATE",
            self.components.context_state,
            "condition",
            stage="COMPUTE",
        )
        context = condition(proposal.hypotheses)
        if not isinstance(context, ContextSnapshot):
            raise self._output_loss("CONTEXT_STATE", "COMPUTE")

        evaluate = self._method(
            "FITTING_OR_SUCCESS_CRITERION",
            self.components.success_criterion,
            "evaluate",
            stage="COMPUTE",
        )
        closures = evaluate(
            observation,
            context,
            proposal.hypotheses,
            proposal.candidates,
        )
        if (
            not isinstance(closures, tuple)
            or len(closures) != len(proposal.candidates)
            or not all(isinstance(closure, ClosureIR) for closure in closures)
            or tuple(closure.candidate_id for closure in closures)
            != tuple(candidate.candidate_id for candidate in proposal.candidates)
        ):
            raise self._output_loss(
                "FITTING_OR_SUCCESS_CRITERION",
                "COMPUTE",
            )
        record(
            lifecycle.stage,
            "FITTING_OR_SUCCESS_CRITERION",
            "CLOSURE_PROPOSALS_CONSTRUCTED",
            closures=digest_object(closures),
        )

        lifecycle.transition("JUDGE")
        decision = self.components.hds.judge(
            command,
            proposal,
            closures,
            observation,
            context,
        )
        decision_failures = decision.validate()
        if decision_failures:
            raise AuthorityViolation(";".join(decision_failures))
        record(
            lifecycle.stage,
            "HDS",
            "CLOSURE_DECISION",
            decision=decision.decision_id,
            status=decision.status,
        )

        memory_result: MemoryMutationResult | None = None
        emission_result: EmissionResult | None = None
        status = decision.status
        if decision.allow_external_emit:
            candidate_by_id = {
                candidate.candidate_id: candidate
                for candidate in proposal.candidates
            }
            candidate = candidate_by_id.get(decision.candidate_id or "")
            if candidate is None:
                raise AuthorityViolation("HDS_SELECTED_CANDIDATE_MISSING")
            self._method(
                "EMISSION_INTERFACE",
                self.components.emission_interface,
                "emit",
                stage="ACT",
            )
            emission_directive = self.components.hds.emission_directive(
                decision,
                candidate,
            )
            lifecycle.transition("ACT")
            emission_result = self.components.compute.execute_emission(
                emission_directive,
                decision,
                candidate,
                observation,
                self.components.emission_interface,
            )
            if not isinstance(emission_result, EmissionResult):
                raise self._output_loss("EMISSION_INTERFACE", "ACT")
            record(
                lifecycle.stage,
                "PURE_LLM",
                "AUTHORIZED_EXTERNAL_EMIT_EXECUTED",
                result=emission_result.result_signature,
            )

            lifecycle.transition("OBSERVE_RESULT")
            hds_observation = self.components.hds.observe_emission_result(
                decision,
                emission_directive,
                candidate,
                observation,
                emission_result,
            )
            record(
                lifecycle.stage,
                "HDS",
                "EMISSION_RESULT_OBSERVED",
                result=hds_observation,
            )
            result_outcome = self.components.hds.judge_emission_result(
                decision,
                emission_result,
            )
            record(
                lifecycle.stage,
                "HDS",
                "EMISSION_RESULT_JUDGED",
                status=result_outcome,
            )
            record_emission = self._method(
                "CONTEXT_STATE",
                self.components.context_state,
                "record_emission",
                stage="OBSERVE_RESULT",
            )
            context = record_emission(
                emission_result.action_id,
                emission_result.visible_effects
                or ("EMIT_PENDING_REOBSERVATION",),
            )
            if not isinstance(context, ContextSnapshot):
                raise self._output_loss("CONTEXT_STATE", "OBSERVE_RESULT")
            record(
                lifecycle.stage,
                "CONTEXT_STATE",
                "EMISSION_RESULT_RECORDED",
                context=context.digest,
            )

            if result_outcome == "PASS" and decision.allow_memory_write:
                memory_directive = self.components.hds.memory_directive(
                    decision,
                    proposal.memory_proposal,
                )
                lifecycle.transition("UPDATE_MEMORY")
                memory_result = self.components.compute.execute_memory(
                    memory_directive,
                    decision,
                    proposal.memory_proposal,
                    self.components.memory,
                )
                record(
                    lifecycle.stage,
                    "PURE_LLM",
                    "AUTHORIZED_MEMORY_WRITE_EXECUTED",
                    memory_version=memory_result.version,
                )
                lifecycle.transition("REFRAME")
            else:
                lifecycle.transition("REFRAME")
            status = self.components.hds.finalize_cycle(
                decision,
                emission_result,
                memory_result,
                context,
                self.components.memory.view(),
            )
            if status == "STOP":
                lifecycle.transition("STOP")
                self._stopped = True
            record(
                lifecycle.stage,
                "HDS",
                "CYCLE_FINALIZED",
                status=status,
            )
        elif decision.status == "STOP":
            lifecycle.transition("STOP")
            self._stopped = True
        else:
            lifecycle.transition("SUSPEND")

        record(
            lifecycle.stage,
            "HDS",
            "CYCLE_BOUNDARY",
            status=status,
        )
        trace = tuple(events)
        return KernelResult(
            status=status,
            observation=observation,
            hypotheses=proposal.hypotheses,
            candidates=proposal.candidates,
            closures=closures,
            decision=decision,
            trace=trace,
            trace_digest=digest_object(trace),
            memory_result=memory_result,
            emission_result=emission_result,
        )


__all__ = [
    "AuthorizedComputeCommand",
    "ComputeProposal",
    "HDSController",
    "KernelResult",
    "KernelTraceEvent",
    "Layer0Components",
    "Layer0Kernel",
    "MemoryProposal",
    "PureLLMCompute",
]
