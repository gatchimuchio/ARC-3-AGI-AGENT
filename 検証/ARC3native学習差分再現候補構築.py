"""C2-087 r2 LOCAL drafts: explicit OFFLINE seed and observed runtime software stamp."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "検証/ARC3native学習差分候補構築.py"
FROZEN_SHA = "eed35c7bf2ac128ac946508ba170c4cf17125a80fba272f4ba8ec600f87030f6"
SNAPSHOT = ROOT / "出力/ARC3-RUN-003-local/C2-087/source-snapshots-r2/manifest.json"
GAME_API = "src/tufa-arc-agi-framework/src/taaf/game_api.py"
GAME_API_SHA = "51639e22cc0d35db49137f0168b2de557b1848482a4c2cf65ade2a1202511221"
SOURCE_ROOT = ROOT / "入力/モデル実行基底/v5/taaf-source-v1/patched"
WHEEL_CELL_SHA = "0acc65bba3dd5435f5e25a73cb378b3ff269364f0f7a5a99226fc4a41060ae44"
OLD = "            env = arcade.make(self.env_name, scorecard_id=self._scorecard_id)\n"
NEW = (
    "            # C2-087 r2: explicit seed only for the public OFFLINE pilot.\n"
    "            env = arcade.make(\n"
    "                self.env_name, scorecard_id=self._scorecard_id,\n"
    '                **({"seed": 0} if spec.operation_mode == arc_agi.OperationMode.OFFLINE else {}),\n'
    "            )\n"
)
STAMP_FILENAME = "arc3-runtime-software.json"
STAMP_SCHEMA = "arc3-runtime-software.v1"
STAMP_SOURCE = """
# C2-087 r2: observe software actually installed by the competition wheelhouse.
# No version-value gate or client/game construction occurs here.
import importlib.metadata as _stamp_metadata
import inspect as _stamp_inspect
import platform as _stamp_platform

_stamp_errors = {}
_stamp_packages = {}
for _stamp_name in ("arc-agi", "arcengine"):
    try:
        _stamp_packages[_stamp_name] = _stamp_metadata.version(_stamp_name)
    except Exception as _stamp_exc:
        _stamp_packages[_stamp_name] = None
        _stamp_errors["package:" + _stamp_name] = type(_stamp_exc).__name__
try:
    import arc_agi as _stamp_arc_agi
    _stamp_signature = str(_stamp_inspect.signature(_stamp_arc_agi.Arcade.make))
except Exception as _stamp_exc:
    _stamp_signature = None
    _stamp_errors["public_Arcade_make_signature"] = type(_stamp_exc).__name__
_stamp_payload = {
    "schema": "arc3-runtime-software.v1",
    "python": {
        "version": _stamp_platform.python_version(),
        "implementation": _stamp_platform.python_implementation(),
    },
    "packages": _stamp_packages,
    "public_Arcade_make_signature": _stamp_signature,
    "environment_seed": {
        "declared_offline_seed": 0,
        "explicit_keyword_scope": "OFFLINE private pilot only",
        "competition_rerun_allowed": False,
    },
    "observation_errors": _stamp_errors,
}
(WORKING_DIR / "arc3-runtime-software.json").write_text(
    json.dumps(_stamp_payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
)
print("C2-087 runtime software stamp:", json.dumps(_stamp_payload, ensure_ascii=False))
"""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def seed_patch(raw):
    if sha(raw) != GAME_API_SHA or raw.decode("utf-8").count(OLD) != 1:
        raise ValueError("Frozen public GameAPI preimage/anchor drift")
    patched = raw.decode("utf-8").replace(OLD, NEW, 1).encode("utf-8")
    compile(patched, GAME_API, "exec")
    return patched


def validate_frozen():
    if sha(FROZEN.read_bytes()) != FROZEN_SHA:
        raise ValueError("Frozen C2-087 r1 builder drift")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for row in snapshot["sources"]:
        if any(
            sha((ROOT / row[key]).read_bytes()) != row["sha256"] for key in ("source", "snapshot")
        ):
            raise ValueError("Frozen C2-087 r1 source/proof drift")
    for arm, files in snapshot["original_arm_file_hashes"].items():
        folder = ROOT / "出力/ARC3-RUN-003-local/C2-087" / arm
        actual = {
            p.relative_to(folder).as_posix(): sha(p.read_bytes())
            for p in folder.rglob("*")
            if p.is_file()
        }
        if actual != files:
            raise ValueError("Frozen C2-087 r1 artifact drift")


def load_builder():
    validate_frozen()
    spec = importlib.util.spec_from_file_location("c2087_r2_frozen_r1_builder", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != ROOT:
        raise ValueError("Frozen C2-087 builder ROOT mismatch")
    original_load = module.load_builder
    patched_api = seed_patch((SOURCE_ROOT / GAME_API).read_bytes())

    def load(mode):
        observer_builder = original_load(mode)
        previous_load = observer_builder.load_builder

        def layered_load():
            previous, observer = previous_load()
            original_configure = previous.configure

            def configure(base, visibility):
                extras = original_configure(base, visibility)
                old_cell, old_cpu = base._patch_cell, base._cpu_patch_cell

                def cell(payload, records, selected_mode, budgets):
                    source = old_cell(payload, records, selected_mode, budgets)
                    source += f"""
# C2-087 r2: no change to COMPETITION calls; existing rerun refusal remains above.
_seed_path = BUNDLE_DIR / PurePosixPath({GAME_API!r})
_seed_raw = _seed_path.read_bytes()
if hashlib.sha256(_seed_raw).hexdigest() != {GAME_API_SHA!r}:
    raise RuntimeError("C2-087 public GameAPI seed preimage drift")
_seed_text = _seed_raw.decode("utf-8")
if _seed_text.count({OLD!r}) != 1:
    raise RuntimeError("C2-087 public GameAPI seed anchor drift")
_seed_text = _seed_text.replace({OLD!r}, {NEW!r}, 1)
compile(_seed_text, str(_seed_path), "exec")
_seed_path.write_bytes(_seed_text.encode("utf-8"))
if hashlib.sha256(_seed_path.read_bytes()).hexdigest() != {sha(patched_api)!r}:
    raise RuntimeError("C2-087 public GameAPI seed postimage drift")
"""
                    return source

                def cpu(source, sources, solver):
                    check = f"\nassert hashlib.sha256((BUNDLE_DIR / PurePosixPath({GAME_API!r})).read_bytes()).hexdigest() == {sha(patched_api)!r}\n"
                    return {
                        **old_cpu(source + check, sources, solver),
                        "OFFLINE_explicit_seed_postimage_verified": True,
                        "OFFLINE_declared_seed": 0,
                    }

                base._patch_cell, base._cpu_patch_cell = cell, cpu
                return {**extras, GAME_API: patched_api}

            previous.configure = configure
            return previous, observer

        observer_builder.load_builder = layered_load
        return observer_builder

    module.load_builder = load
    return module


def build(output, *, game_updates, kernel_id):
    previous = load_builder()
    result = previous.build(output, game_updates=game_updates, kernel_id=kernel_id)
    path = output / "submission.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    wheel_source = "".join(notebook["cells"][10]["source"])
    if sha(wheel_source.encode("utf-8")) != WHEEL_CELL_SHA:
        raise ValueError("Frozen after-wheel-install cell drift")
    notebook["cells"][10]["source"] = (wheel_source + STAMP_SOURCE).splitlines(keepends=True)
    path.write_bytes((json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    result.update(
        {
            "schema": "arc3-native-game-learning-ablation-repro-build.v1",
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "frozen_C2_087_r1_builder_sha256": FROZEN_SHA,
            "C2_087_revision": "r2",
            "output_notebook_sha256": sha(path.read_bytes()),
            "r2_shared_changes_only": [
                "explicit OFFLINE make seed0",
                "after-wheel-install observed runtime software stamp",
            ],
            "r1_learning_runtime_native_observer_prompt_model_and_budgets_unchanged": True,
            "public_GameAPI_seed_preimage_sha256": GAME_API_SHA,
            "public_GameAPI_seed_postimage_sha256": sha(
                seed_patch((SOURCE_ROOT / GAME_API).read_bytes())
            ),
            "software_stamp_filename": STAMP_FILENAME,
            "software_stamp_schema": STAMP_SCHEMA,
            "software_stamp_source_sha256": sha(STAMP_SOURCE.encode("utf-8")),
            "software_stamp_cell_after_install": 10,
            "software_stamp_runtime_GPU_observed": False,
            "GPU_SDK_version_pinned_or_guessed": False,
            "package_version_value_gate_added": False,
            "future_pair_requires_observed_software_comparison": True,
            "environment_seed": {
                "explicitly_requested_by_notebook": True,
                "value": 0,
                "scope": "OFFLINE private pilot only",
                "GPU_SDK_actual_version": "not yet observed; record runtime stamp",
                "local_pinned_SDK_default_separate": {"arc-agi": "0.9.8", "default_seed": 0},
                "runtime_initial_state_equivalence": "pending public-frame comparison",
            },
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
