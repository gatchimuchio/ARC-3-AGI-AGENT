"""C2-087 r3 LOCAL drafts: a common three-sentence optional reconsultation note only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "検証/ARC3native学習差分再現候補構築.py"
FROZEN_SHA = "8632af8c96af77bdb4836cc191a6ea9c18997b8985d72cd143510d0ba7e30ead"
SNAPSHOT = ROOT / "出力/ARC3-RUN-003-local/C2-087/source-snapshots-r3/manifest.json"
R2_MANIFEST = ROOT / "出力/ARC3-RUN-003-local/C2-087/prior-only-r2/build-manifest.json"
ADDITION = (
    " After new observed responses alter your visual hypothesis, consider a fresh optional "
    "hds_query for one legal candidate rather than treating an early HOLD or empty packet as conclusive. "
    "Print the bounded returned packet without manual slicing. "
    "At most two distinct candidates are supported for one current state."
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_frozen():
    if sha(FROZEN.read_bytes()) != FROZEN_SHA:
        raise ValueError("Frozen C2-087 r2 builder drift")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for row in snapshot["sources"]:
        if any(
            sha((ROOT / row[key]).read_bytes()) != row["sha256"] for key in ("source", "snapshot")
        ):
            raise ValueError("Frozen C2-087 r2 source/proof drift")
    for arm, files in snapshot["original_arm_file_hashes"].items():
        folder = ROOT / "出力/ARC3-RUN-003-local/C2-087" / arm
        actual = {
            p.relative_to(folder).as_posix(): sha(p.read_bytes())
            for p in folder.rglob("*")
            if p.is_file()
        }
        if actual != files:
            raise ValueError("Frozen C2-087 r2 artifact drift")


def load_builder():
    validate_frozen()
    expected_note = json.loads(R2_MANIFEST.read_text(encoding="utf-8"))["shared_prompt_note"]
    spec = importlib.util.spec_from_file_location("c2087_r3_frozen_r2_builder", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != ROOT:
        raise ValueError("Frozen C2-087 r2 ROOT mismatch")
    original_load = module.load_builder

    def load():
        r1 = original_load()
        original_r1_load = r1.load_builder

        def load_r1(mode):
            observer_builder = original_r1_load(mode)
            original_observer_load = observer_builder.load_builder

            def load_observer():
                previous, observer = original_observer_load()
                if previous.NOTE != expected_note:
                    raise ValueError("Frozen C2-087 r2 common prompt note drift")
                previous.NOTE += ADDITION
                return previous, observer

            observer_builder.load_builder = load_observer
            return observer_builder

        r1.load_builder = load_r1
        return r1

    module.load_builder = load
    return module


def build(output, *, game_updates, kernel_id):
    previous = load_builder()
    result = previous.build(output, game_updates=game_updates, kernel_id=kernel_id)
    expected_note = (
        json.loads(R2_MANIFEST.read_text(encoding="utf-8"))["shared_prompt_note"] + ADDITION
    )
    if result["shared_prompt_note"] != expected_note:
        raise ValueError("Generated r3 common prompt differs")
    result.update(
        {
            "schema": "arc3-native-game-learning-ablation-reconsult-build.v1",
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "frozen_C2_087_r2_builder_sha256": FROZEN_SHA,
            "C2_087_revision": "r3",
            "r3_shared_change_only": "three-sentence optional reconsultation and packet-display prompt note",
            "shared_optional_reconsultation_note": ADDITION.strip(),
            "shared_optional_reconsultation_note_sha256": sha(ADDITION.encode("utf-8")),
            "r1_learning_runtime_native_observer_prompt_model_and_budgets_unchanged": False,
            "r2_runtime_native_observer_render_algorithm_budgets_model_seed_stamp_unchanged": True,
            "r3_prompt_identical_in_both_arms": True,
            "mandatory_all_game_all_step_or_action_gate_added": False,
            "native_judgment_modified": False,
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
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
