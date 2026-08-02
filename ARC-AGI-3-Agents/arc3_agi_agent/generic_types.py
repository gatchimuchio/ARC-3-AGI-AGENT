"""Identity-free contracts for the pre-official GenericAGIRuntime.

These types intentionally do not contain task, game, level, replay, source, or
hidden-state fields. Environment identity belongs to orchestration only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from .evidence_binding import (
    CandidateEvidenceBinding,
    EvidenceBindingKey,
    TypedCandidateProvenance,
)
from .schema import digest_object
from .taint import (
    COORDINATE_PROVENANCE_NONE,
    validate_coordinate_provenance,
)

GENERIC_TYPES_VERSION = "arc3-generic-types-v1"
GENERIC_TERMINAL_STATES = frozenset({"NOT_FINISHED", "WIN", "GAME_OVER", "UNKNOWN"})
GENERIC_DECISION_OPERATIONS = frozenset(
    {"EXECUTE", "PROBE", "REOBSERVE", "ROLLBACK", "SUSPEND", "STOP"}
)
GENERIC_ASSERTION_STATES = frozenset({"PASS", "SUSPEND", "FAIL"})


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sorted_unique_text(values: Sequence[str]) -> bool:
    return all(_text(item) for item in values) and tuple(values) == tuple(
        sorted(set(values))
    )


@dataclass(frozen=True, slots=True)
class GenericObservation:
    """One action-complete, identity-free environment observation.

    ``rendered_layers`` is retained as the compatibility field name.  For the
    official ARC3 contract its items are temporal camera renders produced
    during one external action, not independent spatial layers.  The final
    item is the action-complete composited view used for spatial reasoning.
    """

    signature: str
    available_actions: tuple[int, ...]
    rendered_layers: tuple[tuple[tuple[int, ...], ...], ...] = field(
        default=(),
        repr=False,
    )
    terminal_state: str = "UNKNOWN"
    progress_count: int = 0
    visible_effects: tuple[str, ...] = ()
    action_payload_schema: tuple[tuple[int, tuple[str, ...]], ...] = ()
    control_actions: tuple[int, ...] = ()
    win_level_count: int = 0
    full_reset: bool = False
    last_action_id: int = 0
    last_action_payload_items: tuple[tuple[str, int], ...] = ()
    observation_history: tuple[str, ...] = ()
    action_complete: bool = True
    _validation_cache: tuple[str, ...] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _digest_cache: str | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    @property
    def rendered_action_frames(
        self,
    ) -> tuple[tuple[tuple[int, ...], ...], ...]:
        """Return every temporal render from the current external action."""

        return self.rendered_layers

    @property
    def composited_view(self) -> tuple[tuple[int, ...], ...]:
        """Return the final camera-composited render for spatial reasoning."""

        return self.rendered_layers[-1] if self.rendered_layers else ()

    @property
    def action_frame_count(self) -> int:
        return len(self.rendered_layers)

    @property
    def animation_observed(self) -> bool:
        return len(self.rendered_layers) > 1

    @property
    def frame_relations(self) -> tuple[str, ...]:
        return tuple(
            f"action-frame:{index - 1}:precedes:action-frame:{index}"
            for index in range(1, len(self.rendered_layers))
        )

    @property
    def legal_action_surface(self) -> tuple[int, ...]:
        """Normal actions plus separately governed control actions."""

        return tuple(sorted({*self.control_actions, *self.available_actions}))

    def validate(self) -> tuple[str, ...]:
        if self._validation_cache is not None:
            return self._validation_cache
        failures: list[str] = []
        if not _text(self.signature):
            failures.append("GENERIC_OBSERVATION_SIGNATURE_MISSING")
        if (
            not self.available_actions
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.available_actions
            )
            or self.available_actions != tuple(sorted(set(self.available_actions)))
        ):
            failures.append("GENERIC_AVAILABLE_ACTIONS_INVALID")
        if (
            any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.control_actions
            )
            or self.control_actions != tuple(sorted(set(self.control_actions)))
            or any(item != 0 for item in self.control_actions)
            or bool(set(self.control_actions) & set(self.available_actions))
        ):
            failures.append("GENERIC_CONTROL_ACTIONS_INVALID")
        if self.terminal_state not in GENERIC_TERMINAL_STATES:
            failures.append("GENERIC_TERMINAL_STATE_INVALID")
        if (
            isinstance(self.progress_count, bool)
            or not isinstance(self.progress_count, int)
            or self.progress_count < 0
        ):
            failures.append("GENERIC_PROGRESS_COUNT_INVALID")
        if (
            isinstance(self.win_level_count, bool)
            or not isinstance(self.win_level_count, int)
            or self.win_level_count < 0
            or (self.win_level_count > 0 and self.progress_count > self.win_level_count)
        ):
            failures.append("GENERIC_WIN_LEVEL_COUNT_INVALID")
        if not isinstance(self.full_reset, bool):
            failures.append("GENERIC_FULL_RESET_INVALID")
        if (
            isinstance(self.last_action_id, bool)
            or not isinstance(self.last_action_id, int)
            or self.last_action_id < 0
        ):
            failures.append("GENERIC_LAST_ACTION_INVALID")
        payload_keys = tuple(key for key, _ in self.last_action_payload_items)
        if (
            payload_keys != tuple(sorted(set(payload_keys)))
            or any(key not in {"x", "y"} for key in payload_keys)
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for _, value in self.last_action_payload_items
            )
            or (self.last_action_id != 6 and bool(self.last_action_payload_items))
            or (self.last_action_payload_items and set(payload_keys) != {"x", "y"})
        ):
            failures.append("GENERIC_LAST_ACTION_PAYLOAD_INVALID")
        if len(self.observation_history) > 16 or any(
            not _text(item) for item in self.observation_history
        ):
            failures.append("GENERIC_OBSERVATION_HISTORY_INVALID")
        if not isinstance(self.action_complete, bool):
            failures.append("GENERIC_ACTION_COMPLETE_INVALID")
        if not _sorted_unique_text(self.visible_effects):
            failures.append("GENERIC_VISIBLE_EFFECTS_INVALID")
        schema_actions = tuple(item[0] for item in self.action_payload_schema)
        if (
            schema_actions != tuple(sorted(set(schema_actions)))
            or any(action not in self.available_actions for action in schema_actions)
            or any(
                not _sorted_unique_text(fields)
                for _, fields in self.action_payload_schema
            )
        ):
            failures.append("GENERIC_ACTION_PAYLOAD_SCHEMA_INVALID")
        for layer in self.rendered_layers:
            if not layer:
                failures.append("GENERIC_RENDER_LAYER_EMPTY")
                break
            widths = {len(row) for row in layer}
            if len(widths) != 1 or next(iter(widths), 0) <= 0:
                failures.append("GENERIC_RENDER_LAYER_RAGGED")
                break
            if any(
                isinstance(cell, bool) or not isinstance(cell, int)
                for row in layer
                for cell in row
            ):
                failures.append("GENERIC_RENDER_CELL_INVALID")
                break
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def digest(self) -> str:
        cached = self._digest_cache
        if cached is None:
            cached = "generic-observation:" + digest_object(self)
            object.__setattr__(
                self,
                "_digest_cache",
                cached,
            )
        return cached


@dataclass(frozen=True, slots=True)
class ActionEffectRecord:
    """One HDS-authorized action and its rendered, episode-local effect.

    The record deliberately contains no environment identity or replay index.
    It is the bounded passive-memory input used by executable P bodies that
    need temporal action/effect context.
    """

    action_id: int
    payload_items: tuple[tuple[str, int], ...] = ()
    visible_change: bool = False
    compatibility_reset: bool = False
    target_palette: int = 0
    plan_id: str = ""
    outcome_category: str = ""
    hypothesis_refs: tuple[str, ...] = ()

    def payload(self) -> dict[str, int]:
        return dict(self.payload_items)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            isinstance(self.action_id, bool)
            or not isinstance(self.action_id, int)
            or self.action_id < 0
        ):
            failures.append("ACTION_EFFECT_HISTORY_ACTION_INVALID")
        keys = tuple(key for key, _ in self.payload_items)
        if keys != tuple(sorted(set(keys))):
            failures.append("ACTION_EFFECT_HISTORY_PAYLOAD_INVALID")
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for _, value in self.payload_items
        ):
            failures.append("ACTION_EFFECT_HISTORY_PAYLOAD_VALUE_INVALID")
        if self.action_id == 6:
            payload = self.payload()
            if set(payload) != {"x", "y"}:
                failures.append("ACTION_EFFECT_HISTORY_POINTER_PAYLOAD_INVALID")
            elif not (0 <= payload["x"] < 64 and 0 <= payload["y"] < 64):
                failures.append("ACTION_EFFECT_HISTORY_POINTER_RANGE_INVALID")
            if not 0 <= self.target_palette < 16:
                failures.append("ACTION_EFFECT_HISTORY_PALETTE_INVALID")
        elif self.payload_items or self.target_palette != 0:
            failures.append("ACTION_EFFECT_HISTORY_NON_POINTER_PAYLOAD_PRESENT")
        if self.compatibility_reset != (self.action_id == 0):
            failures.append("ACTION_EFFECT_HISTORY_RESET_SCOPE_INVALID")
        plan_metadata_present = bool(
            self.plan_id or self.outcome_category or self.hypothesis_refs
        )
        if plan_metadata_present:
            if not _text(self.plan_id):
                failures.append("ACTION_EFFECT_HISTORY_PLAN_ID_INVALID")
            if self.outcome_category not in {
                "FAILURE",
                "NO_EFFECT",
                "PROGRESS",
                "VISIBLE_CHANGE",
            }:
                failures.append("ACTION_EFFECT_HISTORY_OUTCOME_INVALID")
            if not self.hypothesis_refs or not _sorted_unique_text(
                self.hypothesis_refs
            ):
                failures.append("ACTION_EFFECT_HISTORY_HYPOTHESIS_REFS_INVALID")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "action-effect-record:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class ObjectRole:
    """Appearance-normalized object role computed from the current render."""

    role_id: str
    area_rank: int
    area_bucket: str
    shape_signature: str
    relative_vertical: str
    relative_horizontal: str
    neighbor_count: int
    target_x: int
    target_y: int

    def semantic_tokens(self) -> tuple[str, ...]:
        return (
            f"role-rank:{self.area_rank}",
            f"area:{self.area_bucket}",
            f"shape:{self.shape_signature}",
            f"vertical:{self.relative_vertical}",
            f"horizontal:{self.relative_horizontal}",
            f"neighbors:{self.neighbor_count}",
        )


@dataclass(frozen=True, slots=True)
class RelationalRepresentation:
    """The first Layer-0 stage: object/role/relation/topology representation."""

    observation_signature: str
    roles: tuple[ObjectRole, ...]
    relations: tuple[str, ...]
    topology_tokens: tuple[str, ...]
    goal_tokens: tuple[str, ...]
    digest_value: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text(self.observation_signature):
            failures.append("GENERIC_REPRESENTATION_OBSERVATION_MISSING")
        role_ids = tuple(item.role_id for item in self.roles)
        if role_ids != tuple(sorted(set(role_ids))):
            failures.append("GENERIC_REPRESENTATION_ROLE_IDS_INVALID")
        if not _sorted_unique_text(self.relations):
            failures.append("GENERIC_REPRESENTATION_RELATIONS_INVALID")
        if not _sorted_unique_text(self.topology_tokens):
            failures.append("GENERIC_REPRESENTATION_TOPOLOGY_INVALID")
        if not _sorted_unique_text(self.goal_tokens):
            failures.append("GENERIC_REPRESENTATION_GOALS_INVALID")
        if self.digest_value != "generic-representation:" + digest_object(
            {
                "observation_signature": self.observation_signature,
                "roles": self.roles,
                "relations": self.relations,
                "topology_tokens": self.topology_tokens,
                "goal_tokens": self.goal_tokens,
            }
        ):
            failures.append("GENERIC_REPRESENTATION_DIGEST_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class SemanticMemoryCitation:
    memory_id: str
    version: int
    kind: str
    semantic_tokens: tuple[str, ...]
    content_digest: str


@dataclass(frozen=True, slots=True)
class ActionDescriptor:
    """One legal action or legal action/role binding."""

    action_id: int
    surface_ordinal: int
    semantic_key: str
    payload_items: tuple[tuple[str, int], ...] = ()
    target_role: str | None = None
    coordinate_provenance: str = COORDINATE_PROVENANCE_NONE
    coordinate_observation_digest: str = ""

    def payload(self) -> dict[str, int]:
        return dict(self.payload_items)

    def validate(self, observation: GenericObservation) -> tuple[str, ...]:
        failures: list[str] = []
        if self.action_id not in observation.available_actions:
            failures.append("GENERIC_DESCRIPTOR_ACTION_UNAVAILABLE")
        if (
            isinstance(self.surface_ordinal, bool)
            or not isinstance(self.surface_ordinal, int)
            or self.surface_ordinal < 0
        ):
            failures.append("GENERIC_DESCRIPTOR_ORDINAL_INVALID")
        if not _text(self.semantic_key):
            failures.append("GENERIC_DESCRIPTOR_KEY_MISSING")
        if tuple(key for key, _ in self.payload_items) != tuple(
            sorted(set(key for key, _ in self.payload_items))
        ):
            failures.append("GENERIC_DESCRIPTOR_PAYLOAD_INVALID")
        failures.extend(
            validate_coordinate_provenance(
                payload_items=self.payload_items,
                coordinate_provenance=self.coordinate_provenance,
                coordinate_observation_digest=(self.coordinate_observation_digest),
                current_observation_digest=observation.digest(),
                rendered_layers=observation.rendered_layers,
            )
        )
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GenericPrediction:
    descriptor: ActionDescriptor
    predicted_effects: tuple[str, ...]
    progress_likelihood: float
    hazard_likelihood: float
    information_gain: float
    prior: float
    uncertainty: float
    instruction_refs: tuple[str, ...]
    memory_refs: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name, value in (
            ("PROGRESS", self.progress_likelihood),
            ("HAZARD", self.hazard_likelihood),
            ("INFORMATION", self.information_gain),
            ("PRIOR", self.prior),
            ("UNCERTAINTY", self.uncertainty),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.0 <= float(value) <= 1.0
            ):
                failures.append(f"GENERIC_PREDICTION_{name}_INVALID")
        if not _sorted_unique_text(self.predicted_effects):
            failures.append("GENERIC_PREDICTION_EFFECTS_INVALID")
        if not self.instruction_refs:
            failures.append("GENERIC_PREDICTION_INSTRUCTION_REF_MISSING")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GenericHypothesis:
    hypothesis_id: str
    model_type: str
    statement: str
    predictions: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()
    confidence: float = 0.0

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not all(
            _text(value)
            for value in (self.hypothesis_id, self.model_type, self.statement)
        ):
            failures.append("GENERIC_HYPOTHESIS_TEXT_INVALID")
        if not _sorted_unique_text(self.predictions):
            failures.append("GENERIC_HYPOTHESIS_PREDICTIONS_INVALID")
        if not _sorted_unique_text(self.falsification_conditions):
            failures.append("GENERIC_HYPOTHESIS_FALSIFIER_INVALID")
        if not 0.0 <= self.confidence <= 1.0:
            failures.append("GENERIC_HYPOTHESIS_CONFIDENCE_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GenericPlanStep:
    """One internal or external step in a bounded receding-horizon plan."""

    step_index: int
    operation: str
    completion_predicate: str
    failure_transition: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            isinstance(self.step_index, bool)
            or not isinstance(self.step_index, int)
            or self.step_index < 0
        ):
            failures.append("GENERIC_PLAN_STEP_INDEX_INVALID")
        if self.operation not in {
            "ACTION",
            "BOUNDED_PROBE",
            "ROLLBACK",
            "REOBSERVE",
            "VERIFY",
            "REPLAN",
        }:
            failures.append("GENERIC_PLAN_STEP_OPERATION_INVALID")
        if not _text(self.completion_predicate):
            failures.append("GENERIC_PLAN_STEP_COMPLETION_INVALID")
        if not _text(self.failure_transition):
            failures.append("GENERIC_PLAN_STEP_FAILURE_TRANSITION_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GenericPlan:
    """Identity-free online plan bound to hypotheses, evidence, and a subgoal.

    Only the first step may cause an external side effect.  The remaining
    steps force reobservation, effect verification, and contingent replanning
    before another external action can be authorized.
    """

    plan_id: str
    candidate_id: str | None
    mode: str
    phase: str
    goal_predicate: str
    subgoal: str
    hypothesis_refs: tuple[str, ...]
    representation_refs: tuple[str, ...]
    memory_refs: tuple[str, ...]
    steps: tuple[GenericPlanStep, ...]
    revision_reason: str
    predecessor_plan_id: str = ""
    invalidated_hypothesis_refs: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text(self.plan_id):
            failures.append("GENERIC_PLAN_ID_INVALID")
        if self.candidate_id is not None and not _text(self.candidate_id):
            failures.append("GENERIC_PLAN_CANDIDATE_ID_INVALID")
        if self.mode not in {"ACTION_PLAN", "PROBE_PLAN", "ROLLBACK_PLAN"}:
            failures.append("GENERIC_PLAN_MODE_INVALID")
        if not all(
            _text(value)
            for value in (
                self.phase,
                self.goal_predicate,
                self.subgoal,
                self.revision_reason,
            )
        ):
            failures.append("GENERIC_PLAN_PURPOSE_INVALID")
        if not self.hypothesis_refs or not _sorted_unique_text(
            self.hypothesis_refs
        ):
            failures.append("GENERIC_PLAN_HYPOTHESIS_REFS_INVALID")
        if (
            len(self.representation_refs) < 2
            or not _sorted_unique_text(self.representation_refs)
        ):
            failures.append("GENERIC_PLAN_REPRESENTATION_REFS_INVALID")
        if not _sorted_unique_text(self.memory_refs):
            failures.append("GENERIC_PLAN_MEMORY_REFS_INVALID")
        if self.predecessor_plan_id and not _text(self.predecessor_plan_id):
            failures.append("GENERIC_PLAN_PREDECESSOR_INVALID")
        if not _sorted_unique_text(self.invalidated_hypothesis_refs):
            failures.append("GENERIC_PLAN_INVALIDATED_REFS_INVALID")
        if set(self.hypothesis_refs).intersection(
            self.invalidated_hypothesis_refs
        ):
            failures.append("GENERIC_PLAN_REUSES_INVALIDATED_HYPOTHESIS")
        if not 3 <= len(self.steps) <= 5:
            failures.append("GENERIC_PLAN_DEPTH_INVALID")
        if tuple(step.step_index for step in self.steps) != tuple(
            range(len(self.steps))
        ):
            failures.append("GENERIC_PLAN_STEP_ORDER_INVALID")
        for step in self.steps:
            failures.extend(step.validate())
        if self.steps:
            expected_first = {
                "ACTION_PLAN": "ACTION",
                "PROBE_PLAN": "BOUNDED_PROBE",
                "ROLLBACK_PLAN": "ROLLBACK",
            }.get(self.mode)
            if self.steps[0].operation != expected_first:
                failures.append("GENERIC_PLAN_FIRST_STEP_INVALID")
            if tuple(step.operation for step in self.steps[1:3]) != (
                "REOBSERVE",
                "VERIFY",
            ):
                failures.append("GENERIC_PLAN_VERIFY_SEQUENCE_INVALID")
        if self.mode == "ROLLBACK_PLAN" and self.candidate_id is not None:
            failures.append("GENERIC_PLAN_ROLLBACK_CANDIDATE_PRESENT")
        if self.mode != "ROLLBACK_PLAN" and self.candidate_id is None:
            failures.append("GENERIC_PLAN_ACTION_CANDIDATE_MISSING")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GenericCandidate:
    candidate_id: str
    descriptor: ActionDescriptor
    operation: str
    expected_progress: float
    expected_information_gain: float
    expected_risk: float
    uncertainty: float
    prediction_refs: tuple[str, ...]
    provenance: tuple[str, ...]
    evidence_binding_key: EvidenceBindingKey
    evidence_bindings: tuple[CandidateEvidenceBinding, ...]
    typed_provenance: TypedCandidateProvenance
    plan: GenericPlan
    memory_effects: tuple[str, ...] = ()

    def semantic_identity(self) -> tuple[int, tuple[tuple[str, int], ...]]:
        return (self.descriptor.action_id, self.descriptor.payload_items)

    def validate(self, observation: GenericObservation) -> tuple[str, ...]:
        failures = list(self.descriptor.validate(observation))
        if not _text(self.candidate_id):
            failures.append("GENERIC_CANDIDATE_ID_MISSING")
        if self.operation not in {"ACTION", "BOUNDED_PROBE"}:
            failures.append("GENERIC_CANDIDATE_OPERATION_INVALID")
        for name, value in (
            ("PROGRESS", self.expected_progress),
            ("INFORMATION", self.expected_information_gain),
            ("RISK", self.expected_risk),
            ("UNCERTAINTY", self.uncertainty),
        ):
            if not 0.0 <= value <= 1.0:
                failures.append(f"GENERIC_CANDIDATE_{name}_INVALID")
        if not self.prediction_refs or not self.provenance:
            failures.append("GENERIC_CANDIDATE_PROVENANCE_MISSING")
        failures.extend(self.evidence_binding_key.validate())
        for binding in self.evidence_bindings:
            failures.extend(binding.validate())
            if binding.key != self.evidence_binding_key:
                failures.append("GENERIC_CANDIDATE_EVIDENCE_KEY_MISMATCH")
        failures.extend(self.typed_provenance.validate())
        failures.extend(self.plan.validate())
        if self.plan.candidate_id != self.candidate_id:
            failures.append("GENERIC_CANDIDATE_PLAN_BINDING_INVALID")
        expected_mode = (
            "ACTION_PLAN" if self.operation == "ACTION" else "PROBE_PLAN"
        )
        if self.plan.mode != expected_mode:
            failures.append("GENERIC_CANDIDATE_PLAN_MODE_INVALID")
        if not _sorted_unique_text(self.memory_effects):
            failures.append("GENERIC_CANDIDATE_MEMORY_EFFECTS_INVALID")
        binding_refs = tuple(
            sorted(binding.record_digest for binding in self.evidence_bindings)
        )
        if binding_refs != self.typed_provenance.memory_binding_refs:
            failures.append("GENERIC_CANDIDATE_MEMORY_BINDING_REFS_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class Layer0StageTrace:
    stage: str
    input_digest: str
    output_digest: str
    selected_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GenericComputeCommand:
    command_id: str
    purpose: str
    goal_tokens: tuple[str, ...]
    required_outputs: tuple[str, ...]
    observation_signature: str
    memory_version: int
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class GenericComputeResult:
    command_id: str
    representation: RelationalRepresentation
    memory_citations: tuple[SemanticMemoryCitation, ...]
    hypotheses: tuple[GenericHypothesis, ...]
    predictions: tuple[GenericPrediction, ...]
    candidates: tuple[GenericCandidate, ...]
    stages: tuple[Layer0StageTrace, ...]
    instruction_body_format: str
    instruction_body_version: str
    instruction_body_digest: str
    p_ir_logical_digest: str
    p_ir_execution_digest: str
    l0_abi_version: str
    uncertainty: float
    provenance: tuple[str, ...]
    control_operation: str = ""
    control_instruction_refs: tuple[str, ...] = ()
    control_plan: GenericPlan | None = None
    _digest_cache: str | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def digest(self) -> str:
        cached = self._digest_cache
        if cached is None:
            cached = "generic-compute-result:" + digest_object(self)
            object.__setattr__(
                self,
                "_digest_cache",
                cached,
            )
        return cached

    def validate(self, observation: GenericObservation) -> tuple[str, ...]:
        failures: list[str] = []
        if len(self.hypotheses) < 2:
            failures.append("GENERIC_INDEPENDENT_HYPOTHESES_INSUFFICIENT")
        model_types = {item.model_type for item in self.hypotheses}
        if len(model_types) < 2:
            failures.append("GENERIC_HYPOTHESIS_MODEL_DIVERSITY_MISSING")
        semantic_candidates = {item.semantic_identity() for item in self.candidates}
        if (
            not self.control_operation
            and len(observation.available_actions) >= 2
            and len(semantic_candidates) < 2
        ):
            failures.append("GENERIC_CANDIDATE_DIVERSITY_MISSING")
        for hypothesis in self.hypotheses:
            failures.extend(hypothesis.validate())
        for prediction in self.predictions:
            failures.extend(prediction.validate())
        for candidate in self.candidates:
            failures.extend(candidate.validate(observation))
        hypothesis_ids = {item.hypothesis_id for item in self.hypotheses}
        plans = tuple(item.plan for item in self.candidates)
        if self.control_plan is not None:
            failures.extend(self.control_plan.validate())
            plans = (*plans, self.control_plan)
        for plan in plans:
            if not set(plan.hypothesis_refs).issubset(hypothesis_ids):
                failures.append("GENERIC_PLAN_HYPOTHESIS_BINDING_INVALID")
        plan_ids = tuple(item.plan_id for item in plans)
        if len(plan_ids) != len(set(plan_ids)):
            failures.append("GENERIC_PLAN_ID_DUPLICATED")
        expected_stages = (
            "represent",
            "retrieve",
            "model",
            "predict",
            "candidate",
        )
        if tuple(item.stage for item in self.stages) != expected_stages:
            failures.append("GENERIC_SERIAL_DEPTH_INVALID")
        if not all(
            _text(value)
            for value in (
                self.command_id,
                self.instruction_body_format,
                self.instruction_body_version,
                self.instruction_body_digest,
                self.p_ir_logical_digest,
                self.p_ir_execution_digest,
                self.l0_abi_version,
            )
        ):
            failures.append("GENERIC_COMPUTE_METADATA_INVALID")
        if not 0.0 <= self.uncertainty <= 1.0:
            failures.append("GENERIC_COMPUTE_UNCERTAINTY_INVALID")
        if self.control_operation not in {"", "ROLLBACK"}:
            failures.append("GENERIC_COMPUTE_CONTROL_OPERATION_INVALID")
        if bool(self.control_operation) != bool(self.control_instruction_refs):
            failures.append("GENERIC_COMPUTE_CONTROL_PROVENANCE_INVALID")
        if bool(self.control_operation) != bool(self.control_plan):
            failures.append("GENERIC_COMPUTE_CONTROL_PLAN_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    status: str
    reason_codes: tuple[str, ...] = ()
    required_information: tuple[str, ...] = ()
    next_probe: str = ""


@dataclass(frozen=True, slots=True)
class GenericHDSFrame:
    frame_id: str
    purpose: str
    value_criteria: tuple[str, ...]
    risk_limit: float
    x: tuple[str, ...]
    r: tuple[str, ...]
    mc: tuple[str, ...]
    evidence_boundary: tuple[str, ...]
    resource_budget: int
    authority_boundary: tuple[str, ...]
    unresolved_terms: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    cycle_index: int


@dataclass(frozen=True, slots=True)
class GenericHDSDecision:
    decision_id: str
    assertion_state: str
    operation_state: str
    selected_candidate_id: str | None
    selected_plan_id: str | None
    gate_results: tuple[GateResult, ...]
    reasons: tuple[str, ...]
    next_question: str
    next_observation: str
    required_information: tuple[str, ...]
    next_probe: str
    stop_condition: str
    memory_update_authorized: bool
    external_action_authorized: bool
    frame_digest: str
    compute_result_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.assertion_state not in GENERIC_ASSERTION_STATES:
            failures.append("GENERIC_DECISION_ASSERTION_INVALID")
        if self.operation_state not in GENERIC_DECISION_OPERATIONS:
            failures.append("GENERIC_DECISION_OPERATION_INVALID")
        if not all(
            _text(value)
            for value in (
                self.decision_id,
                self.next_question,
                self.next_observation,
                self.next_probe,
                self.stop_condition,
                self.frame_digest,
                self.compute_result_digest,
            )
        ):
            failures.append("GENERIC_DECISION_REQUIRED_FIELD_MISSING")
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != tuple(f"G{index:02d}" for index in range(16)):
            failures.append("GENERIC_DECISION_GATE_STACK_INCOMPLETE")
        if self.external_action_authorized != (
            self.operation_state in {"EXECUTE", "PROBE"}
            and self.selected_candidate_id is not None
        ):
            failures.append("GENERIC_DECISION_ACTION_AUTHORITY_INVALID")
        if self.operation_state in {"EXECUTE", "PROBE", "ROLLBACK"}:
            if self.selected_plan_id is None:
                failures.append("GENERIC_DECISION_PLAN_MISSING")
        elif self.selected_plan_id is not None:
            failures.append("GENERIC_DECISION_PLAN_UNEXPECTED")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class OutcomeAttribution:
    attribution_id: str
    category: str
    before_signature: str
    after_signature: str
    action_semantic_key: str
    visible_effects: tuple[str, ...]
    progress_delta: int
    terminal_state: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenericCycleTrace:
    cycle_index: int
    observation: GenericObservation
    frame: GenericHDSFrame
    compute_result: GenericComputeResult
    decision: GenericHDSDecision
    selected_candidate: GenericCandidate | None
    result_observation: GenericObservation | None
    attribution: OutcomeAttribution | None
    memory_query_digest: str
    memory_update_digests: tuple[str, ...]
    authority_events: tuple[str, ...]
    failure_signatures: tuple[str, ...]
    trace_digest: str
    runtime_identity_digest: str = ""
    session_lineage_digest: str = ""
    decision_context_digest: str = ""
    experience_event_digests: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GenericRunReport:
    runtime_version: str
    instruction_body_version: str
    initial_observation_digest: str
    final_observation_digest: str
    final_state: str
    progress_count: int
    actions_executed: int
    cycles: tuple[GenericCycleTrace, ...]
    stop_reason: str
    memory_initial_version: int
    memory_final_version: int
    no_fallback_used: bool
    runtime_identity_received: bool
    runtime_identity_digest: str
    session_lineage_digest: str
    episode_handle_digest: str
    identity_boundary_passed: bool
    failure_signatures: tuple[str, ...]
    cycle_trace_digests: tuple[str, ...] = ()

    def digest(self) -> str:
        trace_digests = self.cycle_trace_digests or tuple(
            cycle.trace_digest for cycle in self.cycles
        )
        return "generic-run:" + digest_object(
            {
                "runtime_version": self.runtime_version,
                "instruction_body_version": self.instruction_body_version,
                "initial_observation_digest": (self.initial_observation_digest),
                "final_observation_digest": self.final_observation_digest,
                "final_state": self.final_state,
                "progress_count": self.progress_count,
                "actions_executed": self.actions_executed,
                "cycle_trace_digests": trace_digests,
                "stop_reason": self.stop_reason,
                "memory_initial_version": self.memory_initial_version,
                "memory_final_version": self.memory_final_version,
                "no_fallback_used": self.no_fallback_used,
                "runtime_identity_received": self.runtime_identity_received,
                "runtime_identity_digest": self.runtime_identity_digest,
                "session_lineage_digest": self.session_lineage_digest,
                "episode_handle_digest": self.episode_handle_digest,
                "identity_boundary_passed": self.identity_boundary_passed,
                "failure_signatures": self.failure_signatures,
            }
        )


class GenericEnvironment(Protocol):
    """Environment boundary exposed to GenericAGIRuntime."""

    def observe(self) -> GenericObservation: ...

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation: ...

    def reset_level(self, *, request_id: str) -> GenericObservation: ...


__all__ = [
    "ActionDescriptor",
    "ActionEffectRecord",
    "CandidateEvidenceBinding",
    "GENERIC_ASSERTION_STATES",
    "GENERIC_DECISION_OPERATIONS",
    "GENERIC_TERMINAL_STATES",
    "GENERIC_TYPES_VERSION",
    "GateResult",
    "GenericCandidate",
    "GenericComputeCommand",
    "GenericComputeResult",
    "GenericCycleTrace",
    "GenericEnvironment",
    "GenericHDSDecision",
    "GenericHDSFrame",
    "GenericHypothesis",
    "GenericObservation",
    "GenericPlan",
    "GenericPlanStep",
    "GenericPrediction",
    "GenericRunReport",
    "Layer0StageTrace",
    "ObjectRole",
    "OutcomeAttribution",
    "RelationalRepresentation",
    "EvidenceBindingKey",
    "SemanticMemoryCitation",
    "TypedCandidateProvenance",
]
