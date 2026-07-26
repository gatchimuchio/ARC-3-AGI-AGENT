"""Identity-free contracts for the pre-official GenericAGIRuntime.

These types intentionally do not contain task, game, level, replay, source, or
hidden-state fields. Environment identity belongs to orchestration only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from .schema import digest_object

GENERIC_TYPES_VERSION = "arc3-generic-types-v1"
GENERIC_TERMINAL_STATES = frozenset(
    {"NOT_FINISHED", "WIN", "GAME_OVER", "UNKNOWN"}
)
GENERIC_DECISION_OPERATIONS = frozenset(
    {"EXECUTE", "PROBE", "REOBSERVE", "ROLLBACK", "SUSPEND", "STOP"}
)
GENERIC_ASSERTION_STATES = frozenset({"PASS", "SUSPEND", "FAIL"})


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sorted_unique_text(values: Sequence[str]) -> bool:
    return (
        all(_text(item) for item in values)
        and tuple(values) == tuple(sorted(set(values)))
    )


@dataclass(frozen=True, slots=True)
class GenericObservation:
    """One rendered, identity-free environment observation."""

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

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text(self.signature):
            failures.append("GENERIC_OBSERVATION_SIGNATURE_MISSING")
        if (
            not self.available_actions
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.available_actions
            )
            or self.available_actions
            != tuple(sorted(set(self.available_actions)))
        ):
            failures.append("GENERIC_AVAILABLE_ACTIONS_INVALID")
        if self.terminal_state not in GENERIC_TERMINAL_STATES:
            failures.append("GENERIC_TERMINAL_STATE_INVALID")
        if (
            isinstance(self.progress_count, bool)
            or not isinstance(self.progress_count, int)
            or self.progress_count < 0
        ):
            failures.append("GENERIC_PROGRESS_COUNT_INVALID")
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
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        return "generic-observation:" + digest_object(self)


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
    uncertainty: float
    provenance: tuple[str, ...]

    def digest(self) -> str:
        return "generic-compute-result:" + digest_object(self)

    def validate(self, observation: GenericObservation) -> tuple[str, ...]:
        failures: list[str] = []
        if len(self.hypotheses) < 2:
            failures.append("GENERIC_INDEPENDENT_HYPOTHESES_INSUFFICIENT")
        model_types = {item.model_type for item in self.hypotheses}
        if len(model_types) < 2:
            failures.append("GENERIC_HYPOTHESIS_MODEL_DIVERSITY_MISSING")
        semantic_candidates = {
            item.semantic_identity() for item in self.candidates
        }
        if (
            len(observation.available_actions) >= 2
            and len(semantic_candidates) < 2
        ):
            failures.append("GENERIC_CANDIDATE_DIVERSITY_MISSING")
        for hypothesis in self.hypotheses:
            failures.extend(hypothesis.validate())
        for prediction in self.predictions:
            failures.extend(prediction.validate())
        for candidate in self.candidates:
            failures.extend(candidate.validate(observation))
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
            )
        ):
            failures.append("GENERIC_COMPUTE_METADATA_INVALID")
        if not 0.0 <= self.uncertainty <= 1.0:
            failures.append("GENERIC_COMPUTE_UNCERTAINTY_INVALID")
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
    failure_signatures: tuple[str, ...]

    def digest(self) -> str:
        return "generic-run:" + digest_object(self)


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
    "GenericPrediction",
    "GenericRunReport",
    "Layer0StageTrace",
    "ObjectRole",
    "OutcomeAttribution",
    "RelationalRepresentation",
    "SemanticMemoryCitation",
]
