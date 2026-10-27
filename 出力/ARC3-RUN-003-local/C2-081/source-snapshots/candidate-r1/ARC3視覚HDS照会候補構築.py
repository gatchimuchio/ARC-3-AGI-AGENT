"""C2-081 LOCAL drafts: original native HDS evidence through the existing Python RPC."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCE = ROOT / "検証/ARC3視覚HDS候補構築.py"
BASE_SHA = "3b1b87bf7075c015c41f0378d7e8b5b42135ec1fa6868886f555565ee270eb1d"
RUNTIME_SOURCE = ROOT / "検証/候補/ARC3PythonHDS照会runtime.py"
SANDBOX_REL = "src/ARC3-Inference/inference/agent/python_tool_sandbox.py"
NOTE = (
    "Optional hds_query(candidate) inspects ONE legal action without executing it. "
    "Use an inspection-only Python call, read its returned UNCERTAIN native evidence, "
    "then visually reason and choose your action in a separate Python call. "
    "Native HOLD and missing evidence remain unresolved; there is no endorsement or action authorization. "
    "Continue independent legal exploration on HOLD, errors, or budget exhaustion. "
    "For MOUSE use exact integer row/col; do not enumerate coordinates. "
    "Board change is not proof of level progress."
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def base_builder():
    if sha(BASE_SOURCE.read_bytes()) != BASE_SHA:
        raise ValueError("Frozen R3 builder drift")
    snapshots = ROOT / "出力/ARC3-RUN-003-local/C2-081/source-snapshots/manifest.json"
    for row in json.loads(snapshots.read_text(encoding="utf-8"))["sources"]:
        if sha((ROOT / row["snapshot"]).read_bytes()) != row["sha256"]:
            raise ValueError("Frozen R3 source snapshot drift")
    spec = importlib.util.spec_from_file_location("arc3_c2081_frozen_builder", BASE_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != ROOT:
        raise ValueError("Frozen builder ROOT must resolve explicitly to this repository")
    return module


def source_patches(base):
    tool = base.TOOL_AGENT_REL
    return [
        (
            tool,
            '    "and `action(actions)` for executing one or more real environment actions. "',
            '    "`hds_query(candidate)` for optional UNCERTAIN native evidence, "\n'
            '    "and `action(actions)` for executing one or more real environment actions. "',
        ),
        (
            tool,
            '                "Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.",',
            f"                {NOTE!r},\n"
            '                "Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.",',
        ),
        (
            tool,
            '        code = str(arguments.get("code", "")).rstrip()\n',
            '        code = str(arguments.get("code", "")).rstrip()\n'
            '        self._arc3_hds_python_sequence = getattr(self, "_arc3_hds_python_sequence", 0) + 1\n'
            '        hds_tool_call_id = f"python-{self._arc3_hds_python_sequence}:" + str(getattr(self, "_arc3_active_tool_call_id", ""))\n'
            '        hds_model_turn_id = str(getattr(self, "_arc3_hds_active_model_turn", ""))\n',
        ),
        (
            tool,
            "        def _handle_animation(request: dict[str, Any]) -> dict[str, Any]:\n",
            "        def _handle_hds_query(request: dict[str, Any]) -> dict[str, Any]:\n"
            "            if self._step_env_callback is None:\n"
            '                return {"executed": False, "authorization": False, "endorsement": False, "status": "session_unavailable"}\n'
            '            return self._step_env_callback({**request, "query": "hds", "tool_call_id": hds_tool_call_id, "model_turn_id": hds_model_turn_id})\n\n'
            "        def _handle_animation(request: dict[str, Any]) -> dict[str, Any]:\n",
        ),
        (
            tool,
            "            normalized_actions = self._normalize_python_actions(actions)\n",
            "            normalized_actions = self._normalize_python_actions(actions)\n"
            "            try:\n"
            '                self._step_env_callback({"query": "hds_action_order", "tool_call_id": hds_tool_call_id, "model_turn_id": hds_model_turn_id})\n'
            "            except Exception:\n"
            "                pass  # Ordering telemetry never prevents independent legal play.\n",
        ),
        (
            tool,
            "            action_handler=_handle_action,\n",
            "            action_handler=_handle_action,\n"
            "            hds_query_handler=_handle_hds_query,\n",
        ),
        (
            tool,
            "                for tool_index, tool_call in enumerate(tool_calls):\n",
            '                self._arc3_hds_model_response_sequence = getattr(self, "_arc3_hds_model_response_sequence", 0) + 1\n'
            '                self._arc3_hds_active_model_turn = f"model-{self._arc3_hds_model_response_sequence}"\n'
            "                for tool_index, tool_call in enumerate(tool_calls):\n",
        ),
        (
            tool,
            "                    dispatch = self._dispatch_tool(state_path, tool_name, arguments)\n",
            '                    self._arc3_active_tool_call_id = str(tool_call.get("id", ""))\n'
            "                    dispatch = self._dispatch_tool(state_path, tool_name, arguments)\n",
        ),
        (
            SANDBOX_REL,
            "    animation_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,\n",
            "    animation_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,\n"
            "    hds_query_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,\n",
        ),
        (
            SANDBOX_REL,
            '        runtime_globals["action"] = action\n',
            """        def hds_query(candidate):
            if not isinstance(candidate, (str, dict)):
                return {"executed": False, "authorization": False, "endorsement": False,
                        "status": "invalid_single_candidate", "evidence_status": "UNAVAILABLE"}
            current = runtime_globals.get("current_frame")
            _send({"type": "hds_query", "request": {
                "candidate": candidate, "expected_step": getattr(current, "step", None)}})
            reply = _recv()
            if reply.get("type") != "hds_query_result":
                return {"executed": False, "authorization": False, "endorsement": False,
                        "status": "query_unavailable", "evidence_status": "UNAVAILABLE"}
            return reply.get("evidence") or {}

        runtime_globals["hds_query"] = hds_query
        runtime_globals["action"] = action
""",
        ),
        (
            SANDBOX_REL,
            '            if msg_type == "animation":\n',
            """            if msg_type == "hds_query":
                fallback = {"executed": False, "authorization": False, "endorsement": False,
                            "status": "query_unavailable", "evidence_status": "UNAVAILABLE"}
                try:
                    evidence = (hds_query_handler(dict(message.get("request") or {}))
                                if hds_query_handler is not None else fallback)
                except Exception:
                    evidence = fallback
                _send_json_line(process.stdin, {"type": "hds_query_result", "evidence": evidence})
                continue
            if msg_type == "animation":
""",
        ),
    ]


def patched_extra_sources(base):
    manifest = json.loads(base.SOURCE_MANIFEST.read_text(encoding="utf-8"))
    byname = {r["path"]: r["sha256"] for r in manifest["patched_source_manifest"]}
    result = {}
    for name, old, new in source_patches(base):
        if name not in result:
            result[name] = base._guarded(base.SOURCE_ROOT / name, byname[name]).decode("utf-8")
        result[name] = base._replace_once(result[name], old, new)
    for name, text in result.items():
        compile(text, name, "exec")
    return {name: text.encode("utf-8") for name, text in result.items()}


def configure(base, visibility):
    if visibility not in {"masked", "shown"}:
        raise ValueError("visibility must be masked or shown")
    frozen_runtime = base.RUNTIME_SOURCE
    base.RUNTIME_SOURCE = RUNTIME_SOURCE.read_text(encoding="utf-8")
    compile(base.RUNTIME_SOURCE, "python-hds-runtime", "exec")
    extra_sources = patched_extra_sources(base)
    base.SOLVER_REPLACEMENTS += (
        (
            "from arc3_visual_hds_runtime import before_action as _arc3_hds_before_action, after_action as _arc3_hds_after_action\n",
            "from arc3_visual_hds_runtime import before_action as _arc3_hds_before_action, after_action as _arc3_hds_after_action, query_candidate as _arc3_hds_query_candidate, record_action_call as _arc3_hds_record_action_call\n",
        ),
        (
            "    def step_env(self, arguments: dict[str, Any]) -> dict[str, Any]:\n",
            "    def step_env(self, arguments: dict[str, Any]) -> dict[str, Any]:\n"
            '        if str(arguments.get("query") or "") == "hds":\n'
            "            return _arc3_hds_query_candidate(self, arguments)\n"
            '        if str(arguments.get("query") or "") == "hds_action_order":\n'
            "            return _arc3_hds_record_action_call(self, arguments)\n",
        ),
    )
    original_bundle, original_cell, original_cpu = (
        base._bundle,
        base._patch_cell,
        base._cpu_patch_cell,
    )

    def bundle():
        payload, manifest = original_bundle()
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            files = {
                name: archive.read(name)
                for name in archive.namelist()
                if name != "ARC3-VISUAL-HDS-MANIFEST.json"
            }
        files["arc3_visual_hds_base.py"] = frozen_runtime.encode("utf-8")
        manifest["files"] = [
            {"path": name, "bytes": len(raw), "sha256": sha(raw)}
            for name, raw in sorted(files.items())
        ]
        manifest["frozen_R3_runtime_base_sha256"] = sha(frozen_runtime.encode("utf-8"))
        files["ARC3-VISUAL-HDS-MANIFEST.json"] = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        result = BytesIO()
        with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
                archive.writestr(info, raw)
        return result.getvalue(), manifest

    def cell(payload, records, mode, budgets):
        source = original_cell(payload, records, mode, budgets)
        source = base._replace_once(
            source,
            '"arc3_visual_hds_runtime.py", "ARC3-VISUAL-HDS-MANIFEST.json"',
            '"arc3_visual_hds_runtime.py", "arc3_visual_hds_base.py", "ARC3-VISUAL-HDS-MANIFEST.json"',
        )
        source = source.replace(
            "# C2-078: isolated visual-HDS OFF/SHADOW pilot; original visual model remains in control.",
            "# C2-081 LOCAL: optional uncertain native evidence; original native judgment retained.",
        )
        specs = json.dumps(source_patches(base), ensure_ascii=False)
        post = json.dumps(
            {name: sha(raw) for name, raw in extra_sources.items()}, ensure_ascii=False
        )
        source += f"""\n# Shared RPC/prompt overlay, applied before any inference/framework import.
for _name, _old, _new in json.loads({specs!r}):
    _path = BUNDLE_DIR / PurePosixPath(_name)
    _text = _path.read_text(encoding="utf-8")
    if _text.count(_old) != 1:
        raise RuntimeError("Python-HDS RPC anchor drift: " + _name)
    _text = _text.replace(_old, _new, 1)
    compile(_text, str(_path), "exec")
    _path.write_bytes(_text.encode("utf-8"))
for _name, _expected in json.loads({post!r}).items():
    if hashlib.sha256((BUNDLE_DIR / PurePosixPath(_name)).read_bytes()).hexdigest() != _expected:
        raise RuntimeError("Python-HDS RPC postimage drift: " + _name)
os.environ["ARC3_HDS_EVIDENCE_VISIBILITY"] = {visibility!r}
"""
        source = source.replace(
            "; model context unchanged; authorization=false",
            "; optional UNCERTAIN evidence; authorization=false",
        )
        return source

    def cpu(source, source_files, expected_solver):
        original_sha = base.TOOL_AGENT_SHA
        base.TOOL_AGENT_SHA = sha(extra_sources[base.TOOL_AGENT_REL])
        try:
            result = original_cpu(source, source_files, expected_solver)
        finally:
            base.TOOL_AGENT_SHA = original_sha
        return {
            **result,
            "RPC_postimage_hashes_verified": True,
            "evidence_visibility": visibility,
            "native_HDS_patched": False,
        }

    base._bundle, base._patch_cell, base._cpu_patch_cell = bundle, cell, cpu
    return extra_sources


def build(output, *, visibility, kernel_id):
    if not re.fullmatch(r"[a-z0-9_-]+/[a-z0-9-]+", kernel_id):
        raise ValueError("draft id must use an explicit lowercase owner/slug")
    base = base_builder()
    extras = configure(base, visibility)
    manifest = base.build(output, mode="shadow", kernel_id=kernel_id)
    for name, raw in extras.items():
        (output / "preflight-source" / name).write_bytes(raw)
    metadata_path = output / "kernel-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["title"] = kernel_id.split("/", 1)[1]
    assert (
        re.sub(r"[^a-z0-9]+", "-", metadata["title"].lower()).strip("-")
        == kernel_id.split("/", 1)[1]
    )
    metadata_path.write_bytes(
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    manifest.pop("tool_agent_source_unchanged_sha256")
    manifest.update(
        {
            "schema": "arc3-python-hds-query-pilot-build.v1",
            "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "builder_source_sha256": sha(Path(__file__).read_bytes()),
            "frozen_R3_builder_sha256": BASE_SHA,
            "candidate_runtime_source_sha256": sha(RUNTIME_SOURCE.read_bytes()),
            "evidence_visibility": visibility,
            "system_prompt_unchanged": False,
            "shared_prompt_note": NOTE,
            "shared_Python_tool_API_extended": True,
            "model_context_modified": visibility == "shown",
            "per_actual_action_query_before_execute_update_after_public_response": False,
            "automatic_execute_time_query_removed_in_both_arms": True,
            "one_after_response_update_per_actual_nonRESET_action": True,
            "native_HDS_version": "original canonical 0.4.2; no C2-079 patch",
            "native_judgment_modified": False,
            "uncertain_native_HOLD_and_partial_forecasts_may_be_shown": True,
            "endorsement": False,
            "distinct_candidate_queries_max_per_public_state": 2,
            "same_call_query_action_flag": "UNREVIEWED; no causal adoption claim",
            "query_scope": "whole_query_original_0.4.2",
            "kernel_id_and_title_normalize_identically": True,
            "kernel_metadata_sha256": sha(metadata_path.read_bytes()),
            "patched_additional_source_sha256": {name: sha(raw) for name, raw in extras.items()},
            "native_target_prediction_measurement": "uncertain-native-query-evidence.v1",
            "render_hint_statistics_preserved_and_separate": False,
            "source_parity_limit": manifest["source_parity_limit"]
            + " Shared Python RPC/helper and prompt note are new experimental changes.",
        }
    )
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


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
