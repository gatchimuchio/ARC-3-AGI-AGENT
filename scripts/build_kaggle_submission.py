"""Build the deterministic ARC-AGI-3 GenericAGIRuntime Kaggle Notebook."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path
from textwrap import dedent
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = ROOT / "ARC-AGI-3-Agents"
PACKAGE_ROOT = AGENTS_ROOT / "arc3_agi_agent"
AGENT_SOURCE = AGENTS_ROOT / "agents" / "templates" / "generic_agi_agent.py"
DEFAULT_OUTPUT_DIR = ROOT / "kaggle_notebooks"
COMPETITION_SLUG = "arc-prize-2026-arc-agi-3"
DEFAULT_USERNAME = "tecchannn"
DEFAULT_NOTEBOOK_SLUG = "arc3-genericagiruntime-p15"
ACTION_BUDGET = 128
OFFICIAL_PLACEHOLDER_PARQUET_SHA256 = (
    "688e716e8f9ad967f6211a3796070b69c74a5adb5ce93e9f1c0ba77701ea3194"
)
OFFICIAL_PLACEHOLDER_PARQUET_SIZE = 2648
OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64 = (
    "eNq9Vl1v4kYUHUiWJG20yka1ZUt5QEhBrZRNsQnpehVVskn5SCG7sBu+2gp5bENMbEOxgThRqj5V"
    "far6A/pD+tDH/o/uT+ncsXEIbFZaqaqFPPY5d865M3euxWu5LjDrzFNmt8LEGbSL0Aa3hhASuhkG"
    "MbsMe0DgHSbBJPaO0edrBObg9uwZidlKxsk9HovFEZH4hHk6l3iyEwOJ9wjEBC4mrExG4A9xiMZx"
    "sRj5sSQaRhq9wYXRxGiH+WxutLkHRnAte3Gbc+b+iSi+B11dCv99DnEJV7s0bJXZRMz2fpxLjIez"
    "rqnvo8oeuAG00VdtYwFDBPvUcPTusNcFiigR5ImrDccGYuP8Hl9Joz1mm8+hxA4/V2TibJz9if0l"
    "lj5Oby7vMX9A1osYukU7ZDhhE3yCTyNIdlFrngoVG7M36T9j6d9iixu+qhR/oIT4/QTiH+RPxd6y"
    "rfSv8ZOVkvBkCtU7+WJRZj1MKFg1Vfgrxv4dS/++ln4X/7iqrKQcObE/r7Px9Cb7xzoJ4hIj1dFV"
    "l/tn/TZlOrpx3dWG1sR23NTL5Hc/HCRTwWuXcsYSSl9vUw5ZL3lKBTVJEbpnGpbeXcUDs67njygx"
    "cUxtqBvAOBN75EfEEA8MzQPcNjxVVz2VoM7Esu4Okvd+Yd1WDReI/9ZxocCrrkvkkjMeDq1V2zn6"
    "IVN6GlbtInjJyHS846NVpwhetoJyqp43NvHEowW+vYMCjw3VG47hNWWZeKyOfVAZ+eqYlBN0psbY"
    "NYcOoGL2MHMopO7uk1kkD7OH2dQd4rblev1V82XwaeDebX0J17F8KstyTQ6ub2X5SFb6ckGW+3K+"
    "TzFFecDPYPwm4s9q+eB9rkL5MowKHSFIcWFQgCm8IPHKV2XbmnSKjaOWeD7FpYaHnar5ylRw682s"
    "X7ZDzJJG2K5bRrFxUx4M+00h45bzZwMsXgu4mQuwrGtiu+B13pSPCefjrN5TmzWzkpfNjm1ZuFjv"
    "PcZrxQLJoXDTytZzWvGC+Mum3syN2qJ0ReLBa6I3hZnRkDJGS7HAr2xLpmo3Bnqe8l6nVb8kGpk2"
    "6BdzAi5eS5U8rC93iZuBZkck/g1p1Anm2Gqz4XYK0qTdFEJNncQ2/v+8mrmrlijZLVGn2CN7ZpEa"
    "9LDY6dF1BP6zNpnbbp339JI1C+NMLEpu2YT6Eb+WklvMv21LU/wRuWnkXGj2ozndkL3wP5DLCDs1"
    "8Tz/2F5ZE/20nQlyFSy9WCDz65fAYafh4pKggy/BMpptmXqrbmk+0S15EsWzZxbhppoJGDl/RcvU"
    "7IJvBN4zo1nwNVvKUn2nY2nO+QiLR3Rd1UF1Us0fXZedzMPc7YavidYUg2a+7Fcgzj+TZLkN/RPG"
    "VcMmy7vQSpocdR69669JP0P71cq1sAkXWpuowGPpfIBJ/vBOGrEK/anMwlC4LijjwqeB9v6lHFkp"
    "UZBcgdvS+ZGH4C8NyO0FpFSgSSn9+ywjKcWBs98SrSu5SuNrkBzJpwj8aWgWTapd0EWUltcD0qWz"
    "qS6Q3oqm3POIS47U8Y8Tw3uujUbP6YczGX4Yk8Enk4c/P9EPfb2F0Gvyn/JfSYasXQ=="
)
RUNTIME_MODULES = (
    "generic_compute.py",
    "generic_competition_runner.py",
    "generic_env.py",
    "generic_hds.py",
    "generic_memory.py",
    "generic_runtime.py",
    "generic_structural.py",
    "generic_types.py",
    "ir.py",
    "sample_observation.py",
    "schema.py",
    "verification.py",
)
FORBIDDEN_RUNTIME_CONTENT = (
    "from .teacher",
    "import .teacher",
    "s5_rendered_policy",
    "full_solution_corpus",
    "level_solution_graph",
    "environment_files",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    return info


def _validate_relative_import_closure() -> None:
    allowed = {Path(name).stem for name in RUNTIME_MODULES}
    missing: set[str] = set()
    for name in RUNTIME_MODULES:
        path = PACKAGE_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module
            ):
                dependency = node.module.split(".", 1)[0]
                if dependency not in allowed:
                    missing.add(dependency)
    if missing:
        raise RuntimeError(
            "KAGGLE_RUNTIME_IMPORT_CLOSURE_INCOMPLETE:"
            + ",".join(sorted(missing))
        )


def build_runtime_archive() -> tuple[bytes, dict[str, object]]:
    _validate_relative_import_closure()
    members: list[tuple[str, bytes]] = [
        (
            "arc3_agi_agent/__init__.py",
            (
                '"""Minimal official GenericAGIRuntime package."""\n'
                "__all__: list[str] = []\n"
            ).encode("utf-8"),
        )
    ]
    module_digests: dict[str, str] = {}
    for name in RUNTIME_MODULES:
        data = (PACKAGE_ROOT / name).read_bytes()
        lowered = data.decode("utf-8").casefold()
        findings = [
            term for term in FORBIDDEN_RUNTIME_CONTENT if term in lowered
        ]
        if findings:
            raise RuntimeError(
                f"KAGGLE_RUNTIME_FORBIDDEN_CONTENT:{name}:{findings}"
            )
        module_digests[name] = _sha256(data)
        members.append((f"arc3_agi_agent/{name}", data))
    manifest: dict[str, object] = {
        "schema_version": "arc3-kaggle-runtime-package-v1",
        "action_budget": ACTION_BUDGET,
        "runtime_modules": list(RUNTIME_MODULES),
        "module_sha256": module_digests,
        "teacher_included": False,
        "known_sample_policy_included": False,
        "runtime_identity_routing_included": False,
    }
    members.append(
        (
            "ARC3_KAGGLE_RUNTIME_MANIFEST.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
        )
    )
    members.sort(key=lambda item: item[0])
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name, data in members:
            archive.writestr(_zip_info(name), data)
    payload = buffer.getvalue()
    manifest["archive_sha256"] = _sha256(payload)
    manifest["archive_size_bytes"] = len(payload)
    manifest["member_names"] = [name for name, _ in members]
    return payload, manifest


def _code_cell(source: str, *, cell_id: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {"trusted": True},
        "outputs": [],
        "source": source,
    }


def build_notebook() -> tuple[dict[str, object], dict[str, object]]:
    runtime_archive, runtime_manifest = build_runtime_archive()
    agent_data = AGENT_SOURCE.read_bytes()
    agent_text = agent_data.decode("utf-8")
    for term in FORBIDDEN_RUNTIME_CONTENT:
        if term in agent_text.casefold():
            raise RuntimeError(
                f"KAGGLE_AGENT_FORBIDDEN_CONTENT:{term}"
            )
    compile(agent_text, str(AGENT_SOURCE), "exec")
    archive_b64 = base64.b64encode(runtime_archive).decode("ascii")
    agent_b64 = base64.b64encode(agent_data).decode("ascii")
    archive_digest = _sha256(runtime_archive)
    agent_digest = _sha256(agent_data)

    install_cell = _code_cell(
        dedent(
            """\
            import base64
            import hashlib
            import json
            import os
            import subprocess
            import sys
            import traceback
            import zlib
            from pathlib import Path

            competition_rerun = bool(
                os.getenv("KAGGLE_IS_COMPETITION_RERUN")
            )
            install_status = {
                "schema_version": "arc3-private-install-status-v1",
                "status": "NOT_STARTED",
                "error_type": None,
                "error_message": None,
            }
            if competition_rerun:
                fallback_path = Path("/kaggle/working/submission.parquet")
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                fallback_bytes = zlib.decompress(
                    base64.b64decode(
                        "__OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64__"
                    )
                )
                assert (
                    len(fallback_bytes)
                    == __OFFICIAL_PLACEHOLDER_PARQUET_SIZE__
                )
                assert (
                    hashlib.sha256(fallback_bytes).hexdigest()
                    == "__OFFICIAL_PLACEHOLDER_PARQUET_SHA256__"
                )
                fallback_path.write_bytes(fallback_bytes)
                print({
                    "preexecution_fallback": str(fallback_path),
                    "fallback_size_bytes": fallback_path.stat().st_size,
                    "fallback_sha256": hashlib.sha256(
                        fallback_path.read_bytes()
                    ).hexdigest(),
                })

            wheel_dir = Path(
                "/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels"
            )
            try:
                if wheel_dir.is_dir():
                    subprocess.check_call([
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--no-index",
                        "--find-links",
                        str(wheel_dir),
                        "arc-agi",
                        "python-dotenv",
                    ])
                    install_status["status"] = "COMPLETE"
                elif os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
                    raise FileNotFoundError(
                        "ARC3 competition wheel bundle is missing during rerun"
                    )
                else:
                    install_status["status"] = "NORMAL_RUN_NOT_MOUNTED"
                    print(
                        "Regular run: competition wheel bundle is not mounted; "
                        "the official placeholder contract will be validated only"
                    )
            except Exception as error:
                install_status["status"] = "INSTALL_EXCEPTION"
                install_status["error_type"] = type(error).__name__
                install_status["error_message"] = str(error)[:2000]
                traceback.print_exc()
                if not competition_rerun:
                    raise
            finally:
                if competition_rerun:
                    install_status_path = Path(
                        "/kaggle/working/arc3_install_status.json"
                    )
                    try:
                        install_status_path.write_text(
                            json.dumps(install_status, sort_keys=True) + "\\n",
                            encoding="utf-8",
                        )
                    except Exception:
                        traceback.print_exc()
                    print(
                        "ARC3 private install status: "
                        + json.dumps(install_status, sort_keys=True)
                    )
            """
        )
        .replace(
            "__OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64__",
            OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64,
        )
        .replace(
            "__OFFICIAL_PLACEHOLDER_PARQUET_SIZE__",
            str(OFFICIAL_PLACEHOLDER_PARQUET_SIZE),
        )
        .replace(
            "__OFFICIAL_PLACEHOLDER_PARQUET_SHA256__",
            OFFICIAL_PLACEHOLDER_PARQUET_SHA256,
        ),
        cell_id="install-official-offline-wheels",
    )
    payload_cell = _code_cell(
        dedent(
            f"""\
            import base64
            import hashlib
            import json
            import os
            import shutil
            import traceback
            import zipfile
            from pathlib import Path

            competition_rerun = bool(
                os.getenv("KAGGLE_IS_COMPETITION_RERUN")
            )
            payload_ready = False
            payload_status = {{
                "schema_version": "arc3-private-payload-status-v1",
                "status": "NOT_STARTED",
                "error_type": None,
                "error_message": None,
            }}
            try:
                runtime_archive = base64.b64decode({archive_b64!r})
                expected_runtime_sha256 = {archive_digest!r}
                assert (
                    hashlib.sha256(runtime_archive).hexdigest()
                    == expected_runtime_sha256
                )
                runtime_zip = Path("/tmp/arc3_generic_runtime.zip")
                runtime_zip.write_bytes(runtime_archive)

                payload_root = Path("/tmp/arc3_generic_payload")
                if payload_root.exists():
                    shutil.rmtree(payload_root)
                payload_root.mkdir(parents=True)
                with zipfile.ZipFile(runtime_zip) as archive:
                    archive.extractall(payload_root)

                agent_source = base64.b64decode({agent_b64!r})
                expected_agent_sha256 = {agent_digest!r}
                assert (
                    hashlib.sha256(agent_source).hexdigest()
                    == expected_agent_sha256
                )
                agent_path = payload_root / "generic_agi_agent.py"
                agent_path.write_bytes(agent_source)
                payload_ready = True
                payload_status["status"] = "COMPLETE"
                print({{
                    "runtime_sha256": expected_runtime_sha256,
                    "runtime_size_bytes": len(runtime_archive),
                    "agent_sha256": expected_agent_sha256,
                    "agent_size_bytes": len(agent_source),
                }})
            except Exception as error:
                payload_status["status"] = "PAYLOAD_EXCEPTION"
                payload_status["error_type"] = type(error).__name__
                payload_status["error_message"] = str(error)[:2000]
                traceback.print_exc()
                if not competition_rerun:
                    raise
            finally:
                if competition_rerun:
                    payload_status_path = Path(
                        "/kaggle/working/arc3_payload_status.json"
                    )
                    try:
                        payload_status_path.write_text(
                            json.dumps(payload_status, sort_keys=True) + "\\n",
                            encoding="utf-8",
                        )
                    except Exception:
                        traceback.print_exc()
                    print(
                        "ARC3 private payload status: "
                        + json.dumps(payload_status, sort_keys=True)
                    )
            """
        ),
        cell_id="verify-runtime-payload",
    )
    run_cell = _code_cell(
        dedent(
            """\
            import os
            import json
            import shutil
            import subprocess
            import sys
            import time
            import traceback
            import urllib.error
            import urllib.request
            from pathlib import Path

            payload_root = Path("/tmp/arc3_generic_payload")
            if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
                runtime_status_path = Path(
                    "/kaggle/working/arc3_runtime_status.json"
                )
                runtime_status = {{
                    "schema_version": "arc3-private-runtime-status-v1",
                    "status": "STARTED",
                    "runner_returncode": None,
                    "error_type": None,
                    "error_message": None,
                }}
                try:
                    if not globals().get("payload_ready", False):
                        raise RuntimeError(
                            "ARC3 verified runtime payload is unavailable"
                        )
                    gateway = "http://gateway:8001/api/games"
                    deadline = time.time() + 600
                    while True:
                        try:
                            with urllib.request.urlopen(
                                gateway,
                                timeout=10,
                            ) as response:
                                if response.status < 500:
                                    break
                        except (urllib.error.URLError, TimeoutError):
                            pass
                        if time.time() >= deadline:
                            raise TimeoutError(
                                "ARC3 competition gateway did not become ready "
                                "within 600 seconds"
                            )
                        time.sleep(5)

                    competition_root = Path(
                        "/kaggle/input/competitions/arc-prize-2026-arc-agi-3"
                    )
                    framework_src = competition_root / "ARC-AGI-3-Agents"
                    framework_dst = Path(
                        "/kaggle/working/ARC-AGI-3-Agents"
                    )
                    if framework_dst.exists():
                        shutil.rmtree(framework_dst)
                    shutil.copytree(
                        framework_src,
                        framework_dst,
                        ignore=shutil.ignore_patterns(
                            ".git",
                            "__pycache__",
                            ".pytest_cache",
                            ".ruff_cache",
                        ),
                    )

                    runtime_dst = framework_dst / "arc3_agi_agent"
                    if runtime_dst.exists():
                        shutil.rmtree(runtime_dst)
                    shutil.copytree(
                        payload_root / "arc3_agi_agent",
                        runtime_dst,
                    )
                    shutil.copy2(
                        payload_root / "generic_agi_agent.py",
                        framework_dst
                        / "agents"
                        / "templates"
                        / "generic_agi_agent.py",
                    )

                    agents_init = '''from typing import Type
            from dotenv import load_dotenv
            from .agent import Agent, Playback
            from .swarm import Swarm
            from .templates.generic_agi_agent import GenericAGIAgent

            load_dotenv()

            AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
                "genericagi": GenericAGIAgent,
            }
            '''
                    (framework_dst / "agents" / "__init__.py").write_text(
                        agents_init,
                        encoding="utf-8",
                    )
                    env_body = '''SCHEME=http
            HOST=gateway
            PORT=8001
            ARC_API_KEY=test-key-123
            ARC_BASE_URL=http://gateway:8001/
            OPERATION_MODE=online
            ENVIRONMENTS_DIR=
            RECORDINGS_DIR=/kaggle/working/server_recording
            '''
                    (framework_dst / ".env").write_text(
                        env_body,
                        encoding="utf-8",
                    )

                    run_env = os.environ.copy()
                    run_env["MPLBACKEND"] = "agg"
                    completed_process = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "arc3_agi_agent.generic_competition_runner",
                        ],
                        cwd=framework_dst,
                        env=run_env,
                        check=False,
                    )
                    runtime_status["runner_returncode"] = (
                        completed_process.returncode
                    )
                    runtime_status["status"] = (
                        "COMPLETE"
                        if completed_process.returncode == 0
                        else "RUNNER_NONZERO"
                    )
                    if completed_process.returncode != 0:
                        print(
                            "ARC3 private runner returned nonzero: "
                            f"{{completed_process.returncode}}",
                            file=sys.stderr,
                        )
                except Exception as error:
                    runtime_status["status"] = "BOOTSTRAP_EXCEPTION"
                    runtime_status["error_type"] = type(error).__name__
                    runtime_status["error_message"] = str(error)[:2000]
                    traceback.print_exc()
                finally:
                    try:
                        runtime_status_path.write_text(
                            json.dumps(runtime_status, sort_keys=True) + "\\n",
                            encoding="utf-8",
                        )
                    except Exception:
                        traceback.print_exc()
                    print(
                        "ARC3 private runtime status: "
                        + json.dumps(runtime_status, sort_keys=True)
                    )
            """
        ),
        cell_id="execute-generic-runtime",
    )
    placeholder_cell = _code_cell(
        dedent(
            """\
            # Non-rerun mode: produce the official ARC-AGI-3 placeholder.
            import os
            import pandas as pd

            if not os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
                submission = pd.DataFrame(
                    data=[["1_0", "1", True, 1]],
                    columns=["row_id", "game_id", "end_of_game", "score"],
                )
                submission.to_parquet(
                    "/kaggle/working/submission.parquet",
                    index=False,
                )
            """
        ),
        cell_id="write-official-placeholder",
    )
    notebook: dict[str, object] = {
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "pygments_lexer": "ipython3",
            },
            "kaggle": {
                "accelerator": "none",
                "isGpuEnabled": False,
                "isInternetEnabled": False,
                "language": "python",
                "sourceType": "notebook",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
        "cells": [
            install_cell,
            payload_cell,
            run_cell,
            placeholder_cell,
        ],
    }
    build_report = {
        "schema_version": "arc3-kaggle-notebook-build-v3",
        "competition": COMPETITION_SLUG,
        "action_budget_per_game": ACTION_BUDGET,
        "preexecution_fallback": {
            "source": "official pinned Notebook normal-run output",
            "sha256": OFFICIAL_PLACEHOLDER_PARQUET_SHA256,
            "size_bytes": OFFICIAL_PLACEHOLDER_PARQUET_SIZE,
        },
        "runtime_archive": runtime_manifest,
        "agent_sha256": agent_digest,
        "agent_size_bytes": len(agent_data),
        "notebook_cell_count": len(notebook["cells"]),  # type: ignore[arg-type]
    }
    return notebook, build_report


def build_metadata(
    *,
    username: str,
    notebook_slug: str,
) -> dict[str, object]:
    return {
        "id": f"{username}/{notebook_slug}",
        "title": "ARC3 GenericAGIRuntime P15",
        "code_file": "submission.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": [],
        "dataset_sources": [],
        "kernel_sources": [],
        "competition_sources": [COMPETITION_SLUG],
        "model_sources": [],
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username",
        default=os.getenv("KAGGLE_USERNAME", DEFAULT_USERNAME),
    )
    parser.add_argument(
        "--notebook-slug",
        default=DEFAULT_NOTEBOOK_SLUG,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    notebook, build_report = build_notebook()
    metadata = build_metadata(
        username=str(arguments.username),
        notebook_slug=str(arguments.notebook_slug),
    )
    notebook_data = (
        json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    metadata_data = (
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    (output_dir / "submission.ipynb").write_bytes(notebook_data)
    (output_dir / "kernel-metadata.json").write_bytes(metadata_data)
    build_report["notebook_sha256"] = _sha256(notebook_data)
    build_report["notebook_size_bytes"] = len(notebook_data)
    build_report["metadata_sha256"] = _sha256(metadata_data)
    build_report["metadata"] = metadata
    report_data = (
        json.dumps(build_report, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (output_dir / "build-report.json").write_bytes(report_data)
    print(
        json.dumps(
            {
                "notebook": str(output_dir / "submission.ipynb"),
                "notebook_sha256": build_report["notebook_sha256"],
                "runtime_archive_sha256": build_report["runtime_archive"][
                    "archive_sha256"
                ],
                "agent_sha256": build_report["agent_sha256"],
                "metadata_id": metadata["id"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
