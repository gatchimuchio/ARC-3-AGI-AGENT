"""PH-D07A extensional exact-fit accounting for ARC3 HypothesisIR.

The evaluator consumes immutable PH-D05 canonical teacher trajectories and
immutable PH-D06 candidate packages.  It rebinds only inputs explicitly marked
``OBSERVED`` and compares each candidate's declared output axis against an
independently derived teacher observation for every step in that candidate's
trajectory.  Fit is recorded separately from causal support, selection,
intervention, promotion, Bridge, and Runtime state.
"""

from __future__ import annotations

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
from .causal_ir import TypeCheckedProgram, type_check_program
from .hypothesis_generation import teacher_case_ref
from .interpreter import execute_type_checked_program
from .ir_types import IRContractError, JsonObject, validate_typed_value
from .verification import CanonicalExactComparator

PHASE_ID: Final = "PH-D07A"
EVALUATOR_VERSION: Final = "hds-arc3-extensional-fit-evaluator-v1"
CASE_RESULT_VERSION: Final = "hds-arc3-extensional-fit-case-v1"
FIT_RESULT_VERSION: Final = "hds-arc3-extensional-fit-result-v1"
FIT_AXES: Final = (
    "STEP_PRECONDITION",
    "RAW_ACTION_MATCH",
    "PREDICTED_EFFECT",
    "STATE_ABSTRACTION",
    "TRANSITION",
    "ORDERING",
    "TERMINAL_CONTRIBUTION",
)
EXPECTED_CANDIDATES_PER_CASE: Final = 18
EXPECTED_EXECUTABLE_PER_CASE: Final = 16
EXPECTED_REJECTED_PER_CASE: Final = 2
MISMATCH_SAMPLE_LIMIT: Final = 16


class ExactFitError(RuntimeError):
    """Stable fail-closed PH-D07A evaluation error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code + (":" + detail if detail else ""))


@dataclass(frozen=True, slots=True)
class StepContext:
    """Identity-free observed projection for one canonical teacher step."""

    step_index: int
    action: JsonObject
    before_state: JsonObject
    after_state: JsonObject
    observed_effect: JsonObject
    action_event: JsonObject
    progress_event: JsonObject
    reset_state: JsonObject
    action_precedes_next_progress: bool
    terminal_state_after: str


def _object(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExactFitError(code + "_NOT_OBJECT")
    return cast(Mapping[str, object], value)


def _array(value: object, code: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ExactFitError(code + "_NOT_ARRAY")
    return cast(Sequence[object], value)


def _integer(value: object, code: str) -> int:
    if type(value) is not int:
        raise ExactFitError(code + "_NOT_INTEGER")
    return value


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExactFitError(code + "_NOT_STRING")
    return value


def _fit_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"fit_result_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _case_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"fit_case_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def _finalize(
    value: JsonObject,
    *,
    id_field: str,
    id_namespace: str,
    digest_namespace: str,
    policy: DigestExclusionPolicy,
) -> JsonObject:
    value[id_field] = content_derived_id(
        id_namespace,
        value,
        policy=policy,
    )
    value["content_digest"] = logical_content_digest(
        digest_namespace,
        value,
        policy=policy,
    )
    return value


def _action_record(raw_step: Mapping[str, object]) -> JsonObject:
    raw = _object(raw_step.get("action"), "PH_D07A_STEP_ACTION")
    raw_payload = _object(raw.get("payload"), "PH_D07A_ACTION_PAYLOAD")
    raw_available = _array(
        raw.get("available_actions_before"),
        "PH_D07A_AVAILABLE_ACTIONS",
    )
    action = {
        "action_id": _integer(raw.get("action_id"), "PH_D07A_ACTION_ID"),
        "available_actions": [
            _integer(item, "PH_D07A_AVAILABLE_ACTION")
            for item in raw_available
        ],
        "payload": dict(raw_payload),
    }
    return cast(
        JsonObject,
        validate_typed_value("ActionRecord", action),
    )


def _state(
    *,
    action_count: int,
    completion_count: int,
    visible_change_count: int,
    terminal_state: str,
) -> JsonObject:
    return {
        "observed_action_count": action_count,
        "observed_completion_count": completion_count,
        "progress_observed": completion_count > 0,
        "terminal_observed": terminal_state == "WIN",
        "visible_change_count": visible_change_count,
    }


def _effect(
    before: Mapping[str, JsonValue],
    after: Mapping[str, JsonValue],
) -> JsonObject:
    changes: JsonObject = {
        key: value for key, value in after.items() if before.get(key) != value
    }
    return cast(
        JsonObject,
        validate_typed_value(
            "Effect",
            {"changes": changes, "delay": 0},
        ),
    )


def _step_contexts(teacher_package: Mapping[str, object]) -> tuple[StepContext, ...]:
    if teacher_package.get("causal_assertion_count") != 0:
        raise ExactFitError("PH_D07A_CAUSAL_SOURCE_FORBIDDEN")
    trajectory = _object(
        teacher_package.get("detailed_trajectory"),
        "PH_D07A_DETAILED_TRAJECTORY",
    )
    if trajectory.get("domain") != "ARC3":
        raise ExactFitError("PH_D07A_DOMAIN_MISMATCH")
    raw_steps = _array(trajectory.get("steps"), "PH_D07A_STEPS")
    if not raw_steps:
        raise ExactFitError("PH_D07A_EMPTY_TRAJECTORY")

    steps = [_object(item, "PH_D07A_STEP") for item in raw_steps]
    progress_indices = [
        index
        for index, step in enumerate(steps)
        if _integer(step.get("progress_delta"), "PH_D07A_PROGRESS_DELTA") > 0
    ]
    if not progress_indices:
        raise ExactFitError("PH_D07A_PROGRESS_EVENT_MISSING")

    initial_terminal = _string(
        steps[0].get("terminal_state_before"),
        "PH_D07A_INITIAL_TERMINAL",
    )
    initial_completion = _integer(
        steps[0].get("levels_completed_before"),
        "PH_D07A_INITIAL_COMPLETION",
    )
    initial_state = _state(
        action_count=0,
        completion_count=initial_completion,
        visible_change_count=0,
        terminal_state=initial_terminal,
    )

    result: list[StepContext] = []
    cumulative_visible_change = 0
    progress_cursor = 0
    for index, step in enumerate(steps):
        while (
            progress_cursor < len(progress_indices)
            and progress_indices[progress_cursor] < index
        ):
            progress_cursor += 1
        next_progress = (
            progress_indices[progress_cursor]
            if progress_cursor < len(progress_indices)
            else index
        )
        progress_step = steps[next_progress]
        action = _action_record(step)
        terminal_before = _string(
            step.get("terminal_state_before"),
            "PH_D07A_TERMINAL_BEFORE",
        )
        terminal_after = _string(
            step.get("terminal_state_after"),
            "PH_D07A_TERMINAL_AFTER",
        )
        completion_before = _integer(
            step.get("levels_completed_before"),
            "PH_D07A_COMPLETION_BEFORE",
        )
        completion_after = _integer(
            step.get("levels_completed_after"),
            "PH_D07A_COMPLETION_AFTER",
        )
        visible_diff = _object(
            step.get("visible_diff"),
            "PH_D07A_VISIBLE_DIFF",
        )
        changed_cells = _integer(
            visible_diff.get("changed_cell_count"),
            "PH_D07A_CHANGED_CELL_COUNT",
        )
        before_state = _state(
            action_count=index,
            completion_count=completion_before,
            visible_change_count=cumulative_visible_change,
            terminal_state=terminal_before,
        )
        cumulative_visible_change += changed_cells
        after_state = _state(
            action_count=index + 1,
            completion_count=completion_after,
            visible_change_count=cumulative_visible_change,
            terminal_state=terminal_after,
        )
        action_event: JsonObject = {
            "kind": "observed_action",
            "payload": {
                "action_id": action["action_id"],
                "payload": action["payload"],
            },
            "step": index,
        }
        progress_event: JsonObject = {
            "kind": "observed_progress",
            "payload": {
                "completion_count": _integer(
                    progress_step.get("levels_completed_after"),
                    "PH_D07A_PROGRESS_COMPLETION",
                )
            },
            "step": next_progress,
        }
        raw_action = _object(step.get("action"), "PH_D07A_STEP_ACTION")
        reset_state: JsonObject = {
            "initial_state": initial_state,
            "reset_marker": (
                raw_action.get("full_reset") is True or action["action_id"] == 0
            ),
        }
        result.append(
            StepContext(
                step_index=index,
                action=action,
                before_state=before_state,
                after_state=after_state,
                observed_effect=_effect(before_state, after_state),
                action_event=cast(
                    JsonObject,
                    validate_typed_value("Event", action_event),
                ),
                progress_event=cast(
                    JsonObject,
                    validate_typed_value("Event", progress_event),
                ),
                reset_state=reset_state,
                action_precedes_next_progress=index < next_progress,
                terminal_state_after=terminal_after,
            )
        )

    declared_count = _integer(
        trajectory.get("canonical_success_prefix_action_count"),
        "PH_D07A_DECLARED_ACTION_COUNT",
    )
    if declared_count != len(result):
        raise ExactFitError("PH_D07A_ACTION_COUNT_MISMATCH")
    return tuple(result)


def _observed_binding(name: str, context: StepContext) -> JsonValue:
    if name in {
        "enumerated_action",
        "observed_action",
        "payload_action",
    }:
        return context.action
    if name == "observed_before":
        return context.before_state
    if name == "observed_effect":
        return context.observed_effect
    if name == "action_event":
        return context.action_event
    if name == "progress_event":
        return context.progress_event
    if name == "reset_state":
        return context.reset_state
    raise ExactFitError("PH_D07A_OBSERVED_BINDING_UNSUPPORTED", name)


def _observed_bindings(
    checked: TypeCheckedProgram,
    context: StepContext,
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for raw_input in checked.inputs:
        if raw_input.provenance != "OBSERVED":
            continue
        result[raw_input.name] = validate_typed_value(
            raw_input.type_name,
            _observed_binding(raw_input.name, context),
        )
    return result


def _output_node(checked: TypeCheckedProgram) -> tuple[str, str, str]:
    if len(checked.output_refs) != 1:
        raise ExactFitError("PH_D07A_SINGLE_OUTPUT_REQUIRED")
    output_ref = checked.output_refs[0]
    node = next((item for item in checked.nodes if item.node_id == output_ref), None)
    if node is None:
        raise ExactFitError("PH_D07A_OUTPUT_NODE_MISSING")
    output_type = checked.reference_types[output_ref]
    return output_ref, node.opcode, output_type


def _axis(opcode: str) -> str:
    if opcode in {"MATCH_ACTION_ID", "MATCH_ACTION_PAYLOAD"}:
        return "RAW_ACTION_MATCH"
    if opcode in {"PRECONDITION", "EXCLUSION"}:
        return "STEP_PRECONDITION"
    if opcode == "DELAYED_EFFECT":
        return "PREDICTED_EFFECT"
    if opcode == "INVARIANT":
        return "STATE_ABSTRACTION"
    if opcode in {"PREDICT_EFFECT", "RESET_EFFECT", "PREDICT_TRANSITION"}:
        return "TRANSITION"
    if opcode in {"ORDER_BEFORE", "ORDER_ADJACENT"}:
        return "ORDERING"
    if opcode in {"GOAL_PREDICATE", "HAZARD_PREDICATE"}:
        return "TERMINAL_CONTRIBUTION"
    raise ExactFitError("PH_D07A_OUTPUT_OPCODE_UNSUPPORTED", opcode)


def _expected(
    *,
    axis: str,
    opcode: str,
    context: StepContext,
) -> tuple[str, JsonValue]:
    if axis in {"RAW_ACTION_MATCH", "STEP_PRECONDITION"}:
        return "Boolean", True
    if axis == "PREDICTED_EFFECT":
        return "Effect", context.observed_effect
    if axis == "STATE_ABSTRACTION":
        return "Boolean", context.before_state == context.after_state
    if axis == "TRANSITION":
        return "State", context.after_state
    if axis == "ORDERING":
        return "Boolean", context.action_precedes_next_progress
    if axis == "TERMINAL_CONTRIBUTION":
        if opcode == "GOAL_PREDICATE":
            return "Boolean", context.terminal_state_after == "WIN"
        return "Boolean", context.terminal_state_after == "GAME_OVER"
    raise AssertionError("PH_D07A_INTERNAL_AXIS_DRIFT:" + axis)


def _mismatch_sample(
    *,
    step_index: int,
    axis: str,
    expected_digest: str | None,
    actual_digest: str | None,
    error_code: str | None,
) -> JsonObject:
    return {
        "actual_digest": actual_digest,
        "axis": axis,
        "error_code": error_code,
        "expected_digest": expected_digest,
        "step_index": step_index,
    }


def _rejected_fit_result(candidate: Mapping[str, object]) -> JsonObject:
    result: JsonObject = {
        "schema_version": FIT_RESULT_VERSION,
        "fit_result_id": "",
        "phase_id": PHASE_ID,
        "candidate_id": _string(
            candidate.get("candidate_id"),
            "PH_D07A_CANDIDATE_ID",
        ),
        "candidate_content_digest": _string(
            candidate.get("content_digest"),
            "PH_D07A_CANDIDATE_DIGEST",
        ),
        "candidate_family": _string(
            candidate.get("candidate_family"),
            "PH_D07A_CANDIDATE_FAMILY",
        ),
        "evaluation_eligibility": "NOT_ELIGIBLE_DG_08",
        "comparison_axis": None,
        "teacher_step_count": 0,
        "evaluated_step_count": 0,
        "matched_step_count": 0,
        "mismatch_step_count": 0,
        "execution_error_count": 0,
        "resource_suspension_count": 0,
        "positive_activation_count": 0,
        "positive_activation_observed": False,
        "fit_status": "NOT_ELIGIBLE_DG_08",
        "exact_fit": False,
        "mechanism_support_state": "INCONCLUSIVE",
        "causal_support_state": "NOT_ESTABLISHED",
        "candidate_selection_state": "UNSELECTED",
        "candidate_adoption_state": "NOT_ADOPTED",
        "promotion_state": "NOT_PROMOTED",
        "intervention_execution_state": "NOT_RUN_PH_D07A",
        "rejection_code": _string(
            candidate.get("rejection_code"),
            "PH_D07A_REJECTION_CODE",
        ),
        "comparison_trace_digest": None,
        "error_code_counts": {},
        "mismatch_samples": [],
        "claim_boundary": (
            "Privilege-rejected candidate remains ineligible for fit even if "
            "a forbidden lookup could reproduce the observation."
        ),
        "digest_excluded_fields": ["fit_result_id", "content_digest"],
        "content_digest": "",
    }
    return _finalize(
        result,
        id_field="fit_result_id",
        id_namespace="hds-arc3-extensional-fit-result-id",
        digest_namespace="hds-arc3-extensional-fit-result",
        policy=_fit_policy(),
    )


def evaluate_candidate(
    candidate: Mapping[str, object],
    contexts: Sequence[StepContext],
) -> JsonObject:
    """Recompute one candidate's extensional fit without selecting it."""

    if candidate.get("rejected") is True:
        if (
            candidate.get("candidate_state") != "REJECTED_DG_08"
            or candidate.get("executable") is not False
            or candidate.get("hypothesis_ir") is not None
        ):
            raise ExactFitError("PH_D07A_REJECTED_CANDIDATE_STATE_MISMATCH")
        return _rejected_fit_result(candidate)
    if (
        candidate.get("executable") is not True
        or candidate.get("rejected") is not False
    ):
        raise ExactFitError("PH_D07A_ADMITTED_CANDIDATE_STATE_MISMATCH")
    program = _object(
        candidate.get("hypothesis_ir"),
        "PH_D07A_HYPOTHESIS_IR",
    )
    checked = type_check_program(program)
    output_ref, opcode, output_type = _output_node(checked)
    axis = _axis(opcode)

    comparator = CanonicalExactComparator()
    matched = 0
    mismatched = 0
    errors: Counter[str] = Counter()
    suspensions = 0
    positive_activations = 0
    mismatch_samples: list[JsonValue] = []
    trace_rows: list[JsonValue] = []
    for context in contexts:
        expected_type, expected = _expected(
            axis=axis,
            opcode=opcode,
            context=context,
        )
        if expected_type != output_type:
            raise ExactFitError(
                "PH_D07A_OUTPUT_TYPE_MISMATCH",
                opcode + ":" + output_type + ":" + expected_type,
            )
        expected_digest = logical_content_digest(
            "hds-ph-d07a-expected-observation",
            {"type": expected_type, "value": expected},
            policy=DigestExclusionPolicy(),
        )
        actual_digest: str | None = None
        error_code: str | None = None
        equal = False
        try:
            execution = execute_type_checked_program(
                checked,
                _observed_bindings(checked, context),
            )
            if execution.status == "SUSPEND_RESOURCE":
                suspensions += 1
                error_code = "SUSPEND_RESOURCE"
            elif execution.status != "PASS":
                error_code = "PH_D07A_EXECUTION_STATUS_" + execution.status
                errors[error_code] += 1
            else:
                actual = execution.outputs[output_ref]
                comparison = comparator.compare(
                    type_name=expected_type,
                    expected=expected,
                    actual=actual,
                )
                equal = comparison.equal
                expected_digest = comparison.expected_digest
                actual_digest = comparison.actual_digest
                if type(actual) is bool and actual is True:
                    positive_activations += 1
        except IRContractError as exc:
            error_code = exc.code
            errors[error_code] += 1
        if equal:
            matched += 1
        else:
            mismatched += 1
            if len(mismatch_samples) < MISMATCH_SAMPLE_LIMIT:
                mismatch_samples.append(
                    _mismatch_sample(
                        step_index=context.step_index,
                        axis=axis,
                        expected_digest=expected_digest,
                        actual_digest=actual_digest,
                        error_code=error_code,
                    )
                )
        trace_rows.append(
            {
                "actual_digest": actual_digest,
                "equal": equal,
                "error_code": error_code,
                "expected_digest": expected_digest,
                "step_index": context.step_index,
            }
        )

    exact = mismatched == 0 and not errors and suspensions == 0
    if suspensions:
        fit_status = "INCONCLUSIVE_RESOURCE"
        support_state = "INCONCLUSIVE"
    elif not exact:
        fit_status = "FALSIFIED"
        support_state = "FALSIFIED"
    else:
        fit_status = "LOCAL_EXACT_FIT"
        support_state = (
            "OBSERVED_COMPATIBLE"
            if output_type == "Boolean" and positive_activations == 0
            else "LOCAL_EXACT_FIT"
        )

    result: JsonObject = {
        "schema_version": FIT_RESULT_VERSION,
        "fit_result_id": "",
        "phase_id": PHASE_ID,
        "candidate_id": _string(
            candidate.get("candidate_id"),
            "PH_D07A_CANDIDATE_ID",
        ),
        "candidate_content_digest": _string(
            candidate.get("content_digest"),
            "PH_D07A_CANDIDATE_DIGEST",
        ),
        "candidate_family": _string(
            candidate.get("candidate_family"),
            "PH_D07A_CANDIDATE_FAMILY",
        ),
        "generation_observation_compatible_label": (
            candidate.get("observation_compatible") is True
        ),
        "evaluation_eligibility": "ELIGIBLE_EXECUTABLE_IR",
        "comparison_axis": axis,
        "output_opcode": opcode,
        "output_type": output_type,
        "teacher_step_count": len(contexts),
        "evaluated_step_count": len(contexts),
        "matched_step_count": matched,
        "mismatch_step_count": mismatched,
        "execution_error_count": sum(errors.values()),
        "resource_suspension_count": suspensions,
        "positive_activation_count": positive_activations,
        "positive_activation_observed": positive_activations > 0,
        "fit_status": fit_status,
        "exact_fit": exact,
        "mechanism_support_state": support_state,
        "causal_support_state": "NOT_ESTABLISHED",
        "candidate_selection_state": "UNSELECTED",
        "candidate_adoption_state": "NOT_ADOPTED",
        "promotion_state": "NOT_PROMOTED",
        "intervention_execution_state": "NOT_RUN_PH_D07A",
        "rejection_code": None,
        "comparison_trace_digest": logical_content_digest(
            "hds-ph-d07a-step-fit-trace",
            {
                "axis": axis,
                "candidate_content_digest": candidate.get("content_digest"),
                "rows": trace_rows,
            },
            policy=DigestExclusionPolicy(),
        ),
        "error_code_counts": cast(
            dict[str, JsonValue],
            dict(sorted(errors.items())),
        ),
        "mismatch_samples": mismatch_samples,
        "claim_boundary": (
            "Extensional comparison over one observed teacher trajectory only; "
            "not necessity, uniqueness, counterfactual support, or causal proof."
        ),
        "digest_excluded_fields": ["fit_result_id", "content_digest"],
        "content_digest": "",
    }
    return _finalize(
        result,
        id_field="fit_result_id",
        id_namespace="hds-arc3-extensional-fit-result-id",
        digest_namespace="hds-arc3-extensional-fit-result",
        policy=_fit_policy(),
    )


def evaluate_case(
    candidate_package: Mapping[str, object],
    teacher_package: Mapping[str, object],
) -> JsonObject:
    """Account all eighteen candidates for one canonical ARC3 teacher case."""

    expected_ref = teacher_case_ref(teacher_package)
    if candidate_package.get("teacher_case_ref") != expected_ref:
        raise ExactFitError("PH_D07A_TEACHER_CASE_BINDING_MISMATCH")
    raw_candidates = _array(
        candidate_package.get("candidates"),
        "PH_D07A_CANDIDATES",
    )
    if len(raw_candidates) != EXPECTED_CANDIDATES_PER_CASE:
        raise ExactFitError("PH_D07A_CANDIDATE_COUNT_MISMATCH")
    candidates = [_object(item, "PH_D07A_CANDIDATE") for item in raw_candidates]
    if sum(item.get("executable") is True for item in candidates) != (
        EXPECTED_EXECUTABLE_PER_CASE
    ):
        raise ExactFitError("PH_D07A_EXECUTABLE_COUNT_MISMATCH")
    if sum(item.get("rejected") is True for item in candidates) != (
        EXPECTED_REJECTED_PER_CASE
    ):
        raise ExactFitError("PH_D07A_REJECTED_COUNT_MISMATCH")

    contexts = _step_contexts(teacher_package)
    fit_results = [evaluate_candidate(candidate, contexts) for candidate in candidates]
    status_counts: Counter[str] = Counter(
        _string(item.get("fit_status"), "PH_D07A_FIT_STATUS")
        for item in fit_results
    )
    axis_counts: Counter[str] = Counter(
        cast(str, item["comparison_axis"])
        for item in fit_results
        if isinstance(item.get("comparison_axis"), str)
    )
    candidate_step_count = sum(
        _integer(item.get("evaluated_step_count"), "PH_D07A_EVALUATED_STEPS")
        for item in fit_results
    )
    case: JsonObject = {
        "schema_version": CASE_RESULT_VERSION,
        "fit_case_id": "",
        "phase_id": PHASE_ID,
        "evaluator_version": EVALUATOR_VERSION,
        "teacher_case_ref": expected_ref,
        "teacher_package_content_digest": _string(
            teacher_package.get("content_digest"),
            "PH_D07A_TEACHER_PACKAGE_DIGEST",
        ),
        "candidate_package_content_digest": _string(
            candidate_package.get("content_digest"),
            "PH_D07A_CANDIDATE_PACKAGE_DIGEST",
        ),
        "teacher_step_count": len(contexts),
        "candidate_count": len(fit_results),
        "eligible_candidate_count": EXPECTED_EXECUTABLE_PER_CASE,
        "rejected_ineligible_candidate_count": EXPECTED_REJECTED_PER_CASE,
        "candidate_step_evaluation_count": candidate_step_count,
        "fit_status_counts": cast(
            dict[str, JsonValue],
            dict(sorted(status_counts.items())),
        ),
        "axis_candidate_counts": cast(
            dict[str, JsonValue],
            {axis: axis_counts[axis] for axis in FIT_AXES},
        ),
        "fit_results": cast(list[JsonValue], fit_results),
        "gates": {
            "DG-07": "PASS_EXTENSIONAL_FIT_ACCOUNTED",
            "DG-08": "PASS_PRIVILEGE_REJECTION_PRESERVED",
            "DG-09": "PASS_FIT_CAUSAL_SEPARATION",
        },
        "phase_boundaries": {
            "candidate_adoption_count": 0,
            "candidate_selection_count": 0,
            "causal_support_count": 0,
            "real_intervention_execution_count": 0,
            "rule_promotion_count": 0,
            "bridge_runtime_capability_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "claim_boundary": (
            "All fit results are trajectory-local Derived Distillation Evidence. "
            "LOCAL_EXACT_FIT is the maximum support state in PH-D07A."
        ),
        "digest_excluded_fields": ["fit_case_id", "content_digest"],
        "content_digest": "",
    }
    return _finalize(
        case,
        id_field="fit_case_id",
        id_namespace="hds-arc3-extensional-fit-case-id",
        digest_namespace="hds-arc3-extensional-fit-case",
        policy=_case_policy(),
    )


__all__ = [
    "CASE_RESULT_VERSION",
    "EVALUATOR_VERSION",
    "ExactFitError",
    "FIT_AXES",
    "FIT_RESULT_VERSION",
    "PHASE_ID",
    "StepContext",
    "evaluate_candidate",
    "evaluate_case",
]
