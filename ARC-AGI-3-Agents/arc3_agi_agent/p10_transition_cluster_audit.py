"""Audit C2 observation separately from non-circular C3 prediction.

The retained C2/C3 telemetry is produced after an action.  It can prove that
rendered effects and observed boundaries are classified consistently, but the
stored ``predicted_boundary`` field is also derived after that action and is
therefore not predictive evidence.

This development-only audit gives that field no predictive credit.  C3 is
instead evaluated from information available before each held-out action:
the rendered source structure, action prototype, and action class.  It uses
both leave-one-game-out transfer and within-game prequential evaluation.  A
valid but weak predictor produces an HDS HOLD artifact rather than an
integrity exception.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from .cross_cutting_transition import (
    C2_C3_CAPABILITY_IDS,
    C2_C3_PROBE_FORMAT,
    BoundaryLabel,
)
from .p10_evidence import build_p10_compact_run_evidence
from .schema import digest_object, forbidden_runtime_paths

C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION = (
    "arc3-c2-c3-predictive-cluster-audit-v2"
)
_CONTENT_DIGEST_PREFIX = "arc3_c2_c3_predictive_cluster_audit:"
_BOUNDARY_LABELS: tuple[BoundaryLabel, ...] = (
    "COMMIT",
    "HAZARD",
    "TRANSITION_NO_COMMIT",
    "NO_VISIBLE_COMMIT",
)
_MIN_BOUNDARY_GAME_SUPPORT = {
    "COMMIT": 3,
    "HAZARD": 3,
    "TRANSITION_NO_COMMIT": 3,
    "NO_VISIBLE_COMMIT": 3,
}
_REQUIRED_EFFECT_GAME_SUPPORT = {
    "VISIBLE_STATE_CHANGE": 3,
    "NO_VISIBLE_CHANGE": 3,
    "COMPONENT_MOTION": 3,
    "LOCAL_PIXEL_DELTA": 3,
    "REGIONAL_REDRAW": 2,
    "GLOBAL_REDRAW": 2,
}
_ROLE_BY_BOUNDARY = {
    "COMMIT": "POSITIVE",
    "HAZARD": "HAZARD",
    "TRANSITION_NO_COMMIT": "NEGATIVE",
    "NO_VISIBLE_COMMIT": "NEGATIVE",
}
_OBLIGATION_BY_BOUNDARY = {
    "COMMIT": "REOBSERVE_COMMIT_STATE",
    "HAZARD": "SUSPEND_AND_REQUEST_ROLLBACK",
    "TRANSITION_NO_COMMIT": "REOBSERVE_BEFORE_CONTINUATION",
    "NO_VISIBLE_COMMIT": "WAIT_REOBSERVE_OR_REPLAN",
}
_LOO_MIN_COVERAGE_MILLI = 900
_LOO_MIN_ACCURACY_MILLI = 750
_LOO_MIN_RECALL_MILLI = 500
_PREQUENTIAL_MIN_COVERAGE_MILLI = 800
_PREQUENTIAL_MIN_ACCURACY_MILLI = 800
_PREQUENTIAL_MIN_RECALL_MILLI = 400

PredictionSource = Literal["EXACT", "GLOBAL", "NONE"]


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(value: object, field_name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    rows: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} rows must be objects")
        rows.append(item)
    return rows


def _strings(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return tuple(str(item) for item in value)


def _boundary(value: object, field_name: str) -> BoundaryLabel:
    text = str(value)
    if text not in _BOUNDARY_LABELS:
        raise ValueError(f"{field_name} boundary invalid")
    return cast(BoundaryLabel, text)


def _expected_boundary(record: Mapping[str, Any]) -> BoundaryLabel:
    terminal_state = str(record.get("terminal_state", ""))
    progress = record.get("progress_observed")
    if not isinstance(progress, bool):
        raise TypeError("progress_observed must be boolean")
    effects = set(_strings(record.get("effect_classes"), "effect_classes"))
    if terminal_state == "GAME_OVER":
        return "HAZARD"
    if progress or terminal_state == "WIN":
        return "COMMIT"
    if "VISIBLE_STATE_CHANGE" in effects:
        return "TRANSITION_NO_COMMIT"
    if "NO_VISIBLE_CHANGE" in effects:
        return "NO_VISIBLE_COMMIT"
    raise ValueError("C2_C3_VISIBLE_EFFECT_SEPARATOR_MISSING")


def _post_action_semantics_valid(record: Mapping[str, Any]) -> bool:
    expected = _expected_boundary(record)
    observed = str(record.get("observed_boundary", ""))
    recomputed = str(record.get("predicted_boundary", ""))
    effects = set(_strings(record.get("effect_classes"), "effect_classes"))
    visible_separator = (
        ("VISIBLE_STATE_CHANGE" in effects)
        != ("NO_VISIBLE_CHANGE" in effects)
    )
    hazard_separator = (
        expected != "HAZARD"
        or "IRREVERSIBLE_HAZARD" in effects
    )
    commit_separator = (
        expected != "COMMIT"
        or (
            bool(record.get("progress_observed"))
            and "PROGRESS_BOUNDARY" in effects
        )
        or str(record.get("terminal_state", "")) == "WIN"
    )
    return all(
        (
            observed == expected,
            recomputed == expected,
            str(record.get("contrast_role", ""))
            == _ROLE_BY_BOUNDARY[expected],
            str(record.get("reobserve_obligation", ""))
            == _OBLIGATION_BY_BOUNDARY[expected],
            visible_separator,
            hazard_separator,
            commit_separator,
            bool(str(record.get("source_structure_class", ""))),
            bool(str(record.get("action_prototype", ""))),
            bool(str(record.get("action_class", ""))),
            not forbidden_runtime_paths(record),
        )
    )


@dataclass(frozen=True, slots=True)
class _GameProbe:
    game_id: str
    records: tuple[Mapping[str, Any], ...]


@dataclass(slots=True)
class _PredictionStats:
    total: int = 0
    predicted: int = 0
    correct: int = 0
    exact_model_match_count: int = 0
    global_model_match_count: int = 0
    no_model_match_count: int = 0
    support: Counter[str] = field(default_factory=Counter)
    correct_by_truth: Counter[str] = field(default_factory=Counter)
    confusion: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )

    def observe(
        self,
        *,
        truth: BoundaryLabel,
        prediction: BoundaryLabel | None,
        source: PredictionSource,
    ) -> None:
        self.total += 1
        self.support[truth] += 1
        if source == "EXACT":
            self.exact_model_match_count += 1
        elif source == "GLOBAL":
            self.global_model_match_count += 1
        else:
            self.no_model_match_count += 1
        if prediction is None:
            return
        self.predicted += 1
        self.confusion[truth][prediction] += 1
        if prediction == truth:
            self.correct += 1
            self.correct_by_truth[truth] += 1

    def to_payload(self) -> dict[str, object]:
        recall = {
            label: (
                0
                if self.support[label] == 0
                else round(
                    1000
                    * self.correct_by_truth[label]
                    / self.support[label]
                )
            )
            for label in _BOUNDARY_LABELS
        }
        supported_recall = [
            recall[label]
            for label in _BOUNDARY_LABELS
            if self.support[label] > 0
        ]
        return {
            "total_count": self.total,
            "prediction_count": self.predicted,
            "unknown_count": self.total - self.predicted,
            "correct_count": self.correct,
            "coverage_milli": (
                0
                if self.total == 0
                else round(1000 * self.predicted / self.total)
            ),
            "accuracy_milli": (
                0
                if self.predicted == 0
                else round(1000 * self.correct / self.predicted)
            ),
            "macro_recall_milli": (
                0
                if not supported_recall
                else round(sum(supported_recall) / len(supported_recall))
            ),
            "recall_milli_by_boundary": recall,
            "support_by_boundary": {
                label: self.support[label] for label in _BOUNDARY_LABELS
            },
            "exact_model_match_count": self.exact_model_match_count,
            "global_model_match_count": self.global_model_match_count,
            "no_model_match_count": self.no_model_match_count,
            "confusion_matrix": {
                truth: {
                    predicted: self.confusion[truth][predicted]
                    for predicted in _BOUNDARY_LABELS
                }
                for truth in _BOUNDARY_LABELS
            },
        }


def _exact_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("source_structure_class", "")),
        str(record.get("action_prototype", "")),
    )


def _global_key(record: Mapping[str, Any]) -> str:
    return str(record.get("action_class", ""))


def _majority_label(counts: Mapping[str, int]) -> BoundaryLabel | None:
    if not counts:
        return None
    maximum = max(int(value) for value in counts.values())
    winners = sorted(
        label
        for label, count in counts.items()
        if int(count) == maximum
    )
    if len(winners) != 1:
        return None
    return _boundary(winners[0], "model")


def _predict(
    record: Mapping[str, Any],
    *,
    exact_models: Mapping[tuple[str, str], Counter[str]],
    global_models: Mapping[str, Counter[str]],
) -> tuple[BoundaryLabel | None, PredictionSource]:
    exact = exact_models.get(_exact_key(record))
    if exact:
        return _majority_label(exact), "EXACT"
    global_counts = global_models.get(_global_key(record))
    if global_counts:
        return _majority_label(global_counts), "GLOBAL"
    return None, "NONE"


def _update_models(
    record: Mapping[str, Any],
    *,
    exact_models: dict[tuple[str, str], Counter[str]],
    global_models: dict[str, Counter[str]],
) -> None:
    truth = _boundary(record.get("observed_boundary"), "observed")
    exact_models.setdefault(_exact_key(record), Counter())[truth] += 1
    global_models.setdefault(_global_key(record), Counter())[truth] += 1


def _train_models(
    games: Sequence[_GameProbe],
    *,
    excluded_game_id: str,
) -> tuple[
    dict[tuple[str, str], Counter[str]],
    dict[str, Counter[str]],
]:
    exact_models: dict[tuple[str, str], Counter[str]] = {}
    global_models: dict[str, Counter[str]] = {}
    for game in games:
        if game.game_id == excluded_game_id:
            continue
        for record in game.records:
            _update_models(
                record,
                exact_models=exact_models,
                global_models=global_models,
            )
    return exact_models, global_models


def _leave_one_game_out(games: Sequence[_GameProbe]) -> _PredictionStats:
    stats = _PredictionStats()
    for held_out in games:
        exact_models, global_models = _train_models(
            games,
            excluded_game_id=held_out.game_id,
        )
        for record in held_out.records:
            prediction, source = _predict(
                record,
                exact_models=exact_models,
                global_models=global_models,
            )
            stats.observe(
                truth=_boundary(
                    record.get("observed_boundary"),
                    "observed",
                ),
                prediction=prediction,
                source=source,
            )
    return stats


def _within_game_prequential(
    games: Sequence[_GameProbe],
) -> _PredictionStats:
    stats = _PredictionStats()
    for game in games:
        exact_models: dict[tuple[str, str], Counter[str]] = {}
        global_models: dict[str, Counter[str]] = {}
        for record in game.records:
            prediction, source = _predict(
                record,
                exact_models=exact_models,
                global_models=global_models,
            )
            stats.observe(
                truth=_boundary(
                    record.get("observed_boundary"),
                    "observed",
                ),
                prediction=prediction,
                source=source,
            )
            _update_models(
                record,
                exact_models=exact_models,
                global_models=global_models,
            )
    return stats


def _metric_int(
    metrics: Mapping[str, object],
    field_name: str,
) -> int:
    value = metrics.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _minimum_recall(
    metrics: Mapping[str, object],
) -> int:
    raw = metrics.get("recall_milli_by_boundary")
    if not isinstance(raw, Mapping):
        raise TypeError("recall_milli_by_boundary must be an object")
    values: list[int] = []
    for label in _BOUNDARY_LABELS:
        value = raw.get(label)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{label} recall must be an integer")
        values.append(value)
    return min(values)


def build_c2_c3_cluster_audit(
    *,
    raw_report: Mapping[str, Any],
    raw_report_sha256: str,
    compact_evidence: Mapping[str, Any],
    compact_evidence_sha256: str,
) -> dict[str, Any]:
    """Build a fail-closed C2 observer and C3 predictive tier decision."""

    reports = _rows(raw_report.get("reports"), "reports")
    errors = _rows(raw_report.get("errors"), "errors")
    compact_body = dict(compact_evidence)
    compact_digest = str(compact_body.pop("content_digest", ""))
    compact_digest_valid = compact_digest == digest_object(compact_body)
    compact_matches_raw = (
        dict(compact_evidence)
        == build_p10_compact_run_evidence(raw_report)
    )

    boundary_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    effect_counts: Counter[str] = Counter()
    boundary_games: defaultdict[str, set[str]] = defaultdict(set)
    boundary_structures: defaultdict[str, set[str]] = defaultdict(set)
    effect_games: defaultdict[str, set[str]] = defaultdict(set)
    game_rows: list[dict[str, object]] = []
    games: list[_GameProbe] = []
    game_ids: list[str] = []
    total_actions = 0
    total_observations = 0
    total_records = 0
    total_faults = 0
    total_overflow = 0
    all_records_retained = True
    all_post_action_semantics_valid = True
    all_probe_formats_valid = True
    all_probe_tiers_local = True
    all_probe_runtime_use_forbidden = True
    all_capability_ids_valid = True
    identity_free = True
    action_selection_influence = False
    unauthorized_authority = False

    for report in reports:
        game_id = str(report.get("game_id", ""))
        game_ids.append(game_id)
        probe = report.get("development_transition_probe")
        if not isinstance(probe, Mapping):
            raise ValueError(f"C2_C3_PROBE_MISSING:{game_id}")
        all_probe_formats_valid = all_probe_formats_valid and (
            probe.get("format") == C2_C3_PROBE_FORMAT
        )
        all_probe_tiers_local = all_probe_tiers_local and (
            probe.get("candidate_tier") == "LOCAL_PROBE"
        )
        all_probe_runtime_use_forbidden = (
            all_probe_runtime_use_forbidden
            and probe.get("runtime_decision_use") == "FORBIDDEN"
        )
        all_capability_ids_valid = all_capability_ids_valid and (
            _strings(probe.get("capability_ids"), "capability_ids")
            == C2_C3_CAPABILITY_IDS
        )
        records = _rows(
            probe.get("contrast_records"),
            f"{game_id} contrast_records",
        )
        observation_count = int(probe.get("observation_count", -1))
        fault_count = int(probe.get("fault_count", -1))
        overflow_count = sum(
            int(probe.get(field_name, -1))
            for field_name in (
                "model_overflow_count",
                "context_overflow_count",
                "contrast_overflow_count",
            )
        )
        total_actions += int(report.get("actions", 0))
        total_observations += observation_count
        total_records += len(records)
        total_faults += fault_count
        total_overflow += overflow_count
        all_records_retained = all_records_retained and (
            len(records) == observation_count
            and [
                int(record.get("ordinal", -1)) for record in records
            ]
            == list(range(1, observation_count + 1))
        )
        game_boundaries: Counter[str] = Counter()
        game_effects: Counter[str] = Counter()
        for record in records:
            all_post_action_semantics_valid = (
                all_post_action_semantics_valid
                and _post_action_semantics_valid(record)
            )
            identity_free = identity_free and (
                not forbidden_runtime_paths(record)
            )
            boundary = _boundary(
                record.get("observed_boundary"),
                "observed",
            )
            structure = str(record.get("source_structure_class", ""))
            role = str(record.get("contrast_role", ""))
            effects = _strings(
                record.get("effect_classes"),
                "effect_classes",
            )
            boundary_counts[boundary] += 1
            role_counts[role] += 1
            game_boundaries[boundary] += 1
            boundary_games[boundary].add(game_id)
            boundary_structures[boundary].add(structure)
            for effect in effects:
                effect_counts[effect] += 1
                game_effects[effect] += 1
                effect_games[effect].add(game_id)
        action_selection_influence = action_selection_influence or bool(
            probe.get("action_selection_influence")
        )
        unauthorized_authority = unauthorized_authority or any(
            bool(probe.get(field_name))
            for field_name in (
                "memory_write_authority",
                "external_emit_authority",
                "runtime_p_promotion_authority",
            )
        )
        games.append(_GameProbe(game_id, tuple(records)))
        game_rows.append(
            {
                "game_id": game_id,
                "actions": int(report.get("actions", 0)),
                "observations": observation_count,
                "contrast_records": len(records),
                "faults": fault_count,
                "overflow": overflow_count,
                "boundary_counts": dict(sorted(game_boundaries.items())),
                "effect_counts": dict(sorted(game_effects.items())),
            }
        )

    games.sort(key=lambda item: item.game_id)
    game_rows.sort(key=lambda row: str(row["game_id"]))
    game_ids.sort()
    checkpointing = raw_report.get("checkpointing")
    conditions: Mapping[str, Any] | None = None
    conditions_digest_valid = False
    condition_game_ids: list[str] = []
    if isinstance(checkpointing, Mapping):
        raw_conditions = checkpointing.get("conditions")
        if isinstance(raw_conditions, Mapping):
            conditions = raw_conditions
            conditions_body = dict(raw_conditions)
            claimed = str(
                conditions_body.pop("conditions_digest", "")
            )
            conditions_digest_valid = claimed == digest_object(
                conditions_body
            )
            raw_ids = raw_conditions.get("game_ids")
            if isinstance(raw_ids, Sequence) and not isinstance(
                raw_ids,
                (str, bytes, bytearray),
            ):
                condition_game_ids = sorted(str(item) for item in raw_ids)

    integrity_checks = {
        "operation_mode_offline": (
            str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
        ),
        "instruction_lifecycle_active": (
            raw_report.get("instruction_lifecycle") == "active"
        ),
        "standard_budget_450": int(raw_report.get("max_actions", 0)) == 450,
        "all_25_environments_reported": (
            int(raw_report.get("environment_count", 0)) == 25
            and len(reports) == 25
            and len(set(game_ids)) == 25
        ),
        "error_count_zero": (
            int(raw_report.get("error_count", -1)) == 0 and not errors
        ),
        "probe_format_v2": all_probe_formats_valid,
        "probe_tier_local": all_probe_tiers_local,
        "probe_runtime_use_forbidden": (
            all_probe_runtime_use_forbidden
        ),
        "capability_ids_exact": all_capability_ids_valid,
        "probe_fault_count_zero": total_faults == 0,
        "bounded_retention_overflow_zero": total_overflow == 0,
        "all_observations_have_contrast_records": (
            total_observations > 0
            and total_observations == total_records
            and all_records_retained
        ),
        "all_post_action_semantics_recomputed": (
            all_post_action_semantics_valid
        ),
        "runtime_identity_absent": identity_free,
        "action_selection_influence_absent": (
            not action_selection_influence
        ),
        "memory_emit_promotion_authority_absent": (
            not unauthorized_authority
        ),
        "compact_content_digest_valid": compact_digest_valid,
        "compact_matches_raw_report": compact_matches_raw,
        "checkpoint_conditions_present": conditions is not None,
        "checkpoint_conditions_digest_valid": conditions_digest_valid,
        "reported_games_match_checkpoint_conditions": (
            game_ids == condition_game_ids
        ),
    }
    integrity_failures = sorted(
        key for key, passed in integrity_checks.items() if not passed
    )
    if integrity_failures:
        raise ValueError(
            "C2_C3_INPUT_INTEGRITY_AUDIT_FAILED:"
            + ",".join(integrity_failures)
        )
    if conditions is None:
        raise TypeError("C2_C3_CHECKPOINT_CONDITIONS_MISSING")

    c2_observer_checks = {
        "visible_and_no_visible_effects_cross_game": (
            len(effect_games["VISIBLE_STATE_CHANGE"]) >= 3
            and len(effect_games["NO_VISIBLE_CHANGE"]) >= 3
        ),
        "required_local_effect_classes_cross_game": all(
            len(effect_games[effect]) >= minimum
            for effect, minimum in _REQUIRED_EFFECT_GAME_SUPPORT.items()
        ),
        "positive_negative_hazard_contrast_cross_game": (
            len(boundary_games["COMMIT"]) >= 3
            and (
                len(boundary_games["TRANSITION_NO_COMMIT"]) >= 3
                or len(boundary_games["NO_VISIBLE_COMMIT"]) >= 3
            )
            and len(boundary_games["HAZARD"]) >= 3
            and role_counts["POSITIVE"] > 0
            and role_counts["NEGATIVE"] > 0
            and role_counts["HAZARD"] > 0
        ),
        "all_boundaries_have_cross_structure_support": all(
            len(boundary_structures[label]) >= 3
            for label in _BOUNDARY_LABELS
        ),
        "reobserve_and_rollback_obligations_recomputed": (
            all_post_action_semantics_valid
        ),
    }

    loo_payload = _leave_one_game_out(games).to_payload()
    prequential_payload = _within_game_prequential(games).to_payload()
    loo_recall = _minimum_recall(loo_payload)
    prequential_recall = _minimum_recall(prequential_payload)
    c3_predictive_checks = {
        "all_boundaries_have_training_game_support": all(
            len(boundary_games[label])
            >= _MIN_BOUNDARY_GAME_SUPPORT[label]
            for label in _BOUNDARY_LABELS
        ),
        "leave_one_game_out_coverage": (
            _metric_int(loo_payload, "coverage_milli")
            >= _LOO_MIN_COVERAGE_MILLI
        ),
        "leave_one_game_out_accuracy": (
            _metric_int(loo_payload, "accuracy_milli")
            >= _LOO_MIN_ACCURACY_MILLI
        ),
        "leave_one_game_out_all_boundary_recall": (
            loo_recall >= _LOO_MIN_RECALL_MILLI
        ),
        "within_game_prequential_coverage": (
            _metric_int(prequential_payload, "coverage_milli")
            >= _PREQUENTIAL_MIN_COVERAGE_MILLI
        ),
        "within_game_prequential_accuracy": (
            _metric_int(prequential_payload, "accuracy_milli")
            >= _PREQUENTIAL_MIN_ACCURACY_MILLI
        ),
        "within_game_prequential_all_boundary_recall": (
            prequential_recall >= _PREQUENTIAL_MIN_RECALL_MILLI
        ),
        "post_action_recomputed_label_not_counted_as_prediction": True,
    }
    c2_cluster_stable = all(c2_observer_checks.values())
    c3_cluster_stable = all(c3_predictive_checks.values())
    pair_cluster_stable = c2_cluster_stable and c3_cluster_stable

    boundary_support = {
        label: {
            "observations": boundary_counts[label],
            "game_count": len(boundary_games[label]),
            "structure_count": len(boundary_structures[label]),
        }
        for label in _BOUNDARY_LABELS
    }
    effect_support = {
        effect: {
            "observations": effect_counts[effect],
            "game_count": len(effect_games[effect]),
        }
        for effect in sorted(effect_counts)
    }
    body: dict[str, Any] = {
        "schema_version": C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_c2_c3_predictive_cluster_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_ids": list(C2_C3_CAPABILITY_IDS),
        "candidate_tier": (
            "CLUSTER_STABLE" if pair_cluster_stable else "LOCAL_PROBE"
        ),
        "capability_tiers": {
            C2_C3_CAPABILITY_IDS[0]: (
                "CLUSTER_STABLE"
                if c2_cluster_stable
                else "LOCAL_PROBE"
            ),
            C2_C3_CAPABILITY_IDS[1]: (
                "CLUSTER_STABLE"
                if c3_cluster_stable
                else "LOCAL_PROBE"
            ),
        },
        "source_evidence": {
            "raw_report_sha256": raw_report_sha256,
            "compact_evidence_sha256": compact_evidence_sha256,
            "compact_content_digest": compact_digest,
            "conditions": dict(conditions),
        },
        "prediction_contract": {
            "available_before_held_out_action": [
                "rendered source structure class",
                "action prototype",
                "action class",
            ],
            "forbidden_prediction_inputs": [
                "target structure class",
                "post-action effect classes",
                "terminal state",
                "progress observed",
                "observed boundary",
                "task game or level identity",
            ],
            "stored_predicted_boundary_semantics": (
                "post-action recomputation retained for telemetry integrity"
            ),
            "stored_predicted_boundary_predictive_credit": "NONE",
            "leave_one_game_out_model": (
                "exact source-structure plus action-prototype majority, "
                "then global action-class majority"
            ),
            "within_game_model": (
                "same model updated only after each prediction"
            ),
        },
        "thresholds": {
            "minimum_boundary_game_support": (
                _MIN_BOUNDARY_GAME_SUPPORT
            ),
            "required_effect_game_support": (
                _REQUIRED_EFFECT_GAME_SUPPORT
            ),
            "leave_one_game_out": {
                "minimum_coverage_milli": _LOO_MIN_COVERAGE_MILLI,
                "minimum_accuracy_milli": _LOO_MIN_ACCURACY_MILLI,
                "minimum_recall_milli_each_boundary": (
                    _LOO_MIN_RECALL_MILLI
                ),
            },
            "within_game_prequential": {
                "minimum_coverage_milli": (
                    _PREQUENTIAL_MIN_COVERAGE_MILLI
                ),
                "minimum_accuracy_milli": (
                    _PREQUENTIAL_MIN_ACCURACY_MILLI
                ),
                "minimum_recall_milli_each_boundary": (
                    _PREQUENTIAL_MIN_RECALL_MILLI
                ),
            },
        },
        "summary": {
            "game_count": len(game_rows),
            "completed_levels": int(
                raw_report.get("completed_levels", 0)
            ),
            "total_levels": int(raw_report.get("total_levels", 0)),
            "action_count": total_actions,
            "observation_count": total_observations,
            "contrast_record_count": total_records,
            "fault_count": total_faults,
            "overflow_count": total_overflow,
            "boundary_counts": dict(sorted(boundary_counts.items())),
            "contrast_role_counts": dict(sorted(role_counts.items())),
            "effect_counts": dict(sorted(effect_counts.items())),
            "error_count": int(raw_report.get("error_count", -1)),
        },
        "cross_context_support": {
            "boundaries": boundary_support,
            "effects": effect_support,
        },
        "predictive_evaluation": {
            "leave_one_game_out": loo_payload,
            "within_game_prequential": prequential_payload,
        },
        "integrity_checks": integrity_checks,
        "c2_observer_checks": c2_observer_checks,
        "c3_predictive_checks": c3_predictive_checks,
        "rows": game_rows,
        "hds_judgment": {
            "local_probe_status": "PASS",
            "c2_cluster_stable_observer_status": (
                "PASS" if c2_cluster_stable else "HOLD"
            ),
            "c3_cluster_stable_predictor_status": (
                "PASS" if c3_cluster_stable else "HOLD"
            ),
            "cluster_stable_status": (
                "PASS" if pair_cluster_stable else "HOLD"
            ),
            "composable_status": "HOLD",
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "reason_codes": [
                (
                    "C2_POST_ACTION_OBSERVER_CROSS_GAME_STABLE"
                    if c2_cluster_stable
                    else "C2_POST_ACTION_OBSERVER_INSUFFICIENT"
                ),
                (
                    "C3_NON_CIRCULAR_PREDICTOR_CROSS_GAME_STABLE"
                    if c3_cluster_stable
                    else "C3_NON_CIRCULAR_PREDICTOR_INSUFFICIENT"
                ),
                "C2_C3_COMPOSITION_AND_REMOVAL_NOT_PROVEN",
            ],
            "next_bounded_experiment": (
                "add an identity-free visible causal-context feature and "
                "repeat held-out prediction before any Runtime P compile"
                if not c3_cluster_stable
                else "compose C2 and C3 with removal and regression controls"
            ),
        },
    }
    return {
        **body,
        "content_digest": _CONTENT_DIGEST_PREFIX + digest_object(body),
    }


def write_c2_c3_cluster_audit(
    *,
    raw_report_path: Path,
    compact_evidence_path: Path,
    output_path: Path,
) -> Path:
    value = build_c2_c3_cluster_audit(
        raw_report=_json_object(raw_report_path),
        raw_report_sha256=_sha256(raw_report_path),
        compact_evidence=_json_object(compact_evidence_path),
        compact_evidence_sha256=_sha256(compact_evidence_path),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
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
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit C2 post-action observation and non-circular C3 "
            "prediction separately."
        )
    )
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--compact-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c2_c3_cluster_audit(
        raw_report_path=args.raw_report,
        compact_evidence_path=args.compact_evidence,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION",
    "build_c2_c3_cluster_audit",
    "write_c2_c3_cluster_audit",
]
