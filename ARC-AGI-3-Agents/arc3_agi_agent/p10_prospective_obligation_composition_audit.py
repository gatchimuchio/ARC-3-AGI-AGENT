"""HDS composition audit for the prospective-obligation P10 work block.

This is the late-subtraction boundary between task-aware development memory
and an identity-free candidate Runtime P.  It compares H1/H2/H3, selects only
the existing-capability H3 composition, and authorizes an isolated candidate
compile.  It never authorizes active mutation or score claims.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .development_trinity import (
    DevelopmentFrame,
    DevelopmentHDS,
    DevelopmentHypothesis,
)
from .directional_force_route import DIRECTIONAL_FORCE_ROUTE_OPERATOR
from .multi_actor_shape_push import (
    MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
)
from .p10_instruction_compiler import (
    directional_force_route_instruction_mapping,
)
from .p10_prospective_relation_cluster_audit import (
    P10_PROSPECTIVE_RELATION_CLUSTER_AUDIT_SCHEMA_VERSION,
)
from .schema import digest_object, forbidden_runtime_paths

P10_PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-prospective-obligation-composition-audit-v1"
)
_CONTENT_DIGEST_PREFIX = (
    "arc3_p10_prospective_obligation_composition_audit:"
)
_CLUSTER_DIGEST_PREFIX = (
    "arc3_p10_prospective_relation_cluster_audit:"
)
_DEVELOPMENT_PREFIXES = {
    "ledger": "arc3_p10_legacy_level_analysis_ledger:",
    "reconciliation": "arc3_p10_analysis_reconciliation_matrix:",
    "coverage": "arc3_p10_capability_coverage_matrix:",
    "queue": "arc3_p10_capability_build_queue:",
}


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def _development_row(
    value: Mapping[str, Any],
    *,
    completed_levels: int,
    next_level: int,
) -> Mapping[str, Any]:
    rows = _sequence(value.get("rows"), "development rows")
    matches = [
        _mapping(row, "development row")
        for row in rows
        if isinstance(row, Mapping)
        and row.get("game_id") == "ka59-38d34dbb"
        and row.get("level") == next_level
    ]
    if len(matches) != 1:
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_DEVELOPMENT_ROW_INVALID"
        )
    row = matches[0]
    if completed_levels != next_level - 1:
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_FRONTIER_ALIGNMENT_INVALID"
        )
    return row


def _active_evidence_report(
    value: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    body = dict(value)
    claimed = body.pop("content_digest", None)
    if claimed != digest_object(body):
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_ACTIVE_DIGEST_INVALID"
        )
    if (
        value.get("schema_version")
        == "arc3-p10-batch-checkpoint-v1"
    ):
        run = _mapping(
            value.get("single_game_report"),
            "active checkpoint report",
        )
        if (
            run.get("operation_mode") != "offline"
            or run.get("instruction_lifecycle") != "active"
            or run.get("instruction_variant") != "hybrid"
            or run.get("max_actions") != 450
        ):
            raise ValueError(
                "P10_PROSPECTIVE_COMPOSITION_ACTIVE_SOURCE_INVALID"
            )
        reports = _sequence(run.get("reports"), "active reports")
        if len(reports) != 1:
            raise ValueError(
                "P10_PROSPECTIVE_COMPOSITION_ACTIVE_REPORT_COUNT_INVALID"
            )
        return _mapping(reports[0], "active report"), run
    if (
        value.get("schema_version")
        != "arc3-p10-compact-run-evidence-v1"
        or value.get("operation_mode") != "offline"
    ):
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_ACTIVE_SOURCE_INVALID"
        )
    compact = _mapping(value.get("compact_run"), "active compact run")
    reports = _sequence(compact.get("reports"), "active compact reports")
    if len(reports) != 1:
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_ACTIVE_REPORT_COUNT_INVALID"
        )
    return _mapping(reports[0], "active compact report"), compact


def _frame() -> DevelopmentFrame:
    return DevelopmentFrame(
        frame_id="frame:prospective-obligation-composition",
        phase="P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        x_observe=(
            "task-aware frontier mechanics and current rendered trace",
            "shadow prospective relation contrast across retained games",
            "active multi-actor and directional operator contracts",
        ),
        x_change=(
            "identity-free composition gate on the existing directional operator",
            "bounded all-obligation relation-event search",
            "visible successor verification and re-observation",
        ),
        x_evidence_use=(
            "development ledger and reconciliation row",
            "all-game shadow relation cluster audit",
            "active compact removal control",
        ),
        x_evidence_exclude=(
            "stale score",
            "fixed replay or action sequence",
            "literal coordinate table",
            "task identity at runtime",
        ),
        r_hypotheses=(
            "H1 add a dedicated frontier operator",
            "H2 make the shadow predictor select actions directly",
            "H3 compose existing multi-actor directional and obligation capabilities",
        ),
        r_predictions=(
            "H3 changes only the joint capability surface",
            "H3 retains the operator set and active baseline until promotion",
        ),
        r_comparators=(
            "active composition gate removed",
            "candidate composition gate enabled",
            "remove either composed capability",
        ),
        r_expected_transitions=(
            "six-of-seven active frontier to candidate completion",
            "no regression outside the joint rendered precondition",
        ),
        r_falsification_relations=(
            "candidate requires identity routing",
            "candidate adds a dedicated operator",
            "candidate fails deterministic rebuild",
            "candidate does not improve completed levels",
        ),
        mc_identity="prospective-obligation-capability-composition",
        mc_boundary="offline retained samples and identity-free Runtime P",
        mc_acceptance=(
            "H1 H2 H3 compared",
            "H3 selected by development HDS",
            "cluster and removal evidence pass",
            "runtime identity subtraction passes",
        ),
        mc_stop=(
            "active manifest changes before promotion",
            "game or level routing reaches Runtime P",
            "candidate error or stable regression",
        ),
        mc_rollback=(
            "restore candidate slot byte-for-byte",
            "retain active manifest unchanged on any failed gate",
        ),
        mc_completion=(
            "target improves reproducibly",
            "all retained games do not regress",
            "standard oracle delta is positive",
        ),
        non_goals=(
            "dedicated frontier operator",
            "official environment connection",
            "competition mode",
        ),
        evidence_boundary=(
            "task identity remains in development-only source references",
            "candidate mapping contains rendered relations only",
        ),
        falsifiers=(
            "historical directional-settle control is re-enabled",
            "unbounded search or observation",
            "action sequence is retained",
        ),
        regression_line=(
            "active all-game standard oracle",
            "candidate all-game standard oracle",
            "identical target rerun",
        ),
        maximum_work_scope=(
            "one existing-operator composition gate",
            "one bounded relation-event planner",
        ),
    )


def _hypotheses() -> tuple[DevelopmentHypothesis, ...]:
    return (
        DevelopmentHypothesis(
            hypothesis_id="hypothesis:h1-dedicated-frontier-operator",
            kind="H1",
            summary="add a dedicated frontier operator",
            predicted_effects=("local completion may improve",),
            applicability=("one development frontier",),
            required_evidence=("dedicated identity-free mechanism",),
            falsifiers=("level-specific routing is required",),
            implementation_cost=4,
            rollback_cost=3,
            generality=0.1,
            information_gain=0.2,
            contamination_risk=1.0,
            regression_risk=0.7,
            status="REJECTED",
        ),
        DevelopmentHypothesis(
            hypothesis_id="hypothesis:h2-shadow-predictor-policy",
            kind="H2",
            summary="allow the shadow relation predictor to select actions",
            predicted_effects=("relation prediction affects action choice",),
            applicability=("cross-game relation observations",),
            required_evidence=("causal action improvement and HDS authority",),
            falsifiers=("shadow-only boundary would be crossed",),
            implementation_cost=3,
            rollback_cost=3,
            generality=0.7,
            information_gain=0.5,
            contamination_risk=0.6,
            regression_risk=0.8,
            status="SUSPENDED",
        ),
        DevelopmentHypothesis(
            hypothesis_id="hypothesis:h3-existing-capability-composition",
            kind="H3",
            summary=(
                "compose existing multi-actor directional and obligation capabilities"
            ),
            predicted_effects=(
                "joint rendered precondition closes the remaining obligation",
                "unrelated operator behavior remains unchanged",
            ),
            applicability=(
                "multiple marker-controlled actors",
                "multiple directional-force blocks",
                "balanced rendered shape-target obligations",
            ),
            required_evidence=(
                "identity-free relation cluster",
                "active removal control",
                "candidate target and all-game regression",
            ),
            falsifiers=(
                "either component can be removed without loss",
                "target completion does not improve",
                "stable completion decreases",
            ),
            implementation_cost=2,
            rollback_cost=1,
            generality=0.8,
            information_gain=0.9,
            contamination_risk=0.0,
            regression_risk=0.2,
        ),
    )


def build_p10_prospective_obligation_composition_audit(
    *,
    cluster_audit: Mapping[str, Any],
    active_compact: Mapping[str, Any],
    ledger: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    coverage: Mapping[str, Any],
    queue: Mapping[str, Any],
    active_operator_ids: Sequence[str],
    maximum_transition_observations: int = 8,
) -> dict[str, object]:
    """Select H3 and authorize only an isolated candidate compile."""

    active_report, active_run = _active_evidence_report(active_compact)
    completed_levels = int(active_report.get("levels_completed", -1))
    total_levels = int(active_report.get("win_levels", -1))
    next_level = completed_levels + 1
    ledger_row = _development_row(
        ledger,
        completed_levels=completed_levels,
        next_level=next_level,
    )
    reconciliation_row = _development_row(
        reconciliation,
        completed_levels=completed_levels,
        next_level=next_level,
    )
    frame = _frame()
    hypotheses = _hypotheses()
    development_hds = DevelopmentHDS()
    decision = development_hds.judge(
        frame,
        hypotheses,
        status="PROBE",
        selected_hypothesis_id=(
            "hypothesis:h3-existing-capability-composition"
        ),
        reason_codes=(
            "dedicated-operator-prohibited",
            "shadow-predictor-has-no-action-authority",
            "existing-capability-composition-maximizes-bounded-information-gain",
        ),
        maximum_information_gain_next=(
            "isolated-candidate-target-and-all-game-regression"
        ),
    )

    active_directional = directional_force_route_instruction_mapping()
    candidate_directional = directional_force_route_instruction_mapping(
        multi_actor_composition_enabled=True,
        maximum_composition_transition_observations=(
            maximum_transition_observations
        ),
    )
    active_parameters = _mapping(
        active_directional.get("parameters"),
        "active directional parameters",
    )
    candidate_parameters = _mapping(
        candidate_directional.get("parameters"),
        "candidate directional parameters",
    )
    active_ids = tuple(str(value) for value in active_operator_ids)
    candidate_ids = active_ids
    identity_paths = forbidden_runtime_paths(candidate_directional)
    cluster_judgment = _mapping(
        cluster_audit.get("hds_judgment"),
        "cluster HDS judgment",
    )
    source_integrity = {
        "cluster_schema_valid": (
            cluster_audit.get("schema_version")
            == P10_PROSPECTIVE_RELATION_CLUSTER_AUDIT_SCHEMA_VERSION
        ),
        "cluster_digest_valid": _content_digest_valid(
            cluster_audit,
            _CLUSTER_DIGEST_PREFIX,
        ),
        "ledger_digest_valid": _content_digest_valid(
            ledger,
            _DEVELOPMENT_PREFIXES["ledger"],
        ),
        "reconciliation_digest_valid": _content_digest_valid(
            reconciliation,
            _DEVELOPMENT_PREFIXES["reconciliation"],
        ),
        "coverage_digest_valid": _content_digest_valid(
            coverage,
            _DEVELOPMENT_PREFIXES["coverage"],
        ),
        "queue_digest_valid": _content_digest_valid(
            queue,
            _DEVELOPMENT_PREFIXES["queue"],
        ),
        "all_development_sources_forbid_runtime_use": all(
            value.get("development_only") is True
            and value.get("runtime_use") == "FORBIDDEN"
            for value in (
                cluster_audit,
                ledger,
                reconciliation,
                coverage,
                queue,
            )
        ),
    }
    failed_integrity = [
        key for key, passed in source_integrity.items() if not passed
    ]
    if failed_integrity:
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_SOURCE_INTEGRITY_FAILED:"
            + ",".join(failed_integrity)
        )

    checks = {
        "prospective_relation_cluster_stable": (
            cluster_audit.get("candidate_tier") == "CLUSTER_STABLE"
            and cluster_judgment.get("cluster_stable_status") == "PASS"
            and cluster_judgment.get("composition_input_authorized")
            is True
        ),
        "task_aware_frontier_reaches_next_level": (
            ledger_row.get("frontier") == "BLOCKED"
            and reconciliation_row.get("current_directly_reached") is True
            and reconciliation_row.get("current_completed_levels")
            == completed_levels
        ),
        "active_removal_control_is_six_of_seven": (
            completed_levels == 6
            and total_levels == 7
            and active_report.get("actions") == 450
            and active_report.get("max_action_exhausted") is True
            and active_run.get("error_count") == 0
        ),
        "h1_h2_h3_present": (
            {item.kind for item in hypotheses} >= {"H1", "H2", "H3"}
        ),
        "h3_selected_by_development_hds": (
            decision.is_owned_by(development_hds)
            and decision.selected_hypothesis_id
            == "hypothesis:h3-existing-capability-composition"
        ),
        "h1_dedicated_operator_rejected": (
            hypotheses[0].status == "REJECTED"
        ),
        "h2_shadow_policy_suspended": (
            hypotheses[1].status == "SUSPENDED"
            and cluster_judgment.get("action_selection_authorized")
            is False
        ),
        "both_existing_operator_capabilities_are_active": (
            DIRECTIONAL_FORCE_ROUTE_OPERATOR in active_ids
            and MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR in active_ids
        ),
        "operator_set_and_count_unchanged": (
            candidate_ids == active_ids
            and len(set(candidate_ids)) == len(candidate_ids)
        ),
        "active_composition_gate_absent": (
            "multi_actor_composition_enabled" not in active_parameters
        ),
        "candidate_composition_gate_is_one": (
            candidate_parameters.get("multi_actor_composition_enabled")
            == 1
        ),
        "candidate_bounds_are_finite": (
            candidate_parameters.get(
                "maximum_composition_transition_observations"
            )
            == maximum_transition_observations
            and int(
                candidate_parameters.get(
                    "maximum_composition_search_states",
                    0,
                )
            )
            > 0
            and int(
                candidate_parameters.get(
                    "maximum_composition_plan_actions",
                    0,
                )
            )
            > 0
        ),
        "historical_directional_settle_not_reenabled": (
            "maximum_transition_observations"
            not in candidate_parameters
        ),
        "late_identity_subtraction_pass": not identity_paths,
        "fixed_route_material_absent": all(
            token not in json.dumps(
                candidate_directional,
                ensure_ascii=True,
                sort_keys=True,
            ).casefold()
            for token in (
                "game_id",
                "level_id",
                "replay",
                "answer_map",
                "literal_coordinate",
            )
        ),
    }
    composable = all(checks.values())
    body: dict[str, object] = {
        "schema_version": (
            P10_PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_prospective_obligation_composition_audit"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "work_block_id": (
            "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER"
        ),
        "candidate_tier": (
            "COMPOSABLE" if composable else "CLUSTER_STABLE"
        ),
        "source_evidence": {
            "cluster_audit_digest": cluster_audit["content_digest"],
            "active_compact_digest": active_compact["content_digest"],
            "ledger_digest": ledger["content_digest"],
            "reconciliation_digest": reconciliation["content_digest"],
            "coverage_digest": coverage["content_digest"],
            "queue_digest": queue["content_digest"],
            "development_frontier_row_digest": digest_object(ledger_row),
            "current_frontier_row_digest": digest_object(
                reconciliation_row
            ),
        },
        "x_r_mc": {
            "frame": dataclasses.asdict(frame),
            "frame_digest": frame.digest,
            "hypotheses": [
                dataclasses.asdict(hypothesis)
                for hypothesis in hypotheses
            ],
            "hypothesis_digests": [
                hypothesis.digest for hypothesis in hypotheses
            ],
            "decision": {
                "decision_id": decision.decision_id,
                "decision_digest": decision.digest,
                "status": decision.status,
                "selected_hypothesis_id": (
                    decision.selected_hypothesis_id
                ),
                "reason_codes": list(decision.reason_codes),
                "maximum_information_gain_next": (
                    decision.maximum_information_gain_next
                ),
                "authority": decision.authority,
            },
        },
        "candidate_contract": {
            "capability_ids": [
                "prospective_rendered_relation_compiler",
                "visible_successor_obligation_predictor",
                "multi_actor_selection_and_shape_target",
                "directional_force_multi_obligation_route",
            ],
            "operator_ids": list(candidate_ids),
            "new_operator_count": 0,
            "composition_trigger": [
                "multiple rendered marker-controlled actors",
                "balanced rendered shape-target obligations",
                "multiple synchronously charged directional blocks",
            ],
            "search": (
                "bounded relation-event all-obligation search"
            ),
            "successor_verification": (
                "content-bound normalized visible transition"
            ),
            "maximum_transition_observations": (
                maximum_transition_observations
            ),
            "task_identity": False,
            "fixed_action_sequence": False,
            "literal_coordinate_table": False,
        },
        "removal_controls": {
            "without_composition_gate_completed_levels": (
                completed_levels
            ),
            "without_composition_gate_total_levels": total_levels,
            "remove_multi_actor_capability": (
                "joint rendered precondition cannot hold"
            ),
            "remove_directional_force_capability": (
                "force phase and directional transition are unavailable"
            ),
            "remove_prospective_obligation_relation": (
                "joint successor obligations cannot be ranked"
            ),
            "historical_directional_settle_reenabled": False,
        },
        "source_integrity_checks": source_integrity,
        "composable_checks": checks,
        "identity_subtraction": {
            "development_identity_retained": True,
            "runtime_identity_paths": list(identity_paths),
            "runtime_identity_free": not identity_paths,
        },
        "hds_judgment": {
            "authority": "development-hds-only",
            "composable_status": "PASS" if composable else "HOLD",
            "selected_hypothesis": "H3",
            "isolated_candidate_compile_authorized": composable,
            "target_probe_authorized": composable,
            "all_sample_regression_authorized": False,
            "active_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "reason_codes": (
                [
                    "H3-existing-capability-composition-selected",
                    "all-game-relation-cluster-stable",
                    "active-composition-removal-control-bound",
                    "operator-set-unchanged",
                    "late-identity-subtraction-pass",
                ]
                if composable
                else [
                    key for key, passed in checks.items() if not passed
                ]
            ),
        },
    }
    return {
        **body,
        "content_digest": _CONTENT_DIGEST_PREFIX
        + digest_object(body),
    }


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the prospective-obligation H1/H2/H3 composition audit."
        )
    )
    parser.add_argument("--cluster-audit", type=Path, required=True)
    parser.add_argument("--active-compact", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--maximum-transition-observations",
        type=int,
        default=8,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from .instruction_body import load_p10_hybrid_instruction_body

    active_ids = tuple(
        instruction.operator_id
        for instruction in (
            load_p10_hybrid_instruction_body().operator_instructions
        )
    )
    audit = build_p10_prospective_obligation_composition_audit(
        cluster_audit=_json(args.cluster_audit),
        active_compact=_json(args.active_compact),
        ledger=_json(args.ledger),
        reconciliation=_json(args.reconciliation),
        coverage=_json(args.coverage),
        queue=_json(args.queue),
        active_operator_ids=active_ids,
        maximum_transition_observations=(
            args.maximum_transition_observations
        ),
    )
    _write_json(args.output.resolve(), audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT_SCHEMA_VERSION",
    "build_p10_prospective_obligation_composition_audit",
    "main",
]
