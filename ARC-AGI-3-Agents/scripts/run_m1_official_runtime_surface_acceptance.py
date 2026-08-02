from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from arc3_agi_agent.product_runtime_surface import (
    M1_RUNTIME_SURFACE_EXIT,
    inspect_official_runtime_surface,
)


def _default_environments_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "environment_files"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect the official ARC3 M1 runtime surface."
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="arc3-m1-surface-") as temporary:
        report = inspect_official_runtime_surface(
            environments_dir=arguments.environments_dir,
            recordings_dir=(arguments.recordings_dir or Path(temporary) / "recordings"),
        )
    encoded = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return int(report["exit_status"] != M1_RUNTIME_SURFACE_EXIT)


if __name__ == "__main__":
    raise SystemExit(main())
