"""Inspect exact-version visual/HDS pilot outputs; never submit or infer learning gains.

Reads only the selected files declared by a terminal retrieval manifest. The existing
C2-059 helper owns RHAE calculation and public initial-event field definitions.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path, PurePosixPath
import re
from statistics import mean
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from 道具.benchmark_telemetry_audit import audit_benchmark

HELPER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-scorecard.py"
HELPER_SHA = "d19754a0e8df5aaeb73a5b763517bc4c5aa5a413fd4b08e8f11d0725f8e066ac"
EXPECTED_PILOT = {
    "games_max": 3, "passes": 1, "concurrency": 1, "actions_max": 80,
    "runtime_seconds_max": 1200, "competition_rerun_allowed": False,
}
COMMON_BUILD = (
    "builder_source_sha256", "runtime_adapter_sha256", "base_notebook_sha256",
    "source_preparation_manifest_sha256", "bridge_sha256", "bundle_sha256",
    "patched_solver_sha256", "tool_agent_source_unchanged_sha256", "shared_model_seed",
    "pilot", "budgets_per_game",
)
HDS_COUNTS = (
    "updates_attempted", "updates_succeeded", "queries_attempted", "queries_succeeded",
    "update_errors", "query_errors", "summary_errors", "prior_updates_attempted",
    "prior_updates_succeeded", "prior_update_errors", "skipped_resets",
    "rejected_requests", "budget_exhaustion_requests",
)
HDS_SECONDS = ("update_seconds", "query_seconds", "total_hds_seconds", "prior_load_seconds")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "expected a JSON object")
    return value


def helper() -> Any:
    require(sha256(HELPER) == HELPER_SHA, "existing score helper hash changed")
    spec = importlib.util.spec_from_file_location("arc3_c2059_score_helper", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def nonnegative(value: Any, label: str, *, integer: bool = False) -> float | int:
    require(type(value) in ({int} if integer else {int, float}), f"invalid {label}")
    require(math.isfinite(value) and value >= 0, f"invalid {label}")
    return value


def output_manifest_digest(files: list[dict[str, Any]]) -> str:
    """Same path/NUL/hash/NUL/bytes convention as the existing helper's manifest."""
    return hashlib.sha256("".join(
        f"{row['path']}\0{row['sha256']}\0{row['bytes']}\n"
        for row in sorted(files, key=lambda row: row["path"])
    ).encode()).hexdigest()


def repo_evidence_path(value: Any, *, absolute_allowed: bool = False) -> Path:
    require(isinstance(value, str) and value, "missing identity evidence path")
    path = Path(value)
    if not path.is_absolute():
        relative = PurePosixPath(value)
        require("\\" not in value and ":" not in value and ".." not in relative.parts
                and value == relative.as_posix(), "unsafe identity evidence path")
        path = ROOT / path
    else:
        require(absolute_allowed, "identity proof paths must be repo-relative")
    require(path.resolve().is_relative_to(ROOT.resolve()), "identity evidence escapes repository")
    return path.resolve()


def canonical_cells(notebook: dict[str, Any]) -> list[dict[str, str]]:
    cells = notebook.get("cells")
    require(isinstance(cells, list) and cells, "missing identity notebook cells")
    result = []
    for cell in cells:
        require(isinstance(cell, dict) and cell.get("cell_type") in {"code", "markdown", "raw"},
                "invalid identity notebook cell type")
        source = cell.get("source", "")
        require(isinstance(source, str) or
                isinstance(source, list) and all(isinstance(s, str) for s in source),
                "invalid identity notebook cell source")
        result.append({"cell_type": cell["cell_type"],
                       "source": "".join(source) if isinstance(source, list) else source})
    return result


def verify_kernel_identity(doc: dict[str, Any], build: dict[str, Any],
                           metadata: dict[str, Any], version: int) -> dict[str, Any]:
    requested, actual = metadata.get("id"), doc.get("kernel")
    identity = {"requested_kernel": requested, "actual_kernel": actual,
                "identity_alias_applied": requested != actual}
    if requested == actual and not any(k in doc for k in
                                      ("identity_verification", "identity_verification_sha256")):
        return identity
    require(isinstance(requested, str) and isinstance(actual, str)
            and re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", requested) is not None
            and re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", actual) is not None
            and requested.split("/")[0] == actual.split("/")[0], "invalid kernel identity alias")
    require("identity_verification" in doc and "identity_verification_sha256" in doc,
            "kernel identity mismatch requires explicit verified identity proof")
    proof_path = repo_evidence_path(doc["identity_verification"])
    require(sha256(proof_path) == doc["identity_verification_sha256"], "identity proof hash mismatch")
    proof = load(proof_path)
    require(proof.get("schema") == "arc3-returned-kernel-identity-source-verification.v1"
            and proof.get("requested_kernel") == requested and proof.get("actual_kernel") == actual
            and type(proof.get("version")) is int and proof["version"] == version,
            "identity proof kernel/version mismatch")
    require(proof.get("status_command_exit_code") == 0 and proof.get("read_only_pull_exit_code") == 0
            and proof.get("notebook_resubmitted_or_edited") is False
            and proof.get("official_submission_or_rerun_performed") is False,
            "identity source retrieval/operation evidence invalid")

    local_path = repo_evidence_path(proof.get("local_notebook"))
    remote_path = repo_evidence_path(proof.get("remote_notebook"))
    remote_meta_path = repo_evidence_path(proof.get("remote_metadata"))
    for path, field in ((local_path, "local_notebook_sha256"),
                        (remote_path, "remote_notebook_sha256"),
                        (remote_meta_path, "remote_metadata_sha256")):
        require(sha256(path) == proof.get(field), "identity source raw hash mismatch")
    local_meta_path = local_path.parent / "kernel-metadata.json"
    require(local_meta_path.resolve().is_relative_to(ROOT.resolve()), "identity metadata escapes repository")
    require(sha256(local_path) == build["output_notebook_sha256"]
            and sha256(local_meta_path) == proof.get("local_metadata_sha256")
            == build["kernel_metadata_sha256"] and load(local_meta_path) == metadata,
            "identity local source differs from build")
    local_cells, remote_cells = canonical_cells(load(local_path)), canonical_cells(load(remote_path))
    source_digest = hashlib.sha256(json.dumps(local_cells, ensure_ascii=False,
                                               separators=(",", ":")).encode("utf-8")).hexdigest()
    require(local_cells == remote_cells and len(local_cells) == proof.get("local_cells")
            and len(remote_cells) == proof.get("remote_cells")
            and proof.get("all_cell_types_and_joined_sources_match") is True
            and source_digest == proof.get("canonical_cell_source_sha256"),
            "identity notebook sources differ")

    remote_meta = load(remote_meta_path)
    require(metadata.get("code_file") == local_path.name and remote_meta.get("code_file") == remote_path.name
            and remote_meta.get("id") == actual, "identity remote code/id mismatch")
    require(metadata.get("id_no") is None and type(remote_meta.get("id_no")) is int
            and remote_meta["id_no"] > 0 and metadata.get("enable_tpu") in (None, False)
            and remote_meta.get("enable_tpu") is False and metadata.get("keywords") in (None, [])
            and remote_meta.get("keywords") == [], "unexpected server metadata normalization")
    normalized_keys = {"id", "code_file", "id_no", "enable_tpu", "keywords"}
    require({k: v for k, v in metadata.items() if k not in normalized_keys}
            == {k: v for k, v in remote_meta.items() if k not in normalized_keys},
            "identity remote runtime/model configuration differs")
    differences = {k: {"requested": metadata.get(k), "returned": remote_meta.get(k)}
                   for k in sorted(set(metadata) | set(remote_meta))
                   if metadata.get(k) != remote_meta.get(k)}
    require(differences == proof.get("metadata_differences"), "identity metadata differences mismatch")

    receipt_path = repo_evidence_path(proof.get("push_receipt"))
    require(sha256(receipt_path) == proof.get("push_receipt_sha256"), "identity receipt hash mismatch")
    receipt = load(receipt_path)
    matches = re.findall(r"(?m)^Kernel version ([1-9][0-9]*) successfully pushed\.\s+"
                         r"Please check progress at https://www\.kaggle\.com/code/"
                         r"([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)(?:\s|$)",
                         receipt.get("stdout", ""))
    require(type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0
            and matches == [(str(version), actual)],
            "identity push receipt actual URL/version mismatch")
    request_path = repo_evidence_path(receipt.get("request"))
    request = load(request_path)
    require(request.get("schema") == "arc3-private-kernel-push-request.v1"
            and request.get("kernel") == requested and request.get("official_submission_or_rerun") is False
            and request.get("notebook_sha256") == build["output_notebook_sha256"]
            and request.get("metadata_sha256") == build["kernel_metadata_sha256"]
            and request.get("bundle_sha256") == build["bundle_sha256"],
            "identity push request source/configuration mismatch")
    command = request.get("command")
    require(isinstance(command, list) and all(isinstance(x, str) for x in command)
            and len(command) >= 5 and command[1:3] == ["kernels", "push"]
            and len(command[3:]) % 2 == 0, "identity push request command invalid")
    options = dict(zip(command[3::2], command[4::2]))
    require(len(options) == len(command[3::2]) and set(options) <= {"--path", "--timeout"}
            and "--path" in options, "identity push request options invalid")
    require(repo_evidence_path(options["--path"], absolute_allowed=True) == local_path.parent,
            "identity push request source directory mismatch")
    identity["identity_evidence"] = {
        "verification_sha256": sha256(proof_path), "receipt_sha256": sha256(receipt_path),
        "request_sha256": sha256(request_path), "remote_notebook_sha256": sha256(remote_path),
        "remote_metadata_sha256": sha256(remote_meta_path),
        "canonical_cell_source_sha256": source_digest, "all_cells_verified": len(local_cells),
        "remote_runtime_model_configuration_verified": True, "version": version,
    }
    return identity


def verify_retrieval(doc: dict[str, Any], output_root: Path, build: dict[str, Any],
                     metadata: dict[str, Any], version: int) -> tuple[set[str], dict[str, Any]]:
    require(doc.get("schema") == "arc26-arc3-private-kernel-terminal-output.v1",
            "unknown terminal retrieval schema")
    require(doc.get("terminal") is True and doc.get("status") == "KernelWorkerStatus.COMPLETE",
            "exact-version retrieval is not terminal COMPLETE")
    require(type(doc.get("version")) is int and doc["version"] == version and version > 0,
            "wrong exact kernel version")
    identity = verify_kernel_identity(doc, build, metadata, version)
    require(doc.get("output_exit_code") == 0, "output retrieval did not succeed")
    for recorded, expected in (
        ("candidate_notebook_sha256", "output_notebook_sha256"),
        ("candidate_metadata_sha256", "kernel_metadata_sha256"),
    ):
        require(doc.get(recorded) == build.get(expected), "retrieved source hash differs from build")
    declared_root = Path(doc.get("output_directory", ""))
    if not declared_root.is_absolute():
        declared_root = ROOT / declared_root
    require(declared_root.resolve() == output_root.resolve(), "wrong output directory")
    files = doc.get("output_files")
    require(isinstance(files, list) and files, "missing selected output manifest")
    paths: set[str] = set()
    for row in files:
        require(isinstance(row, dict), "invalid selected file record")
        name = row.get("path")
        require(isinstance(name, str) and "\\" not in name, "noncanonical output path")
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and name == rel.as_posix() and ":" not in name
                and ".." not in rel.parts and name not in paths, "unsafe/duplicate output path")
        paths.add(name)
        path = output_root / name
        require(path.is_file() and path.resolve().is_relative_to(output_root.resolve()),
                "missing selected output file")
        require(type(row.get("bytes")) is int and row["bytes"] == path.stat().st_size
                and row.get("sha256") == sha256(path), "selected output file hash/size mismatch")
    require(doc.get("output_manifest_sha256") == output_manifest_digest(files),
            "selected output manifest hash mismatch")
    return paths, identity


def aggregate_hds(mode: str, rows: list[dict[str, Any]], histories: list[list[dict[str, Any]]],
                  budgets: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    stats: Counter[str] = Counter()
    seconds: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    prior_status: Counter[str] = Counter()
    budget_exhausted: Counter[str] = Counter()
    measurement_revisions: Counter[str] = Counter()
    connected = 0
    max_time_overrun = 0.0
    valid = True
    for row, history in zip(rows, histories):
        require(row.get("schema") == "arc3-visual-hds-shadow-telemetry.v1"
                and row.get("mode") == mode, "wrong HDS telemetry schema/mode")
        require(row.get("authorization") is False and row.get("continue_visual_solver") is True
                and row.get("model_context_modified") is False,
                "HDS telemetry violates shadow/action boundary")
        c = row.get("counts")
        require(isinstance(c, dict), "missing HDS counters")
        revision = row.get("prediction_measurement_revision")
        require(revision in {None, "native-target-outcome-prequential.v1"},
                "unknown prediction measurement revision")
        measurement_revisions[revision or "render_hint_only"] += 1
        require(revision is not None or not any(k.startswith(("target_qualified_", "target_forecast_"))
                                                for k in c), "unversioned target forecast counters")
        for key, value in c.items():
            counts[key] += nonnegative(value, "HDS counter", integer=True)
        require(c.get("actual_action_calls_seen") == len(history),
                "HDS actual-action count differs from saved history")
        require(c.get("supported_unique_prediction_matches", 0)
                <= c.get("supported_unique_predictions_observed", 0), "invalid HDS match count")
        require(c.get("target_qualified_unique_prediction_matches", 0)
                <= c.get("target_qualified_unique_predictions_observed", 0)
                <= c.get("target_qualified_forecast_queries", 0), "invalid target forecast count")
        adapter_error = row.get("last_adapter_error")
        if adapter_error:
            errors[str(adapter_error)] += 1
            valid = False
        if mode == "off":
            require(row.get("hds") is None and row.get("prior") is None
                    and not any(value for key, value in c.items()
                                if key.startswith(("query_", "update_", "queries_", "supported_", "target_"))),
                    "off arm performed HDS work")
            continue
        hds = row.get("hds")
        prior = row.get("prior")
        if not isinstance(hds, dict) or not isinstance(prior, dict):
            valid = False
            prior_status["bridge_unavailable"] += 1
            continue
        for key in HDS_COUNTS:
            stats[key] += nonnegative(hds.get(key), key, integer=True)
        for key in HDS_SECONDS:
            seconds[key] += nonnegative(hds.get(key), key)
        for key in ("update_budget", "query_budget", "hds_seconds_budget"):
            require(hds.get(key) == budgets.get(key), "HDS runtime/build budget mismatch")
        for kind, plural in (("update", "updates"), ("query", "queries")):
            require(hds[f"{plural}_succeeded"] <= hds[f"{plural}_attempted"]
                    <= budgets[f"{kind}_budget"], "HDS operation count exceeds budget")
        for key in ("update_budget_exhausted", "query_budget_exhausted", "time_budget_exhausted"):
            require(type(hds.get(key)) is bool, "missing HDS exhaustion flag")
            budget_exhausted[key] += int(hds[key])
        max_time_overrun = max(max_time_overrun,
                               hds["total_hds_seconds"] - budgets["hds_seconds_budget"])
        prior_status[str(prior.get("load_status", "missing"))] += 1
        loaded = (prior.get("load_status") == "loaded" and prior.get("loaded_count") == 5
                  and prior.get("action_authorization") is False)
        active = hds["updates_succeeded"] > 0 and hds["queries_succeeded"] > 0
        connected += int(loaded and active)
        valid &= loaded and active
        if hds.get("last_error_type"):
            errors[str(hds["last_error_type"])] += 1
            valid = False
    adapter_errors = sum(v for k, v in counts.items()
                         if k.endswith("_errors") or k in {
                             "unavailable_bridge", "public_state_changed_during_HDS_query",
                             "public_action_step_mismatch"})
    hds_errors = sum(stats[k] for k in ("update_errors", "query_errors", "summary_errors",
                                      "prior_update_errors", "rejected_requests"))
    require(len(measurement_revisions) == 1, "inconsistent prediction measurement revisions")
    valid &= adapter_errors == 0 and hds_errors == 0
    observed = counts["supported_unique_predictions_observed"]
    matches = counts["supported_unique_prediction_matches"]
    target_observed = counts["target_qualified_unique_predictions_observed"]
    target_matches = counts["target_qualified_unique_prediction_matches"]
    return {
        "sidecars": len(rows), "integration_valid": bool(valid),
        "games_with_prior_and_actual_query_update": connected,
        "counters": dict(sorted(counts.items())), "operations": dict(sorted(stats.items())),
        "seconds": dict(sorted(seconds.items())), "prior_status_counts": dict(prior_status),
        "error_type_counts": dict(errors), "adapter_error_count": adapter_errors,
        "HDS_error_count": hds_errors, "budget_exhausted_game_counts": dict(budget_exhausted),
        "budgets_per_game": budgets, "max_soft_time_budget_overrun_seconds": max_time_overrun,
        "soft_time_budget_can_overrun_one_inflight_call": True,
        "off_zero_HDS_confirmed": mode == "off",
        "prediction_measurement_revision_counts": dict(measurement_revisions),
        "prediction_match_measurement": {
            "status": ("NOT_APPLICABLE_OFF" if mode == "off" else
                       "CONDITIONAL_RENDERED_CONTEXT_ONLY" if observed else
                       "UNMEASURED_NO_RENDERED_SUPPORTED_CONTEXT"),
            "observations": observed, "matches": matches,
            "conditional_match_fraction": matches / observed if observed else None,
            "limitation": "Rendered-context telemetry uses render_hint; a global native HOLD can suppress target-supported predictions. Zero observed matches do not establish absence of learned rules.",
        },
        "target_qualified_prediction_measurement": {
            "status": ("NOT_APPLICABLE_OFF" if mode == "off" else
                       "MEASURED_PREQUENTIAL_TARGET_FORECAST" if target_observed else
                       "UNMEASURED_NO_UNIQUE_TARGET_FORECAST"),
            "forecast_queries": counts["target_qualified_forecast_queries"],
            "unique_predictions_observed": target_observed, "matches": target_matches,
            "conditional_match_fraction": target_matches / target_observed if target_observed else None,
            "multiple_prediction_values": counts["target_qualified_multiple_prediction_values"],
            "native_status_counts": {k.split(":", 1)[1]: v for k, v in counts.items()
                                     if k.startswith("target_qualified_unique_native_status:")},
            "blocked_reason_counts": {k.split(":", 1)[1]: v for k, v in counts.items()
                                      if k.startswith("target_forecast_blocked:")},
            "causal_learning_or_score_improvement_proven": False,
        },
    }


def inspect_arm(retrieval_path: Path, build_path: Path, output_root: Path,
                version: int, mode: str, scorer: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    build, retrieval = load(build_path), load(retrieval_path)
    require(build.get("schema") == "arc3-visual-hds-pilot-build.v1"
            and build.get("mode") == mode, "wrong pilot build/mode")
    require(build.get("pilot") == EXPECTED_PILOT and build.get("shared_model_seed") == 0,
            "pilot budget/model seed differs from matched three-game contract")
    budgets = build.get("budgets_per_game")
    require(budgets == {"update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120},
            "unexpected HDS pilot budgets")
    metadata = load(build_path.parent / "kernel-metadata.json")
    for filename, field in (("submission.ipynb", "output_notebook_sha256"),
                            ("kernel-metadata.json", "kernel_metadata_sha256"),
                            ("visual-hds-source.zip", "bundle_sha256")):
        require(sha256(build_path.parent / filename) == build.get(field), "build source hash mismatch")
    require(metadata.get("is_private") is True and metadata.get("enable_internet") is False
            and metadata.get("enable_gpu") is True, "expected private offline GPU pilot metadata")
    paths, identity = verify_retrieval(retrieval, output_root, build, metadata, version)
    require("benchmark.json" in paths, "missing benchmark in selected output manifest")
    benchmark = load(output_root / "benchmark.json")
    runs = benchmark.get("game_runs")
    require(isinstance(runs, list) and len(runs) == 3 and benchmark.get("n_passes") == 1,
            "expected exactly three games and one pass")
    keyed = {r.get("game_id"): r for r in runs}
    require(len(keyed) == 3 and all(isinstance(k, str) and k for k in keyed),
            "missing/duplicate game identities")
    scores, starts, telemetry, histories = {}, {}, [], []
    for gid, run in keyed.items():
        required = (f"artifacts/{gid}_p0_events.jsonl",
                    f"artifacts/{gid}_p0_tool_runtime_state.visual-hds.json")
        require(all(name in paths for name in required), "missing initial event/HDS sidecar")
        starts[gid] = scorer.first_event(output_root, gid)
        require(all(f in starts[gid] for f in scorer.START_FIELDS), "incomplete public initial event")
        score = scorer.score_run(run)
        require(type(run.get("final_score")) in {int, float}
                and math.isfinite(run["final_score"])
                and abs(score - run["final_score"]) <= 1e-9, "saved final_score mismatch")
        scores[gid] = score
        history = run.get("history")
        require(isinstance(history, list) and all(isinstance(h, dict) for h in history),
                "missing actual action history")
        require(len(history) == sum(run["actions_per_level"]) <= EXPECTED_PILOT["actions_max"],
                "pilot actual action budget/history mismatch")
        histories.append(history)
        telemetry.append(load(output_root / required[1]))
    clocks = audit_benchmark(benchmark)
    elapsed = [r["elapsed_since_previous_game_seconds"] for r in clocks["game_runs"]]
    require(all(type(x) in {int, float} and math.isfinite(x) and x >= 0 for x in elapsed),
            "missing/invalid cumulative game clock")
    runtime_ok = max(elapsed) <= EXPECTED_PILOT["runtime_seconds_max"] + 5.0
    hds = aggregate_hds(mode, telemetry, histories, budgets)
    states = Counter(str(r.get("state")) for r in runs)
    model_generation_observed = clocks["total_history_generated_tokens"] > 0
    generation_flags = [r["history_generated_tokens"] > 0 for r in clocks["game_runs"]]
    all_games_generated = all(generation_flags)
    execution_ok = set(states) <= {"gave_up", "won"} and runtime_ok and all_games_generated
    result = {
        "kernel": retrieval["kernel"], "version": version, "status": retrieval["status"],
        **identity,
        "mode": mode, "build_manifest_sha256": sha256(build_path),
        "retrieval_manifest_sha256": sha256(retrieval_path),
        "notebook_sha256": build["output_notebook_sha256"],
        "selected_output_manifest_sha256": retrieval["output_manifest_sha256"],
        "selected_output_file_count": len(paths),
        "retrieval_scope": retrieval.get("retrieval_scope", "only explicitly listed output_files"),
        "benchmark_sha256": sha256(output_root / "benchmark.json"),
        "games": 3, "public_offline_RHAE_mean": mean(scores.values()),
        "saved_scores_match_recomputed": True, "run_state_counts": dict(states),
        "levels_completed": sum(r["levels_completed"] for r in runs),
        "levels_total": sum(r["number_of_levels"] for r in runs),
        "actual_actions": sum(map(len, histories)),
        "history_generated_tokens": clocks["total_history_generated_tokens"],
        "visual_model_generation_observed": model_generation_observed,
        "all_games_visual_model_generation_observed": all_games_generated,
        "games_with_visual_model_generation": sum(generation_flags),
        "visual_generation_flags_in_benchmark_order_when_invalid": (
            generation_flags if not all_games_generated else None),
        "job_elapsed_seconds": clocks["job_elapsed_seconds"],
        "max_game_elapsed_seconds": max(elapsed), "runtime_budget_compliant_with_5s_grace": runtime_ok,
        "pilot": build["pilot"], "shared_model_seed": 0, "HDS": hds,
        "execution_valid": execution_ok,
        "integration_valid": execution_ok and hds["integration_valid"],
    }
    return result, {"runs": keyed, "starts": starts, "scores": scores,
                    "build": build, "metadata": metadata}


def compare(off: dict[str, Any], shadow: dict[str, Any], scorer: Any) -> dict[str, Any]:
    require(set(off["runs"]) == set(shadow["runs"]), "paired game sets differ")
    require(all(off["build"].get(k) == shadow["build"].get(k) for k in COMMON_BUILD),
            "paired source/configuration/budgets differ")
    metadata = lambda d: {k: v for k, v in d["metadata"].items() if k not in {"id", "title"}}
    require(metadata(off) == metadata(shadow), "paired model/dataset/GPU metadata differs")
    for gid in off["runs"]:
        require(all(off["starts"][gid][field] == shadow["starts"][gid][field]
                    for field in scorer.START_FIELDS), "paired public initial fields differ")
        require(all(off["runs"][gid].get(field) == shadow["runs"][gid].get(field)
                    for field in ("number_of_levels", "base_actions_per_level")),
                "paired public levels/baselines differ")
    deltas = [shadow["scores"][gid] - off["scores"][gid] for gid in off["runs"]]
    return {"games": 3, "all_public_initial_fields_matched": True,
            "shared_source_model_pilot_and_HDS_budgets_matched": True,
            "descriptive_mean_RHAE_delta_shadow_minus_off": mean(deltas),
            "descriptive_game_score_direction_counts": {
                "higher": sum(x > 1e-9 for x in deltas),
                "equal": sum(abs(x) <= 1e-9 for x in deltas),
                "lower": sum(x < -1e-9 for x in deltas)},
            "causal_learning_or_score_improvement_proven": False}


def report_header(scorer: Any) -> dict[str, Any]:
    score_source = Path(inspect.getsourcefile(scorer.EnvironmentScoreCalculator))
    return {
        "schema": "arc3-visual-hds-matched-scorecard.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "inspection": "control_only", "score_helper_sha256": HELPER_SHA,
        "score_source": "arc_agi.scorecard.EnvironmentScoreCalculator",
        "score_source_file_sha256": sha256(score_source),
        "scorecard_source_sha256": sha256(Path(__file__)),
        "official_score_observed": False,
        "official_submission_or_quota_use": False,
        "causal_learning_or_score_improvement_proven": False,
        "limitation": "Shadow does not alter model context/actions; fixed model seed does not prove GPU determinism. Repeats are required for causal comparisons.",
    }


def evaluate_single(retrieval_path: Path, build_path: Path, output_root: Path,
                    version: int) -> dict[str, Any]:
    mode = load(build_path).get("mode")
    require(mode in {"off", "shadow"}, "single arm must be off or shadow")
    scorer = helper()
    arm, _ = inspect_arm(retrieval_path, build_path, output_root, version, mode, scorer)
    result = report_header(scorer)
    result.update(inspection=f"single_{mode}", arm=arm,
                  integration_valid=arm["integration_valid"], paired_comparison_performed=False)
    return result


def evaluate(off_retrieval: Path, off_build: Path, off_output_root: Path, off_version: int,
             *, shadow_retrieval: Path | None = None, shadow_build: Path | None = None,
             shadow_output_root: Path | None = None, shadow_version: int | None = None) -> dict[str, Any]:
    scorer = helper()
    off_result, off_internal = inspect_arm(off_retrieval, off_build, off_output_root,
                                          off_version, "off", scorer)
    result = report_header(scorer)
    result["off"] = off_result
    optional = (shadow_retrieval, shadow_build, shadow_output_root, shadow_version)
    require(all(x is None for x in optional) or all(x is not None for x in optional),
            "shadow requires retrieval/build/output-root/exact-version together")
    if shadow_retrieval is not None:
        shadow_result, shadow_internal = inspect_arm(shadow_retrieval, shadow_build,
                                                     shadow_output_root, shadow_version,
                                                     "shadow", scorer)
        result.update(inspection="paired", shadow=shadow_result,
                      paired=compare(off_internal, shadow_internal, scorer))
        result["integration_valid"] = off_result["integration_valid"] and shadow_result["integration_valid"]
    else:
        result["control_valid_for_shadow"] = off_result["integration_valid"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    entry = parser.add_mutually_exclusive_group(required=True)
    entry.add_argument("--off-retrieval", type=Path)
    entry.add_argument("--single-retrieval", type=Path)
    for arm in ("off", "shadow", "single"):
        for field in ("retrieval", "build", "output-root", "version"):
            if field == "retrieval" and arm in {"off", "single"}:
                continue
            parser.add_argument(f"--{arm}-{field}", type=int if field == "version" else Path,
                                required=False)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing scorecard")
    try:
        if args.single_retrieval is not None:
            require(all(getattr(args, f"single_{name}") is not None
                        for name in ("build", "output_root", "version")),
                    "single requires build/output-root/exact-version")
            require(all(getattr(args, f"{arm}_{name}") is None
                        for arm in ("off", "shadow")
                        for name in ("retrieval", "build", "output_root", "version")),
                    "single inspection cannot include control/paired arguments")
            result = evaluate_single(args.single_retrieval, args.single_build,
                                     args.single_output_root, args.single_version)
        else:
            require(all(getattr(args, f"off_{name}") is not None
                        for name in ("build", "output_root", "version")),
                    "off requires build/output-root/exact-version")
            require(all(getattr(args, f"single_{name}") is None
                        for name in ("build", "output_root", "version")),
                    "paired inspection cannot include single arguments")
            result = evaluate(args.off_retrieval, args.off_build, args.off_output_root, args.off_version,
                              shadow_retrieval=args.shadow_retrieval, shadow_build=args.shadow_build,
                              shadow_output_root=args.shadow_output_root, shadow_version=args.shadow_version)
    except (ValueError, KeyError, OSError, StopIteration, TypeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
