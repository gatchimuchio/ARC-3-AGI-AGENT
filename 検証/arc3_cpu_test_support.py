"""Isolated official Starter fixture for the CPU Agent's synthetic tests."""
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import types
import pytest

STAGE_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = STAGE_ROOT / '接続' / 'ARC3公開探索agent.py'


def starter_dir():
    override = os.getenv('ARC3_STARTER_DIR')
    if override:
        directory = Path(override).expanduser().resolve()
        if not (directory / 'agent.py').is_file():
            pytest.fail('ARC3_STARTER_DIR must point to the official Starter agents directory', pytrace=False)
        return directory
    explicit_root = os.getenv('ARC3_REPO_ROOT')
    roots = [Path(explicit_root).expanduser().resolve()] if explicit_root else [STAGE_ROOT, *STAGE_ROOT.parents]
    for root in roots:
        candidate = root / '入力' / 'Kaggle' / 'ARC-AGI-3-Agents' / 'agents'
        if (candidate / 'agent.py').is_file():
            return candidate
    if explicit_root:
        pytest.fail('ARC3_REPO_ROOT does not contain the official Starter agents directory', pytrace=False)
    pytest.skip('Official Starter not found; place it under 入力/Kaggle or set ARC3_STARTER_DIR', allow_module_level=True)


@contextmanager
def isolated_agents():
    # Restore other repository tests' package modules after loading the fixture.
    saved = {k:v for k,v in tuple(sys.modules.items()) if k=='agents' or k.startswith('agents.')}
    for key in saved:sys.modules.pop(key, None)
    try:
        package = types.ModuleType('agents')
        package.__path__ = [str(starter_dir())]
        sys.modules['agents'] = package
        yield
    finally:
        for key in tuple(sys.modules):
            if key=='agents' or key.startswith('agents.'):
                sys.modules.pop(key, None)
        sys.modules.update(saved)


def load_cpu(path=CANDIDATE, name='arc3_cpu_fixture'):
    with isolated_agents():
        Agent = importlib.import_module('agents.agent').Agent
        spec = importlib.util.spec_from_file_location(name, path)
        if not spec or not spec.loader:
            raise RuntimeError('cannot load test candidate')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return Agent, module


def previous_path():
    path=os.getenv('ARC3_CPU_PREVIOUS_AGENT')
    expected=os.getenv('ARC3_CPU_PREVIOUS_SHA256')
    if not path and not expected:
        pytest.skip('Previous CPU source not supplied; comparative tests are NOT_RUN')
    if not path or not expected:
        pytest.fail('Both ARC3_CPU_PREVIOUS_AGENT and ARC3_CPU_PREVIOUS_SHA256 are required',pytrace=False)
    p=Path(path).expanduser().resolve()
    if not p.is_file():
        pytest.fail('Previous CPU source path is unavailable',pytrace=False)
    if hashlib.sha256(p.read_bytes()).hexdigest().lower()!=expected.lower():
        pytest.fail('Previous CPU source hash mismatch',pytrace=False)
    return p