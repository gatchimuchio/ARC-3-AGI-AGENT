"""Build the pinned public CPU notebook locally; no network or submission."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPETITION = "arc-prize-2026-arc-agi-3"
EXPECTED = {
    "my_agent.py": "32addefe36a2db754b71d71f58d2fb49893c52143bad2fb33985f1e1b5fb1c0c",
    "main.py": "96675962f7e0678e450b76f3c46514eda13b253df7caa2c9e9bc49c7367004da",
    "swarm.py": "f2e6c1ee1814d30cd10b47ed3d58eeb3e79ef0512dd666c05d8d06804e11b5ee",
    "STARTER-MIT-LICENSE.txt": "75c4276c506fd93082b38ad39f67ee97aa859574401ef978e701710c7a40af04",
}
MARKDOWN = '# Experimental CPU Agent\n\nNo HDS. Save & Run creates a placeholder only; competition performance is unverified.\n'
SETUP = "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links',\n    '/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels',\n    'arc-agi==0.9.8', 'arcengine==0.9.3', 'python-dotenv==1.2.2'], check=True)\n"
EXTRACT_TEMPLATE = "import base64, hashlib\nfrom pathlib import Path\nentries = @@ENTRIES@@\nroot = Path('/tmp/arc3-cpu-agent')\nroot.mkdir(parents=True, exist_ok=True)\nfor name, meta in entries.items():\n    data = base64.b64decode(meta['bytes'], validate=True)\n    if hashlib.sha256(data).hexdigest() != meta['sha256']:\n        raise RuntimeError('source integrity failure')\n    (root / name).write_bytes(data)\n"
RUN = 'import os, shutil, subprocess, sys\nfrom pathlib import Path\nflag = os.environ.get(\'KAGGLE_IS_COMPETITION_RERUN\', \'\').strip().lower()\nif flag not in (\'\', \'0\', \'false\', \'1\', \'true\'):\n    raise RuntimeError(\'Unknown competition rerun flag\')\nif flag in (\'1\', \'true\'):\n    # Only wait for the socket; the authenticated starter owns game enumeration.\n    # A listening socket does not itself prove that the API is ready.\n    import socket, time\n    deadline = time.monotonic() + 120\n    while True:\n        try:\n            with socket.create_connection((\'gateway\', 8001), timeout=3):\n                break\n        except OSError:\n            if time.monotonic() >= deadline:\n                raise RuntimeError(\'Gateway socket did not become available\') from None\n            time.sleep(2)\n    source = Path(\'/kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents\')\n    working = Path(\'/tmp/arc3-cpu-starter\')\n    shutil.copytree(source, working, dirs_exist_ok=False)\n    for original, destination in [(\'my_agent.py\', \'agents/templates/my_agent.py\'),\n                                  (\'main.py\', \'main.py\'), (\'swarm.py\', \'agents/swarm.py\')]:\n        shutil.copyfile(Path(\'/tmp/arc3-cpu-agent\') / original, working / destination)\n    (working / \'agents/__init__.py\').write_text(\n        \'from typing import Type\\nfrom dotenv import load_dotenv\\nfrom .agent import Agent, Playback\\n\'\n        \'from .swarm import Swarm\\nfrom .templates.random_agent import Random\\n\'\n        \'from .templates.my_agent import MyAgent\\nload_dotenv()\\n\'\n        \'AVAILABLE_AGENTS: dict[str, Type[Agent]] = {"random": Random, "myagent": MyAgent}\\n\', encoding=\'utf8\')\n    (working / \'.env\').write_text(\'SCHEME=http\\nHOST=gateway\\nPORT=8001\\nARC_API_KEY=test-key-123\\n\'\n        \'ARC_BASE_URL=http://gateway:8001/\\nOPERATION_MODE=online\\nENVIRONMENTS_DIR=\\n\'\n        \'RECORDINGS_DIR=/tmp/server_recording\\n\', encoding=\'utf8\')\n    env = dict(os.environ, MPLBACKEND=\'agg\', PYTHONUTF8=\'1\', PYTHONDONTWRITEBYTECODE=\'1\')\n    env.pop(\'PYTHONPATH\', None)\n    subprocess.run([sys.executable, \'main.py\', \'--agent\', \'myagent\'], cwd=working, env=env, check=True)\n    print(\'Competition runner exited; output contract and official score remain unverified.\')\nelse:\n    import pandas as pd\n    pd.DataFrame([[\'1_0\', \'1\', True, 1]], columns=[\'row_id\', \'game_id\', \'end_of_game\', \'score\']).to_parquet(\n        \'/kaggle/working/submission.parquet\', index=False)\n    print(\'Placeholder only; no Agent gameplay or official score.\')\n'
NB_METADATA = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}, 'kaggle': {'accelerator': 'none', 'isGpuEnabled': False, 'isInternetEnabled': False, 'language': 'python', 'sourceType': 'notebook'}}


def build(repo_root: Path, output_dir: Path, *, owner: str, slug: str, title: str) -> dict[str, str]:
    """Require exact pinned source, create one new output directory; never push."""
    if output_dir.exists():
        raise FileExistsError("output already exists")
    if not owner or not slug or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in owner+slug):
        raise ValueError("invalid owner or slug")
    if not title.strip():
        raise ValueError("title required")
    inputs = {"my_agent.py": repo_root / "接続" / "ARC3公開探索agent.py",
              "main.py": HERE / "starter" / "main.py",
              "swarm.py": HERE / "starter" / "swarm.py",
              "STARTER-MIT-LICENSE.txt": repo_root / "STARTER-MIT-LICENSE.txt"}
    entries = {}
    snapshots = {}
    for name, path in inputs.items():
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != EXPECTED[name]:
            raise ValueError("pinned source mismatch")
        snapshots[name] = raw
        entries[name] = {"sha256": digest, "bytes": base64.b64encode(raw).decode("ascii")}
    extract = EXTRACT_TEMPLATE.replace("@@ENTRIES@@", repr(entries))
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": NB_METADATA,
        "cells": [{"cell_type": "markdown", "metadata": {}, "source": MARKDOWN}] +
                 [{"cell_type": "code", "metadata": {}, "execution_count": None,
                   "outputs": [], "source": source} for source in (SETUP, extract, RUN)]}
    payload = (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    metadata = {"id": f"{owner}/{slug}", "title": title, "code_file": "cpu-prototype.ipynb",
                "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
                "dataset_sources": [], "kernel_sources": [], "competition_sources": [COMPETITION],
                "model_sources": []}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "cpu-prototype.ipynb").write_bytes(payload)
    (output_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output_dir / "STARTER-MIT-LICENSE.txt").write_bytes(snapshots["STARTER-MIT-LICENSE.txt"])
    return {"notebook_sha256": hashlib.sha256(payload).hexdigest(), "agent_sha256": EXPECTED["my_agent.py"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root, args.output_dir, owner=args.owner, slug=args.slug, title=args.title)))


if __name__ == "__main__":
    main()
