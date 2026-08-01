"""Deterministic, source-blind PH-D06 ARC3 hypothesis generation.

The generator consumes one canonical PH-D05 teacher trajectory package and
emits a bounded set of executable *candidates*.  It deliberately does not
select, fit, promote, or make a causal claim.  Environment source, hidden
state, identity routing, complete action sequences, and answer literals are
outside this module's input contract.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    content_derived_id,
    logical_content_digest,
)
from .causal_ir import IRNode, TypedInput, build_program, type_check_program
from .interpreter import execute_program
from .ir_types import IRContractError, JsonObject

PHASE_ID: Final = "PH-D06"
GENERATOR_VERSION: Final = "hds-arc3-hypothesis-generator-v1"
CASE_PACKAGE_VERSION: Final = "hds-arc3-hypothesis-case-package-v1"
CANDIDATE_VERSION: Final = "hds-arc3-hypothesis-candidate-v1"
RESOURCE_PROFILE_VERSION: Final = "hds-ph-d06-candidate-budget-v1"

CANDIDATE_FAMILIES: Final = (
    "MINIMAL_MECHANISM",
    "ALTERNATIVE_SELECTOR",
    "ALTERNATIVE_OPERATOR_ORDER",
    "ALTERNATIVE_ADJACENCY_ORDER",
    "NULL_NO_OP",
    "OBSERVATION_ERROR",
    "SURFACE_CORRELATION",
    "OVERFIT",
    "WRONG_TARGET",
    "WRONG_ORDER",
    "DELAYED_EFFECT",
    "DIFFERENT_GOAL",
    "COUNTER_IMMEDIATE_EFFECT",
    "RESET_MODEL",
    "BOUNDED_ENUM_ACTION_PRECONDITION",
    "BOUNDED_ENUM_PAYLOAD_PRECONDITION",
    "ANSWER_COPY_ADVERSARIAL",
    "TRAJECTORY_LOOKUP_ADVERSARIAL",
)

EXECUTABLE_CANDIDATE_COUNT: Final = 16
REJECTED_ADVERSARIAL_COUNT: Final = 2
CANDIDATES_PER_CASE: Final = 18
DEFAULT_MAX_CANDIDATES_PER_CASE: Final = 20
DEFAULT_MAX_TOTAL_CANDIDATES: Final = 500
DEFAULT_MAX_NODES_PER_CANDIDATE: Final = 4


class HypothesisGenerationError(RuntimeError):
    """Stable fail-closed PH-D06 generation error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code + (":" + detail if detail else ""))


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    family: str
    mechanism_family: str
    selector_family: str
    operator_ordering_family: str
    generation_method: str
    non_strawman: bool
    observation_compatible: bool
    probe_field: str
    probe_discriminator: str


def _candidate_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"candidate_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _case_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"case_package_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _object(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise HypothesisGenerationError(code + "_NOT_OBJECT")
    return cast(Mapping[str, object], value)


def _array(value: object, code: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise HypothesisGenerationError(code + "_NOT_ARRAY")
    return cast(Sequence[object], value)


def _integer(value: object, code: str) -> int:
    if type(value) is not int:
        raise HypothesisGenerationError(code + "_NOT_INTEGER")
    return value


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise HypothesisGenerationError(code + "_NOT_STRING")
    return value


def _typed_input(
    name: str,
    type_name: str,
    value: JsonValue,
    provenance: str = "OBSERVED",
) -> TypedInput:
    return TypedInput(
        name=name,
        type_name=type_name,
        value=value,
        provenance=provenance,
    )


def _node(
    node_id: str,
    opcode: str,
    input_refs: Sequence[str],
    output_type: str,
    parameters: JsonObject | None = None,
) -> IRNode:
    return IRNode(
        node_id=node_id,
        opcode=opcode,
        input_refs=tuple(input_refs),
        parameters=parameters or {},
        declared_output_type=output_type,
    )


def _program(
    *,
    inputs: Sequence[TypedInput],
    selector_nodes: Sequence[IRNode] = (),
    precondition_nodes: Sequence[IRNode] = (),
    operator_nodes: Sequence[IRNode] = (),
    output_ref: str,
) -> JsonObject:
    program = build_program(
        domain="ARC3",
        inputs=inputs,
        selector_nodes=selector_nodes,
        precondition_nodes=precondition_nodes,
        operator_nodes=operator_nodes,
        output_refs=(output_ref,),
        claim_scope="PREDICTIVE_HYPOTHESIS",
    )
    checked = type_check_program(program)
    if len(checked.nodes) > DEFAULT_MAX_NODES_PER_CANDIDATE:
        raise HypothesisGenerationError("SUSPEND_RESOURCE", "NODE_BUDGET")
    return program


def _action_record(raw: Mapping[str, object]) -> JsonObject:
    action_id = _integer(raw.get("action_id"), "PH_D06_ACTION_ID")
    raw_payload = _object(raw.get("payload"), "PH_D06_ACTION_PAYLOAD")
    raw_available = _array(
        raw.get("available_actions_before"),
        "PH_D06_AVAILABLE_ACTIONS",
    )
    available_actions = [
        _integer(item, "PH_D06_AVAILABLE_ACTION") for item in raw_available
    ]
    return {
        "action_id": action_id,
        "available_actions": [cast(JsonValue, item) for item in available_actions],
        "payload": cast(JsonObject, dict(raw_payload)),
    }


def _teacher_observation(package: Mapping[str, object]) -> JsonObject:
    if package.get("causal_assertion_count") != 0:
        raise HypothesisGenerationError("PH_D06_CAUSAL_INPUT_FORBIDDEN")
    trajectory = _object(
        package.get("detailed_trajectory"),
        "PH_D06_DETAILED_TRAJECTORY",
    )
    if trajectory.get("domain") != "ARC3":
        raise HypothesisGenerationError("PH_D06_DOMAIN_MISMATCH")
    steps = _array(trajectory.get("steps"), "PH_D06_STEPS")
    if not steps:
        raise HypothesisGenerationError("PH_D06_EMPTY_TRAJECTORY")

    actions: list[JsonObject] = []
    action_counts: Counter[int] = Counter()
    changed_cell_count = 0
    first_progress_step = len(steps) - 1
    progress_observed = False
    completion_count = 0
    payload_action: JsonObject | None = None
    for index, raw_step in enumerate(steps):
        step = _object(raw_step, "PH_D06_STEP")
        action = _action_record(_object(step.get("action"), "PH_D06_STEP_ACTION"))
        actions.append(action)
        action_counts[_integer(action["action_id"], "PH_D06_ACTION_ID")] += 1
        visible_diff = _object(
            step.get("visible_diff"),
            "PH_D06_VISIBLE_DIFF",
        )
        changed_cell_count += _integer(
            visible_diff.get("changed_cell_count"),
            "PH_D06_CHANGED_CELL_COUNT",
        )
        progress_delta = _integer(
            step.get("progress_delta"),
            "PH_D06_PROGRESS_DELTA",
        )
        if progress_delta > 0 and not progress_observed:
            first_progress_step = index
            progress_observed = True
        completion_count = max(
            completion_count,
            _integer(
                step.get("levels_completed_after"),
                "PH_D06_LEVELS_COMPLETED",
            ),
        )
        if payload_action is None and cast(JsonObject, action["payload"]):
            payload_action = action

    declared_action_count = _integer(
        trajectory.get("canonical_success_prefix_action_count"),
        "PH_D06_DECLARED_ACTION_COUNT",
    )
    declared_completion_count = _integer(
        trajectory.get("level_completion_count"),
        "PH_D06_DECLARED_COMPLETION_COUNT",
    )
    if declared_action_count != len(actions):
        raise HypothesisGenerationError("PH_D06_ACTION_COUNT_MISMATCH")
    if declared_completion_count != completion_count:
        raise HypothesisGenerationError("PH_D06_COMPLETION_COUNT_MISMATCH")

    dominant_action_id = min(
        action_counts,
        key=lambda action_id: (-action_counts[action_id], action_id),
    )
    least_action_id = min(
        action_counts,
        key=lambda action_id: (action_counts[action_id], action_id),
    )
    first_action = actions[0]
    least_action = next(
        action for action in actions if action["action_id"] == least_action_id
    )
    selected_payload_action = payload_action or first_action
    before_state: JsonObject = {
        "observed_action_count": len(actions),
        "observed_completion_count": completion_count,
        "progress_observed": progress_observed,
        "visible_change_count": changed_cell_count,
    }
    after_state: JsonObject = {
        **before_state,
        "terminal_observed": trajectory.get("final_terminal_state") == "WIN",
    }
    return {
        "after_state": after_state,
        "before_state": before_state,
        "completion_count": completion_count,
        "dominant_action_id": dominant_action_id,
        "first_action": first_action,
        "first_progress_step": first_progress_step,
        "least_action_id": least_action_id,
        "least_action": least_action,
        "payload_action": selected_payload_action,
        "total_action_count": len(actions),
        "visible_change_count": changed_cell_count,
    }


def _candidate_specs() -> tuple[CandidateSpec, ...]:
    values = (
        (
            "MINIMAL_MECHANISM",
            "ACTION_MATCH",
            "ACTION_ID",
            "NONE",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "action_id",
            "ID_MATCH_VS_ALTERNATIVES",
        ),
        (
            "ALTERNATIVE_SELECTOR",
            "PAYLOAD_MATCH",
            "ACTION_PAYLOAD",
            "NONE",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "payload",
            "PAYLOAD_MATCH_VS_ID_MATCH",
        ),
        (
            "ALTERNATIVE_OPERATOR_ORDER",
            "EVENT_ORDER",
            "EVENT_PAIR",
            "ORDER_BEFORE",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "event_step",
            "BEFORE_VS_ADJACENT",
        ),
        (
            "ALTERNATIVE_ADJACENCY_ORDER",
            "EVENT_ORDER",
            "EVENT_PAIR",
            "ORDER_ADJACENT",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "event_step",
            "ADJACENT_VS_BEFORE",
        ),
        (
            "NULL_NO_OP",
            "INVARIANCE",
            "STATE_PAIR",
            "INVARIANT",
            "DETERMINISTIC_TEMPLATE",
            False,
            True,
            "visible_change_count",
            "CHANGE_VS_NO_CHANGE",
        ),
        (
            "OBSERVATION_ERROR",
            "OBSERVATION_EXCLUSION",
            "STATE_PAIR",
            "EXCLUSION",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "observation_validity",
            "VALID_VS_ERROR",
        ),
        (
            "SURFACE_CORRELATION",
            "DOMINANT_ACTION",
            "ACTION_ID",
            "NONE",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "action_frequency",
            "DOMINANT_VS_RARE",
        ),
        (
            "OVERFIT",
            "COUNT_EQUALITY",
            "STATE_FIELD",
            "GOAL_PREDICATE",
            "DETERMINISTIC_TEMPLATE",
            False,
            True,
            "observed_action_count",
            "COUNT_PERTURBATION",
        ),
        (
            "WRONG_TARGET",
            "HAZARD_TARGET",
            "STATE_FIELD",
            "HAZARD_PREDICATE",
            "DETERMINISTIC_TEMPLATE",
            False,
            False,
            "visible_change_count",
            "PROGRESS_VS_VISIBLE_CHANGE",
        ),
        (
            "WRONG_ORDER",
            "REVERSED_EVENT_ORDER",
            "EVENT_PAIR",
            "ORDER_BEFORE_REVERSED",
            "DETERMINISTIC_TEMPLATE",
            False,
            False,
            "event_step",
            "FORWARD_VS_REVERSED",
        ),
        (
            "DELAYED_EFFECT",
            "DELAY_MODEL",
            "EFFECT_DELAY",
            "DELAYED_EFFECT",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "effect_delay",
            "IMMEDIATE_VS_DELAYED",
        ),
        (
            "DIFFERENT_GOAL",
            "ALTERNATIVE_GOAL",
            "STATE_FIELD",
            "GOAL_PREDICATE",
            "DETERMINISTIC_TEMPLATE",
            True,
            False,
            "observed_completion_count",
            "CURRENT_VS_NEXT_GOAL",
        ),
        (
            "COUNTER_IMMEDIATE_EFFECT",
            "STATE_EFFECT",
            "STATE_EFFECT",
            "PREDICT_EFFECT",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "effect_delay",
            "IMMEDIATE_VS_DELAYED",
        ),
        (
            "RESET_MODEL",
            "RESET_TRANSITION",
            "STATE",
            "RESET_EFFECT",
            "DETERMINISTIC_TEMPLATE",
            True,
            True,
            "reset_marker",
            "RESET_VS_CONTINUE",
        ),
        (
            "BOUNDED_ENUM_ACTION_PRECONDITION",
            "ACTION_PRECONDITION",
            "ACTION_ID",
            "MATCH_THEN_PRECONDITION",
            "BOUNDED_GRAPH_ENUMERATION",
            True,
            True,
            "action_id",
            "PRECONDITION_REMOVAL",
        ),
        (
            "BOUNDED_ENUM_PAYLOAD_PRECONDITION",
            "PAYLOAD_PRECONDITION",
            "ACTION_PAYLOAD",
            "MATCH_THEN_PRECONDITION",
            "BOUNDED_GRAPH_ENUMERATION",
            True,
            True,
            "payload",
            "PRECONDITION_REMOVAL",
        ),
        (
            "ANSWER_COPY_ADVERSARIAL",
            "PRIVILEGED_ANSWER_COPY",
            "FORBIDDEN",
            "REJECTED",
            "ADVERSARIAL_GENERATION",
            False,
            False,
            "answer_literal",
            "DG_08_REJECTION",
        ),
        (
            "TRAJECTORY_LOOKUP_ADVERSARIAL",
            "IDENTITY_ROUTE",
            "FORBIDDEN",
            "REJECTED",
            "ADVERSARIAL_GENERATION",
            False,
            False,
            "trajectory_identity",
            "DG_08_REJECTION",
        ),
    )
    return tuple(CandidateSpec(*value) for value in values)


def _programs(observation: Mapping[str, JsonValue]) -> list[JsonObject]:
    first_action = cast(JsonObject, observation["first_action"])
    least_action = cast(JsonObject, observation["least_action"])
    payload_action = cast(JsonObject, observation["payload_action"])
    before_state = cast(JsonObject, observation["before_state"])
    action_event: JsonObject = {
        "kind": "observed_action",
        "payload": {"action_id": first_action["action_id"]},
        "step": 0,
    }
    progress_event: JsonObject = {
        "kind": "observed_progress",
        "payload": {"completion_count": observation["completion_count"]},
        "step": max(1, cast(int, observation["first_progress_step"])),
    }
    immediate_effect: JsonObject = {
        "changes": {"visible_change_count": observation["visible_change_count"]},
        "delay": 0,
    }
    reset_state: JsonObject = {
        "initial_state": before_state,
        "reset_marker": True,
    }

    action_input = _typed_input("observed_action", "ActionRecord", first_action)
    payload_action_input = _typed_input(
        "payload_action", "ActionRecord", payload_action
    )
    before_input = _typed_input("observed_before", "State", before_state)
    action_event_input = _typed_input("action_event", "Event", action_event)
    progress_event_input = _typed_input("progress_event", "Event", progress_event)
    effect_input = _typed_input("observed_effect", "Effect", immediate_effect)

    result = [
        _program(
            inputs=(
                action_input,
                _typed_input(
                    "first_action_value",
                    "Scalar",
                    cast(int, first_action["action_id"]),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            selector_nodes=(
                _node(
                    "match_action",
                    "MATCH_ACTION_ID",
                    ("observed_action", "first_action_value"),
                    "Boolean",
                ),
            ),
            output_ref="match_action",
        ),
        _program(
            inputs=(
                payload_action_input,
                _typed_input(
                    "payload_predicate",
                    "State",
                    cast(JsonObject, payload_action["payload"]),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            selector_nodes=(
                _node(
                    "match_payload",
                    "MATCH_ACTION_PAYLOAD",
                    ("payload_action", "payload_predicate"),
                    "Boolean",
                ),
            ),
            output_ref="match_payload",
        ),
        _program(
            inputs=(action_event_input, progress_event_input),
            operator_nodes=(
                _node(
                    "before_progress",
                    "ORDER_BEFORE",
                    ("action_event", "progress_event"),
                    "Boolean",
                ),
            ),
            output_ref="before_progress",
        ),
        _program(
            inputs=(action_event_input, progress_event_input),
            operator_nodes=(
                _node(
                    "adjacent_progress",
                    "ORDER_ADJACENT",
                    ("action_event", "progress_event"),
                    "Boolean",
                ),
            ),
            output_ref="adjacent_progress",
        ),
        _program(
            inputs=(
                before_input,
                _typed_input(
                    "comparison_state",
                    "State",
                    before_state,
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            operator_nodes=(
                _node(
                    "no_change",
                    "INVARIANT",
                    ("observed_before", "comparison_state"),
                    "Boolean",
                ),
            ),
            output_ref="no_change",
        ),
        _program(
            inputs=(
                before_input,
                _typed_input(
                    "error_state",
                    "State",
                    {"observation_error": True},
                    "GENERAL_RULE_CONSTANT",
                ),
            ),
            operator_nodes=(
                _node(
                    "exclude_error",
                    "EXCLUSION",
                    ("observed_before", "error_state"),
                    "Boolean",
                ),
            ),
            output_ref="exclude_error",
        ),
        _program(
            inputs=(
                action_input,
                _typed_input(
                    "dominant_action_value",
                    "Scalar",
                    cast(int, observation["dominant_action_id"]),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            selector_nodes=(
                _node(
                    "match_dominant",
                    "MATCH_ACTION_ID",
                    ("observed_action", "dominant_action_value"),
                    "Boolean",
                ),
            ),
            output_ref="match_dominant",
        ),
        _program(
            inputs=(before_input,),
            operator_nodes=(
                _node(
                    "count_goal",
                    "GOAL_PREDICATE",
                    ("observed_before",),
                    "Boolean",
                    {
                        "field": "observed_action_count",
                        "value": observation["total_action_count"],
                    },
                ),
            ),
            output_ref="count_goal",
        ),
        _program(
            inputs=(before_input,),
            operator_nodes=(
                _node(
                    "change_hazard",
                    "HAZARD_PREDICATE",
                    ("observed_before",),
                    "Boolean",
                    {
                        "field": "visible_change_count",
                        "value": observation["visible_change_count"],
                    },
                ),
            ),
            output_ref="change_hazard",
        ),
        _program(
            inputs=(action_event_input, progress_event_input),
            operator_nodes=(
                _node(
                    "reversed_before",
                    "ORDER_BEFORE",
                    ("progress_event", "action_event"),
                    "Boolean",
                ),
            ),
            output_ref="reversed_before",
        ),
        _program(
            inputs=(
                effect_input,
                _typed_input(
                    "observed_delay",
                    "Scalar",
                    max(1, cast(int, observation["first_progress_step"])),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            operator_nodes=(
                _node(
                    "delayed_effect",
                    "DELAYED_EFFECT",
                    ("observed_effect", "observed_delay"),
                    "Effect",
                ),
            ),
            output_ref="delayed_effect",
        ),
        _program(
            inputs=(before_input,),
            operator_nodes=(
                _node(
                    "alternative_goal",
                    "GOAL_PREDICATE",
                    ("observed_before",),
                    "Boolean",
                    {
                        "field": "observed_completion_count",
                        "value": cast(int, observation["completion_count"]) + 1,
                    },
                ),
            ),
            output_ref="alternative_goal",
        ),
        _program(
            inputs=(before_input, effect_input),
            operator_nodes=(
                _node(
                    "immediate_effect",
                    "PREDICT_EFFECT",
                    ("observed_before", "observed_effect"),
                    "State",
                ),
            ),
            output_ref="immediate_effect",
        ),
        _program(
            inputs=(_typed_input("reset_state", "State", reset_state),),
            operator_nodes=(
                _node(
                    "reset_effect",
                    "RESET_EFFECT",
                    ("reset_state",),
                    "State",
                ),
            ),
            output_ref="reset_effect",
        ),
        _program(
            inputs=(
                _typed_input(
                    "enumerated_action",
                    "ActionRecord",
                    least_action,
                ),
                _typed_input(
                    "rare_action_value",
                    "Scalar",
                    cast(int, observation["least_action_id"]),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            selector_nodes=(
                _node(
                    "enumerated_action_match",
                    "MATCH_ACTION_ID",
                    ("enumerated_action", "rare_action_value"),
                    "Boolean",
                ),
            ),
            precondition_nodes=(
                _node(
                    "enumerated_action_precondition",
                    "PRECONDITION",
                    ("enumerated_action_match",),
                    "Boolean",
                ),
            ),
            output_ref="enumerated_action_precondition",
        ),
        _program(
            inputs=(
                payload_action_input,
                _typed_input(
                    "enumerated_payload",
                    "State",
                    cast(JsonObject, payload_action["payload"]),
                    "DETERMINISTIC_DERIVATION",
                ),
            ),
            selector_nodes=(
                _node(
                    "enumerated_payload_match",
                    "MATCH_ACTION_PAYLOAD",
                    ("payload_action", "enumerated_payload"),
                    "Boolean",
                ),
            ),
            precondition_nodes=(
                _node(
                    "enumerated_payload_precondition",
                    "PRECONDITION",
                    ("enumerated_payload_match",),
                    "Boolean",
                ),
            ),
            output_ref="enumerated_payload_precondition",
        ),
    ]
    if len(result) != EXECUTABLE_CANDIDATE_COUNT:
        raise AssertionError("PH_D06_INTERNAL_EXECUTABLE_COUNT_DRIFT")
    return result


def _execution_digest(program: Mapping[str, object]) -> str:
    result = execute_program(program).as_json()
    return logical_content_digest(
        "hds-ph-d06-execution-witness",
        result,
        policy=DigestExclusionPolicy(),
    )


def _finalize_candidate(candidate: JsonObject) -> JsonObject:
    candidate["candidate_id"] = content_derived_id(
        "hds-hypothesis-candidate-id",
        candidate,
        policy=_candidate_policy(),
    )
    candidate["content_digest"] = logical_content_digest(
        "hds-hypothesis-candidate",
        candidate,
        policy=_candidate_policy(),
    )
    return candidate


def _executable_candidate(
    spec: CandidateSpec,
    program: JsonObject,
    *,
    ordinal: int,
    teacher_case_ref: str,
) -> JsonObject:
    checked = type_check_program(program)
    candidate: JsonObject = {
        "schema_version": CANDIDATE_VERSION,
        "candidate_id": "",
        "phase_id": PHASE_ID,
        "ordinal": ordinal,
        "teacher_case_ref": teacher_case_ref,
        "candidate_family": spec.family,
        "mechanism_family": spec.mechanism_family,
        "selector_family": spec.selector_family,
        "operator_ordering_family": spec.operator_ordering_family,
        "generation_method": spec.generation_method,
        "candidate_state": "PENDING_PH_D07A",
        "fit_status": "NOT_EVALUATED",
        "causal_assertion_state": "NOT_ASSERTED",
        "promotion_state": "NOT_PROMOTED",
        "automatic_adoption": False,
        "executable": True,
        "rejected": False,
        "rejection_code": None,
        "non_strawman": spec.non_strawman,
        "observation_compatible": spec.observation_compatible,
        "distinguishing_intervention": {
            "probe_kind": "PH_D07B_OBLIGATION",
            "mutated_observation_field": spec.probe_field,
            "expected_discriminator": spec.probe_discriminator,
            "execution_state": "NOT_RUN",
        },
        "hypothesis_ir": program,
        "ir_node_count": len(checked.nodes),
        "ir_resource_cost": checked.resource_cost,
        "execution_status": "PASS",
        "execution_witness_digest": _execution_digest(program),
        "rejected_payload_commitment": None,
        "digest_excluded_fields": ["candidate_id", "content_digest"],
        "content_digest": "",
    }
    return _finalize_candidate(candidate)


def _rejected_candidate(
    spec: CandidateSpec,
    base_program: JsonObject,
    *,
    ordinal: int,
    teacher_case_ref: str,
    forbidden_key: str,
    expected_code: str,
) -> JsonObject:
    invalid = copy.deepcopy(base_program)
    invalid[forbidden_key] = {
        "redacted": True,
        "stored_only_as_commitment": True,
    }
    commitment = logical_content_digest(
        "hds-rejected-candidate-payload-commitment",
        invalid,
        policy=DigestExclusionPolicy(),
    )
    observed_code = "NO_REJECTION"
    try:
        type_check_program(invalid)
    except IRContractError as exc:
        observed_code = exc.code
    if observed_code != expected_code:
        raise HypothesisGenerationError(
            "PH_D06_ADVERSARIAL_REJECTION_MISMATCH",
            spec.family + ":" + observed_code,
        )
    candidate: JsonObject = {
        "schema_version": CANDIDATE_VERSION,
        "candidate_id": "",
        "phase_id": PHASE_ID,
        "ordinal": ordinal,
        "teacher_case_ref": teacher_case_ref,
        "candidate_family": spec.family,
        "mechanism_family": spec.mechanism_family,
        "selector_family": spec.selector_family,
        "operator_ordering_family": spec.operator_ordering_family,
        "generation_method": spec.generation_method,
        "candidate_state": "REJECTED_DG_08",
        "fit_status": "NOT_ELIGIBLE",
        "causal_assertion_state": "NOT_ASSERTED",
        "promotion_state": "NOT_PROMOTED",
        "automatic_adoption": False,
        "executable": False,
        "rejected": True,
        "rejection_code": observed_code,
        "non_strawman": spec.non_strawman,
        "observation_compatible": spec.observation_compatible,
        "distinguishing_intervention": {
            "probe_kind": "STATIC_DG_08_REJECTION",
            "mutated_observation_field": spec.probe_field,
            "expected_discriminator": spec.probe_discriminator,
            "execution_state": "PASS",
        },
        "hypothesis_ir": None,
        "ir_node_count": 0,
        "ir_resource_cost": 0,
        "execution_status": "REJECTED_BEFORE_EXECUTION",
        "execution_witness_digest": None,
        "rejected_payload_commitment": commitment,
        "digest_excluded_fields": ["candidate_id", "content_digest"],
        "content_digest": "",
    }
    return _finalize_candidate(candidate)


def teacher_case_ref(package: Mapping[str, object]) -> str:
    trajectory = _object(
        package.get("detailed_trajectory"),
        "PH_D06_DETAILED_TRAJECTORY",
    )
    binding: JsonObject = {
        "canonical_trajectory_digest": _string(
            trajectory.get("canonical_trajectory_digest"),
            "PH_D06_CANONICAL_TRAJECTORY_DIGEST",
        ),
        "package_content_digest": _string(
            package.get("content_digest"),
            "PH_D06_PACKAGE_CONTENT_DIGEST",
        ),
    }
    return logical_content_digest(
        "hds-teacher-case-ref",
        binding,
        policy=DigestExclusionPolicy(),
    )


def generate_case_candidates(
    package: Mapping[str, object],
    *,
    max_candidates_per_case: int = DEFAULT_MAX_CANDIDATES_PER_CASE,
) -> JsonObject:
    """Generate exactly one bounded, non-adopted candidate package."""

    if max_candidates_per_case < CANDIDATES_PER_CASE:
        raise HypothesisGenerationError("SUSPEND_RESOURCE", "CASE_BUDGET")
    observation = _teacher_observation(package)
    case_ref = teacher_case_ref(package)
    specs = _candidate_specs()
    programs = _programs(observation)
    candidates = [
        _executable_candidate(
            specs[index],
            program,
            ordinal=index,
            teacher_case_ref=case_ref,
        )
        for index, program in enumerate(programs)
    ]
    candidates.extend(
        (
            _rejected_candidate(
                specs[16],
                programs[0],
                ordinal=16,
                teacher_case_ref=case_ref,
                forbidden_key="answer_map",
                expected_code="IR_ANSWER_COPY_FORBIDDEN",
            ),
            _rejected_candidate(
                specs[17],
                programs[0],
                ordinal=17,
                teacher_case_ref=case_ref,
                forbidden_key="trajectory_lookup",
                expected_code="IR_IDENTITY_ROUTING_FORBIDDEN",
            ),
        )
    )
    if len(candidates) != CANDIDATES_PER_CASE:
        raise AssertionError("PH_D06_INTERNAL_CANDIDATE_COUNT_DRIFT")
    if tuple(candidate["candidate_family"] for candidate in candidates) != (
        CANDIDATE_FAMILIES
    ):
        raise AssertionError("PH_D06_INTERNAL_CANDIDATE_FAMILY_DRIFT")

    executable_count = sum(candidate["executable"] is True for candidate in candidates)
    rejected_count = sum(candidate["rejected"] is True for candidate in candidates)
    non_strawman_count = sum(
        candidate["non_strawman"] is True for candidate in candidates
    )
    observation_compatible_count = sum(
        candidate["observation_compatible"] is True for candidate in candidates
    )
    selector_families = sorted(
        {
            cast(str, candidate["selector_family"])
            for candidate in candidates
            if candidate["executable"] is True
        }
    )
    ordering_families = sorted(
        {
            cast(str, candidate["operator_ordering_family"])
            for candidate in candidates
            if candidate["executable"] is True
        }
    )
    source_provenance: JsonObject = {
        "canonical_trajectory_digest": _string(
            _object(
                package.get("detailed_trajectory"),
                "PH_D06_DETAILED_TRAJECTORY",
            ).get("canonical_trajectory_digest"),
            "PH_D06_CANONICAL_TRAJECTORY_DIGEST",
        ),
        "source_package_content_digest": _string(
            package.get("content_digest"),
            "PH_D06_PACKAGE_CONTENT_DIGEST",
        ),
        "normalization_certificate_digest": _string(
            _object(
                package.get("normalization_certificate"),
                "PH_D06_NORMALIZATION_CERTIFICATE",
            ).get("content_digest"),
            "PH_D06_NORMALIZATION_CERTIFICATE_DIGEST",
        ),
        "identity_fields_consumed_for_routing": 0,
        "complete_action_sequence_copied": False,
        "environment_source_access_count": 0,
        "hidden_state_access_count": 0,
    }
    case_package: JsonObject = {
        "schema_version": CASE_PACKAGE_VERSION,
        "case_package_id": "",
        "phase_id": PHASE_ID,
        "teacher_case_ref": case_ref,
        "generator_version": GENERATOR_VERSION,
        "source_provenance": source_provenance,
        "candidate_families": cast(list[JsonValue], list(CANDIDATE_FAMILIES)),
        "candidates": cast(list[JsonValue], candidates),
        "candidate_count": len(candidates),
        "executable_candidate_count": executable_count,
        "rejected_adversarial_count": rejected_count,
        "candidate_adoption_count": 0,
        "automatic_adoption_forbidden": True,
        "alternative_adequacy": {
            "status": "PASS",
            "fit_evaluation_status": "DEFERRED_TO_PH_D07A",
            "non_strawman_count": non_strawman_count,
            "strawman_count": len(candidates) - non_strawman_count,
            "strawman_ratio_ppm": (
                (len(candidates) - non_strawman_count) * 1_000_000 // len(candidates)
            ),
            "observation_compatible_competitor_count": (observation_compatible_count),
            "selector_family_count": len(selector_families),
            "selector_families": cast(list[JsonValue], selector_families),
            "operator_ordering_family_count": len(ordering_families),
            "operator_ordering_families": cast(list[JsonValue], ordering_families),
            "distinguishing_intervention_obligation_count": len(candidates),
            "answer_copy_generated_and_rejected_count": 1,
            "trajectory_lookup_generated_and_rejected_count": 1,
            "selected_candidate_count": 0,
        },
        "resource_budget": {
            "profile_version": RESOURCE_PROFILE_VERSION,
            "max_candidates_per_case": max_candidates_per_case,
            "observed_candidates_per_case": len(candidates),
            "max_nodes_per_candidate": DEFAULT_MAX_NODES_PER_CANDIDATE,
            "overflow_policy": "SUSPEND_WITHOUT_PARTIAL_AUTHORITATIVE_CORPUS",
            "overflow_count": 0,
        },
        "gates": {
            "DG-03": "PASS_TYPED_EXECUTABLE_IR",
            "DG-04": "PASS_MULTIPLE_COMPETING_HYPOTHESES",
            "DG-05": "PASS_ALTERNATIVE_ADEQUACY",
            "DG-08": "PASS_PRIVILEGED_ADVERSARIAL_REJECTION",
            "DG-12": "PASS_CONTENT_BOUND_DETERMINISM",
        },
        "phase_boundaries": {
            "fit_execution_count": 0,
            "real_intervention_execution_count": 0,
            "causal_assertion_count": 0,
            "rule_promotion_count": 0,
            "bridge_runtime_capability_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "claim_boundary": (
            "Executable competing hypotheses only; no fit, necessity, "
            "irreversibility, causal, promotion, Bridge, or Runtime claim."
        ),
        "digest_excluded_fields": ["case_package_id", "content_digest"],
        "content_digest": "",
    }
    case_package["case_package_id"] = content_derived_id(
        "hds-hypothesis-case-package-id",
        case_package,
        policy=_case_policy(),
    )
    case_package["content_digest"] = logical_content_digest(
        "hds-hypothesis-case-package",
        case_package,
        policy=_case_policy(),
    )
    return case_package


def validate_corpus_budget(case_count: int) -> None:
    if case_count < 1:
        raise HypothesisGenerationError("PH_D06_CASE_COUNT_INVALID")
    candidate_count = case_count * CANDIDATES_PER_CASE
    if candidate_count > DEFAULT_MAX_TOTAL_CANDIDATES:
        raise HypothesisGenerationError("SUSPEND_RESOURCE", "CORPUS_BUDGET")


__all__ = [
    "CANDIDATES_PER_CASE",
    "CANDIDATE_FAMILIES",
    "DEFAULT_MAX_CANDIDATES_PER_CASE",
    "DEFAULT_MAX_TOTAL_CANDIDATES",
    "EXECUTABLE_CANDIDATE_COUNT",
    "GENERATOR_VERSION",
    "HypothesisGenerationError",
    "REJECTED_ADVERSARIAL_COUNT",
    "generate_case_candidates",
    "teacher_case_ref",
    "validate_corpus_budget",
]
