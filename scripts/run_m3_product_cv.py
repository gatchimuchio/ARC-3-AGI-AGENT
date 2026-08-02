#!/usr/bin/env python3
"""Compile and execute product-equivalent ARC3 cross-game CV folds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.product_cross_validation import (  # noqa: E402
    PRODUCT_CV_FOLD_COUNT,
    assemble_product_cv_manifest,
    compile_product_cv_fold,
    run_product_cv_fold,
)

DEFAULT_CORPUS = Path("analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.npz")
DEFAULT_CORPUS_MANIFEST = Path(
    "analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json"
)
DEFAULT_ENVIRONMENTS = Path("environment_files")
DEFAULT_OUTPUT = Path("analysis/product/rev4/cv_v2")


def _rooted(root: Path, value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def _folds(raw_fold: int | None) -> tuple[int, ...]:
    if raw_fold is None:
        return tuple(range(PRODUCT_CV_FOLD_COUNT))
    if not 0 <= raw_fold < PRODUCT_CV_FOLD_COUNT:
        raise ValueError("PRODUCT_CV_FOLD_INDEX_INVALID")
    return (raw_fold,)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("compile", "run", "assemble", "all"),
    )
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--corpus-manifest",
        type=Path,
        default=DEFAULT_CORPUS_MANIFEST,
    )
    parser.add_argument(
        "--environments",
        type=Path,
        default=DEFAULT_ENVIRONMENTS,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fold", type=int)
    parser.add_argument("--no-cache", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output = _rooted(root, arguments.output)
    selected_folds = _folds(arguments.fold)
    summaries: list[dict[str, object]] = []
    if arguments.command in {"compile", "all"}:
        for fold_index in selected_folds:
            report = compile_product_cv_fold(
                repository_root=root,
                corpus_path=_rooted(root, arguments.corpus),
                corpus_manifest_path=_rooted(
                    root,
                    arguments.corpus_manifest,
                ),
                output_dir=output,
                fold_index=fold_index,
                use_cache=not arguments.no_cache,
            )
            summaries.append(
                {
                    "event": "PRODUCT_CV_FOLD_COMPILED",
                    "fold_id": report["fold_id"],
                    "p_logical_digest": report["p_logical_digest"],
                    "elapsed_seconds": report["elapsed_seconds"],
                    "status": report["status"],
                }
            )
    if arguments.command in {"run", "all"}:
        for fold_index in selected_folds:
            report = run_product_cv_fold(
                repository_root=root,
                environments_dir=_rooted(root, arguments.environments),
                output_dir=output,
                fold_index=fold_index,
            )
            summaries.append(
                {
                    "event": "PRODUCT_CV_FOLD_EXECUTED",
                    "fold_id": report["fold_id"],
                    "completed_environment_count": report[
                        "completed_environment_count"
                    ],
                    "completed_level_count": report["completed_level_count"],
                    "elapsed_seconds": report["elapsed_seconds"],
                    "status": report["status"],
                }
            )
    if arguments.command == "assemble" or (
        arguments.command == "all" and arguments.fold is None
    ):
        report = assemble_product_cv_manifest(output_dir=output)
        summaries.append(
            {
                "event": "PRODUCT_CV_MANIFEST_ASSEMBLED",
                "holdout_completed_environment_count": report[
                    "holdout_completed_environment_count"
                ],
                "holdout_completed_level_count": report[
                    "holdout_completed_level_count"
                ],
                "capability_status": report["capability_status"],
                "status": report["status"],
            }
        )
    print(json.dumps(summaries, sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
