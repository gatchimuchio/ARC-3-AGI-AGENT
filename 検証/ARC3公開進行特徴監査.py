from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ACTION_CATEGORIES = tuple([f"ACTION{i}" for i in range(1, 8)] + ["RESET", "OTHER"])
VISUAL_FEATURE_NAMES = (
    "distinct_value_count",
    *(f"ranked_value_frequency_{i}" for i in range(1, 9)),
    "value_entropy_bits",
    "active_row_fraction",
    "active_column_fraction",
    "horizontal_inequality_fraction",
    "vertical_inequality_fraction",
)


def board_features(board: Any) -> np.ndarray:
    """Return color-renaming-invariant statistics from one visible board."""
    array = np.asarray(board)
    if array.ndim != 2 or array.size == 0 or not np.issubdtype(array.dtype, np.number):
        raise ValueError("board must be a nonempty numeric 2D public frame")
    if not np.all(np.isfinite(array)):
        raise ValueError("board contains a non-finite value")

    values, counts = np.unique(array, return_counts=True)
    frequencies = np.sort(counts.astype(np.float64) / array.size)[::-1]
    ranked = np.pad(frequencies[:8], (0, max(0, 8 - len(frequencies[:8]))))
    probabilities = counts / array.size
    entropy = float(-(probabilities * np.log2(probabilities)).sum())
    modal_values = values[counts == counts.max()]
    nonmodal = ~np.isin(array, modal_values)
    active_rows = float(np.any(nonmodal, axis=1).mean())
    active_columns = float(np.any(nonmodal, axis=0).mean())
    horizontal_inequality = (
        float(np.not_equal(array[:, 1:], array[:, :-1]).mean()) if array.shape[1] > 1 else 0.0
    )
    vertical_inequality = (
        float(np.not_equal(array[1:, :], array[:-1, :]).mean()) if array.shape[0] > 1 else 0.0
    )
    return np.asarray(
        [
            len(values),
            *ranked.tolist(),
            entropy,
            active_rows,
            active_columns,
            horizontal_inequality,
            vertical_inequality,
        ],
        dtype=np.float64,
    )


def action_features(action_name: Any) -> np.ndarray:
    """Encode only the generic action category; ignore display text/arguments."""
    name = action_name.strip().upper() if isinstance(action_name, str) else ""
    category = name if name in ACTION_CATEGORIES[:-1] else "OTHER"
    return np.asarray([float(category == item) for item in ACTION_CATEGORIES], dtype=np.float64)


def rows_from_events(rows: list[dict[str, Any]], group: int) -> list[dict[str, Any]]:
    """Build pre-action features and public level-transition labels for one run."""
    initial = [row for row in rows if row.get("type") == "initial"]
    if len(initial) != 1:
        raise ValueError("each event stream must have one initial observation")
    previous_board = initial[0].get("board")
    previous_level = initial[0].get("level")
    if type(previous_level) is not int or previous_level < 1:
        raise ValueError("initial public level is missing or invalid")

    examples: list[dict[str, Any]] = []
    for row in rows:
        if row.get("type") != "action":
            continue
        current_level = row.get("level")
        current_board = row.get("board")
        if type(current_level) is not int or current_level < 1:
            raise ValueError("post-action public level is missing or invalid")
        if current_level > previous_level + 1:
            raise ValueError(
                "public level jumped by more than one; refusing to infer skipped transitions"
            )
        examples.append(
            {
                "visual": board_features(previous_board),
                "action": action_features(row.get("action_name")),
                "advanced": int(current_level > previous_level),
                "group": group,
            }
        )
        previous_board = current_board
        previous_level = current_level
    return examples


def grouped_folds(groups: np.ndarray, labels: np.ndarray, n_splits: int, seed: int):
    """Create deterministic, roughly outcome-stratified folds with whole runs held out."""
    unique_groups = np.unique(groups)
    if len(unique_groups) < n_splits:
        raise ValueError("fewer run groups than folds")
    rng = np.random.default_rng(seed)
    tie_break = {int(group): float(rng.random()) for group in unique_groups}
    stats = []
    for group in unique_groups:
        mask = groups == group
        stats.append((int(group), int(labels[mask].sum()), int(mask.sum())))
    stats.sort(key=lambda item: (-item[1], -item[2], tie_break[item[0]]))

    fold_groups: list[list[int]] = [[] for _ in range(n_splits)]
    fold_positive = [0] * n_splits
    fold_size = [0] * n_splits
    for group, positive_count, sample_count in stats:
        selected = min(
            range(n_splits),
            key=lambda index: (
                fold_positive[index],
                fold_size[index],
                len(fold_groups[index]),
                index,
            ),
        )
        fold_groups[selected].append(group)
        fold_positive[selected] += positive_count
        fold_size[selected] += sample_count

    folds = []
    for held_groups in fold_groups:
        test_mask = np.isin(groups, held_groups)
        train_mask = ~test_mask
        if np.intersect1d(groups[train_mask], groups[test_mask]).size:
            raise AssertionError("run group leaked across fold")
        if labels[test_mask].sum() == 0:
            raise ValueError("held-out fold has no positive level transition")
        folds.append((train_mask, test_mask))
    return folds


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def fit_logistic_predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    alpha: float = 0.1,
    max_iterations: int = 100,
) -> np.ndarray:
    """Fit one fixed L2 logistic model; standardization is train-fold-only."""
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    train_scaled = (train_x - mean) / scale
    test_scaled = (test_x - mean) / scale
    design = np.column_stack((np.ones(len(train_scaled)), train_scaled))
    test_design = np.column_stack((np.ones(len(test_scaled)), test_scaled))
    beta = np.zeros(design.shape[1], dtype=np.float64)
    penalty = np.eye(design.shape[1], dtype=np.float64) * alpha
    penalty[0, 0] = 0.0
    count = max(1, len(train_y))

    for _ in range(max_iterations):
        probabilities = _sigmoid(design @ beta)
        weights = np.maximum(probabilities * (1.0 - probabilities), 1e-9)
        gradient = design.T @ (probabilities - train_y) / count + penalty @ beta
        hessian = (design.T * weights) @ design / count + penalty
        hessian.flat[:: hessian.shape[0] + 1] += 1e-9
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return _sigmoid(test_design @ beta)


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    """Compute non-interpolated AP with tied scores handled as one threshold."""
    positive_total = int(labels.sum())
    if positive_total == 0:
        return float("nan")
    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    true_positive = 0
    seen = 0
    area = 0.0
    index = 0
    while index < len(order):
        stop = index + 1
        while stop < len(order) and sorted_scores[stop] == sorted_scores[index]:
            stop += 1
        positives = int(sorted_labels[index:stop].sum())
        true_positive += positives
        seen += stop - index
        area += (positives / positive_total) * (true_positive / seen)
        index = stop
    return float(area)


def score_predictions(labels: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    return {
        "pr_auc": average_precision(labels, scores),
        "brier": float(np.mean((labels - scores) ** 2)),
    }


def evaluate(input_root: Path, reference_path: Path, seed: int = 20261024) -> dict[str, Any]:
    artifact_root = input_root / "artifacts"
    event_files = sorted(artifact_root.glob("*_events.jsonl"))
    if len(event_files) != 25:
        raise ValueError(f"expected 25 saved public event streams, got {len(event_files)}")

    prompt_path = input_root / "prompts" / "prompt.log"
    prompt_text = prompt_path.read_text(encoding="utf-8", errors="replace")
    if "current_frame" not in prompt_text or ".level" not in prompt_text:
        raise ValueError("saved model prompt does not establish public current_frame.level access")

    examples: list[dict[str, Any]] = []
    for group, path in enumerate(event_files):
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        examples.extend(rows_from_events(rows, group))

    labels = np.asarray([row["advanced"] for row in examples], dtype=np.int64)
    groups = np.asarray([row["group"] for row in examples], dtype=np.int64)
    visual = np.vstack([row["visual"] for row in examples])
    action = np.vstack([row["action"] for row in examples])
    combined = np.column_stack((visual, action))
    folds = grouped_folds(groups, labels, n_splits=5, seed=seed)

    matrices = {
        "action_only": action,
        "visual_only": visual,
        "action_visual": combined,
    }
    oof: dict[str, np.ndarray] = {
        "base_rate": np.zeros(len(labels), dtype=np.float64),
        **{name: np.zeros(len(labels), dtype=np.float64) for name in matrices},
    }
    fold_metrics: dict[str, list[dict[str, float]]] = {name: [] for name in oof}
    for train_mask, test_mask in folds:
        train_y = labels[train_mask]
        test_y = labels[test_mask]
        base_rate = float(train_y.mean())
        oof["base_rate"][test_mask] = base_rate
        fold_metrics["base_rate"].append(
            score_predictions(test_y, np.full(test_mask.sum(), base_rate, dtype=np.float64))
        )
        for name, matrix in matrices.items():
            predictions = fit_logistic_predict(matrix[train_mask], train_y, matrix[test_mask])
            oof[name][test_mask] = predictions
            fold_metrics[name].append(score_predictions(test_y, predictions))

    overall = {name: score_predictions(labels, predictions) for name, predictions in oof.items()}
    joint_fold_wins = sum(
        visual_metrics["pr_auc"] > action_metrics["pr_auc"]
        and visual_metrics["brier"] < action_metrics["brier"]
        for visual_metrics, action_metrics in zip(
            fold_metrics["action_visual"], fold_metrics["action_only"], strict=True
        )
    )
    improves_base = (
        overall["action_visual"]["pr_auc"] > overall["base_rate"]["pr_auc"]
        and overall["action_visual"]["brier"] < overall["base_rate"]["brier"]
    )
    improves_action = (
        overall["action_visual"]["pr_auc"] > overall["action_only"]["pr_auc"]
        and overall["action_visual"]["brier"] < overall["action_only"]["brier"]
    )
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_totals = reference["totals"]
    action_count = len(examples)
    positive_count = int(labels.sum())
    if (
        action_count != reference_totals["actions"]
        or positive_count != reference_totals["level_advance_events"]
    ):
        raise AssertionError("current public event extraction disagrees with C1-019 aggregate")

    def file_sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    notebook_path = Path("出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb")
    expected_notebook_sha = "5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc"
    notebook_sha = file_sha(notebook_path)
    if notebook_sha != expected_notebook_sha:
        raise AssertionError("saved v5 Notebook identity differs from the reviewed candidate")
    return {
        "task_id": "ARC3-RUN-003-C1-020",
        "scope": {
            "public_runs": len(event_files),
            "action_responses": action_count,
            "positive_public_level_transitions": positive_count,
            "grouped_folds": len(folds),
            "split_seed": seed,
            "group_names_retained": False,
            "trajectory_replayed": False,
        },
        "feature_policy": {
            "visual_feature_count": len(VISUAL_FEATURE_NAMES),
            "visual_features": list(VISUAL_FEATURE_NAMES),
            "action_categories": len(ACTION_CATEGORIES),
            "color_label_invariant": True,
            "pre_action_board_only": True,
            "absolute_level_excluded": True,
            "coordinates_and_display_excluded": True,
        },
        "positive_rate": positive_count / action_count if action_count else None,
        "oof_metrics": overall,
        "delta_action_visual_vs_base_rate": {
            metric: overall["action_visual"][metric] - overall["base_rate"][metric]
            for metric in ("pr_auc", "brier")
        },
        "delta_action_visual_vs_action_only": {
            metric: overall["action_visual"][metric] - overall["action_only"][metric]
            for metric in ("pr_auc", "brier")
        },
        "folds_where_action_visual_beats_action_only_on_both": int(joint_fold_wins),
        "visual_signal_supported": bool(improves_base and improves_action and joint_fold_wins >= 4),
        "cross_checks": {
            "action_count_matches_C1_019": True,
            "public_level_transitions_match_C1_019": True,
            "same_run_never_crosses_fold": True,
            "no_zero_positive_heldout_fold": True,
        },
        "limitations": [
            "Grouped prediction is observational; it does not establish a causal action improvement.",
            "The 47 positive transitions are sparse and come from one saved model/prompt run per public environment.",
            "Only this fixed generic feature set and regularization were evaluated; no post-result tuning was performed.",
            "No predictions or per-run observations are retained in the aggregate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit generic public visual features for held-out level progress."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5"),
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("出力/ARC3-RUN-003-local/C1-019-model-v5-depth-audit.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("出力/ARC3-RUN-003-local/C1-020-public-progress-features.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    result = evaluate(args.input_root, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
