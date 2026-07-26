"""Adapt a closed S0 Teacher corpus to the existing local-score oracle."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object
from .human_replay_corpus import load_full_solution_corpus
from .solution_graph_compiler import load_teacher_closure_report

TEACHER_SCORE_ADAPTER_SCHEMA_VERSION = "arc3-teacher-score-adapter-v1"
TEACHER_SCORE_ADAPTER_DIGEST_PREFIX = "arc3_teacher_score_adapter:"


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


def _level_action_counts(game: Mapping[str, Any]) -> list[int]:
    boundaries = _sequence(game.get("level_boundaries"), "level_boundaries")
    counts: list[int] = []
    prior = 0
    for raw_boundary in boundaries:
        if not isinstance(raw_boundary, Mapping):
            raise TypeError("TEACHER_SCORE_LEVEL_BOUNDARY_INVALID")
        cumulative = _integer(
            raw_boundary.get("action_count"),
            "action_count",
        )
        delta = cumulative - prior
        if delta <= 0:
            raise ValueError("TEACHER_SCORE_LEVEL_ACTION_COUNT_INVALID")
        counts.append(delta)
        prior = cumulative
    if prior != game.get("action_count"):
        raise ValueError("TEACHER_SCORE_GAME_ACTION_COUNT_MISMATCH")
    return counts


def build_teacher_score_adapter_report(
    *,
    corpus_path: Path,
    closure_report_path: Path,
) -> dict[str, Any]:
    """Create a deterministic P10-shaped input without changing oracle math."""

    corpus = load_full_solution_corpus(corpus_path)
    closure = load_teacher_closure_report(closure_report_path)
    if closure.get("source_corpus_digest") != corpus.get("content_digest"):
        raise ValueError("TEACHER_SCORE_CORPUS_CLOSURE_DIGEST_MISMATCH")
    raw_games = _sequence(corpus.get("games"), "games")
    reports: list[dict[str, Any]] = []
    scorecard_environments: list[dict[str, Any]] = []
    max_actions = 0
    for raw_game in raw_games:
        if not isinstance(raw_game, Mapping):
            raise TypeError("TEACHER_SCORE_GAME_INVALID")
        game_id = str(raw_game.get("game_id", ""))
        target_levels = _integer(
            raw_game.get("target_levels"),
            "target_levels",
        )
        action_count = _integer(
            raw_game.get("action_count"),
            "action_count",
        )
        level_actions = _level_action_counts(raw_game)
        if len(level_actions) != target_levels:
            raise ValueError(
                f"TEACHER_SCORE_LEVEL_COUNT_MISMATCH:{game_id}"
            )
        max_actions = max(max_actions, action_count)
        reports.append(
            {
                "game_id": game_id,
                "actions": action_count,
                "levels_completed": target_levels,
                "win_levels": target_levels,
                "terminal_state": "WIN",
                "max_action_exhausted": False,
                "instruction_body_versions": ["teacher-s0-v1"],
                "instruction_body_digests": [
                    str(corpus.get("content_digest"))
                ],
                "visual_operator_version": (
                    "teacher-s0-privileged-replay"
                ),
            }
        )
        scorecard_environments.append(
            {
                "id": game_id,
                "runs": [
                    {
                        "guid": raw_game.get("content_digest"),
                        "levels_completed": target_levels,
                        "level_actions": level_actions,
                    }
                ],
            }
        )
    reports.sort(key=lambda item: str(item["game_id"]))
    scorecard_environments.sort(key=lambda item: str(item["id"]))
    body: dict[str, Any] = {
        "schema_version": TEACHER_SCORE_ADAPTER_SCHEMA_VERSION,
        "phase": "P10",
        "operation_mode": "offline",
        "teacher_privilege_stage": "S0",
        "architecture_evidence_eligible": False,
        "source_corpus_digest": corpus.get("content_digest"),
        "source_closure_digest": closure.get("content_digest"),
        "environment_count": len(reports),
        "completed_count": len(reports),
        "completed_levels": sum(
            int(report["levels_completed"]) for report in reports
        ),
        "total_levels": int(corpus.get("level_count", 0)),
        "error_count": 0,
        "max_actions": max_actions,
        "instruction_variant": "teacher-s0-privileged",
        "reports": reports,
        "errors": [],
        "local_scorecard": {
            "card_id": "teacher-s0:" + digest_object(scorecard_environments),
            "environments": scorecard_environments,
        },
    }
    return {
        **body,
        "content_digest": (
            TEACHER_SCORE_ADAPTER_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Adapt a closed S0 Teacher run to the local oracle."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_teacher_score_adapter_report(
        corpus_path=args.corpus,
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
    "TEACHER_SCORE_ADAPTER_SCHEMA_VERSION",
    "build_teacher_score_adapter_report",
]
