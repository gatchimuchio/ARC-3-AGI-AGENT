from __future__ import annotations

import ast
import copy
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "検証")]

import ARC3視覚HDS候補構築 as builder
from ARC3視覚HDS接続候補 import (
    PublicAction,
    PublicFrame,
    _OUTCOMES,
    _observed_outcome,
    render_hint,
)


def _state(board, *, state="NOT_FINISHED", levels=0):
    return types.SimpleNamespace(
        frame=types.SimpleNamespace(data=board),
        raw=types.SimpleNamespace(state=types.SimpleNamespace(name=state)),
        levels_completed=levels,
        available_actions=(6,),
    )


def _action(name="ACTION6"):
    return types.SimpleNamespace(id=types.SimpleNamespace(name=name), data={"x": 0, "y": 0})


class VisualHDSBuildContractTests(unittest.TestCase):
    def _runtime(self, bridge_type):
        module = types.ModuleType("isolated_visual_hds_test_runtime")
        exec(compile(builder.RUNTIME_SOURCE, "runtime", "exec"), module.__dict__)
        module._API = types.SimpleNamespace(
            PublicFrame=PublicFrame,
            PublicAction=PublicAction,
            VisualHDSBridge=bridge_type,
            _observed_outcome=_observed_outcome,
            _OUTCOMES=_OUTCOMES,
            render_hint=render_hint,
        )
        return module

    def _bridge(self, events, *, status="queried", constructor_error=False):
        class Bridge:
            def __init__(self, **kwargs):
                if constructor_error:
                    raise RuntimeError("synthetic constructor failure")
                self.stats = {"queries_attempted": 0, "updates_attempted": 0}
                self.prior_report = {"loaded_count": 5, "action_authorization": False}

            def query(self, before, candidate):
                self.stats["queries_attempted"] += 1
                events.append(("query", before, candidate))
                return {
                    "bridge_status": status,
                    "native_status": "断定保留",
                    "authorization": False,
                }

            def update(self, before, candidate, after):
                self.stats["updates_attempted"] += 1
                events.append(("update", before, candidate, after))
                return {
                    "bridge_status": "updated",
                    "native_status": "断定保留",
                    "authorization": False,
                }

        return Bridge

    def _session(self, folder):
        return types.SimpleNamespace(
            state_path=Path(folder) / "public-session.json",
            action_count=0,
            game=types.SimpleNamespace(current_state=_state([[0, 1], [1, 0]])),
        )

    def _env(self, mode):
        return patch.dict(
            os.environ,
            {
                "ARC3_VISUAL_HDS_MODE": mode,
                "ARC3_VISUAL_HDS_UPDATE_BUDGET": "80",
                "ARC3_VISUAL_HDS_QUERY_BUDGET": "80",
                "ARC3_VISUAL_HDS_SECONDS_BUDGET": "120",
            },
        )

    def test_source_patch_queries_before_actual_action_and_updates_before_history(self):
        source = (builder.SOURCE_ROOT / builder.SOLVER_REL).read_bytes()
        patched = builder._patch_solver(source)
        tree = ast.parse(patched)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_execute_action"
        )
        calls = {}
        for node in ast.walk(method):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in {
                    "_arc3_hds_before_action",
                    "execute_action",
                    "_arc3_hds_after_action",
                    "append",
                }:
                    calls.setdefault(name, []).append(node.lineno)
        self.assertEqual(len(calls["_arc3_hds_before_action"]), 1)
        self.assertEqual(len(calls["_arc3_hds_after_action"]), 1)
        self.assertLess(calls["_arc3_hds_before_action"][0], calls["execute_action"][0])
        self.assertLess(calls["execute_action"][0], calls["_arc3_hds_after_action"][0])
        self.assertLess(calls["_arc3_hds_after_action"][0], min(calls["append"]))
        with self.assertRaises(ValueError):
            builder._patch_solver(source + b"\n# unreviewed source drift\n")

    def test_off_mode_does_not_import_or_construct_hds(self):
        runtime = self._runtime(self._bridge([]))
        with (
            tempfile.TemporaryDirectory() as folder,
            self._env("off"),
            patch.object(runtime, "_api", side_effect=AssertionError("off imported HDS")),
        ):
            session = self._session(folder)
            captured = runtime.before_action(session, _action(), public_grid=((0, 1), (1, 0)))
            session.action_count = 1
            runtime.after_action(
                session, _action(), captured, _state([[1, 1], [1, 0]]), public_grid=((1, 1), (1, 0))
            )
            telemetry = json.loads(
                session.state_path.with_suffix(".visual-hds.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(telemetry["hds"])
            self.assertEqual(telemetry["counts"], {"actual_action_calls_seen": 1})

    def test_batched_steps_are_individual_and_fatal_response_survives_auto_reset(self):
        events = []
        runtime = self._runtime(self._bridge(events))
        with tempfile.TemporaryDirectory() as folder, self._env("shadow"):
            session = self._session(folder)
            for state_name in ("NOT_FINISHED", "GAME_OVER"):
                before = session.game.current_state
                captured = runtime.before_action(session, _action(), public_grid=before.frame.data)
                events.append(("actual_execute",))
                session.action_count += 1
                fatal_or_after = _state([[1, 1], [1, 0]], state=state_name)
                # An independently visible reset state must not replace the explicit fatal response.
                session.game.current_state = (
                    _state([[0, 1], [1, 0]]) if state_name == "GAME_OVER" else fatal_or_after
                )
                runtime.after_action(
                    session,
                    _action(),
                    captured,
                    fatal_or_after,
                    public_grid=fatal_or_after.frame.data,
                )
            self.assertEqual([e[0] for e in events], ["query", "actual_execute", "update"] * 2)
            self.assertEqual(events[-1][-1].state, "GAME_OVER")
            self.assertEqual(
                session._arc3_visual_hds_runtime["counts"]["public_outcome:GAME_OVER"], 1
            )
            before_events = len(events)
            runtime.before_action(session, _action("RESET"), public_grid=(), automatic=True)
            self.assertEqual(len(events), before_events)

    def test_constructor_or_lazy_import_failure_preserves_original_action_path(self):
        for fail_import in (False, True):
            with (
                self.subTest(fail_import=fail_import),
                tempfile.TemporaryDirectory() as folder,
                self._env("shadow"),
            ):
                runtime = self._runtime(self._bridge([], constructor_error=True))
                if fail_import:
                    runtime._api = lambda: (_ for _ in ()).throw(ImportError("synthetic"))
                session = self._session(folder)
                captured = runtime.before_action(session, _action(), public_grid=((0, 1), (1, 0)))
                payload = {"executed": True, "game_over": True}
                session.action_count += 1
                runtime.after_action(
                    session,
                    _action(),
                    captured,
                    _state([[0, 1], [1, 0]], state="GAME_OVER"),
                    public_grid=((0, 1), (1, 0)),
                )
                self.assertIsNone(captured)
                self.assertEqual(payload, {"executed": True, "game_over": True})
                self.assertEqual(
                    session._arc3_visual_hds_runtime["counts"]["before_adapter_errors"], 1
                )

    def test_error_and_exhaustion_results_do_not_authorize_or_stop_actions(self):
        for status in ("hds_error", "budget_exhausted"):
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory() as folder,
                self._env("shadow"),
            ):
                events = []
                runtime = self._runtime(self._bridge(events, status=status))
                session = self._session(folder)
                captured = runtime.before_action(session, _action(), public_grid=((0, 1), (1, 0)))
                session.action_count += 1
                runtime.after_action(
                    session,
                    _action(),
                    captured,
                    _state([[1, 1], [1, 0]]),
                    public_grid=((1, 1), (1, 0)),
                )
                self.assertEqual([e[0] for e in events], ["query", "update"])
                telemetry = json.loads(
                    session.state_path.with_suffix(".visual-hds.json").read_text(encoding="utf-8")
                )
                self.assertIs(telemetry["authorization"], False)
                self.assertIs(telemetry["continue_visual_solver"], True)
                for key in ('"board"', '"x"', '"y"', '"game_id"'):
                    self.assertNotIn(key, json.dumps(telemetry))

    def test_action_step_mismatch_never_updates_unmatched_response(self):
        events = []
        runtime = self._runtime(self._bridge(events))
        with tempfile.TemporaryDirectory() as folder, self._env("shadow"):
            session = self._session(folder)
            captured = runtime.before_action(session, _action(), public_grid=((0, 1), (1, 0)))
            session.action_count += 2
            runtime.after_action(
                session, _action(), captured, _state([[1, 1], [1, 0]]), public_grid=((1, 1), (1, 0))
            )
            self.assertEqual([e[0] for e in events], ["query"])
            self.assertEqual(
                session._arc3_visual_hds_runtime["counts"]["public_action_step_mismatch"], 1
            )

    def test_hints_mode_is_rejected_before_any_build_or_runtime_learning(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            builder.build(Path(folder) / "rejected", mode="hints", kernel_id="example/unused-draft")
        runtime = self._runtime(self._bridge([]))
        with self._env("hints"), self.assertRaises(ValueError):
            runtime._mode()

    def test_native_global_HOLD_target_forecast_is_measured_separately_from_hint(self):
        events = []
        base_bridge = self._bridge(events)

        class Bridge(base_bridge):
            def query(self, before, candidate):
                result = super().query(before, candidate)
                result.update(
                    native_status="断定保留",
                    relevant_conflict_count=0,
                    relevant_observation_request_count=0,
                    summary_is_truncated=False,
                    native_hold_reasons=["unrelated result paths unresolved"],
                    predictions=[{"value": "盤面変化", "principle_ref": "observed-rule"}],
                    rule_evidence=[
                        {
                            "principle_ref": "observed-rule",
                            "native_state": "適用範囲付き暫定原理",
                            "native_adoption_state": "有効",
                        }
                    ],
                )
                return result

        runtime = self._runtime(Bridge)
        with tempfile.TemporaryDirectory() as folder, self._env("shadow"):
            session = self._session(folder)
            captured = runtime.before_action(session, _action(), public_grid=((0, 1), (1, 0)))
            session.action_count += 1
            runtime.after_action(
                session,
                _action(),
                captured,
                _state([[1, 1], [1, 0]]),
                public_grid=((1, 1), (1, 0)),
            )
            counts = session._arc3_visual_hds_runtime["counts"]
            self.assertEqual(counts["query_native:断定保留"], 1)
            self.assertEqual(
                counts["query_native_hold_reason:unrelated result paths unresolved"], 1
            )
            self.assertEqual(counts["target_qualified_unique_predictions_observed"], 1)
            self.assertEqual(counts["target_qualified_unique_prediction_matches"], 1)
            self.assertEqual(counts["target_qualified_unique_native_status:断定保留"], 1)
            self.assertEqual(counts["supported_unique_predictions_observed"], 0)
            self.assertEqual([row[0] for row in events], ["query", "update"])

    def test_target_measurement_rejects_conflict_request_truncation_and_unsupported_refs(self):
        runtime = self._runtime(self._bridge([]))
        good = {
            "bridge_status": "queried",
            "native_status": "断定保留",
            "authorization": False,
            "relevant_conflict_count": 0,
            "relevant_observation_request_count": 0,
            "summary_is_truncated": False,
            "predictions": [{"value": "盤面変化", "principle_ref": "active-rule"}],
            "rule_evidence": [
                {
                    "principle_ref": "active-rule",
                    "native_state": "適用範囲付き暫定原理",
                    "native_adoption_state": "有効",
                }
            ],
        }
        self.assertEqual(runtime._target_forecast(good), (None, {"盤面変化"}))
        cases = (
            {"bridge_status": "hds_error"},
            {"native_status": "unknown"},
            {"authorization": True},
            {"relevant_conflict_count": 1},
            {"relevant_observation_request_count": 1},
            {"summary_is_truncated": True},
            {"predictions": [{"value": "盤面変化", "principle_ref": "unrelated-rule"}]},
            {"rule_evidence": []},
        )
        for change in cases:
            with self.subTest(change=change):
                reason, values = runtime._target_forecast({**good, **change})
                self.assertIsInstance(reason, str)
                self.assertFalse(values)

    def test_real_native_HOLD_probe_outcomes_qualify_without_rendering_or_mutation(self):
        path = ROOT / "運用/証拠/ARC26-UNIFIED/C2-078_synthetic-learning-probe.json"
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "b11ca86bb4cb8229accf20ba5b95863cf10d50911dcfabc3cd269dff0b3654a3",
        )
        probe = json.loads(raw)
        runtime = self._runtime(self._bridge([]))
        expected = {1: {"盤面変化"}, 2: {"可視変化なし"}}
        for row in probe["queries"]:
            with self.subTest(action=row["action_number"]):
                result = row["bridge_result"]
                frozen = json.dumps(result, ensure_ascii=False, sort_keys=True)
                self.assertEqual(result["native_status"], "断定保留")
                self.assertEqual(row["rendered_hint"], "")
                self.assertEqual(
                    runtime._target_forecast(result), (None, expected[row["action_number"]])
                )
                self.assertEqual(json.dumps(result, ensure_ascii=False, sort_keys=True), frozen)

    def test_actual_patched_execute_method_keeps_fatal_payload_and_original_history(self):
        states = Enum("PublicState", "NOT_FINISHED GAME_OVER WIN")
        source = (builder.SOURCE_ROOT / builder.SOLVER_REL).read_bytes()

        def execute(raw, runtime, folder, events):
            method = next(
                node
                for node in ast.walk(ast.parse(raw))
                if isinstance(node, ast.FunctionDef) and node.name == "_execute_action"
            )
            tree = ast.Module(
                body=[
                    ast.ImportFrom(
                        module="__future__", names=[ast.alias(name="annotations")], level=0
                    ),
                    method,
                ],
                type_ignores=[],
            )
            ast.fix_missing_locations(tree)
            action = _action()
            namespace = {
                "copy": copy,
                "arcengine": types.SimpleNamespace(
                    GameAction=types.SimpleNamespace(ACTION6=action.id), GameState=states
                ),
                "_grid_from_state": lambda state: tuple(tuple(row) for row in state.frame.data),
                "_level_number": lambda game: 1,
                "_format_action_display": lambda name, data: name,
                "_interior_gameplay_changed": lambda before, after: before != after,
                "_engine_action_names": lambda game: ["ACTION6"],
                "_model_mouse_action_data": lambda data: dict(data),
                "to_model_actions": lambda names: names,
                "Frame": lambda **kwargs: types.SimpleNamespace(**kwargs),
                "HistoryEntry": lambda **kwargs: types.SimpleNamespace(**kwargs),
                "ANIMATION_ENABLED": False,
                "_arc3_hds_before_action": runtime.before_action,
                "_arc3_hds_after_action": runtime.after_action,
            }
            exec(compile(tree, "isolated-real-execute-method", "exec"), namespace)
            session = self._session(folder)
            session.game.number_of_levels = 1
            session.game.current_state.raw.state = states.NOT_FINISHED
            fatal = _state([[1, 1], [1, 0]])
            fatal.raw.state = states.GAME_OVER
            fatal.just_won_level = False

            def actual_execute(_action_input, **kwargs):
                events.append(("actual_execute",))
                session.action_count += 1
                session.game.current_state = _state([[0, 1], [1, 0]])
                session.game.current_state.raw.state = states.NOT_FINISHED
                return fatal

            session.game.execute_action = actual_execute
            session.history_entries = []
            session.timing_payload = lambda: {}
            session.write_runtime_state = lambda: None
            session._append_action_viewer_event = lambda *args: None
            session.write_viewer_payload = lambda: None
            payload = namespace["_execute_action"](
                session, action, batch_index=1, batch_size=2, generated_tokens=0
            )
            return payload, session

        for mode, constructor_error in (("off", False), ("shadow", False), ("shadow", True)):
            with (
                self.subTest(mode=mode, constructor_error=constructor_error),
                tempfile.TemporaryDirectory() as folder,
                self._env(mode),
            ):
                events = []
                runtime = self._runtime(self._bridge(events, constructor_error=constructor_error))
                baseline, baseline_session = execute(source, runtime, folder, [])
                patched, patched_session = execute(
                    builder._patch_solver(source), runtime, folder, events
                )
                self.assertEqual(patched, baseline)
                self.assertIs(patched["game_over"], True)
                self.assertEqual(patched["state"], "GAME_OVER")
                self.assertEqual(patched_session.history_entries, baseline_session.history_entries)
                if mode == "shadow" and not constructor_error:
                    self.assertEqual(
                        [item[0] for item in events], ["query", "actual_execute", "update"]
                    )
                    self.assertEqual(events[-1][-1].state, "GAME_OVER")
                else:
                    self.assertEqual([item[0] for item in events], ["actual_execute"])


if __name__ == "__main__":
    unittest.main()
