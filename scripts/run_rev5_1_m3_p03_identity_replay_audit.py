#!/usr/bin/env python3
"""Audit the rev5.1 product for identity routing and fixed replay paths."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import sys
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.compiled_policy import (  # noqa: E402
    CompiledAutonomousInstructionBody,
)
from arc3_agi_agent.generic_compute import GenericComputeSubject  # noqa: E402
from arc3_agi_agent.generic_hds import (  # noqa: E402
    GenericHDSJudgementSubject,
)
from arc3_agi_agent.generic_memory import SemanticMemory  # noqa: E402
from arc3_agi_agent.generic_package import (  # noqa: E402
    GENERIC_PACKAGE_FORBIDDEN_NAMES,
    GENERIC_RUNTIME_MODULES,
)
from arc3_agi_agent.generic_runtime import GenericAGIRuntime  # noqa: E402
from arc3_agi_agent.generic_types import GenericObservation  # noqa: E402
from arc3_agi_agent.identity_boundary import (  # noqa: E402
    IdentityBoundary,
    OrchestrationMetadata,
    Tainted,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import create_product_session  # noqa: E402

OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m3_p03_identity_replay_audit.json")
BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
MAPPING_PATH: Final = Path("analysis/product/rev5_1/full_mapping_closure.json")
SHUFFLE_PLAN_PATH: Final = Path("analysis/product/rev5_1/m2_shuffle_order_plan.json")
M2_CLOSURE_PATH: Final = Path(
    "analysis/product/rev5_1/m2_full_sample_product_closure.json"
)
SELECTOR_PATH: Final = Path("control/rev5_1/CURRENT_TASK.json")
AGENT_PATH: Final = Path("ARC-AGI-3-Agents/agents/templates/generic_agi_agent.py")
RUNNER_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/generic_competition_runner.py"
)
IDENTITY_BOUNDARY_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/identity_boundary.py"
)
DECISION_MODULE_PATHS: Final = (
    Path("ARC-AGI-3-Agents/arc3_agi_agent/compiled_policy.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_compute.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_hds.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_memory.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_runtime.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/local_capability.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/p_ir_interpreter.py"),
)
FORBIDDEN_DECISION_NAMES: Final = frozenset(
    {
        "action_index",
        "answer_map",
        "exact_frame_hash",
        "fixed_action_sequence",
        "frame_hash",
        "game_id",
        "game_index",
        "level_id",
        "recording_id",
        "replay_index",
        "source_state",
        "successful_action_sequence",
        "task_id",
        "trajectory_id",
    }
)
FORBIDDEN_SERIALIZED_TERMS: Final = tuple(
    sorted(
        {
            *FORBIDDEN_DECISION_NAMES,
            "answer_lookup",
            "literal_coordinate_table",
            "replay_actions",
            "trajectory_actions",
        }
    )
)
SEQUENCE_TARGET_TERMS: Final = (
    "answer",
    "fixed_action",
    "frame_hash",
    "replay",
    "successful_action",
    "trajectory",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _load_object(root: Path, relative: Path) -> tuple[dict[str, object], str]:
    payload = (root / relative).read_bytes()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"M3_P03_OBJECT_REQUIRED:{relative.as_posix()}")
    return value, _sha256(payload)


def scan_serialized(
    value: object,
    *,
    path: str = "$",
) -> tuple[list[str], list[str]]:
    """Return forbidden paths and all lower-cased strings."""

    findings: list[str] = []
    strings: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.casefold()
            if any(term in lowered for term in FORBIDDEN_SERIALIZED_TERMS):
                findings.append(f"{path}.{key}")
            child_findings, child_strings = scan_serialized(
                item,
                path=f"{path}.{key}",
            )
            findings.extend(child_findings)
            strings.extend(child_strings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_findings, child_strings = scan_serialized(
                item,
                path=f"{path}[{index}]",
            )
            findings.extend(child_findings)
            strings.extend(child_strings)
    elif isinstance(value, str):
        lowered = value.casefold()
        strings.append(lowered)
        if any(term in lowered for term in FORBIDDEN_SERIALIZED_TERMS):
            findings.append(path)
    return sorted(set(findings)), strings


def _target_names(node: ast.expr) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(name for item in node.elts for name in _target_names(item))
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    return ()


def scan_source_text(source: str, *, label: str) -> list[str]:
    """Trace forbidden data access and named replay/answer sequence storage."""

    tree = ast.parse(source, filename=label)
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            )
            for argument in arguments:
                if argument.arg.casefold() in FORBIDDEN_DECISION_NAMES:
                    findings.append(f"{label}:{node.lineno}:argument:{argument.arg}")
        elif isinstance(node, ast.Attribute):
            if node.attr.casefold() in FORBIDDEN_DECISION_NAMES:
                findings.append(f"{label}:{node.lineno}:attribute:{node.attr}")
        elif isinstance(node, ast.Subscript):
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if key.value.casefold() in FORBIDDEN_DECISION_NAMES:
                    findings.append(f"{label}:{node.lineno}:subscript:{key.value}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and node.args:
                key = node.args[0]
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if key.value.casefold() in FORBIDDEN_DECISION_NAMES:
                        findings.append(f"{label}:{node.lineno}:get:{key.value}")
        elif isinstance(node, ast.Assign):
            names = tuple(
                name for target in node.targets for name in _target_names(target)
            )
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Dict)):
                for name in names:
                    if any(term in name.casefold() for term in SEQUENCE_TARGET_TERMS):
                        findings.append(f"{label}:{node.lineno}:sequence:{name}")
        elif isinstance(node, ast.AnnAssign):
            names = _target_names(node.target)
            if isinstance(node.value, (ast.List, ast.Tuple, ast.Dict)):
                for name in names:
                    if any(term in name.casefold() for term in SEQUENCE_TARGET_TERMS):
                        findings.append(f"{label}:{node.lineno}:sequence:{name}")
    return sorted(set(findings))


def _runtime_call_audit(source: str) -> dict[str, object]:
    tree = ast.parse(source, filename=AGENT_PATH.as_posix())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "GenericAGIRuntime")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "GenericAGIRuntime"
            )
        )
    ]
    _require(len(calls) == 1, "M3_P03_RUNTIME_CALL_COUNT")
    call = calls[0]
    keyword_names = sorted(
        keyword.arg for keyword in call.keywords if keyword.arg is not None
    )
    expected = sorted(
        {
            "environment",
            "episode_handle",
            "retain_cycle_objects",
            "session",
            "trace_sink",
        }
    )
    _require(not call.args, "M3_P03_RUNTIME_POSITIONAL_INPUT")
    _require(keyword_names == expected, "M3_P03_RUNTIME_CALL_INPUT_DRIFT")
    return {
        "GenericAGIRuntime_call_count": 1,
        "positional_input_count": 0,
        "keyword_inputs": keyword_names,
        "identity_keyword_count": 0,
    }


def _permission_stub_audit(source: str) -> dict[str, bool]:
    tree = ast.parse(source, filename=AGENT_PATH.as_posix())
    results: dict[str, bool] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "GenericAGIAgent":
            continue
        for method in node.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            if method.name not in {"choose_action", "take_action"}:
                continue
            results[method.name] = any(
                isinstance(item, ast.Raise)
                and isinstance(item.exc, ast.Call)
                and isinstance(item.exc.func, ast.Name)
                and item.exc.func.id == "PermissionError"
                for item in ast.walk(method)
            )
    _require(
        results == {"choose_action": True, "take_action": True},
        "M3_P03_DIRECT_ACTION_STUB_DRIFT",
    )
    return results


def _interface_names(callable_object: Callable[..., object]) -> list[str]:
    return [
        name
        for name in inspect.signature(callable_object).parameters
        if name not in {"self", "cls"}
    ]


def _interface_audit() -> dict[str, object]:
    initial = load_product_initial_state()
    interfaces = {
        "create_product_session": _interface_names(create_product_session),
        "C_compute": _interface_names(GenericComputeSubject.compute),
        "J_frame": _interface_names(GenericHDSJudgementSubject.frame),
        "J_judge": _interface_names(GenericHDSJudgementSubject.judge),
        "M_query": _interface_names(SemanticMemory.query),
        "P_query": _interface_names(CompiledAutonomousInstructionBody.query),
    }
    dataclass_fields = {
        "GenericAGIRuntime": [item.name for item in fields(GenericAGIRuntime)],
        "GenericObservation": [item.name for item in fields(GenericObservation)],
        "J0": [item.name for item in fields(initial.j0)],
    }
    all_names = tuple(
        name
        for values in (*interfaces.values(), *dataclass_fields.values())
        for name in values
    )
    forbidden = sorted(
        name for name in all_names if name.casefold() in FORBIDDEN_DECISION_NAMES
    )
    _require(not forbidden, "M3_P03_INTERFACE_IDENTITY_TAINT")
    return {
        "interfaces": interfaces,
        "dataclass_fields": dataclass_fields,
        "forbidden_interface_name_count": len(forbidden),
        "active_P_type": type(initial.p_bundle.body).__name__,
        "M0_record_count": len(initial.m0),
    }


def _identity_boundary_audit() -> dict[str, object]:
    boundary = IdentityBoundary()
    metadata = OrchestrationMetadata(
        scorecard_id=Tainted("scorecard-only"),
        game_id=Tainted("game-only"),
        game_index=Tainted(7),
        environment_handle=Tainted(object()),
    )
    probes = {
        "typed_orchestration_metadata": metadata,
        "mapping_game_id": {"game_id": "game-only"},
        "mapping_level_id": {"level_id": "level-only"},
        "mapping_recording_id": {"recording_id": "recording-only"},
        "mapping_trajectory_id": {"trajectory_id": "trajectory-only"},
        "mapping_exact_frame_hash": {"exact_frame_hash": "hash-only"},
        "mapping_successful_action_sequence": {"successful_action_sequence": [1, 2, 3]},
        "mapping_action_index": {"action_index": 7},
        "mapping_fixed_action_sequence": {"fixed_action_sequence": [1, 2, 3]},
    }
    witnesses: dict[str, str] = {}
    for name, value in probes.items():
        try:
            boundary.require_decision_context(value)
        except PermissionError as error:
            witnesses[name] = str(error).split(":", 1)[0]
    _require(len(witnesses) == len(probes), "M3_P03_BOUNDARY_REJECTION_MISSING")
    clean = GenericObservation(
        signature="m3-p03-clean-observation",
        available_actions=(1, 2),
        rendered_layers=(((0, 1), (1, 0)),),
        terminal_state="NOT_FINISHED",
    )
    _require(
        boundary.inspect_decision_context(clean) == (),
        "M3_P03_CLEAN_OBSERVATION_REJECTED",
    )
    return {
        "probe_count": len(probes),
        "rejected_probe_count": len(witnesses),
        "rejection_witnesses": witnesses,
        "clean_GenericObservation_accepted": True,
    }


def _count_quarantined_text(value: object) -> int:
    if isinstance(value, dict):
        return sum(_count_quarantined_text(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_quarantined_text(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return int(any(term in lowered for term in ("replay", "trajectory")))
    return 0


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    bundle, bundle_sha = _load_object(root, BUNDLE_PATH)
    mapping, mapping_sha = _load_object(root, MAPPING_PATH)
    plan, plan_sha = _load_object(root, SHUFFLE_PLAN_PATH)
    m2_closure, m2_sha = _load_object(root, M2_CLOSURE_PATH)
    selector, _ = _load_object(root, SELECTOR_PATH)
    identity_boundary_payload = (root / IDENTITY_BOUNDARY_PATH).read_bytes()
    official_order = plan.get("official_order")
    if not isinstance(official_order, list) or not all(
        isinstance(item, str) for item in official_order
    ):
        raise TypeError("M3_P03_OFFICIAL_ID_SET_INVALID")

    bundle_findings, bundle_strings = scan_serialized(bundle)
    literal_game_ids = sorted(
        game_id
        for game_id in official_order
        if any(game_id.casefold() in text for text in bundle_strings)
    )
    _require(not bundle_findings, "M3_P03_ACTIVE_BUNDLE_FORBIDDEN_PATH")
    _require(not literal_game_ids, "M3_P03_ACTIVE_BUNDLE_GAME_LITERAL")

    source_findings: list[str] = []
    source_bindings: list[dict[str, object]] = []
    for relative in DECISION_MODULE_PATHS:
        payload = (root / relative).read_bytes()
        source = payload.decode("utf-8")
        source_findings.extend(scan_source_text(source, label=relative.as_posix()))
        for game_id in official_order:
            if game_id.casefold() in source.casefold():
                source_findings.append(
                    f"{relative.as_posix()}:literal-game-id:{game_id}"
                )
        source_bindings.append(
            {"path": relative.as_posix(), "sha256": _sha256(payload)}
        )
    source_findings = sorted(set(source_findings))
    _require(not source_findings, "M3_P03_DECISION_SOURCE_FINDING")

    agent_source = (root / AGENT_PATH).read_text(encoding="utf-8")
    runner_source = (root / RUNNER_PATH).read_text(encoding="utf-8")
    runtime_call = _runtime_call_audit(agent_source)
    direct_action_stubs = _permission_stub_audit(agent_source)
    _require(
        agent_source.count("self.game_id") == 1 and "logger.info" in agent_source,
        "M3_P03_AGENT_GAME_ID_USE_DRIFT",
    )
    _require(
        "game_id=Tainted(game_id)" in runner_source
        and "del orchestration_metadata" in runner_source,
        "M3_P03_ORCHESTRATION_TAINT_WRAPPER_MISSING",
    )

    residues = mapping.get("domain_local_residue_registry")
    if not isinstance(residues, list):
        raise TypeError("M3_P03_RESIDUE_REGISTRY_INVALID")
    residue_selector_findings = [
        str(item.get("residue_id", "UNKNOWN"))
        for item in residues
        if not isinstance(item, dict)
        or item.get("runtime_selector") != "NONE"
        or item.get("runtime_execute_eligibility") is not False
    ]
    _require(not residue_selector_findings, "M3_P03_RESIDUE_RUNTIME_PATH")
    _require(
        mapping.get("development_only_mapping") is True
        and mapping.get("runtime_use") == "FORBIDDEN_AS_ACTION_SELECTOR_OR_TRAJECTORY",
        "M3_P03_MAPPING_BOUNDARY_INVALID",
    )

    endpoint = selector.get("endpoint")
    if not isinstance(endpoint, dict):
        raise TypeError("M3_P03_SELECTOR_ENDPOINT_INVALID")
    _require(
        endpoint.get("identity_action_router_allowed") is False
        and endpoint.get("fixed_trajectory_playback_allowed") is False,
        "M3_P03_SELECTOR_BOUNDARY_INVALID",
    )
    packaged_names = tuple(name.casefold() for name in GENERIC_RUNTIME_MODULES)
    package_scope_findings = sorted(
        name
        for name in packaged_names
        if any(
            term in name
            for term in (
                "analysis",
                "control/",
                "current_task",
                "environment_files",
                "recording",
                "selector",
                "teacher",
            )
        )
    )
    _require(not package_scope_findings, "M3_P03_PACKAGE_SCOPE_FINDING")
    _require(
        all(
            forbidden not in name
            for name in packaged_names
            for forbidden in GENERIC_PACKAGE_FORBIDDEN_NAMES
        ),
        "M3_P03_PACKAGE_FORBIDDEN_NAME",
    )
    preliminary = m2_closure.get("identity_replay_preliminary_audit")
    if not isinstance(preliminary, dict):
        raise TypeError("M3_P03_M2_PRELIMINARY_AUDIT_INVALID")
    _require(
        m2_closure.get("status") == "M2_COMPLETE"
        and preliminary.get("identity_action_router_finding_count") == 0,
        "M3_P03_M2_PRELIMINARY_AUDIT_INVALID",
    )

    interfaces = _interface_audit()
    boundary = _identity_boundary_audit()
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-p03-identity-replay-audit-v1",
        "artifact_type": "IdentityReplayAuditEvidence",
        "point_id": "M3-P03_IDENTITY_REPLAY_AUDIT",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_P03_PASS",
        "evidence_bindings": {
            "active_product_bundle": {
                "path": BUNDLE_PATH.as_posix(),
                "sha256": bundle_sha,
            },
            "full_mapping_closure": {
                "path": MAPPING_PATH.as_posix(),
                "sha256": mapping_sha,
            },
            "shuffle_plan": {
                "path": SHUFFLE_PLAN_PATH.as_posix(),
                "sha256": plan_sha,
            },
            "m2_full_sample_closure": {
                "path": M2_CLOSURE_PATH.as_posix(),
                "sha256": m2_sha,
            },
            "identity_boundary": {
                "path": IDENTITY_BOUNDARY_PATH.as_posix(),
                "sha256": _sha256(identity_boundary_payload),
            },
            "decision_modules": source_bindings,
        },
        "active_bundle_audit": {
            "serialized_P_J0_M0_scanned": True,
            "forbidden_path_count": len(bundle_findings),
            "official_game_literal_count": len(literal_game_ids),
            "M0_record_count": interfaces["M0_record_count"],
        },
        "decision_source_audit": {
            "module_count": len(DECISION_MODULE_PATHS),
            "identity_data_access_finding_count": len(source_findings),
            "named_replay_or_answer_sequence_finding_count": 0,
            "exact_frame_hash_route_finding_count": 0,
            "official_game_literal_count": 0,
        },
        "interface_taint_audit": interfaces,
        "orchestration_boundary_audit": {
            "game_identity_wrapped_as_Tainted": True,
            "orchestration_metadata_deleted_before_agent_construction": True,
            "agent_game_id_use": "LOGGING_ONLY",
            "runtime_call": runtime_call,
            "direct_action_stubs": direct_action_stubs,
            "identity_boundary": boundary,
        },
        "domain_local_residue_audit": {
            "residue_count": len(residues),
            "runtime_selector_count": len(residue_selector_findings),
            "runtime_execute_eligible_count": len(residue_selector_findings),
            "quarantined_development_replay_or_trajectory_text_count": (
                _count_quarantined_text(residues)
            ),
            "quarantined_text_is_runtime_finding": False,
        },
        "selector_and_package_audit": {
            "selector_classification": "GOVERNANCE_ONLY",
            "analysis_classification": "DEVELOPMENT_EVIDENCE_ONLY",
            "runtime_module_count": len(GENERIC_RUNTIME_MODULES),
            "selector_or_analysis_runtime_member_count": len(package_scope_findings),
        },
        "finding_summary": {
            "runtime_decision_identity_taint_finding_count": len(source_findings),
            "active_bundle_forbidden_path_count": len(bundle_findings),
            "active_bundle_official_game_literal_count": len(literal_game_ids),
            "domain_local_residue_runtime_selector_count": len(
                residue_selector_findings
            ),
            "identity_action_router_finding_count": 0,
            "fixed_trajectory_playback_finding_count": 0,
        },
        "exit_audit": {
            "runtime_decision_identity_taint_finding_count": 0,
            "active_bundle_forbidden_path_count": 0,
            "active_bundle_official_game_literal_count": 0,
            "domain_local_residue_runtime_selector_count": 0,
            "orchestration_identity_boundary_rejection": True,
            "identity_action_router_finding_count": 0,
            "fixed_trajectory_playback_finding_count": 0,
            "active_development_product_bundle_count": 1,
            "runtime_policy_changed": False,
            "status": "M3_P03_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M3_P03_IDENTITY_REPLAY_AUDIT_ONLY",
            "M3_complete": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P04_APPLICABILITY_COUNTERFACTUAL",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "output": OUTPUT_PATH.as_posix(),
                "point_status": report["status"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
