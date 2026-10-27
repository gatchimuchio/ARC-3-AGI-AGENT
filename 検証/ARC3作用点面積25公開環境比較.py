"""C2-086: fixed full-schema 25-public-environment paired observer validation.

Two process-local OFFLINE SDK/native instances; uniform legal action numbers,
uniform visible coordinates conditional on Action6. HDS never chooses actions.
Both locality queries precede the actual SDK action; both teachers follow it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import statistics
import sys
import time

sys.dont_write_bytecode = True
import ARC3作用点成分面積HDS比較 as comparison

learning, replay, ROOT = comparison.learning, comparison.replay, comparison.ROOT
SEED, GAME_LIMIT, CALL_LIMIT, WORKERS = 3701, 25, 80, 2


class FullSchemaArm(comparison.OnlineArm):
    def query(self, before, action):
        content = comparison._augment(self.api._query_content(before, action), before, action, self.enriched)
        replay.base._require(learning.TARGET not in content and "公開応答区分" not in content, "query_contains_teacher")
        knowledge = replay.paired._knowledge(self.core._hds)
        self.last_native = None
        result = self.core._call("query", content)
        replay.base._require(result["bridge_status"] == "queried" and self.last_native is not None, "full_schema_query_incomplete")
        replay.base._require(replay.paired._knowledge(self.core._hds) == knowledge, "query_trained_native")
        replay.base._require(self.last_input_hash == replay.paired._digest(content), "actual_full_query_hash")
        self.query_content = content
        self.query_invariance_checks += 1
        return learning._target_summary(self.last_native)

    def update(self, before, action, after):
        content = learning._teacher(before, action, after, self.api)
        # Replace the reduced replay context with the canonical real SDK context.
        content["作用前公開状態"] = self.api._public_context(before, action)
        comparison._augment(content, before, action, self.enriched)
        result = self.core._call("update", content)
        replay.base._require(result["bridge_status"] == "updated", "full_schema_teacher_incomplete")
        replay.base._require(self.last_teacher_hash == replay.paired._digest(content), "actual_full_teacher_hash")
        self.teacher_content = content


def _query_pair(previous, current, before, action, check_budget, counts):
    check_budget()
    p = previous.query(before, action)
    check_budget()
    c = current.query(before, action)
    replay.base._require(comparison.AREA not in previous.query_content["作用前公開状態"] and type(current.query_content["作用前公開状態"].get(comparison.AREA)) is int, "one_area_query_feature")
    replay.base._require(replay.paired._digest(comparison._without_area(current.query_content)) == previous.last_input_hash, "full_queries_differ_beyond_area")
    counts["both_Action6_queries_BEFORE_SDK_action"] += 1
    return p, c


def _finish_response(previous, current, before, action, after, pending, past, scores, paired, aliases, counts, digests, check_budget):
    if action.number == 6:
        replay.base._require(pending is not None, "Action6_response_without_pre_action_queries")
        p, c = pending
        effect = learning._effect(before, action, after)
        scores.record("A", p, effect, past)
        scores.record("B", c, effect, past)
        scores.observed[effect] += 1
        paired.record(p, c, effect, past)
        aliases.record(previous.query_content, current.query_content, effect)
        counts["Action6_pairs_scored_before_both_teachers"] += 1
    else:
        effect = None
    for label, arm in (("previous", previous), ("current", current)):
        check_budget()
        arm.update(before, action, after)
        learning._feed_digest(digests[label], before, action, after)
        counts[label + "_public_updates"] += 1
    replay.base._require(replay.paired._digest(comparison._without_area(current.teacher_content)) == previous.last_teacher_hash, "full_teachers_differ_beyond_area")
    counts["same_teacher_with_only_optional_PRE_area_difference"] += 1
    if effect is not None:
        past[effect] += 1
        counts["strict_previous_Action6_counter_advanced_once_after_teachers"] += 1
    else:
        replay.base._require(comparison.AREA not in current.teacher_content["作用前公開状態"] and learning.TARGET not in current.teacher_content, "nonAction6_optional_labels_not_omitted")
        counts["nonAction6_optional_area_and_effect_omitted"] += 1
    check_budget()


def _safe_error(exc, stage):
    return {"type": type(exc).__name__, "stage": stage,
            "contract": str(exc)[:160] if isinstance(exc, replay.base.ContractError) else "external_exception_details_not_persisted"}


def _one_game(ordinal, identity, arcade, api):
    from arcengine import GameAction
    from 接続.ARC3境界 import 観測する

    def public_frame(raw, number):
        observed = 観測する(raw, 観測通番=number)
        return api.PublicFrame(observed.最新盤面, observed.状態, observed.完了レベル数, observed.作用可能番号)

    started, calls, stage = time.perf_counter(), 0, "construct"
    scores, paired, aliases = learning.Scores(), comparison.PairedPrediction(), comparison.Aliases()
    counts, errors, past = Counter(), [], Counter()
    digests = {label: hashlib.sha256() for label in ("observed", "previous", "current")}
    previous = current = None
    outcome, state = None, "ERROR"
    try:
        previous, current = FullSchemaArm("previous", api, False), FullSchemaArm("current", api, True)

        def check_budget():
            replay.base._require(previous.seconds() + current.seconds() < 120.0, "combined_HDS_120_seconds_exhausted")

        check_budget()
        env = arcade.make(identity, seed=SEED, save_recording=False, include_frame_data=True)
        replay.base._require(env is not None, "public_environment_missing")
        rng = random.Random(SEED)
        while calls < CALL_LIMIT:
            stage = "pre_action_public_frame"
            before = public_frame(env.observation_space, calls)
            if before.state == "WIN":
                state = "WIN_EARLY"
                break
            reset = before.state in {"NOT_PLAYED", "GAME_OVER"}
            if reset:
                action = api.PublicAction(0)
            else:
                legal = sorted(number for number in before.available_actions if 1 <= number <= 7)
                replay.base._require(bool(legal), "public_legal_action_set_empty")
                number = rng.choice(legal)
                action = api.PublicAction(6, rng.randrange(len(before.board[0])), rng.randrange(len(before.board))) if number == 6 else api.PublicAction(number)
            replay.base._require(api._legal(before, action), "selected_public_action_not_legal")
            pending = None
            if action.number == 6:
                stage = "native_queries_before_SDK"
                pending = _query_pair(previous, current, before, action, check_budget, counts)
                replay.base._require(public_frame(env.observation_space, calls) == before, "observer_changed_public_SDK_state")
            check_budget()
            stage = "actual_SDK_action"
            calls += 1
            counts["SDK_calls_attempted"] += 1
            data = {"x": action.x, "y": action.y} if action.number == 6 else {}
            response = env.step(GameAction.from_id(action.number), data=data)
            replay.base._require(response is not None, "actual_SDK_response_missing")
            counts["SDK_responses_received"] += 1
            after = public_frame(response, calls)
            if reset:
                counts["RESET_calls_excluded_from_learning"] += 1
                continue
            outcome = api._observed_outcome(before, after)
            counts["original_public_outcome:" + outcome] += 1
            counts["nonRESET_responses_observed"] += 1
            learning._feed_digest(digests["observed"], before, action, after)
            stage = "actual_response_scoring_and_causal_teachers"
            _finish_response(previous, current, before, action, after, pending, past, scores, paired, aliases, counts, digests, check_budget)
        else:
            state = "COMPLETE_80_CALLS"
        replay.base._require(digests["observed"].hexdigest() == digests["previous"].hexdigest() == digests["current"].hexdigest(), "complete_public_teacher_streams_differ")
    except Exception as exc:
        errors.append(_safe_error(exc, stage))
        state = "BUDGET_PARTIAL" if isinstance(exc, replay.base.ContractError) and str(exc) == "combined_HDS_120_seconds_exhausted" else "CONTRACT_OR_SDK_ERROR"
    arm_reports = scores.report()
    pair_report = paired.report()
    fallback = pair_report["fixed_offline_all_point_fallback"]
    n = fallback.get("matched_scored_points", 0)
    delta = fallback["current_minus_previous_correct"]
    direction = "UNMEASURED" if not n else "INCREASED" if delta > 0 else "DECREASED" if delta < 0 else "UNCHANGED"
    cost = {"previous": previous.cost() if previous else None, "current": current.cost() if current else None,
            "combined_actual_hds_seconds": previous.seconds() + current.seconds() if previous and current else None,
            "combined_hds_seconds_limit": 120.0}
    row = {"anonymous_ordinal": ordinal + 1, "completion": state, "SDK_calls": calls,
           "arms": {"previous": arm_reports["A"], "current": arm_reports["B"]},
           "paired_forecast_comparison": pair_report, "context_alias_analysis": aliases.report(),
           "observed_Action6_effect_counts": dict(scores.observed), "checks_and_outcomes": dict(sorted(counts.items())),
           "fallback_direction": direction, "costs": cost,
           "observation_and_teacher_stream_sha256": {name: digest.hexdigest() for name, digest in digests.items()},
           "last_public_outcome_if_partial": outcome if errors else None,
           "errors": errors, "wall_seconds": round(time.perf_counter() - started, 6)}
    print(json.dumps({"progress_anonymous_game": ordinal + 1, "completion": state, "SDK_calls": calls}, ensure_ascii=False), flush=True)
    return row, scores, paired


def _partition(ordinals):
    from arc_agi import Arcade, OperationMode

    versions = {name: importlib.metadata.version(name) for name in ("arc-agi", "arcengine")}
    replay.base._require(versions == {"arc-agi": "0.9.8", "arcengine": "0.9.3"}, "pinned_public_SDK_versions")
    initial_input_hash = replay.base._input_manifest()
    with replay.base._frozen_api() as (_, api, manifest, temporary):
        native_hashes = {}
        for name, sha in learning.NATIVE_ORIGINALS.items():
            actual = replay.base._sha(temporary / "HDS/学習系統/v0.4.2/hds学習系統" / name)
            replay.base._require(actual == sha, "original_native_source_hash")
            native_hashes[name] = actual
        arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(replay.base.ENVIRONMENTS),
                        recordings_dir=str(temporary / "disabled-recordings"))
        catalog = sorted(row.game_id for row in arcade.available_environments)
        replay.base._require(len(catalog) == len(set(catalog)) == GAME_LIMIT, "exact_25_public_environments")
        catalog_hash = replay.paired._digest(catalog)
        rows = [_one_game(ordinal, catalog[ordinal], arcade, api) for ordinal in ordinals]
        final_input_hash = replay.base._input_manifest()
        partition_errors = [] if final_input_hash == initial_input_hash else [{"type": "ContractError", "stage": "worker_source_postcheck", "contract": "public_environment_input_bytes_changed"}]
        return {"rows": rows, "partition_errors": partition_errors, "provenance": {"SDK_versions": versions, "public_environment_input_manifest_sha256": initial_input_hash,
                 "postrun_environment_input_manifest_sha256": final_input_hash,
                 "catalog_sha256": catalog_hash, "catalog_count": len(catalog), "original_native_sha256": native_hashes,
                 "frozen_bundle_sha256": replay.base.EXPECTED_BUNDLE, "frozen_bridge_sha256": replay.base.EXPECTED_BRIDGE,
                 "frozen_build_manifest_sha256": replay.base._sha(replay.base.BUILD / "build-manifest.json"),
                 "public_frame_validator_sha256": replay.base._sha(ROOT / "接続/ARC3境界.py"),
                 "actual_canonical_full_context_function": "frozen bridge._public_context/_query_content with actual available_actions"}}


def _merge_scores(total, source):
    for arm in ("A", "B"):
        total.total[arm].update(source.total[arm])
        total.native[arm].update(source.native[arm])
    for key, value in source.strata.items():
        total.strata[key].update(value)
    total.observed.update(source.observed)


def _macro(rows):
    usable = [row for row in rows if row["paired_forecast_comparison"]["fixed_offline_all_point_fallback"].get("matched_scored_points", 0)]
    output = {"games_with_matched_scored_points": len(usable), "games_without_matched_points": len(rows) - len(usable)}
    for label in ("previous", "current"):
        accuracies = [row["paired_forecast_comparison"]["fixed_offline_all_point_fallback"][label + "_accuracy"] for row in usable]
        output[label + "_fallback_accuracy_macro"] = statistics.mean(accuracies) if accuracies else None
        coverage = [row["arms"][label]["overall"]["coverage"] for row in rows if row["arms"][label]["overall"]["coverage"] is not None]
        precision = [row["arms"][label]["overall"]["precision"] for row in rows if row["arms"][label]["overall"]["precision"] is not None]
        output[label + "_native_coverage_macro"] = {"games": len(coverage), "mean": statistics.mean(coverage) if coverage else None}
        output[label + "_native_precision_macro"] = {"games": len(precision), "mean": statistics.mean(precision) if precision else None}
    output["fallback_accuracy_macro_delta"] = output["current_fallback_accuracy_macro"] - output["previous_fallback_accuracy_macro"] if usable else None
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    replay.base._require(not output.exists(), "refusing_output_overwrite")
    started, rows, provenance, errors = time.perf_counter(), [], [], []
    total_scores, total_paired = learning.Scores(), comparison.PairedPrediction()
    paths = [Path(__file__), Path(comparison.__file__), Path(learning.__file__), Path(comparison.geometry.__file__), Path(replay.base.__file__)]
    software = {path.relative_to(ROOT).as_posix(): replay.base._sha(path) for path in paths}
    try:
        replay.base._require(replay.base._sha(Path(comparison.__file__)) == "cf3f783c39501b2887eb41acba20dd865854c00fc23d21127952cda8490c91e1", "frozen_C2_084_method")
        with ProcessPoolExecutor(max_workers=WORKERS) as executor:
            futures = [executor.submit(_partition, list(range(index, GAME_LIMIT, WORKERS))) for index in range(WORKERS)]
            for future in as_completed(futures):
                result = future.result()
                provenance.append(result["provenance"])
                errors.extend(result["partition_errors"])
                for row, scores, paired in result["rows"]:
                    rows.append(row)
                    _merge_scores(total_scores, scores)
                    total_paired.raw.update(paired.raw)
                    total_paired.fallback.update(paired.fallback)
        rows.sort(key=lambda row: row["anonymous_ordinal"])
        replay.base._require(len(rows) == GAME_LIMIT and [row["anonymous_ordinal"] for row in rows] == list(range(1, GAME_LIMIT + 1)), "all_25_games_accounted")
        replay.base._require(len(provenance) == WORKERS and provenance[0] == provenance[1], "process_source_provenance_mismatch")
        replay.base._require(all(replay.base._sha(ROOT / name) == sha for name, sha in software.items()), "frozen_25game_source_changed")
    except Exception as exc:
        errors.append(_safe_error(exc, "parent_worker_or_provenance"))
    merged = total_scores.report()
    completions = Counter(row["completion"] for row in rows)
    report = {
        "schema": "arc3-full-schema-25-public-environment-native-area-observer-comparison.v1", "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "result": "FAIL" if errors else "OBSERVATIONAL_WITH_CONTROLLED_PARTIALS_OR_ERRORS" if any(row["errors"] for row in rows) else "OBSERVATIONAL_ONLY",
        "seed": SEED, "max_SDK_calls_per_game": CALL_LIMIT, "local_process_workers": WORKERS,
        "software_sha256": software, "worker_provenance": provenance,
        "full_schema_difference_from_C2_084": "actual public available_actions -> canonical 作用可能数; reduced-record5/4 reproduction is NOT expected",
        "chooser": "pergame Random(3701), uniform sorted legal action number; uniform visible x/y conditional Action6; independent of HDS output",
        "same_one_added_PRE_feature": ["作用前公開状態", comparison.AREA],
        "same_observed_locality_target": learning.TARGET,
        "first_no_prior_Action6_point_both_abstain_then_native_else_strict_previous_majority": True,
        "native_original_0_4_2_no_C2_079_patch_HOLD_and_authfalse_preserved": True,
        "micro_arms": {"previous": merged["A"], "current": merged["B"]},
        "micro_paired_forecast_comparison": total_paired.report(), "macro": _macro(rows),
        "per_game_direction_counts": dict(Counter(row["fallback_direction"] for row in rows)),
        "completion_counts": dict(completions), "observed_Action6_effect_counts": dict(total_scores.observed),
        "anonymous_game_aggregates": rows,
        "all_25_public_games_previously_reused_NEW_trajectory_not_unseen_benchmark": True,
        "controlled_pair_partial_kept_not_silently_dropped": True,
        "missing_statistics_UNKNOWN_no_invented_values": True,
        "not_action_policy_native_PASS_gameplay_score_gain_or_feature_promotion": True,
        "no_runtime_core_protected_edits_gpu_model_kaggle_or_game_internals": True,
        "no_raw_boards_absolute_coordinates_game_ids_or_action_sequences_persisted": True,
        "errors": errors, "wall_seconds": round(time.perf_counter() - started, 6),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "sha256": replay.base._sha(output), "result": report["result"], "games": len(rows), "wall_seconds": report["wall_seconds"], "errors": errors}, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
