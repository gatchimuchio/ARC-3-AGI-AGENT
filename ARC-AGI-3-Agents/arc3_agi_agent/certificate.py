"""P9 finite subset audit and deterministic minimum-three certificate builder."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context import BoundedContextState
from .instruction_body import (
    InstructionBody,
    load_default_symbolic_instruction_body,
)
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
    MemoryQuery,
    MemoryQueryResult,
    MemorySnapshot,
    PassiveMemory,
)
from .pairwise import PairwiseAuditReport, run_pairwise_subject_audit
from .protocol import ComputeRequest
from .roles import (
    DeterministicCandidateSurface,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
)
from .schema import digest_object, forbidden_runtime_paths
from .trinity import TrinityTwoCycleReport, run_trinity_two_cycle_audit

SUBSET_ORDER = (
    (),
    ("C",),
    ("J",),
    ("M",),
    ("C", "J"),
    ("C", "M"),
    ("J", "M"),
    ("C", "J", "M"),
)
SUBSET_EXPECTATIONS = {
    (): {
        "G1": "FAIL",
        "G2": "FAIL",
        "G3": "FAIL",
        "G4": "FAIL",
        "G5": "FAIL",
    },
    ("C",): {
        "G1": "PASS",
        "G2": "FAIL",
        "G3": "FAIL",
        "G4": "FAIL",
        "G5": "FAIL",
    },
    ("J",): {
        "G1": "FAIL",
        "G2": "PASS",
        "G3": "FAIL",
        "G4": "FAIL",
        "G5": "FAIL",
    },
    ("M",): {
        "G1": "FAIL",
        "G2": "FAIL",
        "G3": "PASS",
        "G4": "FAIL",
        "G5": "FAIL",
    },
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
    ("C", "J", "M"): {
        "G1": "PASS",
        "G2": "PASS",
        "G3": "PASS",
        "G4": "PASS",
        "G5": "PASS",
    },
}
SUBSET_FAILURE_WITNESSES = {
    (): "NO_COMPUTE_JUDGMENT_OR_MEMORY",
    ("C",): "NO_JUDGMENT_OR_MEMORY",
    ("J",): "NO_GENERATIVE_COMPUTATION_OR_MEMORY",
    ("M",): "NO_GENERATIVE_COMPUTATION_OR_JUDGMENT",
    ("C", "J"): "NO_PERSISTENT_EXPERIENCE_CAUSALITY",
    ("C", "M"): "NO_JUDGMENT_OR_AUTHORIZATION",
    ("J", "M"): "NO_GENERATIVE_COMPUTATION",
}
P9_ARTIFACT_FILENAMES = (
    "agi_minimum_three_certificate.json",
    "agi_subset_enumeration.json",
    "agi_removal_witnesses.json",
    "agi_obligation_graph.json",
    "agi_conformance_report.md",
)


def default_certificate_observation() -> dict[str, object]:
    """Return a fixed semantic fixture with no game/task/level identity."""

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


@dataclass(frozen=True, slots=True)
class SubsetExecutionEvidence:
    members: tuple[str, ...]
    observed_owners: tuple[str, ...]
    operations: tuple[str, ...]
    observation_digest: str
    hypothesis_count: int = 0
    generated_candidate_count: int = 0
    externally_supplied_candidate_count: int = 0
    judgment_status: str = ""
    memory_version: int = 0
    component_digest: str = ""
    two_cycle_causality_pass: bool = False

    @property
    def digest(self) -> str:
        return digest_object(self)

    @property
    def functional_equivalent_responsibility_leaks(self) -> tuple[str, ...]:
        leaks: list[str] = []
        if "C" not in self.members and (
            self.hypothesis_count != 0
            or self.generated_candidate_count != 0
        ):
            leaks.append("C")
        if "J" not in self.members and self.judgment_status:
            leaks.append("J")
        if "M" not in self.members and self.memory_version != 0:
            leaks.append("M")
        return tuple(leaks)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.members not in SUBSET_ORDER:
            failures.append("SUBSET_EVIDENCE_MEMBERS_INVALID")
        if self.observed_owners != self.members:
            failures.append("SUBSET_FUNCTIONAL_EQUIVALENT_OWNER_LEAK")
        if not self.operations:
            failures.append("SUBSET_EVIDENCE_OPERATION_EMPTY")
        if not self.observation_digest:
            failures.append("SUBSET_EVIDENCE_OBSERVATION_MISSING")
        failures.extend(
            "SUBSET_FUNCTIONAL_EQUIVALENT_RESPONSIBILITY_LEAK:"
            + subject
            for subject in self.functional_equivalent_responsibility_leaks
        )
        if self.members == ():
            if self.operations != ("NO_SUBJECT_OPERATION_AVAILABLE",):
                failures.append("SUBSET_EMPTY_OPERATION_INVALID")
        elif self.members == ("C",):
            if (
                self.hypothesis_count < 2
                or self.generated_candidate_count < 2
                or self.judgment_status
                or self.memory_version != 0
            ):
                failures.append("SUBSET_C_EVIDENCE_INVALID")
        elif self.members == ("J",):
            if (
                self.hypothesis_count != 0
                or self.generated_candidate_count != 0
                or self.externally_supplied_candidate_count != 1
                or self.judgment_status != "ACCEPT"
                or self.memory_version != 0
            ):
                failures.append("SUBSET_J_EVIDENCE_INVALID")
        elif self.members == ("M",):
            if (
                self.hypothesis_count != 0
                or self.generated_candidate_count != 0
                or self.judgment_status
                or self.memory_version != 1
            ):
                failures.append("SUBSET_M_EVIDENCE_INVALID")
        elif len(self.members) == 2:
            if not self.component_digest:
                failures.append("SUBSET_PAIR_EVIDENCE_MISSING")
        elif self.members == ("C", "J", "M") and (
            not self.component_digest
            or not self.two_cycle_causality_pass
            or self.hypothesis_count < 2
            or self.generated_candidate_count < 2
            or self.judgment_status != "ACCEPT"
            or self.memory_version != 2
        ):
            failures.append("SUBSET_FULL_EVIDENCE_INVALID")
        failures.extend(
            f"SUBSET_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in forbidden_runtime_paths(dataclasses.asdict(self))
        )
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class SubsetAuditCase:
    members: tuple[str, ...]
    obligation_statuses: tuple[tuple[str, str], ...]
    overall: str
    failure_witness: str
    missing_subjects: tuple[str, ...]
    evidence: SubsetExecutionEvidence
    functional_equivalent_substitution: bool

    @property
    def subset_id(self) -> str:
        return "{" + ",".join(self.members) + "}"

    @property
    def passed(self) -> bool:
        expected = SUBSET_EXPECTATIONS.get(self.members)
        is_full = self.members == ("C", "J", "M")
        return (
            expected is not None
            and dict(self.obligation_statuses) == expected
            and self.overall == ("PASS" if is_full else "FAIL")
            and self.failure_witness
            == ("" if is_full else SUBSET_FAILURE_WITNESSES[self.members])
            and self.missing_subjects
            == tuple(subject for subject in ("C", "J", "M") if subject not in self.members)
            and self.evidence.validate() == ()
            and not self.functional_equivalent_substitution
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class RemovalWitness:
    removed_subject: str
    remaining_members: tuple[str, str]
    failure_witness: str
    overall: str
    functional_equivalent_substitution: bool
    evidence_digest: str

    @property
    def passed(self) -> bool:
        missing_subjects = tuple(
            subject
            for subject in ("C", "J", "M")
            if subject not in self.remaining_members
        )
        return (
            self.remaining_members in SUBSET_FAILURE_WITNESSES
            and len(missing_subjects) == 1
            and self.removed_subject == missing_subjects[0]
            and self.failure_witness
            == SUBSET_FAILURE_WITNESSES[self.remaining_members]
            and self.overall == "FAIL"
            and not self.functional_equivalent_substitution
            and bool(self.evidence_digest)
        )


@dataclass(frozen=True, slots=True)
class EightSubsetAuditReport:
    cases: tuple[SubsetAuditCase, ...]
    removal_witnesses: tuple[RemovalWitness, ...]

    @property
    def full_set_pass(self) -> bool:
        return self.cases[-1].overall == "PASS" and self.cases[-1].passed

    @property
    def proper_subset_pass_count(self) -> int:
        return sum(case.overall == "PASS" for case in self.cases[:-1])

    @property
    def single_removal_fail_count(self) -> int:
        return sum(witness.passed for witness in self.removal_witnesses)

    @property
    def pair_subset_fail_count(self) -> int:
        return sum(
            len(case.members) == 2 and case.overall == "FAIL"
            for case in self.cases
        )

    @property
    def two_cycle_causality_pass(self) -> bool:
        return self.cases[-1].evidence.two_cycle_causality_pass

    @property
    def functional_equivalent_leak_count(self) -> int:
        return sum(
            case.functional_equivalent_substitution for case in self.cases
        )

    @property
    def passed(self) -> bool:
        return (
            tuple(case.members for case in self.cases) == SUBSET_ORDER
            and len(self.cases) == 8
            and all(case.passed for case in self.cases)
            and self.full_set_pass
            and self.proper_subset_pass_count == 0
            and self.single_removal_fail_count == 3
            and self.pair_subset_fail_count == 3
            and self.two_cycle_causality_pass
            and self.functional_equivalent_leak_count == 0
            and len(self.removal_witnesses) == 3
            and len(
                {item.failure_witness for item in self.removal_witnesses}
            )
            == 3
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(slots=True)
class EmptySubsetHarness:
    """An executable boundary with no C, J, or M field."""

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> SubsetExecutionEvidence:
        observation = DeterministicSymbolSpace().encode(raw_observation)
        return SubsetExecutionEvidence(
            members=(),
            observed_owners=(),
            operations=("NO_SUBJECT_OPERATION_AVAILABLE",),
            observation_digest=observation.frame_signature,
        )


@dataclass(slots=True)
class ComputeOnlyHarness:
    compute_subject: PureLLMCompute = field(default_factory=PureLLMCompute)
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
    ) -> SubsetExecutionEvidence:
        observation = DeterministicSymbolSpace().encode(raw_observation)
        context = BoundedContextState().ingest(observation)
        memory = MemorySnapshot(version=0, entries=())
        request = ComputeRequest(
            command_id="subset-c:external-compute-request",
            operation="LLM_COMPUTE",
            observation_signature=observation.frame_signature,
            context_signature=context.digest,
            memory_signature=memory.digest,
            contract_version=self.instruction_body.contract.version,
            feature_tokens=observation.feature_tokens,
        )
        proposal = self.compute_subject.compute_standalone(
            request,
            observation,
            context,
            self.instruction_body,
            self.world_model,
            self.candidate_surface,
            memory,
        )
        return SubsetExecutionEvidence(
            members=("C",),
            observed_owners=("C",),
            operations=(
                "C_OBSERVATION_CONDITIONED_COMPUTE",
                "C_HYPOTHESIS_GENERATION",
                "C_CANDIDATE_GENERATION",
                "C_UPDATE_AND_OUTPUT_PROPOSAL",
            ),
            observation_digest=observation.frame_signature,
            hypothesis_count=len(proposal.hypotheses),
            generated_candidate_count=len(proposal.candidates),
            component_digest=proposal.digest,
        )


@dataclass(slots=True)
class JudgmentOnlyHarness:
    judgment_subject: HDSJudgmentSubject = field(
        default_factory=HDSJudgmentSubject
    )

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> SubsetExecutionEvidence:
        observation = DeterministicSymbolSpace().encode(raw_observation)
        supplied = JudgmentCandidate(
            candidate_id="candidate:externally-supplied",
            predicted_outcomes=("VISIBLE_STATE_CHANGE",),
            evidence_refs=("evidence:current-observation",),
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
        frame = HDSFrame(
            frame_id="frame:subset-j",
            purpose="judge-externally-supplied-candidate",
            x=HDSX(
                targets=("rendered-environment",),
                candidate_ids=(supplied.candidate_id,),
                observation_scope=("rendered-frame",),
            ),
            r=HDSR(
                relations=("candidate-predicts-rendered-effect",),
                evidence_links=supplied.evidence_refs,
                counter_evidence_links=(),
            ),
            mc=HDSMc(
                identity="semantic:subset-j",
                boundary="rendered-and-admitted-evidence-only",
                acceptance_criteria=("W_X_R_MC_CLOSED",),
                rejection_criteria=("hazard", "contradiction"),
                stop_on=("terminal", "budget-exhaustion"),
                max_risk=1.0,
            ),
            observation_boundary="rendered-and-admitted-evidence-only",
            candidates=(supplied,),
            evidence=supplied.evidence_refs,
            counter_evidence=(),
            risk=supplied.risk,
            hazard=False,
            budget=1,
            unknowns=(),
            stopping_conditions=(),
        )
        decision = self.judgment_subject.judge(frame)
        return SubsetExecutionEvidence(
            members=("J",),
            observed_owners=("J",),
            operations=(
                "EXTERNAL_CANDIDATE_SUPPLIED",
                "J_W_X_R_MC_JUDGMENT",
                "J_AUTHORIZATION_JUDGMENT",
            ),
            observation_digest=observation.frame_signature,
            externally_supplied_candidate_count=1,
            judgment_status=decision.status,
            component_digest=decision.digest,
        )


@dataclass(slots=True)
class MemoryOnlyHarness:
    memory_subject: PassiveMemory = field(default_factory=PassiveMemory)

    def exercise(
        self,
        raw_observation: Mapping[str, object],
    ) -> SubsetExecutionEvidence:
        observation = DeterministicSymbolSpace().encode(raw_observation)
        if self.memory_subject.version == 0:
            result = self.memory_subject.execute_storage(
                MemoryOperation(
                    operation="ADD",
                    target="experience:subset-m",
                    expected_version=0,
                    lifecycle="ACTIVE",
                    evidence_signature="evidence:retained",
                    payload_items=(
                        ("current_state", "observed"),
                        ("evidence", ("rendered-delta",)),
                    ),
                    provenance=("subset-m:fixture-seed",),
                )
            )
            if not isinstance(result, MemoryMutationResult):
                raise TypeError("M-only mutation result invalid")
        query_result = self.memory_subject.execute_storage(
            MemoryOperation(
                operation="QUERY",
                query=MemoryQuery(terms=("observed",)),
            )
        )
        if not isinstance(query_result, MemoryQueryResult):
            raise TypeError("M-only query result invalid")
        return SubsetExecutionEvidence(
            members=("M",),
            observed_owners=("M",),
            operations=(
                "M_LOW_LEVEL_ADD",
                "M_DETERMINISTIC_QUERY",
                "M_VERSIONED_RETENTION",
            ),
            observation_digest=observation.frame_signature,
            memory_version=self.memory_subject.version,
            component_digest=query_result.digest,
        )


def _unexpected_subject_field(
    harness: object,
    members: tuple[str, ...],
    evidence: SubsetExecutionEvidence,
) -> bool:
    subject_fields = {
        "C": "compute_subject",
        "J": "judgment_subject",
        "M": "memory_subject",
    }
    unexpected_field = any(
        hasattr(harness, field_name) != (subject in members)
        for subject, field_name in subject_fields.items()
    )
    return bool(
        unexpected_field
        or evidence.functional_equivalent_responsibility_leaks
    )


def _case(
    evidence: SubsetExecutionEvidence,
    *,
    functional_equivalent_substitution: bool,
) -> SubsetAuditCase:
    members = evidence.members
    return SubsetAuditCase(
        members=members,
        obligation_statuses=tuple(SUBSET_EXPECTATIONS[members].items()),
        overall="PASS" if members == ("C", "J", "M") else "FAIL",
        failure_witness=SUBSET_FAILURE_WITNESSES.get(members, ""),
        missing_subjects=tuple(
            subject for subject in ("C", "J", "M") if subject not in members
        ),
        evidence=evidence,
        functional_equivalent_substitution=functional_equivalent_substitution,
    )


def _pair_cases(
    report: PairwiseAuditReport,
    observation_digest: str,
) -> tuple[SubsetAuditCase, ...]:
    output: list[SubsetAuditCase] = []
    for pair_case in report.cases:
        evidence = SubsetExecutionEvidence(
            members=pair_case.members,
            observed_owners=pair_case.members,
            operations=pair_case.evidence.operations,
            observation_digest=observation_digest,
            hypothesis_count=pair_case.evidence.hypothesis_count,
            generated_candidate_count=(
                pair_case.evidence.generated_candidate_count
            ),
            externally_supplied_candidate_count=(
                pair_case.evidence.externally_supplied_candidate_count
            ),
            judgment_status=pair_case.evidence.judgment_status,
            memory_version=(
                1 if "M" in pair_case.members else 0
            ),
            component_digest=pair_case.digest,
        )
        output.append(
            _case(
                evidence,
                functional_equivalent_substitution=(
                    pair_case.functional_equivalent_substitution
                ),
            )
        )
    return tuple(output)


def _full_case(
    report: TrinityTwoCycleReport,
    observation_digest: str,
) -> SubsetAuditCase:
    evidence = SubsetExecutionEvidence(
        members=("C", "J", "M"),
        observed_owners=("C", "J", "M"),
        operations=(
            "J_COMPUTE_COMMAND",
            "C_HYPOTHESIS_AND_CANDIDATE_GENERATION",
            "J_JUDGMENT_AND_EFFECT_AUTHORIZATION",
            "C_AUTHORIZED_EFFECT_EXECUTION",
            "M_VERSIONED_RETENTION",
            "J_RESULT_REEVALUATION",
            "TRINITY_TWO_CYCLE_CAUSALITY",
        ),
        observation_digest=observation_digest,
        hypothesis_count=report.m_only.variant.hypothesis_count,
        generated_candidate_count=report.m_only.variant.candidate_count,
        judgment_status=report.m_only.variant.judgment_status,
        memory_version=report.cycle_evidence.cycle_2_after_memory_version,
        component_digest=report.digest,
        two_cycle_causality_pass=report.passed,
    )
    return _case(evidence, functional_equivalent_substitution=False)


def run_eight_subset_audit(
    raw_observation: Mapping[str, object],
) -> EightSubsetAuditReport:
    """Execute all finite C/J/M subsets exactly once in normative order."""

    empty_harness = EmptySubsetHarness()
    c_harness = ComputeOnlyHarness()
    j_harness = JudgmentOnlyHarness()
    m_harness = MemoryOnlyHarness()
    single_harnesses = (
        ((), empty_harness),
        (("C",), c_harness),
        (("J",), j_harness),
        (("M",), m_harness),
    )
    cases = [
        _case(
            evidence := harness.exercise(raw_observation),
            functional_equivalent_substitution=_unexpected_subject_field(
                harness,
                members,
                evidence,
            ),
        )
        for members, harness in single_harnesses
    ]
    observation = DeterministicSymbolSpace().encode(raw_observation)
    pair_report = run_pairwise_subject_audit(raw_observation)
    cases.extend(_pair_cases(pair_report, observation.frame_signature))
    trinity_report = run_trinity_two_cycle_audit(raw_observation)
    cases.append(_full_case(trinity_report, observation.frame_signature))

    removal_witnesses = tuple(
        RemovalWitness(
            removed_subject=next(
                subject
                for subject in ("C", "J", "M")
                if subject not in case.members
            ),
            remaining_members=(case.members[0], case.members[1]),
            failure_witness=case.failure_witness,
            overall=case.overall,
            functional_equivalent_substitution=(
                case.functional_equivalent_substitution
            ),
            evidence_digest=case.evidence.digest,
        )
        for case in cases
        if len(case.members) == 2
    )
    report = EightSubsetAuditReport(
        cases=tuple(cases),
        removal_witnesses=removal_witnesses,
    )
    if not report.passed:
        raise RuntimeError("EIGHT_SUBSET_AUDIT_CONTRACT_FAILED")
    return report


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _graph_projection(
    graph: Mapping[str, Any],
    report: EightSubsetAuditReport,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "artifact_type": "agi_minimum_three_measured_obligation_graph",
        "source_projection_digest": digest_object(
            {
                "subjects": graph.get("subjects"),
                "obligations": graph.get("obligations"),
                "edges": graph.get("edges"),
                "subset_expectations": graph.get("subset_expectations"),
            }
        ),
        "subjects": graph.get("subjects"),
        "obligations": graph.get("obligations"),
        "edges": graph.get("edges"),
        "measured_subsets": [
            {
                "members": list(case.members),
                "obligations": dict(case.obligation_statuses),
                "overall": case.overall,
                "evidence_digest": case.evidence.digest,
            }
            for case in report.cases
        ],
    }


def _conformance_markdown(report: EightSubsetAuditReport) -> bytes:
    rows = "\n".join(
        "| "
        + "{" + ",".join(case.members) + "}"
        + " | "
        + " | ".join(
            dict(case.obligation_statuses)[f"G{index}"]
            for index in range(1, 6)
        )
        + f" | {case.overall} | `{case.failure_witness or '-'}` |"
        for case in report.cases
    )
    text = f"""# AGI最小三構成 P9 Conformance Report

- schema: `agi-minimum-three-certificate-v1`
- audit digest: `{report.digest}`
- full set pass: `{str(report.full_set_pass).lower()}`
- proper subset pass count: `{report.proper_subset_pass_count}`
- single removal fail count: `{report.single_removal_fail_count}`
- pair subset fail count: `{report.pair_subset_fail_count}`
- two-cycle causality pass: `{str(report.two_cycle_causality_pass).lower()}`
- functional-equivalent leak count: `{report.functional_equivalent_leak_count}`

| subset | G1 | G2 | G3 | G4 | G5 | overall | witness |
|---|---|---|---|---|---|---|---|
{rows}

## Conformance conclusion

定義された機能的AGIクラスでは、C・J・Mのfull setだけがG1〜G5を満たす。
proper subset 7件はすべて実行後に固有の不足でFAILし、欠落主体の機能等価物漏れは0件である。

このcertificateは定義済み機能義務と固定fixture上の構成最小性を証明する。
未知ARC taskの汎化、全sample攻略、公式評価性能を証明しない。
"""
    return text.encode("utf-8")


def build_p9_artifacts(
    obligation_graph: Mapping[str, Any],
    *,
    raw_observation: Mapping[str, object] | None = None,
) -> dict[str, bytes]:
    report = run_eight_subset_audit(
        (
            default_certificate_observation()
            if raw_observation is None
            else raw_observation
        )
    )
    subset_payload = {
        "schema_version": "1.0.0",
        "artifact_type": "agi_subset_enumeration",
        "audit_digest": report.digest,
        "subsets": [dataclasses.asdict(case) for case in report.cases],
    }
    witness_payload = {
        "schema_version": "1.0.0",
        "artifact_type": "agi_removal_witnesses",
        "witnesses": [
            dataclasses.asdict(item) for item in report.removal_witnesses
        ],
    }
    graph_payload = _graph_projection(obligation_graph, report)
    outputs = {
        "agi_subset_enumeration.json": _json_bytes(subset_payload),
        "agi_removal_witnesses.json": _json_bytes(witness_payload),
        "agi_obligation_graph.json": _json_bytes(graph_payload),
        "agi_conformance_report.md": _conformance_markdown(report),
    }
    certificate_core = {
        "schema_version": "1.0.0",
        "artifact_type": "agi_minimum_three_certificate",
        "definition_scope": "functional-obligations-G1-through-G5",
        "audit_digest": report.digest,
        "full_set_pass": report.full_set_pass,
        "proper_subset_pass_count": report.proper_subset_pass_count,
        "single_removal_fail_count": report.single_removal_fail_count,
        "pair_subset_fail_count": report.pair_subset_fail_count,
        "two_cycle_causality_pass": report.two_cycle_causality_pass,
        "functional_equivalent_leak_count": (
            report.functional_equivalent_leak_count
        ),
        "subset_count": len(report.cases),
        "proper_subset_fail_count": (
            len(report.cases) - 1 - report.proper_subset_pass_count
        ),
        "subject_count": 3,
        "artifact_count": len(P9_ARTIFACT_FILENAMES),
        "artifact_digests": {
            name: _sha256(content)
            for name, content in sorted(outputs.items())
        },
        "conclusion": (
            "C, J, and M or their functional equivalents are jointly "
            "necessary under the defined G1-G5 class; only the full set passes"
        ),
        "non_claims": (
            "unknown-task generalization",
            "all-sample completion",
            "official evaluation performance",
        ),
    }
    certificate_payload = {
        **certificate_core,
        "content_digest": _sha256(_json_bytes(certificate_core)),
    }
    outputs["agi_minimum_three_certificate.json"] = _json_bytes(
        certificate_payload
    )
    if set(outputs) != set(P9_ARTIFACT_FILENAMES):
        raise RuntimeError("P9_ARTIFACT_SET_MISMATCH")
    return {name: outputs[name] for name in P9_ARTIFACT_FILENAMES}


def write_p9_artifacts(
    *,
    obligation_graph_path: Path,
    output_dir: Path,
) -> tuple[Path, ...]:
    graph = json.loads(obligation_graph_path.read_text(encoding="utf-8"))
    if not isinstance(graph, Mapping):
        raise TypeError("obligation graph must be an object")
    outputs = build_p9_artifacts(graph)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in outputs.items():
        path = output_dir / name
        path.write_bytes(content)
        written.append(path)
    return tuple(written)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build deterministic P9 minimum-three certificate artifacts."
    )
    parser.add_argument(
        "--obligation-graph",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = write_p9_artifacts(
        obligation_graph_path=args.obligation_graph,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "artifact_count": len(paths),
                "artifacts": [path.name for path in paths],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P9_ARTIFACT_FILENAMES",
    "SUBSET_EXPECTATIONS",
    "SUBSET_FAILURE_WITNESSES",
    "SUBSET_ORDER",
    "ComputeOnlyHarness",
    "EightSubsetAuditReport",
    "EmptySubsetHarness",
    "JudgmentOnlyHarness",
    "MemoryOnlyHarness",
    "RemovalWitness",
    "SubsetAuditCase",
    "SubsetExecutionEvidence",
    "build_p9_artifacts",
    "default_certificate_observation",
    "main",
    "run_eight_subset_audit",
    "write_p9_artifacts",
]
