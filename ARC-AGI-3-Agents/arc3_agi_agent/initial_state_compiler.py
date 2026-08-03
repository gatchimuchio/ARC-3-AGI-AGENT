"""Canonical P/J0/M0 initial-state artifact and process-restart loader."""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .canonical_artifact import build_canonical_zip, canonical_json_bytes
from .generic_hds import HDSConfiguration
from .generic_memory import SemanticRecord
from .generic_session import CognitiveSession, create_cognitive_session
from .identity_boundary import IdentityBoundary
from .p_bundle import PBundle, p_bundle_from_package
from .schema import digest_object

INITIAL_STATE_SCHEMA_VERSION: Final = "arc3-initial-state-v1"
INITIAL_STATE_ALLOWED_MEMORY_KINDS: Final = frozenset(
    {
        "ACTION_EFFECT",
        "CONTRADICTION",
        "FAILURE_SIGNATURE",
        "GOAL_MODEL",
        "HAZARD_MODEL",
        "PRECONDITION",
        "PROCEDURE_CAPABILITY",
        "RELATION_SCHEMA",
        "STATE_VARIABLE",
        "TRANSITION_RULE",
        "UNCERTAINTY_MODEL",
        "WORLD_MODEL",
    }
)
_IDENTITY_VALUE = re.compile(r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)")


def _initial_state_digest(
    *,
    version: str,
    p_logical_digest: str,
    j0: HDSConfiguration,
    m0: Sequence[SemanticRecord],
    adapter_digest: str,
) -> str:
    return "initial-state-logical:" + digest_object(
        {
            "schema_version": INITIAL_STATE_SCHEMA_VERSION,
            "version": version,
            "p_logical_digest": p_logical_digest,
            "j0": j0,
            "m0": tuple(m0),
            "adapter_digest": adapter_digest,
        }
    )


@dataclass(frozen=True, slots=True)
class InitialStateBundle:
    version: str
    p_bundle: PBundle
    j0: HDSConfiguration
    m0: tuple[SemanticRecord, ...]
    adapter_digest: str
    logical_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.version or not self.adapter_digest:
            failures.append("INITIAL_STATE_METADATA_MISSING")
        failures.extend(self.p_bundle.validate())
        if self.p_bundle.manifest.lifecycle != "ACTIVE":
            failures.append("INITIAL_STATE_ACTIVE_P_REQUIRED")
        failures.extend(self.j0.validate())
        if self.m0 != tuple(sorted(self.m0, key=lambda item: item.memory_id)):
            failures.append("INITIAL_STATE_M0_ORDER_INVALID")
        if len({item.memory_id for item in self.m0}) != len(self.m0):
            failures.append("INITIAL_STATE_M0_DUPLICATE")
        boundary = IdentityBoundary()
        for record in self.m0:
            failures.extend(record.validate())
            if record.kind not in INITIAL_STATE_ALLOWED_MEMORY_KINDS:
                failures.append("INITIAL_STATE_M0_KIND_FORBIDDEN")
            if record.state not in {"ACTIVE", "PROBATION"}:
                failures.append("INITIAL_STATE_M0_STATE_FORBIDDEN")
            if any(
                marker in record.scope for marker in ("EPISODE_LOCAL", "LEVEL_LOCAL")
            ):
                failures.append("INITIAL_STATE_M0_SCOPE_FORBIDDEN")
            failures.extend(
                "INITIAL_STATE_M0_IDENTITY_TAINT:" + item
                for item in boundary.inspect_decision_context(record)
            )
            if _IDENTITY_VALUE.search(str(record)):
                failures.append("INITIAL_STATE_M0_IDENTITY_VALUE")
        expected = _initial_state_digest(
            version=self.version,
            p_logical_digest=self.p_bundle.logical_digest(),
            j0=self.j0,
            m0=self.m0,
            adapter_digest=self.adapter_digest,
        )
        if self.logical_digest != expected:
            failures.append("INITIAL_STATE_LOGICAL_DIGEST_MISMATCH")
        return tuple(sorted(set(failures)))

    def artifact_members(self) -> dict[str, bytes]:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return {
            "initial_state_manifest.json": canonical_json_bytes(
                {
                    "schema_version": INITIAL_STATE_SCHEMA_VERSION,
                    "version": self.version,
                    "p_logical_digest": self.p_bundle.logical_digest(),
                    "j0_digest": "j0:" + digest_object(self.j0),
                    "m0_digest": "m0:" + digest_object(self.m0),
                    "adapter_digest": self.adapter_digest,
                    "logical_digest": self.logical_digest,
                }
            ),
            "p_bundle.zip": self.p_bundle.package_bytes(),
            "j0.json": canonical_json_bytes(self.j0),
            "m0.json": canonical_json_bytes(self.m0),
        }

    def package_bytes(self) -> bytes:
        return build_canonical_zip(self.artifact_members())


@dataclass(frozen=True, slots=True)
class InitialStateCompiler:
    adapter_digest: str = "generic-adapter:arc3-v1"

    def compile(
        self,
        *,
        p_bundle: PBundle,
        j0: HDSConfiguration,
        memory_records: Sequence[SemanticRecord],
        version: str,
    ) -> InitialStateBundle:
        if not version:
            raise ValueError("INITIAL_STATE_VERSION_REQUIRED")
        selected = tuple(
            sorted(
                (
                    record
                    for record in memory_records
                    if record.kind in INITIAL_STATE_ALLOWED_MEMORY_KINDS
                    and record.state in {"ACTIVE", "PROBATION"}
                    and not any(
                        marker in record.scope
                        for marker in ("EPISODE_LOCAL", "LEVEL_LOCAL")
                    )
                ),
                key=lambda item: item.memory_id,
            )
        )
        bundle = InitialStateBundle(
            version=version,
            p_bundle=p_bundle,
            j0=j0,
            m0=selected,
            adapter_digest=self.adapter_digest,
            logical_digest=_initial_state_digest(
                version=version,
                p_logical_digest=p_bundle.logical_digest(),
                j0=j0,
                m0=selected,
                adapter_digest=self.adapter_digest,
            ),
        )
        failures = bundle.validate()
        if failures:
            raise ValueError(";".join(failures))
        return bundle


def _mapping(value: object, error: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(error)
    return value


def _int_field(value: Mapping[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError("INITIAL_STATE_INTEGER_FIELD_INVALID:" + key)
    return item


def _float_field(value: Mapping[str, object], key: str) -> float:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise TypeError("INITIAL_STATE_FLOAT_FIELD_INVALID:" + key)
    return float(item)


def _strings(value: object, error: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(error)
    return tuple(str(item) for item in value)


class _FrozenJSONMapping(Mapping[str, object]):
    """Immutable JSON mapping that preserves typed causal payload shape."""

    __slots__ = ("_items",)

    def __init__(self, items: Sequence[tuple[str, object]]) -> None:
        self._items = tuple(sorted(items))

    def __getitem__(self, key: str) -> object:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return _FrozenJSONMapping(
            tuple((str(key), _freeze_json(item)) for key, item in value.items())
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _payload_pairs(value: object) -> tuple[tuple[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("INITIAL_STATE_PAYLOAD_INVALID")
    output: list[tuple[str, object]] = []
    for item in value:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)):
            raise TypeError("INITIAL_STATE_PAYLOAD_PAIR_INVALID")
        pair = tuple(item)
        if len(pair) != 2:
            raise TypeError("INITIAL_STATE_PAYLOAD_PAIR_INVALID")
        output.append((str(pair[0]), _freeze_json(pair[1])))
    return tuple(output)


def _semantic_record_from_dict(
    value: Mapping[str, object],
) -> SemanticRecord:
    return SemanticRecord(
        memory_id=str(value["memory_id"]),
        kind=str(value["kind"]),
        statement=str(value["statement"]),
        semantic_tokens=_strings(
            value.get("semantic_tokens", ()),
            "INITIAL_STATE_RECORD_TOKENS_INVALID",
        ),
        relations=_strings(
            value.get("relations", ()),
            "INITIAL_STATE_RECORD_RELATIONS_INVALID",
        ),
        evidence=_strings(
            value.get("evidence", ()),
            "INITIAL_STATE_RECORD_EVIDENCE_INVALID",
        ),
        counter_evidence=_strings(
            value.get("counter_evidence", ()),
            "INITIAL_STATE_RECORD_COUNTER_INVALID",
        ),
        scope=_strings(
            value.get("scope", ()),
            "INITIAL_STATE_RECORD_SCOPE_INVALID",
        ),
        falsification_condition=str(value["falsification_condition"]),
        authority=str(value["authority"]),
        state=str(value["state"]),
        created_version=_int_field(value, "created_version"),
        updated_version=_int_field(value, "updated_version"),
        rollback_pointer=_int_field(value, "rollback_pointer"),
        payload_items=_payload_pairs(value.get("payload_items", ())),
    )


def _hds_configuration_from_dict(
    value: Mapping[str, object],
) -> HDSConfiguration:
    return HDSConfiguration(
        purpose=str(value["purpose"]),
        value_criteria=_strings(
            value.get("value_criteria", ()),
            "INITIAL_STATE_J0_VALUES_INVALID",
        ),
        risk_limit=_float_field(value, "risk_limit"),
        evidence_mode=str(value["evidence_mode"]),
        resource_budget=_int_field(value, "resource_budget"),
        stop_after_no_progress=_int_field(value, "stop_after_no_progress"),
        required_authorities=_strings(
            value.get("required_authorities", ()),
            "INITIAL_STATE_J0_AUTHORITIES_INVALID",
        ),
        projection_boundary=str(value["projection_boundary"]),
        local_min_support=_int_field(value, "local_min_support"),
        session_min_total_support=_int_field(value, "session_min_total_support"),
        session_min_distinct_episode_support=_int_field(
            value,
            "session_min_distinct_episode_support",
        ),
        active_confidence_ppm=_int_field(value, "active_confidence_ppm"),
        max_contradiction_ratio_ppm=_int_field(value, "max_contradiction_ratio_ppm"),
        max_hazard_for_execute=_int_field(value, "max_hazard_for_execute"),
    )


def initial_state_from_package(payload: bytes) -> InitialStateBundle:
    with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
        expected = {
            "initial_state_manifest.json",
            "p_bundle.zip",
            "j0.json",
            "m0.json",
        }
        if set(archive.namelist()) != expected:
            raise ValueError("INITIAL_STATE_PACKAGE_MEMBERS_INVALID")
        manifest = _mapping(
            json.loads(archive.read("initial_state_manifest.json")),
            "INITIAL_STATE_MANIFEST_INVALID",
        )
        p_bundle = p_bundle_from_package(archive.read("p_bundle.zip"))
        j0 = _hds_configuration_from_dict(
            _mapping(
                json.loads(archive.read("j0.json")),
                "INITIAL_STATE_J0_INVALID",
            )
        )
        m0_value = json.loads(archive.read("m0.json"))
        if not isinstance(m0_value, Sequence) or isinstance(
            m0_value, (str, bytes, bytearray)
        ):
            raise TypeError("INITIAL_STATE_M0_INVALID")
        m0 = tuple(
            _semantic_record_from_dict(_mapping(item, "INITIAL_STATE_RECORD_INVALID"))
            for item in m0_value
        )
        bundle = InitialStateBundle(
            version=str(manifest["version"]),
            p_bundle=p_bundle,
            j0=j0,
            m0=m0,
            adapter_digest=str(manifest["adapter_digest"]),
            logical_digest=str(manifest["logical_digest"]),
        )
    failures = bundle.validate()
    if failures:
        raise ValueError(";".join(failures))
    if bundle.package_bytes() != payload:
        raise ValueError("INITIAL_STATE_PACKAGE_REPRODUCTION_MISMATCH")
    return bundle


def restart_from_initial_state_package(
    payload: bytes,
    *,
    mode: str = "VALIDATION",
) -> CognitiveSession:
    initial = initial_state_from_package(payload)
    return create_cognitive_session(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        mode=mode,
        hds_configuration=initial.j0,
        initial_memory_records=initial.m0,
    )


__all__ = [
    "INITIAL_STATE_ALLOWED_MEMORY_KINDS",
    "INITIAL_STATE_SCHEMA_VERSION",
    "InitialStateBundle",
    "InitialStateCompiler",
    "initial_state_from_package",
    "restart_from_initial_state_package",
]
