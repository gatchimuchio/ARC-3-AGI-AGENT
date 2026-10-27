"""C2-084: one exact PRE-target component-area feature, same native teacher stream.

Offline forecast comparison only. Native HOLD/authorization stay intact. Fixed
fallback is guarded native prediction else strictly previous Action6 majority;
without any previous Action6 effect both arms abstain.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import ARC3作用点効果HDS学習診断 as learning
import ARC3公開画素効果診断 as geometry

replay, ROOT = learning.replay, learning.ROOT
AREA = "作用点同色4連結成分面積"
REFERENCE = ROOT / "運用/証拠/ARC26-UNIFIED/C2-083_action6-locality-prior-vs-online-native.json"
REFERENCE_SHA = "1ddc5a2b43a06710984a482f80f0d0384894b7265cb1a79e93f7e0560549ed05"


def _area(before, action):
    replay.base._require(action.number == 6, "component_area_nonAction6")
    for components in geometry._components(before.board).values():
        for _, _, cells in components:
            if (action.x, action.y) in cells:
                return len(cells)
    raise replay.base.ContractError("target_component_not_found")


def _augment(content, before, action, enriched):
    if enriched and action.number == 6:
        content["作用前公開状態"][AREA] = _area(before, action)
    return content


def _without_area(content):
    result = dict(content)
    result["作用前公開状態"] = dict(result["作用前公開状態"])
    result["作用前公開状態"].pop(AREA, None)
    return result


class OnlineArm(learning.Arm):
    def __init__(self, label, api, enriched):
        # Both are online B learners; the historical Arm name A is prior-only.
        super().__init__("B", api, 80)
        self.label, self.enriched = label, enriched
        self.query_content, self.teacher_content = None, None
        self.last_teacher_hash = None
        original = self.core._hds.処理する

        def observed_teacher(value):
            self.last_teacher_hash = replay.paired._digest(value.内容)
            result = original(value)
            replay.base._require(self.last_teacher_hash == replay.paired._digest(value.内容), "native_teacher_input_mutation")
            return result

        self.core._hds.処理する = observed_teacher

    def query(self, before, action):
        content = _augment(replay._reduced_content(before, action, self.api), before, action, self.enriched)
        replay.base._require(learning.TARGET not in content and "公開応答区分" not in content, "query_contains_future_teacher")
        knowledge = replay.paired._knowledge(self.core._hds)
        self.last_native = None
        result = self.core._call("query", content)
        replay.base._require(result["bridge_status"] == "queried" and self.last_native is not None, "online_query_incomplete")
        replay.base._require(replay.paired._knowledge(self.core._hds) == knowledge, "query_changed_online_memory")
        replay.base._require(self.last_input_hash == replay.paired._digest(content), "actual_query_content_hash")
        self.query_content = content
        self.query_invariance_checks += 1
        return learning._target_summary(self.last_native)

    def update(self, before, action, after):
        content = _augment(learning._teacher(before, action, after, self.api), before, action, self.enriched)
        result = self.core._call("update", content)
        replay.base._require(result["bridge_status"] == "updated", "online_teacher_incomplete")
        replay.base._require(self.last_teacher_hash == replay.paired._digest(content), "actual_teacher_content_hash")
        self.teacher_content = content

    def cost(self):
        result = super().cost()
        result["arm"] = self.label
        result["one_additional_PRE_area_feature"] = self.enriched
        return result


def _unique(result):
    return next(iter(result["forecast_values"])) if result["forecast_blocked"] is None and len(result["forecast_values"]) == 1 else None


class PairedPrediction:
    def __init__(self):
        self.raw, self.fallback = Counter(), Counter()

    def record(self, previous, current, effect, past):
        p, c = _unique(previous), _unique(current)
        majority = learning._majority(past)
        self.raw["same_Action6_points"] += 1
        if p is not None and c is not None:
            self.raw["common_native_covered"] += 1
            self.raw["previous_correct_on_common"] += int(p == effect)
            self.raw["current_correct_on_common"] += int(c == effect)
            self.raw["value_agreement_on_common"] += int(p == c)
            if majority is not None:
                self.raw["common_with_strict_previous_majority"] += 1
                self.raw["strict_previous_majority_correct_on_common"] += int(majority == effect)
        else:
            self.raw["previous_only_native_covered"] += int(p is not None)
            self.raw["current_only_native_covered"] += int(c is not None)
            self.raw["neither_native_covered"] += int(p is None and c is None)
        self.fallback["same_Action6_points"] += 1
        if majority is None:
            self.fallback["both_abstain_no_prior_Action6_effect"] += 1
            return
        self.fallback["matched_scored_points"] += 1
        self.fallback["strict_previous_majority_correct"] += int(majority == effect)
        for label, value in (("previous", p), ("current", c)):
            self.fallback[label + "_native_used"] += int(value is not None)
            self.fallback[label + "_majority_fallback_used"] += int(value is None)
            prediction = majority if value is None else value
            self.fallback[label + "_correct"] += int(prediction == effect)

    def report(self):
        raw, fallback = dict(sorted(self.raw.items())), dict(sorted(self.fallback.items()))
        raw["current_minus_previous_correct_on_common"] = self.raw["current_correct_on_common"] - self.raw["previous_correct_on_common"]
        fallback["current_minus_previous_correct"] = self.fallback["current_correct"] - self.fallback["previous_correct"]
        n = self.fallback["matched_scored_points"]
        fallback["previous_accuracy"] = self.fallback["previous_correct"] / n if n else None
        fallback["current_accuracy"] = self.fallback["current_correct"] / n if n else None
        return {"raw_common_covered": raw, "fixed_offline_all_point_fallback": fallback}


class Aliases:
    def __init__(self):
        self.groups = {"previous": defaultdict(Counter), "current": defaultdict(Counter)}
        self.areas_by_previous_context = defaultdict(set)

    def record(self, previous_content, current_content, effect):
        p, c = replay.paired._digest(previous_content), replay.paired._digest(current_content)
        self.groups["previous"][p][effect] += 1
        self.groups["current"][c][effect] += 1
        self.areas_by_previous_context[p].add(current_content["作用前公開状態"][AREA])

    def report(self):
        output = {}
        for label, groups in self.groups.items():
            output[label] = {"distinct_contexts": len(groups), "mixed_effect_contexts": sum(len(labels) > 1 for labels in groups.values()),
                             "points_in_mixed_effect_contexts": sum(sum(labels.values()) for labels in groups.values() if len(labels) > 1),
                             "context_support_histogram": dict(sorted(Counter(sum(labels.values()) for labels in groups.values()).items()))}
        output["previous_contexts_split_into_multiple_areas"] = sum(len(areas) > 1 for areas in self.areas_by_previous_context.values())
        output["diagnostic_only_no_oracle_predictions_or_group_keys_saved"] = True
        return output


def _step(previous, current, before, action, after, past, scores, paired, aliases, counts, digests, check_budget):
    if action.number == 6:
        check_budget()
        p = previous.query(before, action)
        check_budget()
        c = current.query(before, action)
        replay.base._require(AREA not in previous.query_content["作用前公開状態"] and type(current.query_content["作用前公開状態"].get(AREA)) is int, "single_area_feature_contract")
        replay.base._require(replay.paired._digest(_without_area(current.query_content)) == previous.last_input_hash, "query_diff_exceeds_one_area_feature")
        counts["same_query_point_only_one_PRE_area_difference"] += 1
        effect = learning._effect(before, action, after)
        scores.record("A", p, effect, past)
        scores.record("B", c, effect, past)
        scores.observed[effect] += 1
        paired.record(p, c, effect, past)
        aliases.record(previous.query_content, current.query_content, effect)
        counts["both_queries_and_scores_before_teachers"] += 1
    else:
        effect = None
    for label, arm in (("previous", previous), ("current", current)):
        check_budget()
        arm.update(before, action, after)
        learning._feed_digest(digests[label], before, action, after)
        counts[label + "_updates"] += 1
    replay.base._require(replay.paired._digest(_without_area(current.teacher_content)) == previous.last_teacher_hash, "teacher_diff_exceeds_one_PRE_area_feature")
    counts["same_teacher_only_one_optional_PRE_area_difference"] += 1
    if action.number != 6:
        replay.base._require(AREA not in current.teacher_content["作用前公開状態"] and learning.TARGET not in current.teacher_content, "nonAction6_optional_fields_present")
        counts["nonAction6_area_and_effect_omitted"] += 1
    else:
        past[effect] += 1
        counts["past_Action6_effect_added_once_after_both_teachers"] += 1
    check_budget()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    replay.base._require(not output.exists(), "refusing_output_overwrite")
    started, errors, source, costs = time.perf_counter(), [], {}, []
    scores, paired, aliases, counts = learning.Scores(), PairedPrediction(), Aliases(), Counter()
    digests = {label: hashlib.sha256() for label in ("input", "previous", "current")}
    software_paths = [Path(__file__), Path(learning.__file__), Path(geometry.__file__), Path(replay.__file__), Path(replay.integrity.__file__)]
    software = {p.relative_to(ROOT).as_posix(): replay.base._sha(p) for p in software_paths}
    reproduction, native_hashes = {"status": "UNKNOWN_INCOMPLETE"}, {}
    try:
        replay.base._require(replay.base._sha(Path(learning.__file__)) == "331245be4dbffb17826fecc081c38ec68957e22992163e763cf97c6bfbb69dff", "frozen_C2_083_source")
        replay.base._require(replay.base._sha(Path(geometry.__file__)) == "003cbbae82e6da73919341496faaab47ad353fd6a2f9b1697375a4b5aea10d7c", "frozen_component_source")
        replay.base._require(replay.base._sha(REFERENCE) == REFERENCE_SHA, "C2_083_reference_hash")
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        build = json.loads((replay.SOURCE_BUILD / "build-manifest.json").read_text(encoding="utf-8"))
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "submission.ipynb") == build["output_notebook_sha256"], "actual_source_notebook_hash")
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "kernel-metadata.json") == build["kernel_metadata_sha256"], "actual_source_metadata_hash")
        with replay.base._frozen_api() as (_, api, _, temporary):
            for name, sha in learning.NATIVE_ORIGINALS.items():
                actual = replay.base._sha(temporary / "HDS/学習系統/v0.4.2/hds学習系統" / name)
                replay.base._require(actual == sha, "original_canonical_native_source")
                native_hashes[name] = actual
            streams, source = replay._load_inputs(api)
            for transitions in streams:
                for before, action, after in transitions:
                    if action.number:
                        learning._feed_digest(digests["input"], before, action, after)
            replay.base._require(digests["input"].hexdigest() == learning.EXPECTED_STREAM, "exact_verified_public_stream")
            for transitions in streams:
                previous, current = OnlineArm("previous", api, False), OnlineArm("current", api, True)

                def check_budget():
                    replay.base._require(previous.seconds() + current.seconds() < 120.0, "combined_HDS_120_seconds_exhausted")

                past = Counter()
                try:
                    check_budget()
                    for before, action, after in transitions:
                        if action.number == 0:
                            counts["RESET_excluded"] += 1
                            continue
                        _step(previous, current, before, action, after, past, scores, paired, aliases, counts, digests, check_budget)
                finally:
                    costs.append({"previous": previous.cost(), "current": current.cost(),
                                  "combined_actual_hds_seconds": previous.seconds() + current.seconds(),
                                  "combined_hds_seconds_limit": 120.0, "time_budget_exhausted": previous.seconds() + current.seconds() >= 120.0})
            replay.base._require(counts["previous_updates"] == counts["current_updates"] == 239 and counts["both_queries_and_scores_before_teachers"] == 80, "complete_paired_learning_stream")
            replay.base._require(digests["previous"].hexdigest() == digests["current"].hexdigest() == learning.EXPECTED_STREAM, "identical_complete_teacher_source_streams")
        measured = scores.report()["A"]["overall"]
        expected = reference["arms"]["B"]["overall"]
        reproduction = {"status": "MATCHED" if measured == expected else "FAIL", "previous_measured": measured,
                        "frozen_C2_083_expected": expected}
        replay.base._require(measured == expected, "frozen_C2_083_baseline_not_reproduced")
        replay.base._require(all(replay.base._sha(ROOT / name) == sha for name, sha in software.items()), "C2_084_source_drift")
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "contract": str(exc)[:160]})
    raw = scores.report()
    report = {
        "schema": "arc3-native-locality-learning-one-PRE-component-area-comparison.v1", "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(), "result": "FAIL" if errors else "OBSERVATIONAL_ONLY",
        "software_sha256": software, "source": source, "original_native_source_sha256": native_hashes,
        "C2_083_reference_sha256": REFERENCE_SHA, "baseline_reproduction": reproduction,
        "additional_feature": {"path": ["作用前公開状態", AREA], "definition": "exact pixel area of4-connected same-color component containing PRE-action Action6 target", "nonAction6": "omitted", "thresholds_bins_shapes_directions_color_ids": False},
        "fallback_preregistered_before_results": "Without prior Action6 effect BOTH abstain; otherwise guarded unique native effect forecast, else STRICTLYprevious Action6 effect majority with C2-083 fixed tie order",
        "fallback_is_offline_diagnostic_not_native_PASS_or_action_policy": True,
        "arms": {"previous": raw["A"], "current": raw["B"]},
        "paired_forecast_comparison": paired.report(),
        "observational_context_alias_analysis": aliases.report(),
        "observed_Action6_effect_counts": dict(scores.observed),
        "causal_and_one_feature_checks": dict(sorted(counts.items())),
        "source_and_teacher_stream_sha256": {label: digest.hexdigest() for label, digest in digests.items()},
        "shared_and_per_arm_costs": costs,
        "native_HOLD_action_authorization_false_and_missing_statistics_UNKNOWN_preserved": True,
        "C2_079_native_patch_applied": False,
        "original_public_outcome_and_locality_teacher_preserved": True,
        "observed_class_precision_is_accuracy_on_covered_steps_of_that_true_class": True,
        "no_raw_boards_absolute_coordinates_game_ids_action_sequences_context_keys_or_shapes_persisted": True,
        "no_runtime_core_protected_edits_gpu_model_sdk_kaggle_or_game_internals": True,
        "not_gameplay_score_gain_or_feature_promotion_proof": True,
        "all_public_games_reused": True,
        "budget_can_overrun_one_inflight_native_call": True,
        "errors": errors, "wall_seconds": round(time.perf_counter() - started, 6),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "sha256": replay.base._sha(output), "result": report["result"], "errors": errors, "wall_seconds": report["wall_seconds"]}, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
