"""Measure whether within-game HDS action guidance changes public scorecard outcomes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3MyAgent_local_smoke import load_games
from ARC3HDS公開転移shadow評価 import _実行する
from test_ARC3提出agent import _load_agent_module

ROOT = Path(__file__).resolve().parents[1]


def _condition(games, agent_type, seeds, *, guidance: bool):
    runs = []
    for seed in seeds:
        seed_rows = []
        for index, (metadata, path) in enumerate(games):
            result, _ = _実行する(
                agent_type,
                metadata,
                path,
                seed=seed,
                max_actions=80,
                guidance=guidance,
            )
            seed_rows.append({"seed": seed, "game_index": index, **result})
        runs.extend(seed_rows)
    return runs


def _summarize(rows, seeds, games_per_seed):
    summaries = []
    for seed in seeds:
        selected = [row for row in rows if row["seed"] == seed]
        if len(selected) != games_per_seed:
            raise RuntimeError("paired run count mismatch")
        summaries.append(
            {
                "seed": seed,
                "games": len(selected),
                "rhae_score_mean": round(
                    sum(row["score"] for row in selected) / len(selected), 9
                ),
                "levels": sum(row["levels"] for row in selected),
                "wins": sum(row["wins"] for row in selected),
                "no_ops": sum(row["no_ops"] for row in selected),
                "resets": sum(row["resets"] for row in selected),
                "guided_actions": sum(row["hds_guided_actions"] for row in selected),
                "predicted_candidates": sum(
                    row["hds_predicted_candidates"] for row in selected
                ),
                "hds_update_seconds": round(
                    sum(row["hds_update_seconds"] for row in selected), 6
                ),
            }
        )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    games, manifest = load_games()
    if len(games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(games)
    random.Random(20261022).shuffle(split)
    selected = split[:5] if args.stage == "dev" else split[5:25]
    agent_type = _load_agent_module().MyAgent
    started = time.perf_counter()

    guided = _condition(selected, agent_type, args.seeds, guidance=True)
    withheld = _condition(selected, agent_type, args.seeds, guidance=False)
    baseline_lookup = {(row["seed"], row["game_index"]): row for row in withheld}
    deltas = []
    for row in guided:
        control = baseline_lookup[(row["seed"], row["game_index"])]
        deltas.append(
            {
                "score_delta": round(row["score"] - control["score"], 9),
                "levels_delta": row["levels"] - control["levels"],
                "no_ops_delta": row["no_ops"] - control["no_ops"],
                "wins_delta": row["wins"] - control["wins"],
                "guided_actions": row["hds_guided_actions"],
            }
        )

    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    agent_source_hash = hashlib.sha256(
        (ROOT / "接続/ARC3提出agent.py").read_bytes()
    ).hexdigest()
    result = {
        "schema": "arc3-hds-action-guidance-paired-rhae.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "public offline paired; same seed, environment, action cap and online HDS updates",
        "stage": args.stage,
        "split_seed": 20261022,
        "games": len(selected),
        "seeds": args.seeds,
        "max_actions_per_game": 80,
        "environment_metadata_manifest_sha256": manifest,
        "agent_source_sha256": agent_source_hash,
        "guided": {
            "runs": _summarize(guided, args.seeds, len(selected)),
            "per_game_aggregates": guided,
        },
        "guidance_withheld_control": {
            "runs": _summarize(withheld, args.seeds, len(selected)),
            "per_game_aggregates": withheld,
        },
        "paired_delta_guided_minus_control": {
            "pairs": len(deltas),
            "score_improvements": sum(x["score_delta"] > 0 for x in deltas),
            "score_regressions": sum(x["score_delta"] < 0 for x in deltas),
            "score_ties": sum(x["score_delta"] == 0 for x in deltas),
            "score_delta_mean": round(
                sum(x["score_delta"] for x in deltas) / len(deltas), 9
            ),
            "levels_delta_total": sum(x["levels_delta"] for x in deltas),
            "no_ops_delta_total": sum(x["no_ops_delta"] for x in deltas),
            "wins_delta_total": sum(x["wins_delta"] for x in deltas),
            "guided_action_count": sum(x["guided_actions"] for x in deltas),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_made": False,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
