"""Adapt closed S5 Runtime Student evidence to the local RHAE oracle."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .s5_runner import (
    S5_DEFAULT_DETERMINISTIC_SEED,
    load_s5_closure_report,
)
from .schema import digest_object

S5_SCORE_ADAPTER_SCHEMA_VERSION = "arc3-s5-score-adapter-v1"
S5_SCORE_ADAPTER_DIGEST_PREFIX = "arc3_s5_score_adapter:"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def build_s5_score_adapter_report(
    *,
    closure_report_path: Path,
) -> dict[str, Any]:
    closure = load_s5_closure_report(closure_report_path)
    if (
        closure.get("all_complete") is not True
        or closure.get("complete_inventory") is not True
        or closure.get("deterministic_seed")
        != S5_DEFAULT_DETERMINISTIC_SEED
        or closure.get("error_count") != 0
    ):
        raise ValueError("S5_SCORE_REQUIRES_COMPLETE_RUNTIME_CLOSURE")
    reports: list[dict[str, Any]] = []
    scorecard_environments: list[dict[str, Any]] = []
    max_actions = 0
    for raw_report in _sequence(closure.get("reports"), "reports"):
        if not isinstance(raw_report, Mapping):
            raise TypeError("S5_SCORE_ENVIRONMENT_REPORT_INVALID")
        game_id = str(raw_report.get("game_id", ""))
        completed_levels = _integer(
            raw_report.get("completed_levels"),
            "completed_levels",
        )
        action_count = _integer(
            raw_report.get("actions_executed"),
            "actions_executed",
        )
        level_actions = [
            _integer(item, "level_action_counts[]")
            for item in _sequence(
                raw_report.get("level_action_counts"),
                "level_action_counts",
            )
        ]
        if (
            raw_report.get("complete") is not True
            or raw_report.get("final_state") != "WIN"
            or completed_levels <= 0
            or len(level_actions) != completed_levels
            or any(item <= 0 for item in level_actions)
            or sum(level_actions) != action_count
        ):
            raise ValueError(
                f"S5_SCORE_ENVIRONMENT_CLOSURE_INVALID:{game_id}"
            )
        max_actions = max(max_actions, action_count)
        reports.append(
            {
                "game_id": game_id,
                "actions": action_count,
                "levels_completed": completed_levels,
                "win_levels": completed_levels,
                "terminal_state": "WIN",
                "max_action_exhausted": False,
                "instruction_body_versions": [
                    str(closure["instruction_body_version"])
                ],
                "instruction_body_digests": [
                    str(closure["instruction_body_digest"])
                ],
                "visual_operator_version": (
                    "s5-rendered-history-mlp-runtime"
                ),
            }
        )
        scorecard_environments.append(
            {
                "id": game_id,
                "runs": [
                    {
                        "guid": str(
                            raw_report["runtime_trace_digest"]
                        ),
                        "levels_completed": completed_levels,
                        "level_actions": level_actions,
                    }
                ],
            }
        )
    reports.sort(key=lambda item: str(item["game_id"]))
    scorecard_environments.sort(key=lambda item: str(item["id"]))
    body: dict[str, Any] = {
        "schema_version": S5_SCORE_ADAPTER_SCHEMA_VERSION,
        "phase": "P10",
        "operation_mode": "offline",
        "privilege_stage": "S5",
        "runtime_student": True,
        "architecture_evidence_eligible": True,
        "generalization_evidence_eligible": False,
        "source_closure_digest": closure.get("content_digest"),
        "environment_count": len(reports),
        "completed_count": len(reports),
        "completed_levels": sum(
            int(report["levels_completed"]) for report in reports
        ),
        "total_levels": _integer(
            closure.get("completed_levels"),
            "completed_levels",
        ),
        "error_count": 0,
        "max_actions": max_actions,
        "instruction_variant": "s5-rendered-history-mlp-runtime",
        "reports": reports,
        "errors": [],
        "local_scorecard": {
            "card_id": "s5-runtime:"
            + digest_object(scorecard_environments),
            "environments": scorecard_environments,
        },
    }
    return {
        **body,
        "content_digest": (
            S5_SCORE_ADAPTER_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adapt closed S5 Runtime Student to local oracle."
    )
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_s5_score_adapter_report(
        closure_report_path=args.closure_report,
    )
    _write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "environment_count": report["environment_count"],
                "completed_levels": report["completed_levels"],
                "max_actions": report["max_actions"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S5_SCORE_ADAPTER_SCHEMA_VERSION",
    "build_s5_score_adapter_report",
]
