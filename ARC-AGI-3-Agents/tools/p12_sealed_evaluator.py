"""Separate-process sealed evaluator for P12.

The coordinator may launch this file only after the runtime P/code digest has
been frozen. The runtime receives rendered observations and legal actions over
JSON lines; hidden mechanics never cross the process boundary.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from typing import Mapping


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True)
class _World:
    actions: tuple[int, ...]
    winning_ordinals: tuple[int, ...]
    required_progress: int
    failure_ordinals: tuple[int, ...] = ()
    progress: int = 0
    state: str = "NOT_FINISHED"
    last_effects: tuple[str, ...] = ()
    seen: dict[str, dict[str, object]] = field(default_factory=dict)

    def observation(self) -> dict[str, object]:
        matrix = [[0 for _ in range(7)] for _ in range(7)]
        matrix[1][1] = 2
        matrix[1][5] = 3
        matrix[5][1] = 4
        matrix[5][5] = 5
        for index in range(min(self.progress, 5)):
            matrix[3][index + 1] = 8
        body = {
            "render": matrix,
            "available_actions": list(self.actions),
            "terminal_state": self.state,
            "progress_count": self.progress,
            "visible_effects": list(self.last_effects),
        }
        return {"signature": _digest(body), **body}

    def step(self, action_id: int, request_id: str) -> dict[str, object]:
        cached = self.seen.get(request_id)
        if cached is not None:
            return cached
        if self.state != "NOT_FINISHED":
            raise RuntimeError("SEALED_TERMINAL_STEP")
        if action_id not in self.actions:
            raise ValueError("SEALED_INVALID_ACTION")
        ordinal = self.actions.index(action_id)
        if ordinal in self.failure_ordinals:
            self.state = "GAME_OVER"
            self.last_effects = ("IRREVERSIBLE_FAILURE",)
        else:
            expected = self.winning_ordinals[
                self.progress % len(self.winning_ordinals)
            ]
            if ordinal == expected:
                self.progress += 1
                self.last_effects = (
                    "LEVEL_PROGRESS",
                    "VISIBLE_STATE_CHANGE",
                )
                if self.progress >= self.required_progress:
                    self.state = "WIN"
                    self.last_effects = (
                        "LEVEL_PROGRESS",
                        "VISIBLE_STATE_CHANGE",
                        "WIN_TERMINAL",
                    )
            else:
                self.last_effects = ("NO_VISIBLE_CHANGE",)
        result = self.observation()
        self.seen[request_id] = result
        return result

    def reset(self, request_id: str) -> dict[str, object]:
        cached = self.seen.get(request_id)
        if cached is not None:
            return cached
        if self.state != "GAME_OVER":
            raise RuntimeError("SEALED_RESET_WITHOUT_FAILURE")
        self.state = "NOT_FINISHED"
        self.last_effects = ("LEVEL_RESET",)
        result = self.observation()
        self.seen[request_id] = result
        return result


def _worlds(seed: int) -> dict[str, _World]:
    def action_surface(index: int, count: int) -> tuple[int, ...]:
        actions: set[int] = set()
        nonce = 0
        while len(actions) < count:
            material = hashlib.sha256(
                f"{seed}:{index}:action:{nonce}".encode("utf-8")
            ).digest()
            actions.add(1 + int.from_bytes(material[:4], "big") % 4095)
            nonce += 1
        return tuple(sorted(actions))

    specifications: list[
        tuple[tuple[int, ...], tuple[int, ...], int, tuple[int, ...]]
    ] = []
    for index, action_count in enumerate((3, 4, 5)):
        actions = action_surface(index, action_count)
        choice_material = hashlib.sha256(
            f"{seed}:{index}:mechanism".encode("utf-8")
        ).digest()
        winning = (choice_material[0] % action_count,)
        failure_candidates = tuple(
            ordinal
            for ordinal in range(action_count)
            if ordinal != winning[0]
        )
        failure = (
            (failure_candidates[choice_material[1] % len(failure_candidates)],)
            if index == 1
            else ()
        )
        specifications.append(
            (actions, winning, 2 + choice_material[2] % 2, failure)
        )
    return {
        "sealed-handle:" + _digest((seed, index))[:16]: _World(
            actions=tuple(sorted(actions)),
            winning_ordinals=winning,
            required_progress=required,
            failure_ordinals=failure,
        )
        for index, (actions, winning, required, failure) in enumerate(
            specifications
        )
    }


def _response(
    *,
    request_id: object,
    result: object | None = None,
    error: str | None = None,
) -> None:
    payload = {
        "request_id": request_id,
        "ok": error is None,
        "result": result,
        "error": error,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def main() -> int:
    worlds: dict[str, _World] | None = None
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            if not isinstance(request, Mapping):
                raise TypeError("SEALED_REQUEST_INVALID")
            request_id = request.get("request_id")
            operation = request.get("operation")
            if operation == "initialize":
                seed = request.get("seed")
                if isinstance(seed, bool) or not isinstance(seed, int):
                    raise TypeError("SEALED_SEED_INVALID")
                worlds = _worlds(seed)
                _response(
                    request_id=request_id,
                    result={
                        "handles": sorted(worlds),
                        "evaluator_digest": _digest(
                            {
                                "seed": seed,
                                "handles": sorted(worlds),
                                "process": "separate",
                            }
                        ),
                    },
                )
                continue
            if worlds is None:
                raise RuntimeError("SEALED_NOT_INITIALIZED")
            handle = request.get("handle")
            if not isinstance(handle, str) or handle not in worlds:
                raise KeyError("SEALED_HANDLE_INVALID")
            world = worlds[handle]
            if operation == "observe":
                result = world.observation()
            elif operation == "step":
                action_id = request.get("action_id")
                if isinstance(action_id, bool) or not isinstance(action_id, int):
                    raise TypeError("SEALED_ACTION_INVALID")
                if not isinstance(request_id, str):
                    raise TypeError("SEALED_REQUEST_ID_INVALID")
                result = world.step(action_id, request_id)
            elif operation == "reset_level":
                if not isinstance(request_id, str):
                    raise TypeError("SEALED_REQUEST_ID_INVALID")
                result = world.reset(request_id)
            else:
                raise ValueError("SEALED_OPERATION_INVALID")
            _response(request_id=request_id, result=result)
        except Exception as error:
            request_id = (
                request.get("request_id")
                if "request" in locals() and isinstance(request, Mapping)
                else None
            )
            _response(
                request_id=request_id,
                error=f"{type(error).__name__}:{error}",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
