"""PH-D03A deterministic Golden conformance candidate corpus.

The records built here are synthetic implementation-conformance fixtures.
They are deliberately non-authoritative and remain pending a new,
content-specific Owner ApprovalRecord.  This module cannot freeze Golden
expectations, create an Owner decision, start a Sealed corpus, read teacher
payloads, execute an ARC environment, promote a Rule, or serve runtime policy.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Final, Never, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_bytes,
    content_derived_id,
    logical_content_digest,
    verify_canonical_json_bytes,
)
from .causal_ir import (
    EXECUTABLE_IR_VERSION,
    SYNTHETIC_FRAME_REF,
    type_check_program,
)
from .interpreter import execute_program
from .ir_types import IRContractError, JsonObject
from .schema_registry import (
    SchemaRegistry,
    SchemaValidationError,
    build_schema_contract,
)
from .verification import (
    BoundedSyntheticInterventionRunner,
    CanonicalExactComparator,
    SyntheticIntervention,
    build_invalid_ir_vector_artifact,
    build_valid_ir_vector_artifact,
)

GOLDEN_CONTRACT_VERSION: Final = "hds-golden-conformance-contract-v1"
GOLDEN_CANDIDATE_SET_VERSION: Final = "hds-golden-candidate-set-v1"
GOLDEN_CASE_VERSION: Final = "hds-golden-candidate-case-v1"
GOLDEN_EXACT_FIT_VERSION: Final = "hds-golden-exact-fit-result-v1"
GOLDEN_PROVISIONAL_EXPECTATION_VERSION: Final = (
    "hds-golden-provisional-expected-artifact-v1"
)
GOLDEN_GATE_COVERAGE_VERSION: Final = "hds-golden-gate-coverage-report-v1"
GOLDEN_OWNER_REVIEW_VERSION: Final = "hds-golden-owner-review-request-v1"

PH_D03A_FRAME_DIGEST: Final = (
    "rev3-work-block-frame:"
    "ce4de522b3e5d269d5f80b260e0b0bf24586f0965207149d2043742c2a7b9132"
)
PH_D03A_PREINVENTORY_DIGEST: Final = (
    "rev3-ph-d03a-golden-preinventory:"
    "102465e690258f967061b70d2023ec9645818c6e68558c01ca6c74a6b7245104"
)
PH_D02C_STATE_DIGEST: Final = (
    "rev3-d02c-phase-state:"
    "bd01666bf05b5e40a8fe896cc4078814d4ddbcbc63f47c7dd705d4ec5eeb66c8"
)
PH_D02C_IR_CONTRACT_DIGEST: Final = (
    "hds-causal-ir-contract:"
    "38b6892f94cab73fa123653a37c248f447257b00d638eeeb0bcfe2ee2e21f98b"
)
PH_D02C_SCHEMA_CONTRACT_DIGEST: Final = (
    "hds-schema-contract:"
    "d0b7e0ebbe826a5c3b0b16eb1d28844ee9daa496a430a747a83e0157b0c0bd29"
)

REQUIRED_ARTIFACT_CLASSES: Final = (
    "RawObservation",
    "DeterministicDerivation",
    "InterpretationHypothesis",
    "multiple HypothesisIR candidates",
    "exact fit result",
    "CounterfactualInterventionPlan",
    "InterventionResult",
    "HDSCausalRecord",
    "FailureSignature",
    "GateResult",
    "non-authoritative ApprovalRecord template",
)

GATE_IDS: Final = tuple(f"DG-{index:02d}" for index in range(16))

CASE_SPECS: Final = (
    {
        "fixture_id": "golden.arc2.recolor",
        "domain": "ARC2",
        "category": "RECOLOR",
        "operators": ("RECOLOR", "DELETE"),
        "primary_gate_id": "DG-00",
    },
    {
        "fixture_id": "golden.arc2.object_selection",
        "domain": "ARC2",
        "category": "OBJECT_SELECTION",
        "operators": (
            "SELECT_COMPONENTS_4",
            "SELECT_COMPONENTS_8",
            "UNIQUE",
        ),
        "primary_gate_id": "DG-01",
    },
    {
        "fixture_id": "golden.arc2.translation_copy",
        "domain": "ARC2",
        "category": "TRANSLATION_COPY",
        "operators": ("TRANSLATE", "OUTLINE", "COPY"),
        "primary_gate_id": "DG-02",
    },
    {
        "fixture_id": "golden.arc2.symmetry",
        "domain": "ARC2",
        "category": "SYMMETRY",
        "operators": ("REFLECT_HORIZONTAL", "REFLECT_VERTICAL"),
        "primary_gate_id": "DG-03",
    },
    {
        "fixture_id": "golden.arc2.count_relation",
        "domain": "ARC2",
        "category": "COUNT_RELATION",
        "operators": ("COUNT", "COUNT_ENCODE"),
        "primary_gate_id": "DG-04",
    },
    {
        "fixture_id": "golden.arc2.composite_transform",
        "domain": "ARC2",
        "category": "COMPOSITE_TRANSFORM",
        "operators": ("COMPOSE", "ROTATE_90", "RECOLOR"),
        "primary_gate_id": "DG-05",
    },
    {
        "fixture_id": "golden.arc2.ambiguous_multi_causal",
        "domain": "ARC2",
        "category": "AMBIGUOUS_MULTI_CAUSAL",
        "operators": ("IDENTITY", "COMPOSE"),
        "primary_gate_id": "DG-06",
    },
    {
        "fixture_id": "golden.arc2.impossible_unsupported_opcode",
        "domain": "ARC2",
        "category": "IMPOSSIBLE_UNSUPPORTED_OPCODE",
        "operators": ("COPY", "IR_UNKNOWN_OPCODE"),
        "primary_gate_id": "DG-07",
    },
    {
        "fixture_id": "golden.arc3.simple_action_effect",
        "domain": "ARC3",
        "category": "SIMPLE_ACTION_EFFECT",
        "operators": ("MATCH_ACTION_ID", "PREDICT_EFFECT"),
        "primary_gate_id": "DG-08",
    },
    {
        "fixture_id": "golden.arc3.action6_payload",
        "domain": "ARC3",
        "category": "ACTION6_PAYLOAD",
        "operators": (
            "MATCH_ACTION_PAYLOAD",
            "MATCH_ACTION_ID",
            "PREDICT_EFFECT",
        ),
        "primary_gate_id": "DG-09",
    },
    {
        "fixture_id": "golden.arc3.order_observed",
        "domain": "ARC3",
        "category": "ORDER_OBSERVED",
        "operators": ("ORDER_BEFORE", "ORDER_ADJACENT"),
        "primary_gate_id": "DG-11",
    },
    {
        "fixture_id": "golden.arc3.delayed_effect",
        "domain": "ARC3",
        "category": "DELAYED_EFFECT",
        "operators": ("DELAYED_EFFECT", "PREDICT_TRANSITION"),
        "primary_gate_id": "DG-10",
    },
    {
        "fixture_id": "golden.arc3.game_over_reset",
        "domain": "ARC3",
        "category": "GAME_OVER_RESET",
        "operators": ("TERMINAL_CONTRIBUTION", "RESET_EFFECT"),
        "primary_gate_id": "DG-13",
    },
    {
        "fixture_id": "golden.arc3.ambiguous_mechanism",
        "domain": "ARC3",
        "category": "AMBIGUOUS_MECHANISM",
        "operators": ("PREDICT_EFFECT", "PREDICT_TRANSITION"),
        "primary_gate_id": "DG-14",
    },
    {
        "fixture_id": "golden.arc3.counterfactual_supported",
        "domain": "ARC3",
        "category": "COUNTERFACTUAL_SUPPORTED",
        "operators": ("PRECONDITION", "EXCLUSION"),
        "primary_gate_id": "DG-15",
    },
    {
        "fixture_id": "golden.arc3.resource_suspension",
        "domain": "ARC3",
        "category": "RESOURCE_SUSPENSION",
        "operators": ("REPEAT_N", "SUSPEND_RESOURCE"),
        "primary_gate_id": "DG-12",
    },
)

GATE_ASSERTIONS: Final = {
    "DG-00": "PASS_COORDINATE_AND_FRAME_BOUND",
    "DG-01": "PASS_OPEN_TERM_EXPLICIT",
    "DG-02": "PASS_X_R_MC_SCOPE_CLOSED",
    "DG-03": "PASS_TYPED_HYPOTHESES_EXECUTABLE",
    "DG-04": "PASS_COUNTER_HYPOTHESIS_PRESENT",
    "DG-05": "PASS_ALTERNATIVE_NOT_STRAWMAN",
    "DG-06": "PASS_SYNTHETIC_EVIDENCE_ORIGIN_LIMITED",
    "DG-07": "PASS_EXACT_FIT_AND_NONEXECUTABLE_ACCOUNTED",
    "DG-08": "PASS_PRIVILEGED_ROUTING_REJECTED",
    "DG-09": "PASS_NO_CAUSAL_PROJECTION",
    "DG-10": "PASS_PREDECLARED_REVERSIBLE_SYNTHETIC_INTERVENTION",
    "DG-11": "PASS_TEMPORAL_ORDER_OR_DELAY_EXPLICIT",
    "DG-12": "PASS_RESOURCE_OVERFLOW_SUSPENDS",
    "DG-13": "PASS_SURFACE_CORRELATION_NOT_PROMOTED",
    "DG-14": "SUSPEND_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL",
    "DG-15": "PASS_UNAPPROVED_COMMIT_AND_PROMOTION_REJECTED",
}

GOLDEN_ERROR_CODES: Final = (
    "D03A_CONTRACT_MISMATCH",
    "D03A_CASE_COUNT_MISMATCH",
    "D03A_CASE_INVENTORY_MISMATCH",
    "D03A_CASE_ARTIFACT_MISSING",
    "D03A_HYPOTHESIS_COUNT_BELOW_MINIMUM",
    "D03A_IR_RESULT_MISMATCH",
    "D03A_INVALID_IR_ACCEPTED",
    "D03A_EXACT_FIT_MISMATCH",
    "D03A_INTERVENTION_PLAN_NOT_PRE_RESULT",
    "D03A_INTERVENTION_RESULT_MISMATCH",
    "D03A_REFERENCE_INVALID",
    "D03A_GATE_COVERAGE_INCOMPLETE",
    "D03A_PRIVILEGED_ROUTING_FORBIDDEN",
    "D03A_CAUSAL_OVERCLAIM",
    "D03A_OWNER_APPROVAL_FABRICATION",
    "D03A_GOLDEN_FREEZE_FORBIDDEN",
    "D03A_EXPECTATION_AUTO_UPDATE_FORBIDDEN",
    "D03A_PROMOTION_FORBIDDEN",
    "D03A_RESOURCE_STATE_MISMATCH",
    "D03A_CONTENT_DIGEST_MISMATCH",
)

PRIVILEGED_KEYS: Final = frozenset(
    {
        "answer_map",
        "fixed_action_sequence",
        "fixed_actions",
        "full_answer_literal",
        "game_id",
        "hidden_state_route",
        "level_id",
        "literal_coordinate_map",
        "replay_id",
        "replay_index",
        "replay_route",
        "source_code_route",
        "source_filename",
        "task_id",
    }
)


class GoldenCorpusError(ValueError):
    """Stable fail-closed PH-D03A candidate-corpus validation error."""

    def __init__(self, code: str, path: str = "") -> None:
        self.code = code
        self.path = path
        super().__init__(code + (":" + path if path else ""))


def _fail(code: str, path: str = "") -> Never:
    raise GoldenCorpusError(code, path)


def _json_object(value: object, code: str, path: str = "") -> JsonObject:
    if not isinstance(value, Mapping):
        _fail(code, path)
    return cast(JsonObject, copy.deepcopy(dict(value)))


def _artifact_policy(id_field: str) -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({id_field}),
        digest_fields=frozenset({"content_digest"}),
    )


def _bind_artifact(
    artifact: JsonObject,
    *,
    namespace: str,
    id_field: str,
) -> JsonObject:
    policy = _artifact_policy(id_field)
    artifact[id_field] = ""
    artifact["content_digest"] = ""
    artifact[id_field] = content_derived_id(
        namespace + "-id",
        artifact,
        policy=policy,
    )
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=policy,
    )
    return artifact


def _bind_digest_only(
    artifact: JsonObject,
    *,
    namespace: str,
) -> JsonObject:
    artifact["content_digest"] = ""
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=DigestExclusionPolicy(
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    return artifact


@lru_cache(maxsize=1)
def _schema_entries_by_name() -> dict[str, Mapping[str, JsonValue]]:
    contract = build_schema_contract()
    entries = cast(list[Mapping[str, JsonValue]], contract["schema_entries"])
    return {cast(str, entry["name"]): entry for entry in entries}


def _schema_entry(schema_name: str) -> Mapping[str, JsonValue]:
    return _schema_entries_by_name()[schema_name]


def _finalize_record(schema_name: str, body: JsonObject) -> JsonObject:
    entry = _schema_entry(schema_name)
    id_field = cast(str, entry["id_field"])
    digest_field = cast(str, entry["digest_field"])
    id_namespace = cast(str, entry["id_namespace"])
    digest_namespace = cast(str, entry["digest_namespace"])
    timestamp_fields = frozenset(cast(list[str], entry["timestamp_fields"]))
    body[id_field] = ""
    body[digest_field] = ""
    body["digest_excluded_fields"] = cast(
        JsonValue,
        list(cast(list[str], entry["digest_excluded_fields"])),
    )
    policy = DigestExclusionPolicy(
        id_fields=frozenset({id_field}),
        digest_fields=frozenset({digest_field}),
        timestamp_fields=timestamp_fields,
    )
    body[id_field] = content_derived_id(
        id_namespace,
        body,
        policy=policy,
    )
    body[digest_field] = logical_content_digest(
        digest_namespace,
        body,
        policy=policy,
    )
    return body


def _rebind_program(program: JsonObject) -> JsonObject:
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"hypothesis_ir_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    program["hypothesis_ir_id"] = ""
    program["content_digest"] = ""
    program["hypothesis_ir_id"] = content_derived_id(
        "hds-hypothesis-i-r-id",
        program,
        policy=policy,
    )
    program["content_digest"] = logical_content_digest(
        "hds-hypothesis-ir",
        program,
        policy=policy,
    )
    return program


@lru_cache(maxsize=1)
def _valid_vector_index() -> dict[tuple[str, str], Mapping[str, object]]:
    artifact = build_valid_ir_vector_artifact()
    vectors = cast(list[Mapping[str, object]], artifact["vectors"])
    return {
        (cast(str, vector["domain"]), cast(str, vector["opcode"])): vector
        for vector in vectors
    }


def _unknown_opcode_program() -> tuple[JsonObject, str]:
    artifact = build_invalid_ir_vector_artifact()
    vectors = cast(list[Mapping[str, object]], artifact["vectors"])
    vector = next(
        item
        for item in vectors
        if item["expected_error_code"] == "IR_UNKNOWN_OPCODE"
        and "UNKNOWN_OPCODE" in cast(str, item["vector_id"])
    )
    return (
        _json_object(
            vector["program"],
            "D03A_CASE_ARTIFACT_MISSING",
            "unknown_opcode_program",
        ),
        cast(str, vector["expected_error_code"]),
    )


def _resource_suspension_program() -> JsonObject:
    vector = _valid_vector_index()[("ARC3", "REPEAT_N")]
    program = _json_object(
        vector["program"],
        "D03A_CASE_ARTIFACT_MISSING",
        "resource_program",
    )
    graph = cast(list[JsonObject], program["operator_graph"])
    first = copy.deepcopy(graph[0])
    first["node_id"] = "result_repeat"
    first["input_refs"] = ["result", "input_1"]
    graph.append(first)
    program["ordering_constraints"] = [{"after": "result_repeat", "before": "result"}]
    program["output_refs"] = ["result_repeat"]
    program["predicted_effects"] = [{"output_ref": "result_repeat"}]
    program["resource_cost"] = 2
    program["resource_limit"] = 1
    _rebind_program(program)
    type_check_program(program)
    result = execute_program(program)
    if result.status != "SUSPEND_RESOURCE":
        _fail("D03A_RESOURCE_STATE_MISMATCH")
    return program


def _program_descriptor(
    *,
    domain: str,
    operator: str,
    index: int,
) -> JsonObject:
    if operator == "IR_UNKNOWN_OPCODE":
        program, error_code = _unknown_opcode_program()
        return {
            "hypothesis_role": "NEGATIVE_CONTROL",
            "operator_focus": operator,
            "hypothesis_ir": program,
            "expected_execution": {
                "kind": "ERROR",
                "error_code": error_code,
            },
        }
    if operator == "SUSPEND_RESOURCE":
        program = _resource_suspension_program()
        result = execute_program(program)
        return {
            "hypothesis_role": "RESOURCE_BOUNDARY",
            "operator_focus": operator,
            "hypothesis_ir": program,
            "expected_execution": {
                "kind": "SUSPEND_RESOURCE",
                "result": result.as_json(),
            },
        }
    vector = _valid_vector_index()[(domain, operator)]
    return {
        "hypothesis_role": ("PRIMARY" if index == 0 else "COUNTER_HYPOTHESIS"),
        "operator_focus": operator,
        "hypothesis_ir": copy.deepcopy(cast(JsonObject, vector["program"])),
        "expected_execution": {
            "kind": "PASS",
            "result": copy.deepcopy(cast(JsonObject, vector["expected_result"])),
        },
    }


def _replacement_for(type_name: str, value: JsonValue) -> JsonValue:
    if type_name == "Grid":
        grid = copy.deepcopy(cast(list[list[int]], value))
        grid[0][0] = (grid[0][0] + 1) % 10
        return cast(JsonValue, grid)
    if type_name == "Cell":
        return [9, 9]
    if type_name == "CellSet":
        return [[1, 1]]
    if type_name == "Region":
        return {"height": 1, "left": 0, "top": 0, "width": 1}
    if type_name == "ObjectCandidate":
        return {
            "attributes": {"node_id": "replacement", "size": 1},
            "cells": [[0, 0]],
            "color": 9,
        }
    if type_name == "ObjectSet":
        return []
    if type_name == "RelationGraph":
        return {"edges": [], "nodes": []}
    if type_name == "Scalar":
        return 1 if value != 1 else 2
    if type_name == "Color":
        return 9 if value != 9 else 8
    if type_name == "Vector":
        return [0, 1]
    if type_name == "Sequence":
        return ["counterfactual"]
    if type_name == "Boolean":
        return not cast(bool, value)
    if type_name == "State":
        state = copy.deepcopy(cast(JsonObject, value))
        state["counterfactual_marker"] = True
        return state
    if type_name == "ActionRecord":
        return {
            "action_id": 1,
            "available_actions": [0, 1, 2, 3],
            "payload": {"kind": "counterfactual"},
        }
    if type_name == "Trajectory":
        return []
    if type_name == "Event":
        return {"kind": "counterfactual", "payload": {}, "step": 9}
    if type_name == "Effect":
        return {"changes": {"status": "counterfactual"}, "delay": 1}
    if type_name == "TerminalState":
        return "GAME_OVER"
    _fail("D03A_INTERVENTION_RESULT_MISMATCH", type_name)


def _build_resource_profile() -> JsonObject:
    return _finalize_record(
        "ResourceProfile",
        {
            "schema_version": "hds-resource-profile-v1",
            "candidate_count_budget": 256,
            "candidate_graph_node_limit": 128,
            "arc2_intervention_budget": 64,
            "arc3_intervention_budget": 128,
            "interpreter_step_limit": 100000,
            "unification_timeout_ms": 60000,
            "per_case_wall_seconds": 900,
            "memory_limit_mb": 4096,
            "llm_call_budget": 0,
        },
    )


def _build_exact_fit(
    descriptor: Mapping[str, object],
    *,
    domain: str,
) -> JsonObject:
    program = cast(Mapping[str, object], descriptor["hypothesis_ir"])
    hypothesis_ref = cast(str, program["hypothesis_ir_id"])
    expected = cast(Mapping[str, object], descriptor["expected_execution"])
    kind = expected["kind"]
    result: JsonObject = {
        "schema_version": GOLDEN_EXACT_FIT_VERSION,
        "hypothesis_ir_ref": hypothesis_ref,
        "domain": domain,
        "comparison_scope": "SYNTHETIC_IMPLEMENTATION_CONFORMANCE_ONLY",
        "causal_establishment": False,
        "pair_count": 1,
        "exact_match_count": 0,
        "cell_mismatch_count": 0,
        "shape_mismatch": False,
        "extra_change_count": 0,
        "missing_change_count": 0,
        "step_count": 1,
        "matched_step_count": 0,
        "fit_status": "",
        "expected_error_code": None,
        "actual_error_code": None,
        "comparison": None,
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    if kind == "PASS":
        actual = execute_program(program)
        expected_result = cast(Mapping[str, object], expected["result"])
        if actual.as_json() != dict(expected_result):
            _fail("D03A_IR_RESULT_MISMATCH", hypothesis_ref)
        checked = type_check_program(program)
        output_ref = checked.output_refs[0]
        output_type = checked.reference_types[output_ref]
        expected_outputs = cast(
            Mapping[str, object],
            expected_result["outputs"],
        )
        expected_value = expected_outputs[output_ref]
        actual_value = actual.outputs[output_ref]
        comparison = CanonicalExactComparator().compare(
            type_name=output_type,
            expected=expected_value,
            actual=actual_value,
        )
        result.update(
            {
                "exact_match_count": 1,
                "matched_step_count": 1,
                "fit_status": "LOCAL_EXACT_FIT",
                "comparison": comparison.as_json(),
            }
        )
    elif kind == "ERROR":
        expected_code = cast(str, expected["error_code"])
        try:
            execute_program(program)
        except IRContractError as exc:
            actual_code = exc.code
        else:
            actual_code = "ACCEPTED_INVALID_IR"
        if actual_code != expected_code:
            _fail("D03A_INVALID_IR_ACCEPTED", hypothesis_ref)
        result.update(
            {
                "fit_status": "NOT_EXECUTABLE",
                "expected_error_code": expected_code,
                "actual_error_code": actual_code,
            }
        )
    elif kind == "SUSPEND_RESOURCE":
        actual = execute_program(program)
        if (
            actual.status != "SUSPEND_RESOURCE"
            or actual.assertion_state != "SUSPEND"
            or actual.operation_state != "HOLD"
            or actual.evidence_state != "INCONCLUSIVE"
            or actual.reason_code != "SUSPEND_RESOURCE"
        ):
            _fail("D03A_RESOURCE_STATE_MISMATCH", hypothesis_ref)
        result["fit_status"] = "INCONCLUSIVE_RESOURCE"
    else:
        _fail("D03A_IR_RESULT_MISMATCH", hypothesis_ref)
    return _bind_digest_only(
        result,
        namespace="hds-golden-exact-fit-result",
    )


def _gate_outcome(gate_id: str) -> tuple[str, str, str]:
    if gate_id == "DG-14":
        return "SUSPEND", "INCONCLUSIVE", "INCONCLUSIVE"
    if gate_id == "DG-12":
        return "PASS", "INCONCLUSIVE", "INCONCLUSIVE"
    return "PASS", "LOCAL_FIT", "LOCAL_EXACT_FIT"


def _build_case(
    spec: Mapping[str, object],
    resource_profile: Mapping[str, JsonValue],
) -> JsonObject:
    fixture_id = cast(str, spec["fixture_id"])
    domain = cast(str, spec["domain"])
    category = cast(str, spec["category"])
    operators = cast(tuple[str, ...], spec["operators"])
    gate_id = cast(str, spec["primary_gate_id"])
    descriptors = [
        _program_descriptor(domain=domain, operator=operator, index=index)
        for index, operator in enumerate(operators)
    ]
    programs = [
        cast(Mapping[str, object], descriptor["hypothesis_ir"])
        for descriptor in descriptors
    ]
    input_snapshots: list[JsonValue] = [
        cast(
            JsonValue,
            {
                "input_set_index": index,
                "inputs": copy.deepcopy(cast(JsonValue, program["inputs"])),
            },
        )
        for index, program in enumerate(programs)
    ]
    raw = _finalize_record(
        "RawObservation",
        {
            "schema_version": "hds-raw-observation-v1",
            "domain": domain,
            "evidence_origin": "DIRECT_OBSERVATION",
            "raw_value": {
                "input_snapshots": input_snapshots,
            },
            "available_actions": ([] if domain == "ARC2" else [1, 2, 3, 4, 5, 6, 7]),
            "terminal": False,
            "progress": 0,
            "source_pointer": (
                "synthetic-golden-candidate/"
                + domain.casefold()
                + "/"
                + category.casefold()
            ),
            "observed_fields": ["input_snapshots"],
        },
    )
    execution_observations: list[JsonValue] = []
    for descriptor in descriptors:
        expected = cast(
            Mapping[str, object],
            descriptor["expected_execution"],
        )
        observation: JsonObject = {
            "kind": cast(str, expected["kind"]),
            "hypothesis_ir_ref": cast(
                str,
                cast(Mapping[str, object], descriptor["hypothesis_ir"])[
                    "hypothesis_ir_id"
                ],
            ),
        }
        if expected["kind"] in {"PASS", "SUSPEND_RESOURCE"}:
            result = cast(Mapping[str, object], expected["result"])
            observation["result_digest"] = cast(
                JsonValue,
                result["result_digest"],
            )
        else:
            observation["error_code"] = cast(
                JsonValue,
                expected["error_code"],
            )
        execution_observations.append(observation)
    derivation = _finalize_record(
        "DeterministicDerivation",
        {
            "schema_version": "hds-deterministic-derivation-v1",
            "derivation_origin": "DETERMINISTIC_ALGORITHM",
            "algorithm_id": "ph-d03a-synthetic-ir-execution-summary",
            "algorithm_version": "1",
            "configuration": {
                "ir_contract_digest": PH_D02C_IR_CONTRACT_DIGEST,
            },
            "input_evidence_refs": [raw["observation_id"]],
            "output": {
                "execution_observations": execution_observations,
            },
            "output_type": (
                "ACTION_EFFECT_DELTA" if domain == "ARC3" else "FRAME_DIFF"
            ),
        },
    )
    interpretation = _finalize_record(
        "InterpretationHypothesis",
        {
            "schema_version": "hds-interpretation-hypothesis-v1",
            "hypothesis_kind": (
                "ACTION_SEMANTICS" if domain == "ARC3" else "COPIED_STRUCTURE"
            ),
            "statement": (
                "Synthetic registered alternatives are held for "
                + category
                + " implementation conformance; no real causal claim."
            ),
            "evidence_refs": [derivation["derivation_id"]],
            "confidence_ppm": 500000,
            "status": "HELD",
        },
    )
    evidence = _finalize_record(
        "EvidenceRecord",
        {
            "schema_version": "hds-evidence-record-v1",
            "evidence_origin": "DETERMINISTIC_DERIVATION",
            "evidence_ref": derivation["derivation_id"],
            "evidence_state": (
                "INCONCLUSIVE"
                if category
                in {
                    "AMBIGUOUS_MECHANISM",
                    "IMPOSSIBLE_UNSUPPORTED_OPCODE",
                    "RESOURCE_SUSPENSION",
                }
                else "LOCAL_FIT"
            ),
            "limitations": [
                "SYNTHETIC_IMPLEMENTATION_CONFORMANCE_ONLY",
                "NOT_GENERALITY_EVIDENCE",
                "NOT_REAL_CAUSAL_EVIDENCE",
            ],
            "provenance": {
                "synthetic": True,
                "phase": "PH-D03A",
            },
        },
    )
    exact_fit_results = [
        _build_exact_fit(descriptor, domain=domain) for descriptor in descriptors
    ]
    models = [
        _finalize_record(
            "ModelRecord",
            {
                "schema_version": "hds-model-record-v1",
                "frame_ref": SYNTHETIC_FRAME_REF,
                "model_type": ("BASELINE" if index == 0 else "COUNTER_HYPOTHESIS"),
                "statement": (
                    "Synthetic "
                    + cast(str, descriptor["operator_focus"])
                    + " conformance candidate"
                ),
                "hypothesis_ir_ref": cast(
                    Mapping[str, JsonValue],
                    descriptor["hypothesis_ir"],
                )["hypothesis_ir_id"],
                "assumptions": [
                    "SYNTHETIC_INPUT_ONLY",
                    "SEALED_PH_D02C_ABI",
                ],
                "supporting_evidence_refs": [evidence["evidence_id"]],
                "contradicting_evidence_refs": [],
                "expected_observations": [
                    {
                        "execution_kind": cast(
                            Mapping[str, JsonValue],
                            descriptor["expected_execution"],
                        )["kind"]
                    }
                ],
                "falsification_procedure": {
                    "kind": "BOUNDED_SYNTHETIC_INPUT_REPLACEMENT",
                },
                "valid_scope": {
                    "synthetic_implementation_conformance_only": True,
                },
                "resource_requirement": {
                    "llm_calls": 0,
                    "real_environment_actions": 0,
                },
                "risks": [
                    "MUST_NOT_BE_PROJECTED_TO_REAL_CAUSAL_SUPPORT",
                ],
                "confidence_ppm": 0,
                "status": "HELD",
            },
        )
        for index, descriptor in enumerate(descriptors)
    ]
    gate_result, evidence_state, support_state = _gate_outcome(gate_id)
    gate = _finalize_record(
        "GateResult",
        {
            "schema_version": "hds-gate-result-v1",
            "gate_id": gate_id,
            "frame_ref": SYNTHETIC_FRAME_REF,
            "model_refs": [model["model_id"] for model in models],
            "evidence_refs": [evidence["evidence_id"]],
            "evidence_state": evidence_state,
            "mechanism_support_state": support_state,
            "result": gate_result,
            "reason_codes": [GATE_ASSERTIONS[gate_id]],
        },
    )
    decision = _finalize_record(
        "DecisionRecord",
        {
            "schema_version": "hds-decision-record-v1",
            "frame_ref": SYNTHETIC_FRAME_REF,
            "decision_mode": "SUSPEND",
            "selected_model_refs": [],
            "held_model_refs": [model["model_id"] for model in models],
            "rejected_model_refs": [],
            "gate_result_refs": [gate["gate_result_id"]],
            "reason_codes": [
                "PROPOSED_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL",
            ],
            "expected_outcome": {
                "candidate_state": "PROPOSED_PENDING_OWNER_APPROVAL",
            },
            "falsification_condition": {
                "kind": "CONFORMANCE_EXPECTATION_MISMATCH",
            },
            "rollback_condition": {
                "kind": "REVERT_PH_D03A_CANDIDATE_ONLY",
            },
            "stop_condition": {
                "kind": "CONTENT_SPECIFIC_OWNER_APPROVAL_REQUIRED",
            },
            "assertion_state": "SUSPEND",
            "operation_state": "HOLD",
            "adoption_state": "PROPOSED",
            "evidence_state": evidence_state,
            "mechanism_support_state": support_state,
            "closure_state": "OPEN",
            "update_state": "PROPOSED",
        },
    )
    intervention_program_index = 1 if operators[0] == "PRECONDITION" else 0
    intervention_program = cast(
        JsonObject,
        programs[intervention_program_index],
    )
    checked = type_check_program(intervention_program)
    intervention_input = checked.inputs[0]
    replacement = _replacement_for(
        intervention_input.type_name,
        intervention_input.value,
    )
    plan = _finalize_record(
        "CounterfactualInterventionPlan",
        {
            "schema_version": "hds-counterfactual-intervention-plan-v1",
            "domain": domain,
            "hypothesis_ir_ref": intervention_program["hypothesis_ir_id"],
            "intervention_kind": "SYNTHETIC_TYPED_INPUT_REPLACEMENT",
            "predicted_outcomes": [
                {
                    "branch": "BASELINE",
                    "prediction": "REGISTERED_PROGRAM_OUTPUT",
                },
                {
                    "branch": "INPUT_REPLACED",
                    "prediction": "OUTPUT_MAY_DIFFER",
                },
            ],
            "reversibility": "REVERSIBLE",
            "safety_constraints": [
                "SYNTHETIC_ONLY",
                "NO_ENVIRONMENT_ACTION",
                "NO_ADAPTIVE_SEARCH",
            ],
            "resource_profile_ref": resource_profile["resource_profile_id"],
            "freeze_state": "PRE_RESULT_FROZEN",
        },
    )
    intervention_outcome = BoundedSyntheticInterventionRunner().run(
        intervention_program,
        (
            SyntheticIntervention(
                input_name=intervention_input.name,
                replacement_value=replacement,
            ),
        ),
    )
    intervention_result = _finalize_record(
        "InterventionResult",
        {
            "schema_version": "hds-intervention-result-v1",
            "intervention_plan_ref": plan["intervention_plan_id"],
            "result_state": "OBSERVED",
            "observed_outcome": intervention_outcome.as_json(),
            "evidence_refs": [evidence["evidence_id"]],
            "operation_state": "HOLD",
            "reason_codes": [
                "SYNTHETIC_ONLY_NO_REAL_CAUSAL_CLAIM",
            ],
        },
    )
    failure = _finalize_record(
        "FailureSignature",
        {
            "schema_version": "hds-failure-signature-v1",
            "target_ref": models[0]["model_id"],
            "target_version": "1",
            "attempted_hypothesis_ref": cast(
                Mapping[str, JsonValue],
                descriptors[1]["hypothesis_ir"],
            )["hypothesis_ir_id"],
            "hds_failure_class": "CONFORMANCE_COUNTER_HYPOTHESIS",
            "domain_failure_code": (
                "UNSUPPORTED_OPCODE"
                if category == "IMPOSSIBLE_UNSUPPORTED_OPCODE"
                else "ALTERNATIVE_RETAINED"
            ),
            "cognition_stage": "SYNTHETIC_CONFORMANCE",
            "surface_symptom": "NO_SINGLE_CAUSAL_SELECTION",
            "structural_cause": "OWNER_APPROVAL_AND_REAL_EVIDENCE_ABSENT",
            "trigger": {
                "category": category,
                "synthetic": True,
            },
            "affected_scope": {
                "fixture_only": True,
            },
            "unaffected_scope": {
                "all_real_cases": True,
            },
            "violated_assumption": "NONE",
            "evidence_state": evidence_state,
            "public_local_boundary": "LOCAL_SYNTHETIC_CANDIDATE",
            "repair_requirement": "OWNER_REVIEW_OR_MORE_EVIDENCE",
            "recovery": {
                "kind": "RETAIN_MULTIPLE_CANDIDATES",
            },
            "next_probe_axes": [
                "CONTENT_SPECIFIC_OWNER_REVIEW",
            ],
            "reusable_check": gate_id,
            "regression_risk": "SELF_APPROVING_EXPECTATION",
            "recurrence_count": 1,
            "status": "QUARANTINED",
            "provenance": {
                "phase": "PH-D03A",
                "synthetic": True,
            },
        },
    )
    open_term = _finalize_record(
        "OpenTermRecord",
        {
            "schema_version": "hds-open-term-record-v1",
            "frame_ref": SYNTHETIC_FRAME_REF,
            "term": "content_specific_golden_expectation_approval",
            "question": (
                "Does the Owner approve this provisional synthetic "
                "conformance expectation?"
            ),
            "required_resolution": "OWNER_RECORDED_APPROVAL_OR_REJECTION",
            "information_value": "REQUIRED_FOR_GOLDEN_FREEZE",
            "blocking": True,
            "status": "OPEN",
            "evidence_refs": [gate["gate_result_id"]],
        },
    )
    hds_record = _finalize_record(
        "HDSCausalRecord",
        {
            "schema_version": "hds-causal-record-v1",
            "record_version": 1,
            "frame_ref": SYNTHETIC_FRAME_REF,
            "raw_observation_refs": [raw["observation_id"]],
            "deterministic_derivation_refs": [derivation["derivation_id"]],
            "interpretation_hypothesis_refs": [interpretation["interpretation_id"]],
            "model_refs": [model["model_id"] for model in models],
            "selected_model_refs": [],
            "held_model_refs": [model["model_id"] for model in models],
            "rejected_model_refs": [],
            "gate_result_refs": [gate["gate_result_id"]],
            "decision_ref": decision["decision_id"],
            "intervention_result_refs": [intervention_result["intervention_result_id"]],
            "failure_signature_refs": [failure["signature_id"]],
            "open_term_refs": [open_term["open_term_id"]],
            "assertion_state": "SUSPEND",
            "operation_state": "HOLD",
            "adoption_state": "PROPOSED",
            "evidence_state": evidence_state,
            "mechanism_support_state": support_state,
            "closure_state": "OPEN",
            "update_state": "PROPOSED",
            "closed_within": {
                "candidate_budget": len(descriptors),
                "evidence_boundary": ("SYNTHETIC_IMPLEMENTATION_CONFORMANCE_ONLY"),
                "hypothesis_language_version": EXECUTABLE_IR_VERSION,
                "intervention_set_digest": plan["content_digest"],
                "limitations": [
                    "NOT_GENERALITY_EVIDENCE",
                    "NOT_REAL_CAUSAL_EVIDENCE",
                    "NOT_OWNER_APPROVED",
                ],
                "observed_case_set_digest": raw["content_digest"],
                "resource_profile_id": resource_profile["resource_profile_id"],
            },
            "claim_refs": [],
            "update_proposal_refs": [],
            "summary": (
                "Non-authoritative synthetic PH-D03A conformance candidate; "
                "all models held pending content-specific Owner review."
            ),
        },
    )
    provisional = _bind_digest_only(
        {
            "schema_version": GOLDEN_PROVISIONAL_EXPECTATION_VERSION,
            "fixture_id": fixture_id,
            "state": "PROPOSED_NOT_FROZEN",
            "component_digests": {
                "raw_observation": raw["content_digest"],
                "deterministic_derivation": derivation["content_digest"],
                "interpretation_hypothesis": interpretation["content_digest"],
                "hypothesis_irs": [
                    cast(JsonValue, program["content_digest"]) for program in programs
                ],
                "exact_fit_results": [
                    result["content_digest"] for result in exact_fit_results
                ],
                "intervention_plan": plan["content_digest"],
                "intervention_result": intervention_result["content_digest"],
                "hds_causal_record": hds_record["content_digest"],
                "failure_signature": failure["content_digest"],
                "gate_result": gate["content_digest"],
            },
            "claim_boundary": ("SYNTHETIC_IMPLEMENTATION_CONFORMANCE_ONLY"),
            "digest_excluded_fields": ["content_digest"],
            "content_digest": "",
        },
        namespace="hds-golden-provisional-expected-artifact",
    )
    approval = _finalize_record(
        "ApprovalRecord",
        {
            "schema_version": "hds-approval-record-v1",
            "approval_mode": "SCHEMA_TEMPLATE",
            "authoritative": False,
            "authority": "UNBOUND_SCHEMA_TEMPLATE",
            "target_artifact_digest": provisional["content_digest"],
            "previous_state": "PROPOSED_PENDING_OWNER_APPROVAL",
            "next_state": "UNBOUND",
            "decision": "SUSPEND",
            "reason_codes": [
                "NON_AUTHORITATIVE_SCHEMA_TEMPLATE",
                "CONTENT_SPECIFIC_OWNER_DECISION_REQUIRED",
            ],
            "evidence_refs": [gate["gate_result_id"]],
            "spec_version": "rev3",
            "approved_at": "2000-01-01T00:00:00Z",
        },
    )
    case = {
        "schema_version": GOLDEN_CASE_VERSION,
        "fixture_id": fixture_id,
        "domain": domain,
        "category": category,
        "primary_gate_id": gate_id,
        "operator_focus": list(operators),
        "candidate_state": "PROPOSED_PENDING_OWNER_APPROVAL",
        "artifact_inventory": list(REQUIRED_ARTIFACT_CLASSES),
        "resource_profile_ref": resource_profile["resource_profile_id"],
        "raw_observation": raw,
        "deterministic_derivation": derivation,
        "interpretation_hypothesis": interpretation,
        "hypothesis_candidates": descriptors,
        "exact_fit_results": exact_fit_results,
        "counterfactual_intervention_plan": plan,
        "intervention_result": intervention_result,
        "hds_causal_record": hds_record,
        "failure_signatures": [failure],
        "gate_result": gate,
        "supporting_records": {
            "evidence_record": evidence,
            "model_records": models,
            "decision_record": decision,
            "open_term_record": open_term,
        },
        "provisional_expected_artifact": provisional,
        "approval_record_template": approval,
        "phase_boundaries": {
            "content_specific_owner_approval_present": False,
            "golden_expected_artifact_frozen": False,
            "sealed_corpus_started": False,
            "source_payload_read_count": 0,
            "teacher_trajectory_read_count": 0,
            "real_intervention_execution_count": 0,
            "causal_mechanism_assertion_count": 0,
            "general_candidate_generation_count": 0,
            "rule_promotion_count": 0,
        },
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    return _bind_digest_only(
        cast(JsonObject, case),
        namespace="hds-golden-candidate-case",
    )


def build_golden_conformance_contract() -> JsonObject:
    """Build the immutable PH-D03A candidate-only conformance contract."""

    contract: JsonObject = {
        "schema_version": GOLDEN_CONTRACT_VERSION,
        "contract_id": "HDS-PH-D03A-GOLDEN-CONFORMANCE-CANDIDATE-V1",
        "phase_id": "PH-D03A",
        "authority": {
            "work_block_frame_digest": PH_D03A_FRAME_DIGEST,
            "preinventory_digest": PH_D03A_PREINVENTORY_DIGEST,
            "input_phase_state_digest": PH_D02C_STATE_DIGEST,
            "schema_contract_digest": PH_D02C_SCHEMA_CONTRACT_DIGEST,
            "causal_ir_contract_digest": PH_D02C_IR_CONTRACT_DIGEST,
        },
        "candidate_state": "PROPOSED_PENDING_OWNER_APPROVAL",
        "candidate_only": True,
        "synthetic_fixture_only": True,
        "required_arc2_case_count": 8,
        "required_arc3_case_count": 8,
        "required_total_case_count": 16,
        "required_hypothesis_count_per_case_minimum": 2,
        "required_artifact_classes": list(REQUIRED_ARTIFACT_CLASSES),
        "required_cases": [
            {
                "fixture_id": cast(str, spec["fixture_id"]),
                "domain": cast(str, spec["domain"]),
                "category": cast(str, spec["category"]),
                "operator_focus": list(cast(tuple[str, ...], spec["operators"])),
                "primary_gate_id": cast(str, spec["primary_gate_id"]),
            }
            for spec in CASE_SPECS
        ],
        "gate_registry": [
            {
                "gate_id": gate_id,
                "expected_assertion": GATE_ASSERTIONS[gate_id],
            }
            for gate_id in GATE_IDS
        ],
        "stable_error_codes": list(GOLDEN_ERROR_CODES),
        "approval_contract": {
            "allowed_mode": "SCHEMA_TEMPLATE",
            "authoritative": False,
            "authority": "UNBOUND_SCHEMA_TEMPLATE",
            "decision": "SUSPEND",
            "owner_recorded_generation_allowed": False,
            "golden_freeze_allowed": False,
            "approved_expectation_auto_update_allowed": False,
        },
        "claim_boundary": {
            "allowed": "SYNTHETIC_IMPLEMENTATION_CONFORMANCE_CANDIDATE",
            "prohibited": [
                "GOLDEN_CONFORMANCE_CORPUS_FROZEN",
                "CONTENT_SPECIFIC_OWNER_APPROVED",
                "SEALED_AUDIT_CORPUS_READY",
                "REAL_TEACHER_EXACT_FIT",
                "REAL_COUNTERFACTUAL_SUPPORTED",
                "CAUSAL_MECHANISM_ESTABLISHED",
                "GENERALITY_PROVEN",
                "RULE_PROMOTED",
                "STRUCTURE_BUNDLE_OWNER_APPROVED",
                "BRIDGE_READY",
                "RUNTIME_READY",
                "OFFICIAL_READY",
            ],
        },
        "phase_boundaries": {
            "golden_candidate_construction_started": True,
            "golden_expected_artifact_freeze_started": False,
            "owner_approval_generated_count": 0,
            "sealed_corpus_started": False,
            "source_payload_read_count": 0,
            "teacher_trajectory_read_count": 0,
            "real_intervention_execution_count": 0,
            "causal_mechanism_assertion_count": 0,
            "general_candidate_generation_count": 0,
            "rule_promotion_count": 0,
            "bridge_started": False,
            "runtime_started": False,
            "locked_final_access_count": 0,
            "official_access_count": 0,
            "network_submission_count": 0,
            "kaggle_mutation_count": 0,
        },
        "digest_excluded_fields": ["content_digest", "contract_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        contract,
        namespace="hds-golden-conformance-contract",
        id_field="contract_id",
    )


def build_golden_candidate_set() -> JsonObject:
    """Build all sixteen synthetic, non-authoritative candidate cases."""

    contract = build_golden_conformance_contract()
    resource_profile = _build_resource_profile()
    cases = [_build_case(spec, resource_profile) for spec in CASE_SPECS]
    artifact: JsonObject = {
        "schema_version": GOLDEN_CANDIDATE_SET_VERSION,
        "corpus_id": "",
        "phase_id": "PH-D03A",
        "contract_digest": contract["content_digest"],
        "candidate_state": "PROPOSED_PENDING_OWNER_APPROVAL",
        "candidate_only": True,
        "synthetic_fixture_only": True,
        "resource_profile": resource_profile,
        "arc2_case_count": 8,
        "arc3_case_count": 8,
        "case_count": len(cases),
        "cases": cast(JsonValue, cases),
        "content_specific_owner_approval_count": 0,
        "golden_frozen_case_count": 0,
        "sealed_case_count": 0,
        "phase_boundaries": copy.deepcopy(
            cast(JsonObject, contract["phase_boundaries"])
        ),
        "digest_excluded_fields": ["content_digest", "corpus_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        artifact,
        namespace="hds-golden-candidate-set",
        id_field="corpus_id",
    )


def _walk_privileged(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                _fail(
                    "D03A_PRIVILEGED_ROUTING_FORBIDDEN",
                    "/".join(path),
                )
            if raw_key.casefold() in PRIVILEGED_KEYS:
                _fail(
                    "D03A_PRIVILEGED_ROUTING_FORBIDDEN",
                    "/".join((*path, raw_key)),
                )
            _walk_privileged(item, (*path, raw_key))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_privileged(item, (*path, str(index)))


def _verify_digest_only(
    artifact: Mapping[str, JsonValue],
    namespace: str,
) -> None:
    expected = logical_content_digest(
        namespace,
        artifact,
        policy=DigestExclusionPolicy(
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    if artifact.get("content_digest") != expected:
        _fail("D03A_CONTENT_DIGEST_MISMATCH", namespace)


def _validate_record(
    registry: SchemaRegistry,
    schema_name: str,
    record: object,
) -> JsonObject:
    instance = _json_object(
        record,
        "D03A_CASE_ARTIFACT_MISSING",
        schema_name,
    )
    try:
        registry.validate_instance(schema_name, instance)
    except SchemaValidationError as exc:
        _fail(
            "D03A_CONTENT_DIGEST_MISMATCH",
            schema_name + ":" + exc.code,
        )
    return instance


def _validate_case(
    registry: SchemaRegistry,
    case: Mapping[str, JsonValue],
    spec: Mapping[str, object],
    resource_profile: Mapping[str, JsonValue],
) -> JsonObject:
    fixture_id = cast(str, spec["fixture_id"])
    if case.get("fixture_id") != fixture_id:
        _fail("D03A_CASE_INVENTORY_MISMATCH", fixture_id)
    if case.get("candidate_state") != "PROPOSED_PENDING_OWNER_APPROVAL":
        _fail("D03A_OWNER_APPROVAL_FABRICATION", fixture_id)
    if case.get("artifact_inventory") != list(REQUIRED_ARTIFACT_CLASSES):
        _fail("D03A_CASE_ARTIFACT_MISSING", fixture_id)
    _verify_digest_only(case, "hds-golden-candidate-case")
    raw = _validate_record(
        registry,
        "RawObservation",
        case.get("raw_observation"),
    )
    source_pointer = raw.get("source_pointer")
    if not isinstance(source_pointer, str) or not source_pointer.startswith(
        "synthetic-golden-candidate/"
    ):
        _fail("D03A_PRIVILEGED_ROUTING_FORBIDDEN", fixture_id)
    derivation = _validate_record(
        registry,
        "DeterministicDerivation",
        case.get("deterministic_derivation"),
    )
    interpretation = _validate_record(
        registry,
        "InterpretationHypothesis",
        case.get("interpretation_hypothesis"),
    )
    supporting = _json_object(
        case.get("supporting_records"),
        "D03A_CASE_ARTIFACT_MISSING",
        fixture_id + "/supporting_records",
    )
    evidence = _validate_record(
        registry,
        "EvidenceRecord",
        supporting.get("evidence_record"),
    )
    models_raw = supporting.get("model_records")
    if not isinstance(models_raw, list):
        _fail("D03A_CASE_ARTIFACT_MISSING", fixture_id + "/models")
    models = [_validate_record(registry, "ModelRecord", item) for item in models_raw]
    decision = _validate_record(
        registry,
        "DecisionRecord",
        supporting.get("decision_record"),
    )
    open_term = _validate_record(
        registry,
        "OpenTermRecord",
        supporting.get("open_term_record"),
    )
    descriptors = case.get("hypothesis_candidates")
    if not isinstance(descriptors, list) or len(descriptors) < 2:
        _fail("D03A_HYPOTHESIS_COUNT_BELOW_MINIMUM", fixture_id)
    if len(models) != len(descriptors):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/models")
    hypothesis_ids: list[str] = []
    for descriptor in descriptors:
        descriptor_object = _json_object(
            descriptor,
            "D03A_CASE_ARTIFACT_MISSING",
            fixture_id + "/hypothesis",
        )
        raw_program = _json_object(
            descriptor_object.get("hypothesis_ir"),
            "D03A_CASE_ARTIFACT_MISSING",
            fixture_id + "/hypothesis_ir",
        )
        _walk_privileged(raw_program)
        program = _validate_record(
            registry,
            "HypothesisIR",
            raw_program,
        )
        if program.get("claim_scope") not in {
            "PREDICTIVE_HYPOTHESIS",
            "COUNTERFACTUAL_CANDIDATE",
        }:
            _fail("D03A_CAUSAL_OVERCLAIM", fixture_id)
        hypothesis_ids.append(cast(str, program["hypothesis_ir_id"]))
        expected = _json_object(
            descriptor_object.get("expected_execution"),
            "D03A_CASE_ARTIFACT_MISSING",
            fixture_id + "/expected_execution",
        )
        kind = expected.get("kind")
        if kind == "PASS":
            try:
                actual = execute_program(program).as_json()
            except IRContractError as exc:
                _fail("D03A_IR_RESULT_MISMATCH", exc.code)
            if actual != expected.get("result"):
                _fail("D03A_IR_RESULT_MISMATCH", fixture_id)
        elif kind == "ERROR":
            try:
                execute_program(program)
            except IRContractError as exc:
                actual_error = exc.code
            else:
                actual_error = "ACCEPTED_INVALID_IR"
            if actual_error != expected.get("error_code"):
                _fail("D03A_INVALID_IR_ACCEPTED", fixture_id)
        elif kind == "SUSPEND_RESOURCE":
            actual_result = execute_program(program)
            if (
                actual_result.status != "SUSPEND_RESOURCE"
                or actual_result.assertion_state != "SUSPEND"
                or actual_result.operation_state != "HOLD"
                or actual_result.evidence_state != "INCONCLUSIVE"
                or actual_result.reason_code != "SUSPEND_RESOURCE"
            ):
                _fail("D03A_RESOURCE_STATE_MISMATCH", fixture_id)
            if actual_result.as_json() != expected.get("result"):
                _fail("D03A_IR_RESULT_MISMATCH", fixture_id)
        else:
            _fail("D03A_IR_RESULT_MISMATCH", fixture_id)
    exact_results = case.get("exact_fit_results")
    if not isinstance(exact_results, list) or len(exact_results) != len(descriptors):
        _fail("D03A_EXACT_FIT_MISMATCH", fixture_id)
    for index, exact in enumerate(exact_results):
        exact_object = _json_object(
            exact,
            "D03A_EXACT_FIT_MISMATCH",
            fixture_id,
        )
        _verify_digest_only(
            exact_object,
            "hds-golden-exact-fit-result",
        )
        if exact_object.get("hypothesis_ir_ref") != hypothesis_ids[index]:
            _fail("D03A_EXACT_FIT_MISMATCH", fixture_id)
        if exact_object.get("causal_establishment") is not False:
            _fail("D03A_CAUSAL_OVERCLAIM", fixture_id)
    plan = _validate_record(
        registry,
        "CounterfactualInterventionPlan",
        case.get("counterfactual_intervention_plan"),
    )
    if (
        plan.get("freeze_state") != "PRE_RESULT_FROZEN"
        or plan.get("reversibility") != "REVERSIBLE"
        or "NO_ENVIRONMENT_ACTION"
        not in cast(list[JsonValue], plan.get("safety_constraints"))
    ):
        _fail("D03A_INTERVENTION_PLAN_NOT_PRE_RESULT", fixture_id)
    intervention_result = _validate_record(
        registry,
        "InterventionResult",
        case.get("intervention_result"),
    )
    gate = _validate_record(
        registry,
        "GateResult",
        case.get("gate_result"),
    )
    failures_raw = case.get("failure_signatures")
    if not isinstance(failures_raw, list) or len(failures_raw) < 1:
        _fail("D03A_CASE_ARTIFACT_MISSING", fixture_id + "/failure")
    failures = [
        _validate_record(registry, "FailureSignature", item) for item in failures_raw
    ]
    hds_record = _validate_record(
        registry,
        "HDSCausalRecord",
        case.get("hds_causal_record"),
    )
    approval = _validate_record(
        registry,
        "ApprovalRecord",
        case.get("approval_record_template"),
    )
    if (
        approval.get("approval_mode") != "SCHEMA_TEMPLATE"
        or approval.get("authoritative") is not False
        or approval.get("authority") != "UNBOUND_SCHEMA_TEMPLATE"
        or approval.get("decision") != "SUSPEND"
    ):
        _fail("D03A_OWNER_APPROVAL_FABRICATION", fixture_id)
    provisional = _json_object(
        case.get("provisional_expected_artifact"),
        "D03A_CASE_ARTIFACT_MISSING",
        fixture_id + "/provisional",
    )
    _verify_digest_only(
        provisional,
        "hds-golden-provisional-expected-artifact",
    )
    if provisional.get("state") != "PROPOSED_NOT_FROZEN":
        _fail("D03A_GOLDEN_FREEZE_FORBIDDEN", fixture_id)
    if approval.get("target_artifact_digest") != provisional.get("content_digest"):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/approval_target")
    model_ids = [cast(str, model["model_id"]) for model in models]
    evidence_id = evidence["evidence_id"]
    gate_id = gate["gate_result_id"]
    if derivation.get("input_evidence_refs") != [raw["observation_id"]]:
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/derivation")
    if interpretation.get("evidence_refs") != [derivation["derivation_id"]]:
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/interpretation")
    if evidence.get("evidence_ref") != derivation["derivation_id"]:
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/evidence")
    for index, model in enumerate(models):
        if (
            model.get("frame_ref") != SYNTHETIC_FRAME_REF
            or model.get("hypothesis_ir_ref") != hypothesis_ids[index]
            or model.get("supporting_evidence_refs") != [evidence_id]
        ):
            _fail("D03A_REFERENCE_INVALID", fixture_id + "/model")
    if (
        gate.get("frame_ref") != SYNTHETIC_FRAME_REF
        or gate.get("model_refs") != model_ids
        or gate.get("evidence_refs") != [evidence_id]
        or gate.get("gate_id") != spec["primary_gate_id"]
    ):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/gate")
    if (
        decision.get("frame_ref") != SYNTHETIC_FRAME_REF
        or decision.get("selected_model_refs") != []
        or decision.get("held_model_refs") != model_ids
        or decision.get("gate_result_refs") != [gate_id]
        or decision.get("operation_state") != "HOLD"
    ):
        _fail("D03A_PROMOTION_FORBIDDEN", fixture_id)
    if (
        open_term.get("frame_ref") != SYNTHETIC_FRAME_REF
        or open_term.get("evidence_refs") != [gate_id]
        or open_term.get("status") != "OPEN"
    ):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/open_term")
    if (
        plan.get("hypothesis_ir_ref") not in hypothesis_ids
        or plan.get("resource_profile_ref") != resource_profile["resource_profile_id"]
        or intervention_result.get("intervention_plan_ref")
        != plan["intervention_plan_id"]
        or intervention_result.get("evidence_refs") != [evidence_id]
    ):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/intervention")
    for failure in failures:
        if (
            failure.get("target_ref") not in model_ids
            or failure.get("attempted_hypothesis_ref") not in hypothesis_ids
        ):
            _fail("D03A_REFERENCE_INVALID", fixture_id + "/failure")
    if (
        hds_record.get("frame_ref") != SYNTHETIC_FRAME_REF
        or hds_record.get("raw_observation_refs") != [raw["observation_id"]]
        or hds_record.get("deterministic_derivation_refs")
        != [derivation["derivation_id"]]
        or hds_record.get("interpretation_hypothesis_refs")
        != [interpretation["interpretation_id"]]
        or hds_record.get("model_refs") != model_ids
        or hds_record.get("selected_model_refs") != []
        or hds_record.get("held_model_refs") != model_ids
        or hds_record.get("gate_result_refs") != [gate_id]
        or hds_record.get("decision_ref") != decision["decision_id"]
        or hds_record.get("intervention_result_refs")
        != [intervention_result["intervention_result_id"]]
        or hds_record.get("failure_signature_refs")
        != [failure["signature_id"] for failure in failures]
        or hds_record.get("open_term_refs") != [open_term["open_term_id"]]
        or hds_record.get("operation_state") != "HOLD"
        or hds_record.get("update_state") != "PROPOSED"
    ):
        _fail("D03A_REFERENCE_INVALID", fixture_id + "/hds_record")
    boundaries = _json_object(
        case.get("phase_boundaries"),
        "D03A_CASE_ARTIFACT_MISSING",
        fixture_id + "/boundaries",
    )
    if (
        boundaries.get("content_specific_owner_approval_present") is not False
        or boundaries.get("golden_expected_artifact_frozen") is not False
        or boundaries.get("sealed_corpus_started") is not False
        or boundaries.get("source_payload_read_count") != 0
        or boundaries.get("teacher_trajectory_read_count") != 0
        or boundaries.get("real_intervention_execution_count") != 0
        or boundaries.get("causal_mechanism_assertion_count") != 0
        or boundaries.get("general_candidate_generation_count") != 0
        or boundaries.get("rule_promotion_count") != 0
    ):
        _fail("D03A_GOLDEN_FREEZE_FORBIDDEN", fixture_id)
    return copy.deepcopy(dict(case))


def validate_golden_candidate_set(
    project_root: Path,
    contract: Mapping[str, JsonValue],
    artifact: Mapping[str, JsonValue],
) -> tuple[JsonObject, ...]:
    """Recompute every candidate and reject authority or phase overreach."""

    if dict(contract) != build_golden_conformance_contract():
        _fail("D03A_CONTRACT_MISMATCH")
    if artifact.get("contract_digest") != contract.get("content_digest"):
        _fail("D03A_CONTRACT_MISMATCH", "candidate_set")
    policy = _artifact_policy("corpus_id")
    if artifact.get("content_digest") != logical_content_digest(
        "hds-golden-candidate-set",
        artifact,
        policy=policy,
    ):
        _fail("D03A_CONTENT_DIGEST_MISMATCH", "candidate_set")
    if (
        artifact.get("candidate_state") != "PROPOSED_PENDING_OWNER_APPROVAL"
        or artifact.get("content_specific_owner_approval_count") != 0
        or artifact.get("golden_frozen_case_count") != 0
        or artifact.get("sealed_case_count") != 0
    ):
        _fail("D03A_OWNER_APPROVAL_FABRICATION", "candidate_set")
    cases = artifact.get("cases")
    if not isinstance(cases, list) or len(cases) != 16:
        _fail("D03A_CASE_COUNT_MISMATCH")
    resource_profile = _json_object(
        artifact.get("resource_profile"),
        "D03A_CASE_ARTIFACT_MISSING",
        "resource_profile",
    )
    registry = SchemaRegistry.from_directory(
        project_root / "distillation/schemas",
        project_root / "distillation/input/schema_contract.json",
    )
    _validate_record(
        registry,
        "ResourceProfile",
        resource_profile,
    )
    validated: list[JsonObject] = []
    for case, spec in zip(cases, CASE_SPECS, strict=True):
        validated.append(
            _validate_case(
                registry,
                cast(Mapping[str, JsonValue], case),
                spec,
                resource_profile,
            )
        )
    if [case["fixture_id"] for case in validated] != [
        spec["fixture_id"] for spec in CASE_SPECS
    ]:
        _fail("D03A_CASE_INVENTORY_MISMATCH")
    if sum(case["domain"] == "ARC2" for case in validated) != 8:
        _fail("D03A_CASE_COUNT_MISMATCH", "ARC2")
    if sum(case["domain"] == "ARC3" for case in validated) != 8:
        _fail("D03A_CASE_COUNT_MISMATCH", "ARC3")
    return tuple(validated)


def build_golden_gate_coverage_report(
    candidate_set: Mapping[str, JsonValue],
) -> JsonObject:
    cases = cast(list[Mapping[str, JsonValue]], candidate_set["cases"])
    entries: list[JsonValue] = []
    for gate_id in GATE_IDS:
        case = next(item for item in cases if item["primary_gate_id"] == gate_id)
        gate = cast(Mapping[str, JsonValue], case["gate_result"])
        entries.append(
            {
                "gate_id": gate_id,
                "fixture_id": case["fixture_id"],
                "expected_assertion": GATE_ASSERTIONS[gate_id],
                "actual_result": gate["result"],
                "actual_reason_codes": gate["reason_codes"],
                "gate_result_digest": gate["content_digest"],
                "covered": True,
            }
        )
    report: JsonObject = {
        "schema_version": GOLDEN_GATE_COVERAGE_VERSION,
        "report_id": "",
        "phase_id": "PH-D03A",
        "candidate_set_digest": candidate_set["content_digest"],
        "gate_count": 16,
        "covered_gate_count": 16,
        "missing_gate_ids": [],
        "pass_result_count": 15,
        "suspend_result_count": 1,
        "fail_result_count": 0,
        "coverage_complete": True,
        "implementation_conformance_candidate_pass": True,
        "gate_entries": entries,
        "approval_boundary": {
            "DG-14": "SUSPEND_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL",
            "owner_approval_generated": False,
            "golden_freeze_started": False,
            "approved_expectation_auto_update": False,
        },
        "claim_boundary": ("GATE_BEHAVIOR_COVERAGE_IS_NOT_GENERALITY_OR_CAUSAL_PROOF"),
        "digest_excluded_fields": ["content_digest", "report_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        report,
        namespace="hds-golden-gate-coverage",
        id_field="report_id",
    )


def build_golden_owner_review_request(
    candidate_set: Mapping[str, JsonValue],
    coverage_report: Mapping[str, JsonValue],
) -> JsonObject:
    cases = cast(list[Mapping[str, JsonValue]], candidate_set["cases"])
    request: JsonObject = {
        "schema_version": GOLDEN_OWNER_REVIEW_VERSION,
        "review_request_id": "",
        "phase_id": "PH-D03A",
        "request_state": "AWAITING_CONTENT_SPECIFIC_OWNER_DECISION",
        "requested_decision": (
            "APPROVE_REJECT_OR_SUSPEND_EACH_PROVISIONAL_EXPECTATION"
        ),
        "candidate_set_digest": candidate_set["content_digest"],
        "gate_coverage_report_digest": coverage_report["content_digest"],
        "target_count": len(cases),
        "targets": [
            {
                "fixture_id": case["fixture_id"],
                "candidate_case_digest": case["content_digest"],
                "provisional_expected_artifact_digest": cast(
                    Mapping[str, JsonValue],
                    case["provisional_expected_artifact"],
                )["content_digest"],
                "approval_template_digest": cast(
                    Mapping[str, JsonValue],
                    case["approval_record_template"],
                )["approval_artifact_digest"],
                "current_state": "PROPOSED_PENDING_OWNER_APPROVAL",
            }
            for case in cases
        ],
        "owner_response_contract": {
            "approval_mode": "OWNER_RECORDED",
            "authority": "OWNER",
            "authoritative": True,
            "decision_values": ["APPROVE", "REJECT", "SUSPEND"],
            "target_must_equal_provisional_digest": True,
            "trusted_external_digest_required": True,
            "codex_must_not_generate_response": True,
        },
        "freeze_preconditions": [
            "ALL_SIXTEEN_TARGETS_HAVE_TRUSTED_CONTENT_SPECIFIC_OWNER_RECORDS",
            "APPROVED_TARGET_DIGESTS_MATCH_PROVISIONAL_EXPECTATIONS",
            "REJECTION_OR_SUSPEND_IS_RESOLVED_WITHOUT_AUTO_UPDATE",
            "POST_APPROVAL_REBUILD_AND_REGRESSION_PASS",
        ],
        "owner_decision_present": False,
        "owner_approval_generated": False,
        "golden_freeze_started": False,
        "sealed_corpus_started": False,
        "automatic_expectation_update_allowed": False,
        "digest_excluded_fields": [
            "content_digest",
            "review_request_id",
        ],
        "content_digest": "",
    }
    return _bind_artifact(
        request,
        namespace="hds-golden-owner-review-request",
        id_field="review_request_id",
    )


def validate_golden_gate_coverage(
    candidate_set: Mapping[str, JsonValue],
    report: Mapping[str, JsonValue],
) -> None:
    policy = _artifact_policy("report_id")
    if report.get("content_digest") != logical_content_digest(
        "hds-golden-gate-coverage",
        report,
        policy=policy,
    ):
        _fail("D03A_CONTENT_DIGEST_MISMATCH", "gate_coverage")
    entries = report.get("gate_entries")
    if not isinstance(entries, list):
        _fail("D03A_GATE_COVERAGE_INCOMPLETE")
    actual_ids = [item.get("gate_id") for item in entries if isinstance(item, Mapping)]
    if actual_ids != list(GATE_IDS):
        _fail("D03A_GATE_COVERAGE_INCOMPLETE")
    if (
        report.get("candidate_set_digest") != candidate_set.get("content_digest")
        or report.get("covered_gate_count") != 16
        or report.get("missing_gate_ids") != []
        or report.get("coverage_complete") is not True
        or report.get("fail_result_count") != 0
    ):
        _fail("D03A_GATE_COVERAGE_INCOMPLETE")
    dg14 = next(
        item
        for item in cast(list[Mapping[str, JsonValue]], entries)
        if item["gate_id"] == "DG-14"
    )
    if (
        dg14["actual_result"] != "SUSPEND"
        or dg14["expected_assertion"]
        != "SUSPEND_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    ):
        _fail("D03A_OWNER_APPROVAL_FABRICATION", "DG-14")


def validate_golden_owner_review_request(
    candidate_set: Mapping[str, JsonValue],
    coverage_report: Mapping[str, JsonValue],
    request: Mapping[str, JsonValue],
) -> None:
    policy = _artifact_policy("review_request_id")
    if request.get("content_digest") != logical_content_digest(
        "hds-golden-owner-review-request",
        request,
        policy=policy,
    ):
        _fail("D03A_CONTENT_DIGEST_MISMATCH", "owner_review_request")
    if (
        request.get("candidate_set_digest") != candidate_set.get("content_digest")
        or request.get("gate_coverage_report_digest")
        != coverage_report.get("content_digest")
        or request.get("target_count") != 16
    ):
        _fail("D03A_REFERENCE_INVALID", "owner_review_request")
    if (
        request.get("owner_decision_present") is not False
        or request.get("owner_approval_generated") is not False
        or request.get("golden_freeze_started") is not False
        or request.get("sealed_corpus_started") is not False
        or request.get("automatic_expectation_update_allowed") is not False
    ):
        _fail("D03A_OWNER_APPROVAL_FABRICATION", "owner_review_request")
    response_contract = request.get("owner_response_contract")
    if (
        not isinstance(response_contract, Mapping)
        or response_contract.get("codex_must_not_generate_response") is not True
        or response_contract.get("trusted_external_digest_required") is not True
    ):
        _fail("D03A_OWNER_APPROVAL_FABRICATION", "response_contract")


def build_phase_d03a_candidate_artifacts(
    project_root: Path,
) -> dict[str, bytes]:
    """Build and validate all four deterministic PH-D03A candidate artifacts."""

    contract = build_golden_conformance_contract()
    candidate_set = build_golden_candidate_set()
    validate_golden_candidate_set(project_root, contract, candidate_set)
    coverage = build_golden_gate_coverage_report(candidate_set)
    validate_golden_gate_coverage(candidate_set, coverage)
    review = build_golden_owner_review_request(candidate_set, coverage)
    validate_golden_owner_review_request(candidate_set, coverage, review)
    artifacts: dict[str, JsonObject] = {
        "distillation/input/golden_conformance_contract.json": contract,
        "distillation/artifacts/golden/candidate_cases.json": candidate_set,
        "distillation/artifacts/reports/golden_gate_coverage.json": coverage,
        "distillation/artifacts/golden/owner_review_request.json": review,
    }
    encoded = {
        path: canonical_json_bytes(value) for path, value in sorted(artifacts.items())
    }
    for payload in encoded.values():
        verify_canonical_json_bytes(payload)
    return encoded


def write_phase_d03a_candidate_artifacts(
    project_root: Path,
) -> dict[str, str]:
    """Write only deterministic PH-D03A candidate-owned artifact paths."""

    artifacts = build_phase_d03a_candidate_artifacts(project_root)
    digests: dict[str, str] = {}
    for relative_path, payload in artifacts.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        digests[relative_path] = hashlib.sha256(payload).hexdigest()
    return digests


__all__ = [
    "CASE_SPECS",
    "GATE_ASSERTIONS",
    "GATE_IDS",
    "GOLDEN_ERROR_CODES",
    "GoldenCorpusError",
    "REQUIRED_ARTIFACT_CLASSES",
    "build_golden_candidate_set",
    "build_golden_conformance_contract",
    "build_golden_gate_coverage_report",
    "build_golden_owner_review_request",
    "build_phase_d03a_candidate_artifacts",
    "validate_golden_candidate_set",
    "validate_golden_gate_coverage",
    "validate_golden_owner_review_request",
    "write_phase_d03a_candidate_artifacts",
]
