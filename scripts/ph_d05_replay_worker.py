#!/usr/bin/env python3
"""Isolated PH-D05 OFFLINE replay and canonical observation capture worker."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import struct
import sys
import tempfile
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPLAY_WORKER_VERSION = "hds-arc3-ph-d05-replay-worker-v1"
CAPTURE_VERSION = "hds-arc3-ph-d05-replay-capture-v1"
EXPECTED_ENVIRONMENT_DIGEST = (
    "hds-environment-manifest:"
    "1d116488cd85ee5ad9d641aeb2af66187572b181cb03d819fac1cdba3252cfe0"
)
EXPECTED_SOURCE_MANIFEST_DIGEST = (
    "hds-source-content-manifest:"
    "2c97915953dda659ab039def7c9de33223db2ea78acf7de3e7ee70b51d9d6e79"
)
EXPECTED_SOURCE_MERKLE = (
    "hds-directory-merkle-v1:"
    "1b574ca53167e25e3cea5ce562ecba1eb8bc1830e232a1e2e28877b91879dfeb"
)
EXPECTED_CORPUS_DIGEST = (
    "arc3_full_solution_corpus:"
    "995bbdb3e8323824bdd8ac4a5c3b8f7b64dfffcd2e2618ec87733fc75c1067ce"
)
SECRET_MARKERS = (
    "API_KEY",
    "AUTH_TOKEN",
    "BEARER",
    "COOKIE",
    "CREDENTIAL",
    "KAGGLE",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)


class ReplayWorkerError(RuntimeError):
    """Stable PH-D05 replay-worker failure."""


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


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value).rstrip(b"\n")).hexdigest()


def _deterministic_gzip(payload: bytes) -> bytes:
    compressor = zlib.compressobj(
        level=6,
        method=zlib.DEFLATED,
        wbits=-zlib.MAX_WBITS,
        memLevel=8,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    compressed = compressor.compress(payload) + compressor.flush()
    header = bytes.fromhex("1f8b08000000000000ff")
    trailer = struct.pack(
        "<II",
        zlib.crc32(payload) & 0xFFFFFFFF,
        len(payload) & 0xFFFFFFFF,
    )
    return header + compressed + trailer


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=".ph-d05-replay-",
        suffix=".tmp",
        dir=path.parent,
    )
    temp = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReplayWorkerError(f"PH_D05_JSON_OBJECT_REQUIRED:{path}")
    return value


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _install_audit_boundary(write_root: Path) -> None:
    write_root = write_root.resolve()
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

    def require_write_path(value: object, event: str) -> None:
        if isinstance(value, int):
            return
        try:
            path = Path(os.fspath(value)).resolve()
        except (TypeError, ValueError, OSError) as error:
            raise ReplayWorkerError(f"PH_D05_WRITE_PATH_INVALID:{event}") from error
        if not _inside(path, write_root):
            raise ReplayWorkerError(f"PH_D05_WRITE_BOUNDARY_VIOLATION:{event}:{path}")

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event.startswith("socket.") or event in {
            "http.client.connect",
            "urllib.Request",
        }:
            raise ReplayWorkerError(f"PH_D05_NETWORK_DENIED:{event}")
        if event == "open" and len(args) >= 3:
            mode = args[1]
            flags = args[2]
            writes = (
                isinstance(mode, str)
                and any(marker in mode for marker in ("w", "a", "x", "+"))
            ) or (isinstance(flags, int) and bool(flags & write_flags))
            if writes:
                require_write_path(args[0], event)
        elif (
            event
            in {
                "os.mkdir",
                "os.remove",
                "os.rename",
                "os.rmdir",
                "os.truncate",
            }
            and args
        ):
            require_write_path(args[0], event)
            if event == "os.rename" and len(args) > 1:
                require_write_path(args[1], event)

    sys.addaudithook(audit)


def _verify_no_secrets() -> None:
    present = sorted(
        name
        for name in os.environ
        if any(marker in name.upper() for marker in SECRET_MARKERS)
    )
    if present:
        raise ReplayWorkerError(
            "PH_D05_SECRET_ENVIRONMENT_PRESENT:" + ",".join(present)
        )


def _verify_source_snapshot(
    repository_root: Path,
    source_manifest: Mapping[str, Any],
) -> str:
    if source_manifest.get("content_digest") != EXPECTED_SOURCE_MANIFEST_DIGEST:
        raise ReplayWorkerError("PH_D05_SOURCE_MANIFEST_DIGEST_MISMATCH")
    files = source_manifest.get("files")
    if not isinstance(files, list) or len(files) != 50:
        raise ReplayWorkerError("PH_D05_SOURCE_FILE_INVENTORY_INVALID")
    for index, item in enumerate(files):
        if not isinstance(item, Mapping):
            raise ReplayWorkerError(f"PH_D05_SOURCE_FILE_INVALID:{index}")
        relative = item.get("repository_relative_posix_path")
        if not isinstance(relative, str) or not relative:
            raise ReplayWorkerError(f"PH_D05_SOURCE_PATH_INVALID:{index}")
        path = repository_root / relative
        payload = path.read_bytes()
        if len(payload) != item.get("size_bytes"):
            raise ReplayWorkerError(f"PH_D05_SOURCE_SIZE_MISMATCH:{relative}")
        if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
            raise ReplayWorkerError(f"PH_D05_SOURCE_SHA_MISMATCH:{relative}")

    distillation_src = repository_root / "distillation" / "src"
    sys.path.insert(0, str(distillation_src))
    from hds_distill.manifest_freeze import directory_merkle_root

    root = directory_merkle_root(files)
    if root != EXPECTED_SOURCE_MERKLE:
        raise ReplayWorkerError("PH_D05_SOURCE_MERKLE_MISMATCH")
    return root


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplayWorkerError(f"PH_D05_INTEGER_REQUIRED:{field}")
    return value


def _frame_values(frame: Any) -> list[Any]:
    return [
        value.tolist() if hasattr(value, "tolist") else value for value in frame.frame
    ]


def _frame_state(frame: Any) -> str:
    return str(getattr(frame.state, "value", frame.state)).upper()


def _available_actions(frame: Any) -> list[int]:
    return [
        _integer(getattr(item, "value", item), "available_actions[]")
        for item in frame.available_actions
    ]


def _observation(frame: Any, digest_object: Any) -> dict[str, Any]:
    values = _frame_values(frame)
    return {
        "frame": values,
        "frame_digest": "sha256:" + digest_object(values),
        "available_actions": _available_actions(frame),
        "terminal_state": _frame_state(frame),
        "levels_completed": _integer(
            frame.levels_completed,
            "levels_completed",
        ),
    }


def _action_payload(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ReplayWorkerError("PH_D05_ACTION_PAYLOAD_INVALID")
    payload: dict[str, int] = {}
    for key in ("x", "y"):
        if key in value:
            payload[key] = _integer(value[key], "action_data." + key)
    return payload


def _replay_one(
    *,
    arcade: Any,
    game_solution: Mapping[str, Any],
    output_dir: Path,
    run_index: int,
    digest_object: Any,
    frame_type: type[Any],
    game_action_type: Any,
    local_wrapper_type: type[Any],
) -> dict[str, Any]:
    game_id = str(game_solution.get("game_id", ""))
    target_levels = _integer(game_solution.get("target_levels"), "target_levels")
    actions = game_solution.get("actions")
    if not isinstance(actions, Sequence) or isinstance(
        actions, str | bytes | bytearray
    ):
        raise ReplayWorkerError(f"PH_D05_ACTIONS_INVALID:{game_id}")
    card_id = arcade.open_scorecard(tags=["ph-d05", "replay-only", f"run-{run_index}"])
    try:
        environment = arcade.make(
            game_id,
            scorecard_id=card_id,
            save_recording=False,
            include_frame_data=True,
        )
        if not isinstance(environment, local_wrapper_type):
            raise ReplayWorkerError(f"PH_D05_LOCAL_WRAPPER_REQUIRED:{game_id}")
        initial_frame = environment.observation_space
        if not isinstance(initial_frame, frame_type):
            raise ReplayWorkerError(f"PH_D05_INITIAL_FRAME_MISSING:{game_id}")
        initial = _observation(initial_frame, digest_object)
        expected_initial = game_solution.get("initial_observation")
        if not isinstance(expected_initial, Mapping):
            raise ReplayWorkerError(f"PH_D05_INITIAL_EXPECTATION_INVALID:{game_id}")
        expected_available = expected_initial.get("available_actions")
        available_known = isinstance(expected_available, list) and bool(
            expected_available
        )
        if (
            initial["terminal_state"] != str(expected_initial.get("state", "")).upper()
            or initial["levels_completed"] != expected_initial.get("levels_completed")
            or (available_known and initial["available_actions"] != expected_available)
        ):
            raise ReplayWorkerError(f"PH_D05_INITIAL_OBSERVATION_DIVERGED:{game_id}")

        capture_steps: list[dict[str, Any]] = []
        actual_trace: list[dict[str, Any]] = []
        source_frame_difference_count = 0
        previous = initial_frame
        for raw_step in actions:
            if not isinstance(raw_step, Mapping):
                raise ReplayWorkerError(f"PH_D05_STEP_INVALID:{game_id}")
            step = _integer(raw_step.get("step"), "step")
            action_id = _integer(raw_step.get("action_id"), "action_id")
            payload = _action_payload(raw_step.get("action_data"))
            before_available = _available_actions(previous)
            if action_id != 0 and action_id not in before_available:
                raise ReplayWorkerError(
                    f"PH_D05_ACTION_UNAVAILABLE:{game_id}:{step}:{action_id}"
                )
            compatibility_reset = (
                action_id == 0 and raw_step.get("full_reset") is not True
            )
            prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
            if compatibility_reset:
                os.environ["ONLY_RESET_LEVELS"] = "true"
            try:
                frame = environment.step(
                    game_action_type.from_id(action_id),
                    data=payload,
                    reasoning={
                        "authority": "REPLAY_HARNESS_MAINTAINER",
                        "phase_id": "PH-D05",
                        "runtime_use": "FORBIDDEN",
                    },
                )
            finally:
                if compatibility_reset:
                    if prior_reset_scope is None:
                        os.environ.pop("ONLY_RESET_LEVELS", None)
                    else:
                        os.environ["ONLY_RESET_LEVELS"] = prior_reset_scope
            if not isinstance(frame, frame_type):
                raise ReplayWorkerError(f"PH_D05_STEP_FAILED:{game_id}:{step}")
            after = _observation(frame, digest_object)
            expected_state = str(raw_step.get("expected_state", "")).upper()
            expected_levels = _integer(
                raw_step.get("expected_levels_completed"),
                "expected_levels_completed",
            )
            expected_available = raw_step.get("expected_available_actions")
            if (
                after["terminal_state"] != expected_state
                or after["levels_completed"] != expected_levels
                or after["available_actions"] != expected_available
            ):
                raise ReplayWorkerError(f"PH_D05_TRANSITION_DIVERGED:{game_id}:{step}")
            source_frame_match = after["frame_digest"] == raw_step.get(
                "expected_frame_digest"
            )
            if not source_frame_match:
                source_frame_difference_count += 1
            reset_scope = (
                "LEVEL_COMPATIBILITY" if compatibility_reset else "RECORDED_ACTION"
            )
            actual_trace.append(
                {
                    "step": step,
                    "action_id": action_id,
                    "action_data": payload,
                    "state": after["terminal_state"],
                    "levels_completed": after["levels_completed"],
                    "frame_digest": after["frame_digest"],
                    "reset_scope": reset_scope,
                }
            )
            capture_steps.append(
                {
                    "step": step,
                    "action_id": action_id,
                    "action_data": payload,
                    "reset_scope": reset_scope,
                    "after": after,
                    "source_frame_match": source_frame_match,
                    "source_frame_digest": raw_step.get("expected_frame_digest"),
                }
            )
            previous = frame

        if (
            _frame_state(previous) != "WIN"
            or _integer(previous.levels_completed, "final_levels") != target_levels
        ):
            raise ReplayWorkerError(f"PH_D05_FINAL_CLOSURE_FAILED:{game_id}")
        capture_core: dict[str, Any] = {
            "schema_version": CAPTURE_VERSION,
            "phase_id": "PH-D05",
            "game_id": game_id,
            "target_levels": target_levels,
            "source_solution_digest": game_solution.get("content_digest"),
            "initial": initial,
            "steps": capture_steps,
            "actual_trace_digest": digest_object(actual_trace),
            "source_frame_difference_count": source_frame_difference_count,
            "terminal_state": "WIN",
        }
        capture_core["content_digest"] = "hds-arc3-replay-capture:" + _digest(
            capture_core
        )
        payload = _canonical_bytes(capture_core)
        compressed = _deterministic_gzip(payload)
        capture_path = output_dir / "captures" / f"{game_id}.json.gz"
        _atomic_write(capture_path, compressed)
        return {
            "game_id": game_id,
            "target_levels": target_levels,
            "action_count": len(capture_steps),
            "actual_trace_digest": capture_core["actual_trace_digest"],
            "capture_content_digest": capture_core["content_digest"],
            "capture_sha256": hashlib.sha256(compressed).hexdigest(),
            "capture_size_bytes": len(compressed),
            "source_frame_difference_count": source_frame_difference_count,
        }
    finally:
        arcade.close_scorecard(card_id)
        gc.collect()


def run(
    *,
    repository_root: Path,
    output_dir: Path,
    run_index: int,
    requested_games: Sequence[str] = (),
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output_dir = output_dir.resolve()
    if _inside(output_dir, repository_root):
        raise ReplayWorkerError("PH_D05_REPLAY_OUTPUT_INSIDE_REPOSITORY")
    output_dir.mkdir(parents=True, exist_ok=True)
    _verify_no_secrets()
    _install_audit_boundary(output_dir)
    random.seed(0)

    source_manifest = _object(
        repository_root
        / "distillation/manifests/source_content/arc3-environment-source-bundle.json"
    )
    source_before = _verify_source_snapshot(repository_root, source_manifest)
    environment_manifest = _object(
        repository_root / "distillation/manifests/environment/arc3-replay.json"
    )
    if environment_manifest.get("content_digest") != EXPECTED_ENVIRONMENT_DIGEST:
        raise ReplayWorkerError("PH_D05_ENVIRONMENT_DIGEST_MISMATCH")
    corpus = _object(repository_root / "analysis/teacher/FULL_SOLUTION_CORPUS.json")
    if corpus.get("content_digest") != EXPECTED_CORPUS_DIGEST:
        raise ReplayWorkerError("PH_D05_CORPUS_DIGEST_MISMATCH")
    games = corpus.get("games")
    if not isinstance(games, list) or len(games) != 25:
        raise ReplayWorkerError("PH_D05_CORPUS_GAME_COUNT_INVALID")
    requested = tuple(dict.fromkeys(requested_games))
    known = {str(game.get("game_id")) for game in games if isinstance(game, Mapping)}
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ReplayWorkerError("PH_D05_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown))
    selected_games = [
        game
        for game in games
        if isinstance(game, Mapping)
        and (not requested or str(game.get("game_id")) in set(requested))
    ]

    agents_root = repository_root / "ARC-AGI-3-Agents"
    sys.path.insert(0, str(agents_root))
    from arc3_agi_agent.schema import digest_object
    from arc_agi import Arcade, OperationMode
    from arc_agi.local_wrapper import LocalEnvironmentWrapper
    from arcengine import FrameDataRaw, GameAction

    try:
        import numpy as np

        np.random.seed(0)
    except ImportError:
        pass
    runtime_dir = output_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(repository_root / "environment_files"),
        recordings_dir=str(runtime_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise ReplayWorkerError("PH_D05_OFFLINE_MODE_NOT_EFFECTIVE")

    reports: list[dict[str, Any]] = []
    for game in sorted(
        selected_games,
        key=lambda item: str(item.get("game_id", "")),
    ):
        if not isinstance(game, Mapping):
            raise ReplayWorkerError("PH_D05_CORPUS_GAME_INVALID")
        reports.append(
            _replay_one(
                arcade=arcade,
                game_solution=game,
                output_dir=output_dir,
                run_index=run_index,
                digest_object=digest_object,
                frame_type=FrameDataRaw,
                game_action_type=GameAction,
                local_wrapper_type=LocalEnvironmentWrapper,
            )
        )
    source_after = _verify_source_snapshot(repository_root, source_manifest)
    if source_before != source_after:
        raise ReplayWorkerError("PH_D05_SOURCE_MUTATED_DURING_REPLAY")
    body: dict[str, Any] = {
        "schema_version": REPLAY_WORKER_VERSION,
        "phase_id": "PH-D05",
        "authority": "REPLAY_HARNESS_MAINTAINER",
        "run_index": run_index,
        "operation_mode": "OFFLINE",
        "seed": 0,
        "network_denied": True,
        "secret_environment_count": 0,
        "write_boundary": "EXTERNAL_RUN_OUTPUT_ONLY",
        "source_snapshot_before": source_before,
        "source_snapshot_after": source_after,
        "source_write_count": 0,
        "source_mutation_count": 0,
        "environment_manifest_digest": EXPECTED_ENVIRONMENT_DIGEST,
        "source_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
        "source_corpus_digest": EXPECTED_CORPUS_DIGEST,
        "complete_inventory": not requested,
        "game_count": len(reports),
        "level_count": sum(item["target_levels"] for item in reports),
        "action_count": sum(item["action_count"] for item in reports),
        "source_frame_difference_count": sum(
            item["source_frame_difference_count"] for item in reports
        ),
        "replay_error_count": 0,
        "reports": reports,
    }
    body["content_digest"] = "hds-arc3-replay-worker:" + _digest(body)
    _atomic_write(output_dir / "worker_report.json", _canonical_bytes(body))
    return body


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-index", type=int, required=True, choices=(1, 2, 3))
    parser.add_argument("--game", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = run(
            repository_root=args.repository_root,
            output_dir=args.output_dir,
            run_index=args.run_index,
            requested_games=tuple(args.game),
        )
    except Exception as error:
        print(
            f"PH_D05_REPLAY_WORKER_FAIL:{type(error).__name__}:{error}",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "action_count": report["action_count"],
                "content_digest": report["content_digest"],
                "game_count": report["game_count"],
                "level_count": report["level_count"],
                "run_index": report["run_index"],
                "source_frame_difference_count": report[
                    "source_frame_difference_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
