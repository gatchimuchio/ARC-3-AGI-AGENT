"""Synthetic SDK boundary checks. These tests do not start a game or network."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import threading
import time
import types
from unittest.mock import patch

from arcengine import FrameData, GameAction, GameState

from arc3_cpu_test_support import CANDIDATE, load_cpu, previous_path

Agent, cpu = load_cpu()


def frame(state=GameState.NOT_FINISHED, actions=None, board=None):
    return FrameData(state=state, available_actions=[1, 6] if actions is None else actions,
                     frame=[board or [[1, 1], [1, 2]]], levels_completed=0)


def agent(obs):
    env = types.SimpleNamespace(observation_space=obs)
    return cpu.MyAgent(card_id='local', game_id='unused', agent_name='MyAgent', ROOT_URL='local', record=False, arc_env=env)


def test_initial_real_observation_and_terminal():
    win = frame(GameState.WIN)
    a = agent(win)
    assert a.is_done([], frame())
    b = agent(frame())
    assert not b.is_done([], frame(GameState.WIN))
    b.action_counter = 1
    assert b.is_done([], win)
    assert b.is_done([], frame(actions=[]))


def test_legal_action_and_coordinates():
    obs = frame(actions=[6])
    a = agent(obs)
    action = a.choose_action([], obs)
    assert action is GameAction.ACTION6
    captured = []
    with patch.object(Agent, 'take_action', lambda _self, act: captured.append(dict(act.action_data.model_dump()))):
        a.take_action(action)
    assert 0 <= captured[0]['x'] < 2 and 0 <= captured[0]['y'] < 2
    assert len(captured) == 1


def test_invalid_actions_and_coordinate_fail_closed():
    obs = frame(actions=[6], board=[[1] * 65])
    a = agent(obs)
    assert a.choose_action([], obs) is None
    assert a._safe_stop
    assert cpu._visible_frame(obs) == []


def test_reset_is_state_driven():
    for state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
        obs = frame(state=state, actions=[])
        a = agent(obs)
        assert not a.is_done([], obs)
        assert a.choose_action([], obs) is GameAction.RESET


def test_mutable_enum_use_is_serialized():
    obs = frame(actions=[6]); a = agent(obs); b = agent(obs)
    fingerprint = cpu._fingerprint(obs)
    a._pending = (GameAction.ACTION6, {'x': 0, 'y': 0}, fingerprint, cpu._identity_key(obs))
    b._pending = (GameAction.ACTION6, {'x': 1, 'y': 1}, fingerprint, cpu._identity_key(obs))
    received = []
    def mocked(_self, action):
        before = action.action_data.model_dump(); time.sleep(.02); after = action.action_data.model_dump()
        assert before == after
        received.append((before['x'], before['y']))
    with patch.object(Agent, 'take_action', mocked):
        threads = [threading.Thread(target=x.take_action, args=(GameAction.ACTION6,)) for x in (a, b)]
        for t in threads: t.start()
        for t in threads: t.join()
    assert sorted(received) == [(0, 0), (1, 1)]


def test_observation_only_and_seed_reproducible():
    one = agent(frame()); two = agent(frame())
    # Different identity labels never feed decision logic.
    one.game_id = 'identity-a'; two.game_id = 'identity-b'
    obs = frame()
    left = [one.choose_action([], obs).value for _ in range(8)]
    right = [two.choose_action([], obs).value for _ in range(8)]
    assert left == right
    import ast
    tree = ast.parse(CANDIDATE.read_text(encoding='utf-8'))
    assert not any(isinstance(n, ast.ImportFrom) and (n.module or '').startswith('hds学習系統') or isinstance(n, ast.Import) and any(x.name.startswith('hds学習系統') for x in n.names) for n in ast.walk(tree))


def test_mismatched_action_rejected_without_dispatch():
    obs = frame(actions=[1]); a = agent(obs)
    assert a.choose_action([], obs) is GameAction.ACTION1
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(GameAction.ACTION2) is None
        assert a._safe_stop


def test_unknown_only_stops_before_choose_or_step():
    obs = frame(actions=[8, 99]); a = agent(obs)
    assert a.is_done([], obs)
    assert a._safe_stop
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(None) is None


def test_current_legal_set_is_rechecked_at_dispatch():
    obs = frame(actions=[1]); a = agent(obs)
    action = a.choose_action([], obs)
    a.arc_env.observation_space = frame(actions=[2])
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(action) is None
    assert a._safe_stop


def test_changed_observation_is_rejected():
    obs = frame(actions=[1]); a = agent(obs)
    action = a.choose_action([], obs)
    a.arc_env.observation_space = frame(actions=[1], board=[[9, 9], [9, 2]])
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(action) is None
    assert a._safe_stop


def test_reset_stale_state_rejected():
    obs = frame(state=GameState.GAME_OVER, actions=[]); a = agent(obs)
    action = a.choose_action([], obs)
    a.arc_env.observation_space = frame(actions=[1])
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(action) is None
    assert a._safe_stop


def test_choose_sentinel_is_fail_closed_and_stops():
    obs = frame(actions=[8]); a = agent(obs)
    assert a.choose_action([], obs) is None
    assert a.is_done([], obs)
    with patch.object(Agent, 'take_action', side_effect=AssertionError('must not dispatch')):
        assert a.take_action(None) is None


def test_valid_observation_rng_and_actions_match_old():
    _, old = load_cpu(previous_path(), 'cpu_agent_old_test')
    obs = frame()
    new = agent(obs)
    prev = old.MyAgent(card_id='local', game_id='unused', agent_name='MyAgent', ROOT_URL='local', record=False, arc_env=types.SimpleNamespace(observation_space=obs))
    for _ in range(20):
        assert prev.choose_action([], obs).value == new.choose_action([], obs).value
        assert prev._pending[1] == new._pending[1]
