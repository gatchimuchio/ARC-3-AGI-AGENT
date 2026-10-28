"""Real Starter/SDK class boundary against a synthetic local environment; no game."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import types
import numpy as np
from arcengine import FrameDataRaw, GameState

from arc3_cpu_test_support import CANDIDATE, load_cpu, previous_path


def load(path, name):
    return load_cpu(path, name)[1]


def raw(actions, state=GameState.NOT_FINISHED):
    f = FrameDataRaw(state=state, available_actions=actions, levels_completed=0)
    f.frame = [np.array([[1, 1], [1, 2]], dtype=np.uint8)]
    return f


class SyntheticEnv:
    def __init__(self, actions): self.observation_space = raw(actions); self.calls = []
    def step(self, action, *, data, reasoning):
        self.calls.append((action.value, dict(data)))
        if len(self.calls) >= 4: self.observation_space = raw([], GameState.WIN)
        return self.observation_space


def construct(module, env):
    return module.MyAgent(card_id='local', game_id='synthetic', agent_name='MyAgent', ROOT_URL='local', record=False, arc_env=env)


def test_real_starter_unknown_actions_stop_without_step():
    module = load(CANDIDATE,'safe_agent_sdk_1'); env = SyntheticEnv([8,99]); agent = construct(module,env)
    agent.main()
    assert agent._safe_stop and agent.action_counter == 0 and not env.calls


def test_real_starter_stale_legality_stops_without_step():
    module = load(CANDIDATE,'safe_agent_sdk_2'); env = SyntheticEnv([1]); agent = construct(module,env)
    original = agent.choose_action
    def changed(*args):
        action = original(*args)
        env.observation_space = raw([2])
        return action
    agent.choose_action = changed
    agent.main()
    assert agent._safe_stop and not env.calls


def test_real_starter_non_degraded_normal_actions():
    old = load(previous_path(),'old_agent_sdk')
    new = load(CANDIDATE,'safe_agent_sdk_3')
    a,b = SyntheticEnv([1,6]),SyntheticEnv([1,6])
    previous,current = construct(old,a),construct(new,b)
    previous.main();current.main()
    assert a.calls == b.calls and len(a.calls)==4 and not current._safe_stop


def test_full_reset_change_rejected_by_real_starter():
    module = load(CANDIDATE,'safe_agent_sdk_full_reset'); env = SyntheticEnv([1]); agent = construct(module,env)
    original = agent.choose_action
    def changed(*args):
        action = original(*args)
        env.observation_space.full_reset = True
        return action
    agent.choose_action = changed
    agent.main()
    assert agent._safe_stop and not env.calls


def test_non_last_frame_layer_change_rejected():
    module = load(CANDIDATE,'safe_agent_sdk_all_layers'); env = SyntheticEnv([1]); agent = construct(module,env)
    env.observation_space.frame = [np.array([[1,1],[1,1]],dtype=np.uint8), np.array([[2,2],[2,2]],dtype=np.uint8)]
    original = agent.choose_action
    def changed(*args):
        action = original(*args)
        env.observation_space.frame[0][0,0] = 9
        return action
    agent.choose_action = changed
    agent.main()
    assert agent._safe_stop and not env.calls


def test_dispatch_rejects_changed_identity_and_win_levels():
    for name, changed_value in [('game_id','another'),('guid','another'),('win_levels',9)]:
        module = load(CANDIDATE,'safe_agent_gate_'+name); env = SyntheticEnv([1]); agent = construct(module,env)
        original = agent.choose_action
        def changed(*args):
            action = original(*args)
            setattr(env.observation_space, name, changed_value)
            return action
        agent.choose_action = changed
        agent.main()
        assert agent._safe_stop and not env.calls


def test_identity_is_not_policy_state_or_selection():
    module = load(CANDIDATE,'safe_agent_identity_policy'); a,b = SyntheticEnv([1,6]),SyntheticEnv([1,6])
    a.observation_space.game_id='identity-a'; a.observation_space.guid='token-a'
    b.observation_space.game_id='identity-b'; b.observation_space.guid='token-b'
    left,right = construct(module,a),construct(module,b)
    fa=left._convert_raw_frame_data(a.observation_space); fb=right._convert_raw_frame_data(b.observation_space)
    assert module._fingerprint(fa)==module._fingerprint(fb)
    for _ in range(8):
        assert left.choose_action([],fa).value==right.choose_action([],fb).value
        assert left._pending[1]==right._pending[1]


def test_starter_projection_preserves_full_reset_and_ignores_raw_action_input():
    from arcengine import ActionInput, GameAction
    module=load(CANDIDATE,'safe_agent_projection'); env=SyntheticEnv([1]); agent=construct(module,env)
    env.observation_space.game_id='synthetic';env.observation_space.guid='token'
    env.observation_space.win_levels=3;env.observation_space.full_reset=True
    env.observation_space.action_input=ActionInput(id=GameAction.ACTION1,data={})
    converted=agent._convert_raw_frame_data(env.observation_space)
    assert converted.game_id==env.observation_space.game_id and converted.guid==env.observation_space.guid
    assert converted.full_reset is True and converted.win_levels==3
    assert converted.action_input.id != env.observation_space.action_input.id
    assert module._fingerprint(converted)==module._fingerprint(env.observation_space)
    agent.main()
    assert len(env.calls)==4 and not agent._safe_stop


def test_noninitial_not_played_stops_before_reset():
    module=load(CANDIDATE,'safe_agent_unexpected_not_played');env=SyntheticEnv([1]);agent=construct(module,env)
    agent.action_counter=1
    env.observation_space=raw([],GameState.NOT_PLAYED)
    agent.main()
    assert agent._safe_stop and not env.calls


def test_initial_not_played_is_valid_reset():
    module=load(CANDIDATE,'safe_agent_initial_not_played');env=SyntheticEnv([]);agent=construct(module,env)
    env.observation_space=raw([],GameState.NOT_PLAYED)
    # One valid RESET is followed by terminal synthetic WIN.
    def reset_once(action, *, data, reasoning):
        env.calls.append((action.value,dict(data)));env.observation_space=raw([],GameState.WIN);return env.observation_space
    env.step=reset_once
    agent.main()
    assert len(env.calls)==1 and env.calls[0][0]==0 and not agent._safe_stop


def test_invalid_identity_or_action_type_stops_before_step():
    module=load(CANDIDATE,'safe_agent_ambiguous');
    for field, value in [('guid', 123), ('available_actions', [1,'unknown'])]:
        env=SyntheticEnv([1]);agent=construct(module,env)
        setattr(env.observation_space,field,value)
        agent.main()
        assert agent._safe_stop and not env.calls


def test_mixed_legal_types_at_dispatch_stops_without_step():
    module=load(CANDIDATE,'safe_agent_late_ambiguous');env=SyntheticEnv([1]);agent=construct(module,env)
    original=agent.choose_action
    def changed(*args):
        action=original(*args);env.observation_space.available_actions=[1,'unknown'];return action
    agent.choose_action=changed
    agent.main()
    assert agent._safe_stop and not env.calls
