"""HDS Judgement Subject for the pre-official GenericAGIRuntime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .generic_memory import MemoryAuthorization, MemoryMutationProposal, MemoryView
from .generic_types import (
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
        "HDS_COMPUTE",
        "HDS_COMMIT",
        "HDS_MEMORY_UPDATE",
        "HDS_EXTERNAL_ACTION",
    )
    projection_boundary: str = "MODEL_IS_NOT_WORLD"

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
        return tuple(sorted(set(failures)))


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


@dataclass(slots=True)
class ActionAuthorizationExecutor:
    """Mechanical single-use capability check; it owns no selection policy."""

    authority_token: object = field(repr=False)
    _consumed: set[str] = field(default_factory=set, init=False)

    def consume(
        self,
        authorization: ActionAuthorization,
        decision: GenericHDSDecision,
        candidate: GenericCandidate,
        observation: GenericObservation,
    ) -> tuple[int, dict[str, int]]:
        if authorization._authority_token is not self.authority_token:
            raise PermissionError("GENERIC_ACTION_AUTHORITY_INVALID")
        if authorization.authorization_id in self._consumed:
            raise PermissionError("GENERIC_ACTION_AUTHORIZATION_REUSED")
        if not decision.external_action_authorized:
            raise PermissionError("GENERIC_ACTION_NOT_HDS_APPROVED")
        if (
            authorization.decision_id != decision.decision_id
            or authorization.candidate_id != candidate.candidate_id
            or authorization.candidate_id != decision.selected_candidate_id
            or authorization.observation_signature != observation.signature
            or authorization.action_id != candidate.descriptor.action_id
            or authorization.payload_digest
            != digest_object(candidate.descriptor.payload())
        ):
            raise PermissionError("GENERIC_ACTION_AUTHORIZATION_BINDING_INVALID")
        if candidate.descriptor.action_id not in observation.available_actions:
            raise PermissionError("GENERIC_ACTION_UNAVAILABLE")
        self._consumed.add(authorization.authorization_id)
        return candidate.descriptor.action_id, candidate.descriptor.payload()


@dataclass(slots=True)
class RollbackAuthorizationExecutor:
    """Consume a failure-bound HDS rollback capability exactly once."""

    authority_token: object = field(repr=False)
    _consumed: set[str] = field(default_factory=set, init=False)

    def consume(
        self,
        authorization: RollbackAuthorization,
        decision: GenericHDSDecision,
        attribution: OutcomeAttribution,
        observation: GenericObservation,
    ) -> str:
        if authorization._authority_token is not self.authority_token:
            raise PermissionError("GENERIC_ROLLBACK_AUTHORITY_INVALID")
        if authorization.authorization_id in self._consumed:
            raise PermissionError("GENERIC_ROLLBACK_AUTHORIZATION_REUSED")
        if (
            authorization.decision_id != decision.decision_id
            or authorization.attribution_id != attribution.attribution_id
            or authorization.failed_observation_signature
            != observation.signature
            or attribution.category != "FAILURE"
            or observation.terminal_state != "GAME_OVER"
        ):
            raise PermissionError("GENERIC_ROLLBACK_BINDING_INVALID")
        self._consumed.add(authorization.authorization_id)
        return authorization.authorization_id


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

    authority_token: object = field(repr=False)
    configuration: HDSConfiguration = field(default_factory=HDSConfiguration)
    run_id: str = "generic-run"
    _cycle_index: int = field(default=0, init=False)
    _no_progress_count: int = field(default=0, init=False)
    _issued_commands: set[str] = field(default_factory=set, init=False)
    _issued_decisions: dict[str, GenericHDSDecision] = field(
        default_factory=dict,
        init=False,
    )
    _last_question: str = field(
        default="What current relation can safely advance the delegated goal?",
        init=False,
    )

    @property
    def cycle_index(self) -> int:
        return self._cycle_index

    @property
    def next_question(self) -> str:
        return self._last_question

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
                f"no-progress:{self._no_progress_count}",
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
            f"cycle:{self._cycle_index}",
        )
        r = tuple(
            sorted(
                {
                    *(f"legal-action:{item}" for item in observation.available_actions),
                    *(f"active-memory:{item.memory_id}" for item in memory.active),
                    *(f"sealed-boundary:{item.memory_id}" for item in memory.sealed),
                }
            )
        )
        body = {
            "run_id": self.run_id,
            "cycle": self._cycle_index,
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
            cycle_index=self._cycle_index,
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
        command_id = "generic-compute-command:" + digest_object(
            {
                "frame": frame,
                "observation": observation.signature,
                "memory": memory.digest,
                "question": self._last_question,
            }
        )[:24]
        if command_id in self._issued_commands:
            raise PermissionError("HDS_COMPUTE_COMMAND_DUPLICATE")
        self._issued_commands.add(command_id)
        return GenericComputeCommand(
            command_id=command_id,
            purpose=frame.purpose,
            goal_tokens=tuple(
                sorted(
                    set(
                        (
                            f"purpose:{frame.purpose}",
                            "goal:progress",
                            "value:information",
                            "boundary:reversible",
                        )
                    )
                )
            ),
            required_outputs=(
                "representations",
                "hypotheses",
                "counter_hypotheses",
                "predictions",
                "candidates",
            ),
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
        has_memory_evidence = any(
            item.kind
            in {
                "ACTION_EFFECT",
                "FAILURE_SIGNATURE",
                "PROCEDURE_CAPABILITY",
                "WORLD_MODEL",
            }
            for item in result.memory_citations
        )
        legal_candidates = tuple(
            item
            for item in result.candidates
            if item.descriptor.action_id in observation.available_actions
        )
        safe_candidates = tuple(
            item
            for item in legal_candidates
            if item.expected_risk <= frame.risk_limit
        )
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
                "PASS" if legal_candidates else "SUSPEND",
                *(("I202",) if not legal_candidates else ()),
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
            has_memory_evidence
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
                "PASS" if safe_candidates else "SUSPEND",
                *(("D602",) if not safe_candidates else ()),
                next_probe="find-lower-risk-candidate",
            )
        )
        gates.append(_gate("G11", "NOT_APPLICABLE"))
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
        elif (
            self._no_progress_count
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
                selected = max(
                    safe_candidates,
                    key=lambda item: (
                        self._candidate_score(item, purpose=frame.purpose),
                        -item.expected_risk,
                        item.candidate_id,
                    ),
                )
                reproduced = has_memory_evidence and (
                    bool(
                    set(selected.provenance).intersection(
                        item.content_digest
                        for item in result.memory_citations
                    )
                    )
                    or has_memory_evidence
                )
                if (
                    self.configuration.evidence_mode == "REPRODUCED_ONLY"
                    and not reproduced
                ):
                    operation = "SUSPEND"
                    reasons.append("EVIDENCE_BOUNDARY_NOT_MET")
                elif (
                    not reproduced
                    or selected.operation == "BOUNDED_PROBE"
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
        decision_id = "hds-decision:" + digest_object(
            {
                "run": self.run_id,
                "cycle": self._cycle_index,
                "frame": frame,
                "compute": result.digest(),
                "operation": operation,
                "selected": (
                    selected.candidate_id if selected is not None else None
                ),
                "gates": gates,
            }
        )[:24]
        decision = GenericHDSDecision(
            decision_id=decision_id,
            assertion_state=assertion,
            operation_state=operation,
            selected_candidate_id=(
                selected.candidate_id if selected is not None else None
            ),
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
        self._issued_decisions[decision_id] = decision
        self._last_question = next_question
        return decision

    def authorize_action(
        self,
        decision: GenericHDSDecision,
        candidate: GenericCandidate,
        observation: GenericObservation,
    ) -> ActionAuthorization:
        issued = self._issued_decisions.get(decision.decision_id)
        if issued != decision:
            raise PermissionError("HDS_ACTION_DECISION_NOT_ISSUED")
        if (
            not decision.external_action_authorized
            or decision.selected_candidate_id != candidate.candidate_id
        ):
            raise PermissionError("HDS_ACTION_NOT_COMMITTED")
        return ActionAuthorization(
            authorization_id="action-authorization:"
            + digest_object(
                {
                    "decision": decision.decision_id,
                    "candidate": candidate.candidate_id,
                    "observation": observation.signature,
                    "payload": candidate.descriptor.payload(),
                }
            )[:24],
            decision_id=decision.decision_id,
            candidate_id=candidate.candidate_id,
            observation_signature=observation.signature,
            action_id=candidate.descriptor.action_id,
            payload_digest=digest_object(candidate.descriptor.payload()),
            _authority_token=self.authority_token,
        )

    def authorize_memory(
        self,
        decision: GenericHDSDecision,
        proposal: MemoryMutationProposal,
        *,
        memory_version: int,
    ) -> MemoryAuthorization:
        issued = self._issued_decisions.get(decision.decision_id)
        if issued != decision:
            raise PermissionError("HDS_MEMORY_DECISION_NOT_ISSUED")
        if not decision.memory_update_authorized:
            raise PermissionError("HDS_MEMORY_UPDATE_NOT_AUTHORIZED")
        proposal_failures = proposal.validate()
        if proposal_failures:
            raise ValueError(";".join(proposal_failures))
        return MemoryAuthorization(
            authorization_id="memory-authorization:"
            + digest_object(
                {
                    "decision": decision.decision_id,
                    "proposal": proposal,
                    "version": memory_version,
                }
            )[:24],
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
        issued = self._issued_decisions.get(decision.decision_id)
        if issued != decision:
            raise PermissionError("HDS_ROLLBACK_DECISION_NOT_ISSUED")
        if (
            attribution.category != "FAILURE"
            or observation.terminal_state != "GAME_OVER"
        ):
            raise PermissionError("HDS_ROLLBACK_FAILURE_REQUIRED")
        return RollbackAuthorization(
            authorization_id="rollback-authorization:"
            + digest_object(
                {
                    "decision": decision.decision_id,
                    "attribution": attribution.attribution_id,
                    "observation": observation.signature,
                }
            )[:24],
            decision_id=decision.decision_id,
            attribution_id=attribution.attribution_id,
            failed_observation_signature=observation.signature,
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
        elif after.signature == before.signature:
            category = "NO_EFFECT"
        else:
            category = "VISIBLE_CHANGE"
        effects = set(after.visible_effects)
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

    def observe_outcome(self, attribution: OutcomeAttribution) -> None:
        if attribution.category == "PROGRESS":
            self._no_progress_count = 0
        else:
            self._no_progress_count += 1
        self._cycle_index += 1
        self._last_question = (
            "Which current relation, revised memory, and legal probe should "
            "be evaluated next?"
        )


__all__ = [
    "ActionAuthorization",
    "ActionAuthorizationExecutor",
    "GENERIC_HDS_VERSION",
    "HDSAblation",
    "HDSConfiguration",
    "HDS_FAILURE_UPDATE_REQUIRED",
    "HDS_GATE_IDS",
    "GenericHDSJudgementSubject",
    "RollbackAuthorization",
    "RollbackAuthorizationExecutor",
]
