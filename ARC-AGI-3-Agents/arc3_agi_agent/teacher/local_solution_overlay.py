"""Overlay retained local successes onto incompatible public trajectories.

The public human corpus can contain trajectories recorded against an older
revision of a retained sample.  P10-R1 permits a development-only, identity-
aware Teacher to replace such a row with a pinned local success, while keeping
the original row provenance and action count visible for audit.
"""

from __future__ import annotations

import argparse
import hashlib
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
from .human_replay_corpus import (
    FULL_SOLUTION_CORPUS_DIGEST_PREFIX,
    GAME_SOLUTION_DIGEST_PREFIX,
    load_full_solution_corpus,
)
from .replay_runner import (
    _available_action_ids,
    _frame_digest,
    _frame_levels,
    _frame_state,
)

LOCAL_OVERRIDE_MANIFEST_SCHEMA_VERSION = (
    "arc3-teacher-local-solution-override-manifest-v1"
)
LOCAL_OVERRIDE_MANIFEST_DIGEST_PREFIX = (
    "arc3_teacher_local_solution_override_manifest:"
)
LOCAL_OVERRIDE_PRIVILEGE = "RETAINED_LOCAL_SUCCESS_EVIDENCE"


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


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


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_local_override_manifest(path: Path) -> dict[str, Any]:
    """Load and validate the development-only local override declaration."""

    manifest = _json_object(path)
    failures: list[str] = []
    if (
        manifest.get("schema_version")
        != LOCAL_OVERRIDE_MANIFEST_SCHEMA_VERSION
    ):
        failures.append("TEACHER_LOCAL_OVERRIDE_SCHEMA_INVALID")
    if manifest.get("development_only") is not True:
        failures.append("TEACHER_LOCAL_OVERRIDE_NOT_DEVELOPMENT_ONLY")
    if manifest.get("runtime_use") != "FORBIDDEN":
        failures.append("TEACHER_LOCAL_OVERRIDE_RUNTIME_BOUNDARY_INVALID")
    raw_overrides = manifest.get("overrides")
    if not isinstance(raw_overrides, list) or not raw_overrides:
        failures.append("TEACHER_LOCAL_OVERRIDES_INVALID")
        raw_overrides = []
    game_ids: list[str] = []
    for index, raw_override in enumerate(raw_overrides):
        if not isinstance(raw_override, dict):
            failures.append(f"TEACHER_LOCAL_OVERRIDE_INVALID:{index}")
            continue
        try:
            game_id = _string(
                raw_override.get("game_id"),
                f"overrides[{index}].game_id",
            )
            evidence_path = _string(
                raw_override.get("evidence_path"),
                f"overrides[{index}].evidence_path",
            )
            file_sha256 = _string(
                raw_override.get("file_sha256"),
                f"overrides[{index}].file_sha256",
            )
            _string(
                raw_override.get("evidence_content_digest"),
                f"overrides[{index}].evidence_content_digest",
            )
            expected_actions = _integer(
                raw_override.get("expected_actions"),
                f"overrides[{index}].expected_actions",
            )
            expected_levels = _integer(
                raw_override.get("expected_levels"),
                f"overrides[{index}].expected_levels",
            )
        except (TypeError, ValueError) as error:
            failures.append(
                f"TEACHER_LOCAL_OVERRIDE_FIELD_INVALID:{index}:{error}"
            )
            continue
        if raw_override.get("kind") != "P10_COMPACT_EMITTED_STEPS":
            failures.append(f"TEACHER_LOCAL_OVERRIDE_KIND_INVALID:{index}")
        if (
            Path(evidence_path).is_absolute()
            or len(file_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in file_sha256
            )
            or expected_actions < 1
            or expected_levels < 1
        ):
            failures.append(f"TEACHER_LOCAL_OVERRIDE_RANGE_INVALID:{index}")
        game_ids.append(game_id)
    if len(set(game_ids)) != len(game_ids):
        failures.append("TEACHER_LOCAL_OVERRIDE_GAME_DUPLICATE")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return manifest


def local_override_manifest_digest(manifest: Mapping[str, Any]) -> str:
    return LOCAL_OVERRIDE_MANIFEST_DIGEST_PREFIX + digest_object(dict(manifest))


def _resolve_evidence_path(
    repository_root: Path,
    relative_path: str,
) -> Path:
    root = repository_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise AuthorityViolation(
            "TEACHER_LOCAL_OVERRIDE_PATH_ESCAPES_REPOSITORY"
        ) from error
    if not path.is_file():
        raise FileNotFoundError(f"local success evidence not found: {path}")
    return path


def _extract_evidence_actions(
    *,
    repository_root: Path,
    override: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, int]], Path]:
    game_id = _string(override.get("game_id"), "game_id")
    evidence_path = _resolve_evidence_path(
        repository_root,
        _string(override.get("evidence_path"), "evidence_path"),
    )
    actual_file_sha256 = _sha256_file(evidence_path)
    if actual_file_sha256 != override.get("file_sha256"):
        raise ValueError(
            f"TEACHER_LOCAL_OVERRIDE_FILE_DIGEST_INVALID:{game_id}"
        )
    evidence = _json_object(evidence_path)
    if (
        evidence.get("content_digest")
        != override.get("evidence_content_digest")
    ):
        raise ValueError(
            f"TEACHER_LOCAL_OVERRIDE_CONTENT_DIGEST_INVALID:{game_id}"
        )
    compact_run = evidence.get("compact_run")
    if not isinstance(compact_run, Mapping):
        raise TypeError("TEACHER_LOCAL_OVERRIDE_COMPACT_RUN_INVALID")
    raw_reports = _sequence(
        compact_run.get("reports"),
        "compact_run.reports",
    )
    reports = [
        item
        for item in raw_reports
        if isinstance(item, Mapping) and item.get("game_id") == game_id
    ]
    if len(reports) != 1:
        raise ValueError(
            f"TEACHER_LOCAL_OVERRIDE_REPORT_NOT_UNIQUE:{game_id}"
        )
    report = reports[0]
    expected_actions = _integer(
        override.get("expected_actions"),
        "expected_actions",
    )
    expected_levels = _integer(
        override.get("expected_levels"),
        "expected_levels",
    )
    if (
        report.get("complete") is not True
        or report.get("terminal_state") != "WIN"
        or report.get("actions") != expected_actions
        or report.get("levels_completed") != expected_levels
    ):
        raise ValueError(
            f"TEACHER_LOCAL_OVERRIDE_SUCCESS_CLAIM_INVALID:{game_id}"
        )
    raw_cycles = _sequence(report.get("emitted_steps"), "emitted_steps")
    if len(raw_cycles) != expected_actions:
        raise ValueError(
            f"TEACHER_LOCAL_OVERRIDE_ACTION_COUNT_INVALID:{game_id}"
        )
    actions: list[dict[str, int]] = []
    for cycle_index, raw_cycle in enumerate(raw_cycles, start=1):
        cycle = _sequence(raw_cycle, f"emitted_steps[{cycle_index}]")
        if len(cycle) != 1 or not isinstance(cycle[0], Mapping):
            raise ValueError(
                f"TEACHER_LOCAL_OVERRIDE_CYCLE_INVALID:{game_id}:"
                f"{cycle_index}"
            )
        raw_action = cycle[0]
        action_id = _integer(
            raw_action.get("action_id"),
            f"emitted_steps[{cycle_index}].action_id",
        )
        if not 0 <= action_id <= 7:
            raise ValueError(
                f"TEACHER_LOCAL_OVERRIDE_ACTION_ID_INVALID:{game_id}:"
                f"{cycle_index}"
            )
        action: dict[str, int] = {"action_id": action_id}
        for key in ("x", "y"):
            if raw_action.get(key) is not None:
                action[key] = _integer(
                    raw_action.get(key),
                    f"emitted_steps[{cycle_index}].{key}",
                )
        actions.append(action)
    return evidence, actions, evidence_path


def _compile_override_game(
    *,
    arcade: Arcade,
    repository_root: Path,
    override: Mapping[str, Any],
    original_solution: Mapping[str, Any],
) -> dict[str, Any]:
    game_id = _string(override.get("game_id"), "game_id")
    evidence, source_actions, evidence_path = _extract_evidence_actions(
        repository_root=repository_root,
        override=override,
    )
    target_levels = _integer(
        override.get("expected_levels"),
        "expected_levels",
    )
    scorecard_id = arcade.open_scorecard(
        tags=["p10-r1", "s0-teacher", "local-success-override"]
    )
    try:
        environment = arcade.make(
            game_id,
            scorecard_id=scorecard_id,
            save_recording=False,
            include_frame_data=True,
        )
        if not isinstance(environment, LocalEnvironmentWrapper):
            raise RuntimeError("S0_TEACHER_ENVIRONMENT_LOAD_FAILED")
        initial = environment.observation_space
        if not isinstance(initial, FrameDataRaw):
            raise RuntimeError("S0_TEACHER_INITIAL_FRAME_MISSING")
        initial_observation = {
            "source": "LOCAL_RETAINED_SUCCESS_REPLAY",
            "state": _frame_state(initial),
            "levels_completed": _frame_levels(initial),
            "available_actions": _available_action_ids(initial),
            "frame_digest": _frame_digest(initial),
        }
        compiled_actions: list[dict[str, Any]] = []
        level_boundaries: list[dict[str, int]] = []
        prior_levels = _frame_levels(initial)
        final = initial
        for step, source_action in enumerate(source_actions, start=1):
            action_id = source_action["action_id"]
            payload = {
                key: source_action[key]
                for key in ("x", "y")
                if key in source_action
            }
            if (
                action_id != 0
                and action_id not in _available_action_ids(final)
            ):
                raise RuntimeError(
                    "TEACHER_LOCAL_OVERRIDE_ACTION_UNAVAILABLE:"
                    f"{game_id}:step={step}:action={action_id}"
                )
            frame = environment.step(
                GameAction.from_id(action_id),
                data=payload,
                reasoning={
                    "authority": "S0_PRIVILEGED_TEACHER",
                    "runtime_use": "FORBIDDEN",
                    "source": "PINNED_LOCAL_SUCCESS_EVIDENCE",
                    "game_id": game_id,
                    "source_step": step,
                },
            )
            if not isinstance(frame, FrameDataRaw):
                raise RuntimeError(
                    f"TEACHER_LOCAL_OVERRIDE_STEP_FAILED:{game_id}:{step}"
                )
            completed = _frame_levels(frame)
            compiled_actions.append(
                {
                    "step": step,
                    "action_id": action_id,
                    "action_data": payload,
                    "expected_state": _frame_state(frame),
                    "expected_levels_completed": completed,
                    "expected_available_actions": (
                        _available_action_ids(frame)
                    ),
                    "expected_frame_digest": _frame_digest(frame),
                    "full_reset": bool(frame.full_reset),
                }
            )
            if completed > prior_levels:
                for level in range(prior_levels + 1, completed + 1):
                    level_boundaries.append(
                        {"level": level, "action_count": step}
                    )
            prior_levels = completed
            final = frame
    finally:
        arcade.close_scorecard(scorecard_id)
    if _frame_state(final) != "WIN" or prior_levels != target_levels:
        raise RuntimeError(
            f"TEACHER_LOCAL_OVERRIDE_CLOSURE_FAILED:{game_id}:"
            f"{_frame_state(final)}/{prior_levels}/{target_levels}"
        )
    if len(level_boundaries) != target_levels:
        raise RuntimeError(
            f"TEACHER_LOCAL_OVERRIDE_BOUNDARIES_INVALID:{game_id}"
        )
    original_source = original_solution.get("source")
    body: dict[str, Any] = {
        "schema_version": "arc3-teacher-game-solution-v1",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "privilege_stage": "S0",
        "privileges": sorted(
            {
                *(
                    str(item)
                    for item in original_solution.get("privileges", ())
                ),
                LOCAL_OVERRIDE_PRIVILEGE,
            }
        ),
        "game_id": game_id,
        "target_levels": target_levels,
        "source_recorded_action_count": _integer(
            original_solution.get("source_recorded_action_count"),
            "source_recorded_action_count",
        ),
        "action_count": len(compiled_actions),
        "solution_origin": "PINNED_LOCAL_SUCCESS_EVIDENCE_OVERRIDE",
        "source": {
            "public_human_trajectory": original_source,
            "public_solution_digest": original_solution.get(
                "content_digest"
            ),
            "override_kind": override.get("kind"),
            "evidence_path": evidence_path.relative_to(
                repository_root.resolve()
            ).as_posix(),
            "evidence_file_sha256": _sha256_file(evidence_path),
            "evidence_content_digest": evidence.get("content_digest"),
        },
        "initial_observation": initial_observation,
        "level_boundaries": level_boundaries,
        "actions": compiled_actions,
        "final_state": "WIN",
    }
    return {
        **body,
        "content_digest": GAME_SOLUTION_DIGEST_PREFIX + digest_object(body),
    }


def apply_local_solution_overrides(
    *,
    repository_root: Path,
    environments_dir: Path,
    corpus_path: Path,
    override_manifest_path: Path,
) -> dict[str, Any]:
    """Compile and apply all pinned local-success overrides."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_P10_R1")
    corpus = load_full_solution_corpus(corpus_path)
    manifest = load_local_override_manifest(override_manifest_path)
    raw_games = corpus.get("games")
    if not isinstance(raw_games, list):
        raise TypeError("TEACHER_CORPUS_GAMES_INVALID")
    by_game_id = {
        str(game["game_id"]): game
        for game in raw_games
        if isinstance(game, dict)
    }
    raw_overrides = manifest.get("overrides")
    if not isinstance(raw_overrides, list):
        raise TypeError("TEACHER_LOCAL_OVERRIDES_INVALID")
    requested_ids = {
        str(item.get("game_id"))
        for item in raw_overrides
        if isinstance(item, Mapping)
    }
    unknown = sorted(requested_ids.difference(by_game_id))
    if unknown:
        raise ValueError(
            "TEACHER_LOCAL_OVERRIDE_GAME_UNKNOWN:" + ",".join(unknown)
        )
    environments_dir = environments_dir.resolve()
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(environments_dir.parent / "recordings"),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")
    for raw_override in raw_overrides:
        if not isinstance(raw_override, Mapping):
            raise TypeError("TEACHER_LOCAL_OVERRIDE_INVALID")
        game_id = _string(raw_override.get("game_id"), "game_id")
        by_game_id[game_id] = _compile_override_game(
            arcade=arcade,
            repository_root=repository_root,
            override=raw_override,
            original_solution=by_game_id[game_id],
        )
    games = sorted(
        by_game_id.values(),
        key=lambda item: str(item["game_id"]),
    )
    body = dict(corpus)
    body.pop("content_digest", None)
    body["games"] = games
    body["action_count"] = sum(
        _integer(game.get("action_count"), "action_count")
        for game in games
    )
    body["privileges"] = sorted(
        {
            *(str(item) for item in corpus.get("privileges", ())),
            LOCAL_OVERRIDE_PRIVILEGE,
        }
    )
    body["local_solution_override_manifest_digest"] = (
        local_override_manifest_digest(manifest)
    )
    body["local_solution_override_count"] = len(raw_overrides)
    return {
        **body,
        "content_digest": (
            FULL_SOLUTION_CORPUS_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply pinned local-success overrides to an S0 corpus."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--override-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    corpus = apply_local_solution_overrides(
        repository_root=args.repository_root,
        environments_dir=args.environments_dir,
        corpus_path=args.corpus,
        override_manifest_path=args.override_manifest,
    )
    _write_json(args.output, corpus)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "game_count": corpus["game_count"],
                "level_count": corpus["level_count"],
                "action_count": corpus["action_count"],
                "local_solution_override_count": corpus[
                    "local_solution_override_count"
                ],
                "content_digest": corpus["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LOCAL_OVERRIDE_MANIFEST_SCHEMA_VERSION",
    "LOCAL_OVERRIDE_PRIVILEGE",
    "apply_local_solution_overrides",
    "load_local_override_manifest",
    "local_override_manifest_digest",
]
