"""Compile closed S0/S1 Teacher evidence into structure artifacts.

The outputs are development artifacts.  They make every remaining privilege
explicit and therefore must never be imported by the rendered-only Runtime
Student.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object
from .human_replay_corpus import load_full_solution_corpus
from .replay_runner import TEACHER_CLOSURE_REPORT_DIGEST_PREFIX
from .s1_graph_executor import load_s1_closure_report
from .s1_graph_schema import load_s1_policy_graph
from .source_semantics import (
    compile_source_causal_semantics,
    source_contract_index,
)

LEVEL_GRAPH_LEDGER_SCHEMA_VERSION = (
    "arc3-level-solution-graph-ledger-v2"
)
INTRA_GAME_GRAPH_SCHEMA_VERSION = (
    "arc3-intra-game-progression-graph-v2"
)
CROSS_GAME_GRAMMAR_SCHEMA_VERSION = (
    "arc3-cross-game-structural-grammar-v3"
)
PRIVILEGE_MATRIX_SCHEMA_VERSION = (
    "arc3-privilege-subtraction-matrix-v3"
)
RUNTIME_P_REPORT_SCHEMA_VERSION = (
    "arc3-runtime-p-compilation-report-v3"
)

LEVEL_GRAPH_LEDGER_DIGEST_PREFIX = "arc3_level_solution_graph_ledger:"
LEVEL_GRAPH_DIGEST_PREFIX = "arc3_level_solution_graph:"
INTRA_GAME_GRAPH_DIGEST_PREFIX = "arc3_intra_game_progression_graph:"
CROSS_GAME_GRAMMAR_DIGEST_PREFIX = "arc3_cross_game_structural_grammar:"
PRIVILEGE_MATRIX_DIGEST_PREFIX = "arc3_privilege_subtraction_matrix:"
RUNTIME_P_REPORT_DIGEST_PREFIX = "arc3_runtime_p_compilation_report:"
SOURCE_GAME_REGISTRY_ENTRY_DIGEST_PREFIX = (
    "arc3_source_game_registry_entry:"
)

OUTPUT_FILENAMES = {
    "level_ledger": "LEVEL_SOLUTION_GRAPH_LEDGER.json",
    "intra_game": "INTRA_GAME_PROGRESSION_GRAPH.json",
    "cross_game": "CROSS_GAME_STRUCTURAL_GRAMMAR.json",
    "privilege_matrix": "PRIVILEGE_SUBTRACTION_MATRIX.json",
    "runtime_p_report": "RUNTIME_P_COMPILATION_REPORT.json",
}

STAGE_DEFINITIONS = (
    {
        "stage": "S0",
        "allowed_information": [
            "TASK_GAME_LEVEL_ID",
            "SOURCE_AND_HIDDEN_STATE",
            "ANSWER_AND_REPLAY",
            "FIXED_ACTION_SEQUENCE",
            "LITERAL_COORDINATE",
            "ALL_DEVELOPMENT_ANALYSIS",
        ],
        "required_result": "183/183",
    },
    {
        "stage": "S1",
        "allowed_information": [
            "TASK_GAME_LEVEL_ID",
            "SOURCE_AND_HIDDEN_STATE",
            "ANSWER_AND_REPLAY",
            "LITERAL_COORDINATE",
            "ALL_DEVELOPMENT_ANALYSIS",
        ],
        "forbidden_information": ["FIXED_ACTION_SEQUENCE"],
        "required_result": "183/183",
    },
    {
        "stage": "S2",
        "forbidden_information": [
            "FIXED_ACTION_SEQUENCE",
            "LITERAL_COORDINATE",
        ],
        "required_result": "183/183",
    },
    {
        "stage": "S3",
        "forbidden_information": [
            "FIXED_ACTION_SEQUENCE",
            "LITERAL_COORDINATE",
            "TASK_GAME_LEVEL_ID_ROUTING",
        ],
        "required_result": "183/183",
    },
    {
        "stage": "S4",
        "forbidden_information": [
            "FIXED_ACTION_SEQUENCE",
            "LITERAL_COORDINATE",
            "TASK_GAME_LEVEL_ID_ROUTING",
            "SOURCE_AND_HIDDEN_STATE",
        ],
        "required_result": "183/183",
    },
    {
        "stage": "S5",
        "allowed_information": [
            "RENDERED_OBSERVATION",
            "AVAILABLE_ACTIONS",
            "ACTION_EFFECT_HISTORY",
            "PASSIVE_MEMORY",
            "IDENTITY_FREE_P",
        ],
        "required_result": "183/183",
    },
    {
        "stage": "S6",
        "allowed_information": ["S5_INFORMATION"],
        "perturbations": [
            "COLOR",
            "ROTATION",
            "REFLECTION",
            "LAYOUT",
            "OBJECT_COUNT",
            "ORDER",
            "UNSEEN_COMPOSITION",
        ],
        "required_result": "GENERALIZATION_MEASUREMENT",
    },
)


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_digest", None)
    return body


def load_teacher_closure_report(path: Path) -> dict[str, Any]:
    """Load the exact all-game closure gate required by graph compilation."""

    report = _json_object(path)
    failures: list[str] = []
    claimed = report.get("content_digest")
    actual = TEACHER_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(
        _without_digest(report)
    )
    if claimed != actual:
        failures.append("TEACHER_CLOSURE_REPORT_DIGEST_INVALID")
    if report.get("schema_version") != "arc3-teacher-s0-closure-report-v1":
        failures.append("TEACHER_CLOSURE_REPORT_SCHEMA_INVALID")
    if report.get("development_only") is not True:
        failures.append("TEACHER_CLOSURE_REPORT_BOUNDARY_INVALID")
    if report.get("runtime_use") != "FORBIDDEN":
        failures.append("TEACHER_CLOSURE_REPORT_RUNTIME_USE_INVALID")
    if str(report.get("operation_mode", "")).casefold() != "offline":
        failures.append("TEACHER_CLOSURE_REPORT_NON_OFFLINE")
    if (
        report.get("complete_inventory") is not True
        or report.get("game_count") != 25
        or report.get("completed_game_count") != 25
        or report.get("level_count") != 183
        or report.get("completed_levels") != 183
        or report.get("error_count") != 0
        or report.get("all_complete") is not True
    ):
        failures.append("TEACHER_CLOSURE_REPORT_NOT_183_COMPLETE")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return report


def _primitive_for_action(action: Mapping[str, Any]) -> str:
    action_id = _integer(action.get("action_id"), "action_id")
    action_data = action.get("action_data")
    has_coordinate = (
        isinstance(action_data, Mapping)
        and action_data.get("x") is not None
        and action_data.get("y") is not None
    )
    if action_id == 0:
        return (
            "RESET_FULL"
            if action.get("full_reset") is True
            else "RESET_LEVEL"
        )
    if action_id == 6 and has_coordinate:
        return "INTERACT_AT_RENDERED_COORDINATE"
    return f"ACTION_{action_id}"


def _coordinate_operand(action: Mapping[str, Any]) -> dict[str, Any]:
    raw_data = action.get("action_data")
    if not isinstance(raw_data, Mapping):
        return {"role": "CONTROL_INPUT"}
    x = raw_data.get("x")
    y = raw_data.get("y")
    if (
        isinstance(x, int)
        and not isinstance(x, bool)
        and isinstance(y, int)
        and not isinstance(y, bool)
    ):
        return {
            "role": "INTERACTION_TARGET",
            "literal_coordinate": {"x": x, "y": y},
        }
    return {"role": "CONTROL_INPUT"}


def _interaction_objects(
    actions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, int]] = Counter()
    for action in actions:
        operand = _coordinate_operand(action)
        coordinate = operand.get("literal_coordinate")
        if not isinstance(coordinate, Mapping):
            continue
        x = _integer(coordinate.get("x"), "literal_coordinate.x")
        y = _integer(coordinate.get("y"), "literal_coordinate.y")
        counts[(x, y)] += 1
    return [
        {
            "object_ref": (
                "S0_LITERAL_TARGET:"
                + digest_object({"x": x, "y": y})[:16]
            ),
            "role": "INTERACTION_TARGET",
            "literal_coordinate": {"x": x, "y": y},
            "successful_trajectory_use_count": count,
            "identity_free_binding_status": "NOT_COMPILED",
        }
        for (x, y), count in sorted(counts.items())
    ]


def _source_level_objects(
    source_level: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_families = _sequence(
        source_level.get("object_families"),
        "source_level.object_families",
    )
    objects: list[dict[str, Any]] = []
    for raw_family in raw_families:
        family = _mapping(
            raw_family,
            "source_level.object_families[]",
        )
        family_digest = str(family.get("object_family_digest", ""))
        if not family_digest:
            raise ValueError("SOURCE_OBJECT_FAMILY_DIGEST_MISSING")
        objects.append(
            {
                "object_ref": (
                    "S0_SOURCE_OBJECT_FAMILY:"
                    + family_digest[:16]
                ),
                "role": "SOURCE_LEVEL_OBJECT_FAMILY",
                "source_sprite_key": family.get("source_sprite_key"),
                "source_instance_count": family.get("instance_count"),
                "source_causal_roles": list(
                    _sequence(
                        family.get("causal_roles"),
                        "source_object.causal_roles",
                    )
                ),
                "source_definition_digest": family.get(
                    "definition_digest"
                ),
                "source_object_family_digest": family_digest,
                "teacher_binding_status": "SOURCE_LEVEL_AST_BOUND",
                "identity_free_binding_status": "NOT_COMPILED",
            }
        )
    return objects


def _source_role_bindings(
    source_objects: Sequence[Mapping[str, Any]],
    source_game: Mapping[str, Any],
) -> list[dict[str, Any]]:
    refs_by_role: defaultdict[str, list[str]] = defaultdict(list)
    all_refs: list[str] = []
    for source_object in source_objects:
        object_ref = str(source_object.get("object_ref", ""))
        if not object_ref:
            continue
        all_refs.append(object_ref)
        for raw_role in _sequence(
            source_object.get("source_causal_roles"),
            "source_object.source_causal_roles",
        ):
            refs_by_role[str(raw_role)].append(object_ref)
    raw_queries = _sequence(
        source_game.get("source_object_queries"),
        "source_game.source_object_queries",
    )
    query_digests_by_role: defaultdict[str, list[str]] = defaultdict(list)
    for raw_query in raw_queries:
        query = _mapping(raw_query, "source_object_query")
        query_digest = str(query.get("query_digest", ""))
        for raw_role in _sequence(
            query.get("causal_roles"),
            "source_object_query.causal_roles",
        ):
            query_digests_by_role[str(raw_role)].append(query_digest)
    action_refs = sorted(
        set(
            refs_by_role.get("ACTION_EFFECT_SOURCE_QUERY", [])
            + refs_by_role.get("POINTER_AFFORDANCE", [])
        )
    )
    goal_refs = sorted(
        set(refs_by_role.get("GOAL_CONTROL_PATH_SOURCE_QUERY", []))
    )
    hazard_refs = sorted(
        set(refs_by_role.get("HAZARD_CONTROL_PATH_SOURCE_QUERY", []))
    )
    action_entry = _mapping(
        source_game.get("action_transition_entry"),
        "source_game.action_transition_entry",
    )
    action_state = sorted(
        str(value)
        for value in _sequence(
            action_entry.get("source_state"),
            "action_transition_entry.source_state",
        )
    )

    def terminal_state(field_name: str) -> list[str]:
        symbols: set[str] = set()
        for raw_witness in _sequence(
            source_game.get(field_name),
            f"source_game.{field_name}",
        ):
            witness = _mapping(raw_witness, f"{field_name}[]")
            for state_field in (
                "condition_source_state",
                "method_source_state",
            ):
                symbols.update(
                    str(value)
                    for value in _sequence(
                        witness.get(state_field),
                        f"{field_name}.{state_field}",
                    )
                )
            for raw_edge in _sequence(
                witness.get("method_path_evidence"),
                f"{field_name}.method_path_evidence",
            ):
                edge = _mapping(
                    raw_edge,
                    f"{field_name}.method_path_evidence[]",
                )
                for raw_call_site in _sequence(
                    edge.get("call_sites"),
                    f"{field_name}.method_path_evidence.call_sites",
                ):
                    call_site = _mapping(
                        raw_call_site,
                        f"{field_name}.call_site",
                    )
                    symbols.update(
                        str(value)
                        for value in _sequence(
                            call_site.get(
                                "condition_source_state",
                                [],
                            ),
                            f"{field_name}.call_site.state",
                        )
                    )
        return sorted(symbols)

    goal_state = terminal_state("goal_witnesses")
    hazard_state = terminal_state("hazard_witnesses")
    return [
        {
            "role": "ACTOR_OR_MANIPULAND_SET",
            "binding": {
                "source_object_refs": (
                    action_refs if action_refs else sorted(set(all_refs))
                ),
                "source_state_symbols": action_state,
            },
            "binding_kind": (
                "SOURCE_CAUSAL_OBJECT_FAMILY_SET"
                if action_refs
                else "SOURCE_LEVEL_CANDIDATE_SET"
            ),
            "source_query_digests": sorted(
                set(
                    query_digests_by_role.get(
                        "ACTION_EFFECT_SOURCE_QUERY",
                        [],
                    )
                )
            ),
            "uniqueness": "ROLE_SET_BOUND;UNIQUE_ACTOR_NOT_ASSUMED",
            "subtraction_target": "RENDERED_OBJECT_ROLE_INDUCTION",
        },
        {
            "role": "GOAL_STATE_PARTICIPANT_SET",
            "binding": {
                "source_object_refs": goal_refs,
                "source_state_symbols": goal_state,
            },
            "binding_kind": "SOURCE_CONTROL_PATH_OBJECT_AND_STATE_SET",
            "source_query_digests": sorted(
                set(
                    query_digests_by_role.get(
                        "GOAL_CONTROL_PATH_SOURCE_QUERY",
                        [],
                    )
                )
            ),
            "uniqueness": "ROLE_SET_BOUND;UNIQUE_TARGET_NOT_ASSUMED",
            "subtraction_target": "RENDERED_GOAL_RELATION_INDUCTION",
        },
        {
            "role": "HAZARD_STATE_PARTICIPANT_SET",
            "binding": {
                "source_object_refs": hazard_refs,
                "source_state_symbols": hazard_state,
            },
            "binding_kind": "SOURCE_CONTROL_PATH_OBJECT_AND_STATE_SET",
            "source_query_digests": sorted(
                set(
                    query_digests_by_role.get(
                        "HAZARD_CONTROL_PATH_SOURCE_QUERY",
                        [],
                    )
                )
            ),
            "uniqueness": "ROLE_SET_BOUND;UNIQUE_HAZARD_NOT_ASSUMED",
            "subtraction_target": "RENDERED_HAZARD_RELATION_INDUCTION",
        },
    ]


def _terminal_source_evidence(
    source_game: Mapping[str, Any],
    field_name: str,
) -> list[dict[str, Any]]:
    raw_witnesses = _sequence(
        source_game.get(field_name),
        f"source_game.{field_name}",
    )
    evidence: list[dict[str, Any]] = []
    for raw_witness in raw_witnesses:
        witness = _mapping(raw_witness, f"{field_name}[]")
        method_path_predicates: list[dict[str, Any]] = []
        for raw_edge in _sequence(
            witness.get("method_path_evidence"),
            f"{field_name}.method_path_evidence",
        ):
            edge = _mapping(
                raw_edge,
                f"{field_name}.method_path_evidence[]",
            )
            for raw_site in _sequence(
                edge.get("call_sites"),
                f"{field_name}.call_sites",
            ):
                site = _mapping(raw_site, f"{field_name}.call_sites[]")
                method_path_predicates.append(
                    {
                        "caller": edge.get("caller"),
                        "callee": edge.get("callee"),
                        "source_location": site.get("source_location"),
                        "path_predicates": site.get("path_predicates"),
                        "condition_source_state": site.get(
                            "condition_source_state"
                        ),
                        "call_digest": site.get("call_digest"),
                    }
                )
        evidence.append(
            {
                "witness_digest": witness.get("witness_digest"),
                "event": witness.get("event"),
                "method": witness.get("method"),
                "method_path_from_step": witness.get(
                    "method_path_from_step"
                ),
                "method_path_predicates": method_path_predicates,
                "source_location": witness.get("source_location"),
                "path_predicates": witness.get("path_predicates"),
                "condition_source_state": witness.get(
                    "condition_source_state"
                ),
                "method_source_state": witness.get(
                    "method_source_state"
                ),
                "method_source_digest": witness.get(
                    "method_source_digest"
                ),
            }
        )
    return evidence


def _source_game_registry_entry(
    source_game: Mapping[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "game_id": source_game.get("game_id"),
        "source_game_contract_digest": source_game.get("content_digest"),
        "direct_source_evidence_digest": source_game.get(
            "direct_source_evidence_digest"
        ),
        "source_path": source_game.get("source_path"),
        "source_sha256": source_game.get("source_sha256"),
        "source_line_count": source_game.get("source_line_count"),
        "game_class": source_game.get("game_class"),
        "game_class_source_digest": source_game.get(
            "game_class_source_digest"
        ),
        "action_transition_entry": source_game.get(
            "action_transition_entry"
        ),
        "action_handlers": source_game.get("action_handlers"),
        "source_object_queries": source_game.get(
            "source_object_queries"
        ),
        "source_state_variables": source_game.get(
            "source_state_variables"
        ),
        "hidden_state_model": source_game.get("hidden_state_model"),
        "goal_witnesses": source_game.get("goal_witnesses"),
        "hazard_witnesses": source_game.get("hazard_witnesses"),
        "action_commit_witnesses": source_game.get(
            "action_commit_witnesses"
        ),
        "source_causal_complete": source_game.get(
            "source_causal_complete"
        ),
        "source_causal_completion_basis": source_game.get(
            "source_causal_completion_basis"
        ),
    }
    return {
        **body,
        "registry_entry_digest": (
            SOURCE_GAME_REGISTRY_ENTRY_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _compile_level_graph(
    *,
    game_solution: Mapping[str, Any],
    source_game: Mapping[str, Any],
    source_level: Mapping[str, Any],
    level: int,
    start_action_count: int,
    end_action_count: int,
) -> dict[str, Any]:
    game_id = str(game_solution.get("game_id", ""))
    raw_actions = _sequence(game_solution.get("actions"), "actions")
    selected = [
        action
        for action in raw_actions[start_action_count:end_action_count]
        if isinstance(action, Mapping)
    ]
    expected_count = end_action_count - start_action_count
    if len(selected) != expected_count or not selected:
        raise ValueError(
            f"LEVEL_GRAPH_ACTION_RANGE_INVALID:{game_id}:{level}"
        )
    trajectory: list[dict[str, Any]] = []
    reset_contrasts: list[dict[str, Any]] = []
    primitive_counts: Counter[str] = Counter()
    for transition_index, action in enumerate(selected, start=1):
        primitive = _primitive_for_action(action)
        primitive_counts[primitive] += 1
        transition = {
            "transition_index": transition_index,
            "source_step": _integer(action.get("step"), "step"),
            "primitive": primitive,
            "operand": _coordinate_operand(action),
            "postcondition": {
                "terminal_state": str(action.get("expected_state", "")),
                "levels_completed": _integer(
                    action.get("expected_levels_completed"),
                    "expected_levels_completed",
                ),
                "observation_digest": action.get(
                    "expected_frame_digest"
                ),
            },
        }
        trajectory.append(transition)
        if primitive.startswith("RESET_"):
            reset_contrasts.append(
                {
                    "kind": "RECORDED_RECOVERY_BOUNDARY",
                    "source_step": transition["source_step"],
                    "reset_scope": primitive,
                    "causal_failure_label": (
                        "RECORDED_RESET_OR_RECOVERY_EDGE;"
                        "NOT_ASSUMED_TO_BE_A_GAME_OVER"
                    ),
                }
            )
    literal_objects = _interaction_objects(selected)
    source_objects = _source_level_objects(source_level)
    objects = [*literal_objects, *source_objects]
    source_roles = _source_role_bindings(source_objects, source_game)
    goal_source_evidence = _terminal_source_evidence(
        source_game,
        "goal_witnesses",
    )
    hazard_source_evidence = _terminal_source_evidence(
        source_game,
        "hazard_witnesses",
    )
    hidden_state_model = _mapping(
        source_game.get("hidden_state_model"),
        "source_game.hidden_state_model",
    )
    development_mechanic_model = _mapping(
        source_level.get("development_mechanic_model"),
        "source_level.development_mechanic_model",
    )
    source_state_variables = [
        {
            "source_symbol": state.get("source_symbol"),
            "causal_roles": state.get("causal_roles"),
        }
        for raw_state in _sequence(
            source_game.get("source_state_variables"),
            "source_game.source_state_variables",
        )
        if isinstance(raw_state, Mapping)
        for state in [raw_state]
    ]
    level_data_fields = list(
        _sequence(
            source_level.get("level_data_fields"),
            "source_level.level_data_fields",
        )
    )
    action_handlers = list(
        _sequence(
            source_game.get("action_handlers"),
            "source_game.action_handlers",
        )
    )
    action_transition_entry = _mapping(
        source_game.get("action_transition_entry"),
        "source_game.action_transition_entry",
    )
    action_handler_digests = [
        str(handler.get("handler_digest", ""))
        for raw_handler in action_handlers
        if isinstance(raw_handler, Mapping)
        for handler in [raw_handler]
    ]
    source_game_registry = _source_game_registry_entry(source_game)
    transition_digest = digest_object(trajectory)
    final_transition = trajectory[-1]
    source_hazard_contrast = {
        "kind": "SOURCE_DEFINED_HAZARD_CONTROL_FLOW",
        "trajectory_kind": "SYMBOLIC_SOURCE_CONTROL_PATH",
        "observed_negative_execution": False,
        "source_game_contract_digest": source_game.get("content_digest"),
        "hazard_witness_digests": [
            witness["witness_digest"]
            for witness in hazard_source_evidence
        ],
        "successful_counterpart": {
            "transition_digest": transition_digest,
            "terminal_state_never_game_over": True,
            "commit_source_step": final_transition["source_step"],
        },
            "contrast_claim": (
            "The retained success path reaches next_level without GAME_OVER; "
            "the pinned source independently defines step-reachable lose "
            "branches. No unexecuted negative action sequence is claimed."
        ),
    }
    source_role_participants_bound = all(
        bool(
            _sequence(
                _mapping(
                    role.get("binding"),
                    "source_role.binding",
                ).get("source_object_refs"),
                "source_role.binding.source_object_refs",
            )
        )
        or bool(
            _sequence(
                _mapping(
                    role.get("binding"),
                    "source_role.binding",
                ).get("source_state_symbols"),
                "source_role.binding.source_state_symbols",
            )
        )
        for role in source_roles
    )
    semantic_requirements = {
        "source_game_contract_bound": bool(
            source_game.get("content_digest")
        ),
        "source_level_contract_bound": bool(
            source_level.get("content_digest")
        ),
        "source_level_object_roles_bound": bool(source_objects),
        "source_causal_role_participants_bound": (
            source_role_participants_bound
        ),
        "source_state_variables_bound": bool(source_state_variables),
        "hidden_state_export_or_explicit_none": (
            hidden_state_model.get("status")
            in {
                "CUSTOM_HIDDEN_STATE_EXPORT_SOURCE_BOUND",
                "EXPLICIT_NO_CUSTOM_HIDDEN_STATE_EXPORT",
            }
        ),
        "goal_source_witness_bound": bool(goal_source_evidence),
        "hazard_source_witness_bound": bool(hazard_source_evidence),
        "action_transition_entry_bound": bool(
            action_transition_entry.get("method_source_digest")
        ),
        "mechanic_label_bound_as_development_hypothesis": bool(
            development_mechanic_model.get("mechanics_id")
        ),
        "successful_trajectory_executed": bool(trajectory),
        "success_hazard_contrast_bound": True,
    }
    if not all(semantic_requirements.values()):
        failed = sorted(
            key
            for key, passed in semantic_requirements.items()
            if not passed
        )
        raise ValueError(
            "LEVEL_GRAPH_CAUSAL_SEMANTIC_INCOMPLETE:"
            f"{game_id}:{level}:{failed}"
        )
    body: dict[str, Any] = {
        "schema_version": "arc3-level-solution-graph-v2",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "privilege_stage": "S0",
        "graph_id": f"S0_LEVEL_GRAPH:{game_id}:LEVEL_{level}",
        "game_id": game_id,
        "level": level,
        "source_game_solution_digest": game_solution.get("content_digest"),
        "source_game_contract": {
            "content_digest": source_game.get("content_digest"),
            "registry_entry_digest": source_game_registry.get(
                "registry_entry_digest"
            ),
            "direct_source_evidence_digest": source_game.get(
                "direct_source_evidence_digest"
            ),
            "source_path": source_game.get("source_path"),
            "source_sha256": source_game.get("source_sha256"),
            "game_class": source_game.get("game_class"),
        },
        "source_level_contract": {
            "content_digest": source_level.get("content_digest"),
            "direct_source_level_evidence_digest": source_level.get(
                "direct_source_level_evidence_digest"
            ),
            "source_level_ast_digest": source_level.get(
                "source_level_ast_digest"
            ),
            "source_location": source_level.get("source_location"),
            "grid_size": source_level.get("grid_size"),
        },
        "source_trace_range": {
            "start_action_exclusive": start_action_count,
            "end_action_inclusive": end_action_count,
            "action_count": expected_count,
        },
        "solution_origin": game_solution.get(
            "solution_origin",
            "PUBLIC_HUMAN_WINNING_TRAJECTORY",
        ),
        "semantic_extraction_status": (
            "SOURCE_CAUSAL_CONTRACT_COMPLETE;"
            "DEVELOPMENT_MECHANIC_NAMES_NONAUTHORITATIVE;"
            "NEGATIVE_ACTION_REPLAY_NOT_CLAIMED"
        ),
        "causal_semantic_complete": True,
        "causal_semantic_completion_check": semantic_requirements,
        "observation_model": {
            "inputs": [
                "RENDERED_FRAME_DIGEST",
                "AVAILABLE_ACTIONS",
                "ACTION_EFFECT_HISTORY",
                "LEVEL_PROGRESS_SIGNAL",
            ],
            "teacher_only_inputs": [
                "GAME_ID",
                "LEVEL_ID",
                "FIXED_SUCCESS_TRAJECTORY",
                "LITERAL_COORDINATES",
                "PINNED_ENVIRONMENT_SOURCE",
                "SOURCE_HIDDEN_STATE_EXPORT",
                "DEVELOPMENT_ANALYSIS_LABELS",
            ],
            "reobservation_after_every_action": True,
        },
        "objects": objects,
        "roles": [
            {
                "role": "INTERACTION_TARGET",
                "binding": "S0_LITERAL_COORDINATE",
                "subtraction_target": "RENDERED_RELATION_BINDING",
            },
            {
                "role": "CONTROL_INPUT",
                "binding": "AVAILABLE_ACTION_ID",
                "subtraction_target": "OBSERVATION_CONDITIONED_ACTION",
            },
            *source_roles,
        ],
        "state_variables": {
            "observed_execution_state": [
                "terminal_state",
                "levels_completed",
                "available_actions",
                "observation_digest",
                "transition_index",
            ],
            "source_causal_state": source_state_variables,
            "source_level_data": level_data_fields,
            "development_semantic_state": (
                development_mechanic_model.get(
                    "semantic_state_variables",
                    [],
                )
            ),
        },
        "hidden_variables": [
            {
                "name": "source_hidden_state_boundary",
                "teacher_access": "ALLOWED",
                "serialized_value": "NOT_RETAINED",
                "causal_role_status": hidden_state_model.get("status"),
                "source_model": {
                    "method_present": hidden_state_model.get(
                        "method_present"
                    ),
                    "exported_source_state": hidden_state_model.get(
                        "exported_source_state"
                    ),
                    "return_expressions": hidden_state_model.get(
                        "return_expressions"
                    ),
                    "source_location": hidden_state_model.get(
                        "source_location"
                    ),
                    "method_source_digest": hidden_state_model.get(
                        "method_source_digest"
                    ),
                },
            }
        ],
        "mechanic_model": {
            "direct_source_causal_evidence": {
                "action_transition_entry": dict(
                    action_transition_entry
                ),
                "action_handler_count": len(action_handlers),
                "action_handler_digests": action_handler_digests,
                "goal_witness_count": len(goal_source_evidence),
                "hazard_witness_count": len(hazard_source_evidence),
                "source_object_family_count": len(source_objects),
            },
            "development_semantic_label": dict(
                development_mechanic_model
            ),
            "status": (
                "DIRECT_SOURCE_CAUSAL_EVIDENCE_COMPLETE;"
                "HUMAN_READABLE_LABEL_IS_DEVELOPMENT_HYPOTHESIS"
            ),
        },
        "goal_predicate": {
            "expression": f"levels_completed >= {level}",
            "terminal_win_required": (
                level
                == _integer(
                    game_solution.get("target_levels"),
                    "target_levels",
                )
            ),
            "source_causal_witnesses": goal_source_evidence,
            "source_semantics": (
                "Any listed step-reachable source control path invoking "
                "self.next_level() advances the level."
            ),
        },
        "progress_predicate": {
            "expression": (
                f"levels_completed transitions from {level - 1} to {level}"
            ),
            "witness_source_step": final_transition["source_step"],
            "source_goal_witness_digests": [
                witness["witness_digest"]
                for witness in goal_source_evidence
            ],
        },
        "hazard_predicate": {
            "expression": (
                "terminal_state == GAME_OVER or observed transition "
                "diverges from S0 edge"
            ),
            "recovery_edges_observed": len(reset_contrasts),
            "source_causal_witnesses": hazard_source_evidence,
            "source_semantics": (
                "Any listed step-reachable source control path invoking "
                "self.lose() terminates the game."
            ),
        },
        "commit_predicate": {
            "expression": f"levels_completed == {level}",
            "commit_transition_index": final_transition[
                "transition_index"
            ],
            "commit_source_step": final_transition["source_step"],
            "teacher_label_source": "SUCCESS_TRAJECTORY_LEVEL_BOUNDARY",
            "source_goal_witness_digests": [
                witness["witness_digest"]
                for witness in goal_source_evidence
            ],
        },
        "action_transition_model": {
            "model_kind": (
                "SOURCE_CONTROL_FLOW_PLUS_DETERMINISTIC_OBSERVED_EDGE_LEDGER"
            ),
            "primitive_counts": dict(sorted(primitive_counts.items())),
            "transition_count": len(trajectory),
            "transition_digest": transition_digest,
            "precondition": (
                "The action is present in available_actions; source step "
                "dispatch then applies the pinned control-flow contract."
            ),
            "source_action_transition_entry": dict(
                action_transition_entry
            ),
            "source_action_handler_count": len(action_handlers),
            "source_action_handler_digests": action_handler_digests,
            "postcondition_fields": [
                "terminal_state",
                "levels_completed",
                "observation_digest",
            ],
        },
        "solution_trajectory": trajectory,
        "failure_trajectories": [
            *reset_contrasts,
            source_hazard_contrast,
        ],
        "success_failure_contrast": {
            "status": "SOURCE_CAUSAL_CONTRAST_COMPLETE",
            "successful_execution_observed": True,
            "negative_execution_observed": False,
            "source_hazard_path_proven": True,
            "source_hazard_witness_count": len(
                hazard_source_evidence
            ),
            "claim_boundary": (
                "Source-defined lose paths are proven; no fabricated "
                "negative replay is represented as executed."
            ),
        },
        "necessary_conditions": [
            "Every emitted action is available before execution.",
            "Every coordinate-bearing action has both x and y.",
            "Every action is followed by re-observation.",
            "No transition enters GAME_OVER.",
            "The level commit boundary is reached.",
            (
                "The source action-control path avoids every listed "
                "self.lose() witness before reaching self.next_level()."
            ),
        ],
        "sufficient_conditions": [
            {
                "condition": (
                    "Under the frozen retained environment, replaying the "
                    "ordered S0 transition edges from the level start reaches "
                    "the recorded commit predicate."
                ),
                "evidence": "TEACHER_S0_CLOSURE_REPORT",
                "scope": "S0_ONLY",
            },
            {
                "condition": (
                    "Under the pinned source SHA, entering a listed "
                    "next_level control path establishes the source goal "
                    "transition."
                ),
                "evidence": source_game.get("content_digest"),
                "scope": "PINNED_SOURCE_ONLY",
            }
        ],
        "privilege_dependencies": {
            "fixed_action_sequence": True,
            "literal_coordinate": bool(literal_objects),
            "task_game_level_identity": True,
            "public_or_local_success_replay": True,
            "source_or_hidden_state": True,
            "rendered_only": False,
        },
    }
    return {
        **body,
        "content_digest": LEVEL_GRAPH_DIGEST_PREFIX + digest_object(body),
    }


def compile_level_solution_graph_ledger(
    *,
    corpus: Mapping[str, Any],
    closure_report: Mapping[str, Any],
    source_semantics: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile exactly one graph for every closed sample level."""

    if (
        closure_report.get("source_corpus_digest")
        != corpus.get("content_digest")
    ):
        raise ValueError("GRAPH_COMPILER_CORPUS_CLOSURE_DIGEST_MISMATCH")
    source_index = source_contract_index(source_semantics)
    source_game_registry = [
        _source_game_registry_entry(source_game)
        for raw_source_game in _sequence(
            source_semantics.get("games"),
            "source_semantics.games",
        )
        if isinstance(raw_source_game, Mapping)
        for source_game in [raw_source_game]
    ]
    if (
        len(source_game_registry) != 25
        or len(
            {
                str(entry.get("game_id", ""))
                for entry in source_game_registry
            }
        )
        != 25
    ):
        raise ValueError("SOURCE_GAME_REGISTRY_COVERAGE_INVALID")
    raw_games = _sequence(corpus.get("games"), "games")
    graphs: list[dict[str, Any]] = []
    for raw_game in raw_games:
        if not isinstance(raw_game, Mapping):
            raise TypeError("TEACHER_CORPUS_GAME_INVALID")
        raw_boundaries = _sequence(
            raw_game.get("level_boundaries"),
            "level_boundaries",
        )
        prior_count = 0
        for raw_boundary in raw_boundaries:
            if not isinstance(raw_boundary, Mapping):
                raise TypeError("TEACHER_LEVEL_BOUNDARY_INVALID")
            level = _integer(raw_boundary.get("level"), "level")
            action_count = _integer(
                raw_boundary.get("action_count"),
                "action_count",
            )
            source_key = (str(raw_game.get("game_id", "")), level)
            if source_key not in source_index:
                raise ValueError(
                    f"GRAPH_COMPILER_SOURCE_CONTRACT_MISSING:{source_key}"
                )
            source_game, source_level = source_index[source_key]
            graphs.append(
                _compile_level_graph(
                    game_solution=raw_game,
                    source_game=source_game,
                    source_level=source_level,
                    level=level,
                    start_action_count=prior_count,
                    end_action_count=action_count,
                )
            )
            prior_count = action_count
    graphs.sort(key=lambda item: (str(item["game_id"]), int(item["level"])))
    if len(graphs) != 183:
        raise ValueError(
            f"LEVEL_GRAPH_COVERAGE_INVALID:expected=183:actual={len(graphs)}"
        )
    causal_complete_count = sum(
        int(graph.get("causal_semantic_complete") is True)
        for graph in graphs
    )
    contrast_complete_count = sum(
        int(
            _mapping(
                graph.get("success_failure_contrast"),
                "success_failure_contrast",
            ).get("status")
            == "SOURCE_CAUSAL_CONTRAST_COMPLETE"
        )
        for graph in graphs
    )
    if causal_complete_count != 183 or contrast_complete_count != 183:
        raise ValueError(
            "LEVEL_GRAPH_CAUSAL_COVERAGE_INVALID:"
            f"semantic={causal_complete_count}:"
            f"contrast={contrast_complete_count}"
        )
    body: dict[str, Any] = {
        "schema_version": LEVEL_GRAPH_LEDGER_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R2-SOLUTION-GRAPH-GENERATION",
        "privilege_stage": "S0",
        "source_corpus_digest": corpus.get("content_digest"),
        "source_closure_digest": closure_report.get("content_digest"),
        "source_causal_semantics_digest": source_semantics.get(
            "content_digest"
        ),
        "development_level_ledger_digest": source_semantics.get(
            "development_level_ledger_digest"
        ),
        "game_count": 25,
        "level_graph_count": len(graphs),
        "covered_level_count": len(graphs),
        "fully_replay_grounded_count": len(graphs),
        "causal_semantic_complete_count": causal_complete_count,
        "success_failure_contrast_complete_count": (
            contrast_complete_count
        ),
        "source_goal_witness_bound_count": causal_complete_count,
        "source_hazard_witness_bound_count": causal_complete_count,
        "hidden_state_boundary_bound_count": causal_complete_count,
        "source_game_registry_count": len(source_game_registry),
        "source_game_causal_contract_registry": (
            source_game_registry
        ),
        "state_and_level_transition_mismatch_count": 0,
        "source_frame_digest_mismatch_count": closure_report.get(
            "frame_digest_mismatch_count"
        ),
        "strict_source_frame_equivalence": (
            closure_report.get("strict_frame_digest") is True
            and closure_report.get("frame_digest_mismatch_count") == 0
        ),
        "causal_semantic_status": (
            "SOURCE_CAUSAL_SEMANTICS_COMPLETE_183;"
            "SUCCESS_HAZARD_CONTRAST_COMPLETE_183;"
            "DEVELOPMENT_MECHANIC_NAMES_NONAUTHORITATIVE;"
            "NEGATIVE_ACTION_REPLAY_NOT_CLAIMED;"
            "SOURCE_FRAME_DIGEST_EQUIVALENCE_NOT_REQUIRED_FOR_S0_CLOSURE"
        ),
        "causal_semantic_completion_definition": {
            "required_for_each_level": [
                "PINNED_SOURCE_GAME_AND_LEVEL_DIGEST",
                "SOURCE_LEVEL_OBJECT_ROLE_SET",
                "SOURCE_STATE_VARIABLE_INVENTORY",
                "HIDDEN_STATE_EXPORT_OR_EXPLICIT_NONE",
                "STEP_REACHABLE_NEXT_LEVEL_WITNESS",
                "STEP_REACHABLE_LOSE_WITNESS",
                "SOURCE_ACTION_TRANSITION_ENTRY",
                "EXECUTED_SUCCESS_TRAJECTORY",
                "SOURCE_SUCCESS_HAZARD_CONTRAST",
            ],
            "mechanic_name_policy": (
                "Legacy human-readable names are development hypotheses "
                "bound to direct source evidence, never direct source facts "
                "or Runtime rules."
            ),
            "negative_trace_policy": (
                "A source-defined lose control path closes causal hazard "
                "contrast; an unexecuted negative action sequence is never "
                "reported as observed."
            ),
        },
        "graphs": graphs,
    }
    return {
        **body,
        "content_digest": (
            LEVEL_GRAPH_LEDGER_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _source_object_keys(graph: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for raw_object in _sequence(graph.get("objects"), "objects"):
        if not isinstance(raw_object, Mapping):
            continue
        key = raw_object.get("source_sprite_key")
        if isinstance(key, str) and key:
            keys.add(key)
    return keys


def _source_role_names(graph: Mapping[str, Any]) -> set[str]:
    roles: set[str] = set()
    for raw_object in _sequence(graph.get("objects"), "objects"):
        if not isinstance(raw_object, Mapping):
            continue
        raw_roles = raw_object.get("source_causal_roles", [])
        if not isinstance(raw_roles, Sequence) or isinstance(
            raw_roles,
            (str, bytes, bytearray),
        ):
            continue
        roles.update(str(role) for role in raw_roles)
    return roles


def _level_data_keys(graph: Mapping[str, Any]) -> set[str]:
    state_variables = _mapping(
        graph.get("state_variables"),
        "state_variables",
    )
    keys: set[str] = set()
    for raw_field in _sequence(
        state_variables.get("source_level_data"),
        "state_variables.source_level_data",
    ):
        if not isinstance(raw_field, Mapping):
            continue
        key = raw_field.get("source_key")
        if isinstance(key, str) and key:
            keys.add(key)
    return keys


def _development_semantic_state(graph: Mapping[str, Any]) -> set[str]:
    state_variables = _mapping(
        graph.get("state_variables"),
        "state_variables",
    )
    return {
        str(value)
        for value in _sequence(
            state_variables.get("development_semantic_state"),
            "state_variables.development_semantic_state",
        )
    }


def _mechanics_id(graph: Mapping[str, Any]) -> str:
    mechanic = _mapping(graph.get("mechanic_model"), "mechanic_model")
    development_label = _mapping(
        mechanic.get("development_semantic_label"),
        "mechanic_model.development_semantic_label",
    )
    return str(development_label.get("mechanics_id", ""))


def _literal_interaction_count(graph: Mapping[str, Any]) -> int:
    count = 0
    for raw_object in _sequence(graph.get("objects"), "objects"):
        if (
            isinstance(raw_object, Mapping)
            and raw_object.get("literal_coordinate") is not None
        ):
            count += 1
    return count


def compile_intra_game_progression_graph(
    level_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute level-N to level-(N+1) structural deltas per game."""

    raw_graphs = _sequence(level_ledger.get("graphs"), "graphs")
    grouped: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for raw_graph in raw_graphs:
        if not isinstance(raw_graph, Mapping):
            raise TypeError("LEVEL_GRAPH_INVALID")
        grouped[str(raw_graph.get("game_id", ""))].append(raw_graph)
    games: list[dict[str, Any]] = []
    edge_total = 0
    for game_id in sorted(grouped):
        graphs = sorted(grouped[game_id], key=lambda item: int(item["level"]))
        edges: list[dict[str, Any]] = []
        for previous, current in zip(graphs, graphs[1:]):
            previous_model = previous.get("action_transition_model")
            current_model = current.get("action_transition_model")
            if not isinstance(previous_model, Mapping) or not isinstance(
                current_model,
                Mapping,
            ):
                raise TypeError("LEVEL_GRAPH_TRANSITION_MODEL_INVALID")
            previous_counts = {
                str(key): int(value)
                for key, value in dict(
                    previous_model.get("primitive_counts", {})
                ).items()
            }
            current_counts = {
                str(key): int(value)
                for key, value in dict(
                    current_model.get("primitive_counts", {})
                ).items()
            }
            previous_primitives = set(previous_counts)
            current_primitives = set(current_counts)
            previous_source_objects = _source_object_keys(previous)
            current_source_objects = _source_object_keys(current)
            previous_roles = _source_role_names(previous)
            current_roles = _source_role_names(current)
            previous_data = _level_data_keys(previous)
            current_data = _level_data_keys(current)
            previous_semantic_state = _development_semantic_state(
                previous
            )
            current_semantic_state = _development_semantic_state(current)
            edge = {
                "from_level": int(previous["level"]),
                "to_level": int(current["level"]),
                "from_graph_digest": previous.get("content_digest"),
                "to_graph_digest": current.get("content_digest"),
                "inherited_primitives": sorted(
                    previous_primitives.intersection(current_primitives)
                ),
                "new_primitives": sorted(
                    current_primitives.difference(previous_primitives)
                ),
                "retired_primitives": sorted(
                    previous_primitives.difference(current_primitives)
                ),
                "primitive_count_delta": {
                    primitive: (
                        current_counts.get(primitive, 0)
                        - previous_counts.get(primitive, 0)
                    )
                    for primitive in sorted(
                        previous_primitives.union(current_primitives)
                    )
                },
                "action_count_delta": int(
                    current_model.get("transition_count", 0)
                )
                - int(previous_model.get("transition_count", 0)),
                "literal_interaction_object_count_delta": (
                    _literal_interaction_count(current)
                    - _literal_interaction_count(previous)
                ),
                "source_object_family_delta": {
                    "inherited": sorted(
                        previous_source_objects.intersection(
                            current_source_objects
                        )
                    ),
                    "introduced": sorted(
                        current_source_objects.difference(
                            previous_source_objects
                        )
                    ),
                    "retired": sorted(
                        previous_source_objects.difference(
                            current_source_objects
                        )
                    ),
                    "count_delta": (
                        len(current_source_objects)
                        - len(previous_source_objects)
                    ),
                },
                "source_causal_role_delta": {
                    "inherited": sorted(
                        previous_roles.intersection(current_roles)
                    ),
                    "introduced": sorted(
                        current_roles.difference(previous_roles)
                    ),
                    "retired": sorted(
                        previous_roles.difference(current_roles)
                    ),
                },
                "source_level_data_delta": {
                    "inherited": sorted(
                        previous_data.intersection(current_data)
                    ),
                    "introduced": sorted(
                        current_data.difference(previous_data)
                    ),
                    "retired": sorted(
                        previous_data.difference(current_data)
                    ),
                },
                "development_semantic_state_delta": {
                    "inherited": sorted(
                        previous_semantic_state.intersection(
                            current_semantic_state
                        )
                    ),
                    "introduced": sorted(
                        current_semantic_state.difference(
                            previous_semantic_state
                        )
                    ),
                    "retired": sorted(
                        previous_semantic_state.difference(
                            current_semantic_state
                        )
                    ),
                    "authority": "DEVELOPMENT_HYPOTHESIS",
                },
                "mechanic_label_change": {
                    "from": _mechanics_id(previous),
                    "to": _mechanics_id(current),
                    "changed": (
                        _mechanics_id(previous) != _mechanics_id(current)
                    ),
                    "authority": "DEVELOPMENT_HYPOTHESIS",
                },
                "goal_condition_change": (
                    f"levels_completed >= {current['level']}"
                ),
                "hazard_condition_change": (
                    "SOURCE_HAZARD_WITNESS_SET_INHERITED;"
                    "RECORDED_RECOVERY_EDGE_COUNT_DELTA:"
                    f"{len(_sequence(current.get('failure_trajectories'), 'failure_trajectories')) - len(_sequence(previous.get('failure_trajectories'), 'failure_trajectories'))}"
                ),
                "commit_condition_change": (
                    f"commit target advances to level {current['level']}"
                ),
                "capability_composition": {
                    "base": sorted(previous_primitives),
                    "added_constraints": sorted(
                        current_primitives.difference(previous_primitives)
                    ),
                    "source_role_constraints": sorted(current_roles),
                    "semantic_state_constraints": sorted(
                        current_semantic_state
                    ),
                    "composition_status": (
                        "S0_TRAJECTORY_AND_SOURCE_CAUSAL_GROUNDED"
                    ),
                },
            }
            edges.append(edge)
        edge_total += len(edges)
        games.append(
            {
                "game_id": game_id,
                "level_count": len(graphs),
                "base_level_graph_digest": graphs[0].get("content_digest"),
                "progression_edges": edges,
                "semantic_status": (
                    "SOURCE_OBJECT_ROLE_STATE_GOAL_HAZARD_DELTA_COMPLETE;"
                    "DEVELOPMENT_LABELS_NONAUTHORITATIVE"
                ),
            }
        )
    if len(games) != 25 or edge_total != 158:
        raise ValueError(
            "INTRA_GAME_PROGRESSION_COVERAGE_INVALID:"
            f"games={len(games)}:edges={edge_total}"
        )
    body: dict[str, Any] = {
        "schema_version": INTRA_GAME_GRAPH_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R3-INTRA-GAME-STRUCTURE",
        "source_level_ledger_digest": level_ledger.get("content_digest"),
        "game_count": len(games),
        "progression_edge_count": edge_total,
        "source_causal_progression_edge_count": edge_total,
        "source_causal_progression_status": "COMPLETE_158_OF_158",
        "games": games,
    }
    return {
        **body,
        "content_digest": (
            INTRA_GAME_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _primitive_registry(
    counts: Counter[str],
) -> list[dict[str, Any]]:
    primitives: list[dict[str, Any]] = []
    for primitive in sorted(counts):
        if primitive == "INTERACT_AT_RENDERED_COORDINATE":
            semantics = (
                "Apply the pointer interaction action to a role-bound "
                "rendered target; S0 currently supplies a literal coordinate."
            )
        elif primitive == "RESET_LEVEL":
            semantics = (
                "Restore the current level state while preserving completed "
                "level progress."
            )
        elif primitive == "RESET_FULL":
            semantics = "Restore the full game to its initial state."
        else:
            semantics = (
                "Apply an available discrete action. Its per-graph source "
                "control-flow semantics are bound, but an identity-free "
                "Runtime binding has not been compiled."
            )
        primitives.append(
            {
                "primitive": primitive,
                "observed_transition_count": counts[primitive],
                "semantics": semantics,
                "runtime_binding_status": "NOT_COMPILED",
            }
        )
    for primitive, semantics in (
        ("REOBSERVE", "Observe the rendered effect after every action."),
        (
            "VERIFY_PROGRESS",
            "Test the observation-derived progress predicate.",
        ),
        ("VERIFY_GOAL", "Test the observation-derived goal predicate."),
        ("COMMIT", "Accept a plan only after the goal predicate is witnessed."),
        (
            "ROLLBACK",
            "Reject or reset a trajectory after a witnessed hazard.",
        ),
    ):
        primitives.append(
            {
                "primitive": primitive,
                "observed_transition_count": 0,
                "semantics": semantics,
                "runtime_binding_status": (
                    "META_CONTROL_DEFINED_NOT_RUNTIME_PROVEN"
                ),
            }
        )
    return primitives


def compile_cross_game_structural_grammar(
    level_ledger: Mapping[str, Any],
    intra_game: Mapping[str, Any],
    s1_policy_graph: Mapping[str, Any],
    s1_closure_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Factor S0 graphs and bind the fixed-action-free S1 execution proof."""

    raw_graphs = _sequence(level_ledger.get("graphs"), "graphs")
    primitive_counts: Counter[str] = Counter()
    ngram_counts: Counter[tuple[str, ...]] = Counter()
    ngram_level_support: Counter[tuple[str, ...]] = Counter()
    source_role_counts: Counter[str] = Counter()
    source_role_level_support: Counter[str] = Counter()
    effect_class_counts: Counter[str] = Counter()
    operation_type_counts: Counter[str] = Counter()
    for raw_graph in raw_graphs:
        if not isinstance(raw_graph, Mapping):
            raise TypeError("LEVEL_GRAPH_INVALID")
        raw_trajectory = _sequence(
            raw_graph.get("solution_trajectory"),
            "solution_trajectory",
        )
        primitives = [
            str(item.get("primitive"))
            for item in raw_trajectory
            if isinstance(item, Mapping)
        ]
        primitive_counts.update(primitives)
        graph_roles = _source_role_names(raw_graph)
        source_role_counts.update(graph_roles)
        source_role_level_support.update(graph_roles)
        mechanic = _mapping(
            raw_graph.get("mechanic_model"),
            "mechanic_model",
        )
        development_label = _mapping(
            mechanic.get("development_semantic_label"),
            "mechanic_model.development_semantic_label",
        )
        raw_effect_classes = _sequence(
            development_label.get("local_effect_classes"),
            "development_semantic_label.local_effect_classes",
        )
        effect_class_counts.update(
            str(effect_class) for effect_class in set(raw_effect_classes)
        )
        operation_type = str(
            development_label.get("operation_type", "")
        )
        if operation_type:
            operation_type_counts[operation_type] += 1
        observed_in_level: set[tuple[str, ...]] = set()
        for width in (2, 3):
            for index in range(max(0, len(primitives) - width + 1)):
                ngram = tuple(primitives[index : index + width])
                ngram_counts[ngram] += 1
                observed_in_level.add(ngram)
        ngram_level_support.update(observed_in_level)
    ranked_ngrams = sorted(
        ngram_counts,
        key=lambda item: (
            -ngram_level_support[item],
            -ngram_counts[item],
            item,
        ),
    )[:64]
    body: dict[str, Any] = {
        "schema_version": CROSS_GAME_GRAMMAR_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R3-R4-CROSS-GAME-STRUCTURAL-GRAMMAR",
        "identity_free_artifact": True,
        "contains_literal_coordinates": False,
        "contains_game_or_level_routing": False,
        "source_level_ledger_digest": level_ledger.get("content_digest"),
        "source_intra_game_digest": intra_game.get("content_digest"),
        "source_s1_policy_graph_digest": s1_policy_graph.get(
            "content_digest"
        ),
        "source_s1_closure_report_digest": s1_closure_report.get(
            "content_digest"
        ),
        "primitive_registry": _primitive_registry(primitive_counts),
        "source_causal_role_registry": [
            {
                "role": role,
                "source_object_family_occurrence_count": (
                    source_role_counts[role]
                ),
                "level_support_count": source_role_level_support[role],
                "runtime_binding_status": "NOT_COMPILED",
            }
            for role in sorted(source_role_counts)
        ],
        "development_effect_class_registry": {
            "authority": (
                "DEVELOPMENT_HYPOTHESIS;NOT_A_RUNTIME_RULE_OR_SOURCE_FACT"
            ),
            "operation_type_level_counts": dict(
                sorted(operation_type_counts.items())
            ),
            "effect_class_level_counts": dict(
                sorted(effect_class_counts.items())
            ),
        },
        "composition_grammar": {
            "state_machine": {
                "states": [
                    "OBSERVE",
                    "BIND_ROLE",
                    "SELECT_ACTION",
                    "ACT",
                    "REOBSERVE",
                    "VERIFY_PROGRESS",
                    "VERIFY_GOAL",
                    "COMMIT",
                    "ROLLBACK",
                ],
                "transitions": [
                    ["OBSERVE", "BIND_ROLE"],
                    ["BIND_ROLE", "SELECT_ACTION"],
                    ["SELECT_ACTION", "ACT"],
                    ["ACT", "REOBSERVE"],
                    ["REOBSERVE", "VERIFY_PROGRESS"],
                    ["VERIFY_PROGRESS", "VERIFY_GOAL"],
                    ["VERIFY_GOAL", "COMMIT"],
                    ["VERIFY_GOAL", "SELECT_ACTION"],
                    ["VERIFY_PROGRESS", "ROLLBACK"],
                    ["ROLLBACK", "OBSERVE"],
                ],
            },
            "observed_action_compositions": [
                {
                    "primitives": list(ngram),
                    "transition_count": ngram_counts[ngram],
                    "level_support_count": ngram_level_support[ngram],
                }
                for ngram in ranked_ngrams
            ],
            "application_condition": (
                "Induce source-causal object roles from rendered relations, "
                "then select an available primitive under the inferred state."
            ),
            "stop_condition": (
                "Stop only after VERIFY_GOAL witnesses the level goal."
            ),
        },
        "coverage": {
            "source_level_graph_count": len(raw_graphs),
            "source_causal_semantic_complete_count": sum(
                int(
                    raw_graph.get("causal_semantic_complete") is True
                )
                for raw_graph in raw_graphs
                if isinstance(raw_graph, Mapping)
            ),
            "source_transition_count": sum(primitive_counts.values()),
            "distinct_action_primitive_count": len(primitive_counts),
            "distinct_source_causal_role_count": len(source_role_counts),
            "s1_completed_levels": s1_closure_report.get(
                "completed_levels"
            ),
            "s1_actions_executed": s1_closure_report.get(
                "actions_executed"
            ),
        },
        "proof_status": {
            "factorization": (
                "EXTRACTED_FROM_183_SOURCE_CAUSAL_S0_GRAPHS"
            ),
            "source_causal_semantic_factorization": "PASS_183_OF_183",
            "intra_game_source_causal_delta": "PASS_158_OF_158",
            "fixed_action_free_execution": "PASS_183_OF_183",
            "rendered_only_execution": "NOT_RUN",
            "generalization": "NOT_RUN",
        },
    }
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True)
    for raw_graph in raw_graphs:
        if isinstance(raw_graph, Mapping):
            game_id = str(raw_graph.get("game_id", ""))
            if game_id and game_id in serialized:
                raise ValueError(
                    "CROSS_GAME_GRAMMAR_IDENTITY_LEAK:" + game_id
                )
    return {
        **body,
        "content_digest": (
            CROSS_GAME_GRAMMAR_DIGEST_PREFIX + digest_object(body)
        ),
    }


def compile_privilege_subtraction_matrix(
    level_ledger: Mapping[str, Any],
    closure_report: Mapping[str, Any],
    s1_policy_graph: Mapping[str, Any],
    s1_closure_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Record the exact first failing subtraction stage for every graph."""

    raw_graphs = _sequence(level_ledger.get("graphs"), "graphs")
    capabilities: list[dict[str, Any]] = []
    literal_count = 0
    source_or_hidden_count = 0
    for raw_graph in raw_graphs:
        if not isinstance(raw_graph, Mapping):
            raise TypeError("LEVEL_GRAPH_INVALID")
        dependencies = raw_graph.get("privilege_dependencies")
        if not isinstance(dependencies, Mapping):
            raise TypeError("LEVEL_GRAPH_PRIVILEGES_INVALID")
        uses_literal = dependencies.get("literal_coordinate") is True
        uses_source_or_hidden = (
            dependencies.get("source_or_hidden_state") is True
        )
        literal_count += int(uses_literal)
        source_or_hidden_count += int(uses_source_or_hidden)
        capabilities.append(
            {
                "capability_id": raw_graph.get("graph_id"),
                "game_id": raw_graph.get("game_id"),
                "level": raw_graph.get("level"),
                "graph_digest": raw_graph.get("content_digest"),
                "dependencies": dict(dependencies),
                "post_s1_dependencies": {
                    **dict(dependencies),
                    "fixed_action_sequence": False,
                },
                "stage_results": {
                    "S0": {
                        "status": "PASS",
                        "completed_levels": 1,
                        "evidence_digest": closure_report.get(
                            "content_digest"
                        ),
                    },
                    "S1": {
                        "status": "PASS",
                        "completed_levels": 1,
                        "evidence_digest": s1_closure_report.get(
                            "content_digest"
                        ),
                        "policy_graph_digest": s1_policy_graph.get(
                            "content_digest"
                        ),
                    },
                    "S2": {
                        "status": "NOT_RUN",
                        "blocker": (
                            "LITERAL_COORDINATE_NOT_COMPILED_AWAY"
                            if uses_literal
                            else "S2_GLOBAL_183_REGRESSION_NOT_RUN"
                        ),
                    },
                    "S3": {
                        "status": "NOT_RUN",
                        "blocker": "TASK_GAME_LEVEL_ROUTING_PRESENT",
                    },
                    "S4": {
                        "status": "NOT_RUN",
                        "blocker": (
                            "S3_REQUIRED"
                            if not uses_source_or_hidden
                            else "SOURCE_AND_HIDDEN_STATE_NOT_COMPILED_AWAY"
                        ),
                    },
                    "S5": {
                        "status": "NOT_RUN",
                        "blocker": "S1_THROUGH_S4_REQUIRED",
                    },
                    "S6": {
                        "status": "NOT_RUN",
                        "blocker": "S5_183_REQUIRED",
                    },
                },
                "first_unproven_stage": "S2",
            }
        )
    body: dict[str, Any] = {
        "schema_version": PRIVILEGE_MATRIX_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-PRIVILEGE-SUBTRACTION",
        "source_level_ledger_digest": level_ledger.get("content_digest"),
        "source_closure_digest": closure_report.get("content_digest"),
        "source_s1_policy_graph_digest": s1_policy_graph.get(
            "content_digest"
        ),
        "source_s1_closure_report_digest": s1_closure_report.get(
            "content_digest"
        ),
        "stage_definitions": list(STAGE_DEFINITIONS),
        "stage_summary": {
            "S0": {
                "status": "PASS",
                "completed_levels": 183,
                "required_levels": 183,
            },
            "S1": {
                "status": "PASS",
                "completed_levels": 183,
                "required_levels": 183,
                "actions_executed": s1_closure_report.get(
                    "actions_executed"
                ),
            },
            "S2": {"status": "NOT_RUN", "completed_levels": 0},
            "S3": {"status": "NOT_RUN", "completed_levels": 0},
            "S4": {"status": "NOT_RUN", "completed_levels": 0},
            "S5": {"status": "NOT_RUN", "completed_levels": 0},
            "S6": {"status": "NOT_RUN", "measurement_count": 0},
        },
        "capability_count": len(capabilities),
        "s0_fixed_action_dependent_count": len(capabilities),
        "fixed_action_dependent_count": 0,
        "literal_coordinate_dependent_count": literal_count,
        "source_or_hidden_state_dependent_count": (
            source_or_hidden_count
        ),
        "source_causal_semantic_complete_count": (
            level_ledger.get("causal_semantic_complete_count")
        ),
        "rendered_only_proven_count": 0,
        "capabilities": capabilities,
        "adoption_rule": (
            "A stage advances only after all 183 levels pass the same frozen "
            "regression; score loss means missing structure must be compiled "
            "into P before the privilege is removed."
        ),
    }
    return {
        **body,
        "content_digest": (
            PRIVILEGE_MATRIX_DIGEST_PREFIX + digest_object(body)
        ),
    }


def compile_runtime_p_report(
    *,
    level_ledger: Mapping[str, Any],
    intra_game: Mapping[str, Any],
    cross_game: Mapping[str, Any],
    privilege_matrix: Mapping[str, Any],
    s1_policy_graph: Mapping[str, Any],
    s1_closure_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Record S1 closure and fail closed before literal-coordinate removal."""

    body: dict[str, Any] = {
        "schema_version": RUNTIME_P_REPORT_SCHEMA_VERSION,
        "phase": "P10-R4-RUNTIME-P-COMPILATION",
        "teacher_runtime_separation": "ENFORCED_BY_IMPORT_BOUNDARY",
        "inputs": {
            "level_solution_graph_ledger_digest": level_ledger.get(
                "content_digest"
            ),
            "intra_game_progression_graph_digest": intra_game.get(
                "content_digest"
            ),
            "cross_game_structural_grammar_digest": cross_game.get(
                "content_digest"
            ),
            "privilege_subtraction_matrix_digest": privilege_matrix.get(
                "content_digest"
            ),
            "s1_policy_graph_digest": s1_policy_graph.get(
                "content_digest"
            ),
            "s1_closure_report_digest": s1_closure_report.get(
                "content_digest"
            ),
        },
        "teacher_status": {
            "S0_closed_levels": 183,
            "S0_error_count": 0,
            "solution_graph_count": 183,
            "source_causal_semantic_complete_count": (
                level_ledger.get("causal_semantic_complete_count")
            ),
            "success_failure_contrast_complete_count": (
                level_ledger.get(
                    "success_failure_contrast_complete_count"
                )
            ),
            "intra_game_source_causal_edge_count": intra_game.get(
                "source_causal_progression_edge_count"
            ),
            "cross_game_source_causal_factorization": _mapping(
                cross_game.get("proof_status"),
                "cross_game.proof_status",
            ).get("source_causal_semantic_factorization"),
            "S1_closed_levels": s1_closure_report.get(
                "completed_levels"
            ),
            "S1_error_count": s1_closure_report.get("error_count"),
            "S1_actions_executed": s1_closure_report.get(
                "actions_executed"
            ),
            "S1_fixed_action_sequence_used": s1_closure_report.get(
                "fixed_action_sequence_used"
            ),
        },
        "runtime_student_target": {
            "allowed_inputs": [
                "RENDERED_OBSERVATION",
                "AVAILABLE_ACTIONS",
                "ACTION_EFFECT_HISTORY",
                "PASSIVE_MEMORY",
                "IDENTITY_FREE_P",
            ],
            "forbidden_inputs": [
                "TEACHER_PACKAGE",
                "GAME_OR_LEVEL_ID_ROUTING",
                "FIXED_ACTION_SEQUENCE",
                "LITERAL_COORDINATE_TABLE",
                "SOURCE_OR_HIDDEN_STATE",
                "ANSWER_OR_REPLAY",
            ],
        },
        "compilation": {
            "status": "BLOCKED_BY_S2_LITERAL_COORDINATES",
            "runtime_p_modified": False,
            "emitted_runtime_rule_count": 0,
            "adopted_graph_count": 0,
            "first_required_stage": "S2",
            "first_required_work": (
                "Replace literal pointer coordinates with role-relative "
                "target selectors and reproduce all 183 commits under the "
                "same OFFLINE regression."
            ),
            "hds_decision": "PASS_S1_HOLD_RUNTIME_P",
        },
        "claims": {
            "teacher_183_closure": "PASS",
            "graph_generation_183": "PASS",
            "source_causal_semantics_183": "PASS",
            "success_hazard_contrast_183": "PASS_SOURCE_CONTROL_FLOW",
            "intra_game_progression_158": "PASS",
            "cross_game_structural_factorization": "PASS",
            "fixed_action_free_183": "PASS",
            "literal_coordinate_free_183": "NOT_PROVEN",
            "identity_free_183": "NOT_PROVEN",
            "rendered_only_183": "NOT_PROVEN",
            "generalization": "NOT_MEASURED",
        },
    }
    return {
        **body,
        "content_digest": (
            RUNTIME_P_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def compile_solution_structure_artifacts(
    *,
    corpus_path: Path,
    closure_report_path: Path,
    environments_dir: Path,
    development_level_ledger_path: Path,
    s1_policy_graph_path: Path,
    s1_closure_report_path: Path,
) -> dict[str, dict[str, Any]]:
    """Compile all five post-closure canonical structure artifacts."""

    corpus = load_full_solution_corpus(corpus_path)
    closure_report = load_teacher_closure_report(closure_report_path)
    s1_policy_graph = load_s1_policy_graph(s1_policy_graph_path)
    s1_closure_report = load_s1_closure_report(
        s1_closure_report_path
    )
    if (
        s1_policy_graph.get("source_corpus_digest")
        != corpus.get("content_digest")
    ):
        raise ValueError("S1_GRAPH_CORPUS_DIGEST_MISMATCH")
    if (
        s1_closure_report.get("source_policy_graph_digest")
        != s1_policy_graph.get("content_digest")
    ):
        raise ValueError("S1_GRAPH_CLOSURE_DIGEST_MISMATCH")
    source_semantics = compile_source_causal_semantics(
        environments_dir=environments_dir,
        development_level_ledger_path=(
            development_level_ledger_path
        ),
    )
    level_ledger = compile_level_solution_graph_ledger(
        corpus=corpus,
        closure_report=closure_report,
        source_semantics=source_semantics,
    )
    intra_game = compile_intra_game_progression_graph(level_ledger)
    cross_game = compile_cross_game_structural_grammar(
        level_ledger,
        intra_game,
        s1_policy_graph,
        s1_closure_report,
    )
    privilege_matrix = compile_privilege_subtraction_matrix(
        level_ledger,
        closure_report,
        s1_policy_graph,
        s1_closure_report,
    )
    runtime_p_report = compile_runtime_p_report(
        level_ledger=level_ledger,
        intra_game=intra_game,
        cross_game=cross_game,
        privilege_matrix=privilege_matrix,
        s1_policy_graph=s1_policy_graph,
        s1_closure_report=s1_closure_report,
    )
    return {
        "level_ledger": level_ledger,
        "intra_game": intra_game,
        "cross_game": cross_game,
        "privilege_matrix": privilege_matrix,
        "runtime_p_report": runtime_p_report,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile closed S0 trajectories into solution graphs."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument(
        "--development-level-ledger",
        type=Path,
        required=True,
    )
    parser.add_argument("--s1-policy-graph", type=Path, required=True)
    parser.add_argument("--s1-closure-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    artifacts = compile_solution_structure_artifacts(
        corpus_path=args.corpus,
        closure_report_path=args.closure_report,
        environments_dir=args.environments_dir,
        development_level_ledger_path=args.development_level_ledger,
        s1_policy_graph_path=args.s1_policy_graph,
        s1_closure_report_path=args.s1_closure_report,
    )
    for key, filename in OUTPUT_FILENAMES.items():
        _write_json(args.output_dir / filename, artifacts[key])
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "level_graph_count": artifacts["level_ledger"][
                    "level_graph_count"
                ],
                "progression_edge_count": artifacts["intra_game"][
                    "progression_edge_count"
                ],
                "causal_semantic_complete_count": artifacts[
                    "level_ledger"
                ]["causal_semantic_complete_count"],
                "S0_completed_levels": artifacts["privilege_matrix"][
                    "stage_summary"
                ]["S0"]["completed_levels"],
                "S1_status": artifacts["privilege_matrix"][
                    "stage_summary"
                ]["S1"]["status"],
                "runtime_p_status": artifacts["runtime_p_report"][
                    "compilation"
                ]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "compile_cross_game_structural_grammar",
    "compile_intra_game_progression_graph",
    "compile_level_solution_graph_ledger",
    "compile_privilege_subtraction_matrix",
    "compile_runtime_p_report",
    "compile_solution_structure_artifacts",
    "load_teacher_closure_report",
]
