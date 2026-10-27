from __future__ import annotations
import argparse, hashlib, importlib, importlib.util, io, json, logging, os, random, subprocess, sys, tempfile, types, zipfile
from pathlib import Path

ROOT = Path.cwd()
ENV_ROOT = ROOT / '\u5165\u529b' / 'Kaggle' / 'environment_files'
STARTER_AGENTS = ROOT / '\u5165\u529b' / 'Kaggle' / 'ARC-AGI-3-Agents' / 'agents'


def _load_builder():
    p = ROOT / '\u9053\u5177' / 'ARC3\u63d0\u51fa\u7269\u69cb\u7bc9.py'
    spec = importlib.util.spec_from_file_location('arc3_pair_builder', p)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _games():
    rows = []
    for p in sorted(ENV_ROOT.rglob('metadata.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        gid = data.get('game_id') if isinstance(data, dict) else None
        if isinstance(gid, str) and gid:
            rows.append(gid)
    if len(rows) != len(set(rows)):
        raise RuntimeError('duplicate public starter game metadata')
    return sorted(rows)


def _child(condition: str, bundle_path: Path, previous_coefficient: float, candidate_coefficient: float):
    from arc_agi import Arcade, OperationMode
    from ARC3公開RHAE評価 import _スコアを計算する
    logging.disable(logging.CRITICAL)
    tmp = tempfile.TemporaryDirectory(prefix='arc3-pair-child-')
    base = Path(tmp.name)
    source = base / 'source'
    source.mkdir()
    with zipfile.ZipFile(bundle_path) as z:
        z.extractall(source)
    sys.path[:0] = [str(source), str(source / 'HDS' / '\u5b66\u7fd2\u7cfb\u7d71' / 'v0.4.2')]
    package = types.ModuleType('agents')
    package.__path__ = [str(STARTER_AGENTS)]
    sys.modules['agents'] = package
    starter = importlib.import_module('agents.agent')
    agent_path = source / '\u63a5\u7d9a' / 'ARC3\u63d0\u51faagent.py'
    spec = importlib.util.spec_from_file_location('packed_arc3_agent', agent_path)
    assert spec and spec.loader
    agent_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_module)
    if not issubclass(agent_module.MyAgent, starter.Agent):
        raise RuntimeError('packed agent does not use official starter Agent')

    old_policy = getattr(agent_module, '\u89b3\u6e2c\u99c6\u52d5\u63a2\u7d22\u65b9\u91dd')
    def fixed_policy(*args, **kwargs):
        kwargs['\u4e71\u6570\u7a2e'] = 31025
        return old_policy(*args, **kwargs)
    setattr(agent_module, '\u89b3\u6e2c\u99c6\u52d5\u63a2\u7d22\u65b9\u91dd', fixed_policy)
    memory_loader = getattr(agent_module, '\u4e8b\u524d\u8a18\u61b6\u3092HDS\u3078\u4f9b\u7d66\u3059\u308b')
    coefficient = previous_coefficient if condition == 'previous' else candidate_coefficient
    def configured_memory(hds):
        report = dict(memory_loader(hds))
        report['visible_change_coefficient'] = coefficient
        return report
    setattr(agent_module, '\u4e8b\u524d\u8a18\u61b6\u3092HDS\u3078\u4f9b\u7d66\u3059\u308b', configured_memory)

    games = _games()
    if len(games) != 25:
        raise RuntimeError(f'expected 25 public Starter games, found {len(games)}')
    arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(ENV_ROOT), recordings_dir=str(base / 'recordings'))
    results = []
    for index, game_id in enumerate(games, 1):
        try:
            env = arcade.make(game_id, seed=0, save_recording=False, include_frame_data=True)
            if env is None:
                raise RuntimeError('offline Arcade did not create an environment')
            agent = agent_module.MyAgent(card_id='local-evaluation', game_id=game_id, agent_name='MyAgent', ROOT_URL='http://offline', record=False, arc_env=env)
            trace = []
            response_deltas = []
            initial_levels = int(getattr(env.observation_space, 'levels_completed', 0))
            previous_levels = initial_levels
            original_request = agent.do_action_request
            def traced_request(action):
                nonlocal previous_levels
                trace.append([getattr(action, '\u4f5c\u7528\u756a\u53f7'), dict(getattr(action, '\u5f15\u6570'))])
                response = original_request(action)
                current_levels = int(getattr(env.observation_space, 'levels_completed', previous_levels))
                response_deltas.append({'level_delta': current_levels - previous_levels})
                previous_levels = current_levels
                return response
            agent.do_action_request = traced_request
            agent.main()
            final = env.observation_space
            baseline = None
            for metadata_path in ENV_ROOT.rglob('metadata.json'):
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                if metadata.get('game_id') == game_id:
                    baseline = metadata.get('baseline_actions')
                    break
            if not isinstance(baseline, list) or not all(type(v) is int and v > 0 for v in baseline):
                raise RuntimeError('public scorecard baseline metadata is invalid')
            rhae_score, scored_level_events, _ = _スコアを計算する(
                baseline,
                {
                    'action_responses': response_deltas,
                    'actions': len(trace),
                    'initial_levels_completed': initial_levels,
                },
            )
            if scored_level_events != int(getattr(final, 'levels_completed', 0)) - initial_levels:
                raise RuntimeError('scorecard level boundaries disagree with Starter completion count')
            stats = agent.exploration_stats
            legal_actions = sum(int(v.get('\u56de\u6570', 0)) for v in stats.values())
            runtime = agent.hds_runtime_stats
            trace_sha = hashlib.sha256(json.dumps(trace, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            results.append({
                'levels': int(getattr(final, 'levels_completed', 0)),
                'wins': int(getattr(final.state, 'name', '') == 'WIN'),
                'rhae_score': float(rhae_score),
                'requests': int(agent.action_counter),
                'legal_non_reset_actions': legal_actions,
                'prior_records': int(runtime.get('\u4e8b\u524d\u8a18\u61b6\u8aad\u8fbc\u4ef6\u6570', 0)),
                'hds_updates': int(runtime.get('\u89b3\u6e2c\u66f4\u65b0\u6570', 0)),
                'action_authorization': bool(runtime.get('\u4e8b\u524d\u8a18\u61b6Action\u8a8d\u53ef', True)),
                'coefficient': float(runtime.get('\u4e8b\u524d\u8a18\u61b6\u53cd\u6620\u53ef\u8996\u5909\u5316\u4fc2\u6570', -1)),
                'trace_sha256': trace_sha,
            })
        except Exception as exc:
            results.append({'error': type(exc).__name__})
        if index % 5 == 0:
            print(f'PROGRESS {condition} {index}/25', flush=True)
    print('RESULT ' + json.dumps({'condition': condition, 'rows': results}, separators=(',', ':')), flush=True)
    tmp.cleanup()


def _parent(script: Path, previous_coefficient: float, candidate_coefficient: float):
    builder = _load_builder()
    payload, manifest = builder._bundle()
    bundle_sha = hashlib.sha256(payload).hexdigest()
    with tempfile.TemporaryDirectory(prefix='arc3-prior-pair-') as folder:
        zpath = Path(folder) / 'candidate.zip'
        zpath.write_bytes(payload)
        condition_rows = {}
        for condition in ('previous', 'candidate'):
            cmd = [
                sys.executable,
                str(script),
                '--child',
                condition,
                '--bundle',
                str(zpath),
                '--previous-coefficient',
                str(previous_coefficient),
                '--candidate-coefficient',
                str(candidate_coefficient),
            ]
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', bufsize=1)
            result = None
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip('\r\n')
                if line.startswith('PROGRESS '):
                    print(line, flush=True)
                elif line.startswith('RESULT '):
                    result = json.loads(line[7:])
            code = proc.wait()
            if code != 0 or result is None:
                raise RuntimeError(f'{condition} child failed with exit={code}')
            condition_rows[condition] = result['rows']
        prev, cur = condition_rows['previous'], condition_rows['candidate']
        if len(prev) != 25 or len(cur) != 25:
            raise RuntimeError('paired run did not complete 25 episodes per condition')
        errors = sum('error' in r for r in prev + cur)
        if errors:
            summary = {'errors': errors, 'error_types': sorted({r['error'] for r in prev + cur if 'error' in r})}
        else:
            level_deltas = [b['levels'] - a['levels'] for a,b in zip(prev,cur)]
            win_deltas = [b['wins'] - a['wins'] for a,b in zip(prev,cur)]
            score_deltas = [b['rhae_score'] - a['rhae_score'] for a,b in zip(prev,cur)]
            previous_score = sum(r['rhae_score'] for r in prev) / len(prev)
            candidate_score = sum(r['rhae_score'] for r in cur) / len(cur)
            summary = {
                'episodes_per_condition':25,
                'previous': {
                    'visible_change_coefficient':previous_coefficient,
                    'levels_completed':sum(r['levels'] for r in prev),
                    'wins':sum(r['wins'] for r in prev),
                    'public_starter_rhae_score_mean':round(previous_score, 9),
                    'legal_non_reset_actions':sum(r['legal_non_reset_actions'] for r in prev),
                    'max_requests':max(r['requests'] for r in prev),
                    'episodes_with_two_or_more_legal_actions':sum(r['legal_non_reset_actions'] >= 2 for r in prev),
                    'prior_records_loaded_25_each':all(r['prior_records']==5 for r in prev),
                    'action_authorization_false_all':all(not r['action_authorization'] for r in prev),
                },
                'candidate': {
                    'visible_change_coefficient':candidate_coefficient,
                    'levels_completed':sum(r['levels'] for r in cur),
                    'wins':sum(r['wins'] for r in cur),
                    'public_starter_rhae_score_mean':round(candidate_score, 9),
                    'legal_non_reset_actions':sum(r['legal_non_reset_actions'] for r in cur),
                    'max_requests':max(r['requests'] for r in cur),
                    'episodes_with_two_or_more_legal_actions':sum(r['legal_non_reset_actions'] >= 2 for r in cur),
                    'prior_records_loaded_25_each':all(r['prior_records']==5 for r in cur),
                    'action_authorization_false_all':all(not r['action_authorization'] for r in cur),
                },
                'delta': {
                    'levels_completed':sum(level_deltas),
                    'wins':sum(win_deltas),
                    'public_starter_rhae_score_mean':round(candidate_score - previous_score, 9),
                    'score_regressions':sum(d < -1e-9 for d in score_deltas),
                    'score_improvements':sum(d > 1e-9 for d in score_deltas),
                    'score_ties':sum(abs(d) <= 1e-9 for d in score_deltas),
                    'legal_non_reset_actions':sum(r['legal_non_reset_actions'] for r in cur)-sum(r['legal_non_reset_actions'] for r in prev),
                    'episode_level_regressions':sum(d<0 for d in level_deltas),
                    'episode_level_improvements':sum(d>0 for d in level_deltas),
                    'episode_level_ties':sum(d==0 for d in level_deltas),
                    'episode_win_regressions':sum(d<0 for d in win_deltas),
                    'episode_win_improvements':sum(d>0 for d in win_deltas),
                    'identical_action_traces':sum(a['trace_sha256']==b['trace_sha256'] for a,b in zip(prev,cur)),
                },
                'exceptions':0,
                'scorecard_contract_errors':0,
                'answers_or_hidden_data_read':False,
                'game_ids_or_per_episode_rows_persisted':False,
                'source_bundle_sha256':bundle_sha,
                'bundle_manifest_file_count':len(manifest.get('含有',[])),
            }
        print('SUMMARY ' + json.dumps(summary, separators=(',', ':')), flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',choices=('previous','candidate'))
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--previous-coefficient',type=float,default=0.25)
    parser.add_argument('--candidate-coefficient',type=float,default=0.0)
    args=parser.parse_args()
    if args.previous_coefficient < 0 or args.candidate_coefficient < 0:
        parser.error('visible-change coefficients must be nonnegative')
    if args.child:
        _child(args.child,args.bundle,args.previous_coefficient,args.candidate_coefficient)
    else:
        _parent(Path(__file__).resolve(),args.previous_coefficient,args.candidate_coefficient)
