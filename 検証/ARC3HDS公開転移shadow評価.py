"""Train a generic HDS action-outcome prior on public games and shadow-check transfer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import random
import time

from arc_agi import EnvironmentInfo, LocalEnvironmentWrapper

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3公開RHAE評価 import _スコアを計算する  # noqa: E402
from ARC3MyAgent_local_smoke import ENVIRONMENT_DIR, load_games  # noqa: E402
from test_ARC3提出agent import _load_agent_module  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402


def _実行する(
    agent_type,
    metadata,
    metadata_path,
    *,
    seed: int,
    max_actions: int,
    shared_hds=None,
    training: bool = False,
    guidance: bool = True,
) -> dict:
    info = EnvironmentInfo(
        game_id=metadata["game_id"],
        class_name=metadata.get("class_name"),
        local_dir=str(metadata_path.parent),
    )
    env = LocalEnvironmentWrapper(
        info,
        logging.getLogger("arc3-hds-public-transfer"),
        f"hds-transfer-{seed}",
        seed=seed,
    )
    agent = agent_type(
        card_id="local-transfer",
        game_id="local-transfer",
        agent_name="MyAgent",
        ROOT_URL="http://offline",
        record=False,
        arc_env=env,
    )
    agent._policy = 観測駆動探索方針(乱数種=seed)
    if training or not guidance:
        # Training is policy-matched and does not consume its own new HDS hints.
        agent._HDS状態を照会する = lambda _observed: ()
    if shared_hds is not None:
        agent._hds = shared_hds
        if training:
            # In the offline trainer, one generic HDS accumulates public
            # transitions across games. No game ID is sent into HDS inputs.
            agent._HDS適用範囲を保つ = lambda _observed: None
            # Keep the training behavior matched to the non-guided policy.
            agent._HDS状態を照会する = lambda _observed: ()

    frame = agent._convert_raw_frame_data(env.observation_space)
    initial_levels = int(frame.levels_completed)
    frames = [frame]
    responses: list[dict[str, int]] = []
    no_ops = 0
    reset_actions = 0
    stop_reason = "action_limit"
    for _ in range(max_actions):
        if agent.is_done(frames, frame):
            stop_reason = "agent_done"
            break
        action = agent.choose_action(frames, frame)
        if action.作用番号 == 0:
            reset_actions += 1
        elif action.作用番号 not in frame.available_actions:
            raise RuntimeError("agent returned a non-legal Action")
        previous_levels = int(frame.levels_completed)
        previous_board = frame.frame
        next_frame = agent.do_action_request(action)
        delta = int(next_frame.levels_completed) - previous_levels
        no_ops += int(action.作用番号 != 0 and next_frame.frame == previous_board and delta == 0)
        responses.append({"level_delta": delta})
        frame = next_frame
        agent.action_counter += 1
        frames.append(frame)
        if frame.state.name in ("WIN", "GAME_OVER"):
            stop_reason = frame.state.name
            if frame.state.name == "WIN":
                break

    baseline = metadata.get("baseline_actions")
    if (
        not isinstance(baseline, list)
        or not baseline
        or not all(type(value) is int and value > 0 for value in baseline)
    ):
        raise RuntimeError("public scorecard baseline metadata is invalid")
    score, scored_levels, _ = _スコアを計算する(
        baseline,
        {
            "action_responses": responses,
            "actions": len(responses),
            "initial_levels_completed": initial_levels,
        },
    )
    stats = agent.hds_runtime_stats
    if stats["観測更新数"] != len(responses) - reset_actions:
        # GAME_OVER reset requests are excluded from HDS learning. The precise
        # request/action consistency is also checked in the standard smoke.
        raise RuntimeError("HDS update count does not match non-reset actions")
    result = {
        "score": score,
        "levels": scored_levels,
        "actions": len(responses),
        "resets": reset_actions,
        "no_ops": no_ops,
        "wins": int(frame.state.name == "WIN"),
        "stop_reason": stop_reason,
        "hds_updates": stats["観測更新数"],
        "hds_update_seconds": stats["学習累計秒"],
        "hds_predicted_candidates": stats["HDS応答区分候補数"],
        "hds_guided_actions": stats["HDS優先選択適用数"],
    }
    return result, agent._hds


def _active_public_rules(hds) -> int:
    rules = hds.エンジン._有効原理群()
    return sum(
        1
        for rule in rules
        if rule.結果経路 == ("公開応答区分",)
        and any(path and path[0] == "作用前公開状態" for path in rule.条件経路群)
        and ("作用", "番号") in rule.条件経路群
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-games", type=int, default=2)
    parser.add_argument("--train-actions", type=int, default=40)
    parser.add_argument("--holdout-actions", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.train_games < 1 or min(args.train_actions, args.holdout_actions) < 1:
        parser.error("game and action counts must be positive")

    games, environment_manifest = load_games()
    split = list(games)
    random.Random(20261022).shuffle(split)
    if len(split) != 25 or args.train_games > 5:
        parser.error("expected the 25 public environments and no more than five train games")
    dev_games, holdout_games = split[:5], split[5:]
    training_games = dev_games[: args.train_games]
    holdout = holdout_games[0]
    agent_type = _load_agent_module().MyAgent

    shared_hds = None
    train_rows = []
    started = time.perf_counter()
    for index, (metadata, path) in enumerate(training_games):
        row, shared_hds = _実行する(
            agent_type,
            metadata,
            path,
            seed=31 + index,
            max_actions=args.train_actions,
            shared_hds=shared_hds,
            training=True,
        )
        train_rows.append(row)

    duration_training = time.perf_counter() - started
    if shared_hds is None or not train_rows:
        raise RuntimeError("no HDS training instance was produced")

    output = args.output if args.output.is_absolute() else ROOT / args.output
    model_path = output.with_name(output.stem + ".hds.json")
    for target in (output, model_path):
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing evidence: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
    shared_hds.保存する(model_path)
    model_bytes = model_path.read_bytes()
    model_text = model_bytes.decode("utf-8")
    loaded_hds = type(shared_hds).読み込む(model_path)

    holdout_metadata, holdout_path = holdout
    baseline, _ = _実行する(
        agent_type,
        holdout_metadata,
        holdout_path,
        seed=20261027,
        max_actions=args.holdout_actions,
    )
    candidate, _ = _実行する(
        agent_type,
        holdout_metadata,
        holdout_path,
        seed=20261027,
        max_actions=args.holdout_actions,
        shared_hds=loaded_hds,
    )
    delta = {
        "score": round(candidate["score"] - baseline["score"], 9),
        "levels": candidate["levels"] - baseline["levels"],
        "no_ops": candidate["no_ops"] - baseline["no_ops"],
        "wins": candidate["wins"] - baseline["wins"],
        "guided_actions": candidate["hds_guided_actions"],
    }
    result = {
        "schema": "arc3-hds-public-transfer-shadow.v1",
        "evaluation": "public offline paired shadow; one held-out public environment, same seed and action cap",
        "environment_count": len(games),
        "split_seed": 20261022,
        "environment_metadata_manifest_sha256": environment_manifest,
        "training_games": len(train_rows),
        "training_actions_per_game_cap": args.train_actions,
        "training_summary": {
            "actions": sum(row["actions"] for row in train_rows),
            "levels": sum(row["levels"] for row in train_rows),
            "hds_updates": sum(row["hds_updates"] for row in train_rows),
            "hds_update_seconds": round(sum(row["hds_update_seconds"] for row in train_rows), 6),
            "elapsed_seconds": round(duration_training, 6),
        },
        "trained_hds": {
            "active_public_action_outcome_rules": _active_public_rules(shared_hds),
            "serialized_bytes": len(model_bytes),
            "sha256": hashlib.sha256(model_bytes).hexdigest(),
            "contains_game_id_key": '"game_id"' in model_text,
            "contains_board_key": '"board"' in model_text or '"盤面"' in model_text,
            "round_trip_loaded": True,
        },
        "holdout_action_cap": args.holdout_actions,
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "interpretation": "diagnostic only; one holdout environment is insufficient for a performance claim",
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
