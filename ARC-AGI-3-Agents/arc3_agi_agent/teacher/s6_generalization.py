"""Measure S5 response stability under deterministic S6 perturbations.

This module is development-only.  It measures how the frozen rendered-only
Runtime P responds to controlled transformations of observations and bounded
history.  It does not execute transformed environments and therefore cannot
claim semantic correctness or generalization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from ..s5_policy import (
    S5_FEATURE_COUNT,
    S5_FRAME_SIDE,
    S5_POINTER_ACTION_ID,
    S5HistoryRecord,
    S5MLPHead,
    S5RenderedPolicyBody,
    load_s5_rendered_policy_body,
    s5_feature_vector_from_render,
)
from ..schema import digest_object
from .s5_policy_compiler import _load_corpus

S6_GENERALIZATION_SCHEMA_VERSION = (
    "arc3-s6-perturbation-measurement-v1"
)
S6_GENERALIZATION_DIGEST_PREFIX = (
    "arc3_s6_perturbation_measurement:"
)
S6_DEFAULT_SAMPLE_SIZE = 2048
S6_REQUIRED_FAMILIES = (
    "COLOR",
    "ROTATION",
    "REFLECTION",
    "LAYOUT",
    "OBJECT_COUNT",
    "ORDER",
    "UNSEEN_COMPOSITION",
)
S6_SELECTION_ALGORITHM = (
    "level-first-last-first-pointer-all-reset-then-"
    "breadth-first-midpoint-round-robin-v1"
)

_COLOR_LUT = np.asarray(
    [(5 * value + 3) % 16 for value in range(16)],
    dtype=np.uint8,
)


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


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_digest", None)
    return body


def load_s6_generalization_report(
    path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("S6_REPORT_INVALID")
    report = dict(value)
    if (
        report.get("content_digest")
        != S6_GENERALIZATION_DIGEST_PREFIX
        + digest_object(_without_digest(report))
    ):
        raise ValueError("S6_REPORT_CONTENT_DIGEST_INVALID")
    if (
        report.get("schema_version")
        != S6_GENERALIZATION_SCHEMA_VERSION
    ):
        raise ValueError("S6_REPORT_SCHEMA_INVALID")
    if require_complete:
        failures: list[str] = []
        if report.get("status") != "COMPLETE":
            failures.append("S6_REPORT_NOT_COMPLETE")
        if report.get("generalization_claim") != "MEASURED_NOT_PROVEN":
            failures.append("S6_GENERALIZATION_CLAIM_INVALID")
        if report.get("semantic_ground_truth_available") is not False:
            failures.append("S6_SEMANTIC_GROUND_TRUTH_FLAG_INVALID")
        if report.get("full_environment_completion_executed") is not False:
            failures.append("S6_ENVIRONMENT_EXECUTION_FLAG_INVALID")
        raw_families = report.get("families")
        if not isinstance(raw_families, Sequence) or isinstance(
            raw_families,
            (str, bytes, bytearray),
        ):
            failures.append("S6_FAMILY_REPORTS_INVALID")
        else:
            family_ids = tuple(
                str(item.get("family_id", ""))
                for item in raw_families
                if isinstance(item, Mapping)
            )
            if family_ids != S6_REQUIRED_FAMILIES:
                failures.append("S6_FAMILY_INVENTORY_INVALID")
        if report.get("exception_count") != 0:
            failures.append("S6_EXCEPTION_COUNT_NONZERO")
        if failures:
            raise ValueError(";".join(sorted(set(failures))))
    return report


def _breadth_first_midpoint_order(
    values: Sequence[int],
) -> tuple[int, ...]:
    if not values:
        return ()
    result: list[int] = []
    intervals: deque[tuple[int, int]] = deque([(0, len(values))])
    while intervals:
        low, high = intervals.popleft()
        if low >= high:
            continue
        middle = (low + high) // 2
        result.append(int(values[middle]))
        intervals.append((low, middle))
        intervals.append((middle + 1, high))
    return tuple(result)


def select_s6_measurement_indices(
    arrays: Mapping[str, np.ndarray],
    *,
    sample_size: int = S6_DEFAULT_SAMPLE_SIZE,
) -> np.ndarray:
    """Select exact, deterministic, level-balanced corpus rows."""

    actions = arrays["actions"]
    ordinals = arrays["game_ordinal"]
    levels = arrays["levels_completed"]
    resets = arrays["level_compatibility_reset"]
    record_count = len(actions)
    if (
        isinstance(sample_size, bool)
        or not isinstance(sample_size, int)
        or sample_size <= 0
        or sample_size > record_count
    ):
        raise ValueError("S6_SAMPLE_SIZE_INVALID")
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index in range(record_count):
        groups[
            (int(ordinals[index]), int(levels[index]))
        ].append(index)
    if not groups:
        raise ValueError("S6_LEVEL_GROUPS_EMPTY")

    selected: set[int] = set()
    for indices in groups.values():
        selected.add(indices[0])
        selected.add(indices[-1])
        pointer = next(
            (
                index
                for index in indices
                if int(actions[index]) == S5_POINTER_ACTION_ID
            ),
            None,
        )
        if pointer is not None:
            selected.add(pointer)
        selected.update(
            index for index in indices if bool(resets[index])
        )
    if len(selected) > sample_size:
        raise ValueError("S6_SAMPLE_SIZE_BELOW_REQUIRED_COVERAGE")

    remaining: dict[tuple[int, int], deque[int]] = {}
    for key in sorted(groups):
        spread = _breadth_first_midpoint_order(groups[key])
        remaining[key] = deque(
            index for index in spread if index not in selected
        )
    while len(selected) < sample_size:
        progressed = False
        for key in sorted(remaining):
            candidates = remaining[key]
            if candidates and len(selected) < sample_size:
                selected.add(candidates.popleft())
                progressed = True
        if not progressed:
            raise RuntimeError("S6_SELECTION_EXHAUSTED")
    return np.asarray(sorted(selected), dtype=np.int64)


def _erase_smallest_component(frame: np.ndarray) -> np.ndarray:
    result = np.array(frame, dtype=np.uint8, copy=True)
    counts = np.bincount(result.ravel(), minlength=16)
    background = int(np.flatnonzero(counts == counts.max())[0])
    visited = np.zeros(result.shape, dtype=bool)
    best_key: tuple[int, int, int, int] | None = None
    best_component: list[tuple[int, int]] = []
    for vertical in range(S5_FRAME_SIDE):
        for horizontal in range(S5_FRAME_SIDE):
            color = int(result[vertical, horizontal])
            if color == background or visited[vertical, horizontal]:
                continue
            pending = [(vertical, horizontal)]
            visited[vertical, horizontal] = True
            component: list[tuple[int, int]] = []
            while pending:
                current_vertical, current_horizontal = pending.pop()
                component.append((current_vertical, current_horizontal))
                for candidate_vertical, candidate_horizontal in (
                    (current_vertical - 1, current_horizontal),
                    (current_vertical + 1, current_horizontal),
                    (current_vertical, current_horizontal - 1),
                    (current_vertical, current_horizontal + 1),
                ):
                    if not (
                        0 <= candidate_vertical < S5_FRAME_SIDE
                        and 0 <= candidate_horizontal < S5_FRAME_SIDE
                    ):
                        continue
                    if visited[
                        candidate_vertical,
                        candidate_horizontal,
                    ]:
                        continue
                    if (
                        int(
                            result[
                                candidate_vertical,
                                candidate_horizontal,
                            ]
                        )
                        != color
                    ):
                        continue
                    visited[
                        candidate_vertical,
                        candidate_horizontal,
                    ] = True
                    pending.append(
                        (candidate_vertical, candidate_horizontal)
                    )
            anchor_vertical, anchor_horizontal = min(component)
            key = (
                len(component),
                color,
                anchor_vertical,
                anchor_horizontal,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_component = component
    for vertical, horizontal in best_component:
        result[vertical, horizontal] = background
    return result


def perturb_s6_frame(frame: np.ndarray, family_id: str) -> np.ndarray:
    matrix = np.asarray(frame, dtype=np.uint8)
    if matrix.shape != (S5_FRAME_SIDE, S5_FRAME_SIDE):
        raise ValueError("S6_FRAME_SHAPE_INVALID")
    if int(matrix.max(initial=0)) >= 16:
        raise ValueError("S6_FRAME_PALETTE_INVALID")
    if family_id == "COLOR":
        return _COLOR_LUT[matrix]
    if family_id == "ROTATION":
        return np.rot90(matrix, 1).copy()
    if family_id == "REFLECTION":
        return np.fliplr(matrix).copy()
    if family_id == "LAYOUT":
        return np.roll(matrix, shift=(3, 5), axis=(0, 1))
    if family_id == "OBJECT_COUNT":
        return _erase_smallest_component(matrix)
    if family_id == "ORDER":
        return np.array(matrix, copy=True)
    if family_id == "UNSEEN_COMPOSITION":
        return np.rot90(_COLOR_LUT[matrix], 1).copy()
    raise ValueError("S6_PERTURBATION_FAMILY_INVALID")


def _transform_pointer(
    horizontal: int,
    vertical: int,
    family_id: str,
) -> tuple[int, int]:
    if family_id in {"ROTATION", "UNSEEN_COMPOSITION"}:
        return vertical, S5_FRAME_SIDE - 1 - horizontal
    if family_id == "REFLECTION":
        return S5_FRAME_SIDE - 1 - horizontal, vertical
    if family_id == "LAYOUT":
        return (
            (horizontal + 5) % S5_FRAME_SIDE,
            (vertical + 3) % S5_FRAME_SIDE,
        )
    return horizontal, vertical


def perturb_s6_history(
    history: tuple[S5HistoryRecord, ...],
    family_id: str,
) -> tuple[S5HistoryRecord, ...]:
    transformed: list[S5HistoryRecord] = []
    for record in history:
        horizontal = record.horizontal
        vertical = record.vertical
        palette = record.target_palette
        if record.action_id == S5_POINTER_ACTION_ID:
            horizontal, vertical = _transform_pointer(
                horizontal,
                vertical,
                family_id,
            )
            if family_id in {"COLOR", "UNSEEN_COMPOSITION"}:
                palette = int(_COLOR_LUT[palette])
        transformed.append(
            replace(
                record,
                horizontal=horizontal,
                vertical=vertical,
                target_palette=palette,
                source_render_digest="",
            )
        )
    if family_id in {"ORDER", "UNSEEN_COMPOSITION"}:
        transformed.reverse()
    return tuple(transformed)


def _histories_for_indices(
    arrays: Mapping[str, np.ndarray],
    selected_indices: np.ndarray,
) -> dict[int, tuple[S5HistoryRecord, ...]]:
    actions = arrays["actions"]
    frames = arrays["frames"]
    ordinals = arrays["game_ordinal"]
    resets = arrays["level_compatibility_reset"]
    targets = arrays["targets"]
    selected = {int(index) for index in selected_indices}
    histories: dict[int, tuple[S5HistoryRecord, ...]] = {}
    history: tuple[S5HistoryRecord, ...] = ()
    for index in range(len(actions)):
        if index == 0 or ordinals[index] != ordinals[index - 1]:
            history = ()
        if index in selected:
            histories[index] = history
        action_id = int(actions[index])
        horizontal = int(targets[index, 0])
        vertical = int(targets[index, 1])
        palette = (
            int(frames[index, vertical, horizontal])
            if action_id == S5_POINTER_ACTION_ID
            else 0
        )
        changed = bool(
            index + 1 < len(actions)
            and ordinals[index + 1] == ordinals[index]
            and np.any(frames[index] != frames[index + 1])
        )
        history = (
            *history,
            S5HistoryRecord(
                action_id=action_id,
                horizontal=horizontal,
                vertical=vertical,
                target_palette=palette,
                visible_change=changed,
                compatibility_reset=bool(resets[index]),
            ),
        )[-16:]
    if len(histories) != len(selected):
        raise RuntimeError("S6_HISTORY_SELECTION_INCOMPLETE")
    return histories


def _feature_matrix(
    arrays: Mapping[str, np.ndarray],
    selected_indices: np.ndarray,
    histories: Mapping[int, tuple[S5HistoryRecord, ...]],
    family_id: str | None,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...], int]:
    features = np.empty(
        (len(selected_indices), S5_FEATURE_COUNT),
        dtype=np.float32,
    )
    surfaces: list[tuple[int, ...]] = []
    transformed_frame_count = 0
    for position, raw_index in enumerate(selected_indices):
        index = int(raw_index)
        original = arrays["frames"][index]
        frame = (
            original
            if family_id is None
            else perturb_s6_frame(original, family_id)
        )
        transformed_frame_count += int(np.any(frame != original))
        surface = tuple(
            int(item)
            for item in np.flatnonzero(arrays["available"][index])
        )
        history = histories[index]
        if family_id is not None:
            history = perturb_s6_history(history, family_id)
        features[position] = s5_feature_vector_from_render(
            frame,
            surface,
            history,
        )
        surfaces.append(surface)
    return features, tuple(surfaces), transformed_frame_count


def _batch_predict_head(
    head: S5MLPHead,
    features: np.ndarray,
) -> np.ndarray:
    failures = head.validate()
    if failures:
        raise ValueError(";".join(failures))
    hidden = np.maximum(features @ head.weight0 + head.bias0, 0.0)
    logits = hidden @ head.weight1 + head.bias1
    classes = np.asarray(head.classes, dtype=np.int64)
    if logits.shape[1] == 1:
        indices = (logits[:, 0] > 0.0).astype(np.int64)
    else:
        indices = np.argmax(logits, axis=1)
    return np.asarray(classes[indices], dtype=np.int64)


def _batch_predict_policy(
    policy: S5RenderedPolicyBody,
    features: np.ndarray,
    surfaces: tuple[tuple[int, ...], ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    actions = np.full(len(features), -1, dtype=np.int64)
    grouped: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index, surface in enumerate(surfaces):
        grouped[surface].append(index)
    unknown_surface_count = 0
    for surface, raw_indices in sorted(grouped.items()):
        head = policy.action_heads.get(surface)
        if head is None:
            unknown_surface_count += len(raw_indices)
            continue
        indices = np.asarray(raw_indices, dtype=np.int64)
        actions[indices] = _batch_predict_head(head, features[indices])
    horizontal = np.full(len(features), -1, dtype=np.int64)
    vertical = np.full(len(features), -1, dtype=np.int64)
    pointer_indices = np.flatnonzero(actions == S5_POINTER_ACTION_ID)
    if len(pointer_indices):
        horizontal[pointer_indices] = _batch_predict_head(
            policy.horizontal_head,
            features[pointer_indices],
        )
        vertical[pointer_indices] = _batch_predict_head(
            policy.vertical_head,
            features[pointer_indices],
        )
    return actions, horizontal, vertical, unknown_surface_count


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 12) if denominator else 0.0


def _family_specification(family_id: str) -> dict[str, object]:
    specifications: dict[str, dict[str, object]] = {
        "COLOR": {
            "observation_transform": "palette[x]=(5*x+3) mod 16",
            "history_transform": "same palette bijection",
            "pointer_proxy_meaningful": True,
        },
        "ROTATION": {
            "observation_transform": "90 degrees counter-clockwise",
            "history_transform": "(x,y)->(y,63-x)",
            "pointer_proxy_meaningful": True,
        },
        "REFLECTION": {
            "observation_transform": "left-right reflection",
            "history_transform": "(x,y)->(63-x,y)",
            "pointer_proxy_meaningful": True,
        },
        "LAYOUT": {
            "observation_transform": "cyclic translation dy=3 dx=5",
            "history_transform": "(x,y)->((x+5)%64,(y+3)%64)",
            "pointer_proxy_meaningful": True,
        },
        "OBJECT_COUNT": {
            "observation_transform": (
                "erase deterministic smallest non-background "
                "four-connected same-color component"
            ),
            "history_transform": "unchanged",
            "pointer_proxy_meaningful": False,
        },
        "ORDER": {
            "observation_transform": "unchanged",
            "history_transform": "reverse bounded history",
            "pointer_proxy_meaningful": True,
        },
        "UNSEEN_COMPOSITION": {
            "observation_transform": (
                "palette bijection then 90 degrees counter-clockwise"
            ),
            "history_transform": (
                "palette bijection plus coordinate rotation plus reversal"
            ),
            "pointer_proxy_meaningful": True,
        },
    }
    try:
        return specifications[family_id]
    except KeyError as error:
        raise ValueError("S6_PERTURBATION_FAMILY_INVALID") from error


def measure_s6_generalization(
    *,
    corpus_path: Path,
    corpus_manifest_path: Path,
    policy_manifest_path: Path | None = None,
    policy_weights_path: Path | None = None,
    sample_size: int = S6_DEFAULT_SAMPLE_SIZE,
) -> dict[str, Any]:
    """Run deterministic static measurements without semantic claims."""

    arrays, corpus_manifest = _load_corpus(
        corpus_path,
        corpus_manifest_path,
    )
    policy = load_s5_rendered_policy_body(
        manifest_path=policy_manifest_path,
        weights_path=policy_weights_path,
    )
    selected_indices = select_s6_measurement_indices(
        arrays,
        sample_size=sample_size,
    )
    histories = _histories_for_indices(arrays, selected_indices)
    baseline_features, surfaces, _ = _feature_matrix(
        arrays,
        selected_indices,
        histories,
        None,
    )
    (
        baseline_actions,
        baseline_horizontal,
        baseline_vertical,
        baseline_unknown_surface_count,
    ) = _batch_predict_policy(policy, baseline_features, surfaces)
    teacher_actions = arrays["actions"][selected_indices].astype(
        np.int64,
        copy=False,
    )
    teacher_targets = arrays["targets"][selected_indices].astype(
        np.int64,
        copy=False,
    )
    pointer_mask = teacher_actions == S5_POINTER_ACTION_ID
    baseline_action_error_count = int(
        np.sum(baseline_actions != teacher_actions)
    )
    baseline_pointer_error_count = int(
        np.sum(
            pointer_mask
            & (
                (baseline_horizontal != teacher_targets[:, 0])
                | (baseline_vertical != teacher_targets[:, 1])
            )
        )
    )
    if (
        baseline_unknown_surface_count
        or baseline_action_error_count
        or baseline_pointer_error_count
    ):
        raise RuntimeError(
            "S6_BASELINE_NOT_CLOSED:"
            f"{baseline_unknown_surface_count}:"
            f"{baseline_action_error_count}:"
            f"{baseline_pointer_error_count}"
        )

    family_reports: list[dict[str, Any]] = []
    exception_count = 0
    for family_id in S6_REQUIRED_FAMILIES:
        features, family_surfaces, transformed_frame_count = (
            _feature_matrix(
                arrays,
                selected_indices,
                histories,
                family_id,
            )
        )
        try:
            (
                predicted_actions,
                predicted_horizontal,
                predicted_vertical,
                unknown_surface_count,
            ) = _batch_predict_policy(
                policy,
                features,
                family_surfaces,
            )
        except (TypeError, ValueError) as error:
            exception_count += sample_size
            family_reports.append(
                {
                    "family_id": family_id,
                    "measurement_count": sample_size,
                    "exception_count": sample_size,
                    "exception_signature": type(error).__name__,
                    **_family_specification(family_id),
                }
            )
            continue
        retained = predicted_actions == teacher_actions
        retention_count = int(np.sum(retained))
        unavailable_count = sum(
            int(
                action_id != 0
                and action_id not in family_surfaces[position]
            )
            for position, action_id in enumerate(predicted_actions)
            if action_id >= 0
        )
        specification = _family_specification(family_id)
        pointer_proxy_meaningful = bool(
            specification["pointer_proxy_meaningful"]
        )
        pointer_report: dict[str, object]
        if pointer_proxy_meaningful:
            expected_horizontal = np.array(
                teacher_targets[:, 0],
                dtype=np.int64,
                copy=True,
            )
            expected_vertical = np.array(
                teacher_targets[:, 1],
                dtype=np.int64,
                copy=True,
            )
            for position in np.flatnonzero(pointer_mask):
                (
                    expected_horizontal[position],
                    expected_vertical[position],
                ) = _transform_pointer(
                    int(teacher_targets[position, 0]),
                    int(teacher_targets[position, 1]),
                    family_id,
                )
            pointer_retention_count = int(
                np.sum(
                    pointer_mask
                    & (predicted_actions == S5_POINTER_ACTION_ID)
                    & (predicted_horizontal == expected_horizontal)
                    & (predicted_vertical == expected_vertical)
                )
            )
            pointer_count = int(np.sum(pointer_mask))
            pointer_report = {
                "status": "MEASURED_RESPONSE_EQUIVARIANCE_PROXY",
                "measurement_count": pointer_count,
                "retention_count": pointer_retention_count,
                "retention_rate": _rate(
                    pointer_retention_count,
                    pointer_count,
                ),
            }
        else:
            pointer_report = {
                "status": "NOT_MEANINGFUL_FOR_OBJECT_REMOVAL",
                "measurement_count": 0,
                "retention_count": 0,
                "retention_rate": None,
            }
        family_reports.append(
            {
                "family_id": family_id,
                "measurement_count": sample_size,
                "transformed_frame_count": transformed_frame_count,
                "teacher_action_retention_count": retention_count,
                "teacher_action_retention_rate": _rate(
                    retention_count,
                    sample_size,
                ),
                "response_change_count": sample_size - retention_count,
                "unknown_action_surface_count": unknown_surface_count,
                "predicted_unavailable_action_count": unavailable_count,
                "exception_count": 0,
                "pointer_proxy": pointer_report,
                "semantic_correctness": "NOT_AVAILABLE",
                **specification,
            }
        )
        print(
            json.dumps(
                {
                    "event": "S6_PERTURBATION_MEASURED",
                    "family_id": family_id,
                    "measurement_count": sample_size,
                    "teacher_action_retention_count": retention_count,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    covered_pairs = {
        (
            int(arrays["game_ordinal"][index]),
            int(arrays["levels_completed"][index]),
        )
        for index in selected_indices
    }
    covered_games = {
        int(arrays["game_ordinal"][index])
        for index in selected_indices
    }
    selection_body = {
        "algorithm": S6_SELECTION_ALGORITHM,
        "source_corpus_sha256": corpus_manifest.get("corpus_sha256"),
        "selected_record_indices": [
            int(index) for index in selected_indices
        ],
    }
    total_measurement_count = sample_size * len(S6_REQUIRED_FAMILIES)
    body: dict[str, Any] = {
        "schema_version": S6_GENERALIZATION_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R6-GENERALIZATION-MEASUREMENT",
        "status": "COMPLETE" if exception_count == 0 else "INCOMPLETE",
        "source_training_corpus_digest": corpus_manifest.get(
            "content_digest"
        ),
        "source_training_corpus_sha256": corpus_manifest.get(
            "corpus_sha256"
        ),
        "source_record_count": len(arrays["actions"]),
        "source_runtime_policy_digest": policy.digest(),
        "source_runtime_weights_sha256": policy._weights_sha256,
        "selection_algorithm": S6_SELECTION_ALGORITHM,
        "selection_digest": (
            "sha256:" + hashlib.sha256(
                json.dumps(
                    selection_body,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        ),
        "selected_record_count": sample_size,
        "selected_record_indices": [
            int(index) for index in selected_indices
        ],
        "covered_game_count": len(covered_games),
        "covered_level_count": len(covered_pairs),
        "required_family_count": len(S6_REQUIRED_FAMILIES),
        "measured_family_count": len(family_reports),
        "total_measurement_count": total_measurement_count,
        "baseline_policy_action_error_count": (
            baseline_action_error_count
        ),
        "baseline_policy_pointer_error_count": (
            baseline_pointer_error_count
        ),
        "baseline_unknown_action_surface_count": (
            baseline_unknown_surface_count
        ),
        "exception_count": exception_count,
        "families": family_reports,
        "full_environment_completion_executed": False,
        "semantic_ground_truth_available": False,
        "measurement_interpretation": (
            "Action retention compares the perturbed Runtime P response "
            "with the original Teacher label. It is a response-stability "
            "proxy, not transformed-environment correctness."
        ),
        "generalization_claim": "MEASURED_NOT_PROVEN",
        "hds_decision": "S6_MEASURED_HOLD_GENERALIZATION_CLAIM",
        "next_stage": "P11_RELEASE_STATE",
    }
    return {
        **body,
        "content_digest": (
            S6_GENERALIZATION_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure S5 response stability under fixed S6 perturbations."
        )
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--policy-manifest", type=Path)
    parser.add_argument("--policy-weights", type=Path)
    parser.add_argument(
        "--sample-size",
        type=int,
        default=S6_DEFAULT_SAMPLE_SIZE,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = measure_s6_generalization(
        corpus_path=args.corpus,
        corpus_manifest_path=args.corpus_manifest,
        policy_manifest_path=args.policy_manifest,
        policy_weights_path=args.policy_weights,
        sample_size=args.sample_size,
    )
    _write_json(args.output, report)
    load_s6_generalization_report(args.output)
    print(
        json.dumps(
            {
                "content_digest": report["content_digest"],
                "covered_game_count": report["covered_game_count"],
                "covered_level_count": report["covered_level_count"],
                "generalization_claim": report[
                    "generalization_claim"
                ],
                "selected_record_count": report[
                    "selected_record_count"
                ],
                "status": report["status"],
                "total_measurement_count": report[
                    "total_measurement_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S6_DEFAULT_SAMPLE_SIZE",
    "S6_GENERALIZATION_DIGEST_PREFIX",
    "S6_GENERALIZATION_SCHEMA_VERSION",
    "S6_REQUIRED_FAMILIES",
    "load_s6_generalization_report",
    "measure_s6_generalization",
    "perturb_s6_frame",
    "perturb_s6_history",
    "select_s6_measurement_indices",
]
