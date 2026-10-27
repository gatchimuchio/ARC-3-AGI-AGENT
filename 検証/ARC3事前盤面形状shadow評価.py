"""作用前の公開盤面色分布を使うHDS shadow予測のdev-only評価。"""

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
from ARC3複数Frame公開観測診断 import _grid_sequence  # noqa: E402
from arc_agi import LocalEnvironmentWrapper  # noqa: E402
from hds学習系統 import HDS学習系統, 外部入力  # noqa: E402
from 検証.ARC3Frame特徴crossGameTransfer import _public_content_hash  # noqa: E402

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C1-009-board-morphology-shadow-dev.json"
境界 = "ARC-AGI-3公開Action応答"
結果経路群 = {
    "可視変化あり": ("結果", "可視変化あり"),
    "level進行あり": ("結果", "level進行あり"),
    "新規盤面あり": ("結果", "新規盤面あり"),
}
_POLICY_SEEDS = (7, 31, 73)
_ENVIRONMENT_SEED = 31
_TRAIN_FRACTION = 0.75
_BOARD_KEYS = ("事前盤面色分布帯",)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _board_features(grid: tuple[tuple[int, ...], ...] | None) -> dict[str, str] | None:
    if not grid or any(not row for row in grid):
        return None
    counts = Counter(value for row in grid for value in row)
    cells = sum(counts.values())
    if not cells:
        return None
    colors = len(counts)
    dominant_share = max(counts.values()) / cells
    colors_band = "1-2" if colors <= 2 else "3-4" if colors <= 4 else "5+"
    dominant_band = (
        "50%以下" if dominant_share <= 0.5 else "50%-75%" if dominant_share <= 0.75 else "75%超"
    )
    return {"事前盤面色分布帯": f"色数{colors_band};最多色{dominant_band}"}


def _samples_from_trace(
    responses: list[dict[str, Any]],
    pre_action_features: list[dict[str, str] | None],
) -> list[dict[str, Any]]:
    if len(responses) != len(pre_action_features):
        raise ValueError("captured pre-action feature count differs from response count")
    samples = []
    for response, features in zip(responses, pre_action_features, strict=True):
        action_id = response.get("action_id")
        if (
            response.get("lifecycle_action")
            or action_id == 0
            or type(action_id) is not int
            or not 1 <= action_id <= 7
            or features is None
        ):
            continue
        samples.append(
            {
                "action_id": action_id,
                "changed_cells": int(response["changed_cells"]),
                "level_delta": int(response["level_delta"]),
                "new_visible_board": bool(response["new_visible_board"]),
                "board_features": features,
            }
        )
    return samples


def _input(sample: dict[str, Any], *, include_board: bool, include_result: bool) -> 外部入力:
    conditions: dict[str, Any] = {"Action番号": sample["action_id"]}
    if include_board:
        conditions.update(sample["board_features"])
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


def _empty_metrics() -> dict[str, int]:
    return {
        "照会件数": 0,
        "Action多数派適用": 0,
        "Action多数派正答": 0,
        "ActionOnlyHDS単一予測": 0,
        "ActionOnlyHDS正答": 0,
        "BoardHDS単一予測": 0,
        "BoardHDS正答": 0,
        "共通coverage": 0,
        "共通ActionOnlyHDS正答": 0,
        "共通BoardHDS正答": 0,
        "共通Action多数派正答": 0,
        "BoardHDSが多数派誤りを正答": 0,
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
        "Board条件": (HDS学習系統(), True),
    }
    for model, include_board in models.values():
        for sample in training:
            model.処理する(_input(sample, include_board=include_board, include_result=True))

    metrics = {target: _empty_metrics() for target in 結果経路群}
    for sample in heldout:
        results = {
            name: model.照会する(_input(sample, include_board=include_board, include_result=False))
            for name, (model, include_board) in models.items()
        }
        for target, path in 結果経路群.items():
            row = metrics[target]
            actual = _result_value(sample, target)
            majority = _majority(training, target, sample["action_id"])
            predictions = {name: _prediction(result, path) for name, result in results.items()}
            row["照会件数"] += 1
            if majority is not None:
                row["Action多数派適用"] += 1
                row["Action多数派正答"] += int(majority == actual)
            for name, label in (
                ("ActionOnly", "ActionOnlyHDS"),
                ("Board条件", "BoardHDS"),
            ):
                prediction = predictions[name]
                if prediction is not None:
                    row[f"{label}単一予測"] += 1
                    row[f"{label}正答"] += int(prediction == actual)
            action_only = predictions["ActionOnly"]
            board_prediction = predictions["Board条件"]
            if majority is not None and action_only is not None and board_prediction is not None:
                row["共通coverage"] += 1
                row["共通ActionOnlyHDS正答"] += int(action_only == actual)
                row["共通BoardHDS正答"] += int(board_prediction == actual)
                row["共通Action多数派正答"] += int(majority == actual)
            if majority is not None and majority != actual and board_prediction is not None:
                row["BoardHDSが多数派誤りを正答"] += int(board_prediction == actual)
    return {
        "適格サンプル": len(samples),
        "学習件数": len(training),
        "後半照会件数": len(heldout),
        "結果": metrics,
    }


def _capture_game(
    metadata: dict[str, Any], metadata_path: Path, *, policy_seed: int
) -> tuple[dict[str, Any], list[dict[str, str] | None]]:
    captured: list[dict[str, str] | None] = []
    original_step = LocalEnvironmentWrapper.step

    def instrumented_step(self, action, data=None, reasoning=None):
        before = getattr(self, "observation_space", None)
        grids = _grid_sequence(getattr(before, "frame", None))
        features = _board_features(grids[-1]) if grids else None
        response = original_step(self, action, data=data, reasoning=reasoning)
        captured.append(features)
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
        raise RuntimeError("captured pre-action feature count differs from action count")
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

    by_policy_seed: dict[str, Any] = {
        str(seed): {
            "環境数": 0,
            "公開開始状態一致数": 0,
            "適格サンプル": 0,
            "学習件数": 0,
            "後半照会件数": 0,
            "結果": {target: _empty_metrics() for target in 結果経路群},
        }
        for seed in _POLICY_SEEDS
    }
    all_starts_match = True
    for metadata, metadata_path in development:
        reference_start = None
        for policy_seed in _POLICY_SEEDS:
            game, features = _capture_game(metadata, metadata_path, policy_seed=policy_seed)
            start = (
                game["initial_state"],
                game["initial_levels_completed"],
                tuple(game["initial_available_actions"]),
                game["initial_board"],
            )
            same_start = reference_start is None or start == reference_start
            if reference_start is None:
                reference_start = start
            all_starts_match = all_starts_match and same_start
            samples = _samples_from_trace(game["action_responses"], features)
            run_result = _evaluate_samples(samples)
            aggregate = by_policy_seed[str(policy_seed)]
            aggregate["環境数"] += 1
            aggregate["公開開始状態一致数"] += int(same_start)
            for key in ("適格サンプル", "学習件数", "後半照会件数"):
                aggregate[key] += run_result[key]
            for target, fields in run_result["結果"].items():
                for key, value in fields.items():
                    aggregate["結果"][target][key] += value

    input_count, input_hash = _public_content_hash(ROOT / "入力/Kaggle/environment_files")
    result = {
        "評価": "作用前盤面色分布を使ったHDS shadow予測",
        "範囲": "固定dev先頭5公開環境、environment seed 31、policy seed 7/31/73、各80要求",
        "splitSeed": 20261022,
        "trainFraction": _TRAIN_FRACTION,
        "developmentEnvironmentCount": len(development),
        "allPublicStartsMatch": all_starts_match,
        "byPolicySeed": by_policy_seed,
        "features": {
            "ActionOnlyHDS": ["条件.Action番号"],
            "BoardHDS追加条件": [f"条件.{key}" for key in _BOARD_KEYS],
            "targets": [f"結果.{key}" for key in 結果経路群],
        },
        "input": {
            "publicEnvironmentFileCount": input_count,
            "contentSetSha256": input_hash,
        },
        "source_sha256": {
            "evaluation_runner": _sha256(Path(__file__)),
            "local_evaluation_runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "frame_parser": _sha256(ROOT / "検証/ARC3複数Frame公開観測診断.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
        },
        "exclusion": [
            "game/level identifiers",
            "GUID",
            "raw board and color values",
            "coordinates",
            "same-response outcome features",
            "trajectory",
        ],
        "interpretation_boundary": (
            "within-environment sequential dev split only; no cross-game transfer "
            "or official-score claim"
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
