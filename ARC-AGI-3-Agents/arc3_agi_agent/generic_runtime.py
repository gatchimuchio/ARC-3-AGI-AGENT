"""Autonomous C/J/M/P loop for pre-official generic ARC3 evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .generic_compute import (
    ComputeAblation,
    GenericComputeSubject,
    GenericInstructionBody,
)
from .generic_hds import (
    ActionAuthorizationExecutor,
    GenericHDSJudgementSubject,
    HDSAblation,
    RollbackAuthorizationExecutor,
)
from .generic_memory import (
    MemoryMutationProposal,
    MemoryMutationReceipt,
    SemanticMemory,
    SemanticMemoryQuery,
    SemanticMemoryQueryResult,
    SemanticRecord,
    semantic_record,
)
from .generic_types import (
    GenericCandidate,
    GenericCycleTrace,
    GenericEnvironment,
    GenericObservation,
    GenericRunReport,
    OutcomeAttribution,
)
from .schema import digest_object

GENERIC_RUNTIME_VERSION = "arc3-generic-agi-runtime-v1"


@dataclass(frozen=True, slots=True)
class GenericRuntimeAblation:
    compute: ComputeAblation = field(default_factory=ComputeAblation)
    hds: HDSAblation = field(default_factory=HDSAblation)
    memory_read: bool = True
    memory_write: bool = True


@dataclass(frozen=True, slots=True)
class GenericRuntimeConfiguration:
    max_cycles: int = 256
    max_memory_updates_per_cycle: int = 8

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            isinstance(self.max_cycles, bool)
            or not isinstance(self.max_cycles, int)
            or not 1 <= self.max_cycles <= 100_000
        ):
            failures.append("GENERIC_RUNTIME_CYCLE_BUDGET_INVALID")
        if (
            isinstance(self.max_memory_updates_per_cycle, bool)
            or not isinstance(self.max_memory_updates_per_cycle, int)
            or not 1 <= self.max_memory_updates_per_cycle <= 64
        ):
            failures.append("GENERIC_RUNTIME_MEMORY_BUDGET_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class _EmptyMemoryReader:
    """Read-ablation view preserving only version synchronization."""

    version: int

    def query(self, query: SemanticMemoryQuery) -> SemanticMemoryQueryResult:
        return SemanticMemoryQueryResult(
            query_id=query.query_id,
            memory_version=self.version,
            records=(),
            selected_scores=(),
            archive_included=False,
            digest_value="semantic-memory-query:READ_ABLATION:"
            + digest_object((query, self.version)),
        )


def _selected_candidate(
    candidates: Sequence[GenericCandidate],
    candidate_id: str | None,
) -> GenericCandidate | None:
    if candidate_id is None:
        return None
    return next(
        (item for item in candidates if item.candidate_id == candidate_id),
        None,
    )


def _active_by_id(
    records: Sequence[SemanticRecord],
) -> dict[str, SemanticRecord]:
    return {item.memory_id: item for item in records}


def _counter(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _upsert_proposal(
    *,
    active: Mapping[str, SemanticRecord],
    record: SemanticRecord,
    evidence: Sequence[str],
    counter_evidence: Sequence[str],
    reason: str,
    operation_when_present: str = "REVISE",
) -> MemoryMutationProposal:
    normalized_counter_evidence = tuple(sorted(set(counter_evidence))) or (
        "no-counter-evidence-observed-in-current-bounded-scope",
    )
    return MemoryMutationProposal(
        operation=(
            operation_when_present if record.memory_id in active else "ADD"
        ),
        target_id=record.memory_id,
        record=record,
        evidence=tuple(sorted(set(evidence))),
        counter_evidence=normalized_counter_evidence,
        scope=("generic-runtime",),
        falsification_condition=record.falsification_condition,
        reason=reason,
    )


def outcome_memory_proposals(
    *,
    memory_records: Sequence[SemanticRecord],
    candidate: GenericCandidate,
    attribution: OutcomeAttribution,
    hypotheses: Sequence[object],
    decision_id: str,
) -> tuple[MemoryMutationProposal, ...]:
    """C-side update proposal generation; it does not authorize or apply writes."""

    active = _active_by_id(memory_records)
    semantic_key = candidate.descriptor.semantic_key
    procedure_id = "procedure:" + digest_object(semantic_key)[:24]
    old_procedure = active.get(procedure_id)
    old_payload = old_procedure.payload() if old_procedure is not None else {}
    success_count = _counter(old_payload, "success_count")
    hazard_count = _counter(old_payload, "hazard_count")
    no_effect_count = _counter(old_payload, "no_effect_count")
    visible_change_count = _counter(old_payload, "visible_change_count")
    if attribution.category == "PROGRESS":
        success_count += 1
    elif attribution.category == "FAILURE":
        hazard_count += 1
    elif attribution.category == "NO_EFFECT":
        no_effect_count += 1
    else:
        visible_change_count += 1
    procedure = semantic_record(
        memory_id=procedure_id,
        kind="PROCEDURE_CAPABILITY",
        statement=(
            "Observed action/role relation statistics for a legal action "
            "surface binding."
        ),
        semantic_tokens=(
            "goal:progress",
            semantic_key,
            f"outcome:{attribution.category.casefold()}",
        ),
        relations=(f"action-relation:{semantic_key}",),
        evidence=attribution.evidence,
        counter_evidence=(
            attribution.evidence
            if attribution.category in {"FAILURE", "NO_EFFECT"}
            else ()
        ),
        falsification_condition=(
            "future repeated effects contradict accumulated action statistics"
        ),
        payload={
            "success_count": success_count,
            "hazard_count": hazard_count,
            "no_effect_count": no_effect_count,
            "visible_change_count": visible_change_count,
        },
    )
    proposals: list[MemoryMutationProposal] = [
        _upsert_proposal(
            active=active,
            record=procedure,
            evidence=attribution.evidence,
            counter_evidence=procedure.counter_evidence,
            reason="attribute authorized environment outcome to action relation",
        )
    ]

    model_values = tuple(hypotheses)
    baseline = next(
        (
            item
            for item in model_values
            if getattr(item, "model_type", "") == "baseline"
        ),
        None,
    )
    counter = next(
        (
            item
            for item in model_values
            if getattr(item, "model_type", "")
            in {"counter_hypothesis", "null_model"}
        ),
        None,
    )
    if baseline is not None:
        baseline_record = semantic_record(
            memory_id="current-hypothesis",
            kind="HYPOTHESIS",
            statement=str(getattr(baseline, "statement", "current baseline")),
            semantic_tokens=("goal:progress", semantic_key, "model:baseline"),
            evidence=attribution.evidence,
            counter_evidence=(
                attribution.evidence
                if attribution.category in {"FAILURE", "NO_EFFECT"}
                else ()
            ),
            falsification_condition=(
                "the selected relation fails bounded repeated probes"
            ),
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=baseline_record,
                evidence=attribution.evidence,
                counter_evidence=baseline_record.counter_evidence,
                reason="revise current hypothesis from attributed outcome",
                operation_when_present="REPLACE",
            )
        )
    if counter is not None:
        counter_record = semantic_record(
            memory_id="current-counter-hypothesis",
            kind="COUNTER_HYPOTHESIS",
            statement=str(
                getattr(counter, "statement", "current counter hypothesis")
            ),
            semantic_tokens=("goal:progress", semantic_key, "model:counter"),
            evidence=attribution.evidence,
            counter_evidence=(
                attribution.evidence
                if attribution.category == "PROGRESS"
                else ()
            ),
            falsification_condition=(
                "safe reproducible progress defeats the counter hypothesis"
            ),
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=counter_record,
                evidence=attribution.evidence,
                counter_evidence=counter_record.counter_evidence,
                reason="retain a live counter hypothesis for HDS comparison",
                operation_when_present="REPLACE",
            )
        )
    rationale = semantic_record(
        memory_id="current-decision-rationale",
        kind="DECISION_RATIONALE",
        statement=(
            f"HDS decision {decision_id} authorized a bounded action and "
            f"observed {attribution.category}."
        ),
        semantic_tokens=(
            "goal:progress",
            semantic_key,
            f"decision:{attribution.category.casefold()}",
        ),
        evidence=attribution.evidence,
        counter_evidence=(),
        falsification_condition="decision provenance or attribution is invalid",
    )
    proposals.append(
        _upsert_proposal(
            active=active,
            record=rationale,
            evidence=attribution.evidence,
            counter_evidence=(),
            reason="retain current HDS decision rationale",
            operation_when_present="REPLACE",
        )
    )
    world_model = semantic_record(
        memory_id="current-world-model",
        kind="WORLD_MODEL",
        statement=(
            "Current relational action-effect model is conditioned on the "
            "observed role topology and remains falsifiable."
        ),
        semantic_tokens=(
            "goal:progress",
            semantic_key,
            "model:relational-transition",
        ),
        relations=(f"action-relation:{semantic_key}",),
        evidence=attribution.evidence,
        counter_evidence=(
            attribution.evidence
            if attribution.category in {"FAILURE", "NO_EFFECT"}
            else ()
        ),
        falsification_condition=(
            "future action-effect evidence contradicts the relational transition"
        ),
    )
    proposals.append(
        _upsert_proposal(
            active=active,
            record=world_model,
            evidence=attribution.evidence,
            counter_evidence=world_model.counter_evidence,
            reason="revise the active relational world model",
            operation_when_present="REPLACE",
        )
    )
    if attribution.category == "PROGRESS":
        contradiction = semantic_record(
            memory_id="current-contradiction",
            kind="CONTRADICTION",
            statement=(
                "Observed progress contradicts the active null/no-effect "
                "explanation for this action relation."
            ),
            semantic_tokens=(
                "goal:progress",
                semantic_key,
                "contradiction:null-model",
            ),
            evidence=attribution.evidence,
            counter_evidence=(),
            falsification_condition=(
                "progress attribution is later classified as observation error"
            ),
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=contradiction,
                evidence=attribution.evidence,
                counter_evidence=(),
                reason="retain explicit model contradiction",
                operation_when_present="REPLACE",
            )
        )
    if attribution.category == "NO_EFFECT":
        open_term = semantic_record(
            memory_id="current-open-term",
            kind="OPEN_TERM",
            statement=(
                "The causal meaning of the no-effect action relation remains open."
            ),
            semantic_tokens=("goal:progress", semantic_key, "open:no-effect"),
            evidence=attribution.evidence,
            counter_evidence=(),
            falsification_condition=(
                "a later bounded probe reveals a reproducible effect"
            ),
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=open_term,
                evidence=attribution.evidence,
                counter_evidence=(),
                reason="retain unresolved no-effect causal term",
                operation_when_present="REPLACE",
            )
        )
    if attribution.category == "FAILURE":
        failure = semantic_record(
            memory_id="failure:" + digest_object(semantic_key)[:24],
            kind="FAILURE_SIGNATURE",
            statement=(
                "This action/role relation produced GAME_OVER under the "
                "observed precondition."
            ),
            semantic_tokens=(
                "goal:progress",
                semantic_key,
                "hazard:game-over",
            ),
            evidence=attribution.evidence,
            counter_evidence=(),
            falsification_condition=(
                "the same relation is later shown safe under a distinguished scope"
            ),
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=failure,
                evidence=attribution.evidence,
                counter_evidence=(),
                reason="compile GAME_OVER into a reusable failure signature",
            )
        )
        rollback = semantic_record(
            memory_id="current-rollback-pointer",
            kind="ROLLBACK_POINTER",
            statement="Rollback to the last safe pre-action observation.",
            semantic_tokens=("boundary:reversible", semantic_key),
            evidence=attribution.evidence,
            counter_evidence=(),
            falsification_condition="rollback target is not a safe level state",
            payload={"failed_observation": attribution.after_signature},
        )
        proposals.append(
            _upsert_proposal(
                active=active,
                record=rollback,
                evidence=attribution.evidence,
                counter_evidence=(),
                reason="retain HDS rollback pointer after failure",
                operation_when_present="REPLACE",
            )
        )
    return tuple(proposals)


@dataclass(slots=True)
class GenericSideEffectExecutor:
    """C-side mechanical executor for HDS-authorized effects only."""

    authority_token: object = field(repr=False)
    action_executor: ActionAuthorizationExecutor = field(init=False)
    rollback_executor: RollbackAuthorizationExecutor = field(init=False)

    def __post_init__(self) -> None:
        self.action_executor = ActionAuthorizationExecutor(self.authority_token)
        self.rollback_executor = RollbackAuthorizationExecutor(
            self.authority_token
        )

    def execute_memory(
        self,
        memory: SemanticMemory,
        proposal: MemoryMutationProposal,
        authorization: object,
    ) -> MemoryMutationReceipt:
        from .generic_memory import MemoryAuthorization

        if not isinstance(authorization, MemoryAuthorization):
            raise TypeError("GENERIC_MEMORY_AUTHORIZATION_REQUIRED")
        return memory.apply_authorized(proposal, authorization)


@dataclass(slots=True)
class GenericAGIRuntime:
    """Active generic path. It never imports or falls back to S5/Teacher."""

    environment: GenericEnvironment
    instruction_body: GenericInstructionBody
    configuration: GenericRuntimeConfiguration = field(
        default_factory=GenericRuntimeConfiguration
    )
    hds_configuration: object | None = field(default=None, repr=False)
    initial_memory_records: tuple[SemanticRecord, ...] = field(
        default=(),
        repr=False,
    )
    authority_token: object = field(default_factory=object, init=False, repr=False)
    memory: SemanticMemory = field(init=False)
    compute: GenericComputeSubject = field(init=False)
    hds: GenericHDSJudgementSubject = field(init=False)
    executor: GenericSideEffectExecutor = field(init=False)

    def __post_init__(self) -> None:
        from .generic_hds import HDSConfiguration

        failures = self.configuration.validate()
        if failures:
            raise ValueError(";".join(failures))
        body_failures = self.instruction_body.validate()
        if body_failures:
            raise ValueError(";".join(body_failures))
        selected_hds = (
            self.hds_configuration
            if isinstance(self.hds_configuration, HDSConfiguration)
            else HDSConfiguration(
                resource_budget=self.configuration.max_cycles,
                stop_after_no_progress=self.configuration.max_cycles,
            )
        )
        self.memory = SemanticMemory(self.authority_token)
        self.memory.seed_sealed(
            (
                semantic_record(
                    memory_id="constitution:authority",
                    kind="PURPOSE_BOUNDARY",
                    statement=(
                        "HDS alone commits actions and active-memory updates; "
                        "models are not the world."
                    ),
                    semantic_tokens=(
                        "boundary:authority",
                        "boundary:reversible",
                        "goal:progress",
                    ),
                    evidence=("AGI_Trinity_Blueprint_v0_1",),
                    falsification_condition=(
                        "a non-HDS path can commit an action or active-memory write"
                    ),
                    state="SEALED",
                ),
            )
        )
        self.memory.seed_active(self.initial_memory_records)
        self.compute = GenericComputeSubject(self.authority_token)
        self.hds = GenericHDSJudgementSubject(
            authority_token=self.authority_token,
            configuration=selected_hds,
            run_id="generic-runtime:" + digest_object(
                {
                    "p": self.instruction_body.digest(),
                    "budget": self.configuration.max_cycles,
                }
            )[:20],
        )
        self.executor = GenericSideEffectExecutor(self.authority_token)

    def _cycle_trace(
        self,
        *,
        cycle_index: int,
        observation: GenericObservation,
        frame: object,
        compute_result: object,
        decision: object,
        selected_candidate: GenericCandidate | None,
        result_observation: GenericObservation | None,
        attribution: OutcomeAttribution | None,
        memory_query_digest: str,
        memory_update_digests: Sequence[str],
        authority_events: Sequence[str],
        failure_signatures: Sequence[str],
    ) -> GenericCycleTrace:
        from .generic_types import (
            GenericComputeResult,
            GenericHDSDecision,
            GenericHDSFrame,
        )

        if not isinstance(frame, GenericHDSFrame):
            raise TypeError("GENERIC_TRACE_FRAME_REQUIRED")
        if not isinstance(compute_result, GenericComputeResult):
            raise TypeError("GENERIC_TRACE_COMPUTE_REQUIRED")
        if not isinstance(decision, GenericHDSDecision):
            raise TypeError("GENERIC_TRACE_DECISION_REQUIRED")
        update_digest_tuple = tuple(memory_update_digests)
        authority_event_tuple = tuple(authority_events)
        failure_signature_tuple = tuple(failure_signatures)
        trace_digest = "generic-cycle-trace:" + digest_object(
            {
                "cycle_index": cycle_index,
                "observation": observation,
                "frame": frame,
                "compute_result": compute_result,
                "decision": decision,
                "selected_candidate": selected_candidate,
                "result_observation": result_observation,
                "attribution": attribution,
                "memory_query_digest": memory_query_digest,
                "memory_update_digests": update_digest_tuple,
                "authority_events": authority_event_tuple,
                "failure_signatures": failure_signature_tuple,
            }
        )
        return GenericCycleTrace(
            cycle_index=cycle_index,
            observation=observation,
            frame=frame,
            compute_result=compute_result,
            decision=decision,
            selected_candidate=selected_candidate,
            result_observation=result_observation,
            attribution=attribution,
            memory_query_digest=memory_query_digest,
            memory_update_digests=update_digest_tuple,
            authority_events=authority_event_tuple,
            failure_signatures=failure_signature_tuple,
            trace_digest=trace_digest,
        )

    def run(
        self,
        *,
        ablation: GenericRuntimeAblation | None = None,
    ) -> GenericRunReport:
        selected_ablation = ablation or GenericRuntimeAblation()
        observation = self.environment.observe()
        observation_failures = observation.validate()
        if observation_failures:
            raise ValueError(";".join(observation_failures))
        initial_digest = observation.digest()
        initial_memory_version = self.memory.version
        traces: list[GenericCycleTrace] = []
        failures: list[str] = []
        actions_executed = 0
        stop_reason = "RESOURCE_LIMIT"
        highest_progress = observation.progress_count

        for cycle_index in range(self.configuration.max_cycles):
            remaining = self.configuration.max_cycles - cycle_index
            memory_view = self.memory.view()
            frame = self.hds.frame(
                observation,
                memory_view,
                remaining_budget=remaining,
                ablation=selected_ablation.hds,
            )
            command = self.hds.issue_compute(frame, observation, memory_view)
            memory_reader: object = (
                self.memory
                if selected_ablation.memory_read
                else _EmptyMemoryReader(self.memory.version)
            )
            if not hasattr(memory_reader, "query"):
                raise TypeError("GENERIC_MEMORY_READER_INVALID")
            compute_result = self.compute.compute(
                command=command,
                observation=observation,
                memory=memory_reader,  # type: ignore[arg-type]
                instruction_body=self.instruction_body,
                ablation=selected_ablation.compute,
            )
            decision = self.hds.judge(
                frame=frame,
                observation=observation,
                result=compute_result,
                ablation=selected_ablation.hds,
            )
            selected = _selected_candidate(
                compute_result.candidates,
                decision.selected_candidate_id,
            )
            retrieval_stage = next(
                item
                for item in compute_result.stages
                if item.stage == "retrieve"
            )
            authority_events = [command.command_id, decision.decision_id]
            cycle_failures: list[str] = []
            if decision.operation_state in {"STOP", "SUSPEND"}:
                stop_reason = (
                    decision.stop_condition
                    if decision.operation_state == "STOP"
                    else "HDS_SUSPEND"
                )
                if decision.operation_state == "SUSPEND":
                    cycle_failures.append("HDS_UNCLOSED_SUSPEND")
                traces.append(
                    self._cycle_trace(
                        cycle_index=cycle_index,
                        observation=observation,
                        frame=frame,
                        compute_result=compute_result,
                        decision=decision,
                        selected_candidate=selected,
                        result_observation=None,
                        attribution=None,
                        memory_query_digest=retrieval_stage.output_digest,
                        memory_update_digests=(),
                        authority_events=authority_events,
                        failure_signatures=cycle_failures,
                    )
                )
                failures.extend(cycle_failures)
                break
            if selected is None:
                raise RuntimeError("GENERIC_HDS_SELECTED_CANDIDATE_MISSING")
            authorization = self.hds.authorize_action(
                decision, selected, observation
            )
            authority_events.append(authorization.authorization_id)
            action_id, payload = self.executor.action_executor.consume(
                authorization,
                decision,
                selected,
                observation,
            )
            request_id = "generic-action-request:" + digest_object(
                {
                    "authorization": authorization.authorization_id,
                    "cycle": cycle_index,
                }
            )[:24]
            try:
                result_observation = self.environment.step(
                    action_id,
                    payload=payload,
                    request_id=request_id,
                )
            except Exception as error:
                failure = "GENERIC_ENVIRONMENT_EXECUTION_FAILURE:" + type(
                    error
                ).__name__
                failures.append(failure)
                cycle_failures.append(failure)
                stop_reason = "SYSTEM_FAULT"
                traces.append(
                    self._cycle_trace(
                        cycle_index=cycle_index,
                        observation=observation,
                        frame=frame,
                        compute_result=compute_result,
                        decision=decision,
                        selected_candidate=selected,
                        result_observation=None,
                        attribution=None,
                        memory_query_digest=retrieval_stage.output_digest,
                        memory_update_digests=(),
                        authority_events=authority_events,
                        failure_signatures=cycle_failures,
                    )
                )
                break
            result_failures = result_observation.validate()
            if result_failures:
                raise ValueError(";".join(result_failures))
            actions_executed += 1
            highest_progress = max(
                highest_progress, result_observation.progress_count
            )
            attribution = self.hds.attribute(
                before=observation,
                after=result_observation,
                candidate=selected,
            )
            memory_update_digests: list[str] = []
            if (
                selected_ablation.memory_write
                and decision.memory_update_authorized
            ):
                proposals = outcome_memory_proposals(
                    memory_records=self.memory.view().active,
                    candidate=selected,
                    attribution=attribution,
                    hypotheses=compute_result.hypotheses,
                    decision_id=decision.decision_id,
                )
                for proposal in proposals[
                    : self.configuration.max_memory_updates_per_cycle
                ]:
                    memory_authorization = self.hds.authorize_memory(
                        decision,
                        proposal,
                        memory_version=self.memory.version,
                    )
                    authority_events.append(
                        memory_authorization.authorization_id
                    )
                    receipt = self.executor.execute_memory(
                        self.memory,
                        proposal,
                        memory_authorization,
                    )
                    memory_update_digests.append(receipt.event_digest)
            if attribution.category == "FAILURE":
                cycle_failures.append("GENERIC_GAME_OVER_OBSERVED")
                rollback = self.hds.authorize_rollback(
                    decision,
                    attribution,
                    result_observation,
                )
                authority_events.append(rollback.authorization_id)
                self.executor.rollback_executor.consume(
                    rollback,
                    decision,
                    attribution,
                    result_observation,
                )
                observation_after_cycle = self.environment.reset_level(
                    request_id="generic-rollback-request:"
                    + digest_object(rollback.authorization_id)[:24]
                )
            else:
                observation_after_cycle = result_observation
            self.hds.observe_outcome(attribution)
            traces.append(
                self._cycle_trace(
                    cycle_index=cycle_index,
                    observation=observation,
                    frame=frame,
                    compute_result=compute_result,
                    decision=decision,
                    selected_candidate=selected,
                    result_observation=result_observation,
                    attribution=attribution,
                    memory_query_digest=retrieval_stage.output_digest,
                    memory_update_digests=memory_update_digests,
                    authority_events=authority_events,
                    failure_signatures=cycle_failures,
                )
            )
            failures.extend(cycle_failures)
            observation = observation_after_cycle
            if result_observation.terminal_state == "WIN":
                stop_reason = "GOAL_REACHED"
                break
        else:
            failures.append("GENERIC_RESOURCE_LIMIT")

        return GenericRunReport(
            runtime_version=GENERIC_RUNTIME_VERSION,
            instruction_body_version=self.instruction_body.body_version(),
            initial_observation_digest=initial_digest,
            final_observation_digest=observation.digest(),
            final_state=observation.terminal_state,
            progress_count=highest_progress,
            actions_executed=actions_executed,
            cycles=tuple(traces),
            stop_reason=stop_reason,
            memory_initial_version=initial_memory_version,
            memory_final_version=self.memory.version,
            no_fallback_used=True,
            runtime_identity_received=False,
            failure_signatures=tuple(sorted(set(failures))),
        )


__all__ = [
    "GENERIC_RUNTIME_VERSION",
    "GenericAGIRuntime",
    "GenericRuntimeAblation",
    "GenericRuntimeConfiguration",
    "GenericSideEffectExecutor",
    "outcome_memory_proposals",
]
