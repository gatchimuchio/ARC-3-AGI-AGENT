"""C2-087 exact-output inspection: prior-only versus online native game updates."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from statistics import mean
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGACY_PATH = ROOT / "検証/ARC3視覚HDS照会対応採点.py"
LEGACY_SHA = "ac5250d5a36d846205166e7aed36715a81e8341efe227aae395a185672cb7520"
FROZEN_OBSERVER_ZIP = ROOT / "出力/ARC3-RUN-003-local/C2-085/shown/visual-hds-source.zip"
FROZEN_OBSERVER_SHA = "d66a348026852a9a8e3286d22ae7dfacb10b7cf7d7b26ae8c8cbf33862418312"
FLAG = "ARC3_HDS_GAME_RESPONSE_UPDATES"
DISABLED = "game_response_update_disabled"
TARGET = "公開作用点効果区分"
AREA = "作用点同色4連結成分面積"
EFFECT_ORDER = ("局所なし・局所以外なし", "局所なし・局所以外あり",
                "局所あり・局所以外なし", "局所あり・局所以外あり")
EFFECTS = set(EFFECT_ORDER)

if hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest() != LEGACY_SHA:
    raise ValueError("frozen C2-081 scorecard source drift")
_spec = importlib.util.spec_from_file_location("_c2087_frozen_scorecard", LEGACY_PATH)
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
common = legacy.common
require, load, sha256 = common.require, common.load, common.sha256
_legacy_build_contract = legacy.build_contract
# A bijective label adapter reuses the frozen strictly-past comparator, whose
# majority helper accepts only its five public-outcome labels. No class merges
# or runtime forecasts are introduced; output counter labels are decoded below.
_effect_encode = dict(zip(EFFECT_ORDER, legacy._record_response.__globals__["MAJORITY_ORDER"][:4], strict=True))
_effect_decode = {v: k for k, v in _effect_encode.items()}


def build_contract(path: Path, visibility: str) -> tuple[dict, dict, dict]:
    b = load(path)
    mode = b.get("native_game_response_learning_mode")
    require(b.get("schema") in {"arc3-native-game-learning-ablation-build.v1",
                                "arc3-native-game-learning-ablation-repro-build.v1"}
            and visibility == "shown" and mode in {"disabled", "enabled"}, "wrong learning build/mode")
    require(b.get("learning_treatment_flag") == FLAG
            and b.get("native_game_response_updates_enabled") is (mode == "enabled")
            and b.get("evidence_visibility_both_arms") == "shown"
            and b.get("initial_prior_records_both_arms") == 5
            and b.get("disabled_update_status") == DISABLED
            and b.get("query_renderer_uses_actual_native_return_not_new_teacher_history") is True,
            "learning treatment/prior/renderer contract differs")
    if b["schema"] == "arc3-native-game-learning-ablation-repro-build.v1":
        seed = b.get("environment_seed", {})
        require(seed.get("explicitly_requested_by_notebook") is True and seed.get("value") == 0
                and seed.get("scope") == "OFFLINE private pilot only"
                and b.get("software_stamp_filename") == "arc3-runtime-software.json"
                and b.get("software_stamp_schema") == "arc3-runtime-software.v1"
                and b.get("r1_learning_runtime_native_observer_prompt_model_and_budgets_unchanged") is True,
                "r2 seed/stamp contract differs")
    # Reuse all frozen source/budget/authorization checks. Only the already
    # validated schema discriminator is adapted, never native counts or files.
    original_load = legacy.load
    legacy.load = lambda p: ({**b, "schema": "arc3-python-hds-query-pilot-build.v1"}
                             if Path(p).resolve() == path.resolve() else load(p))
    try:
        _, metadata, notebook = _legacy_build_contract(path, visibility)
    finally:
        legacy.load = original_load
    require(sha256(FROZEN_OBSERVER_ZIP) == FROZEN_OBSERVER_SHA, "frozen observer source drift")
    with zipfile.ZipFile(FROZEN_OBSERVER_ZIP) as old, zipfile.ZipFile(path.parent / "visual-hds-source.zip") as z:
        require(set(old.namelist()) == set(z.namelist()), "observer source file set differs")
        preserved = set(old.namelist()) - {"ARC3-VISUAL-HDS-MANIFEST.json", "arc3_visual_hds_runtime.py"}
        require(all(old.read(n) == z.read(n) for n in preserved), "observer/RPC/native/prior source differs")
        runtime = z.read("arc3_visual_hds_runtime.py")
        require(runtime.startswith(old.read("arc3_visual_hds_runtime.py"))
                and hashlib.sha256(runtime).hexdigest() == b.get("learning_runtime_source_sha256"),
                "learning runtime/source prefix differs")
    return b, metadata, notebook


def _response_metrics(rows: list, history: list, trace: list, truncated: bool) -> dict:
    require(isinstance(rows, list), "missing public response stream")
    projected = deepcopy(rows)
    locality_past, locality_counts = Counter(), Counter()
    for row in projected:
        require(isinstance(row, dict), "invalid public response row")
        teacher = row.get("projected_update_input")
        require(isinstance(teacher, dict), "missing computed public teacher")
        query = row.get("projected_query_input_at_matching_inspection")
        require(not isinstance(query, dict) or TARGET not in query, "locality teacher leaked into query")
        number = row.get("actual_action_number")
        if number == 6:
            area = row.get("PRE_target_samecolor4CC_pixel_area")
            require(type(area) is int and area > 0
                    and teacher.get("作用前公開状態", {}).get(AREA) == area, "PRE area projection differs")
            observed = row.get("observed_Action6_effect_class")
            require(observed in EFFECTS or observed is None, "unknown locality label")
            require(teacher.get(TARGET) == observed and (observed is not None or TARGET not in teacher),
                    "locality response/teacher differs")
            values = row.get("native_linked_Action6_effect_forecast_values_at_query")
            measurable = (row.get("matching_candidate_was_queried_before_action") is True
                          and row.get("native_Action6_summary_truncated_at_query") is False
                          and isinstance(values, list) and len(values) == 1 and values[0] in EFFECTS
                          and row.get("native_status_at_query") in {"出力", "断定保留"})
            if observed is None:
                locality_counts["unknown_actual_effect_not_scored"] += 1
            else:
                legacy._record_response(locality_past, {_effect_encode[values[0]]} if measurable else set(),
                                        None if measurable else "UNMEASURED", _effect_encode[observed], locality_counts)
        else:
            require(TARGET not in teacher and AREA not in teacher.get("作用前公開状態", {}),
                    "nonAction6 observer labels not omitted")
        # The frozen comparator validates identical PRE inputs. This field is
        # an AFTER-only teacher, unlike PRE area, and must not enter that join.
        teacher.pop(TARGET, None)
    result = legacy.response_metrics(projected, history, trace, truncated)
    result["locality_counts"] = {
        (k.rsplit(":", 1)[0] + ":" + _effect_decode[k.rsplit(":", 1)[1]]
         if ":" in k and k.rsplit(":", 1)[1] in _effect_decode else k): v
        for k, v in locality_counts.items()}
    return result


def _check_updates(d: dict, h: dict, c: dict, rows: list, mode: str) -> dict:
    a = d.get("learning_ablation")
    require(isinstance(a, dict) and a.get("revision") == "native-game-response-learning-only.v1"
            and a.get("configuration_flag") == FLAG and a.get("frozen_mode") == mode
            and a.get("configuration_unchanged") is True
            and a.get("game_response_native_updates_enabled") is (mode == "enabled")
            and a.get("disabled_skips_are_expected_not_errors") is (mode == "disabled")
            and a.get("expected_disabled_skip_status") == DISABLED
            and a.get("prior_records_expected") == 5, "learning configuration missing/drifted")
    require(h.get("prior_updates_attempted") == h.get("prior_updates_succeeded") == 5
            and a.get("prior_native_updates_attempted") == 5
            and a.get("prior_native_updates_succeeded") == 5, "prior native updates not separate/five")
    statuses = Counter(r.get("update_bridge_status") for r in rows)
    require(all(r.get("native_game_response_learning_enabled") is (mode == "enabled")
                and r.get("native_game_update_skip_is_expected") is
                (mode == "disabled" and r.get("update_bridge_status") == DISABLED) for r in rows),
            "per-response learning mode/expected skip differs")
    require(c.get("game_response_teacher_inputs_computed", 0) == len(rows),
            "teacher computation/callback coverage differs")
    require(all(c.get("update_status:" + k, 0) == v for k, v in statuses.items()),
            "update status counters/receipts differ")
    if mode == "disabled":
        require(h["updates_attempted"] == h["updates_succeeded"] == 0
                and statuses[DISABLED] == len(rows)
                and c.get("game_response_update_expected_disabled", 0) == len(rows)
                and c.get("game_response_update_enabled_requests", 0) == 0,
                "prior-only native ingestion or missing expected disabled receipt")
    else:
        require(statuses[DISABLED] == 0 and c.get("game_response_update_expected_disabled", 0) == 0
                and c.get("game_response_update_enabled_requests", 0) == len(rows)
                and h["updates_succeeded"] == statuses["updated"]
                and h["updates_attempted"] == h["updates_succeeded"]
                and statuses["updated"] + statuses["budget_exhausted"] == len(rows),
                "online native ingestion/callback coverage differs")
        if statuses["budget_exhausted"]:
            require((h["update_budget_exhausted"] or h["time_budget_exhausted"])
                    and h["budget_exhaustion_requests"] >= statuses["budget_exhausted"],
                    "unsubstantiated update budget skip")
    return {"nonRESET_callbacks": len(rows), "computed_game_teachers": len(rows),
            "expected_disabled_skips": statuses[DISABLED], "native_budget_skips": statuses["budget_exhausted"]}


def _measurement(counts: Counter, streams: int) -> dict:
    covered, compared = counts["target_qualified_unique_forecasts"], counts["same_covered_steps_with_majority"]
    return {"complete_game_streams": streams, "counts": dict(counts),
            "forecast_precision": counts["target_unique_matches"] / covered if covered else None,
            "same_covered_steps": compared,
            "same_covered_native_precision": counts["target_matches_on_majority_comparable_steps"] / compared if compared else None,
            "same_covered_past_majority_precision": counts["majority_matches_on_same_covered_steps"] / compared if compared else None,
            "native_guard_qualification": "UNKNOWN_NOT_INFERRED_FROM_ACTIVE_REF_LINKS",
            "qualification": "Descriptive actual active/adopted-reference forecasts; native HOLD/uncertainty retained. Unknown/clipped/nonunique forecasts unmeasured."}


def telemetry(paths: set[str], root: Path, runs: dict, visibility: str, budgets: dict) -> dict:
    counts, operations, seconds, budgets_seen, errors, callbacks = (Counter() for _ in range(6))
    order, coarse, locality, native, targets, unknown_targets = (Counter() for _ in range(6))
    strata = {}
    failures, streams, max_overrun = [], 0, 0.0
    mode = _inspection_mode
    for gid, run in runs.items():
        try:
            name = f"artifacts/{gid}_p0_tool_runtime_state.visual-hds-query.json"
            require(name in paths, "missing learning sidecar")
            d = load(root / name)
            require(d.get("schema") == "arc3-python-hds-learning-ablation-telemetry.v1"
                    and d.get("visibility") == visibility == "shown" and d.get("authorization") is False
                    and d.get("endorsement") is False and d.get("native_judgment_modified") is False
                    and d.get("native_scope") == "whole_query_original_0.4.2", "wrong learning telemetry boundary")
            c, h, p = d.get("counts"), d.get("hds"), d.get("prior")
            require(isinstance(c, dict) and isinstance(h, dict) and isinstance(p, dict), "learner/prior unavailable")
            for k, v in c.items():
                counts[k] += common.nonnegative(v, "runtime counter", integer=True)
                if k.endswith("_errors"):
                    errors[k] += v
            for k in common.HDS_COUNTS:
                operations[k] += common.nonnegative(h.get(k), k, integer=True)
            for k in common.HDS_SECONDS:
                seconds[k] += common.nonnegative(h.get(k), k)
            for k in ("update_errors", "query_errors", "summary_errors", "prior_update_errors", "rejected_requests"):
                errors[k] += h[k]
            if d.get("last_error_type") or h.get("last_error_type"):
                errors["reported_error_type"] += 1
            require(c.get("actual_action_calls_seen") == len(run["history"]), "runtime/history actions differ")
            require(all(h.get(k) == v for k, v in budgets.items()), "runtime/build budgets differ")
            require(p.get("load_status") == "loaded" and p.get("loaded_count") == 5
                    and p.get("action_authorization") is False, "fixed prior incomplete")
            for kind, plural in (("update", "updates"), ("query", "queries")):
                require(h[f"{plural}_succeeded"] <= h[f"{plural}_attempted"] <= budgets[f"{kind}_budget"],
                        "native operation budget exceeded")
                require(h.get(f"{kind}_budget_exhausted") is (h[f"{plural}_attempted"] >= budgets[f"{kind}_budget"]),
                        "dishonest operation budget flag")
            require(type(h.get("time_budget_exhausted")) is bool
                    and (h["total_hds_seconds"] >= budgets["hds_seconds_budget"] - 1e-6
                         if h["time_budget_exhausted"] else h["total_hds_seconds"] <= budgets["hds_seconds_budget"] + 1e-6),
                    "dishonest time budget flag")
            for k in ("update_budget_exhausted", "query_budget_exhausted", "time_budget_exhausted"):
                budgets_seen[k] += int(h[k])
            max_overrun = max(max_overrun, h["total_hds_seconds"] - budgets["hds_seconds_budget"])
            m = _response_metrics(d.get("public_response_rows"), run["history"], d.get("ordering_trace"),
                                  bool(c.get("ordering_trace_truncated")))
            callbacks.update(_check_updates(d, h, c, d["public_response_rows"], mode))
            coarse.update(m["counts"])
            locality.update(m["locality_counts"])
            order.update(m["ordering"])
            targets.update(m["native_target_count_sums"])
            unknown_targets.update(m["native_target_UNKNOWN_query_counts"])
            for status, values in m["native_status_forecast_counts"].items():
                strata.setdefault(status, Counter()).update(values)
            streams += 1
        except (ValueError, KeyError, TypeError, OSError) as exc:
            failures.append(str(exc) if isinstance(exc, ValueError) else f"telemetry data error: {type(exc).__name__}")
    for k, v in counts.items():
        if k.startswith("query_native:"):
            native[k.split(":", 1)[1]] += v
    valid = not failures and not sum(errors.values())
    queries = counts["query_helper_calls"]
    return {"integration_valid": bool(valid), "integration_failures": failures, "errors": dict(errors),
            "learning_mode": mode, "counters": dict(counts), "operations": dict(operations),
            "seconds": dict(seconds), "game_response_update_evidence": dict(callbacks),
            "prior_native_updates_are_separate": True, "budgets_per_game": budgets,
            "budget_exhausted_game_counts": dict(budgets_seen), "max_soft_HDS_time_overrun_seconds": max_overrun,
            "native_query_status_counts": dict(native), "matched_candidate_ordering": dict(order),
            "native_target_count_sums_on_matched_responses": dict(targets),
            "native_target_UNKNOWN_query_counts": dict(unknown_targets),
            "strict_past_prediction_measurement": {**_measurement(coarse, streams),
                "native_status_forecast_counts": {k: dict(v) for k, v in strata.items()}},
            "Action6_effect_prediction_measurement": {**_measurement(locality, streams),
                "majority_tie_break_order": list(EFFECT_ORDER)},
            "exposure_classification": ("UNKNOWN_INTEGRATION_FAILURE" if not valid else "NO_QUERY" if not queries else
                                        "SHOWN_RPC_NATIVE_AVAILABLE_MODEL_RENDERING_UNKNOWN" if operations["queries_succeeded"] else "QUERY_UNAVAILABLE"),
            "rendered_model_evidence_exposure": "UNKNOWN", "comprehension_or_adoption_proven": False,
            "same_response_unreviewed_is_gameplay_failure": False}


_inspection_mode = None
legacy.build_contract, legacy.telemetry = build_contract, telemetry


def inspect_arm(retrieval: Path, build: Path, output_root: Path, version: int) -> tuple[dict, dict]:
    global _inspection_mode
    _inspection_mode = load(build).get("native_game_response_learning_mode")
    result, internal = legacy.inspect_arm(retrieval, build, output_root, version)
    result["native_game_response_learning_mode"] = _inspection_mode
    result["runtime_software_and_seed"] = runtime_software(output_root, load(retrieval))
    return result, internal


def runtime_software(root: Path, retrieval: dict) -> dict:
    paths = {r["path"] for r in retrieval["output_files"]}
    if "arc3-runtime-software.json" not in paths:
        return {"status": "UNKNOWN_MISSING_RUNTIME_STAMP", "actual_versions": None,
                "actual_seed_settings": None, "full_reproducibility_proven": False}
    stamp = load(root / "arc3-runtime-software.json")
    require(stamp.get("schema") == "arc3-runtime-software.v1", "invalid runtime software stamp schema")
    python, packages, seed = stamp.get("python"), stamp.get("packages"), stamp.get("environment_seed")
    require(isinstance(python, dict) and all(isinstance(python.get(k), str) and python[k]
                                          for k in ("version", "implementation"))
            and isinstance(packages, dict) and set(packages) == {"arc-agi", "arcengine"}
            and all(v is None or isinstance(v, str) and v for v in packages.values())
            and isinstance(stamp.get("observation_errors"), dict)
            and (stamp.get("public_Arcade_make_signature") is None
                 or isinstance(stamp["public_Arcade_make_signature"], str)), "invalid runtime version observations")
    require(seed == {"declared_offline_seed": 0, "explicit_keyword_scope": "OFFLINE private pilot only",
                     "competition_rerun_allowed": False}, "unexpected declared runtime seed settings")
    complete = (all(packages.values()) and bool(stamp["public_Arcade_make_signature"])
                and not stamp["observation_errors"])
    return {"status": "OBSERVED_COMPLETE" if complete else "OBSERVED_PARTIAL", "stamp": stamp,
            "actual_versions": packages, "declared_seed_settings": seed, "full_reproducibility_proven": False}


def compare(prior: dict, online: dict) -> dict:
    normalized = []
    for arm, mode in ((prior, "disabled"), (online, "enabled")):
        b = deepcopy(arm["build"])
        require(b["native_game_response_learning_mode"] == mode, "pair needs prior-only and online")
        for k in ("native_game_response_learning_mode", "native_game_response_updates_enabled",
                  "output_notebook_sha256", "kernel_metadata_sha256", "built_at_utc"):
            b.pop(k, None)
        b["cpu_generated_patch_cell"].pop("game_response_learning_mode", None)
        cells = common.canonical_cells(arm["notebook"])
        marker = f"os.environ[{FLAG!r}] = {mode!r}"
        require(len(cells) > 6 and sum(c["source"].count(marker) for c in cells) == 1
                and marker in cells[6]["source"], "missing unique cell6 learning selector")
        cells[6]["source"] = cells[6]["source"].replace(marker, "LEARNING_SELECTOR")
        normalized.append((b, {k: v for k, v in arm["metadata"].items() if k not in {"id", "title"}},
                           cells, arm["notebook"].get("metadata")))
    require(normalized[0] == normalized[1], "paired source/model/observer/prompt/config differs beyond learning flag")
    require(set(prior["runs"]) == set(online["runs"]), "paired game sets differ")
    helper = common.helper()
    for gid in prior["runs"]:
        require(all(prior["starts"][gid][k] == online["starts"][gid][k] for k in helper.START_FIELDS),
                "paired public initial fields differ")
        require(all(prior["runs"][gid][k] == online["runs"][gid][k]
                    for k in ("number_of_levels", "base_actions_per_level")), "paired public baselines differ")
    delta = [online["scores"][gid] - prior["scores"][gid] for gid in prior["runs"]]
    return {"games": 3, "source_model_observer_prompt_budget_initial_fields_matched": True,
            "descriptive_mean_RHAE_delta_online_minus_prior": mean(delta),
            "descriptive_game_direction_counts": {"higher": sum(x > 1e-9 for x in delta),
                                                 "equal": sum(abs(x) <= 1e-9 for x in delta),
                                                 "lower": sum(x < -1e-9 for x in delta)}}


def evaluate(retrieval: Path, build: Path, output_root: Path, version: int, *, other_retrieval: Path | None = None,
             other_build: Path | None = None, other_output_root: Path | None = None, other_version: int | None = None) -> dict:
    require(sha256(Path(common.__file__)) == legacy.COMMON_SHA, "shared score/retrieval helper drift")
    arm, internal = inspect_arm(retrieval, build, output_root, version)
    result = {"schema": "arc3-native-game-learning-scorecard.v1", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "inspection": "single", "arm": arm, "frozen_C2_081_scorecard_sha256": LEGACY_SHA,
              "common_scorecard_sha256": legacy.COMMON_SHA, "official_RHAE_helper_sha256": common.HELPER_SHA,
              "scorecard_source_sha256": sha256(Path(__file__)), "official_score_observed": False,
              "official_submission_or_quota_use": False, "learning_effect_proven": False,
              "learning_benefit": "UNPROVEN", "limitation": "Both arms SHOWN. RPC return does not prove rendered model exposure, comprehension or adoption. Prior5 and game teachers are separate. Descriptive single-run comparison is not a repeated learning-effect demonstration; missing runtime software/seed evidence stays UNKNOWN."}
    optional = (other_retrieval, other_build, other_output_root, other_version)
    require(all(v is None for v in optional) or all(v is not None for v in optional), "paired arm requires four exact inputs")
    if other_retrieval is not None:
        other, oi = inspect_arm(other_retrieval, other_build, other_output_root, other_version)
        arms = {arm["native_game_response_learning_mode"]: (arm, internal), other["native_game_response_learning_mode"]: (other, oi)}
        require(set(arms) == {"disabled", "enabled"}, "pair needs both learning modes")
        result.update(inspection="paired", prior_only=arms["disabled"][0], online_learning=arms["enabled"][0],
                      paired=compare(arms["disabled"][1], arms["enabled"][1]))
        stamps = [arms[k][0]["runtime_software_and_seed"] for k in ("disabled", "enabled")]
        present = all("stamp" in s for s in stamps)
        known = all(s["status"] == "OBSERVED_COMPLETE" for s in stamps)
        if present:
            require(stamps[0]["stamp"] == stamps[1]["stamp"], "paired observed runtime software/seed differs")
        result["paired"].update(runtime_software_seed_match=True if known else None,
                                both_gameplay_valid=all(a[0]["gameplay_valid"] for a in arms.values()),
                                both_integration_valid=all(a[0]["integration_valid"] for a in arms.values()))
        result.pop("arm")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("", "other-"):
        for name in ("retrieval", "build", "output-root", "version"):
            parser.add_argument("--" + prefix + name, type=int if name == "version" else Path, required=not prefix)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing scorecard overwrite")
    result = evaluate(args.retrieval, args.build, args.output_root, args.version,
                      other_retrieval=args.other_retrieval, other_build=args.other_build,
                      other_output_root=args.other_output_root, other_version=args.other_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output), "inspection": result["inspection"]}))


if __name__ == "__main__":
    main()
