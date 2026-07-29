from __future__ import annotations

from dataclasses import dataclass

from arc3_agi_agent.generic_competition_runner import (
    run_sequential_competition,
)


@dataclass(frozen=True)
class _EnvironmentInfo:
    game_id: str


class _Environment:
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        self._session = _Session()


class _Session:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FailingSession(_Session):
    def close(self) -> None:
        super().close()
        raise RuntimeError("bounded release failure")


class _Arcade:
    def __init__(self) -> None:
        self.game_ids = ("hidden-a", "hidden-b", "hidden-c")
        self.open_calls = 0
        self.close_calls = 0
        self.make_calls: list[str] = []
        self.environments: list[_Environment] = []

    def get_environments(self) -> list[_EnvironmentInfo]:
        return [_EnvironmentInfo(game_id=value) for value in self.game_ids]

    def open_scorecard(self, *, tags: list[str]) -> str:
        assert tags == ["agent", "genericagi", "sequential"]
        self.open_calls += 1
        return "card-one"

    def make(
        self,
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> _Environment:
        assert scorecard_id == "card-one"
        assert save_recording is False
        assert include_frame_data is True
        self.make_calls.append(game_id)
        environment = _Environment(game_id)
        self.environments.append(environment)
        return environment

    def close_scorecard(self, card_id: str) -> object:
        assert card_id == "card-one"
        self.close_calls += 1
        return object()


@dataclass(frozen=True)
class _RuntimeReport:
    actions_executed: int = 128
    progress_count: int = 0
    final_state: str = "NOT_FINISHED"
    stop_reason: str = "RESOURCE_LIMIT"


class _Agent:
    active = 0
    active_peak = 0
    session_object_ids: list[int] = []
    memory_object_ids: list[int] = []
    p_object_ids: list[int] = []

    def __init__(self, **kwargs: object) -> None:
        assert kwargs["record"] is False
        self.game_id = str(kwargs["game_id"])
        cognitive_session = kwargs["cognitive_session"]
        self.__class__.session_object_ids.append(id(cognitive_session))
        self.__class__.memory_object_ids.append(
            id(getattr(cognitive_session, "memory"))
        )
        self.__class__.p_object_ids.append(
            id(getattr(getattr(cognitive_session, "p_bundle"), "body"))
        )
        self.runtime_report: _RuntimeReport | None = None

    def main(self) -> None:
        type(self).active += 1
        type(self).active_peak = max(
            type(self).active_peak,
            type(self).active,
        )
        try:
            if self.game_id == "hidden-b":
                raise RuntimeError("bounded per-game failure")
            self.runtime_report = _RuntimeReport()
        finally:
            type(self).active -= 1


def test_runner_isolates_one_game_and_closes_one_scorecard() -> None:
    arcade = _Arcade()
    _Agent.active = 0
    _Agent.active_peak = 0
    _Agent.session_object_ids = []
    _Agent.memory_object_ids = []
    _Agent.p_object_ids = []

    report = run_sequential_competition(
        arcade=arcade,
        agent_factory=_Agent,
    )

    assert arcade.open_calls == 1
    assert arcade.close_calls == 1
    assert arcade.make_calls == list(arcade.game_ids)
    assert all(item._session.closed for item in arcade.environments)
    assert _Agent.active_peak == 1
    assert report["advertised_game_count"] == 3
    assert report["completed_game_count"] == 2
    assert report["failed_game_count"] == 1
    assert report["lifecycle_failure_count"] == 0
    assert report["active_agent_peak"] == 1
    assert report["scorecard_closed"] is True
    assert report["runtime_policy_changed"] is False
    assert len(set(_Agent.session_object_ids)) == 1
    assert len(set(_Agent.memory_object_ids)) == 1
    assert len(set(_Agent.p_object_ids)) == 1
    assert report["shared_session_count"] == 1
    assert report["per_game_new_memory_count"] == 0
    assert report["per_game_new_p_count"] == 0
    assert report["cross_game_semantic_promotion"] == "ENABLED"
    assert report["state_owner_violation_count"] == 0
    assert report["identity_boundary"] == "PASS"


def test_runner_records_release_failure_and_continues() -> None:
    arcade = _Arcade()
    _Agent.active = 0
    _Agent.active_peak = 0
    _Agent.session_object_ids = []
    _Agent.memory_object_ids = []
    _Agent.p_object_ids = []
    original_make = arcade.make

    def make_with_one_release_failure(
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> _Environment:
        environment = original_make(
            game_id,
            scorecard_id=scorecard_id,
            save_recording=save_recording,
            include_frame_data=include_frame_data,
        )
        if game_id == "hidden-a":
            environment._session = _FailingSession()
        return environment

    arcade.make = make_with_one_release_failure  # type: ignore[method-assign]
    report = run_sequential_competition(
        arcade=arcade,
        agent_factory=_Agent,
    )

    assert arcade.make_calls == list(arcade.game_ids)
    assert arcade.close_calls == 1
    assert report["completed_game_count"] == 2
    assert report["failed_game_count"] == 1
    assert report["lifecycle_failure_count"] == 1
    lifecycle_failures = report["lifecycle_failures"]
    assert isinstance(lifecycle_failures, list)
    assert lifecycle_failures == [
        {
            "game_index": 0,
            "phase": "environment_release",
            "error_type": "RuntimeError",
            "error_message": "bounded release failure",
        }
    ]
