"""Paired public dev evaluation for generic HDS guidance of coordinate Action 6."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3HDS公開転移shadow評価 import _実行する
from ARC3MyAgent_local_smoke import load_games
from test_ARC3提出agent import _load_agent_module
from hds学習系統.型 import 外部入力


SPLIT_SEED = 20261022
SEEDS = (7, 31, 73)
MAX_ACTIONS = 80
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/P1-3_HDS_action6_generic_query_dev_20261027.json"
CHECKPOINT = ROOT / "運用/証拠/ARC26-UNIFIED/P1-3_HDS_action6_generic_query_dev_20261027.jsonl"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score_deltas = [float(row["candidate_score"]) - float(row["baseline_score"]) for row in rows]
    return {
        "pairs": len(rows),
        "baseline_rhae_mean": round(sum(float(row["baseline_score"]) for row in rows) / len(rows), 9),
        "candidate_rhae_mean": round(sum(float(row["candidate_score"]) for row in rows) / len(rows), 9),
        "score_delta_mean": round(sum(score_deltas) / len(score_deltas), 9),
        "score_improvements": sum(delta > 1e-9 for delta in score_deltas),
        "score_regressions": sum(delta < -1e-9 for delta in score_deltas),
        "score_ties": sum(abs(delta) <= 1e-9 for delta in score_deltas),
        "levels_delta_total": sum(int(row["candidate_levels"]) - int(row["baseline_levels"]) for row in rows),
        "wins_delta_total": sum(int(row["candidate_wins"]) - int(row["baseline_wins"]) for row in rows),
        "no_ops_delta_total": sum(int(row["candidate_no_ops"]) - int(row["baseline_no_ops"]) for row in rows),
        "candidate_action6_guided_actions": sum(int(row["candidate_action6_guided_actions"]) for row in rows),
        "candidate_action6_predicted_candidates": sum(int(row["candidate_action6_predicted_candidates"]) for row in rows),
    }


def main() -> int:
    if OUTPUT.exists() or CHECKPOINT.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {OUTPUT} or {CHECKPOINT}")

    base = _load_agent_module().MyAgent

    class _Action6GenericQueryAgent(base):
        """Try HDS's existing action-outcome ranking for generic Action 6 only."""

        action6_query_predictions = 0
        action6_guided_selections = 0

        def _HDS状態を照会する(self, observed):
            preferred = super()._HDS状態を照会する(observed)
            if preferred or 6 not in observed.作用可能番号:
                return preferred

            # Action 6 is queried by generic action type and argument presence;
            # coordinates remain owned by the independent legal exploration policy.
            self._HDS適用範囲を保つ(observed)
            started = time.perf_counter()
            self._hds_queries += 1
            self._hds_candidate_action_queries += 1
            try:
                result = self._hds.照会する(
                    外部入力(
                        {
                            "作用前公開状態": self._HDS作用前状態(observed),
                            "作用": {"番号": 6, "引数あり": True},
                        },
                        "ARC3公開作用応答",
                        目的="公開観測から学んだAction 6の一般応答順位を照会。座標選択とAction認可には不使用",
                    )
                )
                self._hds_last_query_state = result.状態
                rank = self._HDS公開応答順位予測(result)
                if rank is None:
                    return ()
                self._hds_predicted_outcome_candidates += 1
                type(self).action6_query_predictions += 1
                self._action6_hint_for_next_action = True
                return (6,)
            except Exception as exc:
                self._hds_last_query_state = f"ERROR:{type(exc).__name__}"
                return ()
            finally:
                self._hds_query_seconds += time.perf_counter() - started

        def choose_action(self, frames, latest_frame):
            self._action6_hint_for_next_action = False
            action = super().choose_action(frames, latest_frame)
            if self._action6_hint_for_next_action and action.作用番号 == 6:
                type(self).action6_guided_selections += 1
            return action

    games, manifest = load_games()
    if len(games) != 25:
        raise RuntimeError(f"expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(SPLIT_SEED).shuffle(split)
    selected = split[:5]

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for seed in SEEDS:
        for index, (metadata, path) in enumerate(selected, start=1):
            baseline, _ = _実行する(base, metadata, path, seed=seed, max_actions=MAX_ACTIONS)
            predictions_before = _Action6GenericQueryAgent.action6_query_predictions
            guided_before = _Action6GenericQueryAgent.action6_guided_selections
            candidate, _ = _実行する(_Action6GenericQueryAgent, metadata, path, seed=seed, max_actions=MAX_ACTIONS)
            if baseline["actions"] != candidate["actions"] and not (
                baseline["stop_reason"] in ("WIN", "GAME_OVER")
                or candidate["stop_reason"] in ("WIN", "GAME_OVER")
            ):
                raise RuntimeError("paired action budget mismatch before terminal state")
            baseline_score = float(baseline["score"])
            candidate_score = float(candidate["score"])
            rows.append(
                {
                    "seed": seed,
                    "public_start_index": index,
                    "baseline_score": baseline_score,
                    "candidate_score": candidate_score,
                    "baseline_levels": int(baseline["levels"]),
                    "candidate_levels": int(candidate["levels"]),
                    "baseline_wins": int(baseline["wins"]),
                    "candidate_wins": int(candidate["wins"]),
                    "baseline_no_ops": int(baseline["no_ops"]),
                    "candidate_no_ops": int(candidate["no_ops"]),
                    "candidate_action6_guided_actions": _Action6GenericQueryAgent.action6_guided_selections - guided_before,
                    "candidate_action6_predicted_candidates": _Action6GenericQueryAgent.action6_query_predictions - predictions_before,
                    "baseline_stop_reason": baseline["stop_reason"],
                    "candidate_stop_reason": candidate["stop_reason"],
                }
            )
            with CHECKPOINT.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(rows[-1], ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    overall = _summarize(rows)
    by_seed = [
        {"seed": seed, **_summarize([row for row in rows if row["seed"] == seed])}
        for seed in SEEDS
    ]
    gates = {
        "dev_mean_delta_at_least_0_01": overall["score_delta_mean"] >= 0.01,
        "improvements_at_least_regressions": overall["score_improvements"] >= overall["score_regressions"],
        "levels_not_regressed": overall["levels_delta_total"] >= 0,
        "wins_not_regressed": overall["wins_delta_total"] >= 0,
    }
    result = {
        "schema": "arc3-hds-action6-generic-query-dev.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "paired public dev; current HDS action query versus generic Action 6 query; coordinate choice unchanged",
        "split_seed": SPLIT_SEED,
        "public_environments": 25,
        "selected_public_starts": 5,
        "seed_groups": list(SEEDS),
        "max_actions_per_episode": MAX_ACTIONS,
        "environment_metadata_manifest_sha256": manifest,
        "base_agent_source_sha256": _sha(ROOT / "接続/ARC3提出agent.py"),
        "hds_source_sha256": _sha(ROOT / "HDS/学習系統/v0.4.2/hds学習系統/__init__.py"),
        "rows": rows,
        "overall": overall,
        "by_seed": by_seed,
        "gates": gates,
        "passes_dev_gate": all(gates.values()),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_made": False,
        "runtime_modified": False,
        "interpretation": "local dev evidence only; a passing dev gate requires a fresh seed holdout and full public evaluation before any runtime promotion",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"overall": overall, "by_seed": by_seed, "gates": gates, "passes_dev_gate": result["passes_dev_gate"], "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
