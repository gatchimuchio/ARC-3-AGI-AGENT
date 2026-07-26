"""Orchestration-only client for the separate P12 sealed evaluator process."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Mapping, cast

from .generic_types import GenericObservation
from .schema import digest_object

SEALED_CLIENT_VERSION = "arc3-sealed-evaluator-client-v1"


def _parse_observation(value: object) -> GenericObservation:
    if not isinstance(value, Mapping):
        raise TypeError("SEALED_OBSERVATION_MAPPING_REQUIRED")
    render = value.get("render")
    actions = value.get("available_actions")
    effects = value.get("visible_effects", ())
    terminal = value.get("terminal_state")
    progress = value.get("progress_count")
    if not isinstance(render, list) or not render:
        raise TypeError("SEALED_RENDER_INVALID")
    rows: list[tuple[int, ...]] = []
    for row in render:
        if not isinstance(row, list) or any(
            isinstance(cell, bool) or not isinstance(cell, int) for cell in row
        ):
            raise TypeError("SEALED_RENDER_INVALID")
        rows.append(tuple(row))
    if not isinstance(actions, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in actions
    ):
        raise TypeError("SEALED_ACTION_SURFACE_INVALID")
    if not isinstance(effects, list) or any(
        not isinstance(item, str) for item in effects
    ):
        raise TypeError("SEALED_EFFECTS_INVALID")
    if not isinstance(terminal, str):
        raise TypeError("SEALED_TERMINAL_INVALID")
    if isinstance(progress, bool) or not isinstance(progress, int):
        raise TypeError("SEALED_PROGRESS_INVALID")
    observation = GenericObservation(
        signature="sealed-observation:" + digest_object(
            {
                "render": rows,
                "actions": tuple(actions),
                "effects": tuple(effects),
                "terminal": terminal,
                "progress": progress,
            }
        )[:24],
        available_actions=tuple(sorted(set(actions))),
        rendered_layers=(tuple(rows),),
        terminal_state=terminal,
        progress_count=progress,
        visible_effects=tuple(sorted(set(effects))),
    )
    failures = observation.validate()
    if failures:
        raise ValueError(";".join(failures))
    return observation


@dataclass(slots=True)
class SealedEvaluatorSession:
    evaluator_script: Path
    seed: int
    frozen_code_commit: str
    frozen_p_digest: str
    _process: subprocess.Popen[str] = field(init=False, repr=False)
    _stdin: IO[str] = field(init=False, repr=False)
    _stdout: IO[str] = field(init=False, repr=False)
    _handles: tuple[str, ...] = field(default=(), init=False)
    evaluator_digest: str = field(default="", init=False)

    def __post_init__(self) -> None:
        evaluator_script = self.evaluator_script.resolve()
        if not evaluator_script.is_file():
            raise FileNotFoundError(evaluator_script)
        self.evaluator_script = evaluator_script
        if not self.frozen_code_commit or not self.frozen_p_digest:
            raise ValueError("SEALED_FREEZE_BINDING_REQUIRED")
        self._process = subprocess.Popen(
            [sys.executable, str(evaluator_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(evaluator_script.parent),
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("SEALED_PROCESS_PIPE_MISSING")
        self._stdin = self._process.stdin
        self._stdout = self._process.stdout
        result = self._request(
            {
                "request_id": "sealed-initialize:"
                + digest_object(
                    {
                        "seed": self.seed,
                        "code": self.frozen_code_commit,
                        "p": self.frozen_p_digest,
                    }
                )[:24],
                "operation": "initialize",
                "seed": self.seed,
            }
        )
        handles = result.get("handles")
        evaluator_digest = result.get("evaluator_digest")
        if (
            not isinstance(handles, list)
            or len(handles) < 3
            or any(not isinstance(item, str) for item in handles)
            or not isinstance(evaluator_digest, str)
        ):
            raise RuntimeError("SEALED_INITIALIZATION_RESPONSE_INVALID")
        self._handles = tuple(sorted(handles))
        self.evaluator_digest = evaluator_digest

    @property
    def handles(self) -> tuple[str, ...]:
        return self._handles

    def _request(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        self._stdin.write(json.dumps(payload, sort_keys=True) + "\n")
        self._stdin.flush()
        line = self._stdout.readline()
        if not line:
            detail = ""
            if self._process.stderr is not None:
                detail = self._process.stderr.read().strip()
            suffix = ":" + detail[:1000] if detail else ""
            raise RuntimeError("SEALED_EVALUATOR_PROCESS_CLOSED" + suffix)
        response = json.loads(line)
        if not isinstance(response, Mapping):
            raise TypeError("SEALED_RESPONSE_INVALID")
        if response.get("ok") is not True:
            raise RuntimeError("SEALED_EVALUATOR_ERROR:" + str(response.get("error")))
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise TypeError("SEALED_RESULT_INVALID")
        return cast(Mapping[str, object], result)

    def environment(self, handle: str) -> SealedProcessEnvironment:
        if handle not in self._handles:
            raise KeyError(handle)
        return SealedProcessEnvironment(self, handle)

    def close(self) -> None:
        if self._process.poll() is None:
            self._stdin.close()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                self._process.wait(timeout=5)

    def __enter__(self) -> SealedEvaluatorSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass(slots=True)
class SealedProcessEnvironment:
    """Runtime-facing environment; hidden mechanics stay in another process."""

    session: SealedEvaluatorSession = field(repr=False)
    _handle: str = field(repr=False)
    _current: GenericObservation | None = field(default=None, init=False)

    def observe(self) -> GenericObservation:
        if self._current is None:
            raw = self.session._request(
                {
                    "request_id": "sealed-observe:"
                    + digest_object(self._handle)[:24],
                    "operation": "observe",
                    "handle": self._handle,
                }
            )
            self._current = _parse_observation(raw)
        return self._current

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        del payload
        raw = self.session._request(
            {
                "request_id": request_id,
                "operation": "step",
                "handle": self._handle,
                "action_id": action_id,
            }
        )
        self._current = _parse_observation(raw)
        return self._current

    def reset_level(self, *, request_id: str) -> GenericObservation:
        raw = self.session._request(
            {
                "request_id": request_id,
                "operation": "reset_level",
                "handle": self._handle,
            }
        )
        self._current = _parse_observation(raw)
        return self._current


def run_sealed_evaluation(
    *,
    evaluator_script: Path,
    seed: int,
    frozen_code_commit: str,
    frozen_p_digest: str,
    runtime_factory: object,
) -> tuple[object, ...]:
    """Convenience orchestration hook kept untyped at the runtime boundary."""

    if not callable(runtime_factory):
        raise TypeError("SEALED_RUNTIME_FACTORY_REQUIRED")
    reports: list[object] = []
    with SealedEvaluatorSession(
        evaluator_script=evaluator_script,
        seed=seed,
        frozen_code_commit=frozen_code_commit,
        frozen_p_digest=frozen_p_digest,
    ) as session:
        for handle in session.handles:
            runtime = runtime_factory(session.environment(handle))
            run = getattr(runtime, "run", None)
            if not callable(run):
                raise TypeError("SEALED_RUNTIME_RUN_REQUIRED")
            reports.append(run())
    return tuple(reports)


__all__ = [
    "SEALED_CLIENT_VERSION",
    "SealedEvaluatorSession",
    "SealedProcessEnvironment",
    "run_sealed_evaluation",
]
