"""HDS Judgement Subject for the pre-official GenericAGIRuntime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .authority_state import AuthorityState
from .control_state import ControlState
from .evidence_binding import candidate_hazard_veto, candidate_reproduced
from .evidence_policy import EvidencePolicy
from .generic_memory import (
    ActionHistoryAuthorization,
    MemoryAuthorization,
    MemoryMutationProposal,
    MemoryView,
    action_history_authorization_binding,
)
from .generic_structural import infer_relational_rewrite_state
from .generic_types import (
    ActionEffectRecord,
    GateResult,
    GenericCandidate,
    GenericComputeCommand,
    GenericComputeResult,
    GenericHDSDecision,
    GenericHDSFrame,
    GenericObservation,
    OutcomeAttribution,
)
from .schema import digest_object

GENERIC_HDS_VERSION = "arc3-generic-hds-judgement-subject-v1"
HDS_GATE_IDS = tuple(f"G{index:02d}" for index in range(16))
HDS_FAILURE_UPDATE_REQUIRED = "HDS_FAILURE_UPDATE_REQUIRED"


@dataclass(frozen=True, slots=True)
class HDSConfiguration:
    """Delegated purpose/value/risk/Mc boundary, not a candidate policy."""

    purpose: str = "maximize_progress"
    value_criteria: tuple[str, ...] = (
        "goal_progress",
        "information_gain",
        "reversibility",
    )
    risk_limit: float = 0.45
    evidence_mode: str = "PROBE_WHEN_UNREPRODUCED"
    resource_budget: int = 256
    stop_after_no_progress: int = 96
    required_authorities: tuple[str, ...] = (
        "HDS_ACTION_HISTORY",
        "HDS_COMPUTE",
        "HDS_COMMIT",
        "HDS_CONTROL_ROLLBACK",
        "HDS_MEMORY_UPDATE",
        "HDS_EXTERNAL_ACTION",
    )
    projection_boundary: str = "MODEL_IS_NOT_WORLD"
    local_min_support: int = 2
    session_min_total_support: int = 3
    session_min_distinct_episode_support: int = 2
    active_confidence_ppm: int = 800_000
    max_contradiction_ratio_ppm: int = 100_000
    max_hazard_for_execute: int = 0

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.purpose not in {
            "maximize_progress",
            "maximize_information",
            "minimize_risk",
        }:
            failures.append("HDS_PURPOSE_INVALID")
        if not self.value_criteria:
            failures.append("HDS_VALUE_MODEL_MISSING")
        if not 0.0 <= self.risk_limit <= 1.0:
            failures.append("HDS_RISK_BOUNDARY_INVALID")
        if self.evidence_mode not in {
            "PROBE_WHEN_UNREPRODUCED",
            "REPRODUCED_ONLY",
            "ALLOW_LOCAL_EVIDENCE",
        }:
            failures.append("HDS_EVIDENCE_BOUNDARY_INVALID")
        if (
            isinstance(self.resource_budget, bool)
            or not isinstance(self.resource_budget, int)
            or self.resource_budget <= 0
        ):
            failures.append("HDS_RESOURCE_BUDGET_INVALID")
        if (
            isinstance(self.stop_after_no_progress, bool)
            or not isinstance(self.stop_after_no_progress, int)
            or self.stop_after_no_progress <= 0
        ):
            failures.append("HDS_STOP_BOUNDARY_INVALID")
        if not self.required_authorities:
            failures.append("HDS_AUTHORITY_BOUNDARY_MISSING")
        if self.projection_boundary != "MODEL_IS_NOT_WORLD":
            failures.append("HDS_PROJECTION_BOUNDARY_INVALID")
        failures.extend(self.evidence_policy().validate())
        return tuple(sorted(set(failures)))

    def evidence_policy(self) -> EvidencePolicy:
        return EvidencePolicy(
            local_min_support=self.local_min_support,
            session_min_total_support=self.session_min_total_support,
            session_min_distinct_episode_support=(
                self.session_min_distinct_episode_support
            ),
            active_confidence_ppm=self.active_confidence_ppm,
            max_contradiction_ratio_ppm=(
                self.max_contradiction_ratio_ppm
            ),
            max_hazard_for_execute=self.max_hazard_for_execute,
        )


@dataclass(frozen=True, slots=True)
class HDSAblation:
    purpose: bool = True
    mc: bool = True
    counter_hypothesis: bool = True
    suspend: bool = True
    evidence_gate: bool = True
    failure_update: bool = True
    projection_gate: bool = True


@dataclass(frozen=True, slots=True)
class ActionAuthorization:
    authorization_id: str
    decision_id: str
    candidate_id: str
    observation_signature: str
    action_id: int
    payload_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class RollbackAuthorization:
    authorization_id: str
    decision_id: str
    attribution_id: str
    failed_observation_signature: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class ControlRollbackAuthorization:
    """Single-use reset capability for a P-proposed, HDS-approved rollback."""

    authorization_id: str
    decision_id: str
    observation_signature: str
    control_instruction_ref: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(slots=True)
class ActionAuthorizationExecutor:
    """Mechanical single-use capability check; it owns no selection policy."""

    authority_state: AuthorityState = field(repr=False)

    def consume(
        self,
        authorization: ActionAuthorization,
        decision: GenericHDSDecision,
        candidate: GenericCandidate,
        observation: GenericObservation,
    ) -> tuple[int, dict[str, int]]:
        self.authority_state.require_live_token(
            authorization._authority_token,
            error="GENERIC_ACTION_AUTHORITY_INVALID",
        )
        if not decision.external_action_authorized:
            raise PermissionError("GENERIC_ACTION_NOT_HDS_APPROVED")
        if (
            authorization.decision_id != decision.decision_id
            or authorization.candidate_id != candidate.candidate_id
            or authorization.candidate_id != decision.selected_candidate_id
            or decision.selected_plan_id != candidate.plan.plan_id
            or authorization.observation_signature != observation.signature
            or authorization.action_id != candidate.descriptor.action_id
            or authorization.payload_digest
            != digest_object(candidate.descriptor.payload())
        ):
            raise PermissionError("GENERIC_ACTION_AUTHORIZATION_BINDING_INVALID")
        if candidate.descriptor.action_id not in observation.available_actions:
            raise PermissionError("GENERIC_ACTION_UNAVAILABLE")
        self.authority_state.consume(
            authorization.authorization_id,
            kind="HDS_EXTERNAL_ACTION",
            binding_digest=_action_binding(
                decision_id=authorization.decision_id,
                candidate_id=authorization.candidate_id,
                observation_signature=authorization.observation_signature,
                action_id=authorization.action_id,
                payload_digest=authorization.payload_digest,
            ),
            unknown_error="GENERIC_ACTION_AUTHORIZATION_NOT_ISSUED",
            reused_error="GENERIC_ACTION_AUTHORIZATION_REUSED",
            binding_error="GENERIC_ACTION_AUTHORIZATION_BINDING_INVALID",
        )
        return candidate.descriptor.action_id, candidate.descriptor.payload()


@dataclass(slots=True)
class RollbackAuthorizationExecutor:
    """Consume a failure-bound HDS rollback capability exactly once."""

    authority_state: AuthorityState = field(repr=False)

    def consume(
        self,
        authorization: RollbackAuthorization,
        decision: GenericHDSDecision,
        attribution: OutcomeAttribution,
        observation: GenericObservation,
    ) -> str:
        self.authority_state.require_live_token(
            authorization._authority_token,
            error="GENERIC_ROLLBACK_AUTHORITY_INVALID",
        )
        if (
            authorization.decision_id != decision.decision_id
            or authorization.attribution_id != attribution.attribution_id
            or authorization.failed_observation_signature
            != observation.signature
            or attribution.category != "FAILURE"
            or observation.terminal_state != "GAME_OVER"
        ):
            raise PermissionError("GENERIC_ROLLBACK_BINDING_INVALID")
        self.authority_state.consume(
            authorization.authorization_id,
            kind="HDS_ROLLBACK",
            binding_digest=_rollback_binding(
                decision_id=authorization.decision_id,
                attribution_id=authorization.attribution_id,
                observation_signature=authorization.failed_observation_signature,
            ),
            unknown_error="GENERIC_ROLLBACK_AUTHORIZATION_NOT_ISSUED",
            reused_error="GENERIC_ROLLBACK_AUTHORIZATION_REUSED",
            binding_error="GENERIC_ROLLBACK_BINDING_INVALID",
        )
        return authorization.authorization_id


@dataclass(slots=True)
class ControlRollbackAuthorizationExecutor:
    """Consume an HDS control rollback without treating P as authority."""

    authority_state: AuthorityState = field(repr=False)

    def consume(
        self,
        authorization: ControlRollbackAuthorization,
        decision: GenericHDSDecision,
        observation: GenericObservation,
    ) -> str:
        self.authority_state.require_live_token(
            authorization._authority_token,
            error="GENERIC_CONTROL_ROLLBACK_AUTHORITY_INVALID",
        )
        if (
            decision.operation_state != "ROLLBACK"
            or decision.selected_candidate_id is not None
            or decision.selected_plan_id is None
            or authorization.decision_id != decision.decision_id
            or authorization.observation_signature != observation.signature
            or not authorization.control_instruction_ref
        ):
            raise PermissionError("GENERIC_CONTROL_ROLLBACK_BINDING_INVALID")
        binding = _control_rollback_binding(
            decision_id=authorization.decision_id,
            observation_signature=authorization.observation_signature,
            control_instruction_ref=authorization.control_instruction_ref,
        )
        self.authority_state.consume(
            authorization.authorization_id,
            kind="HDS_CONTROL_ROLLBACK",
            binding_digest=binding,
            unknown_error="GENERIC_CONTROL_ROLLBACK_AUTHORIZATION_NOT_ISSUED",
            reused_error="GENERIC_CONTROL_ROLLBACK_AUTHORIZATION_REUSED",
            binding_error="GENERIC_CONTROL_ROLLBACK_BINDING_INVALID",
        )
        return authorization.authorization_id


def _action_binding(
    *,
    decision_id: str,
    candidate_id: str,
    observation_signature: str,
    action_id: int,
    payload_digest: str,
) -> str:
    return digest_object(
        {
            "decision": decision_id,
            "candidate": candidate_id,
            "observation": observation_signature,
            "action_id": action_id,
            "payload_digest": payload_digest,
        }
    )


def _rollback_binding(
    *,
    decision_id: str,
    attribution_id: str,
    observation_signature: str,
) -> str:
    return digest_object(
        {
            "decision": decision_id,
            "attribution": attribution_id,
            "observation": observation_signature,
        }
    )


def _control_rollback_binding(
    *,
    decision_id: str,
    observation_signature: str,
    control_instruction_ref: str,
) -> str:
    return digest_object(
        {
            "decision": decision_id,
            "observation": observation_signature,
            "control_instruction_ref": control_instruction_ref,
        }
    )


def _gate(
    gate_id: str,
    status: str,
    *reason_codes: str,
    required_information: Sequence[str] = (),
    next_probe: str = "",
) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        status=status,
        reason_codes=tuple(sorted(set(reason_codes))),
        required_information=tuple(sorted(set(required_information))),
        next_probe=next_probe,
    )


@dataclass(slots=True)
class GenericHDSJudgementSubject:
    """J_hds: sole owner of framing, commit, action, update, and stop."""

    authority_state: AuthorityState = field(repr=False)
    control_state: ControlState = field(repr=False)
    configuration: HDSConfiguration = field(default_factory=HDSConfiguration)
    run_id: str = "generic-run"

    def __post_init__(self) -> None:
        if self.authority_state.session_id != self.control_state.session_id:
            raise ValueError("HDS_SESSION_STATE_MISMATCH")

    @property
    def authority_token(self) -> object:
        """Compatibility view; AuthorityState remains the token owner."""

        return self.authority_state.live_token

    @property
    def cycle_index(self) -> int:
        return self.control_state.cycle_index

    @property
    def next_question(self) -> str:
        return self.control_state.next_question

    def frame(
        self,
        observation: GenericObservation,
        memory: MemoryView,
        *,
        remaining_budget: int,
        unresolved_terms: Sequence[str] = (),
        ablation: HDSAblation | None = None,
    ) -> GenericHDSFrame:
        selected_ablation = ablation or HDSAblation()
        failures = self.configuration.validate()
        if failures:
            raise ValueError(";".join(failures))
        purpose = (
            self.configuration.purpose
            if selected_ablation.purpose
            else ""
        )
        mc = (
            (
                f"terminal:{observation.terminal_state}",
                f"remaining-budget:{remaining_budget}",
                f"no-progress:{self.control_state.no_progress_count}",
                f"risk-limit:{self.configuration.risk_limit:.6f}",
                "rollback:on-game-over",
                "stop:on-win-or-resource-boundary",
            )
            if selected_ablation.mc
            else ()
        )
        x = (
            f"observation:{observation.signature}",
            f"memory-version:{memory.version}",
            f"cycle:{self.control_state.cycle_index}",
        )
        r = tuple(
            sorted(
                {
                    *(f"legal-action:{item}" for item in observation.available_actions),
                    *(f"active-memory:{item.memory_id}" for item in memory.active),
                    *(f"working-memory:{item.memory_id}" for item in memory.working),
                    *(f"sealed-boundary:{item.memory_id}" for item in memory.sealed),
                }
            )
        )
        body = {
            "run_id": self.run_id,
            "cycle": self.control_state.cycle_index,
            "observation": observation.signature,
            "memory": memory.digest,
            "purpose": purpose,
            "mc": mc,
        }
        return GenericHDSFrame(
            frame_id="hds-frame:" + digest_object(body)[:24],
            purpose=purpose,
            value_criteria=self.configuration.value_criteria,
            risk_limit=self.configuration.risk_limit,
            x=x,
            r=r,
            mc=mc,
            evidence_boundary=(
                self.configuration.evidence_mode,
                "claims-do-not-exceed-observed-evidence",
            ),
            resource_budget=min(
                remaining_budget, self.configuration.resource_budget
            ),
            authority_boundary=self.configuration.required_authorities,
            unresolved_terms=tuple(sorted(set(unresolved_terms))),
            stop_conditions=(
                "WIN",
                "RESOURCE_LIMIT",
                "GAME_OVER_REQUIRES_ROLLBACK",
                "UNCLOSED_REQUIRES_SUSPEND",
            ),
            cycle_index=self.control_state.cycle_index,
        )

    def issue_compute(
        self,
        frame: GenericHDSFrame,
        observation: GenericObservation,
        memory: MemoryView,
    ) -> GenericComputeCommand:
        if not frame.purpose:
            raise PermissionError("HDS_COMPUTE_PURPOSE_MISSING")
        if not frame.mc:
            raise PermissionError("HDS_COMPUTE_MC_MISSING")
        if not frame.x or not frame.r:
            raise PermissionError("HDS_COMPUTE_FRAME_NOT_CLOSED")
        if frame.resource_budget <= 0:
            raise PermissionError("HDS_COMPUTE_RESOURCE_EXHAUSTED")
        goal_tokens = tuple(
            sorted(
                {
                    f"purpose:{frame.purpose}",
                    "goal:progress",
                    "value:information",
                    "boundary:reversible",
                }
            )
        )
        required_outputs = (
            "representations",
            "hypotheses",
            "counter_hypotheses",
            "predictions",
            "candidates",
        )
        binding_digest = digest_object(
            {
                "purpose": frame.purpose,
                "goal_tokens": goal_tokens,
                "required_outputs": required_outputs,
                "observation_signature": observation.signature,
                "memory_version": memory.version,
            }
        )
        command_id = self.authority_state.issue(
            "HDS_COMPUTE",
            binding_digest,
        )
        return GenericComputeCommand(
            command_id=command_id,
            purpose=frame.purpose,
            goal_tokens=goal_tokens,
            required_outputs=required_outputs,
            observation_signature=observation.signature,
            memory_version=memory.version,
            _authority_token=self.authority_token,
        )

    def _candidate_score(
        self,
        candidate: GenericCandidate,
        *,
        purpose: str,
    ) -> float:
        if purpose == "maximize_information":
            return (
                0.15 * candidate.expected_progress
                + 0.75 * candidate.expected_information_gain
                - 0.65 * candidate.expected_risk
                - 0.1 * candidate.uncertainty
            )
        if purpose == "minimize_risk":
            return (
                0.25 * candidate.expected_progress
                + 0.15 * candidate.expected_information_gain
                - 1.2 * candidate.expected_risk
                - 0.2 * candidate.uncertainty
            )
        return (
            0.65 * candidate.expected_progress
            + 0.3 * candidate.expected_information_gain
            - 0.85 * candidate.expected_risk
            - 0.1 * candidate.uncertainty
        )

    def _relational_rewrite_candidate(
        self,
        observation: GenericObservation,
        candidates: Sequence[GenericCandidate],
    ) -> GenericCandidate | None:
        if (
            not self.control_state.legacy_structural_compatibility
            or not observation.rendered_layers
        ):
            return None
        state = infer_relational_rewrite_state(
            observation.rendered_layers[-1]
        )
        if state is None or any(
            item.descriptor.target_role is not None for item in candidates
        ):
            return None

        by_action: dict[int, GenericCandidate] = {}
        for candidate in candidates:
            by_action.setdefault(candidate.descriptor.action_id, candidate)
        selected_action: int | None = None
        if state.selected_matches and not state.all_matches:
            forward = tuple(
                candidate.descriptor.action_id
                for candidate in candidates
                if "STRUCTURAL_SELECTION_DELTA:1"
                in candidate.memory_effects
            )
            if forward:
                selected_action = min(forward)
        elif not state.selected_matches:
            memory_derived_value_candidates = tuple(
                candidate.descriptor.action_id
                for candidate in candidates
                if "STRUCTURAL_VALUE_ACTION" in candidate.memory_effects
            )
            if memory_derived_value_candidates:
                selected_action = min(memory_derived_value_candidates)
        if selected_action is None:
            classified = {
                candidate.descriptor.action_id
                for candidate in candidates
                if any(
                    effect.startswith("STRUCTURAL_SELECTION_DELTA:")
                    or effect == "STRUCTURAL_VALUE_ACTION"
                    for effect in candidate.memory_effects
                )
            }
            selected_action = next(
                (
                    candidate.descriptor.action_id
                    for candidate in candidates
                    if candidate.descriptor.action_id not in classified
                ),
                None,
            )
        if selected_action is None:
            return None
        return by_action[selected_action]

    def judge(
        self,
        *,
        frame: GenericHDSFrame,
        observation: GenericObservation,
        result: GenericComputeResult,
        ablation: HDSAblation | None = None,
    ) -> GenericHDSDecision:
        selected_ablation = ablation or HDSAblation()
        result_failures = result.validate(observation)
        has_counter = any(
            item.model_type in {"counter_hypothesis", "null_model"}
            for item in result.hypotheses
        )
        retrieved_citation_digests = tuple(
            item.content_digest for item in result.memory_citations
        )
        legal_candidates = tuple(
            item
            for item in result.candidates
            if item.descriptor.action_id in observation.available_actions
        )
        control_rollback_requested = result.control_operation == "ROLLBACK"
        action_or_control_available = bool(
            legal_candidates or control_rollback_requested
        )
        hazard_vetoed_candidate_ids = {
            item.candidate_id
            for item in legal_candidates
            if candidate_hazard_veto(item.evidence_bindings)
        }
        safe_candidates = tuple(
            item
            for item in legal_candidates
            if item.expected_risk <= frame.risk_limit
            and item.candidate_id not in hazard_vetoed_candidate_ids
        )
        reproduced_candidate_ids = {
            item.candidate_id
            for item in safe_candidates
            if candidate_reproduced(
                item.evidence_bindings,
                retrieved_citation_digests=retrieved_citation_digests,
            )
        }
        gates: list[GateResult] = []
        gates.append(
            _gate(
                "G00",
                "PASS" if frame.frame_id and self.run_id else "FAIL",
                *(() if frame.frame_id else ("A005",)),
            )
        )
        gates.append(
            _gate(
                "G01",
                "PASS" if not frame.unresolved_terms else "SUSPEND",
                *(("C104",) if frame.unresolved_terms else ()),
                required_information=frame.unresolved_terms,
                next_probe="resolve-open-terms",
            )
        )
        closure_pass = bool(
            frame.x and frame.r and frame.mc and frame.purpose
        )
        gates.append(
            _gate(
                "G02",
                "PASS" if closure_pass else "FAIL",
                *(("C101", "C102", "C103") if not closure_pass else ()),
            )
        )
        gates.append(
            _gate(
                "G03",
                "PASS" if action_or_control_available else "SUSPEND",
                *(("I202",) if not action_or_control_available else ()),
                next_probe="request-legal-action-observation",
            )
        )
        counter_gate_pass = has_counter and selected_ablation.counter_hypothesis
        gates.append(
            _gate(
                "G04",
                "PASS" if counter_gate_pass else "FAIL",
                *(("I203",) if not counter_gate_pass else ()),
            )
        )
        gates.append(
            _gate(
                "G05",
                "PASS" if len(result.hypotheses) >= 2 else "FAIL",
                *(("I204",) if len(result.hypotheses) < 2 else ()),
            )
        )
        evidence_pass = selected_ablation.evidence_gate and (
            bool(reproduced_candidate_ids)
            or self.configuration.evidence_mode != "REPRODUCED_ONLY"
        )
        gates.append(
            _gate(
                "G06",
                "PASS" if evidence_pass else "SUSPEND",
                *(("E301",) if not evidence_pass else ()),
                required_information=(
                    () if evidence_pass else ("reproduced action/effect evidence",)
                ),
                next_probe="bounded-reversible-probe",
            )
        )
        gates.append(
            _gate(
                "G07",
                "PASS" if not result_failures else "FAIL",
                *(("L403",) if result_failures else ()),
            )
        )
        gates.append(_gate("G08", "PASS"))
        projection_pass = (
            selected_ablation.projection_gate
            and self.configuration.projection_boundary == "MODEL_IS_NOT_WORLD"
        )
        gates.append(
            _gate(
                "G09",
                "PASS" if projection_pass else "FAIL",
                *(("P501",) if not projection_pass else ()),
            )
        )
        gates.append(
            _gate(
                "G10",
                "PASS"
                if safe_candidates or control_rollback_requested
                else "SUSPEND",
                *(
                    (
                        "EVIDENCE_HAZARD_VETO"
                        if legal_candidates
                        and hazard_vetoed_candidate_ids
                        and not safe_candidates
                        else "D602",
                    )
                    if not safe_candidates and not control_rollback_requested
                    else ()
                ),
                next_probe="find-lower-risk-candidate",
            )
        )
        temporal_attribution_pass = observation.action_complete
        gates.append(
            _gate(
                "G11",
                "PASS" if temporal_attribution_pass else "SUSPEND",
                *(
                    ()
                    if temporal_attribution_pass
                    else ("TEMPORAL_EFFECT_UNSETTLED",)
                ),
                required_information=(
                    ()
                    if temporal_attribution_pass
                    else ("action-complete rendered observation",)
                ),
                next_probe="wait-for-action-complete-render",
            )
        )
        resource_pass = frame.resource_budget > 0
        gates.append(
            _gate(
                "G12",
                "PASS" if resource_pass else "FAIL",
                *(("D603",) if not resource_pass else ()),
            )
        )
        gates.append(_gate("G13", "PASS"))
        authority_pass = set(self.configuration.required_authorities).issubset(
            frame.authority_boundary
        )
        gates.append(
            _gate(
                "G14",
                "PASS" if authority_pass else "FAIL",
                *(("D606",) if not authority_pass else ()),
            )
        )

        selected: GenericCandidate | None = None
        operation = "SUSPEND"
        assertion = "SUSPEND"
        reasons: list[str] = []
        stop_condition = "continue until WIN, resource boundary, or unclosed risk"
        if observation.terminal_state == "WIN":
            operation = "STOP"
            assertion = "PASS"
            reasons.append("GOAL_REACHED")
            stop_condition = "WIN"
        elif frame.resource_budget <= 0:
            operation = "STOP"
            assertion = "FAIL"
            reasons.append("RESOURCE_LIMIT")
            stop_condition = "RESOURCE_LIMIT"
        elif result.control_operation == "ROLLBACK":
            blocking_gate_ids = {
                item.gate_id
                for item in gates
                if item.status in {"FAIL", "SUSPEND"}
            }
            if blocking_gate_ids:
                reasons.extend(
                    f"{item.gate_id}:{','.join(item.reason_codes)}"
                    for item in gates
                    if item.status in {"FAIL", "SUSPEND"}
                )
            else:
                operation = "ROLLBACK"
                assertion = "PASS"
                reasons.append("P_PROPOSED_HDS_APPROVED_ROLLBACK")
                stop_condition = "continue after bounded level rollback"
        elif (
            self.control_state.no_progress_count
            >= self.configuration.stop_after_no_progress
        ):
            operation = "STOP"
            assertion = "SUSPEND"
            reasons.append("NO_PROGRESS_STOP_BOUNDARY")
            stop_condition = "NO_PROGRESS_LIMIT"
        else:
            blocking_gate_ids = {
                item.gate_id
                for item in gates
                if item.status in {"FAIL", "SUSPEND"}
            }
            if not blocking_gate_ids and safe_candidates:
                # Preserve C's deterministic evidence ranking when scores tie.
                # A digest tie-break makes equivalent novel probes look random
                # and can repeatedly skip the first role-bound affordance.
                selected = (
                    None
                    if reproduced_candidate_ids
                    else self._relational_rewrite_candidate(
                        observation,
                        safe_candidates,
                    )
                )
                if selected is None:
                    selected = max(
                        enumerate(safe_candidates),
                        key=lambda indexed: (
                            indexed[1].candidate_id
                            in reproduced_candidate_ids,
                            self._candidate_score(
                                indexed[1],
                                purpose=frame.purpose,
                            ),
                            -indexed[1].expected_risk,
                            -indexed[0],
                        ),
                    )[1]
                reproduced = candidate_reproduced(
                    selected.evidence_bindings,
                    retrieved_citation_digests=retrieved_citation_digests,
                )
                if (
                    self.configuration.evidence_mode == "REPRODUCED_ONLY"
                    and not reproduced
                ):
                    operation = "SUSPEND"
                    reasons.append("EVIDENCE_BOUNDARY_NOT_MET")
                elif (
                    not reproduced
                    or frame.purpose == "maximize_information"
                ):
                    operation = "PROBE"
                    assertion = "PASS"
                    reasons.append("BOUNDED_INFORMATION_PROBE")
                else:
                    operation = "EXECUTE"
                    assertion = "PASS"
                    reasons.append("EVIDENCE_SUPPORTED_ACTION")
            else:
                reasons.extend(
                    f"{item.gate_id}:{','.join(item.reason_codes)}"
                    for item in gates
                    if item.status in {"FAIL", "SUSPEND"}
                )
        if operation == "SUSPEND" and not selected_ablation.suspend:
            operation = "STOP"
            assertion = "FAIL"
            reasons.append("SUSPEND_CAPABILITY_REMOVED")
            stop_condition = "HDS_SUSPEND_ABLATION"
        commit_pass = operation in {
            "EXECUTE",
            "PROBE",
            "ROLLBACK",
            "SUSPEND",
            "STOP",
        }
        gates.append(
            _gate(
                "G15",
                "PASS" if commit_pass else "FAIL",
                *(("D604",) if not commit_pass else ()),
            )
        )
        if operation in {"EXECUTE", "PROBE"} and selected is not None:
            next_question = (
                "Did the authorized action cause progress, hazard, delayed "
                "effect, observation error, or no effect?"
            )
            next_observation = "reobserve rendered state and legal action surface"
            next_probe = selected.descriptor.semantic_key
        elif operation == "ROLLBACK":
            next_question = (
                "Did the single-use rollback restore a safe observable state?"
            )
            next_observation = "reobserve the reset level"
            next_probe = result.control_instruction_refs[0]
        elif operation == "SUSPEND":
            next_question = "What missing evidence can safely close the current frame?"
            next_observation = "obtain required information without external action"
            next_probe = "resolve-gate-suspension"
        else:
            next_question = "Has the delegated purpose reached a valid stop state?"
            next_observation = "confirm terminal and resource state"
            next_probe = "none"
        required_information = tuple(
            sorted(
                {
                    information
                    for item in gates
                    for information in item.required_information
                }
            )
        )
        selected_plan_id = (
            selected.plan.plan_id
            if selected is not None
            else (
                result.control_plan.plan_id
                if operation == "ROLLBACK" and result.control_plan is not None
                else None
            )
        )
        decision_binding = digest_object(
            {
                "run": self.run_id,
                "cycle": self.control_state.cycle_index,
                "frame": frame,
                "compute": result.digest(),
                "operation": operation,
                "selected": (
                    selected.candidate_id if selected is not None else None
                ),
                "selected_plan": selected_plan_id,
                "gates": gates,
            }
        )
        decision_id = self.authority_state.issue(
            "HDS_COMMIT",
            decision_binding,
        )
        decision = GenericHDSDecision(
            decision_id=decision_id,
            assertion_state=assertion,
            operation_state=operation,
            selected_candidate_id=(
                selected.candidate_id if selected is not None else None
            ),
            selected_plan_id=selected_plan_id,
            gate_results=tuple(gates),
            reasons=tuple(sorted(set(reasons))),
            next_question=next_question,
            next_observation=next_observation,
            required_information=required_information,
            next_probe=next_probe,
            stop_condition=stop_condition,
            memory_update_authorized=(
                operation in {"EXECUTE", "PROBE"}
                and selected_ablation.failure_update
            ),
            external_action_authorized=operation in {"EXECUTE", "PROBE"},
            frame_digest="hds-frame:" + digest_object(frame),
            compute_result_digest=result.digest(),
        )
        decision_failures = decision.validate()
        if decision_failures:
            raise RuntimeError(";".join(decision_failures))
        self.authority_state.register_decision(decision_id, decision)
        self.authority_state.consume(
            decision_id,
            kind="HDS_COMMIT",
            binding_digest=decision_binding,
            unknown_error="HDS_DECISION_NOT_ISSUED",
            reused_error="HDS_DECISION_COMMIT_REUSED",
            binding_error="HDS_DECISION_BINDING_INVALID",
        )
        self.control_state.record_decision(
            next_question=next_question,
            pending_probe=next_probe,
            stop_boundary=stop_condition,
        )
        return decision

    def authorize_action(
        self,
        decision: GenericHDSDecision,
        candidate: GenericCandidate,
        observation: GenericObservation,
    ) -> ActionAuthorization:
        self.authority_state.require_decision(
            decision.decision_id,
            decision,
            error="HDS_ACTION_DECISION_NOT_ISSUED",
        )
        if (
            not decision.external_action_authorized
            or decision.selected_candidate_id != candidate.candidate_id
            or decision.selected_plan_id != candidate.plan.plan_id
        ):
            raise PermissionError("HDS_ACTION_NOT_COMMITTED")
        payload_digest = digest_object(candidate.descriptor.payload())
        binding_digest = _action_binding(
            decision_id=decision.decision_id,
            candidate_id=candidate.candidate_id,
            observation_signature=observation.signature,
            action_id=candidate.descriptor.action_id,
            payload_digest=payload_digest,
        )
        return ActionAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_EXTERNAL_ACTION",
                binding_digest,
            ),
            decision_id=decision.decision_id,
            candidate_id=candidate.candidate_id,
            observation_signature=observation.signature,
            action_id=candidate.descriptor.action_id,
            payload_digest=payload_digest,
            _authority_token=self.authority_token,
        )

    def authorize_action_history(
        self,
        decision: GenericHDSDecision,
        record: ActionEffectRecord,
        *,
        before_observation: GenericObservation,
        after_observation: GenericObservation,
        history_version: int,
        selected_candidate: GenericCandidate | None,
    ) -> ActionHistoryAuthorization:
        """Authorize one passive-M append after an observed side effect."""

        self.authority_state.require_decision(
            decision.decision_id,
            decision,
            error="HDS_ACTION_HISTORY_DECISION_NOT_ISSUED",
        )
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        if decision.operation_state in {"EXECUTE", "PROBE"}:
            if (
                selected_candidate is None
                or decision.selected_candidate_id
                != selected_candidate.candidate_id
                or record.action_id != selected_candidate.descriptor.action_id
                or record.payload_items
                != selected_candidate.descriptor.payload_items
                or record.plan_id != selected_candidate.plan.plan_id
                or record.hypothesis_refs
                != selected_candidate.plan.hypothesis_refs
            ):
                raise PermissionError("HDS_ACTION_HISTORY_ACTION_BINDING_INVALID")
        elif decision.operation_state == "ROLLBACK":
            if (
                selected_candidate is not None
                or decision.selected_candidate_id is not None
                or record.action_id != 0
                or not record.compatibility_reset
                or record.plan_id != decision.selected_plan_id
            ):
                raise PermissionError("HDS_ACTION_HISTORY_ROLLBACK_BINDING_INVALID")
        else:
            raise PermissionError("HDS_ACTION_HISTORY_OPERATION_INVALID")
        record_digest = record.digest()
        binding = action_history_authorization_binding(
            decision_id=decision.decision_id,
            before_observation_signature=before_observation.signature,
            after_observation_signature=after_observation.signature,
            expected_version=history_version,
            record_digest=record_digest,
        )
        return ActionHistoryAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_ACTION_HISTORY",
                binding,
            ),
            decision_id=decision.decision_id,
            before_observation_signature=before_observation.signature,
            after_observation_signature=after_observation.signature,
            expected_version=history_version,
            record_digest=record_digest,
            _authority_token=self.authority_token,
        )

    def authorize_control_rollback(
        self,
        decision: GenericHDSDecision,
        result: GenericComputeResult,
        observation: GenericObservation,
    ) -> ControlRollbackAuthorization:
        self.authority_state.require_decision(
            decision.decision_id,
            decision,
            error="HDS_CONTROL_ROLLBACK_DECISION_NOT_ISSUED",
        )
        if (
            decision.operation_state != "ROLLBACK"
            or decision.selected_candidate_id is not None
            or result.control_operation != "ROLLBACK"
            or not result.control_instruction_refs
            or result.control_plan is None
            or decision.selected_plan_id != result.control_plan.plan_id
            or decision.compute_result_digest != result.digest()
        ):
            raise PermissionError("HDS_CONTROL_ROLLBACK_NOT_COMMITTED")
        instruction_ref = result.control_instruction_refs[0]
        binding = _control_rollback_binding(
            decision_id=decision.decision_id,
            observation_signature=observation.signature,
            control_instruction_ref=instruction_ref,
        )
        return ControlRollbackAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_CONTROL_ROLLBACK",
                binding,
            ),
            decision_id=decision.decision_id,
            observation_signature=observation.signature,
            control_instruction_ref=instruction_ref,
            _authority_token=self.authority_token,
        )

    def authorize_memory(
        self,
        decision: GenericHDSDecision,
        proposal: MemoryMutationProposal,
        *,
        memory_version: int,
    ) -> MemoryAuthorization:
        self.authority_state.require_decision(
            decision.decision_id,
            decision,
            error="HDS_MEMORY_DECISION_NOT_ISSUED",
        )
        if not decision.memory_update_authorized:
            raise PermissionError("HDS_MEMORY_UPDATE_NOT_AUTHORIZED")
        proposal_failures = proposal.validate()
        if proposal_failures:
            raise ValueError(";".join(proposal_failures))
        binding_digest = digest_object(
            {
                "decision": decision.decision_id,
                "proposal": proposal,
                "version": memory_version,
            }
        )
        return MemoryAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_MEMORY_UPDATE",
                binding_digest,
            ),
            decision_id=decision.decision_id,
            expected_version=memory_version,
            proposal_digest=digest_object(proposal),
            _authority_token=self.authority_token,
        )

    def authorize_rollback(
        self,
        decision: GenericHDSDecision,
        attribution: OutcomeAttribution,
        observation: GenericObservation,
    ) -> RollbackAuthorization:
        self.authority_state.require_decision(
            decision.decision_id,
            decision,
            error="HDS_ROLLBACK_DECISION_NOT_ISSUED",
        )
        if (
            attribution.category != "FAILURE"
            or observation.terminal_state != "GAME_OVER"
        ):
            raise PermissionError("HDS_ROLLBACK_FAILURE_REQUIRED")
        binding_digest = _rollback_binding(
            decision_id=decision.decision_id,
            attribution_id=attribution.attribution_id,
            observation_signature=observation.signature,
        )
        return RollbackAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_ROLLBACK",
                binding_digest,
            ),
            decision_id=decision.decision_id,
            attribution_id=attribution.attribution_id,
            failed_observation_signature=observation.signature,
            _authority_token=self.authority_token,
        )

    def authorize_overlay_discard(
        self,
        proposal: MemoryMutationProposal,
        *,
        memory_version: int,
    ) -> MemoryAuthorization:
        """Authorize a fail-closed episode-boundary rollback."""

        if not self.control_state.episode_active:
            raise PermissionError("HDS_EPISODE_DISCARD_ACTIVE_EPISODE_REQUIRED")
        proposal_failures = proposal.validate()
        if proposal_failures:
            raise ValueError(";".join(proposal_failures))
        if proposal.operation != "ROLLBACK":
            raise PermissionError("HDS_EPISODE_DISCARD_ROLLBACK_REQUIRED")
        decision_id = "hds-episode-discard:" + digest_object(
            {
                "session": self.run_id,
                "target_version": proposal.rollback_version,
                "memory_version": memory_version,
            }
        )[:24]
        binding_digest = digest_object(
            {
                "decision": decision_id,
                "proposal": proposal,
                "version": memory_version,
            }
        )
        return MemoryAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_MEMORY_UPDATE",
                binding_digest,
            ),
            decision_id=decision_id,
            expected_version=memory_version,
            proposal_digest=digest_object(proposal),
            _authority_token=self.authority_token,
        )

    def authorize_consolidation(
        self,
        proposal: MemoryMutationProposal,
        *,
        memory_version: int,
    ) -> MemoryAuthorization:
        """Authorize only validated SESSION_GLOBAL typed causal promotion."""

        from .causal_record import causal_record_from_semantic

        if not self.control_state.episode_active:
            raise PermissionError(
                "HDS_CONSOLIDATION_ACTIVE_EPISODE_REQUIRED"
            )
        proposal_failures = proposal.validate()
        if proposal_failures:
            raise ValueError(";".join(proposal_failures))
        if proposal.operation not in {"ADD", "REVISE", "INVALIDATE"}:
            raise PermissionError("HDS_CONSOLIDATION_OPERATION_INVALID")
        if proposal.record is None:
            raise PermissionError("HDS_CONSOLIDATION_RECORD_REQUIRED")
        typed = causal_record_from_semantic(
            proposal.record,
            policy=self.configuration.evidence_policy(),
        )
        if typed.scope_class != "SESSION_GLOBAL":
            raise PermissionError("HDS_CONSOLIDATION_SCOPE_INVALID")
        if (
            typed.state == "ACTIVE"
            and typed.distinct_episode_support
            < self.configuration.session_min_distinct_episode_support
        ):
            raise PermissionError(
                "HDS_CONSOLIDATION_INDEPENDENT_SUPPORT_REQUIRED"
            )
        decision_id = "hds-consolidation:" + digest_object(
            {
                "session": self.run_id,
                "record": typed.digest(),
                "memory_version": memory_version,
            }
        )[:24]
        binding_digest = digest_object(
            {
                "decision": decision_id,
                "proposal": proposal,
                "version": memory_version,
            }
        )
        return MemoryAuthorization(
            authorization_id=self.authority_state.issue(
                "HDS_MEMORY_UPDATE",
                binding_digest,
            ),
            decision_id=decision_id,
            expected_version=memory_version,
            proposal_digest=digest_object(proposal),
            _authority_token=self.authority_token,
        )

    def attribute(
        self,
        *,
        before: GenericObservation,
        after: GenericObservation,
        candidate: GenericCandidate,
    ) -> OutcomeAttribution:
        progress_delta = after.progress_count - before.progress_count
        if after.terminal_state == "GAME_OVER":
            category = "FAILURE"
        elif progress_delta > 0 or after.terminal_state == "WIN":
            category = "PROGRESS"
        elif (
            after.signature == before.signature
            or "NO_VISIBLE_CHANGE" in after.visible_effects
        ):
            category = "NO_EFFECT"
        else:
            category = "VISIBLE_CHANGE"
        effects = set(after.visible_effects)
        if before.rendered_layers and after.rendered_layers:
            before_rewrite = infer_relational_rewrite_state(
                before.rendered_layers[-1]
            )
            after_rewrite = infer_relational_rewrite_state(
                after.rendered_layers[-1]
            )
            if (
                before_rewrite is not None
                and after_rewrite is not None
                and before_rewrite.sequence_length
                == after_rewrite.sequence_length
            ):
                if (
                    before_rewrite.output_shapes
                    == after_rewrite.output_shapes
                    and before_rewrite.selected_index
                    != after_rewrite.selected_index
                ):
                    raw_delta = (
                        after_rewrite.selected_index
                        - before_rewrite.selected_index
                    ) % before_rewrite.sequence_length
                    delta = (
                        -1
                        if raw_delta
                        == before_rewrite.sequence_length - 1
                        else raw_delta
                    )
                    effects.add("STRUCTURAL_SELECTION_CHANGE")
                    effects.add(f"STRUCTURAL_SELECTION_DELTA:{delta}")
                elif (
                    before_rewrite.selected_index
                    == after_rewrite.selected_index
                    and before_rewrite.output_shapes
                    != after_rewrite.output_shapes
                ):
                    effects.add("STRUCTURAL_VALUE_CHANGE")
                    effects.add("STRUCTURAL_VALUE_ACTION")
        if progress_delta > 0:
            effects.add("LEVEL_PROGRESS")
        if after.terminal_state == "GAME_OVER":
            effects.add("IRREVERSIBLE_FAILURE")
        if after.signature == before.signature:
            effects.add("NO_VISIBLE_CHANGE")
        return OutcomeAttribution(
            attribution_id="outcome-attribution:"
            + digest_object(
                {
                    "before": before.digest(),
                    "after": after.digest(),
                    "candidate": candidate.candidate_id,
                    "category": category,
                }
            )[:24],
            category=category,
            before_signature=before.signature,
            after_signature=after.signature,
            action_semantic_key=candidate.descriptor.semantic_key,
            visible_effects=tuple(sorted(effects)),
            progress_delta=progress_delta,
            terminal_state=after.terminal_state,
            evidence=(
                before.digest(),
                after.digest(),
                candidate.candidate_id,
            ),
        )

    def attribute_control_rollback(
        self,
        *,
        before: GenericObservation,
        after: GenericObservation,
        result: GenericComputeResult,
    ) -> OutcomeAttribution:
        """Attribute one HDS-approved P rollback without fabricating a candidate."""

        if result.control_operation != "ROLLBACK":
            raise ValueError("HDS_CONTROL_ROLLBACK_RESULT_REQUIRED")
        if not result.control_instruction_refs:
            raise ValueError("HDS_CONTROL_ROLLBACK_PROVENANCE_REQUIRED")
        progress_delta = after.progress_count - before.progress_count
        if after.terminal_state == "GAME_OVER":
            category = "FAILURE"
        elif progress_delta > 0 or after.terminal_state == "WIN":
            category = "PROGRESS"
        elif after.signature == before.signature:
            category = "NO_EFFECT"
        else:
            category = "VISIBLE_CHANGE"
        effects = {"CONTROL_ROLLBACK", "LEVEL_RESET", *after.visible_effects}
        if after.signature == before.signature:
            effects.add("NO_VISIBLE_CHANGE")
        return OutcomeAttribution(
            attribution_id="control-rollback-attribution:"
            + digest_object(
                {
                    "before": before.digest(),
                    "after": after.digest(),
                    "result": result.digest(),
                    "category": category,
                }
            )[:24],
            category=category,
            before_signature=before.signature,
            after_signature=after.signature,
            action_semantic_key="control:rollback",
            visible_effects=tuple(sorted(effects)),
            progress_delta=progress_delta,
            terminal_state=after.terminal_state,
            evidence=(
                before.digest(),
                after.digest(),
                *result.control_instruction_refs,
            ),
        )

    def observe_outcome(self, attribution: OutcomeAttribution) -> None:
        self.control_state.observe_outcome(
            progress=attribution.category == "PROGRESS"
        )


__all__ = [
    "ActionAuthorization",
    "ActionAuthorizationExecutor",
    "ControlRollbackAuthorization",
    "ControlRollbackAuthorizationExecutor",
    "GENERIC_HDS_VERSION",
    "HDSAblation",
    "HDSConfiguration",
    "HDS_FAILURE_UPDATE_REQUIRED",
    "HDS_GATE_IDS",
    "GenericHDSJudgementSubject",
    "RollbackAuthorization",
    "RollbackAuthorizationExecutor",
]
