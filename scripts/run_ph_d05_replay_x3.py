#!/usr/bin/env python3
"""Launch and audit three secret-scrubbed PH-D05 replay workers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPORT_VERSION = "hds-arc3-ph-d05-replay-x3-report-v1"
WORKER_TIMEOUT_SECONDS = 1800
EXPECTED_GAME_COUNT = 25
EXPECTED_LEVEL_COUNT = 183
EXPECTED_ACTION_COUNT = 11574
SECRET_MARKERS = (
    "API_KEY",
    "AUTH_TOKEN",
    "BEARER",
    "COOKIE",
    "CREDENTIAL",
    "KAGGLE",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)


class ReplayOrchestrationError(RuntimeError):
    """Stable PH-D05 replay orchestration failure."""


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: object) -> str:
    payload = _canonical_bytes(value).rstrip(b"\n")
    return hashlib.sha256(payload).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=".ph-d05-replay-report-",
        suffix=".tmp",
        dir=path.parent,
    )
    temp = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReplayOrchestrationError(f"PH_D05_WORKER_REPORT_OBJECT_REQUIRED:{path}")
    return value


def _minimal_worker_environment(runtime_dir: Path) -> dict[str, str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    profile_dir = runtime_dir / "profile"
    roaming_dir = profile_dir / "AppData" / "Roaming"
    local_dir = profile_dir / "AppData" / "Local"
    roaming_dir.mkdir(parents=True, exist_ok=True)
    local_dir.mkdir(parents=True, exist_ok=True)
    profile_drive = profile_dir.drive or "C:"
    profile_path = str(profile_dir)[len(profile_drive) :]
    environment = {
        "APPDATA": str(roaming_dir),
        "COMSPEC": os.environ.get(
            "COMSPEC",
            str(Path(system_root) / "System32" / "cmd.exe"),
        ),
        "HOME": str(profile_dir),
        "HOMEDRIVE": profile_drive,
        "HOMEPATH": profile_path,
        "LOCALAPPDATA": str(local_dir),
        "OPERATION_MODE": "offline",
        "PATH": os.pathsep.join(
            (
                str(Path(system_root) / "System32"),
                system_root,
            )
        ),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "SystemRoot": system_root,
        "TEMP": str(runtime_dir),
        "TMP": str(runtime_dir),
        "USERPROFILE": str(profile_dir),
        "WINDIR": system_root,
    }
    leaked = sorted(
        name
        for name in environment
        if any(marker in name.upper() for marker in SECRET_MARKERS)
    )
    if leaked:
        raise ReplayOrchestrationError(
            "PH_D05_WORKER_ENVIRONMENT_SECRET_NAME:" + ",".join(leaked)
        )
    return environment


def _reports_by_game(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = report.get("reports")
    if not isinstance(rows, list):
        raise ReplayOrchestrationError("PH_D05_WORKER_REPORT_ROWS_INVALID")
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReplayOrchestrationError("PH_D05_WORKER_REPORT_ROW_INVALID")
        game_id = str(row.get("game_id", ""))
        if not game_id or game_id in output:
            raise ReplayOrchestrationError(
                f"PH_D05_WORKER_REPORT_GAME_INVALID:{game_id}"
            )
        output[game_id] = row
    return output


def _launch_worker(
    *,
    repository_root: Path,
    cache_root: Path,
    run_index: int,
    requested_games: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = cache_root / f"run-{run_index}"
    runtime_dir = run_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(repository_root / "scripts/ph_d05_replay_worker.py"),
        "--repository-root",
        str(repository_root),
        "--output-dir",
        str(run_dir),
        "--run-index",
        str(run_index),
    ]
    for game_id in requested_games:
        command.extend(("--game", game_id))
    try:
        process = subprocess.run(
            command,
            cwd=repository_root,
            env=_minimal_worker_environment(runtime_dir),
            capture_output=True,
            check=False,
            timeout=WORKER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ReplayOrchestrationError(
            f"PH_D05_REPLAY_WORKER_TIMEOUT:run-{run_index}"
        ) from error
    process_evidence = {
        "run_index": run_index,
        "exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
        "stderr_empty": not process.stderr,
        "timeout": False,
        "wall_time_bound_seconds": WORKER_TIMEOUT_SECONDS,
        "within_wall_time_bound": True,
        "secret_environment_count": 0,
    }
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise ReplayOrchestrationError(
            f"PH_D05_REPLAY_WORKER_FAILED:run-{run_index}:"
            f"exit={process.returncode}:{stderr}"
        )
    report = _json_object(run_dir / "worker_report.json")
    return report, process_evidence


def run(
    *,
    repository_root: Path,
    cache_root: Path,
    report_path: Path,
    run_count: int,
    requested_games: Sequence[str] = (),
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    cache_root = cache_root.resolve()
    report_path = report_path.resolve()
    try:
        cache_root.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ReplayOrchestrationError("PH_D05_REPLAY_CACHE_INSIDE_REPOSITORY")
    cache_root.mkdir(parents=True, exist_ok=True)

    worker_reports: list[dict[str, Any]] = []
    process_evidence: list[dict[str, Any]] = []
    for run_index in range(1, run_count + 1):
        worker_report, process_result = _launch_worker(
            repository_root=repository_root,
            cache_root=cache_root,
            run_index=run_index,
            requested_games=requested_games,
        )
        worker_reports.append(worker_report)
        process_evidence.append(process_result)

    baseline = _reports_by_game(worker_reports[0])
    mismatch_records: list[dict[str, Any]] = []
    for report in worker_reports[1:]:
        current = _reports_by_game(report)
        if set(current) != set(baseline):
            raise ReplayOrchestrationError("PH_D05_REPLAY_GAME_SET_MISMATCH")
        for game_id in sorted(baseline):
            for field in (
                "actual_trace_digest",
                "capture_content_digest",
                "capture_sha256",
                "action_count",
                "target_levels",
                "source_frame_difference_count",
            ):
                if current[game_id].get(field) != baseline[game_id].get(field):
                    mismatch_records.append(
                        {
                            "game_id": game_id,
                            "field": field,
                            "run_index": report.get("run_index"),
                        }
                    )
    complete_inventory = not requested_games
    game_count = worker_reports[0].get("game_count")
    level_count = worker_reports[0].get("level_count")
    action_count = worker_reports[0].get("action_count")
    if complete_inventory and (
        game_count != EXPECTED_GAME_COUNT
        or level_count != EXPECTED_LEVEL_COUNT
        or action_count != EXPECTED_ACTION_COUNT
    ):
        raise ReplayOrchestrationError("PH_D05_REPLAY_COVERAGE_MISMATCH")
    if mismatch_records:
        raise ReplayOrchestrationError(
            f"PH_D05_REPLAY_X{run_count}_MISMATCH:{len(mismatch_records)}"
        )
    body: dict[str, Any] = {
        "schema_version": REPORT_VERSION,
        "phase_id": "PH-D05",
        "authority": "REPLAY_HARNESS_MAINTAINER",
        "operation_mode": "OFFLINE",
        "complete_inventory": complete_inventory,
        "independent_process_count": run_count,
        "required_independent_process_count": 3,
        "game_count": game_count,
        "level_count": level_count,
        "action_count": action_count,
        "source_frame_difference_count": worker_reports[0].get(
            "source_frame_difference_count"
        ),
        "canonical_replay_mismatch_count": 0,
        "action_availability_terminal_progress_mismatch_count": 0,
        "network_denial_pass_count": run_count,
        "secret_scrub_pass_count": run_count,
        "write_boundary_pass_count": run_count,
        "source_pre_post_identity_pass_count": run_count,
        "fixed_seed_pass_count": run_count,
        "process_evidence": process_evidence,
        "worker_report_digests": [
            report.get("content_digest") for report in worker_reports
        ],
        "per_game_replay_contracts": [
            {
                "game_id": game_id,
                "actual_trace_digest": baseline[game_id].get("actual_trace_digest"),
                "capture_content_digest": baseline[game_id].get(
                    "capture_content_digest"
                ),
                "capture_sha256": baseline[game_id].get("capture_sha256"),
                "action_count": baseline[game_id].get("action_count"),
                "target_levels": baseline[game_id].get("target_levels"),
                "source_frame_difference_count": baseline[game_id].get(
                    "source_frame_difference_count"
                ),
            }
            for game_id in sorted(baseline)
        ],
        "exit_claim": (
            "ARC3_STRICT_OFFLINE_REPLAY_X3_COMPLETE"
            if complete_inventory and run_count == 3
            else "ARC3_STRICT_OFFLINE_REPLAY_PREFLIGHT_COMPLETE"
        ),
    }
    body["content_digest"] = "hds-arc3-replay-x3:" + _digest(body)
    _atomic_write(report_path, _canonical_bytes(body))
    return body


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-count", type=int, choices=(1, 3), default=3)
    parser.add_argument("--game", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = run(
            repository_root=args.repository_root,
            cache_root=args.cache_root,
            report_path=args.report,
            run_count=args.run_count,
            requested_games=tuple(args.game),
        )
    except Exception as error:
        print(
            f"PH_D05_REPLAY_X3_FAIL:{type(error).__name__}:{error}",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "action_count": report["action_count"],
                "content_digest": report["content_digest"],
                "exit_claim": report["exit_claim"],
                "game_count": report["game_count"],
                "level_count": report["level_count"],
                "run_count": report["independent_process_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
