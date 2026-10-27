"""C2-087 LOCAL shown/shown drafts: native game-response updates are the only treatment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_BUILDER = ROOT / "検証/ARC3局所応答observer候補構築.py"
FROZEN_SHA = "1d10bbce0082c79a802b9425b243fdd91e194402c24802ec3854c2d6391a47df"
FROZEN_RUNTIME = ROOT / "検証/候補/ARC3PythonHDS局所応答runtime.py"
FROZEN_RUNTIME_SHA = "6ddb8b29fe4f52576fea8cadbb0c8450c470fb730640df527ebb5d6cc1db48b8"
RUNTIME = ROOT / "検証/候補/ARC3PythonHDS学習有効無効runtime.py"
FLAG = "ARC3_HDS_GAME_RESPONSE_UPDATES"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_builder(mode):
    if mode not in {"disabled", "enabled"}:
        raise ValueError("native game-response updates must be disabled or enabled")
    if (
        sha(FROZEN_BUILDER.read_bytes()) != FROZEN_SHA
        or sha(FROZEN_RUNTIME.read_bytes()) != FROZEN_RUNTIME_SHA
    ):
        raise ValueError("Frozen C2-085 sources drifted")
    if not RUNTIME.read_bytes().startswith(FROZEN_RUNTIME.read_bytes()):
        raise ValueError("C2-087 must retain the exact frozen C2-085 runtime prefix")
    snapshot = json.loads(
        (ROOT / "出力/ARC3-RUN-003-local/C2-087/source-snapshots/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for row in snapshot["sources"]:
        if (
            sha((ROOT / row["source"]).read_bytes()) != row["sha256"]
            or sha((ROOT / row["snapshot"]).read_bytes()) != row["sha256"]
        ):
            raise ValueError("Frozen C2-085 snapshot drift")
    spec = importlib.util.spec_from_file_location("c2087_frozen_observer_builder", FROZEN_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != ROOT:
        raise ValueError("Frozen builder ROOT must resolve explicitly to this repository")
    module.RUNTIME = RUNTIME
    original_load = module.load_builder

    def load():
        previous, observer = original_load()
        original_configure = previous.configure

        def configure(base, visibility):
            if visibility != "shown":
                raise ValueError("Both learning arms must use SHOWN evidence")
            extras = original_configure(base, visibility)
            original_cell, original_cpu = base._patch_cell, base._cpu_patch_cell

            def cell(payload, records, selected_mode, budgets):
                source = original_cell(payload, records, selected_mode, budgets)
                source += (
                    f"\nos.environ[{FLAG!r}] = {mode!r}\n"
                    f'assert os.environ[{FLAG!r}] in {{"disabled", "enabled"}}\n'
                    f'print("C2-087 native game-response updates:", os.environ[{FLAG!r}])\n'
                )
                return source

            def cpu(source, source_files, solver):
                result = original_cpu(source, source_files, solver)
                return {
                    **result,
                    "game_response_learning_mode": mode,
                    "prior_initialization_separate_from_game_update_gate": True,
                }

            base._patch_cell, base._cpu_patch_cell = cell, cpu
            return extras

        previous.configure = configure
        return previous, observer

    module.load_builder = load
    return module


def build(output, *, game_updates, kernel_id):
    previous = load_builder(game_updates)
    result = previous.build(output, visibility="shown", kernel_id=kernel_id)
    result.update(
        {
            "schema": "arc3-native-game-learning-ablation-build.v1",
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "frozen_C2_085_builder_sha256": FROZEN_SHA,
            "frozen_C2_085_runtime_prefix_sha256": FROZEN_RUNTIME_SHA,
            "learning_runtime_source_sha256": sha(RUNTIME.read_bytes()),
            "learning_treatment_flag": FLAG,
            "native_game_response_updates_enabled": game_updates == "enabled",
            "native_game_response_learning_mode": game_updates,
            "initial_prior_records_both_arms": 5,
            "evidence_visibility_both_arms": "shown",
            "only_treatment": "native game-response update ingestion enabled versus disabled",
            "actual_public_observer_teachers_computed_and_logged_in_both": True,
            "disabled_update_status": "game_response_update_disabled",
            "disabled_update_is_expected_not_native_rejection_or_budget_exhaustion": True,
            "query_renderer_uses_actual_native_return_not_new_teacher_history": True,
            "prior_native_updates_separate_from_game_update_counts": True,
            "learning_configuration_frozen_in_manifest_and_telemetry": True,
            "observer_helper_action_policy_prompt_and_model_same_in_both": True,
            "offline_majority_fallback_used_as_action_policy": False,
            "C2_085_visibility_study_completed": False,
            "actual_learning_effect_score_gain_proven": False,
            "Kaggle_operation_performed": False,
        }
    )
    (output / "build-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game-updates", choices=("disabled", "enabled"), required=True)
    parser.add_argument("--kernel-id", required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build(output, game_updates=args.game_updates, kernel_id=args.kernel_id)
    print(
        json.dumps(
            {"output": str(output), "notebook_sha256": result["output_notebook_sha256"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
