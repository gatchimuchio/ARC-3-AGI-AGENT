"""C2-081 local candidate: expose uncertain native evidence; never select/authorize an action."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

from arc3_visual_hds_base import _action, _api, _bridge, _current_grid, _frame, _runtime

_TARGET = ("公開応答区分",)
_NOTE = "UNCERTAIN native evidence only; no endorsement or action authorization."


def _state(session):
    runtime = _runtime(session)
    runtime.setdefault("cache", {})
    runtime.setdefault("cache_state", None)
    runtime.setdefault("trace", [])
    runtime.setdefault("inspection_sequence", 0)
    runtime.setdefault("action_call_id", "")
    runtime.setdefault("action_model_turn_id", "")
    runtime.setdefault("last_query", None)
    runtime.setdefault("query_receipts", {})
    runtime.setdefault("public_response_rows", [])
    return runtime


def _visibility():
    value = os.environ.get("ARC3_HDS_EVIDENCE_VISIBILITY", "masked")
    if value not in {"masked", "shown"}:
        raise ValueError("evidence visibility must be masked or shown")
    return value


def _event(runtime, kind, step, call_id, **fields):
    runtime["counts"]["order_event:" + kind] += 1
    if len(runtime["trace"]) < 256:
        runtime["trace"].append(
            {
                "sequence": sum(
                    v for k, v in runtime["counts"].items() if k.startswith("order_event:")
                ),
                "event": kind,
                "step": step,
                "tool_call_id": str(call_id)[:100],
                **fields,
            }
        )
    else:
        runtime["counts"]["ordering_trace_truncated"] += 1


def _write(session, runtime):
    try:
        learner = runtime["bridge"]
        payload = {
            "schema": "arc3-python-hds-query-telemetry.v1",
            "visibility": _visibility(),
            "authorization": False,
            "endorsement": False,
            "native_judgment_modified": False,
            "native_scope": "whole_query_original_0.4.2",
            "counts": dict(sorted(runtime["counts"].items())),
            "hds": learner.stats if learner else None,
            "prior": learner.prior_report if learner else None,
            "ordering_trace": runtime["trace"],
            "public_response_rows": runtime["public_response_rows"],
            "response_measurement_revision": "matched-query-before-actual-outcome.v1",
            "past_majority_coverage": "All nonRESET public responses retained, including unqueried preceding outcomes; no future label is included in query evidence.",
            "last_error_type": runtime["last_adapter_error"],
            "raw_boards_coordinates_game_ids_persisted": False,
            "same_tool_call_query_action_is_not_model_reviewed": True,
            "learning_action_or_score_improvement_proven": False,
        }
        path = Path(session.state_path).with_suffix(".visual-hds-query.json")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    except Exception as exc:
        runtime["counts"]["telemetry_write_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__


def _clip(value, depth=0):
    """Bound actual returned fields only; never fill missing evidence with invented zeroes."""
    if type(value) is str:
        return value[:240], len(value) > 240
    if value is None or type(value) in {int, float, bool}:
        return value, False
    if depth >= 6:
        return "OMITTED_DEPTH_LIMIT", True
    if isinstance(value, dict):
        result, truncated = {}, len(value) > 20
        for key, item in list(value.items())[:20]:
            clipped, cut = _clip(item, depth + 1)
            result[str(key)[:80]] = clipped
            truncated |= cut
        return result, truncated
    if isinstance(value, (list, tuple)):
        result, truncated = [], len(value) > 8
        for item in value[:8]:
            clipped, cut = _clip(item, depth + 1)
            result.append(clipped)
            truncated |= cut
        return result, truncated
    return "OMITTED_UNSUPPORTED_NATIVE_TYPE", True


def _native_evidence(native, bridge_result):
    content = getattr(native, "内容", None)
    if not isinstance(content, dict):
        return {
            "native_status": None,
            "native_hold_reasons": None,
            "target_records": None,
            "missing_fields_are_unknown": True,
            "native_capture_available": False,
            "bridge_status": bridge_result.get("bridge_status"),
        }
    records, counts, truncated = {}, {}, False
    for key in ("予測群", "有効原理群", "競合群", "追加観測要求群", "係争中原理群", "識別不能群"):
        rows = content.get(key)
        if not isinstance(rows, (tuple, list)):
            records[key], counts[key] = None, None
            continue
        selected = [
            row
            for row in rows
            if isinstance(row, dict) and tuple(row.get("結果経路", ())) == _TARGET
        ]
        counts[key] = len(selected)
        records[key], cut = _clip(selected)
        truncated |= cut
    holds, cut = _clip(content.get("断定保留理由群"))
    truncated |= cut
    result = {
        "native_status": getattr(native, "状態", None),
        "native_learning_state": content.get("学習成立状態"),
        "native_judgment_scope": "whole_query_original_0.4.2",
        "native_hold_reasons": holds,
        "target_result_path": list(_TARGET),
        "target_records": records,
        "target_record_counts": counts,
        "support_counts": "UNKNOWN_UNLESS_EXPLICITLY_RETURNED_IN_NATIVE_RECORD",
        "missing_fields_are_unknown": True,
        "summary_is_truncated": truncated,
        "native_capture_available": True,
        "bridge_status": bridge_result.get("bridge_status"),
    }
    if len(json.dumps(result, ensure_ascii=False)) > 6000:
        # Keep actual judgment/reasons/counts, but explicitly omit oversized rule detail.
        result["summary_is_truncated"] = True
        result["target_records"] = {key: None if rows else rows for key, rows in records.items()}
        result["target_record_details"] = "OMITTED_RESPONSE_BUDGET"
    return result


def _public_response(session, runtime, status, call_id, evidence=None, **fields):
    visible = _visibility()
    return {
        "executed": False,
        "authorization": False,
        "endorsement": False,
        "recommendation": None,
        "evidence_status": (
            "UNCERTAIN" if evidence and evidence.get("native_capture_available") else "UNAVAILABLE"
        ),
        "note": _NOTE,
        "status": status,
        "public_step": int(session.action_count),
        "tool_call_id": str(call_id)[:100],
        "visibility": visible,
        "evidence": deepcopy(evidence) if visible == "shown" else {"masked": True},
        **fields,
    }


def _strict_candidate(session, request, frame):
    raw = request.get("candidate")
    if isinstance(raw, str):
        raw = {"action": raw}
    if not isinstance(raw, dict) or set(raw) - {"action", "row", "col"}:
        raise ValueError("query expects exactly one action string/object")
    if type(raw.get("action")) is not str:
        raise ValueError("candidate action must be a string")
    if raw["action"].strip().upper() in {"MOUSE", "ACTION6"}:
        row, col = raw.get("row"), raw.get("col")
        if (
            type(row) is not int
            or type(col) is not int
            or not frame.board
            or not 0 <= row < len(frame.board)
            or not 0 <= col < len(frame.board[0])
        ):
            raise ValueError("MOUSE query needs exact integer row/col within the current board")
    elif "row" in raw or "col" in raw:
        raise ValueError("only a MOUSE candidate may carry coordinates")
    normalized, error = session._normalize_actions({"actions": [raw]})
    if error or not normalized or len(normalized) != 1:
        raise ValueError(error or "query requires one candidate")
    action = _action(normalized[0])
    if action.number == 0 or not _api()._legal(frame, action):
        raise ValueError("candidate is not a legal nonRESET action")
    return action


def query_candidate(session, request):
    runtime, call_id = _state(session), str(request.get("tool_call_id", ""))[:100]
    model_turn = str(request.get("model_turn_id", ""))[:100]
    runtime["counts"]["query_helper_calls"] += 1
    try:
        frame = _frame(session.game.current_state, _current_grid(session.game.current_state))
        step = int(session.action_count)
        if type(request.get("expected_step")) is not int or request["expected_step"] != step:
            return _public_response(session, runtime, "stale_public_step", call_id)
        action = _strict_candidate(session, request, frame)
        state_key = (step, frame)
        if runtime["cache_state"] != state_key:
            runtime["cache_state"], runtime["cache"] = state_key, {}
            runtime["query_receipts"] = {}
        hit = action in runtime["cache"]
        if not hit and len(runtime["cache"]) >= 2:
            return _public_response(session, runtime, "distinct_candidate_limit", call_id)
        if hit:
            evidence, status = runtime["cache"][action]
            runtime["counts"]["query_cache_hits"] += 1
        else:
            learner = _bridge(runtime)
            if learner is None:
                return _public_response(session, runtime, "learner_unavailable", call_id)
            captured = []
            original = learner._hds.照会する

            def observe_native(value):
                result = original(value)
                captured.append(result)
                return result

            learner._hds.照会する = observe_native
            try:
                result = learner.query(frame, action)
            finally:
                learner._hds.照会する = original
            evidence = _native_evidence(captured[-1] if captured else None, result)
            status = result.get("bridge_status", "unknown")
            if (
                int(session.action_count),
                _frame(session.game.current_state, _current_grid(session.game.current_state)),
            ) != state_key:
                raise RuntimeError("public_state_changed_during_query")
            runtime["cache"][action] = (evidence, status)
            runtime["counts"]["query_status:" + str(status)] += 1
            runtime["counts"]["query_native:" + str(evidence.get("native_status"))] += 1
        runtime["inspection_sequence"] += 1
        inspection = runtime["inspection_sequence"]
        runtime["last_query"] = {
            "step": step,
            "frame": frame,
            "action": action,
            "tool_call_id": call_id,
            "model_turn_id": model_turn,
            "inspection_id": inspection,
            "public_available_actions": list(frame.available_actions),
            "projected_query_input": _api()._query_content(frame, action),
        }
        runtime["query_receipts"][action] = dict(runtime["last_query"])
        _event(
            runtime,
            "query_returned",
            step,
            call_id,
            inspection_id=inspection,
            model_turn_id=model_turn,
            public_available_actions=list(frame.available_actions),
            projected_query_input=_api()._query_content(frame, action),
            cache_hit=hit,
            native_status=evidence.get("native_status"),
        )
        return _public_response(
            session,
            runtime,
            status,
            call_id,
            evidence,
            inspection_id=inspection,
            cache_hit=hit,
            model_turn_id=model_turn,
        )
    except Exception as exc:
        runtime["counts"]["query_adapter_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
        return _public_response(
            session, runtime, "query_unavailable", call_id, error_type=type(exc).__name__
        )
    finally:
        _write(session, runtime)


def record_action_call(session, request):
    runtime = _state(session)
    call_id = str(request.get("tool_call_id", ""))[:100]
    runtime["action_call_id"] = call_id
    runtime["action_model_turn_id"] = str(request.get("model_turn_id", ""))[:100]
    _event(
        runtime,
        "action_call_requested",
        int(session.action_count),
        call_id,
        model_turn_id=runtime["action_model_turn_id"],
    )
    _write(session, runtime)
    return {"executed": False, "authorization": False, "endorsement": False}


def before_action(session, action, *, public_grid, automatic=False):
    runtime = _state(session)
    runtime["counts"]["actual_action_calls_seen"] += 1
    if automatic or getattr(action.id, "name", "") == "RESET":
        runtime["cache"], runtime["cache_state"], runtime["last_query"] = {}, None, None
        runtime["query_receipts"] = {}
        runtime["counts"]["skipped_RESET_or_automatic"] += 1
        return None
    try:
        before, candidate = _frame(session.game.current_state, public_grid), _action(action)
        _bridge(runtime)  # Learn actual responses even if the model has not queried yet.
        step, last = int(session.action_count), runtime["last_query"]
        matching_cache = runtime["cache_state"] == (step, before)
        receipt = runtime["query_receipts"].get(candidate) if matching_cache else None
        forecast = runtime["cache"].get(candidate) if matching_cache else None
        if last and (last["step"], last["frame"]) == (step, before):
            same_call = last["tool_call_id"] == runtime["action_call_id"]
            known_turns = bool(last["model_turn_id"] and runtime["action_model_turn_id"])
            same_turn = known_turns and last["model_turn_id"] == runtime["action_model_turn_id"]
            runtime["counts"][
                "same_model_response_query_action_unreviewed"
                if same_turn
                else "distinct_model_response_after_query"
                if known_turns
                else "model_response_relation_unknown"
            ] += 1
            runtime["counts"][
                "same_tool_call_query_then_action_unreviewed"
                if same_call
                else "action_after_distinct_tool_call_query"
            ] += 1
            runtime["counts"]["executed_candidate_was_queried"] += int(
                candidate in runtime["cache"]
            )
            _event(
                runtime,
                "action_after_query",
                step,
                runtime["action_call_id"],
                inspection_id=last["inspection_id"],
                latest_context_inspection_id=last["inspection_id"],
                matched_candidate_inspection_id=receipt["inspection_id"] if receipt else None,
                same_tool_call_unreviewed=same_call,
                same_model_response_unreviewed=bool(same_turn),
                model_turn_id=runtime["action_model_turn_id"],
                model_observation_opportunity=bool(known_turns and not same_turn and not same_call),
            )
        return {
            "before": before,
            "action": candidate,
            "step": step,
            "matched_query_receipt": deepcopy(receipt),
            "matched_forecast": deepcopy(forecast[0]) if forecast else None,
        }
    except Exception as exc:
        runtime["counts"]["before_adapter_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
        return None


def after_action(session, action, captured, new_state, *, public_grid, automatic=False):
    runtime = _state(session)
    try:
        if captured is None or automatic or getattr(action.id, "name", "") == "RESET":
            return
        if int(session.action_count) != captured["step"] + 1:
            raise RuntimeError("public_action_step_mismatch")
        after = _frame(new_state, public_grid)
        outcome = _api()._observed_outcome(captured["before"], after)
        runtime["counts"]["public_outcome:" + outcome] += 1
        evidence, receipt = captured["matched_forecast"], captured["matched_query_receipt"]
        records = evidence.get("target_records") if evidence else None
        predictions = records.get("予測群") if isinstance(records, dict) else None
        active = records.get("有効原理群") if isinstance(records, dict) else None
        qualified_values = None
        if (
            isinstance(predictions, list)
            and isinstance(active, list)
            and evidence.get("summary_is_truncated") is False
        ):
            refs = {
                r.get("原理識別子")
                for r in active
                if r.get("状態") == "適用範囲付き暫定原理"
                and r.get("採用状態") == "有効"
                and type(r.get("原理識別子")) is str
                and r["原理識別子"]
            }
            qualified_values = sorted(
                {
                    r["予測値"]
                    for r in predictions
                    if r.get("原理参照") in refs and r.get("予測値") in _api()._OUTCOMES
                }
            )
        row = {
            "public_step_before": captured["step"],
            "public_step_after": int(session.action_count),
            "actual_action_number": captured["action"].number,
            "before_levels_completed": captured["before"].levels_completed,
            "after_levels_completed": after.levels_completed,
            "after_public_state": after.state,
            "before_public_state": captured["before"].state,
            "before_available_actions": list(captured["before"].available_actions),
            "after_available_actions": list(after.available_actions),
            "projected_query_input_at_matching_inspection": receipt["projected_query_input"]
            if receipt
            else None,
            "projected_update_input": {
                **_api()._query_content(captured["before"], captured["action"]),
                "公開応答区分": outcome,
            },
            "observed_public_outcome": outcome,
            "matching_candidate_was_queried_before_action": receipt is not None,
            "matching_inspection_id": receipt["inspection_id"] if receipt else None,
            "query_tool_call_id": receipt["tool_call_id"] if receipt else None,
            "query_model_turn_id": receipt["model_turn_id"] if receipt else None,
            "action_tool_call_id": runtime["action_call_id"],
            "action_model_turn_id": runtime["action_model_turn_id"],
            "native_status_at_query": evidence.get("native_status") if evidence else None,
            "native_active_ref_forecast_values_at_query": qualified_values,
            "native_target_counts_at_query": evidence.get("target_record_counts")
            if evidence
            else None,
            "native_summary_truncated_at_query": evidence.get("summary_is_truncated")
            if evidence
            else None,
            "update_bridge_status": "not_called",
            "endorsement": False,
            "authorization": False,
        }
        if len(runtime["public_response_rows"]) < 80:
            runtime["public_response_rows"].append(row)
        else:
            runtime["counts"]["public_response_rows_truncated"] += 1
        learner = runtime["bridge"]
        if learner is not None:
            result = learner.update(captured["before"], captured["action"], after)
            row["update_bridge_status"] = result.get("bridge_status")
            runtime["counts"]["update_status:" + str(result.get("bridge_status"))] += 1
        runtime["cache"], runtime["cache_state"], runtime["last_query"] = {}, None, None
        runtime["query_receipts"] = {}
    except Exception as exc:
        runtime["counts"]["after_adapter_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
    finally:
        _write(session, runtime)
