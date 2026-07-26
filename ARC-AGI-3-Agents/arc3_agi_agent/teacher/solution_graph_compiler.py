"""Compile closed S0 Teacher trajectories into solution-structure artifacts.

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

LEVEL_GRAPH_LEDGER_SCHEMA_VERSION = (
    "arc3-level-solution-graph-ledger-v1"
)
INTRA_GAME_GRAPH_SCHEMA_VERSION = (
    "arc3-intra-game-progression-graph-v1"
)
CROSS_GAME_GRAMMAR_SCHEMA_VERSION = (
    "arc3-cross-game-structural-grammar-v1"
)
PRIVILEGE_MATRIX_SCHEMA_VERSION = (
    "arc3-privilege-subtraction-matrix-v1"
)
RUNTIME_P_REPORT_SCHEMA_VERSION = (
    "arc3-runtime-p-compilation-report-v1"
)

LEVEL_GRAPH_LEDGER_DIGEST_PREFIX = "arc3_level_solution_graph_ledger:"
LEVEL_GRAPH_DIGEST_PREFIX = "arc3_level_solution_graph:"
INTRA_GAME_GRAPH_DIGEST_PREFIX = "arc3_intra_game_progression_graph:"
CROSS_GAME_GRAMMAR_DIGEST_PREFIX = "arc3_cross_game_structural_grammar:"
PRIVILEGE_MATRIX_DIGEST_PREFIX = "arc3_privilege_subtraction_matrix:"
RUNTIME_P_REPORT_DIGEST_PREFIX = "arc3_runtime_p_compilation_report:"

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


def _compile_level_graph(
    *,
    game_solution: Mapping[str, Any],
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
                        "UNRESOLVED_UNTIL_FAILURE_CONTRAST_COMPILATION"
                    ),
                }
            )
    objects = _interaction_objects(selected)
    transition_digest = digest_object(trajectory)
    final_transition = trajectory[-1]
    body: dict[str, Any] = {
        "schema_version": "arc3-level-solution-graph-v1",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "privilege_stage": "S0",
        "graph_id": f"S0_LEVEL_GRAPH:{game_id}:LEVEL_{level}",
        "game_id": game_id,
        "level": level,
        "source_game_solution_digest": game_solution.get("content_digest"),
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
            "TRAJECTORY_GROUNDED_SOURCE_ROLE_LABELING_PENDING"
        ),
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
            {
                "role": "ACTOR",
                "binding": "UNRESOLVED",
                "subtraction_target": "RENDERED_OBJECT_BINDING",
            },
        ],
        "state_variables": [
            "terminal_state",
            "levels_completed",
            "available_actions",
            "observation_digest",
            "transition_index",
        ],
        "hidden_variables": [
            {
                "name": "environment_internal_state",
                "teacher_access": "ALLOWED",
                "serialized_value": "NOT_RETAINED",
                "causal_role_status": "PENDING_SOURCE_CAUSAL_EXTRACTION",
            }
        ],
        "goal_predicate": {
            "expression": f"levels_completed >= {level}",
            "terminal_win_required": (
                level
                == _integer(
                    game_solution.get("target_levels"),
                    "target_levels",
                )
            ),
        },
        "progress_predicate": {
            "expression": (
                f"levels_completed transitions from {level - 1} to {level}"
            ),
            "witness_source_step": final_transition["source_step"],
        },
        "hazard_predicate": {
            "expression": (
                "terminal_state == GAME_OVER or observed transition "
                "diverges from S0 edge"
            ),
            "recovery_edges_observed": len(reset_contrasts),
        },
        "commit_predicate": {
            "expression": f"levels_completed == {level}",
            "commit_transition_index": final_transition[
                "transition_index"
            ],
            "commit_source_step": final_transition["source_step"],
            "teacher_label_source": "SUCCESS_TRAJECTORY_LEVEL_BOUNDARY",
        },
        "action_transition_model": {
            "model_kind": "DETERMINISTIC_OBSERVED_EDGE_LEDGER",
            "primitive_counts": dict(sorted(primitive_counts.items())),
            "transition_count": len(trajectory),
            "transition_digest": transition_digest,
            "precondition": (
                "action is available and any pointer operand is accepted"
            ),
            "postcondition_fields": [
                "terminal_state",
                "levels_completed",
                "observation_digest",
            ],
        },
        "solution_trajectory": trajectory,
        "failure_trajectories": reset_contrasts,
        "necessary_conditions": [
            "Every emitted action is available before execution.",
            "Every coordinate-bearing action has both x and y.",
            "Every action is followed by re-observation.",
            "No transition enters GAME_OVER.",
            "The level commit boundary is reached.",
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
            }
        ],
        "privilege_dependencies": {
            "fixed_action_sequence": True,
            "literal_coordinate": bool(objects),
            "task_game_level_identity": True,
            "public_or_local_success_replay": True,
            "source_or_hidden_state": False,
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
) -> dict[str, Any]:
    """Compile exactly one graph for every closed sample level."""

    if (
        closure_report.get("source_corpus_digest")
        != corpus.get("content_digest")
    ):
        raise ValueError("GRAPH_COMPILER_CORPUS_CLOSURE_DIGEST_MISMATCH")
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
            graphs.append(
                _compile_level_graph(
                    game_solution=raw_game,
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
    body: dict[str, Any] = {
        "schema_version": LEVEL_GRAPH_LEDGER_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R2-SOLUTION-GRAPH-GENERATION",
        "privilege_stage": "S0",
        "source_corpus_digest": corpus.get("content_digest"),
        "source_closure_digest": closure_report.get("content_digest"),
        "game_count": 25,
        "level_graph_count": len(graphs),
        "covered_level_count": len(graphs),
        "fully_replay_grounded_count": len(graphs),
        "causal_semantic_complete_count": 0,
        "state_and_level_transition_mismatch_count": 0,
        "source_frame_digest_mismatch_count": closure_report.get(
            "frame_digest_mismatch_count"
        ),
        "strict_source_frame_equivalence": (
            closure_report.get("strict_frame_digest") is True
            and closure_report.get("frame_digest_mismatch_count") == 0
        ),
        "causal_semantic_status": (
            "ACTION_EFFECT_GRAPHS_COMPLETE;"
            "SOURCE_ROLE_CAUSAL_LABELING_PENDING;"
            "SOURCE_FRAME_DIGEST_EQUIVALENCE_NOT_REQUIRED_FOR_S0_CLOSURE"
        ),
        "graphs": graphs,
    }
    return {
        **body,
        "content_digest": (
            LEVEL_GRAPH_LEDGER_DIGEST_PREFIX + digest_object(body)
        ),
    }


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
            previous_objects = _sequence(previous.get("objects"), "objects")
            current_objects = _sequence(current.get("objects"), "objects")
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
                    len(current_objects) - len(previous_objects)
                ),
                "goal_condition_change": (
                    f"levels_completed >= {current['level']}"
                ),
                "hazard_condition_change": (
                    "RECOVERY_EDGE_COUNT_DELTA:"
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
                    "composition_status": "S0_TRAJECTORY_GROUNDED",
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
                    "STRUCTURAL_DELTA_EXTRACTED;"
                    "OBJECT_ROLE_CAUSAL_DELTA_PENDING"
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
                "Apply an available discrete action; mechanic-specific "
                "semantic role remains to be compiled from contrasts."
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
) -> dict[str, Any]:
    """Factor S0 graphs into an identity-free primitive grammar."""

    raw_graphs = _sequence(level_ledger.get("graphs"), "graphs")
    primitive_counts: Counter[str] = Counter()
    ngram_counts: Counter[tuple[str, ...]] = Counter()
    ngram_level_support: Counter[tuple[str, ...]] = Counter()
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
        "phase": "P10-R3-CROSS-GAME-STRUCTURAL-GRAMMAR",
        "identity_free_artifact": True,
        "contains_literal_coordinates": False,
        "contains_game_or_level_routing": False,
        "source_level_ledger_digest": level_ledger.get("content_digest"),
        "source_intra_game_digest": intra_game.get("content_digest"),
        "primitive_registry": _primitive_registry(primitive_counts),
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
                "Bind operands from rendered relations before selecting a "
                "primitive."
            ),
            "stop_condition": (
                "Stop only after VERIFY_GOAL witnesses the level goal."
            ),
        },
        "coverage": {
            "source_level_graph_count": len(raw_graphs),
            "source_transition_count": sum(primitive_counts.values()),
            "distinct_action_primitive_count": len(primitive_counts),
        },
        "proof_status": {
            "factorization": "EXTRACTED_FROM_183_S0_GRAPHS",
            "fixed_action_free_execution": "NOT_RUN",
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
) -> dict[str, Any]:
    """Record the exact first failing subtraction stage for every graph."""

    raw_graphs = _sequence(level_ledger.get("graphs"), "graphs")
    capabilities: list[dict[str, Any]] = []
    literal_count = 0
    for raw_graph in raw_graphs:
        if not isinstance(raw_graph, Mapping):
            raise TypeError("LEVEL_GRAPH_INVALID")
        dependencies = raw_graph.get("privilege_dependencies")
        if not isinstance(dependencies, Mapping):
            raise TypeError("LEVEL_GRAPH_PRIVILEGES_INVALID")
        uses_literal = dependencies.get("literal_coordinate") is True
        literal_count += int(uses_literal)
        capabilities.append(
            {
                "capability_id": raw_graph.get("graph_id"),
                "game_id": raw_graph.get("game_id"),
                "level": raw_graph.get("level"),
                "graph_digest": raw_graph.get("content_digest"),
                "dependencies": dict(dependencies),
                "stage_results": {
                    "S0": {
                        "status": "PASS",
                        "completed_levels": 1,
                        "evidence_digest": closure_report.get(
                            "content_digest"
                        ),
                    },
                    "S1": {
                        "status": "NOT_RUN",
                        "blocker": "FIXED_ACTION_SEQUENCE_NOT_COMPILED_AWAY",
                    },
                    "S2": {
                        "status": "NOT_RUN",
                        "blocker": (
                            "S1_REQUIRED"
                            if not uses_literal
                            else "LITERAL_COORDINATE_NOT_COMPILED_AWAY"
                        ),
                    },
                    "S3": {
                        "status": "NOT_RUN",
                        "blocker": "TASK_GAME_LEVEL_ROUTING_PRESENT",
                    },
                    "S4": {
                        "status": "NOT_RUN",
                        "blocker": "S3_REQUIRED",
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
                "first_unproven_stage": "S1",
            }
        )
    body: dict[str, Any] = {
        "schema_version": PRIVILEGE_MATRIX_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-PRIVILEGE-SUBTRACTION",
        "source_level_ledger_digest": level_ledger.get("content_digest"),
        "source_closure_digest": closure_report.get("content_digest"),
        "stage_definitions": list(STAGE_DEFINITIONS),
        "stage_summary": {
            "S0": {
                "status": "PASS",
                "completed_levels": 183,
                "required_levels": 183,
            },
            "S1": {"status": "NOT_RUN", "completed_levels": 0},
            "S2": {"status": "NOT_RUN", "completed_levels": 0},
            "S3": {"status": "NOT_RUN", "completed_levels": 0},
            "S4": {"status": "NOT_RUN", "completed_levels": 0},
            "S5": {"status": "NOT_RUN", "completed_levels": 0},
            "S6": {"status": "NOT_RUN", "measurement_count": 0},
        },
        "capability_count": len(capabilities),
        "fixed_action_dependent_count": len(capabilities),
        "literal_coordinate_dependent_count": literal_count,
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
) -> dict[str, Any]:
    """Fail closed until a fixed-action-free graph executor exists."""

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
        },
        "teacher_status": {
            "S0_closed_levels": 183,
            "S0_error_count": 0,
            "solution_graph_count": 183,
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
            "status": "BLOCKED_BY_UNSUBTRACTED_S0_PRIVILEGES",
            "runtime_p_modified": False,
            "emitted_runtime_rule_count": 0,
            "adopted_graph_count": 0,
            "first_required_stage": "S1",
            "first_required_work": (
                "Compile observation-conditioned plans that reproduce all "
                "183 commits without reading fixed action sequences."
            ),
        },
        "claims": {
            "teacher_183_closure": "PASS",
            "graph_generation_183": "PASS",
            "fixed_action_free_183": "NOT_PROVEN",
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
) -> dict[str, dict[str, Any]]:
    """Compile all five post-closure canonical structure artifacts."""

    corpus = load_full_solution_corpus(corpus_path)
    closure_report = load_teacher_closure_report(closure_report_path)
    level_ledger = compile_level_solution_graph_ledger(
        corpus=corpus,
        closure_report=closure_report,
    )
    intra_game = compile_intra_game_progression_graph(level_ledger)
    cross_game = compile_cross_game_structural_grammar(
        level_ledger,
        intra_game,
    )
    privilege_matrix = compile_privilege_subtraction_matrix(
        level_ledger,
        closure_report,
    )
    runtime_p_report = compile_runtime_p_report(
        level_ledger=level_ledger,
        intra_game=intra_game,
        cross_game=cross_game,
        privilege_matrix=privilege_matrix,
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
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    artifacts = compile_solution_structure_artifacts(
        corpus_path=args.corpus,
        closure_report_path=args.closure_report,
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
