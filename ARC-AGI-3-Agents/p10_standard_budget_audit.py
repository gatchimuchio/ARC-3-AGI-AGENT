"""Build a content-bound audit for the P10 all-sample standard-budget run."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc3_agi_agent.schema import digest_object

SCHEMA_VERSION = "arc3-p10-standard-budget-all25-audit-v1"
ARTIFACT_TYPE = "p10_standard_budget_all25_audit"
EXPECTED_GAME_COUNT = 25
EXPECTED_LEVEL_COUNT = 183
EXPECTED_MAX_ACTIONS = 450
_TIME_PATTERN = re.compile(
    r"^elapsed=(?P<elapsed>[0-9]+(?:\.[0-9]+)?) "
    r"max_rss_kb=(?P<rss>[0-9]+)"
    r"(?: swaps=(?P<swaps>[0-9]+))?"
    r"(?: exit=(?P<exit>[0-9]+))?$",
    re.MULTILINE,
)


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _floating(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _json(path: Path, field_name: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _file_ref(path: Path, repository_root: Path) -> dict[str, object]:
    try:
        display_path = path.resolve().relative_to(
            repository_root.resolve()
        ).as_posix()
    except ValueError:
        display_path = str(path.resolve())
    return {
        "path": display_path,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _content_digest_valid(
    value: Mapping[str, Any],
    *,
    prefix: str = "",
) -> bool:
    body = copy.deepcopy(dict(value))
    claimed = body.pop("content_digest", None)
    return bool(claimed == prefix + digest_object(body))


def _checkpoint_inventory(
    checkpoint_dir: Path,
    conditions_digest: str,
) -> tuple[list[dict[str, object]], bool]:
    rows: list[dict[str, object]] = []
    valid = True
    for path in sorted(checkpoint_dir.glob("*.checkpoint.json")):
        checkpoint = _json(path, f"checkpoint {path.name}")
        body = copy.deepcopy(checkpoint)
        claimed = body.pop("content_digest", None)
        valid = (
            valid
            and claimed == digest_object(body)
            and checkpoint.get("conditions_digest") == conditions_digest
        )
        rows.append(
            {
                "filename": path.name,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "game_id": checkpoint.get("game_id"),
                "stable_report_digest": checkpoint.get(
                    "stable_report_digest"
                ),
            }
        )
    return rows, valid


def _resource_rows(
    *,
    game_ids: Sequence[str],
    log_dirs: Sequence[Path],
) -> tuple[list[dict[str, object]], bool]:
    rows: list[dict[str, object]] = []
    complete = True
    for game_id in game_ids:
        candidates: list[tuple[Path, re.Match[str]]] = []
        executed_logs = 0
        for directory in log_dirs:
            worker_path = directory / f"{game_id}.log"
            if worker_path.is_file():
                worker_text = worker_path.read_text(encoding="utf-8")
                if '"status": "EXECUTED"' in worker_text:
                    executed_logs += 1
                worker_match = _TIME_PATTERN.search(worker_text)
                if worker_match is not None:
                    candidates.append((worker_path, worker_match))
            timing_path = directory / f"{game_id}.time.log"
            if timing_path.is_file():
                timing_text = timing_path.read_text(encoding="utf-8")
                timing_match = _TIME_PATTERN.search(timing_text)
                if timing_match is not None:
                    candidates.append((timing_path, timing_match))
        if not candidates or executed_logs != 1:
            complete = False
            continue
        if len(candidates) != 1:
            raise ValueError(f"P10_RESOURCE_LOG_AMBIGUOUS:{game_id}")
        path, match = candidates[0]
        rows.append(
            {
                "game_id": game_id,
                "elapsed_wall_seconds": float(match.group("elapsed")),
                "maximum_rss_kb": int(match.group("rss")),
                "swaps": (
                    None
                    if match.group("swaps") is None
                    else int(match.group("swaps"))
                ),
                "exit_code": (
                    None
                    if match.group("exit") is None
                    else int(match.group("exit"))
                ),
                "log_sha256": _sha256(path),
            }
        )
    return rows, complete and len(rows) == len(game_ids)


def build_standard_budget_audit(
    *,
    raw_report_path: Path,
    compact_evidence_path: Path,
    oracle_path: Path,
    checkpoint_dir: Path,
    log_dirs: Sequence[Path],
    repository_root: Path,
    parallel_worker_limit: int,
    observed_parallel_peak_swap_mb: int,
) -> dict[str, object]:
    """Validate and bind one exact all-25 max-450 measurement."""

    raw_report = _json(raw_report_path, "raw report")
    compact = _json(compact_evidence_path, "compact evidence")
    oracle = _json(oracle_path, "local oracle")
    index_path = checkpoint_dir / "CHECKPOINT_INDEX.json"
    index = _json(index_path, "checkpoint index")

    checkpointing = _mapping(
        raw_report.get("checkpointing"),
        "raw report checkpointing",
    )
    conditions = _mapping(
        checkpointing.get("conditions"),
        "raw report checkpoint conditions",
    )
    conditions_digest = str(conditions.get("conditions_digest", ""))
    game_ids = [
        str(value)
        for value in _sequence(
            conditions.get("game_ids"),
            "checkpoint game ids",
        )
    ]
    reports = [
        _mapping(value, "game report")
        for value in _sequence(raw_report.get("reports"), "raw reports")
    ]
    errors = _sequence(raw_report.get("errors"), "raw errors")
    report_game_ids = [str(report.get("game_id", "")) for report in reports]
    probe_fault_count = 0
    action_influence_count = 0
    for report in reports:
        probe = _mapping(
            report.get("development_transition_probe"),
            "development transition probe",
        )
        probe_fault_count += _integer(
            probe.get("fault_count"),
            "probe fault count",
        )
        action_influence_count += int(
            bool(probe.get("action_selection_influence"))
        )

    checkpoint_rows, checkpoints_valid = _checkpoint_inventory(
        checkpoint_dir,
        conditions_digest,
    )
    resource_rows, resource_logs_complete = _resource_rows(
        game_ids=game_ids,
        log_dirs=log_dirs,
    )
    max_resource = (
        max(
            resource_rows,
            key=lambda row: _integer(
                row["maximum_rss_kb"],
                "resource maximum RSS",
            ),
        )
        if resource_rows
        else None
    )
    worker_swap_count = sum(
        _integer(row["swaps"], "resource swaps")
        for row in resource_rows
        if row["swaps"] is not None
    )
    worker_swap_measurement_complete = all(
        row["swaps"] is not None for row in resource_rows
    )
    worker_nonzero_exit_count = sum(
        _integer(row["exit_code"], "resource exit code") != 0
        for row in resource_rows
        if row["exit_code"] is not None
    )
    worker_exit_measurement_complete = all(
        row["exit_code"] is not None for row in resource_rows
    )
    compact_summary = _mapping(
        compact.get("summary"),
        "compact summary",
    )
    oracle_result = _mapping(
        oracle.get("current_local_result"),
        "oracle current result",
    )
    oracle_source = _mapping(oracle.get("source"), "oracle source")
    index_conditions = _mapping(
        index.get("conditions"),
        "index conditions",
    )
    checks = {
        "raw_report_is_offline_active_hybrid": (
            raw_report.get("phase") == "P10"
            and str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
            and raw_report.get("instruction_lifecycle") == "active"
            and raw_report.get("instruction_variant") == "hybrid"
        ),
        "standard_budget_is_450": (
            _integer(raw_report.get("max_actions"), "max actions")
            == EXPECTED_MAX_ACTIONS
            and _integer(conditions.get("max_actions"), "condition max actions")
            == EXPECTED_MAX_ACTIONS
        ),
        "all_25_games_and_183_levels_are_represented": (
            len(game_ids) == EXPECTED_GAME_COUNT
            and len(set(game_ids)) == EXPECTED_GAME_COUNT
            and sorted(report_game_ids) == sorted(game_ids)
            and _integer(raw_report.get("completed_count"), "completed count")
            == EXPECTED_GAME_COUNT
            and _integer(raw_report.get("total_levels"), "total levels")
            == EXPECTED_LEVEL_COUNT
        ),
        "runtime_errors_are_zero": (
            _integer(raw_report.get("error_count"), "error count") == 0
            and not errors
        ),
        "transition_probe_faults_are_zero": probe_fault_count == 0,
        "transition_probe_action_influence_is_zero": (
            action_influence_count == 0
        ),
        "checkpoint_conditions_digest_is_valid": (
            conditions_digest
            == digest_object(
                {
                    key: value
                    for key, value in conditions.items()
                    if key != "conditions_digest"
                }
            )
        ),
        "all_checkpoint_payloads_are_valid": (
            len(checkpoint_rows) == EXPECTED_GAME_COUNT
            and checkpoints_valid
            and sorted(str(row["game_id"]) for row in checkpoint_rows)
            == sorted(game_ids)
        ),
        "exact_condition_resume_reused_25_executed_zero": (
            _integer(
                checkpointing.get("reused_game_count"),
                "reused game count",
            )
            == EXPECTED_GAME_COUNT
            and _integer(
                checkpointing.get("executed_game_count"),
                "executed game count",
            )
            == 0
            and len(
                _sequence(
                    index.get("reused_game_ids"),
                    "index reused ids",
                )
            )
            == EXPECTED_GAME_COUNT
            and not _sequence(
                index.get("remaining_game_ids"),
                "index remaining ids",
            )
        ),
        "checkpoint_index_is_content_bound": (
            _content_digest_valid(index)
            and dict(index_conditions) == dict(conditions)
        ),
        "compact_evidence_is_content_bound_and_matches_raw": (
            _content_digest_valid(compact)
            and compact_summary.get("completed_levels")
            == raw_report.get("completed_levels")
            and compact_summary.get("error_count")
            == raw_report.get("error_count")
            and compact_summary.get("action_count")
            == sum(_integer(row.get("actions"), "report actions") for row in reports)
        ),
        "oracle_is_bound_to_raw_report_and_183_level_zip": (
            oracle_source.get("p10_report_sha256")
            == _sha256(raw_report_path)
            and oracle_result.get("completed_levels")
            == raw_report.get("completed_levels")
            and _mapping(oracle.get("oracle"), "oracle metadata").get(
                "game_count"
            )
            == EXPECTED_GAME_COUNT
            and _mapping(oracle.get("oracle"), "oracle metadata").get(
                "level_count"
            )
            == EXPECTED_LEVEL_COUNT
        ),
        "resource_logs_cover_every_game": resource_logs_complete,
        "worker_swap_measurement_is_zero_when_present": (
            worker_swap_count == 0
        ),
        "worker_exit_codes_are_zero_when_present": (
            worker_nonzero_exit_count == 0
        ),
        "active_p_is_unchanged": (
            conditions.get("active_manifest_digest")
            == "6b67437d771d2a31f4c93303dee858f5151120412c2b7cf3ce55061b987aa2e1"
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise ValueError(
            "P10_STANDARD_BUDGET_AUDIT_FAILED:" + ",".join(failures)
        )

    completed_levels = _integer(
        raw_report.get("completed_levels"),
        "completed levels",
    )
    complete_games = _integer(
        raw_report.get("complete_game_count"),
        "complete game count",
    )
    maxed_out = _integer(
        compact_summary.get("max_action_exhausted_count"),
        "max action exhausted count",
    )
    raw_ref = _file_ref(raw_report_path, repository_root)
    compact_ref = _file_ref(compact_evidence_path, repository_root)
    oracle_ref = _file_ref(oracle_path, repository_root)
    index_ref = _file_ref(index_path, repository_root)
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "fixed_conditions": dict(conditions),
        "source_evidence": {
            "raw_report": raw_ref,
            "compact_evidence": compact_ref,
            "local_score_oracle": oracle_ref,
            "checkpoint_index": index_ref,
            "checkpoint_inventory_digest": digest_object(checkpoint_rows),
            "checkpoint_count": len(checkpoint_rows),
            "sample_zip_sha256": oracle_source.get("sample_zip_sha256"),
        },
        "summary": {
            "game_count": EXPECTED_GAME_COUNT,
            "level_count": EXPECTED_LEVEL_COUNT,
            "complete_game_count": complete_games,
            "completed_levels": completed_levels,
            "remaining_levels": EXPECTED_LEVEL_COUNT - completed_levels,
            "action_count": sum(
                _integer(row.get("actions"), "report actions")
                for row in reports
            ),
            "error_count": 0,
            "probe_fault_count": probe_fault_count,
            "max_action_exhausted_count": maxed_out,
            "official_rhae_score_percent": oracle_result.get(
                "official_rhae_score_percent"
            ),
            "completion_rate_percent": oracle_result.get(
                "completion_rate_percent"
            ),
            "score_digest": oracle.get("score_digest"),
        },
        "resource_measurement": {
            "method": "per-process /usr/bin/time maximum resident set",
            "parallel_worker_limit": parallel_worker_limit,
            "observed_parallel_peak_swap_mb": (
                observed_parallel_peak_swap_mb
            ),
            "worker_swap_measurement_complete": (
                worker_swap_measurement_complete
            ),
            "worker_swap_count": worker_swap_count,
            "worker_exit_measurement_complete": (
                worker_exit_measurement_complete
            ),
            "worker_nonzero_exit_count": worker_nonzero_exit_count,
            "sum_worker_elapsed_seconds": round(
                sum(
                    _floating(
                        row["elapsed_wall_seconds"],
                        "resource elapsed wall seconds",
                    )
                    for row in resource_rows
                ),
                2,
            ),
            "maximum_worker": max_resource,
            "high_water_threshold_kb": 1024 * 1024,
            "high_water_exceeded": bool(
                max_resource is not None
                and _integer(
                    max_resource["maximum_rss_kb"],
                    "maximum worker RSS",
                )
                > 1024 * 1024
            ),
            "worker_swap_detected": worker_swap_count > 0,
            "worker_nonzero_exit_detected": (
                worker_nonzero_exit_count > 0
            ),
            "rows": resource_rows,
        },
        "checks": checks,
        "hds_judgment": {
            "phase_a_standard_measurement_status": "PASS",
            "checkpoint_resume_status": "PASS",
            "resource_worker_completion_status": "PASS",
            "resource_headroom_status": (
                "FAIL_HIGH_WATER_OR_SWAP"
                if max_resource is not None
                and (
                    _integer(
                        max_resource["maximum_rss_kb"],
                        "maximum worker RSS",
                    )
                    > 1024 * 1024
                    or worker_swap_count > 0
                    or worker_nonzero_exit_count > 0
                )
                else "PASS"
            ),
            "capability_progress_status": "NOT_CLAIMED",
            "score_progress_status": "NOT_CLAIMED",
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "p10_completion_status": "HOLD",
            "p11_status": "GATED",
        },
        "failure_signatures": (
            [
                {
                    "failure_id": (
                        "high-water-runtime-allocation-on-standard-budget"
                    ),
                    "classification": "RESOURCE_HEADROOM_FAILURE",
                    "game_id": (
                        None
                        if max_resource is None
                        else max_resource["game_id"]
                    ),
                    "maximum_rss_kb": (
                        None
                        if max_resource is None
                        else max_resource["maximum_rss_kb"]
                    ),
                    "falsifier": (
                        "same-condition worker completes below the "
                        "one-gibibyte high-water threshold without swap"
                    ),
                }
            ]
            if max_resource is not None
            and (
                _integer(
                    max_resource["maximum_rss_kb"],
                    "maximum worker RSS",
                )
                > 1024 * 1024
                or worker_swap_count > 0
                or worker_nonzero_exit_count > 0
            )
            else []
        ),
    }
    return {
        **body,
        "content_digest": (
            "arc3_p10_standard_budget_all25_audit:" + digest_object(body)
        ),
    }


def _atomic_write(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                value,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--compact-evidence", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, action="append", required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--parallel-worker-limit", type=int, required=True)
    parser.add_argument(
        "--observed-parallel-peak-swap-mb",
        type=int,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.parallel_worker_limit < 1:
        raise ValueError("parallel worker limit must be positive")
    if args.observed_parallel_peak_swap_mb < 0:
        raise ValueError("observed swap must be nonnegative")
    audit = build_standard_budget_audit(
        raw_report_path=args.raw_report.resolve(),
        compact_evidence_path=args.compact_evidence.resolve(),
        oracle_path=args.oracle.resolve(),
        checkpoint_dir=args.checkpoint_dir.resolve(),
        log_dirs=[path.resolve() for path in args.log_dir],
        repository_root=args.repository_root.resolve(),
        parallel_worker_limit=args.parallel_worker_limit,
        observed_parallel_peak_swap_mb=(
            args.observed_parallel_peak_swap_mb
        ),
    )
    _atomic_write(args.output.resolve(), audit)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
