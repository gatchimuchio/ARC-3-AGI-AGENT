"""Paired dev scorecard trial of a lower HDS provisional-rule support threshold."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

from ARC3MyAgent_local_smoke import load_games
from ARC3HDS公開転移shadow評価 import _実行する
from test_ARC3提出agent import _load_agent_module

ROOT = Path(__file__).resolve().parents[1]


def _summarize(rows, seeds, games_per_seed):
    output = []
    for seed in seeds:
        selected = [row for row in rows if row["seed"] == seed]
        if len(selected) != games_per_seed:
            raise RuntimeError("paired run count mismatch")
        output.append(
            {
                "seed": seed,
                "games": len(selected),
                "rhae_score_mean": round(
                    sum(row["score"] for row in selected) / len(selected), 9
                ),
                "levels": sum(row["levels"] for row in selected),
                "no_ops": sum(row["no_ops"] for row in selected),
                "guided_actions": sum(row["hds_guided_actions"] for row in selected),
                "predicted_candidates": sum(
                    row["hds_predicted_candidates"] for row in selected
                ),
                "hds_update_seconds": round(
                    sum(row["hds_update_seconds"] for row in selected), 6
                ),
            }
        )
    return output


def _deltas(candidate, baseline):
    by_key = {(row["seed"], row["game_index"]): row for row in baseline}
    pairs = []
    for row in candidate:
        control = by_key[(row["seed"], row["game_index"])]
        pairs.append(
            {
                "score_delta": round(row["score"] - control["score"], 9),
                "levels_delta": row["levels"] - control["levels"],
                "no_ops_delta": row["no_ops"] - control["no_ops"],
                "guided_action_delta": row["hds_guided_actions"] - control["hds_guided_actions"],
            }
        )
    return {
        "pairs": len(pairs),
        "score_improvements": sum(row["score_delta"] > 0 for row in pairs),
        "score_regressions": sum(row["score_delta"] < 0 for row in pairs),
        "score_ties": sum(row["score_delta"] == 0 for row in pairs),
        "score_delta_mean": round(sum(row["score_delta"] for row in pairs) / len(pairs), 9),
        "levels_delta_total": sum(row["levels_delta"] for row in pairs),
        "no_ops_delta_total": sum(row["no_ops_delta"] for row in pairs),
        "guided_action_delta_total": sum(
            row["guided_action_delta"] for row in pairs
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    games, manifest = load_games()
    if len(games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(games)
    random.Random(20261022).shuffle(split)
    selected = split[:5]
    module = _load_agent_module()
    baseline_type = module.MyAgent
    base_hds_type = module.HDS学習系統
    output = args.output if args.output.is_absolute() else ROOT / args.output
    checkpoint_path = output.with_name(output.stem + ".partial.json")
    if output.exists() or checkpoint_path.exists():
        raise FileExistsError("refusing to overwrite existing result or partial checkpoint")
    output.parent.mkdir(parents=True, exist_ok=True)

    class _HDSMinimumSupport2(base_hds_type):
        def __init__(self):
            super().__init__(最小支持数=2, 最大条件数=2)

    class _MyAgentMinimumSupport2(baseline_type):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._hds = _HDSMinimumSupport2()
            self._hds_prior_report = module.事前記憶をHDSへ供給する(self._hds)
            self._policy = module.観測駆動探索方針(
                可視変化係数=self._hds_prior_report["visible_change_coefficient"]
            )

    def run_condition(agent_type, label):
        rows = []
        for seed in args.seeds:
            for index, (metadata, path) in enumerate(selected):
                row, _ = _実行する(
                    agent_type,
                    metadata,
                    path,
                    seed=seed,
                    max_actions=80,
                    guidance=True,
                )
                rows.append({"seed": seed, "game_index": index, **row})
                print(f"PROGRESS {label} {len(rows)}/{len(args.seeds) * len(selected)}", flush=True)
        return rows

    started = time.perf_counter()
    baseline = run_condition(baseline_type, "support3")
    checkpoint_path.write_text(
        json.dumps(
            {"schema": "arc3-hds-minimum-support-paired-rhae.partial.v1", "baseline": baseline},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    candidate = run_condition(_MyAgentMinimumSupport2, "support2")
    checkpoint_path.write_text(
        json.dumps(
            {
                "schema": "arc3-hds-minimum-support-paired-rhae.partial.v1",
                "baseline": baseline,
                "candidate": candidate,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = {
        "schema": "arc3-hds-minimum-support-paired-rhae.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "public dev paired; default min support 3 versus 2; online HDS guidance enabled",
        "split_seed": 20261022,
        "games": len(selected),
        "seeds": args.seeds,
        "max_actions_per_game": 80,
        "environment_metadata_manifest_sha256": manifest,
        "agent_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC3提出agent.py").read_bytes()
        ).hexdigest(),
        "baseline_support_3": {
            "runs": _summarize(baseline, args.seeds, len(selected)),
            "per_game_aggregates": baseline,
        },
        "candidate_support_2": {
            "runs": _summarize(candidate, args.seeds, len(selected)),
            "per_game_aggregates": candidate,
        },
        "paired_delta_support2_minus_support3": _deltas(candidate, baseline),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_made": False,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint_path.unlink()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
