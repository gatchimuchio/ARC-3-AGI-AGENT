"""C2-083: prior-only versus causal native learning of visible Action6 locality.

Frozen canonical 0.4.2 only. No scoped-native patch or runtime promotion. Queries
use unchanged C2-080 reduced before-features; teacher locality follows the actual
public response and never labels remote-only changes as failure/no-op/HUD.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import ARC3HDS視覚公開記録逐次比較 as replay

ROOT = replay.ROOT
TARGET = "公開作用点効果区分"
EFFECT_BY_FLAGS = {
    (False, False): "局所なし・局所以外なし",
    (False, True): "局所なし・局所以外あり",
    (True, False): "局所あり・局所以外なし",
    (True, True): "局所あり・局所以外あり",
}
EFFECT_ORDER = tuple(EFFECT_BY_FLAGS.values())
EXPECTED_STREAM = "c583f71ec531d9f1a5858ef465d8dc0a55dc76ace50ca8190a58167794d2892e"
NATIVE_ORIGINALS = {
    "系統.py": "f57e34fcab9249ad7fef72d7b9088fbb440c01afcd4313c9447b7a31427bd4a5",
    "実行系.py": "11d253705181873bcc22e312a0d0a2198fe16a82e3d7289ea8746fdc14695429",
}


def _effect(before, action, after):
    if action.number != 6:
        return None
    replay.base._require(len(before.board) == len(after.board) and len(before.board[0]) == len(after.board[0]), "locality_board_dimensions")
    local = remote = 0
    for y, row in enumerate(before.board):
        for x, cell in enumerate(row):
            if cell != after.board[y][x]:
                if abs(x - action.x) <= 3 and abs(y - action.y) <= 3:
                    local += 1
                else:
                    remote += 1
    return EFFECT_BY_FLAGS[(local > 0, remote > 0)]


def _teacher(before, action, after, api):
    content = replay._reduced_content(before, action, api)
    content["公開応答区分"] = api._observed_outcome(before, after)
    effect = _effect(before, action, after)
    if effect is not None:
        content[TARGET] = effect
    return content


def _feed_digest(digest, before, action, after):
    value = {"before": asdict(before), "action": asdict(action), "after": asdict(after)}
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest.update(len(data).to_bytes(8, "big"))
    digest.update(data)


def _target_summary(native):
    content = native.内容
    replay.base._require(isinstance(content, dict), "native_content_shape")

    def rows(field):
        value = content.get(field)
        if not isinstance(value, (list, tuple)) or any(not isinstance(row, dict) for row in value):
            return None
        return [row for row in value if tuple(row.get("結果経路", ())) == (TARGET,)]

    fields = {name: rows(name) for name in ("予測群", "有効原理群", "競合群", "追加観測要求群", "係争中原理群", "識別不能群")}
    counts = {name: len(value) if value is not None else None for name, value in fields.items()}
    status = getattr(native, "状態", None)
    holds = content.get("断定保留理由群")
    holds = list(holds) if isinstance(holds, (list, tuple)) and all(isinstance(reason, str) for reason in holds) else None
    blocked, values = None, set()
    if status not in {"出力", "断定保留"}:
        blocked = "unknown_native_status"
    elif any(value is None for value in fields.values()):
        blocked = "UNKNOWN_target_statistics"
    elif counts["競合群"]:
        blocked = "native_target_conflict"
    elif counts["追加観測要求群"]:
        blocked = "native_target_observation_request"
    else:
        refs = {row["原理識別子"] for row in fields["有効原理群"]
                if row.get("状態") == "適用範囲付き暫定原理" and row.get("採用状態") == "有効"
                and isinstance(row.get("原理識別子"), str) and row["原理識別子"]}
        values = {row["予測値"] for row in fields["予測群"]
                  if row.get("原理参照") in refs and isinstance(row.get("予測値"), str)
                  and row["予測値"] in EFFECT_ORDER}
        if not refs:
            blocked = "no_active_adopted_target_rule"
        elif len(values) != 1:
            blocked = "no_unique_linked_native_effect_prediction"
    return {"native_status": status, "native_hold_reasons": holds, "target_counts": counts,
            "forecast_blocked": blocked, "forecast_values": values,
            "action_authorization": False}


class Arm:
    def __init__(self, name, api, update_budget):
        self.name, self.api = name, api
        self.core = api.VisualHDSBridge(update_budget=update_budget, query_budget=80, hds_seconds_budget=120.0)
        replay.base._require(self.core.prior_report.get("loaded_count") == 5, "five_prior_records")
        self.prior_knowledge = replay.paired._knowledge(self.core._hds)
        self.last_native = None
        self.last_input_hash = None
        self.query_invariance_checks = 0
        original = self.core._hds.照会する

        def capture(value):
            self.last_input_hash = replay.paired._digest(value.内容)
            native = original(value)
            replay.base._require(self.last_input_hash == replay.paired._digest(value.内容), "native_query_input_mutation")
            self.last_native = native
            return native

        self.core._hds.照会する = capture

    def query(self, before, action):
        content = replay._reduced_content(before, action, self.api)
        replay.base._require(TARGET not in content and "公開応答区分" not in content, "query_contains_teacher")
        knowledge = replay.paired._knowledge(self.core._hds)
        if self.name == "A":
            replay.base._require(knowledge == self.prior_knowledge, "prior_only_memory_changed")
        self.last_native = None
        result = self.core._call("query", content)
        replay.base._require(result["bridge_status"] == "queried" and self.last_native is not None, "native_query_not_completed")
        replay.base._require(replay.paired._knowledge(self.core._hds) == knowledge, "query_changed_learned_memory")
        self.query_invariance_checks += 1
        return _target_summary(self.last_native)

    def update(self, before, action, after):
        replay.base._require(self.name == "B", "prior_only_teacher_forbidden")
        content = _teacher(before, action, after, self.api)
        result = self.core._call("update", content)
        replay.base._require(result["bridge_status"] == "updated", "native_update_not_completed")

    def seconds(self):
        return sum(self.core._seconds.values())

    def cost(self):
        return {"arm": self.name, "stats": self.core.stats, "prior_report": self.core.prior_report,
                "query_memory_invariance_checks": self.query_invariance_checks,
                "prior_only_memory_unchanged": replay.paired._knowledge(self.core._hds) == self.prior_knowledge if self.name == "A" else None}


def _majority(previous):
    if not previous:
        return None
    maximum = max(previous.values())
    return next(value for value in EFFECT_ORDER if previous[value] == maximum)


def _metric(counts):
    forecasts, comparable = counts["forecasts"], counts["same_covered_with_previous_majority"]
    return {"counts": dict(sorted(counts.items())),
            "coverage": forecasts / counts["queries"] if counts["queries"] else None,
            "precision": counts["matches"] / forecasts if forecasts else None,
            "precision_status": "MEASURED" if forecasts else "UNMEASURED",
            "same_covered_strict_previous_majority_precision": counts["previous_majority_matches"] / comparable if comparable else None,
            "majority_precision_status": "MEASURED" if comparable else "UNMEASURED"}


class Scores:
    def __init__(self):
        self.total = {name: Counter() for name in ("A", "B")}
        self.strata = defaultdict(Counter)
        self.native = {name: Counter() for name in ("A", "B")}
        self.observed = Counter()

    def record(self, name, result, effect, previous):
        majority = _majority(previous)
        values, blocked = result["forecast_values"], result["forecast_blocked"]
        status = str(result["native_status"])
        buckets = [self.total[name], self.strata[(name, "native_status", status)], self.strata[(name, "observed_class", effect)]]
        self.native[name]["status:" + status] += 1
        reasons = result["native_hold_reasons"]
        if reasons is None:
            self.native[name]["UNKNOWN_native_hold_reasons"] += 1
        else:
            for reason in reasons:
                self.native[name]["hold_reason:" + reason] += 1
        for field, count in result["target_counts"].items():
            if count is None:
                self.native[name]["UNKNOWN_target_count:" + field] += 1
            else:
                self.native[name]["target_count_sum:" + field] += count
                self.native[name]["target_queries_nonzero:" + field] += int(count > 0)
        for bucket in buckets:
            bucket["queries"] += 1
        if blocked is not None or len(values) != 1:
            self.total[name]["blocked:" + str(blocked)] += 1
            return
        predicted = next(iter(values))
        buckets.append(self.strata[(name, "predicted_class", predicted)])
        for bucket in buckets:
            bucket["forecasts"] += 1
            bucket["matches"] += int(predicted == effect)
            if majority is not None:
                bucket["same_covered_with_previous_majority"] += 1
                bucket["previous_majority_matches"] += int(majority == effect)

    def report(self):
        return {name: {"overall": _metric(self.total[name]), "native_counts": dict(sorted(self.native[name].items())),
                       "strata": {dimension: {label: _metric(self.strata[(name, dimension, label)]) for label in labels}
                                  for dimension, labels in (("native_status", ("出力", "断定保留")), ("predicted_class", EFFECT_ORDER), ("observed_class", EFFECT_ORDER))}}
                for name in ("A", "B")}


def _step(a, b, before, action, after, previous, scores, counts, check_budget):
    """The sole learning-order boundary, including all scoring before the teacher."""
    if action.number == 6:
        check_budget()
        frozen = a.query(before, action)
        check_budget()
        online = b.query(before, action)
        replay.base._require(a.last_input_hash == b.last_input_hash, "A_B_query_content_mismatch")
        counts["identical_native_query_content_pairs"] += 1
        effect = _effect(before, action, after)
        scores.record("A", frozen, effect, previous)
        scores.record("B", online, effect, previous)
        scores.observed[effect] += 1
        counts["Action6_query_pairs_scored_before_teacher"] += 1
    else:
        effect = None
        counts["nonAction6_effect_target_omitted"] += 1
    check_budget()
    b.update(before, action, after)
    counts["B_shared_public_updates"] += 1
    if effect is not None:
        previous[effect] += 1
        counts["previous_Action6_counter_advanced_once_after_both_scores"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    replay.base._require(not output.exists(), "refusing_output_overwrite")
    started, errors, source = time.perf_counter(), [], {}
    scores, counts, costs = Scores(), Counter(), []
    completed_stream, input_stream = hashlib.sha256(), hashlib.sha256()
    software_paths = [Path(__file__), Path(replay.__file__), Path(replay.paired.__file__), Path(replay.base.__file__), Path(replay.integrity.__file__)]
    software = {p.relative_to(ROOT).as_posix(): replay.base._sha(p) for p in software_paths}
    native_hashes = {}
    try:
        replay.base._require(replay.base._sha(Path(replay.__file__)) == "4d917e5007c88eb510664b872535dc016417d9b7d728113242f612f2b7cdee37", "frozen_model_trace_loader")
        build = json.loads((replay.SOURCE_BUILD / "build-manifest.json").read_text(encoding="utf-8"))
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "submission.ipynb") == build["output_notebook_sha256"], "actual_notebook_hash")
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "kernel-metadata.json") == build["kernel_metadata_sha256"], "actual_metadata_hash")
        with replay.base._frozen_api() as (_, api, _, temporary):
            for name, sha in NATIVE_ORIGINALS.items():
                actual = replay.base._sha(temporary / "HDS/学習系統/v0.4.2/hds学習系統" / name)
                replay.base._require(actual == sha, "canonical_native_original_hash")
                native_hashes[name] = actual
            streams, source = replay._load_inputs(api)
            for transitions in streams:
                for before, action, after in transitions:
                    if action.number:
                        _feed_digest(input_stream, before, action, after)
            replay.base._require(input_stream.hexdigest() == EXPECTED_STREAM, "exact_C2_080_public_stream")
            for transitions in streams:
                a, b = Arm("A", api, 0), Arm("B", api, 80)

                def check_budget():
                    replay.base._require(a.seconds() + b.seconds() < 120.0, "combined_A_B_HDS_120_seconds_exhausted")

                previous = Counter()
                try:
                    check_budget()
                    for before, action, after in transitions:
                        if action.number == 0:
                            counts["RESET_excluded"] += 1
                            continue
                        _step(a, b, before, action, after, previous, scores, counts, check_budget)
                        _feed_digest(completed_stream, before, action, after)
                        check_budget()
                    replay.base._require(a.core.stats["updates_attempted"] == 0, "A_received_online_teacher")
                    replay.base._require(replay.paired._knowledge(a.core._hds) == a.prior_knowledge, "A_final_memory_changed")
                finally:
                    costs.append({"A": a.cost(), "B": b.cost(), "combined_actual_hds_seconds": a.seconds() + b.seconds(),
                                  "combined_hds_seconds_limit": 120.0, "time_budget_exhausted": a.seconds() + b.seconds() >= 120.0})
            replay.base._require(counts["B_shared_public_updates"] == 239 and counts["Action6_query_pairs_scored_before_teacher"] == 80, "complete_learning_stream")
            replay.base._require(completed_stream.hexdigest() == EXPECTED_STREAM, "complete_teacher_stream_digest")
        replay.base._require(all(replay.base._sha(ROOT / name) == sha for name, sha in software.items()), "learning_diagnostic_source_drift")
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "contract": str(exc)[:160]})
    report = {
        "schema": "arc3-prior-only-vs-causal-native-locality-learning.v1", "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(), "result": "FAIL" if errors else "OBSERVATIONAL_ONLY",
        "software_sha256": software, "source": source, "original_native_source_sha256": native_hashes,
        "frozen_R3_bundle_sha256": replay.base.EXPECTED_BUNDLE,
        "C2_079_native_scope_patch_applied": False,
        "source_public_stream_sha256": input_stream.hexdigest(), "completed_B_teacher_stream_sha256": completed_stream.hexdigest(),
        "target_path": [TARGET], "target_categories": list(EFFECT_ORDER),
        "target_definition": "(changed pixels within PRE-target-centred clipped7x7 >0, changed pixels outside that window >0)",
        "original_public_outcome_retained_on_all_teachers": True,
        "target_absent_from_nonAction6_teachers": True,
        "input_features_unchanged_from_C2_080_reduced_schema": True,
        "unavailable_action_count_never_imputed": True,
        "strict_previous_Action6_majority_fixed_tie_order": list(EFFECT_ORDER),
        "observed_Action6_effect_counts": dict(scores.observed),
        "arms": scores.report(), "causal_order_checks": dict(sorted(counts.items())),
        "observed_class_precision_is_accuracy_on_covered_steps_of_that_true_class": True,
        "shared_and_per_arm_costs": costs,
        "missing_native_statistics": "UNKNOWN; never coerced to zero",
        "empty_forecast_precision": "UNMEASURED/UNKNOWN; never zero",
        "forecast_measurement_gate": "genuine linked active/adopted native target prediction, unique declared value, native target conflicts/requests known zero; global HOLD retained",
        "native_HOLD_and_action_authorization_false_preserved": True,
        "no_geometry_input_features_motion_thresholds_or_runtime_changes": True,
        "no_gpu_model_sdk_kaggle_or_game_internals": True,
        "no_raw_boards_absolute_coordinates_game_ids_or_action_sequences_persisted": True,
        "remote_only_is_not_noop_failure_or_HUD": True,
        "all_public_games_reused": True,
        "not_gameplay_score_causal_action_gain_or_feature_promotion_proof": True,
        "budget_may_overrun_one_inflight_call": True,
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
