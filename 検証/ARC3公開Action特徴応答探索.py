"""Explore public action-response feature counts without persisting game rows."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games, _run_game


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha256() -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be unique")
    if args.max_actions <= 0:
        parser.error("max-actions must be positive")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")

    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError("expected 25 public environments")

    totals: dict[str, int | float] = {
        "episodes": 0,
        "rhae_sum": 0.0,
        "levels_completed": 0,
        "wins": 0,
        "actions": 0,
        "noops": 0,
        "level_events": 0,
        "errors": 0,
        "illegal_actions": 0,
        "duplicate_observations": 0,
    }
    by_seed: list[dict[str, int | float]] = []
    feature_counts: dict[tuple[int, int | None], dict[str, object]] = defaultdict(
        lambda: {
            "actions": 0,
            "noops": 0,
            "visible_changes": 0,
            "new_visible_boards": 0,
            "level_events": 0,
            "level_event_episodes": set(),
            "level_event_games": set(),
            "public_reward_sum": 0.0,
            "game_over_events": 0,
        }
    )

    episode_index = 0
    for seed in args.seeds:
        seed_totals: dict[str, int | float] = {
            "seed": seed,
            "episodes": 0,
            "rhae_sum": 0.0,
            "levels_completed": 0,
            "wins": 0,
            "actions": 0,
            "noops": 0,
            "level_events": 0,
        }
        for game_index, (metadata, metadata_path) in enumerate(games, start=1):
            run = _run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=args.max_actions,
                visible_change_coefficient=0.0,
            )
            score, levels, _ = _スコアを計算する(metadata["baseline_actions"], run)
            won = int(run["final_state"] == "WIN")
            episode_index += 1
            events_this_episode = 0
            for response in run["action_responses"]:
                action_id = int(response["action_id"])
                public_response = response.get("policy_response", {})
                color_value = public_response.get("座標可視色") if action_id == 6 else None
                color = int(color_value) if color_value is not None else None
                group = feature_counts[(action_id, color)]
                event = int(int(response.get("level_delta", 0)) > 0)
                group["actions"] = int(group["actions"]) + 1
                group["noops"] = int(group["noops"]) + int(
                    int(response.get("changed_cells", 0)) == 0 and event == 0
                )
                group["visible_changes"] = int(group["visible_changes"]) + int(
                    int(response.get("changed_cells", 0)) > 0
                )
                group["new_visible_boards"] = int(group["new_visible_boards"]) + int(
                    bool(response.get("new_visible_board"))
                )
                group["level_events"] = int(group["level_events"]) + event
                if event:
                    group["level_event_episodes"].add(episode_index)
                    group["level_event_games"].add(game_index)
                    events_this_episode += event
                group["public_reward_sum"] = float(group["public_reward_sum"]) + float(
                    public_response.get("公開応答報酬", 0.0)
                )
                group["game_over_events"] = int(group["game_over_events"]) + int(
                    response.get("after_state") == "GAME_OVER"
                )

            run_counts = {
                "episodes": 1,
                "rhae_sum": score,
                "levels_completed": levels,
                "wins": won,
                "actions": int(run["actions"]),
                "noops": int(run["no_op_actions"]),
                "level_events": events_this_episode,
            }
            for key, value in run_counts.items():
                seed_totals[key] = seed_totals[key] + value
                totals[key] = totals[key] + value
            totals["illegal_actions"] = int(totals["illegal_actions"]) + int(
                run["illegal_action_attempts"]
            )
            totals["duplicate_observations"] = int(totals["duplicate_observations"]) + int(
                run["duplicate_observation_steps"]
            )
            if run["illegal_action_attempts"] or run["duplicate_observation_steps"]:
                totals["errors"] = int(totals["errors"]) + 1
            print(
                f"PROGRESS seed={seed} episode={game_index}/{len(games)}",
                flush=True,
            )
        seed_totals["rhae_mean"] = float(seed_totals.pop("rhae_sum")) / int(seed_totals["episodes"])
        by_seed.append(seed_totals)

    episodes = int(totals["episodes"])
    aggregate_rows = []
    for (action_id, color), values in sorted(feature_counts.items()):
        count = int(values["actions"])
        event_episodes = values["level_event_episodes"]
        aggregate_rows.append(
            {
                "action_id": action_id,
                "selected_visible_color": color,
                "actions": count,
                "noops": int(values["noops"]),
                "visible_changes": int(values["visible_changes"]),
                "new_visible_boards": int(values["new_visible_boards"]),
                "level_events": int(values["level_events"]),
                "episodes_with_level_event": len(event_episodes),
                "public_games_with_level_event": len(values["level_event_games"]),
                "mean_public_reward": float(values["public_reward_sum"]) / count,
                "game_over_events": int(values["game_over_events"]),
            }
        )

    result = {
        "schema": "arc3-public-action-feature-response-aggregate.v1",
        "stage": "all_public_games_aggregate_only",
        "games_per_seed": len(games),
        "seeds": args.seeds,
        "episodes": episodes,
        "policy": "current_observation_driven_exploration",
        "policy_seed_rule": "policy seed equals environment seed",
        "max_actions_per_episode": args.max_actions,
        "visible_change_coefficient": 0.0,
        "level_progress_reward": 4.0,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "summary": {
            **{key: value for key, value in totals.items() if key != "rhae_sum"},
            "rhae_mean": float(totals["rhae_sum"]) / episodes,
        },
        "per_seed_aggregate": by_seed,
        "action_and_selected_color_aggregates": aggregate_rows,
        "game_ids_or_per_game_rows_persisted": False,
        "only_public_observations_used": True,
        "official_submission_made": False,
        "competition_api_called": False,
        "environment_manifest_sha256": _manifest_sha256(),
        "policy_sha256": _sha(ROOT / "接続/観測駆動探索Action.py"),
        "runner_sha256": _sha(ROOT / "検証/ARC3探索Actionローカル評価.py"),
        "scorer_sha256": _sha(ROOT / "検証/ARC3公開RHAE評価.py"),
        "aggregator_sha256": _sha(Path(__file__)),
    }
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
