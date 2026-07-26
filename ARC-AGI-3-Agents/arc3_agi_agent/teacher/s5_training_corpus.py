"""Compile the privileged S4 trajectory into a development-only S5 corpus."""

from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import os
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw

from ..protocol import AuthorityViolation
from ..schema import digest_object
from .s4_graph_executor import execute_s4_global_policy
from .s4_graph_schema import load_s4_policy_graph

S5_TRAINING_CORPUS_SCHEMA_VERSION = (
    "arc3-s5-rendered-policy-training-corpus-v1"
)
S5_TRAINING_CORPUS_DIGEST_PREFIX = "arc3_s5_training_corpus:"


def _npy_bytes(value: np.ndarray) -> bytes:
    output = io.BytesIO()
    np.save(output, value, allow_pickle=False)
    return output.getvalue()


def write_deterministic_npz(
    path: Path,
    arrays: Mapping[str, np.ndarray],
) -> None:
    """Write stable NPY members with fixed ZIP metadata and ordering."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name in sorted(arrays):
            if not name or "/" in name or "\\" in name:
                raise ValueError("S5_NPZ_MEMBER_NAME_INVALID")
            info = zipfile.ZipInfo(
                filename=f"{name}.npy",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                _npy_bytes(np.asarray(arrays[name])),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


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


def _discover_environment_ids(environments_dir: Path) -> list[str]:
    identifiers: list[str] = []
    for metadata_path in sorted(
        environments_dir.glob("*/*/metadata.json")
    ):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise TypeError("S5_CORPUS_METADATA_INVALID")
        identifier = value.get("game_id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("S5_CORPUS_METADATA_ID_INVALID")
        identifiers.append(identifier)
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("S5_CORPUS_ENVIRONMENT_INVENTORY_INVALID")
    return identifiers


def compile_s5_training_corpus(
    *,
    environments_dir: Path,
    s4_policy_graph_path: Path,
    output_npz: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Collect Teacher labels; the output is forbidden at Runtime."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S5_COMPILE")
    environments_dir = environments_dir.resolve()
    graph = load_s4_policy_graph(
        s4_policy_graph_path,
        require_complete=not requested_games,
    )
    discovered = _discover_environment_ids(environments_dir)
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    unknown = sorted(set(requested).difference(discovered))
    if unknown:
        raise ValueError(
            "S5_CORPUS_REQUESTED_ENVIRONMENT_UNKNOWN:"
            + ",".join(unknown)
        )
    selected = sorted(requested) if requested else sorted(discovered)
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
    frames: list[np.ndarray] = []
    actions: list[int] = []
    targets: list[tuple[int, int]] = []
    available: list[np.ndarray] = []
    game_ordinals: list[int] = []
    levels_completed: list[int] = []
    compatibility_resets: list[int] = []
    environment_action_counts: list[int] = []
    environment_level_counts: list[int] = []

    for game_ordinal, evaluation_identifier in enumerate(selected):
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r5", "s5-training-corpus", "development-only"]
        )
        before_count = len(actions)
        try:
            environment = arcade.make(
                evaluation_identifier,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise RuntimeError("S5_CORPUS_ENVIRONMENT_LOAD_FAILED")

            def collect(
                before: FrameDataRaw,
                action: Mapping[str, Any],
                payload: Mapping[str, int],
            ) -> None:
                frame = np.asarray(before.frame[-1], dtype=np.uint8)
                if frame.shape != (64, 64):
                    raise ValueError("S5_CORPUS_FRAME_SHAPE_INVALID")
                action_id = action.get("action_id")
                if isinstance(action_id, bool) or not isinstance(
                    action_id,
                    int,
                ):
                    raise TypeError("S5_CORPUS_ACTION_INVALID")
                target = (
                    (int(payload["x"]), int(payload["y"]))
                    if action_id == 6
                    else (-1, -1)
                )
                mask = np.zeros(8, dtype=np.uint8)
                for raw_action in before.available_actions:
                    value = int(getattr(raw_action, "value", raw_action))
                    if 1 <= value <= 7:
                        mask[value] = 1
                frames.append(np.array(frame, copy=True))
                actions.append(action_id)
                targets.append(target)
                available.append(mask)
                game_ordinals.append(game_ordinal)
                levels_completed.append(int(before.levels_completed))
                compatibility_resets.append(
                    int(
                        action_id == 0
                        and action.get("reset_scope")
                        == "LEVEL_COMPATIBILITY"
                    )
                )

            report = execute_s4_global_policy(
                environment=environment,
                policy_graph=graph,
                transition_sink=collect,
            )
            action_count = len(actions) - before_count
            if action_count != report["actions_executed"]:
                raise RuntimeError("S5_CORPUS_ACTION_ACCOUNTING_INVALID")
            environment_action_counts.append(action_count)
            environment_level_counts.append(
                int(report["completed_levels"])
            )
            print(
                json.dumps(
                    {
                        "event": "S5_TRAINING_CORPUS_COLLECTED",
                        "evaluation_environment": evaluation_identifier,
                        "records": action_count,
                        "completed_levels": report["completed_levels"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()

    arrays = {
        "actions": np.asarray(actions, dtype=np.uint8),
        "available": np.stack(available).astype(np.uint8),
        "frames": np.stack(frames).astype(np.uint8),
        "game_ordinal": np.asarray(game_ordinals, dtype=np.uint8),
        "level_compatibility_reset": np.asarray(
            compatibility_resets,
            dtype=np.uint8,
        ),
        "levels_completed": np.asarray(
            levels_completed,
            dtype=np.uint8,
        ),
        "targets": np.asarray(targets, dtype=np.int8),
    }
    write_deterministic_npz(output_npz, arrays)
    corpus_sha256 = hashlib.sha256(output_npz.read_bytes()).hexdigest()
    body: dict[str, Any] = {
        "schema_version": S5_TRAINING_CORPUS_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-S5-TEACHER-COMPILATION",
        "operation_mode": "offline",
        "source_policy_digest": graph.get("content_digest"),
        "complete_inventory": not requested,
        "environment_count": len(selected),
        "completed_levels": sum(environment_level_counts),
        "record_count": len(actions),
        "pointer_record_count": sum(
            int(action == 6) for action in actions
        ),
        "compatibility_reset_record_count": sum(
            compatibility_resets
        ),
        "frame_shape": [64, 64],
        "array_names": sorted(arrays),
        "corpus_sha256": corpus_sha256,
        "environment_action_counts": environment_action_counts,
        "environment_level_counts": environment_level_counts,
        "runtime_artifact_must_exclude": [
            "frames",
            "action labels",
            "pointer labels",
            "environment ordinals",
            "level progress labels",
        ],
    }
    return {
        **body,
        "content_digest": (
            S5_TRAINING_CORPUS_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile development-only S5 training corpus."
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--s4-policy-graph", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--game", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = compile_s5_training_corpus(
        environments_dir=args.environments_dir,
        s4_policy_graph_path=args.s4_policy_graph,
        output_npz=args.output_npz,
        requested_games=args.game,
        recordings_dir=args.recordings_dir,
    )
    _write_json(args.output_manifest, report)
    print(
        json.dumps(
            {
                "output_npz": str(args.output_npz.resolve()),
                "output_manifest": str(args.output_manifest.resolve()),
                "record_count": report["record_count"],
                "completed_levels": report["completed_levels"],
                "corpus_sha256": report["corpus_sha256"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S5_TRAINING_CORPUS_SCHEMA_VERSION",
    "compile_s5_training_corpus",
    "write_deterministic_npz",
]
