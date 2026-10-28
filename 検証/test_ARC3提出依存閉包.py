"""提出bundleの静的検出範囲とfresh importの境界を検証する。"""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import types
import zipfile

import pytest


MAIN_ROOT = Path(__file__).resolve().parents[1]
STARTER = Path(os.environ.get("ARC3_STARTER_ROOT", MAIN_ROOT / "入力/Kaggle/ARC-AGI-3-Agents/agents"))


def load_builder(path: Path, root: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("builder_check", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    module.AGENT_SOURCE = root / "接続/ARC3提出agent.py"
    return module


@pytest.fixture
def builder():
    return load_builder(MAIN_ROOT / "道具/ARC3提出物構築.py", MAIN_ROOT)


def fake_project(root: Path, code: str, *, package: str | None = "", child: str | None = None) -> Path:
    connection = root / "接続"
    hds = root / "HDS/学習系統/v0.4.2/hds学習系統"
    connection.mkdir(parents=True)
    hds.mkdir(parents=True)
    if package is not None:
        (connection / "__init__.py").write_text(package, encoding="utf-8")
    (connection / "ARC3提出agent.py").write_text(code, encoding="utf-8")
    if child is not None:
        (connection / "子.py").write_text(child, encoding="utf-8")
    (hds / "__init__.py").write_text("", encoding="utf-8")
    return root


def isolated_import(payload: bytes, root: Path, *, starter: bool = False) -> subprocess.CompletedProcess[str]:
    dest = root / "unpacked"
    dest.mkdir()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(dest)
    code = """
import importlib, sys, types
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'HDS/学習系統/v0.4.2'))
if len(sys.argv) > 2:
    package = types.ModuleType('agents')
    package.__path__ = [sys.argv[2]]
    sys.modules['agents'] = package
importlib.import_module('接続.ARC3提出agent')
"""
    args = [sys.executable, "-I", "-B", "-X", "utf8", "-c", code, str(dest)]
    if starter:
        args.append(str(STARTER))
    return subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=60)


def test_real_bundle_imports_fresh(builder, tmp_path):
    if not (STARTER / "agent.py").is_file():
        pytest.skip("実Starterを含む ARC3_STARTER_ROOT が必要")
    payload, manifest = builder._bundle()
    assert "接続/ARC3提出agent.py" in {item["パス"] for item in manifest["含有"]}
    result = isolated_import(payload, tmp_path, starter=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("statement", [
    "import 接続.未存在\n",
    "from 接続.未存在 import 値\n",
    "from .未存在 import 値\n",
    "import hds学習系統.未存在\n",
])
def test_missing_internal_module_fails_closed(builder, tmp_path, statement):
    builder.ROOT = fake_project(tmp_path / "source", statement)
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    with pytest.raises(ModuleNotFoundError, match="未解決の内部import"):
        builder._bundle()


def test_package_attribute_is_not_mistaken_for_missing_child_module(builder, tmp_path):
    builder.ROOT = fake_project(tmp_path / "source", "from 接続 import 値\n", package="値 = 123\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, _ = builder._bundle()
    result = isolated_import(payload, tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("statement", ["from 接続 import 子\n", "from . import 子\n"])
def test_existing_package_child_is_included_and_imported(builder, tmp_path, statement):
    builder.ROOT = fake_project(tmp_path / "source", statement, child="値 = 1\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, manifest = builder._bundle()
    assert "接続/子.py" in {item["パス"] for item in manifest["含有"]}
    result = isolated_import(payload, tmp_path)
    assert result.returncode == 0, result.stderr


def test_ambiguous_from_name_requires_fresh_import_check(builder, tmp_path):
    builder.ROOT = fake_project(tmp_path / "source", "from 接続 import 未存在\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, _ = builder._bundle()
    result = isolated_import(payload, tmp_path)
    assert result.returncode != 0
    assert "ImportError" in result.stderr


def test_missing_attribute_is_detected_by_fresh_import(builder, tmp_path):
    builder.ROOT = fake_project(tmp_path / "source", "from 接続.子 import 未存在\n", child="値 = 1\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, _ = builder._bundle()
    result = isolated_import(payload, tmp_path)
    assert result.returncode != 0
    assert "ImportError" in result.stderr


def test_import_time_dynamic_dependency_requires_fresh_import_check(builder, tmp_path):
    builder.ROOT = fake_project(tmp_path / "source", "import importlib\nimportlib.import_module('接続.未存在')\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, _ = builder._bundle()
    result = isolated_import(payload, tmp_path)
    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr


@pytest.mark.parametrize("statement", ["from 接続 import 子\n", "from . import 子\n"])
def test_namespace_root_and_child_module_are_supported(builder, tmp_path, statement):
    builder.ROOT = fake_project(tmp_path / "source", statement, package=None, child="値 = 1\n")
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    payload, manifest = builder._bundle()
    assert "接続/子.py" in {item["パス"] for item in manifest["含有"]}
    result = isolated_import(payload, tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("statement", ["from 接続.外.内 import 子\n", "from .外.内 import 子\n"])
def test_multi_level_namespace_child_module_is_supported(builder, tmp_path, statement):
    builder.ROOT = fake_project(tmp_path / "source", statement, package=None)
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    nested = builder.ROOT / "接続/外/内"
    nested.mkdir(parents=True)
    (nested / "子.py").write_text("値 = 1\n", encoding="utf-8")
    payload, _ = builder._bundle()
    result = isolated_import(payload, tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("statement,marker,contains_file", [
    ("from 接続 import 外\n", "接続/外/", True),
    ("import 接続.外.内\n", "接続/外/内/", True),
    ("from 接続 import 外\n", "接続/外/", False),
    ("import 接続.外.内\n", "接続/外/内/", False),
])
def test_namespace_only_import_materializes_directory(builder, tmp_path, statement, marker, contains_file):
    builder.ROOT = fake_project(tmp_path / "source", statement, package=None)
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    nested = builder.ROOT / "接続/外/内"
    nested.mkdir(parents=True)
    if contains_file:
        (nested / "子.py").write_text("値 = 1\n", encoding="utf-8")
    payload, manifest = builder._bundle()
    assert marker in manifest["名前空間ディレクトリ"]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert marker in archive.namelist()
        # 未参照のソースをディレクトリ生成のためだけに同梱しない。
        assert "接続/外/内/子.py" not in archive.namelist()
    result = isolated_import(payload, tmp_path)
    assert result.returncode == 0, result.stderr


def test_missing_multi_level_namespace_fails_closed(builder, tmp_path):
    builder.ROOT = fake_project(tmp_path / "source", "from 接続.不存在.内 import 子\n", package=None)
    builder.AGENT_SOURCE = builder.ROOT / "接続/ARC3提出agent.py"
    with pytest.raises(ModuleNotFoundError, match="未解決の内部import"):
        builder._bundle()
