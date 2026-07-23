"""Executable P7 audits for the three proper two-subject compositions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .context import BoundedContextState, ContextSnapshot
from .instruction_body import (
    InstructionBody,
    load_default_symbolic_instruction_body,
)
from .ir import CandidateIR, ObservationIR
from .judgment import (
    HDSR,
    HDSX,
    HDSFrame,
    HDSJudgmentSubject,
    HDSMc,
    JudgmentCandidate,
)
from .kernel import PureLLMCompute
from .memory import (
    MemoryMutationResult,
    MemoryOperation,
    MemorySnapshot,
    PassiveMemory,
)
from .protocol import (
    AuthorityViolation,
    ComputeRequest,
    HDSDecision,
    MemoryDirective,
)
from .roles import (
    DeterministicCandidateSurface,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
)
from .schema import digest_object, forbidden_runtime_paths

PAIR_FAILURE_WITNESSES = {
    "C+J": "NO_PERSISTENT_EXPERIENCE_CAUSALITY",
    "C+M": "NO_JUDGMENT_OR_AUTHORIZATION",
    "J+M": "NO_GENERATIVE_COMPUTATION",
}
PAIR_ORDER = (("C", "J"), ("C", "M"), ("J", "M"))
PAIR_EXPECTATIONS = {
    ("C", "J"): {
        "G1": "PASS",
        "G2": "PASS",
        "G3": "FAIL",
        "G4": "FAIL",
        "G5": "PARTIAL",
    },
    ("C", "M"): {
        "G1": "PASS",
        "G2": "FAIL",
        "G3": "PASS",
        "G4": "FAIL",
        "G5": "FAIL",
    },
    ("J", "M"): {
        "G1": "FAIL",
        "G2": "PASS",
        "G3": "PASS",
        "G4": "FAIL",
        "G5": "FAIL",
    },
}


class PairwiseObligationFailure(RuntimeError):
    """Raised only after a pair has exercised its available responsibilities."""

    def __init__(
        self,
        *,
        members: tuple[str, str],
        missing_subject: str,
        witness: str,
    ) -> None:
        super().__init__(witness)
        self.members = members
        self.missing_subject = missing_subject
        self.witness = witness


@dataclass(frozen=True, slots=True)
class PairExecutionEvidence:
    members: tuple[str, str]
    operations: tuple[str, ...]
    observation_digest: str
    proposal_digest: str = ""
    judgment_digest: str = ""
    memory_before_digest: str = ""
    memory_after_digest: str = ""
    hypothesis_count: int = 0
    generated_candidate_count: int = 0
    externally_supplied_candidate_count: int = 0
    judgment_status: str = ""
    external_emit_authorization: bool = False
    memory_write_authorization: bool = False
    unauthorized_write_rejected: bool = False

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.members not in PAIR_ORDER:
            failures.append("PAIR_MEMBERS_INVALID")
        if not self.operations:
            failures.append("PAIR_OPERATION_TRACE_EMPTY")
        if not self.observation_digest:
            failures.append("PAIR_OBSERVATION_DIGEST_MISSING")
        failures.extend(
            f"PAIR_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in forbidden_runtime_paths(
                {
                    "members": self.members,
                    "operations": self.operations,
                    "observation_digest": self.observation_digest,
                    "proposal_digest": self.proposal_digest,
                    "judgment_digest": self.judgment_digest,
                    "memory_before_digest": self.memory_before_digest,
                    "memory_after_digest": self.memory_after_digest,
                }
            )
        )
        if self.members == ("C", "J"):
            if (
                self.hypothesis_count < 2
                or self.generated_candidate_count < 2
                or self.judgment_status != "ACCEPT"
                or not self.external_emit_authorization
                or self.memory_before_digest
                or self.memory_after_digest
            ):
                failures.append("PAIR_CJ_EXECUTION_EVIDENCE_INVALID")
        elif self.members == ("C", "M"):
            if (
                self.hypothesis_count < 2
                or self.generated_candidate_count < 2
                or not self.memory_before_digest
                or self.memory_before_digest != self.memory_after_digest
                or not self.unauthorized_write_rejected
                or self.judgment_status
            ):
                failures.append("PAIR_CM_EXECUTION_EVIDENCE_INVALID")
        elif self.members == ("J", "M") and (
            self.hypothesis_count != 0
            or self.generated_candidate_count != 0
            or self.externally_supplied_candidate_count < 1
            or self.judgment_status != "ACCEPT"
            or not self.memory_write_authorization
            or not self.memory_before_digest
            or self.memory_before_digest != self.memory_after_digest
        ):
            failures.append("PAIR_JM_EXECUTION_EVIDENCE_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class PairAuditCase:
    members: tuple[str, str]
    obligation_statuses: tuple[tuple[str, str], ...]
    overall: str
    missing_subject: str
    failure_witness: str
    evidence: PairExecutionEvidence
    functional_equivalent_substitution: bool

    @property
    def pair_id(self) -> str:
        return "+".join(self.members)

    @property
    def passed(self) -> bool:
        expected = PAIR_EXPECTATIONS.get(self.members)
        return (
            expected is not None
            and dict(self.obligation_statuses) == expected
            and self.overall == "FAIL"
            and self.failure_witness
            == PAIR_FAILURE_WITNESSES.get(self.pair_id)
            and self.missing_subject == ({"C", "J", "M"} - set(self.members)).pop()
            and self.evidence.validate() == ()
            and not self.functional_equivalent_substitution
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class PairwiseAuditReport:
    cases: tuple[PairAuditCase, ...]

    @property
    def passed(self) -> bool:
        return (
            tuple(case.members for case in self.cases) == PAIR_ORDER
            and all(case.passed for case in self.cases)
            and len({case.failure_witness for case in self.cases}) == 3
            and len({case.evidence.digest for case in self.cases}) == 3
        )

    @property
    def functional_equivalent_leak_count(self) -> int:
        return sum(
            case.functional_equivalent_substitution for case in self.cases
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


def _observation_and_context(
    raw_observation: Mapping[str, object],
) -> tuple[ObservationIR, ContextSnapshot]:
    observation = DeterministicSymbolSpace().encode(raw_observation)
    context = BoundedContextState().ingest(observation)
    return observation, context


def _request(
    *,
    command_id: str,
    observation: ObservationIR,
    context: ContextSnapshot,
    memory: MemorySnapshot,
    body: InstructionBody,
) -> ComputeRequest:
    return ComputeRequest(
        command_id=command_id,
        operation="LLM_COMPUTE",
        observation_signature=observation.frame_signature,
        context_signature=context.digest,
        memory_signature=memory.digest,
        contract_version=body.contract.version,
        feature_tokens=observation.feature_tokens,
    )


def _judgment_candidate(candidate: CandidateIR) -> JudgmentCandidate:
    predicted = tuple(
        sorted(
            {
                effect
                for effects in candidate.expected_effects_by_hypothesis.values()
                for effect in effects
            }
        )
    ) or ("UNCERTAIN_VISIBLE_EFFECT",)
    evidence = candidate.provenance or ("evidence:current-observation",)
    return JudgmentCandidate(
        candidate_id=candidate.candidate_id,
        predicted_outcomes=predicted,
        evidence_refs=evidence,
        counter_evidence_refs=(),
        preconditions=candidate.preconditions
        or ("CURRENT_OBSERVATION_PRESENT",),
        falsification_conditions=candidate.falsification_conditions
        or ("rendered effect contradicts prediction",),
        score=round(
            min(
                1.0,
                max(
                    0.0,
                    candidate.expected_progress
                    + candidate.expected_information_gain,
                ),
            ),
            6,
        ),
        risk=round(min(1.0, max(0.0, candidate.expected_risk)), 6),
        admissible=True,
        rejected=False,
        reversible=candidate.rollback_cost < 1.0,
        rollback_reference=(
            "snapshot:previous" if candidate.rollback_cost < 1.0 else None
        ),
        reason_codes=("W_X_R_MC_CLOSED",),
    )


def _frame(
    *,
    frame_id: str,
    purpose: str,
    candidates: tuple[JudgmentCandidate, ...],
    evidence: tuple[str, ...],
    allow_memory_write: bool,
    allow_external_emit: bool,
) -> HDSFrame:
    return HDSFrame(
        frame_id=frame_id,
        purpose=purpose,
        x=HDSX(
            targets=("rendered-environment",),
            candidate_ids=tuple(item.candidate_id for item in candidates),
            observation_scope=("rendered-frame", "bounded-context"),
        ),
        r=HDSR(
            relations=("candidate-predicts-rendered-effect",),
            evidence_links=evidence,
            counter_evidence_links=(),
        ),
        mc=HDSMc(
            identity="semantic:pairwise-audit",
            boundary="rendered-and-admitted-evidence-only",
            acceptance_criteria=("W_X_R_MC_CLOSED",),
            rejection_criteria=("hazard", "contradiction"),
            stop_on=("terminal", "budget-exhaustion"),
            max_risk=1.0,
            allow_memory_write=allow_memory_write,
            allow_external_emit=allow_external_emit,
        ),
        observation_boundary="rendered-and-admitted-evidence-only",
        candidates=candidates,
        evidence=evidence,
        counter_evidence=(),
        risk=max((item.risk for item in candidates), default=0.0),
        hazard=False,
        budget=2,
        unknowns=(),
        stopping_conditions=(),
    )


def _seed_memory(memory: PassiveMemory, *, provenance: str) -> None:
    if memory.version != 0:
        retained = memory.read("experience:prior-transition")
        if (
            memory.version == 1
            and retained is not None
            and provenance in retained.provenance
        ):
            return
        raise RuntimeError("PAIR_MEMORY_NOT_IN_EXPECTED_INITIAL_STATE")
    result = memory.execute_storage(
        MemoryOperation(
            operation="ADD",
            target="experience:prior-transition",
            expected_version=memory.version,
            lifecycle="ACTIVE",
            evidence_signature="evidence:prior-rendered-effect",
            payload_items=(
                ("current_purpose", "evaluate-observed-transition"),
                ("current_state", "prior-effect-observed"),
                ("evidence", ("rendered-delta",)),
                ("hypothesis", "action may change rendered state"),
                ("support", 1),
            ),
            provenance=(provenance,),
        )
    )
    if not isinstance(result, MemoryMutationResult):
        raise TypeError("pair seed mutation did not return a mutation result")


@dataclass(slots=True)
class ComputeJudgmentPair:
    """Exercise C and J while deliberately providing no persistent M."""

    compute_subject: PureLLMCompute = field(default_factory=PureLLMCompute)
    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    instruction_body: InstructionBody = field(
        default_factory=load_default_symbolic_instruction_body
    )
    world_model: DeterministicWorldModel = field(
        default_factory=DeterministicWorldModel
    )
    candidate_surface: DeterministicCandidateSurface = field(
        default_factory=DeterministicCandidateSurface
    )

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> PairExecutionEvidence:
        observation, context = _observation_and_context(raw_observation)
        static_empty_view = MemorySnapshot(version=0, entries=())
        compute_request_decision = self.judgment_subject.judge(
            _frame(
                frame_id="frame:pair-cj-request",
                purpose="request-observation-conditioned-candidates",
                candidates=(),
                evidence=("evidence:current-observation",),
                allow_memory_write=False,
                allow_external_emit=True,
            )
        )
        if (
            compute_request_decision.status != "COMPUTE_REQUEST"
            or compute_request_decision.compute_request is None
        ):
            raise RuntimeError("PAIR_CJ_COMPUTE_REQUEST_NOT_ISSUED")
        proposal = self.compute_subject.compute_standalone(
            _request(
                command_id=compute_request_decision.compute_request.request_id,
                observation=observation,
                context=context,
                memory=static_empty_view,
                body=self.instruction_body,
            ),
            observation,
            context,
            self.instruction_body,
            self.world_model,
            self.candidate_surface,
            static_empty_view,
        )
        candidates = tuple(
            _judgment_candidate(item) for item in proposal.candidates
        )
        final_decision = self.judgment_subject.judge(
            _frame(
                frame_id="frame:pair-cj-close",
                purpose="select-safe-observation-conditioned-candidate",
                candidates=candidates,
                evidence=("evidence:current-observation",),
                allow_memory_write=False,
                allow_external_emit=True,
            )
        )
        return PairExecutionEvidence(
            members=("C", "J"),
            operations=(
                "J_COMPUTE_REQUEST",
                "C_HYPOTHESIS_AND_CANDIDATE_GENERATION",
                "J_CANDIDATE_JUDGMENT",
                "J_ONE_CYCLE_ACTION_AUTHORIZATION",
                "NO_MEMORY_CARRIER_AVAILABLE",
            ),
            observation_digest=observation.frame_signature,
            proposal_digest=proposal.digest,
            judgment_digest=final_decision.digest,
            hypothesis_count=len(proposal.hypotheses),
            generated_candidate_count=len(proposal.candidates),
            judgment_status=final_decision.status,
            external_emit_authorization=final_decision.allow_external_emit,
            memory_write_authorization=final_decision.allow_memory_write,
        )

    @staticmethod
    def require_full_obligations() -> None:
        raise PairwiseObligationFailure(
            members=("C", "J"),
            missing_subject="M",
            witness=PAIR_FAILURE_WITNESSES["C+J"],
        )


@dataclass(slots=True)
class ComputeMemoryPair:
    """Exercise C over a real M while deliberately providing no J."""

    compute_subject: PureLLMCompute = field(default_factory=PureLLMCompute)
    memory_subject: PassiveMemory = field(default_factory=PassiveMemory)
    instruction_body: InstructionBody = field(
        default_factory=load_default_symbolic_instruction_body
    )
    world_model: DeterministicWorldModel = field(
        default_factory=DeterministicWorldModel
    )
    candidate_surface: DeterministicCandidateSurface = field(
        default_factory=DeterministicCandidateSurface
    )

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> PairExecutionEvidence:
        observation, context = _observation_and_context(raw_observation)
        _seed_memory(self.memory_subject, provenance="pair-cm:fixture-seed")
        memory_before = self.memory_subject.view()
        proposal = self.compute_subject.compute_standalone(
            _request(
                command_id="pair-cm:externally-supplied-compute-request",
                observation=observation,
                context=context,
                memory=memory_before,
                body=self.instruction_body,
            ),
            observation,
            context,
            self.instruction_body,
            self.world_model,
            self.candidate_surface,
            memory_before,
        )

        denied = HDSDecision(
            command_id="pair-cm:no-judgment",
            decision_id="pair-cm:no-authorization",
            status="SUSPEND",
            reason_codes=("JUDGMENT_SUBJECT_ABSENT",),
        )
        directive = MemoryDirective(
            command_id=denied.command_id,
            decision_id=denied.decision_id,
            operation="ADD",
            target=proposal.memory_proposal.target,
            lifecycle="PROPOSED",
            evidence_signature="evidence:proposal-only",
            expected_version=self.memory_subject.version,
            payload_digest=digest_object(proposal.memory_proposal.payload()),
        )
        rejected = False
        try:
            self.memory_subject.apply_authorized(
                directive,
                denied,
                proposal.memory_proposal.payload(),
                executor=self.compute_subject.executor,
            )
        except AuthorityViolation:
            rejected = True
        memory_after = self.memory_subject.view()
        return PairExecutionEvidence(
            members=("C", "M"),
            operations=(
                "M_LOW_LEVEL_FIXTURE_SEED",
                "C_MEMORY_READ",
                "C_HYPOTHESIS_AND_CANDIDATE_GENERATION",
                "C_MEMORY_UPDATE_PROPOSAL",
                "M_RUNTIME_WRITE_REJECTED_WITHOUT_J",
            ),
            observation_digest=observation.frame_signature,
            proposal_digest=proposal.digest,
            memory_before_digest=memory_before.digest,
            memory_after_digest=memory_after.digest,
            hypothesis_count=len(proposal.hypotheses),
            generated_candidate_count=len(proposal.candidates),
            unauthorized_write_rejected=rejected,
        )

    @staticmethod
    def require_full_obligations() -> None:
        raise PairwiseObligationFailure(
            members=("C", "M"),
            missing_subject="J",
            witness=PAIR_FAILURE_WITNESSES["C+M"],
        )


@dataclass(slots=True)
class JudgmentMemoryPair:
    """Exercise J over supplied candidates and retained evidence with no C."""

    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )
    memory_subject: PassiveMemory = field(default_factory=PassiveMemory)

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> PairExecutionEvidence:
        observation, _ = _observation_and_context(raw_observation)
        _seed_memory(self.memory_subject, provenance="pair-jm:fixture-seed")
        memory_before = self.memory_subject.view()
        retained = self.memory_subject.read("experience:prior-transition")
        if retained is None:
            raise RuntimeError("PAIR_JM_RETAINED_EVIDENCE_MISSING")
        supplied = JudgmentCandidate(
            candidate_id="candidate:externally-supplied",
            predicted_outcomes=("VISIBLE_STATE_CHANGE",),
            evidence_refs=(retained.evidence_signature,),
            counter_evidence_refs=(),
            preconditions=("CURRENT_OBSERVATION_PRESENT",),
            falsification_conditions=(
                "rendered effect contradicts supplied prediction",
            ),
            score=0.75,
            risk=0.1,
            admissible=True,
            rejected=False,
            reversible=True,
            rollback_reference="snapshot:previous",
            reason_codes=("W_X_R_MC_CLOSED",),
        )
        decision = self.judgment_subject.judge(
            _frame(
                frame_id="frame:pair-jm-close",
                purpose="judge-externally-supplied-candidate",
                candidates=(supplied,),
                evidence=(retained.evidence_signature,),
                allow_memory_write=True,
                allow_external_emit=False,
            )
        )
        memory_after = self.memory_subject.view()
        return PairExecutionEvidence(
            members=("J", "M"),
            operations=(
                "M_LOW_LEVEL_FIXTURE_SEED",
                "M_RETAINED_EVIDENCE_READ",
                "EXTERNAL_CANDIDATE_SUPPLIED",
                "J_CANDIDATE_JUDGMENT",
                "J_MEMORY_UPDATE_AUTHORIZATION_JUDGMENT",
                "NO_COMPUTE_EXECUTOR_AVAILABLE",
            ),
            observation_digest=observation.frame_signature,
            judgment_digest=decision.digest,
            memory_before_digest=memory_before.digest,
            memory_after_digest=memory_after.digest,
            externally_supplied_candidate_count=1,
            judgment_status=decision.status,
            memory_write_authorization=decision.allow_memory_write,
        )

    @staticmethod
    def require_full_obligations() -> None:
        raise PairwiseObligationFailure(
            members=("J", "M"),
            missing_subject="C",
            witness=PAIR_FAILURE_WITNESSES["J+M"],
        )


def _case_from_failure(
    *,
    evidence: PairExecutionEvidence,
    failure: PairwiseObligationFailure,
    functional_equivalent_substitution: bool,
) -> PairAuditCase:
    expected = PAIR_EXPECTATIONS[evidence.members]
    return PairAuditCase(
        members=evidence.members,
        obligation_statuses=tuple(expected.items()),
        overall="FAIL",
        missing_subject=failure.missing_subject,
        failure_witness=failure.witness,
        evidence=evidence,
        functional_equivalent_substitution=functional_equivalent_substitution,
    )


def run_pairwise_subject_audit(
    raw_observation: Mapping[str, object],
) -> PairwiseAuditReport:
    """Exercise all three pairs and capture their actual terminal failures."""

    cases: list[PairAuditCase] = []
    harnesses = (
        ComputeJudgmentPair(),
        ComputeMemoryPair(),
        JudgmentMemoryPair(),
    )
    for harness in harnesses:
        evidence = harness.exercise(raw_observation)
        try:
            harness.require_full_obligations()
        except PairwiseObligationFailure as failure:
            missing_field = {
                "C": "compute_subject",
                "J": "judgment_subject",
                "M": "memory_subject",
            }[failure.missing_subject]
            substitution = (
                failure.members != evidence.members
                or hasattr(harness, missing_field)
            )
            cases.append(
                _case_from_failure(
                    evidence=evidence,
                    failure=failure,
                    functional_equivalent_substitution=substitution,
                )
            )
        else:
            raise RuntimeError("PAIRWISE_PROPER_SUBSET_UNEXPECTEDLY_PASSED")
    report = PairwiseAuditReport(cases=tuple(cases))
    if not report.passed:
        raise RuntimeError("PAIRWISE_AUDIT_CONTRACT_FAILED")
    return report


__all__ = [
    "PAIR_EXPECTATIONS",
    "PAIR_FAILURE_WITNESSES",
    "PAIR_ORDER",
    "ComputeJudgmentPair",
    "ComputeMemoryPair",
    "JudgmentMemoryPair",
    "PairAuditCase",
    "PairExecutionEvidence",
    "PairwiseAuditReport",
    "PairwiseObligationFailure",
    "run_pairwise_subject_audit",
]
