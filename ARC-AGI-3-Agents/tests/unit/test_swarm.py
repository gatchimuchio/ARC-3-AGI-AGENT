from unittest.mock import Mock, call, patch

import pytest
from arc_agi import OperationMode
from arc_agi.scorecard import EnvironmentScorecard

from agents.swarm import Swarm
from agents.templates.random_agent import Random


@pytest.fixture
def arcade():
    with patch("agents.swarm.Arcade") as arcade_type:
        instance = arcade_type.return_value
        instance.operation_mode = OperationMode.OFFLINE
        yield instance


@pytest.mark.unit
class TestSwarmInitialization:
    def test_swarm_init(self, arcade):
        with patch.dict("os.environ", {"ARC_API_KEY": "test-api-key"}):
            swarm = Swarm(
                agent="random",
                ROOT_URL="https://example.com",
                games=["game1", "game2"],
            )

        assert swarm.agent_name == "random"
        assert swarm.ROOT_URL == "https://example.com"
        assert swarm.GAMES == ["game1", "game2"]
        assert swarm.agent_class is Random
        assert swarm.threads == []
        assert swarm.agents == []
        assert swarm.headers == {
            "X-API-Key": "test-api-key",
            "Accept": "application/json",
        }
        assert swarm._arc is arcade


@pytest.mark.unit
class TestSwarmScorecard:
    def test_open_scorecard_uses_arcade_boundary(self, arcade):
        arcade.open_scorecard.return_value = "test-card-123"
        swarm = Swarm(
            agent="random",
            ROOT_URL="https://example.com",
            games=["game1"],
            tags=["experiment"],
        )

        assert swarm.open_scorecard() == "test-card-123"
        arcade.open_scorecard.assert_called_once_with(
            tags=["experiment", "agent", "random"]
        )

    def test_close_scorecard_clears_active_card(self, arcade):
        scorecard = Mock(spec=EnvironmentScorecard)
        arcade.close_scorecard.return_value = scorecard
        swarm = Swarm(
            agent="random",
            ROOT_URL="https://example.com",
            games=["game1"],
        )
        swarm.card_id = "test-card-123"

        result = swarm.close_scorecard("test-card-123")

        assert result is scorecard
        assert swarm.card_id is None
        arcade.close_scorecard.assert_called_once_with("test-card-123")


@pytest.mark.unit
class TestSwarmAgentManagement:
    def test_main_builds_one_agent_and_thread_per_game(self, arcade):
        swarm = Swarm(
            agent="random",
            ROOT_URL="https://example.com",
            games=["game1", "game2", "game3"],
        )
        agents = [Mock(name=f"agent-{index}") for index in range(3)]
        agent_factory = Mock(side_effect=agents)
        swarm.agent_class = agent_factory
        environments = [Mock(name=f"env-{index}") for index in range(3)]
        arcade.make.side_effect = environments
        scorecard = Mock(spec=EnvironmentScorecard)
        scorecard.model_dump.return_value = {"card_id": "test-card-123"}
        threads = [Mock(name=f"thread-{index}") for index in range(3)]

        with (
            patch.object(
                swarm,
                "open_scorecard",
                return_value="test-card-123",
            ) as open_scorecard,
            patch.object(
                swarm,
                "close_scorecard",
                return_value=scorecard,
            ) as close_scorecard,
            patch("agents.swarm.Thread", side_effect=threads) as thread_type,
        ):
            result = swarm.main()

        assert result is scorecard
        open_scorecard.assert_called_once_with()
        close_scorecard.assert_called_once_with("test-card-123")
        assert arcade.make.call_args_list == [
            call("game1", scorecard_id="test-card-123"),
            call("game2", scorecard_id="test-card-123"),
            call("game3", scorecard_id="test-card-123"),
        ]
        assert agent_factory.call_count == 3
        assert thread_type.call_count == 3
        for thread in threads:
            thread.start.assert_called_once_with()
            thread.join.assert_called_once_with()
        for agent in agents:
            agent.cleanup.assert_called_once_with(scorecard)


@pytest.mark.unit
class TestSwarmCleanup:
    def test_cleanup_is_safe_with_and_without_legacy_session(self, arcade):
        swarm = Swarm(
            agent="random",
            ROOT_URL="https://example.com",
            games=["game1", "game2"],
        )
        agents = [Mock(), Mock()]
        swarm.agents = agents
        scorecard = Mock(spec=EnvironmentScorecard)

        swarm.cleanup(scorecard)

        for agent in agents:
            agent.cleanup.assert_called_once_with(scorecard)

        session = Mock()
        swarm._session = session
        swarm.cleanup()

        for agent in agents:
            agent.cleanup.assert_called_with(None)
        session.close.assert_called_once_with()


@pytest.mark.unit
class TestSwarmTags:
    @pytest.mark.parametrize(
        "custom_tags,expected",
        [
            (["experiment1", "version2"], ["experiment1", "version2", "agent", "random"]),
            ([], ["agent", "random"]),
        ],
    )
    def test_open_scorecard_combines_custom_and_agent_tags(
        self,
        arcade,
        custom_tags,
        expected,
    ):
        arcade.open_scorecard.return_value = "test-card-123"
        swarm = Swarm(
            agent="random",
            ROOT_URL="https://example.com",
            games=["game1"],
            tags=custom_tags,
        )

        assert swarm.open_scorecard() == "test-card-123"
        arcade.open_scorecard.assert_called_once_with(tags=expected)
