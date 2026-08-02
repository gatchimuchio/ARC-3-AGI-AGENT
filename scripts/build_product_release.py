"""Build the deterministic ARC3CompletionAgent v1.0 release wheel."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Sequence

from build_kaggle_submission import (
    AGENT_SOURCES,
    AGENTS_ROOT,
    build_runtime_archive,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ID = "ARC3CompletionAgent"
PRODUCT_VERSION = "1.0.0"
DISTRIBUTION_NAME = "arc3_completion_agent"
WHEEL_FILENAME = f"{DISTRIBUTION_NAME}-{PRODUCT_VERSION}-py3-none-any.whl"
DIST_INFO = f"{DISTRIBUTION_NAME}-{PRODUCT_VERSION}.dist-info"
DEFAULT_OUTPUT_DIR = ROOT / "release" / "ARC3CompletionAgent-v1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_digest(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
    return "sha256=" + encoded.rstrip(b"=").decode("ascii")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    return info


def _agents_init() -> bytes:
    return (
        "from .agent import Agent\n"
        "from .templates.arc3_completion_agent import ARC3CompletionAgent\n"
        "AVAILABLE_AGENTS = {'arc3completion': ARC3CompletionAgent}\n"
        "__all__ = ['AVAILABLE_AGENTS', 'ARC3CompletionAgent', 'Agent']\n"
    ).encode("utf-8")


def _metadata() -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        "Name: arc3-completion-agent\n"
        f"Version: {PRODUCT_VERSION}\n"
        "Summary: Identity-free ARC-AGI-3 completion agent\n"
        "Requires-Python: >=3.12\n"
        "Requires-Dist: arc-agi==0.9.8\n"
        "Requires-Dist: numpy==2.3.2\n"
        "\n"
    ).encode("utf-8")


def _wheel_metadata() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: arc3-product-release-v1\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
        "\n"
    ).encode("utf-8")


def _record(members: dict[str, bytes]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for name, data in sorted(members.items()):
        writer.writerow((name, _record_digest(data), len(data)))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    return output.getvalue().encode("utf-8")


def build_release_wheel() -> tuple[bytes, dict[str, object]]:
    """Return one byte-reproducible product wheel and its source binding."""

    runtime_archive, runtime_manifest = build_runtime_archive()
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(runtime_archive)) as archive:
        for name in sorted(archive.namelist()):
            data = archive.read(name)
            if name == "ARC3_KAGGLE_RUNTIME_MANIFEST.json":
                members[
                    "arc3_agi_agent/ARC3_PRODUCT_RUNTIME_MANIFEST.json"
                ] = data
            elif name.startswith("arc3_agi_agent/"):
                members[name] = data

    members.update(
        {
            "agents/__init__.py": _agents_init(),
            "agents/agent.py": (AGENTS_ROOT / "agents" / "agent.py").read_bytes(),
            "agents/recorder.py": (
                AGENTS_ROOT / "agents" / "recorder.py"
            ).read_bytes(),
            "agents/tracing.py": (
                AGENTS_ROOT / "agents" / "tracing.py"
            ).read_bytes(),
            "agents/templates/__init__.py": b"",
            **{
                f"agents/templates/{name}": path.read_bytes()
                for name, path in AGENT_SOURCES.items()
            },
            f"{DIST_INFO}/METADATA": _metadata(),
            f"{DIST_INFO}/WHEEL": _wheel_metadata(),
            f"{DIST_INFO}/entry_points.txt": (
                "[console_scripts]\n"
                "arc3-completion-product = "
                "arc3_agi_agent.product_runner:main\n"
            ).encode("utf-8"),
            f"{DIST_INFO}/top_level.txt": b"agents\narc3_agi_agent\n",
        }
    )
    members[f"{DIST_INFO}/RECORD"] = _record(members)

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(_zip_info(name), data)
    wheel = buffer.getvalue()
    names = tuple(sorted(members))
    report: dict[str, object] = {
        "schema_version": "arc3-product-release-build-v1",
        "product_id": PRODUCT_ID,
        "product_version": PRODUCT_VERSION,
        "wheel_filename": WHEEL_FILENAME,
        "wheel_sha256": _sha256(wheel),
        "wheel_size_bytes": len(wheel),
        "wheel_member_count": len(names),
        "wheel_member_inventory_sha256": _sha256(
            ("\n".join(names) + "\n").encode("utf-8")
        ),
        "runtime_archive_sha256": runtime_manifest["archive_sha256"],
        "runtime_asset_sha256": runtime_manifest["asset_sha256"],
        "agent_sha256": {
            name: _sha256(path.read_bytes())
            for name, path in AGENT_SOURCES.items()
        },
        "entrypoint": "arc3_agi_agent.product_runner:main",
        "python_requires": ">=3.12",
        "arc_agi_version": "0.9.8",
        "numpy_version": "2.3.2",
        "teacher_included": False,
        "fixed_action_trajectory_included": False,
        "runtime_identity_routing_included": False,
        "literal_coordinate_table_included": False,
        "compiled_identity_free_product_policy_included": True,
        "byte_reproducible": True,
    }
    return wheel, report


def write_release(output_dir: Path) -> dict[str, object]:
    wheel, report = build_release_wheel()
    reproduction, reproduction_report = build_release_wheel()
    if wheel != reproduction or report != reproduction_report:
        raise RuntimeError("ARC3_PRODUCT_RELEASE_NOT_REPRODUCIBLE")
    output_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = output_dir / WHEEL_FILENAME
    wheel_path.write_bytes(wheel)
    manifest_path = output_dir / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "SHA256SUMS").write_text(
        f"{report['wheel_sha256']}  {WHEEL_FILENAME}\n"
        f"{_sha256(manifest_path.read_bytes())}  MANIFEST.json\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    report = write_release(arguments.output_dir.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
