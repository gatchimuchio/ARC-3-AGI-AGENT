"""Audit the shadow-only prospective relation probe across retained games.

The source report is development evidence (B layer): game identity remains
available for contrast and provenance.  The probe payload itself is required
to stay identity-free, bounded, passive, and unable to affect Runtime P,
action selection, memory writes, or external emission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .prospective_relation import PROSPECTIVE_RELATION_PROBE_FORMAT
from .schema import digest_object, forbidden_runtime_paths

P10_PROSPECTIVE_RELATION_CLUSTER_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-prospective-relation-cluster-audit-v1"
)
_CONTENT_DIGEST_PREFIX = "arc3_p10_prospective_relation_cluster_audit:"
_EXPECTED_GAME_COUNT = 25
_EXPECTED_MAX_ACTIONS = 16


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


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _dominant_label(counts: Counter[str]) -> str | None:
    if not counts:
        return None
    ordered = sorted(
        ((count, label) for label, count in counts.items()),
        key=lambda item: (-item[0], item[1]),
    )
    if len(ordered) > 1 and ordered[0][0] == ordered[1][0]:
        return None
    return ordered[0][1]


def _probe_metrics(
    report: Mapping[str, Any],
) -> dict[str, object]:
    game_id = str(report.get("game_id", ""))
    if not game_id:
        raise ValueError("P10_PROSPECTIVE_RELATION_GAME_ID_MISSING")
    probe = _mapping(
        report.get("development_prospective_relation_probe"),
        "prospective relation probe",
    )
    records = _sequence(probe.get("records"), "prospective records")
    observation_count = _integer(
        probe.get("observation_count"),
        "prospective observation count",
    )
    fault_count = _integer(
        probe.get("fault_count"),
        "prospective fault count",
    )
    known_count = _integer(
        probe.get("known_prediction_count"),
        "prospective known prediction count",
    )
    correct_count = _integer(
        probe.get("correct_prediction_count"),
        "prospective correct prediction count",
    )
    if observation_count != len(records):
        raise ValueError(
            "P10_PROSPECTIVE_RELATION_RECORD_COUNT_MISMATCH:"
            + game_id
        )

    baseline_counts: Counter[str] = Counter()
    baseline_known = 0
    baseline_correct = 0
    observed_obligations: Counter[str] = Counter()
    observed_relations: Counter[str] = Counter()
    recomputed_known = 0
    recomputed_correct = 0
    for ordinal, raw_record in enumerate(records, start=1):
        record = _mapping(raw_record, "prospective record")
        if _integer(record.get("ordinal"), "record ordinal") != ordinal:
            raise ValueError(
                "P10_PROSPECTIVE_RELATION_ORDINAL_MISMATCH:"
                + game_id
            )
        obligation = str(record.get("observed_obligation", ""))
        relation_delta = str(record.get("relation_delta", ""))
        prediction = _mapping(
            record.get("prediction_before_update"),
            "prospective pre-action prediction",
        )
        prediction_label = str(prediction.get("label", ""))
        if prediction_label != "UNKNOWN":
            recomputed_known += 1
            recomputed_correct += int(prediction_label == obligation)
        baseline_label = _dominant_label(baseline_counts)
        if baseline_label is not None:
            baseline_known += 1
            baseline_correct += int(baseline_label == obligation)
        baseline_counts[obligation] += 1
        observed_obligations[obligation] += 1
        observed_relations[relation_delta] += 1
    if (
        recomputed_known != known_count
        or recomputed_correct != correct_count
    ):
        raise ValueError(
            "P10_PROSPECTIVE_RELATION_PREDICTION_COUNT_MISMATCH:"
            + game_id
        )

    identity_paths = forbidden_runtime_paths(probe)
    boundary_safe = (
        probe.get("format") == PROSPECTIVE_RELATION_PROBE_FORMAT
        and probe.get("candidate_tier") == "LOCAL_PROBE"
        and probe.get("runtime_use") == "FORBIDDEN"
        and probe.get("runtime_decision_use") == "FORBIDDEN"
        and probe.get("action_selection_influence") is False
        and probe.get("memory_write_authority") is False
        and probe.get("external_emit_authority") is False
        and probe.get("runtime_p_promotion_authority") is False
        and probe.get("raw_grid_retention") is False
        and not identity_paths
    )
    relation_accuracy_milli = (
        0 if not known_count else round(1000 * correct_count / known_count)
    )
    baseline_accuracy_milli = (
        0
        if not baseline_known
        else round(1000 * baseline_correct / baseline_known)
    )
    accuracy_relation = (
        correct_count * baseline_known
        - baseline_correct * known_count
    )
    return {
        "game_id": game_id,
        "observation_count": observation_count,
        "fault_count": fault_count,
        "known_prediction_count": known_count,
        "correct_prediction_count": correct_count,
        "relation_accuracy_milli": relation_accuracy_milli,
        "baseline_known_prediction_count": baseline_known,
        "baseline_correct_prediction_count": baseline_correct,
        "baseline_accuracy_milli": baseline_accuracy_milli,
        "accuracy_contrast": (
            "POSITIVE"
            if accuracy_relation > 0
            else ("NEGATIVE" if accuracy_relation < 0 else "TIE")
        ),
        "obligation_counts": dict(sorted(observed_obligations.items())),
        "relation_delta_counts": dict(sorted(observed_relations.items())),
        "identity_paths": list(identity_paths),
        "passive_boundary_pass": boundary_safe,
        "probe_digest": digest_object(probe),
    }


def build_p10_prospective_relation_cluster_audit(
    source_report: Mapping[str, Any],
    *,
    source_sha256: str,
    source_bytes: int,
) -> dict[str, object]:
    """Return the HDS cluster judgment for one all-25 shadow probe."""

    reports = _sequence(source_report.get("reports"), "source reports")
    errors = _sequence(source_report.get("errors"), "source errors")
    if not source_sha256 or source_bytes < 1:
        raise ValueError("P10_PROSPECTIVE_RELATION_SOURCE_REF_INVALID")
    metrics = [
        _probe_metrics(_mapping(report, "source report"))
        for report in reports
    ]
    game_ids = [str(item["game_id"]) for item in metrics]
    observation_count = sum(
        _integer(item["observation_count"], "observation count")
        for item in metrics
    )
    fault_count = sum(
        _integer(item["fault_count"], "fault count")
        for item in metrics
    )
    known_count = sum(
        _integer(item["known_prediction_count"], "known count")
        for item in metrics
    )
    correct_count = sum(
        _integer(item["correct_prediction_count"], "correct count")
        for item in metrics
    )
    baseline_known = sum(
        _integer(
            item["baseline_known_prediction_count"],
            "baseline known count",
        )
        for item in metrics
    )
    baseline_correct = sum(
        _integer(
            item["baseline_correct_prediction_count"],
            "baseline correct count",
        )
        for item in metrics
    )
    obligations: Counter[str] = Counter()
    relation_deltas: Counter[str] = Counter()
    contrasts: Counter[str] = Counter()
    for item in metrics:
        obligations.update(
            {
                str(key): _integer(value, "obligation count")
                for key, value in _mapping(
                    item["obligation_counts"],
                    "obligation counts",
                ).items()
            }
        )
        relation_deltas.update(
            {
                str(key): _integer(value, "relation delta count")
                for key, value in _mapping(
                    item["relation_delta_counts"],
                    "relation delta counts",
                ).items()
            }
        )
        contrasts[str(item["accuracy_contrast"])] += 1
    relation_accuracy_milli = (
        0 if not known_count else round(1000 * correct_count / known_count)
    )
    baseline_accuracy_milli = (
        0
        if not baseline_known
        else round(1000 * baseline_correct / baseline_known)
    )
    checks = {
        "source_is_p10_offline": (
            source_report.get("phase") == "P10"
            and source_report.get("operation_mode") == "offline"
        ),
        "source_is_active_hybrid_shadow_probe": (
            source_report.get("instruction_lifecycle") == "active"
            and source_report.get("instruction_variant") == "hybrid"
            and source_report.get("max_actions")
            == _EXPECTED_MAX_ACTIONS
        ),
        "all_25_games_reported_once": (
            source_report.get("environment_count")
            == _EXPECTED_GAME_COUNT
            and source_report.get("completed_count")
            == _EXPECTED_GAME_COUNT
            and len(metrics) == _EXPECTED_GAME_COUNT
            and len(set(game_ids)) == _EXPECTED_GAME_COUNT
        ),
        "source_execution_errors_zero": (
            source_report.get("error_count") == 0 and not errors
        ),
        "every_probe_has_16_observations": all(
            item["observation_count"] == _EXPECTED_MAX_ACTIONS
            for item in metrics
        ),
        "probe_faults_zero": fault_count == 0,
        "passive_identity_free_boundary_pass": all(
            item["passive_boundary_pass"] is True for item in metrics
        ),
        "positive_and_negative_relation_deltas_observed": (
            relation_deltas["RELATION_CHANGED"] > 0
            and relation_deltas["RELATION_STABLE"] > 0
        ),
        "commit_and_hazard_obligations_observed": (
            obligations["REOBSERVE_COMMIT_STATE"] > 0
            and obligations["SUSPEND_AND_REQUEST_ROLLBACK"] > 0
        ),
        "relation_accuracy_exceeds_history_only_baseline": (
            relation_accuracy_milli > baseline_accuracy_milli
        ),
        "positive_game_contrasts_exceed_negative": (
            contrasts["POSITIVE"] > contrasts["NEGATIVE"]
        ),
        "known_predictions_cover_at_least_four_fifths": (
            5 * known_count >= 4 * observation_count
        ),
    }
    cluster_stable = all(checks.values())
    body: dict[str, object] = {
        "schema_version": (
            P10_PROSPECTIVE_RELATION_CLUSTER_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_prospective_relation_cluster_audit"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "work_block_id": (
            "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER"
        ),
        "candidate_tier": (
            "CLUSTER_STABLE" if cluster_stable else "LOCAL_PROBE"
        ),
        "source_report": {
            "sha256": source_sha256,
            "bytes": source_bytes,
            "max_actions": source_report.get("max_actions"),
            "game_count": len(metrics),
        },
        "aggregate": {
            "observation_count": observation_count,
            "fault_count": fault_count,
            "known_prediction_count": known_count,
            "correct_prediction_count": correct_count,
            "relation_accuracy_milli": relation_accuracy_milli,
            "baseline_known_prediction_count": baseline_known,
            "baseline_correct_prediction_count": baseline_correct,
            "baseline_accuracy_milli": baseline_accuracy_milli,
            "accuracy_delta_milli": (
                relation_accuracy_milli - baseline_accuracy_milli
            ),
            "game_contrasts": dict(sorted(contrasts.items())),
            "obligation_counts": dict(sorted(obligations.items())),
            "relation_delta_counts": dict(sorted(relation_deltas.items())),
        },
        "per_game": metrics,
        "cluster_checks": checks,
        "hds_judgment": {
            "authority": "development-hds-only",
            "local_probe_status": "PASS",
            "cluster_stable_status": (
                "PASS" if cluster_stable else "HOLD"
            ),
            "composition_input_authorized": cluster_stable,
            "action_selection_authorized": False,
            "memory_write_authorized": False,
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "reason_codes": (
                [
                    "all-25-shadow-probe-complete",
                    "pre-action-relation-outperforms-history-only-baseline",
                    "passive-identity-free-boundary-pass",
                    "cluster-evidence-may-enter-composition-audit-only",
                ]
                if cluster_stable
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


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
            "Build the all-25 shadow prospective-relation cluster audit."
        )
    )
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_path = args.source_report.resolve()
    audit = build_p10_prospective_relation_cluster_audit(
        _json(source_path),
        source_sha256=_sha256(source_path),
        source_bytes=source_path.stat().st_size,
    )
    _write_json(args.output.resolve(), audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_PROSPECTIVE_RELATION_CLUSTER_AUDIT_SCHEMA_VERSION",
    "build_p10_prospective_relation_cluster_audit",
    "main",
]
