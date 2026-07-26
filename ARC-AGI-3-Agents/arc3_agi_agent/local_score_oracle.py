"""Score a complete P10 OFFLINE report with the ARC-AGI-3 RHAE oracle.

This is an identity-free post-processing tool.  It does not import an agent,
execute an environment, choose an action, or connect to an external service.
The scoring equations are adapted from the legacy local oracle at:

* repository: ``gatchimuchio/ARC-Layer-0-Functional-Compliance``
* commit: ``62a16b6f930b8f2663d4a07f791314069ca3043b``
* blob: ``5a5a77e7ef017c46c4b28581a06240e07ad718e5``
* path: ``scripts/generate_arc3_local_score_oracle.py``

The legacy evaluation adapter is intentionally not imported.  This module
normalizes the current ``p10_main.py`` report and fails closed unless its
reports, errors, scorecard rows, and the 25-game/183-level sample metadata
form one complete scoring input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from .schema import digest_object

ORACLE_ADAPTER_VERSION = "arc3-p10-local-score-oracle-v1"
ARTIFACT_TYPE = "arc3_local_score_oracle"
OFFICIAL_METHODOLOGY = "https://docs.arcprize.org/methodology"
TOOLKIT_VERSION = "0.9.8"
LEVEL_CAP_PERCENT = 115.0
EXPECTED_GAME_COUNT = 25
EXPECTED_LEVEL_COUNT = 183
LEGACY_SOURCE = {
    "repository": "gatchimuchio/ARC-Layer-0-Functional-Compliance",
    "commit": "62a16b6f930b8f2663d4a07f791314069ca3043b",
    "blob": "5a5a77e7ef017c46c4b28581a06240e07ad718e5",
    "path": "scripts/generate_arc3_local_score_oracle.py",
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "arc3_local_score_oracle_latest.json"
)
DEFAULT_MARKDOWN = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "arc3_local_score_oracle_latest.md"
)


@dataclass(frozen=True, slots=True)
class BaselineGame:
    """One immutable game row read from the retained official sample ZIP."""

    game_id: str
    title: str
    baseline_actions: tuple[int, ...]
    metadata_path: str


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
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


def _nonnegative_integer(value: object, field_name: str) -> int:
    result = _integer(value, field_name)
    if result < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return result


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path, field_name: str) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, field_name)


def load_sample_baselines(
    sample_zip: Path,
) -> tuple[dict[str, BaselineGame], str]:
    """Load and validate all 25 games and 183 baseline action counts."""

    rows: dict[str, BaselineGame] = {}
    with ZipFile(sample_zip) as archive:
        for name in archive.namelist():
            if not (
                name.startswith("environment_files/")
                and name.endswith("/metadata.json")
            ):
                continue
            metadata = _mapping(
                json.loads(archive.read(name).decode("utf-8")),
                f"sample metadata {name}",
            )
            game_id = str(metadata.get("game_id", "")).strip()
            title = str(metadata.get("title", game_id))
            baseline_values = _sequence(
                metadata.get("baseline_actions"),
                f"baseline_actions for {game_id or name}",
            )
            baseline_actions = tuple(
                _integer(value, f"baseline action for {game_id or name}")
                for value in baseline_values
            )
            if not game_id or not baseline_actions:
                raise ValueError(f"invalid sample metadata: {name}")
            if any(value <= 0 for value in baseline_actions):
                raise ValueError(
                    f"non-positive baseline action count: {name}"
                )
            if game_id in rows:
                raise ValueError(f"duplicate game metadata: {game_id}")
            rows[game_id] = BaselineGame(
                game_id=game_id,
                title=title,
                baseline_actions=baseline_actions,
                metadata_path=name,
            )
    if len(rows) != EXPECTED_GAME_COUNT:
        raise ValueError(
            "SAMPLE_GAME_COUNT_INVALID:"
            f"expected={EXPECTED_GAME_COUNT},actual={len(rows)}"
        )
    level_count = sum(len(row.baseline_actions) for row in rows.values())
    if level_count != EXPECTED_LEVEL_COUNT:
        raise ValueError(
            "SAMPLE_LEVEL_COUNT_INVALID:"
            f"expected={EXPECTED_LEVEL_COUNT},actual={level_count}"
        )
    return dict(sorted(rows.items())), _sha256(sample_zip)


def _score_level(baseline: int, actions: int, completed: bool) -> float:
    if not completed or actions <= 0:
        return 0.0
    return min(
        (baseline / actions) ** 2 * 100.0,
        LEVEL_CAP_PERCENT,
    )


def score_game(
    baseline_actions: Sequence[int],
    action_values: Sequence[int],
    reported_levels_completed: int,
) -> dict[str, object]:
    """Apply the legacy toolkit-0.9.8-compatible per-game equations."""

    level_count = len(baseline_actions)
    if level_count < 1:
        raise ValueError("baseline_actions must not be empty")
    if any(value <= 0 for value in baseline_actions):
        raise ValueError("baseline_actions must be positive")
    if reported_levels_completed < 0 or reported_levels_completed > level_count:
        raise ValueError("reported_levels_completed is outside game bounds")
    if any(value < 0 for value in action_values):
        raise ValueError("action_values must be nonnegative")
    padded_actions = tuple(action_values[:level_count]) + (0,) * max(
        0,
        level_count - len(action_values),
    )
    if any(
        padded_actions[index] <= 0
        for index in range(reported_levels_completed)
    ):
        raise ValueError(
            "COMPLETED_LEVEL_ACTION_COUNT_MISSING:"
            f"completed={reported_levels_completed},actions={padded_actions}"
        )
    level_scores = tuple(
        _score_level(
            baseline,
            actions,
            level_index < reported_levels_completed,
        )
        for level_index, (baseline, actions) in enumerate(
            zip(baseline_actions, padded_actions),
        )
    )
    scored_actions = tuple(
        actions if index < reported_levels_completed else 0
        for index, actions in enumerate(padded_actions)
    )
    total_weight = sum(range(1, level_count + 1))
    weighted_score = sum(
        score * index
        for index, score in enumerate(level_scores, start=1)
    )
    completed_weight = sum(
        index
        for index, score in enumerate(level_scores, start=1)
        if score > 0.0
    )
    raw_game_score = weighted_score / total_weight
    completion_ceiling = completed_weight / total_weight * 100.0
    game_score = min(raw_game_score, completion_ceiling)
    return {
        "level_count": level_count,
        "levels_completed": reported_levels_completed,
        "completion_rate": reported_levels_completed / level_count,
        "attempted_level_actions": list(padded_actions),
        "scored_level_actions": list(scored_actions),
        "level_scores_percent": [
            round(value, 9) for value in level_scores
        ],
        "weighted_raw_score_percent": round(raw_game_score, 9),
        "completion_ceiling_percent": round(completion_ceiling, 9),
        "game_score_percent": round(game_score, 9),
    }


def _scorecard_runs(
    value: object,
) -> dict[str, Mapping[str, object] | None]:
    scorecard = _mapping(value, "P10 local_scorecard")
    environments = _sequence(
        scorecard.get("environments"),
        "P10 local_scorecard.environments",
    )
    runs: dict[str, Mapping[str, object] | None] = {}
    for raw_environment in environments:
        environment = _mapping(
            raw_environment,
            "P10 scorecard environment",
        )
        game_id = str(environment.get("id", "")).strip()
        if not game_id:
            raise ValueError("P10_SCORECARD_GAME_ID_MISSING")
        if game_id in runs:
            raise ValueError(f"P10_SCORECARD_GAME_DUPLICATE:{game_id}")
        raw_runs = _sequence(
            environment.get("runs"),
            f"P10 scorecard runs for {game_id}",
        )
        runs[game_id] = (
            None
            if not raw_runs
            else _mapping(
                raw_runs[-1],
                f"P10 latest scorecard run for {game_id}",
            )
        )
    return runs


def normalize_p10_report(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Convert one complete P10 report into the legacy evaluation contract."""

    if value.get("phase") != "P10":
        raise ValueError("P10_REPORT_PHASE_INVALID")
    if str(value.get("operation_mode", "")).casefold() != "offline":
        raise ValueError("P10_REPORT_NON_OFFLINE")
    reports = _sequence(value.get("reports"), "P10 reports")
    errors = _sequence(value.get("errors"), "P10 errors")
    scorecard_runs = _scorecard_runs(value.get("local_scorecard"))
    normalized_rows: dict[str, dict[str, object]] = {}
    instruction_versions: set[str] = set()
    instruction_digests: set[str] = set()
    visual_versions: set[str] = set()

    for raw_report in reports:
        report = _mapping(raw_report, "P10 game report")
        game_id = str(report.get("game_id", "")).strip()
        if not game_id:
            raise ValueError("P10_REPORT_GAME_ID_MISSING")
        if game_id in normalized_rows:
            raise ValueError(f"P10_REPORT_GAME_DUPLICATE:{game_id}")
        levels_completed = _nonnegative_integer(
            report.get("levels_completed"),
            f"levels_completed for {game_id}",
        )
        win_levels = _nonnegative_integer(
            report.get("win_levels"),
            f"win_levels for {game_id}",
        )
        actions_used = _nonnegative_integer(
            report.get("actions"),
            f"actions for {game_id}",
        )
        if levels_completed > win_levels:
            raise ValueError(f"P10_COMPLETION_OUT_OF_RANGE:{game_id}")
        scorecard_run = scorecard_runs.get(game_id)
        if scorecard_run is None:
            raise ValueError(f"P10_SCORECARD_GAME_MISSING:{game_id}")
        scorecard_completed = _nonnegative_integer(
            scorecard_run.get("levels_completed"),
            f"scorecard levels_completed for {game_id}",
        )
        if scorecard_completed != levels_completed:
            raise ValueError(
                "P10_SCORECARD_COMPLETION_MISMATCH:"
                f"{game_id}:report={levels_completed},"
                f"scorecard={scorecard_completed}"
            )
        raw_level_actions = _sequence(
            scorecard_run.get("level_actions"),
            f"scorecard level_actions for {game_id}",
        )
        level_actions = [
            _nonnegative_integer(
                action,
                f"scorecard level action for {game_id}",
            )
            for action in raw_level_actions
        ]
        if any(
            level_actions[index] <= 0
            for index in range(
                min(levels_completed, len(level_actions)),
            )
        ) or len(level_actions) < levels_completed:
            raise ValueError(
                f"P10_COMPLETED_LEVEL_ACTION_COUNT_MISSING:{game_id}"
            )
        terminal_state = str(
            report.get("terminal_state", "UNKNOWN")
        ).upper()
        normalized_rows[game_id] = {
            "game_id": game_id,
            "levels_completed": levels_completed,
            "win_levels": win_levels,
            "state": terminal_state,
            "actions_used": actions_used,
            "game_over": terminal_state == "GAME_OVER",
            "not_finished": terminal_state == "NOT_FINISHED",
            "max_action_exhausted": bool(
                report.get("max_action_exhausted")
            ),
            "level_actions": level_actions,
            "error": "",
        }
        instruction_versions.update(
            str(item)
            for item in _sequence(
                report.get("instruction_body_versions", ()),
                f"instruction_body_versions for {game_id}",
            )
        )
        instruction_digests.update(
            str(item)
            for item in _sequence(
                report.get("instruction_body_digests", ()),
                f"instruction_body_digests for {game_id}",
            )
        )
        visual_version = str(
            report.get("visual_operator_version", "")
        ).strip()
        if visual_version:
            visual_versions.add(visual_version)

    normalized_errors: list[dict[str, str]] = []
    for raw_error in errors:
        error = _mapping(raw_error, "P10 error")
        game_id = str(error.get("game_id", "")).strip()
        if not game_id:
            raise ValueError("P10_ERROR_GAME_ID_MISSING")
        if game_id in normalized_rows:
            raise ValueError(f"P10_RESULT_AND_ERROR_CONFLICT:{game_id}")
        error_type = str(error.get("error_type", "")).strip()
        message = str(error.get("message", "")).strip()
        normalized_rows[game_id] = {
            "game_id": game_id,
            "levels_completed": 0,
            "win_levels": None,
            "state": "ERROR",
            "actions_used": 0,
            "game_over": False,
            "not_finished": False,
            "max_action_exhausted": False,
            "level_actions": [],
            "error": (
                f"{error_type}: {message}".strip(": ")
            ),
        }
        normalized_errors.append(
            {
                "game_id": game_id,
                "error_type": error_type,
                "message": message,
            }
        )

    unknown_scorecards = sorted(set(scorecard_runs) - set(normalized_rows))
    if unknown_scorecards:
        raise ValueError(
            "P10_SCORECARD_UNKNOWN_GAMES:"
            + ",".join(unknown_scorecards)
        )
    environment_count = _nonnegative_integer(
        value.get("environment_count"),
        "P10 environment_count",
    )
    if environment_count != len(normalized_rows):
        raise ValueError(
            "P10_ENVIRONMENT_COUNT_MISMATCH:"
            f"reported={environment_count},actual={len(normalized_rows)}"
        )
    if _nonnegative_integer(
        value.get("completed_count"),
        "P10 completed_count",
    ) != len(reports):
        raise ValueError("P10_COMPLETED_COUNT_MISMATCH")
    if _nonnegative_integer(
        value.get("error_count"),
        "P10 error_count",
    ) != len(errors):
        raise ValueError("P10_ERROR_COUNT_MISMATCH")
    completed_levels = sum(
        _integer(row["levels_completed"], "normalized levels_completed")
        for row in normalized_rows.values()
    )
    if _nonnegative_integer(
        value.get("completed_levels"),
        "P10 completed_levels",
    ) != completed_levels:
        raise ValueError("P10_COMPLETED_LEVEL_TOTAL_MISMATCH")

    instruction_variant = str(
        value.get("instruction_variant", "")
    ).strip()
    max_actions = _nonnegative_integer(
        value.get("max_actions"),
        "P10 max_actions",
    )
    rows = [normalized_rows[key] for key in sorted(normalized_rows)]
    evaluation: dict[str, object] = {
        "schema_version": 1,
        "adapter_version": ORACLE_ADAPTER_VERSION,
        "agent": f"arc3-agi-agent:p10:{instruction_variant}",
        "evaluation_provenance": {
            "mode": "p10-offline",
            "operation_mode": "offline",
            "phase": "P10",
            "instruction_variant": instruction_variant,
            "max_actions": max_actions,
            "instruction_body_versions": sorted(instruction_versions),
            "instruction_body_digests": sorted(instruction_digests),
            "visual_operator_versions": sorted(visual_versions),
            "architecture_evidence_eligible": False,
            "architecture_evidence_rule": (
                "local score is a regression metric and does not prove "
                "genericity or P10 completion"
            ),
        },
        "max_actions": max_actions,
        "environment_count": environment_count,
        "public_total_levels": completed_levels,
        "public_total_win_levels": sum(
            _integer(row["win_levels"], "normalized win_levels")
            for row in rows
            if row["win_levels"] is not None
        ),
        "game_over_count": sum(bool(row["game_over"]) for row in rows),
        "not_finished_count": sum(
            bool(row["not_finished"]) for row in rows
        ),
        "maxed_out_count": sum(
            bool(row["max_action_exhausted"]) for row in rows
        ),
        "errors": sorted(
            normalized_errors,
            key=lambda item: (
                item["game_id"],
                item["error_type"],
                item["message"],
            ),
        ),
        "results": rows,
    }
    evaluation["scoring_input_digest"] = digest_object(evaluation)
    return evaluation


def build_local_score_oracle(
    sample_zip: Path,
    p10_report_path: Path,
) -> dict[str, object]:
    """Build a complete RHAE score artifact from one P10 report."""

    baselines, sample_sha256 = load_sample_baselines(sample_zip)
    p10_report = _load_json_object(p10_report_path, "P10 report")
    evaluation = normalize_p10_report(p10_report)
    raw_rows = _sequence(evaluation.get("results"), "normalized results")
    evaluation_rows = {
        str(_mapping(row, "normalized result").get("game_id", "")): _mapping(
            row,
            "normalized result",
        )
        for row in raw_rows
    }
    missing = sorted(set(baselines) - set(evaluation_rows))
    unknown = sorted(set(evaluation_rows) - set(baselines))
    if missing or unknown:
        raise ValueError(
            "EVALUATION_GAME_MISMATCH:"
            f"missing={missing},unknown={unknown}"
        )

    games: list[dict[str, object]] = []
    for game_id, metadata in baselines.items():
        result = evaluation_rows[game_id]
        reported_win_levels = result.get("win_levels")
        if (
            reported_win_levels is not None
            and _integer(
                reported_win_levels,
                f"win_levels for {game_id}",
            )
            != len(metadata.baseline_actions)
        ):
            raise ValueError(
                "EVALUATION_LEVEL_COUNT_MISMATCH:"
                f"{game_id}:report={reported_win_levels},"
                f"baseline={len(metadata.baseline_actions)}"
            )
        raw_actions = _sequence(
            result.get("level_actions"),
            f"level_actions for {game_id}",
        )
        action_values = [
            _nonnegative_integer(
                value,
                f"level action for {game_id}",
            )
            for value in raw_actions
        ]
        completed = _nonnegative_integer(
            result.get("levels_completed"),
            f"levels_completed for {game_id}",
        )
        score = score_game(
            metadata.baseline_actions,
            action_values,
            completed,
        )
        games.append(
            {
                "game_id": game_id,
                "title": metadata.title,
                "baseline_actions": list(metadata.baseline_actions),
                "evaluation_state": str(result.get("state", "UNKNOWN")),
                "evaluation_error": str(result.get("error", "")),
                "actions_used": _nonnegative_integer(
                    result.get("actions_used"),
                    f"actions_used for {game_id}",
                ),
                **score,
            }
        )

    total_levels = sum(
        _integer(game["level_count"], "game level_count")
        for game in games
    )
    completed_levels = sum(
        _integer(game["levels_completed"], "game levels_completed")
        for game in games
    )
    total_score = sum(
        _number(
            game["game_score_percent"],
            "game_score_percent",
        )
        for game in games
    ) / len(games)
    current_result: dict[str, object] = {
        "agent_label": str(evaluation.get("agent", "")),
        "evaluation_provenance": evaluation.get(
            "evaluation_provenance",
            {},
        ),
        "completed_levels": completed_levels,
        "completion_rate": completed_levels / total_levels,
        "completion_rate_percent": round(
            completed_levels / total_levels * 100.0,
            9,
        ),
        "official_rhae_score_percent": round(total_score, 9),
        "official_rhae_score_fraction": round(
            total_score / 100.0,
            9,
        ),
        "error_count": len(
            _sequence(evaluation.get("errors"), "normalized errors")
        ),
        "game_over_count": _nonnegative_integer(
            evaluation.get("game_over_count"),
            "normalized game_over_count",
        ),
        "maxed_out_count": _nonnegative_integer(
            evaluation.get("maxed_out_count"),
            "normalized maxed_out_count",
        ),
        "not_finished_count": _nonnegative_integer(
            evaluation.get("not_finished_count"),
            "normalized not_finished_count",
        ),
    }
    scoring_authority = {
        "methodology_url": OFFICIAL_METHODOLOGY,
        "toolkit": "arc-agi",
        "toolkit_version": TOOLKIT_VERSION,
        "level_formula": (
            "min((baseline_actions / ai_actions)^2 * 100, 115)"
        ),
        "game_formula": (
            "min(weighted_level_average, "
            "weighted_completed_level_ceiling)"
        ),
        "total_formula": "arithmetic_mean(per_game_scores)",
        "full_completion_score_cap_percent": 100.0,
        "per_level_efficiency_cap_percent": LEVEL_CAP_PERCENT,
    }
    oracle_summary = {
        "game_count": len(games),
        "level_count": total_levels,
        "perfect_completion_levels": total_levels,
        "perfect_completion_rate": 1.0,
        "perfect_score_percent": 100.0,
        "baseline_action_total": sum(
            sum(
                _integer(value, "baseline action")
                for value in _sequence(
                    game["baseline_actions"],
                    "game baseline_actions",
                )
            )
            for game in games
        ),
    }
    score_digest = digest_object(
        {
            "adapter_version": ORACLE_ADAPTER_VERSION,
            "scoring_authority": scoring_authority,
            "oracle": oracle_summary,
            "current_local_result": current_result,
            "games": games,
            "scoring_input_digest": evaluation[
                "scoring_input_digest"
            ],
        }
    )
    return {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "adapter_version": ORACLE_ADAPTER_VERSION,
        "legacy_source": dict(LEGACY_SOURCE),
        "source": {
            "sample_zip": str(sample_zip.resolve()),
            "sample_zip_sha256": sample_sha256,
            "p10_report": str(p10_report_path.resolve()),
            "p10_report_sha256": _sha256(p10_report_path),
            "scoring_input_digest": evaluation[
                "scoring_input_digest"
            ],
        },
        "scoring_authority": scoring_authority,
        "oracle": oracle_summary,
        "current_local_result": current_result,
        "games": games,
        "score_digest": score_digest,
    }


def render_oracle_markdown(oracle: Mapping[str, object]) -> str:
    """Render a deterministic, compact human-readable score report."""

    current = _mapping(
        oracle.get("current_local_result"),
        "oracle current_local_result",
    )
    oracle_summary = _mapping(oracle.get("oracle"), "oracle summary")
    games = _sequence(oracle.get("games"), "oracle games")
    rows = [
        "| game_id | completed | game score % | "
        "completion ceiling % | actions |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for raw_game in games:
        game = _mapping(raw_game, "oracle game")
        rows.append(
            "| {game_id} | {levels_completed}/{level_count} | "
            "{game_score:.6f} | {completion_ceiling:.6f} | "
            "{actions_used} |".format(
                game_id=str(game.get("game_id", "")),
                levels_completed=_nonnegative_integer(
                    game.get("levels_completed"),
                    "markdown levels_completed",
                ),
                level_count=_nonnegative_integer(
                    game.get("level_count"),
                    "markdown level_count",
                ),
                game_score=_number(
                    game.get("game_score_percent"),
                    "markdown game_score_percent",
                ),
                completion_ceiling=_number(
                    game.get("completion_ceiling_percent"),
                    "markdown completion_ceiling_percent",
                ),
                actions_used=_nonnegative_integer(
                    game.get("actions_used"),
                    "markdown actions_used",
                ),
            )
        )
    return "\n".join(
        [
            "# ARC-AGI-3 Local Score Oracle",
            "",
            f"- adapter: {oracle.get('adapter_version', '')}",
            f"- games: {oracle_summary.get('game_count', 0)}",
            f"- levels: {oracle_summary.get('level_count', 0)}",
            (
                "- current completion: "
                f"{current.get('completed_levels', 0)}/"
                f"{oracle_summary.get('level_count', 0)} "
                f"({_number(current.get('completion_rate_percent', 0.0), 'completion_rate_percent'):.6f}%)"
            ),
            (
                "- current official RHAE: "
                f"{_number(current.get('official_rhae_score_percent', 0.0), 'official_rhae_score_percent'):.6f}%"
            ),
            f"- errors: {current.get('error_count', 0)}",
            f"- game over: {current.get('game_over_count', 0)}",
            f"- maxed out: {current.get('maxed_out_count', 0)}",
            f"- not finished: {current.get('not_finished_count', 0)}",
            f"- score digest: {oracle.get('score_digest', '')}",
            "",
            f"Scoring authority: {OFFICIAL_METHODOLOGY}",
            "",
            *rows,
            "",
        ]
    )


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )
    try:
        temporary.write_text(
            value,
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_paths(
    sample_zip: Path,
    p10_report: Path,
    output: Path,
    markdown: Path,
) -> None:
    if not sample_zip.is_file():
        raise FileNotFoundError(
            f"sample ZIP not found: {sample_zip}"
        )
    if not p10_report.is_file():
        raise FileNotFoundError(
            f"P10 report not found: {p10_report}"
        )
    resolved_inputs = {
        sample_zip.resolve(),
        p10_report.resolve(),
    }
    resolved_outputs = {
        output.resolve(),
        markdown.resolve(),
    }
    if len(resolved_outputs) != 2:
        raise ValueError("ORACLE_OUTPUT_PATHS_MUST_DIFFER")
    if resolved_inputs & resolved_outputs:
        raise ValueError("ORACLE_OUTPUT_MUST_NOT_OVERWRITE_INPUT")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-zip", type=Path, required=True)
    parser.add_argument("--p10-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--markdown",
        type=Path,
        default=DEFAULT_MARKDOWN,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = _parser().parse_args(argv)
    _validate_paths(
        args.sample_zip,
        args.p10_report,
        args.output,
        args.markdown,
    )
    oracle = build_local_score_oracle(
        args.sample_zip,
        args.p10_report,
    )
    encoded = json.dumps(
        oracle,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _atomic_write_text(args.output, encoded + "\n")
    _atomic_write_text(
        args.markdown,
        render_oracle_markdown(oracle),
    )
    current = _mapping(
        oracle["current_local_result"],
        "oracle current_local_result",
    )
    summary = _mapping(oracle["oracle"], "oracle summary")
    print(
        "games={games} levels={levels} completed={completed} "
        "completion_percent={completion:.6f} "
        "rhae_percent={rhae:.6f} score_digest={digest}".format(
            games=summary["game_count"],
            levels=summary["level_count"],
            completed=current["completed_levels"],
            completion=_number(
                current["completion_rate_percent"],
                "completion_rate_percent",
            ),
            rhae=_number(
                current["official_rhae_score_percent"],
                "official_rhae_score_percent",
            ),
            digest=oracle["score_digest"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
