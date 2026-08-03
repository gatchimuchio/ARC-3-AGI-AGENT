"""Observation-grounded LOCAL_M development capability integration.

This module is deliberately identity-free.  It compiles only the current
render sequence, legal action surface, bounded history summary, and terminal
state into cycle-local semantic records.  ACTIVE_DEV still informs C and J
through ordinary evidence binding; it never bypasses J or selects by identity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from .generic_memory import SemanticMemory, SemanticRecord, semantic_record
from .generic_types import GenericHypothesis, GenericObservation, GenericPrediction
from .schema import digest_object

LOCAL_CAPABILITY_VERSION = "arc3-local-capability-horizontal-v2"
LOCAL_CAPABILITY_STAGE = "PROBATION_DEV"
ACTIVE_DEV_CAPABILITY_STAGE = "ACTIVE_DEV"
GENERIC_MECHANISM_FAMILY_VERSION = "arc3-generic-mechanism-family-v1"
LOCAL_MEMORY_SCOPE = ("EPISODE_LOCAL", "LEVEL_LOCAL", "LOCAL_M")

TEMPORAL_CAPABILITY = "TEMPORAL_SETTLE_AND_ATTRIBUTION"
RELATION_CAPABILITY = "RELATION_BOUND_ACTION_EMISSION"
RESOURCE_CAPABILITY = "RESOURCE_AWARE_PLAN_AND_ROLLBACK"

ACTIVE_DEV_CAPABILITY_IDS = (RELATION_CAPABILITY,)


@dataclass(frozen=True, slots=True)
class GenericMechanismFamily:
    """Identity-free runtime contract produced by horizontal subtraction."""

    family_id: str
    purpose_class: str
    required_observation: tuple[str, ...]
    state_schema: tuple[str, ...]
    role_schema: tuple[str, ...]
    relation_schema: tuple[str, ...]
    precondition_pattern: tuple[str, ...]
    operation_pattern: tuple[str, ...]
    transition_pattern: tuple[str, ...]
    goal_pattern: tuple[str, ...]
    hazard_pattern: tuple[str, ...]
    order_pattern: tuple[str, ...]
    planning_pattern: tuple[str, ...]
    parameter_schema: tuple[str, ...]
    independent_support_count: int
    negative_case_count: int
    boundary_case_count: int
    asset_state: str = ACTIVE_DEV_CAPABILITY_STAGE
    execute_eligibility: bool = False

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.family_id or self.asset_state != ACTIVE_DEV_CAPABILITY_STAGE:
            failures.append("GENERIC_MECHANISM_FAMILY_ID_OR_STATE_INVALID")
        sequence_fields = (
            self.required_observation,
            self.state_schema,
            self.role_schema,
            self.relation_schema,
            self.precondition_pattern,
            self.operation_pattern,
            self.transition_pattern,
            self.goal_pattern,
            self.hazard_pattern,
            self.order_pattern,
            self.planning_pattern,
            self.parameter_schema,
        )
        if any(values != tuple(sorted(set(values))) for values in sequence_fields):
            failures.append("GENERIC_MECHANISM_FAMILY_SCHEMA_INVALID")
        if self.independent_support_count < 2:
            failures.append("GENERIC_MECHANISM_FAMILY_SUPPORT_INSUFFICIENT")
        if self.negative_case_count < 1 or self.boundary_case_count < 1:
            failures.append("GENERIC_MECHANISM_FAMILY_COUNTERCASE_MISSING")
        forbidden = (
            "game_id",
            "level_id",
            "recording_id",
            "trajectory_id",
            "full-frame exact hash",
            "successful action index",
        )
        serialized = repr(self).casefold()
        if any(token in serialized for token in forbidden):
            failures.append("GENERIC_MECHANISM_FAMILY_IDENTITY_FEATURE_PRESENT")
        if self.execute_eligibility:
            failures.append("ACTIVE_DEV_FAMILY_DIRECT_EXECUTION_FORBIDDEN")
        return tuple(sorted(set(failures)))

    def logical_digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "generic-mechanism-family:" + digest_object(self)


RELATION_BOUND_ACTION_FAMILY = GenericMechanismFamily(
    family_id=RELATION_CAPABILITY,
    purpose_class="RELATION_BOUND_STATE_TRANSITION",
    required_observation=tuple(
        sorted(
            {
                "ACTION_COMPLETE_RENDER_SEQUENCE",
                "CURRENT_LEGAL_ACTION_SURFACE",
                "CURRENT_RENDERED_LAYERS",
            }
        )
    ),
    state_schema=tuple(sorted({"CURRENT_STATE", "PREDICTED_EFFECT", "SETTLED_RESULT"})),
    role_schema=tuple(sorted({"ACTOR_ROLE", "AFFORDANCE_ROLE", "TARGET_ROLE"})),
    relation_schema=tuple(sorted({"ACTION_BINDS_ROLE", "EFFECT_UPDATES_RELATION"})),
    precondition_pattern=tuple(
        sorted(
            {
                "ACTION_IS_CURRENTLY_LEGAL",
                "BINDING_IS_CURRENT_RENDER_DERIVED",
                "OBSERVATION_IS_SETTLED",
            }
        )
    ),
    operation_pattern=tuple(
        sorted({"BIND_PARAMETER", "EMIT_ONE_ACTION", "VERIFY_EFFECT"})
    ),
    transition_pattern=tuple(
        sorted(
            {
                "CURRENT_STATE_TO_PREDICTED_EFFECT",
                "PREDICTION_TO_SUPPORT_OR_INVALIDATION",
            }
        )
    ),
    goal_pattern=("OBSERVED_PROGRESS_OR_WIN",),
    hazard_pattern=tuple(
        sorted(
            {
                "AMBIGUOUS_BINDING",
                "STALE_OR_UNSETTLED_RENDER",
                "UNATTRIBUTED_VISIBLE_CHANGE",
            }
        )
    ),
    order_pattern=tuple(
        sorted(
            {
                "ATTRIBUTE_BEFORE_REPLAN",
                "BIND_BEFORE_EMIT",
                "EMIT_BEFORE_ATTRIBUTE",
                "OBSERVE_BEFORE_BIND",
            }
        )
    ),
    planning_pattern=tuple(
        sorted({"BOUNDED_RECEDING_HORIZON", "ONE_EXTERNAL_ACTION_PER_CYCLE"})
    ),
    parameter_schema=tuple(
        sorted(
            {
                "ACTION_KIND_PARAMETER",
                "EFFECT_CLASS_PARAMETER",
                "PAYLOAD_SCHEMA_PARAMETER",
                "RELATION_PARAMETER",
                "ROLE_PARAMETER",
            }
        )
    ),
    independent_support_count=3,
    negative_case_count=3,
    boundary_case_count=3,
)

ACTIVE_DEV_MECHANISM_FAMILIES = (RELATION_BOUND_ACTION_FAMILY,)


def active_dev_mechanism_families() -> tuple[GenericMechanismFamily, ...]:
    """Return the validated runtime registry without development case IDs."""

    failures = tuple(
        failure
        for family in ACTIVE_DEV_MECHANISM_FAMILIES
        for failure in family.validate()
    )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return ACTIVE_DEV_MECHANISM_FAMILIES


@dataclass(frozen=True, slots=True)
class ApplicabilityEvaluation:
    """One identity-free MechanismSpec applicability decision."""

    family_id: str
    required_entities: tuple[str, ...]
    required_relations: tuple[str, ...]
    required_state_pattern: tuple[str, ...]
    required_action_surface: tuple[str, ...]
    temporal_conditions: tuple[str, ...]
    negative_conditions: tuple[str, ...]
    falsification_condition: tuple[str, ...]
    satisfied_conditions: tuple[str, ...]
    missing_conditions: tuple[str, ...]
    action_principle: tuple[str, ...]
    applicable: bool

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        required_groups = (
            self.required_entities,
            self.required_relations,
            self.required_state_pattern,
            self.required_action_surface,
            self.temporal_conditions,
        )
        sequence_fields = (
            *required_groups,
            self.negative_conditions,
            self.falsification_condition,
            self.satisfied_conditions,
            self.missing_conditions,
            self.action_principle,
        )
        if self.family_id != RELATION_CAPABILITY:
            failures.append("APPLICABILITY_FAMILY_ID_INVALID")
        if any(not values for values in required_groups):
            failures.append("APPLICABILITY_REQUIRED_GROUP_EMPTY")
        if any(values != tuple(sorted(set(values))) for values in sequence_fields):
            failures.append("APPLICABILITY_CONDITION_SET_INVALID")
        required = set().union(*map(set, required_groups))
        satisfied = set(self.satisfied_conditions)
        missing = set(self.missing_conditions)
        if satisfied & missing or satisfied | missing != required:
            failures.append("APPLICABILITY_CONDITION_PARTITION_INVALID")
        expected = not self.missing_conditions and not self.negative_conditions
        if self.applicable is not expected:
            failures.append("APPLICABILITY_DECISION_INCONSISTENT")
        if self.action_principle != RELATION_BOUND_ACTION_FAMILY.operation_pattern:
            failures.append("APPLICABILITY_ACTION_PRINCIPLE_DRIFT")
        forbidden = (
            "game_id",
            "level_id",
            "recording_id",
            "trajectory_id",
            "frame_hash",
            "action_index",
        )
        if any(token in repr(self).casefold() for token in forbidden):
            failures.append("APPLICABILITY_IDENTITY_FEATURE_PRESENT")
        return tuple(sorted(set(failures)))

    def logical_digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "applicability-evaluation:" + digest_object(self)


def evaluate_relation_bound_action_applicability(
    observation: GenericObservation,
) -> ApplicabilityEvaluation:
    """Evaluate the full ApplicabilityPredicate from current observation only."""

    required_entities = ("CURRENT_RENDERED_LAYERS",)
    required_relations = ("LEGAL_ACTION_TO_RENDERED_TRANSITION",)
    required_state_pattern = ("NON_TERMINAL_STATE",)
    required_action_surface = ("NON_CONTROL_LEGAL_ACTION",)
    temporal_conditions = ("ACTION_COMPLETE",)
    has_render = bool(observation.rendered_layers)
    has_external_action = any(
        action_id != 0 for action_id in observation.available_actions
    )
    conditions = {
        "CURRENT_RENDERED_LAYERS": has_render,
        "LEGAL_ACTION_TO_RENDERED_TRANSITION": (has_render and has_external_action),
        "NON_TERMINAL_STATE": observation.terminal_state not in {"WIN", "GAME_OVER"},
        "NON_CONTROL_LEGAL_ACTION": has_external_action,
        "ACTION_COMPLETE": observation.action_complete,
    }
    validation_failures = observation.validate()
    negative_conditions = set()
    if validation_failures:
        negative_conditions.add("INVALID_OBSERVATION_CONTRACT")
    if not has_render:
        negative_conditions.add("RENDERED_ENTITY_ABSENT")
    if not has_external_action:
        negative_conditions.add("EXTERNAL_ACTION_SURFACE_ABSENT")
    if observation.terminal_state in {"WIN", "GAME_OVER"}:
        negative_conditions.add("TERMINAL_STATE")
    if not observation.action_complete:
        negative_conditions.add("UNSETTLED_OBSERVATION")
    evaluation = ApplicabilityEvaluation(
        family_id=RELATION_CAPABILITY,
        required_entities=required_entities,
        required_relations=required_relations,
        required_state_pattern=required_state_pattern,
        required_action_surface=required_action_surface,
        temporal_conditions=temporal_conditions,
        negative_conditions=tuple(sorted(negative_conditions)),
        falsification_condition=(
            "NEGATIVE_CONDITION_OBSERVED",
            "REQUIRED_CONDITION_MISSING",
        ),
        satisfied_conditions=tuple(
            sorted(name for name, present in conditions.items() if present)
        ),
        missing_conditions=tuple(
            sorted(name for name, present in conditions.items() if not present)
        ),
        action_principle=RELATION_BOUND_ACTION_FAMILY.operation_pattern,
        applicable=all(conditions.values()) and not validation_failures,
    )
    failures = evaluation.validate()
    if failures:
        raise ValueError(";".join(failures))
    return evaluation


def relation_bound_action_applicable(observation: GenericObservation) -> bool:
    """Evaluate the promoted family from current observation fields only."""

    return evaluate_relation_bound_action_applicability(observation).applicable


@dataclass(frozen=True, slots=True)
class LocalCapabilityRefresh:
    """Auditable replacement receipt for non-authoritative working M."""

    observation_digest: str
    added_ids: tuple[str, ...]
    revised_ids: tuple[str, ...]
    invalidated_ids: tuple[str, ...]
    retained_ids: tuple[str, ...]
    working_record_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        partitions = (
            self.added_ids,
            self.revised_ids,
            self.invalidated_ids,
            self.retained_ids,
        )
        if not self.observation_digest.startswith("generic-observation:"):
            failures.append("LOCAL_M_OBSERVATION_DIGEST_INVALID")
        for values in (*partitions, self.working_record_ids, self.capability_ids):
            if values != tuple(sorted(set(values))):
                failures.append("LOCAL_M_REFRESH_SET_INVALID")
        if set(self.added_ids) & set(self.revised_ids):
            failures.append("LOCAL_M_REFRESH_PARTITION_OVERLAP")
        if set(self.invalidated_ids) & set(self.working_record_ids):
            failures.append("LOCAL_M_INVALIDATED_RECORD_RETAINED")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "local-capability-refresh:" + digest_object(self)


def _surface_family(observation: GenericObservation) -> str:
    actions = set(observation.available_actions)
    directional = bool(actions.intersection({1, 2, 3, 4}))
    if actions == {6}:
        return "COORDINATE_RELATION_TRANSITION"
    if 6 in actions and directional:
        return "MIXED_DIRECTION_AND_COORDINATE_TRANSITION"
    if 5 in actions and directional:
        return "COUPLED_ACTOR_ATTACHMENT_TRANSITION"
    if directional:
        return "DIRECTIONAL_STATE_TRANSITION"
    return "GENERIC_LEGAL_ACTION_TRANSITION"


def _observation_tokens(observation: GenericObservation) -> tuple[str, ...]:
    repeat_count = observation.observation_history.count(observation.signature)
    values = {
        f"action-count:{len(observation.available_actions)}",
        f"legal-action-count:{len(observation.legal_action_surface)}",
        f"action-frame-count:{observation.action_frame_count}",
        f"animation-observed:{str(observation.animation_observed).casefold()}",
        f"action-complete:{str(observation.action_complete).casefold()}",
        f"terminal:{observation.terminal_state.casefold()}",
        f"progress-count:{observation.progress_count}",
        f"history-length:{len(observation.observation_history)}",
        f"current-signature-repeat-count:{repeat_count}",
        f"mechanism-family:{_surface_family(observation).casefold()}",
    }
    values.update(
        f"payload-schema:{action_id}:{','.join(fields)}"
        for action_id, fields in observation.action_payload_schema
    )
    return tuple(sorted(values))


def _record(
    *,
    observation: GenericObservation,
    memory_id: str,
    kind: str,
    statement: str,
    capability_id: str,
    falsification_condition: str,
    tokens: Sequence[str],
    predictions: Sequence[str] = (),
) -> SemanticRecord:
    active_dev = capability_id in ACTIVE_DEV_CAPABILITY_IDS
    applicability_match = (
        relation_bound_action_applicable(observation)
        if capability_id == RELATION_CAPABILITY
        else True
    )
    asset_stage = ACTIVE_DEV_CAPABILITY_STAGE if active_dev else LOCAL_CAPABILITY_STAGE
    evidence = (
        LOCAL_CAPABILITY_VERSION,
        observation.digest(),
        "rendered-observation-only",
    )
    return semantic_record(
        memory_id=memory_id,
        kind=kind,
        statement=statement,
        semantic_tokens=tuple(tokens),
        evidence=evidence,
        scope=LOCAL_MEMORY_SCOPE,
        falsification_condition=falsification_condition,
        state="PROBATION",
        payload={
            "applicability_match": applicability_match,
            "asset_stage": asset_stage,
            "capability_id": capability_id,
            "confidence_ppm": 800_000 if active_dev else 450_000,
            "execute_eligibility": False,
            "family_version": (GENERIC_MECHANISM_FAMILY_VERSION if active_dev else ""),
            "predictions": tuple(sorted(set(predictions))),
            "scope_class": "LEVEL_OVERLAY",
            "support_count": 3 if active_dev else 0,
        },
    )


def local_capability_records(
    observation: GenericObservation,
) -> tuple[SemanticRecord, ...]:
    """Compile the current observation into replaceable LOCAL_M records."""

    failures = observation.validate()
    if failures:
        raise ValueError(";".join(failures))
    tokens = _observation_tokens(observation)
    family = _surface_family(observation)
    settled = observation.action_complete
    records = [
        _record(
            observation=observation,
            memory_id="local-m:observation-state",
            kind="STATE_MODEL",
            statement=(
                "The current action-complete render sequence and legal surface "
                "define the only local world state available for this cycle."
            ),
            capability_id=TEMPORAL_CAPABILITY,
            falsification_condition=(
                "the next official observation contradicts the current render "
                "sequence, action surface, or terminal state"
            ),
            tokens=tokens,
            predictions=("CURRENT_RENDER_ONLY",),
        ),
        _record(
            observation=observation,
            memory_id="local-m:temporal-settle",
            kind="TRANSITION_RULE",
            statement=(
                "The current external effect is settled and may be attributed."
                if settled
                else "The current external effect is not settled; wait and reobserve."
            ),
            capability_id=TEMPORAL_CAPABILITY,
            falsification_condition=(
                "a later render shows that the assumed action-complete boundary "
                "was incorrect"
            ),
            tokens=tokens,
            predictions=(
                ("ACTION_COMPLETE_EFFECT",)
                if settled
                else ("DELAYED_EFFECT", "WAIT_FOR_SETTLE")
            ),
        ),
        _record(
            observation=observation,
            memory_id="local-m:resource-recovery",
            kind="HAZARD_MODEL",
            statement=(
                "Repeated no-progress state and terminal failure require a "
                "causally named replan or rollback, never blind repetition."
            ),
            capability_id=RESOURCE_CAPABILITY,
            falsification_condition=(
                "independent progress evidence shows repetition or rollback was "
                "not hazardous under the same rendered precondition"
            ),
            tokens=tokens,
            predictions=("BUDGET_HAZARD", "CAUSAL_RECOVERY"),
        ),
        _record(
            observation=observation,
            memory_id="local-m:goal-model",
            kind="GOAL_MODEL",
            statement=(
                "Progress count or WIN, not visible change alone, is the current "
                "goal predicate."
            ),
            capability_id=RESOURCE_CAPABILITY,
            falsification_condition=(
                "the environment exposes a different rendered completion predicate"
            ),
            tokens=(*tokens, "goal:progress"),
            predictions=("LEVEL_PROGRESS", "WIN"),
        ),
        _record(
            observation=observation,
            memory_id="local-m:mechanism-hypothesis",
            kind="HYPOTHESIS",
            statement=(
                f"The current legal surface supports a {family.casefold()} "
                "mechanism whose effects must be verified after one action."
            ),
            capability_id=RELATION_CAPABILITY,
            falsification_condition=(
                "a bound legal action repeatedly contradicts the predicted "
                "relation transition"
            ),
            tokens=tokens,
            predictions=(family, "VISIBLE_STATE_CHANGE"),
        ),
        _record(
            observation=observation,
            memory_id="local-m:counter-hypothesis",
            kind="COUNTER_HYPOTHESIS",
            statement=(
                "The apparent affordance may be interface animation, a no-op, or "
                "a non-causal visible change."
            ),
            capability_id=RELATION_CAPABILITY,
            falsification_condition=(
                "a bounded current-render action reproducibly causes goal progress"
            ),
            tokens=tokens,
            predictions=("DELAYED_EFFECT", "NO_VISIBLE_CHANGE"),
        ),
    ]
    action_set = set(observation.available_actions)
    if 6 in action_set:
        records.append(
            _record(
                observation=observation,
                memory_id="local-m:coordinate-binding",
                kind="PROCEDURE_CAPABILITY",
                statement=(
                    "Bind ACTION6 x/y only to a role or affordance derived from "
                    "the current composited render."
                ),
                capability_id=RELATION_CAPABILITY,
                falsification_condition=(
                    "the current-render binding is unavailable, ambiguous, or "
                    "contradicted by its observed effect"
                ),
                tokens=(*tokens, "payload-schema:6:x,y"),
                predictions=("RELATION_BOUND_INTERACTION",),
            )
        )
    if 5 in action_set:
        records.append(
            _record(
                observation=observation,
                memory_id="local-m:coupling-binding",
                kind="PROCEDURE_CAPABILITY",
                statement=(
                    "Treat ACTION5 as a candidate coupling transition and verify "
                    "both immediate and autonomous follow-on effects."
                ),
                capability_id=RELATION_CAPABILITY,
                falsification_condition=(
                    "ACTION5 produces no coupling-related effect under the current "
                    "rendered precondition"
                ),
                tokens=tokens,
                predictions=("COUPLED_TRANSITION", "DELAYED_EFFECT"),
            )
        )
    ordered = tuple(sorted(records, key=lambda item: item.memory_id))
    record_failures = tuple(
        failure for record in ordered for failure in record.validate()
    )
    if record_failures:
        raise ValueError(";".join(sorted(set(record_failures))))
    return ordered


def refresh_local_capability_memory(
    memory: SemanticMemory,
    observation: GenericObservation,
) -> LocalCapabilityRefresh:
    """Replace working M and report ADD/REVISE/INVALIDATE semantics."""

    before = {item.memory_id: item for item in memory.view().working}
    records = local_capability_records(observation)
    after = {item.memory_id: item for item in records}
    shared = set(before).intersection(after)
    revised = tuple(
        sorted(
            identifier
            for identifier in shared
            if before[identifier].citation().content_digest
            != after[identifier].citation().content_digest
        )
    )
    retained = tuple(sorted(shared.difference(revised)))
    memory.set_working(records)
    capability_ids = tuple(
        sorted({str(record.payload()["capability_id"]) for record in records})
    )
    receipt = LocalCapabilityRefresh(
        observation_digest=observation.digest(),
        added_ids=tuple(sorted(set(after).difference(before))),
        revised_ids=revised,
        invalidated_ids=tuple(sorted(set(before).difference(after))),
        retained_ids=retained,
        working_record_ids=tuple(sorted(after)),
        capability_ids=capability_ids,
    )
    failures = receipt.validate()
    if failures:
        raise ValueError(";".join(failures))
    return receipt


def _development_records(
    records: Sequence[SemanticRecord],
) -> tuple[SemanticRecord, ...]:
    return tuple(
        record
        for record in records
        if (
            "LOCAL_M" in record.scope
            and (
                (
                    record.state == "PROBATION"
                    and record.payload().get("asset_stage") == LOCAL_CAPABILITY_STAGE
                )
                or (
                    record.state == "PROBATION"
                    and record.payload().get("asset_stage")
                    == ACTIVE_DEV_CAPABILITY_STAGE
                    and record.payload().get("applicability_match") is True
                )
            )
        )
    )


def _capability_ref(record: SemanticRecord) -> str:
    prefix = (
        "active-capability:"
        if record.payload().get("asset_stage") == ACTIVE_DEV_CAPABILITY_STAGE
        else "probation-capability:"
    )
    return prefix + str(record.payload()["capability_id"])


def enrich_development_predictions(
    predictions: Sequence[GenericPrediction],
    records: Sequence[SemanticRecord],
    observation: GenericObservation,
) -> tuple[GenericPrediction, ...]:
    """Add explicit P_dev citations/effects without granting execute authority."""

    development = _development_records(records)
    if not development:
        return tuple(predictions)
    capability_refs = tuple(sorted({_capability_ref(record) for record in development}))
    memory_refs = tuple(sorted(record.memory_id for record in development))
    enriched: list[GenericPrediction] = []
    for prediction in predictions:
        effects = set(prediction.predicted_effects)
        if observation.animation_observed or not observation.action_complete:
            effects.add("DELAYED_EFFECT")
        if prediction.descriptor.action_id == 6:
            effects.add("RELATION_BOUND_INTERACTION")
        if prediction.descriptor.action_id == 5:
            effects.add("COUPLED_TRANSITION")
        risk = 1.0 if not observation.action_complete else prediction.hazard_likelihood
        enriched.append(
            replace(
                prediction,
                predicted_effects=tuple(sorted(effects)),
                hazard_likelihood=risk,
                instruction_refs=tuple(
                    sorted({*prediction.instruction_refs, *capability_refs})
                ),
                memory_refs=tuple(sorted({*prediction.memory_refs, *memory_refs})),
            )
        )
    return tuple(enriched)


def development_hypotheses(
    records: Sequence[SemanticRecord],
    observation: GenericObservation,
    *,
    include_counter_hypotheses: bool = True,
) -> tuple[GenericHypothesis, ...]:
    """Project LOCAL_M mechanism, goal, and counter records into C output."""

    selected = tuple(
        record
        for record in _development_records(records)
        if record.kind in {"HYPOTHESIS", "COUNTER_HYPOTHESIS", "GOAL_MODEL"}
        and (include_counter_hypotheses or record.kind != "COUNTER_HYPOTHESIS")
    )
    output: list[GenericHypothesis] = []
    for record in selected:
        raw_predictions = record.payload().get("predictions", ())
        if isinstance(raw_predictions, (str, bytes)) or not isinstance(
            raw_predictions,
            Sequence,
        ):
            raw_predictions = ()
        predictions = tuple(
            sorted(
                str(item) for item in raw_predictions if isinstance(item, str) and item
            )
        )
        active_dev = record.payload().get("asset_stage") == ACTIVE_DEV_CAPABILITY_STAGE
        model_type = {
            "HYPOTHESIS": ("active_mechanism" if active_dev else "probation_mechanism"),
            "COUNTER_HYPOTHESIS": "counter_hypothesis",
            "GOAL_MODEL": "goal_model",
        }[record.kind]
        output.append(
            GenericHypothesis(
                hypothesis_id="hypothesis:local-capability:"
                + digest_object((record.citation(), observation.digest()))[:20],
                model_type=model_type,
                statement=record.statement,
                predictions=predictions,
                falsification_conditions=(record.falsification_condition,),
                supporting_evidence=(
                    observation.digest(),
                    record.citation().content_digest,
                    _capability_ref(record),
                ),
                confidence=0.8 if active_dev else 0.45,
            )
        )
    ordered = tuple(sorted(output, key=lambda item: item.hypothesis_id))
    failures = tuple(
        failure for hypothesis in ordered for failure in hypothesis.validate()
    )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return ordered


__all__ = [
    "ACTIVE_DEV_CAPABILITY_IDS",
    "ACTIVE_DEV_CAPABILITY_STAGE",
    "ACTIVE_DEV_MECHANISM_FAMILIES",
    "GENERIC_MECHANISM_FAMILY_VERSION",
    "LOCAL_CAPABILITY_STAGE",
    "LOCAL_CAPABILITY_VERSION",
    "GenericMechanismFamily",
    "ApplicabilityEvaluation",
    "LocalCapabilityRefresh",
    "RELATION_BOUND_ACTION_FAMILY",
    "active_dev_mechanism_families",
    "development_hypotheses",
    "evaluate_relation_bound_action_applicability",
    "enrich_development_predictions",
    "local_capability_records",
    "refresh_local_capability_memory",
    "relation_bound_action_applicable",
]
