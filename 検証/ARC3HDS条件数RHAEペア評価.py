"""Paired dev scorecard trial of HDS using up to three public conditions."""

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
from ARC3HDS最低支持数RHAEペア評価 import _deltas, _summarize
from test_ARC3提出agent import _load_agent_module

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[31])
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
    hds_type = module.HDS学習系統

    class _HDSMaximumConditions3(hds_type):
        def __init__(self):
            super().__init__(最小支持数=3, 最大条件数=3)

    class _MyAgentMaximumConditions3(baseline_type):
        def __init__(self, *positional, **named):
            super().__init__(*positional, **named)
            self._hds = _HDSMaximumConditions3()
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
                print(
                    f"PROGRESS {label} {len(rows)}/{len(args.seeds) * len(selected)}",
                    flush=True,
                )
        return rows

    output = args.output if args.output.is_absolute() else ROOT / args.output
    checkpoint = output.with_name(output.stem + ".partial.json")
    if output.exists() or checkpoint.exists():
        raise FileExistsError("refusing to overwrite existing result or checkpoint")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    baseline = run_condition(baseline_type, "max_conditions_2")
    checkpoint.write_text(
        json.dumps({"schema": "arc3-hds-condition-count.partial.v1", "baseline": baseline}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    candidate = run_condition(_MyAgentMaximumConditions3, "max_conditions_3")
    checkpoint.write_text(
        json.dumps({"schema": "arc3-hds-condition-count.partial.v1", "baseline": baseline, "candidate": candidate}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = {
        "schema": "arc3-hds-condition-count-paired-rhae.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "public dev paired; HDS max conditions 2 versus 3; support fixed at 3; online guidance enabled",
        "split_seed": 20261022,
        "games": len(selected),
        "seeds": args.seeds,
        "max_actions_per_game": 80,
        "environment_metadata_manifest_sha256": manifest,
        "agent_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC3提出agent.py").read_bytes()
        ).hexdigest(),
        "baseline_max_conditions_2": {
            "runs": _summarize(baseline, args.seeds, len(selected)),
            "per_game_aggregates": baseline,
        },
        "candidate_max_conditions_3": {
            "runs": _summarize(candidate, args.seeds, len(selected)),
            "per_game_aggregates": candidate,
        },
        "paired_delta_conditions3_minus_conditions2": _deltas(candidate, baseline),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_made": False,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint.unlink()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
