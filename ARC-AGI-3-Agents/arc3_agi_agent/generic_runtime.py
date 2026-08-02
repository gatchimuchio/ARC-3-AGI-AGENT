"""Autonomous C/J/M/P loop for pre-official generic ARC3 evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from .causal_record import (
    causal_record,
    causal_record_from_semantic,
    causal_record_id,
)
from .decision_context import DecisionContext, DecisionObservation
from .evidence_policy import EvidencePolicy, evidence_group
from .generic_compute import (
    ComputeAblation,
    GenericComputeSubject,
    GenericInstructionBody,
)
from .generic_hds import GenericHDSJudgementSubject, HDSAblation
from .generic_memory import (
    MemoryMutationProposal,
    SemanticMemory,
    SemanticMemoryQuery,
    SemanticMemoryQueryResult,
    SemanticRecord,
)
from .generic_session import (
    CognitiveSession,
    EpisodeHandle,
    GenericSideEffectExecutor,
)
from .generic_types import (
    ActionEffectRecord,
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
    rollback: bool = True

    def validate(self) -> tuple[str, ...]:
        return (
            ()
            if all(
                isinstance(item, bool)
                for item in (
                    self.memory_read,
                    self.memory_write,
                    self.rollback,
                )
            )
            else ("GENERIC_RUNTIME_ABLATION_FLAG_INVALID",)
        )


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


class GenericCycleTraceSink(Protocol):
    def append(self, trace: GenericCycleTrace) -> None: ...


@dataclass(slots=True)
class _TraceCollector:
    retain_cycle_objects: bool
    sink: GenericCycleTraceSink | None
    items: list[GenericCycleTrace] = field(default_factory=list)
    digests: list[str] = field(default_factory=list)

    def append(self, trace: GenericCycleTrace) -> None:
        self.digests.append(trace.trace_digest)
        if self.sink is not None:
            self.sink.append(trace)
        if self.retain_cycle_objects:
            self.items.append(trace)


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


def _rendered_changed(
    before: GenericObservation,
    after: GenericObservation,
) -> bool:
    """Return the persistent rendered effect consumed by bounded policy M.

    ``visible_effects`` also describes transient animation and interface
    classifications.  Those facts remain available to representation and HDS,
    but the compiled product P was trained on equality of consecutive
    action-complete renders.  Letting a semantic effect label override that
    equality changes the policy feature alphabet and causes closed-loop drift.
    """

    if before.rendered_layers and after.rendered_layers:
        return before.composited_view != after.composited_view
    return before.signature != after.signature


def _action_effect_record(
    *,
    action_id: int,
    payload: dict[str, int],
    before: GenericObservation,
    after: GenericObservation,
    compatibility_reset: bool = False,
    plan_id: str = "",
    outcome_category: str = "",
    hypothesis_refs: tuple[str, ...] = (),
) -> ActionEffectRecord:
    target_palette = 0
    if action_id == 6:
        if set(payload) != {"x", "y"}:
            raise ValueError("GENERIC_POINTER_HISTORY_PAYLOAD_INVALID")
        if not before.rendered_layers:
            raise ValueError("GENERIC_POINTER_HISTORY_RENDER_REQUIRED")
        x = payload["x"]
        y = payload["y"]
        matrix = before.composited_view
        if not (0 <= y < len(matrix) and 0 <= x < len(matrix[y])):
            raise ValueError("GENERIC_POINTER_HISTORY_TARGET_INVALID")
        target_palette = matrix[y][x]
    record = ActionEffectRecord(
        action_id=action_id,
        payload_items=tuple(sorted(payload.items())),
        visible_change=_rendered_changed(before, after),
        compatibility_reset=compatibility_reset,
        target_palette=target_palette,
        plan_id=plan_id,
        outcome_category=outcome_category,
        hypothesis_refs=hypothesis_refs,
    )
    failures = record.validate()
    if failures:
        raise ValueError(";".join(failures))
    return record


def _semantic_causal_memory_required(
    instruction_body: GenericInstructionBody,
    observation: GenericObservation,
) -> bool:
    selector = getattr(
        instruction_body,
        "semantic_causal_memory_required",
        None,
    )
    if selector is None:
        return True
    if not callable(selector):
        raise TypeError("GENERIC_P_SEMANTIC_MEMORY_SELECTOR_INVALID")
    result = selector(observation)
    if not isinstance(result, bool):
        raise TypeError("GENERIC_P_SEMANTIC_MEMORY_SELECTOR_RESULT_INVALID")
    return result


def _explicit_rollback_cycle_required(
    instruction_body: GenericInstructionBody,
    observation: GenericObservation,
) -> bool:
    selector = getattr(
        instruction_body,
        "explicit_rollback_cycle_required",
        None,
    )
    if selector is None:
        return False
    if not callable(selector):
        raise TypeError("GENERIC_P_ROLLBACK_CYCLE_SELECTOR_INVALID")
    result = selector(observation)
    if not isinstance(result, bool):
        raise TypeError("GENERIC_P_ROLLBACK_CYCLE_SELECTOR_RESULT_INVALID")
    return result


def outcome_memory_proposals(
    *,
    memory_records: Sequence[SemanticRecord],
    candidate: GenericCandidate,
    attribution: OutcomeAttribution,
    hypotheses: Sequence[object],
    decision_id: str,
    evidence_episode_nonce: str = "",
    cycle_index: int = 0,
    evidence_policy: EvidencePolicy | None = None,
) -> tuple[MemoryMutationProposal, ...]:
    """Compile one attributed transition into a typed causal M proposal."""

    del hypotheses
    selected_policy = evidence_policy or EvidencePolicy()
    if not evidence_episode_nonce:
        evidence_episode_nonce = "compatibility-episode:" + digest_object(decision_id)
    if cycle_index < 0:
        raise ValueError("CAUSAL_MEMORY_CYCLE_INVALID")
    active = {item.memory_id: item for item in memory_records}
    semantic_key = candidate.descriptor.semantic_key
    binding_key = candidate.evidence_binding_key
    kind = "HAZARD_MODEL" if attribution.category == "FAILURE" else "ACTION_EFFECT"
    record_id = causal_record_id(
        kind=kind,
        binding_key=binding_key,
        scope_class="EPISODE_OVERLAY",
    )
    prior_semantic = active.get(record_id)
    prior = (
        causal_record_from_semantic(
            prior_semantic,
            policy=selected_policy,
        )
        if prior_semantic is not None
        else None
    )
    outcome = {
        "PROGRESS": "SUPPORT",
        "FAILURE": "HAZARD",
        "NO_EFFECT": "NO_EFFECT",
        "VISIBLE_CHANGE": "SUPPORT",
    }[attribution.category]
    delay_steps = 1 if "DELAYED_EFFECT" in attribution.visible_effects else 0
    group = evidence_group(
        outcome=outcome,
        normalized_before_pattern_digest=(binding_key.normalized_state_pattern_digest),
        action_relation_digest=binding_key.action_relation_digest,
        normalized_after_effect_digest="normalized-effect:"
        + digest_object(
            {
                "category": attribution.category,
                "visible_effects": attribution.visible_effects,
                "progress_delta": attribution.progress_delta,
                "terminal_state": attribution.terminal_state,
            }
        ),
        delay_min_steps=delay_steps,
        delay_max_steps=delay_steps,
        episode_nonce=evidence_episode_nonce,
        event_ids=attribution.evidence,
    )
    prior_groups = prior.evidence_groups if prior is not None else ()
    group_is_new = group.group_id not in {item.group_id for item in prior_groups}
    prior_payload = prior.payload() if prior is not None else {}

    def prior_count(name: str) -> int:
        value = prior_payload.get(name, 0)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value)
        return 0

    progress_count = prior_count("progress_count")
    visible_change_count = prior_count("visible_change_count")
    if group_is_new and attribution.category == "PROGRESS":
        progress_count += 1
    if group_is_new and attribution.category == "VISIBLE_CHANGE":
        visible_change_count += 1
    prior_effects_value = prior_payload.get("learned_effects", ())
    prior_learned_effects = (
        {str(item) for item in prior_effects_value if isinstance(item, str)}
        if isinstance(prior_effects_value, (tuple, list))
        else set()
    )
    learned_effects = tuple(
        sorted(
            prior_learned_effects
            | {
                item
                for item in attribution.visible_effects
                if item.startswith("STRUCTURAL_")
            }
        )
    )
    typed = causal_record(
        kind=kind,
        binding_key=binding_key,
        scope_class="EPISODE_OVERLAY",
        statement=(
            "Observed normalized action relation caused a bounded rendered "
            "effect under an explicit precondition."
        ),
        semantic_tokens=(
            "goal:progress",
            semantic_key,
            f"outcome:{attribution.category.casefold()}",
        ),
        relations=(f"action-relation:{semantic_key}",),
        applicability_predicates=(
            "current-legal-action",
            "normalized-role-topology",
            "rendered-observation-only",
        ),
        evidence_groups=(*prior_groups, group),
        falsification_condition=(
            "independent causal evidence contradicts the predicted effect "
            "under the same normalized precondition"
        ),
        policy=selected_policy,
        created_version=prior.created_version if prior is not None else 0,
        updated_version=prior.updated_version if prior is not None else 0,
        rollback_pointer=prior.rollback_pointer if prior is not None else 0,
        usage_count=prior.usage_count if prior is not None else 0,
        last_verified_cycle=cycle_index,
        payload={
            "progress_count": progress_count,
            "visible_change_count": visible_change_count,
            "learned_effects": learned_effects,
            "decision_provenance_digest": digest_object(decision_id),
        },
    )
    semantic = typed.to_semantic_record()
    return (
        MemoryMutationProposal(
            operation="REVISE" if prior_semantic is not None else "ADD",
            target_id=semantic.memory_id,
            record=semantic,
            evidence=semantic.evidence,
            counter_evidence=semantic.counter_evidence
            or ("no-counter-evidence-in-current-bounded-scope",),
            scope=("EPISODE_OVERLAY",),
            falsification_condition=semantic.falsification_condition,
            reason="attribute authorized outcome to typed causal memory",
        ),
    )


@dataclass(slots=True)
class GenericAGIRuntime:
    """Active generic path. It never imports or falls back to S5/Teacher."""

    environment: GenericEnvironment
    session: CognitiveSession
    episode_handle: EpisodeHandle = field(repr=False)
    retain_cycle_objects: bool = True
    trace_sink: GenericCycleTraceSink | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.retain_cycle_objects, bool) or (
            not self.retain_cycle_objects and self.trace_sink is None
        ):
            raise ValueError("GENERIC_RUNTIME_TRACE_RETENTION_INVALID")
        self.session.require_episode(self.episode_handle)
        failures = self.configuration.validate()
        if failures:
            raise ValueError(";".join(failures))
        body_failures = self.instruction_body.validate()
        if body_failures:
            raise ValueError(";".join(body_failures))
        ownership_failures = self.session.state_owner_violations()
        if ownership_failures:
            raise RuntimeError(";".join(ownership_failures))

    @property
    def configuration(self) -> GenericRuntimeConfiguration:
        resources = self.session.resource_contract
        return GenericRuntimeConfiguration(
            max_cycles=resources.action_budget_per_episode,
            max_memory_updates_per_cycle=(resources.max_memory_updates_per_cycle),
        )

    @property
    def instruction_body(self) -> GenericInstructionBody:
        return self.session.instruction_body

    @property
    def authority_token(self) -> object:
        return self.session.authority.live_token

    @property
    def memory(self) -> SemanticMemory:
        return self.session.memory

    @property
    def compute(self) -> GenericComputeSubject:
        return self.session.compute

    @property
    def hds(self) -> GenericHDSJudgementSubject:
        return self.session.hds

    @property
    def executor(self) -> GenericSideEffectExecutor:
        return self.session.executor

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
        decision_context_digest: str,
        experience_event_digests: Sequence[str] = (),
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
        experience_event_digest_tuple = tuple(experience_event_digests)
        runtime_identity_digest = self.session.runtime_identity.digest()
        session_lineage_digest = self.session.lineage_digest
        trace_digest = "generic-cycle-trace:" + digest_object(
            {
                "cycle_index": cycle_index,
                "observation": observation.digest(),
                "frame": "hds-frame:" + digest_object(frame),
                "compute_result": compute_result.digest(),
                "decision": "hds-decision:" + digest_object(decision),
                "selected_candidate": (
                    "generic-candidate:" + digest_object(selected_candidate)
                    if selected_candidate is not None
                    else None
                ),
                "result_observation": (
                    result_observation.digest()
                    if result_observation is not None
                    else None
                ),
                "attribution": (
                    "outcome-attribution:" + digest_object(attribution)
                    if attribution is not None
                    else None
                ),
                "memory_query_digest": memory_query_digest,
                "memory_update_digests": update_digest_tuple,
                "authority_events": authority_event_tuple,
                "failure_signatures": failure_signature_tuple,
                "runtime_identity_digest": runtime_identity_digest,
                "session_lineage_digest": session_lineage_digest,
                "decision_context_digest": decision_context_digest,
                "experience_event_digests": (experience_event_digest_tuple),
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
            runtime_identity_digest=runtime_identity_digest,
            session_lineage_digest=session_lineage_digest,
            decision_context_digest=decision_context_digest,
            experience_event_digests=experience_event_digest_tuple,
        )

    def run(
        self,
        *,
        ablation: GenericRuntimeAblation | None = None,
    ) -> GenericRunReport:
        self.session.require_episode(self.episode_handle)
        self.session.p_bundle.require_unchanged()
        selected_ablation = ablation or GenericRuntimeAblation()
        ablation_failures = selected_ablation.validate()
        if ablation_failures:
            raise ValueError(";".join(ablation_failures))
        observation = self.environment.observe()
        observation_failures = observation.validate()
        if observation_failures:
            raise ValueError(";".join(observation_failures))
        initial_digest = observation.digest()
        self.session.identity_boundary.require_decision_context(observation)
        initial_level_event_digest = self.session.bind_level_scope(
            self.episode_handle,
            progress_count=observation.progress_count,
            observation_digest=initial_digest,
        )
        initial_memory_version = self.memory.version
        traces = _TraceCollector(
            retain_cycle_objects=self.retain_cycle_objects,
            sink=self.trace_sink,
        )
        failures: list[str] = []
        actions_executed = 0
        stop_reason = "RESOURCE_LIMIT"
        highest_progress = observation.progress_count
        self.session.ledger.append(
            "RUNTIME_BEGIN",
            {
                "runtime_identity_digest": (self.session.runtime_identity.digest()),
                "session_lineage_digest": self.session.lineage_digest,
                "episode_handle_digest": self.episode_handle.handle_digest,
                "initial_observation_digest": initial_digest,
                "initial_level_event_digest": initial_level_event_digest,
            },
        )

        for cycle_index in range(self.configuration.max_cycles):
            remaining = self.configuration.max_cycles - cycle_index
            if self.session.control.cycle_index != cycle_index:
                raise RuntimeError("GENERIC_CONTROL_CYCLE_INDEX_DIVERGED")
            self.session.control.set_remaining_budget(remaining)
            memory_view = self.memory.view()
            decision_context = DecisionContext(
                observation=DecisionObservation.from_observation(observation),
                memory_version=memory_view.version,
                cycle_index=self.session.control.cycle_index,
                purpose_tokens=tuple(
                    sorted(
                        {
                            "goal:progress",
                            "value:information",
                            "boundary:reversible",
                        }
                    )
                ),
            )
            context_failures = decision_context.validate()
            if context_failures:
                raise PermissionError(";".join(context_failures))
            self.session.identity_boundary.require_decision_context(
                memory_view,
            )
            frame = self.hds.frame(
                observation,
                memory_view,
                remaining_budget=remaining,
                ablation=selected_ablation.hds,
            )
            self.session.identity_boundary.require_decision_context(frame)
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
                p_ir_program=self.session.p_ir_program,
                action_history=(
                    self.session.action_history.view()
                    if selected_ablation.memory_read
                    else ()
                ),
                ablation=selected_ablation.compute,
            )
            decision = self.hds.judge(
                frame=frame,
                observation=observation,
                result=compute_result,
                ablation=selected_ablation.hds,
            )
            self.session.identity_boundary.require_decision_context(
                compute_result,
                decision,
            )
            selected = _selected_candidate(
                compute_result.candidates,
                decision.selected_candidate_id,
            )
            retrieval_stage = next(
                item for item in compute_result.stages if item.stage == "retrieve"
            )
            authority_events = [command.command_id, decision.decision_id]
            cycle_failures: list[str] = []
            if decision.operation_state == "ROLLBACK":
                if not selected_ablation.rollback:
                    cycle_failures.append("GENERIC_ROLLBACK_ABLATED")
                    failures.extend(cycle_failures)
                    stop_reason = "ROLLBACK_ABLATED"
                    traces.append(
                        self._cycle_trace(
                            cycle_index=cycle_index,
                            observation=observation,
                            frame=frame,
                            compute_result=compute_result,
                            decision=decision,
                            selected_candidate=None,
                            result_observation=None,
                            attribution=None,
                            memory_query_digest=retrieval_stage.output_digest,
                            memory_update_digests=(),
                            authority_events=authority_events,
                            failure_signatures=cycle_failures,
                            decision_context_digest=decision_context.digest(),
                        )
                    )
                    break
                control_rollback_authorization = self.hds.authorize_control_rollback(
                    decision,
                    compute_result,
                    observation,
                )
                authority_events.append(control_rollback_authorization.authorization_id)
                self.executor.control_rollback_executor.consume(
                    control_rollback_authorization,
                    decision,
                    observation,
                )
                control_experience_events = [
                    self.session.record_level_reset(
                        self.episode_handle,
                        progress_count=observation.progress_count,
                        observation_digest=observation.digest(),
                        cycle_index=cycle_index,
                        reason="HDS_CONTROL_ROLLBACK",
                    )
                ]
                request_id = (
                    "generic-control-rollback-request:"
                    + digest_object(
                        {
                            "authorization": (
                                control_rollback_authorization.authorization_id
                            ),
                            "cycle": cycle_index,
                        }
                    )[:24]
                )
                try:
                    result_observation = self.environment.reset_level(
                        request_id=request_id
                    )
                except Exception as error:
                    failure = (
                        "GENERIC_ENVIRONMENT_CONTROL_ROLLBACK_FAILURE:"
                        + type(error).__name__
                    )
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
                            selected_candidate=None,
                            result_observation=None,
                            attribution=None,
                            memory_query_digest=retrieval_stage.output_digest,
                            memory_update_digests=(),
                            authority_events=authority_events,
                            failure_signatures=cycle_failures,
                            decision_context_digest=(decision_context.digest()),
                            experience_event_digests=(control_experience_events),
                        )
                    )
                    break
                result_failures = result_observation.validate()
                if result_failures:
                    raise ValueError(";".join(result_failures))
                self.session.identity_boundary.require_decision_context(
                    result_observation
                )
                actions_executed += 1
                highest_progress = max(
                    highest_progress,
                    result_observation.progress_count,
                )
                attribution = self.hds.attribute_control_rollback(
                    before=observation,
                    after=result_observation,
                    result=compute_result,
                )
                rollback_memory_update_digests: list[str] = []
                if selected_ablation.memory_write:
                    control_plan = compute_result.control_plan
                    if control_plan is None:
                        raise RuntimeError("GENERIC_CONTROL_PLAN_MISSING")
                    record = _action_effect_record(
                        action_id=0,
                        payload={},
                        before=observation,
                        after=result_observation,
                        compatibility_reset=True,
                        plan_id=control_plan.plan_id,
                        outcome_category=attribution.category,
                        hypothesis_refs=control_plan.hypothesis_refs,
                    )
                    history_authorization = self.hds.authorize_action_history(
                        decision,
                        record,
                        before_observation=observation,
                        after_observation=result_observation,
                        history_version=(self.session.action_history.version),
                        selected_candidate=None,
                    )
                    authority_events.append(history_authorization.authorization_id)
                    history_event = self.executor.execute_action_history(
                        self.session.action_history,
                        record,
                        history_authorization,
                    )
                    rollback_memory_update_digests.append(history_event.event_digest)
                self.hds.observe_outcome(attribution)
                traces.append(
                    self._cycle_trace(
                        cycle_index=cycle_index,
                        observation=observation,
                        frame=frame,
                        compute_result=compute_result,
                        decision=decision,
                        selected_candidate=None,
                        result_observation=result_observation,
                        attribution=attribution,
                        memory_query_digest=retrieval_stage.output_digest,
                        memory_update_digests=(rollback_memory_update_digests),
                        authority_events=authority_events,
                        failure_signatures=cycle_failures,
                        decision_context_digest=decision_context.digest(),
                        experience_event_digests=control_experience_events,
                    )
                )
                observation = result_observation
                if attribution.category == "FAILURE":
                    failure = "GENERIC_CONTROL_ROLLBACK_DID_NOT_RECOVER"
                    failures.append(failure)
                    stop_reason = "SYSTEM_FAULT"
                    break
                if result_observation.terminal_state == "WIN":
                    stop_reason = "GOAL_REACHED"
                    break
                continue
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
                        decision_context_digest=decision_context.digest(),
                    )
                )
                failures.extend(cycle_failures)
                break
            if selected is None:
                raise RuntimeError("GENERIC_HDS_SELECTED_CANDIDATE_MISSING")
            action_authorization = self.hds.authorize_action(
                decision, selected, observation
            )
            authority_events.append(action_authorization.authorization_id)
            action_id, payload = self.executor.action_executor.consume(
                action_authorization,
                decision,
                selected,
                observation,
            )
            request_id = (
                "generic-action-request:"
                + digest_object(
                    {
                        "authorization": action_authorization.authorization_id,
                        "cycle": cycle_index,
                    }
                )[:24]
            )
            try:
                result_observation = self.environment.step(
                    action_id,
                    payload=payload,
                    request_id=request_id,
                )
            except Exception as error:
                failure = (
                    "GENERIC_ENVIRONMENT_EXECUTION_FAILURE:" + type(error).__name__
                )
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
                        decision_context_digest=decision_context.digest(),
                    )
                )
                break
            result_failures = result_observation.validate()
            if result_failures:
                raise ValueError(";".join(result_failures))
            self.session.identity_boundary.require_decision_context(result_observation)
            actions_executed += 1
            highest_progress = max(highest_progress, result_observation.progress_count)
            attribution = self.hds.attribute(
                before=observation,
                after=result_observation,
                candidate=selected,
            )
            memory_update_digests: list[str] = []
            experience_event_digests: list[str] = []
            if selected_ablation.memory_write:
                history_record = _action_effect_record(
                    action_id=action_id,
                    payload=payload,
                    before=observation,
                    after=result_observation,
                    plan_id=selected.plan.plan_id,
                    outcome_category=attribution.category,
                    hypothesis_refs=selected.plan.hypothesis_refs,
                )
                history_authorization = self.hds.authorize_action_history(
                    decision,
                    history_record,
                    before_observation=observation,
                    after_observation=result_observation,
                    history_version=self.session.action_history.version,
                    selected_candidate=selected,
                )
                authority_events.append(history_authorization.authorization_id)
                history_event = self.executor.execute_action_history(
                    self.session.action_history,
                    history_record,
                    history_authorization,
                )
                memory_update_digests.append(history_event.event_digest)
            if (
                selected_ablation.memory_write
                and decision.memory_update_authorized
                and _semantic_causal_memory_required(
                    self.instruction_body,
                    observation,
                )
            ):
                proposals = outcome_memory_proposals(
                    memory_records=self.memory.view().active,
                    candidate=selected,
                    attribution=attribution,
                    hypotheses=compute_result.hypotheses,
                    decision_id=decision.decision_id,
                    evidence_episode_nonce=self.session.evidence_nonce(
                        self.episode_handle
                    ),
                    cycle_index=cycle_index,
                    evidence_policy=self.session.hds_config.evidence_policy(),
                )
                if len(proposals) > self.configuration.max_memory_updates_per_cycle:
                    cycle_failures.append("SEMANTIC_MEMORY_MANDATORY_BATCH_SUSPEND")
                else:
                    memory_version = self.memory.version
                    memory_authorizations = tuple(
                        self.hds.authorize_memory(
                            decision,
                            proposal,
                            memory_version=memory_version,
                        )
                        for proposal in proposals
                    )
                    authority_events.extend(
                        item.authorization_id for item in memory_authorizations
                    )
                    receipts = self.executor.execute_memory_batch(
                        self.memory,
                        proposals,
                        memory_authorizations,
                        idempotency_key="memory-cycle-batch:"
                        + digest_object(
                            {
                                "decision": decision.decision_id,
                                "cycle": cycle_index,
                                "proposals": proposals,
                            }
                        ),
                    )
                    memory_update_digests.extend(
                        sorted({receipt.event_digest for receipt in receipts})
                    )
            if result_observation.progress_count > observation.progress_count:
                experience_event_digests.append(
                    self.session.record_level_transition(
                        self.episode_handle,
                        before_progress=observation.progress_count,
                        after_progress=result_observation.progress_count,
                        observation_digest=result_observation.digest(),
                        cycle_index=cycle_index,
                    )
                )
            if attribution.category == "FAILURE":
                cycle_failures.append("GENERIC_GAME_OVER_OBSERVED")
                if selected_ablation.rollback:
                    if _explicit_rollback_cycle_required(
                        self.instruction_body,
                        result_observation,
                    ):
                        observation_after_cycle = result_observation
                    else:
                        experience_event_digests.append(
                            self.session.record_level_reset(
                                self.episode_handle,
                                progress_count=(result_observation.progress_count),
                                observation_digest=(result_observation.digest()),
                                cycle_index=cycle_index,
                                reason="GAME_OVER_AUTO_ROLLBACK",
                            )
                        )
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
                        rollback_failures = observation_after_cycle.validate()
                        if rollback_failures:
                            raise ValueError(";".join(rollback_failures))
                        self.session.identity_boundary.require_decision_context(
                            observation_after_cycle
                        )
                else:
                    cycle_failures.append("GENERIC_ROLLBACK_ABLATED")
                    observation_after_cycle = result_observation
                    stop_reason = "ROLLBACK_ABLATED"
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
                    decision_context_digest=decision_context.digest(),
                    experience_event_digests=experience_event_digests,
                )
            )
            failures.extend(
                failure
                for failure in cycle_failures
                if not (
                    selected_ablation.rollback
                    and failure == "GENERIC_GAME_OVER_OBSERVED"
                )
            )
            observation = observation_after_cycle
            if attribution.category == "FAILURE" and not selected_ablation.rollback:
                break
            if result_observation.terminal_state == "WIN":
                stop_reason = "GOAL_REACHED"
                break
        else:
            failures.append("GENERIC_RESOURCE_LIMIT")

        report = GenericRunReport(
            runtime_version=GENERIC_RUNTIME_VERSION,
            instruction_body_version=self.instruction_body.body_version(),
            initial_observation_digest=initial_digest,
            final_observation_digest=observation.digest(),
            final_state=observation.terminal_state,
            progress_count=highest_progress,
            actions_executed=actions_executed,
            cycles=tuple(traces.items),
            stop_reason=stop_reason,
            memory_initial_version=initial_memory_version,
            memory_final_version=self.memory.version,
            no_fallback_used=True,
            runtime_identity_received=True,
            runtime_identity_digest=self.session.runtime_identity.digest(),
            session_lineage_digest=self.session.lineage_digest,
            episode_handle_digest=self.episode_handle.handle_digest,
            identity_boundary_passed=True,
            failure_signatures=tuple(sorted(set(failures))),
            cycle_trace_digests=tuple(traces.digests),
        )
        self.session.ledger.append(
            "RUNTIME_END",
            {
                "report_digest": report.digest(),
                "final_state": report.final_state,
                "stop_reason": report.stop_reason,
                "actions_executed": report.actions_executed,
            },
        )
        return report


__all__ = [
    "GENERIC_RUNTIME_VERSION",
    "GenericAGIRuntime",
    "GenericCycleTraceSink",
    "GenericRuntimeAblation",
    "GenericRuntimeConfiguration",
    "GenericSideEffectExecutor",
    "outcome_memory_proposals",
]
