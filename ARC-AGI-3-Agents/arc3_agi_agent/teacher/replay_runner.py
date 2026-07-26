"""Execute the S0 Teacher corpus against retained OFFLINE samples.

This is a privileged development harness, not an ARC Runtime Student.  It may
consume task identity, fixed replay order, and literal click coordinates only
from ``FULL_SOLUTION_CORPUS.json``.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw, GameAction

from ..protocol import AuthorityViolation
from ..schema import digest_object
from .human_replay_corpus import load_full_solution_corpus

TEACHER_CLOSURE_REPORT_SCHEMA_VERSION = (
    "arc3-teacher-s0-closure-report-v1"
)
TEACHER_CLOSURE_REPORT_DIGEST_PREFIX = "arc3_teacher_s0_closure:"


class TeacherReplayDivergence(RuntimeError):
    """Raised when a retained replay no longer matches the local sample."""


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


def _frame_state(frame: FrameDataRaw) -> str:
    raw = getattr(frame.state, "value", frame.state)
    return str(raw).upper()


def _frame_levels(frame: FrameDataRaw) -> int:
    value = frame.levels_completed
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("OFFLINE_TEACHER_FRAME_LEVELS_INVALID")
    return value


def _available_action_ids(frame: FrameDataRaw) -> list[int]:
    output: list[int] = []
    for raw in frame.available_actions:
        value = getattr(raw, "value", raw)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("OFFLINE_TEACHER_AVAILABLE_ACTION_INVALID")
        output.append(value)
    return output


def _frame_digest(frame: FrameDataRaw) -> str:
    normalized = [
        value.tolist() if hasattr(value, "tolist") else value
        for value in frame.frame
    ]
    return "sha256:" + digest_object(normalized)


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _action_payload(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise TypeError("TEACHER_REPLAY_ACTION_DATA_INVALID")
    output: dict[str, int] = {}
    for key in ("x", "y"):
        raw = value.get(key)
        if raw is not None:
            output[key] = _integer(raw, f"action_data.{key}")
    return output


def _restore_environment_variable(name: str, prior: str | None) -> None:
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior


def replay_game_solution(
    *,
    environment: LocalEnvironmentWrapper,
    game_solution: Mapping[str, Any],
    strict_frame_digest: bool = False,
) -> dict[str, Any]:
    """Replay one selected trajectory and require full local completion."""

    if not isinstance(environment, LocalEnvironmentWrapper):
        raise AuthorityViolation("S0_TEACHER_LOCAL_WRAPPER_REQUIRED")
    game_id = str(game_solution.get("game_id", ""))
    target_levels = _integer(
        game_solution.get("target_levels"),
        "target_levels",
    )
    raw_actions = game_solution.get("actions")
    if not isinstance(raw_actions, Sequence) or isinstance(
        raw_actions,
        (str, bytes, bytearray),
    ):
        raise TypeError("TEACHER_REPLAY_ACTIONS_INVALID")
    initial = environment.observation_space
    if not isinstance(initial, FrameDataRaw):
        raise RuntimeError("S0_TEACHER_INITIAL_FRAME_MISSING")
    expected_initial = game_solution.get("initial_observation")
    if not isinstance(expected_initial, Mapping):
        raise TypeError("TEACHER_REPLAY_INITIAL_OBSERVATION_INVALID")
    if _frame_levels(initial) != int(
        expected_initial.get("levels_completed", -1)
    ):
        raise TeacherReplayDivergence(
            f"S0_TEACHER_INITIAL_LEVEL_DIVERGED:{game_id}"
        )
    if _frame_state(initial) != str(
        expected_initial.get("state", "")
    ).upper():
        raise TeacherReplayDivergence(
            f"S0_TEACHER_INITIAL_STATE_DIVERGED:{game_id}"
        )

    frame_digest_mismatches = 0
    available_action_mismatches = 0
    level_reset_compatibility_count = 0
    actual_trace: list[dict[str, Any]] = []
    previous = initial
    for raw_step in raw_actions:
        if not isinstance(raw_step, Mapping):
            raise TypeError("TEACHER_REPLAY_STEP_INVALID")
        step = _integer(raw_step.get("step"), "step")
        action_id = _integer(raw_step.get("action_id"), "action_id")
        if not 0 <= action_id <= 7:
            raise ValueError("TEACHER_REPLAY_ACTION_ID_INVALID")
        available_before = _available_action_ids(previous)
        if action_id != 0 and action_id not in available_before:
            raise TeacherReplayDivergence(
                "S0_TEACHER_ACTION_UNAVAILABLE:"
                f"{game_id}:step={step}:action={action_id}"
            )
        payload = _action_payload(raw_step.get("action_data"))
        recorded_full_reset = raw_step.get("full_reset") is True
        use_level_reset_compatibility = (
            action_id == 0 and not recorded_full_reset
        )
        prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
        if use_level_reset_compatibility:
            os.environ["ONLY_RESET_LEVELS"] = "true"
            level_reset_compatibility_count += 1
        try:
            frame = environment.step(
                GameAction.from_id(action_id),
                data=payload,
                reasoning={
                    "authority": "S0_PRIVILEGED_TEACHER",
                    "runtime_use": "FORBIDDEN",
                    "game_id": game_id,
                    "source_step": step,
                    "reset_scope": (
                        "LEVEL_COMPATIBILITY"
                        if use_level_reset_compatibility
                        else "RECORDED_ACTION"
                    ),
                },
            )
        finally:
            if use_level_reset_compatibility:
                _restore_environment_variable(
                    "ONLY_RESET_LEVELS",
                    prior_reset_scope,
                )
        if not isinstance(frame, FrameDataRaw):
            raise RuntimeError(
                f"S0_TEACHER_STEP_FAILED:{game_id}:step={step}"
            )
        actual_state = _frame_state(frame)
        actual_levels = _frame_levels(frame)
        expected_state = str(
            raw_step.get("expected_state", "")
        ).upper()
        expected_levels = _integer(
            raw_step.get("expected_levels_completed"),
            "expected_levels_completed",
        )
        if (
            actual_state != expected_state
            or actual_levels != expected_levels
        ):
            raise TeacherReplayDivergence(
                "S0_TEACHER_OUTCOME_DIVERGED:"
                f"{game_id}:step={step}:"
                f"expected={expected_state}/{expected_levels}:"
                f"actual={actual_state}/{actual_levels}"
            )
        actual_available = _available_action_ids(frame)
        expected_available = [
            _integer(item, "expected_available_actions[]")
            for item in raw_step.get("expected_available_actions", ())
        ]
        if actual_available != expected_available:
            available_action_mismatches += 1
        actual_digest = _frame_digest(frame)
        expected_digest = str(
            raw_step.get("expected_frame_digest", "")
        )
        frame_match = actual_digest == expected_digest
        if not frame_match:
            frame_digest_mismatches += 1
            if strict_frame_digest:
                raise TeacherReplayDivergence(
                    "S0_TEACHER_FRAME_DIVERGED:"
                    f"{game_id}:step={step}"
                )
        actual_trace.append(
            {
                "step": step,
                "action_id": action_id,
                "action_data": payload,
                "state": actual_state,
                "levels_completed": actual_levels,
                "frame_digest": actual_digest,
                "reset_scope": (
                    "LEVEL_COMPATIBILITY"
                    if use_level_reset_compatibility
                    else "RECORDED_ACTION"
                ),
            }
        )
        previous = frame

    final_state = _frame_state(previous)
    final_levels = _frame_levels(previous)
    if final_state != "WIN" or final_levels != target_levels:
        raise TeacherReplayDivergence(
            "S0_TEACHER_FINAL_CLOSURE_FAILED:"
            f"{game_id}:{final_state}/{final_levels}/{target_levels}"
        )
    trace_digest = digest_object(actual_trace)
    return {
        "game_id": game_id,
        "target_levels": target_levels,
        "completed_levels": final_levels,
        "complete": True,
        "final_state": final_state,
        "actions_executed": len(actual_trace),
        "source_recorded_action_count": int(
            game_solution.get(
                "source_recorded_action_count",
                len(actual_trace),
            )
        ),
        "frame_digest_mismatch_count": frame_digest_mismatches,
        "available_action_mismatch_count": available_action_mismatches,
        "level_reset_compatibility_count": (
            level_reset_compatibility_count
        ),
        "actual_trace_digest": trace_digest,
        "source_solution_digest": game_solution.get("content_digest"),
    }


def run_teacher_corpus(
    *,
    environments_dir: Path,
    corpus_path: Path,
    requested_games: Sequence[str] = (),
    strict_frame_digest: bool = False,
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Run selected S0 solutions in OFFLINE mode with per-game scorecards."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_P10_R1")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    corpus = load_full_solution_corpus(corpus_path)
    games = corpus.get("games")
    if not isinstance(games, list):
        raise TypeError("TEACHER_CORPUS_GAMES_INVALID")
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(game.get("game_id"))
        for game in games
        if isinstance(game, Mapping)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "TEACHER_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown)
        )
    selected = [
        game
        for game in games
        if isinstance(game, Mapping)
        and (
            not requested
            or str(game.get("game_id")) in set(requested)
        )
    ]
    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else environments_dir.parent / "recordings"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")

    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for game_solution in selected:
        game_id = str(game_solution["game_id"])
        card_id = arcade.open_scorecard(
            tags=["p10-r1", "s0-teacher", "development-only"]
        )
        try:
            environment = arcade.make(
                game_id,
                scorecard_id=card_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise RuntimeError("S0_TEACHER_ENVIRONMENT_LOAD_FAILED")
            reports.append(
                replay_game_solution(
                    environment=environment,
                    game_solution=game_solution,
                    strict_frame_digest=strict_frame_digest,
                )
            )
        except Exception as error:
            errors.append(
                {
                    "game_id": game_id,
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            )
        finally:
            arcade.close_scorecard(card_id)
            gc.collect()

    reports.sort(key=lambda item: str(item["game_id"]))
    errors.sort(key=lambda item: str(item["game_id"]))
    level_count = sum(
        int(game["target_levels"])
        for game in selected
    )
    completed_levels = sum(
        int(report["completed_levels"])
        for report in reports
    )
    body: dict[str, Any] = {
        "schema_version": TEACHER_CLOSURE_REPORT_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R1-TEACHER-183-CLOSURE",
        "privilege_stage": "S0",
        "operation_mode": "offline",
        "source_corpus_digest": corpus["content_digest"],
        "complete_inventory": (
            corpus.get("complete_inventory") is True
            and not requested
        ),
        "game_count": len(selected),
        "completed_game_count": len(reports),
        "level_count": level_count,
        "completed_levels": completed_levels,
        "actions_executed": sum(
            int(report["actions_executed"])
            for report in reports
        ),
        "error_count": len(errors),
        "all_complete": (
            not errors
            and len(reports) == len(selected)
            and completed_levels == level_count
        ),
        "strict_frame_digest": strict_frame_digest,
        "frame_digest_mismatch_count": sum(
            int(report["frame_digest_mismatch_count"])
            for report in reports
        ),
        "available_action_mismatch_count": sum(
            int(report["available_action_mismatch_count"])
            for report in reports
        ),
        "level_reset_compatibility_count": sum(
            int(report["level_reset_compatibility_count"])
            for report in reports
        ),
        "reports": reports,
        "errors": errors,
    }
    return {
        **body,
        "content_digest": (
            TEACHER_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay S0 Teacher solutions in retained OFFLINE samples."
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--strict-frame-digest", action="store_true")
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = run_teacher_corpus(
        environments_dir=args.environments_dir,
        corpus_path=args.corpus,
        requested_games=tuple(args.game),
        strict_frame_digest=args.strict_frame_digest,
        recordings_dir=args.recordings_dir,
    )
    _write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "game_count": report["game_count"],
                "completed_levels": report["completed_levels"],
                "level_count": report["level_count"],
                "actions_executed": report["actions_executed"],
                "error_count": report["error_count"],
                "all_complete": report["all_complete"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TEACHER_CLOSURE_REPORT_SCHEMA_VERSION",
    "TeacherReplayDivergence",
    "replay_game_solution",
    "run_teacher_corpus",
]
