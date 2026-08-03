"""Deterministic RELEASE_FROZEN packaging for ARC3CompletionAgent."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from .canonical_artifact import build_canonical_zip, canonical_json_bytes
from .initial_state_compiler import InitialStateBundle
from .local_capability import (
    ACTIVE_DEV_CAPABILITY_STAGE,
    GENERIC_MECHANISM_FAMILY_VERSION,
    GenericMechanismFamily,
    active_dev_mechanism_families,
)
from .p_ir_abi import (
    L0_ABI_VERSION,
    PIR_SEMANTICS_DIGEST,
    PIR_SEMANTICS_VERSION,
)
from .p_ir_types import (
    PIR_EXTERNAL_INPUT_TYPES,
    PIR_GRAPH_KINDS,
    PIR_OPCODE_SPECS,
    PIR_OPCODE_VERSION,
    PIR_SCHEMA_VERSION,
    PIR_TYPE_VERSION,
    PIR_VALUE_TYPES,
)
from .product_capability import (
    PRODUCT_CAPABILITY_ADAPTER_DIGEST,
    PRODUCT_CAPABILITY_PROGRAM_ID,
    load_product_initial_state_payloads,
)
from .product_governance import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
    ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)
from .schema import digest_object

PRODUCT_RELEASE_SCHEMA_VERSION: Final = "arc3-product-release-v1"
PRODUCT_RELEASE_BUNDLE_ID: Final = "ARC3ProductBundle-release-v1"
PRODUCT_RELEASE_STAGE: Final = "RELEASE_FROZEN"
PRODUCT_RELEASE_DESCRIPTOR_FILENAME: Final = "arc3_product_release_v1.json"
PRODUCT_RELEASE_PACKAGE_FILENAME: Final = "arc3_product_release_v1.zip"

_INITIAL_DESCRIPTOR_MEMBER: Final = "initial_state/descriptor.json"
_INITIAL_PACKAGE_MEMBER: Final = "initial_state/package.zip"
_PROVENANCE_MEMBER: Final = "provenance/release_provenance.json"
_TYPE_OPERATOR_REGISTRY_MEMBER: Final = "registries/type_operator_registry.json"
_MECHANISM_REGISTRY_MEMBER: Final = "registries/mechanism_family_registry.json"
_PLANNER_CONFIG_MEMBER: Final = "config/planner.json"
_RESOURCE_CONTRACT_MEMBER: Final = "config/resource_contract.json"
_ADAPTER_CONFIG_MEMBER: Final = "config/official_adapter.json"
_MANIFEST_MEMBER: Final = "release_manifest.json"

_PAYLOAD_MEMBERS: Final = (
    _ADAPTER_CONFIG_MEMBER,
    _INITIAL_DESCRIPTOR_MEMBER,
    _INITIAL_PACKAGE_MEMBER,
    _MECHANISM_REGISTRY_MEMBER,
    _PLANNER_CONFIG_MEMBER,
    _PROVENANCE_MEMBER,
    _RESOURCE_CONTRACT_MEMBER,
    _TYPE_OPERATOR_REGISTRY_MEMBER,
)
_ALL_MEMBERS: Final = frozenset((*_PAYLOAD_MEMBERS, _MANIFEST_MEMBER))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(value: str, error: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(error)
    return value


def _content_bound(
    namespace: str,
    body: Mapping[str, object],
) -> dict[str, object]:
    output = dict(body)
    output["content_digest"] = namespace + ":" + digest_object(output)
    return output


def _verify_content_bound(
    value: object,
    *,
    namespace: str,
    error: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(error)
    output = {str(key): item for key, item in value.items()}
    expected = output.pop("content_digest", None)
    actual = namespace + ":" + digest_object(output)
    if expected != actual:
        raise ValueError(error + "_DIGEST_MISMATCH")
    output["content_digest"] = expected
    return output


def _json_member(value: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(value)


def _selected_program_opcodes(initial_state: InitialStateBundle) -> tuple[str, ...]:
    program = initial_state.p_bundle.program
    return tuple(
        sorted(
            {
                node.opcode
                for graph in (
                    program.representation_graph,
                    program.model_graph,
                    program.candidate_graph,
                )
                for node in graph.nodes
            }
        )
    )


def _type_operator_registry(
    initial_state: InitialStateBundle,
) -> dict[str, object]:
    opcodes = tuple(
        {
            "opcode": spec.opcode,
            "graph_kind": spec.graph_kind,
            "input_signatures": spec.input_signatures,
            "output_types": spec.output_types,
            "base_cost": spec.base_cost,
        }
        for _, spec in sorted(PIR_OPCODE_SPECS.items())
    )
    return _content_bound(
        "release-type-operator-registry",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "p_ir_schema_version": PIR_SCHEMA_VERSION,
            "l0_abi_version": L0_ABI_VERSION,
            "type_version": PIR_TYPE_VERSION,
            "opcode_version": PIR_OPCODE_VERSION,
            "semantics_version": PIR_SEMANTICS_VERSION,
            "semantics_digest": PIR_SEMANTICS_DIGEST,
            "graph_kinds": tuple(sorted(PIR_GRAPH_KINDS)),
            "value_types": tuple(sorted(PIR_VALUE_TYPES)),
            "external_input_types": tuple(sorted(PIR_EXTERNAL_INPUT_TYPES.items())),
            "operators": opcodes,
            "selected_program_id": initial_state.p_bundle.program.program_id,
            "selected_program_opcodes": _selected_program_opcodes(initial_state),
        },
    )


def _release_family_projection(
    family: GenericMechanismFamily,
) -> dict[str, object]:
    failures = family.validate()
    if failures:
        raise ValueError(";".join(failures))
    if family.asset_state != ACTIVE_DEV_CAPABILITY_STAGE:
        raise ValueError("RELEASE_SOURCE_FAMILY_NOT_ACTIVE_DEV")
    source_digest = family.logical_digest()
    body = asdict(family)
    body["asset_state"] = PRODUCT_RELEASE_STAGE
    body["source_active_dev_logical_digest"] = source_digest
    body["family_version"] = GENERIC_MECHANISM_FAMILY_VERSION
    body["release_logical_digest"] = "release-mechanism-family:" + digest_object(body)
    return body


def _mechanism_family_registry(
    families: Sequence[GenericMechanismFamily],
) -> dict[str, object]:
    projected = tuple(
        _release_family_projection(family)
        for family in sorted(families, key=lambda item: item.family_id)
    )
    if not projected:
        raise ValueError("RELEASE_MECHANISM_FAMILY_REQUIRED")
    return _content_bound(
        "release-mechanism-family-registry",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "family_count": len(projected),
            "families": projected,
            "included_non_release_asset_count": 0,
            "identity_router_count": 0,
            "fixed_trajectory_count": 0,
        },
    )


def _planner_configuration(
    initial_state: InitialStateBundle,
) -> dict[str, object]:
    program = initial_state.p_bundle.program
    return _content_bound(
        "release-planner-config",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "program_id": program.program_id,
            "representation_graph_id": program.representation_graph.graph_id,
            "model_graph_id": program.model_graph.graph_id,
            "candidate_graph_id": program.candidate_graph.graph_id,
            "planning_mode": "BOUNDED_RECEDING_HORIZON",
            "external_action_cardinality_per_cycle": 1,
            "reobserve_after_external_action": True,
            "effect_attribution_before_replan": True,
            "hds_authorization_required": True,
            "fixed_trajectory_playback": False,
            "identity_selected_plan": False,
        },
    )


def _resource_contract(
    initial_state: InitialStateBundle,
) -> dict[str, object]:
    resource = initial_state.p_bundle.program.resource_manifest
    return _content_bound(
        "release-resource-contract",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "action_budget_per_episode": ARC3_DEVELOPMENT_ACTION_BUDGET,
            "no_progress_limit": ARC3_PRODUCT_NO_PROGRESS_LIMIT,
            "known_success_action_ceiling": ARC3_KNOWN_SUCCESS_ACTION_CEILING,
            "official_sample_game_target": ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
            "official_sample_level_target": ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
            "p_ir": asdict(resource),
        },
    )


def _adapter_configuration(
    initial_state: InitialStateBundle,
) -> dict[str, object]:
    if initial_state.adapter_digest != PRODUCT_CAPABILITY_ADAPTER_DIGEST:
        raise ValueError("RELEASE_ADAPTER_DIGEST_MISMATCH")
    return _content_bound(
        "release-official-adapter-config",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "adapter_digest": initial_state.adapter_digest,
            "input_contract": "FrameDataRaw_PER_CYCLE",
            "output_contract": "ONE_CURRENTLY_LEGAL_GameAction_PER_CYCLE",
            "render_layer_policy": "ALL_LAYERS_TEMPORAL_COMPOSITE",
            "action_ids": tuple(range(8)),
            "pointer_action_id": 6,
            "pointer_payload_fields": ("x", "y"),
            "reobserve_after_action": True,
            "terminal_states": ("GAME_OVER", "WIN"),
            "orchestration_identity_to_decision_context": False,
        },
    )


def _release_provenance(
    *,
    initial_state: InitialStateBundle,
    active_descriptor_sha256: str,
    active_package_sha256: str,
    m3_closure_sha256: str,
    m3_closure_logical_sha256: str,
    excluded_candidate_sha256: str,
    families: Sequence[GenericMechanismFamily],
) -> dict[str, object]:
    return _content_bound(
        "release-provenance",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "product_bundle_id": PRODUCT_RELEASE_BUNDLE_ID,
            "source_asset_stage": ACTIVE_DEV_CAPABILITY_STAGE,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "m3_closure_status": "M3_COMPLETE",
            "m3_closure_sha256": _require_sha256(
                m3_closure_sha256,
                "RELEASE_M3_CLOSURE_SHA256_INVALID",
            ),
            "m3_closure_logical_sha256": _require_sha256(
                m3_closure_logical_sha256,
                "RELEASE_M3_CLOSURE_LOGICAL_SHA256_INVALID",
            ),
            "source_active_descriptor_sha256": _require_sha256(
                active_descriptor_sha256,
                "RELEASE_SOURCE_DESCRIPTOR_SHA256_INVALID",
            ),
            "source_active_package_sha256": _require_sha256(
                active_package_sha256,
                "RELEASE_SOURCE_PACKAGE_SHA256_INVALID",
            ),
            "source_initial_state_logical_digest": initial_state.logical_digest,
            "source_p_logical_digest": initial_state.p_bundle.logical_digest(),
            "source_j0_digest": "j0:" + digest_object(initial_state.j0),
            "source_m0_digest": "m0:" + digest_object(initial_state.m0),
            "source_mechanism_family_digests": tuple(
                family.logical_digest()
                for family in sorted(families, key=lambda item: item.family_id)
            ),
            "excluded_assets": (
                {
                    "classification": "UNACTIVATED_VERSION_CANDIDATE",
                    "sha256": _require_sha256(
                        excluded_candidate_sha256,
                        "RELEASE_EXCLUDED_CANDIDATE_SHA256_INVALID",
                    ),
                    "included": False,
                },
            ),
            "included_non_release_asset_count": 0,
            "identity_replay_finding_count": 0,
            "contains_teacher_runtime_data": False,
            "contains_fixed_action_sequence": False,
            "contains_literal_coordinate_table": False,
            "contains_identity_router": False,
            "contains_source_or_hidden_state": False,
            "contains_credentials": False,
        },
    )


def _release_manifest(
    *,
    initial_state: InitialStateBundle,
    payload_members: Mapping[str, bytes],
) -> dict[str, object]:
    entries = tuple(
        {
            "name": name,
            "sha256": _sha256(payload),
            "size_bytes": len(payload),
        }
        for name, payload in sorted(payload_members.items())
    )
    return _content_bound(
        "release-manifest",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "product_bundle_id": PRODUCT_RELEASE_BUNDLE_ID,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "initial_state_logical_digest": initial_state.logical_digest,
            "p_logical_digest": initial_state.p_bundle.logical_digest(),
            "j0_digest": "j0:" + digest_object(initial_state.j0),
            "m0_digest": "m0:" + digest_object(initial_state.m0),
            "payload_member_count": len(entries),
            "payload_members": entries,
            "one_product_bundle": True,
        },
    )


def _release_descriptor(
    *,
    package_payload: bytes,
    manifest: Mapping[str, object],
    initial_state: InitialStateBundle,
) -> dict[str, object]:
    return _content_bound(
        "release-descriptor",
        {
            "schema_version": PRODUCT_RELEASE_SCHEMA_VERSION,
            "product_bundle_id": PRODUCT_RELEASE_BUNDLE_ID,
            "asset_stage": PRODUCT_RELEASE_STAGE,
            "package_filename": PRODUCT_RELEASE_PACKAGE_FILENAME,
            "package_sha256": _sha256(package_payload),
            "package_size_bytes": len(package_payload),
            "manifest_logical_digest": manifest["content_digest"],
            "initial_state_logical_digest": initial_state.logical_digest,
            "p_logical_digest": initial_state.p_bundle.logical_digest(),
            "j0_digest": "j0:" + digest_object(initial_state.j0),
            "m0_digest": "m0:" + digest_object(initial_state.m0),
            "release_product_bundle_count": 1,
            "included_non_release_asset_count": 0,
            "identity_replay_finding_count": 0,
        },
    )


def compile_product_release_bundle(
    *,
    initial_state_descriptor_payload: bytes,
    initial_state_package_payload: bytes,
    active_descriptor_sha256: str,
    active_package_sha256: str,
    m3_closure_sha256: str,
    m3_closure_logical_sha256: str,
    excluded_candidate_sha256: str,
    mechanism_families: Sequence[GenericMechanismFamily] | None = None,
) -> tuple[dict[str, object], bytes]:
    """Freeze the M3-passed product state into one canonical release bundle."""

    if _sha256(initial_state_descriptor_payload) != active_descriptor_sha256:
        raise ValueError("RELEASE_SOURCE_DESCRIPTOR_BINDING_MISMATCH")
    if _sha256(initial_state_package_payload) != active_package_sha256:
        raise ValueError("RELEASE_SOURCE_PACKAGE_BINDING_MISMATCH")
    initial_state = load_product_initial_state_payloads(
        descriptor_payload=initial_state_descriptor_payload,
        package_payload=initial_state_package_payload,
    )
    if initial_state.package_bytes() != initial_state_package_payload:
        raise ValueError("RELEASE_INITIAL_STATE_RECOMPILATION_NOT_BYTE_IDENTICAL")
    if any(record.state != "ACTIVE" for record in initial_state.m0):
        raise ValueError("RELEASE_NON_ACTIVE_M0_RECORD_FORBIDDEN")
    if any(
        record.payload().get("asset_stage") in {"LOCAL_M", "PROBATION_DEV", "PROBATION"}
        for record in initial_state.m0
    ):
        raise ValueError("RELEASE_DEVELOPMENT_MEMORY_ASSET_FORBIDDEN")
    if initial_state.p_bundle.program.program_id != PRODUCT_CAPABILITY_PROGRAM_ID:
        raise ValueError("RELEASE_PRODUCT_PROGRAM_MISMATCH")
    selected_families = tuple(
        mechanism_families
        if mechanism_families is not None
        else active_dev_mechanism_families()
    )
    payload_members = {
        _INITIAL_DESCRIPTOR_MEMBER: initial_state_descriptor_payload,
        _INITIAL_PACKAGE_MEMBER: initial_state_package_payload,
        _TYPE_OPERATOR_REGISTRY_MEMBER: _json_member(
            _type_operator_registry(initial_state)
        ),
        _MECHANISM_REGISTRY_MEMBER: _json_member(
            _mechanism_family_registry(selected_families)
        ),
        _PLANNER_CONFIG_MEMBER: _json_member(_planner_configuration(initial_state)),
        _RESOURCE_CONTRACT_MEMBER: _json_member(_resource_contract(initial_state)),
        _ADAPTER_CONFIG_MEMBER: _json_member(_adapter_configuration(initial_state)),
        _PROVENANCE_MEMBER: _json_member(
            _release_provenance(
                initial_state=initial_state,
                active_descriptor_sha256=active_descriptor_sha256,
                active_package_sha256=active_package_sha256,
                m3_closure_sha256=m3_closure_sha256,
                m3_closure_logical_sha256=m3_closure_logical_sha256,
                excluded_candidate_sha256=excluded_candidate_sha256,
                families=selected_families,
            )
        ),
    }
    if set(payload_members) != set(_PAYLOAD_MEMBERS):
        raise RuntimeError("RELEASE_PAYLOAD_MEMBER_SET_INVALID")
    manifest = _release_manifest(
        initial_state=initial_state,
        payload_members=payload_members,
    )
    package_payload = build_canonical_zip(
        {**payload_members, _MANIFEST_MEMBER: _json_member(manifest)}
    )
    descriptor = _release_descriptor(
        package_payload=package_payload,
        manifest=manifest,
        initial_state=initial_state,
    )
    return descriptor, package_payload


@dataclass(frozen=True, slots=True)
class LoadedProductReleaseBundle:
    """Verified immutable release artifact and its runtime initial state."""

    descriptor: dict[str, object]
    manifest: dict[str, object]
    provenance: dict[str, object]
    type_operator_registry: dict[str, object]
    mechanism_family_registry: dict[str, object]
    planner_configuration: dict[str, object]
    resource_contract: dict[str, object]
    adapter_configuration: dict[str, object]
    initial_state: InitialStateBundle
    package_sha256: str
    package_size_bytes: int

    @property
    def logical_digest(self) -> str:
        return str(self.manifest["content_digest"])


def _json_object(payload: bytes, error: str) -> dict[str, object]:
    value = json.loads(payload)
    if not isinstance(value, Mapping):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}


def _payload_entry_map(manifest: Mapping[str, object]) -> dict[str, tuple[str, int]]:
    entries = manifest.get("payload_members")
    if not isinstance(entries, Sequence) or isinstance(
        entries, (str, bytes, bytearray)
    ):
        raise TypeError("RELEASE_MANIFEST_MEMBER_ENTRIES_INVALID")
    output: dict[str, tuple[str, int]] = {}
    for value in entries:
        if not isinstance(value, Mapping):
            raise TypeError("RELEASE_MANIFEST_MEMBER_ENTRY_INVALID")
        name = value.get("name")
        digest = value.get("sha256")
        size = value.get("size_bytes")
        if (
            not isinstance(name, str)
            or not isinstance(digest, str)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or name in output
        ):
            raise TypeError("RELEASE_MANIFEST_MEMBER_ENTRY_INVALID")
        output[name] = (digest, size)
    return output


def load_product_release_bundle_payloads(
    *,
    descriptor_payload: bytes,
    package_payload: bytes,
) -> LoadedProductReleaseBundle:
    """Fail closed while loading a release bundle from exact bytes."""

    descriptor = _verify_content_bound(
        _json_object(descriptor_payload, "RELEASE_DESCRIPTOR_INVALID"),
        namespace="release-descriptor",
        error="RELEASE_DESCRIPTOR_INVALID",
    )
    if (
        descriptor.get("schema_version") != PRODUCT_RELEASE_SCHEMA_VERSION
        or descriptor.get("product_bundle_id") != PRODUCT_RELEASE_BUNDLE_ID
        or descriptor.get("asset_stage") != PRODUCT_RELEASE_STAGE
        or descriptor.get("package_filename") != PRODUCT_RELEASE_PACKAGE_FILENAME
        or descriptor.get("package_sha256") != _sha256(package_payload)
        or descriptor.get("package_size_bytes") != len(package_payload)
        or descriptor.get("release_product_bundle_count") != 1
        or descriptor.get("included_non_release_asset_count") != 0
        or descriptor.get("identity_replay_finding_count") != 0
    ):
        raise ValueError("RELEASE_DESCRIPTOR_CONTRACT_INVALID")
    with zipfile.ZipFile(io.BytesIO(package_payload), mode="r") as archive:
        if set(archive.namelist()) != _ALL_MEMBERS:
            raise ValueError("RELEASE_PACKAGE_MEMBERS_INVALID")
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = _verify_content_bound(
        _json_object(members[_MANIFEST_MEMBER], "RELEASE_MANIFEST_INVALID"),
        namespace="release-manifest",
        error="RELEASE_MANIFEST_INVALID",
    )
    if (
        manifest.get("schema_version") != PRODUCT_RELEASE_SCHEMA_VERSION
        or manifest.get("product_bundle_id") != PRODUCT_RELEASE_BUNDLE_ID
        or manifest.get("asset_stage") != PRODUCT_RELEASE_STAGE
        or manifest.get("one_product_bundle") is not True
        or manifest.get("content_digest") != descriptor.get("manifest_logical_digest")
    ):
        raise ValueError("RELEASE_MANIFEST_CONTRACT_INVALID")
    entries = _payload_entry_map(manifest)
    if set(entries) != set(_PAYLOAD_MEMBERS) or len(entries) != manifest.get(
        "payload_member_count"
    ):
        raise ValueError("RELEASE_MANIFEST_MEMBER_SET_INVALID")
    for name, (digest, size) in entries.items():
        payload = members[name]
        if digest != _sha256(payload) or size != len(payload):
            raise ValueError("RELEASE_MEMBER_BINDING_MISMATCH:" + name)
    initial_state = load_product_initial_state_payloads(
        descriptor_payload=members[_INITIAL_DESCRIPTOR_MEMBER],
        package_payload=members[_INITIAL_PACKAGE_MEMBER],
    )
    provenance = _verify_content_bound(
        _json_object(members[_PROVENANCE_MEMBER], "RELEASE_PROVENANCE_INVALID"),
        namespace="release-provenance",
        error="RELEASE_PROVENANCE_INVALID",
    )
    type_registry = _verify_content_bound(
        _json_object(
            members[_TYPE_OPERATOR_REGISTRY_MEMBER],
            "RELEASE_TYPE_OPERATOR_REGISTRY_INVALID",
        ),
        namespace="release-type-operator-registry",
        error="RELEASE_TYPE_OPERATOR_REGISTRY_INVALID",
    )
    mechanism_registry = _verify_content_bound(
        _json_object(
            members[_MECHANISM_REGISTRY_MEMBER],
            "RELEASE_MECHANISM_REGISTRY_INVALID",
        ),
        namespace="release-mechanism-family-registry",
        error="RELEASE_MECHANISM_REGISTRY_INVALID",
    )
    planner = _verify_content_bound(
        _json_object(members[_PLANNER_CONFIG_MEMBER], "RELEASE_PLANNER_INVALID"),
        namespace="release-planner-config",
        error="RELEASE_PLANNER_INVALID",
    )
    resource = _verify_content_bound(
        _json_object(
            members[_RESOURCE_CONTRACT_MEMBER],
            "RELEASE_RESOURCE_CONTRACT_INVALID",
        ),
        namespace="release-resource-contract",
        error="RELEASE_RESOURCE_CONTRACT_INVALID",
    )
    adapter = _verify_content_bound(
        _json_object(
            members[_ADAPTER_CONFIG_MEMBER],
            "RELEASE_ADAPTER_CONFIG_INVALID",
        ),
        namespace="release-official-adapter-config",
        error="RELEASE_ADAPTER_CONFIG_INVALID",
    )
    if (
        manifest.get("initial_state_logical_digest") != initial_state.logical_digest
        or manifest.get("p_logical_digest") != initial_state.p_bundle.logical_digest()
        or manifest.get("j0_digest") != "j0:" + digest_object(initial_state.j0)
        or manifest.get("m0_digest") != "m0:" + digest_object(initial_state.m0)
        or descriptor.get("initial_state_logical_digest")
        != initial_state.logical_digest
        or provenance.get("asset_stage") != PRODUCT_RELEASE_STAGE
        or provenance.get("included_non_release_asset_count") != 0
        or provenance.get("identity_replay_finding_count") != 0
        or mechanism_registry.get("asset_stage") != PRODUCT_RELEASE_STAGE
        or mechanism_registry.get("included_non_release_asset_count") != 0
        or mechanism_registry.get("identity_router_count") != 0
        or mechanism_registry.get("fixed_trajectory_count") != 0
        or planner.get("fixed_trajectory_playback") is not False
        or planner.get("identity_selected_plan") is not False
        or resource.get("action_budget_per_episode") != ARC3_DEVELOPMENT_ACTION_BUDGET
        or adapter.get("adapter_digest") != initial_state.adapter_digest
        or type_registry.get("semantics_digest") != PIR_SEMANTICS_DIGEST
    ):
        raise ValueError("RELEASE_COMPONENT_CONTRACT_INVALID")
    return LoadedProductReleaseBundle(
        descriptor=descriptor,
        manifest=manifest,
        provenance=provenance,
        type_operator_registry=type_registry,
        mechanism_family_registry=mechanism_registry,
        planner_configuration=planner,
        resource_contract=resource,
        adapter_configuration=adapter,
        initial_state=initial_state,
        package_sha256=_sha256(package_payload),
        package_size_bytes=len(package_payload),
    )


def load_product_release_bundle(
    *,
    descriptor_path: Path,
    package_path: Path,
) -> LoadedProductReleaseBundle:
    """Load an explicitly selected release artifact pair from disk."""

    return load_product_release_bundle_payloads(
        descriptor_payload=descriptor_path.read_bytes(),
        package_payload=package_path.read_bytes(),
    )


@lru_cache(maxsize=1)
def load_default_product_release_bundle() -> LoadedProductReleaseBundle:
    """Load the one release artifact installed beside the runtime package."""

    directory = Path(__file__).resolve().parent / "bundles"
    return load_product_release_bundle(
        descriptor_path=directory / PRODUCT_RELEASE_DESCRIPTOR_FILENAME,
        package_path=directory / PRODUCT_RELEASE_PACKAGE_FILENAME,
    )


__all__ = [
    "PRODUCT_RELEASE_BUNDLE_ID",
    "PRODUCT_RELEASE_DESCRIPTOR_FILENAME",
    "PRODUCT_RELEASE_PACKAGE_FILENAME",
    "PRODUCT_RELEASE_SCHEMA_VERSION",
    "PRODUCT_RELEASE_STAGE",
    "LoadedProductReleaseBundle",
    "compile_product_release_bundle",
    "load_default_product_release_bundle",
    "load_product_release_bundle",
    "load_product_release_bundle_payloads",
]
