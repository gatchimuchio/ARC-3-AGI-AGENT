"""Run P22-A local autonomous-completion evidence stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arc3_agi_agent.p22_evaluator import (
    assemble_cv_manifest,
    build_active_compiled_p_bundle,
    run_cv_holdout_fold,
    run_known_public_regression,
    run_memory_ablation,
    run_transformation_stress,
)
from arc3_agi_agent.teacher.p22_cross_validation import (
    compile_cv_fold_artifacts,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parser() -> argparse.ArgumentParser:
    root = _repository_root()
    parser = argparse.ArgumentParser(
        description="Run P22-A strictly in the retained local OFFLINE scope."
    )
    parser.add_argument(
        "stage",
        choices=(
            "memory",
            "public",
            "transformation",
            "cv-compile",
            "cv-fold",
            "cv-assemble",
            "all",
        ),
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=root / "environment_files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "analysis" / "autonomous_completion",
    )
    parser.add_argument("--fold-index", type=int)
    parser.add_argument(
        "--training-corpus",
        type=Path,
        default=(
            root
            / "analysis"
            / "teacher"
            / "S5_RENDERED_POLICY_TRAINING_CORPUS.npz"
        ),
    )
    parser.add_argument(
        "--training-corpus-manifest",
        type=Path,
        default=(
            root
            / "analysis"
            / "teacher"
            / "S5_RENDERED_POLICY_TRAINING_CORPUS.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    root = _repository_root()
    output_dir = arguments.output_dir.resolve()
    results: dict[str, object] = {}
    if arguments.stage == "cv-compile":
        results["cv_compile"] = compile_cv_fold_artifacts(
            corpus_path=arguments.training_corpus.resolve(),
            corpus_manifest_path=(
                arguments.training_corpus_manifest.resolve()
            ),
            output_dir=output_dir,
        )
    elif arguments.stage == "cv-fold":
        if arguments.fold_index is None:
            raise ValueError("--fold-index is required for cv-fold")
        results["cv_fold"] = run_cv_holdout_fold(
            repository_root=root,
            environments_dir=arguments.environments_dir,
            output_dir=output_dir,
            compile_manifest_path=(
                output_dir / "cv_compile_manifest.json"
            ),
            fold_index=arguments.fold_index,
        )
    elif arguments.stage == "cv-assemble":
        results["cv"] = assemble_cv_manifest(output_dir=output_dir)
    bundle = (
        build_active_compiled_p_bundle()
        if arguments.stage
        in {"transformation", "memory", "public", "all"}
        else None
    )
    if arguments.stage in {"transformation", "all"}:
        if bundle is None:
            raise RuntimeError("P22_ACTIVE_BUNDLE_REQUIRED")
        results["transformation"] = run_transformation_stress(
            output_path=output_dir / "transformation_completion.json",
            bundle=bundle,
        )
    if arguments.stage in {"memory", "all"}:
        if bundle is None:
            raise RuntimeError("P22_ACTIVE_BUNDLE_REQUIRED")
        results["memory"] = run_memory_ablation(
            output_path=output_dir / "memory_ablation.json",
            bundle=bundle,
        )
    if arguments.stage in {"public", "all"}:
        if bundle is None:
            raise RuntimeError("P22_ACTIVE_BUNDLE_REQUIRED")
        results["public"] = run_known_public_regression(
            repository_root=root,
            environments_dir=arguments.environments_dir,
            output_dir=output_dir,
            bundle=bundle,
            command=(
                "python p22_main.py "
                + arguments.stage
                + " --environments-dir "
                + str(arguments.environments_dir.resolve())
                + " --output-dir "
                + str(output_dir)
            ),
        )
    summary = {
        key: {
            "status": value["status"],
            "failed_requirement_ids": value["failed_requirement_ids"],
            "content_digest": value["content_digest"],
        }
        for key, value in results.items()
        if isinstance(value, dict)
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return int(
        any(
            value.get("status") != "PASS"
            for value in results.values()
            if isinstance(value, dict)
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
