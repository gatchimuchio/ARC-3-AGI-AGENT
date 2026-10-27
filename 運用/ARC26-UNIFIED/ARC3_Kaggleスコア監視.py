#!/usr/bin/env python3
"""Read-only ARC3 Kaggle score monitor for Windows Task Scheduler."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
COMPETITION = "arc-prize-2026-arc-agi-3"
SCORE_LEDGER = ROOT / "運用/ARC26-UNIFIED/score-ledger.jsonl"
WORK_LEDGER = ROOT / "運用/ARC26-UNIFIED/work-ledger.jsonl"
EVIDENCE_DIR = ROOT / "運用/証拠/ARC26-UNIFIED"
RUNBOOK = ROOT / "検証/運転記録/ARC3-RUN-003_C1-018_modelv5公式Rerun_20261024.md"
TASK_LOG = ROOT / "運用/ARC26-UNIFIED/score-monitor-task.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
    return result


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _numeric_score(value: object) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        score = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return score if score.is_finite() else None


def _score_delta(current: object, previous: object) -> float | None:
    current_score = _numeric_score(current)
    previous_score = _numeric_score(previous)
    if current_score is None or previous_score is None:
        return None
    return float(current_score - previous_score)


def _pending_interval_minutes(pending_observations: int) -> int:
    intervals = (5, 15, 30, 60)
    index = max(0, min(pending_observations - 1, len(intervals) - 1))
    return intervals[index]


def _next_interval_minutes(status: str, score: object, pending_observations: int) -> int:
    normalized = status.rsplit(".", 1)[-1].upper()
    if normalized in {"PENDING", "SUBMITTED", "RUNNING"}:
        return _pending_interval_minutes(pending_observations)
    if normalized == "COMPLETE":
        return 24 * 60 if _numeric_score(score) is not None else 15
    if normalized in {"FAILED", "ERROR", "INVALID"}:
        return 15
    return 15


def _cli_prefix() -> list[str]:
    """Prefer this repo's pinned CLI environment, then fall back to uv tooling."""
    manifest_path = ROOT / "運用" / "ARC26-UNIFIED" / "kaggle-cli-environment.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = None
    if (
        isinstance(manifest, dict)
        and manifest.get("track") == "ARC3"
        and manifest.get("kaggle_cli") == "Kaggle CLI 2.2.5"
    ):
        venv_path = manifest.get("venv_path")
        if isinstance(venv_path, str) and venv_path:
            project_cli = Path(venv_path) / "Scripts" / "kaggle.exe"
            if project_cli.is_file():
                return [str(project_cli)]

    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "--from", "kaggle==2.2.5", "kaggle"]
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "run", "--from", "kaggle==2.2.5", "kaggle"]
    user_scripts = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Python"
        / f"Python{sys.version_info.major}{sys.version_info.minor}"
        / "Scripts"
    )
    for name, prefix in (
        ("uvx.exe", ["--from", "kaggle==2.2.5", "kaggle"]),
        ("uv.exe", ["tool", "run", "--from", "kaggle==2.2.5", "kaggle"]),
    ):
        candidate = user_scripts / name
        if candidate.is_file():
            return [str(candidate), *prefix]
    # Scheduled tasks may run with a reduced PATH and a different home
    # directory. In that case, use the already pinned project environment.
    try:
        import kaggle
    except Exception:
        kaggle_version = None
    else:
        kaggle_version = getattr(kaggle, "__version__", None)
    if kaggle_version == "2.2.5":
        interpreter = Path(sys.executable)
        if interpreter.name.lower() == "pythonw.exe":
            interpreter = interpreter.with_name("python.exe")
        if interpreter.is_file():
            return [str(interpreter), "-m", "kaggle"]
    raise FileNotFoundError(
        "a manifest-pinned project Kaggle CLI or uvx/uv is required (Kaggle CLI 2.2.5)"
    )


def _run_cli(arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [*_cli_prefix(), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"kaggle CLI exit {completed.returncode}")
    return completed


def _parse_kaggle_json_output(stdout: str) -> Any:
    """Parse Kaggle CLI JSON while ignoring its known version notice on stdout."""
    lines = stdout.lstrip("\ufeff").splitlines()
    warning_prefix = "Warning: Looks like you're using an outdated `kaggle` version "
    while lines and (not lines[0].strip() or lines[0].startswith(warning_prefix)):
        lines.pop(0)
    return json.loads("\n".join(lines))


def _fetch_history() -> list[dict[str, Any]]:
    result = _run_cli(["competitions", "submissions", COMPETITION, "--format", "json"])
    parsed = _parse_kaggle_json_output(result.stdout)
    if not isinstance(parsed, list):
        raise ValueError("Kaggle history response is not a list")
    rows = [row for row in parsed if isinstance(row, dict) and _parse_datetime(row.get("date"))]
    if not rows:
        raise LookupError("Kaggle history has no parseable submissions")
    return sorted(
        rows,
        key=lambda row: _parse_datetime(row.get("date")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def _fetch_limits() -> tuple[dict[str, int | None], str | None]:
    try:
        result = _run_cli(["competitions", "submission-limits", COMPETITION])
    except Exception as error:
        return {"numToday": None, "numTotal": None, "remainingToday": None}, type(error).__name__
    fields: dict[str, int | None] = {}
    for output_name, label in (
        ("numToday", "Submissions today"),
        ("numTotal", "Lifetime submissions"),
        ("remainingToday", "Remaining today"),
    ):
        match = re.search(rf"^{re.escape(label)}:\s*(\d+)\s*$", result.stdout, re.MULTILINE | re.IGNORECASE)
        fields[output_name] = int(match.group(1)) if match else None
    return fields, None if all(value is not None for value in fields.values()) else "limits_parse_incomplete"


def _status_text(row: dict[str, Any]) -> str:
    value = row.get("status")
    return str(value).strip() if value is not None else "UNKNOWN"


def _write_evidence(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _runbook_append(
    observed_at: str,
    submission_id: str,
    status: str,
    score: object,
    limits: dict[str, int | None],
    evidence_rel: str,
    next_due: str,
) -> None:
    if not RUNBOOK.is_file():
        return
    score_text = "unobserved" if _numeric_score(score) is None else str(score)
    with RUNBOOK.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n## {observed_at} scheduled read-only Kaggle observation\n\n")
        stream.write(f"- Submission {submission_id}: {status}, public score {score_text}.\n")
        stream.write(
            f"- Limits: today={limits.get('numToday')}, lifetime={limits.get('numTotal')}, "
            f"remaining={limits.get('remainingToday')}. No submit, rerun, push, or Notebook edit was performed.\n"
        )
        stream.write(f"- Evidence: {evidence_rel}. Next scheduled query: {next_due} UTC.\n")


def _due_record(now: datetime, due: datetime | None, force: bool) -> dict[str, Any] | None:
    if not force and due is not None and now < due:
        return {
            "state": "not_due",
            "checked_at_utc": _utc_text(now),
            "next_due_utc": _utc_text(due),
        }
    return None


def tick(*, force: bool = False) -> dict[str, Any]:
    prior_rows = _read_jsonl(SCORE_LEDGER)
    if not prior_rows:
        raise LookupError(f"score ledger is empty: {SCORE_LEDGER}")
    previous = prior_rows[-1]
    now = _now()
    not_due = _due_record(now, _parse_datetime(previous.get("next_due_utc")), force)
    if not_due:
        _append_jsonl(TASK_LOG, not_due)
        return not_due

    try:
        history = _fetch_history()
    except Exception as error:
        retry_at = now + timedelta(minutes=15)
        failure = {
            "event": "scheduled Kaggle history observation failed",
            "track": "ARC3",
            "observed_at_utc": _utc_text(now),
            "error_type": type(error).__name__,
            "error": str(error)[:500],
            "next_due_utc": _utc_text(retry_at),
            "submission_created": False,
        }
        _append_jsonl(WORK_LEDGER, failure)
        _append_jsonl(TASK_LOG, {"state": "observation_error", **failure})
        return {"state": "observation_error", "error_type": type(error).__name__, "next_due_utc": _utc_text(retry_at)}

    latest = history[0]
    submission_id = str(latest.get("ref"))
    status = _status_text(latest)
    public_score = latest.get("publicScore")
    numeric_score = _numeric_score(public_score)
    same_submission = previous.get("submission_id") == submission_id
    pending_count = sum(
        1
        for row in prior_rows
        if row.get("submission_id") == submission_id
        and str(row.get("official_status", "")).rsplit(".", 1)[-1].upper()
        in {"PENDING", "SUBMITTED", "RUNNING"}
    )
    pending_count = pending_count + 1 if status.rsplit(".", 1)[-1].upper() in {"PENDING", "SUBMITTED", "RUNNING"} else 0
    interval = _next_interval_minutes(status, public_score, pending_count)
    next_due = _utc_text(now + timedelta(minutes=interval))
    previous_numeric_row = next(
        (
            row
            for row in history[1:]
            if str(row.get("status", "")).rsplit(".", 1)[-1].upper() == "COMPLETE"
            and _numeric_score(row.get("publicScore")) is not None
        ),
        None,
    )
    previous_score = previous_numeric_row.get("publicScore") if previous_numeric_row else None
    score_delta = _score_delta(public_score, previous_score)
    observed_at = _utc_text(now)
    limits, limits_error = _fetch_limits()
    submitted_at = _parse_datetime(latest.get("date")) or now

    evidence = {
        "schema": "arc26-unified-kaggle-cli-observation-v1",
        "track": "ARC3",
        "competition_slug": COMPETITION,
        "submission_id": submission_id,
        "observed_at_utc": observed_at,
        "retrieval_method": "Pinned Kaggle CLI 2.2.5 via the per-repo environment manifest, with uvx/uv fallback; read-only",
        "commands": [
            "kaggle competitions submissions arc-prize-2026-arc-agi-3 --format json",
            "kaggle competitions submission-limits arc-prize-2026-arc-agi-3",
        ],
        "monitor_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "history": {
            "notebook_slug": previous.get("notebook_slug") if same_submission else None,
            "notebook_version": previous.get("notebook_version") if same_submission else None,
            "official_status": status,
            "publicScore": public_score,
            "privateScore": latest.get("privateScore"),
            "submitted_at_utc": _utc_text(submitted_at),
            "error_description_present": bool(latest.get("errorDescription")),
        },
        "previous_numeric_submission": {
            "submission_id": previous_numeric_row.get("ref") if previous_numeric_row else None,
            "publicScore": previous_score,
        },
        "submission_limits": limits,
        "submission_limits_error": limits_error,
        "official_score_is_unobserved_not_zero": numeric_score is None,
        "next_check_at_utc": next_due,
        "submission_or_rerun_performed": False,
    }
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    evidence_path = EVIDENCE_DIR / f"official-cli-observation-{stamp}.json"
    _write_evidence(evidence_path, evidence)
    evidence_rel = evidence_path.relative_to(ROOT).as_posix()
    prior_same = previous if same_submission else {}
    score_row: dict[str, Any] = {
        "track": "ARC3",
        "competition_slug": COMPETITION,
        "submission_id": submission_id,
        "submitted_at_utc": _utc_text(submitted_at),
        "observed_at_utc": observed_at,
        "official_status": status,
        "official_score": float(numeric_score) if numeric_score is not None else None,
        "score_unit": "public_score" if numeric_score is not None else None,
        "notebook_slug": evidence["history"]["notebook_slug"],
        "notebook_version": evidence["history"]["notebook_version"],
        "source_commit": prior_same.get("source_commit"),
        "input_sha256": prior_same.get("input_sha256"),
        "output_sha256": prior_same.get("output_sha256"),
        "local_score_and_dataset": prior_same.get("local_score_and_dataset"),
        "arc2_solved_hold_fallback": None,
        "arc3_actions_levels_games": prior_same.get("arc3_actions_levels_games"),
        "previous_score": float(_numeric_score(previous_score)) if _numeric_score(previous_score) is not None else None,
        "score_delta": score_delta,
        "experiment_id": f"scheduled official follow-up {submission_id}",
        "change_sha": prior_same.get("change_sha"),
        "failure_signature": status if status.rsplit(".", 1)[-1].upper() in {"FAILED", "ERROR", "INVALID"} else None,
        "next_due_utc": next_due,
        "evidence_files": [evidence_rel, RUNBOOK.relative_to(ROOT).as_posix()],
        "official_score_is_unobserved_not_zero": numeric_score is None,
        "quota": limits,
        "submission_or_rerun_performed": False,
    }
    if numeric_score is None:
        score_row["why_unobserved"] = {
            "official_score": f"Kaggle returned {status} with publicScore={public_score!r}.",
            "score_delta": "No numeric public score is available for this submission.",
        }
    _append_jsonl(SCORE_LEDGER, score_row)
    _append_jsonl(
        WORK_LEDGER,
        {
            "event": "scheduled read-only Kaggle score observation",
            "track": "ARC3",
            "experiment_id": score_row["experiment_id"],
            "observed_at_utc": observed_at,
            "submission_id": submission_id,
            "official_status": status,
            "official_score": score_row["official_score"],
            "previous_score": score_row["previous_score"],
            "score_delta": score_delta,
            "quota": limits,
            "next_due_utc": next_due,
            "evidence_files": [evidence_rel],
            "submission_or_rerun_performed": False,
        },
    )
    _runbook_append(observed_at, submission_id, status, public_score, limits, evidence_rel, next_due)
    result = {
        "state": "observed",
        "submission_id": submission_id,
        "official_status": status,
        "official_score": score_row["official_score"],
        "observed_at_utc": observed_at,
        "next_due_utc": next_due,
        "evidence": evidence_rel,
    }
    _append_jsonl(TASK_LOG, result)
    return result


def _self_test() -> dict[str, Any]:
    assert _parse_datetime("2026-10-24T01:00:00") == datetime(2026, 10, 24, 1, tzinfo=timezone.utc)
    assert [_pending_interval_minutes(n) for n in (1, 2, 3, 4, 5)] == [5, 15, 30, 60, 60]
    assert _next_interval_minutes("SubmissionStatus.COMPLETE", "0.00", 0) == 1440
    assert _next_interval_minutes("SubmissionStatus.COMPLETE", "", 0) == 15
    assert _score_delta("0.25", "0.00") == 0.25
    assert _score_delta("", "0.25") is None
    assert Path(_cli_executable()).is_file()
    return {"state": "PASS", "network": "not used", "submission_or_rerun": "not used"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tick", action="store_true", help="query only when next_due_utc has arrived")
    parser.add_argument("--force", action="store_true", help="perform one immediate read-only observation")
    parser.add_argument("--self-test", action="store_true", help="check scheduling and score handling offline")
    args = parser.parse_args(argv)
    if args.self_test:
        print(json.dumps(_self_test(), ensure_ascii=False))
        return 0
    if not args.tick and not args.force:
        parser.error("--tick or --force is required")
    result = tick(force=args.force)
    if sys.stdout is not None:
        print(json.dumps(result, ensure_ascii=False))
    return 1 if result["state"] == "observation_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
