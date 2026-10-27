"""C2-088 scorecard adapter that preserves the new boundary-only outcome class.

This is an explicit, scorecard-only schema extension. It does not change the
Notebook, HDS runtime, game actions, or the frozen legacy scorer file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from 検証 import ARC3視覚HDS学習比較採点 as core


BOUNDARY_ONLY = "境界領域変化のみ"
BASE_ORDER = ("可視変化なし", "盤面変化", "レベル進行", "GAME_OVER", "勝利")
EXTENDED_ORDER = BASE_ORDER + (BOUNDARY_ONLY,)


def enable_boundary_only_schema() -> dict:
    legacy = core.legacy
    globals_ = legacy._record_response.__globals__
    if legacy._majority.__globals__ is not globals_:
        raise ValueError("legacy majority and response functions do not share globals")
    if set(legacy.OUTCOMES) != set(BASE_ORDER):
        raise ValueError("frozen legacy outcome set drift")
    if tuple(globals_.get("MAJORITY_ORDER", ())) != BASE_ORDER:
        raise ValueError("frozen legacy tie-break order drift")
    legacy.OUTCOMES = set(BASE_ORDER) | {BOUNDARY_ONLY}
    globals_["MAJORITY_ORDER"] = EXTENDED_ORDER
    return {
        "added_label": BOUNDARY_ONLY,
        "base_outcome_order": list(BASE_ORDER),
        "extended_majority_tie_break_order": list(EXTENDED_ORDER),
        "class_aliasing": False,
        "scope": "scorecard-only; runtime game/HDS behavior unchanged",
        "tie_policy": "append the new class after all five frozen labels, preserving their prior precedence",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("", "other-"):
        for name in ("retrieval", "build", "output-root", "version"):
            parser.add_argument("--" + prefix + name, type=int if name == "version" else Path,
                                required=not prefix)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"refusing scorecard overwrite: {args.output}")

    schema = enable_boundary_only_schema()
    result = core.evaluate(
        args.retrieval, args.build, args.output_root, args.version,
        other_retrieval=args.other_retrieval, other_build=args.other_build,
        other_output_root=args.other_output_root, other_version=args.other_version,
    )
    schema["adapter_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["public_outcome_schema_extension"] = schema
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "output": str(args.output),
        "scorecard_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "inspection": result["inspection"],
        "extended_outcome": BOUNDARY_ONLY,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
