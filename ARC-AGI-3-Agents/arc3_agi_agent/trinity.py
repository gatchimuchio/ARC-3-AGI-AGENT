"""P8 full-Trinity cycle, temporal causality, and factor-isolation audits."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .context import BoundedContextState
from .instruction_body import (
    InstructionBody,
    load_default_parametric_instruction_body,
    load_default_symbolic_instruction_body,
)
from .judgment import HDSFramePolicy
from .kernel import (
    HDSController,
    KernelResult,
    Layer0Components,
    Layer0Kernel,
    PureLLMCompute,
)
from .memory import MemorySnapshot, PassiveMemory
from .roles import (
    DeterministicCandidateSurface,
    DeterministicSuccessCriterion,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
)
from .schema import digest_object, forbidden_runtime_paths

_FULL_CYCLE_OPERATIONS = (
    "COMPUTE_COMMAND_ISSUED",
    "HYPOTHESES_AND_CANDIDATES_PROPOSED",
    "CLOSURE_DECISION",
    "AUTHORIZED_EXTERNAL_EMIT_EXECUTED",
    "EMISSION_RESULT_OBSERVED",
    "EMISSION_RESULT_JUDGED",
    "AUTHORIZED_MEMORY_WRITE_EXECUTED",
    "CYCLE_FINALIZED",
)
_C_OUTPUT_FIELDS = (
    "proposal",
    "hypotheses",
    "predictions",
    "candidates",
    "output_proposals",
)
_J_OUTPUT_FIELDS = (
    "judgment",
    "judgment_status",
    "selected_candidate",
    "authorization",
)


def _ordered_subsequence(
    required: Sequence[str],
    observed: Sequence[str],
) -> bool:
    position = 0
    for value in observed:
        if position < len(required) and value == required[position]:
            position += 1
    return position == len(required)


@dataclass(frozen=True, slots=True)
class ControlledTrinityProbe:
    """A compute/judge boundary with observation and context freshly fixed."""

    observation_digest: str
    context_digest: str
    instruction_body_format: str
    instruction_body_version: str
    instruction_body_digest: str
    frame_policy_digest: str
    memory_version: int
    memory_digest: str
    cited_memory_version: int
    cited_memory_digest: str
    proposal_digest: str
    hypotheses_digest: str
    predictions_digest: str
    candidates_digest: str
    output_proposals_digest: str
    judgment_digest: str
    judgment_status: str
    selected_candidate_id: str
    allow_memory_write: bool
    allow_external_emit: bool

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name, value in (
            ("OBSERVATION", self.observation_digest),
            ("CONTEXT", self.context_digest),
            ("P_FORMAT", self.instruction_body_format),
            ("P_VERSION", self.instruction_body_version),
            ("P_DIGEST", self.instruction_body_digest),
            ("J_POLICY", self.frame_policy_digest),
            ("M_DIGEST", self.memory_digest),
            ("PROPOSAL", self.proposal_digest),
            ("HYPOTHESES", self.hypotheses_digest),
            ("PREDICTIONS", self.predictions_digest),
            ("CANDIDATES", self.candidates_digest),
            ("OUTPUT_PROPOSALS", self.output_proposals_digest),
            ("JUDGMENT", self.judgment_digest),
            ("JUDGMENT_STATUS", self.judgment_status),
        ):
            if not value:
                failures.append(f"TRINITY_PROBE_{name}_MISSING")
        if (
            self.cited_memory_version != self.memory_version
            or self.cited_memory_digest != self.memory_digest
        ):
            failures.append("TRINITY_PROBE_MEMORY_CITATION_MISMATCH")
        if self.memory_version < 0:
            failures.append("TRINITY_PROBE_MEMORY_VERSION_INVALID")
        failures.extend(
            f"TRINITY_PROBE_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in forbidden_runtime_paths(
                {
                    "observation": self.observation_digest,
                    "context": self.context_digest,
                    "p": self.instruction_body_digest,
                    "j": self.frame_policy_digest,
                    "m": self.memory_digest,
                }
            )
        )
        return tuple(sorted(set(failures)))

    def input_factor_digest(self, factor: str) -> str:
        if factor == "P":
            return digest_object(
                (
                    self.instruction_body_format,
                    self.instruction_body_version,
                    self.instruction_body_digest,
                )
            )
        if factor == "J":
            return self.frame_policy_digest
        if factor == "M":
            return digest_object((self.memory_version, self.memory_digest))
        raise ValueError(f"unknown Trinity factor: {factor}")

    def output_digest(self, field_name: str) -> str:
        values = {
            "proposal": self.proposal_digest,
            "hypotheses": self.hypotheses_digest,
            "predictions": self.predictions_digest,
            "candidates": self.candidates_digest,
            "output_proposals": self.output_proposals_digest,
            "judgment": self.judgment_digest,
            "judgment_status": self.judgment_status,
            "selected_candidate": self.selected_candidate_id,
            "authorization": digest_object(
                (self.allow_memory_write, self.allow_external_emit)
            ),
        }
        return values[field_name]


@dataclass(frozen=True, slots=True)
class CausalIsolationCase:
    changed_factor: str
    baseline: ControlledTrinityProbe
    variant: ControlledTrinityProbe
    changed_inputs: tuple[str, ...]
    changed_outputs: tuple[str, ...]

    @property
    def passed(self) -> bool:
        if (
            self.changed_factor not in {"P", "J", "M"}
            or self.changed_inputs != (self.changed_factor,)
            or self.baseline.observation_digest
            != self.variant.observation_digest
            or self.baseline.context_digest != self.variant.context_digest
            or self.baseline.validate()
            or self.variant.validate()
        ):
            return False
        changed = set(self.changed_outputs)
        if self.changed_factor == "M":
            return "predictions" in changed
        if self.changed_factor == "P":
            return bool(
                changed & {"hypotheses", "predictions", "candidates"}
            )
        return (
            not changed & set(_C_OUTPUT_FIELDS)
            and bool(changed & set(_J_OUTPUT_FIELDS))
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class TrinityCycleEvidence:
    cycle_1_status: str
    cycle_2_status: str
    cycle_1_trace_operations: tuple[str, ...]
    cycle_2_trace_operations: tuple[str, ...]
    cycle_1_trace_digest: str
    cycle_2_trace_digest: str
    initial_memory_digest: str
    cycle_1_compute_memory_version: int
    cycle_1_compute_memory_digest: str
    cycle_1_after_memory_version: int
    cycle_1_after_memory_digest: str
    cycle_2_compute_memory_version: int
    cycle_2_compute_memory_digest: str
    cycle_2_after_memory_version: int
    cycle_2_after_memory_digest: str
    cycle_1_query_digest: str
    cycle_2_query_digest: str
    cycle_1_hypotheses_digest: str
    cycle_2_hypotheses_digest: str
    cycle_1_candidates_digest: str
    cycle_2_candidates_digest: str
    cycle_1_decision_digest: str
    cycle_2_decision_digest: str

    @property
    def behavior_changed(self) -> bool:
        return any(
            before != after
            for before, after in (
                (self.cycle_1_query_digest, self.cycle_2_query_digest),
                (
                    self.cycle_1_hypotheses_digest,
                    self.cycle_2_hypotheses_digest,
                ),
                (
                    self.cycle_1_candidates_digest,
                    self.cycle_2_candidates_digest,
                ),
                (
                    self.cycle_1_decision_digest,
                    self.cycle_2_decision_digest,
                ),
            )
        )

    @property
    def authority_order_passed(self) -> bool:
        return (
            self.cycle_1_status == "PASS"
            and self.cycle_2_status == "PASS"
            and _ordered_subsequence(
                _FULL_CYCLE_OPERATIONS,
                self.cycle_1_trace_operations,
            )
            and _ordered_subsequence(
                _FULL_CYCLE_OPERATIONS,
                self.cycle_2_trace_operations,
            )
            and self.cycle_1_compute_memory_version == 0
            and self.cycle_1_compute_memory_digest
            == self.initial_memory_digest
            and self.cycle_1_after_memory_version == 1
            and self.cycle_2_compute_memory_version
            == self.cycle_1_after_memory_version
            and self.cycle_2_compute_memory_digest
            == self.cycle_1_after_memory_digest
            and self.cycle_2_after_memory_version == 2
            and self.cycle_2_after_memory_digest
            != self.cycle_1_after_memory_digest
        )

    @property
    def passed(self) -> bool:
        return self.authority_order_passed and self.behavior_changed

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class TrinityTwoCycleReport:
    cycle_evidence: TrinityCycleEvidence
    m_only: CausalIsolationCase
    p_only: CausalIsolationCase
    j_only: CausalIsolationCase
    deterministic_probe_replay: bool
    hidden_global_state_observed: bool
    authority_violation_observed: bool

    @property
    def passed(self) -> bool:
        return (
            self.cycle_evidence.passed
            and self.m_only.changed_factor == "M"
            and self.m_only.passed
            and self.p_only.changed_factor == "P"
            and self.p_only.passed
            and self.j_only.changed_factor == "J"
            and self.j_only.passed
            and self.deterministic_probe_replay
            and not self.hidden_global_state_observed
            and not self.authority_violation_observed
        )

    @property
    def digest(self) -> str:
        return digest_object(self)


def _controlled_probe(
    raw_observation: Mapping[str, object],
    *,
    instruction_body: InstructionBody,
    frame_policy: HDSFramePolicy,
    memory: MemorySnapshot,
) -> ControlledTrinityProbe:
    observation = DeterministicSymbolSpace().encode(raw_observation)
    context_state = BoundedContextState()
    context = context_state.ingest(observation)
    hds = HDSController(frame_policy=frame_policy)
    compute = PureLLMCompute()
    world_model = DeterministicWorldModel()
    candidate_surface = DeterministicCandidateSurface()
    success_criterion = DeterministicSuccessCriterion()
    command = hds.issue_compute(observation, context, memory)
    proposal = compute.compute(
        command,
        hds,
        observation,
        context,
        memory,
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
    decision = hds.judge(
        command,
        proposal,
        closures,
        observation,
        conditioned,
    )
    standalone = hds.standalone_judgment(decision)
    return ControlledTrinityProbe(
        observation_digest=observation.frame_signature,
        context_digest=context.digest,
        instruction_body_format=instruction_body.format_id,
        instruction_body_version=instruction_body.body_version,
        instruction_body_digest=instruction_body.digest(),
        frame_policy_digest=frame_policy.digest,
        memory_version=memory.version,
        memory_digest=memory.digest,
        cited_memory_version=proposal.memory_view_version,
        cited_memory_digest=proposal.memory_view_digest,
        proposal_digest=proposal.digest,
        hypotheses_digest=digest_object(proposal.hypotheses),
        predictions_digest=digest_object(proposal.predictions),
        candidates_digest=digest_object(proposal.candidates),
        output_proposals_digest=digest_object(proposal.output_proposals),
        judgment_digest=standalone.digest,
        judgment_status=standalone.status,
        selected_candidate_id=standalone.selected_candidate_id or "",
        allow_memory_write=standalone.allow_memory_write,
        allow_external_emit=standalone.allow_external_emit,
    )


def _isolation_case(
    changed_factor: str,
    baseline: ControlledTrinityProbe,
    variant: ControlledTrinityProbe,
) -> CausalIsolationCase:
    changed_inputs = tuple(
        factor
        for factor in ("P", "J", "M")
        if baseline.input_factor_digest(factor)
        != variant.input_factor_digest(factor)
    )
    changed_outputs = tuple(
        field_name
        for field_name in (*_C_OUTPUT_FIELDS, *_J_OUTPUT_FIELDS)
        if baseline.output_digest(field_name)
        != variant.output_digest(field_name)
    )
    return CausalIsolationCase(
        changed_factor=changed_factor,
        baseline=baseline,
        variant=variant,
        changed_inputs=changed_inputs,
        changed_outputs=changed_outputs,
    )


def _cycle_evidence(
    *,
    initial: MemorySnapshot,
    cycle_1: KernelResult,
    after_cycle_1: MemorySnapshot,
    cycle_2: KernelResult,
    after_cycle_2: MemorySnapshot,
) -> TrinityCycleEvidence:
    return TrinityCycleEvidence(
        cycle_1_status=cycle_1.status,
        cycle_2_status=cycle_2.status,
        cycle_1_trace_operations=tuple(
            event.operation for event in cycle_1.trace
        ),
        cycle_2_trace_operations=tuple(
            event.operation for event in cycle_2.trace
        ),
        cycle_1_trace_digest=cycle_1.trace_digest,
        cycle_2_trace_digest=cycle_2.trace_digest,
        initial_memory_digest=initial.digest,
        cycle_1_compute_memory_version=cycle_1.compute_memory_version,
        cycle_1_compute_memory_digest=cycle_1.compute_memory_digest,
        cycle_1_after_memory_version=after_cycle_1.version,
        cycle_1_after_memory_digest=after_cycle_1.digest,
        cycle_2_compute_memory_version=cycle_2.compute_memory_version,
        cycle_2_compute_memory_digest=cycle_2.compute_memory_digest,
        cycle_2_after_memory_version=after_cycle_2.version,
        cycle_2_after_memory_digest=after_cycle_2.digest,
        cycle_1_query_digest=cycle_1.instruction_query_digest,
        cycle_2_query_digest=cycle_2.instruction_query_digest,
        cycle_1_hypotheses_digest=digest_object(cycle_1.hypotheses),
        cycle_2_hypotheses_digest=digest_object(cycle_2.hypotheses),
        cycle_1_candidates_digest=digest_object(cycle_1.candidates),
        cycle_2_candidates_digest=digest_object(cycle_2.candidates),
        cycle_1_decision_digest=digest_object(cycle_1.decision),
        cycle_2_decision_digest=digest_object(cycle_2.decision),
    )


def run_trinity_two_cycle_audit(
    raw_observation: Mapping[str, object],
) -> TrinityTwoCycleReport:
    """Run two full cycles and three one-factor controlled comparisons."""

    symbolic = load_default_symbolic_instruction_body()
    parametric = load_default_parametric_instruction_body()
    default_policy = HDSFramePolicy()
    stop_policy = replace(
        default_policy,
        policy_id="hds-frame-policy:controlled-stop-v1",
        purpose="stop-after-current-closed-frame",
        boundary="controlled-rendered-observation-only",
        additional_stopping_conditions=("CONTROLLED_J_STOP",),
    )
    if stop_policy.validate():
        raise ValueError("controlled J policy is invalid")

    components = Layer0Components(
        instruction_body=symbolic,
        hds=HDSController(frame_policy=default_policy),
        memory=PassiveMemory(),
    )
    memory_subject = components.memory
    assert memory_subject is not None
    kernel = Layer0Kernel(components)
    initial = memory_subject.view()
    cycle_1 = kernel.run_cycle(raw_observation)
    after_cycle_1 = memory_subject.view()
    cycle_2 = kernel.run_cycle(raw_observation)
    after_cycle_2 = memory_subject.view()

    empty_probe = _controlled_probe(
        raw_observation,
        instruction_body=symbolic,
        frame_policy=default_policy,
        memory=initial,
    )
    learned_probe = _controlled_probe(
        raw_observation,
        instruction_body=symbolic,
        frame_policy=default_policy,
        memory=after_cycle_1,
    )
    parametric_probe = _controlled_probe(
        raw_observation,
        instruction_body=parametric,
        frame_policy=default_policy,
        memory=after_cycle_1,
    )
    stopped_probe = _controlled_probe(
        raw_observation,
        instruction_body=symbolic,
        frame_policy=stop_policy,
        memory=after_cycle_1,
    )
    replay_probes = (
        _controlled_probe(
            raw_observation,
            instruction_body=symbolic,
            frame_policy=default_policy,
            memory=initial,
        ),
        _controlled_probe(
            raw_observation,
            instruction_body=symbolic,
            frame_policy=default_policy,
            memory=after_cycle_1,
        ),
        _controlled_probe(
            raw_observation,
            instruction_body=parametric,
            frame_policy=default_policy,
            memory=after_cycle_1,
        ),
        _controlled_probe(
            raw_observation,
            instruction_body=symbolic,
            frame_policy=stop_policy,
            memory=after_cycle_1,
        ),
    )
    m_only = _isolation_case("M", empty_probe, learned_probe)
    p_only = _isolation_case("P", learned_probe, parametric_probe)
    j_only = _isolation_case("J", learned_probe, stopped_probe)
    deterministic_replay = replay_probes == (
        empty_probe,
        learned_probe,
        parametric_probe,
        stopped_probe,
    )
    cycle_evidence = _cycle_evidence(
        initial=initial,
        cycle_1=cycle_1,
        after_cycle_1=after_cycle_1,
        cycle_2=cycle_2,
        after_cycle_2=after_cycle_2,
    )
    hidden_global_state_observed = (
        not deterministic_replay
        or m_only.changed_inputs != ("M",)
        or p_only.changed_inputs != ("P",)
        or j_only.changed_inputs != ("J",)
        or any(
            case.baseline.observation_digest
            != case.variant.observation_digest
            or case.baseline.context_digest != case.variant.context_digest
            for case in (m_only, p_only, j_only)
        )
    )
    report = TrinityTwoCycleReport(
        cycle_evidence=cycle_evidence,
        m_only=m_only,
        p_only=p_only,
        j_only=j_only,
        deterministic_probe_replay=deterministic_replay,
        hidden_global_state_observed=hidden_global_state_observed,
        authority_violation_observed=not cycle_evidence.authority_order_passed,
    )
    if not report.passed:
        raise RuntimeError("TRINITY_TWO_CYCLE_AUDIT_CONTRACT_FAILED")
    return report


__all__ = [
    "CausalIsolationCase",
    "ControlledTrinityProbe",
    "TrinityCycleEvidence",
    "TrinityTwoCycleReport",
    "run_trinity_two_cycle_audit",
]
