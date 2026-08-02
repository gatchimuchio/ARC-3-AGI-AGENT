from __future__ import annotations

from dataclasses import dataclass

from arc3_agi_agent.product_runner import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    create_product_session,
    run_arc3_completion_product,
)


@dataclass(frozen=True)
class _EnvironmentInfo:
    game_id: str


class _Session:
    def close(self) -> None:
        return None


class _Environment:
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        self._session = _Session()


class _Arcade:
    def __init__(self) -> None:
        self.game_ids = ("sample-a", "sample-b")

    def get_environments(self) -> list[_EnvironmentInfo]:
        return [_EnvironmentInfo(game_id=value) for value in self.game_ids]

    def open_scorecard(self, *, tags: list[str]) -> str:
        assert tags == ["agent", "genericagi", "sequential"]
        return "product-card"

    def make(
        self,
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> _Environment:
        assert scorecard_id == "product-card"
        assert save_recording is False
        assert include_frame_data is True
        return _Environment(game_id)

    def close_scorecard(self, card_id: str) -> object:
        assert card_id == "product-card"
        return object()


@dataclass(frozen=True)
class _RuntimeReport:
    actions_executed: int
    progress_count: int
    final_state: str = "WIN"
    stop_reason: str = "GOAL_REACHED"


class _ProductAgent:
    progress_values: tuple[int, ...] = (91, 92)
    call_count = 0

    def __init__(self, **kwargs: object) -> None:
        assert kwargs["record"] is False
        self.runtime_report: _RuntimeReport | None = None

    def main(self) -> None:
        progress = self.progress_values[type(self).call_count]
        type(self).call_count += 1
        self.runtime_report = _RuntimeReport(
            actions_executed=128,
            progress_count=progress,
        )


def test_product_session_closes_known_budget_impossibility() -> None:
    session = create_product_session()

    assert ARC3_DEVELOPMENT_ACTION_BUDGET == 4096
    assert ARC3_KNOWN_SUCCESS_ACTION_CEILING == 1519
    assert ARC3_DEVELOPMENT_ACTION_BUDGET >= ARC3_KNOWN_SUCCESS_ACTION_CEILING
    assert session.resource_contract.action_budget_per_episode == 4096
    assert session.hds_config.resource_budget == 4096
    assert session.hds_config.stop_after_no_progress == 650


def test_product_runner_reports_endpoint_metrics_without_false_completion() -> None:
    _ProductAgent.call_count = 0

    report = run_arc3_completion_product(
        arcade=_Arcade(),
        agent_factory=_ProductAgent,
    )

    assert report["product_id"] == "ARC3CompletionAgent"
    assert report["product_action_budget_per_game"] == 4096
    assert report["known_success_action_ceiling"] == 1519
    assert report["known_budget_impossibility"] is False
    assert report["product_game_started_count"] == 2
    assert report["product_game_win_count"] == 2
    assert report["product_level_completion_count"] == 183
    endpoint_failure_count = report["product_endpoint_failure_count"]
    assert isinstance(endpoint_failure_count, int)
    assert endpoint_failure_count > 0
    endpoint_failures = report["product_endpoint_failures"]
    assert isinstance(endpoint_failures, tuple)
    assert "PRODUCT_ADVERTISED_GAME_COUNT_MISMATCH" in endpoint_failures
    assert report["product_completion_established"] is False
    assert report["product_baseline_executable"] is False
    assert report["product_status"] == "INCOMPLETE"
