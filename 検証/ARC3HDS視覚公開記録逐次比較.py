"""C2-080: exact public visual-solver records, reduced-schema native HDS replay.

This is an observational replay, not canonical bridge replay or an action policy.
Available actions were not recorded; both update/query omit 作用可能数 entirely.
Only aggregate evidence is saved. No SDK, model, Kaggle, pickle or hidden state.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))
import ARC3HDS対象経路公開逐次比較 as paired
import ARC3視覚HDS対応採点 as integrity

base = paired.base
RETRIEVAL = ROOT / "出力/ARC3-RUN-003-local/C2-078/off-r2-terminal-v1-retrieval-20261026T232820Z.json"
OUTPUT_ROOT = ROOT / "出力/ARC3-RUN-003-local/C2-078/off-r2-terminal-v1-20261026T232820Z"
SOURCE_BUILD = ROOT / "出力/ARC3-RUN-003-local/C2-078/off-r2"
SOURCE_WRITER = ROOT / "入力/モデル実行基底/v5/taaf-source-v1/patched/src/ARC3-Inference/inference/framework/solver.py"
OUTCOMES = ("勝利", "GAME_OVER", "レベル進行", "盤面変化", "可視変化なし")


@dataclass(frozen=True)
class RecordedFrame:
    board: tuple[tuple[int, ...], ...]
    state: str
    levels_completed: int

    def __post_init__(self):
        base._require(self.state in {"NOT_PLAYED", "NOT_FINISHED", "GAME_OVER", "WIN"}, "recorded_state")
        base._require(type(self.levels_completed) is int and self.levels_completed >= 0, "recorded_public_level_count")
        board = tuple(tuple(row) for row in self.board)
        width = len(board[0]) if board else 0
        base._require(1 <= len(board) <= 64 and 1 <= width <= 64, "recorded_board_shape")
        base._require(all(len(row) == width for row in board), "recorded_board_rectangular")
        base._require(all(type(cell) is int and 0 <= cell <= 15 for row in board for cell in row), "recorded_board_colors")
        object.__setattr__(self, "board", board)


def _frame(row):
    return RecordedFrame(row["board"], row["state"], row["score"])


def _action(history, event, before, api):
    raw = history.get("action")
    base._require(isinstance(raw, dict), "structured_history_action")
    name, data = raw.get("id"), raw.get("data")
    base._require(isinstance(name, str) and re.fullmatch(r"RESET|ACTION[1-7]", name), "history_action_name")
    base._require(event.get("action_name") == name, "event_history_action_join")
    number = 0 if name == "RESET" else int(name[-1])
    if number == 6:
        base._require(isinstance(data, dict) and set(data) == {"x", "y"}, "recorded_mouse_arguments")
        action = api.PublicAction(number, data["x"], data["y"])
        base._require(0 <= action.y < len(before.board) and 0 <= action.x < len(before.board[0]), "recorded_mouse_board_bounds")
        expected_display = f"MOUSE(row={action.y}, col={action.x})"
        base._require(event.get("action_display") == expected_display, "event_history_mouse_coordinate_join")
    else:
        base._require(data is None or data == {}, "nonmouse_action_arguments")
        action = api.PublicAction(number)
    if number:
        base._require(before.state == "NOT_FINISHED", "recorded_nonreset_lifecycle")
    return action


def _parse_events(rows, history, api):
    """Read actual responses only; initial display/analysis never create transitions."""
    base._require(isinstance(history, list) and len(history) == 80, "recorded_history_eighty")
    base._require(rows and rows[0].get("type") == "initial", "recorded_initial_first")
    base._require(sum(row.get("type") == "initial" for row in rows) == 1, "recorded_single_initial")
    base._require(rows[0].get("action_num") == 0, "initial_is_not_an_action")
    before = _frame(rows[0])
    transitions, analysis = [], 0
    for row in rows[1:]:
        if row.get("type") == "analysis":
            analysis += 1
            continue
        base._require(row.get("type") == "action", "unknown_event_record_type")
        index = len(transitions)
        base._require(type(row.get("action_num")) is int and row["action_num"] == index + 1, "contiguous_recorded_action_number")
        base._require(index < len(history), "event_history_length")
        base._require("available_actions" not in row and "available_actions" not in history[index], "source_available_actions_contract")
        after = _frame(row)
        action = _action(history[index], row, before, api)
        base._require(action.number == 0 or after.state == "GAME_OVER" or after.levels_completed >= before.levels_completed, "recorded_public_levels_decrease")
        transitions.append((before, action, after))
        before = after
    base._require(len(transitions) == len(history), "complete_event_history_join")
    return transitions, analysis


def _reduced_content(frame, action, api):
    """Same known projection except explicitly absent action availability."""
    counts = Counter(cell for row in frame.board for cell in row)
    share = max(counts.values()) / sum(counts.values())
    context = {
        "色種類数": len(counts),
        "最多色占有帯": "低" if share < 0.25 else "中低" if share < 0.5 else "中高" if share < 0.75 else "高",
    }
    if action.number == 6:
        values = api._target_topology(frame.board, action.x, action.y)
        context["対象局所配置"] = "|".join(f"{direction}={value}" for (direction, _, _), value in zip(api._DIRECTIONS, values))
    return {"作用前公開状態": context, "作用": {"番号": action.number, "引数あり": action.number == 6}}


def _reduced_type(api):
    class ReducedSchemaBridge(api.VisualHDSBridge):
        def query(self, current, candidate):
            base._require(candidate.number != 0, "reset_query_forbidden")
            result = self._call("query", _reduced_content(current, candidate, api))
            result["candidate_action_number"] = candidate.number
            return result

        def update(self, before, action, after):
            base._require(action.number != 0, "reset_update_forbidden")
            content = _reduced_content(before, action, api)
            content["公開応答区分"] = api._observed_outcome(before, after)
            return self._call("update", content)

    return ReducedSchemaBridge


def _native_causes(result):
    content = result.内容
    counts = {}
    for field in ("係争中原理群", "識別不能群", "競合群", "追加観測要求群"):
        rows = content.get(field, ())
        base._require(isinstance(rows, (list, tuple)), "native_hold_cause_rows")
        counts[field] = sum(isinstance(row, dict) and tuple(row.get("結果経路", ())) == ("公開応答区分",) for row in rows)
    return counts


class ReplayBridge(paired._PairedBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.native_causes = {}
        original = self.real._hds.照会する

        def observe(value, **scope):
            result = original(value, **scope)
            label = "scoped" if scope.get("結果経路群") is not None else "whole"
            self.native_causes[label] = _native_causes(result)
            return result

        self.real._hds.照会する = observe

    def query(self, before, action):
        self.native_causes.clear()
        return super().query(before, action)


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _bucket_summary(counts):
    return {
        "counts": dict(sorted(counts.items())),
        "precision": _ratio(counts["matches"], counts["forecasts"]),
        "same_covered_strict_past_majority_precision": _ratio(counts["majority_matches"], counts["majority_comparable"]),
        "forecast_coverage": _ratio(counts["forecasts"], counts["responses"]),
    }


class Strata:
    def __init__(self):
        self.buckets = defaultdict(Counter)
        self.causes = Counter()

    def record(self, arm, result, blocked, values, outcome, previous, native_causes):
        majority, _ = base._majority(previous)
        status = str(result.get("native_status", "missing"))
        status_bucket = self.buckets[(arm, "native_status", status)]
        observed = self.buckets[(arm, "observed_class", outcome)]
        status_bucket["responses"] += 1
        observed["responses"] += 1
        for cause, count in native_causes.items():
            self.causes[f"{arm}:{cause}:count_sum"] += count
            self.causes[f"{arm}:{cause}:queries_nonzero"] += int(count > 0)
        if blocked is not None or len(values) != 1:
            return
        predicted = next(iter(values))
        for bucket in (status_bucket, observed, self.buckets[(arm, "predicted_class", predicted)]):
            bucket["forecasts"] += 1
            bucket["matches"] += int(predicted == outcome)
            if majority is not None:
                bucket["majority_comparable"] += 1
                bucket["majority_matches"] += int(majority == outcome)

    def report(self):
        result = {}
        for arm in ("whole", "scoped"):
            result[arm] = {}
            for dimension, labels in (("native_status", ("出力", "断定保留")),
                                      ("predicted_class", OUTCOMES),
                                      ("observed_class", OUTCOMES)):
                result[arm][dimension] = {label: _bucket_summary(self.buckets[(arm, dimension, label)]) for label in labels}
        return result


def _score_pair(collector, strata, previous, whole_counts, outcome):
    active = collector.current
    whole = active.pending["whole"]
    blocked, values = active.runtime._target_forecast(whole)
    for arm in ("whole", "scoped"):
        result = active.pending[arm]
        arm_blocked, arm_values = active.runtime._target_forecast(result)
        strata.record(arm, result, arm_blocked, arm_values, outcome, previous, active.native_causes.get(arm, {}))
    collector.score(previous, values, blocked, outcome, whole_counts)


def _load_inputs(api):
    doc = json.loads(RETRIEVAL.read_text(encoding="utf-8"))
    build = json.loads((SOURCE_BUILD / "build-manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((SOURCE_BUILD / "kernel-metadata.json").read_text(encoding="utf-8"))
    declared, identity = integrity.verify_retrieval(doc, OUTPUT_ROOT, build, metadata, 1)
    source_archive = SOURCE_BUILD / "visual-hds-source.zip"
    base._require(base._sha(source_archive) == build["bundle_sha256"], "recording_source_bundle_hash")
    with zipfile.ZipFile(source_archive) as archive:
        for item in build["bundle_manifest"]["files"]:
            base._require(hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"], "recording_source_member_hash")
    benchmark = json.loads((OUTPUT_ROOT / "benchmark.json").read_text(encoding="utf-8"))
    runs = benchmark.get("game_runs")
    base._require(isinstance(runs, list) and len(runs) == 3, "exact_three_recorded_runs")
    streams, counts, used = [], Counter(), set()
    for run in runs:
        identity_key = run.get("game_id")
        base._require(isinstance(identity_key, str) and identity_key not in used, "unique_source_join_key")
        used.add(identity_key)
        name = f"artifacts/{identity_key}_p0_events.jsonl"
        base._require(name in declared, "event_file_in_verified_manifest")
        rows = [json.loads(line) for line in (OUTPUT_ROOT / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        transitions, analysis = _parse_events(rows, run.get("history"), api)
        streams.append(transitions)
        counts["initial_records"] += 1
        counts["analysis_records_excluded"] += analysis
        counts["actual_action_records"] += len(transitions)
        for before, action, after in transitions:
            counts["reset_actions_excluded"] += int(action.number == 0)
            counts["nonreset_transitions"] += int(action.number != 0)
            counts["action6_coordinate_joins"] += int(action.number == 6)
            if action.number:
                counts["public_outcome:" + api._observed_outcome(before, after)] += 1
    base._require(counts["actual_action_records"] == 240 and counts["nonreset_transitions"] == 239 and counts["reset_actions_excluded"] == 1, "source_transition_counts")
    base._require(counts["public_outcome:レベル進行"] == 4 and counts["public_outcome:GAME_OVER"] == counts["public_outcome:勝利"] == 0, "source_public_outcome_audit")
    return streams, {
        "retrieval_path": RETRIEVAL.relative_to(ROOT).as_posix(),
        "retrieval_sha256": base._sha(RETRIEVAL),
        "output_manifest_sha256": doc["output_manifest_sha256"],
        "all_declared_output_files_hash_verified": len(declared),
        "all_240_action_history_joins_verified": True,
        "source_build_manifest_sha256": base._sha(SOURCE_BUILD / "build-manifest.json"),
        "source_notebook_sha256": build["output_notebook_sha256"],
        "source_metadata_sha256": build["kernel_metadata_sha256"],
        "actual_recording_source_bundle_sha256": build["bundle_sha256"],
        "recording_solver_declared_sha256_from_build": build["patched_solver_sha256"],
        "recording_solver_is_not_separate_bundle_member": True,
        "all_recording_source_members_hash_verified": len(build["bundle_manifest"]["files"]),
        "public_event_definition_original_source_sha256": base._sha(SOURCE_WRITER),
        "source_event_writer_public_levels_line": 782,
        "immediate_action_response_source_line": 1251,
        "exact_kernel_version": 1,
        "kernel_identity_verified": identity["identity_alias_applied"] is False,
        "source_counts": dict(sorted(counts.items())),
        "public_level_provenance": "event.score = int(new_state.raw.levels_completed); not benchmark RHAE/reward",
        "available_action_fields_absent": 240,
        "automatic_flags_absent": True,
        "initial_RESET_display_not_an_actual_action": True,
        "benchmark_fields_used": ["game_runs.game_id (join only)", "game_runs.history.action"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    base._require(not output.exists(), "refusing_output_overwrite")
    started = time.perf_counter()
    collector, strata, whole_counts = paired._Collector(), Strata(), Counter()
    errors, costs, priors, source, native_proof = [], [], Counter(), {}, {}
    software_paths = [Path(__file__), Path(paired.__file__), Path(base.__file__), Path(integrity.__file__)]
    software = {p.relative_to(ROOT).as_posix(): base._sha(p) for p in software_paths}
    try:
        base._require(software[Path(paired.__file__).relative_to(ROOT).as_posix()] == "861bce445f9f4342952dd8394d418990c2a6ba3d201bc2e3d3a1b62bba0527cc", "frozen_paired_reducer_source")
        with base._frozen_api() as (runtime, api, manifest, temporary):
            streams, source = _load_inputs(api)
            if not args.contract_only:
                native_proof = paired._apply_candidate(temporary)
                api = importlib.reload(api)
                runtime._API = api
                proxy = SimpleNamespace(**{name: getattr(api, name) for name in dir(api) if not name.startswith("__")})
                proxy._query_content = lambda frame, action: _reduced_content(frame, action, api)
                reduced_type = _reduced_type(api)
                for transitions in streams:
                    bridge = ReplayBridge(reduced_type, proxy, runtime, collector, update_budget=80, query_budget=80, hds_seconds_budget=120.0)
                    base._require(bridge.prior_report["loaded_count"] == 5, "five_priors_loaded")
                    priors[bridge.prior_report["load_status"]] += 1
                    previous = Counter()
                    for before, action, after in transitions:
                        if action.number == 0:
                            whole_counts["resets_excluded"] += 1
                            continue
                        query = bridge.query(before, action)
                        base._require(query["bridge_status"] not in {"hds_error", "summary_error", "rejected"}, "replay_whole_query_error")
                        base._require(bridge.pending["scoped"]["bridge_status"] not in {"hds_error", "summary_error", "rejected"}, "replay_scoped_query_error")
                        outcome = api._observed_outcome(before, after)
                        _score_pair(collector, strata, previous, whole_counts, outcome)
                        update = bridge.update(before, action, after)
                        base._require(update["bridge_status"] not in {"hds_error", "summary_error", "rejected"}, "replay_update_error")
                    costs.append(bridge.cost())
                base._require(collector.pairs["identical_strictly_previous_majority_counter_steps"] == 239, "all_replay_steps_scored_once")
        base._require(all(base._sha(ROOT / name) == sha for name, sha in software.items()), "diagnostic_source_changed_during_run")
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "contract": str(exc)[:160]})
    report = {
        "schema": "arc3-visual-public-trace-reduced-schema-native-paired-replay.v1",
        "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "result": "FAIL" if errors else "CONTRACT_ONLY" if args.contract_only else "OBSERVATIONAL_ONLY",
        "source": source,
        "software_sha256": software,
        "frozen_bundle_sha256": base.EXPECTED_BUNDLE,
        "frozen_bridge_sha256": base.EXPECTED_BRIDGE,
        "frozen_runtime_qualifier_sha256": base.EXPECTED_RUNTIME,
        "native_scope_patch_sha256": paired.PATCH_SHA,
        "native_default_compatibility_proof_sha256": paired.PROOF_SHA,
        "native_default_whole_compatibility_preserved": native_proof.get("whole_query_full_structure_matches_frozen_original"),
        "schema_limitation": "Declared reduced schema: omit 作用可能数 from BOTH query/update; no available actions invented; not canonical bridge replay",
        "shared_before_action_after_stream_sha256": collector.stream.hexdigest() if collector.bridges else None,
        "whole": paired._summary(whole_counts),
        "scoped": paired._summary(collector.scoped_counts),
        "stratified_from_first_response": strata.report(),
        "native_target_hold_causes": dict(sorted(strata.causes.items())),
        "paired_checks": dict(sorted(collector.pairs.items())),
        "shared_and_per_arm_costs": costs,
        "prior_load_status_counts": dict(priors),
        "partial_bridge_stats_if_failure": [bridge.stats for bridge in collector.bridges] if errors else [],
        "errors": errors,
        "wall_seconds": round(time.perf_counter() - started, 6),
        "no_canonical_hds_bridge_runtime_or_notebook_edits": True,
        "no_sdk_model_kaggle_gpu_calls": True,
        "no_game_ids_boards_coordinates_or_action_sequences_persisted": True,
        "all_public_games_reused": True,
        "not_closed_loop_score_or_causal_action_improvement_proof": True,
        "no_causal_comparison_with_random_policy_diagnostic": True,
        "native_HOLD_and_authorization_unchanged": True,
        "scope_and_strata_add_no_applicability_filter": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "sha256": base._sha(output), "result": report["result"], "errors": errors, "wall_seconds": report["wall_seconds"]}, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
