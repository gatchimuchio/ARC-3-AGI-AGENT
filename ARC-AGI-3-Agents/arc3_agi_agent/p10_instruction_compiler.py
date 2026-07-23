"""Explicitly compile P10 P-A, P-B, and hybrid instruction bodies."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .instruction_body import (
    instruction_body_from_mapping,
    seal_instruction_bundle,
)
from .schema import canonical_json, digest_object
from .semantic_operators import (
    FRUIT_MERGE_OPERATOR,
    OBJECT_TARGET_CONTROL_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
    SYMBOLIC_REWRITE_OPERATOR,
)

P10_INSTRUCTION_COMPILER_VERSION = "arc3-p10-instruction-compiler-v5"
P10_COMPILER_SEED = 0
P10_SYMBOLIC_VERSION = "p10-p-a-symbolic-v6"
P10_PARAMETRIC_VERSION = "p10-p-b-parametric-v6"
P10_HYBRID_VERSION = "p10-hybrid-v5"


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
        "operator_id": FRUIT_MERGE_OPERATOR,
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


def _upgrade(
    base: dict[str, Any],
    *,
    body_version: str,
    variant: str,
    operator_instructions: list[dict[str, object]],
) -> dict[str, Any]:
    upgraded = copy.deepcopy(base)
    predecessor_digest = str(upgraded.get("content_digest", ""))
    predecessor_provenance = str(upgraded.get("provenance_digest", ""))
    provenance_digest = "p10-evidence-provenance:" + digest_object(
        {
            "predecessor": predecessor_provenance,
            "variant": variant,
            "operators": operator_instructions,
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
        "seed": P10_COMPILER_SEED,
        "variant": variant,
        "predecessor_content_digest": predecessor_digest,
        "predecessor_provenance_digest": predecessor_provenance,
        "operator_count": len(operator_instructions),
        "operator_digest": digest_object(operator_instructions),
        "method": "explicit-versioned-identity-free-operator-compile",
    }
    payload["operator_instructions"] = operator_instructions
    return seal_instruction_bundle(upgraded)


def compile_p10_instruction_bodies(
    *,
    base_bundle_dir: Path,
    output_dir: Path,
    seed: int = P10_COMPILER_SEED,
) -> dict[str, object]:
    """Compile three explicit P variants from the frozen P4 predecessors."""

    if seed != P10_COMPILER_SEED:
        raise ValueError("P10 instruction compiler seed is fixed at 0")
    base_symbolic = _load(base_bundle_dir / "p_a_symbolic_v1.json")
    base_parametric = _load(base_bundle_dir / "p_b_parametric_v1.json")
    operators = [
        relation_toggle_instruction_mapping(),
        object_target_control_instruction_mapping(),
        symbolic_rewrite_instruction_mapping(),
        fruit_merge_instruction_mapping(),
    ]
    bundles = {
        "P-A": (
            "p10_p_a_symbolic_v6.json",
            _upgrade(
                base_symbolic,
                body_version=P10_SYMBOLIC_VERSION,
                variant="P-A",
                operator_instructions=operators,
            ),
        ),
        "P-B": (
            "p10_p_b_parametric_v6.json",
            _upgrade(
                base_parametric,
                body_version=P10_PARAMETRIC_VERSION,
                variant="P-B",
                operator_instructions=[],
            ),
        ),
        "hybrid": (
            "p10_hybrid_v5.json",
            _upgrade(
                base_parametric,
                body_version=P10_HYBRID_VERSION,
                variant="hybrid",
                operator_instructions=operators,
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
        "seed": seed,
        "runtime_identity_free": True,
        "bundles": manifest_bundles,
    }
    _write(output_dir / "p10_manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile explicit P10 P-A, P-B, and hybrid bundles."
    )
    parser.add_argument("--base-bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=P10_COMPILER_SEED)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = compile_p10_instruction_bodies(
        base_bundle_dir=args.base_bundle_dir,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    print(canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_COMPILER_SEED",
    "P10_HYBRID_VERSION",
    "P10_INSTRUCTION_COMPILER_VERSION",
    "P10_PARAMETRIC_VERSION",
    "P10_SYMBOLIC_VERSION",
    "compile_p10_instruction_bodies",
    "fruit_merge_instruction_mapping",
    "main",
    "object_target_control_instruction_mapping",
    "relation_toggle_instruction_mapping",
    "symbolic_rewrite_instruction_mapping",
]
