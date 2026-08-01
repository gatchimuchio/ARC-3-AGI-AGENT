from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.arc3_trajectory_normalization import (
    TrajectoryNormalizationError,
    apply_visible_diff,
    canonical_invariance_projection,
    decode_frame_rle,
    encode_frame_rle,
    normalize_teacher_recording,
    visible_diff,
)
from hds_distill.canonical import (
    DigestExclusionPolicy,
    canonical_json_document_bytes,
    canonical_trajectory_digest,
    content_derived_id,
    logical_content_digest,
)
from hds_distill.schema_registry import validate_json_schema_instance

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _builder_module() -> Any:
    path = REPOSITORY_ROOT / "scripts/build_ph_d05_teacher_trajectories.py"
    spec = importlib.util.spec_from_file_location("ph_d05_builder", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(
    *,
    action_id: int,
    frame_value: int,
    state: str = "NOT_FINISHED",
    levels_completed: int = 0,
    payload: dict[str, int] | None = None,
    timestamp: str = "2026-01-01T00:00:00Z",
    guid: str = "variable-guid",
    reasoning: str = "variable human reasoning",
    full_reset: bool = False,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "data": {
            "action_input": {
                "id": str(action_id),
                "data": payload or {},
                "reasoning": reasoning,
            },
            "available_actions": [7, 6, 5, 4, 3, 2, 1],
            "frame": [[[frame_value, (frame_value + 1) % 10]]],
            "full_reset": full_reset,
            "game_id": "fixture-game",
            "guid": guid,
            "levels_completed": levels_completed,
            "state": state,
            "win_levels": 1,
        },
    }


def _events() -> list[dict[str, Any]]:
    values = [
        _event(action_id=0, frame_value=0, full_reset=True),
        _event(action_id=1, frame_value=1),
        _event(action_id=2, frame_value=2),
        _event(action_id=3, frame_value=3),
        _event(action_id=4, frame_value=4),
        _event(action_id=5, frame_value=5),
        _event(action_id=6, frame_value=6, payload={"x": 12, "y": 34}),
        _event(action_id=7, frame_value=7),
        _event(
            action_id=0,
            frame_value=8,
            state="WIN",
            levels_completed=1,
        ),
    ]
    return values


def _raw(events: list[dict[str, Any]] | None = None) -> bytes:
    return json.dumps(
        events or _events(),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _source(raw: bytes) -> dict[str, object]:
    return {
        "game_id": "fixture-game",
        "recording_file": "fixture.recording",
        "target_levels": 1,
        "expected_actions": 8,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _fixture_action_id(value: object) -> int:
    text = str(value).upper()
    return int(text.removeprefix("ACTION"))


def _fixture_frame_digest(frame: object) -> str:
    payload = json.dumps(
        frame,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _capture(events: list[dict[str, Any]]) -> dict[str, Any]:
    first_id = _fixture_action_id(events[0]["data"]["action_input"]["id"])
    if first_id != 0:
        raise AssertionError("fixture capture requires an initial reset event")
    initial_data = events[0]["data"]
    initial = {
        "frame": initial_data["frame"],
        "frame_digest": _fixture_frame_digest(initial_data["frame"]),
        "available_actions": sorted(initial_data["available_actions"]),
        "terminal_state": initial_data["state"],
        "levels_completed": initial_data["levels_completed"],
    }
    steps: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    for event in events[1:]:
        data = event["data"]
        action_input = data["action_input"]
        action_id = _fixture_action_id(action_input["id"])
        payload = {
            key: action_input["data"][key]
            for key in ("x", "y")
            if key in action_input["data"]
        }
        frame_digest = _fixture_frame_digest(data["frame"])
        reset_scope = (
            "LEVEL_COMPATIBILITY"
            if action_id == 0 and data.get("full_reset") is not True
            else "RECORDED_ACTION"
        )
        step = len(steps) + 1
        after = {
            "frame": data["frame"],
            "frame_digest": frame_digest,
            "available_actions": sorted(data["available_actions"]),
            "terminal_state": data["state"],
            "levels_completed": data["levels_completed"],
        }
        steps.append(
            {
                "step": step,
                "action_id": action_id,
                "action_data": payload,
                "reset_scope": reset_scope,
                "after": after,
                "source_frame_match": True,
                "source_frame_digest": frame_digest,
            }
        )
        trace.append(
            {
                "step": step,
                "action_id": action_id,
                "action_data": payload,
                "state": data["state"],
                "levels_completed": data["levels_completed"],
                "frame_digest": frame_digest,
                "reset_scope": reset_scope,
            }
        )
        if data["state"] == "WIN":
            break
    body: dict[str, Any] = {
        "schema_version": "hds-arc3-ph-d05-replay-capture-v1",
        "phase_id": "PH-D05",
        "game_id": "fixture-game",
        "target_levels": 1,
        "source_solution_digest": "fixture-solution",
        "initial": initial,
        "steps": steps,
        "actual_trace_digest": hashlib.sha256(
            json.dumps(
                trace,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "source_frame_difference_count": 0,
        "terminal_state": "WIN",
    }
    body["content_digest"] = (
        "hds-arc3-replay-capture:"
        + hashlib.sha256(
            json.dumps(
                body,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
    return body


def _environment() -> dict[str, object]:
    return {
        "manifest_id": "arc3-replay-environment-ph-d01b",
        "content_digest": (
            "hds-environment-manifest:"
            "1d116488cd85ee5ad9d641aeb2af66187572b181cb03d819fac1cdba3252cfe0"
        ),
    }


def _package(raw: bytes | None = None) -> dict[str, Any]:
    payload = raw or _raw()
    events = cast(list[dict[str, Any]], json.loads(payload))
    return cast(
        dict[str, Any],
        normalize_teacher_recording(
            payload,
            source_binding=_source(payload),
            environment_binding=_environment(),
            replay_capture=_capture(events),
        ),
    )


def _schema(name: str) -> dict[str, Any]:
    value = json.loads(
        (REPOSITORY_ROOT / "distillation/schemas" / name).read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_frame_rle_and_visible_diff_are_exactly_invertible() -> None:
    before = [
        [[0, 0, 1, 1], [2, 2, 2, 3]],
        [[4, 4, 4, 4], [5, 5, 6, 6]],
    ]
    after = copy.deepcopy(before)
    after[0][0][1:3] = [7, 8]
    after[1][1][3] = 9

    encoded = encode_frame_rle(before)
    assert decode_frame_rle(encoded) == before
    delta = visible_diff(before, after)
    assert delta["changed_cell_count"] == 3
    assert apply_visible_diff(before, delta) == after


def test_visible_diff_shape_change_is_exactly_invertible() -> None:
    before = [[[0, 1], [2, 3]]]
    after = [[[4, 5, 6]], [[7, 8, 9]]]
    delta = visible_diff(before, after)
    assert delta["mode"] == "FULL_FRAME_REPLACEMENT"
    assert apply_visible_diff(before, delta) == after


def test_normalizer_preserves_complete_raw_action_surface_and_transitions() -> None:
    package = _package()
    trajectory = package["detailed_trajectory"]
    steps = trajectory["steps"]

    assert len(steps) == 8
    assert trajectory["recorded_action_count"] == 8
    assert trajectory["canonical_success_prefix_action_count"] == 8
    assert trajectory["post_terminal_action_count"] == 0
    assert trajectory["level_completion_count"] == 1
    assert trajectory["final_terminal_state"] == "WIN"
    assert trajectory["action_surface_counts"] == {str(index): 1 for index in range(8)}
    assert [step["action"]["action_id"] for step in steps] == list(range(1, 8)) + [0]
    assert steps[5]["action"]["payload"] == {"x": 12, "y": 34}
    assert all(
        step["action"]["payload"] == {}
        for index, step in enumerate(steps)
        if index != 5
    )
    assert all(
        {
            "before_frame_digest",
            "before_canonical_frame_ref",
            "available_actions_before",
            "action",
            "after_frame_digest",
            "after_canonical_frame_ref",
            "available_actions_after",
            "terminal_state_after",
            "visible_diff",
            "progress_delta",
        }
        <= set(step)
        for step in steps
    )
    frames = package["frame_store"]["frames"]
    by_id = {item["frame_id"]: item for item in frames}
    assert all(step["before_canonical_frame_ref"] in by_id for step in steps)
    assert all(step["after_canonical_frame_ref"] in by_id for step in steps)
    assert all(decode_frame_rle(item["canonical_frame"]) for item in frames)


def test_d02b_compatibility_projections_validate_without_mutating_schema() -> None:
    package = _package()
    action_schema = _schema("arc3_action_record.schema.json")
    trajectory_schema = _schema("arc3_teacher_trajectory.schema.json")
    certificate_schema = _schema("normalization_certificate.schema.json")

    action_projections = package["ph_d02b_action_record_projections"]
    assert len(action_projections) == 7
    assert {item["action_id"] for item in action_projections} == set(range(1, 8))
    for item in action_projections:
        validate_json_schema_instance(item, action_schema)
    validate_json_schema_instance(
        package["ph_d02b_teacher_trajectory_projection"],
        trajectory_schema,
    )
    validate_json_schema_instance(
        package["normalization_certificate"],
        certificate_schema,
    )


def test_single_pass_content_bindings_match_canonical_contract() -> None:
    package = _package()
    policy = DigestExclusionPolicy()
    self_policy = DigestExclusionPolicy(
        id_fields=frozenset(
            {
                "action_record_id",
                "certificate_id",
                "frame_id",
                "package_id",
                "trajectory_id",
            }
        ),
        digest_fields=frozenset({"content_digest"}),
    )
    package_binding = package["logical_binding_projection"]
    assert package["content_digest"] == logical_content_digest(
        "hds-arc3-teacher-trajectory-package",
        package_binding,
        policy=policy,
    )
    assert package["package_id"] == content_derived_id(
        "hds-arc3-teacher-trajectory-package-id",
        package_binding,
        policy=policy,
    )
    frame_store = package["frame_store"]
    assert frame_store["content_digest"] == logical_content_digest(
        "hds-arc3-canonical-frame-store",
        frame_store["logical_binding_projection"],
        policy=policy,
    )
    frame = frame_store["frames"][0]
    assert frame["content_digest"] == logical_content_digest(
        "hds-canonical-frame",
        frame,
        policy=self_policy,
    )
    assert frame["frame_id"] == content_derived_id(
        "hds-canonical-frame-id",
        frame,
        policy=self_policy,
    )
    action = package["detailed_trajectory"]["steps"][0]["action"]
    assert action["content_digest"] == logical_content_digest(
        "hds-arc3-detailed-action-record",
        action,
        policy=self_policy,
    )
    assert action["action_record_id"] == content_derived_id(
        "hds-arc3-detailed-action-record-id",
        action,
        policy=self_policy,
    )
    fast_bytes = (
        json.dumps(
            package,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    assert fast_bytes == canonical_json_document_bytes(package)


def test_canonical_digest_excludes_variable_metadata() -> None:
    original_events = _events()
    mutated_events = copy.deepcopy(original_events)
    for index, event in enumerate(mutated_events):
        event["timestamp"] = f"2099-12-31T23:59:{index:02d}Z"
        event["data"]["guid"] = f"different-guid-{index}"
        event["data"]["action_input"]["reasoning"] = f"different reasoning {index}"
    original = _package(_raw(original_events))
    mutated = _package(_raw(mutated_events))
    original_trajectory = original["detailed_trajectory"]
    mutated_trajectory = mutated["detailed_trajectory"]

    assert (
        original_trajectory["raw_recording_digest"]
        != mutated_trajectory["raw_recording_digest"]
    )
    assert (
        original_trajectory["canonical_trajectory_digest"]
        == (mutated_trajectory["canonical_trajectory_digest"])
    )
    assert canonical_invariance_projection(original) == (
        canonical_invariance_projection(mutated)
    )
    rebuilt = canonical_trajectory_digest(
        canonical_invariance_projection(original),
        policy=DigestExclusionPolicy(),
    )
    assert rebuilt == original_trajectory["canonical_trajectory_digest"]


def test_post_terminal_raw_tail_is_counted_but_not_canonicalized() -> None:
    events = _events()
    events.append(_event(action_id=1, frame_value=9, state="WIN", levels_completed=1))
    raw = _raw(events)
    source = _source(raw)
    source["expected_actions"] = 9
    package = cast(
        dict[str, Any],
        normalize_teacher_recording(
            raw,
            source_binding=source,
            environment_binding=_environment(),
            replay_capture=_capture(events),
        ),
    )
    trajectory = package["detailed_trajectory"]
    assert trajectory["recorded_action_count"] == 9
    assert trajectory["canonical_success_prefix_action_count"] == 8
    assert trajectory["post_terminal_action_count"] == 1


def test_missing_raw_pre_action_observation_is_bound_from_replay() -> None:
    complete_events = _events()
    action_events = complete_events[1:]
    raw = _raw(action_events)
    source = _source(raw)
    source["expected_actions"] = len(action_events)
    package = cast(
        dict[str, Any],
        normalize_teacher_recording(
            raw,
            source_binding=source,
            environment_binding=_environment(),
            replay_capture=_capture(complete_events),
        ),
    )
    trajectory = package["detailed_trajectory"]
    assert trajectory["raw_initial_observation_event_present"] is False
    assert trajectory["initial_reset_action_id"] is None
    assert trajectory["steps"][0]["source_event_index"] == 0
    assert trajectory["steps"][0]["raw_before_frame_source"] == (
        "REPLAY_INITIAL_OBSERVATION_RAW_PRE_ACTION_ABSENT"
    )


def test_verified_local_override_preserves_distinct_raw_trajectory() -> None:
    raw_events = _events()
    canonical_events = copy.deepcopy(raw_events)
    canonical_events[1]["data"]["action_input"]["id"] = "2"
    raw = _raw(raw_events)
    source = _source(raw)
    source["canonical_action_source"] = "VERIFIED_LOCAL_SOLUTION_OVERRIDE"
    package = cast(
        dict[str, Any],
        normalize_teacher_recording(
            raw,
            source_binding=source,
            environment_binding=_environment(),
            replay_capture=_capture(canonical_events),
        ),
    )
    trajectory = package["detailed_trajectory"]
    assert trajectory["canonical_action_source"] == ("VERIFIED_LOCAL_SOLUTION_OVERRIDE")
    assert trajectory["raw_canonical_action_alignment"] == (
        "DIVERGENT_VERIFIED_OVERRIDE"
    )
    assert trajectory["steps"][0]["action"]["action_id"] == 2
    raw_projection = package["raw_source_trajectory_projection"]
    assert raw_projection["steps"][0]["action_id"] == 1
    assert raw_projection["recorded_action_count"] == 8


@pytest.mark.parametrize(
    ("action_id", "payload", "code"),
    [
        (6, {"x": 1}, "PH_D05_ACTION6_XY_REQUIRED"),
        (5, {"x": 1, "y": 2}, "PH_D05_NON_ACTION6_PAYLOAD_FORBIDDEN"),
    ],
)
def test_action_payload_contract_fails_closed(
    action_id: int,
    payload: dict[str, int],
    code: str,
) -> None:
    events = _events()
    events[1]["data"]["action_input"]["id"] = str(action_id)
    events[1]["data"]["action_input"]["data"] = payload
    raw = _raw(events)
    with pytest.raises(TrajectoryNormalizationError, match=code):
        normalize_teacher_recording(
            raw,
            source_binding=_source(raw),
            environment_binding=_environment(),
            replay_capture=_capture(events),
        )


def test_action_game_id_is_validated_and_excluded_from_payload() -> None:
    events = _events()
    for event in events:
        action_data = event["data"]["action_input"]["data"]
        action_data["game_id"] = "fixture-game"
    raw = _raw(events)
    package = cast(
        dict[str, Any],
        normalize_teacher_recording(
            raw,
            source_binding=_source(raw),
            environment_binding=_environment(),
            replay_capture=_capture(events),
        ),
    )
    steps = package["detailed_trajectory"]["steps"]
    assert all("game_id" not in step["action"]["payload"] for step in steps)

    events[1]["data"]["action_input"]["data"]["game_id"] = "wrong-game"
    mismatched = _raw(events)
    with pytest.raises(
        TrajectoryNormalizationError,
        match="PH_D05_ACTION_GAME_FAMILY_MISMATCH",
    ):
        normalize_teacher_recording(
            mismatched,
            source_binding=_source(mismatched),
            environment_binding=_environment(),
            replay_capture=_capture(events),
        )


def test_raw_content_and_environment_drift_fail_closed() -> None:
    raw = _raw()
    bad_source = _source(raw)
    bad_source["sha256"] = "0" * 64
    with pytest.raises(
        TrajectoryNormalizationError,
        match="PH_D05_RAW_RECORDING_SHA_MISMATCH",
    ):
        normalize_teacher_recording(
            raw,
            source_binding=bad_source,
            environment_binding=_environment(),
            replay_capture=_capture(_events()),
        )

    bad_environment = _environment()
    bad_environment["content_digest"] = "hds-environment-manifest:" + "0" * 64
    with pytest.raises(
        TrajectoryNormalizationError,
        match="PH_D05_ENVIRONMENT_BINDING_DIGEST_MISMATCH",
    ):
        normalize_teacher_recording(
            raw,
            source_binding=_source(raw),
            environment_binding=bad_environment,
            replay_capture=_capture(_events()),
        )


def test_committed_normalization_contract_matches_builder_exactly() -> None:
    builder = _builder_module()
    contract = builder.normalization_contract()
    path = (
        REPOSITORY_ROOT
        / "distillation/input/arc3_teacher_trajectory_normalization_contract.json"
    )
    assert path.read_bytes() == canonical_json_document_bytes(contract)
    assert contract["source_contract"] == {
        "acquisition_report_digest": (
            "hds-arc3-teacher-recording-acquisition:"
            "65986e9a82459fc5cbe93641aff16a37bd3c5d9f9e0efb759a8a955ec135a266"
        ),
        "canonical_success_prefix_action_count": 11574,
        "dataset_id": "magic-sword/arc_agi_3_public_demo_human_testing",
        "dataset_repo_sha": "455b7c58eaa9d5ea05f91cd1b5b603121599e758",
        "environment_manifest_digest": (
            "hds-environment-manifest:"
            "1d116488cd85ee5ad9d641aeb2af66187572b181cb03d819fac1cdba3252cfe0"
        ),
        "full_solution_corpus_digest": (
            "arc3_full_solution_corpus:"
            "995bbdb3e8323824bdd8ac4a5c3b8f7b64dfffcd2e2618ec87733fc75c1067ce"
        ),
        "game_count": 25,
        "level_count": 183,
        "raw_recording_cache_location": "OUTSIDE_REPOSITORY",
        "recorded_action_count": 11648,
        "replay_x3_report_digest": (
            "hds-arc3-replay-x3:"
            "22b230deae993e9a590214a39e76c40e8b0800d334ad1ca9ba42356dbfb36c80"
        ),
        "source_content_manifest_digest": (
            "hds-source-content-manifest:"
            "3098feb7241e4ea3444b5942ab8ba0371d8168a51f32a1f3d44c0e09db36eda9"
        ),
        "source_recording_count": 25,
    }


def test_committed_canonical_corpus_and_rebuild_evidence_are_bound() -> None:
    artifact_root = (
        REPOSITORY_ROOT
        / "distillation/artifacts/teacher/arc3/ph_d05_v1"
    )
    manifest = json.loads((artifact_root / "manifest.json").read_bytes())
    rebuild = json.loads((artifact_root / "rebuild_x3.json").read_bytes())
    packages = manifest["packages"]
    assert (
        manifest["game_count"],
        manifest["level_count"],
        manifest["recorded_action_count"],
        manifest["canonical_success_prefix_action_count"],
    ) == (25, 183, 11648, 11574)
    assert len(packages) == 25
    for item in packages:
        payload = (artifact_root / item["package_path"]).read_bytes()
        assert len(payload) == item["package_size_bytes"]
        assert hashlib.sha256(payload).hexdigest() == item["package_sha256"]
    assert rebuild["canonical_build_count"] == 3
    assert rebuild["compared_file_count_per_build"] == 27
    assert rebuild["total_byte_mismatch_count"] == 0
    assert rebuild["failed_requirement_ids"] == []
    assert len(rebuild["file_bindings"]) == 27
