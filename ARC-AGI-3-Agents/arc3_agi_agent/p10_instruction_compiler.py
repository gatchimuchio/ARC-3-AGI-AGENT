"""Explicitly compile P10 P-A, P-B, and hybrid instruction bodies."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .instruction_body import (
    ParametricInstructionBody,
    instruction_body_from_mapping,
    seal_instruction_bundle,
)
from .p_b_learning import PBLearningResult
from .p_update import (
    HDSPUpdateAuthority,
    InstructionBodyCompileDirective,
    PUpdateDecision,
    parameter_digest,
)
from .protocol import AuthorityViolation
from .schema import digest_object
from .semantic_operators import (
    DIRECTIONAL_FORCE_ROUTE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    MARKER_SHAPE_PUSH_TARGET_OPERATOR,
    MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
    OBJECT_TARGET_CONTROL_OPERATOR,
    OCCLUDED_TARGET_ROUTE_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
    SELECTABLE_PUSH_TARGET_OPERATOR,
    SELECTABLE_ROUTE_TARGET_OPERATOR,
    SYMBOLIC_REWRITE_OPERATOR,
)
from .visual_explorer import GLOBAL_EFFECT_DIVERSIFICATION_POLICY

P10_INSTRUCTION_COMPILER_VERSION = "arc3-p10-instruction-compiler-v26"
P10_COMPILER_SEED = 0
P10_SYMBOLIC_VERSION = "p10-p-a-symbolic-v27"
P10_PARAMETRIC_VERSION = "p10-p-b-parametric-v27"
P10_HYBRID_VERSION = "p10-hybrid-v26"
P10_CANDIDATE_SET_VERSION = "p10-candidate-set-v26"
P10_CANDIDATE_MANIFEST_FILENAME = "p10_candidate_manifest.json"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"instruction body must be an object: {path}")
    return value


def _write(path: Path, value: object) -> None:
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


def active_p10_manifest_digest(bundle_dir: Path) -> str:
    """Digest the exact active manifest used as the compile predecessor."""

    manifest = _load(bundle_dir / "p10_manifest.json")
    if manifest.get("runtime_identity_free") is not True:
        raise ValueError("active P10 manifest is not identity-free")
    if manifest.get("lifecycle", "ACTIVE") != "ACTIVE":
        raise ValueError("active P10 manifest lifecycle invalid")
    return digest_object(manifest)


def _active_bundle_mapping(
    bundle_dir: Path,
    manifest: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    raw_bundles = manifest.get("bundles")
    if not isinstance(raw_bundles, dict):
        raise TypeError("active P10 manifest bundles invalid")
    raw_entry = raw_bundles.get(variant)
    if not isinstance(raw_entry, dict):
        raise KeyError(f"active P10 variant missing: {variant}")
    filename = raw_entry.get("filename")
    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
    ):
        raise ValueError(f"active P10 filename invalid: {variant}")
    path = bundle_dir / filename
    if raw_entry.get("sha256") != _file_digest(path):
        raise ValueError(f"active P10 sha256 mismatch: {variant}")
    mapping = _load(path)
    body = instruction_body_from_mapping(mapping)
    if raw_entry.get("body_version") != body.body_version:
        raise ValueError(f"active P10 body version mismatch: {variant}")
    if raw_entry.get("content_digest") != body.digest():
        raise ValueError(f"active P10 body digest mismatch: {variant}")
    return mapping


def relation_toggle_instruction_mapping() -> dict[str, object]:
    """Return identity-free P material for the generic toggle primitive."""

    return {
        "operator_id": RELATION_TOGGLE_OPERATOR,
        "action_id": 6,
        "detector": "rendered relation tile lattice",
        "transform": "constraint options plus dynamic gf2 solve",
        "parameters": {
            "tile_size": 3,
            "neighbor_stride": 4,
            "mask_color": 6,
            "equality_relation_color": 0,
            "excluded_colors": [0, 2, 3, 4, 5, 7],
            "relation_colors": [0, 2, 3],
            "status_scan_width": 6,
            "status_scan_height": 10,
            "max_camera_scale": 4,
            "minimum_cell_count": 2,
        },
        "preconditions": [
            "ACTION6_AVAILABLE",
            "RENDERED_RELATION_GRID",
        ],
        "falsification_conditions": [
            "relation grid detector does not close",
            "planned action does not change rendered state",
            "rendered progress does not follow complete plan",
        ],
        "provenance": [
            "compiled-identity-free-transition-evidence",
            "compiled-rendered-relation-evidence",
        ],
    }


def object_target_control_instruction_mapping() -> dict[str, object]:
    """Return P material for a rendered object-target control primitive."""

    return {
        "operator_id": OBJECT_TARGET_CONTROL_OPERATOR,
        "action_id": 6,
        "detector": "rendered four-corner targets and compact controls",
        "transform": "single-step goal-displacement control with reobservation",
        "parameters": {
            "left_control_color": 8,
            "right_control_color": 14,
            "state_excluded_colors": [3, 4, 5],
            "minimum_control_area": 8,
            "maximum_control_area": 16,
            "goal_to_corner_width_ratio": 2,
            "target_corner_stride_ratio": 3,
            "paired_far_tolerance_in_corner_widths": 12,
            "near_tolerance_in_corner_widths": 3,
            "far_tolerance_in_corner_widths": 15,
            "vertical_far_tolerance_in_corner_widths": 27,
            "minimum_guided_cost_per_goal": 4,
            "maximum_search_states": 4096,
            "maximum_control_cycle_steps": 32,
            "minimum_model_observations_per_action": 2,
            "maximum_model_plan_depth": 12,
            "maximum_mechanism_slots": 96,
            "minimum_dense_model_slots": 32,
        },
        "preconditions": [
            "ACTION6_AVAILABLE",
            "RENDERED_TARGET_MARKER",
            "RENDERED_COMPACT_CONTROL",
        ],
        "falsification_conditions": [
            "target marker detector does not close",
            "selected control does not move a rendered goal",
            "goal displacement does not reduce a current-frame mismatch",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-single-step-transition-evidence",
        ],
    }


def symbolic_rewrite_instruction_mapping() -> dict[str, object]:
    """Return P material for visible example-driven symbol rewriting."""

    return {
        "operator_id": SYMBOLIC_REWRITE_OPERATOR,
        "action_id": 2,
        "detector": (
            "rendered bordered symbol rows with relation connectors "
            "and selector"
        ),
        "transform": (
            "bounded visible rewrite plus observed editable-node "
            "constraint solve"
        ),
        "parameters": {
            "tile_size": 7,
            "symbol_color": 5,
            "connector_color": 3,
            "selector_color": 0,
            "cycle_size": 7,
            "decrement_action": 1,
            "increment_action": 2,
            "previous_action": 3,
            "next_action": 4,
            "minimum_border_count": 23,
            "maximum_rewrite_depth": 2,
            "maximum_intermediate_candidates": 4096,
            "maximum_output_tokens": 64,
        },
        "preconditions": [
            "DIRECTIONAL_ACTIONS_AVAILABLE",
            "RENDERED_SYMBOL_TILE_ROWS",
            "RENDERED_REWRITE_CONNECTOR",
            "RENDERED_SELECTOR",
        ],
        "falsification_conditions": [
            "symbol row detector does not close",
            "visible connector rules cannot rewrite the source",
            "selector action does not expose a bounded cycle",
            "editable rule constraints have no verified solution",
        ],
        "provenance": [
            "compiled-identity-free-symbol-relation-evidence",
            "compiled-visible-rewrite-and-cycle-evidence",
        ],
    }


def fruit_merge_instruction_mapping() -> dict[str, object]:
    """Return P material for visible goal-aware merging and placement."""

    return {
        "operator_id": FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
        "action_id": 6,
        "detector": (
            "rendered interface goal glyphs, square rank entities, "
            "actor patterns, and irregular target zones"
        ),
        "transform": (
            "single-step equal-rank merge and goal-aware placement "
            "with mandatory reobservation"
        ),
        "parameters": {
            "click_action": 6,
            "undo_action": 7,
            "click_x_origin": 0,
            "click_y_origin": 10,
            "click_step": 4,
            "click_radius": 8,
            "fruit_move_step": 4,
            "actor_move_distance": 14,
            "actor_chase_risk_distance": 24,
            "actor_divert_interval": 1,
            "actor_fruit_rank_delta": -1,
            "maximum_transition_observations": 4,
            "interface_max_y": 9,
            "playfield_min_y": 10,
            "playfield_max_y": 62,
            "target_color": 9,
            "target_min_side": 8,
            "target_max_side": 10,
            "target_min_area": 35,
            "target_max_area": 80,
            "rank_specs": [
                {"rank": 0, "color": 10, "side": 1},
                {"rank": 1, "color": 6, "side": 2},
                {"rank": 2, "color": 15, "side": 3},
                {"rank": 3, "color": 11, "side": 4},
                {"rank": 4, "color": 12, "side": 5},
                {"rank": 5, "color": 8, "side": 7},
                {"rank": 6, "color": 9, "side": 8},
                {"rank": 7, "color": 7, "side": 9},
                {"rank": 8, "color": 14, "side": 10},
            ],
            "actor_specs": [
                {
                    "kind": "actor-pattern-a",
                    "color": 7,
                    "width": 5,
                    "height": 4,
                    "mask": [
                        [2, 0],
                        [1, 1],
                        [3, 1],
                        [0, 2],
                        [4, 2],
                        [1, 3],
                        [2, 3],
                        [3, 3],
                    ],
                },
                {
                    "kind": "actor-pattern-b",
                    "color": 14,
                    "width": 5,
                    "height": 4,
                    "mask": [
                        [2, 0],
                        [1, 1],
                        [3, 1],
                        [0, 2],
                        [2, 2],
                        [4, 2],
                        [1, 3],
                        [3, 3],
                    ],
                },
                {
                    "kind": "actor-pattern-c",
                    "color": 13,
                    "width": 5,
                    "height": 4,
                    "mask": [
                        [0, 0],
                        [2, 0],
                        [4, 0],
                        [1, 1],
                        [3, 1],
                        [0, 2],
                        [1, 2],
                        [2, 2],
                        [3, 2],
                        [4, 2],
                        [1, 3],
                        [2, 3],
                        [3, 3],
                    ],
                },
            ],
            "actor_merge_chain": [
                "actor-pattern-a",
                "actor-pattern-b",
                "actor-pattern-c",
            ],
        },
        "preconditions": [
            "ACTION6_AND_ACTION7_AVAILABLE",
            "RENDERED_GOAL_GLYPHS",
            "RENDERED_TARGET_ZONES",
        ],
        "falsification_conditions": [
            "goal-aware surface detector does not close",
            "selected click does not change the rendered surface",
            "current-frame merge or placement relation is not improved",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-merge-and-placement-evidence",
        ],
    }


def global_effect_diversification_instruction_mapping() -> dict[str, object]:
    """Return P material that favors unobserved action-effect prototypes."""

    return {
        "operator_id": GLOBAL_EFFECT_DIVERSIFICATION_POLICY,
        "action_id": 1,
        "detector": (
            "rendered state changes while one action prototype repeats "
            "and other available prototypes remain unobserved"
        ),
        "transform": (
            "rank verified progress first, then unobserved prototypes, "
            "then least-observed visible transitions"
        ),
        "parameters": {
            "priority_mode": "novelty-first",
            "progress_priority": 0,
            "unobserved_priority": 1,
            "transition_priority": 2,
            "no_change_priority": 3,
            "hazard_priority": 4,
        },
        "preconditions": [
            "ACTION1_AVAILABLE",
            "RENDERED_TRANSITION_HISTORY_AVAILABLE",
        ],
        "falsification_conditions": [
            "known transition remains ahead of an unobserved prototype",
            "verified progress prototype loses first priority",
            "stable semantic operator behavior changes",
        ],
        "provenance": [
            "compiled-identity-free-visible-effect-evidence",
            "compiled-candidate-surface-stagnation-evidence",
        ],
    }


def selectable_push_target_instruction_mapping() -> dict[str, object]:
    """Return P material for a rendered selectable-object target relation."""

    return {
        "operator_id": SELECTABLE_PUSH_TARGET_OPERATOR,
        "action_id": 6,
        "detector": (
            "paired rendered border objects, enclosing target rings, "
            "and an intervening rectangular barrier"
        ),
        "transform": (
            "derive selection points and directional displacement counts "
            "from current geometry"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "required_pair_count": 2,
            "target_inset": 1,
            "minimum_block_side": 2,
            "maximum_block_side": 8,
            "minimum_barrier_area_ratio": 4,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "RENDERED_SELECTABLE_BORDER_OBJECT_PAIR",
            "RENDERED_ENCLOSING_TARGET_PAIR",
            "RENDERED_INTERVENING_BARRIER",
        ],
        "falsification_conditions": [
            "structural role assignment is ambiguous",
            "derived displacement is not aligned to object scale",
            "planned selection or movement does not change the rendered state",
            "level progress does not follow the complete relation plan",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-target-contact-evidence",
        ],
    }


def selectable_route_target_instruction_mapping() -> dict[str, object]:
    """Return P material for rendered multi-object selection and routing."""

    return {
        "operator_id": SELECTABLE_ROUTE_TARGET_OPERATOR,
        "action_id": 6,
        "detector": (
            "rendered selectable border objects and uniquely "
            "dimension-matched target rings"
        ),
        "transform": (
            "infer object scale and traversable terrain, then run bounded "
            "observation-state search with reobserved action validation"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "selected_marker_color": 0,
            "unselected_marker_color": 5,
            "released_marker_color": 4,
            "push_through_color": 15,
            "target_inset": 1,
            "minimum_object_count": 4,
            "maximum_object_count": 8,
            "minimum_push_steps": 5,
            "maximum_push_steps": 32,
            "maximum_search_states": 200000,
            "maximum_plan_actions": 128,
            "maximum_transition_observations": 8,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "RENDERED_SELECTABLE_BORDER_OBJECTS",
            "UNIQUE_DIMENSION_MATCHED_TARGET_RINGS",
            "SINGLE_RENDERED_SELECTION_MARKER",
        ],
        "falsification_conditions": [
            "object or target role assignment is ambiguous",
            "target displacement is not aligned to inferred object scale",
            "bounded observation-state search finds no plan",
            "reobserved state differs from the predicted queued-action state",
            "stable capability regression decreases",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-transition-delta-evidence",
            "compiled-bounded-state-search-evidence",
        ],
    }


def occluded_target_route_instruction_mapping() -> dict[str, object]:
    """Return P material for a uniquely occluded rendered target route."""

    return {
        "operator_id": OCCLUDED_TARGET_ROUTE_OPERATOR,
        "action_id": 6,
        "detector": (
            "one rendered selected marker object and one target outline "
            "whose single contiguous missing side is covered by a coherent "
            "non-walkable region extending outside the inferred outline"
        ),
        "transform": (
            "complete the uniquely implied target side from the three "
            "intact sides, infer object scale and traversable terrain, then "
            "run bounded observation-state search that enters the target "
            "perpendicular to the exterior occluder normal"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "selected_marker_color": 0,
            "unselected_marker_color": 5,
            "released_marker_color": 4,
            "marker_divisor": 3,
            "target_inset": 1,
            "minimum_object_side": 3,
            "maximum_object_side": 12,
            "maximum_missing_border_cells": 12,
            "maximum_search_states": 200000,
            "maximum_plan_actions": 128,
            "maximum_transition_observations": 12,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "SINGLE_RENDERED_SELECTED_MARKER_OBJECT",
            "UNIQUE_THREE_SIDE_TARGET_COMPLETION",
            "COHERENT_EXTERIOR_OCCLUDER",
        ],
        "falsification_conditions": [
            "the missing outline side is open rather than occluded",
            "target completion or selected object role is ambiguous",
            "target displacement is not aligned to inferred object scale",
            "bounded rendered-state search finds no perpendicular route",
            "reobserved state differs from the predicted queued state",
            "stable capability regression decreases",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-three-side-completion-evidence",
            "compiled-rendered-occluder-continuity-evidence",
            "compiled-occluder-perpendicular-entry-evidence",
            "compiled-bounded-state-search-evidence",
        ],
    }


def directional_force_route_instruction_mapping() -> dict[str, object]:
    """Return P material for rendered directional-force region routing."""

    return {
        "operator_id": DIRECTIONAL_FORCE_ROUTE_OPERATOR,
        "action_id": 6,
        "detector": (
            "one rendered selected marker actor with no rendered "
            "unselected marker role, one shape-target obligation, "
            "separated target regions, a normally impassable band, and "
            "synchronously charged movable directional blocks"
        ),
        "transform": (
            "infer charge phase and direction from rendered edge bands, "
            "derive normal-movement regions and force portals, then run "
            "bounded re-observation-gated searches for shape placement, "
            "region return, and final actor placement"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "selected_marker_color": 0,
            "unselected_marker_color": 5,
            "released_marker_color": 4,
            "marker_divisor": 3,
            "target_inset": 1,
            "minimum_pushable_count": 1,
            "maximum_pushable_count": 1,
            "minimum_target_side": 3,
            "maximum_target_side": 16,
            "minimum_push_steps": 5,
            "maximum_push_steps": 32,
            "hazard_color": 15,
            "force_charge_color": 12,
            "force_idle_color": 13,
            "minimum_force_side": 3,
            "maximum_force_side": 9,
            "minimum_force_count": 3,
            "maximum_force_count": 8,
            "force_expansion_steps": 3,
            "maximum_search_states": 2000,
            "maximum_stage_actions": 32,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "SINGLE_RENDERED_SELECTED_MARKER_ACTOR",
            "NO_RENDERED_UNSELECTED_MARKER_ROLE",
            "ONE_RENDERED_SHAPE_TARGET_OBLIGATION",
            "SYNCHRONOUS_RENDERED_DIRECTIONAL_CHARGE_BANDS",
            "FORCE_PORTALS_CONNECT_SEPARATED_GOAL_REGIONS",
        ],
        "falsification_conditions": [
            "charge phase or force direction is ambiguous",
            "an unselected marker role is rendered",
            "normal-movement regions or force portals are not unique",
            "shape and actor goals are not in separated regions",
            "bounded stage search finds no re-observation action",
            "a completed shape obligation would be displaced",
            "stable capability regression decreases",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-charge-band-evidence",
            "compiled-rendered-region-separation-evidence",
            "compiled-force-portal-transition-evidence",
            "compiled-bounded-stage-search-evidence",
        ],
    }


def marker_shape_push_target_instruction_mapping() -> dict[str, object]:
    """Return P material for actor-mediated rendered shape placement."""

    return {
        "operator_id": MARKER_SHAPE_PUSH_TARGET_OPERATOR,
        "action_id": 6,
        "detector": (
            "one rendered marker-controlled actor, filled movable "
            "shapes, and closed enclosing outline targets"
        ),
        "transform": (
            "derive translation-invariant interior masks, pair shape "
            "families, and run bounded impulse-push state search with "
            "reobserved queued-action validation"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "selected_marker_color": 0,
            "unselected_marker_color": 5,
            "released_marker_color": 4,
            "marker_divisor": 3,
            "target_inset": 1,
            "minimum_pushable_count": 1,
            "maximum_pushable_count": 8,
            "minimum_target_side": 3,
            "maximum_target_side": 16,
            "minimum_push_steps": 5,
            "maximum_push_steps": 32,
            "push_through_color": 15,
            "maximum_search_states": 200000,
            "maximum_plan_actions": 192,
            "maximum_transition_observations": 8,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "SINGLE_RENDERED_SELECTED_MARKER_ACTOR",
            "RENDERED_FILLED_MOVABLE_SHAPES",
            "CLOSED_ENCLOSING_OUTLINE_TARGETS",
        ],
        "falsification_conditions": [
            "outline interior is open or role assignment is ambiguous",
            "filled shape and target interior masks do not match",
            "bounded state search finds no all-obligation plan",
            "reobserved state differs from the predicted queued state",
            "stable capability regression decreases",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-outline-interior-evidence",
            "compiled-bounded-impulse-transition-evidence",
            "compiled-bounded-state-search-evidence",
        ],
    }


def multi_actor_shape_push_target_instruction_mapping() -> dict[str, object]:
    """Return P material for selectable actors and shaped pushables."""

    return {
        "operator_id": MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
        "action_id": 6,
        "detector": (
            "multiple rendered marker-controlled actors, filled movable "
            "shapes, and closed enclosing outline targets"
        ),
        "transform": (
            "derive interchangeable shape families and run bounded "
            "selection plus actor-mediated impulse-push state search"
        ),
        "parameters": {
            "click_action": 6,
            "up_action": 1,
            "down_action": 2,
            "left_action": 3,
            "right_action": 4,
            "selected_marker_color": 0,
            "unselected_marker_color": 5,
            "released_marker_color": 4,
            "marker_divisor": 3,
            "target_inset": 1,
            "minimum_actor_count": 2,
            "maximum_actor_count": 8,
            "minimum_entity_count": 3,
            "maximum_entity_count": 12,
            "minimum_target_side": 3,
            "maximum_target_side": 16,
            "minimum_push_steps": 5,
            "maximum_push_steps": 32,
            "push_through_color": 15,
            "maximum_search_states": 600000,
            "maximum_plan_actions": 256,
            "maximum_transition_observations": 12,
        },
        "preconditions": [
            "DIRECTIONAL_AND_ACTION6_AVAILABLE",
            "MULTIPLE_RENDERED_MARKER_ACTORS",
            "RENDERED_FILLED_MOVABLE_SHAPES",
            "CLOSED_ENCLOSING_OUTLINE_TARGETS",
        ],
        "falsification_conditions": [
            "actor selection state is missing or ambiguous",
            "filled shape and target interior families do not balance",
            "bounded selection and push search finds no complete plan",
            "reobserved state differs from the predicted queued state",
            "stable capability regression decreases",
        ],
        "provenance": [
            "compiled-identity-free-object-relation-evidence",
            "compiled-rendered-selection-transition-evidence",
            "compiled-rendered-outline-interior-evidence",
            "compiled-bounded-impulse-transition-evidence",
            "compiled-bounded-state-search-evidence",
        ],
    }


def _upgrade(
    base: dict[str, Any],
    *,
    body_version: str,
    variant: str,
    operator_instructions: list[dict[str, object]],
    compile_directive_digest: str,
    compile_decision_digest: str,
    evidence_set_digest: str,
    learning_result: PBLearningResult | None = None,
) -> dict[str, Any]:
    upgraded = copy.deepcopy(base)
    predecessor_digest = str(upgraded.get("content_digest", ""))
    predecessor_provenance = str(upgraded.get("provenance_digest", ""))
    provenance_digest = "p10-evidence-provenance:" + digest_object(
        {
            "predecessor": predecessor_provenance,
            "variant": variant,
            "operators": operator_instructions,
            "compile_directive": compile_directive_digest,
            "compile_decision": compile_decision_digest,
            "evidence_set": evidence_set_digest,
            "learning": (
                learning_result.digest if learning_result is not None else None
            ),
        }
    )
    upgraded["body_version"] = body_version
    upgraded["provenance_digest"] = provenance_digest
    contract = upgraded.get("contract")
    payload = upgraded.get("payload")
    if not isinstance(contract, dict) or not isinstance(payload, dict):
        raise TypeError("base instruction body structure invalid")
    contract["body_version"] = body_version
    contract["provenance_digest"] = provenance_digest
    contract["compile_contract"] = list(
        dict.fromkeys(
            (
                *contract.get("compile_contract", ()),
                "explicit-semantic-operator-compile",
            )
        )
    )
    contract["output_contract"] = list(
        dict.fromkeys(
            (
                *contract.get("output_contract", ()),
                "semantic-operator-instructions",
            )
        )
    )
    upgraded["compile"] = {
        "compiler_version": P10_INSTRUCTION_COMPILER_VERSION,
        "compile_decision_digest": compile_decision_digest,
        "compile_directive_digest": compile_directive_digest,
        "evidence_set_digest": evidence_set_digest,
        "seed": P10_COMPILER_SEED,
        "variant": variant,
        "predecessor_content_digest": predecessor_digest,
        "predecessor_provenance_digest": predecessor_provenance,
        "operator_count": len(operator_instructions),
        "operator_digest": digest_object(operator_instructions),
        "method": "explicit-versioned-identity-free-operator-compile",
    }
    payload["operator_instructions"] = operator_instructions
    if learning_result is not None:
        model = payload.get("model")
        if not isinstance(model, dict):
            raise TypeError("parametric model structure invalid")
        model["weights"] = [
            list(row) for row in learning_result.candidate_weights
        ]
        model["parameter_digest"] = learning_result.candidate_parameter_digest
        training_count = model.get("training_record_count")
        holdout_count = model.get("holdout_record_count")
        if (
            isinstance(training_count, bool)
            or not isinstance(training_count, int)
            or isinstance(holdout_count, bool)
            or not isinstance(holdout_count, int)
        ):
            raise TypeError("parametric model record counts invalid")
        model["training_record_count"] = (
            training_count + learning_result.training_example_count
        )
        model["holdout_record_count"] = (
            holdout_count + learning_result.holdout_example_count
        )
        model["learning_update"] = {
            "attribution": learning_result.attribution,
            "candidate_holdout_loss": learning_result.candidate_holdout_loss,
            "candidate_train_loss": learning_result.candidate_train_loss,
            "changed_parameter_digest": digest_object(
                learning_result.changed_parameters
            ),
            "dataset_digest": learning_result.dataset_digest,
            "epochs": learning_result.epochs,
            "learning_rate": learning_result.learning_rate,
            "same_input_candidate_output_digest": (
                learning_result.candidate_same_input_output_digest
            ),
            "same_input_example_digest": (
                learning_result.same_input_example_digest
            ),
            "same_input_predecessor_output_digest": (
                learning_result.source_same_input_output_digest
            ),
            "source_holdout_loss": learning_result.source_holdout_loss,
            "source_parameter_digest": (
                learning_result.source_parameter_digest
            ),
            "source_train_loss": learning_result.source_train_loss,
            "trainer_seed": learning_result.seed,
        }
        upgraded["compile"]["learning_result_digest"] = learning_result.digest
        upgraded["compile"]["method"] = (
            "hds-authorized-memory-trained-parametric-and-operator-compile"
        )
    return seal_instruction_bundle(upgraded)


def compile_p10_instruction_bodies(
    *,
    base_bundle_dir: Path,
    output_dir: Path,
    compile_directive: InstructionBodyCompileDirective,
    compile_decision: PUpdateDecision,
    hds_authority: HDSPUpdateAuthority,
    learning_result: PBLearningResult,
    seed: int = P10_COMPILER_SEED,
) -> dict[str, object]:
    """Compile an isolated candidate set from the exact active predecessors."""

    if seed != P10_COMPILER_SEED:
        raise ValueError("P10 instruction compiler seed is fixed at 0")
    if compile_directive.seed != seed:
        raise AuthorityViolation("P10_COMPILE_DIRECTIVE_SEED_MISMATCH")
    if compile_directive.target_body_version != P10_CANDIDATE_SET_VERSION:
        raise AuthorityViolation("P10_COMPILE_TARGET_VERSION_MISMATCH")
    active_manifest = _load(base_bundle_dir / "p10_manifest.json")
    source_manifest_digest = active_p10_manifest_digest(base_bundle_dir)
    if compile_directive.source_p_digest != source_manifest_digest:
        raise AuthorityViolation("P10_COMPILE_SOURCE_MANIFEST_MISMATCH")
    learning_failures = learning_result.validate()
    if learning_failures:
        raise ValueError(";".join(learning_failures))
    base_symbolic = _active_bundle_mapping(
        base_bundle_dir,
        active_manifest,
        "P-A",
    )
    base_parametric = _active_bundle_mapping(
        base_bundle_dir,
        active_manifest,
        "P-B",
    )
    base_hybrid = _active_bundle_mapping(
        base_bundle_dir,
        active_manifest,
        "hybrid",
    )
    parametric_body = instruction_body_from_mapping(base_parametric)
    hybrid_body = instruction_body_from_mapping(base_hybrid)
    if not isinstance(parametric_body, ParametricInstructionBody):
        raise TypeError("active P-B body is not parametric")
    if not isinstance(hybrid_body, ParametricInstructionBody):
        raise TypeError("active hybrid body is not parametric")
    active_parameter_digest = parameter_digest(parametric_body.weights)
    hybrid_parameter_digest = parameter_digest(hybrid_body.weights)
    if (
        learning_result.source_parameter_digest != active_parameter_digest
        or hybrid_parameter_digest != active_parameter_digest
    ):
        raise ValueError("P10 learning predecessor parameter digest mismatch")
    compile_directive.consume(compile_decision, hds_authority)
    compile_directive_digest = compile_directive.digest
    compile_decision_digest = compile_decision.digest
    evidence_set_digest = compile_directive.evidence_set_digest
    operators = [
        relation_toggle_instruction_mapping(),
        object_target_control_instruction_mapping(),
        symbolic_rewrite_instruction_mapping(),
        fruit_merge_instruction_mapping(),
        selectable_push_target_instruction_mapping(),
        selectable_route_target_instruction_mapping(),
        marker_shape_push_target_instruction_mapping(),
        multi_actor_shape_push_target_instruction_mapping(),
        occluded_target_route_instruction_mapping(),
        directional_force_route_instruction_mapping(),
    ]
    bundles = {
        "P-A": (
            "p10_p_a_symbolic_v27.json",
            _upgrade(
                base_symbolic,
                body_version=P10_SYMBOLIC_VERSION,
                variant="P-A",
                operator_instructions=operators,
                compile_directive_digest=compile_directive_digest,
                compile_decision_digest=compile_decision_digest,
                evidence_set_digest=evidence_set_digest,
            ),
        ),
        "P-B": (
            "p10_p_b_parametric_v27.json",
            _upgrade(
                base_parametric,
                body_version=P10_PARAMETRIC_VERSION,
                variant="P-B",
                operator_instructions=[],
                compile_directive_digest=compile_directive_digest,
                compile_decision_digest=compile_decision_digest,
                evidence_set_digest=evidence_set_digest,
                learning_result=learning_result,
            ),
        ),
        "hybrid": (
            "p10_hybrid_v26.json",
            _upgrade(
                base_hybrid,
                body_version=P10_HYBRID_VERSION,
                variant="hybrid",
                operator_instructions=operators,
                compile_directive_digest=compile_directive_digest,
                compile_decision_digest=compile_decision_digest,
                evidence_set_digest=evidence_set_digest,
                learning_result=learning_result,
            ),
        ),
    }
    manifest_bundles: dict[str, object] = {}
    for name, (filename, mapping) in bundles.items():
        path = output_dir / filename
        _write(path, mapping)
        body = instruction_body_from_mapping(mapping)
        manifest_bundles[name] = {
            "filename": filename,
            "format_id": body.format_id,
            "body_version": body.body_version,
            "content_digest": body.digest(),
            "sha256": _file_digest(path),
            "operator_count": len(
                mapping["payload"].get("operator_instructions", [])
            ),
        }
    manifest: dict[str, object] = {
        "schema_version": "arc3-p10-instruction-manifest-v1",
        "compiler_version": P10_INSTRUCTION_COMPILER_VERSION,
        "compile_decision_digest": compile_decision_digest,
        "compile_directive_digest": compile_directive_digest,
        "evidence_set_digest": evidence_set_digest,
        "seed": seed,
        "runtime_identity_free": True,
        "lifecycle": "CANDIDATE",
        "activation_authority": "hds-promotion-required",
        "source_manifest_digest": source_manifest_digest,
        "learning_result_digest": learning_result.digest,
        "bundles": manifest_bundles,
    }
    _write(output_dir / P10_CANDIDATE_MANIFEST_FILENAME, manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate P10 compile arguments. Candidate generation requires "
            "an in-process HDS-owned compile directive."
        )
    )
    parser.add_argument("--base-bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=P10_COMPILER_SEED)
    return parser


def main() -> int:
    _parser().parse_args()
    print(
        "P10_COMPILE_REQUIRES_HDS_OWNED_DIRECTIVE:"
        "use the P update workflow API",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_CANDIDATE_MANIFEST_FILENAME",
    "P10_CANDIDATE_SET_VERSION",
    "P10_COMPILER_SEED",
    "P10_HYBRID_VERSION",
    "P10_INSTRUCTION_COMPILER_VERSION",
    "P10_PARAMETRIC_VERSION",
    "P10_SYMBOLIC_VERSION",
    "active_p10_manifest_digest",
    "compile_p10_instruction_bodies",
    "directional_force_route_instruction_mapping",
    "fruit_merge_instruction_mapping",
    "global_effect_diversification_instruction_mapping",
    "main",
    "marker_shape_push_target_instruction_mapping",
    "multi_actor_shape_push_target_instruction_mapping",
    "occluded_target_route_instruction_mapping",
    "object_target_control_instruction_mapping",
    "relation_toggle_instruction_mapping",
    "selectable_push_target_instruction_mapping",
    "selectable_route_target_instruction_mapping",
    "symbolic_rewrite_instruction_mapping",
]
