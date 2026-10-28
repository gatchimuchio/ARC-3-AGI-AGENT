"""固定した旧版と現行の公開盤面成分抽出を合成盤面で比較する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from 接続.図式観測 import 成分群  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="比較元のGit commit")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--concurrent-workload", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"出力を上書きしません: {args.output}")

    revision = subprocess.run(
        ["git", "rev-parse", "--verify", f"{args.base}^{{commit}}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    old_bytes = subprocess.run(
        ["git", "show", f"{revision}:接続/図式観測.py"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    old_module: dict = {}
    exec(compile(old_bytes, "previous_図式観測.py", "exec"), old_module)
    previous = old_module["成分群"]

    rng = random.Random(20261029)
    boards = [[], [[], []], [[1]], [[1, 2, 1], [1], [2, 2]]]
    boards.extend(
        [[rng.randrange(4) for _ in range(rng.randrange(9))] for _ in range(rng.randrange(9))]
        for _ in range(100)
    )
    boards.extend([
        [[0] * 64 for _ in range(64)],
        [[x % 2 for x in range(64)] for _ in range(64)],
        [[(x + y) % 2 for x in range(64)] for y in range(64)],
    ])
    for index, board in enumerate(boards):
        if previous(board) != 成分群(board):
            raise AssertionError(f"成分・順序が一致しません: synthetic case {index}")

    checkerboard = boards[-1]
    previous_seconds = []
    current_seconds = []
    for _ in range(3):
        start = time.perf_counter()
        previous(checkerboard)
        previous_seconds.append(time.perf_counter() - start)
        start = time.perf_counter()
        成分群(checkerboard)
        current_seconds.append(time.perf_counter() - start)

    old_median = statistics.median(previous_seconds)
    new_median = statistics.median(current_seconds)
    result = {
        "base_commit": revision,
        "previous_source_sha256": hashlib.sha256(old_bytes).hexdigest(),
        "current_source_sha256": hashlib.sha256((ROOT / "接続/図式観測.py").read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "synthetic_cases_equal": len(boards),
        "checkerboard_shape": [64, 64],
        "checkerboard_components": len(成分群(checkerboard)),
        "previous_seconds": previous_seconds,
        "current_seconds": current_seconds,
        "previous_median_seconds": old_median,
        "current_median_seconds": new_median,
        "median_ratio_current_to_previous": new_median / old_median,
        "concurrent_workload": args.concurrent_workload,
        "scope": "synthetic CPU timing; not an ARC3 game score or learning result",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
