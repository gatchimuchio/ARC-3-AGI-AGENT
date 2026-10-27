"""C2-085 thin observer over frozen C2-081r2 RPC, learner, policy and receipts."""

from __future__ import annotations

import json

import arc3_python_hds_query_base as _base
from arc3_action6_locality_observer import (
    AREA,
    TARGET,
    EFFECT_VALUES,
    REVISION,
    ObserverBridge,
    component_area,
    effect_class,
    native_locality_evidence,
    query_content,
)

_original_api = _base._api
_original_bridge = _base._bridge
_original_native_evidence = _base._native_evidence
_original_after = _base.after_action


class _ObservedAPI:
    def __getattr__(self, key):
        return getattr(_original_api(), key)

    def _query_content(self, before, action):
        return query_content(_original_api(), before, action)


_observed_api = _ObservedAPI()


def _bridge(runtime):
    value = _original_bridge(runtime)
    if value is not None and not isinstance(value, ObserverBridge):
        value = runtime["bridge"] = ObserverBridge(value)
    return value


def _native_evidence(native, result):
    evidence = _original_native_evidence(native, result)
    if result.get("candidate_action_number") != 6:
        return evidence
    evidence["Action6_locality_evidence"] = native_locality_evidence(native, _base._clip)
    if len(json.dumps(evidence, ensure_ascii=False)) > 6000:
        for section in (evidence, evidence["Action6_locality_evidence"]):
            records = section.get("target_records")
            if isinstance(records, dict):
                section["target_records"] = {
                    key: None if rows else rows for key, rows in records.items()
                }
                section["target_record_details"] = "OMITTED_COMBINED_RESPONSE_BUDGET"
            section["summary_is_truncated"] = True
    return evidence


def _locality_values(evidence):
    if not isinstance(evidence, dict) or evidence.get("summary_is_truncated") is not False:
        return None
    records = evidence.get("target_records")
    if not isinstance(records, dict):
        return None
    rules, predictions = records.get("有効原理群"), records.get("予測群")
    if not isinstance(rules, list) or not isinstance(predictions, list):
        return None
    refs = {
        r["原理識別子"]
        for r in rules
        if r.get("状態") == "適用範囲付き暫定原理"
        and r.get("採用状態") == "有効"
        and isinstance(r.get("原理識別子"), str)
        and r["原理識別子"]
    }
    return sorted(
        {
            r["予測値"]
            for r in predictions
            if r.get("原理参照") in refs
            and isinstance(r.get("予測値"), str)
            and r["予測値"] in EFFECT_VALUES
        }
    )


def after_action(session, action, captured, new_state, *, public_grid, automatic=False):
    _original_after(
        session, action, captured, new_state, public_grid=public_grid, automatic=automatic
    )
    if captured is None or automatic or getattr(action.id, "name", "") == "RESET":
        return
    runtime = _base._state(session)
    try:
        rows = runtime["public_response_rows"]
        if not rows or rows[-1]["public_step_before"] != captured["step"]:
            return
        row = rows[-1]
        row["observer_projection_revision"] = REVISION
        if captured["action"].number == 6:
            after = _base._frame(new_state, public_grid)
            observed = effect_class(captured["before"], captured["action"], after)
            row["observed_Action6_effect_class"] = observed
            row["effect_observation_missing_reason"] = (
                "visible_shape_mismatch_or_empty" if observed is None else None
            )
            row["PRE_target_samecolor4CC_pixel_area"] = component_area(
                captured["before"], captured["action"]
            )
            if observed is not None:
                row["projected_update_input"][TARGET] = observed
            evidence = captured.get("matched_forecast")
            locality = (
                evidence.get("Action6_locality_evidence") if isinstance(evidence, dict) else None
            )
            row["native_linked_Action6_effect_forecast_values_at_query"] = _locality_values(
                locality
            )
            row["native_Action6_target_counts_at_query"] = (
                locality.get("target_record_counts") if isinstance(locality, dict) else None
            )
            row["native_Action6_summary_truncated_at_query"] = (
                locality.get("summary_is_truncated") if isinstance(locality, dict) else None
            )
    except Exception as exc:
        runtime["counts"]["observer_telemetry_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
    finally:
        _base._write(session, runtime)


# Replace callbacks only inside this NEW process-local copy of the frozen R2 module.
# Frozen files/artifacts and original canonical native HDS are never modified.
_base._api = lambda: _observed_api
_base._bridge = _bridge
_base._native_evidence = _native_evidence
before_action = _base.before_action
query_candidate = _base.query_candidate
record_action_call = _base.record_action_call

# C2-087: explicit native game-response learning ablation follows.

import os as _learning_os
from pathlib import Path as _LearningPath

_LEARNING_FLAG = "ARC3_HDS_GAME_RESPONSE_UPDATES"
_observer_bridge_factory = _bridge
_observer_stats_writer = _base._write


def _learning_mode():
    value = _learning_os.environ.get(_LEARNING_FLAG)
    if value not in {"disabled", "enabled"}:
        raise ValueError("C2-087 requires explicit disabled/enabled game-response learning")
    return value


def _learning_bridge(runtime):
    mode = _learning_mode()
    previous = runtime.setdefault("native_game_learning_mode_frozen", mode)
    if previous != mode:
        raise RuntimeError("native game-response learning configuration drift")
    learner = _observer_bridge_factory(runtime)
    if learner is not None and not getattr(learner.core, "_c2087_game_gate_installed", False):
        original = learner.core._call

        def game_learning_gate(kind, content):
            if _learning_mode() != mode:
                raise RuntimeError("native game-response learning configuration drift")
            if kind == "update":
                # This is after the unchanged public lifecycle guards and observer
                # enrichment. Prior5 initialization never uses this game call path.
                runtime["counts"]["game_response_teacher_inputs_computed"] += 1
                if mode == "disabled":
                    runtime["counts"]["game_response_update_expected_disabled"] += 1
                    return learner.core._result(
                        "game_response_update_disabled", operation="update",
                        expected_experimental_skip=True, native_status=None,
                    )
                runtime["counts"]["game_response_update_enabled_requests"] += 1
            return original(kind, content)

        learner.core._call = game_learning_gate
        learner.core._c2087_game_gate_installed = True
    return learner


def _learning_stats_writer(session, runtime):
    _observer_stats_writer(session, runtime)
    try:
        path = _LearningPath(session.state_path).with_suffix(".visual-hds-query.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        mode = runtime.get("native_game_learning_mode_frozen", _learning_mode())
        enabled = mode == "enabled"
        for row in payload.get("public_response_rows", []):
            row["native_game_response_learning_enabled"] = enabled
            row["native_game_update_skip_is_expected"] = (
                not enabled and row.get("update_bridge_status") == "game_response_update_disabled"
            )
        stats = payload.get("hds") or {}
        payload["schema"] = "arc3-python-hds-learning-ablation-telemetry.v1"
        payload["learning_ablation"] = {
            "revision": "native-game-response-learning-only.v1",
            "configuration_flag": _LEARNING_FLAG,
            "frozen_mode": mode,
            "configuration_unchanged": _learning_os.environ.get(_LEARNING_FLAG) == mode,
            "game_response_native_updates_enabled": enabled,
            "disabled_skips_are_expected_not_errors": not enabled,
            "expected_disabled_skip_status": "game_response_update_disabled",
            "prior_records_expected": 5,
            "prior_native_updates_attempted": stats.get("prior_updates_attempted"),
            "prior_native_updates_succeeded": stats.get("prior_updates_succeeded"),
            "query_renderer_source": "actual native return only; no response-row teacher history",
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _learning_os.replace(temporary, path)
    except Exception as exc:
        runtime["counts"]["learning_telemetry_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__


_base._bridge = _learning_bridge
_base._write = _learning_stats_writer
_bridge = _learning_bridge
