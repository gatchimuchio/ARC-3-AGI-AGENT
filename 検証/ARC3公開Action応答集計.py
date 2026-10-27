"""Summarize public action/response effects without persisting game-level rows."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_manifest_sha256() -> str:
    root = ROOT / "入力/Kaggle/environment_files"
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _summarize_policy(
    games: list[dict[str, Any]], metadata_by_id: dict[str, dict[str, Any]], policy: str
) -> dict[str, Any]:
    scores: list[float] = []
    action_total = level_total = noop_total = game_over_total = win_total = 0
    for game in games:
        run = game[policy]
        metadata = metadata_by_id[run["game_id"]]
        score, levels, _ = _スコアを計算する(metadata["baseline_actions"], run)
        scores.append(score)
        action_total += int(run["actions"])
        level_total += levels
        noop_total += int(run["no_op_actions"])
        game_over_total += int(run["game_over_events"])
        win_total += int(run["final_state"] == "WIN")
    return {
        "games": len(scores),
        "rhae_mean": sum(scores) / len(scores),
        "levels_completed_total": level_total,
        "wins": win_total,
        "actions_total": action_total,
        "noops_total": noop_total,
        "game_over_events_total": game_over_total,
    }


def _action_effects(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[int, Counter[str | int | float]] = defaultdict(Counter)
    rewards: dict[int, Counter[str]] = defaultdict(Counter)
    for game in games:
        for response in game["exploration"]["action_responses"]:
            action_id = int(response["action_id"])
            row = stats[action_id]
            row["actions"] += 1
            row["visible_change_actions"] += int(int(response["changed_cells"]) > 0)
            row["noops"] += int(int(response["changed_cells"]) == 0)
            row["new_visible_boards"] += int(bool(response["new_visible_board"]))
            row["level_events"] += int(int(response["level_delta"]) > 0)
            row["levels_completed"] += int(response["level_delta"])
            row["game_over_events"] += int(response["after_state"] == "GAME_OVER")
            public_response = response.get("policy_response", {})
            reward = float(public_response.get("公開応答報酬", 0.0))
            row["reward_sum"] += reward
            rewards[action_id][f"{reward:.3f}"] += 1

    output: list[dict[str, Any]] = []
    for action_id, row in sorted(stats.items()):
        count = int(row["actions"])
        output.append(
            {
                "action_id": action_id,
                "actions": count,
                "visible_change_actions": int(row["visible_change_actions"]),
                "noops": int(row["noops"]),
                "new_visible_boards": int(row["new_visible_boards"]),
                "level_events": int(row["level_events"]),
                "levels_completed": int(row["levels_completed"]),
                "game_over_events": int(row["game_over_events"]),
                "mean_public_response_reward": float(row["reward_sum"]) / count,
                "public_response_reward_counts": dict(sorted(rewards[action_id].items())),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    trace = json.loads(args.input.read_text(encoding="utf-8"))
    if trace.get("stage") != "all" or len(trace.get("games", [])) != 25:
        raise ValueError("expected an all-stage public 25-game local trace")
    if not all(game.get("same_public_start") for game in trace["games"]):
        raise ValueError("paired policies did not share all public starts")

    loaded = _load_games(ROOT / "入力/Kaggle/environment_files")
    metadata_by_id = {metadata["game_id"]: metadata for metadata, _ in loaded}
    if len(metadata_by_id) != 25:
        raise ValueError("expected 25 public game metadata records")
    all_game_ids = set(metadata_by_id)
    traced_ids = {game["game_id"] for game in trace["games"]}
    if traced_ids != all_game_ids:
        raise ValueError("trace does not cover the public metadata set")

    random_summary = _summarize_policy(trace["games"], metadata_by_id, "random")
    exploration_summary = _summarize_policy(trace["games"], metadata_by_id, "exploration")
    output: dict[str, Any] = {
        "schema": "arc3-public-action-response-attribution.v1",
        "stage": "all",
        "games": 25,
        "split_seed": trace["split_seed"],
        "action_seed": trace["action_seed"],
        "policy_seed": trace["policy_seed"],
        "max_actions_per_policy": trace["max_actions_per_policy"],
        "visible_change_coefficient": trace["visible_change_coefficient"],
        "same_public_starts": 25,
        "policies": {
            "random": random_summary,
            "exploration": exploration_summary,
            "exploration_minus_random": {
                key: exploration_summary[key] - random_summary[key]
                for key in (
                    "rhae_mean",
                    "levels_completed_total",
                    "wins",
                    "actions_total",
                    "noops_total",
                    "game_over_events_total",
                )
            },
        },
        "exploration_action_response_effects": _action_effects(trace["games"]),
        "errors": 0,
        "hidden_or_answer_data_read": False,
        "game_ids_or_per_game_rows_persisted": False,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "trace_sha256": _sha(args.input),
        "environment_manifest_sha256": _input_manifest_sha256(),
        "local_runner_sha256": _sha(ROOT / "検証/ARC3探索Actionローカル評価.py"),
        "scorer_sha256": _sha(ROOT / "検証/ARC3公開RHAE評価.py"),
        "policy_sha256": _sha(ROOT / "接続/観測駆動探索Action.py"),
        "analyzer_sha256": _sha(Path(__file__)),
    }
    encoded = json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if any(game_id in encoded for game_id in all_game_ids):
        raise RuntimeError("per-game identifier leaked into aggregate output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
