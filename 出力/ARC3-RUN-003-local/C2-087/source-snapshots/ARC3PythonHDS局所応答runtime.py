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
