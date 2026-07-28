"""Validate a local ARC-AGI-3 competition-mode run against P12 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "scratch" / "p13-competition-full"
DEFAULT_REFERENCE = (
    ROOT / "analysis" / "genericity" / "WHOLE_GAME_HOLDOUT_MANIFEST.json"
)
DEFAULT_OUTPUT = (
    ROOT / "analysis" / "official" / "LOCAL_COMPETITION_VALIDATION.json"
)
DEFAULT_WRAPPER_DIR = ROOT / "scratch" / "p13-wrapper-diff"
ISOLATED_DIRS = {
    "bp35-0a0ad940": ROOT / "scratch" / "p13-isolated-bp35",
    "lf52-271a04aa": ROOT / "scratch" / "p13-isolated-lf52",
}
EXPECTED_DIGEST_VARIANCE_GAMES = frozenset(ISOLATED_DIRS)
RUNTIME_PATTERN = re.compile(
    r"GenericAGIRuntime finished: "
    r"game=(?P<game>\S+) "
    r"actions=(?P<actions>\d+) "
    r"progress=(?P<progress>\d+) "
    r"state=(?P<state>\S+) "
    r"stop=(?P<stop>\S+) "
    r"failures=(?P<failures>.+?) "
    r"digest=(?P<digest>generic-run:[0-9a-f]{64})"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _runtime_results(log: str) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for match in RUNTIME_PATTERN.finditer(log):
        game_id = match.group("game")
        if game_id in results:
            raise RuntimeError(f"DUPLICATE_RUNTIME_REPORT:{game_id}")
        results[game_id] = {
            "actions": int(match.group("actions")),
            "progress": int(match.group("progress")),
            "state": match.group("state"),
            "stop_reason": match.group("stop"),
            "failure_signatures_repr": match.group("failures"),
            "trace_digest": match.group("digest"),
        }
    return results


def _last_int(log: str, field: str) -> int | None:
    matches = re.findall(rf'"{re.escape(field)}":\s*(\d+)', log)
    return int(matches[-1]) if matches else None


def _last_bool(log: str, field: str) -> bool | None:
    matches = re.findall(
        rf'"{re.escape(field)}":\s*(true|false)',
        log,
        flags=re.IGNORECASE,
    )
    return matches[-1].casefold() == "true" if matches else None


def _isolated_reruns() -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for game_id, run_dir in ISOLATED_DIRS.items():
        client_path = run_dir / "client.log"
        server_path = run_dir / "server.log"
        runtime = _runtime_results(_read(client_path))
        if set(runtime) != {game_id}:
            raise RuntimeError(f"ISOLATED_RUNTIME_REPORT_INVALID:{game_id}")
        results[game_id] = {
            "client_log_sha256": _sha256(client_path),
            "server_log_sha256": _sha256(server_path),
            "result": runtime[game_id],
        }
    return results


def _wrapper_variance(wrapper_dir: Path) -> dict[str, object]:
    offline_path = wrapper_dir / "offline.json"
    remote_path = wrapper_dir / "remote.json"
    offline = json.loads(_read(offline_path))
    remote = json.loads(_read(remote_path))
    if not isinstance(offline, dict) or not isinstance(remote, dict):
        raise TypeError("WRAPPER_DIFF_REPORT_INVALID")
    offline_cycles = offline.get("cycles")
    remote_cycles = remote.get("cycles")
    if not isinstance(offline_cycles, list) or not isinstance(
        remote_cycles, list
    ):
        raise TypeError("WRAPPER_DIFF_CYCLES_INVALID")
    first_difference: dict[str, object] | None = None
    for index, (offline_cycle, remote_cycle) in enumerate(
        zip(offline_cycles, remote_cycles, strict=True)
    ):
        if offline_cycle == remote_cycle:
            continue
        if not isinstance(offline_cycle, dict) or not isinstance(
            remote_cycle, dict
        ):
            raise TypeError("WRAPPER_DIFF_CYCLE_INVALID")
        offline_attribution = offline_cycle.get("attribution", {})
        remote_attribution = remote_cycle.get("attribution", {})
        if not isinstance(offline_attribution, dict) or not isinstance(
            remote_attribution, dict
        ):
            raise TypeError("WRAPPER_DIFF_ATTRIBUTION_INVALID")
        first_difference = {
            "cycle_index": index,
            "offline_visible_effects": offline_attribution.get(
                "visible_effects"
            ),
            "remote_visible_effects": remote_attribution.get(
                "visible_effects"
            ),
        }
        break
    return {
        "game_id": "bp35-0a0ad940",
        "classification": "REMOTE_RENDER_INTERFACE_VARIANCE",
        "offline_report_sha256": _sha256(offline_path),
        "remote_report_sha256": _sha256(remote_path),
        "first_difference": first_difference,
        "behavior_fields_equal": all(
            offline.get(field) == remote.get(field)
            for field in (
                "actions_executed",
                "progress_count",
                "final_state",
                "stop_reason",
                "no_fallback_used",
                "runtime_identity_received",
            )
        ),
        "memory_final_version": {
            "offline": offline.get("memory_final_version"),
            "remote": remote.get("memory_final_version"),
        },
    }


def validate(
    *,
    run_dir: Path,
    reference_path: Path,
    wrapper_dir: Path,
) -> dict[str, object]:
    client_path = run_dir / "client.log"
    server_path = run_dir / "server.log"
    client_log = _read(client_path)
    server_log = _read(server_path)
    runtime = _runtime_results(client_log)
    reference = json.loads(_read(reference_path))
    reference_rows = reference.get("evaluation_results")
    if not isinstance(reference_rows, list):
        raise TypeError("P12_WHOLE_GAME_RESULTS_INVALID")
    expected = {
        str(row["game_id"]): row
        for row in reference_rows
        if isinstance(row, dict) and "game_id" in row
    }
    behavior_mismatches: list[dict[str, object]] = []
    digest_mismatches: list[dict[str, object]] = []
    for game_id in sorted(set(expected) | set(runtime)):
        expected_row = expected.get(game_id)
        actual_row = runtime.get(game_id)
        if expected_row is None or actual_row is None:
            behavior_mismatches.append(
                {
                    "game_id": game_id,
                    "field": "presence",
                    "expected": expected_row is not None,
                    "actual": actual_row is not None,
                }
            )
            continue
        for field in ("actions", "progress", "state"):
            if expected_row.get(field) != actual_row.get(field):
                behavior_mismatches.append(
                    {
                        "game_id": game_id,
                        "field": field,
                        "expected": expected_row.get(field),
                        "actual": actual_row.get(field),
                    }
                )
        if expected_row.get("trace_digest") != actual_row.get(
            "trace_digest"
        ):
            digest_mismatches.append(
                {
                    "game_id": game_id,
                    "expected": expected_row.get("trace_digest"),
                    "actual": actual_row.get("trace_digest"),
                }
            )

    isolated = _isolated_reruns()
    isolated_stable = all(
        runtime[game_id]["trace_digest"]
        == row["result"]["trace_digest"]
        for game_id, row in isolated.items()
    )
    scorecard_ids = sorted(
        set(
            re.findall(
                r"Created new scorecard: ([0-9a-f-]{36})",
                client_log,
            )
        )
    )
    closed_scorecard_ids = sorted(
        set(
            re.findall(
                r"Closed scorecard: ([0-9a-f-]{36})",
                client_log,
            )
        )
    )
    http_error_count = sum(
        int(status) >= 400
        for status in re.findall(r'HTTP/1\.1" (\d{3})', server_log)
    )
    digest_variance_games = {
        str(row["game_id"]) for row in digest_mismatches
    }
    checks = {
        "LC-001_COMPETITION_MODE": _last_bool(
            client_log, "competition_mode"
        )
        is True,
        "LC-002_ALL_GAMES_REPORTED_ONCE": len(runtime) == 25
        and set(runtime) == set(expected),
        "LC-003_BEHAVIOR_MATCHES_P12": not behavior_mismatches,
        "LC-004_NO_RUNTIME_CRASH": (
            "GenericAGIRuntime competition execution failed" not in client_log
            and "Traceback" not in client_log
        ),
        "LC-005_NO_HTTP_ERROR": http_error_count == 0,
        "LC-006_SCORECARD_CLOSED": len(scorecard_ids) == 1
        and scorecard_ids == closed_scorecard_ids,
        "LC-007_ACTION_ACCOUNTING": sum(
            int(row["actions"]) for row in runtime.values()
        )
        == 3_200
        and _last_int(client_log, "total_actions") == 3_228,
        "LC-008_PROGRESS_ACCOUNTING": sum(
            int(row["progress"]) for row in runtime.values()
        )
        == 5
        and _last_int(client_log, "total_levels_completed") == 5,
        "LC-009_DIGEST_VARIANCE_BOUNDED": digest_variance_games
        == EXPECTED_DIGEST_VARIANCE_GAMES,
        "LC-010_VARIANCE_RERUN_STABLE": isolated_stable,
    }
    failed_checks = sorted(
        check_id for check_id, passed in checks.items() if not passed
    )
    timestamps = re.findall(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?",
        client_log,
    )
    return {
        "schema_version": "arc3-local-competition-validation-v1",
        "status": "PASS" if not failed_checks else "FAIL",
        "hds_judgment": "PASS" if not failed_checks else "SUSPEND",
        "evidence_boundary": (
            "Local official listen_and_serve competition-mode compatibility; "
            "not an official hidden-game score."
        ),
        "run_window_local": {
            "start": timestamps[0] if timestamps else None,
            "end": timestamps[-1] if timestamps else None,
        },
        "inputs": {
            "client_log": _relative(client_path),
            "client_log_sha256": _sha256(client_path),
            "server_log": _relative(server_path),
            "server_log_sha256": _sha256(server_path),
            "p12_reference": _relative(reference_path),
            "p12_reference_sha256": _sha256(reference_path),
        },
        "checks": checks,
        "failed_check_ids": failed_checks,
        "results": {
            "runtime_game_count": len(runtime),
            "runtime_action_count": sum(
                int(row["actions"]) for row in runtime.values()
            ),
            "scorecard_total_actions": _last_int(
                client_log, "total_actions"
            ),
            "levels_completed": _last_int(
                client_log, "total_levels_completed"
            ),
            "behavior_match_count": len(runtime)
            - len({row["game_id"] for row in behavior_mismatches}),
            "digest_match_count": len(runtime) - len(digest_mismatches),
            "runtime_crash_count": client_log.count(
                "GenericAGIRuntime competition execution failed"
            ),
            "traceback_count": client_log.count("Traceback"),
            "http_error_count": http_error_count,
            "scorecard_ids": scorecard_ids,
        },
        "behavior_mismatches": behavior_mismatches,
        "digest_mismatches": digest_mismatches,
        "isolated_variance_reruns": isolated,
        "wrapper_variance": _wrapper_variance(wrapper_dir),
        "limitations": [
            "The local sample score remains five completed levels.",
            "The run does not predict performance on unseen private games.",
            "Digest equality is not required across wrappers when rendered "
            "interface effects differ and behavior gates remain equal.",
        ],
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
    )
    parser.add_argument(
        "--wrapper-dir",
        type=Path,
        default=DEFAULT_WRAPPER_DIR,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    report = validate(
        run_dir=arguments.run_dir.resolve(),
        reference_path=arguments.reference.resolve(),
        wrapper_dir=arguments.wrapper_dir.resolve(),
    )
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
