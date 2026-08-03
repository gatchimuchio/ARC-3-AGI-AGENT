#!/usr/bin/env python3
"""Build the rev5.1 M1-P07 canonical-action mapping closure.

The output is development evidence.  It binds every privileged teacher action
to one compressed mechanism segment, but it is forbidden as a Runtime action
selector.  Runtime behavior remains bound to the current observation-only
ProductBundle recorded by the full-sample product run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.local_capability import (  # noqa: E402
    ACTIVE_DEV_CAPABILITY_STAGE,
    LOCAL_CAPABILITY_STAGE,
    RELATION_CAPABILITY,
    RESOURCE_CAPABILITY,
    TEMPORAL_CAPABILITY,
    active_dev_mechanism_families,
)
from arc3_agi_agent.schema import digest_object  # noqa: E402

OUTPUT_PATH = Path("analysis/product/rev5_1/full_mapping_closure.json")

PRIMARY_ANALYSIS_ARTIFACTS: tuple[tuple[str, Path, tuple[str, ...]], ...] = (
    (
        "FULL_SOLUTION_CORPUS",
        Path("analysis/teacher/FULL_SOLUTION_CORPUS.json"),
        ("P_dev", "J_dev", "M_dev"),
    ),
    (
        "LEVEL_SOLUTION_GRAPH_LEDGER",
        Path("analysis/teacher/LEVEL_SOLUTION_GRAPH_LEDGER.json"),
        ("P_dev", "J_dev"),
    ),
    (
        "INTRA_GAME_PROGRESSION_GRAPH",
        Path("analysis/teacher/INTRA_GAME_PROGRESSION_GRAPH.json"),
        ("P_dev", "M_dev"),
    ),
    (
        "CROSS_GAME_STRUCTURAL_GRAMMAR",
        Path("analysis/teacher/CROSS_GAME_STRUCTURAL_GRAMMAR.json"),
        ("P_dev", "J_dev"),
    ),
    (
        "PRIVILEGE_SUBTRACTION_MATRIX",
        Path("analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json"),
        ("J_dev", "ProductComponent:GenericityGate"),
    ),
    (
        "RUNTIME_P_COMPILATION_REPORT",
        Path("analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json"),
        ("ProductComponent:PBundle",),
    ),
    (
        "S5_RENDERED_POLICY_TRAINING_CORPUS",
        Path("analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json"),
        ("P_dev",),
    ),
    (
        "S5_RUNTIME_P_COMPILATION_REPORT",
        Path("analysis/teacher/S5_RUNTIME_P_COMPILATION_REPORT.json"),
        ("ProductComponent:CompiledRenderedPolicy",),
    ),
)

PRODUCT_EVIDENCE_ARTIFACTS: tuple[tuple[str, Path], ...] = (
    (
        "INITIAL_HORIZONTAL_SUBTRACTION",
        Path("analysis/product/rev5_1/initial_horizontal_subtraction.json"),
    ),
    (
        "FULL_SAMPLE_FAILURE_CAPABILITY_INVENTORY",
        Path("analysis/product/rev5_1/full_sample_failure_capability_inventory.json"),
    ),
    (
        "FULL_SAMPLE_PRODUCT_RUN",
        Path("analysis/product/rev5_1/m1_p01_full_sample_inventory_run.json"),
    ),
)

ACTION_PRIMITIVES = {
    0: "RESET_LEVEL",
    1: "ACTION_1",
    2: "ACTION_2",
    3: "ACTION_3",
    4: "ACTION_4",
    5: "ACTION_5",
    6: "INTERACT_AT_RENDERED_COORDINATE",
    7: "ACTION_7",
}

COMMIT_BOUNDARY = "COMMIT_BOUNDARY"
RECOVERY_AND_REPLAN = "RECOVERY_AND_REPLAN"
TEMPORAL_SETTLE_OR_NO_EFFECT = "TEMPORAL_SETTLE_OR_NO_EFFECT"
ROLE_BOUND_POINTER_INTERACTION = "ROLE_BOUND_POINTER_INTERACTION"
RELATION_BOUND_DISCRETE_TRANSITION = "RELATION_BOUND_DISCRETE_TRANSITION"

CATEGORY_ORDER = (
    RELATION_BOUND_DISCRETE_TRANSITION,
    ROLE_BOUND_POINTER_INTERACTION,
    TEMPORAL_SETTLE_OR_NO_EFFECT,
    RECOVERY_AND_REPLAN,
    COMMIT_BOUNDARY,
)

CATEGORY_CONTRACTS: dict[str, dict[str, object]] = {
    RELATION_BOUND_DISCRETE_TRANSITION: {
        "phase": "INTERACT",
        "purpose": "Change a currently rendered relation with a legal discrete action.",
        "preconditions": (
            "current observation is action-complete",
            "action is present in the current legal action surface",
            "binding is derived from current rendered roles and relations",
        ),
        "operation": "Emit one relation-bound discrete action, then reobserve.",
        "immediate_effect": "A current rendered state transition may occur.",
        "delayed_effect": "Any follow-on effect is attributed after reobservation.",
        "termination": "Observed effect supports or invalidates the current binding.",
        "action_macro": "APPLY legal operation TO rendered role; REOBSERVE; VERIFY",
    },
    ROLE_BOUND_POINTER_INTERACTION: {
        "phase": "INTERACT",
        "purpose": "Change a rendered relation through a role-bound pointer action.",
        "preconditions": (
            "current observation is action-complete",
            "ACTION6 is currently legal",
            "x/y is bound from the current rendered target rather than a literal table",
        ),
        "operation": "Emit ACTION6 at the currently bound rendered role.",
        "immediate_effect": "The selected rendered relation may change.",
        "delayed_effect": "Animation or autonomous effects are attributed after reobservation.",
        "termination": "Observed effect supports or invalidates the role binding.",
        "action_macro": "CLICK rendered role; REOBSERVE; VERIFY",
    },
    TEMPORAL_SETTLE_OR_NO_EFFECT: {
        "phase": "SETTLE",
        "purpose": "Attribute a legal action whose immediate rendered post-frame is unchanged.",
        "preconditions": (
            "the legal action was emitted from the prior current observation",
            "post-action state, progress count, and frame digest are unchanged",
        ),
        "operation": "Retain competing delayed-effect and no-effect hypotheses.",
        "immediate_effect": "No rendered delta is observed at this boundary.",
        "delayed_effect": "A later render may support a delayed transition.",
        "termination": "A later effect is attributed or the hypothesis is invalidated.",
        "action_macro": "REOBSERVE; ATTRIBUTE delayed effect OR invalidate no-op",
    },
    RECOVERY_AND_REPLAN: {
        "phase": "RECOVER",
        "purpose": "Recover from a disproven or hazardous level-local plan.",
        "preconditions": (
            "current plan is causally invalidated or the level is unsafe",
            "RESET is currently legal",
        ),
        "operation": "Reset the current level and build a revised plan.",
        "immediate_effect": "Level-local state returns to its reset boundary.",
        "delayed_effect": "The next plan must differ through revised M evidence.",
        "termination": "A revised J-authorized plan is available.",
        "action_macro": "RESET; REOBSERVE; INVALIDATE; REPLAN",
    },
    COMMIT_BOUNDARY: {
        "phase": "COMMIT",
        "purpose": "Cross the current level goal boundary.",
        "preconditions": (
            "a rendered goal hypothesis is currently supported",
            "the candidate action is legal and J-authorized",
        ),
        "operation": "Emit the final observed transition for the level.",
        "immediate_effect": "The environment evaluates its level-local goal.",
        "delayed_effect": "Progress count increases or the terminal state becomes WIN.",
        "termination": "Observed progress or WIN witnesses the commit.",
        "action_macro": "EXECUTE; REOBSERVE; VERIFY_PROGRESS; COMMIT",
    },
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(code)
    return {str(key): item for key, item in value.items()}


def _list(value: object, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(code)
    return value


def _string_list(value: object, code: str) -> list[str]:
    items = _list(value, code)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(code)
    return [item for item in items if isinstance(item, str)]


def _integer(value: Mapping[str, object], key: str, code: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError(f"{code}:{key}")
    return item


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _load_json(root: Path, relative: Path) -> tuple[dict[str, Any], str]:
    payload = (root / relative).read_bytes()
    value = _object(json.loads(payload), "M1_P07_JSON_OBJECT_REQUIRED")
    return value, _sha256(payload)


def _load_content_bound_json(
    root: Path,
    relative: Path,
) -> tuple[dict[str, Any], str]:
    value, sha256 = _load_json(root, relative)
    expected = value.get("content_digest")
    _require(
        isinstance(expected, str) and ":" in expected,
        f"M1_P07_CONTENT_DIGEST_MISSING:{relative.as_posix()}",
    )
    body = dict(value)
    body.pop("content_digest")
    assert isinstance(expected, str)
    namespace = expected.split(":", 1)[0]
    _require(
        expected == f"{namespace}:{digest_object(body)}",
        f"M1_P07_CONTENT_DIGEST_MISMATCH:{relative.as_posix()}",
    )
    return value, sha256


def _spans(steps: Iterable[int]) -> list[list[int]]:
    ordered = sorted(set(steps))
    if not ordered:
        return []
    result: list[list[int]] = []
    start = ordered[0]
    previous = start
    for step in ordered[1:]:
        if step != previous + 1:
            result.append([start, previous, previous - start + 1])
            start = step
        previous = step
    result.append([start, previous, previous - start + 1])
    return result


def _frame_is_unchanged(
    game: Mapping[str, object],
    actions: Mapping[int, Mapping[str, object]],
    step: int,
) -> bool:
    current = actions[step]
    if step == 1:
        initial = _object(
            game.get("initial_observation"),
            "M1_P07_INITIAL_OBSERVATION_REQUIRED",
        )
        prior_frame = initial.get("frame_digest")
        prior_levels = initial.get("levels_completed")
        prior_state = initial.get("state")
    else:
        prior_action = actions[step - 1]
        prior_frame = prior_action.get("expected_frame_digest")
        prior_levels = prior_action.get("expected_levels_completed")
        prior_state = prior_action.get("expected_state")
    return (
        current.get("expected_frame_digest") == prior_frame
        and current.get("expected_levels_completed") == prior_levels
        and current.get("expected_state") == prior_state
    )


def _category(
    *,
    primitive: str,
    source_step: int,
    commit_source_step: int,
    frame_unchanged: bool,
) -> str:
    if source_step == commit_source_step:
        return COMMIT_BOUNDARY
    if primitive == "RESET_LEVEL":
        return RECOVERY_AND_REPLAN
    if frame_unchanged:
        return TEMPORAL_SETTLE_OR_NO_EFFECT
    if primitive == "INTERACT_AT_RENDERED_COORDINATE":
        return ROLE_BOUND_POINTER_INTERACTION
    return RELATION_BOUND_DISCRETE_TRANSITION


def _residue_signature(graph: Mapping[str, object]) -> dict[str, object]:
    mechanic_model = _object(
        graph.get("mechanic_model"),
        "M1_P07_MECHANIC_MODEL_REQUIRED",
    )
    label = _object(
        mechanic_model.get("development_semantic_label"),
        "M1_P07_MECHANIC_LABEL_REQUIRED",
    )
    return {
        "goal_family": "OBSERVED_LEVEL_PROGRESS_OR_WIN",
        "hazard_condition": str(label.get("hazard_condition", "")),
        "local_effect_classes": sorted(map(str, label.get("local_effect_classes", ()))),
        "operation_type": str(label.get("operation_type", "")),
        "semantic_state_variables": sorted(
            map(str, label.get("semantic_state_variables", ()))
        ),
        "transition_relation": str(label.get("transition_relation", "")),
    }


def _residue_id(signature: Mapping[str, object]) -> str:
    return "domain-local-residue:" + digest_object(signature)


def _mapping_for_category(
    category: str,
    *,
    residue_id: str,
) -> dict[str, object]:
    if category in {
        RELATION_BOUND_DISCRETE_TRANSITION,
        ROLE_BOUND_POINTER_INTERACTION,
    }:
        return {
            "asset_class": "CAPABILITY_FAMILY",
            "asset_state": ACTIVE_DEV_CAPABILITY_STAGE,
            "target_id": RELATION_CAPABILITY,
            "runtime_execute_eligibility": False,
            "runtime_selection_basis": "CURRENT_OBSERVATION_APPLICABILITY_ONLY",
        }
    if category == TEMPORAL_SETTLE_OR_NO_EFFECT:
        return {
            "asset_class": "CAPABILITY_FAMILY",
            "asset_state": LOCAL_CAPABILITY_STAGE,
            "target_id": TEMPORAL_CAPABILITY,
            "runtime_execute_eligibility": False,
            "runtime_selection_basis": "CURRENT_TEMPORAL_EVIDENCE_ONLY",
        }
    if category == RECOVERY_AND_REPLAN:
        return {
            "asset_class": "CAPABILITY_FAMILY",
            "asset_state": LOCAL_CAPABILITY_STAGE,
            "target_id": RESOURCE_CAPABILITY,
            "runtime_execute_eligibility": False,
            "runtime_selection_basis": "CURRENT_FAILURE_ATTRIBUTION_ONLY",
        }
    _require(category == COMMIT_BOUNDARY, "M1_P07_UNKNOWN_SEGMENT_CATEGORY")
    return {
        "asset_class": "DOMAIN_LOCAL_RESIDUE",
        "asset_state": "DOMAIN_LOCAL_RESIDUE",
        "target_id": residue_id,
        "runtime_execute_eligibility": False,
        "runtime_selection_basis": "NONE_UNCOMPILED_DECLARATIVE_RESIDUE",
    }


def _segment(
    *,
    graph: Mapping[str, object],
    category: str,
    steps: Sequence[int],
    actions: Mapping[int, Mapping[str, object]],
    transitions: Mapping[int, Mapping[str, object]],
    residue_id: str,
) -> dict[str, object]:
    game_id = str(graph["game_id"])
    level = _integer(graph, "level", "M1_P07_LEVEL_INVALID")
    segment_id = f"M1_MAP:{game_id}:L{level:02d}:{category}"
    primitives = sorted({str(transitions[step]["primitive"]) for step in steps})
    action_ids = sorted(
        {
            _integer(actions[step], "action_id", "M1_P07_ACTION_ID_INVALID")
            for step in steps
        }
    )
    contract = CATEGORY_CONTRACTS[category]
    return {
        "segment_id": segment_id,
        "phase": contract["phase"],
        "category": category,
        "purpose": contract["purpose"],
        "preconditions": contract["preconditions"],
        "operation": contract["operation"],
        "immediate_effect": contract["immediate_effect"],
        "delayed_effect": contract["delayed_effect"],
        "termination": contract["termination"],
        "action_macro": contract["action_macro"],
        "raw_step_spans": _spans(steps),
        "raw_action_count": len(steps),
        "observed_action_ids": action_ids,
        "observed_primitives": primitives,
        "mapping": _mapping_for_category(category, residue_id=residue_id),
    }


def _build_game_mapping(
    *,
    game: Mapping[str, object],
    graphs: Sequence[Mapping[str, object]],
    residues: dict[str, dict[str, object]],
    assignment_rows: list[tuple[str, int, str]],
    action_category_counts: Counter[str],
    segment_category_counts: Counter[str],
    primitive_counts: Counter[str],
) -> dict[str, object]:
    game_id = str(game["game_id"])
    raw_actions = _list(game.get("actions"), "M1_P07_GAME_ACTIONS_REQUIRED")
    actions: dict[int, Mapping[str, object]] = {}
    for raw_action in raw_actions:
        action = _object(raw_action, "M1_P07_ACTION_OBJECT_REQUIRED")
        step = _integer(action, "step", "M1_P07_ACTION_STEP_INVALID")
        _require(step not in actions, f"M1_P07_DUPLICATE_SOURCE_STEP:{game_id}:{step}")
        actions[step] = action
    expected_steps = set(range(1, len(raw_actions) + 1))
    _require(set(actions) == expected_steps, f"M1_P07_GAME_STEP_GAP:{game_id}")

    levels: list[dict[str, object]] = []
    game_assigned: dict[int, str] = {}
    for graph in sorted(
        graphs,
        key=lambda item: _integer(item, "level", "M1_P07_LEVEL_INVALID"),
    ):
        graph_id = str(graph["graph_id"])
        trace_range = _object(
            graph.get("source_trace_range"),
            "M1_P07_SOURCE_TRACE_RANGE_REQUIRED",
        )
        start = _integer(
            trace_range,
            "start_action_exclusive",
            "M1_P07_TRACE_RANGE_INVALID",
        )
        end = _integer(
            trace_range,
            "end_action_inclusive",
            "M1_P07_TRACE_RANGE_INVALID",
        )
        expected_count = _integer(
            trace_range,
            "action_count",
            "M1_P07_TRACE_RANGE_INVALID",
        )
        _require(
            end - start == expected_count, f"M1_P07_TRACE_COUNT_MISMATCH:{graph_id}"
        )

        commit = _object(
            graph.get("commit_predicate"),
            "M1_P07_COMMIT_PREDICATE_REQUIRED",
        )
        commit_step = _integer(
            commit,
            "commit_source_step",
            "M1_P07_COMMIT_STEP_INVALID",
        )
        _require(commit_step == end, f"M1_P07_COMMIT_NOT_LEVEL_END:{graph_id}")

        raw_trajectory = _list(
            graph.get("solution_trajectory"),
            "M1_P07_TRAJECTORY_REQUIRED",
        )
        transitions: dict[int, Mapping[str, object]] = {}
        for raw_transition in raw_trajectory:
            transition = _object(
                raw_transition,
                "M1_P07_TRANSITION_OBJECT_REQUIRED",
            )
            step = _integer(
                transition,
                "source_step",
                "M1_P07_TRANSITION_STEP_INVALID",
            )
            _require(
                step not in transitions,
                f"M1_P07_DUPLICATE_TRANSITION:{graph_id}:{step}",
            )
            _require(
                step in actions, f"M1_P07_TRANSITION_ACTION_MISSING:{graph_id}:{step}"
            )
            action_id = _integer(
                actions[step],
                "action_id",
                "M1_P07_ACTION_ID_INVALID",
            )
            primitive = str(transition.get("primitive", ""))
            _require(
                ACTION_PRIMITIVES.get(action_id) == primitive,
                f"M1_P07_PRIMITIVE_ACTION_MISMATCH:{graph_id}:{step}",
            )
            postcondition = _object(
                transition.get("postcondition"),
                "M1_P07_POSTCONDITION_REQUIRED",
            )
            expected_postcondition = (
                actions[step].get("expected_levels_completed"),
                actions[step].get("expected_state"),
                actions[step].get("expected_frame_digest"),
            )
            observed_postcondition = (
                postcondition.get("levels_completed"),
                postcondition.get("terminal_state"),
                postcondition.get("observation_digest"),
            )
            _require(
                observed_postcondition == expected_postcondition,
                f"M1_P07_POSTCONDITION_MISMATCH:{graph_id}:{step}",
            )
            transitions[step] = transition
            primitive_counts[primitive] += 1
        level_steps = set(range(start + 1, end + 1))
        _require(
            set(transitions) == level_steps,
            f"M1_P07_LEVEL_TRANSITION_GAP:{graph_id}",
        )

        signature = _residue_signature(graph)
        residue_id = _residue_id(signature)
        residue = residues.setdefault(
            residue_id,
            {
                "residue_id": residue_id,
                "asset_class": "DOMAIN_LOCAL_RESIDUE",
                "asset_state": "DOMAIN_LOCAL_RESIDUE",
                "declarative_mechanism": signature,
                "applicability_status": (
                    "UNCOMPILED_CURRENT_OBSERVATION_PREDICATE_REQUIRED"
                ),
                "runtime_execute_eligibility": False,
                "runtime_selector": "NONE",
                "evidence_graph_ids": [],
                "development_mechanics_ids": [],
            },
        )
        evidence_graph_ids = residue["evidence_graph_ids"]
        mechanics_ids = residue["development_mechanics_ids"]
        assert isinstance(evidence_graph_ids, list)
        assert isinstance(mechanics_ids, list)
        evidence_graph_ids.append(graph_id)
        mechanic_model = _object(
            graph.get("mechanic_model"),
            "M1_P07_MECHANIC_MODEL_REQUIRED",
        )
        label = _object(
            mechanic_model.get("development_semantic_label"),
            "M1_P07_MECHANIC_LABEL_REQUIRED",
        )
        mechanics_ids.append(str(label.get("mechanics_id", "")))

        category_steps: dict[str, list[int]] = defaultdict(list)
        first_category_step: dict[str, int] = {}
        for step in sorted(level_steps):
            transition_for_step = transitions[step]
            category = _category(
                primitive=str(transition_for_step["primitive"]),
                source_step=step,
                commit_source_step=commit_step,
                frame_unchanged=_frame_is_unchanged(game, actions, step),
            )
            category_steps[category].append(step)
            first_category_step.setdefault(category, step)
            action_category_counts[category] += 1

        level_segments: list[dict[str, object]] = []
        for category in sorted(
            category_steps,
            key=lambda item: (first_category_step[item], CATEGORY_ORDER.index(item)),
        ):
            steps = category_steps[category]
            segment = _segment(
                graph=graph,
                category=category,
                steps=steps,
                actions=actions,
                transitions=transitions,
                residue_id=residue_id,
            )
            segment_id = str(segment["segment_id"])
            for step in steps:
                _require(
                    step not in game_assigned,
                    f"M1_P07_ACTION_SEGMENT_OVERLAP:{game_id}:{step}",
                )
                game_assigned[step] = segment_id
                assignment_rows.append((game_id, step, segment_id))
            level_segments.append(segment)
            segment_category_counts[category] += 1

        assigned_level_steps = {step for step in level_steps if step in game_assigned}
        _require(
            assigned_level_steps == level_steps,
            f"M1_P07_LEVEL_ACTION_UNMAPPED:{graph_id}",
        )
        levels.append(
            {
                "level": _integer(graph, "level", "M1_P07_LEVEL_INVALID"),
                "graph_id": graph_id,
                "graph_digest": str(graph["content_digest"]),
                "source_trace_range": trace_range,
                "mechanism_residue_id": residue_id,
                "phase_order": [str(item["phase"]) for item in level_segments],
                "segments": level_segments,
                "raw_action_coverage": {
                    "expected_count": expected_count,
                    "mapped_count": sum(
                        _integer(
                            item,
                            "raw_action_count",
                            "M1_P07_SEGMENT_ACTION_COUNT_INVALID",
                        )
                        for item in level_segments
                    ),
                    "unmapped_source_steps": [],
                    "overlap_count": 0,
                },
            }
        )

    _require(
        set(game_assigned) == expected_steps,
        f"M1_P07_GAME_ACTION_UNMAPPED:{game_id}",
    )
    _require(
        len(levels) == _integer(game, "target_levels", "M1_P07_TARGET_LEVELS_INVALID"),
        f"M1_P07_GAME_LEVEL_COUNT_MISMATCH:{game_id}",
    )
    return {
        "game_id": game_id,
        "development_identity_use": "TRACEABILITY_ONLY_RUNTIME_ROUTING_FORBIDDEN",
        "final_state": str(game["final_state"]),
        "target_levels": _integer(
            game,
            "target_levels",
            "M1_P07_TARGET_LEVELS_INVALID",
        ),
        "raw_action_count": len(raw_actions),
        "mapped_raw_action_count": len(game_assigned),
        "level_count": len(levels),
        "levels": levels,
        "assignment_digest": "m1-p07-game-assignment:"
        + digest_object(
            tuple((step, game_assigned[step]) for step in sorted(game_assigned))
        ),
    }


def _primary_artifact_ledger(
    root: Path,
) -> tuple[list[dict[str, object]], dict[str, dict[str, Any]]]:
    records: list[dict[str, object]] = []
    loaded: dict[str, dict[str, Any]] = {}
    for artifact_id, relative, targets in PRIMARY_ANALYSIS_ARTIFACTS:
        value, sha256 = _load_content_bound_json(root, relative)
        loaded[artifact_id] = value
        records.append(
            {
                "artifact_id": artifact_id,
                "path": relative.as_posix(),
                "sha256": sha256,
                "content_digest": str(value["content_digest"]),
                "runtime_use": str(value.get("runtime_use", "FORBIDDEN")),
                "mapping_targets": list(targets),
                "consumption_status": "CONSUMED",
            }
        )
    return records, loaded


def _product_evidence_ledger(
    root: Path,
) -> tuple[list[dict[str, object]], dict[str, dict[str, Any]]]:
    records: list[dict[str, object]] = []
    loaded: dict[str, dict[str, Any]] = {}
    for artifact_id, relative in PRODUCT_EVIDENCE_ARTIFACTS:
        value, sha256 = _load_json(root, relative)
        loaded[artifact_id] = value
        records.append(
            {
                "artifact_id": artifact_id,
                "path": relative.as_posix(),
                "sha256": sha256,
                "consumption_status": "CONSUMED",
            }
        )
    return records, loaded


def _verify_selector_hashes(
    root: Path,
    selector: Mapping[str, object],
) -> None:
    verified = _object(
        selector.get("verified_material"),
        "M1_P07_SELECTOR_VERIFIED_MATERIAL_REQUIRED",
    )
    path_fields = {
        "full_sample_failure_capability_inventory": (
            "full_sample_failure_capability_inventory_sha256"
        ),
        "full_sample_run": "full_sample_run_sha256",
        "full_solution_corpus": "full_solution_corpus_sha256",
        "level_solution_graph_ledger": "level_solution_graph_ledger_sha256",
        "cross_game_structural_grammar": "cross_game_structural_grammar_sha256",
        "rendered_policy_training_corpus": ("rendered_policy_training_corpus_sha256"),
    }
    for path_key, hash_key in path_fields.items():
        relative = Path(str(verified[path_key]))
        actual = _sha256((root / relative).read_bytes())
        _require(
            actual == verified[hash_key],
            f"M1_P07_SELECTOR_HASH_MISMATCH:{path_key}",
        )


def _verify_source_closure(
    loaded: Mapping[str, Mapping[str, object]],
) -> None:
    corpus = loaded["FULL_SOLUTION_CORPUS"]
    ledger = loaded["LEVEL_SOLUTION_GRAPH_LEDGER"]
    intra = loaded["INTRA_GAME_PROGRESSION_GRAPH"]
    grammar = loaded["CROSS_GAME_STRUCTURAL_GRAMMAR"]
    matrix = loaded["PRIVILEGE_SUBTRACTION_MATRIX"]
    runtime_report = loaded["RUNTIME_P_COMPILATION_REPORT"]
    s5_corpus = loaded["S5_RENDERED_POLICY_TRAINING_CORPUS"]
    s5_report = loaded["S5_RUNTIME_P_COMPILATION_REPORT"]
    claims = _object(runtime_report.get("claims"), "M1_P07_RUNTIME_CLAIMS_REQUIRED")
    coverage = _object(grammar.get("coverage"), "M1_P07_GRAMMAR_COVERAGE_REQUIRED")
    _require(corpus.get("game_count") == 25, "M1_P07_CORPUS_GAME_COUNT")
    _require(corpus.get("level_count") == 183, "M1_P07_CORPUS_LEVEL_COUNT")
    _require(corpus.get("action_count") == 11574, "M1_P07_CORPUS_ACTION_COUNT")
    _require(ledger.get("covered_level_count") == 183, "M1_P07_LEDGER_LEVEL_COUNT")
    _require(intra.get("game_count") == 25, "M1_P07_INTRA_GAME_COUNT")
    _require(intra.get("progression_edge_count") == 158, "M1_P07_INTRA_EDGE_COUNT")
    _require(
        coverage.get("source_transition_count") == 11574, "M1_P07_GRAMMAR_ACTION_COUNT"
    )
    _require(
        grammar.get("contains_game_or_level_routing") is False,
        "M1_P07_GRAMMAR_IDENTITY_ROUTE",
    )
    _require(
        grammar.get("contains_literal_coordinates") is False,
        "M1_P07_GRAMMAR_LITERAL_COORDINATE",
    )
    _require(matrix.get("capability_count") == 183, "M1_P07_MATRIX_LEVEL_COUNT")
    _require(
        matrix.get("rendered_only_proven_count") == 183, "M1_P07_MATRIX_RENDERED_ONLY"
    )
    _require(
        matrix.get("identity_routing_dependent_count") == 0,
        "M1_P07_MATRIX_IDENTITY_DEPENDENCY",
    )
    _require(
        claims.get("teacher_183_closure") == "PASS", "M1_P07_RUNTIME_TEACHER_CLOSURE"
    )
    _require(
        claims.get("rendered_only_183") == "PASS_183_OF_183",
        "M1_P07_RUNTIME_RENDERED_ONLY",
    )
    _require(s5_corpus.get("record_count") == 10733, "M1_P07_S5_RECORD_COUNT")
    _require(s5_corpus.get("completed_levels") == 183, "M1_P07_S5_LEVEL_COUNT")
    _require(
        s5_report.get("training_record_count") == 10733, "M1_P07_S5_REPORT_RECORD_COUNT"
    )
    _require(
        s5_report.get("teacher_forced_error_count") == 0, "M1_P07_S5_TEACHER_ERROR"
    )
    _require(
        s5_report.get("runtime_routes_by_task_game_level_identity") is False,
        "M1_P07_S5_IDENTITY_ROUTE",
    )


def _verify_product_run(run: Mapping[str, object]) -> None:
    required_values = {
        "advertised_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "lifecycle_failure_count": 0,
        "product_game_win_count": 25,
        "product_level_completion_count": 183,
        "product_total_action_count": 10733,
        "product_endpoint_failure_count": 0,
        "active_product_path_count": 1,
        "product_active_dev_mechanism_family_count": 1,
        "shared_session_count": 1,
        "state_owner_violation_count": 0,
    }
    for key, expected in required_values.items():
        _require(run.get(key) == expected, f"M1_P07_PRODUCT_RUN_MISMATCH:{key}")
    _require(run.get("product_id") == "ARC3CompletionAgent", "M1_P07_PRODUCT_ID")
    _require(
        run.get("known_sample_regression_established") is True,
        "M1_P07_REGRESSION_NOT_ESTABLISHED",
    )
    _require(
        run.get("product_completion_established") is False,
        "M1_P07_PREMATURE_COMPLETION",
    )
    _require(
        run.get("product_status") == "GENERICITY_NOT_ESTABLISHED",
        "M1_P07_PRODUCT_STATUS",
    )
    _require(
        run.get("product_active_dev_mechanism_family_ids") == [RELATION_CAPABILITY],
        "M1_P07_ACTIVE_FAMILY_SET",
    )


def build(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    root = root.resolve()
    selector, selector_sha256 = _load_json(
        root,
        Path("control/rev5_1/CURRENT_TASK.json"),
    )
    _require(
        selector.get("active_point") == "M1-P07_FULL_MAPPING_CLOSURE",
        "M1_P07_SELECTOR_POINT",
    )
    _require(
        selector.get("point_status") == "AUTHORIZED_TO_START", "M1_P07_SELECTOR_STATUS"
    )
    _verify_selector_hashes(root, selector)

    primary_ledger, primary = _primary_artifact_ledger(root)
    product_ledger, product_evidence = _product_evidence_ledger(root)
    _verify_source_closure(primary)
    full_run = product_evidence["FULL_SAMPLE_PRODUCT_RUN"]
    _verify_product_run(full_run)

    corpus = primary["FULL_SOLUTION_CORPUS"]
    ledger = primary["LEVEL_SOLUTION_GRAPH_LEDGER"]
    grammar = primary["CROSS_GAME_STRUCTURAL_GRAMMAR"]
    raw_games = _list(corpus.get("games"), "M1_P07_CORPUS_GAMES_REQUIRED")
    raw_graphs = _list(ledger.get("graphs"), "M1_P07_LEDGER_GRAPHS_REQUIRED")

    graphs_by_game: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for raw_graph in raw_graphs:
        graph = _object(raw_graph, "M1_P07_GRAPH_OBJECT_REQUIRED")
        graphs_by_game[str(graph["game_id"])].append(graph)

    residues: dict[str, dict[str, object]] = {}
    assignment_rows: list[tuple[str, int, str]] = []
    action_category_counts: Counter[str] = Counter()
    segment_category_counts: Counter[str] = Counter()
    primitive_counts: Counter[str] = Counter()
    game_mappings: list[dict[str, object]] = []
    for raw_game in raw_games:
        game = _object(raw_game, "M1_P07_GAME_OBJECT_REQUIRED")
        game_id = str(game["game_id"])
        _require(game_id in graphs_by_game, f"M1_P07_GAME_GRAPH_MISSING:{game_id}")
        game_mappings.append(
            _build_game_mapping(
                game=game,
                graphs=graphs_by_game[game_id],
                residues=residues,
                assignment_rows=assignment_rows,
                action_category_counts=action_category_counts,
                segment_category_counts=segment_category_counts,
                primitive_counts=primitive_counts,
            )
        )

    canonical_action_count = _integer(
        corpus, "action_count", "M1_P07_ACTION_COUNT_INVALID"
    )
    _require(len(assignment_rows) == canonical_action_count, "M1_P07_ASSIGNMENT_COUNT")
    _require(
        len({(game_id, step) for game_id, step, _ in assignment_rows})
        == canonical_action_count,
        "M1_P07_ASSIGNMENT_OVERLAP",
    )
    _require(len(game_mappings) == 25, "M1_P07_MAPPED_GAME_COUNT")
    mapped_level_count = sum(
        _integer(item, "level_count", "M1_P07_GAME_LEVEL_COUNT_INVALID")
        for item in game_mappings
    )
    _require(mapped_level_count == 183, "M1_P07_MAPPED_LEVEL_COUNT")

    grammar_primitives = {
        str(item["primitive"]): int(item["observed_transition_count"])
        for item in grammar["primitive_registry"]
        if int(item["observed_transition_count"]) > 0
    }
    _require(
        dict(sorted(primitive_counts.items()))
        == dict(sorted(grammar_primitives.items())),
        "M1_P07_GRAMMAR_PRIMITIVE_MISMATCH",
    )

    for residue in residues.values():
        graph_ids = residue["evidence_graph_ids"]
        mechanics_ids = residue["development_mechanics_ids"]
        assert isinstance(graph_ids, list)
        assert isinstance(mechanics_ids, list)
        sorted_graph_ids = sorted(set(map(str, graph_ids)))
        residue["evidence_graph_ids"] = sorted_graph_ids
        residue["development_mechanics_ids"] = sorted(set(map(str, mechanics_ids)))
        residue["support_level_count"] = len(sorted_graph_ids)

    active_families = active_dev_mechanism_families()
    _require(len(active_families) == 1, "M1_P07_ACTIVE_FAMILY_COUNT")
    active_family = active_families[0]
    run_family_digests = full_run.get("product_active_dev_mechanism_family_digests")
    _require(
        run_family_digests == [active_family.logical_digest()],
        "M1_P07_ACTIVE_FAMILY_DIGEST",
    )

    capability_family_registry = [
        {
            **asdict(active_family),
            "family_digest": active_family.logical_digest(),
            "mapping_role": "P_dev+C_J_M_OBSERVATION_GROUNDED_INTEGRATION",
            "runtime_execute_eligibility": active_family.execute_eligibility,
        },
        {
            "family_id": TEMPORAL_CAPABILITY,
            "asset_state": LOCAL_CAPABILITY_STAGE,
            "runtime_execute_eligibility": False,
            "mapping_role": "M_dev+J_dev_DELAYED_EFFECT_ATTRIBUTION",
            "promotion_status": "NOT_PROMOTED_INSUFFICIENT_INDEPENDENT_COUNTERFACTUAL_SUPPORT",
        },
        {
            "family_id": RESOURCE_CAPABILITY,
            "asset_state": LOCAL_CAPABILITY_STAGE,
            "runtime_execute_eligibility": False,
            "mapping_role": "M_dev+J_dev_CAUSAL_ROLLBACK_AND_REPLAN",
            "promotion_status": "NOT_PROMOTED_INSUFFICIENT_INDEPENDENT_COUNTERFACTUAL_SUPPORT",
        },
    ]

    primary_unused = [
        item["artifact_id"]
        for item in primary_ledger
        if not item["mapping_targets"] or item["consumption_status"] != "CONSUMED"
    ]
    _require(not primary_unused, "M1_P07_UNUSED_PRIMARY_ARTIFACT")

    runtime_action_count = _integer(
        full_run,
        "product_total_action_count",
        "M1_P07_PRODUCT_ACTION_COUNT_INVALID",
    )
    result: dict[str, object] = {
        "schema_version": "arc3-rev5-1-full-mapping-closure-v1",
        "artifact_type": "FullMappingClosure",
        "point_id": "M1-P07_FULL_MAPPING_CLOSURE",
        "status": "M1_P07_COMPLETE",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": ACTIVE_DEV_CAPABILITY_STAGE,
        "development_only_mapping": True,
        "runtime_use": "FORBIDDEN_AS_ACTION_SELECTOR_OR_TRAJECTORY",
        "input_contract": {
            "selector": "control/rev5_1/CURRENT_TASK.json",
            "selector_sha256": selector_sha256,
            "primary_analysis_artifact_scope": (
                "The eight teacher-pipeline artifacts required to reconstruct, "
                "factor, subtract privilege from, compile, and audit the current "
                "rendered-only policy."
            ),
            "primary_analysis_artifacts": primary_ledger,
            "product_evidence_artifacts": product_ledger,
            "unused_primary_analysis_artifact_ids": primary_unused,
        },
        "mapping_contract": {
            "hierarchy": [
                "Game",
                "Level",
                "Phase",
                "Mechanism Segment",
                "Action Macro",
                "raw step span",
            ],
            "assignment_unit": "CANONICAL_SOURCE_ACTION",
            "assignment_cardinality": "EXACTLY_ONE_NON_OVERLAPPING_SEGMENT",
            "compression": "LEVEL_LOCAL_SEMANTIC_CATEGORY_WITH_CONTIGUOUS_RAW_SPANS",
            "commit_rule": "FINAL_SOURCE_STEP_OF_EACH_LEVEL",
            "temporal_rule": (
                "POST_ACTION_FRAME_STATE_AND_PROGRESS_EQUAL_PRIOR_OBSERVATION"
            ),
            "runtime_boundary": (
                "Teacher identity, coordinates, steps, and trajectories remain "
                "development evidence and are never loaded as Runtime decision input."
            ),
        },
        "capability_family_registry": capability_family_registry,
        "domain_local_residue_registry": [residues[key] for key in sorted(residues)],
        "game_mappings": game_mappings,
        "coverage_summary": {
            "game_count": len(game_mappings),
            "level_count": mapped_level_count,
            "canonical_raw_action_count": canonical_action_count,
            "mapped_raw_action_count": len(assignment_rows),
            "unmapped_raw_action_count": 0,
            "overlapping_raw_action_count": 0,
            "mechanism_segment_count": sum(segment_category_counts.values()),
            "mapped_mechanism_segment_count": sum(segment_category_counts.values()),
            "unmapped_mechanism_segment_count": 0,
            "domain_local_residue_count": len(residues),
            "action_category_counts": dict(sorted(action_category_counts.items())),
            "segment_category_counts": dict(sorted(segment_category_counts.items())),
            "primitive_counts": dict(sorted(primitive_counts.items())),
            "raw_action_assignment_digest": "m1-p07-action-assignment:"
            + digest_object(tuple(assignment_rows)),
        },
        "primary_analysis_consumption_audit": {
            "primary_analysis_artifact_count": len(primary_ledger),
            "consumed_primary_analysis_artifact_count": len(primary_ledger),
            "unused_primary_analysis_artifact_count": 0,
            "all_have_runtime_or_development_mapping": True,
        },
        "active_development_product_bundle": {
            "count": _integer(
                full_run,
                "active_product_path_count",
                "M1_P07_ACTIVE_PRODUCT_COUNT_INVALID",
            ),
            "product_id": str(full_run["product_id"]),
            "runtime_identity_digest": str(full_run["product_runtime_identity_digest"]),
            "initial_state_logical_digest": str(
                full_run["product_initial_state_logical_digest"]
            ),
            "p_logical_digest": str(full_run["product_p_logical_digest"]),
            "j0_digest": str(full_run["product_j0_digest"]),
            "m0_digest": str(full_run["product_m0_digest"]),
            "active_dev_mechanism_family_ids": _string_list(
                full_run.get("product_active_dev_mechanism_family_ids"),
                "M1_P07_ACTIVE_FAMILY_IDS_INVALID",
            ),
            "active_dev_mechanism_family_digests": _string_list(
                full_run.get("product_active_dev_mechanism_family_digests"),
                "M1_P07_ACTIVE_FAMILY_DIGESTS_INVALID",
            ),
        },
        "observed_product_regression": {
            "report": ("analysis/product/rev5_1/m1_p01_full_sample_inventory_run.json"),
            "individual_game_win_count": _integer(
                full_run,
                "product_game_win_count",
                "M1_P07_PRODUCT_GAME_WIN_COUNT_INVALID",
            ),
            "individual_level_completion_count": _integer(
                full_run,
                "product_level_completion_count",
                "M1_P07_PRODUCT_LEVEL_COUNT_INVALID",
            ),
            "runtime_action_count": runtime_action_count,
            "canonical_teacher_action_count": canonical_action_count,
            "action_count_delta": canonical_action_count - runtime_action_count,
            "failed_game_count": _integer(
                full_run,
                "failed_game_count",
                "M1_P07_FAILED_GAME_COUNT_INVALID",
            ),
            "lifecycle_failure_count": _integer(
                full_run,
                "lifecycle_failure_count",
                "M1_P07_LIFECYCLE_FAILURE_COUNT_INVALID",
            ),
            "endpoint_failure_count": _integer(
                full_run,
                "product_endpoint_failure_count",
                "M1_P07_ENDPOINT_FAILURE_COUNT_INVALID",
            ),
            "known_sample_regression_established": bool(
                full_run["known_sample_regression_established"]
            ),
        },
        "boundary_audit": {
            "identity_action_router_added": False,
            "fixed_trajectory_runtime_path_added": False,
            "literal_coordinate_runtime_table_added": False,
            "teacher_artifact_runtime_import_added": False,
            "domain_local_residue_runtime_selector_count": 0,
            "all_external_actions_remain_J_authorized": True,
            "product_completion_claim": False,
            "genericity_claim": False,
            "allowed_claim": "M1_FULL_MAPPING_AND_KNOWN_SAMPLE_REGRESSION_ONLY",
        },
        "exit_audit": {
            "individual_game_win_count": len(game_mappings),
            "individual_level_completion_count": mapped_level_count,
            "canonical_raw_action_mapped_count": len(assignment_rows),
            "unmapped_raw_action_count": 0,
            "unmapped_mechanism_segment_count": 0,
            "unused_primary_analysis_artifact_count": 0,
            "active_development_product_bundle_count": _integer(
                full_run,
                "active_product_path_count",
                "M1_P07_ACTIVE_PRODUCT_COUNT_INVALID",
            ),
            "M1_complete": True,
            "status": "M1_P07_COMPLETE",
        },
        "consumed_by_next_point": "M2-P01_CLEAN_RUN_A_OFFICIAL_ORDER",
    }
    result["logical_content_sha256"] = digest_object(result)
    return result


def output_bytes(root: Path = REPOSITORY_ROOT) -> bytes:
    return _canonical_bytes(build(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    output = arguments.output
    if not output.is_absolute():
        output = root / output
    expected = output_bytes(root)
    if arguments.check:
        if not output.is_file() or output.read_bytes() != expected:
            raise SystemExit("M1_P07_FULL_MAPPING_ARTIFACT_STALE")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)
    artifact = json.loads(expected)
    summary = {
        "output": output.relative_to(root).as_posix(),
        "sha256": _sha256(expected),
        "status": artifact["status"],
        **artifact["coverage_summary"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
