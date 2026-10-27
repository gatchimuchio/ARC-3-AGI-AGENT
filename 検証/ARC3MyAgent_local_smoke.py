"""Run the submitted MyAgent methods through the official local SDK environment.

The local virtualenv does not contain Kaggle's ``agents.agent`` starter module,
so this harness reuses the lightweight framework shim from test_ARC3提出agent.py
while every game observation and step is served by LocalEnvironmentWrapper.
Only aggregate results are persisted; game IDs and boards are omitted.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import random
import sys
import time

from arc_agi import EnvironmentInfo, LocalEnvironmentWrapper


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from test_ARC3提出agent import _load_agent_module  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402


ENVIRONMENT_DIR = ROOT / "入力/Kaggle/environment_files"
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/P1-3_MyAgent_local_smoke.json"


def load_games():
    games = []
    manifest = hashlib.sha256()
    for path in sorted(ENVIRONMENT_DIR.rglob("metadata.json")):
        raw = path.read_bytes()
        metadata = json.loads(raw)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("game_id"), str):
            continue
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        games.append((metadata, path))
    if len(games) < 3:
        raise RuntimeError("3件以上のpublic environment metadataが必要")
    return games, manifest.hexdigest()


def run_game(agent_type, metadata, metadata_path, *, seed: int, max_actions: int):
    info = EnvironmentInfo(
        game_id=metadata["game_id"],
        class_name=metadata.get("class_name"),
        local_dir=str(metadata_path.parent),
    )
    env = LocalEnvironmentWrapper(
        info,
        logging.getLogger("arc3-myagent-local-smoke"),
        f"myagent-smoke-{seed}",
        seed=seed,
    )
    agent = agent_type(
        card_id="local-smoke",
        game_id="local-smoke",
        agent_name="myagent-smoke",
        ROOT_URL="http://offline",
        record=False,
        arc_env=env,
    )
    agent._policy = 観測駆動探索方針(乱数種=seed)
    frame = agent._convert_raw_frame_data(env.observation_space)
    frames = [frame]
    legal_actions = non_reset_actions = reset_actions = 0
    levels_completed = frame.levels_completed
    stop_reason = "action_limit"
    action_trace = []

    for _ in range(max_actions):
        if agent.is_done(frames, frame):
            stop_reason = "agent_done"
            break
        action = agent.choose_action(frames, frame)
        observed = agent._現在のSDK観測(frame)
        if observed is None:
            stop_reason = "missing_current_observation"
            break
        if action.作用番号 == 0:
            reset_actions += 1
        else:
            if action.作用番号 not in observed.available_actions:
                raise RuntimeError("agent returned a non-legal Action")
            legal_actions += 1
            non_reset_actions += 1
        next_frame = agent.do_action_request(action)
        action_trace.append(
            {
                "action": action.作用番号,
                "state_before": frame.state.name,
                "state_after": next_frame.state.name,
                "levels_before": frame.levels_completed,
                "levels_after": next_frame.levels_completed,
            }
        )
        frame = next_frame
        agent.action_counter += 1
        frames.append(frame)
        levels_completed = max(levels_completed, frame.levels_completed)
        if frame.state.name in ("WIN", "GAME_OVER"):
            stop_reason = frame.state.name
            if frame.state.name == "WIN":
                break

    stats = agent.hds_runtime_stats
    if stats["観測更新数"] != non_reset_actions:
        raise RuntimeError("HDS transition update count does not match gameplay actions")
    if stats["状態照会数"] < non_reset_actions:
        raise RuntimeError("HDS did not query updated state before later actions")
    return {
        "non_reset_actions": non_reset_actions,
        "reset_actions": reset_actions,
        "legal_action_count": legal_actions,
        "levels_completed": levels_completed,
        "final_state": frame.state.name,
        "agent_stop_reason": stop_reason,
        "hds_observation_updates": stats["観測更新数"],
        "hds_state_queries": stats["状態照会数"],
        "hds_last_learning_state": stats["最終学習状態"],
        "hds_update_seconds": stats["学習累計秒"],
        "hds_state_query_seconds": stats["状態照会累計秒"],
        "hds_candidate_query_seconds": stats["語彙候補照会累計秒"],
        "hds_candidate_action_queries": stats["HDS候補作用照会数"],
        "hds_predicted_outcome_candidates": stats["HDS応答区分候補数"],
        "hds_guided_action_selections": stats["HDS優先選択適用数"],
        "hds_prior_memory_version": stats["事前記憶版"],
        "hds_prior_memory_loaded_count": stats["事前記憶読込件数"],
        "hds_prior_memory_boundary": stats["事前記憶HDS境界"],
        "hds_prior_memory_action_authorization": stats["事前記憶Action認可"],
        "hds_prior_memory_visible_change_coefficient": stats["事前記憶反映可視変化係数"],
        "action_trace_length": len(action_trace),
        "action_trace_sha256": hashlib.sha256(
            json.dumps(
                action_trace, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
        "two_or_more_non_reset_actions": non_reset_actions >= 2,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=3)
    parser.add_argument("--max-actions", type=int, default=16)
    parser.add_argument("--output", type=Path, help="evidence path; default uses a unique UTC timestamp")
    args = parser.parse_args()
    if args.games < 1 or args.max_actions < 1:
        parser.error("--games and --max-actions must be positive")
    games, environment_manifest = load_games()
    shuffled = list(games)
    random.Random(20261022).shuffle(shuffled)
    if args.games > len(shuffled):
        parser.error("--games exceeds the available public environment count")
    selected = shuffled[:args.games]
    agent_type = _load_agent_module().MyAgent
    started = time.perf_counter()
    rows = [
        run_game(agent_type, metadata, path, seed=31 + index, max_actions=args.max_actions)
        for index, (metadata, path) in enumerate(selected)
    ]
    aggregate = {
        "games": len(rows),
        "games_with_two_or_more_non_reset_actions": sum(
            row["two_or_more_non_reset_actions"] for row in rows
        ),
        "non_reset_actions": sum(row["non_reset_actions"] for row in rows),
        "reset_actions": sum(row["reset_actions"] for row in rows),
        "illegal_actions": 0,
        "levels_completed": sum(row["levels_completed"] for row in rows),
        "wins": sum(row["final_state"] == "WIN" for row in rows),
        "hds_observation_updates": sum(row["hds_observation_updates"] for row in rows),
        "hds_state_queries": sum(row["hds_state_queries"] for row in rows),
        "hds_candidate_action_queries": sum(
            row["hds_candidate_action_queries"] for row in rows
        ),
        "hds_predicted_outcome_candidates": sum(
            row["hds_predicted_outcome_candidates"] for row in rows
        ),
        "hds_guided_action_selections": sum(
            row["hds_guided_action_selections"] for row in rows
        ),
        "hds_update_seconds": round(sum(row["hds_update_seconds"] for row in rows), 6),
        "hds_state_query_seconds": round(sum(row["hds_state_query_seconds"] for row in rows), 6),
        "hds_candidate_query_seconds": round(sum(row["hds_candidate_query_seconds"] for row in rows), 6),
        "hds_update_count_matches_non_reset_actions": all(
            row["hds_observation_updates"] == row["non_reset_actions"] for row in rows
        ),
    }
    output = args.output or OUTPUT.with_name(
        f"{OUTPUT.stem}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    if not output.is_absolute():
        output = ROOT / output
    result = {
        "schema": "arc3-myagent-public-local-smoke.v1",
        "environment": "official arc_agi LocalEnvironmentWrapper",
        "agent_framework": "lightweight shim from test_ARC3提出agent.py; local venv lacks Kaggle agents.agent",
        "population": "project-described public ARC3 local environment set; metadata does not label a train/dev split",
        "environment_count": len(games),
        "selection_seed": 20261022,
        "action_seeds": [31 + index for index in range(args.games)],
        "max_sdk_actions_per_game": args.max_actions,
        "environment_metadata_manifest_sha256": environment_manifest,
        "agent_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC3提出agent.py").read_bytes()
        ).hexdigest(),
        "exploration_policy_source_sha256": hashlib.sha256(
            (ROOT / "接続/観測駆動探索Action.py").read_bytes()
        ).hexdigest(),
        "aggregate": aggregate,
        "per_game_aggregates": rows,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "game_ids_or_boards_saved": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"aggregate": aggregate, "elapsed_seconds": result["elapsed_seconds"], "output": str(output.relative_to(ROOT))}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
