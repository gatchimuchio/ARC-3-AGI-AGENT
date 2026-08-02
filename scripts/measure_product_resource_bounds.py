#!/usr/bin/env python3
"""Measure product resource bounds from the canonical PH-D05 trajectories."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEACHER_ROOT: Final = Path("distillation/artifacts/teacher/arc3/ph_d05_v1")
TEACHER_MANIFEST_PATH: Final = TEACHER_ROOT / "manifest.json"
OUTPUT_PATH: Final = Path("analysis/product/rev4/product_resource_bounds.json")
PRODUCT_ID: Final = "ARC3CompletionAgent"
EXPECTED_GAME_COUNT: Final = 25
EXPECTED_LEVEL_COUNT: Final = 183
EXPECTED_ACTION_CEILING: Final = 1519
EXPECTED_NO_PROGRESS_CEILING: Final = 644
NO_PROGRESS_SAFETY_MARGIN: Final = 6
RECOMMENDED_NO_PROGRESS_LIMIT: Final = 650


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label}:OBJECT_REQUIRED")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label}:LIST_REQUIRED")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label}:INTEGER_REQUIRED")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{label}:NONEMPTY_STRING_REQUIRED")
    return value


def _load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    return _object(json.loads(payload.decode("utf-8")), label)


def _resolve_package(root: Path, relative: str) -> Path:
    teacher_root = (root / TEACHER_ROOT).resolve()
    package_path = (teacher_root / relative).resolve()
    if package_path.parent != teacher_root / "packages":
        raise ValueError(f"PACKAGE_PATH_OUTSIDE_CANONICAL_DIRECTORY:{relative}")
    return package_path


def build_report(root: Path) -> dict[str, object]:
    manifest_path = root / TEACHER_MANIFEST_PATH
    manifest_bytes = manifest_path.read_bytes()
    manifest = _load_json_bytes(manifest_bytes, "teacher_manifest")
    package_summaries = _list(manifest.get("packages"), "teacher_manifest.packages")

    games: list[dict[str, object]] = []
    for index, raw_summary in enumerate(package_summaries):
        summary = _object(raw_summary, f"teacher_manifest.packages[{index}]")
        game_id = _string(summary.get("game_id"), f"packages[{index}].game_id")
        package_relative = _string(
            summary.get("package_path"),
            f"packages[{index}].package_path",
        )
        expected_package_sha = _string(
            summary.get("package_sha256"),
            f"packages[{index}].package_sha256",
        )
        package_path = _resolve_package(root, package_relative)
        package_bytes = package_path.read_bytes()
        actual_package_sha = hashlib.sha256(package_bytes).hexdigest()
        if actual_package_sha != expected_package_sha:
            raise ValueError(f"PACKAGE_SHA256_MISMATCH:{game_id}")

        package = _load_json_bytes(gzip.decompress(package_bytes), game_id)
        if package.get("game_id") != game_id:
            raise ValueError(f"PACKAGE_GAME_ID_MISMATCH:{game_id}")
        detailed_trajectory = _object(
            package.get("detailed_trajectory"),
            f"{game_id}.detailed_trajectory",
        )
        steps = _list(
            detailed_trajectory.get("steps"),
            f"{game_id}.detailed_trajectory.steps",
        )
        expected_action_count = _integer(
            summary.get("canonical_success_prefix_action_count"),
            f"{game_id}.manifest_success_action_count",
        )
        if len(steps) != expected_action_count:
            raise ValueError(f"SUCCESS_ACTION_COUNT_MISMATCH:{game_id}")

        current_streak = 0
        maximum_streak = 0
        progress_event_count = 0
        for step_index, raw_step in enumerate(steps):
            step = _object(
                raw_step,
                f"{game_id}.detailed_trajectory.steps[{step_index}]",
            )
            if _integer(step.get("step_index"), "step_index") != step_index:
                raise ValueError(f"NONCONTIGUOUS_STEP_INDEX:{game_id}:{step_index}")
            progress_delta = _integer(
                step.get("progress_delta"),
                f"{game_id}.progress_delta[{step_index}]",
            )
            if progress_delta > 0:
                progress_event_count += 1
                current_streak = 0
            else:
                current_streak += 1
                maximum_streak = max(maximum_streak, current_streak)

        games.append(
            {
                "canonical_success_action_count": len(steps),
                "game_id": game_id,
                "level_count": _integer(
                    summary.get("level_count"),
                    f"{game_id}.level_count",
                ),
                "max_consecutive_actions_without_level_progress": maximum_streak,
                "package_sha256": actual_package_sha,
                "progress_event_count": progress_event_count,
                "projected_action_count": _integer(
                    summary.get("ph_d02b_action_projection_count"),
                    f"{game_id}.projected_action_count",
                ),
            }
        )

    games.sort(key=lambda item: str(item["game_id"]))
    game_count = len(games)
    level_count = sum(_integer(item["level_count"], "level_count") for item in games)
    action_ceiling = max(
        _integer(item["canonical_success_action_count"], "success_action_count")
        for item in games
    )
    no_progress_ceiling = max(
        _integer(
            item["max_consecutive_actions_without_level_progress"],
            "no_progress_streak",
        )
        for item in games
    )
    observed = {
        "game_count": game_count,
        "level_count": level_count,
        "known_success_action_ceiling": action_ceiling,
        "known_success_no_progress_ceiling": no_progress_ceiling,
    }
    expected = {
        "game_count": EXPECTED_GAME_COUNT,
        "level_count": EXPECTED_LEVEL_COUNT,
        "known_success_action_ceiling": EXPECTED_ACTION_CEILING,
        "known_success_no_progress_ceiling": EXPECTED_NO_PROGRESS_CEILING,
    }
    if observed != expected:
        raise ValueError(f"RESOURCE_BOUND_DRIFT:{observed!r}")

    body: dict[str, object] = {
        "schema_version": "arc3-product-resource-bounds-v1",
        "product_id": PRODUCT_ID,
        "source_manifest_path": TEACHER_MANIFEST_PATH.as_posix(),
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_manifest_content_digest": manifest.get("content_digest"),
        "measurement_definition": (
            "Maximum consecutive actions in each complete canonical successful "
            "trajectory whose progress_delta is not positive; a positive "
            "level-progress delta resets the streak."
        ),
        **observed,
        "no_progress_safety_margin": NO_PROGRESS_SAFETY_MARGIN,
        "recommended_no_progress_limit": RECOMMENDED_NO_PROGRESS_LIMIT,
        "games": games,
        "digest_excluded_fields": ["content_digest"],
    }
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return {
        **body,
        "content_digest": "arc3-product-resource-bounds:" + digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    output_path = root / OUTPUT_PATH
    if arguments.write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(expected)
        status = "WRITTEN"
        ok = True
    else:
        ok = output_path.is_file() and output_path.read_bytes() == expected
        status = "PASS" if ok else "STALE"
    print(
        json.dumps(
            {
                "game_count": report["game_count"],
                "known_success_no_progress_ceiling": report[
                    "known_success_no_progress_ceiling"
                ],
                "output_path": OUTPUT_PATH.as_posix(),
                "recommended_no_progress_limit": report[
                    "recommended_no_progress_limit"
                ],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
