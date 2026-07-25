"""Fail-closed per-game checkpoints for complete P10 OFFLINE measurement."""

from __future__ import annotations

import copy
import functools
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .p10_evidence import stable_p10_run
from .schema import digest_object

P10_BATCH_CHECKPOINT_SCHEMA_VERSION = "arc3-p10-batch-checkpoint-v1"
P10_BATCH_CONDITIONS_SCHEMA_VERSION = "arc3-p10-batch-conditions-v1"
P10_BATCH_INDEX_FILENAME = "CHECKPOINT_INDEX.json"

_SAFE_GAME_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


class P10CheckpointMismatch(ValueError):
    """Raised when resume evidence does not match exact run conditions."""


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _encoded(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def environment_inventory_digest(environments_dir: Path) -> str:
    """Bind checkpoint reuse to retained environment code and metadata."""

    environments_dir = environments_dir.resolve()
    rows = [
        {
            "path": path.relative_to(environments_dir).as_posix(),
            "sha256": _file_digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(environments_dir.glob("*/*/*"))
        if path.is_file() and path.suffix in {".json", ".py"}
    ]
    if not rows:
        raise ValueError("P10_ENVIRONMENT_METADATA_INVENTORY_EMPTY")
    return digest_object(rows)


@functools.lru_cache(maxsize=1)
def runtime_source_inventory_digest() -> str:
    """Bind resume to the local P10 runner and package implementation."""

    source_root = Path(__file__).resolve().parents[1]
    paths = [
        source_root / "p10_main.py",
        source_root / "sample_main.py",
        source_root / "agents" / "templates" / "p10_sample_agent.py",
        *sorted((source_root / "arc3_agi_agent").rglob("*.py")),
    ]
    rows = [
        {
            "path": path.relative_to(source_root).as_posix(),
            "sha256": _file_digest(path),
            "bytes": path.stat().st_size,
        }
        for path in paths
        if path.is_file()
    ]
    if len(rows) < 4:
        raise ValueError("P10_RUNTIME_SOURCE_INVENTORY_INCOMPLETE")
    return digest_object(rows)


def _arc_agi_version() -> str:
    try:
        return importlib.metadata.version("arc-agi")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValueError("P10_ARC_AGI_DISTRIBUTION_MISSING") from error


def build_batch_conditions(
    *,
    environments_dir: Path,
    game_ids: Sequence[str],
    max_actions: int,
    instruction_variant: str,
    instruction_lifecycle: str,
    active_manifest_digest: str,
) -> dict[str, Any]:
    """Create the exact condition object used to accept resume checkpoints."""

    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    normalized_game_ids = [str(game_id) for game_id in game_ids]
    if not normalized_game_ids or len(normalized_game_ids) != len(
        set(normalized_game_ids)
    ):
        raise ValueError("P10_BATCH_GAME_IDS_EMPTY_OR_DUPLICATE")
    if any(
        not _SAFE_GAME_ID.fullmatch(game_id)
        for game_id in normalized_game_ids
    ):
        raise ValueError("P10_BATCH_GAME_ID_UNSAFE")
    if instruction_variant not in {"P-A", "P-B", "hybrid"}:
        raise ValueError("P10_BATCH_INSTRUCTION_VARIANT_INVALID")
    if instruction_lifecycle != "active":
        raise ValueError("P10_BATCH_REQUIRES_ACTIVE_LIFECYCLE")
    if not active_manifest_digest:
        raise ValueError("P10_BATCH_ACTIVE_MANIFEST_DIGEST_MISSING")
    body = {
        "schema_version": P10_BATCH_CONDITIONS_SCHEMA_VERSION,
        "operation_mode": "offline",
        "instruction_lifecycle": instruction_lifecycle,
        "instruction_variant": instruction_variant,
        "max_actions": max_actions,
        "game_ids": normalized_game_ids,
        "environment_inventory_digest": environment_inventory_digest(
            environments_dir
        ),
        "runtime_source_inventory_digest": (
            runtime_source_inventory_digest()
        ),
        "python_version": platform.python_version(),
        "arc_agi_version": _arc_agi_version(),
        "active_manifest_digest": active_manifest_digest,
    }
    return {
        **body,
        "conditions_digest": digest_object(body),
    }


def checkpoint_path(checkpoint_dir: Path, game_id: str) -> Path:
    """Return a non-traversing checkpoint path for one environment."""

    if not _SAFE_GAME_ID.fullmatch(game_id):
        raise ValueError(f"P10_CHECKPOINT_GAME_ID_UNSAFE:{game_id}")
    return checkpoint_dir / f"{game_id}.checkpoint.json"


def _single_report(
    result: Mapping[str, Any],
    *,
    game_id: str,
) -> Mapping[str, Any]:
    if str(result.get("operation_mode", "")).casefold() != "offline":
        raise ValueError("P10_CHECKPOINT_REPORT_NOT_OFFLINE")
    if int(result.get("environment_count", 0)) != 1:
        raise ValueError("P10_CHECKPOINT_REPORT_NOT_SINGLE_ENVIRONMENT")
    reports = result.get("reports")
    errors = result.get("errors")
    if not isinstance(reports, Sequence) or isinstance(
        reports,
        (str, bytes, bytearray),
    ):
        raise TypeError("P10 checkpoint reports must be an array")
    if not isinstance(errors, Sequence) or isinstance(
        errors,
        (str, bytes, bytearray),
    ):
        raise TypeError("P10 checkpoint errors must be an array")
    represented = {
        str(row.get("game_id", ""))
        for row in [*reports, *errors]
        if isinstance(row, Mapping)
    }
    if represented != {game_id}:
        raise ValueError(
            f"P10_CHECKPOINT_GAME_REPRESENTATION_INVALID:{game_id}"
        )
    if len(reports) + len(errors) != 1:
        raise ValueError(
            f"P10_CHECKPOINT_RESULT_CARDINALITY_INVALID:{game_id}"
        )
    if int(result.get("completed_count", -1)) != len(reports):
        raise ValueError(
            f"P10_CHECKPOINT_COMPLETED_COUNT_INVALID:{game_id}"
        )
    if int(result.get("error_count", -1)) != len(errors):
        raise ValueError(
            f"P10_CHECKPOINT_ERROR_COUNT_INVALID:{game_id}"
        )
    if reports:
        report = reports[0]
        if not isinstance(report, Mapping):
            raise TypeError("P10 checkpoint game report must be an object")
        return report
    error = errors[0]
    if not isinstance(error, Mapping):
        raise TypeError("P10 checkpoint error must be an object")
    return error


def _verified_conditions_digest(
    conditions: Mapping[str, Any],
) -> str:
    body = dict(conditions)
    claimed = str(body.pop("conditions_digest", ""))
    if not claimed or claimed != digest_object(body):
        raise P10CheckpointMismatch(
            "P10_CHECKPOINT_CONDITIONS_DIGEST_INVALID"
        )
    return claimed


def _validate_result_conditions(
    *,
    result: Mapping[str, Any],
    conditions: Mapping[str, Any],
    game_id: str,
) -> None:
    _single_report(result, game_id=game_id)
    expected = {
        "max_actions": conditions.get("max_actions"),
        "instruction_variant": conditions.get("instruction_variant"),
        "instruction_lifecycle": conditions.get("instruction_lifecycle"),
    }
    actual = {
        "max_actions": result.get("max_actions"),
        "instruction_variant": result.get("instruction_variant"),
        "instruction_lifecycle": result.get("instruction_lifecycle"),
    }
    if actual != expected:
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_REPORT_CONDITIONS_MISMATCH:{game_id}"
        )


def write_game_checkpoint(
    *,
    checkpoint_dir: Path,
    conditions: Mapping[str, Any],
    game_id: str,
    result: Mapping[str, Any],
) -> Path:
    """Atomically persist one complete single-game runner result."""

    conditions_digest = _verified_conditions_digest(conditions)
    _validate_result_conditions(
        result=result,
        conditions=conditions,
        game_id=game_id,
    )
    stable_digest = digest_object(stable_p10_run(result))
    body = {
        "schema_version": P10_BATCH_CHECKPOINT_SCHEMA_VERSION,
        "conditions_digest": conditions_digest,
        "game_id": game_id,
        "stable_report_digest": stable_digest,
        "single_game_report": copy.deepcopy(dict(result)),
    }
    checkpoint = {
        **body,
        "content_digest": digest_object(body),
    }
    path = checkpoint_path(checkpoint_dir, game_id)
    _atomic_write(path, checkpoint)
    return path


def load_game_checkpoint(
    *,
    checkpoint_dir: Path,
    conditions: Mapping[str, Any],
    game_id: str,
) -> dict[str, Any] | None:
    """Load one checkpoint, rejecting any condition or content drift."""

    conditions_digest = _verified_conditions_digest(conditions)
    path = checkpoint_path(checkpoint_dir, game_id)
    if not path.exists():
        return None
    checkpoint = _json_object(path)
    if (
        checkpoint.get("schema_version")
        != P10_BATCH_CHECKPOINT_SCHEMA_VERSION
    ):
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_SCHEMA_MISMATCH:{game_id}"
        )
    if checkpoint.get("conditions_digest") != conditions_digest:
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_CONDITIONS_MISMATCH:{game_id}"
        )
    if checkpoint.get("game_id") != game_id:
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_GAME_ID_MISMATCH:{game_id}"
        )
    body = dict(checkpoint)
    claimed_digest = str(body.pop("content_digest", ""))
    if claimed_digest != digest_object(body):
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_CONTENT_DIGEST_MISMATCH:{game_id}"
        )
    result = checkpoint.get("single_game_report")
    if not isinstance(result, Mapping):
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_REPORT_MISSING:{game_id}"
        )
    _validate_result_conditions(
        result=result,
        conditions=conditions,
        game_id=game_id,
    )
    if checkpoint.get("stable_report_digest") != digest_object(
        stable_p10_run(result)
    ):
        raise P10CheckpointMismatch(
            f"P10_CHECKPOINT_STABLE_REPORT_DRIFT:{game_id}"
        )
    return checkpoint


def _normalized_scorecard_environment(
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    output = copy.deepcopy(dict(environment))
    raw_runs = output.get("runs", [])
    if not isinstance(raw_runs, list):
        raise TypeError("scorecard environment runs must be an array")
    runs: list[dict[str, Any]] = []
    for raw in raw_runs:
        if not isinstance(raw, Mapping):
            raise TypeError("scorecard run must be an object")
        run = copy.deepcopy(dict(raw))
        run["guid"] = (
            "checkpoint-run:"
            + digest_object(
                {
                    "environment_id": output.get("id"),
                    "levels_completed": run.get("levels_completed"),
                    "level_actions": run.get("level_actions"),
                    "state": run.get("state"),
                }
            )[:24]
        )
        runs.append(run)
    output["runs"] = runs
    return output


def _aggregate_scorecard(
    *,
    game_ids: Sequence[str],
    results: Mapping[str, Mapping[str, Any]],
    conditions_digest: str,
) -> dict[str, Any]:
    environments: list[dict[str, Any]] = []
    for game_id in game_ids:
        scorecard = results[game_id].get("local_scorecard")
        if not isinstance(scorecard, Mapping):
            raise ValueError(
                f"P10_CHECKPOINT_SCORECARD_MISSING:{game_id}"
            )
        raw_environments = scorecard.get("environments")
        if not isinstance(raw_environments, Sequence) or isinstance(
            raw_environments,
            (str, bytes, bytearray),
        ):
            raise TypeError("scorecard environments must be an array")
        matching = [
            environment
            for environment in raw_environments
            if isinstance(environment, Mapping)
            and str(environment.get("id", "")) == game_id
        ]
        if len(matching) != 1:
            raise ValueError(
                f"P10_CHECKPOINT_SCORECARD_ENVIRONMENT_INVALID:{game_id}"
            )
        environments.append(_normalized_scorecard_environment(matching[0]))
    scores = [
        float(environment.get("score", 0.0))
        for environment in environments
    ]
    return {
        "api_key": None,
        "card_id": f"checkpoint-aggregate:{conditions_digest[:24]}",
        "competition_mode": None,
        "environments": environments,
        "opaque": None,
        "score": sum(scores) / len(scores) if scores else 0.0,
        "source_url": None,
        "tags": ["p10", "offline-sample", "checkpoint-aggregate"],
        "tags_scores": [],
        "total_actions": sum(
            int(environment.get("actions", 0))
            for environment in environments
        ),
        "total_environments": len(environments),
        "total_environments_completed": sum(
            bool(environment.get("completed", False))
            for environment in environments
        ),
        "total_levels": sum(
            int(environment.get("level_count", 0))
            for environment in environments
        ),
        "total_levels_completed": sum(
            int(environment.get("levels_completed", 0))
            for environment in environments
        ),
    }


def assemble_checkpointed_report(
    *,
    checkpoint_dir: Path,
    conditions: Mapping[str, Any],
    reused_game_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble an oracle-compatible deterministic report in game order."""

    raw_game_ids = conditions.get("game_ids")
    if not isinstance(raw_game_ids, Sequence) or isinstance(
        raw_game_ids,
        (str, bytes, bytearray),
    ):
        raise TypeError("P10 batch conditions game_ids must be an array")
    game_ids = [str(game_id) for game_id in raw_game_ids]
    checkpoints: dict[str, dict[str, Any]] = {}
    results: dict[str, Mapping[str, Any]] = {}
    for game_id in game_ids:
        checkpoint = load_game_checkpoint(
            checkpoint_dir=checkpoint_dir,
            conditions=conditions,
            game_id=game_id,
        )
        if checkpoint is None:
            raise FileNotFoundError(
                checkpoint_path(checkpoint_dir, game_id)
            )
        result = checkpoint["single_game_report"]
        if not isinstance(result, Mapping):
            raise TypeError("single_game_report must be an object")
        checkpoints[game_id] = checkpoint
        results[game_id] = result

    reports: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for game_id in game_ids:
        result = results[game_id]
        raw_reports = result.get("reports", [])
        raw_errors = result.get("errors", [])
        if not isinstance(raw_reports, Sequence) or not isinstance(
            raw_errors,
            Sequence,
        ):
            raise TypeError("checkpoint report collections invalid")
        reports.extend(
            copy.deepcopy(dict(report))
            for report in raw_reports
            if isinstance(report, Mapping)
        )
        errors.extend(
            copy.deepcopy(dict(error))
            for error in raw_errors
            if isinstance(error, Mapping)
        )
    completed_levels = sum(
        int(report.get("levels_completed", 0)) for report in reports
    )
    total_levels = sum(
        int(report.get("win_levels", 0)) for report in reports
    )
    complete_games = sum(bool(report.get("complete")) for report in reports)
    conditions_digest = str(conditions["conditions_digest"])
    scorecard = _aggregate_scorecard(
        game_ids=game_ids,
        results=results,
        conditions_digest=conditions_digest,
    )
    reused = set(reused_game_ids)
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": len(game_ids),
        "completed_count": len(reports),
        "complete_game_count": complete_games,
        "completed_levels": completed_levels,
        "total_levels": total_levels,
        "all_complete": (
            not errors
            and len(reports) == len(game_ids)
            and complete_games == len(game_ids)
        ),
        "error_count": len(errors),
        "max_actions": int(conditions["max_actions"]),
        "instruction_variant": str(conditions["instruction_variant"]),
        "instruction_lifecycle": str(
            conditions["instruction_lifecycle"]
        ),
        "reports": reports,
        "errors": errors,
        "local_scorecard": scorecard,
        "checkpointing": {
            "schema_version": P10_BATCH_CHECKPOINT_SCHEMA_VERSION,
            "conditions": copy.deepcopy(dict(conditions)),
            "checkpoint_storage": "operator-local",
            "reused_game_count": len(reused),
            "executed_game_count": len(game_ids) - len(reused),
            "game_checkpoints": [
                {
                    "game_id": game_id,
                    "stable_report_digest": checkpoints[game_id][
                        "stable_report_digest"
                    ],
                    "reused": game_id in reused,
                }
                for game_id in game_ids
            ],
        },
    }


def write_checkpoint_index(
    *,
    checkpoint_dir: Path,
    conditions: Mapping[str, Any],
    completed_game_ids: Sequence[str],
    reused_game_ids: Sequence[str],
) -> Path:
    """Write a deterministic progress index after each finished game."""

    body = {
        "schema_version": P10_BATCH_CHECKPOINT_SCHEMA_VERSION,
        "conditions": copy.deepcopy(dict(conditions)),
        "completed_game_ids": list(completed_game_ids),
        "reused_game_ids": list(reused_game_ids),
        "remaining_game_ids": [
            game_id
            for game_id in conditions["game_ids"]
            if game_id not in set(completed_game_ids)
        ],
    }
    value = {**body, "content_digest": digest_object(body)}
    path = checkpoint_dir / P10_BATCH_INDEX_FILENAME
    _atomic_write(path, value)
    return path


__all__ = [
    "P10_BATCH_CHECKPOINT_SCHEMA_VERSION",
    "P10_BATCH_CONDITIONS_SCHEMA_VERSION",
    "P10_BATCH_INDEX_FILENAME",
    "P10CheckpointMismatch",
    "assemble_checkpointed_report",
    "build_batch_conditions",
    "checkpoint_path",
    "environment_inventory_digest",
    "load_game_checkpoint",
    "runtime_source_inventory_digest",
    "write_checkpoint_index",
    "write_game_checkpoint",
]
