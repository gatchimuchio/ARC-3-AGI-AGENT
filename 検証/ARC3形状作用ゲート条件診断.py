"""初回公開観測の形状作用ゲート条件を匿名集計する。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arc_agi import EnvironmentInfo, LocalEnvironmentWrapper  # noqa: E402
from 接続.ARC3境界 import 観測する  # noqa: E402
from 接続.追加語彙接続 import 形状作用の範囲を読む  # noqa: E402
from 接続.形状配置知覚 import 形状場面を読む  # noqa: E402
from 検証.ARC3探索Actionローカル評価 import _load_games  # noqa: E402

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C3-005-shape-gate-conditions.json"
_SPLIT_SEED = 20261022
_ENVIRONMENT_SEED = 31
_SUPPORTED_SHAPE = tuple(sorted((x, y) for x in range(3) for y in range(3)))
_CONDITIONS = (
    "盤面寸法支持",
    "対象と目標を検出",
    "目標が二つ",
    "目標が支持形状かつ完全可視",
    "対象が二つ",
    "対象が支持形状",
    "対象色がモデル支持",
    "搬送候補なし",
    "選択対象が一意",
    "結合分解分岐に非該当",
)
_SAFE_STATES = {"適用可能", "構造上不適用", "未確認"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_content_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluation": Path(__file__),
        "input_loader": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "boundary": ROOT / "接続/ARC3境界.py",
        "shape_perception": ROOT / "接続/形状配置知覚.py",
        "shape_gate": ROOT / "接続/追加語彙接続.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def _condition_results(scene: dict[str, Any], board: list[list[int]]) -> dict[str, bool]:
    objects = scene.get("対象", [])
    targets = scene.get("目標", [])
    if not isinstance(objects, list) or not isinstance(targets, list):
        raise TypeError("shape perception returned a non-list object collection")
    complete_targets = all(
        isinstance(target, dict)
        and target.get("形") == _SUPPORTED_SHAPE
        and "未観測枠" not in target
        for target in targets
    )
    supported_objects = all(
        isinstance(obj, dict) and obj.get("形") == _SUPPORTED_SHAPE for obj in objects
    )
    supported_colors = all(isinstance(obj, dict) and obj.get("色") == 14 for obj in objects)
    unique_selection = (
        sum(isinstance(obj, dict) and obj.get("選択") is True for obj in objects) == 1
    )
    combined_or_split = (
        len(targets) == 2
        and complete_targets
        and len(objects) != 2
        and sum(len(obj.get("点", ())) for obj in objects if isinstance(obj, dict)) == 18
    )
    return {
        "盤面寸法支持": len(board) == 64 and all(len(row) == 64 for row in board),
        "対象と目標を検出": bool(objects) and bool(targets),
        "目標が二つ": len(targets) == 2,
        "目標が支持形状かつ完全可視": bool(targets) and complete_targets,
        "対象が二つ": len(objects) == 2,
        "対象が支持形状": bool(objects) and supported_objects,
        "対象色がモデル支持": bool(objects) and supported_colors,
        "搬送候補なし": not any(value in (12, 13) for row in board for value in row),
        "選択対象が一意": unique_selection,
        "結合分解分岐に非該当": not combined_or_split,
    }


def _safe_gate_state(result: dict[str, Any]) -> str:
    state = result.get("状態")
    return state if isinstance(state, str) and state in _SAFE_STATES else "その他"


def summarize_conditions(
    scenes: list[tuple[dict[str, Any], list[list[int]], dict[str, Any]]],
) -> dict[str, Any]:
    """Return aggregate counts only; never serialize scenes or their source boards."""
    condition_passes: Counter[str] = Counter()
    gate_states: Counter[str] = Counter()
    for scene, board, gate_result in scenes:
        conditions = _condition_results(scene, board)
        if set(conditions) != set(_CONDITIONS):
            raise RuntimeError("condition summary schema drifted")
        condition_passes.update(name for name, passed in conditions.items() if passed)
        gate_states[_safe_gate_state(gate_result)] += 1
    total = len(scenes)
    if total != 5:
        raise RuntimeError("the fixed initial development sample must contain five observations")
    return {
        "初回進行中観測件数": total,
        "条件別成立件数": {
            name: {"成立": condition_passes[name], "不成立": total - condition_passes[name]}
            for name in _CONDITIONS
        },
        "作用ゲート状態件数": dict(sorted(gate_states.items())),
    }


def run_audit(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(_SPLIT_SEED).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    initial_state_counts: Counter[str] = Counter()
    scenes: list[tuple[dict[str, Any], list[list[int]], dict[str, Any]]] = []
    started = time.perf_counter()
    for metadata, metadata_path in development:
        info = EnvironmentInfo(
            game_id=metadata["game_id"],
            class_name=metadata.get("class_name"),
            local_dir=str(metadata_path.parent),
        )
        environment = LocalEnvironmentWrapper(
            info,
            logging.getLogger("arc3-shape-gate-condition-audit"),
            "shape-gate-condition-audit",
            seed=_ENVIRONMENT_SEED,
        )
        observation = 観測する(environment.observation_space, 観測通番=0)
        initial_state_counts[observation.状態] += 1
        if observation.状態 != "NOT_FINISHED":
            continue
        board = [list(row) for row in observation.最新盤面]
        scene = 形状場面を読む(board)
        gate_result = 形状作用の範囲を読む(scene, board)
        scenes.append((scene, board, gate_result))

    if initial_state_counts != Counter({"NOT_FINISHED": 5}):
        raise RuntimeError("the fixed initial observations are not five NOT_FINISHED states")
    summary = summarize_conditions(scenes)
    if summary["作用ゲート状態件数"] != {"構造上不適用": 5}:
        raise RuntimeError("shape-action gate result differs from C3-004 baseline")

    input_count, input_hash = _public_content_hash(ROOT / "入力/Kaggle/environment_files")
    result = {
        "評価": "初回公開観測での形状作用ゲート条件別診断",
        "範囲": "固定dev先頭5公開環境、environment seed 31、各1回の初回観測",
        "splitSeed": _SPLIT_SEED,
        "環境seed": _ENVIRONMENT_SEED,
        **summary,
        "安全境界": {
            "HDS照会": 0,
            "HDS学習": 0,
            "Action要求": 0,
            "候補実行": 0,
        },
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "input": {"publicEnvironmentFileCount": input_count, "contentSetSha256": input_hash},
        "source_sha256": _source_hashes(),
        "exclusion": [
            "game/level identifiers",
            "GUID and observation fingerprint",
            "raw board and pixel values",
            "coordinates, shapes and object/target records",
            "action arguments and trajectories",
            "gate reason text",
        ],
        "interpretation_boundary": (
            "initial public observations only; no action, HDS inference or learning, "
            "transfer, runtime or official-score claim"
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
    print(json.dumps(run_audit(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
