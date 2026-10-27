"""C2-078のSDK/選択/採点を再利用し、同じ学習状態のnative全体/対象照会を比較する。"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))
import ARC3視覚HDS公開逐次予測診断 as base  # noqa: E402

_BASE_RECORD = base._record_response

PATCH = ROOT / "検証/候補/ARC3HDS対象経路照会候補.patch"
PROOF = ROOT / "出力/ARC3-RUN-003-local/C2-079/native-scope-cpu-proof.json"
PATCH_SHA = "df5f071ac51820200b3e95f1f65a50d4697619a8bab00fe19e7fe6c855ca28fb"
PROOF_SHA = "a9c90a4fdeb5f7f125850d3db11590b92acafff05652c88d60e730485137df7a"
SCOPE = (("公開応答区分",),)


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()


def _knowledge(hds) -> str:
    engine = hds.エンジン
    return _digest(
        {
            "ledger_counts": {name: len(rows) for name, rows in engine.台帳.全取得().items()},
            "observations": [asdict(row) for row in engine.台帳.取得("観測台帳")],
            "current_state_version": engine.状態.現在版,
            "current_state": engine.状態.現在状態,
            "active_principles": [asdict(row) for row in engine._有効原理群()],
            "quarantined_principles": [asdict(row) for row in engine._係争中原理群()],
        }
    )


class _Collector:
    def __init__(self):
        self.scoped_counts = Counter()
        self.pairs = Counter()
        self.bridges = []
        self.current = None
        self.stream = hashlib.sha256()
        self.original_record = _BASE_RECORD

    def score(self, previous, legacy_forecast, legacy_blocked, outcome, legacy_counts):
        active = self.current
        base._require(active is not None and active.pending is not None, "missing_paired_query")
        scoped_previous = previous.copy()
        majority, _ = base._majority(previous)
        scoped = active.pending["scoped"]
        scoped_blocked, scoped_forecast = active.runtime._target_forecast(scoped)
        self.original_record(previous, legacy_forecast, legacy_blocked, outcome, legacy_counts)
        self.original_record(
            scoped_previous, scoped_forecast, scoped_blocked, outcome, self.scoped_counts
        )
        base._require(previous == scoped_previous, "previous_label_counter_divergence")
        self.pairs["identical_strictly_previous_majority_counter_steps"] += 1
        self.pairs[
            "whole_native_status:" + str(active.pending["whole"].get("native_status", "missing"))
        ] += 1
        self.pairs["scoped_native_status:" + str(scoped.get("native_status", "missing"))] += 1
        for label, result in (("whole", active.pending["whole"]), ("scoped", scoped)):
            for reason in result.get("native_hold_reasons", ()):
                self.pairs[label + "_native_hold_reason:" + reason] += 1
            self.pairs[label + "_relevant_active_rule_count_sum"] += result.get(
                "relevant_active_rule_count", 0
            )
            self.pairs[label + "_relevant_prediction_count_sum"] += result.get(
                "relevant_prediction_count", 0
            )
        if (
            legacy_blocked is None
            and len(legacy_forecast) == 1
            and scoped_blocked is None
            and len(scoped_forecast) == 1
        ):
            self.pairs["both_arms_unique_covered_steps"] += 1
            self.pairs["both_arms_forecast_value_agreement"] += int(
                legacy_forecast == scoped_forecast
            )
            self.pairs["whole_matches_on_both_covered_steps"] += int(outcome in legacy_forecast)
            self.pairs["scoped_matches_on_both_covered_steps"] += int(outcome in scoped_forecast)
            if majority is not None:
                self.pairs["both_covered_with_previous_majority"] += 1
                self.pairs["previous_majority_matches_on_both_covered_steps"] += int(
                    majority == outcome
                )


class _PairedBridge:
    def __init__(self, real_type, api, runtime, collector, **budgets):
        self.real = real_type(**budgets)
        self.api, self.runtime, self.collector = api, runtime, collector
        self.scoped_attempts = self.scoped_succeeded = self.scoped_errors = 0
        self.scoped_seconds = 0.0
        self.scoped_limit = budgets["query_budget"]
        self.seconds_limit = budgets["hds_seconds_budget"]
        self.pending = None
        self.actual_inputs = []
        collector.bridges.append(self)
        native_query = self.real._hds.照会する

        def observed_native_query(value, **kwargs):
            before = _digest(value.内容)
            result = native_query(value, **kwargs)
            base._require(_digest(value.内容) == before, "native_query_mutated_input")
            self.actual_inputs.append((before, kwargs.get("結果経路群")))
            return result

        self.real._hds.照会する = observed_native_query

    @property
    def prior_report(self):
        return self.real.prior_report

    @property
    def stats(self):
        return self.real.stats

    def elapsed(self):
        return sum(self.real._seconds.values()) + self.scoped_seconds

    def exhausted(self):
        return self.elapsed() >= self.seconds_limit

    def budget_result(self):
        return {
            "bridge_status": "budget_exhausted",
            "authorization": False,
            "continue_visual_solver": True,
            "blocked_by": ["paired_actual_HDS_budget"],
        }

    def query(self, before, action):
        self.collector.current = self
        self.actual_inputs.clear()
        knowledge = _knowledge(self.real._hds)
        whole = self.budget_result() if self.exhausted() else self.real.query(before, action)
        base._require(
            _knowledge(self.real._hds) == knowledge, "whole_query_changed_learned_knowledge"
        )
        if self.exhausted() or self.scoped_attempts >= self.scoped_limit:
            scoped = self.budget_result()
        else:
            content = self.api._query_content(before, action)
            value = self.api.外部入力(content, self.api._BOUNDARY)
            self.scoped_attempts += 1
            started = time.perf_counter()
            try:
                native = self.real._hds.照会する(value, 結果経路群=SCOPE)
                self.scoped_succeeded += 1
            except Exception:
                self.scoped_errors += 1
                raise
            finally:
                self.scoped_seconds += time.perf_counter() - started
            scoped = {
                "bridge_status": "queried",
                "authorization": False,
                "continue_visual_solver": True,
                "candidate_action_number": action.number,
                **self.api._native_summary(native),
            }
            base._require(tuple(native.追跡情報["照会結果経路群"]) == SCOPE, "native_scope_trace")
        base._require(
            _knowledge(self.real._hds) == knowledge, "scoped_query_changed_learned_knowledge"
        )
        if whole["bridge_status"] == scoped["bridge_status"] == "queried":
            base._require(len(self.actual_inputs) == 2, "paired_native_query_count")
            base._require(
                self.actual_inputs[0][0] == self.actual_inputs[1][0], "paired_native_input_mismatch"
            )
            base._require(
                self.actual_inputs[0][1] is None and self.actual_inputs[1][1] == SCOPE,
                "paired_native_scope_arguments",
            )
            self.collector.pairs["identical_native_input_and_learned_state_query_pairs"] += 1
        self.pending = {"before": before, "action": action, "whole": whole, "scoped": scoped}
        return whole

    def update(self, before, action, after):
        base._require(self.pending is not None, "update_without_paired_query")
        base._require(
            self.pending["before"] == before and self.pending["action"] == action,
            "paired_step_mismatch",
        )
        data = {"before": asdict(before), "action": asdict(action), "after": asdict(after)}
        encoded = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.collector.stream.update(len(encoded).to_bytes(8, "big"))
        self.collector.stream.update(encoded)
        self.collector.pairs["shared_nonreset_public_step_digest_count"] += 1
        self.pending = None
        return self.budget_result() if self.exhausted() else self.real.update(before, action, after)

    def cost(self):
        stats = self.real.stats
        return {
            "shared_update_budget": stats["update_budget"],
            "shared_updates_attempted": stats["updates_attempted"],
            "shared_updates_succeeded": stats["updates_succeeded"],
            "shared_update_seconds": stats["update_seconds"],
            "shared_prior_updates": stats["prior_updates_attempted"],
            "shared_prior_seconds": stats["prior_load_seconds"],
            "whole_query_budget": stats["query_budget"],
            "whole_queries_attempted": stats["queries_attempted"],
            "whole_queries_succeeded": stats["queries_succeeded"],
            "whole_query_errors": stats["query_errors"],
            "whole_query_seconds": stats["query_seconds"],
            "scoped_query_budget": self.scoped_limit,
            "scoped_queries_attempted": self.scoped_attempts,
            "scoped_queries_succeeded": self.scoped_succeeded,
            "scoped_query_errors": self.scoped_errors,
            "scoped_query_seconds": self.scoped_seconds,
            "combined_actual_seconds_budget": self.seconds_limit,
            "combined_actual_hds_seconds": self.elapsed(),
            "combined_time_budget_exhausted": self.exhausted(),
        }


def _apply_candidate(destination):
    base._require(
        base._sha(PATCH) == PATCH_SHA and base._sha(PROOF) == PROOF_SHA,
        "reviewed_patch_or_proof_drift",
    )
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    base._require(
        proof["whole_query_full_structure_matches_frozen_original"] is True,
        "default_compatibility_proof",
    )
    base._require(
        proof["explicit_None_equals_omitted_scope"] is True, "explicit_none_compatibility_proof"
    )
    for row in proof["native_source_pre_post"]:
        base._require(
            base._sha(destination / row["path"]) == row["pre_sha256"], "temporary_native_preimage"
        )
    git = shutil.which("git")
    base._require(git is not None, "git_apply_missing")
    command = [git, "-c", "core.autocrlf=false", "apply"]
    subprocess.run(
        command + ["--check", str(PATCH)], cwd=destination, check=True, capture_output=True
    )
    subprocess.run(command + [str(PATCH)], cwd=destination, check=True, capture_output=True)
    for row in proof["native_source_pre_post"]:
        base._require(
            base._sha(destination / row["path"]) == row["post_sha256"], "temporary_native_postimage"
        )
    for name in list(sys.modules):
        if name == "hds学習系統" or name.startswith("hds学習系統.") or name == "接続.ARC3事前記憶":
            del sys.modules[name]
    importlib.invalidate_caches()
    return proof


def _summary(counts):
    total, covered, compared = (
        counts[key]
        for key in (
            "nonreset_public_responses",
            "target_qualified_unique_forecasts",
            "same_covered_steps_with_majority",
        )
    )
    return {
        "counts": dict(sorted(counts.items())),
        "coverage": covered / total if total else None,
        "precision": counts["target_unique_matches"] / covered if covered else None,
        "same_covered_previous_majority_precision": counts["majority_matches_on_same_covered_steps"]
        / compared
        if compared
        else None,
    }


def _smoke(real_type, api, runtime):
    collector = _Collector()
    bridge = _PairedBridge(
        real_type, api, runtime, collector, update_budget=8, query_budget=8, hds_seconds_budget=20.0
    )
    before = api.PublicFrame(((0, 1), (1, 0)), "NOT_FINISHED", 0, (1, 2))
    changed = api.PublicFrame(((1, 1), (1, 0)), "NOT_FINISHED", 0, (1, 2))
    previous, counts = Counter(), Counter()
    for number in (1, 2, 1):
        action = api.PublicAction(number)
        result = bridge.query(before, action)
        blocked, values = runtime._target_forecast(result)
        after = changed if number == 1 else before
        collector.score(previous, values, blocked, api._observed_outcome(before, after), counts)
        bridge.update(before, action, after)
    whole = bridge.query(before, api.PublicAction(1))
    scoped = bridge.pending["scoped"]
    base._require(whole["native_status"] == "断定保留", "smoke_whole_HOLD_preserved")
    base._require(scoped["native_status"] == "出力", "smoke_native_scoped_output")
    base._require(
        runtime._target_forecast(scoped) == (None, {"盤面変化"}), "smoke_scoped_prediction"
    )
    return {
        "passed": True,
        "actual_SDK_or_model_called": False,
        "whole_status": whole["native_status"],
        "scoped_status": scoped["native_status"],
        "same_input_and_learning_state_query_pairs": collector.pairs[
            "identical_native_input_and_learned_state_query_pairs"
        ],
        "strict_previous_counter_steps": collector.pairs[
            "identical_strictly_previous_majority_counter_steps"
        ],
        "cost": bridge.cost(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite evidence: {output}")
    collector = _Collector()
    original_context, original_record, original_argv = (
        base._frozen_api,
        base._record_response,
        sys.argv[:],
    )
    state = {}

    @contextmanager
    def candidate_context():
        with original_context() as (runtime, api, manifest, destination):
            state["proof"] = _apply_candidate(destination)
            api = importlib.reload(api)
            runtime._API = api
            real_type = api.VisualHDSBridge
            state["smoke"] = _smoke(real_type, api, runtime)
            api.VisualHDSBridge = lambda **budgets: _PairedBridge(
                real_type, api, runtime, collector, **budgets
            )
            try:
                yield runtime, api, manifest, destination
            finally:
                api.VisualHDSBridge = real_type

    with tempfile.TemporaryDirectory(prefix="arc3-c2079-measurement-") as directory:
        temporary = Path(directory).resolve()
        base._require(
            temporary.is_relative_to(Path(tempfile.gettempdir()).resolve()),
            "temporary_measurement_root",
        )
        intermediate = temporary / "whole-arm.json"
        try:
            if args.smoke_only:
                with candidate_context():
                    pass
                legacy = None
                code = 0
            else:
                base._frozen_api = candidate_context
                # score delegates to the original function for both independent copies.
                base._record_response = collector.score
                sys.argv = [original_argv[0], "--output", str(intermediate)]
                code = base.main()
                legacy = json.loads(intermediate.read_text(encoding="utf-8"))
        finally:
            base._frozen_api, base._record_response, sys.argv = (
                original_context,
                original_record,
                original_argv,
            )
    costs = [bridge.cost() for bridge in collector.bridges]
    result = {
        "schema": "arc3-native-scoped-public-prequential-comparison.v1",
        "run_id": output.stem,
        "smoke_only": args.smoke_only,
        "cpu_smoke": state.get("smoke"),
        "whole_arm": legacy,
        "scoped_arm": _summary(collector.scoped_counts),
        "paired_counts": dict(sorted(collector.pairs.items())),
        "shared_nonreset_stream_sha256": collector.stream.hexdigest(),
        "stream_digest_contains_no_game_identity": True,
        "raw_stream_persisted": False,
        "shared_update_streams": len(costs),
        "costs_per_anonymous_game": costs,
        "budget_semantics": "80 shared updates, 80 queries per arm, 120 seconds combined actual HDS work per game including prior; one update per actual response",
        "query_identifier_allocation_allowed_and_excluded_from_knowledge_fingerprint": True,
        "knowledge_fingerprint": "all ledger counts; full observations/current state/active and quarantined principles; no query identifiers",
        "legacy_global_HOLD_preserved_alongside_native_scoped_status": True,
        "same_C2_078_configuration_but_exact_old_stream_identity_unproven": True,
        "canonical_bridge_R3_or_notebook_sources_changed": False,
        "HDS_forecasts_changed_chosen_action": False,
        "model_GPU_Kaggle_called": False,
        "ability_or_score_improvement_proven": False,
        "source_sha256": {
            "runner": base._sha(Path(__file__)),
            "reused_C2_078_diagnostic": base._sha(Path(base.__file__)),
            "candidate_patch": PATCH_SHA,
            "CPU_proof": PROOF_SHA,
            "R3_bundle": base.EXPECTED_BUNDLE,
        },
        "native_pre_post_hashes": state.get("proof", {}).get("native_source_pre_post"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "smoke": result["cpu_smoke"],
                "scoped_arm": result["scoped_arm"],
                "paired_counts": result["paired_counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
