"""Compare fresh exploration after GAME_OVER with retained online statistics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASELINE_RUNNER = ROOT / "検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py"
CONTROL_EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-112/fresh-exploration-after-game-over-paired.json"
MAX_ACTIONS = 80
SEED_STRIDE = 104729


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_hash(run: dict[str, Any]) -> str:
    start = {
        key: run[key]
        for key in (
            "initial_state",
            "initial_levels_completed",
            "initial_available_actions",
            "initial_board",
        )
    }
    payload = json.dumps(start, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fresh_policy_type(base_policy: type, base_init: Any) -> type:
    class FreshExplorationAfterGameOver(base_policy):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._base_policy_seed = kwargs.get("乱数種")
            self._game_over_attempt = 0
            super().__init__(*args, **kwargs)

        def 選ぶ(self, 現在: Any) -> Any:
            if 現在.状態 == "GAME_OVER":
                self._game_over_attempt += 1
                seed = self._base_policy_seed
                if seed is None:
                    seed = 0
                base_init(
                    self,
                    乱数種=seed + SEED_STRIDE * self._game_over_attempt,
                    探索係数=0.8,
                    色探索係数=None,
                    可視変化係数=0.25,
                    レベル進行報酬=4.0,
                    座標Action初手優先=False,
                    同盤無変化Action回避=False,
                )
            return super().選ぶ(現在)

    return FreshExplorationAfterGameOver


def evaluate() -> dict[str, Any]:
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    base_policy = experiment["_CurrentHDSRankingPolicy"]
    policy_type = _fresh_policy_type(
        base_policy, experiment["観測駆動探索方針"].__init__
    )
    control_pairs = {
        (pair["seed"], pair["game_id"]): pair
        for pair in control["results"]["pairs"]
    }

    pairs: list[dict[str, Any]] = []
    for (seed, game_id), control_pair in control_pairs.items():
        metadata_path = ROOT / "入力/Kaggle/environment_files" / game_id.split("-")[0] / game_id.split("-")[1] / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        run = run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=seed,
            policy_seed=seed,
            max_actions=MAX_ACTIONS,
            retry_game_over=True,
            exploration_coefficient=0.8,
            coordinate_color_exploration_coefficient=None,
            visible_change_coefficient=0.25,
            level_progress_reward=4.0,
            policy_type_override=policy_type,
        )
        score, levels, level_details = score_game(
            metadata.get("baseline_actions", []), run
        )
        candidate = {
            "start_sha256": _start_hash(run),
            "score": score,
            "levels": levels,
            "actions": run["actions"],
            "gameplay_actions": run["gameplay_actions"],
            "reset_actions": run["reset_actions"],
            "attempts": run["attempts"],
            "game_over_events": run["game_over_events"],
            "no_op_actions": run["no_op_actions"],
            "illegal_action_attempts": run["illegal_action_attempts"],
            "final_state": run["final_state"],
            "stop_reason": run["stop_reason"],
            "level_details": level_details,
        }
        previous = {
            key: control_pair["candidate"][key]
            for key in (
                "start_sha256",
                "score",
                "levels",
                "actions",
                "gameplay_actions",
                "reset_actions",
                "attempts",
                "game_over_events",
                "no_op_actions",
                "illegal_action_attempts",
                "final_state",
                "stop_reason",
                "level_details",
            )
        }
        pairs.append(
            {
                "seed": seed,
                "game_id": game_id,
                "matched_start": previous["start_sha256"] == candidate["start_sha256"],
                "previous": previous,
                "candidate": candidate,
                "score_delta": candidate["score"] - previous["score"],
                "levels_delta": candidate["levels"] - previous["levels"],
                "actions_delta": candidate["actions"] - previous["actions"],
                "reset_actions_delta": candidate["reset_actions"] - previous["reset_actions"],
            }
        )

    deltas = [pair["score_delta"] for pair in pairs]
    summary = {
        "pairs": len(pairs),
        "matched_start_pairs": sum(pair["matched_start"] for pair in pairs),
        "mean_previous": sum(pair["previous"]["score"] for pair in pairs) / len(pairs),
        "mean_candidate": sum(pair["candidate"]["score"] for pair in pairs) / len(pairs),
        "mean_delta": sum(deltas) / len(deltas),
        "positive_pairs": sum(delta > 0 for delta in deltas),
        "negative_pairs": sum(delta < 0 for delta in deltas),
        "tied_pairs": sum(delta == 0 for delta in deltas),
        "levels_delta": sum(pair["levels_delta"] for pair in pairs),
        "wins_delta": sum(
            int(pair["candidate"]["final_state"] == "WIN")
            - int(pair["previous"]["final_state"] == "WIN")
            for pair in pairs
        ),
        "actions_previous": sum(pair["previous"]["actions"] for pair in pairs),
        "actions_candidate": sum(pair["candidate"]["actions"] for pair in pairs),
        "resets_previous": sum(pair["previous"]["reset_actions"] for pair in pairs),
        "resets_candidate": sum(pair["candidate"]["reset_actions"] for pair in pairs),
        "noops_previous": sum(pair["previous"]["no_op_actions"] for pair in pairs),
        "noops_candidate": sum(pair["candidate"]["no_op_actions"] for pair in pairs),
        "illegal_actions": sum(
            pair["candidate"]["illegal_action_attempts"] for pair in pairs
        ),
    }
    return {
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": sorted({pair["seed"] for pair in pairs}),
        "dev_games": list(dict.fromkeys(pair["game_id"] for pair in pairs)),
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "seed_stride_after_each_GAME_OVER": SEED_STRIDE,
        "baseline": "RESET after GAME_OVER; retain action/coordinate/color UCB statistics and RNG stream.",
        "candidate": "RESET after GAME_OVER; reset action/coordinate/color UCB statistics and use a deterministic fresh RNG seed per attempt; retain HDS memory and public response updates.",
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "holdout_or_promotion_if_gate_fails": False,
        },
        "summary": summary,
        "pairs": pairs,
        "runner_file": Path(__file__).relative_to(ROOT).as_posix(),
        "runner_sha256": _sha256(Path(__file__)),
        "baseline_runner_file": BASELINE_RUNNER.relative_to(ROOT).as_posix(),
        "baseline_runner_sha256": _sha256(BASELINE_RUNNER),
    }


def main() -> None:
    payload = json.dumps(evaluate(), ensure_ascii=False, indent=2)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "sha256": _sha256(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
