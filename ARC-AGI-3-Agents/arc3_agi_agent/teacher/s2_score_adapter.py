"""Adapt the closed S2 Teacher graph run to the local RHAE oracle."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object
from .s2_graph_executor import load_s2_closure_report

S2_SCORE_ADAPTER_SCHEMA_VERSION = "arc3-teacher-s2-score-adapter-v1"
S2_SCORE_ADAPTER_DIGEST_PREFIX = "arc3_teacher_s2_score_adapter:"


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


def build_s2_score_adapter_report(
    *,
    closure_report_path: Path,
) -> dict[str, Any]:
    """Create a complete P10-shaped score input from executed S2 evidence."""

    closure = load_s2_closure_report(closure_report_path)
    raw_reports = _sequence(closure.get("reports"), "reports")
    reports: list[dict[str, Any]] = []
    scorecard_environments: list[dict[str, Any]] = []
    max_actions = 0
    for raw_report in raw_reports:
        if not isinstance(raw_report, Mapping):
            raise TypeError("S2_SCORE_GAME_REPORT_INVALID")
        game_id = str(raw_report.get("game_id", ""))
        target_levels = _integer(
            raw_report.get("target_levels"),
            "target_levels",
        )
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
            or completed_levels != target_levels
            or len(level_actions) != target_levels
            or any(item <= 0 for item in level_actions)
            or sum(level_actions) != action_count
            or raw_report.get("selector_resolution_failure_count") != 0
        ):
            raise ValueError(
                f"S2_SCORE_GAME_CLOSURE_INVALID:{game_id}"
            )
        max_actions = max(max_actions, action_count)
        source_game_graph_digest = str(
            raw_report.get("source_game_graph_digest", "")
        )
        reports.append(
            {
                "game_id": game_id,
                "actions": action_count,
                "levels_completed": completed_levels,
                "win_levels": target_levels,
                "terminal_state": "WIN",
                "max_action_exhausted": False,
                "instruction_body_versions": [
                    "teacher-s2-role-relative-graph-v1"
                ],
                "instruction_body_digests": [
                    source_game_graph_digest
                ],
                "visual_operator_version": (
                    "teacher-s2-render-role-resolution"
                ),
            }
        )
        scorecard_environments.append(
            {
                "id": game_id,
                "runs": [
                    {
                        "guid": source_game_graph_digest,
                        "levels_completed": completed_levels,
                        "level_actions": level_actions,
                    }
                ],
            }
        )
    reports.sort(key=lambda item: str(item["game_id"]))
    scorecard_environments.sort(key=lambda item: str(item["id"]))
    body: dict[str, Any] = {
        "schema_version": S2_SCORE_ADAPTER_SCHEMA_VERSION,
        "phase": "P10",
        "operation_mode": "offline",
        "teacher_privilege_stage": "S2",
        "architecture_evidence_eligible": False,
        "source_policy_graph_digest": closure.get(
            "source_policy_graph_digest"
        ),
        "source_closure_digest": closure.get("content_digest"),
        "environment_count": len(reports),
        "completed_count": len(reports),
        "completed_levels": sum(
            int(report["levels_completed"]) for report in reports
        ),
        "total_levels": _integer(
            closure.get("level_count"),
            "level_count",
        ),
        "error_count": 0,
        "max_actions": max_actions,
        "instruction_variant": "teacher-s2-role-relative",
        "reports": reports,
        "errors": [],
        "local_scorecard": {
            "card_id": "teacher-s2:"
            + digest_object(scorecard_environments),
            "environments": scorecard_environments,
        },
    }
    return {
        **body,
        "content_digest": (
            S2_SCORE_ADAPTER_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adapt a closed S2 Teacher graph run to the local oracle."
    )
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_s2_score_adapter_report(
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
    "S2_SCORE_ADAPTER_SCHEMA_VERSION",
    "build_s2_score_adapter_report",
]
