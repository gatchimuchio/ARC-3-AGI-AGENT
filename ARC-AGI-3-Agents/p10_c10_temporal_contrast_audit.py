"""Audit a materially new C10 temporal-causal contrast from P10 traces.

The legacy C10 phase/timer surface is closed negative.  This development-only
audit therefore does not count timer changes.  It asks a narrower question:
does the same rendered source frame and same action have different visible
outcomes, and can the immediately preceding action/effect boundary separate
those outcomes without game identity or a replay suffix?

The audit only reads completed shadow telemetry.  It cannot choose or emit an
action, write memory, compile Runtime P, or promote a capability.
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

from arc3_agi_agent.cross_cutting_transition import C2_C3_PROBE_FORMAT
from arc3_agi_agent.schema import digest_object

C10_TEMPORAL_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c10-temporal-causal-contrast-audit-v2"
)
C10_CAPABILITY_ID = "C10_phase_timer_unlock_model"
C10_EXAMPLE_LIMIT = 128
C10_MIN_GAME_SUPPORT = 3
C10_MIN_SEPARABLE_GROUPS = 2
C10_MIN_AMBIGUOUS_ACCURACY_DELTA_MILLI = 100
C10_MIN_HELD_OUT_MECHANISM_GAME_SUPPORT = 2

BoundaryLabel = Literal[
    "COMMIT",
    "HAZARD",
    "TRANSITION_NO_COMMIT",
    "NO_VISIBLE_COMMIT",
]
CoarseOutcome = Literal["TRANSITION", "NO_CHANGE", "HAZARD"]
PredictionSource = Literal["CONTEXT", "GROUP", "GLOBAL", "NONE"]
GroupKey = tuple[str, str, str]
ContextToken = tuple[str, CoarseOutcome]
_BOUNDARY_LABELS: tuple[BoundaryLabel, ...] = (
    "COMMIT",
    "HAZARD",
    "TRANSITION_NO_COMMIT",
    "NO_VISIBLE_COMMIT",
)


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


def _items(value: object, field_name: str) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return list(value)


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


def _coarse_outcome(record: Mapping[str, Any]) -> CoarseOutcome:
    boundary = _boundary(
        record.get("observed_boundary"),
        "observed",
    )
    if boundary == "HAZARD":
        return "HAZARD"
    if boundary == "NO_VISIBLE_COMMIT":
        return "NO_CHANGE"
    return "TRANSITION"


def _emitted_step(
    value: object,
    *,
    game_id: str,
    ordinal: int,
) -> Mapping[str, Any]:
    steps = _rows(value, f"{game_id} emitted_steps[{ordinal}]")
    if not steps:
        raise ValueError(f"C10_EMITTED_STEP_MISSING:{game_id}:{ordinal}")
    step = steps[0]
    source = step.get("visual_source_signature")
    if not isinstance(source, str) or not source.startswith("visual-state:"):
        raise ValueError(
            f"C10_RENDERED_SOURCE_SIGNATURE_MISSING:{game_id}:{ordinal}"
        )
    return step


def _outcome(record: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        _strings(record.get("effect_classes"), "effect_classes"),
        str(record.get("observed_boundary", "")),
    )


def _causal_token(record: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        str(record.get("action_class", "")),
        _strings(record.get("effect_classes"), "effect_classes"),
        str(record.get("observed_boundary", "")),
    )


def _runtime_context_token(
    record: Mapping[str, Any],
) -> ContextToken:
    """Return the bounded token available before the next action."""

    prototype = str(record.get("action_prototype", ""))
    if not prototype:
        raise ValueError("C10_PREVIOUS_ACTION_PROTOTYPE_MISSING")
    return prototype, _coarse_outcome(record)


def _group_key(
    *,
    step: Mapping[str, Any],
    record: Mapping[str, Any],
) -> GroupKey:
    return (
        str(step["visual_source_signature"]),
        str(record.get("action_prototype", "")),
        str(record.get("action_class", "")),
    )


def _group_digest(
    *,
    key: GroupKey,
    observations: Sequence[tuple[int, tuple[object, ...]]],
) -> str:
    return "temporal-contrast-group:" + digest_object(
        {
            "source_rendered_signature": key[0],
            "action_prototype": key[1],
            "action_class": key[2],
            "observations": [
                {
                    "ordinal": ordinal,
                    "outcome": outcome,
                }
                for ordinal, outcome in observations
            ],
        }
    )[:24]


@dataclass(frozen=True, slots=True)
class _PredictiveRow:
    ordinal: int
    group_key: GroupKey
    action_class: str
    previous_context: ContextToken | None
    truth: BoundaryLabel
    detailed_outcome: tuple[object, ...]


@dataclass(slots=True)
class _PredictionStats:
    total: int = 0
    predicted: int = 0
    correct: int = 0
    source_counts: Counter[str] = field(default_factory=Counter)
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
        self.source_counts[source] += 1
        if prediction is None:
            return
        self.predicted += 1
        self.confusion[truth][prediction] += 1
        if prediction == truth:
            self.correct += 1
            self.correct_by_truth[truth] += 1

    def merge(self, other: _PredictionStats) -> None:
        self.total += other.total
        self.predicted += other.predicted
        self.correct += other.correct
        self.source_counts.update(other.source_counts)
        self.support.update(other.support)
        self.correct_by_truth.update(other.correct_by_truth)
        for truth, row in other.confusion.items():
            self.confusion[truth].update(row)

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
            "recall_milli_by_boundary": recall,
            "support_by_boundary": {
                label: self.support[label] for label in _BOUNDARY_LABELS
            },
            "prediction_source_counts": {
                source: self.source_counts[source]
                for source in ("CONTEXT", "GROUP", "GLOBAL", "NONE")
            },
            "confusion_matrix": {
                truth: {
                    prediction: self.confusion[truth][prediction]
                    for prediction in _BOUNDARY_LABELS
                }
                for truth in _BOUNDARY_LABELS
            },
        }


@dataclass(frozen=True, slots=True)
class _GamePredictionResult:
    all_baseline: _PredictionStats
    all_context: _PredictionStats
    all_action_only: _PredictionStats
    ambiguous_baseline: _PredictionStats
    ambiguous_context: _PredictionStats
    ambiguous_action_only: _PredictionStats


def _majority_label(
    counts: Mapping[str, int],
) -> BoundaryLabel | None:
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


def _fallback_prediction(
    *,
    group_counts: Mapping[str, int],
    global_counts: Mapping[str, int],
) -> tuple[BoundaryLabel | None, PredictionSource]:
    group_prediction = _majority_label(group_counts)
    if group_prediction is not None:
        return group_prediction, "GROUP"
    global_prediction = _majority_label(global_counts)
    if global_prediction is not None:
        return global_prediction, "GLOBAL"
    return None, "NONE"


def _context_prediction(
    *,
    context_counts: Mapping[str, int] | None,
    group_counts: Mapping[str, int],
    global_counts: Mapping[str, int],
) -> tuple[BoundaryLabel | None, PredictionSource]:
    if context_counts:
        context_prediction = _majority_label(context_counts)
        if context_prediction is not None:
            return context_prediction, "CONTEXT"
    return _fallback_prediction(
        group_counts=group_counts,
        global_counts=global_counts,
    )


def _evaluate_prequential_game(
    *,
    rows: Sequence[_PredictiveRow],
    ambiguous_keys: frozenset[GroupKey],
) -> _GamePredictionResult:
    """Predict before update; no current or future outcome enters a model."""

    group_models: dict[GroupKey, Counter[str]] = {}
    global_models: dict[str, Counter[str]] = {}
    context_models: dict[
        tuple[GroupKey, ContextToken],
        Counter[str],
    ] = {}
    action_only_models: dict[
        tuple[GroupKey, str],
        Counter[str],
    ] = {}
    result = _GamePredictionResult(
        all_baseline=_PredictionStats(),
        all_context=_PredictionStats(),
        all_action_only=_PredictionStats(),
        ambiguous_baseline=_PredictionStats(),
        ambiguous_context=_PredictionStats(),
        ambiguous_action_only=_PredictionStats(),
    )

    for row in rows:
        group_counts = group_models.get(row.group_key, Counter())
        global_counts = global_models.get(row.action_class, Counter())
        baseline_prediction, baseline_source = _fallback_prediction(
            group_counts=group_counts,
            global_counts=global_counts,
        )
        context_counts = (
            None
            if row.previous_context is None
            else context_models.get(
                (row.group_key, row.previous_context)
            )
        )
        context_prediction, context_source = _context_prediction(
            context_counts=context_counts,
            group_counts=group_counts,
            global_counts=global_counts,
        )
        action_only_counts = (
            None
            if row.previous_context is None
            else action_only_models.get(
                (row.group_key, row.previous_context[0])
            )
        )
        action_only_prediction, action_only_source = (
            _context_prediction(
                context_counts=action_only_counts,
                group_counts=group_counts,
                global_counts=global_counts,
            )
        )
        for stats, prediction, source in (
            (
                result.all_baseline,
                baseline_prediction,
                baseline_source,
            ),
            (
                result.all_context,
                context_prediction,
                context_source,
            ),
            (
                result.all_action_only,
                action_only_prediction,
                action_only_source,
            ),
        ):
            stats.observe(
                truth=row.truth,
                prediction=prediction,
                source=source,
            )
        if row.group_key in ambiguous_keys:
            for stats, prediction, source in (
                (
                    result.ambiguous_baseline,
                    baseline_prediction,
                    baseline_source,
                ),
                (
                    result.ambiguous_context,
                    context_prediction,
                    context_source,
                ),
                (
                    result.ambiguous_action_only,
                    action_only_prediction,
                    action_only_source,
                ),
            ):
                stats.observe(
                    truth=row.truth,
                    prediction=prediction,
                    source=source,
                )

        group_models.setdefault(
            row.group_key,
            Counter(),
        )[row.truth] += 1
        global_models.setdefault(
            row.action_class,
            Counter(),
        )[row.truth] += 1
        if row.previous_context is not None:
            context_models.setdefault(
                (row.group_key, row.previous_context),
                Counter(),
            )[row.truth] += 1
            action_only_models.setdefault(
                (row.group_key, row.previous_context[0]),
                Counter(),
            )[row.truth] += 1
    return result


def _evaluate_leave_one_game_out_outcome_mapping(
    games: Sequence[tuple[str, tuple[_PredictiveRow, ...]]],
) -> tuple[_PredictionStats, _PredictionStats]:
    """Negative control: transfer learned outcome labels across games."""

    baseline = _PredictionStats()
    context = _PredictionStats()
    for held_out_game_id, held_out_rows in games:
        global_models: dict[str, Counter[str]] = {}
        context_models: dict[
            tuple[str, ContextToken],
            Counter[str],
        ] = {}
        for training_game_id, training_rows in games:
            if training_game_id == held_out_game_id:
                continue
            for row in training_rows:
                global_models.setdefault(
                    row.action_class,
                    Counter(),
                )[row.truth] += 1
                if row.previous_context is not None:
                    context_models.setdefault(
                        (
                            row.group_key[1],
                            row.previous_context,
                        ),
                        Counter(),
                    )[row.truth] += 1
        for row in held_out_rows:
            baseline_prediction = _majority_label(
                global_models.get(row.action_class, Counter())
            )
            context_counts = (
                None
                if row.previous_context is None
                else context_models.get(
                    (
                        row.group_key[1],
                        row.previous_context,
                    )
                )
            )
            context_prediction = (
                None
                if context_counts is None
                else _majority_label(context_counts)
            )
            if context_prediction is None:
                context_prediction = baseline_prediction
                context_source: PredictionSource = (
                    "GLOBAL"
                    if baseline_prediction is not None
                    else "NONE"
                )
            else:
                context_source = "CONTEXT"
            baseline.observe(
                truth=row.truth,
                prediction=baseline_prediction,
                source=(
                    "GLOBAL"
                    if baseline_prediction is not None
                    else "NONE"
                ),
            )
            context.observe(
                truth=row.truth,
                prediction=context_prediction,
                source=context_source,
            )
    return baseline, context


def _payload_metric(
    payload: Mapping[str, object],
    field_name: str,
) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _payload_recall(
    payload: Mapping[str, object],
    boundary: BoundaryLabel,
) -> int:
    raw = payload.get("recall_milli_by_boundary")
    if not isinstance(raw, Mapping):
        raise TypeError("recall_milli_by_boundary must be an object")
    value = raw.get(boundary)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{boundary} recall must be an integer")
    return value


def build_c10_temporal_contrast_audit(
    *,
    raw_report: Mapping[str, Any],
    raw_report_sha256: str,
) -> dict[str, object]:
    """Build a bounded C10 reopening audit from a complete shadow run."""

    reports = sorted(
        _rows(raw_report.get("reports"), "reports"),
        key=lambda report: str(report.get("game_id", "")),
    )
    errors = _rows(raw_report.get("errors"), "errors")
    contract_checks = {
        "operation_mode_offline": (
            str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
        ),
        "instruction_lifecycle_active": (
            raw_report.get("instruction_lifecycle") == "active"
        ),
        "standard_budget_450": raw_report.get("max_actions") == 450,
        "all_25_reports_present": (
            raw_report.get("environment_count") == 25
            and len(reports) == 25
            and len(
                {
                    str(report.get("game_id", ""))
                    for report in reports
                }
            )
            == 25
        ),
        "runtime_errors_zero": (
            raw_report.get("error_count") == 0 and not errors
        ),
    }

    game_rows: list[dict[str, object]] = []
    example_rows: list[dict[str, object]] = []
    all_group_digests: list[str] = []
    ambiguous_game_count = 0
    separable_game_count = 0
    ambiguous_group_count = 0
    separable_group_count = 0
    nonseparable_group_count = 0
    total_transitions = 0
    aggregate_prediction = _GamePredictionResult(
        all_baseline=_PredictionStats(),
        all_context=_PredictionStats(),
        all_action_only=_PredictionStats(),
        ambiguous_baseline=_PredictionStats(),
        ambiguous_context=_PredictionStats(),
        ambiguous_action_only=_PredictionStats(),
    )
    ambiguous_game_prediction_rows: list[dict[str, object]] = []
    prediction_games: list[
        tuple[str, tuple[_PredictiveRow, ...]]
    ] = []

    for report in reports:
        game_id = str(report.get("game_id", ""))
        probe = report.get("development_transition_probe")
        if not isinstance(probe, Mapping):
            raise ValueError(f"C10_TRANSITION_PROBE_MISSING:{game_id}")
        probe_checks = {
            "format": probe.get("format") == C2_C3_PROBE_FORMAT,
            "local_probe": probe.get("candidate_tier") == "LOCAL_PROBE",
            "runtime_forbidden": (
                probe.get("runtime_decision_use") == "FORBIDDEN"
            ),
            "action_influence_absent": (
                probe.get("action_selection_influence") is False
            ),
            "memory_authority_absent": (
                probe.get("memory_write_authority") is False
            ),
            "emit_authority_absent": (
                probe.get("external_emit_authority") is False
            ),
            "promotion_authority_absent": (
                probe.get("runtime_p_promotion_authority") is False
            ),
            "faults_zero": probe.get("fault_count") == 0,
            "overflow_zero": all(
                probe.get(field) == 0
                for field in (
                    "model_overflow_count",
                    "context_overflow_count",
                    "contrast_overflow_count",
                )
            ),
        }
        failures = sorted(
            key for key, passed in probe_checks.items() if not passed
        )
        if failures:
            raise ValueError(
                f"C10_SHADOW_CONTRACT_INVALID:{game_id}:"
                + ",".join(failures)
            )

        records = _rows(
            probe.get("contrast_records"),
            f"{game_id} contrast_records",
        )
        emitted_steps = _items(
            report.get("emitted_steps"),
            f"{game_id} emitted_steps",
        )
        if (
            len(records) != len(emitted_steps)
            or probe.get("observation_count") != len(records)
        ):
            raise ValueError(
                f"C10_TRACE_CARDINALITY_MISMATCH:{game_id}"
            )
        total_transitions += len(records)
        groups: defaultdict[
            GroupKey,
            list[tuple[int, tuple[object, ...]]],
        ] = defaultdict(list)
        previous_tokens: dict[int, tuple[object, ...]] = {}
        predictive_rows: list[_PredictiveRow] = []
        for index, (record, raw_steps) in enumerate(
            zip(records, emitted_steps, strict=True),
        ):
            ordinal = index + 1
            if record.get("ordinal") != ordinal:
                raise ValueError(
                    f"C10_TRACE_ORDINAL_INVALID:{game_id}:{ordinal}"
                )
            step = _emitted_step(
                raw_steps,
                game_id=game_id,
                ordinal=ordinal,
            )
            group_key = _group_key(step=step, record=record)
            detailed_outcome = _outcome(record)
            groups[group_key].append((ordinal, detailed_outcome))
            previous_context = (
                None
                if not index
                else _runtime_context_token(records[index - 1])
            )
            predictive_rows.append(
                _PredictiveRow(
                    ordinal=ordinal,
                    group_key=group_key,
                    action_class=str(record.get("action_class", "")),
                    previous_context=previous_context,
                    truth=_boundary(
                        record.get("observed_boundary"),
                        "observed",
                    ),
                    detailed_outcome=detailed_outcome,
                )
            )
            if index:
                previous_tokens[ordinal] = _causal_token(
                    records[index - 1]
                )

        game_ambiguous = 0
        game_separable = 0
        game_nonseparable = 0
        ambiguous_keys: set[GroupKey] = set()
        for key, observations in sorted(groups.items()):
            outcomes = {outcome for _ordinal, outcome in observations}
            if len(outcomes) < 2:
                continue
            ambiguous_keys.add(key)
            game_ambiguous += 1
            ambiguous_group_count += 1
            by_token: defaultdict[
                tuple[object, ...],
                set[tuple[object, ...]],
            ] = defaultdict(set)
            missing_previous = False
            for ordinal, outcome in observations:
                token = previous_tokens.get(ordinal)
                if token is None:
                    missing_previous = True
                    continue
                by_token[token].add(outcome)
            separable = (
                not missing_previous
                and len(by_token) >= 2
                and all(len(values) == 1 for values in by_token.values())
            )
            if separable:
                game_separable += 1
                separable_group_count += 1
            else:
                game_nonseparable += 1
                nonseparable_group_count += 1
            group_digest = _group_digest(
                key=key,
                observations=observations,
            )
            all_group_digests.append(group_digest)
            if len(example_rows) < C10_EXAMPLE_LIMIT:
                example_rows.append(
                    {
                        "game_id": game_id,
                        "group_digest": group_digest,
                        "observation_count": len(observations),
                        "distinct_outcome_count": len(outcomes),
                        "distinct_previous_token_count": len(by_token),
                        "one_step_causal_context_separates": separable,
                        "minimum_token_support": (
                            0
                            if not by_token
                            else min(
                                sum(
                                    previous_tokens.get(ordinal) == token
                                    for ordinal, _outcome_value in observations
                                )
                                for token in by_token
                            )
                        ),
                    }
                )

        if game_ambiguous:
            ambiguous_game_count += 1
        if game_separable:
            separable_game_count += 1
        prediction_games.append((game_id, tuple(predictive_rows)))
        prediction = _evaluate_prequential_game(
            rows=predictive_rows,
            ambiguous_keys=frozenset(ambiguous_keys),
        )
        for aggregate, game_stats in (
            (
                aggregate_prediction.all_baseline,
                prediction.all_baseline,
            ),
            (
                aggregate_prediction.all_context,
                prediction.all_context,
            ),
            (
                aggregate_prediction.all_action_only,
                prediction.all_action_only,
            ),
            (
                aggregate_prediction.ambiguous_baseline,
                prediction.ambiguous_baseline,
            ),
            (
                aggregate_prediction.ambiguous_context,
                prediction.ambiguous_context,
            ),
            (
                aggregate_prediction.ambiguous_action_only,
                prediction.ambiguous_action_only,
            ),
        ):
            aggregate.merge(game_stats)
        baseline_ambiguous = prediction.ambiguous_baseline.to_payload()
        context_ambiguous = prediction.ambiguous_context.to_payload()
        action_only_ambiguous = (
            prediction.ambiguous_action_only.to_payload()
        )
        baseline_accuracy = _payload_metric(
            baseline_ambiguous,
            "accuracy_milli",
        )
        context_accuracy = _payload_metric(
            context_ambiguous,
            "accuracy_milli",
        )
        action_only_accuracy = _payload_metric(
            action_only_ambiguous,
            "accuracy_milli",
        )
        if game_ambiguous:
            ambiguous_game_prediction_rows.append(
                {
                    "game_id": game_id,
                    "ambiguous_group_count": game_ambiguous,
                    "ambiguous_transition_count": (
                        prediction.ambiguous_context.total
                    ),
                    "baseline_accuracy_milli": baseline_accuracy,
                    "context_accuracy_milli": context_accuracy,
                    "context_accuracy_delta_milli": (
                        context_accuracy - baseline_accuracy
                    ),
                    "action_only_accuracy_milli": (
                        action_only_accuracy
                    ),
                    "c2_outcome_token_contribution_milli": (
                        context_accuracy - action_only_accuracy
                    ),
                    "context_prediction_count": (
                        prediction.ambiguous_context.source_counts[
                            "CONTEXT"
                        ]
                    ),
                }
            )
        game_rows.append(
            {
                "game_id": game_id,
                "transition_count": len(records),
                "ambiguous_same_frame_action_group_count": game_ambiguous,
                "one_step_separable_group_count": game_separable,
                "nonseparable_group_count": game_nonseparable,
                "prequential_all_transition_baseline": (
                    prediction.all_baseline.to_payload()
                ),
                "prequential_all_transition_context": (
                    prediction.all_context.to_payload()
                ),
                "prequential_ambiguous_baseline": baseline_ambiguous,
                "prequential_ambiguous_context": context_ambiguous,
                "prequential_ambiguous_action_only": (
                    action_only_ambiguous
                ),
            }
        )

    contract_failures = sorted(
        key for key, passed in contract_checks.items() if not passed
    )
    if contract_failures:
        raise ValueError(
            "C10_INPUT_CONTRACT_INVALID:" + ",".join(contract_failures)
        )

    game_rows.sort(key=lambda row: str(row["game_id"]))
    example_rows.sort(
        key=lambda row: (
            str(row["game_id"]),
            str(row["group_digest"]),
        )
    )
    ambiguous_game_prediction_rows.sort(
        key=lambda row: (
            -_payload_metric(
                row,
                "ambiguous_transition_count",
            ),
            str(row["game_id"]),
        )
    )
    cross_game_reopening_evidence = (
        separable_game_count >= C10_MIN_GAME_SUPPORT
        and separable_group_count >= C10_MIN_SEPARABLE_GROUPS
    )
    all_baseline = aggregate_prediction.all_baseline.to_payload()
    all_context = aggregate_prediction.all_context.to_payload()
    all_action_only = (
        aggregate_prediction.all_action_only.to_payload()
    )
    ambiguous_baseline = (
        aggregate_prediction.ambiguous_baseline.to_payload()
    )
    ambiguous_context = (
        aggregate_prediction.ambiguous_context.to_payload()
    )
    ambiguous_action_only = (
        aggregate_prediction.ambiguous_action_only.to_payload()
    )
    all_accuracy_delta = (
        _payload_metric(all_context, "accuracy_milli")
        - _payload_metric(all_baseline, "accuracy_milli")
    )
    ambiguous_accuracy_delta = (
        _payload_metric(ambiguous_context, "accuracy_milli")
        - _payload_metric(ambiguous_baseline, "accuracy_milli")
    )
    c2_outcome_token_contribution = (
        _payload_metric(ambiguous_context, "accuracy_milli")
        - _payload_metric(ambiguous_action_only, "accuracy_milli")
    )
    held_out_mechanism_rows = ambiguous_game_prediction_rows[1:]
    held_out_positive_count = sum(
        _payload_metric(row, "context_accuracy_delta_milli") > 0
        and _payload_metric(row, "context_prediction_count") > 0
        for row in held_out_mechanism_rows
    )
    all_ambiguous_games_improve = bool(
        ambiguous_game_prediction_rows
    ) and all(
        _payload_metric(row, "context_accuracy_delta_milli") > 0
        and _payload_metric(row, "context_prediction_count") > 0
        for row in ambiguous_game_prediction_rows
    )
    loo_baseline_stats, loo_context_stats = (
        _evaluate_leave_one_game_out_outcome_mapping(
            prediction_games
        )
    )
    loo_baseline = loo_baseline_stats.to_payload()
    loo_context = loo_context_stats.to_payload()
    loo_accuracy_delta = (
        _payload_metric(loo_context, "accuracy_milli")
        - _payload_metric(loo_baseline, "accuracy_milli")
    )
    evidence_checks = {
        "same_rendered_frame_and_action_ambiguity_observed": (
            ambiguous_group_count > 0
        ),
        "one_step_visible_effect_context_separates_outcomes": (
            separable_group_count > 0
        ),
        "separation_has_cross_game_support": cross_game_reopening_evidence,
        "audit_did_not_execute_actions": True,
        "audit_did_not_use_timer_counter_or_path_length_as_selector": True,
        "audit_did_not_change_runtime_p": True,
    }
    predictive_checks = {
        "prediction_occurs_before_model_update": True,
        "current_and_future_outcomes_excluded_from_prediction": True,
        "runtime_context_token_identity_free_and_bounded": True,
        "context_prediction_used_on_ambiguous_rows": (
            aggregate_prediction.ambiguous_context.source_counts[
                "CONTEXT"
            ]
            > 0
        ),
        "aggregate_ambiguous_accuracy_delta": (
            ambiguous_accuracy_delta
            >= C10_MIN_AMBIGUOUS_ACCURACY_DELTA_MILLI
        ),
        "all_transition_accuracy_nonregression": (
            all_accuracy_delta >= 0
        ),
        "ambiguous_hazard_recall_improves": (
            _payload_recall(ambiguous_context, "HAZARD")
            > _payload_recall(ambiguous_baseline, "HAZARD")
        ),
        "ambiguous_no_visible_recall_improves": (
            _payload_recall(
                ambiguous_context,
                "NO_VISIBLE_COMMIT",
            )
            > _payload_recall(
                ambiguous_baseline,
                "NO_VISIBLE_COMMIT",
            )
        ),
        "all_ambiguous_games_improve": (
            all_ambiguous_games_improve
        ),
        "held_out_mechanism_game_support": (
            held_out_positive_count
            >= C10_MIN_HELD_OUT_MECHANISM_GAME_SUPPORT
        ),
        "c2_coarse_outcome_token_has_positive_removal_delta": (
            c2_outcome_token_contribution > 0
        ),
        "cross_game_outcome_label_mapping_not_used_for_tier": True,
    }
    cluster_stable = (
        all(evidence_checks.values())
        and all(predictive_checks.values())
    )
    progress_or_commit_support = (
        _payload_metric(
            cast(
                Mapping[str, object],
                ambiguous_context["support_by_boundary"],
            ),
            "COMMIT",
        )
        > 0
    )
    group_inventory_digest = digest_object(sorted(all_group_digests))
    body: dict[str, object] = {
        "schema_version": C10_TEMPORAL_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_c10_temporal_causal_contrast_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_id": C10_CAPABILITY_ID,
        "candidate_tier": (
            "CLUSTER_STABLE" if cluster_stable else "LOCAL_PROBE"
        ),
        "source_evidence": {
            "raw_report_sha256": raw_report_sha256,
            "transition_group_inventory_digest": group_inventory_digest,
        },
        "reopening_contract": {
            "legacy_phase_timer_surface_status": "CLOSED_NEGATIVE",
            "same_surface_retry": "REJECTED",
            "materially_new_observable_variable": (
                "previous visible action prototype plus coarse visible "
                "outcome causal context"
            ),
            "runtime_compilable_context_token": [
                "previous action prototype",
                "previous coarse visible outcome: transition no-change hazard",
            ],
            "prediction_inputs_available_before_current_action": True,
            "model_key_excludes_game_and_level_identity": True,
            "development_partition_rule": (
                "largest ambiguous-transition support is discovery; "
                "remaining ambiguous games are held-out mechanism checks"
            ),
            "forbidden_shortcuts": [
                "task game or level identity",
                "fixed action suffix",
                "path-length parity as an emitter",
                "source or hidden state",
                "replay or answer map",
            ],
        },
        "thresholds": {
            "minimum_separable_game_support": C10_MIN_GAME_SUPPORT,
            "minimum_separable_group_count": C10_MIN_SEPARABLE_GROUPS,
            "minimum_ambiguous_accuracy_delta_milli": (
                C10_MIN_AMBIGUOUS_ACCURACY_DELTA_MILLI
            ),
            "minimum_held_out_mechanism_game_support": (
                C10_MIN_HELD_OUT_MECHANISM_GAME_SUPPORT
            ),
            "example_retention_limit": C10_EXAMPLE_LIMIT,
        },
        "summary": {
            "game_count": len(game_rows),
            "transition_count": total_transitions,
            "ambiguous_game_count": ambiguous_game_count,
            "separable_game_count": separable_game_count,
            "ambiguous_same_frame_action_group_count": (
                ambiguous_group_count
            ),
            "one_step_separable_group_count": separable_group_count,
            "nonseparable_group_count": nonseparable_group_count,
            "retained_example_count": len(example_rows),
            "prequential_all_accuracy_delta_milli": (
                all_accuracy_delta
            ),
            "prequential_ambiguous_accuracy_delta_milli": (
                ambiguous_accuracy_delta
            ),
            "c2_outcome_token_removal_delta_milli": (
                c2_outcome_token_contribution
            ),
            "held_out_mechanism_game_count": len(
                held_out_mechanism_rows
            ),
            "held_out_positive_game_count": held_out_positive_count,
            "leave_one_game_out_outcome_mapping_accuracy_delta_milli": (
                loo_accuracy_delta
            ),
        },
        "contract_checks": contract_checks,
        "evidence_checks": evidence_checks,
        "predictive_checks": predictive_checks,
        "predictive_evaluation": {
            "within_game_prequential": {
                "all_transition_baseline": all_baseline,
                "all_transition_context": all_context,
                "all_transition_action_only": all_action_only,
                "ambiguous_baseline": ambiguous_baseline,
                "ambiguous_context": ambiguous_context,
                "ambiguous_action_only": ambiguous_action_only,
            },
            "mechanism_transfer": {
                "discovery_rows": (
                    ambiguous_game_prediction_rows[:1]
                ),
                "held_out_rows": held_out_mechanism_rows,
            },
            "cross_game_outcome_mapping_negative_control": {
                "baseline": loo_baseline,
                "context": loo_context,
                "accuracy_delta_milli": loo_accuracy_delta,
                "used_for_cluster_tier": False,
                "reason": (
                    "the generic capability learns visible causal dynamics "
                    "inside a session; it does not transfer fixed result labels"
                ),
            },
        },
        "rows": game_rows,
        "examples": example_rows,
        "hds_judgment": {
            "c10_reopen_probe_status": (
                "PASS" if cross_game_reopening_evidence else "HOLD"
            ),
            "local_probe_status": (
                "PASS" if cross_game_reopening_evidence else "HOLD"
            ),
            "cluster_stable_status": (
                "PASS" if cluster_stable else "HOLD"
            ),
            "composable_status": "HOLD",
            "progress_or_commit_separator_status": (
                "LOCAL_PREDICTIVE_PASS"
                if progress_or_commit_support
                else "HOLD"
            ),
            "hazard_separator_status": (
                "LOCAL_PREDICTIVE_PASS"
                if predictive_checks[
                    "ambiguous_hazard_recall_improves"
                ]
                else "HOLD"
            ),
            "cross_game_outcome_mapping_status": (
                "PASS" if loo_accuracy_delta > 0 else "HOLD"
            ),
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "next_bounded_experiment": (
                "compose the bounded context learner with the C2 observer "
                "and run policy intervention plus removal controls before "
                "any Runtime P compile"
                if cluster_stable
                else "repeat non-circular prequential causal-context testing"
                if cross_game_reopening_evidence
                else "retain C10 closed negative until a new separator exists"
            ),
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_c10_temporal_causal_contrast_audit:"
            + digest_object(body)
        ),
    }


def write_c10_temporal_contrast_audit(
    *,
    raw_report_path: Path,
    output_path: Path,
) -> Path:
    value = build_c10_temporal_contrast_audit(
        raw_report=_json_object(raw_report_path),
        raw_report_sha256=_sha256(raw_report_path),
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
        description="Audit the new C10 temporal-causal contrast axis."
    )
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c10_temporal_contrast_audit(
        raw_report_path=args.raw_report,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "C10_TEMPORAL_AUDIT_SCHEMA_VERSION",
    "build_c10_temporal_contrast_audit",
    "write_c10_temporal_contrast_audit",
]
