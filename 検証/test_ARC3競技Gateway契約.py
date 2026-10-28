"""ローカルSDKの競技Gateway契約。実Kaggle Gatewayの証明ではない。"""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("only_reset_levels", ["true", "false"])
def test_competition_gateway_contract(tmp_path, monkeypatch, only_reset_levels):
    """scorecard・環境再作成・同じ環境でのRESETとstepの責任を確認する。"""
    root = os.environ.get("ARC3_PUBLIC_ROOT")
    if not root:
        pytest.skip("ARC3_PUBLIC_ROOT に公開環境を含む旧作業rootを指定")
    environments = Path(root) / "入力/Kaggle/environment_files"
    if not environments.is_dir():
        pytest.fail("指定された公開環境のディレクトリが存在しません")

    from arc_agi import Arcade, OperationMode
    from arc_agi.server import create_app

    monkeypatch.setenv("ONLY_RESET_LEVELS", only_reset_levels)
    logger = logging.getLogger("arc3-gateway-contract-test")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments),
        recordings_dir=str(tmp_path),
        logger=logger,
    )
    assert arcade.available_environments
    app, api = create_app(arcade, competition_mode=True)
    app.testing = True
    client = app.test_client()
    headers = {"X-API-Key": "synthetic-test"}

    opened = client.post("/api/scorecard/open", json={}, headers=headers)
    assert opened.status_code == 200
    card = opened.get_json()["card_id"]
    assert client.post("/api/scorecard/open", json={}, headers=headers).status_code == 409
    assert client.get("/api/scorecard/" + card, headers=headers).status_code == 403

    game_id = sorted(env.game_id for env in arcade.available_environments)[0]
    created = client.post("/api/cmd/RESET", json={"game_id": game_id, "card_id": card}, headers=headers)
    assert created.status_code == 200
    frame = created.get_json()
    guid = frame["guid"]
    game = api._environmentCache[guid]
    # FrameData由来のAPI返却値とSDK wrapperのraw観測は別々に検査する。
    assert frame["full_reset"] is False
    assert game.observation_space.full_reset is (only_reset_levels == "false")
    local_card = arcade.scorecard_manager.get_scorecard(card, "synthetic-test").get_card(game_id)
    assert (local_card.total_plays, local_card.actions, local_card.resets) == (1, [0], [0])
    payload = {"game_id": game_id, "card_id": card, "guid": guid}
    with patch.object(game, "step", wraps=game.step) as steps:
        first_reset = client.post("/api/cmd/RESET", json=payload, headers=headers)
        assert first_reset.status_code == 200
        assert steps.call_count == 0
        assert (local_card.actions, local_card.resets) == ([1], [1])

        legal = [action for action in frame["available_actions"] if 1 <= action <= 7]
        assert legal
        action = legal[0]
        action_payload = dict(payload)
        if action == 6:
            action_payload.update(x=0, y=0)
        assert client.post(f"/api/cmd/ACTION{action}", json=action_payload, headers=headers).status_code == 200
        assert steps.call_count == 1
        assert (local_card.actions, local_card.resets) == ([2], [1])
        assert client.post("/api/cmd/RESET", json=payload, headers=headers).status_code == 200
        assert steps.call_count == 2
        assert (local_card.total_plays, local_card.actions, local_card.resets) == (1, [3], [2])

    repeated_make = client.post("/api/cmd/RESET", json={"game_id": game_id, "card_id": card}, headers=headers)
    assert repeated_make.status_code == 400
