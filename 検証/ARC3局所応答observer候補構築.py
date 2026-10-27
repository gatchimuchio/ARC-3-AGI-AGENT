"""C2-085 LOCAL drafts: one PRE4CC area and actual Action6 local/remote teacher."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FROZEN_BUILDER = ROOT / "検証/ARC3視覚HDS照会候補構築.py"
FROZEN_SHA = "0a69f1bd43aabbba0746c8269228399dae0f0a87ed71b3cc2d13f164c881098e"
FROZEN_RUNTIME = ROOT / "検証/候補/ARC3PythonHDS照会runtime.py"
FROZEN_RUNTIME_SHA = "34a5c02fddc7caf7648c1b15d9369d2bdb2535b652b3868faa55fdce24853a8b"
OBSERVER = ROOT / "検証/候補/ARC3Action6局所応答observer.py"
RUNTIME = ROOT / "検証/候補/ARC3PythonHDS局所応答runtime.py"
EXTRA_NOTE = (
    " For MOUSE only, native context additionally observes the PRE-target same-color "
    "4-connected component pixel area. The separate actual-effect target distinguishes "
    "changes within the fixed7x7 PRE-target square and outside it. These are observed "
    "geometry, not established mechanisms or progress. Remote-only is not a no-op, "
    "failure or HUD classification. Missing/shape-incomparable effect stays unknown."
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def observer_module():
    spec = importlib.util.spec_from_file_location("c2085_pure_observer", OBSERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_builder():
    if (
        sha(FROZEN_BUILDER.read_bytes()) != FROZEN_SHA
        or sha(FROZEN_RUNTIME.read_bytes()) != FROZEN_RUNTIME_SHA
    ):
        raise ValueError("Frozen C2-081r2 source drift")
    snapshot = json.loads(
        (ROOT / "出力/ARC3-RUN-003-local/C2-085/source-snapshots/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for row in snapshot["sources"]:
        if (
            sha((ROOT / row["source"]).read_bytes()) != row["sha256"]
            or sha((ROOT / row["snapshot"]).read_bytes()) != row["sha256"]
        ):
            raise ValueError("Frozen C2-081r2 snapshot drift")
    observer = observer_module()
    for prefix in ("area", "components", "effect"):
        path = ROOT / observer.PROVENANCE[prefix + "_source"]
        if sha(path.read_bytes()) != observer.PROVENANCE[prefix + "_source_sha256"]:
            raise ValueError("Reviewed pure helper provenance drift: " + prefix)
    proof = ROOT / "運用/証拠/ARC26-UNIFIED/C2-084_PRE-component-area-native-paired.json"
    if sha(proof.read_bytes()) != observer.PROVENANCE["positive_offline_proof_sha256"]:
        raise ValueError("Offline evidence provenance drift")
    spec = importlib.util.spec_from_file_location("c2085_frozen_081_builder", FROZEN_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != ROOT:
        raise ValueError("Frozen builder ROOT must resolve explicitly to this repository")
    module.RUNTIME_SOURCE = RUNTIME
    module.NOTE += EXTRA_NOTE
    original_configure = module.configure

    def configure(base, visibility):
        extras = original_configure(base, visibility)
        original_bundle, original_cell = base._bundle, base._patch_cell

        def bundle():
            payload, manifest = original_bundle()
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                files = {
                    name: archive.read(name)
                    for name in archive.namelist()
                    if name != "ARC3-VISUAL-HDS-MANIFEST.json"
                }
            files["arc3_python_hds_query_base.py"] = FROZEN_RUNTIME.read_bytes()
            files["arc3_action6_locality_observer.py"] = OBSERVER.read_bytes()
            for name, raw in files.items():
                if name.endswith(".py"):
                    compile(raw, name, "exec")
            manifest["files"] = [
                {"path": name, "bytes": len(raw), "sha256": sha(raw)}
                for name, raw in sorted(files.items())
            ]
            manifest["frozen_C2_081_r2_runtime_sha256"] = FROZEN_RUNTIME_SHA
            manifest["observer_projection_revision"] = observer.REVISION
            files["ARC3-VISUAL-HDS-MANIFEST.json"] = (
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
            output = BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, raw in sorted(files.items()):
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
                    archive.writestr(info, raw)
            return output.getvalue(), manifest

        def cell(payload, records, mode, budgets):
            source = original_cell(payload, records, mode, budgets)
            source = base._replace_once(
                source,
                '"arc3_visual_hds_base.py", "ARC3-VISUAL-HDS-MANIFEST.json"',
                '"arc3_visual_hds_base.py", "arc3_python_hds_query_base.py", "arc3_action6_locality_observer.py", "ARC3-VISUAL-HDS-MANIFEST.json"',
            )
            return source.replace(
                "C2-081 Python-HDS query mode", "C2-085 PRE4CC-locality observer mode"
            )

        base._bundle, base._patch_cell = bundle, cell
        return extras

    module.configure = configure
    return module, observer


def build(output, *, visibility, kernel_id):
    previous, observer = load_builder()
    result = previous.build(output, visibility=visibility, kernel_id=kernel_id)
    result.update(
        {
            "schema": "arc3-pre4cc-locality-observer-pilot-build.v1",
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "frozen_C2_081_r2_builder_sha256": FROZEN_SHA,
            "frozen_C2_081_r2_runtime_sha256": FROZEN_RUNTIME_SHA,
            "observer_source_sha256": sha(OBSERVER.read_bytes()),
            "observer_runtime_source_sha256": sha(RUNTIME.read_bytes()),
            "observer_projection_revision": observer.REVISION,
            "observer_provenance": observer.PROVENANCE,
            "additional_PRE_features": [["作用前公開状態", observer.AREA]],
            "PRE_area_used_for_both_query_and_update": True,
            "new_actual_teacher_target": observer.TARGET,
            "new_teacher_classes": list(observer.EFFECT_VALUES),
            "teacher_fields_absent_from_query": ["公開応答区分", observer.TARGET],
            "nonAction6_new_fields": "omitted",
            "shape_mismatch_or_empty_effect": "UNKNOWN; omit new target, retain original public outcome",
            "component_shape_identity_or_color_ids_added_as_features": False,
            "native_HDS_or_helper_action_policy_changed": False,
            "offline_positive_evidence_is_runtime_improvement_proof": False,
            "runtime_context_is_full_not_the_positive_reduced_schema": True,
            "locality_forecast_values_are_descriptive_active_ref_links_not_guarded_qualification": True,
            "shared_user_prompt_note": previous.NOTE,
        }
    )
    (output / "build-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visibility", choices=("masked", "shown"), required=True)
    parser.add_argument("--kernel-id", required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build(output, visibility=args.visibility, kernel_id=args.kernel_id)
    print(
        json.dumps(
            {"output": str(output), "notebook_sha256": result["output_notebook_sha256"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
