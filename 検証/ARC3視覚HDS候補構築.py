"""Build an isolated, offline-only v5 visual solver + HDS shadow pilot."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE_NOTEBOOK = ROOT / "出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb"
SOURCE_ROOT = ROOT / "入力/モデル実行基底/v5/taaf-source-v1/patched"
SOURCE_MANIFEST = SOURCE_ROOT.parent / "source-manifest.json"
METADATA_SOURCE = ROOT / "出力/ARC3-RUN-003-local/C2-046/source/off/kernel-metadata.json"
BRIDGE_SOURCE = ROOT / "検証/ARC3視覚HDS接続候補.py"
BASE_SHA = "5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc"
SOURCE_MANIFEST_SHA = "2c9daf710a75154256e42dcf77a59cd4c580421a08d4bf434a913ef15bf66c12"
METADATA_SHA = "e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372"
BRIDGE_SHA = "1a1c48ad03a3c38668e8b8eba85ef61d8fb86a50143c80c221ba586c22d08617"
SOLVER_REL = "src/ARC3-Inference/inference/framework/solver.py"
SOLVER_SHA = "42b4794f0447e071ba118194c64d009f7fa59df0b84f3d9c35da4dd215824c52"
TOOL_AGENT_REL = "src/ARC3-Inference/inference/agent/tool_agent.py"
TOOL_AGENT_SHA = "053556f4a2d19bbb0f04d3ecde14bad2d76abfe91e89254740b763136a5a8e82"
GUARD_CELL_SHA = "017470ef5a5f0b9ab82836dc13a7137f2f821db1d6770bb3e8e9234930e3e40f"


RUNTIME_SOURCE = r'''"""Observe each actual visual-solver action; never choose or authorize one."""
from __future__ import annotations
from collections import Counter
import importlib
import json
import os
from pathlib import Path
_API = None

def _api():
    global _API
    if _API is None:
        _API = importlib.import_module("ARC3視覚HDS接続候補")
    return _API

def _mode():
    value = os.environ.get("ARC3_VISUAL_HDS_MODE", "shadow")
    if value not in {"off", "shadow"}:
        raise ValueError("Only off/shadow are validated; hints are not supported.")
    return value

def _runtime(session):
    value = getattr(session, "_arc3_visual_hds_runtime", None)
    if value is None:
        value = {"mode": _mode(), "counts": Counter(), "bridge": None,
                 "bridge_init_attempted": False, "last_adapter_error": None}
        session._arc3_visual_hds_runtime = value
    return value

def _frame(state, grid):
    raw_state = state.raw.state
    state_name = getattr(raw_state, "name", str(raw_state))
    return _api().PublicFrame(
        board=tuple(tuple(int(cell) for cell in row) for row in grid),
        state=state_name,
        levels_completed=int(state.levels_completed),
        available_actions=tuple(int(value) for value in state.available_actions),
    )

def _current_grid(state):
    data = state.frame.data
    rows = data.tolist() if hasattr(data, "tolist") else data
    return tuple(tuple(int(cell) for cell in row) for row in rows)

def _action(action):
    name = getattr(action.id, "name", "")
    if name == "RESET":
        return _api().PublicAction(0)
    if not name.startswith("ACTION") or not name[6:].isdigit():
        raise ValueError("Unknown public action name")
    number = int(name[6:])
    if number == 6:
        return _api().PublicAction(number, x=action.data.get("x"), y=action.data.get("y"))
    return _api().PublicAction(number)

def _bridge(runtime):
    if not runtime["bridge_init_attempted"]:
        runtime["bridge_init_attempted"] = True
        runtime["bridge"] = _api().VisualHDSBridge(
            update_budget=int(os.environ["ARC3_VISUAL_HDS_UPDATE_BUDGET"]),
            query_budget=int(os.environ["ARC3_VISUAL_HDS_QUERY_BUDGET"]),
            hds_seconds_budget=float(os.environ["ARC3_VISUAL_HDS_SECONDS_BUDGET"]),
        )
    return runtime["bridge"]

def _write_stats(session, runtime):
    try:
        bridge = runtime["bridge"]
        result = {
            "schema": "arc3-visual-hds-shadow-telemetry.v1",
            "mode": runtime["mode"],
            "authorization": False,
            "continue_visual_solver": True,
            "model_context_modified": False,
            "prediction_measurement_revision": "native-target-outcome-prequential.v1",
            "counts": dict(sorted(runtime["counts"].items())),
            "last_adapter_error": runtime["last_adapter_error"],
            "hds": bridge.stats if bridge is not None else None,
            "prior": bridge.prior_report if bridge is not None else None,
            "raw_ids_boards_coordinates_or_action_sequences_persisted": False,
        }
        path = Path(session.state_path).with_suffix(".visual-hds.json")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except Exception as exc:
        runtime["counts"]["telemetry_write_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__

def before_action(session, action, *, public_grid, automatic=False):
    runtime = _runtime(session)
    runtime["counts"]["actual_action_calls_seen"] += 1
    if runtime["mode"] == "off":
        return None
    if automatic or getattr(action.id, "name", "") == "RESET":
        runtime["counts"]["skipped_automatic_actions"] += int(bool(automatic))
        runtime["counts"]["skipped_RESET_actions"] += int(getattr(action.id, "name", "") == "RESET")
        return None
    try:
        step = int(session.action_count)
        before = _frame(session.game.current_state, public_grid)
        candidate = _action(action)
        bridge = _bridge(runtime)
        if bridge is None:
            runtime["counts"]["unavailable_bridge"] += 1
            return None
        result = bridge.query(before, candidate)
        runtime["counts"]["query_status:" + str(result.get("bridge_status", "missing"))] += 1
        runtime["counts"]["query_native:" + str(result.get("native_status", "missing"))] += 1
        for reason in result.get("native_hold_reasons", ()):
            if isinstance(reason, str):
                runtime["counts"]["query_native_hold_reason:" + reason[:160]] += 1
        runtime["counts"]["queries_with_relevant_predictions"] += int(bool(result.get("relevant_prediction_count")))
        if int(session.action_count) != step or _frame(session.game.current_state, _current_grid(session.game.current_state)) != before:
            runtime["counts"]["public_state_changed_during_HDS_query"] += 1
            return None
        return {"before": before, "action": candidate, "step": step, "query": result}
    except Exception as exc:
        runtime["counts"]["before_adapter_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
        return None

def _target_forecast(result):
    """Qualify returned outcome-path evidence for measurement, without changing HDS judgment."""
    if result.get("bridge_status") != "queried":
        return "query_not_completed", set()
    if result.get("native_status") not in {"出力", "断定保留"}:
        return "unrecognized_native_status", set()
    if result.get("authorization") is not False:
        return "authorization_boundary", set()
    for key, reason in (
        ("relevant_conflict_count", "target_conflict"),
        ("relevant_observation_request_count", "target_observation_request"),
    ):
        if type(result.get(key)) is not int:
            return "missing_target_count", set()
        if result[key] != 0:
            return reason, set()
    if result.get("summary_is_truncated") is not False:
        return "truncated_or_missing_target_summary", set()
    refs = {
        row["principle_ref"]
        for row in result.get("rule_evidence", ())
        if isinstance(row, dict)
        and row.get("native_state") == "適用範囲付き暫定原理"
        and row.get("native_adoption_state") == "有効"
        and isinstance(row.get("principle_ref"), str)
        and row["principle_ref"]
    }
    if not refs:
        return "no_active_target_rule", set()
    values = {
        row["value"]
        for row in result.get("predictions", ())
        if isinstance(row, dict)
        and isinstance(row.get("principle_ref"), str)
        and row["principle_ref"] in refs
        and isinstance(row.get("value"), str)
        and row["value"] in _api()._OUTCOMES
    }
    return (None, values) if values else ("no_qualified_target_prediction", set())

def after_action(session, action, captured, new_state, *, public_grid, automatic=False):
    runtime = _runtime(session)
    if captured is None:
        _write_stats(session, runtime)
        return
    try:
        if automatic or getattr(action.id, "name", "") == "RESET":
            raise ValueError("A skipped lifecycle action unexpectedly has a captured query")
        if int(session.action_count) != captured["step"] + 1:
            runtime["counts"]["public_action_step_mismatch"] += 1
            return
        # Explicit new_state preserves the fatal response even if current_state later resets.
        after = _frame(new_state, public_grid)
        outcome = _api()._observed_outcome(captured["before"], after)
        runtime["counts"]["public_outcome:" + outcome] += 1
        runtime["counts"]["public_responses_observed"] += 1
        blocked, target_values = _target_forecast(captured["query"])
        if blocked is not None:
            runtime["counts"]["target_forecast_blocked:" + blocked] += 1
        elif target_values:
            runtime["counts"]["target_qualified_forecast_queries"] += 1
            if len(target_values) == 1:
                runtime["counts"]["target_qualified_unique_predictions_observed"] += 1
                runtime["counts"]["target_qualified_unique_prediction_matches"] += int(outcome in target_values)
                runtime["counts"]["target_qualified_unique_native_status:" + captured["query"]["native_status"]] += 1
            else:
                runtime["counts"]["target_qualified_multiple_prediction_values"] += 1
        supported = _api().render_hint(captured["query"], max_chars=1200)
        if supported:
            runtime["counts"]["queries_with_supported_nonconflicting_context"] += 1
            payload = json.loads(supported.split("\n", 1)[1])
            values = {row["value"] for row in payload["predictions"]}
            if len(values) == 1:
                runtime["counts"]["supported_unique_predictions_observed"] += 1
                runtime["counts"]["supported_unique_prediction_matches"] += int(outcome in values)
            else:
                runtime["counts"]["supported_multiple_prediction_values"] += 1
        result = runtime["bridge"].update(captured["before"], captured["action"], after)
        runtime["counts"]["update_status:" + str(result.get("bridge_status", "missing"))] += 1
        runtime["counts"]["update_native:" + str(result.get("native_status", "missing"))] += 1
    except Exception as exc:
        runtime["counts"]["after_adapter_errors"] += 1
        runtime["last_adapter_error"] = type(exc).__name__
    finally:
        _write_stats(session, runtime)
'''

SOLVER_REPLACEMENTS = (
    (
        "from __future__ import annotations\n",
        "from __future__ import annotations\n"
        "from arc3_visual_hds_runtime import before_action as _arc3_hds_before_action, after_action as _arc3_hds_after_action\n",
    ),
    (
        "        previous_grid = _grid_from_state(self.game.current_state)\n"
        "        previous_completed = int(self.game.current_state.levels_completed)\n",
        "        previous_grid = _grid_from_state(self.game.current_state)\n"
        "        previous_completed = int(self.game.current_state.levels_completed)\n"
        "        _arc3_hds_step = _arc3_hds_before_action(self, action, public_grid=previous_grid, automatic=automatic)\n",
    ),
    (
        "        new_grid = _grid_from_state(new_state)\n",
        "        new_grid = _grid_from_state(new_state)\n"
        "        _arc3_hds_after_action(self, action, _arc3_hds_step, new_state, public_grid=new_grid, automatic=automatic)\n",
    ),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _guarded(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if _sha(raw) != expected:
        raise ValueError(f"Pinned input drift: {path}")
    return raw


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError("Expected exactly one source anchor; refusing drift")
    return source.replace(old, new, 1)


def _patch_solver(raw: bytes) -> bytes:
    if _sha(raw) != SOLVER_SHA or b"\r" in raw:
        raise ValueError("Pinned LF solver source drift")
    source = raw.decode("utf-8")
    for old, new in SOLVER_REPLACEMENTS:
        source = _replace_once(source, old, new)
    compile(source, SOLVER_REL, "exec")
    return source.encode("utf-8")


def _bundle() -> tuple[bytes, dict]:
    builder_path = ROOT / "道具/ARC3提出物構築.py"
    spec = importlib.util.spec_from_file_location("arc3_visual_bundle_builder", builder_path)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    original, _ = builder._bundle()
    files = {}
    with zipfile.ZipFile(BytesIO(original)) as archive:
        for name in archive.namelist():
            if (
                name.startswith("HDS/学習系統/v0.4.2/hds学習系統/")
                or name == "接続/ARC3事前記憶.py"
            ):
                files[name] = archive.read(name)
    if "接続/ARC3事前記憶.py" not in files or not any(
        name.endswith("hds学習系統/__init__.py") for name in files
    ):
        raise ValueError("Existing source bundle did not supply HDS and prior loader")
    files["検証/ARC3視覚HDS接続候補.py"] = _guarded(BRIDGE_SOURCE, BRIDGE_SHA)
    files["arc3_visual_hds_runtime.py"] = RUNTIME_SOURCE.encode("utf-8")
    manifest = {
        "schema": "arc3-visual-hds-source-bundle.v1",
        "existing_builder_sha256": _sha(builder_path.read_bytes()),
        "original_builder_bundle_sha256": _sha(original),
        "files": [
            {"path": name, "bytes": len(raw), "sha256": _sha(raw)}
            for name, raw in sorted(files.items())
        ],
        "blind_exploration_agent_included": False,
    }
    files["ARC3-VISUAL-HDS-MANIFEST.json"] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            if name.endswith(".py"):
                compile(raw.decode("utf-8"), name, "exec")
            info = zipfile.ZipInfo(name, date_time=builder.EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return output.getvalue(), manifest


def _cpu_bundle_import(payload: bytes) -> dict:
    with tempfile.TemporaryDirectory(prefix="arc3-visual-hds-import-") as folder:
        base = Path(folder)
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            archive.extractall(base)
        smoke = (
            "import json, pathlib, sys\n"
            f"root=pathlib.Path({str(base)!r})\n"
            "sys.path[:0]=[str(root),str(root/'検証'),str(root/'HDS/学習系統/v0.4.2')]\n"
            "import arc3_visual_hds_runtime as runtime\n"
            "assert 'hds学習系統' not in sys.modules\n"
            "import ARC3視覚HDS接続候補 as bridge\n"
            "import hds学習系統 as native\n"
            "assert pathlib.Path(bridge.__file__).is_relative_to(root)\n"
            "assert pathlib.Path(native.__file__).is_relative_to(root)\n"
            "assert 'MyAgent' not in vars(runtime)\n"
            "print(json.dumps({'bundle_import':True,'hds_instance_created':False,'gpu_import_or_call':False}))\n"
        )
        env = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "PATH", "TEMP", "TMP")
            if key in os.environ
        }
        env.update({"CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1"})
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-X", "utf8", "-c", smoke],
            cwd=base,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout.strip())


def _cpu_patch_cell(source: str, source_files: dict[str, bytes], expected_solver: bytes) -> dict:
    """Execute only the generated packaging cell against a temporary public source copy."""
    with tempfile.TemporaryDirectory(prefix="arc3-visual-hds-cell-") as folder:
        base = Path(folder)
        bundle_dir = base / "public-source"
        for name, raw in source_files.items():
            path = bundle_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (base / "cell.py").write_text(source, encoding="utf-8")
        smoke = f"""import hashlib, json, os, pathlib, sys, sysconfig, tempfile
root = pathlib.Path({str(base)!r})
site = root / "isolated-site"
site.mkdir()
sysconfig.get_paths = lambda: {{"purelib": str(site)}}
original_mkdtemp = tempfile.mkdtemp
def isolated_mkdtemp(*args, **kwargs):
    kwargs["dir"] = root
    return original_mkdtemp(*args, **kwargs)
tempfile.mkdtemp = isolated_mkdtemp
context = {{"TRUE_SUBMISSION": False, "BUNDLE_DIR": root / "public-source", "os": os}}
exec(compile((root / "cell.py").read_text(encoding="utf-8"), "generated-cell", "exec"), context)
pth = (site / "arc3_visual_hds_sources.pth").read_text(encoding="utf-8")
assert pth.endswith(chr(10)) and pth.splitlines() == context["_arc3_hds_paths"]
assert all(pathlib.Path(value).is_dir() for value in pth.splitlines())
assert hashlib.sha256((root / "public-source" / {SOLVER_REL!r}).read_bytes()).hexdigest() == {_sha(expected_solver)!r}
assert hashlib.sha256((root / "public-source" / {TOOL_AGENT_REL!r}).read_bytes()).hexdigest() == {TOOL_AGENT_SHA!r}
assert os.environ["LOCAL_ANALYZER_SEED"] == "0"
assert "hds学習系統" not in sys.modules and "inference" not in sys.modules
print(json.dumps({{"generated_cell_executed": True, "pth_newline_paths": len(pth.splitlines()), "model_seed_before_import": 0, "GPU_or_framework_import": False, "public_source_hashguards_passed": True}}))
"""
        script = base / "preflight.py"
        script.write_text(smoke, encoding="utf-8")
        env = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "PATH", "TEMP", "TMP")
            if key in os.environ
        }
        env.update({"CUDA_VISIBLE_DEVICES": "", "HF_HUB_OFFLINE": "1"})
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-X", "utf8", str(script)],
            cwd=base,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=True,
        )
        return json.loads(result.stdout.splitlines()[-1])


def _patch_cell(payload: bytes, records: list[dict], mode: str, budgets: dict) -> str:
    settings = json.dumps({"mode": mode, **budgets}, sort_keys=True)
    patches = json.dumps([[old, new] for old, new in SOLVER_REPLACEMENTS], ensure_ascii=False)
    return f"""# C2-078: isolated visual-HDS OFF/SHADOW pilot; original visual model remains in control.
import base64, hashlib, io, json, sys, sysconfig, tempfile, zipfile
from pathlib import Path, PurePosixPath
if TRUE_SUBMISSION:
    raise RuntimeError("C2-078 is an offline pilot; competition rerun is not enabled.")
_arc3_hds_settings = json.loads({settings!r})
if _arc3_hds_settings["mode"] not in {{"off", "shadow"}}:
    raise ValueError("Only off/shadow are validated; hints are not supported.")
for _item in json.loads({json.dumps(records, ensure_ascii=False)!r}):
    _raw = (BUNDLE_DIR / PurePosixPath(_item["path"])).read_bytes()
    if len(_raw) != _item["bytes"] or hashlib.sha256(_raw).hexdigest() != _item["sha256"]:
        raise RuntimeError("Post-v5 public source drift: " + _item["path"])
_arc3_hds_payload = base64.b64decode({base64.b64encode(payload).decode("ascii")!r}, validate=True)
if hashlib.sha256(_arc3_hds_payload).hexdigest() != {_sha(payload)!r}:
    raise RuntimeError("Visual-HDS bundle hash mismatch")
_arc3_hds_root = Path(tempfile.mkdtemp(prefix="arc3-visual-hds-v6-"))
with zipfile.ZipFile(io.BytesIO(_arc3_hds_payload)) as _archive:
    for _name in _archive.namelist():
        _path = PurePosixPath(_name)
        if _path.is_absolute() or ".." in _path.parts or not (
            _name.startswith("HDS/学習系統/v0.4.2/hds学習系統/")
            or _name in {{"接続/ARC3事前記憶.py", "検証/ARC3視覚HDS接続候補.py", "arc3_visual_hds_runtime.py", "ARC3-VISUAL-HDS-MANIFEST.json"}}
        ):
            raise RuntimeError("Unexpected visual-HDS bundle path")
    _archive.extractall(_arc3_hds_root)
_arc3_hds_manifest = json.loads((_arc3_hds_root / "ARC3-VISUAL-HDS-MANIFEST.json").read_text(encoding="utf-8"))
for _item in _arc3_hds_manifest["files"]:
    _raw = (_arc3_hds_root / PurePosixPath(_item["path"])).read_bytes()
    if len(_raw) != _item["bytes"] or hashlib.sha256(_raw).hexdigest() != _item["sha256"]:
        raise RuntimeError("Extracted visual-HDS source hash mismatch")
_arc3_hds_paths = [str(_arc3_hds_root), str(_arc3_hds_root / "検証"), str(_arc3_hds_root / "HDS/学習系統/v0.4.2")]
sys.path[:0] = _arc3_hds_paths
(Path(sysconfig.get_paths()["purelib"]) / "arc3_visual_hds_sources.pth").write_text("".join(p + chr(10) for p in _arc3_hds_paths), encoding="utf-8")
_arc3_hds_solver_path = BUNDLE_DIR / {SOLVER_REL!r}
_arc3_hds_solver = _arc3_hds_solver_path.read_text(encoding="utf-8")
for _old, _new in json.loads({patches!r}):
    if _arc3_hds_solver.count(_old) != 1:
        raise RuntimeError("Visual-HDS source anchor drift")
    _arc3_hds_solver = _arc3_hds_solver.replace(_old, _new, 1)
compile(_arc3_hds_solver, str(_arc3_hds_solver_path), "exec")
_arc3_hds_solver_path.write_bytes(_arc3_hds_solver.encode("utf-8"))
os.environ["ARC3_VISUAL_HDS_MODE"] = _arc3_hds_settings["mode"]
os.environ["ARC3_VISUAL_HDS_UPDATE_BUDGET"] = str(_arc3_hds_settings["update_budget"])
os.environ["ARC3_VISUAL_HDS_QUERY_BUDGET"] = str(_arc3_hds_settings["query_budget"])
os.environ["ARC3_VISUAL_HDS_SECONDS_BUDGET"] = str(_arc3_hds_settings["hds_seconds_budget"])
os.environ["LOCAL_ANALYZER_SEED"] = "0"
print("C2-078 visual-HDS mode:", _arc3_hds_settings["mode"], "; model context unchanged; authorization=false")
"""


def build(
    output: Path,
    *,
    mode: str,
    kernel_id: str,
    update_budget: int = 80,
    query_budget: int = 80,
    hds_seconds_budget: float = 120.0,
) -> dict:
    if mode not in {"off", "shadow"}:
        raise ValueError("Only off/shadow are validated; hints are not supported")
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", kernel_id):
        raise ValueError("An explicit owner/draft-slug is required")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite output: {output}")
    if (
        any(
            type(value) is not int or not 0 <= value <= 80
            for value in (update_budget, query_budget)
        )
        or not math.isfinite(hds_seconds_budget)
        or not 0 <= hds_seconds_budget <= 120
    ):
        raise ValueError(
            "Pilot budgets must be finite: updates/queries 0..80 and HDS seconds 0..120"
        )
    notebook = json.loads(_guarded(BASE_NOTEBOOK, BASE_SHA).decode("utf-8"))
    source_manifest = json.loads(_guarded(SOURCE_MANIFEST, SOURCE_MANIFEST_SHA).decode("utf-8"))
    metadata = json.loads(_guarded(METADATA_SOURCE, METADATA_SHA).decode("utf-8"))
    if kernel_id == metadata["id"]:
        raise ValueError("Use a distinct local draft slug, not the existing visual kernel")
    if not (
        metadata["is_private"] is True
        and metadata["enable_gpu"] is True
        and metadata["enable_internet"] is False
    ):
        raise ValueError("Private GPU/no-internet metadata contract drift")
    records = source_manifest["patched_source_manifest"]
    source_files = {
        item["path"]: _guarded(SOURCE_ROOT / item["path"], item["sha256"]) for item in records
    }
    if _sha(source_files[TOOL_AGENT_REL]) != TOOL_AGENT_SHA:
        raise ValueError("ToolAgent prompt/control source drift")
    tool_source = source_files[TOOL_AGENT_REL].decode("utf-8")
    if (
        '_LOCAL_ANALYZER_SEED = _get_env_int("LOCAL_ANALYZER_SEED", -1)' not in tool_source
        or "seed=_LOCAL_ANALYZER_SEED," not in tool_source
    ):
        raise ValueError("ToolAgent model-seed request plumbing drift")
    patched_solver = _patch_solver(source_files[SOLVER_REL])
    payload, bundle_manifest = _bundle()
    budgets = {
        "update_budget": update_budget,
        "query_budget": query_budget,
        "hds_seconds_budget": hds_seconds_budget,
    }
    inserted = _patch_cell(payload, records, mode, budgets)
    compile(inserted, "visual-hds-patch-cell", "exec")
    guard = "".join(notebook["cells"][18]["source"])
    if _sha(guard.encode("utf-8")) != GUARD_CELL_SHA:
        raise ValueError("Pinned offline guard cell drift")
    guard = _replace_once(
        guard,
        'os.environ.get("ARC3_DEV_GAME_LIMIT", "25")',
        'os.environ.get("ARC3_DEV_GAME_LIMIT", "3")',
    )
    guard = _replace_once(guard, "if DEV_GAME_LIMIT < 1:", "if not 1 <= DEV_GAME_LIMIT <= 3:")
    guard = _replace_once(
        guard,
        '"ARC3_DEV_GAME_LIMIT must be at least 1"',
        '"ARC3_DEV_GAME_LIMIT must be between 1 and 3"',
    )
    compile(guard, "offline-pilot-guard", "exec")
    notebook["cells"][18]["source"] = guard
    notebook["cells"].insert(
        6,
        {
            "id": "arc3-visual-hds-shadow-patch",
            "cell_type": "code",
            "metadata": {"trusted": True},
            "source": inserted,
            "outputs": [],
            "execution_count": None,
        },
    )
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    parsed = 0
    for name, raw in source_files.items():
        if name.endswith(".py"):
            compile((patched_solver if name == SOLVER_REL else raw).decode("utf-8"), name, "exec")
            parsed += 1
    import_smoke = _cpu_bundle_import(payload)
    cell_smoke = _cpu_patch_cell(inserted, source_files, patched_solver)
    metadata.update(
        {
            "id": kernel_id,
            "title": f"ARC3 Visual HDS V6 {mode.upper()} Pilot",
            "code_file": "submission.ipynb",
        }
    )
    notebook_raw = (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    metadata_raw = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest = {
        "schema": "arc3-visual-hds-pilot-build.v1",
        "builder_source_sha256": _sha(Path(__file__).read_bytes()),
        "runtime_adapter_sha256": _sha(RUNTIME_SOURCE.encode("utf-8")),
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "budgets_per_game": budgets,
        "pilot": {
            "games_max": 3,
            "passes": 1,
            "concurrency": 1,
            "actions_max": 80,
            "runtime_seconds_max": 1200,
            "competition_rerun_allowed": False,
        },
        "base_notebook_sha256": BASE_SHA,
        "source_preparation_manifest_sha256": SOURCE_MANIFEST_SHA,
        "bridge_sha256": BRIDGE_SHA,
        "metadata_template_sha256": METADATA_SHA,
        "output_notebook_sha256": _sha(notebook_raw),
        "kernel_metadata_sha256": _sha(metadata_raw),
        "bundle_sha256": _sha(payload),
        "bundle_manifest": bundle_manifest,
        "patched_solver_sha256": _sha(patched_solver),
        "tool_agent_source_unchanged_sha256": TOOL_AGENT_SHA,
        "base_cells_preserved_except_offline_guard": True,
        "system_prompt_unchanged": True,
        "model_configuration_unchanged_except_shared_explicit_seed": True,
        "shared_model_seed": 0,
        "model_seed_set_before_ToolAgent_import": True,
        "model_seed_passed_to_build_chat_payload": True,
        "environment_seed": {
            "explicitly_requested_by_notebook": False,
            "SDK_default": "unverified",
            "runtime_verified": False,
            "initial_state_equivalence_runtime_check": "pending",
        },
        "GPU_determinism_proven": False,
        "inserted_after_base_cell": 5,
        "per_actual_action_query_before_execute_update_after_public_response": True,
        "RESET_and_automatic_actions_excluded": True,
        "fatal_response_uses_explicit_new_state": True,
        "mode_hints_rejected": True,
        "model_context_modified": False,
        "action_authorization": False,
        "cpu_source_files_compiled_without_import": parsed,
        "cpu_bundled_import": import_smoke,
        "cpu_generated_patch_cell": cell_smoke,
        "source_parity_limit": source_manifest["provenance_caveat"],
        "historical_v5_score_reproduced": False,
        "native_HDS_predictive_or_causal_improvement_proven": False,
        "native_target_prediction_measurement": "native-target-outcome-prequential.v1",
        "render_hint_statistics_preserved_and_separate": True,
        "GPU_model_inference_run": False,
        "Kaggle_operation_performed": False,
        "source_inputs": records,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "submission.ipynb").write_bytes(notebook_raw)
    (output / "kernel-metadata.json").write_bytes(metadata_raw)
    (output / "visual-hds-source.zip").write_bytes(payload)
    for name, raw in source_files.items():
        path = output / "preflight-source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(patched_solver if name == SOLVER_REL else raw)
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("off", "shadow"), default="shadow")
    parser.add_argument("--kernel-id", required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = build(output, mode=args.mode, kernel_id=args.kernel_id)
    print(
        json.dumps(
            {
                "output": str(output),
                "mode": manifest["mode"],
                "notebook_sha256": manifest["output_notebook_sha256"],
                "compiled_source_files": manifest["cpu_source_files_compiled_without_import"],
                "bundled_import": manifest["cpu_bundled_import"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
