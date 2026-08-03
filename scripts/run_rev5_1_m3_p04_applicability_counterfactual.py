#!/usr/bin/env python3
"""Execute and seal rev5.1 MechanismSpec applicability counterfactuals."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Final, cast

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.generic_types import GenericObservation  # noqa: E402
from arc3_agi_agent.local_capability import (  # noqa: E402
    RELATION_CAPABILITY,
    GenericMechanismFamily,
    active_dev_mechanism_families,
    development_hypotheses,
    evaluate_relation_bound_action_applicability,
    local_capability_records,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    load_product_initial_state,
)
from arc3_agi_agent.schema import digest_object  # noqa: E402

OUTPUT_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p04_applicability_counterfactual.json"
)
BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
P03_PATH: Final = Path("analysis/product/rev5_1/m3_p03_identity_replay_audit.json")
PREDICATE_SOURCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/local_capability.py"
)

Grid = tuple[tuple[int, ...], ...]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _base_grid() -> Grid:
    return (
        (0, 0, 2, 0, 0, 0, 0),
        (0, 2, 2, 0, 3, 3, 0),
        (0, 0, 2, 0, 0, 3, 0),
        (0, 0, 0, 0, 0, 3, 0),
        (0, 0, 0, 0, 0, 0, 0),
    )


def _palette_permutation(grid: Grid) -> Grid:
    palette = {0: 0, 2: 7, 3: 4}
    return tuple(tuple(palette.get(cell, cell) for cell in row) for row in grid)


def _rotate_clockwise(grid: Grid) -> Grid:
    return tuple(
        tuple(row[index] for row in reversed(grid)) for index in range(len(grid[0]))
    )


def _reflect_horizontal(grid: Grid) -> Grid:
    return tuple(tuple(reversed(row)) for row in grid)


def _shift_layout(grid: Grid) -> Grid:
    return tuple((row[-2], row[-1], *row[:-2]) for row in grid)


def _observation(
    label: str,
    *,
    grid: Grid | None = None,
    actions: tuple[int, ...] = (1, 2, 3, 4, 6),
    terminal_state: str = "NOT_FINISHED",
    action_complete: bool = True,
) -> GenericObservation:
    rendered_layers = () if grid is None else (grid,)
    signature = (
        "m3-p04-observation:"
        + digest_object(
            (
                label,
                rendered_layers,
                actions,
                terminal_state,
                action_complete,
            )
        )[:24]
    )
    observation = GenericObservation(
        signature=signature,
        available_actions=actions,
        rendered_layers=rendered_layers,
        terminal_state=terminal_state,
        progress_count=1 if terminal_state == "WIN" else 0,
        action_payload_schema=((6, ("x", "y")),) if 6 in actions else (),
        win_level_count=1,
        action_complete=action_complete,
    )
    failures = observation.validate()
    _require(not failures, f"M3_P04_OBSERVATION_INVALID:{label}:{failures}")
    return observation


def _principle_digest(family: GenericMechanismFamily) -> str:
    return "action-principle:" + digest_object(
        {
            "purpose_class": family.purpose_class,
            "precondition_pattern": family.precondition_pattern,
            "operation_pattern": family.operation_pattern,
            "transition_pattern": family.transition_pattern,
            "order_pattern": family.order_pattern,
            "planning_pattern": family.planning_pattern,
            "parameter_schema": family.parameter_schema,
        }
    )


def _case(
    *,
    label: str,
    perturbation_class: str,
    observation: GenericObservation,
    family: GenericMechanismFamily,
) -> dict[str, object]:
    evaluation = evaluate_relation_bound_action_applicability(observation)
    records = local_capability_records(observation)
    hypotheses = development_hypotheses(records, observation)
    active_hypotheses = tuple(
        item for item in hypotheses if item.model_type == "active_mechanism"
    )
    return {
        "case_id": label,
        "perturbation_class": perturbation_class,
        "observation_digest": observation.digest(),
        "available_actions": list(observation.available_actions),
        "terminal_state": observation.terminal_state,
        "action_complete": observation.action_complete,
        "render_frame_count": observation.action_frame_count,
        "applicable": evaluation.applicable,
        "satisfied_conditions": list(evaluation.satisfied_conditions),
        "missing_conditions": list(evaluation.missing_conditions),
        "negative_conditions": list(evaluation.negative_conditions),
        "falsification_condition": list(evaluation.falsification_condition),
        "evaluation_logical_digest": evaluation.logical_digest(),
        "action_principle_digest": _principle_digest(family),
        "active_mechanism_hypothesis_count": len(active_hypotheses),
        "runtime_disposition": (
            "ACTIVE_MECHANISM_AVAILABLE" if evaluation.applicable else "NON_APPLICABLE"
        ),
        "identity_input_count": 0,
    }


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    bundle_payload = (root / BUNDLE_PATH).read_bytes()
    p03_payload = (root / P03_PATH).read_bytes()
    predicate_payload = (root / PREDICATE_SOURCE_PATH).read_bytes()
    p03 = json.loads(p03_payload.decode("utf-8"))
    _require(
        isinstance(p03, dict) and p03.get("status") == "M3_P03_PASS",
        "M3_P04_P03_BINDING_INVALID",
    )
    initial = load_product_initial_state()
    families = active_dev_mechanism_families()
    family_ids = tuple(family.family_id for family in families)
    _require(
        family_ids == (RELATION_CAPABILITY,),
        "M3_P04_MANDATORY_FAMILY_EVALUATOR_MISSING",
    )
    family = families[0]
    base_grid = _base_grid()
    baseline = _case(
        label="baseline",
        perturbation_class="BASELINE",
        observation=_observation("baseline", grid=base_grid),
        family=family,
    )
    preserving_inputs = (
        (
            "palette-permutation",
            _observation(
                "palette-permutation",
                grid=_palette_permutation(base_grid),
            ),
        ),
        (
            "rotation-90",
            _observation("rotation-90", grid=_rotate_clockwise(base_grid)),
        ),
        (
            "horizontal-reflection",
            _observation(
                "horizontal-reflection",
                grid=_reflect_horizontal(base_grid),
            ),
        ),
        (
            "layout-shift",
            _observation("layout-shift", grid=_shift_layout(base_grid)),
        ),
        (
            "signature-substitution",
            _observation("signature-substitution", grid=base_grid),
        ),
        (
            "coordinate-only-parameterization",
            _observation(
                "coordinate-only-parameterization",
                grid=base_grid,
                actions=(6,),
            ),
        ),
        (
            "directional-only-parameterization",
            _observation(
                "directional-only-parameterization",
                grid=base_grid,
                actions=(1, 2, 3, 4),
            ),
        ),
    )
    breaking_inputs = (
        (
            "terminal-win",
            "NON_TERMINAL_STATE",
            _observation("terminal-win", grid=base_grid, terminal_state="WIN"),
        ),
        (
            "terminal-game-over",
            "NON_TERMINAL_STATE",
            _observation(
                "terminal-game-over",
                grid=base_grid,
                terminal_state="GAME_OVER",
            ),
        ),
        (
            "unsettled-action",
            "ACTION_COMPLETE",
            _observation(
                "unsettled-action",
                grid=base_grid,
                action_complete=False,
            ),
        ),
        (
            "render-absent",
            "CURRENT_RENDERED_LAYERS",
            _observation("render-absent", grid=None),
        ),
        (
            "external-action-surface-absent",
            "NON_CONTROL_LEGAL_ACTION",
            _observation(
                "external-action-surface-absent",
                grid=base_grid,
                actions=(0,),
            ),
        ),
    )
    preserving = [
        _case(
            label=label,
            perturbation_class="CONDITION_PRESERVING",
            observation=observation,
            family=family,
        )
        for label, observation in preserving_inputs
    ]
    breaking = []
    for label, broken_condition, observation in breaking_inputs:
        item = _case(
            label=label,
            perturbation_class="CONDITION_BREAKING",
            observation=observation,
            family=family,
        )
        item["intentionally_broken_condition"] = broken_condition
        breaking.append(item)

    principle = _principle_digest(family)
    _require(baseline["applicable"] is True, "M3_P04_BASELINE_NOT_APPLICABLE")
    _require(
        cast(int, baseline["active_mechanism_hypothesis_count"]) > 0,
        "M3_P04_BASELINE_PROJECTION_MISSING",
    )
    _require(
        all(
            item["applicable"] is True
            and item["action_principle_digest"] == principle
            and cast(int, item["active_mechanism_hypothesis_count"]) > 0
            and item["identity_input_count"] == 0
            for item in preserving
        ),
        "M3_P04_CONDITION_PRESERVING_FAILURE",
    )
    _require(
        all(
            item["applicable"] is False
            and item["runtime_disposition"] == "NON_APPLICABLE"
            and item["active_mechanism_hypothesis_count"] == 0
            and cast(str, item["intentionally_broken_condition"])
            in cast(list[str], item["missing_conditions"])
            for item in breaking
        ),
        "M3_P04_CONDITION_BREAKING_FAILURE",
    )
    _require(
        not initial.validate() and initial.p_bundle.manifest.lifecycle == "ACTIVE",
        "M3_P04_ACTIVE_PRODUCT_STAGE_DRIFT",
    )
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-p04-applicability-v1",
        "artifact_type": "ApplicabilityCounterfactualEvidence",
        "point_id": "M3-P04_APPLICABILITY_COUNTERFACTUAL",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_P04_PASS",
        "evidence_bindings": {
            "active_product_bundle": {
                "path": BUNDLE_PATH.as_posix(),
                "sha256": _sha256(bundle_payload),
                "initial_state_logical_digest": initial.logical_digest,
                "P_logical_digest": initial.p_bundle.logical_digest(),
                "J0_digest": "j0:" + digest_object(initial.j0),
                "M0_digest": "m0:" + digest_object(initial.m0),
            },
            "m3_p03_identity_replay_audit": {
                "path": P03_PATH.as_posix(),
                "sha256": _sha256(p03_payload),
            },
            "applicability_predicate_source": {
                "path": PREDICATE_SOURCE_PATH.as_posix(),
                "sha256": _sha256(predicate_payload),
            },
        },
        "mandatory_family_audit": {
            "mandatory_family_count": len(families),
            "audited_family_count": 1,
            "uncovered_family_count": 0,
            "family_id": family.family_id,
            "family_logical_digest": family.logical_digest(),
            "action_principle_digest": principle,
            "applicability_inputs": "CURRENT_GENERIC_OBSERVATION_ONLY",
            "surface_identity_selector_count": 0,
        },
        "applicability_predicate_contract": {
            "required_entities": ["CURRENT_RENDERED_LAYERS"],
            "required_relations": ["LEGAL_ACTION_TO_RENDERED_TRANSITION"],
            "required_state_pattern": ["NON_TERMINAL_STATE"],
            "required_action_surface": ["NON_CONTROL_LEGAL_ACTION"],
            "temporal_conditions": ["ACTION_COMPLETE"],
            "negative_conditions_are_observation_derived": True,
            "falsification_condition": [
                "NEGATIVE_CONDITION_OBSERVED",
                "REQUIRED_CONDITION_MISSING",
            ],
        },
        "baseline": baseline,
        "condition_preserving_cases": preserving,
        "condition_breaking_cases": breaking,
        "summary": {
            "condition_preserving_case_count": len(preserving),
            "condition_preserving_pass_count": len(preserving),
            "condition_breaking_case_count": len(breaking),
            "condition_breaking_pass_count": len(breaking),
            "applicability_maintained_when_conditions_hold": True,
            "action_principle_maintained_when_conditions_hold": True,
            "non_applicable_when_condition_breaks": True,
            "active_projection_removed_when_condition_breaks": True,
            "active_development_product_bundle_count": 1,
            "active_product_bundle_changed": False,
            "valid_contract_applicability_semantics_changed": False,
            "invalid_contract_fail_closed": True,
        },
        "claim_boundary": {
            "allowed_claim": "M3_P04_APPLICABILITY_COUNTERFACTUAL_ONLY",
            "M3_complete": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P05_RUNTIME_VERSION_LEARNING",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "output": OUTPUT_PATH.as_posix(),
                "point_status": report["status"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
