"""C1-006で固定したFrame特徴のleave-one-environment-out dev評価。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from hds学習系統 import HDS学習系統

from 検証 import ARC3Frame特徴公開遷移shadow評価 as shadow

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C1-008-frame-cross-game-dev-summary.json"
_TARGETS = shadow.結果経路群
_POLICY_SEEDS = shadow._POLICY_SEEDS
_MAX_TRAINING_SAMPLES_PER_ENVIRONMENT = 15


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_content_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()
    return len(hashes), digest


def _leave_one_environment_out(
    samples_by_environment: list[list[dict[str, Any]]],
) -> list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    if len(samples_by_environment) < 2:
        raise ValueError("at least two environments are required")
    folds = []
    for heldout_index, heldout in enumerate(samples_by_environment):
        training = [
            sample
            for index, environment_samples in enumerate(samples_by_environment)
            if index != heldout_index
            for sample in _evenly_spaced(environment_samples, _MAX_TRAINING_SAMPLES_PER_ENVIRONMENT)
        ]
        folds.append((training, heldout))
    return folds


def _evenly_spaced(samples: list[dict[str, Any]], maximum: int) -> list[dict[str, Any]]:
    if len(samples) <= maximum:
        return list(samples)
    if maximum < 2:
        raise ValueError("maximum must be at least two when sampling")
    last = len(samples) - 1
    indices = [round(index * last / (maximum - 1)) for index in range(maximum)]
    return [samples[index] for index in indices]


def _empty_target_metrics() -> dict[str, int]:
    return {
        "照会件数": 0,
        "Action多数派適用": 0,
        "Action多数派正答": 0,
        "ActionOnlyHDS単一予測": 0,
        "ActionOnlyHDS正答": 0,
        "FrameHDS単一予測": 0,
        "FrameHDS正答": 0,
        "共通coverage": 0,
        "共通ActionOnlyHDS正答": 0,
        "共通FrameHDS正答": 0,
        "共通Action多数派正答": 0,
        "FrameHDSが多数派誤りを正答": 0,
    }


def _evaluate_fold(training: list[dict[str, Any]], heldout: list[dict[str, Any]]) -> dict[str, Any]:
    if not training or not heldout:
        raise ValueError("training and heldout samples must both be non-empty")
    models = {
        "ActionOnly": (HDS学習系統(), False),
        "Frame条件": (HDS学習系統(), True),
    }
    for model, include_frames in models.values():
        for sample in training:
            model.処理する(
                shadow._input(
                    sample,
                    include_frame_features=include_frames,
                    include_result=True,
                )
            )

    metrics = {target: _empty_target_metrics() for target in _TARGETS}
    for sample in heldout:
        predictions = {}
        for name, (model, include_frames) in models.items():
            result = model.照会する(
                shadow._input(
                    sample,
                    include_frame_features=include_frames,
                    include_result=False,
                )
            )
            predictions[name] = {
                target: shadow._prediction(result, path) for target, path in _TARGETS.items()
            }
        for target in _TARGETS:
            row = metrics[target]
            actual = shadow._result_value(sample, target)
            majority = shadow._majority(training, target, sample["action_id"])
            action_only = predictions["ActionOnly"][target]
            frame_prediction = predictions["Frame条件"][target]
            row["照会件数"] += 1
            if majority is not None:
                row["Action多数派適用"] += 1
                row["Action多数派正答"] += int(majority == actual)
            for prediction, coverage_key, correct_key in (
                (action_only, "ActionOnlyHDS単一予測", "ActionOnlyHDS正答"),
                (frame_prediction, "FrameHDS単一予測", "FrameHDS正答"),
            ):
                if prediction is not None:
                    row[coverage_key] += 1
                    row[correct_key] += int(prediction == actual)
            if majority is not None and action_only is not None and frame_prediction is not None:
                row["共通coverage"] += 1
                row["共通ActionOnlyHDS正答"] += int(action_only == actual)
                row["共通FrameHDS正答"] += int(frame_prediction == actual)
                row["共通Action多数派正答"] += int(majority == actual)
            if majority is not None and majority != actual and frame_prediction is not None:
                row["FrameHDSが多数派誤りを正答"] += int(frame_prediction == actual)
    return {"学習件数": len(training), "照会件数": len(heldout), "結果": metrics}


def _empty_seed_aggregate() -> dict[str, Any]:
    return {
        "環境数": 0,
        "公開開始状態一致数": 0,
        "適格サンプル": 0,
        "fold数": 0,
        "学習件数合計": 0,
        "照会件数合計": 0,
        "結果": {target: _empty_target_metrics() for target in _TARGETS},
    }


def _merge_fold(aggregate: dict[str, Any], fold: dict[str, Any]) -> None:
    aggregate["fold数"] += 1
    aggregate["学習件数合計"] += fold["学習件数"]
    aggregate["照会件数合計"] += fold["照会件数"]
    for target, fields in fold["結果"].items():
        for key, value in fields.items():
            aggregate["結果"][target][key] += value


def run_evaluation(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite experiment output: {output}")
    games = shadow.runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    collected: dict[str, list[list[dict[str, Any]]]] = {str(seed): [] for seed in _POLICY_SEEDS}
    all_starts_match = True
    for metadata, metadata_path in development:
        reference_start = None
        per_seed_samples = {}
        for policy_seed in _POLICY_SEEDS:
            game, frame_metrics = shadow._capture_game(
                metadata, metadata_path, policy_seed=policy_seed
            )
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
            per_seed_samples[str(policy_seed)] = shadow._samples_from_trace(
                game["action_responses"], frame_metrics
            )
        for seed, samples in per_seed_samples.items():
            collected[seed].append(samples)

    by_policy_seed = {}
    for seed, samples_by_environment in collected.items():
        aggregate = _empty_seed_aggregate()
        aggregate["環境数"] = len(samples_by_environment)
        aggregate["公開開始状態一致数"] = len(samples_by_environment)
        aggregate["適格サンプル"] = sum(map(len, samples_by_environment))
        for fold_number, (training, heldout) in enumerate(
            _leave_one_environment_out(samples_by_environment), start=1
        ):
            _merge_fold(aggregate, _evaluate_fold(training, heldout))
            print(
                f"policy seed {seed}: fold {fold_number}/5 complete",
                flush=True,
            )
        by_policy_seed[seed] = aggregate

    input_count, input_hash = _public_content_hash(ROOT / "入力/Kaggle/environment_files")
    result = {
        "評価": "直前公開Frame特徴のleave-one-environment-out転移評価",
        "範囲": "fixed dev先頭5公開環境、environment seed 31、policy seed 7/31/73、各80要求",
        "splitSeed": 20261022,
        "trainEnvironmentCountPerFold": 4,
        "maximumTrainingSamplesPerEnvironment": _MAX_TRAINING_SAMPLES_PER_ENVIRONMENT,
        "trainingSampleSelection": "evenly spaced eligible samples across each training sequence",
        "testEnvironmentCountPerFold": 1,
        "allPublicStartsMatch": all_starts_match,
        "developmentEnvironmentCount": len(development),
        "policySeeds": list(_POLICY_SEEDS),
        "特徴": {
            "ActionOnlyHDS": ["条件.Action番号"],
            "FrameHDS追加条件": list(shadow._FRAME_KEYS),
            "結果": list(_TARGETS),
        },
        "byPolicySeed": by_policy_seed,
        "input": {
            "publicEnvironmentFileCount": input_count,
            "contentSetSha256": input_hash,
        },
        "source_sha256": {
            "transfer_runner": _sha256(Path(__file__)),
            "shadow_runner": _sha256(ROOT / "検証/ARC3Frame特徴公開遷移shadow評価.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
        },
        "interpretation_boundary": (
            "fixed development environments only; heldout environment is excluded "
            "from all training; no official-score claim"
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
