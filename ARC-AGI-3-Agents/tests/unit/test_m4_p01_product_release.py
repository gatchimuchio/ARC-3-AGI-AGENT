from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from arc3_agi_agent.local_capability import RELATION_BOUND_ACTION_FAMILY
from arc3_agi_agent.product_release import (
    PRODUCT_RELEASE_BUNDLE_ID,
    PRODUCT_RELEASE_STAGE,
    compile_product_release_bundle,
    load_product_release_bundle_payloads,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_DESCRIPTOR = (
    REPOSITORY_ROOT
    / "ARC-AGI-3-Agents"
    / "arc3_agi_agent"
    / "bundles"
    / "arc3_product_initial_state_v1.json"
)
ACTIVE_PACKAGE = ACTIVE_DESCRIPTOR.with_name("arc3_product_initial_state_v1.zip")
M3_CLOSURE = (
    REPOSITORY_ROOT
    / "analysis"
    / "product"
    / "rev5_1"
    / "m3_conformance_closure.json"
)
P05_CANDIDATE = M3_CLOSURE.with_name(
    "m3_p05_next_initial_state_candidate.zip"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _compile() -> tuple[dict[str, object], bytes]:
    active_descriptor = ACTIVE_DESCRIPTOR.read_bytes()
    active_package = ACTIVE_PACKAGE.read_bytes()
    closure_payload = M3_CLOSURE.read_bytes()
    closure = json.loads(closure_payload)
    return compile_product_release_bundle(
        initial_state_descriptor_payload=active_descriptor,
        initial_state_package_payload=active_package,
        active_descriptor_sha256=_sha256(active_descriptor),
        active_package_sha256=_sha256(active_package),
        m3_closure_sha256=_sha256(closure_payload),
        m3_closure_logical_sha256=closure["logical_content_sha256"],
        excluded_candidate_sha256=_sha256(P05_CANDIDATE.read_bytes()),
    )


def _descriptor_payload(descriptor: dict[str, object]) -> bytes:
    return (
        json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def test_release_bundle_is_deterministic_and_runtime_loadable() -> None:
    descriptor_a, package_a = _compile()
    descriptor_b, package_b = _compile()

    assert descriptor_a == descriptor_b
    assert package_a == package_b
    loaded = load_product_release_bundle_payloads(
        descriptor_payload=_descriptor_payload(descriptor_a),
        package_payload=package_a,
    )
    assert loaded.descriptor["product_bundle_id"] == PRODUCT_RELEASE_BUNDLE_ID
    assert loaded.descriptor["asset_stage"] == PRODUCT_RELEASE_STAGE
    assert loaded.descriptor["release_product_bundle_count"] == 1
    assert loaded.descriptor["included_non_release_asset_count"] == 0
    assert loaded.descriptor["identity_replay_finding_count"] == 0
    assert loaded.initial_state.package_bytes() == ACTIVE_PACKAGE.read_bytes()
    assert loaded.mechanism_family_registry["family_count"] == 1
    families = loaded.mechanism_family_registry["families"]
    assert isinstance(families, list)
    assert families[0]["asset_state"] == PRODUCT_RELEASE_STAGE
    assert loaded.provenance["excluded_assets"][0]["included"] is False


def test_release_loader_rejects_descriptor_tampering() -> None:
    descriptor, package_payload = _compile()
    descriptor["release_product_bundle_count"] = 2

    with pytest.raises(ValueError, match="RELEASE_DESCRIPTOR_INVALID_DIGEST_MISMATCH"):
        load_product_release_bundle_payloads(
            descriptor_payload=_descriptor_payload(descriptor),
            package_payload=package_payload,
        )


def test_release_compiler_rejects_non_active_mechanism_family() -> None:
    active_descriptor = ACTIVE_DESCRIPTOR.read_bytes()
    active_package = ACTIVE_PACKAGE.read_bytes()
    closure_payload = M3_CLOSURE.read_bytes()
    closure = json.loads(closure_payload)
    probation = replace(
        RELATION_BOUND_ACTION_FAMILY,
        asset_state="PROBATION_DEV",
    )

    with pytest.raises(ValueError, match="GENERIC_MECHANISM_FAMILY_ID_OR_STATE_INVALID"):
        compile_product_release_bundle(
            initial_state_descriptor_payload=active_descriptor,
            initial_state_package_payload=active_package,
            active_descriptor_sha256=_sha256(active_descriptor),
            active_package_sha256=_sha256(active_package),
            m3_closure_sha256=_sha256(closure_payload),
            m3_closure_logical_sha256=closure["logical_content_sha256"],
            excluded_candidate_sha256=_sha256(P05_CANDIDATE.read_bytes()),
            mechanism_families=(probation,),
        )
