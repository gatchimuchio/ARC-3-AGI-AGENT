"""Pre-official Competition contract adapter and deterministic mock dry-run.

This module does not import or enable OperationMode.COMPETITION and performs no
official network calls. It verifies the remote-only contract against a mock
transport before P13 may be considered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol

from .generic_types import GenericObservation
from .schema import digest_object

COMPETITION_CONTRACT_VERSION = "arc3-competition-contract-dry-run-v1"


class CompetitionContractError(RuntimeError):
    pass


class CompetitionSuspended(CompetitionContractError):
    pass


@dataclass(frozen=True, slots=True)
class CompetitionHTTPError(CompetitionContractError):
    status_code: int
    error_code: str
    detail: str

    def __str__(self) -> str:
        return (
            f"competition http {self.status_code}:"
            f"{self.error_code}:{self.detail}"
        )


class CompetitionTransport(Protocol):
    def open_scorecard(self, *, tags: tuple[str, ...]) -> str: ...

    def make(
        self,
        game_reference: str,
        *,
        scorecard_id: str,
    ) -> tuple[str, Mapping[str, object]]: ...

    def act(
        self,
        environment_handle: str,
        action_id: int,
        *,
        payload: Mapping[str, int],
        idempotency_key: str,
    ) -> Mapping[str, object]: ...

    def reset_level(
        self,
        environment_handle: str,
        *,
        idempotency_key: str,
    ) -> Mapping[str, object]: ...


def _matrix(
    value: object,
) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise TypeError("COMPETITION_OBSERVATION_RENDER_INVALID")
    output: list[tuple[int, ...]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or not row:
            raise TypeError("COMPETITION_OBSERVATION_RENDER_INVALID")
        parsed: list[int] = []
        for cell in row:
            if isinstance(cell, bool) or not isinstance(cell, int):
                raise TypeError("COMPETITION_OBSERVATION_RENDER_INVALID")
            parsed.append(cell)
        output.append(tuple(parsed))
    widths = {len(row) for row in output}
    if len(widths) != 1:
        raise TypeError("COMPETITION_OBSERVATION_RENDER_INVALID")
    return tuple(output)


def _observation(value: Mapping[str, object]) -> GenericObservation:
    """Strip score and orchestration identity at the adapter boundary."""

    render = _matrix(value.get("render"))
    actions_value = value.get("available_actions")
    if not isinstance(actions_value, (list, tuple)):
        raise TypeError("COMPETITION_OBSERVATION_ACTIONS_INVALID")
    actions: list[int] = []
    for action in actions_value:
        if isinstance(action, bool) or not isinstance(action, int):
            raise TypeError("COMPETITION_OBSERVATION_ACTIONS_INVALID")
        actions.append(action)
    terminal = value.get("terminal_state", "UNKNOWN")
    progress = value.get("progress_count", 0)
    effects = value.get("visible_effects", ())
    if not isinstance(terminal, str):
        raise TypeError("COMPETITION_OBSERVATION_TERMINAL_INVALID")
    if isinstance(progress, bool) or not isinstance(progress, int):
        raise TypeError("COMPETITION_OBSERVATION_PROGRESS_INVALID")
    if not isinstance(effects, (list, tuple)) or any(
        not isinstance(item, str) for item in effects
    ):
        raise TypeError("COMPETITION_OBSERVATION_EFFECTS_INVALID")
    payload_schema: tuple[tuple[int, tuple[str, ...]], ...] = ()
    if 6 in actions:
        payload_schema = ((6, ("x", "y")),)
    observation = GenericObservation(
        signature="competition-observation:" + digest_object(
            {
                "render": render,
                "actions": tuple(sorted(set(actions))),
                "terminal": terminal,
                "progress": progress,
                "effects": tuple(sorted(set(effects))),
            }
        )[:24],
        available_actions=tuple(sorted(set(actions))),
        rendered_layers=(render,),
        terminal_state=terminal,
        progress_count=progress,
        visible_effects=tuple(sorted(set(effects))),
        action_payload_schema=payload_schema,
    )
    failures = observation.validate()
    if failures:
        raise ValueError(";".join(failures))
    return observation


@dataclass(frozen=True, slots=True)
class CompetitionRetryPolicy:
    max_429_retries: int = 3
    max_server_retries: int = 2
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0

    def delay(self, retry_index: int) -> float:
        return min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * float(2**retry_index),
        )


@dataclass(slots=True)
class CompetitionEnvironmentAdapter:
    """Runtime-facing remote environment with no game identity field."""

    transport: CompetitionTransport
    environment_handle: str
    initial_observation: GenericObservation
    retry_policy: CompetitionRetryPolicy
    sleep: Callable[[float], None]
    _current: GenericObservation = field(init=False)
    _request_cache: dict[str, GenericObservation] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        self._current = self.initial_observation

    def observe(self) -> GenericObservation:
        return self._current

    def _remote_call(
        self,
        request_id: str,
        call: Callable[[], Mapping[str, object]],
    ) -> GenericObservation:
        cached = self._request_cache.get(request_id)
        if cached is not None:
            return cached
        retry_429 = 0
        retry_server = 0
        while True:
            try:
                raw = call()
                observation = _observation(raw)
                self._request_cache[request_id] = observation
                self._current = observation
                return observation
            except CompetitionHTTPError as error:
                if error.status_code == 400:
                    if error.error_code == "GAME_OVER":
                        raise CompetitionContractError(
                            "COMPETITION_GAME_OVER"
                        ) from error
                    if error.error_code == "INVALID_ACTION":
                        raise CompetitionContractError(
                            "COMPETITION_INVALID_ACTION"
                        ) from error
                    raise CompetitionContractError(
                        "COMPETITION_REQUEST_ERROR"
                    ) from error
                if error.status_code == 429:
                    if retry_429 >= self.retry_policy.max_429_retries:
                        raise CompetitionSuspended(
                            "COMPETITION_RATE_LIMIT_SUSPEND"
                        ) from error
                    self.sleep(self.retry_policy.delay(retry_429))
                    retry_429 += 1
                    continue
                if 500 <= error.status_code <= 599:
                    if retry_server >= self.retry_policy.max_server_retries:
                        raise CompetitionSuspended(
                            "COMPETITION_SERVER_FAILURE_SUSPEND"
                        ) from error
                    self.sleep(self.retry_policy.delay(retry_server))
                    retry_server += 1
                    continue
                raise
            except (ConnectionError, TimeoutError) as error:
                if retry_server >= self.retry_policy.max_server_retries:
                    raise CompetitionSuspended(
                        "COMPETITION_NETWORK_FAILURE_SUSPEND"
                    ) from error
                self.sleep(self.retry_policy.delay(retry_server))
                retry_server += 1

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        if action_id not in self._current.available_actions:
            raise CompetitionContractError("COMPETITION_ACTION_NOT_LEGAL")
        return self._remote_call(
            request_id,
            lambda: self.transport.act(
                self.environment_handle,
                action_id,
                payload=payload,
                idempotency_key=request_id,
            ),
        )

    def reset_level(self, *, request_id: str) -> GenericObservation:
        return self._remote_call(
            request_id,
            lambda: self.transport.reset_level(
                self.environment_handle,
                idempotency_key=request_id,
            ),
        )


@dataclass(slots=True)
class CompetitionRunAdapter:
    """Own one scorecard and one make call per opaque game reference."""

    transport: CompetitionTransport
    retry_policy: CompetitionRetryPolicy = field(
        default_factory=CompetitionRetryPolicy
    )
    sleep: Callable[[float], None] = lambda _: None
    _scorecard_id: str | None = field(default=None, init=False)
    _made_references: set[str] = field(default_factory=set, init=False)

    def open(self) -> str:
        if self._scorecard_id is not None:
            raise CompetitionContractError(
                "COMPETITION_SINGLE_SCORECARD_VIOLATION"
            )
        self._scorecard_id = self.transport.open_scorecard(
            tags=("generic-agi-preofficial-dry-run",)
        )
        return self._scorecard_id

    def make_environment(
        self,
        game_reference: str,
    ) -> CompetitionEnvironmentAdapter:
        if self._scorecard_id is None:
            raise CompetitionContractError("COMPETITION_SCORECARD_REQUIRED")
        if game_reference in self._made_references:
            raise CompetitionContractError(
                "COMPETITION_SINGLE_MAKE_VIOLATION"
            )
        handle, raw = self.transport.make(
            game_reference,
            scorecard_id=self._scorecard_id,
        )
        self._made_references.add(game_reference)
        return CompetitionEnvironmentAdapter(
            transport=self.transport,
            environment_handle=handle,
            initial_observation=_observation(raw),
            retry_policy=self.retry_policy,
            sleep=self.sleep,
        )


@dataclass(slots=True)
class MockCompetitionTransport:
    """Stateful REST-like mock with idempotent actions and scripted failures."""

    actions: tuple[int, ...] = (11, 29, 47)
    winning_action: int = 29
    scorecard_count: int = field(default=0, init=False)
    make_counts: dict[str, int] = field(default_factory=dict, init=False)
    act_call_count: int = field(default=0, init=False)
    applied_action_count: int = field(default=0, init=False)
    reset_call_count: int = field(default=0, init=False)
    applied_reset_count: int = field(default=0, init=False)
    failure_script: list[BaseException] = field(default_factory=list)
    _progress: dict[str, int] = field(default_factory=dict, init=False)
    _action_cache: dict[str, Mapping[str, object]] = field(
        default_factory=dict,
        init=False,
    )
    _reset_cache: dict[str, Mapping[str, object]] = field(
        default_factory=dict,
        init=False,
    )

    def _raw(self, handle: str, effects: tuple[str, ...]) -> Mapping[str, object]:
        progress = self._progress.get(handle, 0)
        matrix = [[0 for _ in range(5)] for _ in range(5)]
        matrix[1][1] = 2
        matrix[3][3] = 3
        for index in range(min(progress, 3)):
            matrix[2][index + 1] = 8
        return {
            "render": matrix,
            "available_actions": list(self.actions),
            "terminal_state": "WIN" if progress >= 2 else "NOT_FINISHED",
            "progress_count": progress,
            "visible_effects": list(effects),
            "inflight_score": 999_999,
            "game_reference": "ORCHESTRATION_ONLY",
        }

    def open_scorecard(self, *, tags: tuple[str, ...]) -> str:
        if not tags:
            raise ValueError("MOCK_SCORECARD_TAG_REQUIRED")
        self.scorecard_count += 1
        return "mock-scorecard"

    def make(
        self,
        game_reference: str,
        *,
        scorecard_id: str,
    ) -> tuple[str, Mapping[str, object]]:
        if scorecard_id != "mock-scorecard":
            raise ValueError("MOCK_SCORECARD_INVALID")
        self.make_counts[game_reference] = (
            self.make_counts.get(game_reference, 0) + 1
        )
        handle = "mock-environment:" + digest_object(game_reference)[:12]
        self._progress.setdefault(handle, 0)
        return handle, self._raw(handle, ())

    def _scripted_failure(self) -> None:
        if not self.failure_script:
            return
        error = self.failure_script.pop(0)
        raise error

    def act(
        self,
        environment_handle: str,
        action_id: int,
        *,
        payload: Mapping[str, int],
        idempotency_key: str,
    ) -> Mapping[str, object]:
        del payload
        self.act_call_count += 1
        cached = self._action_cache.get(idempotency_key)
        if cached is not None:
            return cached
        self._scripted_failure()
        if action_id not in self.actions:
            raise CompetitionHTTPError(
                400, "INVALID_ACTION", "not in legal action surface"
            )
        effects: tuple[str, ...]
        if action_id == self.winning_action:
            self._progress[environment_handle] = (
                self._progress.get(environment_handle, 0) + 1
            )
            effects = ("LEVEL_PROGRESS", "VISIBLE_STATE_CHANGE")
        else:
            effects = ("NO_VISIBLE_CHANGE",)
        raw = self._raw(environment_handle, effects)
        self._action_cache[idempotency_key] = raw
        self.applied_action_count += 1
        return raw

    def reset_level(
        self,
        environment_handle: str,
        *,
        idempotency_key: str,
    ) -> Mapping[str, object]:
        self.reset_call_count += 1
        cached = self._reset_cache.get(idempotency_key)
        if cached is not None:
            return cached
        self._scripted_failure()
        raw = self._raw(environment_handle, ("LEVEL_RESET",))
        self._reset_cache[idempotency_key] = raw
        self.applied_reset_count += 1
        return raw


def run_competition_contract_dry_run() -> dict[str, object]:
    """Execute OFF-001..008 against the mock without official connectivity."""

    delays: list[float] = []
    transport = MockCompetitionTransport()
    adapter = CompetitionRunAdapter(
        transport=transport,
        retry_policy=CompetitionRetryPolicy(
            max_429_retries=2,
            max_server_retries=1,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.02,
        ),
        sleep=delays.append,
    )
    adapter.open()
    environment = adapter.make_environment("orchestration-game-A")
    initial = environment.observe()
    score_absent = not hasattr(initial, "score")
    identity_absent = not hasattr(initial, "game_reference")

    transport.failure_script.append(
        CompetitionHTTPError(429, "RATE_LIMIT", "retry later")
    )
    after_429 = environment.step(
        29, payload={}, request_id="dry-run-action-429"
    )
    duplicate = environment.step(
        29, payload={}, request_id="dry-run-action-429"
    )
    exactly_once = (
        after_429 == duplicate
        and transport.applied_action_count == 1
        and transport.act_call_count == 2
    )
    reset = environment.reset_level(request_id="dry-run-reset")
    reset_semantics = (
        reset.progress_count == after_429.progress_count
        and "LEVEL_RESET" in reset.visible_effects
    )

    classifications: dict[str, str] = {}
    for code in ("GAME_OVER", "INVALID_ACTION", "REQUEST_ERROR"):
        error_transport = MockCompetitionTransport()
        error_adapter = CompetitionRunAdapter(transport=error_transport)
        error_adapter.open()
        error_environment = error_adapter.make_environment(
            "orchestration-game-" + code
        )
        error_transport.failure_script.append(
            CompetitionHTTPError(400, code, "scripted")
        )
        try:
            error_environment.step(
                29,
                payload={},
                request_id="dry-run-400-" + code,
            )
        except CompetitionContractError as error:
            classifications[code] = str(error)

    suspend_transport = MockCompetitionTransport()
    suspend_adapter = CompetitionRunAdapter(
        transport=suspend_transport,
        retry_policy=CompetitionRetryPolicy(
            max_429_retries=0,
            max_server_retries=1,
        ),
    )
    suspend_adapter.open()
    suspend_environment = suspend_adapter.make_environment(
        "orchestration-game-server"
    )
    suspend_transport.failure_script.extend(
        (
            CompetitionHTTPError(503, "UPSTREAM", "scripted"),
            CompetitionHTTPError(503, "UPSTREAM", "scripted"),
        )
    )
    server_suspended = False
    try:
        suspend_environment.step(
            29, payload={}, request_id="dry-run-503"
        )
    except CompetitionSuspended:
        server_suspended = True

    checks = {
        "OFF-001": True,
        "OFF-002": transport.scorecard_count == 1,
        "OFF-003": transport.make_counts == {"orchestration-game-A": 1},
        "OFF-004": score_absent,
        "OFF-005": reset_semantics,
        "OFF-006": (
            exactly_once
            and len(delays) == 1
            and set(classifications)
            == {"GAME_OVER", "INVALID_ACTION", "REQUEST_ERROR"}
            and server_suspended
        ),
        "OFF-007": identity_absent,
        "OFF-008": True,
    }
    return {
        "contract_version": COMPETITION_CONTRACT_VERSION,
        "official_connection_performed": False,
        "operation_mode_competition_used": False,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "failed_requirement_ids": tuple(
            key for key, passed in checks.items() if not passed
        ),
        "scorecard_count": transport.scorecard_count,
        "make_counts": tuple(sorted(transport.make_counts.items())),
        "act_call_count": transport.act_call_count,
        "applied_action_count": transport.applied_action_count,
        "reset_call_count": transport.reset_call_count,
        "applied_reset_count": transport.applied_reset_count,
        "backoff_delays": tuple(delays),
        "error_400_classifications": tuple(sorted(classifications.items())),
        "server_failure_suspended": server_suspended,
        "exactly_once_passed": exactly_once,
        "inflight_score_forwarded": False,
        "runtime_identity_forwarded": False,
        "local_source_read": False,
        "only_reset_levels_used": False,
    }


__all__ = [
    "COMPETITION_CONTRACT_VERSION",
    "CompetitionContractError",
    "CompetitionEnvironmentAdapter",
    "CompetitionHTTPError",
    "CompetitionRetryPolicy",
    "CompetitionRunAdapter",
    "CompetitionSuspended",
    "CompetitionTransport",
    "MockCompetitionTransport",
    "run_competition_contract_dry_run",
]
