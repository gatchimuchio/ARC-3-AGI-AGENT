"""Recompute ARC3 C2-056 v25 scores and verify paired starts against C2-046 slim."""
from __future__ import annotations
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any
from arc_agi.scorecard import EnvironmentScoreCalculator

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-056-v25-output"
CONTROL = ROOT / "出力/ARC3-RUN-003-local/C2-046/kaggle-output/slim"
STATUS = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-056-v25-status-20261025T093518Z.json"
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-056-v25-terminal-scorecard.json"
EXPECTED_CONTROL_MEAN = 19.309155943771326
START_FIELDS = ("board", "board_ascii", "level", "title", "run_status", "score", "state", "type", "reward")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value

def manifest(root: Path) -> tuple[int, int, str]:
    rows = []
    total = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        digest = sha256(path)
        size = path.stat().st_size
        total += size
        rows.append(f"{rel}\0{digest}\0{size}\n")
    return len(rows), total, hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()

def first_event(root: Path, game_key: str) -> dict[str, Any]:
    path = root / "artifacts" / f"{game_key}_p0_events.jsonl"
    with path.open(encoding="utf-8") as stream:
        row = json.loads(next(stream))
    if not isinstance(row, dict):
        raise ValueError(f"invalid first event: {path.name}")
    return row

def score_run(run: dict[str, Any]) -> float:
    actions = run.get("actions_per_level")
    baselines = run.get("base_actions_per_level")
    levels = run.get("number_of_levels")
    completed = run.get("levels_completed")
    if not isinstance(actions, list) or not isinstance(baselines, list):
        raise ValueError("missing action arrays")
    if len(actions) != len(baselines) or len(actions) != levels:
        raise ValueError("per-level arrays do not match number_of_levels")
    if type(completed) is not int or not 0 <= completed <= len(actions):
        raise ValueError("invalid completed-level count")
    if any(type(x) is not int or x < 0 for x in actions):
        raise ValueError("invalid candidate action count")
    if any(type(x) is not int or x <= 0 for x in baselines):
        raise ValueError("invalid public baseline action count")
    calculator = EnvironmentScoreCalculator()
    for idx, (count, baseline) in enumerate(zip(actions, baselines), start=1):
        calculator.add_level(level_index=idx, completed=idx <= completed,
                             actions_taken=count, baseline_actions=baseline)
    return float(calculator.to_score(include_levels=True).score)

def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite result: {OUTPUT}")
    status = load_json(STATUS)
    if status.get("version") != 25 or status.get("status") != "KernelWorkerStatus.COMPLETE":
        raise ValueError("exact version 25 is not terminal COMPLETE")
    candidate = load_json(CANDIDATE / "benchmark.json")
    control = load_json(CONTROL / "benchmark.json")
    candidate_rows = candidate.get("game_runs")
    control_rows = control.get("game_runs")
    if not isinstance(candidate_rows, list) or not isinstance(control_rows, list):
        raise ValueError("missing benchmark game_runs")
    if len(candidate_rows) != 3 or len(control_rows) != 3:
        raise ValueError("expected exactly three paired game runs")
    cand = {str(row["game_id"]): row for row in candidate_rows}
    ctrl = {str(row["game_id"]): row for row in control_rows}
    if len(cand) != 3 or len(ctrl) != 3 or set(cand) != set(ctrl):
        raise ValueError("candidate/control run key sets differ")
    paired = {}
    cand_scores, ctrl_scores = {}, {}
    checks = {}
    for key in sorted(cand):
        c, b = cand[key], ctrl[key]
        checks_for_game = {}
        ce, be = first_event(CANDIDATE, key), first_event(CONTROL, key)
        for field in START_FIELDS:
            checks_for_game[field] = field in ce and field in be and ce[field] == be[field]
        checks_for_game["all_initial_event_fields_match"] = all(checks_for_game.values())
        checks_for_game["number_of_levels_match"] = c.get("number_of_levels") == b.get("number_of_levels")
        checks_for_game["public_baseline_actions_match"] = c.get("base_actions_per_level") == b.get("base_actions_per_level")
        if not all(checks_for_game.values()):
            raise ValueError(f"initial conditions or public baseline differ for {key}: {checks_for_game}")
        cs, bs = score_run(c), score_run(b)
        if abs(cs - float(c["final_score"])) > 1e-9:
            raise ValueError(f"candidate saved score mismatch for {key}")
        if abs(bs - float(b["final_score"])) > 1e-9:
            raise ValueError(f"control saved score mismatch for {key}")
        cand_scores[key], ctrl_scores[key] = cs, bs
        paired[key] = cs - bs
        checks[key] = checks_for_game
    cand_mean = sum(cand_scores.values()) / 3
    ctrl_mean = sum(ctrl_scores.values()) / 3
    if abs(ctrl_mean - EXPECTED_CONTROL_MEAN) > 1e-9:
        raise ValueError(f"C2-046 slim reference mismatch: {ctrl_mean}")
    delta = cand_mean - ctrl_mean
    script_path = Path(__file__).resolve()
    scorer_path = Path(inspect.getsourcefile(EnvironmentScoreCalculator) or "")
    count, total_bytes, manifest_sha = manifest(CANDIDATE)
    result = {
        "schema": "arc26-arc3-private-kernel-terminal-scorecard.v1",
        "track": "ARC3",
        "experiment_id": "ARC3-RUN-003/C2-056",
        "kernel": "tecchannn/arc3-model-guided-c2-025",
        "version": 25,
        "kernel_status": status["status"],
        "status_evidence": str(STATUS.relative_to(ROOT)).replace("\\", "/"),
        "candidate_notebook_sha256": "e240d98eac956330e4f1daae8ec73ac05ba611934ce3af4c1c7f5e2f19a6c447",
        "candidate_output_directory": str(CANDIDATE.relative_to(ROOT)).replace("\\", "/"),
        "candidate_output_file_count": count,
        "candidate_output_total_bytes": total_bytes,
        "candidate_output_manifest_sha256": manifest_sha,
        "candidate_benchmark_sha256": sha256(CANDIDATE / "benchmark.json"),
        "control": "C2-046 slim",
        "control_output_directory": str(CONTROL.relative_to(ROOT)).replace("\\", "/"),
        "control_benchmark_sha256": sha256(CONTROL / "benchmark.json"),
        "score_source": "arc_agi.scorecard.EnvironmentScoreCalculator",
        "score_source_file_sha256": sha256(scorer_path),
        "scorecard_source_sha256": sha256(script_path),
        "paired_games": 3,
        "paired_start_checks": checks,
        "candidate_scores": cand_scores,
        "control_C2_046_slim_scores": ctrl_scores,
        "paired_deltas_vs_C2_046_slim": paired,
        "candidate_mean": cand_mean,
        "control_mean": ctrl_mean,
        "paired_mean_delta_vs_C2_046_slim": delta,
        "improved_unchanged_regressed": [sum(x > 1e-9 for x in paired.values()),
                                         sum(abs(x) <= 1e-9 for x in paired.values()),
                                         sum(x < -1e-9 for x in paired.values())],
        "candidate_levels_completed": sum(int(cand[k]["levels_completed"]) for k in cand),
        "control_levels_completed": sum(int(ctrl[k]["levels_completed"]) for k in ctrl),
        "candidate_total_actions": sum(sum(cand[k]["actions_per_level"]) for k in cand),
        "control_total_actions": sum(sum(ctrl[k]["actions_per_level"]) for k in ctrl),
        "candidate_run_states": {state: sum(row.get("state") == state for row in cand.values())
                                  for state in sorted({str(row.get("state")) for row in cand.values()})},
        "candidate_saved_scores_match_recomputed": True,
        "control_saved_scores_match_recomputed": True,
        "acceptance": "mean > 19.309155943771326 and paired mean delta > 0",
        "decision": "ACCEPT_LOCAL_CANDIDATE" if cand_mean > EXPECTED_CONTROL_MEAN and delta > 0 else "REJECT_C2-056",
        "official_submission_or_quota_use": False,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()