#!/usr/bin/env python3
"""現行ARC3ソースから私有Kaggle Notebookを再現生成する。"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile
from io import BytesIO
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENT_SOURCE = ROOT / "接続" / "ARC3提出agent.py"
DEFAULT_OUTPUT = ROOT / "出力" / "ARC3-SUBMIT-001"
KERNEL_SLUG = "arc3-hds-hold-baseline"
COMPETITION = "arc-prize-2026-arc-agi-3"
EPOCH = (2026, 10, 22, 0, 0, 0)


def _source_files(*, namespace_entries: set[str] | None = None) -> list[Path]:
    roots = (
        ROOT / "接続",
        ROOT / "HDS" / "学習系統" / "v0.4.2" / "hds学習系統",
    )
    modules: dict[str, Path] = {}
    directories: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"必要なソースディレクトリがありません: {root}")
        package = "接続" if root == roots[0] else "hds学習系統"
        directories[package] = root
        for directory in sorted(root.rglob("*")):
            if not directory.is_dir() or directory.is_symlink() or "__pycache__" in directory.parts:
                continue
            folder_parts = directory.relative_to(root).parts
            directories[".".join((package, *folder_parts))] = directory
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(root).with_suffix("")
            parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
            modules[".".join((package, *parts))] = path
            for depth in range(1, len(relative.parent.parts) + 1):
                folder_parts = relative.parent.parts[:depth]
                directories[".".join((package, *folder_parts))] = root.joinpath(*folder_parts)

    # __init__.pyのないディレクトリもPythonのnamespace packageとして有効。
    namespaces = {name: path for name, path in directories.items() if name not in modules}
    selected_namespaces: set[str] = set()

    # AgentとHDSの公開packageから始め、静的importで到達するrepo内moduleだけを同梱。
    pending = ["接続.ARC3提出agent", "hds学習系統"]
    included: set[str] = set()
    while pending:
        module = pending.pop()
        if module in included or module not in modules:
            continue
        included.add(module)
        path = modules[module]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names)
                for target in targets:
                    if target.split(".", 1)[0] in {"接続", "hds学習系統"} and target not in modules and target not in namespaces:
                        raise ModuleNotFoundError(f"未解決の内部import: {module} -> {target}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".") if package else []
                    keep = max(0, len(parts) - (node.level - 1))
                    base = ".".join(parts[:keep])
                    target = ".".join(part for part in (base, node.module or "") if part)
                else:
                    target = node.module or ""
                if target:
                    if target.split(".", 1)[0] in {"接続", "hds学習系統"} and target not in modules and target not in namespaces:
                        raise ModuleNotFoundError(f"未解決の内部import: {module} -> {target}")
                    targets.append(target)
                    # from package import name は属性か子モジュールか静的には曖昧。
                    # 物理的に存在する子モジュールのみ同梱し、属性の存在判定はimport時に委ねる。
                    targets.extend(f"{target}.{alias.name}" for alias in node.names if f"{target}.{alias.name}" in modules or f"{target}.{alias.name}" in namespaces)
            for target in targets:
                if target in namespaces:
                    selected_namespaces.add(target)
                for candidate in modules:
                    if target == candidate or target.startswith(candidate + "."):
                        if candidate not in included:
                            pending.append(candidate)

    result = [modules[module] for module in sorted(included)]
    if not result:
        raise ValueError("Notebookへ梱包するPythonソースがありません")
    for path in result:
        if path.is_symlink():
            raise ValueError(f"シンボリックリンクは梱包できません: {path}")
        rel = path.relative_to(ROOT).as_posix()
        if not (rel.startswith("接続/") or rel.startswith("HDS/学習系統/v0.4.2/hds学習系統/")):
            raise ValueError(f"許可外の梱包パスです: {rel}")
        if "__pycache__" in path.parts:
            raise ValueError(f"生成キャッシュは梱包できません: {rel}")
    if AGENT_SOURCE not in result:
        raise ValueError("提出Agentのソースが梱包対象にありません")
    if namespace_entries is not None:
        for name in selected_namespaces:
            # 依存ファイルがディレクトリを作らない場合、ZIP展開時に空のnamespaceを復元する。
            if not any(module.startswith(name + ".") for module in included):
                namespace_entries.add(namespaces[name].relative_to(ROOT).as_posix() + "/")
    return result


def _bundle() -> tuple[bytes, dict[str, Any]]:
    namespace_entries: set[str] = set()
    files = _source_files(namespace_entries=namespace_entries)
    records = []
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            records.append({
                "パス": rel,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            info = zipfile.ZipInfo(rel, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for directory in sorted(namespace_entries):
            info = zipfile.ZipInfo(directory, date_time=EPOCH)
            info.external_attr = (0o40755 << 16) | 0x10
            archive.writestr(info, b"")
        manifest = {
            "形式": "arc3-submission-source-v1",
            "含有": records,
            "除外": ["入力/", "記憶/", "検証/運転記録/", ".git/", "認証情報"],
        }
        if namespace_entries:
            manifest["名前空間ディレクトリ"] = sorted(namespace_entries)
        manifest_raw = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        info = zipfile.ZipInfo("ARC3-SOURCE-MANIFEST.json", date_time=EPOCH)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, manifest_raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = archive_buffer.getvalue()
    return payload, manifest


def _code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "metadata": {"trusted": True},
        "outputs": [],
        "execution_count": None,
        "source": source,
    }


def _markdown_cell(source: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def _notebook(owner: str, payload: bytes) -> dict[str, Any]:
    encoded = base64.b64encode(payload).decode("ascii")
    bundle_sha = hashlib.sha256(payload).hexdigest()
    agent_body = AGENT_SOURCE.read_bytes().decode("utf-8")
    setup = """!pip install --no-index --find-links \\
    /kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels \\
    arc-agi python-dotenv"""
    extract = f'''import base64, hashlib, io, json, sys, zipfile
from pathlib import Path, PurePosixPath

_BUNDLE_SHA256 = "{bundle_sha}"
_BUNDLE_B64 = """{encoded}"""
payload = base64.b64decode(_BUNDLE_B64, validate=True)
if hashlib.sha256(payload).hexdigest() != _BUNDLE_SHA256:
    raise RuntimeError("ARC3 source bundle SHA256 mismatch")
root = Path("/tmp/arc3-hds-source")
root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    if archive.testzip() is not None:
        raise RuntimeError("ARC3 source bundle ZIP is corrupt")
    names = archive.namelist()
    for name in names:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or not (
            name.startswith("接続/") or name.startswith("HDS/学習系統/v0.4.2/hds学習系統/")
            or name == "ARC3-SOURCE-MANIFEST.json"
        ):
            raise RuntimeError(f"Unexpected source bundle path: {{name}}")
    archive.extractall(root)
manifest = json.loads((root / "ARC3-SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
for item in manifest["含有"]:
    path = root / PurePosixPath(item["パス"])
    raw = path.read_bytes()
    if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise RuntimeError(f"Source file verification failed: {{item['パス']}}")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "HDS/学習系統/v0.4.2"))
import compileall
if not compileall.compile_dir(str(root / "接続"), quiet=1, force=True):
    raise RuntimeError("Connection source compile failed")
if not compileall.compile_dir(str(root / "HDS/学習系統/v0.4.2/hds学習系統"), quiet=1, force=True):
    raise RuntimeError("HDS source compile failed")
from hds学習系統 import HDS学習系統
from 接続.ARC3境界 import 観測する
from 接続.共通観測経路 import 公開観測から候補を照会する
print("Verified source files:", len(manifest["含有"]))
print("Verified HDS:", HDS学習系統.__module__)
    '''
    write_agent = "%%writefile /tmp/my_agent.py\n" + agent_body
    run = '''import os
from pathlib import Path
import shutil
import subprocess

if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
    subprocess.run(
        ["curl", "--fail", "--retry", "999", "--retry-all-errors",
         "--retry-delay", "5", "--retry-max-time", "600",
         "http://gateway:8001/api/games"],
        check=True,
    )
    framework = Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents")
    working = Path("/kaggle/working/ARC-AGI-3-Agents")
    shutil.copytree(framework, working, dirs_exist_ok=True)
    shutil.copyfile(
        "/tmp/my_agent.py",
        working / "agents/templates/my_agent.py",
    )
    (working / "agents/__init__.py").write_text(
        """from typing import Type
from dotenv import load_dotenv
from .agent import Agent, Playback
from .swarm import Swarm
from .templates.random_agent import Random
from .templates.my_agent import MyAgent
load_dotenv()
AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "random": Random,
    "myagent": MyAgent,
}
""",
        encoding="utf-8",
    )
    (working / ".env").write_text(
        """SCHEME=http
HOST=gateway
PORT=8001
ARC_API_KEY=test-key-123
ARC_BASE_URL=http://gateway:8001/
OPERATION_MODE=online
ENVIRONMENTS_DIR=
RECORDINGS_DIR=/tmp/server_recording
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = "/tmp/arc3-hds-source:/tmp/arc3-hds-source/HDS/学習系統/v0.4.2"
    env["MPLBACKEND"] = "agg"
    subprocess.run(["python", "main.py", "--agent", "myagent"], cwd=working, env=env, check=True)
else:
    # Save & Run Allのdummy parquet。Competition Rerunの得点や受理を表すものではない。
    import pandas as pd
    submission = pd.DataFrame(
        data=[["1_0", "1", True, 1]],
        columns=["row_id", "game_id", "end_of_game", "score"],
    )
    submission.to_parquet("/kaggle/working/submission.parquet", index=False)
    print("Save & Run All placeholder created; no competition score was evaluated.")
'''
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "language": "python",
                "display_name": "Python 3",
                "name": "python3",
            },
            "language_info": {"name": "python", "mimetype": "text/x-python", "file_extension": ".py"},
            "kaggle": {
                "accelerator": "none",
                "isGpuEnabled": False,
                "isInternetEnabled": False,
                "language": "python",
                "sourceType": "notebook",
            },
        },
        "cells": [
            _markdown_cell(
                "# ARC3 HDS HOLD baseline\n\n"
                "現行HDS候補を照会し、確定作用が存在しない場合は操作せず終了する基線です。"
                "Save & Run Allはdummy parquetを作るだけで、Competition Rerunの結果ではありません。"
                "HDS/接続ソースのみを埋め込み、入力・事前記憶・認証情報は含めません。"
            ),
            _code_cell(setup),
            _code_cell(extract),
            _code_cell(write_agent),
            _code_cell(run),
        ],
    }


def _owner_from_kaggle_config() -> str:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    owner = api.get_config_value("username")
    if not isinstance(owner, str) or not owner.strip():
        raise RuntimeError("Kaggle usernameが認証設定にありません")
    return owner.strip()


def _kernel_metadata(owner: str) -> dict[str, Any]:
    return {
        "id": f"{owner}/{KERNEL_SLUG}",
        "title": "ARC3 HDS HOLD baseline",
        "code_file": "submission.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [],
        "kernel_sources": [],
        "competition_sources": [COMPETITION],
        "model_sources": [],
    }


def build(output_dir: Path, owner: str) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"既存出力を上書きしません: {output_dir}")
    if not owner or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in owner):
        raise ValueError("Kaggle usernameの形式が不正です")
    if not AGENT_SOURCE.is_file():
        raise FileNotFoundError(f"提出Agentがありません: {AGENT_SOURCE}")

    payload, manifest = _bundle()
    output_dir.mkdir(parents=True, exist_ok=False)
    notebook_path = output_dir / "submission.ipynb"
    metadata_path = output_dir / "kernel-metadata.json"
    manifest_path = output_dir / "bundle-manifest.json"
    notebook_path.write_text(
        json.dumps(_notebook(owner, payload), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    metadata = _kernel_metadata(owner)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                **manifest,
                "kernel_id": metadata["id"],
                "notebook_sha256": hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
                "source_bundle_sha256": hashlib.sha256(payload).hexdigest(),
                "source_bundle_bytes": len(payload),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return {
        "kernel_id": metadata["id"],
        "files": len(manifest["含有"]),
        "bundle_bytes": len(payload),
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "notebook_sha256": hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
        "output_dir": str(output_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--owner", help="Kaggle username。省略時は認証済み設定を読む")
    args = parser.parse_args(argv)
    owner = args.owner or _owner_from_kaggle_config()
    print(json.dumps(build(args.output_dir, owner), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
