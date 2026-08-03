#!/usr/bin/env python3
"""Compile and audit the rev5.1 M4-P01 RELEASE_FROZEN product bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.product_release import (  # noqa: E402
    PRODUCT_RELEASE_BUNDLE_ID,
    PRODUCT_RELEASE_DESCRIPTOR_FILENAME,
    PRODUCT_RELEASE_PACKAGE_FILENAME,
    PRODUCT_RELEASE_STAGE,
    compile_product_release_bundle,
    load_product_release_bundle_payloads,
)

M3_CLOSURE_PATH: Final = Path(
    "analysis/product/rev5_1/m3_conformance_closure.json"
)
ACTIVE_DESCRIPTOR_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
ACTIVE_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.zip"
)
P05_CANDIDATE_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p05_next_initial_state_candidate.zip"
)
RELEASE_DIRECTORY: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles"
)
RELEASE_DESCRIPTOR_PATH: Final = (
    RELEASE_DIRECTORY / PRODUCT_RELEASE_DESCRIPTOR_FILENAME
)
RELEASE_PACKAGE_PATH: Final = RELEASE_DIRECTORY / PRODUCT_RELEASE_PACKAGE_FILENAME
REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p01_release_bundle_compilation.json"
)
IMPLEMENTATION_PATHS: Final = (
    Path("ARC-AGI-3-Agents/arc3_agi_agent/product_capability.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/product_release.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/local_capability.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/initial_state_compiler.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/canonical_artifact.py"),
    Path("scripts/build_rev5_1_m4_p01_release_bundle.py"),
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


def _load_object(path: Path, error: str) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}, payload


def _verify_logical_seal(value: dict[str, object]) -> str:
    body = dict(value)
    claimed = body.pop("logical_content_sha256", None)
    actual = _sha256(_canonical_json(body))
    _require(claimed == actual, "M4_P01_M3_CLOSURE_LOGICAL_SEAL_INVALID")
    return actual


def _source_bindings(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.as_posix(),
            "sha256": _sha256((root / path).read_bytes()),
        }
        for path in IMPLEMENTATION_PATHS
    ]


def build_artifacts(
    root: Path = REPOSITORY_ROOT,
) -> tuple[bytes, bytes, bytes]:
    closure, closure_payload = _load_object(
        root / M3_CLOSURE_PATH,
        "M4_P01_M3_CLOSURE_OBJECT_REQUIRED",
    )
    closure_logical_sha = _verify_logical_seal(closure)
    exit_audit = closure.get("exit_audit")
    claim_boundary = closure.get("claim_boundary")
    if not isinstance(exit_audit, dict) or not isinstance(claim_boundary, dict):
        raise TypeError("M4_P01_M3_CLOSURE_SECTIONS_REQUIRED")
    _require(
        closure.get("status") == "M3_COMPLETE"
        and closure.get("point_id") == "M3-P06_CONFORMANCE_FULL_REGRESSION"
        and closure.get("asset_stage") == "ACTIVE_DEV"
        and exit_audit.get("fresh_official_sample_game_WIN_count") == 25
        and exit_audit.get("fresh_official_sample_level_completion_count") == 183
        and exit_audit.get("fresh_failure_count") == 0
        and exit_audit.get("fresh_lifecycle_failure_count") == 0
        and exit_audit.get("fresh_runtime_failure_signature_count") == 0
        and exit_audit.get("P05_candidate_activation_count") == 0
        and claim_boundary.get("M3_complete") is True
        and claim_boundary.get("product_release_frozen") is False,
        "M4_P01_M3_CLOSURE_GATE_FAILED",
    )
    active_descriptor_payload = (root / ACTIVE_DESCRIPTOR_PATH).read_bytes()
    active_package_payload = (root / ACTIVE_PACKAGE_PATH).read_bytes()
    candidate_payload = (root / P05_CANDIDATE_PATH).read_bytes()
    descriptor, package_payload = compile_product_release_bundle(
        initial_state_descriptor_payload=active_descriptor_payload,
        initial_state_package_payload=active_package_payload,
        active_descriptor_sha256=_sha256(active_descriptor_payload),
        active_package_sha256=_sha256(active_package_payload),
        m3_closure_sha256=_sha256(closure_payload),
        m3_closure_logical_sha256=closure_logical_sha,
        excluded_candidate_sha256=_sha256(candidate_payload),
    )
    second_descriptor, second_package_payload = compile_product_release_bundle(
        initial_state_descriptor_payload=active_descriptor_payload,
        initial_state_package_payload=active_package_payload,
        active_descriptor_sha256=_sha256(active_descriptor_payload),
        active_package_sha256=_sha256(active_package_payload),
        m3_closure_sha256=_sha256(closure_payload),
        m3_closure_logical_sha256=closure_logical_sha,
        excluded_candidate_sha256=_sha256(candidate_payload),
    )
    _require(
        descriptor == second_descriptor
        and package_payload == second_package_payload,
        "M4_P01_RELEASE_REBUILD_NOT_BYTE_IDENTICAL",
    )
    descriptor_payload = _encoded(descriptor)
    loaded = load_product_release_bundle_payloads(
        descriptor_payload=descriptor_payload,
        package_payload=package_payload,
    )
    mechanism_registry = loaded.mechanism_family_registry
    families = mechanism_registry.get("families")
    if not isinstance(families, list):
        raise TypeError("M4_P01_RELEASE_FAMILY_LIST_REQUIRED")
    _require(
        loaded.descriptor.get("product_bundle_id") == PRODUCT_RELEASE_BUNDLE_ID
        and loaded.descriptor.get("asset_stage") == PRODUCT_RELEASE_STAGE
        and loaded.descriptor.get("release_product_bundle_count") == 1
        and loaded.descriptor.get("included_non_release_asset_count") == 0
        and loaded.descriptor.get("identity_replay_finding_count") == 0
        and loaded.provenance.get("included_non_release_asset_count") == 0
        and loaded.provenance.get("identity_replay_finding_count") == 0
        and mechanism_registry.get("family_count") == 1
        and all(
            isinstance(family, dict)
            and family.get("asset_state") == PRODUCT_RELEASE_STAGE
            and family.get("execute_eligibility") is False
            for family in families
        )
        and loaded.initial_state.package_bytes() == active_package_payload,
        "M4_P01_RELEASE_LOAD_AUDIT_FAILED",
    )
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p01-release-compilation-v1",
        "artifact_type": "M4ReleaseBundleCompilationEvidence",
        "point_id": "M4-P01_RELEASE_BUNDLE_COMPILATION",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": PRODUCT_RELEASE_STAGE,
        "status": "M4_P01_PASS",
        "source_bindings": {
            "M3_closure": {
                "path": M3_CLOSURE_PATH.as_posix(),
                "sha256": _sha256(closure_payload),
                "logical_content_sha256": closure_logical_sha,
                "status": closure["status"],
            },
            "active_product_descriptor": {
                "path": ACTIVE_DESCRIPTOR_PATH.as_posix(),
                "sha256": _sha256(active_descriptor_payload),
            },
            "active_product_package": {
                "path": ACTIVE_PACKAGE_PATH.as_posix(),
                "sha256": _sha256(active_package_payload),
            },
            "excluded_P05_candidate": {
                "path": P05_CANDIDATE_PATH.as_posix(),
                "sha256": _sha256(candidate_payload),
                "included": False,
            },
            "implementation": _source_bindings(root),
        },
        "release_artifact": {
            "descriptor_path": RELEASE_DESCRIPTOR_PATH.as_posix(),
            "descriptor_sha256": _sha256(descriptor_payload),
            "package_path": RELEASE_PACKAGE_PATH.as_posix(),
            "package_sha256": _sha256(package_payload),
            "package_size_bytes": len(package_payload),
            "product_bundle_id": PRODUCT_RELEASE_BUNDLE_ID,
            "manifest_logical_digest": loaded.logical_digest,
            "initial_state_logical_digest": loaded.initial_state.logical_digest,
            "p_logical_digest": loaded.initial_state.p_bundle.logical_digest(),
            "j0_digest": loaded.descriptor["j0_digest"],
            "m0_digest": loaded.descriptor["m0_digest"],
        },
        "compilation_audit": {
            "source_stage": "ACTIVE_DEV",
            "release_stage": PRODUCT_RELEASE_STAGE,
            "release_product_bundle_count": 1,
            "release_mechanism_family_count": len(families),
            "initial_state_recompilation": "BYTE_IDENTICAL",
            "deterministic_archive_rebuild": "BYTE_IDENTICAL",
            "release_bundle_load": "PASS",
            "P_J0_M0_functional_identity_preserved": True,
            "included_non_release_asset_count": 0,
            "identity_replay_finding_count": 0,
            "P05_candidate_included": False,
            "runtime_policy_changed": False,
        },
        "exit_audit": {
            "M3_closure": "PASS",
            "release_product_bundle_count": 1,
            "release_asset_stage": PRODUCT_RELEASE_STAGE,
            "included_non_release_asset_count": 0,
            "identity_replay_finding_count": 0,
            "deterministic_archive_rebuild": "BYTE_IDENTICAL",
            "release_bundle_load": "PASS",
            "status": "M4_P01_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M4_P01_RELEASE_BUNDLE_COMPILED",
            "release_bundle_compiled": True,
            "code_dependency_resource_freeze_complete": False,
            "clean_install_complete": False,
            "clean_full_sample_repeat_complete": False,
            "ARC3_PRODUCT_COMPLETE": False,
            "next_point": "M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return descriptor_payload, package_payload, _encoded(report)


def _write(root: Path, payloads: tuple[bytes, bytes, bytes]) -> None:
    descriptor_payload, package_payload, report_payload = payloads
    for relative, payload in (
        (RELEASE_DESCRIPTOR_PATH, descriptor_payload),
        (RELEASE_PACKAGE_PATH, package_payload),
        (REPORT_PATH, report_payload),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _check(root: Path, payloads: tuple[bytes, bytes, bytes]) -> None:
    for relative, expected in zip(
        (RELEASE_DESCRIPTOR_PATH, RELEASE_PACKAGE_PATH, REPORT_PATH),
        payloads,
        strict=True,
    ):
        actual = (root / relative).read_bytes()
        _require(actual == expected, "M4_P01_ARTIFACT_STALE:" + relative.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    payloads = build_artifacts(root)
    if arguments.write:
        _write(root, payloads)
        status = "WRITTEN"
    else:
        _check(root, payloads)
        status = "PASS"
    print(
        json.dumps(
            {
                "descriptor": RELEASE_DESCRIPTOR_PATH.as_posix(),
                "package": RELEASE_PACKAGE_PATH.as_posix(),
                "report": REPORT_PATH.as_posix(),
                "point_status": "M4_P01_PASS",
                "status": status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
