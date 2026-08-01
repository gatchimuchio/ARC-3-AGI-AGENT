#!/usr/bin/env python3
"""Build deterministic PH-D05 canonical ARC3 teacher trajectory packages."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import struct
import sys
import tempfile
import zlib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.arc3_trajectory_normalization import (  # noqa: E402
    canonical_invariance_projection,
    normalize_teacher_recording,
)
from hds_distill.canonical import (  # noqa: E402
    DigestExclusionPolicy,
    canonical_json_document_bytes,
    canonical_trajectory_digest,
    content_derived_id,
    logical_content_digest,
)
from hds_distill.schema_registry import (  # noqa: E402
    validate_json_schema_instance,
)

PHASE_ID = "PH-D05"
ARTIFACT_VERSION = "ph-d05-v1"
EXPECTED_SOURCE_MANIFEST_DIGEST = (
    "hds-source-content-manifest:"
    "3098feb7241e4ea3444b5942ab8ba0371d8168a51f32a1f3d44c0e09db36eda9"
)
EXPECTED_ENVIRONMENT_MANIFEST_DIGEST = (
    "hds-environment-manifest:"
    "1d116488cd85ee5ad9d641aeb2af66187572b181cb03d819fac1cdba3252cfe0"
)
EXPECTED_ACQUISITION_REPORT_DIGEST = (
    "hds-arc3-teacher-recording-acquisition:"
    "65986e9a82459fc5cbe93641aff16a37bd3c5d9f9e0efb759a8a955ec135a266"
)
EXPECTED_FULL_SOLUTION_CORPUS_DIGEST = (
    "arc3_full_solution_corpus:"
    "995bbdb3e8323824bdd8ac4a5c3b8f7b64dfffcd2e2618ec87733fc75c1067ce"
)
EXPECTED_REPLAY_X3_REPORT_DIGEST = (
    "hds-arc3-replay-x3:"
    "22b230deae993e9a590214a39e76c40e8b0800d334ad1ca9ba42356dbfb36c80"
)
EXPECTED_WORK_BLOCK_FRAME_DIGEST = (
    "rev3-work-block-frame:"
    "d21494a52736baf15e0ecfe046eeeb947ecffdc183c916c4ada25bcf9108dfab"
)
EXPECTED_PREINVENTORY_DIGEST = (
    "rev3-ph-d05-teacher-trajectory-preinventory:"
    "ccb578094aa4c2931dcf3f65e58209685b4a40b6e18d4473a1b3d530beda0155"
)
EXPECTED_ENTRY_TRANSITION_DIGEST = (
    "rev3-phase-transition:"
    "00f50fe8fc9e77bc26d899392f36a097bdaea5e1f8620d0ef5018bb87254e36f"
)
EXPECTED_ENTRY_DECISION_DIGEST = (
    "sha256:4eb6fdb70f8e4c37883966b17485c318eda07dcd182c0c9dfae90a1ac0f4bcfe"
)
EXPECTED_ENTRY_APPROVAL_DIGEST = (
    "owner-approval-record:"
    "42ba4fc83bc4cb750d1e3ac3a011741a68f557bdd02f06f308860b15567d37f1"
)
EXPECTED_INPUT_EVIDENCE_COMMIT = "caab292eaf3b67de87dcb1a4ae684d6f7dc1a360"
EXPECTED_INPUT_EVIDENCE_PAYLOAD_DIGEST = (
    "sha256:88a5fe85e322640315e3121e0bfd150c96fa05e8119fcdd21b5e391abb9b6e55"
)
EXPECTED_CANONICAL_MANIFEST_DIGEST = (
    "hds-arc3-canonical-teacher-corpus-manifest:"
    "f81183465265bfa9f29208dd788bb3bfd358c23995ab0aeb8ec9549450360aa6"
)
EXPECTED_NORMALIZATION_REPORT_DIGEST = (
    "hds-arc3-teacher-trajectory-normalization-report:"
    "8e9010a597e4351c21af7673467c830fbca176be8f7beda69ff4e4df0b9311a4"
)
EXPECTED_REBUILD_X3_DIGEST = (
    "hds-arc3-canonical-trajectory-rebuild-x3:"
    "5f053c72e7f77115cd1300d21ef70661a430e6dbb8fe4f1535948a192a9b458f"
)


class BuildError(RuntimeError):
    """A deterministic PH-D05 artifact build or conformance failure."""


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"PH_D05_JSON_OBJECT_REQUIRED:{path}")
    return value


def _canonical_body_digest(namespace: str, value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("content_digest", None)
    payload = json.dumps(
        body,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return namespace + ":" + hashlib.sha256(payload).hexdigest()


def _generated_canonical_document_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize already-normalized generated records without a second walk."""

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


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=".ph-d05-build-",
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


def _deterministic_gzip(payload: bytes) -> bytes:
    """Return one fixed-header, raw-DEFLATE gzip member."""

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
    result = header + compressed + trailer
    if gzip.decompress(result) != payload:
        raise BuildError("PH_D05_DETERMINISTIC_GZIP_ROUNDTRIP_FAILED")
    return result


def _source_bindings(
    selection: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> list[dict[str, object]]:
    if source_manifest.get("content_digest") != EXPECTED_SOURCE_MANIFEST_DIGEST:
        raise BuildError("PH_D05_SOURCE_MANIFEST_DIGEST_MISMATCH")
    if (
        selection.get("dataset_id") != "magic-sword/arc_agi_3_public_demo_human_testing"
        or selection.get("dataset_repo_sha")
        != "455b7c58eaa9d5ea05f91cd1b5b603121599e758"
    ):
        raise BuildError("PH_D05_SELECTION_DATASET_MISMATCH")
    raw_files = source_manifest.get("files")
    raw_rows = selection.get("rows")
    digests = selection.get("pinned_trajectory_sha256_by_game")
    if (
        not isinstance(raw_files, list)
        or not isinstance(raw_rows, list)
        or not isinstance(digests, dict)
        or len(raw_files) != 25
        or len(raw_rows) != 25
    ):
        raise BuildError("PH_D05_SOURCE_INVENTORY_INVALID")
    files: dict[str, Mapping[str, Any]] = {}
    for item in raw_files:
        if not isinstance(item, Mapping):
            raise BuildError("PH_D05_SOURCE_FILE_INVALID")
        relative = str(item.get("repository_relative_posix_path", ""))
        files[Path(relative).name] = item
    result: list[dict[str, object]] = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            raise BuildError("PH_D05_SELECTION_ROW_INVALID")
        filename = str(row.get("recording_file", ""))
        source = files.get(filename)
        game_id = str(row.get("game_id", ""))
        if source is None or not game_id:
            raise BuildError("PH_D05_SELECTION_SOURCE_JOIN_FAILED")
        if source.get("sha256") != digests.get(game_id):
            raise BuildError(f"PH_D05_SELECTION_SOURCE_SHA_MISMATCH:{game_id}")
        result.append(
            {
                "game_id": game_id,
                "recording_file": filename,
                "target_levels": row.get("target_levels"),
                "expected_actions": row.get("expected_actions"),
                "row_index": row.get("row_index"),
                "size_bytes": source.get("size_bytes"),
                "sha256": source.get("sha256"),
            }
        )
    result.sort(key=lambda item: str(item["game_id"]))
    if len({str(item["game_id"]) for item in result}) != 25:
        raise BuildError("PH_D05_GAME_COVERAGE_INVALID")
    return result


def _validate_acquisition_report(
    report: Mapping[str, Any],
    source_bindings: list[dict[str, object]],
) -> None:
    if report.get("content_digest") != EXPECTED_ACQUISITION_REPORT_DIGEST:
        raise BuildError("PH_D05_ACQUISITION_REPORT_DIGEST_MISMATCH")
    if _canonical_body_digest(
        "hds-arc3-teacher-recording-acquisition",
        report,
    ) != report.get("content_digest"):
        raise BuildError("PH_D05_ACQUISITION_REPORT_CONTENT_INVALID")
    files = report.get("files")
    if not isinstance(files, list):
        raise BuildError("PH_D05_ACQUISITION_REPORT_FILES_INVALID")
    expected = {
        (
            item["game_id"],
            item["recording_file"],
            item["size_bytes"],
            item["sha256"],
        )
        for item in source_bindings
    }
    actual = {
        (
            item.get("game_id"),
            item.get("recording_file"),
            item.get("size_bytes"),
            item.get("sha256"),
        )
        for item in files
        if isinstance(item, Mapping)
    }
    if expected != actual:
        raise BuildError("PH_D05_ACQUISITION_REPORT_COVERAGE_MISMATCH")


def _full_solution_index(corpus: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if corpus.get("content_digest") != EXPECTED_FULL_SOLUTION_CORPUS_DIGEST:
        raise BuildError("PH_D05_FULL_SOLUTION_CORPUS_DIGEST_MISMATCH")
    games = corpus.get("games")
    if not isinstance(games, list) or len(games) != 25:
        raise BuildError("PH_D05_FULL_SOLUTION_CORPUS_COVERAGE_INVALID")
    result = {
        str(item["game_id"]): item
        for item in games
        if isinstance(item, Mapping) and "game_id" in item
    }
    if len(result) != 25:
        raise BuildError("PH_D05_FULL_SOLUTION_GAME_DUPLICATE")
    return result


def _replay_contract_index(
    report: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if report.get("content_digest") != EXPECTED_REPLAY_X3_REPORT_DIGEST:
        raise BuildError("PH_D05_REPLAY_X3_REPORT_DIGEST_MISMATCH")
    if _canonical_body_digest("hds-arc3-replay-x3", report) != report.get(
        "content_digest"
    ):
        raise BuildError("PH_D05_REPLAY_X3_REPORT_CONTENT_INVALID")
    if (
        report.get("exit_claim") != "ARC3_STRICT_OFFLINE_REPLAY_X3_COMPLETE"
        or report.get("independent_process_count") != 3
        or report.get("game_count") != 25
        or report.get("level_count") != 183
        or report.get("action_count") != 11574
        or report.get("canonical_replay_mismatch_count") != 0
        or report.get("action_availability_terminal_progress_mismatch_count") != 0
    ):
        raise BuildError("PH_D05_REPLAY_X3_REPORT_COVERAGE_INVALID")
    rows = report.get("per_game_replay_contracts")
    if not isinstance(rows, list) or len(rows) != 25:
        raise BuildError("PH_D05_REPLAY_X3_CONTRACTS_INVALID")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise BuildError("PH_D05_REPLAY_X3_CONTRACT_INVALID")
        game_id = str(row.get("game_id", ""))
        if not game_id or game_id in result:
            raise BuildError(f"PH_D05_REPLAY_X3_GAME_INVALID:{game_id}")
        result[game_id] = row
    return result


def _load_replay_capture(
    *,
    capture_dir: Path,
    game_id: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    path = capture_dir / f"{game_id}.json.gz"
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != contract.get("capture_sha256"):
        raise BuildError(f"PH_D05_REPLAY_CAPTURE_SHA_MISMATCH:{game_id}")
    try:
        value = json.loads(gzip.decompress(compressed))
    except (OSError, json.JSONDecodeError) as error:
        raise BuildError(f"PH_D05_REPLAY_CAPTURE_INVALID:{game_id}") from error
    if not isinstance(value, dict):
        raise BuildError(f"PH_D05_REPLAY_CAPTURE_OBJECT_REQUIRED:{game_id}")
    if (
        value.get("game_id") != game_id
        or value.get("content_digest") != contract.get("capture_content_digest")
        or value.get("actual_trace_digest") != contract.get("actual_trace_digest")
    ):
        raise BuildError(f"PH_D05_REPLAY_CAPTURE_CONTRACT_MISMATCH:{game_id}")
    return value


def _assert_replay_corpus_binding(
    package: Mapping[str, Any],
    game_solution: Mapping[str, Any],
) -> None:
    trajectory = package.get("detailed_trajectory")
    if not isinstance(trajectory, Mapping):
        raise BuildError("PH_D05_DETAILED_TRAJECTORY_MISSING")
    frame_binding_field = (
        "after_frame_digest"
        if trajectory.get("canonical_action_source")
        == "VERIFIED_LOCAL_SOLUTION_OVERRIDE"
        else "raw_after_frame_digest"
    )
    steps = trajectory.get("steps")
    source_actions = game_solution.get("actions")
    if not isinstance(steps, list) or not isinstance(source_actions, list):
        raise BuildError("PH_D05_REPLAY_BINDING_ACTIONS_INVALID")
    if len(steps) != len(source_actions):
        raise BuildError(
            f"PH_D05_REPLAY_BINDING_COUNT_MISMATCH:{game_solution.get('game_id')}"
        )
    for index, (raw_step, raw_source) in enumerate(
        zip(steps, source_actions, strict=True)
    ):
        if not isinstance(raw_step, Mapping) or not isinstance(raw_source, Mapping):
            raise BuildError("PH_D05_REPLAY_BINDING_STEP_INVALID")
        action = raw_step.get("action")
        if not isinstance(action, Mapping):
            raise BuildError("PH_D05_REPLAY_BINDING_ACTION_INVALID")
        terminal = raw_step.get("terminal_state_after")
        source_state = raw_source.get("expected_state")
        expected_terminal = (
            "CONTINUE" if source_state == "NOT_FINISHED" else source_state
        )
        expected = (
            raw_source.get("action_id"),
            raw_source.get("action_data"),
            raw_source.get("expected_frame_digest"),
            raw_source.get("expected_available_actions"),
            raw_source.get("expected_levels_completed"),
            expected_terminal,
        )
        actual = (
            action.get("action_id"),
            action.get("payload"),
            raw_step.get(frame_binding_field),
            raw_step.get("available_actions_after"),
            raw_step.get("levels_completed_after"),
            terminal,
        )
        if actual != expected:
            raise BuildError(
                "PH_D05_REPLAY_BINDING_STEP_MISMATCH:"
                f"{game_solution.get('game_id')}:{index}"
            )


def _validate_d02b_projections(
    package: Mapping[str, Any],
    *,
    action_schema: Mapping[str, Any],
    trajectory_schema: Mapping[str, Any],
    certificate_schema: Mapping[str, Any],
) -> None:
    actions = package.get("ph_d02b_action_record_projections")
    if not isinstance(actions, list):
        raise BuildError("PH_D05_D02B_ACTION_PROJECTIONS_INVALID")
    for item in actions:
        validate_json_schema_instance(item, action_schema)
    validate_json_schema_instance(
        package.get("ph_d02b_teacher_trajectory_projection"),
        trajectory_schema,
    )
    validate_json_schema_instance(
        package.get("normalization_certificate"),
        certificate_schema,
    )


def normalization_contract() -> dict[str, Any]:
    """Return the exact content-bound PH-D05 execution contract."""

    contract: dict[str, Any] = {
        "schema_version": "hds-arc3-teacher-trajectory-normalization-contract-v1",
        "phase_id": PHASE_ID,
        "artifact_version": ARTIFACT_VERSION,
        "authority": {
            "work_block_frame_digest": EXPECTED_WORK_BLOCK_FRAME_DIGEST,
            "preinventory_digest": EXPECTED_PREINVENTORY_DIGEST,
            "phase_transition_digest": EXPECTED_ENTRY_TRANSITION_DIGEST,
            "phase_entry_decision_digest": EXPECTED_ENTRY_DECISION_DIGEST,
            "phase_entry_approval_digest": EXPECTED_ENTRY_APPROVAL_DIGEST,
            "input_evidence_commit": EXPECTED_INPUT_EVIDENCE_COMMIT,
            "input_evidence_payload_digest": (
                EXPECTED_INPUT_EVIDENCE_PAYLOAD_DIGEST
            ),
        },
        "source_contract": {
            "dataset_id": "magic-sword/arc_agi_3_public_demo_human_testing",
            "dataset_repo_sha": "455b7c58eaa9d5ea05f91cd1b5b603121599e758",
            "source_content_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
            "acquisition_report_digest": EXPECTED_ACQUISITION_REPORT_DIGEST,
            "environment_manifest_digest": EXPECTED_ENVIRONMENT_MANIFEST_DIGEST,
            "full_solution_corpus_digest": EXPECTED_FULL_SOLUTION_CORPUS_DIGEST,
            "replay_x3_report_digest": EXPECTED_REPLAY_X3_REPORT_DIGEST,
            "raw_recording_cache_location": "OUTSIDE_REPOSITORY",
            "source_recording_count": 25,
            "game_count": 25,
            "level_count": 183,
            "recorded_action_count": 11648,
            "canonical_success_prefix_action_count": 11574,
        },
        "normalization_contract": {
            "action_surface": [
                "RESET",
                "ACTION1",
                "ACTION2",
                "ACTION3",
                "ACTION4",
                "ACTION5",
                "ACTION6",
                "ACTION7",
            ],
            "action6_xy_payload_required": True,
            "non_action6_semantic_payload_forbidden": True,
            "before_action_after_binding_required": True,
            "available_actions_binding_required": True,
            "terminal_level_progress_binding_required": True,
            "raw_and_canonical_digest_separation_required": True,
            "lossless_frame_inverse_required": True,
            "raw_frame_provenance_required": True,
            "ph_d02b_compatibility_projection_required": True,
            "variable_metadata_in_canonical_digest_allowed": False,
        },
        "replay_contract": {
            "operation_mode": "OFFLINE",
            "independent_process_count": 3,
            "network_denial_required": True,
            "secret_scrub_required": True,
            "source_pre_post_identity_required": True,
            "write_allowlist_required": True,
            "fixed_seed_required": True,
            "canonical_replay_mismatch_max": 0,
            "action_availability_terminal_progress_mismatch_max": 0,
            "deterministic_canonical_build_count": 3,
            "deterministic_rebuild_byte_mismatch_max": 0,
        },
        "output_contract": {
            "canonical_manifest_path": (
                "distillation/artifacts/teacher/arc3/ph_d05_v1/manifest.json"
            ),
            "canonical_manifest_digest": EXPECTED_CANONICAL_MANIFEST_DIGEST,
            "normalization_report_path": (
                "distillation/artifacts/reports/"
                "arc3_teacher_trajectory_normalization.json"
            ),
            "normalization_report_digest": EXPECTED_NORMALIZATION_REPORT_DIGEST,
            "rebuild_x3_path": (
                "distillation/artifacts/teacher/arc3/ph_d05_v1/rebuild_x3.json"
            ),
            "rebuild_x3_digest": EXPECTED_REBUILD_X3_DIGEST,
            "package_count": 25,
        },
        "gate_contract": {
            "required_gate_ids": ["DG-00", "DG-06", "DG-10", "DG-11", "DG-12"],
            "required_result": "PASS",
        },
        "claim_boundary": {
            "allowed": "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE",
            "prohibited": [
                "CAUSAL_MECHANISM_ESTABLISHED",
                "HYPOTHESIS_SELECTED",
                "RULE_PROMOTED",
                "STRUCTURE_BUNDLE_OWNER_APPROVED",
                "BRIDGE_READY",
                "RUNTIME_READY",
                "OFFICIAL_READY",
            ],
        },
        "phase_boundaries": {
            "hypothesis_generation_count": 0,
            "causal_assertion_count": 0,
            "real_intervention_execution_count": 0,
            "rule_promotion_count": 0,
            "bridge_runtime_capability_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "stable_error_prefix": "PH_D05_",
        "digest_excluded_fields": ["content_digest", "contract_id"],
    }
    contract["content_digest"] = logical_content_digest(
        "hds-arc3-teacher-trajectory-normalization-contract",
        contract,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    contract["contract_id"] = content_derived_id(
        "hds-arc3-teacher-trajectory-normalization-contract-id",
        contract,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    return contract


def _validate_normalization_contract(path: Path) -> dict[str, Any]:
    expected = normalization_contract()
    if path.read_bytes() != canonical_json_document_bytes(expected):
        raise BuildError("PH_D05_NORMALIZATION_CONTRACT_BYTES_MISMATCH")
    return expected


def build(
    *,
    repository_root: Path,
    raw_recordings_dir: Path,
    replay_capture_dir: Path,
    artifact_root: Path,
    acquisition_report_path: Path,
    replay_report_path: Path,
    normalization_report_path: Path,
    normalization_contract_path: Path,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    raw_recordings_dir = raw_recordings_dir.resolve()
    replay_capture_dir = replay_capture_dir.resolve()
    artifact_root = artifact_root.resolve()
    if _inside(raw_recordings_dir, repository_root):
        raise BuildError("PH_D05_RAW_RECORDING_CACHE_INSIDE_REPOSITORY")
    if _inside(replay_capture_dir, repository_root):
        raise BuildError("PH_D05_REPLAY_CAPTURE_CACHE_INSIDE_REPOSITORY")
    if not _inside(artifact_root, repository_root):
        raise BuildError("PH_D05_ARTIFACT_ROOT_OUTSIDE_REPOSITORY")
    _validate_normalization_contract(normalization_contract_path)

    selection = _json_object(
        repository_root / "analysis/teacher/HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json"
    )
    source_manifest = _json_object(
        repository_root
        / "distillation/manifests/source_content/arc3-raw-teacher-recordings.json"
    )
    environment = _json_object(
        repository_root / "distillation/manifests/environment/arc3-replay.json"
    )
    acquisition_report = _json_object(acquisition_report_path)
    replay_report = _json_object(replay_report_path)
    corpus = _json_object(
        repository_root / "analysis/teacher/FULL_SOLUTION_CORPUS.json"
    )
    if environment.get("content_digest") != EXPECTED_ENVIRONMENT_MANIFEST_DIGEST:
        raise BuildError("PH_D05_ENVIRONMENT_MANIFEST_DIGEST_MISMATCH")
    bindings = _source_bindings(selection, source_manifest)
    _validate_acquisition_report(acquisition_report, bindings)
    full_solution = _full_solution_index(corpus)
    replay_contracts = _replay_contract_index(replay_report)

    action_schema = _json_object(
        repository_root / "distillation/schemas/arc3_action_record.schema.json"
    )
    trajectory_schema = _json_object(
        repository_root / "distillation/schemas/arc3_teacher_trajectory.schema.json"
    )
    certificate_schema = _json_object(
        repository_root / "distillation/schemas/normalization_certificate.schema.json"
    )

    package_dir = artifact_root / "packages"
    summaries: list[dict[str, Any]] = []
    action_surface = Counter[int]()
    package_filenames: set[str] = set()
    for binding in bindings:
        game_id = str(binding["game_id"])
        filename = str(binding["recording_file"])
        game_solution = full_solution[game_id]
        solution_source = game_solution.get("source")
        canonical_action_source = (
            "VERIFIED_LOCAL_SOLUTION_OVERRIDE"
            if isinstance(solution_source, Mapping)
            and "override_kind" in solution_source
            else "RAW_RECORDING"
        )
        normalization_binding = {
            **binding,
            "canonical_action_source": canonical_action_source,
        }
        raw_path = raw_recordings_dir / filename
        try:
            raw_payload = raw_path.read_bytes()
        except OSError as error:
            raise BuildError(
                f"PH_D05_RAW_RECORDING_UNREADABLE:{filename}:{error}"
            ) from error
        replay_capture = _load_replay_capture(
            capture_dir=replay_capture_dir,
            game_id=game_id,
            contract=replay_contracts[game_id],
        )
        package = cast(
            dict[str, Any],
            normalize_teacher_recording(
                raw_payload,
                source_binding=normalization_binding,
                environment_binding=environment,
                replay_capture=replay_capture,
            ),
        )
        _validate_d02b_projections(
            package,
            action_schema=action_schema,
            trajectory_schema=trajectory_schema,
            certificate_schema=certificate_schema,
        )
        _assert_replay_corpus_binding(package, game_solution)
        trajectory = cast(dict[str, Any], package["detailed_trajectory"])
        canonical_projection = canonical_invariance_projection(package)
        rebuilt_digest = canonical_trajectory_digest(
            canonical_projection,
            policy=DigestExclusionPolicy(),
        )
        if rebuilt_digest != trajectory["canonical_trajectory_digest"]:
            raise BuildError(f"PH_D05_CANONICAL_TRAJECTORY_DIGEST_MISMATCH:{game_id}")
        if trajectory["expected_replay_trace_digest"] != replay_contracts[game_id].get(
            "actual_trace_digest"
        ):
            raise BuildError(f"PH_D05_CANONICAL_REPLAY_TRACE_MISMATCH:{game_id}")
        uncompressed = _generated_canonical_document_bytes(package)
        compressed = _deterministic_gzip(uncompressed)
        package_filename = game_id + ".json.gz"
        package_path = package_dir / package_filename
        _atomic_write(package_path, compressed)
        if gzip.decompress(package_path.read_bytes()) != uncompressed:
            raise BuildError(f"PH_D05_PACKAGE_VERIFY_FAILED:{game_id}")
        package_filenames.add(package_filename)
        counts = trajectory["action_surface_counts"]
        if not isinstance(counts, Mapping):
            raise BuildError("PH_D05_ACTION_SURFACE_COUNTS_INVALID")
        action_surface.update({int(key): int(value) for key, value in counts.items()})
        summaries.append(
            {
                "game_id": game_id,
                "package_path": "packages/" + package_filename,
                "package_sha256": hashlib.sha256(compressed).hexdigest(),
                "package_size_bytes": len(compressed),
                "uncompressed_sha256": hashlib.sha256(uncompressed).hexdigest(),
                "uncompressed_size_bytes": len(uncompressed),
                "package_id": package["package_id"],
                "package_content_digest": package["content_digest"],
                "trajectory_id": trajectory["trajectory_id"],
                "raw_recording_digest": trajectory["raw_recording_digest"],
                "canonical_trajectory_digest": trajectory[
                    "canonical_trajectory_digest"
                ],
                "canonical_action_source": trajectory["canonical_action_source"],
                "raw_source_trajectory_projection_digest": trajectory[
                    "raw_source_trajectory_projection_digest"
                ],
                "expected_replay_trace_digest": trajectory[
                    "expected_replay_trace_digest"
                ],
                "recorded_action_count": trajectory["recorded_action_count"],
                "canonical_success_prefix_action_count": trajectory[
                    "canonical_success_prefix_action_count"
                ],
                "post_terminal_action_count": trajectory["post_terminal_action_count"],
                "canonical_override_action_reduction_count": trajectory[
                    "canonical_override_action_reduction_count"
                ],
                "source_frame_difference_count": trajectory[
                    "source_frame_difference_count"
                ],
                "replay_capture_digest": trajectory["replay_capture_digest"],
                "ph_d02b_action_projection_count": len(
                    package["ph_d02b_action_record_projections"]
                ),
                "frame_count": package["frame_store"]["frame_count"],
                "level_count": trajectory["level_completion_count"],
                "normalization_certificate_digest": package[
                    "normalization_certificate"
                ]["content_digest"],
                "status": "CANONICALIZED_REPLAY_READY",
            }
        )
        del package
        del raw_payload
        del replay_capture
        gc.collect()

    existing_packages = {
        path.name for path in package_dir.glob("*.json.gz") if path.is_file()
    }
    if existing_packages != package_filenames:
        raise BuildError("PH_D05_STALE_OR_MISSING_PACKAGE_FILE")
    summaries.sort(key=lambda item: str(item["game_id"]))
    total_recorded_actions = sum(
        int(item["recorded_action_count"]) for item in summaries
    )
    total_canonical_actions = sum(
        int(item["canonical_success_prefix_action_count"]) for item in summaries
    )
    total_projections = sum(
        int(item["ph_d02b_action_projection_count"]) for item in summaries
    )
    total_levels = sum(int(item["level_count"]) for item in summaries)
    total_source_frame_differences = sum(
        int(item["source_frame_difference_count"]) for item in summaries
    )
    canonical_override_count = sum(
        item["canonical_action_source"] == "VERIFIED_LOCAL_SOLUTION_OVERRIDE"
        for item in summaries
    )
    canonical_override_action_reduction_count = sum(
        int(item["canonical_override_action_reduction_count"]) for item in summaries
    )
    if (
        len(summaries) != 25
        or total_levels != 183
        or total_recorded_actions != 11648
        or total_canonical_actions != 11574
        or action_surface.get(6, 0) != 3125
        or total_projections != total_canonical_actions - action_surface.get(0, 0)
        or set(action_surface) != set(range(8))
        or total_source_frame_differences
        != replay_report.get("source_frame_difference_count")
        or canonical_override_count != 1
        or canonical_override_action_reduction_count != 74
    ):
        raise BuildError("PH_D05_CANONICAL_CORPUS_TOTALS_INVALID")

    manifest_body: dict[str, Any] = {
        "schema_version": "hds-arc3-canonical-teacher-corpus-manifest-v1",
        "artifact_version": ARTIFACT_VERSION,
        "phase_id": PHASE_ID,
        "source_content_manifest_digest": source_manifest["content_digest"],
        "acquisition_report_digest": acquisition_report["content_digest"],
        "environment_manifest_digest": environment["content_digest"],
        "replay_x3_report_digest": replay_report["content_digest"],
        "full_solution_corpus_digest": corpus["content_digest"],
        "physical_encoding": {
            "container": "GZIP_SINGLE_MEMBER",
            "compression": "RAW_DEFLATE_LEVEL_6",
            "header_mtime": 0,
            "header_os": 255,
            "json_encoding": "HDS_CANONICAL_JSON_DOCUMENT_WITH_FINAL_LF",
            "zlib_compile_version": zlib.ZLIB_VERSION,
            "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
        },
        "raw_recording_repository_byte_count": 0,
        "game_count": len(summaries),
        "level_count": total_levels,
        "recorded_action_count": total_recorded_actions,
        "canonical_success_prefix_action_count": total_canonical_actions,
        "post_terminal_action_count": sum(
            int(item["post_terminal_action_count"]) for item in summaries
        ),
        "source_frame_difference_count": total_source_frame_differences,
        "canonical_replay_mismatch_count": 0,
        "canonical_override_count": canonical_override_count,
        "canonical_override_action_reduction_count": (
            canonical_override_action_reduction_count
        ),
        "ph_d02b_action_projection_count": total_projections,
        "frame_count": sum(int(item["frame_count"]) for item in summaries),
        "action_surface_counts": {
            str(key): action_surface[key] for key in sorted(action_surface)
        },
        "action_surface_coverage": [
            "RESET",
            "ACTION1",
            "ACTION2",
            "ACTION3",
            "ACTION4",
            "ACTION5",
            "ACTION6",
            "ACTION7",
        ],
        "packages": summaries,
        "variable_metadata_in_canonical_hash_count": 0,
        "hypothesis_generation_count": 0,
        "causal_assertion_count": 0,
        "real_intervention_execution_count": 0,
        "rule_promotion_count": 0,
        "bridge_runtime_capability_count": 0,
        "official_access_count": 0,
        "kaggle_mutation_count": 0,
        "status": "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE",
        "digest_excluded_fields": ["content_digest", "manifest_id"],
    }
    manifest_body["content_digest"] = logical_content_digest(
        "hds-arc3-canonical-teacher-corpus-manifest",
        manifest_body,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"manifest_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    manifest_body["manifest_id"] = content_derived_id(
        "hds-arc3-canonical-teacher-corpus-manifest-id",
        manifest_body,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"manifest_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    if manifest_body["content_digest"] != EXPECTED_CANONICAL_MANIFEST_DIGEST:
        raise BuildError("PH_D05_CANONICAL_MANIFEST_DIGEST_UNEXPECTED")
    manifest_path = artifact_root / "manifest.json"
    _atomic_write(manifest_path, canonical_json_document_bytes(manifest_body))

    report: dict[str, Any] = {
        "schema_version": "hds-arc3-teacher-trajectory-normalization-report-v1",
        "phase_id": PHASE_ID,
        "artifact_version": ARTIFACT_VERSION,
        "canonical_manifest_path": (
            "distillation/artifacts/teacher/arc3/ph_d05_v1/manifest.json"
        ),
        "canonical_manifest_digest": manifest_body["content_digest"],
        "replay_x3_report_digest": replay_report["content_digest"],
        "source_recording_count": len(summaries),
        "game_count": len(summaries),
        "level_count": total_levels,
        "recorded_action_count": total_recorded_actions,
        "canonical_success_prefix_action_count": total_canonical_actions,
        "before_action_after_complete_count": total_canonical_actions,
        "action6_count": action_surface[6],
        "action6_complete_xy_payload_count": action_surface[6],
        "reset_count": action_surface[0],
        "source_frame_difference_count": total_source_frame_differences,
        "canonical_replay_mismatch_count": 0,
        "canonical_override_count": canonical_override_count,
        "canonical_override_action_reduction_count": (
            canonical_override_action_reduction_count
        ),
        "action_surface_counts": {
            str(key): action_surface[key] for key in sorted(action_surface)
        },
        "raw_and_canonical_digest_pair_count": len(summaries),
        "normalization_certificate_count": len(summaries),
        "lossless_inverse_frame_record_count": manifest_body["frame_count"],
        "variable_metadata_in_canonical_hash_count": 0,
        "ph_d02b_schema_mutation_count": 0,
        "ph_d02b_compatible_action_projection_count": total_projections,
        "replay_corpus_binding_mismatch_count": 0,
        "source_access": {
            "normalizer_role": "DISTILLATION_EXECUTOR",
            "raw_recording_access": True,
            "verified_replay_capture_access": True,
            "environment_source_access": False,
            "candidate_generation_access": False,
        },
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-10": "PASS",
            "DG-11": "PASS",
            "DG-12": "PASS",
        },
        "gate_basis": {
            "DG-00": (
                "every OFFLINE canonical frame has lossless RLE and inverse "
                "before-after diff with raw-frame provenance retained"
            ),
            "DG-06": (
                "all source size SHA provenance environment and raw-canonical "
                "digest pairs are complete"
            ),
            "DG-10": (
                "no intervention executed and every replay trajectory is reset-bound"
            ),
            "DG-11": (
                "ordered before-action-after observations retained without "
                "causal overclaim"
            ),
            "DG-12": (
                "bounded 25-game 11574-step build with no runtime dependency "
                "or unbounded search"
            ),
        },
        "claim_boundary": (
            "Lossless raw provenance and exact OFFLINE replay normalization "
            "only; no mechanism, necessity, or promotion claim."
        ),
        "exit_claim": "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE",
        "failed_requirement_ids": [],
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    report["content_digest"] = _canonical_body_digest(
        "hds-arc3-teacher-trajectory-normalization-report",
        report,
    )
    if report["content_digest"] != EXPECTED_NORMALIZATION_REPORT_DIGEST:
        raise BuildError("PH_D05_NORMALIZATION_REPORT_DIGEST_UNEXPECTED")
    _atomic_write(
        normalization_report_path,
        canonical_json_document_bytes(report),
    )
    return {
        "manifest": manifest_body,
        "report": report,
    }


def verify_deterministic_rebuilds(
    *,
    repository_root: Path,
    artifact_root: Path,
    normalization_report_path: Path,
    rebuild_roots: list[Path],
    evidence_report_path: Path,
    normalization_contract_path: Path,
) -> dict[str, Any]:
    """Bind two independent rebuilds to the primary PH-D05 output."""

    repository_root = repository_root.resolve()
    artifact_root = artifact_root.resolve()
    normalization_report_path = normalization_report_path.resolve()
    evidence_report_path = evidence_report_path.resolve()
    rebuild_roots = [path.resolve() for path in rebuild_roots]
    if len(rebuild_roots) != 2 or len(set(rebuild_roots)) != 2:
        raise BuildError("PH_D05_TWO_DISTINCT_REBUILD_ROOTS_REQUIRED")
    checked_paths = [
        artifact_root,
        normalization_report_path,
        evidence_report_path,
        *rebuild_roots,
    ]
    if any(not _inside(path, repository_root) for path in checked_paths):
        raise BuildError("PH_D05_REBUILD_EVIDENCE_PATH_OUTSIDE_REPOSITORY")
    if artifact_root in rebuild_roots:
        raise BuildError("PH_D05_REBUILD_ROOT_EQUALS_PRIMARY")
    contract = _validate_normalization_contract(normalization_contract_path)

    primary_manifest_path = artifact_root / "manifest.json"
    primary_manifest = _json_object(primary_manifest_path)
    primary_report = _json_object(normalization_report_path)
    package_paths = sorted((artifact_root / "packages").glob("*.json.gz"))
    if (
        len(package_paths) != 25
        or primary_manifest.get("game_count") != 25
        or primary_manifest.get("level_count") != 183
        or primary_manifest.get("canonical_success_prefix_action_count") != 11574
        or primary_report.get("exit_claim")
        != "ARC3_CANONICAL_TEACHER_TRAJECTORIES_COMPLETE"
        or primary_report.get("failed_requirement_ids") != []
        or primary_report.get("canonical_manifest_digest")
        != primary_manifest.get("content_digest")
    ):
        raise BuildError("PH_D05_PRIMARY_REBUILD_REFERENCE_INVALID")

    relative_artifact_paths = [Path("manifest.json")]
    relative_artifact_paths.extend(
        Path("packages") / path.name for path in package_paths
    )
    file_bindings: list[dict[str, object]] = []
    for relative in relative_artifact_paths:
        payload = (artifact_root / relative).read_bytes()
        file_bindings.append(
            {
                "logical_path": (
                    "distillation/artifacts/teacher/arc3/ph_d05_v1/"
                    + relative.as_posix()
                ),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    primary_report_bytes = normalization_report_path.read_bytes()
    file_bindings.append(
        {
            "logical_path": (
                "distillation/artifacts/reports/"
                "arc3_teacher_trajectory_normalization.json"
            ),
            "sha256": hashlib.sha256(primary_report_bytes).hexdigest(),
            "size_bytes": len(primary_report_bytes),
        }
    )

    run_evidence: list[dict[str, object]] = [
        {
            "run_index": 1,
            "output_role": "PRIMARY_CANONICAL_BUILD",
            "compared_file_count": len(file_bindings),
            "byte_mismatch_count": 0,
            "exit_claim": primary_report["exit_claim"],
        }
    ]
    for run_index, rebuild_root in enumerate(rebuild_roots, start=2):
        rebuild_packages = sorted((rebuild_root / "packages").glob("*.json.gz"))
        if [path.name for path in rebuild_packages] != [
            path.name for path in package_paths
        ]:
            raise BuildError(f"PH_D05_REBUILD_PACKAGE_SET_MISMATCH:{run_index}")
        mismatches = [
            relative.as_posix()
            for relative in relative_artifact_paths
            if (artifact_root / relative).read_bytes()
            != (rebuild_root / relative).read_bytes()
        ]
        rebuild_report_path = rebuild_root / "rebuild_report.json"
        rebuild_report_bytes = rebuild_report_path.read_bytes()
        if rebuild_report_bytes != primary_report_bytes:
            mismatches.append("normalization_report.json")
        if mismatches:
            raise BuildError(
                f"PH_D05_REBUILD_BYTE_MISMATCH:{run_index}:{','.join(mismatches)}"
            )
        rebuild_report = _json_object(rebuild_report_path)
        run_evidence.append(
            {
                "run_index": run_index,
                "output_role": "INDEPENDENT_CANONICAL_REBUILD",
                "compared_file_count": len(file_bindings),
                "byte_mismatch_count": 0,
                "exit_claim": rebuild_report["exit_claim"],
            }
        )

    evidence: dict[str, Any] = {
        "schema_version": "hds-arc3-ph-d05-deterministic-rebuild-x3-v1",
        "phase_id": PHASE_ID,
        "artifact_version": ARTIFACT_VERSION,
        "independent_process_count": 3,
        "canonical_build_count": 3,
        "package_count_per_build": len(package_paths),
        "compared_file_count_per_build": len(file_bindings),
        "total_byte_mismatch_count": 0,
        "canonical_manifest_digest": primary_manifest["content_digest"],
        "normalization_report_digest": primary_report["content_digest"],
        "file_bindings": file_bindings,
        "run_evidence": run_evidence,
        "variable_process_metadata_in_digest_count": 0,
        "failed_requirement_ids": [],
        "exit_claim": "ARC3_CANONICAL_TRAJECTORY_REBUILD_X3_COMPLETE",
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    evidence["content_digest"] = _canonical_body_digest(
        "hds-arc3-canonical-trajectory-rebuild-x3",
        evidence,
    )
    output_contract = contract["output_contract"]
    if (
        not isinstance(output_contract, Mapping)
        or evidence["content_digest"] != output_contract.get("rebuild_x3_digest")
    ):
        raise BuildError("PH_D05_REBUILD_EVIDENCE_DIGEST_UNEXPECTED")
    _atomic_write(evidence_report_path, canonical_json_document_bytes(evidence))
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--raw-recordings-dir", type=Path)
    parser.add_argument("--replay-capture-dir", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--acquisition-report", type=Path)
    parser.add_argument("--replay-report", type=Path)
    parser.add_argument("--normalization-report", type=Path)
    parser.add_argument("--normalization-contract", type=Path)
    parser.add_argument("--write-contract", action="store_true")
    parser.add_argument(
        "--verify-rebuild-root",
        action="append",
        default=[],
        type=Path,
    )
    parser.add_argument("--rebuild-evidence-report", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.root.resolve()
    artifact_root = args.artifact_root or (
        root / "distillation/artifacts/teacher/arc3/ph_d05_v1"
    )
    acquisition_report = args.acquisition_report or (
        root / "distillation/artifacts/reports/arc3_teacher_recording_acquisition.json"
    )
    replay_report = args.replay_report or (
        root / "distillation/artifacts/reports/arc3_teacher_replay_x3.json"
    )
    normalization_report = args.normalization_report or (
        root
        / "distillation/artifacts/reports/arc3_teacher_trajectory_normalization.json"
    )
    normalization_contract_path = args.normalization_contract or (
        root
        / "distillation/input/arc3_teacher_trajectory_normalization_contract.json"
    )
    if args.write_contract:
        contract = normalization_contract()
        _atomic_write(
            normalization_contract_path,
            canonical_json_document_bytes(contract),
        )
        print(
            json.dumps(
                {
                    "content_digest": contract["content_digest"],
                    "path": normalization_contract_path.as_posix(),
                    "phase_id": PHASE_ID,
                    "status": "PASS",
                },
                sort_keys=True,
            )
        )
        return 0
    if args.verify_rebuild_root:
        evidence_report = args.rebuild_evidence_report or (
            artifact_root / "rebuild_x3.json"
        )
        try:
            evidence = verify_deterministic_rebuilds(
                repository_root=root,
                artifact_root=artifact_root,
                normalization_report_path=normalization_report,
                rebuild_roots=args.verify_rebuild_root,
                evidence_report_path=evidence_report,
                normalization_contract_path=normalization_contract_path,
            )
        except (BuildError, OSError, ValueError) as error:
            print(f"PH_D05_REBUILD_VERIFY_FAIL:{error}")
            return 2
        print(
            json.dumps(
                {
                    "canonical_build_count": evidence["canonical_build_count"],
                    "compared_file_count_per_build": evidence[
                        "compared_file_count_per_build"
                    ],
                    "content_digest": evidence["content_digest"],
                    "exit_claim": evidence["exit_claim"],
                    "phase_id": PHASE_ID,
                    "status": "PASS",
                },
                sort_keys=True,
            )
        )
        return 0
    if args.raw_recordings_dir is None or args.replay_capture_dir is None:
        print("PH_D05_BUILD_FAIL:RAW_AND_REPLAY_DIRECTORIES_REQUIRED")
        return 2
    try:
        result = build(
            repository_root=root,
            raw_recordings_dir=args.raw_recordings_dir,
            replay_capture_dir=args.replay_capture_dir,
            artifact_root=artifact_root,
            acquisition_report_path=acquisition_report,
            replay_report_path=replay_report,
            normalization_report_path=normalization_report,
            normalization_contract_path=normalization_contract_path,
        )
    except (BuildError, OSError, ValueError) as error:
        print(f"PH_D05_BUILD_FAIL:{error}")
        return 2
    manifest = result["manifest"]
    report = result["report"]
    print(
        json.dumps(
            {
                "action_count": manifest["canonical_success_prefix_action_count"],
                "artifact_count": manifest["game_count"] + 2,
                "canonical_manifest_digest": manifest["content_digest"],
                "exit_claim": report["exit_claim"],
                "game_count": manifest["game_count"],
                "level_count": manifest["level_count"],
                "phase_id": PHASE_ID,
                "status": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
