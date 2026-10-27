"""直前の公開Frame要約を条件へ加えたHDS shadow予測のdev-only評価。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402
from ARC3複数Frame公開観測診断 import _transition_metrics  # noqa: E402
from arc_agi import LocalEnvironmentWrapper  # noqa: E402
from hds学習系統 import HDS学習系統, 外部入力  # noqa: E402

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C1-006-frame-shadow-dev-summary.json"
境界 = "ARC-AGI-3公開Action応答"
結果経路群 = {
    "可視変化あり": ("結果", "可視変化あり"),
    "level進行あり": ("結果", "level進行あり"),
    "新規盤面あり": ("結果", "新規盤面あり"),
}
_POLICY_SEEDS = (7, 31, 73)
_ENVIRONMENT_SEED = 31
_TRAIN_FRACTION = 0.75
_FRAME_KEYS = ("直前複数Frame", "直前中間Grid差分", "直前一時Cell差分")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame_features(metrics: dict[str, int]) -> dict[str, bool] | None:
    if metrics["uncomparable_transitions"]:
        return None
    return {
        "直前複数Frame": metrics["multi_frame_responses"] > 0,
        "直前中間Grid差分": metrics["intermediate_grids_different_from_final"] > 0,
        "直前一時Cell差分": metrics["transient_cells_returning_to_prior_value"] > 0,
    }


def _samples_from_trace(
    responses: list[dict[str, Any]], frame_metrics: list[dict[str, int]]
) -> list[dict[str, Any]]:
    if len(responses) != len(frame_metrics):
        raise ValueError("captured Frame metric count differs from response count")
    samples = []
    previous_features: dict[str, bool] | None = None
    for response, metrics in zip(responses, frame_metrics, strict=True):
        current_features = _frame_features(metrics)
        action_id = response.get("action_id")
        if response.get("lifecycle_action") or action_id == 0:
            previous_features = current_features
            continue
        if type(action_id) is int and 1 <= action_id <= 7 and previous_features is not None:
            samples.append(
                {
                    "action_id": action_id,
                    "changed_cells": int(response["changed_cells"]),
                    "level_delta": int(response["level_delta"]),
                    "new_visible_board": bool(response["new_visible_board"]),
                    "previous_frame_features": previous_features,
                }
            )
        previous_features = current_features
    return samples


def _input(
    sample: dict[str, Any], *, include_frame_features: bool, include_result: bool
) -> 外部入力:
    conditions: dict[str, Any] = {"Action番号": sample["action_id"]}
    if include_frame_features:
        conditions.update(sample["previous_frame_features"])
    content: dict[str, Any] = {"条件": conditions}
    if include_result:
        content["結果"] = {
            "可視変化あり": sample["changed_cells"] > 0,
            "level進行あり": sample["level_delta"] > 0,
            "新規盤面あり": sample["new_visible_board"],
        }
    return 外部入力(内容=content, 対象系境界=境界)


def _result_value(sample: dict[str, Any], target: str) -> bool:
    return {
        "可視変化あり": sample["changed_cells"] > 0,
        "level進行あり": sample["level_delta"] > 0,
        "新規盤面あり": sample["new_visible_board"],
    }[target]


def _prediction(result: Any, path: tuple[str, ...]) -> bool | None:
    predictions = {
        item["予測値"]
        for item in result.内容.get("予測群", [])
        if tuple(item.get("結果経路", ())) == path
    }
    if len(predictions) != 1:
        return None
    value = next(iter(predictions))
    return value if type(value) is bool else None


def _majority(samples: list[dict[str, Any]], target: str, action_id: int) -> bool | None:
    counts = Counter(
        _result_value(sample, target) for sample in samples if sample["action_id"] == action_id
    )
    if not counts or (len(counts) > 1 and len(set(counts.values())) == 1):
        return None
    return counts.most_common(1)[0][0]


def _empty_target_metrics() -> dict[str, int]:
    return {
        "照会件数": 0,
        "Action多数派適用": 0,
        "Action多数派正答": 0,
        "ActionOnlyHDS単一予測": 0,
        "ActionOnlyHDS正答": 0,
        "FrameHDS単一予測": 0,
        "FrameHDS正答": 0,
        "matchedCoverage": 0,
        "matchedActionOnlyHDS正答": 0,
        "matchedFrameHDS正答": 0,
        "matchedAction多数派適用": 0,
        "matchedAction多数派正答": 0,
        "FrameHDSがAction多数派誤りを正答": 0,
    }


def _evaluate_samples(
    samples: list[dict[str, Any]], *, train_fraction: float = _TRAIN_FRACTION
) -> dict[str, Any]:
    if not 0.5 <= train_fraction < 1.0:
        raise ValueError("train_fraction must be in [0.5, 1.0)")
    if len(samples) < 2:
        raise ValueError("at least two eligible samples are required")
    split = max(1, min(len(samples) - 1, int(len(samples) * train_fraction)))
    training, heldout = samples[:split], samples[split:]
    models = {
        "ActionOnly": (HDS学習系統(), False),
        "Frame条件": (HDS学習系統(), True),
    }
    for model, include_frame in models.values():
        for sample in training:
            model.処理する(
                _input(sample, include_frame_features=include_frame, include_result=True)
            )

    metrics = {target: _empty_target_metrics() for target in 結果経路群}
    for sample in heldout:
        results = {
            name: model.照会する(
                _input(sample, include_frame_features=include_frame, include_result=False)
            )
            for name, (model, include_frame) in models.items()
        }
        for target, path in 結果経路群.items():
            row = metrics[target]
            actual = _result_value(sample, target)
            row["照会件数"] += 1
            majority = _majority(training, target, sample["action_id"])
            if majority is not None:
                row["Action多数派適用"] += 1
                row["Action多数派正答"] += int(majority == actual)
            predictions = {name: _prediction(result, path) for name, result in results.items()}
            for name, label in (
                ("ActionOnly", "ActionOnlyHDS"),
                ("Frame条件", "FrameHDS"),
            ):
                predicted = predictions[name]
                if predicted is not None:
                    row[f"{label}単一予測"] += 1
                    row[f"{label}正答"] += int(predicted == actual)
            action_only = predictions["ActionOnly"]
            frame_prediction = predictions["Frame条件"]
            if action_only is not None and frame_prediction is not None:
                row["matchedCoverage"] += 1
                row["matchedActionOnlyHDS正答"] += int(action_only == actual)
                row["matchedFrameHDS正答"] += int(frame_prediction == actual)
                if majority is not None:
                    row["matchedAction多数派適用"] += 1
                    row["matchedAction多数派正答"] += int(majority == actual)
            if majority is not None and majority != actual and frame_prediction is not None:
                row["FrameHDSがAction多数派誤りを正答"] += int(frame_prediction == actual)

    return {
        "適格サンプル": len(samples),
        "学習件数": len(training),
        "後半照会件数": len(heldout),
        "結果": metrics,
    }


def _capture_game(
    metadata: dict[str, Any], metadata_path: Path, *, policy_seed: int
) -> tuple[dict[str, Any], list[dict[str, int]]]:
    captured: list[dict[str, int]] = []
    original_step = LocalEnvironmentWrapper.step

    def instrumented_step(self, action, data=None, reasoning=None):
        before = getattr(self, "observation_space", None)
        response = original_step(self, action, data=data, reasoning=reasoning)
        captured.append(_transition_metrics(before, response))
        return response

    with patch.object(LocalEnvironmentWrapper, "step", instrumented_step):
        result = runner._run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=_ENVIRONMENT_SEED,
            policy_seed=policy_seed,
            max_actions=80,
            retry_game_over=True,
        )
    if len(captured) != result["actions"]:
        raise RuntimeError("captured response count differs from evaluator action count")
    return result, captured


def run_evaluation(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite experiment output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    by_policy_seed: dict[str, Any] = {}
    for seed in _POLICY_SEEDS:
        by_policy_seed[str(seed)] = {
            "環境数": 0,
            "公開開始状態一致数": 0,
            "適格サンプル": 0,
            "学習件数": 0,
            "後半照会件数": 0,
            "結果": {target: _empty_target_metrics() for target in 結果経路群},
        }

    all_starts_match = True
    for metadata, metadata_path in development:
        reference_start = None
        for policy_seed in _POLICY_SEEDS:
            game, frame_metrics = _capture_game(metadata, metadata_path, policy_seed=policy_seed)
            start = (
                game["initial_state"],
                game["initial_levels_completed"],
                tuple(game["initial_available_actions"]),
                game["initial_board"],
            )
            if reference_start is None:
                reference_start = start
                same_start = True
            else:
                same_start = start == reference_start
            all_starts_match = all_starts_match and same_start
            samples = _samples_from_trace(game["action_responses"], frame_metrics)
            run_result = _evaluate_samples(samples)
            aggregate = by_policy_seed[str(policy_seed)]
            aggregate["環境数"] += 1
            aggregate["公開開始状態一致数"] += int(same_start)
            for key in ("適格サンプル", "学習件数", "後半照会件数"):
                aggregate[key] += run_result[key]
            for target, fields in run_result["結果"].items():
                for field, value in fields.items():
                    aggregate["結果"][target][field] += value

    hds_source = ROOT / "HDS/学習系統/v0.4.2/hds学習系統"
    result = {
        "評価": "直前公開Frame特徴を使ったHDS shadow予測",
        "範囲": "固定dev split先頭5公開環境、environment seed 31、policy seed 7/31/73、各80要求",
        "splitSeed": 20261022,
        "trainFraction": _TRAIN_FRACTION,
        "environmentCount": len(games),
        "developmentEnvironmentCount": len(development),
        "allPublicStartsMatch": all_starts_match,
        "byPolicySeed": by_policy_seed,
        "features": {
            "ActionOnlyHDS": ["条件.Action番号"],
            "FrameHDS追加条件": [f"条件.{key}" for key in _FRAME_KEYS],
            "targets": [f"結果.{key}" for key in 結果経路群],
        },
        "exclusion": [
            "RESET result",
            "game_id",
            "level_id",
            "GUID",
            "observation fingerprint",
            "raw board/frame",
            "coordinates",
            "color values",
            "trajectory",
            "same-response frame features",
        ],
        "source_sha256": {
            "shadow_runner": _sha256(Path(__file__)),
            "evaluation_runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "frame_diagnostic": _sha256(ROOT / "検証/ARC3複数Frame公開観測診断.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
            "hds_python_sources": {
                path.name: _sha256(path) for path in sorted(hds_source.glob("*.py"))
            },
        },
        "interpretation_boundary": (
            "fixed public development split only; sequential within-environment prediction; "
            "no causal, cross-game transfer, or official-score claim"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    output.write_bytes(raw)
    result["output_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_evaluation(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
