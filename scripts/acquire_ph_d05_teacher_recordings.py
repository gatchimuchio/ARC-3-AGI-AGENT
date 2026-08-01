#!/usr/bin/env python3
"""Acquire the exact PH-D05 ARC3 teacher recordings into an external cache.

The repository stores only immutable source manifests and deterministic
verification evidence.  Raw recording payloads remain outside the repository.
Every accepted byte string must match both the pinned selection and the
PH-D01B SourceContentManifest before an atomic cache write is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"
REPORT_SCHEMA_VERSION = "hds-arc3-teacher-recording-acquisition-v1"
REPORT_DIGEST_NAMESPACE = "hds-arc3-teacher-recording-acquisition"
EXPECTED_DATASET_ID = "magic-sword/arc_agi_3_public_demo_human_testing"
EXPECTED_DATASET_REVISION = "455b7c58eaa9d5ea05f91cd1b5b603121599e758"


class AcquisitionError(RuntimeError):
    """A stable fail-closed acquisition or content-verification error."""


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcquisitionError(f"PH_D05_JSON_OBJECT_REQUIRED:{path}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _content_digest(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("content_digest", None)
    payload = json.dumps(
        body,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return REPORT_DIGEST_NAMESPACE + ":" + hashlib.sha256(payload).hexdigest()


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AcquisitionError(f"PH_D05_INTEGER_REQUIRED:{field}")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AcquisitionError(f"PH_D05_STRING_REQUIRED:{field}")
    return value


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise AcquisitionError(f"PH_D05_ARRAY_REQUIRED:{field}")
    return value


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _source_files_by_name(
    source_manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if source_manifest.get("content_digest") != (
        "hds-source-content-manifest:"
        "3098feb7241e4ea3444b5942ab8ba0371d8168a51f32a1f3d44c0e09db36eda9"
    ):
        raise AcquisitionError("PH_D05_SOURCE_MANIFEST_DIGEST_MISMATCH")
    raw_files = source_manifest.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != 25:
        raise AcquisitionError("PH_D05_SOURCE_MANIFEST_FILE_COUNT_INVALID")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw_files):
        if not isinstance(item, dict):
            raise AcquisitionError(
                f"PH_D05_SOURCE_MANIFEST_FILE_INVALID:{index}"
            )
        relative = _string(
            item.get("repository_relative_posix_path"),
            f"files[{index}].repository_relative_posix_path",
        )
        name = Path(relative).name
        if name in result or not name.endswith(".recording"):
            raise AcquisitionError(
                f"PH_D05_SOURCE_MANIFEST_FILENAME_INVALID:{name}"
            )
        result[name] = item
    return result


def _validate_selection(
    selection: Mapping[str, Any],
    source_files: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if (
        selection.get("dataset_id") != EXPECTED_DATASET_ID
        or selection.get("dataset_repo_sha") != EXPECTED_DATASET_REVISION
        or selection.get("config") != "default"
        or selection.get("split") != "train"
    ):
        raise AcquisitionError("PH_D05_SELECTION_DATASET_BINDING_INVALID")
    raw_rows = selection.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != 25:
        raise AcquisitionError("PH_D05_SELECTION_ROW_COUNT_INVALID")
    trajectory_digests = selection.get("pinned_trajectory_sha256_by_game")
    if not isinstance(trajectory_digests, dict):
        raise AcquisitionError("PH_D05_SELECTION_DIGEST_MAP_INVALID")
    rows: list[dict[str, Any]] = []
    seen_games: set[str] = set()
    seen_files: set[str] = set()
    level_count = 0
    action_count = 0
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise AcquisitionError(f"PH_D05_SELECTION_ROW_INVALID:{index}")
        game_id = _string(row.get("game_id"), f"rows[{index}].game_id")
        filename = _string(
            row.get("recording_file"),
            f"rows[{index}].recording_file",
        )
        if game_id in seen_games or filename in seen_files:
            raise AcquisitionError("PH_D05_SELECTION_DUPLICATE")
        seen_games.add(game_id)
        seen_files.add(filename)
        source_file = source_files.get(filename)
        if source_file is None:
            raise AcquisitionError(
                f"PH_D05_SELECTION_FILE_NOT_IN_SOURCE_MANIFEST:{filename}"
            )
        expected_sha = _string(
            source_file.get("sha256"),
            f"source_files[{filename}].sha256",
        )
        if trajectory_digests.get(game_id) != expected_sha:
            raise AcquisitionError(
                f"PH_D05_SELECTION_SHA_MISMATCH:{game_id}"
            )
        level_count += _integer(
            row.get("target_levels"),
            f"rows[{index}].target_levels",
        )
        action_count += _integer(
            row.get("expected_actions"),
            f"rows[{index}].expected_actions",
        )
        rows.append(
            {
                **row,
                "expected_sha256": expected_sha,
                "expected_size_bytes": _integer(
                    source_file.get("size_bytes"),
                    f"source_files[{filename}].size_bytes",
                ),
            }
        )
    if set(source_files) != seen_files:
        raise AcquisitionError("PH_D05_SELECTION_SOURCE_COVERAGE_INVALID")
    if level_count != 183 or action_count != 11648:
        raise AcquisitionError("PH_D05_SELECTION_TOTALS_INVALID")
    rows.sort(key=lambda item: str(item["game_id"]))
    return rows


def _fetch_row(
    *,
    row_index: int,
    timeout_seconds: float,
    retry_count: int,
) -> tuple[dict[str, Any], int]:
    query = urllib.parse.urlencode(
        {
            "dataset": EXPECTED_DATASET_ID,
            "config": "default",
            "split": "train",
            "offset": row_index,
            "length": 1,
        }
    )
    request = urllib.request.Request(
        f"{ROWS_ENDPOINT}?{query}",
        headers={"User-Agent": "ARC-3-AGI-AGENT-PH-D05/1"},
    )
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                payload = response.read()
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise TypeError("response must be an object")
            wrappers = decoded.get("rows")
            if not isinstance(wrappers, list) or len(wrappers) != 1:
                raise ValueError("response must contain one row")
            wrapper = wrappers[0]
            if not isinstance(wrapper, dict) or wrapper.get("row_idx") != row_index:
                raise ValueError("row index mismatch")
            row = wrapper.get("row")
            if not isinstance(row, dict):
                raise TypeError("row must be an object")
            return row, attempt + 1
        except (
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as error:
            last_error = error
            if attempt >= retry_count:
                break
            time.sleep(min(4.0, 0.5 * (2**attempt)))
    raise AcquisitionError(
        f"PH_D05_DATASET_ROW_FETCH_FAILED:{row_index}:{last_error}"
    ) from last_error


def _validate_row_and_payload(
    row: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bytes:
    game_id = str(expected["game_id"])
    if (
        row.get("game_id") != game_id
        or row.get("guid") != expected["recording_file"]
        or row.get("won") != 1
        or list(_sequence(row.get("states"), "states")) != ["WIN"]
        or list(_sequence(row.get("levels_completed"), "levels_completed"))
        != [expected["target_levels"]]
        or list(_sequence(row.get("actions"), "actions"))
        != [expected["expected_actions"]]
    ):
        raise AcquisitionError(f"PH_D05_DATASET_ROW_MISMATCH:{game_id}")
    trajectory = _string(row.get("trajectory"), "trajectory")
    payload = trajectory.encode("utf-8")
    actual_sha = hashlib.sha256(payload).hexdigest()
    if (
        len(payload) != expected["expected_size_bytes"]
        or actual_sha != expected["expected_sha256"]
    ):
        raise AcquisitionError(
            f"PH_D05_RAW_RECORDING_CONTENT_MISMATCH:{game_id}"
        )
    return payload


def _verified_existing(path: Path, expected: Mapping[str, Any]) -> bool:
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return False
    if len(payload) != expected["expected_size_bytes"]:
        raise AcquisitionError(f"PH_D05_CACHE_SIZE_MISMATCH:{path.name}")
    if hashlib.sha256(payload).hexdigest() != expected["expected_sha256"]:
        raise AcquisitionError(f"PH_D05_CACHE_SHA_MISMATCH:{path.name}")
    return True


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=".ph-d05-",
        suffix=".part",
        dir=path.parent,
    )
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def acquire(
    *,
    repository_root: Path,
    selection_path: Path,
    source_manifest_path: Path,
    output_dir: Path,
    report_path: Path,
    timeout_seconds: float,
    retry_count: int,
    verify_only: bool,
) -> tuple[dict[str, Any], int, int]:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if _inside(output_dir, repository_root):
        raise AcquisitionError("PH_D05_RAW_CACHE_INSIDE_REPOSITORY_FORBIDDEN")
    selection = _load_object(selection_path)
    source_manifest = _load_object(source_manifest_path)
    source_files = _source_files_by_name(source_manifest)
    rows = _validate_selection(selection, source_files)
    request_count = 0
    cache_hit_count = 0
    verified: list[dict[str, Any]] = []
    for expected in rows:
        filename = str(expected["recording_file"])
        target = output_dir / filename
        if _verified_existing(target, expected):
            cache_hit_count += 1
        else:
            if verify_only:
                raise AcquisitionError(
                    f"PH_D05_CACHE_FILE_MISSING:{filename}"
                )
            row, attempts = _fetch_row(
                row_index=int(expected["row_index"]),
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
            )
            request_count += attempts
            payload = _validate_row_and_payload(row, expected)
            _atomic_write(target, payload)
            if not _verified_existing(target, expected):
                raise AcquisitionError(
                    f"PH_D05_CACHE_POST_WRITE_VERIFICATION_FAILED:{filename}"
                )
        verified.append(
            {
                "game_id": expected["game_id"],
                "recording_file": filename,
                "row_index": expected["row_index"],
                "target_levels": expected["target_levels"],
                "recorded_action_count": expected["expected_actions"],
                "size_bytes": expected["expected_size_bytes"],
                "sha256": expected["expected_sha256"],
                "status": "VERIFIED",
            }
        )
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "phase_id": "PH-D05",
        "dataset_id": EXPECTED_DATASET_ID,
        "dataset_revision": EXPECTED_DATASET_REVISION,
        "dataset_config": "default",
        "dataset_split": "train",
        "source_content_manifest_digest": source_manifest["content_digest"],
        "cache_location_policy": "EXTERNAL_CONTENT_VERIFIED_DIRECTORY",
        "raw_payload_repository_byte_count": 0,
        "verification_method": "EXACT_SIZE_AND_SHA256",
        "recording_count": len(verified),
        "level_count": sum(int(item["target_levels"]) for item in verified),
        "recorded_action_count": sum(
            int(item["recorded_action_count"]) for item in verified
        ),
        "total_bytes": sum(int(item["size_bytes"]) for item in verified),
        "network_scope": "PINNED_DATASET_VIEWER_ROWS_ONLY",
        "files": verified,
        "status": "ARC3_RAW_TEACHER_RECORDINGS_VERIFIED",
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    report["content_digest"] = _content_digest(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(_canonical_bytes(report))
    return report, request_count, cache_hit_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire exact PH-D05 teacher recordings externally."
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("--source-content-manifest", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--retry-count", type=int, default=2)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = (
        args.repository_root.resolve()
        if args.repository_root is not None
        else Path(__file__).resolve().parents[1]
    )
    selection = args.selection_manifest or (
        root / "analysis/teacher/HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json"
    )
    source_manifest = args.source_content_manifest or (
        root
        / "distillation/manifests/source_content/arc3-raw-teacher-recordings.json"
    )
    try:
        report, requests, hits = acquire(
            repository_root=root,
            selection_path=selection,
            source_manifest_path=source_manifest,
            output_dir=args.output_dir,
            report_path=args.report,
            timeout_seconds=args.timeout_seconds,
            retry_count=args.retry_count,
            verify_only=args.verify_only,
        )
    except (AcquisitionError, OSError, ValueError) as error:
        print(f"PH_D05_ACQUISITION_FAIL:{error}")
        return 2
    print(
        json.dumps(
            {
                "cache_hit_count": hits,
                "content_digest": report["content_digest"],
                "recording_count": report["recording_count"],
                "request_count": requests,
                "status": report["status"],
                "total_bytes": report["total_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
