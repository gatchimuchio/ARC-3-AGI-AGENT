from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
import platform
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "learning_repro_r2_builder", ROOT / "検証/ARC3native学習差分再現候補構築.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize("offline", [True, False])
def test_actual_patched_make_expression_forwards_zero_only_offline(offline):
    raw = (builder.SOURCE_ROOT / builder.GAME_API).read_bytes()
    patched = builder.seed_patch(raw)
    tree = ast.parse(patched)
    expressions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "arcade"
        and node.value.func.attr == "make"
    ]
    assert len(expressions) == 1
    recorded = []
    expected = object()

    def make(*args, **kwargs):
        recorded.append((args, kwargs))
        return expected

    namespace = {
        "arcade": SimpleNamespace(make=make),
        "self": SimpleNamespace(
            env_name="public-placeholder", _scorecard_id="scorecard-placeholder"
        ),
        "spec": SimpleNamespace(operation_mode="offline" if offline else "competition"),
        "arc_agi": SimpleNamespace(OperationMode=SimpleNamespace(OFFLINE="offline")),
    }
    exec(
        compile(ast.Module(body=expressions, type_ignores=[]), "actual-public-make", "exec"),
        namespace,
    )
    assert namespace["env"] is expected
    assert recorded == [
        (
            ("public-placeholder",),
            {"scorecard_id": "scorecard-placeholder", **({"seed": 0} if offline else {})},
        )
    ]


@pytest.mark.parametrize("mutation", [b"# changed preimage\n", b"\r\n"])
def test_seed_source_exact_preimage_drift_refused(mutation):
    raw = (builder.SOURCE_ROOT / builder.GAME_API).read_bytes()
    with pytest.raises(ValueError, match="preimage/anchor drift"):
        builder.seed_patch(raw + mutation)


@pytest.mark.parametrize("version_mode", ["actual", "missing", "different"])
def test_software_stamp_observes_metadata_without_value_gate_or_environment_leak(
    monkeypatch, tmp_path, version_mode
):
    import arc_agi

    original = importlib.metadata.version
    expected = {name: original(name) for name in ("arc-agi", "arcengine")}
    if version_mode == "missing":
        expected["arcengine"] = None

        def version(name):
            if name == "arcengine":
                raise importlib.metadata.PackageNotFoundError(name)
            return original(name)

        monkeypatch.setattr(importlib.metadata, "version", version)
    elif version_mode == "different":
        expected = {"arc-agi": "future-wheel-version", "arcengine": "different-wheel-version"}
        monkeypatch.setattr(importlib.metadata, "version", lambda name: expected[name])
    monkeypatch.setenv("C2_087_DO_NOT_STAMP", "never-record-this-marker")
    exec(
        compile(builder.STAMP_SOURCE, "after-wheel-install-stamp", "exec"),
        {"WORKING_DIR": tmp_path, "json": json},
    )
    raw = (tmp_path / builder.STAMP_FILENAME).read_text(encoding="utf-8")
    stamp = json.loads(raw)
    assert stamp["schema"] == builder.STAMP_SCHEMA
    assert stamp["packages"] == expected
    assert stamp["python"] == {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
    }
    assert stamp["public_Arcade_make_signature"] == str(inspect.signature(arc_agi.Arcade.make))
    assert stamp["environment_seed"] == {
        "declared_offline_seed": 0,
        "explicit_keyword_scope": "OFFLINE private pilot only",
        "competition_rerun_allowed": False,
    }
    assert stamp["observation_errors"] == (
        {"package:arcengine": "PackageNotFoundError"} if version_mode == "missing" else {}
    )
    assert "never-record-this-marker" not in raw and "C2_087_DO_NOT_STAMP" not in raw


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_generated_cell_patches_seed_postimage_and_retains_competition_refusal(mode, tmp_path):
    r1 = builder.load_builder()
    observer_builder = r1.load_builder(mode)
    previous, _ = observer_builder.load_builder()
    base = previous.base_builder()
    extras = previous.configure(base, "shown")
    records = json.loads(base.SOURCE_MANIFEST.read_text(encoding="utf-8"))[
        "patched_source_manifest"
    ]
    sources = {r["path"]: base._guarded(base.SOURCE_ROOT / r["path"], r["sha256"]) for r in records}
    payload, _ = base._bundle()
    cell = base._patch_cell(
        payload,
        records,
        "shadow",
        {"update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120.0},
    )
    assert extras[builder.GAME_API] == builder.seed_patch(sources[builder.GAME_API])
    result = base._cpu_patch_cell(cell, sources, base._patch_solver(sources[base.SOLVER_REL]))
    assert result["OFFLINE_explicit_seed_postimage_verified"] is True
    assert result["OFFLINE_declared_seed"] == 0
    assert result["game_response_learning_mode"] == mode
    assert result["native_HDS_patched"] is False
    with pytest.raises(RuntimeError, match="offline pilot"):
        exec(
            compile(cell, "competition-refused-before-patch", "exec"),
            {"TRUE_SUBMISSION": True, "BUNDLE_DIR": tmp_path},
        )
    assert not list(tmp_path.iterdir())
